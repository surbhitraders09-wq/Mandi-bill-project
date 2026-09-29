from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class LogOut(BaseModel):
    id: int
    level: str
    message: str
    details: Optional[Any] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LogListResponse(BaseModel):
    items: List[LogOut]
    total: int
    limit: int
    offset: int
