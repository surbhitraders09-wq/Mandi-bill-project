# Phase 1 — Master Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. (This repo has no git history; commit steps are omitted unless the user requests git.)

**Goal:** Ship the Phase 1 master-data modules on the Phase 0 foundation: villages, commodities, farmers, traders. Full CRUD + search + RBAC + audit behind `/api/v1/*`, plus farmer/trader list and profile pages in the ERP shell.

**Architecture:** New SQLAlchemy models (`Village`, `Commodity`, `Farmer`, `Trader`) registered in `init_db`. New domain modules under `backend/app/domain/` (schemas/service/router per module) mounted in `main.py`. Every write is RBAC-gated (`farmers:write`, `traders:write`, `masterdata:write`) and audited through `record_audit`. Global search (`/api/v1/search`) extended to farmers/traders/commodities/villages. Seed adds Madhya Pradesh villages, common mandi commodities, and 3 demo farmers + 3 demo traders. Frontend gains live Farmers and Traders pages (SmartTable list + create/edit dialog + profile detail route), replacing the Phase 0 placeholders.

**Preservation mandate (non-negotiable):** Existing automation engine, `/api/automation/*`, `/api/bills`, `/api/settings`, `/api/history`, `/api/logs`, and the Phase 0 auth/audit/search modules are preserved and untouched except where the plan explicitly says modify.

**Tech Stack:** FastAPI + SQLAlchemy async + aiosqlite (dev) · React + Vite + TS + Tailwind 3.4 (locked) · Zustand · TanStack Query + Table · Radix dialog · existing component library.

---

## Current State (verified at plan time)

- Phase 0 complete: backend live on :8000 (auth/audit/search RBAC-gated, 10 tests pass), frontend live on :5173 (ERP shell, cmd+K, SmartTable, live Settings/Audit pages, browser smoke 11/11).
- Existing models: `Bill`, `Log`, `Setting`, `Role`/`RolePermission`/`User`, `ActivityLog`.
- `PERMISSIONS` matrix in `app/core/rbac.py`; `record_audit` in `app/core/audit.py` writes through the logging pipeline.
- Global search currently covers only `Bill`.
- Farmers/Traders frontend routes are placeholders (`PagePlaceholder`).

---

## Task 1: Master-data models

**Files:**
- Create: `backend/app/models/village.py`, `backend/app/models/commodity.py`, `backend/app/models/farmer.py`, `backend/app/models/trader.py`
- Modify: `backend/app/database.py` (import new models in `init_db`)

**Model fields (follow existing `models/*.py` style — `Mapped`/`mapped_column`, `Base`, index on searchable + FK columns, `created_at` defaults):**

`Village`: `id`, `name` (unique, index), `block`, `district`, `created_at`.
`Commodity`: `id`, `name` (unique, index), `code` (unique), `unit` (default "quintal"), `created_at`.
`Farmer`: `id`, `name` (index), `aadhaar` (unique, index), `mobile` (index), `village_id` (FK → villages.id, nullable), `land_area`, `bank_name`, `account_number`, `ifsc_code`, `created_at`.
`Trader`: `id`, `name` (index), `gstin` (unique, nullable), `pan` (nullable), `license_no` (nullable), `mobile`, `commission_rate` (float, default 0), `created_at`.

- [ ] **Step 1:** Write the four model files.
- [ ] **Step 2:** Add them to `database.py` `init_db` import list (with `# noqa: F401`).

---

## Task 2: Domain modules — villages, commodities, farmers, traders

**Files (create per module under `backend/app/domain/<name>/`):**
- `__init__.py`, `schemas.py`, `service.py`, `router.py`
- Modify: `backend/app/main.py` (mount 4 routers)

**Shared router pattern (each module):**
- `GET /api/v1/{resource}` — list, `?q=` search across searchable fields, `?limit=&offset=` pagination, sorted by `created_at` desc. Guard: `<resource>:read`.
- `GET /api/v1/{resource}/{id}` — single by id. Guard: `<resource>:read`.
- `POST /api/v1/{resource}` — create. Guard: `<resource>:write`. Audited.
- `PUT /api/v1/{resource}/{id}` — update. Guard: `<resource>:write`. Audited with old/new values.
- `DELETE /api/v1/{resource}/{id}` — delete. Guard: `<resource>:write`. Audited. (Farmers/traders: soft-delete not required in v1; hard delete acceptable for master data. Prefer 409 if referenced — v1 skip FK integrity error handling beyond catching `IntegrityError` → `AppError` 409.)

**Permissions to add to `rbac.py` PERMISSIONS:**
- `administrator`: already `*`.
- `operator`: add `farmers:read`, `farmers:write`, `traders:read`, `traders:write`, `masterdata:read`, `masterdata:write`.
- `accountant`: add `farmers:read`, `traders:read`, `masterdata:read`.
- `inspector`: add `farmers:read`, `traders:read`, `masterdata:read` (view-only — no write perms).

**Audit:** every create/update/delete calls `record_audit(action="CREATE|UPDATE|DELETE", entity="farmer|trader|village|commodity", entity_id=str(id), old_value, new_value, actor=user["username"], request=request)`. Pass `request: Request` as a route dependency (`request: Request` param) so IP is captured.

**Service layer:** thin — functions take `session` + payload, do the ORM work. Routers do auth (via `require_permission`) + audit + session handling. Use `get_db` dependency for session.

**Schemas:** Pydantic v2 `BaseModel`; create/update models (all fields optional on update) + `*Out` with `model_config = {"from_attributes": True}` + `ListResponse` envelope `{items, total, limit, offset}` (match `BillListResponse` style).

- [ ] **Step 1:** Write schemas for all 4 modules.
- [ ] **Step 2:** Write services.
- [ ] **Step 3:** Write routers (list/search/get/create/update/delete each).
- [ ] **Step 4:** Update `rbac.py` PERMISSIONS + frontend `constants.ts` mirror.
- [ ] **Step 5:** Mount routers in `main.py`.
- [ ] **Step 6:** `python -c "import app.main"` succeeds.

---

## Task 3: Extend global search

**Files:**
- Modify: `backend/app/domain/search/router.py`

Add farmers (name/aadhaar/mobile), traders (name/gstin/pan/license_no), commodities (name/code), villages (name) to the search results. Each hit gets `type`, `id`, `title`, `subtitle`, `route`:
- farmer → `/farmers/{id}`
- trader → `/traders/{id}`
- commodity → `/stock?commodity={id}` (Phase 2 route; still navigate there)
- village → `/farmers?village={id}`

Keep the same `{items: [...]}` envelope. Per-entity limits to avoid drowning the palette (bills + farmers + traders first, others small cap). No permission change (search:read already required).

- [ ] **Step 1:** Update the search router.
- [ ] **Step 2:** `curl /api/v1/search?q=...` after restart returns master-data hits.

---

## Task 4: Seed master data

**Files:**
- Modify: `backend/app/seed.py`

Inside `seed_defaults()` (idempotent — skip if present):
- 5 villages (e.g. Rewa, Satna, Sidhi, Shahdol, Singrauli) with block/district.
- 6 commodities (Soybean, Wheat, Gram, Paddy, Mustard, Lentil) with unit "quintal" + codes.
- 3 demo farmers (names, unique Aadhaar, mobile, village link, bank details).
- 3 demo traders (names, GSTIN, PAN, license, commission_rate).

Reuse `_seed_roles_and_admin` pattern: `select(...).scalar_one_or_none()` before insert.

- [ ] **Step 1:** Add seed data (idempotent).
- [ ] **Step 2:** Restart backend, verify list endpoints return seeded rows.

---

## Task 5: Backend tests

**Files:**
- Create: `backend/tests/test_masterdata.py`

Extend `conftest.py` fixtures? — No: reuse existing session `prepare_db` (runs `seed_defaults()` which now seeds master data too). Add tests:
- list farmers/traders/commodities/villages returns seeded rows (200).
- create farmer (operator token) → 200/201 + audit row appears in logs.
- duplicate aadhaar → 409/422.
- inspector cannot POST farmer (403); inspector CAN GET.
- search `?q=<farmer name>` returns farmer hit.
- trader CRUD round-trip (create → get → update → delete).

Follow `test_auth.py`/`test_rbac.py` style (`@pytest.mark.asyncio`, `client` fixture, helper `_login`).

- [ ] **Step 1:** Write `test_masterdata.py`.
- [ ] **Step 2:** `./venv/bin/pytest -v` all green.

---

## Task 6: Frontend — Farmers pages

**Files:**
- Create: `frontend/src/pages/farmers.tsx` (list), `frontend/src/pages/farmer-detail.tsx` (profile)
- Create: `frontend/src/components/forms/farmer-form.tsx` (create/edit dialog)
- Modify: `frontend/src/App.tsx` (route `/farmers` → real page; add `/farmers/:id`)
- Modify: `frontend/src/constants.ts` (add `farmers:write` to operator, `farmers:read` to accountant/inspector; keep `farmers:read` for list visibility)

**List page:** PageHeader ("Farmer Registration", actions: New Farmer button gated by `Permission permission="farmers:write"`), SmartTable with columns Name, Aadhaar, Mobile, Village, Bank, Created; row click → `/farmers/:id`. Data via TanStack Query `api('/api/v1/farmers')`. Search box (SmartTable filter) + server `?q=` on the button? Use SmartTable client filter + a debounced server search field. Empty → EmptyState. Skeleton on loading.

**Form dialog:** Radix Dialog + FarmerForm; fields name, aadhaar, mobile, village_id (Select from `/api/v1/villages`), land_area, bank_name, account_number, ifsc_code. Validate aadhaar 12 digits client-side. POST/PUT via `api`. Toast on success; invalidate `['farmers']`.

**Detail page:** Back link, profile card (name/aadhaar/mobile/village/bank), tabs stub (Overview | Purchases | Payments | Documents | Timeline) with the Overview populated and others as "Phase 2/3" placeholders per plan §9.3. `useParams` id; `api('/api/v1/farmers/:id')`.

- [ ] **Step 1:** Farmers list + form + detail.
- [ ] **Step 2:** Wire routes.
- [ ] **Step 3:** Build passes.

---

## Task 7: Frontend — Traders pages

**Files:**
- Create: `frontend/src/pages/traders.tsx` (list), `frontend/src/pages/trader-detail.tsx` (profile)
- Create: `frontend/src/components/forms/trader-form.tsx` (create/edit dialog)
- Modify: `frontend/src/App.tsx` (route `/traders` → real page; add `/traders/:id`)
- Modify: `frontend/src/constants.ts` (add `traders:write` to operator, `traders:read` to accountant/inspector)

Mirror Farmers but fields: name, gstin, pan, license_no, mobile, commission_rate. Detail tabs per plan §9.4 (Overview | Commission | Purchases | Stock | Payments | Reports | Documents | Analytics), Overview populated, rest stubs.

- [ ] **Step 1:** Traders list + form + detail.
- [ ] **Step 2:** Wire routes.
- [ ] **Step 3:** Build passes.

---

## Task 8: E2E verification

- [ ] **Step 1:** Backend: `cd backend && ./venv/bin/pytest -v` — all green (existing 10 + new master-data tests).
- [ ] **Step 2:** Frontend: `cd frontend && npm run build` — passes.
- [ ] **Step 3:** Restart backend; smoke with Playwright:
  - login admin/admin123
  - Farmers list shows 3 seeded farmers
  - Create farmer via dialog → row appears
  - Open farmer detail → profile renders
  - Traders list + create trader → appears
  - cmd+K search farmer name → hit navigates to profile
  - Audit page shows CREATE entries for the new records
- [ ] **Step 4:** Verify legacy routes untouched: `/api/automation/state`, `/api/bills`, `/api/settings` still 200.

**Phase 1 done when:** Farmer/trader CRUD + profiles live with RBAC + audit; search covers master data; legacy endpoints untouched; backend tests + frontend build + browser smoke all green.

---

## Self-Review

- **Spec coverage:** §9.3 farmer registration (profile + tabs), §9.4 trader registration, §11 new tables (villages, commodities, farmers, traders), §12 `/api/v1/farmers` + `/api/v1/traders`, §15 RBAC + audit on every mutation — all covered.
- **Placeholder scan:** none (all code blocks concrete). Timeline/analytics tabs are intentionally stubbed to later phases.
- **Type consistency:** list envelope `{items,total,limit,offset}` matches existing; `api<T>` used in frontend; permission strings match between `rbac.py` and `constants.ts`.
- **Preservation:** only `main.py`, `rbac.py`, `seed.py`, `database.py`, `search/router.py`, `App.tsx`, `constants.ts` are modified — all additive.
