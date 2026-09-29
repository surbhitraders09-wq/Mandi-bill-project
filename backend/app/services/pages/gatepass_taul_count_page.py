"""
Page object for the e-Mandi "गेटपास नीलामी तौल गणना" (Gatepass Auction Taul Count) page.

Real portal: RPT_Gatepass_Auction_Taul_Count.aspx

Shows gatepass-wise auction/weighing status. User selects date → Search All Data →
collects which bills are pending tol/payment.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from app.services.logging_service import log as db_log
from app.services.pages.base_page import BasePage

logger = logging.getLogger(__name__)

TAUL_COUNT_URL = (
    "https://eanugya.mp.gov.in/Anugya_e/EA-Trader/RPT_Gatepass_Auction_Taul_Count.aspx"
)


class GatepassTaulCountPage(BasePage):
    FROM_DATE_SEL = "#From_Date"
    SEARCH_BTN_SEL = "#btnSearchData"
    # ASP.NET wraps IDs in content placeholders — use partial match
    SEARCH_BTN_PARTIAL_SEL = "[id*='btnSearchData']"
    # Broader fallback selectors for submit buttons
    SUBMIT_FALLBACK_SELS = [
        "input[type='submit']",
        "button[type='submit']",
        "input[type='button'][value*='Search']",
        "input[type='button'][value*='खोज']",
        "input[type='button'][value*='Data']",
        "#btnSearch",
    ]

    def __init__(self, page, frame=None):
        super().__init__(page, frame)
        self._response_rows: List[Dict[str, Any]] = []

    async def _dump_buttons(self, context) -> None:
        """Debug: log all button/input elements on the page."""
        try:
            info = await context.evaluate(
                "() => {"
                "  const els = Array.from(document.querySelectorAll("
                "    'input[type=submit], input[type=button], button, a[id*=btn], input[id*=btn]'"
                "  ));"
                "  return els.map(e => ({"
                "    tag: e.tagName,"
                "    id: e.id,"
                "    type: e.type,"
                "    value: e.value || e.innerText,"
                "    visible: e.offsetParent !== null,"
                "    display: getComputedStyle(e).display,"
                "  }));"
                "}"
            )
            if info:
                for b in info:
                    await db_log(
                        "INFO",
                        f"Taul count button: {b['tag']} id={b['id']!r} "
                        f"type={b.get('type','')} value={b.get('value','')!r} "
                        f"visible={b.get('visible')} display={b.get('display')}",
                    )
            else:
                await db_log("WARNING", "Taul count: no button elements found on page")
        except Exception as exc:
            await db_log("WARNING", f"Taul count button dump failed: {exc}")

    async def _try_click_search(self, context, label: str) -> bool:
        """Attempt to click the search button in the given context.

        Tries exact ID → partial ID → JS evaluate → broader selectors.
        Returns True if a click was attempted.
        """
        # 1) Exact ID
        btn = await context.query_selector(self.SEARCH_BTN_SEL)
        if btn:
            await btn.click()
            await db_log("INFO", f"Taul count: clicked via exact id ({label})")
            return True

        # 2) Partial ID (ASP.NET naming container)
        btn = await context.query_selector(self.SEARCH_BTN_PARTIAL_SEL)
        if btn:
            await btn.click()
            await db_log("INFO", f"Taul count: clicked via partial id ({label})")
            return True

        # 3) JS evaluate — find and click by partial ID
        clicked_js = await context.evaluate(
            "() => {"
            "  const el = document.querySelector('[id*=\"btnSearchData\"]');"
            "  if (el) { el.click(); return true; }"
            "  return false;"
            "}"
        )
        if clicked_js:
            await db_log("INFO", f"Taul count: clicked via JS evaluate ({label})")
            return True

        # 4) Broader selectors
        for sel in self.SUBMIT_FALLBACK_SELS:
            btn = await context.query_selector(sel)
            if btn:
                await btn.click()
                await db_log("INFO", f"Taul count: clicked via fallback '{sel}' ({label})")
                return True

        return False

    async def navigate(self) -> None:
        await self._page.goto(TAUL_COUNT_URL, wait_until="domcontentloaded", timeout=45000)
        self._frame = None
        await self.wait_for_timeout(2000)

        # Dump all buttons for diagnostics
        await self._dump_buttons(self._page)

        # Detect content frame (portal loads inside iframe)
        for f in self._page.frames:
            if f == self._page.main_frame:
                continue
            try:
                src = await f.evaluate("window.location.pathname")
                if src and "RPT_Gatepass" in src:
                    self._frame = f
                    await db_log("INFO", f"Taul count frame found: {src}")
                    break
            except Exception:
                continue

        await db_log(
            "INFO",
            f"Navigated to gatepass taul count ({self._page.url}), frame={self._frame is not None}",
        )

        # Try to find and log the search button in the active context
        try:
            target = self.ctx
            btn = await target.query_selector(self.SEARCH_BTN_SEL)
            btn_partial = await target.query_selector(self.SEARCH_BTN_PARTIAL_SEL)
            has_btn_js = await target.evaluate(
                "() => !!document.querySelector('[id*=\"btnSearchData\"]')"
            )
            await db_log(
                "INFO",
                f"Taul count search button: exact={btn is not None} "
                f"partial={btn_partial is not None} js={has_btn_js}",
            )
        except Exception as exc:
            await db_log("WARNING", f"Taul count button check failed: {exc}")

    async def set_date(self, target_date: date) -> None:
        """Set the date field (jQuery datepicker, format dd-mm-yy)."""
        date_str = target_date.strftime("%d-%m-%Y")
        target = self.ctx
        # Try exact selector first, then partial
        set_ok = await target.evaluate(
            "(d) => {"
            "  const el = document.querySelector('#From_Date') "
            "           || document.querySelector('[id*=\"From_Date\"]');"
            "  if (el) { el.value = d; el.dispatchEvent(new Event('change')); return true; }"
            "  return false;}"
            "}",
            date_str,
        )
        await self.wait_for_timeout(400)
        await db_log("INFO", f"Taul count date set: {date_str} (ok={set_ok})")

    async def _capture_response(self, response) -> None:
        try:
            url = response.url
            if "RPT_Gatepass_Auction_Taul_Count" not in url and "taul" not in url.lower():
                return
            if response.status != 200:
                return
            try:
                body = await response.json()
            except Exception:
                text = await response.text()
                body = json.loads(text) if text else {}
            data = body.get("d") if isinstance(body, dict) else None
            if data is None:
                return
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    return
            if isinstance(data, list):
                self._response_rows = [r for r in data if isinstance(r, dict)]
                await db_log("INFO", f"Captured {len(self._response_rows)} taul count rows")
        except Exception as exc:
            await db_log("WARNING", f"Failed to capture taul count response: {exc}")

    async def search_and_collect(self, timeout_sec: int = 120) -> List[Dict[str, Any]]:
        """Click Search All Data and collect results.

        Tries multiple strategies to find and click the button:
        1. Active context (frame or main page) — exact + partial ID + JS
        2. All frames including main_frame — same cascade
        3. If still not clicked, wait 2s and retry (page may still be loading)

        Falls back to table scrape if AJAX response never arrives.
        """
        self._response_rows = []
        self._page.on("response", self._capture_response)
        try:
            clicked = False

            # Strategy 1: Try clicking in the active context
            clicked = await self._try_click_search(self.ctx, "active context")

            # Strategy 2: Search ALL frames (including main_frame)
            if not clicked:
                for f in self._page.frames:
                    try:
                        if await self._try_click_search(f, f"frame {f.url}"):
                            self._frame = f if f != self._page.main_frame else self._frame
                            clicked = True
                            break
                    except Exception:
                        continue

            # Strategy 3: Page may still be loading — wait and retry once
            if not clicked:
                await db_log("INFO", "Taul count: button not found, waiting 3s for page load…")
                await self.wait_for_timeout(3000)
                await self._dump_buttons(self.ctx)
                clicked = await self._try_click_search(self.ctx, "retry after wait")
                if not clicked:
                    for f in self._page.frames:
                        try:
                            if await self._try_click_search(f, f"retry frame {f.url}"):
                                self._frame = f if f != self._page.main_frame else self._frame
                                clicked = True
                                break
                        except Exception:
                            continue

            if clicked:
                await db_log("INFO", "Taul count: Search All Data click succeeded")
            else:
                await db_log("WARNING", "Taul count: Search All Data button not found — will use table scrape")

            # Poll for AJAX response or timeout
            elapsed = 0
            while elapsed < timeout_sec * 1000:
                if self._response_rows:
                    break
                await self.wait_for_timeout(2000)
                elapsed += 2000
        finally:
            self._page.remove_listener("response", self._capture_response)

        # If no AJAX response, try scraping the visible table
        if not self._response_rows:
            self._response_rows = await self._scrape_visible_table()

        await db_log("INFO", f"Taul count final: {len(self._response_rows)} rows")
        return self._response_rows

    async def _scrape_visible_table(self) -> List[Dict[str, Any]]:
        """Scrape data from the visible HTML table if AJAX capture failed."""
        try:
            rows = await self.ctx.evaluate(
                "() => {"
                "  const table = document.querySelector('#example, table.table, table');"
                "  if (!table) return [];"
                "  const trs = Array.from(table.querySelectorAll('tbody tr'));"
                "  return trs.map(tr => {"
                "    const cells = Array.from(tr.querySelectorAll('td'));"
                "    return cells.map(c => c.innerText.trim());"
                "  }).filter(r => r.length > 0);"
                "}"
            )
            if rows:
                await db_log("INFO", f"Scraped {len(rows)} visible taul count rows")
                # Convert to dicts using header row
                headers = await self.ctx.evaluate(
                    "() => {"
                    "  const table = document.querySelector('#example, table.table, table');"
                    "  if (!table) return [];"
                    "  return Array.from(table.querySelectorAll('thead th')).map(h => h.innerText.trim());"
                    "}"
                )
                result = []
                for row in rows:
                    d = {}
                    for i, val in enumerate(row):
                        key = headers[i] if i < len(headers) else f"col_{i}"
                        d[key] = val
                    result.append(d)
                return result
        except Exception as exc:
            await db_log("WARNING", f"Taul count table scrape failed: {exc}")
        return []

    @staticmethod
    def parse_gatepass_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse raw rows into structured gatepass data.

        Identifies bills where tol (weighing) is pending or payment is not done.
        """
        parsed = []
        for row in rows:
            gatepass_id = (
                row.get("GatePass_Id")
                or row.get("gatepass_id")
                or row.get("Gatepass_Id")
                or row.get("गेटपास आईडी")
                or ""
            )
            trader_name = (
                row.get("Trader_Name")
                or row.get("trader_name")
                or row.get("व्यापारी का नाम")
                or ""
            )
            commodity = (
                row.get("Commodity_Name")
                or row.get("commodity")
                or row.get("फसल का नाम")
                or ""
            )
            weight = row.get("ActWeight") or row.get("weight") or row.get("तौल") or "0"
            taul_status = (
                row.get("Taul_Status")
                or row.get("taul_status")
                or row.get("तौल स्थिति")
                or ""
            )
            payment_status = (
                row.get("Payment_Status")
                or row.get("payment_status")
                or row.get("भुगतान स्थिति")
                or ""
            )
            mobile_no = (
                row.get("Mobile_No")
                or row.get("mobile_no")
                or row.get("मोबाइल नं.")
                or row.get("Mobile")
                or ""
            )

            # Determine if tol is pending
            tol_pending = False
            if taul_status:
                taul_lower = taul_status.lower()
                tol_pending = any(
                    kw in taul_lower
                    for kw in ["pending", "पेंडिंग", "नहीं", "not done", "बाकी"]
                )
            # If weight is 0 or empty, tol is likely pending
            try:
                w = float(str(weight).replace(",", ""))
                if w <= 0:
                    tol_pending = True
            except (ValueError, TypeError):
                pass

            parsed.append({
                "gatepass_id": str(gatepass_id).strip(),
                "trader_name": str(trader_name).strip(),
                "commodity": str(commodity).strip(),
                "weight": str(weight).strip(),
                "taul_status": str(taul_status).strip(),
                "payment_status": str(payment_status).strip(),
                "mobile_no": str(mobile_no).strip(),
                "tol_pending": tol_pending,
            })
        return parsed
