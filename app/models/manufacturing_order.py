"""Manufacturing Order: request to produce a quantity of a finished product."""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ManufacturingOrder(Base):
    """Order to produce a given quantity of a finished product. Status: draft | produced | failed."""
    __tablename__ = "manufacturing_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Float, nullable=False)  # number of units to produce
    status = Column(String(32), nullable=False, default="draft")  # draft | produced | failed
    error_message = Column(String(512), nullable=True)  # set when status = failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    produced_at = Column(DateTime(timezone=True), nullable=True)

    product = relationship("Product", backref="manufacturing_orders")

    def __repr__(self) -> str:
        return f"<ManufacturingOrder(id={self.id}, product_id={self.product_id}, qty={self.quantity}, status={self.status})>"
