"""
Page object for the e-Mandi "फसल अनुसार भुगतान पत्रक की समरी रिपोर्ट"
(crop-wise payment-bill summary report) page.

Real portal: RPT_BhugtanPatrak_CropwiseTD.aspx

The search is read-only: clicking #btnSearchData POSTs to
WS_Bhugtan.asmx/tdr_BP_One and renders the per-crop totals into the #example
DataTable. This page has only a From_Date (no To_Date) and never creates a bill.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from app.services.logging_service import log as db_log
from app.services.pages.base_page import BasePage

logger = logging.getLogger(__name__)

CROPWISE_URL = "https://eanugya.mp.gov.in/Anugya_e/EA-Trader/RPT_BhugtanPatrak_CropwiseTD.aspx"
SERVICE_PATH = "WS_Bhugtan.asmx/tdr_BP_One"


class CropWiseSummaryPage(BasePage):
    FROM_DATE_SEL = "#From_Date"
    SEARCH_BTN_SEL = "#btnSearchData"

    def __init__(self, page, frame=None):
        super().__init__(page, frame)
        self._response_rows: List[Dict[str, Any]] = []

    async def navigate(self) -> None:
        await self._page.goto(CROPWISE_URL, wait_until="domcontentloaded", timeout=45000)
        self._frame = None
        await self.wait_for_timeout(1500)
        # Detect content frame
        for f in self._page.frames:
            if f == self._page.main_frame:
                continue
            try:
                src = await f.evaluate("window.location.pathname")
                if src and ("Bhugtan" in src or "Cropwise" in src or "RPT_" in src):
                    self._frame = f
                    await db_log("INFO", f"Crop-wise frame found: {src}")
                    break
            except Exception:
                continue
        await db_log("INFO", f"Navigated to crop-wise summary ({self._page.url}), frame={self._frame is not None}")
        try:
            target = self.ctx
            has_btn = await target.query_selector(self.SEARCH_BTN_SEL) is not None
            await db_log("INFO", f"Crop-wise search button present: {has_btn}")
            if not has_btn:
                # Search all frames for button
                for f in self._page.frames:
                    try:
                        btn = await f.query_selector(self.SEARCH_BTN_SEL)
                        if btn:
                            self._frame = f
                            await db_log("INFO", f"Crop-wise button found in frame: {f.url}")
                            break
                    except Exception:
                        continue
        except Exception as exc:
            await db_log("WARNING", f"Crop-wise button check failed: {exc}")

    async def set_from_date(self, from_date: date) -> None:
        """Set the readonly jQuery datepicker (format dd-mm-yy).

        The field is readonly; the portal JS writes it via
        `$('#From_Date').val(...)` and the search handler reads
        `$('#From_Date').val()`. We set the value the same way and dispatch an
        input event so the search reads it.
        """
        target = self.ctx
        from_str = from_date.strftime("%d-%m-%Y")
        await target.evaluate(
            "({fromDate}) => {"
            "  const el = document.querySelector('#From_Date');"
            "  if (el) { el.value = fromDate; el.dispatchEvent(new Event('change')); }"
            "}",
            {"fromDate": from_str},
        )
        await self.wait_for_timeout(250)
        await db_log("INFO", f"Crop-wise From_Date set: {from_str}")

    async def _capture_response(self, response) -> None:
        try:
            url = response.url
            if SERVICE_PATH not in url:
                return
            if response.status != 200:
                await db_log("WARNING", f"Crop-wise service responded {response.status}")
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
            await db_log("INFO", f"Captured {len(rows)} crop-wise row(s) from service")
        except Exception as exc:
            await db_log("WARNING", f"Failed to read crop-wise service response: {exc}")

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
            # Try clicking in current context
            clicked = False
            try:
                btn = await target.query_selector(self.SEARCH_BTN_SEL)
                if btn:
                    await btn.click(timeout=5000)
                    clicked = True
                    await db_log("INFO", "Crop-wise: search clicked")
            except Exception as exc:
                await db_log("WARNING", f"Crop-wise: click failed in current context: {exc}")

            # If not clicked, search all frames
            if not clicked:
                for f in self._page.frames:
                    try:
                        btn = await f.query_selector(self.SEARCH_BTN_SEL)
                        if btn:
                            await btn.click(timeout=5000)
                            self._frame = f
                            clicked = True
                            await db_log("INFO", f"Crop-wise: clicked in frame {f.url}")
                            break
                    except Exception:
                        continue

            if not clicked:
                # Last resort: JS click
                try:
                    await self.ctx.evaluate(
                        "() => { const b = document.querySelector('#btnSearchData'); if(b) b.click(); }"
                    )
                    await db_log("INFO", "Crop-wise: JS click fallback")
                except Exception:
                    pass

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
        """Map service rows to crop summary rows.

        Service row: ``{Commodity_Name, ActWeight (quintal), TotalAmt (₹)}``.
        Rendered crop names are like "सोयाबीन/Yellow", "चना/चना".
        """
        crops: List[Dict[str, Any]] = []
        for idx, row in enumerate(rows):
            commodity = str(row.get("Commodity_Name", "") or "").strip()
            if not commodity:
                commodity = f"(अन्य {idx + 1})"
            weight = cls._to_float(row.get("ActWeight"))
            amount = cls._to_float(row.get("TotalAmt"))
            crops.append({
                "commodity": commodity,
                "total_weight": round(weight, 3),
                "total_amount": round(amount, 2),
                "avg_rate": round(amount / weight, 2) if weight > 0 else 0.0,
            })
        return crops
