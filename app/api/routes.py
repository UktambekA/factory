"""FastAPI routes for products, BoM, manufacturing orders, and produce action."""
from urllib.parse import quote, unquote

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
    error = request.query_params.get("error")
    if error:
        error = unquote(error)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "products": products, "orders": orders, "produced": request.query_params.get("produced"), "error": error},
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
    return templates.TemplateResponse(
        "orders.html",
        {"request": request, "orders": orders, "finished_products": finished_products},
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
        return RedirectResponse(url="/?produced=1", status_code=303)
    except (InsufficientStockError, ValueError) as e:
        return RedirectResponse(url="/?error=" + quote(str(e)), status_code=303)


# ----- Optional JSON API -----

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
