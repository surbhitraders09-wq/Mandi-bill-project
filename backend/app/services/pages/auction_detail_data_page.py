"""
Page object for the e-Mandi "नीलामी विवरण डेटा" (Auction Detail Data) page.

Real portal: RPT_Auction_Detail_Data.aspx

Search by gatepass ID → get trader details including mobile number.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from app.services.logging_service import log as db_log
from app.services.pages.base_page import BasePage

logger = logging.getLogger(__name__)

AUCTION_DETAIL_URL = (
    "https://eanugya.mp.gov.in/Anugya_e/EA-Trader/RPT_Auction_Detail_Data.aspx"
)


class AuctionDetailDataPage(BasePage):
    SEARCH_INPUT_SEL = "#txtSearch, input[name='txtSearch'], #GatePass_Id"
    SEARCH_INPUT_PARTIAL_SEL = "[id*='txtSearch'], [id*='GatePass_Id']"
    SEARCH_BTN_SEL = "#btnSearch, input[value='Search'], #btnSearchData"
    SEARCH_BTN_PARTIAL_SEL = "[id*='btnSearch']"

    def __init__(self, page, frame=None):
        super().__init__(page, frame)
        self._response_data: Optional[Dict[str, Any]] = None

    async def _dump_buttons(self, context) -> None:
        """Debug: log all button/input elements on the page."""
        try:
            info = await context.evaluate(
                "() => {"
                "  const els = Array.from(document.querySelectorAll("
                "    'input[type=submit], input[type=button], button, input[id*=btn]'"
                "  ));"
                "  return els.map(e => ({"
                "    id: e.id, type: e.type, value: e.value || e.innerText,"
                "    visible: e.offsetParent !== null,"
                "  }));"
                "}"
            )
            if info:
                for b in info:
                    await db_log(
                        "INFO",
                        f"Auction detail button: id={b['id']!r} type={b.get('type','')} "
                        f"value={b.get('value','')!r} visible={b.get('visible')}",
                    )
            else:
                await db_log("WARNING", "Auction detail: no buttons found on page")
        except Exception:
            pass

    async def navigate(self) -> None:
        await self._page.goto(AUCTION_DETAIL_URL, wait_until="domcontentloaded", timeout=45000)
        self._frame = None
        await self.wait_for_timeout(2000)

        # Dump buttons for diagnostics
        await self._dump_buttons(self._page)

        # Detect content frame
        for f in self._page.frames:
            if f == self._page.main_frame:
                continue
            try:
                src = await f.evaluate("window.location.pathname")
                if src and ("Auction_Detail" in src or "RPT_Auction" in src):
                    self._frame = f
                    await db_log("INFO", f"Auction detail frame found: {src}")
                    break
            except Exception:
                continue

        await db_log(
            "INFO",
            f"Navigated to auction detail data ({self._page.url}), frame={self._frame is not None}",
        )

    async def _find_and_fill_input(self, context, gatepass_id: str) -> bool:
        """Find the search input and fill it. Tries exact ID, partial ID, JS fallback."""
        # Exact selectors
        for sel in self.SEARCH_INPUT_SEL.split(", "):
            el = await context.query_selector(sel.strip())
            if el:
                await el.fill(gatepass_id)
                await db_log("INFO", f"Auction detail: filled gatepass {gatepass_id} in {sel}")
                return True

        # Partial ID (ASP.NET naming container)
        el = await context.query_selector(self.SEARCH_INPUT_PARTIAL_SEL)
        if el:
            await el.fill(gatepass_id)
            await db_log("INFO", f"Auction detail: filled via partial id")
            return True

        # JS fallback
        filled = await context.evaluate(
            "(id) => {"
            "  let el = document.querySelector('#txtSearch') "
            "        || document.querySelector('#GatePass_Id') "
            "        || document.querySelector('[id*=\"txtSearch\"]') "
            "        || document.querySelector('[id*=\"GatePass_Id\"]');"
            "  if (!el) {"
            "    const inputs = Array.from(document.querySelectorAll('input[type=text]'));"
            "    el = inputs.find(e => e.offsetParent !== null) || inputs[0];"
            "  }"
            "  if (el) { el.value = id; el.dispatchEvent(new Event('change')); return true; }"
            "  return false;"
            "}",
            gatepass_id,
        )
        if filled:
            await db_log("INFO", "Auction detail: filled via JS fallback")
        return filled

    async def _try_click_search(self, context, label: str) -> bool:
        """Attempt to click the search button. Returns True if clicked."""
        # Exact selectors
        for sel in self.SEARCH_BTN_SEL.split(", "):
            btn = await context.query_selector(sel.strip())
            if btn:
                await btn.click()
                await db_log("INFO", f"Auction detail: clicked via '{sel}' ({label})")
                return True

        # Partial ID
        btn = await context.query_selector(self.SEARCH_BTN_PARTIAL_SEL)
        if btn:
            await btn.click()
            await db_log("INFO", f"Auction detail: clicked via partial id ({label})")
            return True

        # JS evaluate
        clicked = await context.evaluate(
            "() => {"
            "  const el = document.querySelector('#btnSearch') "
            "          || document.querySelector('[id*=\"btnSearch\"]');"
            "  if (el) { el.click(); return true; }"
            "  return false;"
            "}"
        )
        if clicked:
            await db_log("INFO", f"Auction detail: clicked via JS ({label})")
            return True

        return False

    async def search_by_gatepass(self, gatepass_id: str) -> Dict[str, Any]:
        """Enter gatepass ID, click search, collect result."""
        self._response_data = None

        # Find and fill the search input
        target = self.ctx
        filled = await self._find_and_fill_input(target, gatepass_id)

        if not filled:
            # Try all frames
            for f in self._page.frames:
                try:
                    if await self._find_and_fill_input(f, gatepass_id):
                        self._frame = f if f != self._page.main_frame else self._frame
                        filled = True
                        break
                except Exception:
                    continue

        if not filled:
            await db_log("WARNING", f"Auction detail: could not fill gatepass {gatepass_id}")

        await self.wait_for_timeout(400)

        # Click search button
        clicked = await self._try_click_search(target, "active")

        if not clicked:
            for f in self._page.frames:
                try:
                    if await self._try_click_search(f, f"frame {f.url}"):
                        self._frame = f if f != self._page.main_frame else self._frame
                        clicked = True
                        break
                except Exception:
                    continue

        # Last resort: Enter key
        if not clicked:
            try:
                await target.keyboard.press("Enter")
                await db_log("INFO", "Auction detail: pressed Enter as fallback")
            except Exception:
                pass

        # Wait for result
        await self.wait_for_timeout(3000)

        # Extract result
        result = await self._extract_from_page()
        await db_log("INFO", f"Auction detail result: {result}")
        return result

    async def _extract_from_page(self) -> Dict[str, Any]:
        """Extract mobile number and other details from the page."""
        try:
            data = await self.ctx.evaluate(
                "() => {"
                "  const result = {};"
                "  // Try table rows"
                "  const rows = Array.from(document.querySelectorAll('table tr, #example tr'));"
                "  for (const tr of rows) {"
                "    const cells = Array.from(tr.querySelectorAll('td'));"
                "    for (let i = 0; i < cells.length - 1; i++) {"
                "      const label = cells[i].innerText.trim().toLowerCase();"
                "      const value = cells[i + 1].innerText.trim();"
                "      if (label.includes('mobile') || label.includes('मोबाइल') || label.includes('फोन')) {"
                "        result.mobile_no = value;"
                "      }"
                "      if (label.includes('trader') || label.includes('व्यापारी') || label.includes('नाम')) {"
                "        result.trader_name = value;"
                "      }"
                "      if (label.includes('gatepass') || label.includes('गेटपास')) {"
                "        result.gatepass_id = value;"
                "      }"
                "      if (label.includes('commodity') || label.includes('फसल') || label.includes('वस्तु')) {"
                "        result.commodity = value;"
                "      }"
                "      if (label.includes('weight') || label.includes('तौल') || label.includes('वजन')) {"
                "        result.weight = value;"
                "      }"
                "    }"
                "  }"
                "  // Fallback: look for specific elements"
                "  const mobileEl = document.querySelector('#lblMobile, [id*=mobile], [id*=Mobile]');"
                "  if (mobileEl && !result.mobile_no) result.mobile_no = mobileEl.innerText.trim();"
                "  return result;"
                "}"
            )
            return data or {}
        except Exception as exc:
            await db_log("WARNING", f"Auction detail extract failed: {exc}")
            return {}
