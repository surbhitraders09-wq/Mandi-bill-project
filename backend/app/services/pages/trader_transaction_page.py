"""
Page object for the e-Mandi "व्यापारी के मंडी खाता की जानकारी" page.

Real portal: TraderTransactionRpt.aspx

Read-only: reads the trader's available balance (#lbl_AvaBal) and, after clicking
"Click here for last 10 transactions" (#btn_lastTrans), parses the XML returned
by MND_insSelData.asmx/GetBookDetails into mandi-fee transaction rows.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from app.services.logging_service import log as db_log
from app.services.pages.base_page import BasePage

logger = logging.getLogger(__name__)

TRADER_TXN_URL = (
    "https://eanugya.mp.gov.in/Anugya_e/EA-Trader/TraderTransactionRpt.aspx"
)
SERVICE_PATH = "MND_insSelData.asmx/GetBookDetails"


class TraderTransactionPage(BasePage):
    AVAILABLE_BALANCE_SEL = "#lbl_AvaBal"
    LAST_TRANSACTIONS_BTN_SEL = "#btn_lastTrans"
    GRID_SEL = "table[id*='grdBookDetails']"

    def __init__(self, page, frame=None):
        super().__init__(page, frame)
        self._transactions_xml: Optional[str] = None

    async def navigate(self) -> None:
        await self._page.goto(TRADER_TXN_URL, wait_until="domcontentloaded", timeout=45000)
        self._frame = None
        await self.wait_for_timeout(700)
        await db_log("INFO", f"Navigated to trader mandi-fee account ({self._page.url})")

    # ------------------------------------------------------------------
    # Available balance
    # ------------------------------------------------------------------

    async def scrape_available_balance(self) -> float:
        """Read the Available Balance from #lbl_AvaBal.

        The balance is filled in by an AJAX call (GetTraderDataSTI) shortly after
        page load, so we poll until the label has a value.
        """
        for _ in range(20):
            try:
                raw = await self.ctx.eval_on_selector(
                    self.AVAILABLE_BALANCE_SEL,
                    "(el) => (el.textContent || '').trim()",
                )
            except Exception:
                raw = ""
            parsed = self._parse_money(raw)
            if parsed > 0:
                await db_log("INFO", f"Available balance: {parsed}")
                return parsed
            await self.wait_for_timeout(500)
        await db_log("WARNING", "Available balance never loaded")
        return 0.0

    @staticmethod
    def _parse_money(raw: str) -> float:
        match = re.search(r"[\d,]+\.\d{2}", raw or "")
        if not match:
            return 0.0
        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            return 0.0

    # ------------------------------------------------------------------
    # Last-10 transactions
    # ------------------------------------------------------------------

    async def _capture_response(self, response) -> None:
        try:
            url = response.url
            if SERVICE_PATH not in url:
                return
            if response.status != 200:
                await db_log("WARNING", f"GetBookDetails responded {response.status}")
                return
            text = await response.text()
            self._transactions_xml = self._extract_xml(text)
            await db_log("INFO", f"Captured GetBookDetails response ({len(text)} chars)")
        except Exception as exc:
            await db_log("WARNING", f"Failed to read GetBookDetails response: {exc}")

    @staticmethod
    def _extract_xml(text: str) -> Optional[str]:
        """Pull the XML document out of the ASMX JSON wrapper.

        The response is JSON ``{"d":"<xml...>"}`` where the XML double-quotes are
        HTML-escaped (``&quot;``). Return the raw XML or None.
        """
        if not text:
            return None
        stripped = text.strip()
        if stripped.startswith("{"):
            try:
                import json

                payload = json.loads(stripped).get("d")
                return payload if isinstance(payload, str) else None
            except Exception:
                return None
        return stripped

    async def click_last_transactions(self) -> None:
        self._transactions_xml = None
        self._page.on("response", self._capture_response)
        try:
            btn = await self.ctx.query_selector(self.LAST_TRANSACTIONS_BTN_SEL)
            if btn is None:
                await db_log("WARNING", "Last-transactions button not found")
                return
            await btn.click()
            # Poll for the service response (AJAX, no navigation).
            for _ in range(20):
                if self._transactions_xml:
                    break
                await self.wait_for_timeout(500)
        finally:
            self._page.remove_listener("response", self._capture_response)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _local_name(tag: str) -> str:
        """Strip the XML namespace from a tag name."""
        return tag.rsplit("}", 1)[-1] if tag else tag

    @classmethod
    def parse_transactions_xml(cls, xml_text: Optional[str]) -> List[Dict[str, Any]]:
        """Parse the BooksData XML into transaction rows.

        XML shape (NewDataSet/BooksData):
          TRANS_DATE, FeeTransactionID, ETransactionID, Variety_Name,
          MandiFee_Dr, MandiFee_Cr, FLAG ('भुगतान-पत्र')
        """
        if not xml_text:
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("GetBookDetails XML parse failed: %s", exc)
            return []
        transactions: List[Dict[str, Any]] = []
        for book in root.iter():
            if cls._local_name(book.tag) != "BooksData":
                continue
            fields: Dict[str, str] = {}
            for child in book:
                fields[cls._local_name(child.tag)] = (child.text or "").strip()
            transactions.append({
                "date": fields.get("TRANS_DATE", ""),
                "fee_transaction_id": fields.get("FeeTransactionID", ""),
                "reference": fields.get("ETransactionID", ""),
                "crop": fields.get("Variety_Name", ""),
                "mandi_fee_dr": cls._to_float(fields.get("MandiFee_Dr")),
                "mandi_fee_cr": cls._to_float(fields.get("MandiFee_Cr")),
                "flag": fields.get("FLAG", ""),
            })
        logger.info("Parsed %d mandi-fee transaction(s)", len(transactions))
        return transactions

    @staticmethod
    def _to_float(value: Any) -> float:
        if value is None:
            return 0.0
        try:
            return float(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0
