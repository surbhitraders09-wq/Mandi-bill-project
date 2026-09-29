import asyncio

from app.exceptions import LoginError
from app.services.logging_service import log as db_log
from app.services.pages.base_page import BasePage


class LoginPage(BasePage):
    USERNAME_SEL = "#username"
    PASSWORD_SEL = "#password"
    CAPTCHA_IMG_SEL = "#captchaImage"
    CAPTCHA_INPUT_SEL = "#txtCapcha"
    LOGIN_BTN_SEL = "#btn_login"
    ERROR_LBL_SEL = "#lbl_error"
    POST_LOGIN_SEL = (
        "a:has-text('लॉग आउट'), a:has-text('Logout'), "
        "a:has-text('भुगतान-पत्रक'), span:has-text('भुगतान-पत्रक')"
    )

    def __init__(self, page, frame=None):
        super().__init__(page, frame)
        self._setup_dialog_handler()

    def _setup_dialog_handler(self) -> None:
        self._page.on("dialog", lambda dialog: self._page._loop.create_task(
            self._handle_dialog(dialog)
        ))

    async def _handle_dialog(self, dialog) -> None:
        await db_log("INFO", f"Dismissing dialog: {dialog.message[:100]}")
        await dialog.accept()

    async def dismiss_sweetalert(self) -> None:
        """Dismiss the login-rejection popup if one is showing.

        Fast no-op when nothing is visible (no fixed waits). Tries, in order:
        sweetalert `.confirm` buttons, any button inside the alert, Enter key,
        then a JS click fallback.
        """
        target = self._frame if self._frame else self._page
        try:
            overlay = await target.query_selector(
                ".sweet-overlay, .sweet-alert, .swal2-container"
            )
            if overlay is None or not await overlay.is_visible():
                return
            await db_log("INFO", "Sweetalert overlay detected, dismissing...")

            ok_selectors = (
                ".sweet-alert .confirm, .sa-button-container .confirm, "
                "button.confirm, .sweet-alert button, .confirm.btn, "
                ".sweet-alert .swal-button, .swal2-confirm, "
                ".swal2-container button"
            )
            clicked = False
            for sel in ok_selectors.split(","):
                sel = sel.strip()
                if not sel:
                    continue
                btn = await target.query_selector(sel)
                if btn is not None and await btn.is_visible():
                    await btn.click(force=True)
                    clicked = True
                    break
            if not clicked:
                clicked = await target.evaluate(
                    "() => {"
                    "  const els = Array.from(document.querySelectorAll("
                    "    '.sweet-alert button, .swal2-container button, .confirm, .sa-button-container button'"
                    "  ));"
                    "  const vis = els.filter(e => e.offsetParent !== null);"
                    "  if (vis.length) { vis[0].click(); return true; }"
                    "  return false;"
                    "}"
                )
            if not clicked:
                await target.keyboard.press("Enter")
            await self.wait_for_timeout(600)
            await db_log("INFO", "Sweetalert dismissed")
        except Exception:
            pass

    async def fill_username(self, username: str) -> None:
        await self.ctx.fill(self.USERNAME_SEL, username)
        await self.wait_for_timeout(150)

    async def fill_password(self, password: str) -> None:
        await self.ctx.fill(self.PASSWORD_SEL, password)
        await self.wait_for_timeout(150)

    async def fill_captcha(self, text: str) -> None:
        await self.ctx.fill(self.CAPTCHA_INPUT_SEL, text)
        await self.wait_for_timeout(150)
        await db_log("INFO", f"CAPTCHA filled: {text}")

    async def reload_captcha(self) -> None:
        """Trigger a fresh CAPTCHA image (the handler ignores cache)."""
        target = self._frame if self._frame else self._page
        try:
            await target.evaluate(
                "() => { const img = document.querySelector('#captchaImage'); "
                "if (img) img.src = '/Handler/GCaptcha.ashx?r=' + Date.now(); }"
            )
            await self.wait_for_timeout(800)
        except Exception:
            pass

    async def click_login(self) -> None:
        await self.dismiss_sweetalert()
        await self.ctx.click(self.LOGIN_BTN_SEL)
        await db_log("INFO", "Login button clicked")

    async def wait_after_login(self, timeout_ms: int = 30000) -> tuple[bool, str]:
        """Wait for login to succeed.

        Success signals (whichever comes first):
          - the login frame navigates away from the login page (final success)
          - the 4-digit PIN prompt (`#txt4digitPin`) appears in the login frame
          - the post-login marker appears in the login frame

        Failure signals (whichever comes first):
          - `#lbl_error` gets text (e.g. "invalid CAPTCHA")
          - a sweetalert overlay appears (captcha/login rejection popup)
        Returns (True, "") on success or (False, reason) on failure.
        """
        target = self._frame if self._frame else self._page
        nav_ctx = self._frame if self._frame else self._page

        async def check_nav():
            await nav_ctx.wait_for_url(
                lambda url: "loginTrader" not in url and "LoginForm" not in url,
                timeout=timeout_ms,
            )

        async def check_pin_prompt():
            await target.wait_for_selector(
                "#txt4digitPin, input[name='txt4digitPin']",
                timeout=timeout_ms,
                state="attached",
            )

        async def check_post_login():
            await target.wait_for_selector(self.POST_LOGIN_SEL, timeout=timeout_ms)

        async def check_error():
            await target.wait_for_function(
                f"document.querySelector('{self.ERROR_LBL_SEL}')?.innerText?.trim()?.length > 0",
                timeout=timeout_ms,
            )

        async def check_sweetalert():
            await target.wait_for_selector(
                ".sweet-overlay, .sweet-alert, .swal2-container", timeout=timeout_ms
            )

        nav_task = asyncio.create_task(check_nav())
        pin_task = asyncio.create_task(check_pin_prompt())
        post_task = asyncio.create_task(check_post_login())
        err_task = asyncio.create_task(check_error())
        sweet_task = asyncio.create_task(check_sweetalert())

        done, pending = await asyncio.wait(
            {nav_task, pin_task, post_task, err_task, sweet_task},
            return_when=asyncio.FIRST_COMPLETED,
            timeout=timeout_ms / 1000,
        )

        for t in pending:
            t.cancel()

        if err_task in done:
            try:
                err_task.result()
                err_text = await self.get_error_text()
                return False, err_text
            except Exception:
                pass

        if sweet_task in done:
            try:
                sweet_task.result()
                await self.dismiss_sweetalert()
                return False, "Login rejected (invalid CAPTCHA or credentials)"
            except Exception:
                pass

        if nav_task in done or pin_task in done or post_task in done:
            await self.wait_for_timeout(500)
            return True, ""

        return False, "Login timeout"

    async def get_error_text(self) -> str:
        target = self._frame if self._frame else self._page
        try:
            return await target.evaluate(
                f"document.querySelector('{self.ERROR_LBL_SEL}')?.innerText?.trim() || ''"
            )
        except Exception:
            return ""

    async def handle_pin(self) -> None:
        """Fill the 4-digit login PIN prompt that appears after username/password login.

        The PIN modal lives in the login frame (loginTrader.aspx) with `#txt4digitPin`
        and `#btnPin`. Best-effort: if it does not appear, log and continue.
        """
        target = self._frame if self._frame else self._page
        try:
            pin_input = await target.wait_for_selector(
                "#txt4digitPin, input[name='txt4digitPin'], input[placeholder*='पिन']",
                timeout=8000,
            )
            if not pin_input:
                await db_log("INFO", "No PIN prompt detected")
                return
            await db_log("INFO", "PIN prompt detected")

            from sqlalchemy import select
            from app.core.security import decrypt_value
            from app.database import async_session_factory
            from app.models.settings import Setting
            async with async_session_factory() as session:
                result = await session.execute(
                    select(Setting).where(Setting.key == "e_mandi_pin")
                )
                row = result.scalar_one_or_none()
                if not row:
                    await db_log("WARNING", "e_mandi_pin not configured — skipping PIN")
                    return
                pin_value = decrypt_value(row.value)

            await pin_input.fill(pin_value)
            await db_log("INFO", "PIN filled")

            ok_btn = await target.query_selector(
                "#btnPin, a#btnPin, button:has-text('लॉग इन करें'), button:has-text('Login')"
            )
            if ok_btn:
                await ok_btn.click()
            else:
                await target.keyboard.press("Enter")
            await self.wait_for_timeout(1500)
            await db_log("INFO", "PIN submitted")
        except Exception as exc:
            await db_log("INFO", f"No PIN prompt detected ({exc})")
