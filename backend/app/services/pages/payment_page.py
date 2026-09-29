from app.services.logging_service import log as db_log
from app.services.pages.base_page import BasePage


class PaymentPage(BasePage):
    # Exact control IDs as dumped from the live portal form
    # (Ins_eMandiAnubandh_BP_DTWise.aspx payment sheet).
    HAMMALI_INPUT_SEL = (
        "#txt_H_DeductedPrice, "
        "input[name='HT'], "
        "input[id*='H_Deducted'], "
        "input[name*='hammali'], input[id*='hammali'], input[placeholder*='हम्माल']"
    )
    CASH_RADIO_SEL = (
        "#rb_Cash, "
        "input[type='radio'][value='C'], "
        "input[type='radio'][name='chkType']:nth-of-type(3)"
    )
    AMOUNT_INPUT_SEL = "#txt_fee, input[name='fee']:not(#txt_BothPay)"
    # NOTE: do NOT match input[name='TT'] here — the form has TWO name='TT'
    # fields: #total_ToulMulya (तौल, value 0) and #txt_TotalPrice_Farmer
    # (payable). query_selector returns the FIRST DOM match, which is the
    # taul field, so the payable would read 0. Match by exact id only.
    PAYABLE_SEL = "#txt_TotalPrice_Farmer, input[placeholder*='भुगतान योग्य']"
    DATE_INPUT_SEL = (
        "#datepicker_CashDate, "
        "#datepicker_Bhugtan, "
        "input[name*='date'], input[id*='date'], input[placeholder*='दिनांक']"
    )
    SAVE_BTN_SEL = "#btn_show, input[value='Save']"
    PROCEED_YES_SEL = "#btnProceedYes"
    PROCEED_NO_SEL = "#btnProceedNo"
    RECHECK_BTN_SEL = "#btnRecheck"

    async def _dump_form(self, tag: str = "") -> None:
        """Log every input/select/button in the frame with its state, for debugging."""
        try:
            ctx = self.ctx
            try:
                url = await ctx.evaluate("window.location.href")
            except Exception:
                url = await self._page.evaluate("window.location.href")
            await db_log("INFO", f"[form dump {tag}] page url: {url}")
            controls = await ctx.query_selector_all(
                "input, select, textarea, button, a[role='button']"
            )
            await db_log("INFO", f"[form dump {tag}] found {len(controls)} controls")
            for c in controls:
                try:
                    tag_name = await c.evaluate("e => e.tagName")
                    t = await c.get_attribute("type") or ""
                    name = await c.get_attribute("name") or ""
                    ident = await c.get_attribute("id") or ""
                    val = await c.get_attribute("value") or ""
                    ph = await c.get_attribute("placeholder") or ""
                    disabled = await c.is_disabled()
                    readonly = await c.get_attribute("readonly") or ""
                    visible = await c.is_visible()
                    txt = (await c.inner_text() or "").strip()[:20] if tag_name.upper() in ("BUTTON", "A") else ""
                    await db_log(
                        "INFO",
                        f"[form dump {tag}] <{tag_name.lower()} type={t!r} name={name!r} id={ident!r} "
                        f"value={val!r} ph={ph!r} disabled={disabled} readonly={bool(readonly)} "
                        f"visible={visible} text={txt!r}>",
                    )
                except Exception:
                    continue
            try:
                await self._page.screenshot(
                    path=f"/tmp/opencode/form_dump_{tag}.png", full_page=True
                )
                await db_log("INFO", f"[form dump {tag}] screenshot saved")
            except Exception:
                pass
        except Exception as e:
            await db_log("WARNING", f"[form dump {tag}] failed: {e}")

    async def _trace_payment_state(self, tag: str) -> None:
        """Log key payment-field values (lightweight, no full dump)."""
        try:
            keys = {
                "hammali": self.HAMMALI_INPUT_SEL,
                "amount": self.AMOUNT_INPUT_SEL,
                "payable": self.PAYABLE_SEL,
                "cash_radio": "#rb_Cash",
                "date_cash": "#datepicker_CashDate",
                "date_bhugtan": "#datepicker_Bhugtan",
                "save_btn": self.SAVE_BTN_SEL,
            }
            parts = []
            for label, sel in keys.items():
                try:
                    el = await self.ctx.query_selector(sel)
                    if el:
                        v = await el.evaluate("e => e.value") or ""
                        parts.append(f"{label}={v!r}")
                except Exception:
                    continue
            await db_log("INFO", f"[trace {tag}] " + " | ".join(parts))
        except Exception as e:
            await db_log("WARNING", f"[trace {tag}] failed: {e}")

    async def _smart_type(self, sel: str, value: str, label: str) -> bool:
        """Fill a field by SIMULATING REAL KEYBOARD TYPING.

        The portal recomputes payable/gross only when the hammali field
        receives keydown/keyup events (a manual paste via fill() does NOT
        trigger it). So we click into the field, clear it, and type char by
        char like a human would.
        """
        field = await self.ctx.query_selector(sel)
        if not field:
            await db_log("WARNING", f"{label}: no element for selector {sel}")
            return False
        try:
            await field.click()
            await self._page.keyboard.press("ControlOrMeta+a")
            await self._page.keyboard.press("Delete")
            await field.type(value, delay=12)
            await self._page.keyboard.press("Tab")
            await db_log("INFO", f"{label}: typed {value}")
            return True
        except Exception as e:
            await db_log("WARNING", f"{label}: typing failed ({e}) — falling back to JS value set")
            try:
                await field.evaluate(
                    """(el, v) => {
                        el.removeAttribute('disabled');
                        el.readOnly = false;
                        el.value = v;
                        el.dispatchEvent(new Event('keydown', {bubbles: true}));
                        el.dispatchEvent(new Event('keyup', {bubbles: true}));
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }""",
                    value,
                )
                await db_log("INFO", f"{label}: JS keydown fallback set {value}")
                return True
            except Exception as e2:
                await db_log("ERROR", f"{label}: JS fallback failed: {e2}")
                return False

    async def _smart_fill(self, sel: str, value: str, label: str) -> bool:
        """Fill a field, handling disabled/readonly elements via JS if needed."""
        field = await self.ctx.query_selector(sel)
        if not field:
            await db_log("WARNING", f"{label}: no element for selector {sel}")
            return False
        try:
            await field.fill(value)
            await db_log("INFO", f"{label}: filled {value}")
            return True
        except Exception:
            await db_log("WARNING", f"{label}: fill() failed — trying JS fallback")
            try:
                await field.evaluate(
                    """(el, v) => {
                        el.removeAttribute('disabled');
                        el.readOnly = false;
                        el.value = v;
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }""",
                    value,
                )
                await db_log("INFO", f"{label}: JS-fallback filled {value}")
                return True
            except Exception as e2:
                await db_log("ERROR", f"{label}: JS fallback failed: {e2}")
                return False

    async def fill_hammali(self, amount: float) -> None:
        # MUST be typed (not pasted): the portal recomputes payable only on
        # keydown/keyup. fill()/paste leaves it at 0.
        ok = await self._smart_type(self.HAMMALI_INPUT_SEL, str(amount), "hammali")
        if not ok:
            await db_log("ERROR", "Hammali input not found — cannot proceed (no tab fallback)")
            await self._dump_form("hammali_missing")
        await self.wait_for_timeout(400)

    async def select_cash_payment(self) -> None:
        radio = await self.ctx.query_selector(self.CASH_RADIO_SEL)
        if radio:
            try:
                await radio.check(timeout=2500)
                await db_log("INFO", "Cash payment selected (explicit selector)")
                await self.wait_for_timeout(150)
                return
            except Exception:
                await db_log("WARNING", "Cash radio check() failed — JS fallback")
        radios = await self.ctx.query_selector_all("input[type='radio']")
        picked = False
        for r in radios:
            try:
                label = (await r.get_attribute("value") or "") + " " + (await r.evaluate("e => (e.parentElement ? e.parentElement.innerText : '') || ''") or "")
                if any(k in label.lower() for k in ["नगद", "cash", "नकद"]):
                    await r.evaluate(
                        """(el) => { el.removeAttribute('disabled'); el.checked = true;
                            el.dispatchEvent(new Event('click', {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true})); }"""
                    )
                    await db_log("INFO", f"Cash payment selected via JS: {label.strip()[:40]}")
                    picked = True
                    break
            except Exception:
                continue
        if not picked and radios:
            try:
                await radios[0].evaluate(
                    """(el) => { el.removeAttribute('disabled'); el.checked = true;
                        el.dispatchEvent(new Event('click', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true})); }"""
                )
                await db_log("INFO", "Cash payment selected (first radio fallback)")
            except Exception as e:
                await db_log("ERROR", f"Could not select any radio: {e}")
                await self._dump_form("radio_fallback")
        await self.wait_for_timeout(150)

    async def fill_cash_amount(self, amount: float) -> None:
        ok = await self._smart_fill(self.AMOUNT_INPUT_SEL, str(int(amount)), "cash_amount")
        if not ok:
            await db_log("ERROR", "Amount input not found — cannot proceed (no tab fallback)")
            await self._dump_form("amount_missing")
        await self.wait_for_timeout(300)

    async def read_payable_amount(self) -> float:
        """Read 'किसान को भुगतान योग्य राशि' from the payment form and return the amount.

        The portal shows the computed payable in a disabled field
        (#txt_TotalPrice_Farmer, name='TT'). It is recomputed by the portal
        JS after hammali is entered. We read that value.
        """
        try:
            ctx = self.ctx
            # 1) The exact payable field known from the live form dump.
            #    Poll for up to ~3s: the portal recomputes it AFTER the hammali
            #    keydown/keyup (typing), so it is empty at first read.
            for _ in range(6):
                field = await ctx.query_selector(self.PAYABLE_SEL)
                if field:
                    val = await field.evaluate("el => el.value") or ""
                    parsed = self._parse_amount(val)
                    if parsed is not None and parsed > 0:
                        await db_log("INFO", f"Payable read from {self.PAYABLE_SEL}: {parsed}")
                        return parsed
                    await self.wait_for_timeout(500)
            await db_log("INFO", f"Payable field value raw: {val!r} — scanning further")
            # 2) Try inputs whose id/name/placeholder mentions payable/भुगतान योग्य
            for sel in (
                "input[id*='payable']",
                "input[name*='payable']",
                "input[placeholder*='भुगतान योग्य']",
                "input[id*='NetAmt']",
                "input[id*='netamt']",
                "input[id*='PayableAmt']",
            ):
                field = await ctx.query_selector(sel)
                if field:
                    val = await field.evaluate("el => el.value") or ""
                    parsed = self._parse_amount(val)
                    if parsed is not None and parsed > 0:
                        await db_log("INFO", f"Payable from field {sel}: {parsed}")
                        return parsed
        except Exception as e:
            await db_log("WARNING", f"read_payable_amount (selector pass) failed: {e}")

        # 3) Walk label→input pairs looking for the Hindi label
        try:
            labels = await ctx.query_selector_all("label, td, th, span")
            for lb in labels:
                text = (await lb.inner_text() or "").strip()
                if "भुगतान योग्य" in text or "किसान को भुगतान" in text:
                    nearby = await ctx.evaluate(
                        """(labelText) => {
                            const labels = document.querySelectorAll('label, td, th, span');
                            for (const l of labels) {
                                if (l.textContent.includes(labelText)) {
                                    let el = l;
                                    for (let i = 0; i < 5 && el; i++) {
                                        const inp = el.querySelector('input, textarea');
                                        if (inp) return inp.value || inp.textContent || '';
                                        el = el.parentElement;
                                    }
                                }
                            }
                            return '';
                        }""",
                        "भुगतान योग्य",
                    )
                    if nearby:
                        parsed = self._parse_amount(nearby)
                        if parsed is not None and parsed > 0:
                            await db_log("INFO", f"Payable from label lookup: {parsed}")
                            return parsed
        except Exception as e:
            await db_log("WARNING", f"read_payable_amount (label pass) failed: {e}")

        await db_log("WARNING", "Payable amount not found — form dumped")
        await self._dump_form("payable_lookup")
        return 0.0

    @staticmethod
    def _parse_amount(text: str) -> float | None:
        if not text:
            return None
        cleaned = text.replace("₹", "").replace(",", "").replace(" ", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    async def select_today_date(self) -> None:
        from datetime import date
        today = date.today().strftime("%d-%m-%Y")
        # Set the cash payment date (नगद भुगतान-दिनाँक) AND the payment-slip
        # date (भुगतान पत्रक दिनाँक). The portal uses dd-MM-yyyy and its
        # jQueryUI datepickers only pick up a value set through the widget.
        date_sel = "#datepicker_CashDate, #datepicker_Bhugtan"
        try:
            filled = await self.ctx.evaluate(
                """(arg) => {
                    const { sel, today } = arg;
                    const out = [];
                    for (const el of document.querySelectorAll(sel)) {
                        try {
                            if (window.jQuery) {
                                try { window.jQuery(el).datepicker('setDate', today); } catch (e) {}
                            }
                            el.removeAttribute('disabled');
                            el.readOnly = false;
                            el.value = today;
                            el.dispatchEvent(new Event('input', {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                            out.push((el.id || el.name) + '=' + el.value);
                        } catch (e) {}
                    }
                    return out;
                }""",
                {"sel": date_sel, "today": today},
            )
            if filled:
                await db_log("INFO", f"Date set on {', '.join(filled)} ({today})")
            else:
                await db_log("WARNING", "No date fields found — cannot proceed")
                await self._dump_form("date_missing")
        except Exception as e:
            await db_log("ERROR", f"Date fallback failed: {e}")
            await self._dump_form("date_missing")
        await self.wait_for_timeout(250)

    async def click_save(self) -> None:
        btn = await self.ctx.query_selector(self.SAVE_BTN_SEL)
        if btn:
            await btn.click()
        else:
            await db_log("ERROR", "Save button not found")
            await self._dump_form("save_missing")
        await self.wait_for_timeout(1200)
        # Some runs show a confirmation dialog (पुनः सत्यापित करें / Yes, Proceed)
        for sel in (self.RECHECK_BTN_SEL, self.PROCEED_YES_SEL):
            try:
                el = await self.ctx.query_selector(sel)
                if el and await el.is_visible():
                    await el.click()
                    await db_log("INFO", f"Clicked confirmation control {sel}")
                    await self.wait_for_timeout(1000)
            except Exception:
                continue
        await db_log("INFO", "Save clicked")
