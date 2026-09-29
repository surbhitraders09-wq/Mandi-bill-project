# Phase 2 — Stock Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only stock dashboard that aggregates the bills ledger by commodity and government/trader segment, with trend charts, filters, and CSV export.

**Architecture:** Stock is *computed* from the existing `bills` table — no new ledger table. `Bill` gains three nullable columns (`segment`, `commodity_id`, `farmer_id`) via a small `ALTER TABLE` migration in `init_db`. A new read-only `app/domain/stock/` module exposes list + analytics + trader endpoints guarded by the existing `stock:read` permission. The frontend swaps the `/stock` and `/traders/stock` placeholders for a Recharts-driven dashboard page.

**Tech Stack:** FastAPI + SQLAlchemy async (aiosqlite dev), Pydantic v2, React 19 + Vite + TypeScript, TanStack Query + Table, Recharts, Radix Select.

**Spec:** `docs/superpowers/specs/2026-07-31-phase2-stock-design.md`

**Relevant existing patterns (read before starting):**
- Domain module pattern: `backend/app/domain/farmers/{schemas.py,service.py,router.py}`
- RBAC dependency: `backend/app/core/rbac.py` → `require_permission("stock:read")` (already granted to operator/accountant/inspector)
- Audit: `backend/app/core/audit.py` → `record_audit(action, entity, entity_id, ...)`
- Migration approach: `backend/app/database.py` `init_db()` (create_all; add column-ensure step)
- Frontend page pattern: `frontend/src/pages/farmers.tsx` (SmartTable + Select filters)
- Frontend types file: `frontend/src/lib/types.ts`
- Test pattern: `backend/tests/test_masterdata.py` + `backend/tests/conftest.py`

---

### Task 1: Add Bill columns + migration in `init_db`

**Files:**
- Modify: `backend/app/models/bill.py`
- Modify: `backend/app/database.py`
- Test: `backend/tests/test_stock.py` (created later in Task 5; the migration helper is covered indirectly by Task 5's fresh-DB suite)

- [ ] **Step 1: Extend the `Bill` model**

Edit `backend/app/models/bill.py`. Change the imports line and add three columns after `total_amount`:

```python
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
```

```python
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    segment: Mapped[str] = mapped_column(String(20), nullable=False, default="trader")
    commodity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("commodities.id"), nullable=True, index=True
    )
    farmer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("farmers.id"), nullable=True, index=True
    )
```

- [ ] **Step 2: Add the column-ensure migration to `init_db`**

Edit `backend/app/database.py`. Replace the `init_db` function with:

```python
async def init_db() -> None:
    async with engine.begin() as conn:
        from app.models import (  # noqa: F401
            activity_log,
            bill,
            commodity,
            farmer,
            log,
            settings as settings_model,
            trader,
            user,
            village,
        )
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_bill_columns(conn)


async def _ensure_bill_columns(conn) -> None:
    """SQLite create_all does not ALTER existing tables; add new Bill columns if missing."""
    rows = (
        await conn.run_sync(
            lambda sync_conn: sync_conn.exec_driver_sql("PRAGMA table_info(bills)").fetchall()
        )
    )
    existing = {row[1] for row in rows}
    additions = {
        "segment": "VARCHAR(20) NOT NULL DEFAULT 'trader'",
        "commodity_id": "INTEGER",
        "farmer_id": "INTEGER",
    }
    for column, ddl in additions.items():
        if column not in existing:
            await conn.run_sync(
                lambda sync_conn, c=column, d=ddl: sync_conn.exec_driver_sql(
                    f"ALTER TABLE bills ADD COLUMN {c} {d}"
                )
            )
```

- [ ] **Step 3: Verify backend imports cleanly**

Run: `cd backend && venv/bin/python -c "from app.database import init_db; from app.models.bill import Bill; print('ok')"`
Expected: prints `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/bill.py backend/app/database.py
git commit -m "feat: add segment/commodity_id/farmer_id to bills with init migration"
```

---

### Task 2: Stock schemas + aggregation service

**Files:**
- Create: `backend/app/domain/stock/__init__.py` (empty)
- Create: `backend/app/domain/stock/schemas.py`
- Create: `backend/app/domain/stock/service.py`

- [ ] **Step 1: Create the package**

Create `backend/app/domain/stock/__init__.py`:

```python
```

- [ ] **Step 2: Write `schemas.py`**

Create `backend/app/domain/stock/schemas.py`:

```python
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class StockRow(BaseModel):
    commodity_id: Optional[int]
    commodity: str
    segment: str
    qty: float
    avg_rate: Optional[float]
    value: float
    bill_count: int
    last_date: Optional[datetime]


class StockListResponse(BaseModel):
    items: List[StockRow]
    total: int
    limit: int
    offset: int


class TrendPoint(BaseModel):
    date: str
    weight: float
    value: float


class SegmentSlice(BaseModel):
    segment: str
    weight: float
    value: float
    bills: int


class CommoditySlice(BaseModel):
    commodity: str
    weight: float
    value: float


class StockTotals(BaseModel):
    weight: float
    value: float
    avg_rate: Optional[float]
    bills: int


class StockAnalytics(BaseModel):
    daily: List[TrendPoint]
    by_commodity: List[CommoditySlice]
    by_segment: List[SegmentSlice]
    totals: StockTotals
```

- [ ] **Step 3: Write `service.py` — aggregation logic**

Create `backend/app/domain/stock/service.py`:

```python
from collections import defaultdict
from datetime import datetime, time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bill import Bill
from app.models.commodity import Commodity
from app.models.trader import Trader


def _apply_filters(query, commodity_id, segment, date_from, date_to):
    if commodity_id is not None:
        query = query.where(Bill.commodity_id == commodity_id)
    if segment is not None:
        query = query.where(Bill.segment == segment)
    if date_from is not None:
        query = query.where(Bill.date >= datetime.combine(date_from, time.min))
    if date_to is not None:
        query = query.where(Bill.date <= datetime.combine(date_to, time.max))
    return query


def _group_rows(bills: list[Bill]) -> dict:
    """Aggregate bills into buckets keyed by (commodity_label, segment)."""
    buckets: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"commodity_id": None, "qty": 0.0, "rate_w": 0.0, "value": 0.0, "bills": 0, "last": None}
    )
    for b in bills:
        label = b.commodity or "Unknown"
        key = (label, b.segment or "trader")
        bucket = buckets[key]
        bucket["commodity_id"] = b.commodity_id
        bucket["qty"] += b.weight or 0
        bucket["value"] += b.gross_amount or 0
        if b.rate is not None:
            bucket["rate_w"] += (b.weight or 0) * b.rate
        bucket["bills"] += 1
        if bucket["last"] is None or (b.date and b.date > bucket["last"]):
            bucket["last"] = b.date
    return buckets


async def list_stock(
    session: AsyncSession,
    commodity_id: Optional[int] = None,
    segment: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    query = select(Bill)
    query = _apply_filters(query, commodity_id, segment, date_from, date_to)
    if q:
        query = query.where(Bill.commodity.like(f"%{q.strip()}%"))
    bills = (await session.execute(query)).scalars().all()

    buckets = _group_rows(bills)
    rows = []
    for (commodity, seg), data in buckets.items():
        rows.append(
            {
                "commodity_id": data["commodity_id"],
                "commodity": commodity,
                "segment": seg,
                "qty": round(data["qty"], 2),
                "avg_rate": round(data["rate_w"] / data["qty"], 2) if data["qty"] else None,
                "value": round(data["value"], 2),
                "bill_count": data["bills"],
                "last_date": data["last"],
            }
        )
    rows.sort(key=lambda r: (-r["value"], r["commodity"]))
    total = len(rows)
    return {"items": rows[offset : offset + limit], "total": total, "limit": limit, "offset": offset}


async def get_analytics(
    session: AsyncSession,
    commodity_id: Optional[int] = None,
    segment: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    query = select(Bill)
    query = _apply_filters(query, commodity_id, segment, date_from, date_to)
    bills = (await session.execute(query)).scalars().all()

    by_commodity: dict[str, dict] = defaultdict(lambda: {"weight": 0.0, "value": 0.0})
    by_segment: dict[str, dict] = defaultdict(lambda: {"weight": 0.0, "value": 0.0, "bills": 0})
    daily: dict[str, dict] = defaultdict(lambda: {"weight": 0.0, "value": 0.0})
    rate_w = 0.0
    total_weight = 0.0
    total_value = 0.0

    for b in bills:
        w = b.weight or 0
        v = b.gross_amount or 0
        seg = b.segment or "trader"
        label = b.commodity or "Unknown"
        by_commodity[label]["weight"] += w
        by_commodity[label]["value"] += v
        by_segment[seg]["weight"] += w
        by_segment[seg]["value"] += v
        by_segment[seg]["bills"] += 1
        total_weight += w
        total_value += v
        if b.rate is not None:
            rate_w += w * b.rate
        if b.date:
            daily[b.date.date().isoformat()]["weight"] += w
            daily[b.date.date().isoformat()]["value"] += v

    return {
        "daily": [
            {"date": d, "weight": round(v["weight"], 2), "value": round(v["value"], 2)}
            for d, v in sorted(daily.items())
        ],
        "by_commodity": [
            {"commodity": c, "weight": round(v["weight"], 2), "value": round(v["value"], 2)}
            for c, v in sorted(by_commodity.items(), key=lambda kv: -kv[1]["value"])
        ],
        "by_segment": [
            {"segment": s, "weight": round(v["weight"], 2), "value": round(v["value"], 2), "bills": v["bills"]}
            for s, v in sorted(by_segment.items())
        ],
        "totals": {
            "weight": round(total_weight, 2),
            "value": round(total_value, 2),
            "avg_rate": round(rate_w / total_weight, 2) if total_weight else None,
            "bills": len(bills),
        },
    }


async def list_trader_stock(
    session: AsyncSession,
    trader_id: int,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    trader = await session.get(Trader, trader_id)
    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")
    query = select(Bill).where(
        (Bill.trader_name == trader.name) | (Bill.trader_id == str(trader.id))
    )
    bills = (await session.execute(query)).scalars().all()
    buckets = _group_rows(bills)
    rows = []
    for (commodity, seg), data in buckets.items():
        rows.append(
            {
                "commodity_id": data["commodity_id"],
                "commodity": commodity,
                "segment": seg,
                "qty": round(data["qty"], 2),
                "avg_rate": round(data["rate_w"] / data["qty"], 2) if data["qty"] else None,
                "value": round(data["value"], 2),
                "bill_count": data["bills"],
                "last_date": data["last"],
            }
        )
    rows.sort(key=lambda r: (-r["value"], r["commodity"]))
    total = len(rows)
    return {"items": rows[offset : offset + limit], "total": total, "limit": limit, "offset": offset}
```

> Note: `HTTPException` must be imported in `service.py`. Add it to the imports:

```python
from fastapi import HTTPException
```

(Place it above the `sqlalchemy` imports.)

- [ ] **Step 4: Verify imports**

Run: `cd backend && venv/bin/python -c "from app.domain.stock.service import list_stock, get_analytics; print('ok')"`
Expected: prints `ok`

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/stock/
git commit -m "feat: stock aggregation service and schemas"
```

---

### Task 3: Stock router + mount in `main.py`

**Files:**
- Create: `backend/app/domain/stock/router.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the router**

Create `backend/app/domain/stock/router.py`:

```python
from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.rbac import require_permission
from app.database import get_db
from app.domain.stock import service
from app.domain.stock.schemas import StockAnalytics, StockListResponse

router = APIRouter(prefix="/api/v1/stock", tags=["stock"])


async def _audit_read(request: Request, user: dict, params: dict) -> None:
    await record_audit("STOCK_READ", "stock", str(len(params)), details=params, actor=user["username"], request=request)


@router.get("", response_model=StockListResponse)
async def list_stock(
    commodity_id: Optional[int] = Query(None),
    segment: Optional[str] = Query(None),
    date_from: Optional[date_type] = Query(None),
    date_to: Optional[date_type] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("stock:read")),
    request: Request = None,
):
    result = await service.list_stock(
        session, commodity_id=commodity_id, segment=segment,
        date_from=date_from, date_to=date_to, q=q, limit=limit, offset=offset,
    )
    await _audit_read(
        request, user,
        {"commodity_id": commodity_id, "segment": segment, "q": q, "total": result["total"]},
    )
    return result


@router.get("/analytics", response_model=StockAnalytics)
async def get_analytics(
    commodity_id: Optional[int] = Query(None),
    segment: Optional[str] = Query(None),
    date_from: Optional[date_type] = Query(None),
    date_to: Optional[date_type] = Query(None),
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("stock:read")),
    request: Request = None,
):
    result = await service.get_analytics(
        session, commodity_id=commodity_id, segment=segment,
        date_from=date_from, date_to=date_to,
    )
    await _audit_read(request, user, {"segment": segment, "commodity_id": commodity_id, "kind": "analytics"})
    return result


@router.get("/traders/{trader_id}", response_model=StockListResponse)
async def get_trader_stock(
    trader_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("stock:read")),
    request: Request = None,
):
    result = await service.list_trader_stock(session, trader_id, limit=limit, offset=offset)
    await _audit_read(request, user, {"trader_id": trader_id, "total": result["total"]})
    return result
```

> Note: `request: Request = None` combined with `Depends` works in FastAPI because `Request` is auto-injected even when a default is given. `record_audit` guards `request.client` for None. Keep the pattern consistent with Phase 1 routers (they declare `request: Request` as the last param with no default — use that exact style instead if preferred).

- [ ] **Step 2: Mount the router in `main.py`**

Edit `backend/app/main.py`:

Add to the imports block:

```python
from app.domain.stock.router import router as stock_router
```

Add to the router includes:

```python
app.include_router(stock_router)
```

- [ ] **Step 3: Verify app starts**

Run: `cd backend && venv/bin/python -c "from app.main import app; print(len(app.routes))"`
Expected: prints a route count (larger than before) with no exceptions

- [ ] **Step 4: Commit**

```bash
git add backend/app/domain/stock/router.py backend/app/main.py
git commit -m "feat: mount read-only stock endpoints with audit"
```

---

### Task 4: Seed demo bills

**Files:**
- Modify: `backend/app/seed.py`

- [ ] **Step 1: Add imports and the demo-bill seeder**

Edit `backend/app/seed.py`:

Add to the existing imports:

```python
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.models.bill import Bill
```

Add a call in `seed_defaults` after `_seed_master_data(session)`:

```python
        await _seed_master_data(session)
        await _seed_demo_bills(session)
        await session.commit()
```

Add the new function at the end of `seed.py`:

```python
async def _seed_demo_bills(session) -> None:
    bill_count = (await session.execute(select(func.count(Bill.id)))).scalar_one()
    if bill_count:
        return

    commodities = {c.name: c for c in (await session.execute(select(Commodity))).scalars().all()}
    farmers = (await session.execute(select(Farmer))).scalars().all()
    traders = {t.name: t for t in (await session.execute(select(Trader))).scalars().all()}
    if not commodities or not farmers or not traders:
        return

    govt = "MP State Civil Supplies"
    today = datetime.utcnow()

    def bill(spec: dict) -> Bill:
        commodity = commodities[spec["commodity"]]
        farmer = farmers[spec["farmer_idx"] % len(farmers)]
        trader_name = spec["trader"]
        weight = spec["weight"]
        rate = spec["rate"]
        gross = round(weight * rate, 2)
        hammali = round(weight * 12.05, 2)
        return Bill(
            trader_name=trader_name,
            trader_id=(traders[trader_name].gstin if trader_name in traders else None),
            bill_number=spec["bill_number"],
            commodity=spec["commodity"],
            commodity_id=commodity.id,
            farmer_id=farmer.id,
            segment=spec["segment"],
            date=today - timedelta(days=spec["days_ago"]),
            vehicle_number=spec["vehicle"],
            weight=weight,
            rate=rate,
            gross_amount=gross,
            hammali_rate=12.05,
            hammali_amount=hammali,
            total_amount=round(gross + hammali, 2),
        )

    demo_bills = [
        {"bill_number": "SOY-0001", "commodity": "Soybean", "trader": "Sharma Traders", "segment": "trader",
         "weight": 12.5, "rate": 4200, "days_ago": 28, "farmer_idx": 0, "vehicle": "MP-30-A-1001"},
        {"bill_number": "SOY-0002", "commodity": "Soybean", "trader": "Sharma Traders", "segment": "trader",
         "weight": 8.0, "rate": 4250, "days_ago": 21, "farmer_idx": 1, "vehicle": "MP-30-B-2002"},
        {"bill_number": "SOY-0003", "commodity": "Soybean", "trader": govt, "segment": "government",
         "weight": 22.0, "rate": 4150, "days_ago": 7, "farmer_idx": 0, "vehicle": "MP-30-C-3003"},
        {"bill_number": "WHT-0001", "commodity": "Wheat", "trader": "Agro Corporation", "segment": "trader",
         "weight": 20.0, "rate": 2450, "days_ago": 25, "farmer_idx": 2, "vehicle": "MP-30-D-4004"},
        {"bill_number": "WHT-0002", "commodity": "Wheat", "trader": "Ganga Mandi House", "segment": "trader",
         "weight": 16.0, "rate": 2500, "days_ago": 5, "farmer_idx": 1, "vehicle": "MP-30-E-5005"},
        {"bill_number": "GRM-0001", "commodity": "Gram", "trader": govt, "segment": "government",
         "weight": 15.0, "rate": 5600, "days_ago": 18, "farmer_idx": 0, "vehicle": "MP-30-F-6006"},
        {"bill_number": "GRM-0002", "commodity": "Gram", "trader": "Sharma Traders", "segment": "trader",
         "weight": 10.0, "rate": 5700, "days_ago": 4, "farmer_idx": 1, "vehicle": "MP-30-G-7007"},
        {"bill_number": "PDY-0001", "commodity": "Paddy", "trader": "Ganga Mandi House", "segment": "trader",
         "weight": 18.0, "rate": 2300, "days_ago": 14, "farmer_idx": 2, "vehicle": "MP-30-H-8008"},
        {"bill_number": "PDY-0002", "commodity": "Paddy", "trader": "Ganga Mandi House", "segment": "trader",
         "weight": 14.0, "rate": 2250, "days_ago": 1, "farmer_idx": 0, "vehicle": "MP-30-I-9009"},
        {"bill_number": "MST-0001", "commodity": "Mustard", "trader": "Sharma Traders", "segment": "trader",
         "weight": 6.5, "rate": 5900, "days_ago": 10, "farmer_idx": 2, "vehicle": "MP-30-J-1010"},
        {"bill_number": "MST-0002", "commodity": "Mustard", "trader": govt, "segment": "government",
         "weight": 11.0, "rate": 5800, "days_ago": 2, "farmer_idx": 1, "vehicle": "MP-30-K-1111"},
        {"bill_number": "LNT-0001", "commodity": "Lentil", "trader": "Agro Corporation", "segment": "trader",
         "weight": 9.0, "rate": 6100, "days_ago": 6, "farmer_idx": 0, "vehicle": "MP-30-L-1212"},
    ]

    for spec in demo_bills:
        session.add(bill(spec))
```

- [ ] **Step 2: Verify seed runs against a scratch DB**

Run: `cd backend && MANDI_DATABASE_URL="sqlite+aiosqlite:///./scratch_seed.db" venv/bin/python -c "
import asyncio
from app.database import init_db
from app.seed import seed_defaults
from app.database import async_session_factory
from sqlalchemy import select, func
from app.models.bill import Bill

async def main():
    await init_db()
    await seed_defaults()
    async with async_session_factory() as s:
        n = (await s.execute(select(func.count(Bill.id)))).scalar_one()
        print('bills seeded:', n)
        assert n == 12, n

asyncio.run(main())
" && rm -f scratch_seed.db`
Expected: prints `bills seeded: 12`

- [ ] **Step 3: Commit**

```bash
git add backend/app/seed.py
git commit -m "feat: seed 12 demo bills across commodities and segments"
```

---

### Task 5: Backend tests for stock

**Files:**
- Create: `backend/tests/test_stock.py`

- [ ] **Step 1: Write the test suite**

Create `backend/tests/test_stock.py`:

```python
import pytest


async def _login(client, username="admin", password="admin123"):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_stock_aggregates_seeded_bills(client):
    headers = await _login(client, "admin")
    resp = await client.get("/api/v1/stock", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] >= 5
    soy = next((i for i in data["items"] if i["commodity"] == "Soybean" and i["segment"] == "trader"), None)
    assert soy is not None
    assert soy["qty"] == pytest.approx(20.5)
    assert soy["value"] == pytest.approx(86500.0)
    assert soy["bill_count"] == 2
    assert soy["avg_rate"] == pytest.approx(86500.0 / 20.5)


@pytest.mark.asyncio
async def test_stock_segment_filter(client):
    headers = await _login(client, "admin")
    govt = await client.get("/api/v1/stock?segment=government", headers=headers)
    assert govt.status_code == 200
    assert all(i["segment"] == "government" for i in govt.json()["items"])


@pytest.mark.asyncio
async def test_stock_commodity_filter(client):
    headers = await _login(client, "admin")
    resp = await client.get("/api/v1/stock?commodity_id=1", headers=headers)
    assert resp.status_code == 200
    assert all(i["commodity_id"] == 1 for i in resp.json()["items"])


@pytest.mark.asyncio
async def test_stock_date_filter(client):
    headers = await _login(client, "admin")
    # from yesterday onward: only bills with days_ago <= 1
    from datetime import date, timedelta

    to_date = date.today().isoformat()
    resp = await client.get(f"/api/v1/stock?date_from={to_date}", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    # expect only the single bill seeded 1 day ago (PDY-0002)
    pdy = next((i for i in items if i["commodity"] == "Paddy"), None)
    assert pdy is not None
    assert pdy["qty"] == pytest.approx(14.0)


@pytest.mark.asyncio
async def test_stock_empty_filter(client):
    headers = await _login(client, "admin")
    resp = await client.get("/api/v1/stock?q=zzz_no_match", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_stock_analytics_shape(client):
    headers = await _login(client, "admin")
    resp = await client.get("/api/v1/stock/analytics", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "daily" in data and "by_commodity" in data and "by_segment" in data
    assert data["totals"]["bills"] == 12
    assert data["totals"]["value"] > 0
    segs = {s["segment"] for s in data["by_segment"]}
    assert segs == {"trader", "government"}


@pytest.mark.asyncio
async def test_stock_trader_endpoint(client):
    headers = await _login(client, "admin")
    traders = await client.get("/api/v1/traders?q=Sharma", headers=headers)
    trader = traders.json()["items"][0]
    resp = await client.get(f"/api/v1/stock/traders/{trader['id']}", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] >= 3


@pytest.mark.asyncio
async def test_stock_rbac_roles(client):
    from app.core.security import hash_password
    from app.database import async_session_factory
    from app.models.user import Role, User
    from sqlalchemy import select

    async with async_session_factory() as session:
        role = (await session.execute(select(Role).where(Role.name == "inspector"))).scalar_one()
        exists = (
            await session.execute(select(User).where(User.username == "inspector_stock"))
        ).scalar_one_or_none()
        if exists is None:
            session.add(User(username="inspector_stock", password_hash=hash_password("inspector123"), role_id=role.id))
            await session.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "inspector_stock", "password": "inspector123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get("/api/v1/stock", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stock_read_is_audited(client):
    headers = await _login(client, "admin")
    await client.get("/api/v1/stock?segment=trader", headers=headers)
    audit = await client.get("/api/v1/audit?limit=20", headers=headers)
    assert audit.status_code == 200
    assert any("AUDIT STOCK_READ" in item["message"] for item in audit.json()["items"])
```

- [ ] **Step 2: Run the full backend suite**

Run: `cd backend && venv/bin/python -m pytest -q`
Expected: `24 passed` (16 existing + 8 new stock tests)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_stock.py
git commit -m "test: stock aggregation, filters, RBAC, audit"
```

---

### Task 6: Frontend types + StatCard + stock charts

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/components/data/stat-card.tsx`
- Create: `frontend/src/components/data/stock-charts.tsx`

- [ ] **Step 1: Extend `types.ts`**

Append to `frontend/src/lib/types.ts`:

```ts
export interface StockRow {
  commodity_id: number | null
  commodity: string
  segment: string
  qty: number
  avg_rate: number | null
  value: number
  bill_count: number
  last_date?: string | null
}

export interface StockTotals {
  weight: number
  value: number
  avg_rate: number | null
  bills: number
}

export interface StockAnalytics {
  daily: { date: string; weight: number; value: number }[]
  by_commodity: { commodity: string; weight: number; value: number }[]
  by_segment: { segment: string; weight: number; value: number; bills: number }[]
  totals: StockTotals
}
```

- [ ] **Step 2: Create `StatCard`**

Create `frontend/src/components/data/stat-card.tsx`:

```tsx
import type { ReactNode } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

interface StatCardProps {
  label: string
  icon?: ReactNode
  value?: ReactNode
  hint?: string
  loading?: boolean
}

export function StatCard({ label, icon, value, hint, loading = false }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted">{label}</CardTitle>
        {icon && <span className="text-muted">{icon}</span>}
      </CardHeader>
      <CardContent>
        {loading ? <Skeleton className="h-8 w-24" /> : <p className="text-2xl font-semibold tabular-nums">{value}</p>}
        {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 3: Create `stock-charts.tsx`**

Create `frontend/src/components/data/stock-charts.tsx`:

```tsx
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { StockAnalytics } from '@/lib/types'

const SEGMENT_COLORS: Record<string, string> = {
  trader: 'var(--color-primary)',
  government: 'var(--color-saffron, #f97316)',
}
const COMMODITY_COLORS = ['var(--color-primary)', '#f97316', '#10b981', '#8b5cf6', '#ef4444', '#f59e0b']

interface StockChartsProps {
  analytics?: StockAnalytics
  loading?: boolean
}

function ChartSkeleton() {
  return <Skeleton className="h-64 w-full" />
}

export function StockCharts({ analytics, loading = false }: StockChartsProps) {
  if (loading) {
    return (
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2"><CardContent className="pt-6"><ChartSkeleton /></CardContent></Card>
        <Card><CardContent className="pt-6"><ChartSkeleton /></CardContent></Card>
        <Card className="lg:col-span-3"><CardContent className="pt-6"><ChartSkeleton /></CardContent></Card>
      </div>
    )
  }
  if (!analytics) return null

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="text-base">Daily purchase trend</CardTitle>
        </CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={analytics.daily} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="valueGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="date" stroke="var(--color-muted)" fontSize={11} />
              <YAxis stroke="var(--color-muted)" fontSize={11} />
              <Tooltip />
              <Area type="monotone" dataKey="value" name="Value (₹)" stroke="var(--color-primary)" fill="url(#valueGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Commodity distribution</CardTitle>
        </CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={analytics.by_commodity} dataKey="weight" nameKey="commodity" innerRadius={40} outerRadius={80} paddingAngle={2}>
                {analytics.by_commodity.map((c, i) => (
                  <Cell key={c.commodity} fill={COMMODITY_COLORS[i % COMMODITY_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="lg:col-span-3">
        <CardHeader>
          <CardTitle className="text-base">Segment split</CardTitle>
        </CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={analytics.by_segment} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="segment" stroke="var(--color-muted)" fontSize={11} />
              <YAxis stroke="var(--color-muted)" fontSize={11} />
              <Tooltip />
              <Bar dataKey="weight" name="Weight" radius={[4, 4, 0, 0]}>
                {analytics.by_segment.map((s) => (
                  <Cell key={s.segment} fill={SEGMENT_COLORS[s.segment] ?? 'var(--color-primary)'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 4: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build succeeds, lint clean

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/components/data/stat-card.tsx frontend/src/components/data/stock-charts.tsx
git commit -m "feat: stock types, StatCard, Recharts dashboard charts"
```

---

### Task 7: Stock page + routes

**Files:**
- Create: `frontend/src/pages/stock.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the stock page**

Create `frontend/src/pages/stock.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { createColumnHelper, type ColumnDef } from '@tanstack/react-table'
import { Scale, IndianRupee, Receipt, TrendingUp } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { SmartTable } from '@/components/data/smart-table'
import { StatCard } from '@/components/data/stat-card'
import { StockCharts } from '@/components/data/stock-charts'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { api } from '@/lib/api'
import type { Commodity, ListResponse, StockAnalytics, StockRow } from '@/lib/types'

const columnHelper = createColumnHelper<StockRow>()

const SEGMENT_OPTIONS = [
  { value: '', label: 'All segments' },
  { value: 'trader', label: 'Trader' },
  { value: 'government', label: 'Government' },
]

function fmt(value: number | null | undefined, prefix = ''): string {
  if (value === null || value === undefined) return '—'
  return `${prefix}${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

interface StockPageProps {
  defaultSegment?: string
  title?: string
}

export function StockPage({ defaultSegment = '', title = 'Stock' }: StockPageProps) {
  const [searchParams] = useSearchParams()
  const urlCommodity = searchParams.get('commodity')

  const [commodityId, setCommodityId] = useState(urlCommodity ?? '')
  const [segment, setSegment] = useState(defaultSegment)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [applied, setApplied] = useState<{ commodityId: string; segment: string; from: string; to: string }>({
    commodityId: urlCommodity ?? '',
    segment: defaultSegment,
    from: '',
    to: '',
  })

  const commodities = useQuery({
    queryKey: ['commodities'],
    queryFn: () => api<ListResponse<Commodity>>('/api/v1/commodities?limit=500'),
  })

  const params = new URLSearchParams()
  if (applied.commodityId) params.set('commodity_id', applied.commodityId)
  if (applied.segment) params.set('segment', applied.segment)
  if (applied.from) params.set('date_from', applied.from)
  if (applied.to) params.set('date_to', applied.to)
  const qs = params.toString()

  const stock = useQuery({
    queryKey: ['stock', qs],
    queryFn: () => api<ListResponse<StockRow>>(`/api/v1/stock?limit=500${qs ? `&${qs}` : ''}`),
  })
  const analytics = useQuery({
    queryKey: ['stock-analytics', qs],
    queryFn: () => api<StockAnalytics>(`/api/v1/stock/analytics${qs ? `?${qs}` : ''}`),
  })

  const apply = () =>
    setApplied({ commodityId, segment, from: dateFrom, to: dateTo })

  const columns = useMemo<ColumnDef<StockRow, any>[]>(
    () => [
      columnHelper.accessor('commodity', { header: 'Commodity', cell: (info) => info.getValue() }),
      columnHelper.accessor('segment', {
        header: 'Segment',
        cell: (info) => <Badge variant={info.getValue() === 'government' ? 'warning' : 'default'}>{info.getValue()}</Badge>,
      }),
      columnHelper.accessor('qty', { header: 'Qty', cell: (info) => fmt(info.getValue()) }),
      columnHelper.accessor('avg_rate', { header: 'Avg rate', cell: (info) => fmt(info.getValue(), '₹') }),
      columnHelper.accessor('value', { header: 'Value', cell: (info) => fmt(info.getValue(), '₹') }),
      columnHelper.accessor('bill_count', { header: 'Bills', cell: (info) => info.getValue() }),
      columnHelper.accessor('last_date', {
        header: 'Last date',
        cell: (info) => (info.getValue() ? new Date(info.getValue()).toLocaleDateString() : '—'),
      }),
    ],
    [],
  )

  const totals = analytics.data?.totals

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="text-sm text-muted">Live commodity stock computed from the bill ledger.</p>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-md border border-border bg-surface p-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="stock-commodity">Commodity</Label>
          <Select
            id="stock-commodity"
            value={commodityId}
            onChange={(e) => setCommodityId(e.target.value)}
            options={[
              { value: '', label: 'All commodities' },
              ...(commodities.data?.items ?? []).map((c) => ({ value: String(c.id), label: c.name })),
            ]}
            className="w-48"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="stock-segment">Segment</Label>
          <Select
            id="stock-segment"
            value={segment}
            onChange={(e) => setSegment(e.target.value)}
            options={SEGMENT_OPTIONS}
            className="w-40"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="stock-from">From</Label>
          <Input id="stock-from" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="w-40" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="stock-to">To</Label>
          <Input id="stock-to" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="w-40" />
        </div>
        <Button onClick={apply}>Apply</Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total weight" icon={<Scale className="h-4 w-4" />} value={fmt(totals?.weight)} loading={analytics.isLoading} hint="quintals" />
        <StatCard label="Total value" icon={<IndianRupee className="h-4 w-4" />} value={fmt(totals?.value, '₹')} loading={analytics.isLoading} />
        <StatCard label="Avg rate" icon={<TrendingUp className="h-4 w-4" />} value={fmt(totals?.avg_rate, '₹')} loading={analytics.isLoading} />
        <StatCard label="Bills" icon={<Receipt className="h-4 w-4" />} value={String(totals?.bills ?? '')} loading={analytics.isLoading} />
      </div>

      <StockCharts analytics={analytics.data} loading={analytics.isLoading} />

      <SmartTable<StockRow>
        columns={columns}
        data={stock.data?.items ?? []}
        loading={stock.isLoading}
        searchPlaceholder="Filter commodities…"
        exportName={`stock-${applied.segment || 'all'}`}
        filterKey="stock-list"
      />
    </div>
  )
}
```

- [ ] **Step 2: Wire routes in `App.tsx`**

Edit `frontend/src/App.tsx`:

Add import:

```tsx
import { StockPage } from '@/pages/stock'
```

Replace the `/stock` placeholder route:

```tsx
          <Route
            path="/stock"
            element={
              <Permission permission="stock:read">
                <StockPage />
              </Permission>
            }
          />
```

Replace the `/traders/stock` placeholder route:

```tsx
          <Route
            path="/traders/stock"
            element={
              <Permission permission="stock:read">
                <StockPage defaultSegment="trader" title="Trader Stock" />
              </Permission>
            }
          />
```

- [ ] **Step 3: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build succeeds, lint clean

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/stock.tsx frontend/src/App.tsx
git commit -m "feat: stock dashboard page with filters, KPIs, charts, export"
```

---

### Task 8: Live verification + e2e smoke

**Files:**
- Modify: `backend/app/seed.py` (no change needed — verify idempotency on the real DB)
- Test: Playwright smoke script (extend the Phase 1 pattern)

- [ ] **Step 1: Restart the backend and verify the live API**

Kill the running backend, then start fresh (separate commands — killing in the same shell as start hangs):

```bash
pkill -f "uvicorn app.main:app" || true
```

Then:

```bash
cd backend && nohup venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend-server.log 2>&1 &
```

Then verify (login → seed bills present → stock aggregates):

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/stock" | python3 -m json.tool | head -40
```

Expected: `items` non-empty with seeded commodities/segments, `total` ≥ 5.

Also verify idempotent seed — restart once more and confirm bill count stays 12:

```bash
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/stock/analytics" | python3 -c "import sys,json;print('bills:', json.load(sys.stdin)['totals']['bills'])"
```

Expected: `bills: 12` (after exactly one prior restart on the real DB — if the DB already has the 12 from the scratch run, it's still idempotent).

- [ ] **Step 2: Run the full backend test suite once more**

Run: `cd backend && venv/bin/python -m pytest -q`
Expected: `24 passed`

- [ ] **Step 3: Write and run the Playwright smoke**

Create `/tmp/smoke-phase2.mjs` (in `$HOME` so Node resolves `playwright` from `~/node_modules`):

```js
import { chromium } from 'playwright';

const base = 'http://localhost:5173';
const results = [];
const check = (name, ok, extra='') => results.push(`${ok ? 'PASS' : 'FAIL'} ${name}${extra ? ' — '+extra : ''}`);

const browser = await chromium.launch({ executablePath: '/usr/bin/chromium' });
const page = await browser.newPage();
const errors = [];
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', e => errors.push(String(e)));

// 1. Login
await page.goto(base + '/login');
await page.waitForSelector('text=e-Mandi ERP');
await page.fill('#username', 'admin');
await page.fill('#password', 'admin123');
await page.click('button[type=submit]');
await page.waitForURL('**/dashboard', { timeout: 10000 });
check('login redirects to dashboard', true);

// 2. Stock page renders
await page.goto(base + '/stock');
await page.waitForSelector('text=Live commodity stock', { timeout: 10000 });
await page.waitForSelector('text=Soybean', { timeout: 10000 });
check('stock dashboard renders table + seeded commodities', true);

// 3. KPIs present
const kpi = await page.locator('text=Total value').count();
check('stock KPI cards present', kpi > 0);

// 4. Charts render (Recharts mounts SVG paths)
await page.waitForSelector('text=Daily purchase trend', { timeout: 10000 });
check('trend chart section renders', true);

// 5. Segment filter updates table
await page.selectOption('#stock-segment', 'government');
await page.click('text=Apply');
await page.waitForTimeout(800);
const govtRows = await page.locator('tbody tr').count();
check('segment filter applied', govtRows > 0);

// 6. Traders stock route renders
await page.goto(base + '/traders/stock');
await page.waitForSelector('text=Trader Stock', { timeout: 10000 });
check('trader stock page renders', true);

// 7. cmd+K commodity hit navigates to /stock?commodity=
await page.keyboard.press('Control+k');
await page.waitForSelector('text=Global search', { timeout: 5000 });
await page.fill('input[placeholder*="Search bills"]', 'Soybean');
await page.waitForTimeout(1500);
const hit = await page.locator('text=Soybean').count();
check('cmd+K finds commodity', hit > 0);
await page.keyboard.press('Escape');

// 8. Legacy pages still live
let legacyOk = true;
for (const [path, heading] of [['/bills','Bills'],['/audit','Activity Log'],['/settings','Settings'],['/automation','Automation'],['/farmers','Farmer Registration']]) {
  await page.goto(base + path);
  try { await page.waitForSelector(`text=${heading}`, { timeout: 10000 }); }
  catch { legacyOk = false; }
}
check('legacy pages still render', legacyOk);

const consoleErrors = errors.filter(e => !e.includes('favicon'));
check('no console errors', consoleErrors.length === 0, consoleErrors.slice(0,2).join(' | '));

await browser.close();
console.log(results.join('\n'));
```

Run it:

```bash
cp /tmp/smoke-phase2.mjs /home/hereyashhh/smoke-phase2.mjs && node /home/hereyashhh/smoke-phase2.mjs
```

Expected: 10 PASS lines, 0 FAIL.

- [ ] **Step 4: Clean up**

```bash
rm -f /home/hereyashhh/smoke-phase2.mjs
```

- [ ] **Step 5: Commit (if any fixes were made during verification)**

```bash
git add -A
git commit -m "chore: phase 2 verification fixes"
```

---

## Self-Review Notes

- **Spec coverage:** Every §3 endpoint (list, analytics, trader) has a task; §2 migration in Task 1; §4 seed in Task 4; §5 page + `/traders/stock` + cmd+K in Tasks 6–7; §6 preservation respected (only additive changes; legacy routes untouched); §7 tests in Task 5 + Task 8 smoke.
- **Type consistency:** `StockRow`, `StockAnalytics`, `StockTotals` names match between `schemas.py` (Python) and `types.ts` (TS). Service returns match schema fields. Router query params (`date_from`, `date_to`) match frontend query builder.
- **Known gap closed:** `Badge` variants verified — uses existing `default` + `warning` (no Badge change needed).
- **Seed determinism:** Tests in Task 5 rely on `test_mandi.db` being recreated by `conftest.prepare_db` (drop_all + create_all + seed) — deterministic 12 bills.
