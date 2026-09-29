from app.config import settings
from app.services.logging_service import log as db_log
from app.services.pages.base_page import BasePage


class PopupHandler(BasePage):
    OK_BTN_SEL = "button:has-text('OK'), a:has-text('OK'), span:has-text('OK'), .confirm, .ok"
    DONE_BTN_SEL = "button:has-text('Done'), a:has-text('Done'), span:has-text('Done')"
    PRINT_LINK_SEL = "a:has-text('Print'), button:has-text('Print'), input[value='Print']"

    async def handle_ok_popup(self, timeout_ms: int = 3000) -> bool:
        try:
            btn = await self._page.wait_for_selector(self.OK_BTN_SEL, timeout=timeout_ms)
            if btn:
                await btn.click()
                await self.wait_for_timeout(500)
                await db_log("INFO", "OK popup confirmed")
                return True
        except Exception:
            await db_log("INFO", "OK popup not found")
        return False

    async def handle_done_popup(self, timeout_ms: int = 800) -> bool:
        try:
            btn = await self._page.wait_for_selector(self.DONE_BTN_SEL, timeout=timeout_ms)
            if btn:
                await btn.click()
                await self.wait_for_timeout(500)
                await db_log("INFO", "Done popup confirmed")
                return True
        except Exception:
            await db_log("INFO", "Done popup not found")
        return False

    async def wait_for_new_tab(self, timeout_ms: int = 15000):
        new_page = await self._page.context.wait_for_event("page", timeout=timeout_ms)
        await new_page.wait_for_load_state("networkidle")
        await db_log("INFO", "New print tab opened")
        return new_page

    async def apply_print_scale(self, page) -> None:
        """Fit the whole bill on ONE page at a fixed scale (default 90%).

        The user verified 100% spills to two pages and prefers Scale 90%
        (Chromium print dialog "More settings → Scale → Custom 90"). We apply
        that scale as an inline zoom on <html>, which Chromium's print layout
        honors, plus an A4 @page rule so the print output is exactly one page."""
        try:
            scale = getattr(settings, "PRINT_SCALE", 0.90) or 0.90
            await page.add_style_tag(
                content=(
                    "@media print { html { zoom: %s !important; } "
                    "@page { size: A4 portrait; margin: 5mm; } }"
                    % scale
                )
            )
            # Inline zoom on <html> is applied even outside @media print, which
            # makes Chromium's print layout use it reliably.
            await page.evaluate(
                "(z) => { document.documentElement.style.zoom = z; }",
                scale,
            )
            await db_log("INFO", f"Print scale set to {scale:.0%}")
        except Exception as exc:
            await db_log("WARNING", f"Could not inject print scale (non-fatal): {exc}")

    async def click_print_on_page(self, page) -> None:
        await page.wait_for_timeout(10000)
        await self.apply_print_scale(page)
        btn = await page.query_selector(self.PRINT_LINK_SEL)
        if btn:
            await btn.click()
        else:
            await page.evaluate("window.print()")
        await db_log("INFO", "Print triggered")
