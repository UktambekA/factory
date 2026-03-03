"""Production execution: validate stock and apply inventory changes in one transaction."""
from datetime import datetime, timezone
from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import transactional_session
from app.models import BillOfMaterial, ManufacturingOrder, Product


class InsufficientStockError(Exception):
    """Raised when producing would result in negative stock."""
    def __init__(self, message: str, shortfalls: List[Tuple[str, float, float]]):
        super().__init__(message)
        self.shortfalls = shortfalls  # (component_name, required, available)


def produce_order(mo_id: int) -> None:
    """
    Execute a manufacturing order in a single atomic transaction.
    - Validates that all required ingredients have enough stock.
    - If validation fails: raises InsufficientStockError, no DB changes.
    - If validation passes: deducts components, adds finished product, marks MO as produced.
    """
    with transactional_session() as db:
        mo = (
            db.execute(
                select(ManufacturingOrder)
                .options(
                    selectinload(ManufacturingOrder.product).selectinload(Product.bom_components).selectinload(BillOfMaterial.component),
                )
                .where(ManufacturingOrder.id == mo_id)
            )
        ).scalar_one_or_none()

        if not mo:
            raise ValueError(f"Manufacturing order {mo_id} not found.")
        if mo.status == "produced":
            raise ValueError("This order has already been produced.")
        if mo.quantity <= 0:
            raise ValueError("Order quantity must be positive.")

        product = mo.product
        if not product.bom_components:
            raise ValueError(f"Product {product.name} has no Bill of Materials defined.")

        shortfalls: List[Tuple[str, float, float]] = []
        for bom_line in product.bom_components:
            required = bom_line.quantity_per_unit * mo.quantity
            available = bom_line.component.stock_on_hand
            if available < required:
                shortfalls.append((bom_line.component.name, required, available))

        if shortfalls:
            parts = [f"{name}: need {req:.1f}g, have {avail:.1f}g" for name, req, avail in shortfalls]
            raise InsufficientStockError(
                "Insufficient stock to produce: " + "; ".join(parts),
                shortfalls=shortfalls,
            )

        # Deduct components (prevent negative stock by design)
        for bom_line in product.bom_components:
            needed = bom_line.quantity_per_unit * mo.quantity
            comp = bom_line.component
            comp.stock_on_hand -= needed
            if comp.stock_on_hand < 0:
                raise InsufficientStockError(
                    f"Stock would go negative for {comp.name}.",
                    shortfalls=[(comp.name, needed, comp.stock_on_hand + needed)],
                )
            db.add(comp)

        # Add finished product
        product.stock_on_hand += mo.quantity
        db.add(product)

        # Mark order as produced
        mo.status = "produced"
        mo.produced_at = datetime.now(timezone.utc)
        db.add(mo)
