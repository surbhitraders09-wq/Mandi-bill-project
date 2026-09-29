from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    old_value: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<ActivityLog(id={self.id}, action={self.action})>"
