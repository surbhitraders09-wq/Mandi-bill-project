# Design: पिछले 10 दिन का औसत भाव — 2 पाई-चार्ट (सोयाबीन + चना)

## Objective

Mobile सारांश पेज पर "पिछले मंडी फीस लेन-देन (10)" section को हटाकर उसकी जगह
पिछले 10 दिनों का **औसत भाव (₹/क्विं.)** दिखाने वाले **2 पाई-चार्ट** दिखाएँ —
सोयाबीन का एक, चना का एक (प्रति फसल एक pie; हर slice एक दिन का भाव) — ताकि
उपयोगकर्ता को पता चले कि भाव किस दिन कितना था और कितना फ़र्क आया।

स्कोप (उपयोगकर्ता की मंज़ूरी): सिर्फ लेन-देन की सूची हटाएँ। बाकी सब
(फसल समरी, स्टॉक, मंडी फीस टेबल, खाता शेष) ज्यों का त्यों रहेगा।

## Data Source: daily-fasal page (AnubandhDateWisePage), per-day

उपयोगकर्ता की दिशा: जिस daily-fasal page से आज की फसल देखी जाती है
(`Ins_eMandiAnubandh_BP_DTWise.aspx` → `AnubandhDateWisePage`) उसी में
**date बदल-बदल कर** पिछले 10 दिन का डेटा लो:

1. पिछले 10 दिन के हर दिन के लिए `AnubandhDateWisePage.set_date_range(day, day)`
   करके `search_and_collect()` चलाएँ → 10 **प्रति-दिन** नतीजे (page per-day देता है,
   कोई cumulative diff नहीं)।
2. हर दिन के rows को `AnubandhDateWisePage.parse_rows()` से bills बनाएँ।
3. `group_crops(bills)` से प्रति-दिन per-crop `total_weight` / `total_amount` /
   `avg_rate` निकालें।
4. `build_price_trend()` हर दिन की per-crop `avg_rate` को सीधे point बनाता है
   (किसी दिन किसी फसल का डेटा नहीं → वह day/fसल छूट जाता है)।

## Backend Changes

### `backend/app/schemas/automation.py`

```python
class PriceTrendPoint(BaseModel):
    date: str                                  # "22-07-2026"
    rates: Dict[str, float] = {}               # {"सोयाबीन": 7104.57, ...}

class CropTrend(BaseModel):
    commodity: str
    start_rate: float      # पहले उपलब्ध दिन का भाव
    end_rate: float        # आखिरी उपलब्ध दिन का भाव
    change_pct: float      # (end-start)/start * 100
    direction: str         # "up" | "down" | "flat"
```

`SummaryResponse` से `mandi_transactions: List[SummaryMandiTransaction]` हटाएँ;
`SummaryMandiTransaction` मॉडल हटाएँ; नए फ़ील्ड जोड़ें:

```python
    price_trend: List[PriceTrendPoint] = []
    price_trend_summary: List[CropTrend] = []
```

### `backend/app/services/automation_service.py` — `search_summary()`

Step 3 (TraderTransactionRpt: balance + transactions) में **transactions वाला हिस्सा
हटाएँ**, balance वाला रखें:

```python
# 3) Trader mandi-fee account: available balance only.
trader_txn = TraderTransactionPage(self._page, self._frame)
await trader_txn.navigate()
mandi_balance = await trader_txn.scrape_available_balance()
```

नया step: पिछले 10 दिन का per-day भाव (daily-fasal page को date बदल-बदल कर loop):

```python
# 4) पिछले 10 दिन के दैनिक भाव — daily-fasal page, har din date set karke.
trend_days = [today - timedelta(days=i) for i in range(9, -1, -1)]  # oldest → today
daily_runs = []
for day in trend_days:
    await anubandh_page.navigate()
    await anubandh_page.select_all_crops_mode()
    await anubandh_page.set_date_range(day, day)
    rows = await anubandh_page.search_and_collect()
    bills = AnubandhDateWisePage.parse_rows(rows)
    daily_runs.append({"date": day, "crops": group_crops(bills)})
price_trend = build_price_trend(daily_runs)      # pure helper
price_trend_summary = build_crop_trends(price_trend)  # pure helper
```

`result` में `mandi_transactions` की जगह `price_trend` और `price_trend_summary`
डालें। Log message में transactions के बजाय `price_trend` बिंदुओं की गिनती
दिखाएँ।

### `backend/app/services/summary_aggregator.py` — pure helpers

नए pure functions (testable, कोई I/O नहीं):

```python
def group_crops(bills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per-crop totals (weight/amount/avg_rate) from parsed anubandh bills."""

def build_price_trend(daily_runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per-day avg rate per crop. Each run is already daily (no cumulative diff)."""

def build_crop_trends(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """For each crop present: start_rate, end_rate, change_pct, direction.

    direction: "up" if change_pct > +0.5, "down" if < -0.5, else "flat".
    अलग-अलग फसल के नामों को सामान्य बनाएँ (जैसे "सोयाबीन/Yellow" → base crop)
    ताकि सोयाबीन की data एक pie में मिले। (ग्रुप prefix " - " से साफ़ करें।)
    """
```

## Frontend Changes

### `frontend/src/lib/mobile.ts`

- `SummaryMandiTransaction` interface हटाएँ।
- `SummaryResponse` से `mandi_transactions` हटाएँ।
- नए interfaces जोड़ें:

```ts
export interface PriceTrendPoint {
  date: string
  rates: Record<string, number>
}
export interface CropTrend {
  commodity: string
  start_rate: number
  end_rate: number
  change_pct: number
  direction: 'up' | 'down' | 'flat'
}
```

### `frontend/src/pages/mobile/mobile-summary.tsx`

- `hasTransactions` / लेन-देन `Section` हटाएँ।
- नया `PriceTrendCharts` component (recharts, पहले से dependency में है):
  - हर crop के लिए एक `CropPricePie` → `<PieChart>` (प्रति crop एक pie)।
  - प्रत्येक pie में slices = 10 दिन (जिन दिनों में उस crop का डेटा है);
    `dataKey="value"` = उस दिन का `rates[crop]`, `nameKey="date"`।
  - हर crop का अपना base रंग (`CROP_COLORS`), slices उसी रंग की shade।
  - Tooltip: `₹ X/क्विं.`; Label: date (संक्षिप्त)।
  - Pie के ऊपर crop नाम + `TrendBadge`: `सोयाबीन ↑ 3.2%` (हरा) / `↓ 1.8%` (लाल) /
    `स्थिर` (ग्रे)।
  - `ResponsiveContainer` + मोबाइल के हिसाब से छोटी height (~200px)।
  - जिस crop का कोई डेटा नहीं मिला → "इन 10 दिनों में इस फसल का कोई डेटा नहीं मिला।"
- `SEARCH_STEPS` में लेन-देन/भाव चार्ट step शामिल करें
  (जैसे "पिछले 10 दिन के भाव पढ़े जा रहे हैं…")।

## Tests (`backend/tests/test_summary.py`)

- `build_price_trend`:
  - 2 दिन के daily runs से सही per-day भाव (direct avg_rate, कोई diff नहीं)।
  - 3 दिन, एक दिन में कोई फसल नहीं → gap (वह बिंदु छूट जाए)।
  - खाली runs → []।
- `build_crop_trends`:
  - बढ़ा (up), घटा (down), स्थिर (flat) — threshold ±0.5%।
  - "सोयाबीन/Yellow" और "सोयाबीन" जैसे नाम एक फसल में मिलें।
  - खाली points → []।

## Out of Scope

- दूसरे मंडी-फीस sections (होम डैशबोर्ड टेबल, खाता शेष) — यथावत रहेंगे।
- पाई-चार्ट slices का weight/value share — पहले (clarification में) उपयोगकर्ता
  ने कहा: "2 pie chart bana lena soyabean ka ek and chana ka ek" (प्रति crop
  एक pie, day-wise भाव slices)। यदि भाव की जगह share चाहिए तो स्लाइस value बदलनी होगी।
- Mobile पर balance/मंडी-फीस टेबल के बदलाव — बाकी सब untouched।
