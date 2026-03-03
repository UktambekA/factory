"""FastAPI routes for products, BoM, manufacturing orders, and produce action."""
import json
from urllib.parse import quote, unquote

from typing import List

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import BillOfMaterial, ManufacturingOrder, Product
from app.services.produce_service import InsufficientStockError, produce_order

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ----- Web UI (HTML/Bootstrap) -----

@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    """Home: stock levels and produce form."""
    products = db.execute(select(Product).order_by(Product.product_type, Product.name)).scalars().all()
    orders = (
        db.execute(
            select(ManufacturingOrder)
            .options(selectinload(ManufacturingOrder.product))
            .order_by(ManufacturingOrder.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    draft_count = sum(1 for o in orders if o.status == "draft")
    low_stock = [p for p in products if p.product_type == "ingredient" and p.stock_on_hand < 100]
    error = request.query_params.get("error")
    if error:
        error = unquote(error)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "products": products,
            "orders": orders,
            "draft_count": draft_count,
            "low_stock_count": len(low_stock),
            "produced": request.query_params.get("produced"),
            "error": error,
        },
    )


@router.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request, db: Session = Depends(get_db)):
    """List manufacturing orders and create new one."""
    orders = (
        db.execute(
            select(ManufacturingOrder)
            .options(selectinload(ManufacturingOrder.product))
            .order_by(ManufacturingOrder.created_at.desc())
        )
    ).scalars().all()
    finished_products = db.execute(
        select(Product).where(Product.product_type == "finished_good").order_by(Product.name)
    ).scalars().all()
    bom_data = {
        p.id: [
            {
                "name": b.component.name,
                "qty_per_unit": b.quantity_per_unit,
                "stock": b.component.stock_on_hand,
            }
            for b in p.bom_components
        ]
        for p in finished_products
    }
    error = request.query_params.get("error")
    if error:
        error = unquote(error)
    return templates.TemplateResponse(
        "orders.html",
        {
            "request": request,
            "orders": orders,
            "finished_products": finished_products,
            "bom_json": json.dumps(bom_data),
            "produced": request.query_params.get("produced"),
            "error": error,
        },
    )


@router.post("/orders")
def create_order(
    product_id: int = Form(...),
    quantity: float = Form(...),
    db: Session = Depends(get_db),
):
    """Create a draft manufacturing order."""
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive.")
    product = db.get(Product, product_id)
    if not product or product.product_type != "finished_good":
        raise HTTPException(status_code=404, detail="Finished product not found.")
    mo = ManufacturingOrder(product_id=product_id, quantity=quantity, status="draft")
    db.add(mo)
    db.commit()
    db.refresh(mo)
    return RedirectResponse(url="/orders", status_code=303)


@router.get("/orders/{mo_id}/edit", response_class=HTMLResponse)
def edit_order_page(mo_id: int, request: Request, db: Session = Depends(get_db)):
    """Show edit form for a manufacturing order."""
    order = db.get(ManufacturingOrder, mo_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    finished_products = db.execute(
        select(Product).where(Product.product_type == "finished_good").order_by(Product.name)
    ).scalars().all()
    error = request.query_params.get("error")
    if error:
        error = unquote(error)
    return templates.TemplateResponse(
        "order_edit.html",
        {"request": request, "order": order, "finished_products": finished_products, "error": error},
    )


@router.post("/orders/{mo_id}/edit")
def update_order(
    mo_id: int,
    product_id: int = Form(...),
    quantity: float = Form(...),
    db: Session = Depends(get_db),
):
    """Update product and quantity of a manufacturing order."""
    order = db.get(ManufacturingOrder, mo_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.status == "produced":
        raise HTTPException(status_code=400, detail="Cannot edit a produced order.")
    if quantity <= 0:
        return RedirectResponse(
            url=f"/orders/{mo_id}/edit?error=" + quote("Quantity must be positive."),
            status_code=303,
        )
    product = db.get(Product, product_id)
    if not product or product.product_type != "finished_good":
        return RedirectResponse(
            url=f"/orders/{mo_id}/edit?error=" + quote("Invalid product selected."),
            status_code=303,
        )
    order.product_id = product_id
    order.quantity = quantity
    db.commit()
    return RedirectResponse(url="/orders", status_code=303)


@router.post("/orders/{mo_id}/produce")
def execute_produce(mo_id: int, request: Request):
    """Trigger produce for a manufacturing order. Atomic transaction."""
    try:
        produce_order(mo_id)
        return RedirectResponse(url="/orders?produced=1", status_code=303)
    except (InsufficientStockError, ValueError) as e:
        return RedirectResponse(url="/orders?error=" + quote(str(e)), status_code=303)


# ----- Product Management -----

@router.get("/products", response_class=HTMLResponse)
def products_page(request: Request, db: Session = Depends(get_db)):
    """List all products."""
    products = db.execute(select(Product).order_by(Product.product_type, Product.name)).scalars().all()
    error = request.query_params.get("error")
    if error:
        error = unquote(error)
    return templates.TemplateResponse(
        "products.html",
        {
            "request": request,
            "products": products,
            "created": request.query_params.get("created"),
            "error": error,
        },
    )


@router.get("/products/new", response_class=HTMLResponse)
def new_product_page(request: Request):
    """Form to add a new finished good with inline BoM."""
    error = request.query_params.get("error")
    if error:
        error = unquote(error)
    return templates.TemplateResponse(
        "product_new.html",
        {"request": request, "error": error},
    )


@router.post("/products/ingredient")
def restock_ingredient(
    name: str = Form(...),
    amount: float = Form(0.0),
    db: Session = Depends(get_db),
):
    """Restock existing ingredient or create a new one if name not found."""
    name = name.strip()
    if not name:
        return RedirectResponse(url="/products?error=" + quote("Name cannot be empty."), status_code=303)
    if amount < 0:
        return RedirectResponse(url="/products?error=" + quote("Amount cannot be negative."), status_code=303)
    existing = db.execute(
        select(Product).where(Product.name == name, Product.product_type == "ingredient")
    ).scalar_one_or_none()
    if existing:
        existing.stock_on_hand += amount
    else:
        db.add(Product(name=name, product_type="ingredient", stock_on_hand=amount))
    db.commit()
    return RedirectResponse(url="/products?created=1", status_code=303)


@router.post("/products")
def create_product(
    name: str = Form(...),
    component_names: List[str] = Form([]),
    quantities: List[float] = Form([]),
    db: Session = Depends(get_db),
):
    """Create a new finished good; finds or creates each ingredient by name."""
    name = name.strip()
    if not name:
        return RedirectResponse(url="/products/new?error=" + quote("Name cannot be empty."), status_code=303)
    existing = db.execute(select(Product).where(Product.name == name)).scalar_one_or_none()
    if existing:
        return RedirectResponse(url="/products/new?error=" + quote(f"'{name}' already exists."), status_code=303)
    product = Product(name=name, product_type="finished_good", stock_on_hand=0.0)
    db.add(product)
    db.flush()
    for comp_name, qty in zip(component_names, quantities):
        comp_name = comp_name.strip()
        if not comp_name or qty <= 0:
            continue
        ingredient = db.execute(
            select(Product).where(Product.name == comp_name, Product.product_type == "ingredient")
        ).scalar_one_or_none()
        if not ingredient:
            ingredient = Product(name=comp_name, product_type="ingredient", stock_on_hand=0.0)
            db.add(ingredient)
            db.flush()
        db.add(BillOfMaterial(finished_product_id=product.id, component_id=ingredient.id, quantity_per_unit=qty))
    db.commit()
    return RedirectResponse(url="/products?created=1", status_code=303)


@router.get("/products/{product_id}/bom", response_class=HTMLResponse)
def product_bom_page(product_id: int, request: Request, db: Session = Depends(get_db)):
    """Manage Bill of Materials for a finished product."""
    product = db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.bom_components).selectinload(BillOfMaterial.component))
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    if product.product_type != "finished_good":
        raise HTTPException(status_code=400, detail="BoM is only for finished products.")
    ingredients = db.execute(
        select(Product).where(Product.product_type == "ingredient").order_by(Product.name)
    ).scalars().all()
    used_ids = {b.component_id for b in product.bom_components}
    available_ingredients = [i for i in ingredients if i.id not in used_ids]
    error = request.query_params.get("error")
    if error:
        error = unquote(error)
    return templates.TemplateResponse(
        "product_bom.html",
        {
            "request": request,
            "product": product,
            "available_ingredients": available_ingredients,
            "created": request.query_params.get("created"),
            "error": error,
        },
    )


@router.post("/products/{product_id}/bom")
def add_bom_line(
    product_id: int,
    component_id: int = Form(...),
    quantity_per_unit: float = Form(...),
    db: Session = Depends(get_db),
):
    """Add a component to a product's BoM."""
    product = db.get(Product, product_id)
    if not product or product.product_type != "finished_good":
        raise HTTPException(status_code=404, detail="Finished product not found.")
    component = db.get(Product, component_id)
    if not component or component.product_type != "ingredient":
        return RedirectResponse(
            url=f"/products/{product_id}/bom?error=" + quote("Invalid ingredient selected."),
            status_code=303,
        )
    if quantity_per_unit <= 0:
        return RedirectResponse(
            url=f"/products/{product_id}/bom?error=" + quote("Quantity must be positive."),
            status_code=303,
        )
    existing = db.execute(
        select(BillOfMaterial).where(
            BillOfMaterial.finished_product_id == product_id,
            BillOfMaterial.component_id == component_id,
        )
    ).scalar_one_or_none()
    if existing:
        return RedirectResponse(
            url=f"/products/{product_id}/bom?error=" + quote("This ingredient is already in the BoM."),
            status_code=303,
        )
    bom = BillOfMaterial(
        finished_product_id=product_id,
        component_id=component_id,
        quantity_per_unit=quantity_per_unit,
    )
    db.add(bom)
    db.commit()
    return RedirectResponse(url=f"/products/{product_id}/bom", status_code=303)


@router.post("/products/{product_id}/bom/{bom_id}/delete")
def delete_bom_line(product_id: int, bom_id: int, db: Session = Depends(get_db)):
    """Remove a component from a product's BoM."""
    bom = db.get(BillOfMaterial, bom_id)
    if not bom or bom.finished_product_id != product_id:
        raise HTTPException(status_code=404, detail="BoM line not found.")
    db.delete(bom)
    db.commit()
    return RedirectResponse(url=f"/products/{product_id}/bom", status_code=303)


# ----- Optional JSON API -----

@router.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    """Summary stats for navbar badge."""
    from sqlalchemy import func as sqlfunc
    draft_count = db.execute(
        select(sqlfunc.count()).select_from(ManufacturingOrder).where(ManufacturingOrder.status == "draft")
    ).scalar()
    return {"draft_count": draft_count}


@router.get("/api/products")
def list_products(db: Session = Depends(get_db)):
    """List all products with stock."""
    products = db.execute(select(Product).order_by(Product.name)).scalars().all()
    return [{"id": p.id, "name": p.name, "type": p.product_type, "stock_on_hand": p.stock_on_hand} for p in products]


@router.get("/api/orders")
def list_orders(db: Session = Depends(get_db)):
    """List manufacturing orders."""
    orders = (
        db.execute(
            select(ManufacturingOrder).options(selectinload(ManufacturingOrder.product)).order_by(ManufacturingOrder.created_at.desc())
        )
    ).scalars().all()
    return [
        {
            "id": o.id,
            "product_id": o.product_id,
            "product_name": o.product.name,
            "quantity": o.quantity,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]
