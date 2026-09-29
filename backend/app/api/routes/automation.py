from typing import Any, Dict

from fastapi import APIRouter

from app.core.state_machine import AutomationState
from app.exceptions import AutomationError
from app.schemas.automation import (
    CaptchaImageResponse,
    CaptchaSubmitRequest,
    GatepassRow,
    PaymentInfoRequest,
    PrintAnalysedRequest,
    PrintPortalRequest,
    PrintRequest,
    PrintResponse,
    PrintUrlRequest,
    ReportsResponse,
    StateInfo,
    SuccessResponse,
    SummaryRequest,
    SummaryResponse,
    TodayBill,
    TodayBillsResponse,
)
from app.services.automation_service import AutomationService

router = APIRouter(prefix="/api/automation", tags=["automation"])

service = AutomationService.get_instance()


def _state_info() -> StateInfo:
    return StateInfo(
        state=service.state,
        busy=service.state not in (AutomationState.IDLE.value, AutomationState.ERROR.value),
        found_bills=len(service.found_bills),
        current_bill_id=(service.current_bill_data or {}).get("db_id"),
        show_captcha=(
            service.state == AutomationState.AWAITING_CAPTCHA.value
            or service._captcha_fails >= 5
        ),
        progress=service._progress,
        progress_events=service.progress_events,
    )


@router.get("/state", response_model=StateInfo)
async def get_state() -> StateInfo:
    return _state_info()


@router.post("/todays-bills", response_model=TodayBillsResponse)
async def todays_bills() -> TodayBillsResponse:
    from datetime import datetime

    bills = await service.search_todays_bills()
    return TodayBillsResponse(
        state=service.state,
        date=datetime.now().strftime("%d-%m-%Y"),
        bills=[TodayBill(**b) for b in bills],
    )


@router.post("/summary", response_model=SummaryResponse)
async def summary(payload: SummaryRequest) -> SummaryResponse:
    data = await service.search_summary(
        from_date=payload.from_date, to_date=payload.to_date
    )
    return SummaryResponse(**data)


@router.post("/print-analysed", response_model=PrintResponse)
async def print_analysed_bill(payload: PrintAnalysedRequest) -> PrintResponse:
    """Print a locally analysed bill (search-today flow). Does not write to portal."""
    bill = next(
        (b for b in service.found_bills if b.get("auction_id") == payload.auction_id),
        None,
    )
    if bill is None:
        raise AutomationError(f"Bill auction id {payload.auction_id} not in current results")
    from app.services.pages.anubandh_datewise_page import AnubandhDateWisePage

    bill = AnubandhDateWisePage.annotate(
        bill, hammali_rate=payload.hammali_rate, toul_rate=payload.toul_rate
    )
    printed = await service.print_analysed_bill(bill, payload.printed_by)
    return PrintResponse(state=service.state, printed=printed)


@router.get("/captcha", response_model=CaptchaImageResponse)
async def get_captcha() -> CaptchaImageResponse:
    data = await service.get_captcha_image()
    return CaptchaImageResponse(image=(data or {}).get("image"), state=service.state)


@router.post("/captcha", response_model=SuccessResponse)
async def submit_captcha(payload: CaptchaSubmitRequest) -> SuccessResponse:
    ok = await service.submit_manual_captcha(payload.text)
    if not ok:
        raise AutomationError("No active CAPTCHA request")
    return SuccessResponse(success=True, message="CAPTCHA submitted", state=service.state)


@router.post("/print", response_model=PrintResponse)
async def print_bill(payload: PrintRequest) -> PrintResponse:
    printed = await service.print_bill(payload.bill_id, payload.printed_by)
    return PrintResponse(state=service.state, printed=printed)


@router.post("/print-portal", response_model=PrintResponse)
async def print_portal(payload: PrintPortalRequest) -> PrintResponse:
    """Portal automation: select bill → fill payment → save → print."""
    printed = await service.print_portal(
        auction_id=payload.auction_id,
        hammali_rate=payload.hammali_rate,
        hammali_amount=payload.hammali_amount,
        toul_rate=payload.toul_rate,
    )
    return PrintResponse(state=service.state, printed=printed)


@router.post("/print-url", response_model=PrintResponse)
async def print_url(payload: PrintUrlRequest) -> PrintResponse:
    """Print the page at the given URL (e.g. IndPrintBhugtanPatra.aspx) at 95% scale."""
    printed = await service.print_url(payload.url)
    return PrintResponse(state=service.state, printed=printed)


@router.post("/print-inspect")
async def print_inspect(payload: PrintUrlRequest) -> Dict[str, Any]:
    """DRY RUN: report the page's print/download controls without printing."""
    return await service.inspect_print_page(payload.url)


@router.post("/payment-info", response_model=SuccessResponse)
async def save_payment_info(payload: PaymentInfoRequest) -> SuccessResponse:
    await service.save_payment_info(
        payload.bill_id,
        payload.account_holder,
        payload.bank_name,
        payload.account_number,
        payload.ifsc_code,
    )
    return SuccessResponse(success=True, message="Payment info saved", state=service.state)


@router.post("/cancel", response_model=SuccessResponse)
async def cancel_automation() -> SuccessResponse:
    await service.cancel()
    return SuccessResponse(success=True, message="Automation cancelled", state=service.state)


@router.post("/reports", response_model=ReportsResponse)
async def reports() -> ReportsResponse:
    data = await service.search_reports()
    return ReportsResponse(
        state=service.state,
        date=data.get("date", ""),
        total_gatepasses=data.get("total_gatepasses", 0),
        tol_pending_count=data.get("tol_pending_count", 0),
        gatepasses=[GatepassRow(**g) for g in data.get("gatepasses", [])],
    )
