from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trader_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    trader_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    bill_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    commodity: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    vehicle_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross_amount: Mapped[float] = mapped_column(Float, nullable=False)
    hammali_rate: Mapped[float] = mapped_column(Float, nullable=False, default=12.05)
    hammali_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    segment: Mapped[str] = mapped_column(String(20), nullable=False, default="trader")
    commodity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("commodities.id"), nullable=True, index=True
    )
    farmer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("farmers.id"), nullable=True, index=True
    )
    account_holder: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ifsc_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    payment_alert_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    printed: Mapped[bool] = mapped_column(Boolean, default=False)
    printed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    printed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    raw_data: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Bill(id={self.id}, trader={self.trader_name}, bill={self.bill_number})>"
