from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TraderBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    gstin: Optional[str] = Field(None, max_length=15)
    pan: Optional[str] = Field(None, max_length=10)
    license_no: Optional[str] = Field(None, max_length=100)
    mobile: Optional[str] = Field(None, max_length=15)
    commission_rate: float = 0.0


class TraderCreate(TraderBase):
    pass


class TraderUpdate(BaseModel):
    name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    license_no: Optional[str] = None
    mobile: Optional[str] = None
    commission_rate: Optional[float] = None


class TraderOut(TraderBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TraderListResponse(BaseModel):
    items: List[TraderOut]
    total: int
    limit: int
    offset: int
