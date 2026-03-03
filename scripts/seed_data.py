"""Seed products and Bill of Materials. Run after init_db: python -m scripts.seed_data"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import BillOfMaterial, Product
from sqlalchemy import select, func

# Dark Chocolate: 50g Cocoa, 20g Sugar per 1 unit
PRODUCTS = [
    {"name": "Cocoa", "product_type": "ingredient", "stock_on_hand": 1000.0},
    {"name": "Sugar", "product_type": "ingredient", "stock_on_hand": 500.0},
    {"name": "Dark Chocolate", "product_type": "finished_good", "stock_on_hand": 0.0},
]
BOM = [
    # (finished_name, component_name, quantity_per_unit)
    ("Dark Chocolate", "Cocoa", 50.0),
    ("Dark Chocolate", "Sugar", 20.0),
]


def main():
    db = SessionLocal()
    try:
        count = db.execute(select(func.count(Product.id))).scalar() or 0
        if count > 0:
            print("Products already exist. Skipping seed.")
            return
        # Create products
        name_to_id = {}
        for p in PRODUCTS:
            prod = Product(**p)
            db.add(prod)
            db.flush()
            name_to_id[prod.name] = prod.id
        # Create BoM
        for finished_name, component_name, qty in BOM:
            bom_line = BillOfMaterial(
                finished_product_id=name_to_id[finished_name],
                component_id=name_to_id[component_name],
                quantity_per_unit=qty,
            )
            db.add(bom_line)
        db.commit()
        print("Seed data created: Cocoa (1000g), Sugar (500g), Dark Chocolate (0). BoM: 50g Cocoa + 20g Sugar per unit.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
