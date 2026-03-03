"""Bill of Materials: links a finished product to its components with quantities (per unit)."""
from sqlalchemy import Column, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class BillOfMaterial(Base):
    """One line of a BoM: finished_product_id requires quantity_per_unit of component_id."""
    __tablename__ = "bill_of_materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    finished_product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    component_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity_per_unit = Column(Float, nullable=False)  # e.g. 50 (grams of Cocoa per 1 Dark Chocolate)

    __table_args__ = (
        UniqueConstraint("finished_product_id", "component_id", name="uq_bom_finished_component"),
    )

    finished_product = relationship("Product", foreign_keys=[finished_product_id], back_populates="bom_components")
    component = relationship("Product", foreign_keys=[component_id], back_populates="used_in")

    def __repr__(self) -> str:
        return (
            f"<BillOfMaterial(finished_product_id={self.finished_product_id}, "
            f"component_id={self.component_id}, qty={self.quantity_per_unit})>"
        )
