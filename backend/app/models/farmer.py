from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Farmer(Base):
    __tablename__ = "farmers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    aadhaar: Mapped[str] = mapped_column(String(12), nullable=False, unique=True, index=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(15), nullable=True, index=True)
    village_id: Mapped[Optional[int]] = mapped_column(ForeignKey("villages.id"), nullable=True, index=True)
    land_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ifsc_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Farmer(id={self.id}, name={self.name})>"
