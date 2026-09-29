# e-Mandi Portal Modernization Plan

- **Date:** 2026-07-31
- **Project:** mandi-automation-assistant
- **Status:** Approved design — foundation for phased implementation
- **Authoring decision:** Plan first, then build phased (strangler evolution)

---

## Locked Foundation Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Deliverable sequence | Plan → phased build | Every phase gated by this plan and its own spec |
| Runtime model | Modern client + portal underlay | Our app is the daily working surface; own Postgres ledger is the operational system of record; the e-Mandi portal remains the official government record and is driven by the automation engine |
| Users & tenancy | Single office, multi-role; tenant-ready schema, single-tenant v1 | Roles: Administrator, Operator, Accountant, Inspector (view-only) |
| Build approach | A — Strangler evolution | Grow the existing FastAPI + React base module-by-module; nothing breaks mid-migration |
| AI assistant | Cloud OpenRouter (OpenAI-compatible), backend-held key, tool-calling | Structured queries and actions against our own APIs |

**Preservation mandate (non-negotiable):** Every existing workflow, business calculation (hammali ₹12.05/quintal, cash threshold ₹200,000), form, report, government requirement, and validation is preserved. UX may only change how work is reached and presented — never what the work does.

---

# Part I — Strategy

## 1. Product Vision

The Madhya Pradesh e-Mandi (EMIS) portal (`eanugya.mp.gov.in`) is a legacy ASP.NET postback system. Traders, mandi operators, accountants, inspectors, and administrators must log in, navigate deep menu trees, re-enter data, solve mixed-case CAPTCHAs, and manually track bills, stock, and payments. Today's operator workflow — search a date's bills, calculate hammali, record cash payment, print a receipt — takes many minutes per bill and provides zero analytics.

**Vision:** A modern, fast, automation-friendly Government ERP that sits on top of the e-Mandi portal and gives every operator the answer to one question: *"What is the fastest possible way to finish today's work?"*

The system provides:
- A unified, real-time operational dashboard (today's purchases, payments, bills, weight, revenue, mandi fee, stock).
- Command-driven navigation (CTRL+K global search) that replaces deep menu digging.
- Smart tables with filters, sorting, export, and bulk actions replacing static lists.
- Complete farmer, trader, and stock profiles with history and analytics.
- Automated bill search, hammali calculation, cash payment entry, and printing driven through the portal underlay.
- Free-tier notifications (Telegram + FCM) instead of paid channels.
- A local-first, fully open-source stack with an AI assistant powered by OpenRouter.
- Role-based access: Administrator, Operator, Accountant, Inspector (view-only audit).

**Success criteria (v1):**
1. Every action an operator performs daily is reachable in ≤ 3 clicks or via a command.
2. Bill search → analyse → pay → print completes with zero manual portal navigation.
3. Full audit trail of who did what, when, from where, before/after values.
4. Operator time per bill reduced ≥ 60% versus the legacy portal flow.
5. Zero lost or duplicated bills — every bill one identity in the ledger.

## 2. UX Audit — Current State (As-Built / Observed)

Audit of the current experience, based on the automation work against the real portal and the rebuilt assistant.

| Area | Current pain | Severity |
|---|---|---|
| Login | CAPTCHA every session; mixed-case (e.g. `Em28Nh`, `3wlcPT`) must be typed exactly; PIN prompt after login | High |
| Post-login redirects | Silent wait; success only detectable via DOM (भुगतान-पत्रक / लॉग आउट / Logout); error only via `#lbl_error` | High |
| Menu depth | भुगतान-पत्रक → मंडी फीस / निर्धारित शुल्क की गणना = deep, Hindi-labelled tree; easy to lose place | High |
| Bill search | Date radio default unclear; results are raw HTML tables, no filtering/sorting | High |
| Bill details | Labels/values inconsistent (`.detail-row`, `.field-group`, `tr`); numbers mixed with ₹/commas/spaces | Medium |
| Payments | Hammali entry, cash radio, amount, date, save are separate unguided steps; popups (OK/Done) interrupt flow | Medium |
| Printing | Print page opens a new tab; must wait then trigger `window.print()` | Medium |
| CAPTCHA flow (assistant) | Manual dialog with OCR pre-fill guess; guesses sometimes wrong; mixed-case must be preserved (never force uppercase) | Medium |
| Feedback | No progress indication during long waits; failures are generic | High |
| Mobile | Portal not usable on phone; assistant dashboard is desktop-first | High |
| Analytics | None — no trends, no stock valuation, no payment status overview | High |

## 3. UI Audit — Current State

| Dimension | Finding |
|---|---|
| Typography | System fonts; no type scale; Hindi/English mixing without hierarchy |
| Color | Legacy greens; no semantic status colors; poor contrast in places |
| Density | Dense legacy table layouts; inconsistent spacing |
| Components | No shared component library; every screen hand-rolled |
| States | No loading skeletons, empty states, or error states; spinner-less waits |
| Consistency | Button/input patterns vary; two different "search" experiences (portal vs assistant) |
| Theming | No dark mode; no high-contrast; no large-font mode |
| Accessibility | Keyboard nav incomplete; no ARIA; contrast and focus issues |

**Redesign targets:** a token-based design system (below) applied consistently, semantic status colors, skeleton loading, empty/error states on every list, dark mode, and full keyboard accessibility.

---

# Part II — Experience

## 4. Information Architecture

Top-level groups and their objects:

```
Dashboard
  Overview          (analytics)
  Today            (quick operational snapshot)
Farmers
  Registration     (farmer master profile)
  Payments         (farmer payment history)
  History          (purchase & activity timeline)
Traders
  Registration     (trader master profile incl. GST/PAN/license/commission)
  Stock            (trader stock holdings)
  Reports          (trader-level reports)
Stock
  Live Stock       (unified commodity stock dashboard)
  Government       (government stock holdings)
  Trader           (trader stock holdings)
Payments
  Create           (new payment entry)
  Verify           (verification queue)
  Pending          (pending payments list)
  Completed        (completed payments history)
Bills
  Create
  Search           (portal-driven search)
  History          (ledger of analysed/printed bills)
Reports
  Daily / Monthly / Commodity / Finance
Documents
  Invoices · Receipts · Farmer · Trader · Bank · Government · Scanned
Notifications
Activity Log
Settings
```

Global layers above every page: **Global search (CTRL+K)**, **Notification bell**, **AI assistant panel**, **Quick actions**.

## 5. Navigation Architecture

```
+--------------------------------------------------------------+
| Top bar: [Menu] [Global Search cmd+K ........] [AI] [🔔] [🌙] [User ▾] |
+----------------------------+---------------------------------+
| Sidebar (collapsible)      |                                 |
|  ▸ Dashboard               |                                 |
|  ▸ Farmers                 |   Page content (lazy-loaded     |
|     · Registration         |   feature route)                |
|     · Payments             |                                 |
|     · History              |                                 |
|  ▸ Traders                 |                                 |
|  ▸ Stock                  |                                 |
|  ▸ Payments                |                                 |
|  ▸ Bills                  |                                 |
|  ▸ Reports                 |                                 |
|  ▸ Documents               |                                 |
|  ▸ Notifications           |                                 |
|  ▸ Activity Log            |                                 |
|  ▸ Settings                |                                 |
+----------------------------+---------------------------------+
| Status bar: sync state · portal link status · save status · version |
+--------------------------------------------------------------+
```

**Rules:**
- Sidebar groups map 1:1 to IA groups. Active state reflects route.
- Sidebar collapses to icon rail; fully hidden on mobile (drawer).
- Every page has a breadcrumb + page actions row (primary action always first).
- Global search, notification bell, AI, and user menu persist across all routes.
- Role-based visibility: Inspector sees view-only groups (no Create/Edit/Delete); Accountant sees payments/bills/reports; Operator sees operational groups.

## 6. Component Library

Hand-rolled, token-driven, Radix-primitive based (accessibility), documented in Storybook-style docs:

| Category | Components |
|---|---|
| Primitive | Button (variant/size/loading), IconButton, Badge, Chip, Tooltip, Avatar, Spinner |
| Input | Input, Textarea, Select (searchable), Autocomplete, Combobox, DatePicker, DateRangePicker, NumberInput, Switch, Checkbox, RadioGroup, SearchField, PasswordField (reveal) |
| Layout | Card, Section, Stack, Grid, Tabs, Stepper, Accordion, SplitPane, PageHeader, Sidebar, TopBar, StatusBar |
| Data | SmartTable (sort/filter/pin/resize/search/pagination/export/bulk), DataGrid detail drawer, StatCard, Timeline, Tree, Kanban (optional) |
| Feedback | Dialog, Drawer, Toast, Alert, Banner, Progress (linear/skeleton), EmptyState, ErrorState, Confirm, CommandPalette, NotificationPopover |
| Overlay | Modal, Popover, Menu, Dropdown, CommandPalette |
| Charts | Line, Area, Bar, Donut, Pie, Heatmap, KPI (via Recharts) |
| Action | QuickActionMenu (per-row View/Edit/Delete/Print/Download/Duplicate/History/Share/QR) |

**Bulk action pattern:** checkboxes + sticky bulk-action bar (Bulk Print, Bulk Download, Bulk Payment, Bulk Export, Bulk Verification, Bulk Delete, Bulk Approval) — always with confirmation and audit logging.

## 7. Design System

**Tokens (CSS custom properties, light + dark):**

| Token group | Examples |
|---|---|
| Color | `--color-bg`, `--color-surface`, `--color-border`, `--color-text`, `--color-muted`; semantic: `--color-success`, `--color-warning`, `--color-danger`, `--color-info`; brand: mandi green primary + saffron accent |
| Status colors | success (paid/verified) · warning (pending) · danger (failed/overdue) · info (in-progress) · neutral (draft) |
| Typography | Scale 12/14/16/20/24/32/48px; Inter for Latin + Noto Sans Devanagari for Hindi; `lang`-aware font stack |
| Spacing | 4px base grid: 4/8/12/16/24/32/48/64 |
| Radii | 4 (sm) / 8 (md) / 12 (lg) / full |
| Shadows | Subtle elevation scale; dark-mode adjusted |
| Motion | 150–250ms ease-out micro-interactions; `prefers-reduced-motion` respected |
| Density | Comfortable (default) + Compact toggle |
| Modes | Light · Dark · High Contrast · Large Font · Reduced Motion |

**Typography rules:** Hindi numerals where appropriate, ₹ formatting everywhere, tabular-nums for tables and stat cards.

## 8. Dashboard Design

Layout (12-col grid, mobile stacks):

```
+-------------------------------------------------------------------+
| KPI ROW: Today's Purchase | Payments | Pending Payments | Bills  |
|          Weight | Revenue | Mandi Fee | Stock (available)         |
+-------------------------------------------------------------------+
| CHARTS:  Daily Purchase Trend | Monthly Trend | Commodity Dist.   |
+-------------------------------------------------------------------+
| CHARTS:  Payment Status | Stock Analytics | Revenue Analytics     |
+-------------------------------------------------------------------+
| Recent Bills  | Recent Payments | Farmer Activity | Trader Activity|
+-------------------------------------------------------------------+
| QUICK ACTIONS PANEL: Search Bill · New Payment · Print · Report   |
|          [sticky, right rail or top]                              |
+-------------------------------------------------------------------+
```

- KPIs are live numbers with trend deltas (▲/▼ vs yesterday/prev period).
- Charts: Daily/Monthly purchase trend (line/area), Commodity distribution (donut), Payment status (stacked bar), Stock & Revenue analytics (line + area).
- Recent panels link into full lists with "View all".
- Quick actions respect role permissions.
- Skeleton loading on first paint; data fetched via TanStack Query with caching.

## 9. Screen-by-Screen Wireframes

**9.1 Login** — Email/user + password + 2FA-ready field; theme toggle; "portal status" indicator. No CAPTCHA (handled in automation engine underlay, not the app UI).

**9.2 Dashboard** — §8 layout.

**9.3 Farmers — Registration (profile):**
```
Header: [Photo] Farmer Name · Aadhaar · Mobile · Village   [Edit][Print][QR]
Tabs:    Overview | Purchases | Payments | Land | Bank | Documents | Timeline | Analytics
```
Overview: contact, village, land details, pending payments, bank (IFSC). Timeline: activity feed (purchase/payment events). Analytics: volume/value by month.

**9.4 Traders — Registration (profile):**
```
Header: Trader Name · GST · PAN · License · Contact   [Edit][Print][QR]
Tabs:    Overview | Commission | Purchases | Stock | Payments | Reports | Documents | Analytics
```

**9.5 Stock — Live Stock:**
```
Filters: Commodity | Date range | Segment (Govt/Trader) | Saved filters
Table:   Commodity | Purchased | Sold | Pending | Available | Reserved |
         Govt Stock | Trader Stock | Avg Price | Current Value | Trend
Bulk:    Export · Print
```
Trend graphs per commodity.

**9.6 Payments — Create:**
Stepper: Select bill → Amount + method (cash/bank) → Verify details → Confirm (auto-saves receipt, triggers verification + automation entry).

**9.7 Payments — Verify:** Queue with approve/reject, history, bulk verification, receipt reprint with QR.

**9.8 Bills — Search:** Date range + filters → results table → select bill → details drawer with hammali calculation → "Pay & Print".

**9.9 Bills — Detail:** Timeline (created → analysed → paid → printed), attachments, QR, actions (Print/Download/Duplicate/Share).

**9.10 Reports:** Report catalog; run → preview → export (PDF/Excel/CSV/JSON) → email/WhatsApp (free-tier) → schedule → save as favorite.

**9.11 Documents:** Folder tree + file list; upload scan, preview, download; tags + search.

**9.12 Notifications:** Bell popover (unread badge), preferences per category.

**9.13 Activity Log:** Table with filters (actor, action, date); drill-in shows before/after values, IP, device.

**9.14 Settings:** Portal credentials (encrypted), hammali rate, cash threshold, automation toggles, notification channels, roles/permissions, 2FA.

**9.15 AI Assistant panel:** Slide-over chat; tool results rendered as cards/actions (e.g. "Show today's soybean purchases" → rendered bill table).

## 10. User Flows

| Flow | Steps (new) | vs legacy |
|---|---|---|
| Pay & print a bill | cmd+K "search bill" (or Bills→Search) → bill list → select → details+calc → "Pay & Print" → automated portal payment + print | 12+ → ≤ 5 |
| Register farmer | Farmers→Registration → form (autosave) → save | n/a (new) |
| Print pending bills | Reports/queue "pending bills" → select → Bulk Print | manual per bill |
| Verify payments | Payments→Verify → approve/reject | n/a (new) |
| Generate July report | cmd+K "generate July report" → preview → export | manual excel |
| Check stock | Stock dashboard or AI query | n/a (new) |
| Cancel automation | app-level Cancel → resets state, closes browser | n/a |

**Flow rules:** every write action shows save status (autosave drafts with recovery); destructive actions need confirm + audit entry; bulk actions show progress.

---

# Part III — Engineering

## 11. Database Improvements

**Current:** SQLite (`mandi.db`) with `bills`, `logs`, `settings`.

**Target:** PostgreSQL (via asyncpg), single-tenant schema with `tenant_id` columns for future multi-tenancy. Alembic migrations.

| New table | Purpose | Key fields |
|---|---|---|
| `tenants` | Org/office (v1: 1 row) | name, code, settings |
| `users` | App login | tenant_id, username, email, password_hash, role_id, 2fa_secret, trusted_devices |
| `roles` / `role_permissions` | RBAC | role, permission keys |
| `farmers` | Farmer master | aadhaar, name, mobile, village_id, land details, bank_name, account_number, ifsc |
| `traders` | Trader master | gstin, pan, license_no, commission, contact |
| `villages` | Master data | name, block, district |
| `commodities` | Master data | name, unit, code |
| `stock_lots` | Purchase/sale lots | commodity_id, trader_id, segment (govt/trader), qty, price, value, status |
| `bills` | Extend existing | add: source_ref (portal bill no), segment, status, timeline |
| `bill_events` | Bill timeline/history | bill_id, event, actor, old/new value |
| `payments` | Payment ledger | bill_id, farmer_id, amount, method, status, verified_by/at, receipt_no |
| `payment_events` | Payment timeline | payment_id, event, actor, data |
| `documents` | Document center | entity_type/id, kind, file_path, hash, mime, size, uploaded_by |
| `notifications` | Notification center | user/role target, type, payload, read_at |
| `activity_logs` | Audit trail | actor, action, entity, old/new, ip, device, ts |
| `saved_filters` | Per-user filters | user_id, page, json |
| `reports` | Saved/scheduled reports | type, params, schedule, recipients |
| `ai_conversations` | AI chat history | user_id, messages, tool_calls |

**Improvements over current:** typed numerics (Decimal for money), unique keys for bill/payment source refs (idempotency), indexes on all FK + date columns, row-level audit triggers (or app-level audit), soft-delete where required.

## 12. API Improvements

**Current:** 16 routes across automation/bills/settings/history/logs.

**Target (REST, versioned `/api/v1`):**
- `POST /api/v1/auth/login|refresh|logout|otp`
- `GET/POST /api/v1/farmers`, `/api/v1/farmers/{id}/payments`, `/purchases`, `/timeline`, `/analytics`
- `GET/POST /api/v1/traders`, `/api/v1/traders/{id}/stock`, `/payments`, `/analytics`
- `GET /api/v1/stock`, `/api/v1/stock/analytics`, `/api/v1/stock/segments/{segment}`
- `POST /api/v1/payments`, `/api/v1/payments/{id}/verify|reject|receipt|reprint`, `/api/v1/payments/bulk`
- `GET/POST /api/v1/bills/search|create`, `/api/v1/bills/{id}`, `/bills/{id}/events|print|duplicate|share`
- `GET/POST /api/v1/reports/run|export|schedule|favorites`
- `GET/POST /api/v1/documents`, `/api/v1/documents/{id}/download`
- `GET /api/v1/notifications`, `POST /api/v1/notifications/read`
- `GET /api/v1/audit`, `DELETE /api/v1/audit?policy=...`
- `GET/POST /api/v1/automation/*` (existing, preserved + extended: status, sync, jobs)
- `POST /api/v1/ai/chat` (tool-calling)
- `GET/PUT /api/v1/settings/*` (existing, preserved)

**API rules:** `{data, error}` envelope; OpenAPI schemas; idempotency keys on payments/prints; pagination + filtering via query params; rate limiting on auth/AI; server-side validation mirroring portal rules.

## 13. Frontend Architecture

```
frontend/
  src/
    app/            route shells (layout, providers)
    pages/          feature pages (lazy loaded, route-based)
    features/       domain modules (farmers/, traders/, stock/, payments/, bills/, reports/, documents/, notifications/, ai/)
    components/ui/  design-system components
    components/layout/  shell (TopBar, Sidebar, StatusBar, CommandPalette)
    components/data/    SmartTable, StatCard, Timeline, charts
    lib/            api client, auth, session, utils, hooks
    stores/         zustand (auth, ui/theme, dashboard, offline)
    styles/         tokens, base
```

**Key decisions:**
- React + Vite + TypeScript; Tailwind 3.4 (locked — do not upgrade to v4).
- Zustand for UI/auth state; TanStack Query for server state (caching, invalidation).
- TanStack Table for SmartTable; Radix primitives; Recharts; cmdk for command palette.
- Lazy-loaded routes + code splitting; route-based chunking.
- API client with auth + refresh interceptor; offline queue for drafts (extension of existing refresh interceptor).
- Roles drive route/component gating; Inspector role renders read-only.

## 14. Backend Architecture

```
backend/
  app/
    main.py             FastAPI app factory, CORS, error handlers, lifespan
    config.py           pydantic-settings + encryption key
    database.py         async engine (Postgres), sessions, init/migrations
    seed.py             defaults & demo data
    core/
      security.py       JWT, bcrypt, Fernet credential encryption
      rbac.py           role/permission dependency
      events.py         domain event bus (drives automation triggers)
      audit.py          activity log writer
      state_machine.py  automation state (existing, preserved)
      exceptions.py     structured errors (existing, preserved)
    domain/
      auth/  farmers/  traders/  stock/  payments/  bills/  reports/
      documents/  notifications/  ai/  automation/
        (each: schemas.py, service.py, router.py)
    infra/
      db.py            repos/DAO layer
      storage.py       MinIO/S3-compatible file store
      portal.py        Playwright automation engine (existing services/pages preserved)
      notifier.py      Telegram + FCM senders
      ai_client.py     OpenRouter client
      jobs.py          scheduler (APScheduler/celery-beat)
    api/v1/routes/      thin route modules
```

**Key decisions:**
- Domain modules own schemas/services/routes; infra is cross-cutting.
- Domain events → automation: e.g. `payment.recorded` triggers portal payment entry + print job; `bill.analysed` triggers hammali calc persisted.
- Automation engine (existing `AutomationService` + 6 page objects) becomes `infra/portal.py` — preserved, extended with sync + job hooks.
- Scheduler for auto-sync, auto-reports, auto-print queues, notification scans.
- All writes pass through services that enforce RBAC + audit.

## 15. Security Improvements

| Area | Change |
|---|---|
| Credentials | Fernet-encrypted at rest (existing); password/PIN never returned by API (existing, preserve) |
| Auth | JWT access + refresh (existing pattern), session management, auto-logout idle timeout |
| 2FA | TOTP/OTP designed-in (reuse School OS MFA pattern), enabled in hardening phase; trusted devices |
| RBAC | Centralized role→permission matrix; enforced server-side on every route (never client-only) |
| Secrets | No keys in frontend; OpenRouter key server-side only |
| Headers/CORS | Strict CORS (existing), CSP, X-Frame-Options, HSTS in production |
| Audit | Every mutation writes activity_logs (who/when/ip/device/old/new/reason) |
| Payments | Idempotency keys, verify queue, signed receipts (hash) |
| Uploads | File type/size validation, hash, restricted preview |
| Rate limits | Auth, AI, payment endpoints |

## 16. Automation Readiness

- **Portal sync engine:** scheduled sync of bills/payments/stock from portal → ledger; idempotent by source ref.
- **Auto-payment entry & auto-print:** domain events trigger portal actions through the preserved automation engine.
- **Auto-report generation:** scheduled reports render + distribute (email/Telegram).
- **Auto stock update / auto SMS-WhatsApp:** Telegram (free) + FCM (free); WhatsApp via paid gateway later (keep interface).
- **Webhooks:** outbox pattern — outbound webhook delivery for payment/bill events; inbound webhook receiver.
- **API-first:** every UI action calls the same API the automation engine calls — zero divergence.

## 17. AI Integration Strategy

- **Provider:** OpenRouter (OpenAI-compatible), API key server-side in `infra/ai_client.py`. Pluggable interface allows local Ollama later.
- **Capabilities:** conversational queries over the ledger via **tool-calling** against our own APIs.
- **Tools v1:** `search_bills`, `get_stock`, `get_payment_status`, `get_farmer`, `get_trader`, `generate_report`, `print_pending_bills` (confirm-gated), `get_dashboard_summary`.
- **Surfaces:** AI panel (slide-over) + command palette shortcuts.
- **Safety:** tool actions require user confirmation for state-changing tools; conversation history stored per user; all tool calls audited; never returns raw credentials; system prompt scoped to mandi domain.
- **Examples supported:** "Show today's soybean purchases", "Find Bill 1000001", "Print pending bills", "Generate July report", "Show unpaid farmers", "How much stock is available?", "Generate payment summary".

---

# Part IV — Intelligence

*(See §16 Automation Readiness and §17 AI Integration Strategy above.)*

---

# Part V — Delivery

## 18. Mobile Design

- Responsive breakpoints: desktop ≥ 1280 · tablet ≥ 768 · mobile < 768.
- Sidebar → drawer with hamburger; tables → card stacks with horizontal-scroll fallback + sticky first column.
- Touch targets ≥ 44px; bottom action bar on mobile for primary flows.
- PWA-ready shell (installable, offline cached shell, offline draft queue).
- Mobile optimizations for the highest-frequency flows: search bill, pay & print, verify, notifications.

## 19. Accessibility Improvements

- WCAG 2.1 AA target; semantic HTML; Radix for interactive primitives (ARIA correct).
- Full keyboard navigation + visible focus rings; focus trap in dialogs.
- Screen-reader labels for all controls; status regions (`aria-live`) for toasts/progress.
- High-contrast + large-font modes; `prefers-reduced-motion` honored.
- Automated aXe checks in CI; manual screen-reader pass in hardening phase.

## 20. Performance Optimizations

- Lazy-loaded routes + code splitting; route-level chunks.
- TanStack Query caching + optimistic updates; minimal full reloads.
- Virtual tables for large lists (TanStack Table virtualizer); infinite scroll option.
- Skeleton loading everywhere; charts lazy-mount when visible.
- Pagination + indexed queries server-side; aggregated dashboard endpoints (single round-trip).
- Background jobs (scheduler) for sync/print/report; never block requests.
- Lighthouse budget: LCP < 2.5s, CLS < 0.1 on target hardware.

## 21. Migration Plan (Current → Target)

**Current state (as of this plan):**
- Backend rebuilt and verified: FastAPI on port 8000, 16 routes (automation/bills/settings/history/logs), 6 page objects, state machine, Fernet credential encryption, seeded demo credentials (trader ID from env / placeholder), SQLite DB.
- Frontend scaffold not yet recreated (previous scaffold was deleted with the old project; this plan supersedes rebuilding the old shell).
- One pending fix: `/api/settings` response-model correction applied but server restart not yet re-verified.

**Strangler steps:**
1. Finish base verification (restart backend, confirm settings endpoint, confirm health).
2. Phase 0 foundation is built *on* the existing backend + a fresh frontend scaffold; existing `/api/automation/*` preserved unchanged.
3. Each new domain module ships behind the new shell; the automation engine and its routes are never removed — only wrapped.
4. Portal remains source of truth for official records; ledger is operational. Sync bidirectional: portal → ledger (records), ledger → portal (payments, prints) via automation engine.
5. Rollback plan: per-phase feature flags; any phase can be disabled while legacy paths remain reachable.

## 22. Implementation Roadmap

See §25 Development Phases. Sequencing is dependency-ordered: foundation → master data → stock → bills/payments → automation → reporting/docs → AI → hardening.

## 23. Folder Structure

`backend/` and `frontend/` as §13/§14; `docs/superpowers/` holds specs + plans; `infra/` at repo root for docker-compose, nginx, migrations.

## 24. Tech Stack Recommendation

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python FastAPI + SQLAlchemy async + Pydantic v2 | Existing, proven |
| DB | PostgreSQL 16 (asyncpg) | Production ledger; SQLite for dev (existing) |
| Migrations | Alembic | |
| Frontend | React + Vite + TypeScript + Tailwind 3.4 | Locked v3.4 |
| State | Zustand + TanStack Query | |
| Tables | TanStack Table (virtual) | |
| UI primitives | Radix UI | Accessibility |
| Charts | Recharts | |
| Command palette | cmdk | |
| Automation | Playwright (existing) | |
| AI | OpenRouter OpenAI-compatible | Server-side key |
| Files | MinIO (S3-compatible) | Self-hosted |
| Notifications | Telegram Bot + FCM | Free tiers |
| Scheduler | APScheduler | Single office |
| Packaging | Docker Compose + Nginx | |

## 25. Development Phases

| Phase | Scope | Exit criteria |
|---|---|---|
| **0 — Foundation** | Finish base verification; design tokens; component library; ERP shell (TopBar/Sidebar/StatusBar); auth + RBAC; global search cmd+K; smart tables; audit log; dark/high-contrast/large-font modes | Shell runs with seeded roles; cmd+K searches live data; every list uses SmartTable; mutations audited |
| **1 — Master data** | Tenants, users, roles, villages, commodities, farmers, traders; profiles with tabs; timeline/analytics stubs | CRUD + search + profiles for farmers/traders with history |
| **2 — Stock** | Stock lots, government/trader segments, valuations, trend graphs, stock dashboard | Stock dashboard reflects ledger; export works |
| **3 — Bills & payments** | Extend bills (timeline/events/attachments/QR/duplicate/share); payments module (create/verify/pending/completed, receipts, bulk) | Full bill→payment→receipt flow in-app with audit |
| **4 — Automation** | Portal sync engine; auto-pay/auto-print via events; notifications (Telegram/FCM); scheduler jobs | CAPTCHA-assisted bill search→pay→print runs end-to-end unattended; jobs schedulable |
| **5 — Reporting & documents** | Report center (PDF/Excel/CSV/JSON, email/Telegram, schedule, favorites); document center (MinIO upload/preview/search) | Reports run + export + schedule; documents CRUD |
| **6 — AI assistant** | OpenRouter client; tool-calling; AI panel + cmd+K integration | Example queries answered with rendered results; state-changing tools confirm-gated |
| **7 — Hardening** | a11y audit pass, performance budget, mobile refinement, security audit, 2FA/OTP, trusted devices | aXe clean, Lighthouse budget met, security review complete |

## 26. Estimated Timeline

Single full-time engineer + AI-assisted dev (as in this project), open-source stack:

| Phase | Estimate |
|---|---|
| 0 — Foundation | 2–3 weeks |
| 1 — Master data | 2 weeks |
| 2 — Stock | 1.5 weeks |
| 3 — Bills & payments | 2.5 weeks |
| 4 — Automation | 2 weeks |
| 5 — Reporting & documents | 1.5 weeks |
| 6 — AI assistant | 1 week |
| 7 — Hardening | 1.5 weeks |
| **Total** | **~14 weeks** (~3.5 months), with parallelizable chunks (1/2 overlap; 6/7 can partially overlap) |

## 27. Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Portal DOM changes break automation | Med | High | Page objects isolated; selector health-check job; rapid-patch path; manual fallback UI |
| CAPTCHA friction (manual step) | High | Med | OCR pre-fill guess + dialog; attempt-retry loop (existing); user decision to keep hybrid |
| Migration scope creep | Med | High | Strangler; per-phase exit criteria; feature flags; plan gates |
| Money-calculation regressions | Low | High | Preserve calc functions (hammali 12.05, total, cash threshold); golden tests from real bills |
| Single-office scale assumptions | Low | Med | tenant_id schema; role matrix designed multi-org-ready |
| OpenRouter availability/cost | Low | Med | Pluggable AI client; fallback to offline templates for AI tools |
| Data divergence portal↔ledger | Med | High | Idempotent sync by source ref; reconciliation job; conflict flagging |
| Team familiarity with Tailwind 3.4 lock | Low | Low | Documented tokens; no v4 upgrade |

## 28. Future Features Roadmap

- Multi-mandi / multi-tenant SaaS rollout (schema ready).
- 2FA/OTP + trusted devices + passkeys (designed-in, hardening).
- WhatsApp Business payment receipts (paid, behind notifier interface).
- OCR-assisted bill ingestion (document center) for paper bills.
- Predictive analytics: price trend forecasts, payment-due predictions.
- Inspector/regulator read-only portal with government dashboards.
- API tokens + webhooks for external accounting (Tally integration).
- Offline-first mobile app (PWA/Expo) with sync queue.
- Voice assistant (local Whisper) for hands-free queries.
- NFC/QR-based farmer identity at weighbridge (no hardware purchases; QR simulation).
- Kiosk/weighbridge capture terminal integration.

---

*End of plan. Approved foundation decisions documented above. This plan gates every phase's spec → plan → build → verify cycle.*
