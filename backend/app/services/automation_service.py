import asyncio
import base64
import io
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decrypt_value
from app.core.state_machine import AutomationState, StateMachine
from app.database import async_session_factory
from app.exceptions import AutomationError, LoginError, NetworkError
from app.models.bill import Bill
from app.models.settings import Setting
from app.services.logging_service import log as db_log
from app.services.pages import (
    AnubandhDateWisePage,

    CropWiseSummaryPage,
    LoginPage,
    PaymentPage,
    PopupHandler,
    SummaryScraper,
    TraderTransactionPage,
    GatepassTaulCountPage,
    AuctionDetailDataPage,
)

# Shared speed knob — the SAME constants the portal page objects scale by
# (base_page.PORTAL_WAIT_SCALE / MIN_WAIT_MS), imported here so the direct
# print-chain waits in this service shrink by the exact same factor. One knob,
# two consumers: BasePage.wait_for_timeout and automation_service._scaled_portal_wait.
from app.services.pages.base_page import MIN_WAIT_MS, PORTAL_WAIT_SCALE

logger = logging.getLogger(__name__)


async def _portal_wait(page, ms: int) -> None:
    """Direct print-chain wait in AutomationService (driver, not a BasePage).
    Applies the SAME global knob (PORTAL_WAIT_SCALE / MIN_WAIT_MS from base_page)
    so one setting trims the login → CAPTCHA → bill → save → print flow uniformly."""
    await page.wait_for_timeout(max(MIN_WAIT_MS, int(ms * PORTAL_WAIT_SCALE)))


class AutomationService:
    _instance: Optional["AutomationService"] = None

    def __init__(self) -> None:
        self.state_machine = StateMachine()
        self._browser = None
        self._context = None
        self._page = None
        self._frame = None
        self._playwright = None
        self._found_bills: List[Dict[str, Any]] = []
        self._current_bill_data: Optional[Dict[str, Any]] = None
        self._lock = asyncio.Lock()

        self._login_page: Optional[LoginPage] = None
        self._payment_page: Optional[PaymentPage] = None
        self._popup_handler: Optional[PopupHandler] = None
        self._anubandh_page = None

        self._captcha_event: Optional[asyncio.Event] = None
        self._captcha_input: Optional[str] = None
        self._captcha_image_b64: Optional[str] = None
        self._captcha_fails: int = 0
        self._progress: str = ""
        self._progress_events: List[Dict[str, Any]] = []

    @classmethod
    def get_instance(cls) -> "AutomationService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def state(self) -> str:
        return self.state_machine.current_state.value

    @property
    def found_bills(self) -> List[Dict[str, Any]]:
        return self._found_bills

    @property
    def current_bill_data(self) -> Optional[Dict[str, Any]]:
        return self._current_bill_data

    @property
    def progress_events(self) -> List[Dict[str, Any]]:
        return self._progress_events[-50:]

    def _set_progress(self, message: str) -> None:
        self._progress = message
        if message:
            self._progress_events.append(
                {
                    "ts": datetime.now().strftime("%H:%M:%S"),
                    "message": message,
                }
            )

    # ------------------------------------------------------------------
    # Main flow
    # ------------------------------------------------------------------

    async def search_todays_bills(self) -> List[Dict[str, Any]]:
        """Fresh-login flow for the date-wise anubandh page (today only).

        Read-only: fetches today's auction/anubandh rows, never creates a bill.
        """
        async with self._lock:
            if self.state_machine.current_state not in (
                AutomationState.IDLE,
                AutomationState.ERROR,
                AutomationState.BILLS_LOADED,
            ):
                raise AutomationError(
                    f"Cannot start search in state {self.state_machine.current_state.value}"
                )
            self.state_machine.transition(AutomationState.SEARCHING)
            await db_log("INFO", "Automation — starting today's bills search")

            try:
                self._set_progress("ब्राउज़र खोला जा रहा है…")
                await self._launch_browser()
                config = await self.get_automation_config()

                url = config.get("e_mandi_url", "")
                if not url:
                    raise AutomationError("e-Mandi URL not configured")
                self._set_progress("पोर्टल लोड हो रहा है…")
                await self._page.goto(url, wait_until="domcontentloaded", timeout=45000)

                await self._detect_login_frame()
                self._init_page_objects()
                self._set_progress("लॉगिन हो रहा है…")
                await self._login()

                await self._detect_post_login_frame()
                self._init_page_objects()

                today = datetime.now().date()
                self._set_progress("आज के अनुबंध लोड…")
                await self._ensure_logged_in()
                await self._anubandh_page.navigate()
                await self._anubandh_page.select_all_crops_mode()
                await self._anubandh_page.set_today()
                rows = await self._anubandh_page.search_and_collect()
                bills = AnubandhDateWisePage.parse_rows(rows)

                hammali_rate = await self._get_hammali_rate()
                for b in bills:
                    AnubandhDateWisePage.annotate(b, hammali_rate=hammali_rate)

                self._found_bills = bills
                self.state_machine.transition(AutomationState.BILLS_LOADED)

                await db_log("INFO", f"Automation — found {len(bills)} today bill(s)")
                self._set_progress("")
                return bills

            except (LoginError, NetworkError):
                self._set_progress("")
                self.state_machine.transition(AutomationState.ERROR)
                await self.close_browser()
                raise
            except asyncio.CancelledError:
                self._set_progress("")
                self.state_machine.transition(AutomationState.ERROR)
                await self.close_browser()
                await db_log("WARNING", "Automation — search cancelled (client disconnected)")
                raise
            except Exception as exc:
                self._set_progress("")
                self.state_machine.transition(AutomationState.ERROR)
                await db_log("ERROR", f"Automation — today's search failed: {exc}")
                await self.close_browser()
                raise AutomationError(f"Today's bill search failed: {exc}") from exc

    async def search_summary(
        self, from_date: Optional[str] = None, to_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fresh-login flow for the mobile Summary tab.

        One login, then read-only scrapes matching the portal pages the user
        actually opens:
          - RPT_BhugtanPatrak_CropwiseTD.aspx → फसल अनुसार भुगतान-पत्रक समरी
            रिपोर्ट (per-crop totals from the WS_Bhugtan.asmx/tdr_BP_One
            service), once for the requested range and once per day for the
            last 10 days to build the daily price-trend line chart
          - WelcomeTrader.aspx → click 'डैशबोर्ड देखें' (#btn_dashboard), then
            parse फसल स्टॉक (#examplePD) and मंडी फीस/निराश्रित शुल्क
            (#exampleMFNP)
          - TraderTransactionRpt.aspx → available balance

        Returns a JSON summary dict (see schemas.SummaryResponse).
        """
        from app.services.summary_aggregator import (
            _cumulative_to_daily,
            build_crop_trends,
            build_price_trend,
            group_crops,
            soyabean_row,
        )

        async with self._lock:
            if self.state_machine.current_state not in (
                AutomationState.IDLE,
                AutomationState.ERROR,
                AutomationState.BILLS_LOADED,
            ):
                raise AutomationError(
                    f"Cannot start summary in state {self.state_machine.current_state.value}"
                )
            self.state_machine.transition(AutomationState.SEARCHING)
            await db_log("INFO", "Automation — starting summary search")

            try:
                self._set_progress("ब्राउज़र खोला जा रहा है…")
                await self._launch_browser()
                config = await self.get_automation_config()

                url = config.get("e_mandi_url", "")
                if not url:
                    raise AutomationError("e-Mandi URL not configured")
                self._set_progress("पोर्टल लोड हो रहा है…")
                await self._page.goto(url, wait_until="domcontentloaded", timeout=45000)

                await self._detect_login_frame()
                self._init_page_objects()
                self._set_progress("लॉगिन हो रहा है…")
                await self._login()

                self._set_progress("पोस्ट-लॉगिन फ्रेम लोड…")
                await self._detect_post_login_frame()
                self._init_page_objects()

                today = datetime.now().date()
                from_date_obj = self._parse_date(from_date) or today
                to_date_obj = self._parse_date(to_date) or today
                if from_date_obj > to_date_obj:
                    from_date_obj, to_date_obj = to_date_obj, from_date_obj
                date_range = {
                    "from": from_date_obj.strftime("%d-%m-%Y"),
                    "to": to_date_obj.strftime("%d-%m-%Y"),
                }

                # 1) Crop-wise payment-patrak summary report (requested range).
                self._set_progress("फसल अनुसार भुगतान-पत्रक समरी लोड…")
                await self._ensure_logged_in()
                cropwise = CropWiseSummaryPage(self._page, self._frame)
                await cropwise.navigate()
                await cropwise.set_from_date(from_date_obj)
                rows = await cropwise.search_and_collect()
                crops = CropWiseSummaryPage.parse_rows(rows)
                soyabean = soyabean_row(crops)

                # 2) Home page → click 'डैशबोर्ड देखें', then stock + MFNP.
                self._set_progress("होम डैशबोर्ड व मंडी फीस…")
                await self._ensure_logged_in()
                summary_scraper = SummaryScraper(self._page, self._frame)
                await summary_scraper.navigate_home_dashboard()
                tax_paid_stock = await summary_scraper.scrape_tax_paid_stock()
                mandi_fee_summary = await summary_scraper.scrape_mfnp_summary()

                # 3) Trader mandi-fee account: available balance only.
                self._set_progress("मंडी फीस बैलेंस…")
                await self._ensure_logged_in()
                trader_txn = TraderTransactionPage(self._page, self._frame)
                await trader_txn.navigate()
                mandi_balance = await trader_txn.scrape_available_balance()

                # 4) पिछले 7 दिन के दैनिक भाव — crop-wise report (cumulative),
                #    har din From_Date set karke cumulative result collect karo,
                #    phir consecutive difference se per-day avg rate nikalo.
                cropwise_trend = CropWiseSummaryPage(self._page, self._frame)
                trend_days = [
                    today - timedelta(days=i) for i in range(6, -1, -1)
                ]
                cumulative_runs = []
                for idx, day in enumerate(trend_days):
                    self._set_progress(f"ट्रेंड डेटा: दिन {idx+1}/7 ({day.strftime('%d-%m')})")
                    await self._ensure_logged_in()
                    await cropwise_trend.navigate()
                    await cropwise_trend.set_from_date(day)
                    rows = await cropwise_trend.search_and_collect()
                    crops = CropWiseSummaryPage.parse_rows(rows)
                    cumulative_runs.append({
                        "date": day.strftime("%d-%m-%Y"),
                        "crops": crops,
                    })
                    await db_log(
                        "INFO",
                        f"Trend cumulative {day.strftime('%d-%m-%Y')}: "
                        f"{len(crops)} crops",
                    )
                # Convert cumulative → per-day via consecutive difference
                daily_runs = _cumulative_to_daily(cumulative_runs)
                price_trend = build_price_trend(daily_runs)
                price_trend_summary = build_crop_trends(price_trend)
                await db_log(
                    "INFO",
                    f"Trend result: {len(price_trend)} days, "
                    f"{len(price_trend_summary)} crop summaries",
                )

                self._found_bills = []
                self.state_machine.transition(AutomationState.BILLS_LOADED)

                result = {
                    "state": self.state,
                    "date_range": date_range,
                    "tax_paid_stock": tax_paid_stock,
                    "crops": crops,
                    "soyabean": soyabean,
                    "mandi_fee_summary": mandi_fee_summary,
                    "mandi_balance": mandi_balance,
                    "price_trend": price_trend,
                    "price_trend_summary": price_trend_summary,
                    "found_bills": int(mandi_fee_summary.get("total_bills", 0) or len(crops)),
                }
                await db_log(
                    "INFO",
                    f"Automation — summary complete: {len(crops)} crops, "
                    f"{len(price_trend)} trend days, "
                    f"balance {mandi_balance}",
                )
                await self.close_browser()
                self._set_progress("")
                return result

            except (LoginError, NetworkError):
                self._set_progress("")
                self.state_machine.transition(AutomationState.ERROR)
                await self.close_browser()
                raise
            except asyncio.CancelledError:
                self._set_progress("")
                self.state_machine.transition(AutomationState.ERROR)
                await self.close_browser()
                await db_log("WARNING", "Automation — summary cancelled (client disconnected)")
                raise
            except Exception as exc:
                self._set_progress("")
                self.state_machine.transition(AutomationState.ERROR)
                await db_log("ERROR", f"Automation — summary search failed: {exc}")
                await self.close_browser()
                raise AutomationError(f"Summary search failed: {exc}") from exc

    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[datetime.date]:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%d-%m-%Y").date()
        except (ValueError, TypeError):
            return None

    async def print_analysed_bill(self, bill: Dict[str, Any], printed_by: str = "system") -> bool:
        """Print a locally analysed bill (not created on the portal)."""
        from app.services.print_service import print_document

        async with self._lock:
            if self.state_machine.current_state not in (
                AutomationState.BILLS_LOADED,
                AutomationState.READY_TO_PRINT,
            ):
                self.state_machine.transition(AutomationState.READY_TO_PRINT)

            self.state_machine.transition(AutomationState.PRINTING)
            await db_log("INFO", "Printing analysed bill (local, no portal write)")
            try:
                ok = await print_document(bill)
                bill_record = await self._persist_bill(bill)
                async with async_session_factory() as session:
                    db_bill = await session.get(Bill, bill_record.id)
                    if db_bill:
                        db_bill.printed = True
                        db_bill.printed_at = datetime.utcnow()
                        db_bill.printed_by = printed_by
                        await session.commit()
                await db_log("INFO", f"Analysed bill printed (db #{bill_record.id})")
                self.state_machine.transition(AutomationState.IDLE)
                return ok
            except Exception as exc:
                self.state_machine.transition(AutomationState.ERROR)
                await db_log("ERROR", f"Analysed print failed: {exc}")
                raise AutomationError(f"Print failed: {exc}") from exc

    async def print_bill(self, bill_id: int, printed_by: str = "system") -> bool:
        async with self._lock:
            bill_data = await self._load_bill(bill_id)
            if bill_data is None:
                raise AutomationError(f"Bill #{bill_id} not found")

            self.state_machine.transition(AutomationState.PRINTING)
            await db_log("INFO", f"Printing bill #{bill_id}")

            try:
                # Browser should already be open from search; relaunch only if closed
                if not self._page or self._page.is_closed():
                    await self._launch_browser()
                    config = await self.get_automation_config()
                    url = config.get("e_mandi_url", "")
                    if not url:
                        raise AutomationError("e-Mandi URL not configured")
                    await self._page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await self._detect_login_frame()
                    self._init_page_objects()
                    await self._login()
                    await self._detect_post_login_frame()
                    self._init_page_objects()

                # Hammali + taul = total deduction from gross amount
                hammali_amount = bill_data.hammali_amount or 0
                taul_amount = getattr(bill_data, 'taul_amount', 0) or 0
                total_deduction = hammali_amount + taul_amount
                # Cash amount = gross - total deduction
                gross_amount = getattr(bill_data, 'gross_amount', 0) or 0
                cash_amount = gross_amount - total_deduction if gross_amount > 0 else (bill_data.total_amount or 0)

                await self._payment_page.fill_hammali(total_deduction)
                await self._payment_page.select_cash_payment()
                await self._payment_page.fill_cash_amount(cash_amount)
                await self._payment_page.select_today_date()
                await self._payment_page.click_save()

                await self._popup_handler.handle_ok_popup()
                await self._popup_handler.handle_done_popup()

                # Navigate to IndBhugtanPrint.aspx for printing
                PRINT_URL = "https://eanugya.mp.gov.in/Anugya_e/EA-Trader/IndBhugtanPrint.aspx"
                await self._page.goto(PRINT_URL, wait_until="domcontentloaded", timeout=30000)
                await _portal_wait(self._page, 1000)
                await db_log("INFO", f"Navigated to print page ({PRINT_URL})")

                # Select today's date on print page
                from datetime import date as date_cls
                today_str = date_cls.today().strftime("%d/%m/%Y")
                date_inputs = await self._page.query_selector_all("input[type='text'][id*='date'], input[type='date'], input[name*='date']")
                for inp in date_inputs:
                    try:
                        await inp.fill(today_str)
                        await db_log("INFO", f"Print page: filled date {today_str}")
                        break
                    except Exception:
                        continue

                # Click search to load bills
                search_btns = await self._page.query_selector_all("input[type='submit'], button:has-text('Search'), button:has-text('खोज'), #btnSearch")
                for btn in search_btns:
                    try:
                        await btn.click()
                        await _portal_wait(self._page, 1000)
                        await db_log("INFO", "Print page: search clicked")
                        break
                    except Exception:
                        continue

                # Select the bill and print
                bill_id_str = str(bill_data.bill_id) if hasattr(bill_data, 'bill_id') else str(bill_id)
                rows = await self._page.query_selector_all("table tbody tr")
                for row in rows:
                    text = await row.inner_text()
                    if bill_id_str in text:
                        checkbox = await row.query_selector("input[type='checkbox']")
                        if checkbox:
                            await checkbox.check()
                            await db_log("INFO", f"Print page: selected bill {bill_id_str}")
                        # Click print
                        if self._popup_handler:
                            await self._popup_handler.apply_print_scale(self._page)
                        print_btn = await row.query_selector("a:has-text('Print'), button:has-text('Print'), a[href*='print']")
                        if print_btn:
                            await print_btn.click()
                            await _portal_wait(self._page, 1500)
                            await db_log("INFO", "Print page: print clicked")
                        break

                async with async_session_factory() as session:
                    bill = await session.get(Bill, bill_id)
                    if bill:
                        bill.printed = True
                        bill.printed_at = datetime.utcnow()
                        bill.printed_by = printed_by
                        await session.commit()

                await db_log("INFO", f"Bill #{bill_id} printed successfully")
                self.state_machine.transition(AutomationState.IDLE)
                # Browser stays open for more prints
                return True

            except Exception as exc:
                self.state_machine.transition(AutomationState.ERROR)
                await db_log("ERROR", f"Print failed for bill #{bill_id}: {exc}")
                await self.close_browser()
                raise AutomationError(f"Print failed: {exc}") from exc

    async def print_portal(self, auction_id: str, hammali_rate: float = 12.05, hammali_amount: float = 0.0, toul_rate: float = 0.0) -> bool:
        """Portal automation: select bill → fill payment → save → print.

        Process (as verified with the user):
          1. Ensure we are on the date-wise anubandh page
             (Ins_eMandiAnubandh_BP_DTWise.aspx — the browser is already there
             from search_todays_bills, left open on purpose).
          2. Click the search button so the bill grid loads.
          3. Find the bill row (by gatepass / farmer name) and click its
             "select" button to open the payment-entry form.
          4. In the payment form:
               - fill hammali with the amount the user entered on the frontend
                 (hammali_amount param; fallback to the annotated amount)
               - tick the नगद भुगतान (cash) radio option
               - read "किसान को भुगतान योग्य राशि" shown in the form and fill
                 that exact amount into the amount field
               - set today's date
               - click save
          5. Dismiss the OK/done popup.
          6. The portal itself opens the print page (IndBhugtanPrint.aspx,
             same tab or new tab) after a successful save — we WAIT for that
             navigation (no manual goto, which would race and close the page).
             Then set today's date, click search, find the bill and trigger print.
        """
        from datetime import date as date_cls

        async with self._lock:
            if self.state_machine.current_state not in (
                AutomationState.BILLS_LOADED,
                AutomationState.ERROR,
            ):
                raise AutomationError(
                    f"Cannot print portal in state {self.state_machine.current_state.value}. "
                    "Search bills first."
                )

            # Find the bill in current results
            bill = None
            for b in self._found_bills:
                if b.get("auction_id") == auction_id:
                    bill = b
                    break
            if not bill:
                raise AutomationError(f"Bill {auction_id} not found in current results")

            # Annotate with hammali/taul
            from app.services.pages.anubandh_datewise_page import AnubandhDateWisePage
            bill = AnubandhDateWisePage.annotate(bill, hammali_rate=hammali_rate, toul_rate=toul_rate)

            self.state_machine.transition(AutomationState.PRINTING)
            await db_log("INFO", f"Portal print: {auction_id} ({bill.get('farmer_name')})")

            try:
                # --- Ensure browser is open + logged in -------------------------------
                if not self._page or self._page.is_closed():
                    await self._launch_browser()
                    config = await self.get_automation_config()
                    url = config.get("e_mandi_url", "")
                    if not url:
                        raise AutomationError("e-Mandi URL not configured")
                    await self._page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await self._detect_login_frame()
                    self._init_page_objects()
                    await self._login()
                    await self._detect_post_login_frame()
                    self._init_page_objects()

                if not self._payment_page:
                    self._init_page_objects()
                if not self._payment_page:
                    raise AutomationError("PaymentPage failed to initialize")

                # --- Step 1: navigate to the date-wise anubandh page -----------------
                self._set_progress("पोर्टल: अनुबंध पेज खुल रहा है…")
                from app.services.pages.anubandh_datewise_page import (
                    DTWISE_URL,
                    AnubandhDateWisePage as AnubPage,
                )
                await self._page.goto(DTWISE_URL, wait_until="domcontentloaded", timeout=45000)
                await _portal_wait(self._page, 350)
                self._frame = None
                self._init_page_objects()
                await db_log("INFO", f"Portal print: on anubandh page {self._page.url}")

                # --- Step 2: click search to load today's bills -----------------------
                self._set_progress("पोर्टल: बिल खोजे जा रहे हैं…")
                await self._anubandh_page.select_all_crops_mode()
                await self._anubandh_page.set_today()
                rows = await self._anubandh_page.search_and_collect()
                await db_log("INFO", f"Portal print: search returned {len(rows)} bill(s)")
                if not rows:
                    await self._anubandh_page._dump_form("anubandh_no_rows")
                    raise AutomationError("No bills found on portal after search")

                # --- Step 3: find the row and click its select button ----------------
                self._set_progress("पोर्टल: बिल चुना जा रहा है…")
                gatepass_id = bill.get("gatepass_id", "")
                farmer_name = bill.get("farmer_name", "")
                selected = await self._click_anubandh_select(gatepass_id, farmer_name)
                if not selected:
                    await self._anubandh_page._dump_form("anubandh_select_failed")
                    raise AutomationError(
                        f"Could not find select button for bill {gatepass_id or farmer_name}"
                    )
                await _portal_wait(self._page, 1200)

                # The payment form may open in a new tab or in a frame → re-detect
                await self._detect_post_login_frame()
                self._init_page_objects()
                if not self._payment_page:
                    raise AutomationError("PaymentPage not available after bill select")

                # Diagnostic dump + screenshot (only when debugging)
                import os
                if os.environ.get("MANDI_DEBUG_DUMP"):
                    try:
                        await self._payment_page._dump_form("payment_form")
                        await self._page.screenshot(path="/tmp/opencode/payment_form.png", full_page=True)
                    except Exception as e:
                        await db_log("WARNING", f"Portal print: payment-form diagnostics failed: {e}")

                # --- Step 4: fill the payment form ------------------------------------
                self._set_progress("पोर्टल: भुगतान विवरण भरे जा रहे हैं…")
                # 4.1 field label = "कुल हम्माली एवं तौल, जो मूल्य में से काटी जायेगी"
                #     → fill hammali + taul COMBINED (not hammali alone).
                #     hammali_amount = what the user entered on the frontend (fallback
                #     to annotated amount); taul = weight × toul_rate (annotate sets it).
                hammali_amt = hammali_amount if hammali_amount > 0 else bill.get("hammali_amount", 0)
                toul_amt = bill.get("toul_amount", 0) or 0
                final_hammali = round(hammali_amt + toul_amt, 2)
                await db_log(
                    "INFO",
                    f"Portal print: filling कुल हम्माली एवं तौल = hammali {hammali_amt} + taul {toul_amt} = {final_hammali}",
                )
                await self._payment_page.fill_hammali(final_hammali)
                await _portal_wait(self._page, 500)  # let portal recompute payable
                await self._payment_page._trace_payment_state("after_hammali")

                # 4.2 tick नगद भुगतान (cash) option
                await self._payment_page.select_cash_payment()
                await self._payment_page._trace_payment_state("after_cash")

                # 4.3 amount = the "किसान को भुगतान योग्य राशि" shown in the form
                payable = await self._payment_page.read_payable_amount()
                if not payable or payable <= 0:
                    payable = bill.get("payable", 0) or (bill.get("gross_amount", 0) - final_hammali)
                    await db_log("WARNING", f"Portal print: payable not read from form, using {payable}")
                await self._payment_page.fill_cash_amount(payable)
                await self._payment_page._trace_payment_state("after_amount")

                # 4.4 date = today
                await self._payment_page.select_today_date()
                await self._payment_page._trace_payment_state("after_date")

                # 4.5 save
                self._set_progress("पोर्टल: सेव किया जा रहा है…")
                # Register the "page" listener + snapshot existing pages BEFORE the
                # Save/Yes/OK clicks. The print window can open on any of these clicks,
                # so the listener must exist before the first of them. The snapshot lets
                # us distinguish genuinely-new windows from stale ones left open by
                # previous prints (browser stays open across runs).
                import asyncio as _asyncio
                pages_before = set(self._page.context.pages)
                print_win_task = None
                try:
                    print_win_task = _asyncio.create_task(
                        self._page.context.wait_for_event("page", timeout=25000)
                    )
                except Exception:
                    print_win_task = None

                await self._payment_page.click_save()

                # --- Step 5: dismiss popups -------------------------------------------
                # (click_save() already clicked the "Yes, Proceed" confirmation:
                #  #btnRecheck / #btnProceedYes). Then a 2nd popup with OK appears.
                # IMPORTANT: clicking OK opens a NEW print window. The "page" listener
                # was registered above, BEFORE the Save click, so we cannot miss it.
                if self._popup_handler:
                    try:
                        await self._popup_handler.handle_ok_popup()
                        await self._popup_handler.handle_done_popup()
                    except Exception as e:
                        await db_log("WARNING", f"Portal print: popup handler failed (non-fatal): {e}")

                # --- Step 5.5: the OK click opens a NEW print window. ---------------
                # Await the pre-registered listener (cannot miss it now). Fallback:
                # scan existing pages, only accepting windows created after the save
                # (i.e. not in pages_before) to avoid stale windows from prior prints.
                print_done = False
                print_win = None
                if print_win_task is not None:
                    try:
                        print_win = await print_win_task
                    except Exception:
                        print_win = None
                if print_win is None:
                    for p in self._page.context.pages:
                        if (
                            p is not self._page
                            and p not in pages_before
                            and not p.is_closed()
                            and p.url
                        ):
                            print_win = p
                            await db_log("INFO", f"Portal print: print window from existing pages -> {p.url}")
                            break

                if print_win is not None:
                    try:
                        await print_win.wait_for_load_state("domcontentloaded")
                        await db_log("INFO", f"Portal print: new print window opened -> {print_win.url}")
                        # 2.5s wait as the user instructed (window needs time to render)
                        await _portal_wait(print_win, 2500)
                        # Print exactly ONE copy. We deliberately do NOT click a
                        # "Print" button and do NOT probe cascade windows: doing
                        # both earlier caused DOUBLE prints (the button itself
                        # triggers window.print(), and a cascade auto-prints too).
                        # With --kiosk-printing, a single window.print() call
                        # auto-prints exactly one copy to the default printer.
                        # Pre-scale to 95% so the whole bill fits ONE page.
                        if self._popup_handler:
                            await self._popup_handler.apply_print_scale(print_win)
                        await print_win.evaluate("window.print()")
                        await db_log("INFO", "Portal print: print triggered on new window")
                        print_done = True
                    except Exception as e:
                        await db_log("WARNING", f"Portal print: print window handling failed: {e}")
                        print_done = False

                if print_done:
                    self._set_progress("प्रिंट पूर्ण!")
                    await db_log("INFO", f"Portal print completed for {gatepass_id or farmer_name}")
                    self.state_machine.transition(AutomationState.IDLE)
                    return True

                # --- Step 6: portal auto-opens the print page after a successful save ---
                # (verified with the user: the portal itself navigates to the print page.
                #  Doing our own goto() races that navigation and closes the page.)
                self._set_progress("पोर्टल: प्रिंट पेज खुल रहा है…")
                print_page = None
                try:
                    await self._page.wait_for_url("**IndBhugtanPrint*", timeout=10000)
                    print_page = self._page
                    await db_log("INFO", "Portal print: same-tab navigation to print page detected")
                except Exception:
                    print_page = None
                if print_page is None:
                    # The portal may open the print page in a NEW tab instead.
                    try:
                        new_page = await self._page.context.wait_for_event("page", timeout=15000)
                        await new_page.wait_for_load_state("domcontentloaded")
                        await _portal_wait(new_page, 400)
                        print_page = new_page
                        await db_log("INFO", f"Portal print: new tab opened -> {new_page.url}")
                    except Exception:
                        await db_log("WARNING", "Portal print: no print page opened after save (checking current page)")
                        print_page = self._page

                # 6.1 dump the print page so we can see its structure (debug only)
                import os as _os
                if _os.environ.get("MANDI_DEBUG_DUMP"):
                    try:
                        await self._payment_page._dump_form("print_page")
                    except Exception:
                        pass

                # 6.2 set today's date on the print page (if it has a search form)
                today_str = date_cls.today().strftime("%d/%m/%Y")
                date_filled = False
                try:
                    date_inputs = await print_page.query_selector_all(
                        "input[type='text'][id*='date'], input[type='date'], input[name*='date']"
                    )
                    for inp in date_inputs:
                        try:
                            visible = await inp.is_visible()
                            if not visible:
                                continue
                            await inp.fill(today_str)
                            date_filled = True
                            await db_log("INFO", f"Portal print: filled date {today_str}")
                            break
                        except Exception:
                            continue
                except Exception:
                    pass

                # 6.3 if it is a searchable list page, click search to load bills
                self._set_progress("पोर्टल: प्रिंट बिल खोजे जा रहे हैं…")
                search_clicked = False
                try:
                    search_btns = await print_page.query_selector_all(
                        "input[type='submit'], button[type='submit'], #btnSearch, "
                        "a:has-text('Search'), input[value='Search'], "
                        "button:has-text('Search All'), input[value*='Search All']"
                    )
                    for btn in search_btns:
                        try:
                            if await btn.is_visible():
                                await btn.click()
                                await _portal_wait(print_page, 700)
                                await db_log("INFO", "Portal print: search clicked on print page")
                                search_clicked = True
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

                # 6.4 find the bill row and trigger its print
                self._set_progress("पोर्टल: बिल प्रिंट हो रहा है…")
                bill_found = False
                print_triggered = False
                try:
                    rows = await print_page.query_selector_all("table tbody tr")
                    for row in rows:
                        text = await row.inner_text()
                        if gatepass_id and gatepass_id in text:
                            bill_found = True
                        elif farmer_name and farmer_name in text:
                            bill_found = True
                        if bill_found:
                            checkbox = await row.query_selector("input[type='checkbox']")
                            if checkbox:
                                try:
                                    await checkbox.check()
                                    await db_log("INFO", f"Portal print: selected bill {gatepass_id}")
                                except Exception:
                                    pass
                            print_link = await row.query_selector(
                                "a[href*='print'], a:has-text('Print'), a:has-text('प्रिंट'), "
                                "input[value='Print'], button:has-text('Print')"
                            )
                            if print_link:
                                if self._popup_handler:
                                    await self._popup_handler.apply_print_scale(print_page)
                                await print_link.click()
                                await _portal_wait(print_page, 700)
                                await db_log("INFO", "Portal print: print link clicked")
                                print_triggered = True
                            break
                except Exception:
                    pass

                if not bill_found:
                    await db_log("WARNING", f"Portal print: bill {gatepass_id or farmer_name} not found on print page")

                # 6.5 handle the print popup / new tab
                try:
                    print_tab = await print_page.context.wait_for_event("page", timeout=10000)
                    await print_tab.wait_for_load_state("domcontentloaded")
                    await _portal_wait(print_tab, 400)
                    print_btns = await print_tab.query_selector_all(
                        "a:has-text('Print'), button:has-text('Print'), input[value='Print'], #btnPrint"
                    )
                    for btn in print_btns:
                        try:
                            if self._popup_handler:
                                await self._popup_handler.apply_print_scale(print_tab)
                            await btn.click()
                            await db_log("INFO", "Portal print: print triggered on print page")
                            print_triggered = True
                            break
                        except Exception:
                            continue
                except Exception:
                    await db_log("INFO", "Portal print: no new tab opened, print may have triggered directly")

                if not print_triggered and not bill_found:
                    await db_log(
                        "ERROR",
                        f"Portal print FALSE SUCCESS: no print triggered, print page was "
                        f"{print_page.url}, bill {gatepass_id or farmer_name} not found",
                    )
                    self.state_machine.transition(AutomationState.ERROR)
                    raise AutomationError(
                        f"Portal print failed: print was NOT triggered (print page: {print_page.url})"
                    )

                self._set_progress("प्रिंट पूर्ण!")
                await db_log("INFO", f"Portal print completed for {gatepass_id or farmer_name}")
                self.state_machine.transition(AutomationState.IDLE)
                return True

            except Exception as exc:
                self._set_progress("")
                import traceback
                tb = traceback.format_exc()
                await db_log("ERROR", f"Portal print failed: {exc}\n{tb}")
                self.state_machine.transition(AutomationState.ERROR)
                raise AutomationError(f"Portal print failed: {exc}") from exc

    async def print_url(self, url: str) -> bool:
        """Print a bill URL the way a human does:
        1. Open IndPrintBhugtanPatra.aspx
        2. CLICK the page's Print button (a <button type=submit>Text=Print>)
           → portal opens the printable page (often a NEW TAB).
        3. On that printable page: apply the PRINT_SCALE (95%) fit-to-one-page,
           then click ITS print button / trigger window.print()
           → --kiosk-printing physically prints to the default printer (HP).
        """
        async with self._lock:
            if self.state_machine.current_state not in (
                AutomationState.IDLE,
                AutomationState.ERROR,
                AutomationState.BILLS_LOADED,
            ):
                raise AutomationError(
                    f"Cannot print URL in state {self.state_machine.current_state.value}"
                )

            await db_log("INFO", f"Direct print of URL: {url}")
            if self.state_machine.current_state == AutomationState.IDLE:
                self.state_machine.transition(AutomationState.READY_TO_PRINT)
            self.state_machine.transition(AutomationState.PRINTING)
            self._set_progress("पोर्टल: प्रिंट पेज खोला जा रहा है…")

            try:
                if not self._page or self._page.is_closed():
                    await self._launch_browser()
                    config = await self.get_automation_config()
                    base = config.get("e_mandi_url", "")
                    if base:
                        await self._page.goto(base, wait_until="domcontentloaded", timeout=90000)
                    await self._detect_login_frame()
                    self._init_page_objects()
                    await self._login()
                    await self._detect_post_login_frame()
                    self._init_page_objects()

                # FAST: return as soon as navigation commits — no waiting for the
                # whole page to render. Then wait only for the Print button.
                await self._page.goto(url, wait_until="commit", timeout=45000)
                await _portal_wait(self._page, 300)

                # --- Step 2: click the page's Print button (human-like) ---
                print_btn = None
                clicked = False
                try:
                    print_btn = await self._page.wait_for_selector(
                        "button[type='submit']:has-text('Print'), "
                        "input[type='submit'][value='Print'], "
                        "a:has-text('Print'), button:has-text('Print')",
                        state="visible",
                        timeout=45000,
                    )
                except Exception:
                    print_btn = None
                    await db_log(
                        "INFO", "Direct print: Print button not found on page"
                    )

                new_tab = None
                if print_btn:
                    # Arm a popup-waiter BEFORE clicking, like a human reaching
                    # for the new window after pressing the button.
                    wait_task = None
                    if self._popup_handler:
                        wait_task = asyncio.create_task(
                            self._popup_handler.wait_for_new_tab(timeout_ms=12000)
                        )
                    try:
                        await print_btn.click()
                        clicked = True
                        await db_log("INFO", "Direct print: clicked page Print button")
                    except Exception as exc:
                        await db_log("WARNING", f"Print button click failed: {exc}")
                    if wait_task:
                        try:
                            new_tab = await asyncio.wait_for(wait_task, timeout=13000)
                        except Exception:
                            new_tab = None
                            await db_log("INFO", "No new tab after Print click")

                if not clicked and not new_tab:
                    await db_log("INFO", "Direct print: no visible Print button found")

                # --- Step 3: printable page (new tab, or same page) ---
                if new_tab is not None:
                    try:
                        await new_tab.wait_for_load_state("domcontentloaded")
                    except Exception:
                        pass
                    await _portal_wait(new_tab, 300)
                    await new_tab.bring_to_front()
                    await db_log(
                        "INFO",
                        f"Direct print: printable page opened (URL: {new_tab.url})",
                    )

                # Portal "print" popups often open about:blank and fill the body
                # via document.write() a moment later. Verify real content is
                # present; if the tab stays empty, fall back to the main receipt
                # page (guaranteed to hold the bill) so we never print blank.
                target = new_tab if new_tab is not None else self._page
                chosen_target = target
                if new_tab is not None:
                    content_ok = False
                    try:
                        content_ok = bool(
                            await new_tab.evaluate(
                                "() => { const t = (document.body && "
                                "document.body.innerText || '').trim(); "
                                "return t.length > 100 && /[0-9]/.test(t); }"
                            )
                        )
                    except Exception:
                        content_ok = False
                    if not content_ok:
                        try:
                            await new_tab.wait_for_timeout(1000)
                        except Exception:
                            pass
                        try:
                            content_ok = bool(
                                await new_tab.evaluate(
                                    "() => { const t = (document.body && "
                                    "document.body.innerText || '').trim(); "
                                    "return t.length > 100 && /[0-9]/.test(t); }"
                                )
                            )
                        except Exception:
                            content_ok = False
                    if not content_ok:
                        await db_log(
                            "WARNING",
                            "Printable tab empty after wait; printing main recei"
                            "pt page instead",
                        )
                        chosen_target = self._page
                    else:
                        await db_log("INFO", "Printable tab has bill content")
                        chosen_target = new_tab
                target = chosen_target

                # Fit to ONE page at PRINT_SCALE (95%) before triggering print.
                if self._popup_handler:
                    await self._popup_handler.apply_print_scale(target)

                # Click the printable page's own print trigger if it has one,
                # else window.print() — both go to the default printer via
                # --kiosk-printing.
                printed_now = False
                for sel in (
                    "a:has-text('Print'), button:not([type='submit']):has-text('Print'), "
                    "input[type='button'][value='Print'], "
                    "a:has-text('प्रिंट'), button:not([type='submit']):has-text('प्रिंट')",
                ):
                    try:
                        cands = await target.query_selector_all(sel)
                    except Exception:
                        continue
                    for b in cands:
                        try:
                            if await b.is_visible():
                                # Multiple identical print buttons exist; clicking
                                # one triggers the page's print so we stop there.
                                await b.click()
                                printed_now = True
                                break
                        except Exception:
                            continue
                    if printed_now:
                        break

                if printed_now:
                    await db_log("INFO", "Direct print: clicked printable page Print button")
                    # Allow the button's own print() to fire (single job, scaled).
                    try:
                        await target.evaluate("window.__allowPrint = true;")
                    except Exception:
                        pass
                else:
                    await target.evaluate(
                        "() => { window.__allowPrint = true; window.print(); }"
                    )
                    await db_log("INFO", "Direct print: window.print() on printable page")

                await _portal_wait(target, 300)
                # A portal printable page may fire its own print after the button
                # click settles — give it a beat so that also lands.
                await _portal_wait(target, 500)

                if new_tab is not None:
                    try:
                        await new_tab.close()
                    except Exception:
                        pass
                await db_log("INFO", f"Direct print triggered for {url}")
                self._set_progress("प्रिंट पूर्ण!")
                self.state_machine.transition(AutomationState.IDLE)
                return True
            except Exception as exc:
                try:
                    await db_log("ERROR", f"Direct print failed: {exc}")
                except Exception:
                    pass
                self._set_progress("")
                try:
                    self.state_machine.transition(AutomationState.ERROR)
                except Exception:
                    pass
                await self.close_browser()
                raise AutomationError(f"Direct print failed: {exc}") from exc

    async def inspect_print_page(self, url: str) -> Dict[str, Any]:
        """DRY RUN: open the URL (login if needed) and report what the print
        controls actually are, WITHOUT printing. Used to tell whether the page's
        Print button is a real print or a server-side PDF download."""
        async with self._lock:
            if not self._page or self._page.is_closed():
                await self._launch_browser()
                config = await self.get_automation_config()
                base = config.get("e_mandi_url", "")
                if base:
                    await self._page.goto(base, wait_until="domcontentloaded", timeout=90000)
                await self._detect_login_frame()
                self._init_page_objects()
                await self._login()
                await self._detect_post_login_frame()
                self._init_page_objects()

            await self._page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await _portal_wait(self._page, 1500)
            info = await self._page.evaluate(
                """() => {
                    const out = {title: document.title, url: location.href,
                                 printControls: [], pdfLikeLinks: []};
                    const all = document.querySelectorAll(
                        "a, button, input[type=button], input[type=submit], input[type=image]");
                    all.forEach(el => {
                        const text = (el.innerText || el.value || el.getAttribute('alt') || '').trim();
                        const id = el.id || '';
                        const href = (el.getAttribute && el.getAttribute('href')) || '';
                        const onclick = (el.getAttribute && el.getAttribute('onclick')) || '';
                        const hay = (text + ' ' + id + ' ' + href + ' ' + onclick);
                        if (/print|प्रिंट|download|export|pdf/i.test(hay)) {
                            out.printControls.push({
                                tag: el.tagName, id, text: text.slice(0, 40),
                                href: href.slice(0, 200), onclick: onclick.slice(0, 200),
                                type: el.type || '', target: el.target || '',
                                download: el.getAttribute('download') || ''
                            });
                        }
                    });
                    return out;
                }"""
            )
            try:
                await db_log("INFO", f"Print page inspect: {info}")
            except Exception:
                pass
            return info

    async def _click_anubandh_select(
        self, gatepass_id: str, farmer_name: str
    ) -> bool:
        """Find the bill row on the anubandh grid and click its select button.

        The grid is rendered by the ASMX search. Each row has a select control
        (button/link/input). We match the row by gatepass id or farmer name and
        click the select control inside it.
        """
        # Prefer the content frame if we have one
        ctx = self._frame or self._page
        rows = await ctx.query_selector_all(
            "table tbody tr, #grdBhugtan tbody tr, #grdAnubandh tbody tr, table tr"
        )
        await db_log("INFO", f"Portal print: scanning {len(rows)} grid row(s) for select")
        for row in rows:
            try:
                text = await row.inner_text()
            except Exception:
                continue
            if not text:
                continue
            if gatepass_id and gatepass_id in text:
                pass
            elif farmer_name and farmer_name in text:
                pass
            else:
                continue

            # Within the matched row find a select control
            for sel in (
                "button:has-text('select'), button:has-text('Select'), button:has-text('चुने')",
                "a:has-text('select'), a:has-text('Select'), a:has-text('चुने')",
                "input[type='button'][value*='elect'], input[type='submit'][value*='elect']",
                "input[type='button'], input[type='submit'], input[type='image']",
                "button",
            ):
                ctrl = await row.query_selector(sel)
                if ctrl:
                    try:
                        await ctrl.click()
                        await db_log("INFO", f"Portal print: clicked select ({sel}) for {gatepass_id or farmer_name}")
                        return True
                    except Exception as e:
                        await db_log("WARNING", f"Portal print: select click failed ({sel}): {e}")
                        # try the whole row as fallback
                        try:
                            await row.click()
                            await db_log("INFO", "Portal print: clicked whole row fallback")
                            return True
                        except Exception:
                            continue
            # If no select control found, clicking the whole row may still open the form
            try:
                await row.click()
                await db_log("INFO", "Portal print: no select control, clicked row")
                return True
            except Exception:
                continue
        return False

    async def save_payment_info(
        self, bill_id: int, account_holder: str, bank_name: str,
        account_number: str, ifsc_code: str,
    ) -> bool:
        async with async_session_factory() as session:
            bill = await session.get(Bill, bill_id)
            if not bill:
                raise AutomationError(f"Bill #{bill_id} not found")
            bill.account_holder = account_holder
            bill.bank_name = bank_name
            bill.account_number = account_number
            bill.ifsc_code = ifsc_code
            await session.commit()
        await db_log("INFO", f"Payment info saved for bill #{bill_id}")
        return True

    async def cancel(self) -> None:
        async with self._lock:
            await self.close_browser()
            self._found_bills = []
            self._current_bill_data = None
            self._page = None
            self._frame = None
            self.state_machine.reset()
            await db_log("INFO", "Automation cancelled")

    # ------------------------------------------------------------------
    # CAPTCHA
    # ------------------------------------------------------------------

    async def get_captcha_image(self) -> Optional[dict]:
        return {"image": self._captcha_image_b64}

    async def wait_for_manual_captcha(self, timeout: int = 180) -> str:
        if self.state_machine.current_state is not AutomationState.AWAITING_CAPTCHA:
            self.state_machine.transition(AutomationState.AWAITING_CAPTCHA)
        target = self._frame if self._frame else self._page
        self._captcha_image_b64 = None
        try:
            el = await target.query_selector("#captchaImage")
            if el:
                await target.wait_for_function(
                    "() => { const el = document.querySelector('#captchaImage'); return !el || el.tagName !== 'IMG' || (el.complete && el.naturalWidth > 0); }",
                    timeout=10000,
                )
                ss = await el.screenshot()
                self._captcha_image_b64 = base64.b64encode(ss).decode()
        except Exception as exc:
            await db_log("WARNING", f"CAPTCHA capture failed: {exc}")
            self._captcha_image_b64 = None

        self._captcha_event = asyncio.Event()
        self._captcha_input = None
        try:
            await asyncio.wait_for(self._captcha_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise AutomationError("CAPTCHA input timeout")
        text = self._captcha_input or ""
        self._captcha_input = None
        self._captcha_event = None
        return text

    async def submit_manual_captcha(self, text: str) -> bool:
        if self._captcha_event is None:
            return False
        self._captcha_input = text
        self._captcha_event.set()
        return True

    async def close_browser(self) -> None:
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as exc:
            logger.warning("Error closing browser: %s", exc)
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._frame = None

    async def _ensure_logged_in(self) -> bool:
        """Check if logged in; re-login if session expired. Returns True if OK."""
        try:
            if not self._page or self._page.is_closed():
                return False
            login_frame = await self._detect_login_frame()
            if login_frame is None:
                return True  # already logged in
            # Session expired — re-login
            await db_log("INFO", "Session expired, re-logging in…")
            self._set_progress("सेशन एक्सपायर — पुनः लॉगिन…")
            await self._login()
            await self._detect_post_login_frame()
            self._init_page_objects()
            await db_log("INFO", "Re-login successful")
            return True
        except Exception as exc:
            await db_log("WARNING", f"Re-login failed: {exc}")
            return False

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    async def get_automation_config(self) -> Dict[str, Any]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Setting).where(Setting.key.in_([
                    "hammali_rate", "cash_threshold", "automation_timeout",
                    "auto_close_browser", "e_mandi_url", "e_mandi_username",
                    "e_mandi_password", "ignore_https_errors",
                ]))
            )
            rows = result.scalars().all()
            config = {r.key: r.value for r in rows}
        return {
            "hammali_rate": float(config.get("hammali_rate", settings.DEFAULT_HAMMALI_RATE)),
            "cash_threshold": float(config.get("cash_threshold", settings.DEFAULT_CASH_THRESHOLD)),
            "automation_timeout": int(config.get("automation_timeout", settings.DEFAULT_AUTOMATION_TIMEOUT)),
            "auto_close_browser": config.get("auto_close_browser", str(settings.DEFAULT_AUTO_CLOSE_BROWSER)).lower() == "true",
            "ignore_https_errors": config.get("ignore_https_errors", "true").lower() == "true",
            "e_mandi_url": config.get("e_mandi_url", ""),
            "has_credentials": bool(config.get("e_mandi_username") and config.get("e_mandi_password")),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _init_page_objects(self) -> None:
        self._login_page = LoginPage(self._page, self._frame)
        self._payment_page = PaymentPage(self._page, self._frame)
        self._popup_handler = PopupHandler(self._page, self._frame)
        self._anubandh_page = AnubandhDateWisePage(self._page, self._frame)

    async def _detect_post_login_frame(self) -> None:
        self._frame = None
        # The login frame (loginTrader.aspx) may linger after PIN submit while the
        # portal navigates the app frame to WelcomeTrader.aspx. Wait for a non-login
        # frame that actually carries content before treating login as complete.
        deadline = self._page.context.browser is not None
        for _ in range(10):
            available_frames = []
            for f in self._page.frames:
                try:
                    src = await f.evaluate("window.location.href")
                    available_frames.append(src)
                except Exception:
                    available_frames.append("<error>")
            non_login = []
            for f in self._page.frames:
                if f == self._page.main_frame:
                    continue
                try:
                    src = await f.evaluate("window.location.pathname") or ""
                except Exception:
                    continue
                if "loginTrader" in src or "LoginForm" in src:
                    continue
                try:
                    body = await f.inner_text("body")
                except Exception:
                    continue
                if body and body.strip():
                    non_login.append((f, await f.evaluate("window.location.href"), len(body.strip())))
            if non_login:
                non_login.sort(key=lambda x: x[2], reverse=True)
                self._frame = non_login[0][0]
                await db_log("INFO", f"Frames after login: {available_frames}")
                await db_log("INFO", f"Using frame: {non_login[0][1]}")
                return
            await _portal_wait(self._page, 600)

        await db_log("INFO", f"Frames after login (no non-login frame found): {available_frames}")
        main_url = self._page.url
        if "Trader.aspx" in main_url or "trader" in main_url.lower():
            for f in self._page.frames:
                if f != self._page.main_frame:
                    try:
                        body = await f.inner_text("body")
                        if body.strip():
                            self._frame = f
                            await db_log("INFO", f"Using frame: {await f.evaluate('window.location.href')}")
                            break
                    except Exception:
                        continue

    async def _detect_login_frame(self) -> None:
        self._frame = None
        for f in self._page.frames:
            try:
                src = await f.evaluate("window.location.pathname")
                if "loginTrader" in src or "LoginForm" in src:
                    self._frame = f
                    break
            except Exception:
                continue

    async def _get_credentials(self) -> tuple[str, str]:
        async with async_session_factory() as session:
            user_row = (await session.execute(
                select(Setting).where(Setting.key == "e_mandi_username")
            )).scalar_one_or_none()
            pass_row = (await session.execute(
                select(Setting).where(Setting.key == "e_mandi_password")
            )).scalar_one_or_none()

        if not user_row or not pass_row:
            raise LoginError("e-Mandi credentials not configured")

        username = user_row.value
        try:
            password = decrypt_value(pass_row.value)
        except Exception as exc:
            raise LoginError(f"Failed to decrypt credentials: {exc}") from exc
        return username, password

    async def _login(self) -> None:
        username, password = await self._get_credentials()
        await db_log("INFO", "Automation — login started")

        await self._login_page.dismiss_sweetalert()
        await self._login_page.fill_username(username)
        await self._login_page.fill_password(password)

        OCR_TRIES = 3
        MANUAL_CAPTCHA_TIMEOUT = 180  # 3 minutes — user needs time

        attempt = 0
        while True:
            attempt += 1
            captcha_text = None

            # 1) Try automatic OCR solving first, but only on the FIRST pass.
            #    Once we fall back to manual input, keep using manual input —
            #    re-running OCR on every failed attempt wastes time and the user
            #    already proved OCR cannot read this captcha.
            if attempt == 1:
                from app.services.captcha_solver import solve_captcha_async

                for ocr_try in range(OCR_TRIES):
                    try:
                        captcha_text = await solve_captcha_async(self._page, self._frame)
                    except Exception as exc:
                        await db_log("WARNING", f"CAPTCHA OCR attempt failed: {exc}")
                    if captcha_text:
                        self._captcha_fails = 0
                        break
                    self._captcha_fails += 1
                    await db_log(
                        "INFO",
                        f"OCR did not solve CAPTCHA (try {ocr_try+1}/{OCR_TRIES}, fails={self._captcha_fails})",
                    )
                    try:
                        await self._login_page.reload_captcha()
                    except Exception:
                        pass

            # 2) If OCR failed (or this is a retry after a wrong answer), transfer
            #    the fresh CAPTCHA to the mobile page and wait for manual input.
            #    wait_for_manual_captcha() re-captures the CURRENT captcha image,
            #    so after a failed attempt the user always gets the NEW captcha.
            if not captcha_text:
                await db_log(
                    "INFO", "Requesting manual CAPTCHA from mobile page"
                )
                # Set state so frontend shows captcha dialog
                try:
                    self.state_machine.transition(AutomationState.AWAITING_CAPTCHA)
                except Exception:
                    pass  # Already in a valid state
                captcha_text = await self.wait_for_manual_captcha(
                    timeout=MANUAL_CAPTCHA_TIMEOUT
                )
                # Transition back to searching after manual captcha
                try:
                    self.state_machine.transition(AutomationState.SEARCHING)
                except Exception:
                    pass
            if not captcha_text:
                raise LoginError(
                    "CAPTCHA input timeout — no manual answer provided"
                )

            await self._login_page.fill_captcha(captcha_text)
            await self._login_page.click_login()
            success, err = await self._login_page.wait_after_login(30000)
            if success:
                self._captcha_fails = 0
                await self._login_page.handle_pin()
                await db_log("INFO", "Login successful")
                return

            # Wrong CAPTCHA/credentials: the portal shows an OK popup. Dismiss it,
            # re-enter credentials (the portal may have cleared them) and load a
            # FRESH CAPTCHA, then loop back to the mobile page. The session stays
            # alive — we do NOT raise after a fixed number of attempts, so the
            # user can keep trying from the phone.
            await db_log("WARNING", f"Login attempt {attempt} failed: {err}")
            await self._login_page.dismiss_sweetalert()
            await self._login_page.wait_for_timeout(500)
            try:
                await self._login_page.fill_username(username)
                await self._login_page.fill_password(password)
            except Exception as exc:
                await db_log("WARNING", f"Could not re-fill credentials: {exc}")
            try:
                await self._login_page.reload_captcha()
            except Exception:
                pass

    async def _launch_browser(self, retries: int = 3) -> None:
        """Launch the visible automation browser with --kiosk-printing.

        The first launch attempt inside a freshly started uvicorn occasionally
        dies with 'Connection closed while reading from the driver' even though
        a standalone launch works — so we retry with backoff and clean partial
        driver state between attempts.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            await db_log("INFO", "Launching browser")
            pw = browser = context = page = None
            try:
                from playwright.async_api import async_playwright

                config = await self.get_automation_config()

                pw = await async_playwright().start()
                browser = await pw.chromium.launch(
                    headless=False,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--kiosk-printing",
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--no-first-run",
                        "--disable-extensions",
                        "--disable-background-networking",
                    ],
                )
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    ignore_https_errors=config.get("ignore_https_errors", True),
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                # Gate window.print so popups/auto-print scripts can NOT fire an
                # unscaled print on load. Only OUR explicit trigger (which sets
                # __allowPrint after the PRINT_SCALE is applied) prints —
                # exactly one job, at the right scale, to the default printer.
                await context.add_init_script(
                    "(() => {"
                    "  if (window.__printGated) return;"
                    "  window.__printGated = true;"
                    "  window.__allowPrint = false;"
                    "  const orig = window.print.bind(window);"
                    "  window.print = () => { if (window.__allowPrint) orig(); };"
                    "})();"
                )
                page = await context.new_page()

                self._playwright = pw
                self._browser = browser
                self._context = context
                self._page = page
                await db_log("INFO", "Browser launched successfully")
                return
            except ImportError:
                raise AutomationError(
                    "Playwright is not installed. Run: playwright install chromium"
                )
            except Exception as exc:
                last_exc = exc
                await db_log(
                    "WARNING",
                    f"Browser launch attempt {attempt + 1}/{retries} failed: {exc}",
                )
                for obj in (page, context, browser, pw):
                    if obj is None:
                        continue
                    try:
                        close = getattr(obj, "close", None) or getattr(obj, "stop", None)
                        if close:
                            await close()
                    except Exception:
                        pass
                self._page = None
                self._context = None
                self._browser = None
                self._playwright = None
                if attempt < retries - 1:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                raise NetworkError(f"Failed to launch browser: {last_exc}") from last_exc

    async def _persist_bill(self, details: Dict[str, Any]) -> Bill:
        async with async_session_factory() as session:
            bill = Bill(
                trader_name=details.get("trader_name", "Unknown"),
                trader_id=details.get("trader_id"),
                bill_number=details.get("bill_number", "N/A"),
                commodity=details.get("commodity", "Unknown"),
                date=details.get("date") or datetime.utcnow(),
                vehicle_number=details.get("vehicle_number"),
                weight=details.get("weight", 0),
                rate=details.get("rate"),
                gross_amount=details.get("gross_amount", 0),
                hammali_rate=details.get("hammali_rate", settings.DEFAULT_HAMMALI_RATE),
                hammali_amount=details.get("hammali_amount", 0),
                total_amount=details.get("total_amount", 0),
                raw_data=details,
            )
            session.add(bill)
            await session.commit()
            await session.refresh(bill)
            return bill

    async def _load_bill(self, bill_id: int) -> Optional[Bill]:
        async with async_session_factory() as session:
            return await session.get(Bill, bill_id)

    async def _get_hammali_rate(self) -> float:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Setting).where(Setting.key == "hammali_rate")
            )
            row = result.scalar_one_or_none()
            if row:
                try:
                    return float(row.value)
                except (ValueError, TypeError):
                    pass
            return settings.DEFAULT_HAMMALI_RATE

    # ------------------------------------------------------------------
    # Reports: Gatepass Auction Taul Count + Auction Detail Data
    # ------------------------------------------------------------------

    async def search_reports(self) -> Dict[str, Any]:
        """Run the reports flow:
        1. Open Gatepass Auction Taul Count page
        2. Select today's date → Search All Data
        3. Collect results, identify bills with tol pending
        4. For each pending bill, go to Auction Detail Data → search gatepass → get mobile
        5. Return structured data
        """
        from datetime import date as date_cls

        today = date_cls.today()
        result_data: Dict[str, Any] = {
            "date": today.strftime("%d-%m-%Y"),
            "total_gatepasses": 0,
            "tol_pending_count": 0,
            "gatepasses": [],
        }

        async with self._lock:
            if self.state_machine.current_state not in (
                AutomationState.IDLE,
                AutomationState.ERROR,
                AutomationState.BILLS_LOADED,
            ):
                raise AutomationError(
                    f"Cannot start reports in state {self.state_machine.current_state.value}"
                )

            try:
                self._set_progress("रिपोर्ट: ब्राउज़र खोला जा रहा है…")
                self.state_machine.transition(AutomationState.SEARCHING)
                await self._launch_browser()
                config = await self.get_automation_config()
                url = config.get("e_mandi_url", "")
                if not url:
                    raise AutomationError("e-Mandi URL not configured")
                self._set_progress("रिपोर्ट: पोर्टल लोड…")
                await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await self._detect_login_frame()
                self._init_page_objects()
                self._set_progress("रिपोर्ट: लॉगिन…")
                await self._login()
                await self._detect_post_login_frame()
                self._init_page_objects()

                # Step 1: Navigate to Gatepass Auction Taul Count
                self._set_progress("रिपोर्ट: गेटपास टौल काउंट लोड…")
                await self._ensure_logged_in()
                taul_page = GatepassTaulCountPage(self._page, self._frame)
                await taul_page.navigate()
                await taul_page.set_date(today)

                # Step 2: Search and collect (max 2 min timeout)
                self._set_progress("रिपोर्ट: डेटा खोजा जा रहा है…")
                raw_rows = await taul_page.search_and_collect(timeout_sec=120)
                gatepasses = GatepassTaulCountPage.parse_gatepass_rows(raw_rows)

                result_data["total_gatepasses"] = len(gatepasses)
                result_data["gatepasses"] = gatepasses

                # Step 3: Identify tol-pending bills
                pending = [g for g in gatepasses if g.get("tol_pending")]
                result_data["tol_pending_count"] = len(pending)
                await db_log(
                    "INFO",
                    f"Reports: {len(gatepasses)} gatepasses, {len(pending)} tol-pending",
                )

                # Step 4: For each pending bill, get mobile from Auction Detail Data
                if pending:
                    self._set_progress("रिपोर्ट: ऑक्शन डिटेल लोड…")
                    await self._ensure_logged_in()
                    detail_page = AuctionDetailDataPage(self._page, self._frame)
                    await detail_page.navigate()
                    await _portal_wait(self._page, 600)

                    for idx, g in enumerate(pending):
                        gp_id = g.get("gatepass_id", "")
                        if not gp_id:
                            continue
                        self._set_progress(f"रिपोर्ट: गेटपास {idx+1}/{len(pending)} ({gp_id})")
                        await db_log("INFO", f"Reports: looking up gatepass {gp_id}")
                        try:
                            detail = await detail_page.search_by_gatepass(gp_id)
                            if detail.get("mobile_no"):
                                g["mobile_no"] = detail["mobile_no"]
                                await db_log(
                                    "INFO",
                                    f"Reports: gatepass {gp_id} → mobile {detail['mobile_no']}",
                                )
                            for key in ("trader_name", "commodity", "weight"):
                                if detail.get(key) and not g.get(key):
                                    g[key] = detail[key]
                        except Exception as exc:
                            await db_log("WARNING", f"Reports: gatepass {gp_id} lookup failed: {exc}")

                self._set_progress("रिपोर्ट पूर्ण!")
                self.state_machine.transition(AutomationState.IDLE)
                await self.close_browser()
                return result_data

            except (LoginError, NetworkError):
                self._set_progress("")
                try:
                    self.state_machine.transition(AutomationState.ERROR)
                except Exception:
                    pass
                await self.close_browser()
                raise
            except asyncio.CancelledError:
                self._set_progress("")
                try:
                    self.state_machine.transition(AutomationState.ERROR)
                except Exception:
                    pass
                await self.close_browser()
                raise
            except Exception as exc:
                self._set_progress("")
                import traceback as _tb
                await db_log("WARNING", f"Reports flow failed: {exc}\n{_tb.format_exc()}")
                try:
                    self.state_machine.transition(AutomationState.ERROR)
                except Exception:
                    pass
                await self.close_browser()
                raise AutomationError(f"Reports flow failed: {exc}") from exc
