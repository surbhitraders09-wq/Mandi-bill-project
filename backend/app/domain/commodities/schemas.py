from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class CommodityBase(BaseModel):
    name: str
    code: Optional[str] = None
    unit: str = "quintal"


class CommodityCreate(CommodityBase):
    pass


class CommodityUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    unit: Optional[str] = None


class CommodityOut(CommodityBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CommodityListResponse(BaseModel):
    items: List[CommodityOut]
    total: int
    limit: int
    offset: int
