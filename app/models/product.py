"""Product model: ingredients and finished goods with stock on hand."""
from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class ProductType:
    """Product classification for MRP."""
    INGREDIENT = "ingredient"
    FINISHED_GOOD = "finished_good"


class Product(Base):
    """A product (ingredient or finished good) with name and stock (in grams for raw, units for finished)."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    product_type = Column(String(32), nullable=False)  # ingredient | finished_good
    stock_on_hand = Column(Float, nullable=False, default=0.0)

    # As a finished good: list of components (BoM lines)
    bom_components = relationship(
        "BillOfMaterial",
        foreign_keys="BillOfMaterial.finished_product_id",
        back_populates="finished_product",
        lazy="selectin",
    )
    # As a component: list of finished products that use this ingredient
    used_in = relationship(
        "BillOfMaterial",
        foreign_keys="BillOfMaterial.component_id",
        back_populates="component",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name={self.name!r}, type={self.product_type}, stock={self.stock_on_hand})>"
