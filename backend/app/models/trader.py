from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Trader(Base):
    __tablename__ = "traders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(15), nullable=True, unique=True, index=True)
    pan: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    license_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(15), nullable=True, index=True)
    commission_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Trader(id={self.id}, name={self.name})>"
