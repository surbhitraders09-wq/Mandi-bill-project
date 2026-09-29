"""
Page object for the e-Mandi "दिनांक वार अनुबंध पत्रक" (date-wise anubandh) page.

Real portal: Ins_eMandiAnubandh_BP_DTWise.aspx

The search here is read-only: it POSTs to the WSD ASMX service and returns the
auction rows as JSON (DataTable `data.d`). This page never creates a bill.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.services.logging_service import log as db_log
from app.services.pages.base_page import BasePage

logger = logging.getLogger(__name__)

DTWISE_URL = "https://eanugya.mp.gov.in/Anugya_e/EA-Trader/Ins_eMandiAnubandh_BP_DTWise.aspx"
SERVICE_PATH = "eMandiBPMerge.asmx/EM_AnubandhDetail_AllCrops"


class AnubandhDateWisePage(BasePage):
    RADIO_MODE_SEL = "input[name='rb_checkAS']"
    ALL_CROP_SEL = "#rb_ALL_Crop"
    FROM_DATE_SEL = "#From_Date"
    TO_DATE_SEL = "#To_Date"
    SEARCH_BTN_SEL = "#btn_search"
    TRADER_ID_LABEL_SEL = "#lbl_Opt_ID"

    def __init__(self, page, frame=None):
        super().__init__(page, frame)
        self._response_rows: List[Dict[str, Any]] = []

    async def navigate(self) -> None:
        await self._page.goto(DTWISE_URL, wait_until="domcontentloaded", timeout=45000)
        self._frame = None
        await self.wait_for_timeout(700)
        await db_log("INFO", f"Navigated to date-wise anubandh page ({self._page.url})")
        try:
            has_radio = await self._page.query_selector(self.ALL_CROP_SEL) is not None
            await db_log("INFO", f"DTWise radio present on main page: {has_radio}")
            if not has_radio:
                body = await self._page.evaluate(
                    "document.body ? document.body.innerText.slice(0, 300) : '<no body>'"
                )
                await db_log("WARNING", f"DTWise body snippet: {body!r}")
        except Exception as exc:
            await db_log("WARNING", f"DTWise radio check failed: {exc}")

    async def select_all_crops_mode(self) -> None:
        target = self.ctx
        radio = await target.query_selector(self.ALL_CROP_SEL)
        if radio is None:
            raise RuntimeError("All-crops radio (#rb_ALL_Crop) not found")
        checked = await radio.get_attribute("checked")
        if checked is None:
            label = await target.eval_on_selector(
                "#rb_ALL_Crop",
                "(el) => { const l = el.closest('label'); return l ? l.textContent : null; }",
            )
            if label:
                await target.get_by_text(label, exact=False).first.click()
            else:
                await radio.click(force=True)
            await self.wait_for_timeout(300)
        await db_log("INFO", "Selected 'दिनाँक अनुसार अनुबंध क्रमांक(सभी कृषि उपज अनुसार)'")

    async def set_date_range(self, from_date: date, to_date: date) -> None:
        """Set the readonly jQuery datepickers.

        The fields are readonly (jQuery UI datepicker) and the portal itself writes
        them via `$('#From_Date').val(...)` (see ins_dtwise.js), and the search
        handler reads `$('#From_Date').val()`. So we set the value the same way the
        portal does and dispatch an input event so the search reads it.
        """
        target = self.ctx
        from_str = from_date.strftime("%d-%m-%Y")
        to_str = to_date.strftime("%d-%m-%Y")
        await target.evaluate(
            "({fromDate, toDate}) => {"
            "  const fromEl = document.querySelector('#From_Date');"
            "  const toEl = document.querySelector('#To_Date');"
            "  if (fromEl) { fromEl.value = fromDate; fromEl.dispatchEvent(new Event('change')); }"
            "  if (toEl) { toEl.value = toDate; toEl.dispatchEvent(new Event('change')); }"
            "}",
            {"fromDate": from_str, "toDate": to_str},
        )
        await self.wait_for_timeout(250)
        await db_log(
            "INFO",
            f"Date range set: {from_str} → {to_str}",
        )

    async def set_today(self) -> None:
        today = datetime.now().date()
        await self.set_date_range(today, today)

    async def _capture_response(self, response) -> None:
        try:
            url = response.url
            if SERVICE_PATH not in url:
                return
            if response.status != 200:
                await db_log("WARNING", f"Anubandh service responded {response.status}")
                return
            try:
                body = await response.json()
            except Exception:
                text = await response.text()
                body = json.loads(text) if text else {}
            data = self.decode_response_payload(body)
            if data is None:
                return
            rows = [r for r in data if isinstance(r, dict)]
            self._response_rows = rows
            await db_log("INFO", f"Captured {len(rows)} auction row(s) from service")
        except Exception as exc:
            await db_log("WARNING", f"Failed to read anubandh service response: {exc}")

    @staticmethod
    def decode_response_payload(body: Any) -> Optional[Any]:
        """Extract the ASMX `d` payload, decoding the double-encoded string.

        ASP.NET ASMX JSON responses wrap data as ``{"d": ...}`` and the portal
        JS consumes it both as an array (``data: data.d``) and as a JSON string
        (``eval(response.d)``). Return the decoded list (or None if absent).
        """
        data = body.get("d") if isinstance(body, dict) else None
        if data is None:
            return None
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                return None
        return data

    async def search_and_collect(self) -> List[Dict[str, Any]]:
        self._response_rows = []
        self._page.on("response", self._capture_response)
        try:
            target = self.ctx
            await target.click(self.SEARCH_BTN_SEL)
            # Poll for the service response (AJAX, no navigation).
            for _ in range(20):
                if self._response_rows:
                    break
                await self.wait_for_timeout(500)
        finally:
            self._page.remove_listener("response", self._capture_response)
        return self._response_rows

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _to_float(value: Any) -> float:
        if value is None:
            return 0.0
        try:
            return float(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0

    @classmethod
    def parse_rows(cls, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        bills: List[Dict[str, Any]] = []
        for idx, row in enumerate(rows):
            bills.append({
                "index": idx,
                "auction_id": str(row.get("AuctionId", "") or ""),
                "auction_date": str(row.get("AuctionDate", "") or ""),
                "farmer_name": str(row.get("FarmerName", "") or "").strip(),
                "farmer_id": str(row.get("FarmerId", "") or ""),
                "farmer_mobile": str(row.get("MobileNo_Farmer", "") or ""),
                "village": str(row.get("VillageName", "") or ""),
                "comm_group": str(row.get("CommGroup_Name", "") or ""),
                "comm_group_code": str(row.get("CommGroupCode", "") or ""),
                "commodity": str(row.get("Commodity_Name", "") or ""),
                "commodity_code": str(row.get("CommodityCode", "") or ""),
                "variety": str(row.get("Variety_Name", "") or ""),
                "variety_code": str(row.get("VarietyCode", "") or ""),
                "weight": cls._to_float(row.get("ActualWeight")),
                "rate": cls._to_float(row.get("AuctionRate")),
                "gatepass_id": str(row.get("GatepassID", "") or ""),
                "gatepass_date": str(row.get("Gatepass_Date", "") or ""),
                "grade": str(row.get("Grade", "") or ""),
                "category": str(row.get("category", "") or ""),
                "mandi": str(row.get("MandiName", "") or ""),
                "trader_id": str(row.get("TraderID", "") or ""),
                "firm": str(row.get("Traders_ComName", "") or ""),
                "tulavati_id": str(row.get("Tulavati_Id", "") or ""),
                "operator_id": str(row.get("OperatorID", "") or ""),
                "emp_name": str(row.get("EmpName", "") or ""),
            })
        return bills

    @classmethod
    def gross_amount(cls, bill: Dict[str, Any]) -> float:
        return round(bill.get("weight", 0) * bill.get("rate", 0), 2)

    @classmethod
    def payable(cls, bill: Dict[str, Any]) -> float:
        """किसान को भुगतान योग्य = कुल मूल्य − हम्माली − तौल (portal MandiTax)."""
        gross = cls.gross_amount(bill)
        hammali = bill.get("hammali_amount", 0)
        toul = bill.get("toul_amount", 0)
        return round(gross - hammali - toul, 2)

    @classmethod
    def annotate(
        cls,
        bill: Dict[str, Any],
        hammali_rate: float = 12.05,
        toul_rate: float = 0.0,
    ) -> Dict[str, Any]:
        weight = bill.get("weight", 0)
        gross = cls.gross_amount(bill)
        bill["gross_amount"] = gross
        bill["hammali_rate"] = hammali_rate
        bill["hammali_amount"] = round(weight * hammali_rate, 2)
        bill["toul_rate"] = toul_rate
        bill["toul_amount"] = round(weight * toul_rate, 2)
        bill["payable"] = cls.payable(bill)
        return bill
