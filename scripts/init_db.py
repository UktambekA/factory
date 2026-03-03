"""Create all tables in the Choco_factory database. Run from project root: python -m scripts.init_db"""
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, engine
# Import models so they register with Base.metadata
from app.models import BillOfMaterial, ManufacturingOrder, Product  # noqa: F401

def main():
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    main()
