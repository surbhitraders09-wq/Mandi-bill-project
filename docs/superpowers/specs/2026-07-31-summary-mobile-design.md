# Summary — Mobile Crop-Wise Payment-Patrak Dashboard (Design)

**Date:** 2026-07-31
**Status:** Approved (rev.2 — rewired to the real report pages the user opens)
**Phase:** Post-2 (automation agent modernization)

## Goal

Add a **`सारांश` (Summary)** tab to the mobile web app that shows, for a
selectable date range, the data from the portal pages the trader actually opens:

1. **फसल अनुसार भुगतान-पत्रक समरी रिपोर्ट** (`RPT_BhugtanPatrak_CropwiseTD.aspx`)
   — फसल, कुल वजन (क्विंटल), कुल मूल्य (रुपये), औसत दर (= राशि ÷ वजन).
2. **होम पेज डैशबोर्ड** (`WelcomeTrader.aspx` + `#btn_dashboard` click) —
   फसल स्टॉक (`#examplePD`) + कुल भुगतान-पत्रक / कुल मात्रा / देय मंडी फीस /
   देय निराश्रित शुल्क (`#exampleMFNP`).
3. **मंडी खाता** (`TraderTransactionRpt.aspx`) — उपलब्ध शेष (`#lbl_AvaBal`) +
   पिछले 10 मंडी-फीस लेन-देन (`MND_insSelData.asmx/GetBookDetails`).

> **Why the rewrite.** The first design pulled crop data from the DTWise auction
> page (`Ins_eMandiAnubandh_BP_DTWise.aspx`) and a "date-wise daily" grouping.
> The user's portal shows the crop-wise totals on the dedicated report page, not
> via DTWise — so the summary is now sourced from the pages the user navigates.
> The lifetime-total Dashboard fee section stays removed; the date-scoped mandi
> fee data now comes from the home dashboard MFNP table.

The portal stays **100% read-only** — no writes, no bill creation.

## Verified portal facts (from real crawl, 2026-07-31)

- **Crop-wise report** `Anugya_e/EA-Trader/RPT_BhugtanPatrak_CropwiseTD.aspx`:
  only `#From_Date` (readonly jQuery datepicker, `dd-mm-yy`, label
  "दिनाँक (कब से)") + `#btnSearchData`. JS (`../myScript/TDR_BhugtanRPT_Crop.js`)
  clicks → `bindAllData($('#lbl_OptID').text(), 1)` → POSTs to
  `WS_Bhugtan.asmx/tdr_BP_One` with `{divId, distId, mandiId, OpeId, Datefrom,
  flag}`. Renders `#example` DataTable with columns
  `स.क्र. | फसल | कुल वास्तविक वजन(क्विंटल में) | कुल मूल्य(रूपये में)`.
  Live data (31-07-2026): `सोयाबीन/Yellow 97.02 / 689285.50`,
  `चना/चना 31.52 / 190920.80`. Service payload is the ASMX `{"d": ...}`
  (array or double-encoded JSON string). Crop names have no `"ग्रुप - "` prefix.
- **Home dashboard** `Anugya_e/EA-Trader/WelcomeTrader.aspx`: after clicking
  `#btn_dashboard` ('डैशबोर्ड देखें') the tables populate: `#examplePD`
  (फसल स्टॉक, crop rendered `"ग्रुप - फसल"` e.g. `सोयाबीन - सोयाबीन`) and
  `#exampleMFNP` (single row `62 | 320.27 | 29606.81 | 3947.57` =
  कुल भुगतान-पत्रक | कुल मात्रा | देय मंडी फीस | देय निराश्रित शुल्क).
  Before the click the tables are header-only. `TraderCommodityBal.aspx`
  renders `#examplePD` auto-populated (kept as a fallback).
- **Mandi account** `Anugya_e/EA-Trader/TraderTransactionRpt.aspx`: Available
  Balance in `#lbl_AvaBal` (live: `27548.99`). Button `#btn_lastTrans`
  ("Click here for last 10 transactions") → `GetDetails()` → POSTs to
  `MND_insSelData.asmx/GetBookDetails`; the response `d` is an **XML string**
  (`NewDataSet/BooksData` with `TRANS_DATE, FeeTransactionID, ETransactionID,
  Variety_Name, MandiFee_Dr, MandiFee_Cr, FLAG='भुगतान-पत्र'`). Live rows are
  सोयाबीन transactions with MandiFee_Dr 271.87 … 3362.79 (30-Jul-2026).

## Approach

**Single combined scrape** (one login, one browser session):

1. Login (existing `_login()` flow + CAPTCHA OCR/manual fallback).
2. `_detect_post_login_frame()` (existing).
3. Navigate to **RPT_BhugtanPatrak_CropwiseTD.aspx**, set `#From_Date` from the
   requested `from_date`, click `#btnSearchData`, capture the `tdr_BP_One`
   response → crop rows.
4. Navigate to **WelcomeTrader.aspx**, click `#btn_dashboard`, parse
   `#examplePD` (stock) + `#exampleMFNP` (mandi fee summary).
5. Navigate to **TraderTransactionRpt.aspx**, read `#lbl_AvaBal`, click
   `#btn_lastTrans`, capture `GetBookDetails` XML → transaction rows.
6. `close_browser()`, return one JSON summary.

## Response shape

```json
{
  "state": "bills_loaded",
  "date_range": { "from": "01-07-2026", "to": "31-07-2026" },
  "tax_paid_stock": [ { "commodity": "सोयाबीन", "total_weight": 207.02 } ],
  "crops": [ { "commodity": "सोयाबीन/Yellow", "total_weight": 97.02, "total_amount": 689285.5, "avg_rate": 7104.57 } ],
  "soyabean": { "total_weight": 97.02, "total_amount": 689285.5, "avg_rate": 7104.57 },
  "mandi_fee_summary": { "total_bills": 62, "total_quantity": 320.27, "mandi_fee": 29606.81, "nirashrit_fee": 3947.57 },
  "mandi_balance": 27548.99,
  "mandi_transactions": [ { "date": "30-Jul-2026", "crop": "सोयाबीन  -  सोयाबीन", "mandi_fee_dr": 271.87, "mandi_fee_cr": 0.0, "flag": "भुगतान-पत्र" } ],
  "found_bills": 62
}
```

- `avg_rate` = `total_amount / total_weight` when `total_weight > 0`, else `0`.
- `found_bills` = `mandi_fee_summary.total_bills` (the home dashboard's कुल
  भुगतान-पत्रक); falls back to the crop row count.
- Missing/absent tables → log warning, return empty values; never fail the
  whole summary for one absent number.

## Backend changes

- **New** `app/services/pages/cropwise_summary_page.py` — `CropWiseSummaryPage`:
  - `navigate()` to RPT_BhugtanPatrak_CropwiseTD.aspx.
  - `set_from_date(date)` → write `#From_Date` (readonly, `dd-mm-yy`).
  - `search_and_collect()` → click `#btnSearchData`, capture `tdr_BP_One`
    response (poll), decode ASMX `d`.
  - `decode_response_payload(body)` / `parse_rows(rows)` → crop rows
    (`commodity, total_weight, total_amount, avg_rate`).
- **New** `app/services/pages/trader_transaction_page.py` — `TraderTransactionPage`:
  - `scrape_available_balance()` → poll `#lbl_AvaBal` → float.
  - `click_last_transactions()` → click `#btn_lastTrans`, capture
    `GetBookDetails` response.
  - `_extract_xml(text)` (unwraps ASMX JSON `{"d": ...}`) /
    `parse_transactions_xml(xml)` (namespace-safe BooksData → rows).
- **Modify** `app/services/pages/summary_scraper.py`:
  - `navigate_home_dashboard()` → WelcomeTrader.aspx + `#btn_dashboard` click.
  - `scrape_mfnp_summary()` → `#exampleMFNP` single row.
  - Fix invalid JS in `scrape_tax_paid_stock()` (`if not crop or` → valid JS)
    that silently emptied the stock table on every run.
- **Modify** `app/services/automation_service.py`:
  - `search_summary(from_date, to_date)` now runs the three scrapes above in one
    session (previously DTWise + stock only).
- **Modify** `app/api/routes/automation.py`:
  - `POST /api/automation/summary` body `{from_date, to_date}` → `SummaryResponse`
    (unchanged endpoint, new payload).
- **Aggregation helpers** (testable, no I/O): `soyabean_row(crops)` (crop names
  like `सोयाबीन/Yellow` match via the Hindi keyword); `group_crops`/`group_daily`
  kept for other flows.

## Frontend changes

- **Modify** `src/lib/mobile.ts` — `SummaryResponse` gains
  `mandi_fee_summary`, `mandi_balance`, `mandi_transactions`; drops
  `daily_stock`.
- **Modify** `src/pages/mobile/mobile-summary.tsx` — sections:
  फसल अनुसार भुगतान-पत्रक समरी रिपोर्ट (सोयाबीन highlighted), फसल स्टॉक,
  मंडी फीस / निराश्रित शुल्क (होम डैशबोर्ड), मंडी खाता उपलब्ध शेष,
  पिछले मंडी फीस लेन-देन (10).

## CAPTCHA dialog behavior (user requirement)

Unchanged from rev.1 — the dialog closes **only on success** (poll sees the
state leave `awaiting_captcha`).

## Error handling

- Same as today's-bills: OCR → manual CAPTCHA fallback (mobile dialog, 120s),
  client-disconnect → `ERROR` reset, exceptions → 500 → error message on page.
- Any single missing table → log warning, return empty values; do not fail the
  whole summary.

## Testing

- **Backend unit tests** (`tests/test_summary.py`):
  - ASMX `d` decoding for the crop-wise service (array + double-encoded string).
  - `CropWiseSummaryPage.parse_rows` (real shape `सोयाबीन/Yellow 97.02`).
  - `#exampleMFNP` money/float parsing.
  - `TraderTransactionPage.parse_transactions_xml` (plain + namespaced XML,
    empty/invalid, `_extract_xml` unwrap).
  - `group_crops` / `group_daily` / `soyabean_row`.
- `pytest -q` (all suites green).
- `npm run build` (frontend compiles).
- Live run from phone over LAN: date range → summary sections render with real
  portal data (verified: 2 crops, 10 transactions, balance 27548.99, MFNP
  62/320.27/29606.81/3947.57).
