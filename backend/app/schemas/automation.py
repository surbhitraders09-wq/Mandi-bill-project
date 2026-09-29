from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StateInfo(BaseModel):
    state: str
    busy: bool
    found_bills: int
    current_bill_id: Optional[int] = None
    show_captcha: bool = False
    progress: str = ""
    progress_events: List[Dict[str, str]] = []


class TodayBill(BaseModel):
    index: int
    auction_id: str = ""
    auction_date: str = ""
    farmer_name: str = ""
    farmer_id: str = ""
    farmer_mobile: str = ""
    village: str = ""
    comm_group: str = ""
    commodity: str = ""
    variety: str = ""
    weight: float = 0.0
    rate: float = 0.0
    gross_amount: float = 0.0
    hammali_rate: float = 12.05
    hammali_amount: float = 0.0
    toul_rate: float = 0.0
    toul_amount: float = 0.0
    payable: float = 0.0
    gatepass_id: str = ""
    gatepass_date: str = ""
    grade: str = ""
    mandi: str = ""
    trader_id: str = ""
    firm: str = ""


class TodayBillsResponse(BaseModel):
    state: str
    date: str
    bills: List[TodayBill] = []


class SummaryRequest(BaseModel):
    from_date: str = Field(..., pattern=r"^\d{2}-\d{2}-\d{4}$")
    to_date: str = Field(..., pattern=r"^\d{2}-\d{2}-\d{4}$")


class SummaryCropRow(BaseModel):
    commodity: str
    total_weight: float = 0.0
    total_amount: float = 0.0
    avg_rate: float = 0.0


class SummaryStockRow(BaseModel):
    commodity: str
    total_weight: float = 0.0


class SummaryMandiFee(BaseModel):
    total_bills: float = 0.0
    total_quantity: float = 0.0
    mandi_fee: float = 0.0
    nirashrit_fee: float = 0.0


class SummaryResponse(BaseModel):
    state: str
    date_range: Dict[str, str] = {}
    tax_paid_stock: List[SummaryStockRow] = []
    crops: List[SummaryCropRow] = []
    soyabean: Optional[SummaryCropRow] = None
    mandi_fee_summary: Optional[SummaryMandiFee] = None
    mandi_balance: float = 0.0
    found_bills: int = 0


class CaptchaImageResponse(BaseModel):
    image: Optional[str] = None
    state: str


class CaptchaSubmitRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50)


class PrintRequest(BaseModel):
    bill_id: int = Field(..., ge=1)
    printed_by: str = "system"


class PrintAnalysedRequest(BaseModel):
    auction_id: str = Field(..., min_length=1)
    printed_by: str = "system"
    hammali_rate: float = Field(default=12.05, ge=0)
    toul_rate: float = Field(default=0.0, ge=0)


class PrintPortalRequest(BaseModel):
    auction_id: str = Field(..., min_length=1)
    hammali_rate: float = Field(default=12.05, ge=0)
    hammali_amount: float = Field(default=0.0, ge=0)
    toul_rate: float = Field(default=0.0, ge=0)


class PrintUrlRequest(BaseModel):
    url: str = Field(..., min_length=10)


class PrintResponse(BaseModel):
    state: str
    printed: bool


class PaymentInfoRequest(BaseModel):
    bill_id: int = Field(..., ge=1)
    account_holder: str = ""
    bank_name: str = ""
    account_number: str = ""
    ifsc_code: str = ""


class SuccessResponse(BaseModel):
    success: bool
    message: str = ""
    state: Optional[str] = None


class LogEntry(BaseModel):
    id: int
    level: str
    message: str
    details: Optional[Any] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Reports ----------

class GatepassRow(BaseModel):
    gatepass_id: str = ""
    trader_name: str = ""
    commodity: str = ""
    weight: str = "0"
    taul_status: str = ""
    payment_status: str = ""
    mobile_no: str = ""
    tol_pending: bool = False


class ReportsResponse(BaseModel):
    state: str
    date: str
    total_gatepasses: int = 0
    tol_pending_count: int = 0
    gatepasses: List[GatepassRow] = []


