from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.commodities.schemas import CommodityCreate, CommodityUpdate
from app.models.commodity import Commodity


async def list_commodities(
    session: AsyncSession,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    query = select(Commodity).order_by(Commodity.created_at.desc())
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                Commodity.name.like(like),
                Commodity.code.like(like),
            )
        )
    total = len((await session.execute(select(Commodity.id))).scalars().all())
    rows = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


async def get_commodity(session: AsyncSession, commodity_id: int) -> Commodity:
    row = await session.get(Commodity, commodity_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Commodity not found")
    return row


async def create_commodity(session: AsyncSession, payload: CommodityCreate) -> Commodity:
    row = Commodity(**payload.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def update_commodity(session: AsyncSession, commodity_id: int, payload: CommodityUpdate) -> Commodity:
    row = await get_commodity(session, commodity_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row


async def delete_commodity(session: AsyncSession, commodity_id: int) -> None:
    row = await get_commodity(session, commodity_id)
    await session.delete(row)
    await session.commit()
