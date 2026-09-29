from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class BillBase(BaseModel):
    trader_name: str
    trader_id: Optional[str] = None
    bill_number: str
    commodity: str
    date: Optional[datetime] = None
    vehicle_number: Optional[str] = None
    weight: float = 0
    rate: Optional[float] = None
    gross_amount: float = 0
    hammali_rate: float = 12.05
    hammali_amount: float = 0
    total_amount: float = 0


class BillOut(BillBase):
    id: int
    account_holder: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    payment_alert_triggered: bool = False
    printed: bool = False
    printed_at: Optional[datetime] = None
    printed_by: Optional[str] = None
    raw_data: Optional[Any] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BillListResponse(BaseModel):
    items: List[BillOut]
    total: int
    limit: int
    offset: int


class BillPaymentUpdate(BaseModel):
    account_holder: str = ""
    bank_name: str = ""
    account_number: str = ""
    ifsc_code: str = ""
