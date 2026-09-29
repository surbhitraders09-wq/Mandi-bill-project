from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class VillageBase(BaseModel):
    name: str
    block: Optional[str] = None
    district: Optional[str] = None


class VillageCreate(VillageBase):
    pass


class VillageUpdate(BaseModel):
    name: Optional[str] = None
    block: Optional[str] = None
    district: Optional[str] = None


class VillageOut(VillageBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class VillageListResponse(BaseModel):
    items: List[VillageOut]
    total: int
    limit: int
    offset: int
