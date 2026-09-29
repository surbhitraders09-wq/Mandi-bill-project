# Plan — Today's Bills Mobile Search & Print

**Date:** 2026-07-31
**Spec:** `docs/superpowers/specs/2026-07-31-todays-bills-mobile-design.md`

## Goal

Implement the approved design: OCR-CAPTCHA auto-login, date-wise anubandh fetch,
mobile bill cards + detail with editable हम्माली/तौल calculator, ₹2L gate, and
local print — all integrated into the existing FastAPI + React app, served on
`0.0.0.0:8000` so a phone on the same WiFi can use `http://<laptop-ip>:8000/mobile`.

## Steps

### 1. OCR CAPTCHA solver — `backend/app/services/captcha_solver.py`
- Use `rapidocr_onnxruntime` + Pillow (system Python has them; add to venv).
- `solve_captcha_candidates(img_path) -> List[str]`:
  - Greyscale, scale 4×/6×, autocontrast, threshold sweep (90…190), OCR each,
    normalize to `[A-Za-z0-9]`, keep 6-char candidates, dedupe.
- `async solve_captcha(page, frame) -> str`:
  - Screenshot `#captchaImage`, run candidates; on success return text.
  - On failure raise/return None so caller falls back to manual captcha.

### 2. AnubandhDateWisePage — `backend/app/services/pages/anubandh_datewise_page.py`
- `__init__(page, frame)`, `ctx` from BasePage.
- `navigate()` → goto DTWise URL.
- `select_all_crops_mode()` → click `#rb_ALL_Crop` (ensures Date/Search divs show).
- `set_date_range(from_d, to_d)` → fill `#From_Date`, `#To_Date` (format `dd-mm-yy`).
- `search_and_collect() -> List[dict]`:
  - Attach `page.on("response")`, watch for URL ending
    `EM_AnubandhDetail_AllCrops`, read JSON body → `d` array.
  - Click `#btn_search`, wait for response (or short poll), parse rows.
- `parse_rows(data) -> List[dict]` → normalize field names (snake_case keys).

### 3. Automation service — `backend/app/services/automation_service.py`
- Add `async search_todays_bills()`:
  - Guard state, `_launch_browser()`, goto `e_mandi_url`.
  - `_detect_login_frame()`, `_login()` (with OCR: try `solve_captcha`, else manual
    event fallback inside `_login`), `handle_pin()`.
  - `_detect_post_login_frame()`.
  - Init AnubandhDateWisePage; navigate, select all-crops, set today's date,
    `search_and_collect()`.
  - `self._found_bills = rows`, transition `BILLS_LOADED`, close browser.
- Keep existing methods intact; add captcha-OCR attempt before manual wait in `_login`.

### 4. API — `backend/app/api/routes/automation.py`
- `POST /api/automation/todays-bills` → `BillSearchResponse`-like
  `TodayBillsResponse{state, date, bills[]}`.
- Add schema in `schemas/automation.py`.

### 5. Print — `backend/app/services/print_service.py`
- New `build_bill_html(bill_data)` portal-style (Hindi), including कुल हम्माली and
  कुल तौल; keep CUPS/`lp` Linux path; add `toul_rate` handling.

### 6. Mobile frontend
- `src/pages/mobile/index.tsx` — landing + "खोजें" button (calls POST todays-bills).
- `src/pages/mobile/bills.tsx` — card list.
- `src/pages/mobile/bill-detail.tsx` — calculator + validation + print button
  (POST `/api/automation/print`).
- Route `/mobile/*` outside the desktop `AppShell` (plain full-screen mobile layout).
- Add API helper `src/lib/mobile-api.ts` or reuse `api()`.

### 7. Serving + verify
- `main.py`: mount `frontend/dist` as StaticFiles (SPA fallback to index.html).
- `vite.config.ts`: keep dev proxy `/api` → `:8000`; build with `npm run build`.
- Run backend tests (`pytest`), build frontend (`npm run build`), start uvicorn on
  `0.0.0.0:8000`, print LAN URL.

## Verification
- Backend: `pytest -q` (24 existing tests must pass).
- Frontend: `npm run build` clean, `npx tsc -b`.
- Live: open `http://<laptop-ip>:8000/mobile` from phone.

## Risks / Notes
- OCR may fail repeatedly → manual fallback already exists; keep retries low (3).
- Portal session is single-use; close browser after each search.
- CUPS `lp` must exist on the laptop; degrade to save-HTML if unavailable.
