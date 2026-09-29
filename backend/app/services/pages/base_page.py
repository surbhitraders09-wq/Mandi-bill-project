from typing import Optional

from playwright.async_api import Frame, Page

# ---------------------------------------------------------------------------
# Global speed knob for the bill-printing workflow (login → CAPTCHA → select
# bill → save → print). The portal recomputes payable only on keydown/keyup
# and needs the print window to render, but most fixed waits are far longer
# than the portal actually needs. Multiply every portal wait by this single
# factor (shared by base_page.wait_for_timeout and automation_service's direct
# print-chain waits) so one change trims the whole flow consistently.
PORTAL_WAIT_SCALE = 0.25  # 0.25x → ~4x faster; set 0 to floor at MIN_WAIT_MS
MIN_WAIT_MS = 60          # safety floor — never wait less than this


def scaled_portal_wait(ms: int) -> int:
    """Apply the global speed knob to a fixed portal wait (shared by BasePage
    and automation_service's direct print-chain waits so ONE constant trims the
    whole login → CAPTCHA → select bill → save → print flow)."""
    return max(MIN_WAIT_MS, int(ms * PORTAL_WAIT_SCALE))


class BasePage:
    def __init__(self, page: Page, frame: Optional[Frame] = None) -> None:
        self._page = page
        self._frame = frame

    @property
    def ctx(self) -> Page | Frame:
        return self._frame or self._page

    async def goto(self, url: str, **kwargs) -> None:
        await self._page.goto(url, **kwargs)

    async def wait_for_timeout(self, ms: int) -> None:
        # Apply the global speed knob so every fixed portal wait in the page
        # objects (login → CAPTCHA → select bill → save → print) shrinks by the
        # same factor, but never below the safety floor (some timings — e.g. the
        # portal recomputing payable after hammali typing — need a floor).
        await self._page.wait_for_timeout(max(MIN_WAIT_MS, int(ms * PORTAL_WAIT_SCALE)))

    async def wait_for_load(self, state: str = "networkidle", timeout: int = 30000) -> None:
        await self._page.wait_for_load_state(state, timeout=timeout)

    async def screenshot(self, path: str) -> None:
        await self._page.screenshot(path=path)
