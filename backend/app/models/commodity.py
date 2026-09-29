from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Commodity(Base):
    __tablename__ = "commodities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=True, unique=True, index=True)
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="quintal")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Commodity(id={self.id}, name={self.name})>"
