"""
Page object that scrapes the portal Dashboard (mandi/nirashrit fee totals) and
the Home page (per-crop stock on which mandi fee was paid).

Read-only: it only parses what the portal already displays.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.logging_service import log as db_log
from app.services.pages.base_page import BasePage

logger = logging.getLogger(__name__)

DASHBOARD_URL = "https://eanugya.mp.gov.in/Anugya_e/EA-Trader/Dashboard.aspx"
HOME_URL = "https://eanugya.mp.gov.in/Anugya_e/EA-Trader/WelcomeTrader.aspx"
COMMODITY_BAL_URL = "https://eanugya.mp.gov.in/Anugya_e/EA-Trader/TraderCommodityBal.aspx"

FEE_LABELS = {
    "total_mandi": "कुल मंडी फीस",
    "total_nirashrit": "कुल निराश्रित फीस",
    "cash_mandi": "नकद जमा मंडी फीस",
    "cash_nirashrit": "नकद जमा निराश्रित फीस",
    "rtgs_mandi": "RTGS/NEFT/ऑनलाइन द्वारा जमा मंडी फीस",
    "rtgs_nirashrit": "RTGS/NEFT/ऑनलाइन द्वारा जमा निराश्रित फीस",
}

# Label → element id on Dashboard.aspx (the portal renders the value ABOVE the
# label text, so we read the label element ids directly instead of text search).
FEE_IDS = {
    "total_mandi": "TotalMandiFees",
    "total_nirashrit": "TotalN_MandiFees",
    "cash_mandi": "DepositFee",
    "cash_nirashrit": "N_DepositFee",
    "rtgs_mandi": "TotalPaymentByOnline",
    "rtgs_nirashrit": "TotalN_PaymentByOnline",
}

EMPTY_FEES = {key: 0.0 for key in FEE_LABELS}

TAX_PAID_STOCK_HEADER = "फसल स्टॉक, जिस पर मंडी शुल्क दिया गया"


class SummaryScraper(BasePage):

    async def navigate_dashboard(self) -> None:
        await self._page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=45000)
        await self.wait_for_timeout(500)
        await db_log("INFO", f"Navigated to dashboard ({self._page.url})")

    async def navigate_home(self) -> None:
        """Navigate to the page that renders the tax-paid stock tables.

        WelcomeTrader.aspx only populates #examplePD after clicking
        #btn_dashboard ('डैशबोर्ड देखें'); TraderCommodityBal.aspx renders the
        same tables auto-populated. We prefer the dedicated page (no click
        dependency), falling back to the home page + button click.
        """
        for url, needs_click in ((COMMODITY_BAL_URL, False), (HOME_URL, True)):
            await self._page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await self.wait_for_timeout(500)
            await db_log("INFO", f"Navigated to stock page ({url})")
            if needs_click:
                btn = await self._page.query_selector("#btn_dashboard")
                if btn:
                    await btn.click()
                    await self.wait_for_timeout(1000)
                    await db_log("INFO", "Clicked 'डैशबोर्ड देखें' (#btn_dashboard)")
            try:
                await self._page.wait_for_selector(
                    "#examplePD tbody tr", timeout=15000
                )
                return
            except Exception:
                await db_log("WARNING", f"#examplePD rows not ready on {url}")
        raise RuntimeError("Could not load tax-paid stock table from any page")

    async def navigate_home_dashboard(self) -> None:
        """Go to WelcomeTrader.aspx and click 'डैशबोर्ड देखें' (#btn_dashboard).

        Clicking the button populates all the home tables the portal shows the
        trader after login: #examplePD (tax-paid stock), #exampleMFNP (कुल
        भुगतान-पत्रक / कुल मात्रा / देय मंडी फीस / देय निराश्रित शुल्क), etc.
        """
        await self._page.goto(HOME_URL, wait_until="domcontentloaded", timeout=45000)
        await self.wait_for_timeout(500)
        await db_log("INFO", f"Navigated to home page ({HOME_URL})")
        btn = await self._page.query_selector("#btn_dashboard")
        if btn:
            await btn.click()
            await self.wait_for_timeout(1000)
            await db_log("INFO", "Clicked 'डैशबोर्ड देखें' (#btn_dashboard)")
        try:
            await self._page.wait_for_selector("#exampleMFNP tbody tr", timeout=15000)
        except Exception as exc:
            await db_log("WARNING", f"#exampleMFNP rows not ready: {exc}")

    async def scrape_mfnp_summary(self) -> Dict[str, float]:
        """Parse the कुल भुगतान-पत्रक table (#exampleMFNP).

        Single-row table: कुल भुगतान-पत्रक | कुल मात्रा | देय मंडी फीस |
        देय निराश्रित शुल्क. Returns zeros when the table is empty.
        """
        result = {
            "total_bills": 0.0,
            "total_quantity": 0.0,
            "mandi_fee": 0.0,
            "nirashrit_fee": 0.0,
        }
        try:
            cells = await self._page.evaluate(
                """() => {
                    const tr = document.querySelector('#exampleMFNP tbody tr');
                    if (!tr) return [];
                    return Array.from(tr.querySelectorAll('td')).map(c => (c.textContent || '').trim());
                }"""
            )
        except Exception as exc:
            await db_log("WARNING", f"MFNP scrape failed: {exc}")
            return result
        if len(cells) >= 4:
            result["total_bills"] = self._to_float(cells[0])
            result["total_quantity"] = self._to_float(cells[1])
            result["mandi_fee"] = self._to_float(cells[2])
            result["nirashrit_fee"] = self._to_float(cells[3])
        await db_log(
            "INFO",
            f"MFNP summary: bills={result['total_bills']}, qty={result['total_quantity']}, "
            f"mandi={result['mandi_fee']}, nirashrit={result['nirashrit_fee']}",
        )
        return result

    @staticmethod
    def _to_float(raw: Any) -> float:
        try:
            return float(str(raw).replace(",", "").strip())
        except (ValueError, TypeError):
            return 0.0

    async def scrape_dashboard_fees(self) -> Dict[str, float]:
        """Parse the मंडी फीस की जानकारी section into the fees dict.

        Reads the value label elements by id (the portal shows the number above
        the Hindi label). Best-effort: any missing element becomes 0.0.
        """
        fees = dict(EMPTY_FEES)
        try:
            values = await self._page.evaluate(
                """(ids) => {
                    const out = {};
                    for (const [key, id] of Object.entries(ids)) {
                        const el = document.getElementById(id);
                        out[key] = el ? el.textContent.trim() : '';
                    }
                    return out;
                }""",
                FEE_IDS,
            )
        except Exception as exc:
            await db_log("WARNING", f"Dashboard fee scrape failed: {exc}")
            return fees
        for key, raw in values.items():
            fees[key] = self._parse_money(raw)
        await db_log(
            "INFO",
            f"Dashboard fees: total_mandi={fees['total_mandi']}, "
            f"total_nirashrit={fees['total_nirashrit']}",
        )
        return fees

    @staticmethod
    def _parse_money(raw: str) -> float:
        import re

        match = re.search(r"[\d,]+\.\d{2}", raw or "")
        if not match:
            return 0.0
        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            return 0.0

    async def scrape_tax_paid_stock(self) -> List[Dict[str, Any]]:
        """Parse the 'फसल स्टॉक, जिस पर मंडी शुल्क दिया गया हैं' table.

        Table is #examplePD on WelcomeTrader.aspx; rows are filled in by
        DataTables via AJAX shortly after load, so we wait for tbody rows.
        Shape: स.क्र. | फसल | कुल वजन (with a कुल योग footer row in tfoot).
        """
        rows: List[Dict[str, Any]] = []
        try:
            await self._page.wait_for_selector(
                "#examplePD tbody tr", timeout=15000
            )
        except Exception as exc:
            await db_log("WARNING", f"Tax-paid stock rows never loaded: {exc}")
            return rows
        try:
            table = await self._page.evaluate(
                """() => {
                    const out = [];
                    const bodyRows = Array.from(document.querySelectorAll('#examplePD tbody tr'));
                    for (const tr of bodyRows) {
                        const cells = Array.from(tr.querySelectorAll('td')).map(c => (c.textContent || '').trim());
                        if (cells.length < 3) continue;
                        const sNo = cells[0];
                        const crop = cells[1];
                        const weight = cells[2];
                        if (!crop || /^(स\.क्र|सीरियल)/.test(sNo)) continue;
                        if (/कुल योग/.test(crop) || /कुल/.test(sNo)) continue;
                        // Portal renders crops as "ग्रुप - फसल" (e.g. "सोयाबीन - सोयाबीन"); keep the commodity part.
                        const parts = crop.split(' - ');
                        const commodity = parts.length > 1 ? parts[parts.length - 1] : crop;
                        out.push({ commodity: commodity.trim(), total_weight: parseFloat(String(weight).replace(/,/g, '')) || 0 });
                    }
                    return out;
                }"""
            )
        except Exception as exc:
            await db_log("WARNING", f"Tax-paid stock parse failed: {exc}")
            return rows
        for item in table:
            rows.append({"commodity": item.get("commodity", ""), "total_weight": float(item.get("total_weight", 0) or 0)})
        await db_log("INFO", f"Tax-paid stock rows: {len(rows)}")
        return rows
