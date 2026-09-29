from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select

from app.core.rbac import require_permission
from app.database import async_session_factory
from app.models.bill import Bill
from app.models.commodity import Commodity
from app.models.farmer import Farmer
from app.models.trader import Trader
from app.models.village import Village

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("")
async def global_search(
    q: str = Query("", min_length=0, max_length=200),
    limit: int = Query(10, ge=1, le=50),
    _: dict = Depends(require_permission("search:read")),
):
    term = q.strip()
    if not term:
        return {"items": []}
    like = f"%{term}%"

    async with async_session_factory() as session:
        bill_rows = (
            await session.execute(
                select(Bill)
                .where(
                    or_(
                        Bill.bill_number.like(like),
                        Bill.trader_name.like(like),
                        Bill.commodity.like(like),
                        Bill.vehicle_number.like(like),
                    )
                )
                .limit(limit)
            )
        ).scalars().all()

        farmer_rows = (
            await session.execute(
                select(Farmer)
                .where(
                    or_(
                        Farmer.name.like(like),
                        Farmer.aadhaar.like(like),
                        Farmer.mobile.like(like),
                    )
                )
                .limit(limit)
            )
        ).scalars().all()

        trader_rows = (
            await session.execute(
                select(Trader)
                .where(
                    or_(
                        Trader.name.like(like),
                        Trader.gstin.like(like),
                        Trader.pan.like(like),
                        Trader.license_no.like(like),
                        Trader.mobile.like(like),
                    )
                )
                .limit(limit)
            )
        ).scalars().all()

        commodity_rows = (
            await session.execute(
                select(Commodity)
                .where(or_(Commodity.name.like(like), Commodity.code.like(like)))
                .limit(limit)
            )
        ).scalars().all()

        village_rows = (
            await session.execute(
                select(Village).where(Village.name.like(like)).limit(limit)
            )
        ).scalars().all()

    items = []
    items += [
        {
            "type": "bill",
            "id": b.id,
            "title": f"Bill {b.bill_number}",
            "subtitle": f"{b.trader_name} · {b.commodity}",
            "route": f"/bills/{b.id}",
        }
        for b in bill_rows
    ]
    items += [
        {
            "type": "farmer",
            "id": f.id,
            "title": f.name,
            "subtitle": f"Aadhaar {f.aadhaar}" + (f" · {f.mobile}" if f.mobile else ""),
            "route": f"/farmers/{f.id}",
        }
        for f in farmer_rows
    ]
    items += [
        {
            "type": "trader",
            "id": t.id,
            "title": t.name,
            "subtitle": (f"GST {t.gstin} · " if t.gstin else "") + (f"License {t.license_no}" if t.license_no else ""),
            "route": f"/traders/{t.id}",
        }
        for t in trader_rows
    ]
    items += [
        {
            "type": "commodity",
            "id": c.id,
            "title": c.name,
            "subtitle": c.code or "",
            "route": f"/stock?commodity={c.id}",
        }
        for c in commodity_rows
    ]
    items += [
        {
            "type": "village",
            "id": v.id,
            "title": v.name,
            "subtitle": v.district or "",
            "route": f"/farmers?village={v.id}",
        }
        for v in village_rows
    ]
    return {"items": items}
