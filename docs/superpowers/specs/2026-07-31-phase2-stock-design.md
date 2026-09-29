# Phase 2 — Stock Module Design

- **Date:** 2026-07-31
- **Project:** mandi-automation-assistant
- **Status:** Approved design (user: computed stock, explicit segment flag, seed demo bills)
- **Supersedes:** placeholder `/stock` and `/traders/stock` routes

---

## 1. Goal

Give every operator a live stock dashboard derived from the bills ledger: per-commodity quantities and valuations split by government vs trader segment, with trend charts and CSV export — in ≤ 3 clicks, consistent with the Phase 0 design system.

**Exit criteria:**
1. Stock dashboard reflects the bill ledger (no drift — stock *is* an aggregate of bills).
2. Filters work: commodity, segment (All/Trader/Govt), date range.
3. Charts render (Recharts): daily purchase trend, commodity distribution, segment split.
4. CSV export works.
5. `stock:read` RBAC enforced; reads audit-logged; legacy endpoints untouched.

---

## 2. Data Model — Additive Changes Only

`Bill` gains three nullable columns (nothing existing changes; automation engine writes identically):

| Column | Type | Purpose |
|---|---|---|
| `segment` | String(20), default `"trader"` | `"trader"` \| `"government"` — explicit per-bill flag |
| `commodity_id` | Integer, nullable FK → `commodities.id` | wire bill into master data |
| `farmer_id` | Integer, nullable FK → `farmers.id` | wire bill into farmer master (used by detail pages; nullable because portal bills may not resolve a farmer yet) |

**Migration:** `init_db` uses `create_all` (no ALTER on existing tables). Phase 2 adds a lightweight migration in `init_db`: for each new column, check `PRAGMA table_info(bills)` and run `ALTER TABLE bills ADD COLUMN` when missing. Safe on SQLite dev; the same columns are declared on the model so Postgres/Alembic gets them at full-migration time.

---

## 3. Backend — Stock Domain (`app/domain/stock/`)

New read-only domain module following the Phase 1 pattern (`schemas.py`, `service.py`, `router.py`). All routes guarded by `stock:read` (already present for operator/accountant/inspector).

### Endpoints (`/api/v1/stock`)

| Method & path | Purpose | Response |
|---|---|---|
| `GET /api/v1/stock` | Per-commodity stock summary | `{ items: [{commodity_id, commodity, segment, qty, avg_rate, value, bill_count, last_date}], total, limit, offset }` |
| `GET /api/v1/stock/analytics` | Dashboard chart data | `{ daily: [{date, weight, value}], by_commodity: [{commodity, weight, value}], by_segment: [{segment, weight, value}], totals: {weight, value, avg_rate, bills} }` |
| `GET /api/v1/stock/traders/{trader_id}` | Single trader's holdings | `{ items: [...], total, limit, offset }` (bills where `trader_id` matches, grouped by commodity) |

**Query filters (both list endpoints):** `commodity_id`, `segment`, `from` (date ≥), `to` (date ≤), `limit`, `offset`, `q` (commodity name substring).

### Aggregation logic (computed from bills — no lot table)

- `qty` = `SUM(weight)` over matching bills.
- `avg_rate` = weighted average: `SUM(weight * rate) / SUM(weight)` where `rate` is not null; null-rate bills excluded from avg but included in qty/value via gross.
- `value` = `SUM(gross_amount)` (the bill's recorded gross is the valuation basis — matches ledger, no re-pricing).
- `bill_count` = count of bills in the bucket.
- `last_date` = max bill date in the bucket.
- Grouping: `commodity_id` (or commodity name fallback when `commodity_id` null) + `segment`.

### Audit

Every stock read writes one `STOCK_READ` audit entry (actor, params, count) via `record_audit`. Read-only — no new write surface, so no new `stock:write` permission.

---

## 4. Seed — Demo Bills

`seed.py` gains an idempotent `_seed_demo_bills()`: ~12 bills across the 6 seeded commodities, mixed segments (~8 trader, ~4 government), dates spread across the last 30 days, each with `commodity_id`, `farmer_id` (from the 3 seeded farmers), realistic weight/rate/gross/hammali values. Idempotency guard: skip if `bills` table already has rows with these `bill_number` values. Verifies the stock API returns non-empty after seeding.

---

## 5. Frontend

### New page: `src/pages/stock.tsx` (replaces `/stock` placeholder)

Layout (consistent with Phase 1 pages, dashboard grid):
- **Header row:** title + description; filters: commodity `Select`, segment `Select` (All/Trader/Govt), date range (two `Input type=date`), "Apply" button.
- **KPI row (4 StatCards):** Total weight, Total value (₹), Weighted avg rate, Bills count — from `analytics.totals`, filtered by active filters.
- **Charts row (Recharts, `ResponsiveContainer`):**
  - Daily purchase trend — `AreaChart` (weight or value by date).
  - Commodity distribution — `PieChart`/`Donut` (weight by commodity).
  - Segment split — `BarChart` (weight by segment).
- **SmartTable:** per-commodity rows (commodity, segment badge, qty, avg rate, value, bill count, last date) with existing sort/filter/pagination/CSV export. Row click → `/stock?commodity={id}` is already the search route; leave row click inert for now (no detail page this phase).

### `/traders/stock` route
Same `StockPage` with `segment` defaulted to `"trader"` via an optional prop/route state; header reads "Trader Stock".

### cmd+K integration
Commodity search hits already route to `/stock?commodity={id}` — now they land on the real page. The page reads `commodity_id` from the URL query on mount and pre-selects that commodity filter.

### New chart component
`src/components/data/stock-charts.tsx` — one component owning the three Recharts charts (keeps `stock.tsx` lean). Skeleton loading while `analytics` fetches.

---

## 6. Preservation

- `/api/bills`, `/api/automation/*`, `/api/settings`, `/api/history`, `/api/logs`, audit, search, Phase 1 master-data modules — untouched.
- Only additive: Bill columns, migration lines in `init_db`, seed bills, new `app/domain/stock/`, one new page + one chart component, route swap in `App.tsx`.

---

## 7. Testing

**Backend (pytest):**
- Stock aggregation: seeded bills → correct qty, weighted avg rate, value, bill_count per commodity/segment.
- Filters: `commodity_id`, `segment`, `from`/`to` narrow results correctly.
- Empty set: filter matching no bills → empty items, zero totals.
- RBAC: operator/accountant/inspector GET 200; no write surface exists (no POST/PUT/DELETE on stock).
- Audit: stock reads create `STOCK_READ` entries.
- Migration: fresh + existing DB both get the new columns (test the `ALTER TABLE` path).

**Frontend:**
- `npm run build` clean; `npm run lint` clean.

**Playwright smoke (extend existing):**
- Login → `/stock` renders KPIs + table + charts.
- Filter by segment → table updates.
- CSV export triggers download.
- `/traders/stock` renders trader view.
- cmd+K commodity hit navigates to `/stock?commodity={id}`.
- Legacy pages (`/bills`, `/audit`, `/settings`, `/automation`) still live; no console errors.

---

## 8. Out of Scope (later phases)

- Sales / lot exits (Phase 3+ adds status transitions on bills).
- Stock detail page per commodity.
- Trader-level stock analytics beyond the grouped endpoint.
- Manual bill entry UI (Phase 3 — Bills & payments).
