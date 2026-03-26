from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class ShopModel(Base):
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    rating = Column(Float, default=5.0)          # room for future assignment logic
    capacity = Column(Integer, default=20)        # room for future assignment logic

    invoices = relationship("InvoiceModel", back_populates="shop", cascade="all, delete-orphan")


class InvoiceModel(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_code = Column(String, unique=True, nullable=False)   # e.g. FC-20250611-1234
    customer_name = Column(String, nullable=False)
    order_prompt = Column(Text, nullable=False)                  # the raw user message
    bill_json = Column(Text, nullable=False)                     # full bill as JSON string
    grand_total = Column(Float, nullable=False)
    status = Column(String, default="queued")                    # queued | serving | done
    created_at = Column(DateTime, default=datetime.utcnow)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=True)

    shop = relationship("ShopModel", back_populates="invoices")
