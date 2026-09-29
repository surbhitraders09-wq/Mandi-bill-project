from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FarmerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    aadhaar: str = Field(..., min_length=12, max_length=12)
    mobile: Optional[str] = Field(None, max_length=15)
    village_id: Optional[int] = None
    land_area: Optional[float] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None


class FarmerCreate(FarmerBase):
    pass


class FarmerUpdate(BaseModel):
    name: Optional[str] = None
    aadhaar: Optional[str] = None
    mobile: Optional[str] = None
    village_id: Optional[int] = None
    land_area: Optional[float] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None


class FarmerOut(FarmerBase):
    id: int
    village_name: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FarmerListResponse(BaseModel):
    items: List[FarmerOut]
    total: int
    limit: int
    offset: int
