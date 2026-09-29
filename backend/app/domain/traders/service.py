from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.traders.schemas import TraderCreate, TraderUpdate
from app.models.trader import Trader


async def list_traders(
    session: AsyncSession,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    query = select(Trader).order_by(Trader.created_at.desc())
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                Trader.name.like(like),
                Trader.gstin.like(like),
                Trader.pan.like(like),
                Trader.license_no.like(like),
                Trader.mobile.like(like),
            )
        )
    total = len((await session.execute(select(Trader.id))).scalars().all())
    rows = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


async def get_trader(session: AsyncSession, trader_id: int) -> Trader:
    row = await session.get(Trader, trader_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trader not found")
    return row


async def create_trader(session: AsyncSession, payload: TraderCreate) -> Trader:
    row = Trader(**payload.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def update_trader(session: AsyncSession, trader_id: int, payload: TraderUpdate) -> Trader:
    row = await get_trader(session, trader_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row


async def delete_trader(session: AsyncSession, trader_id: int) -> None:
    row = await get_trader(session, trader_id)
    await session.delete(row)
    await session.commit()
