# Today's Bills — Mobile Search & Print (Design)

**Date:** 2026-07-31
**Status:** Approved
**Phase:** Post-2 (automation agent modernization)

## Goal

Give the trader a **mobile-first web page** (opened from their phone over the same
WiFi) that:

1. Fetches **today's** eMandi anubandh/auction records from the MP e-Anugya portal.
2. Shows them as tappable cards.
3. Lets the user open a bill detail and compute the farmer's payable using
   editable **हम्माली** and **तौल** per-quintal rates (defaults ₹12.05 / ₹0).
4. Validates the payable against the **₹2,00,000 cash threshold**.
5. Prints the bill on the **laptop's printer** (CUPS/`lp`), with a layout that
   mirrors the portal's own printed भुगतान-पत्रक.

The portal stays **100% read-only** — no bill is ever created on the portal by
this feature.

## Verified portal facts (from real crawl, 2026-07-31)

- Login page: `https://eanugya.mp.gov.in/Anugya_e/EA-LoginForm/loginTrader.aspx`
  - Username: `#username`, Password: `#password`, CAPTCHA: `#txtCapcha` + `#captchaImage`
  - Login button: `#btn_login`
  - PIN screen: `#txt4digitPin`, submit via `[onclick*='SendUserPinData']` / `#btn_pin`
  - Error label: `#lbl_error`
- Target page: `https://eanugya.mp.gov.in/Anugya_e/EA-Trader/Ins_eMandiAnubandh_BP_DTWise.aspx`
  ("eMandi पोर्टल के अनुबंध पत्रक अनुसार भुगतान पत्रक की दिनांक वार प्रविष्ठी")
  - Mode radios: `input[name="rb_checkAS"]` → `#rb_ALL_Crop` ("दिनाँक अनुसार अनुबंध क्रमांक(सभी कृषि उपज अनुसार)")
  - Date inputs: `#From_Date`, `#To_Date` (readonly datepickers, format `dd-mm-yy`)
  - Search button: `#btn_search` → calls `eMandiAnubandhGrid_AllCrops()`
  - Read-only POST: `Anugya_e/WSD/eMandiBPMerge.asmx/EM_AnubandhDetail_AllCrops`
    with body `{"TI":<lbl_Opt_ID text>,"From_Date":"...","To_Date":"..."}` → returns `{ d: [auction row...] }`
  - Trader ID hidden label: `#lbl_Opt_ID` (contains the trader ID from settings)
- Auction row fields (from `data.d`, DataTable columns):
  `AuctionId, AuctionDate, CommGroupCode, CommodityCode, VarietyCode, FarmerName,
  AuctionRate, ActualWeight, MobileNo_Farmer, VillageName, CommGroup_Name,
  Commodity_Name, Variety_Name, GatepassID, Gatepass_Date, Grade, category,
  FarmerId, MandiName, TraderID, Traders_ComName, Tulavati_Id, OperatorID, EmpName`
- Bill form math (portal's `MandiTax()` in `ins_dtwise.js:981`):
  - `कुल मूल्य` = `वजन × दर`
  - `किसान को भुगतान योग्य` = `कुल मूल्य − हम्माली − तौल + विलम्ब_अतिरिक्त`
  - Portal validations: नीलामी दर ≤ 200000, वजन ≤ 500 क्विं.
- Printed bill columns (`bill_print.html`): नीलामी दर, वास्तविक वजन, कुल मूल्य,
  कुल हम्माली, कुल तौल, अतिरिक्त भुगतान, किसान को भुगतान योग्य राशि, भुगतान का
  प्रकार, नगद/ऑनलाइन भुगतान मूल्य, IFSC, बैंक खाता, भुगतान क्रमांक.

## Architecture

Integrated into existing `mandi-automation-assistant` FastAPI + React app.

### Backend

- **`services/captcha_solver.py`** — offline OCR (rapidocr-onnxruntime) with
  multi-scale/threshold voting and a retry loop (fresh CAPTCHA each attempt).
  Exposes `solve_captcha(page) -> str` returning the best 6-char candidate.
  Falls back to the existing manual-captcha flow if OCR exhausts retries.
- **`services/pages/anubandh_datewise_page.py`** — new page object:
  `select_all_crops_mode()`, `set_date_range(from_d, to_d)`, `search_and_collect()`
  (attaches a Playwright response listener for `EM_AnubandhDetail_AllCrops` and
  parses `data.d` JSON), `parse_rows(json)`.
- **`services/automation_service.py`** — new method `search_todays_bills()`:
  fresh login (OCR CAPTCHA + auto PIN) → navigate to DTWise page → select
  `rb_ALL_Crop` → set From=To=today → click search → collect rows → close browser
  (frees the single portal session). Stores rows in `self._found_bills` with
  structured fields.
- **`api/routes/automation.py`** — new endpoint `POST /api/automation/todays-bills`
  returning `{state, date, bills: [{auction_id, farmer_name, village, commodity_group,
  commodity, variety, weight, rate, auction_date, gatepass_id, mandi, trader_id}]}`.
- **`services/print_service.py`** — replace receipt with a portal-style भुगतान-पत्रक
  HTML (Hindi, DevaNagari): header, farmer details, कुल मूल्य, कुल हम्माली, कुल तौल,
  भुगतान योग्य राशि; print via CUPS `lp` on Linux / `win32print` on Windows.

### Frontend (mobile browser)

New mobile-first pages (no sidebar/desktop chrome):

- `/mobile` — landing: big **आज के बिल खोजें** button + date display + status/progress.
- `/mobile/bills` — tappable card list of today's records.
- `/mobile/bills/:auctionId` — detail: farmer, crop/variety, weight, rate, and live
  हम्माली (default ₹12.05) + तौल (default ₹0) per-quintal inputs; computed कुल मूल्य
  and किसान को भुगतान योग्य राशि; ₹2,00,000 gate; **छापें** button.

Served by FastAPI from `frontend/dist` (StaticFiles) so the phone only needs
`http://<laptop-ip>:8000/mobile`. Vite dev proxy remains for local dev.

## Decisions

| Decision | Choice |
|---|---|
| Integration | Into existing `mandi-automation-assistant` (Option A) |
| Session model | Fresh login per search (Option B), browser closed after |
| CAPTCHA | Offline OCR (rapidocr) + retry loop; manual fallback (Option A) |
| Date range | Today only (From = To = today) |
| Deductions | हम्माली + तौल, both subtracted (portal-exact `MandiTax()`) |
| Print | Local generation on laptop → CUPS/`lp` (portal untouched) |
| Threshold | किसान को भुगतान योग्य > ₹2,00,000 → alert + print disabled |
