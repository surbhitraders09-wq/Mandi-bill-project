from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.villages.schemas import VillageCreate, VillageUpdate
from app.models.village import Village


async def list_villages(
    session: AsyncSession,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    query = select(Village).order_by(Village.created_at.desc())
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                Village.name.like(like),
                Village.block.like(like),
                Village.district.like(like),
            )
        )
    total = len((await session.execute(select(Village.id))).scalars().all())
    rows = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


async def get_village(session: AsyncSession, village_id: int) -> Village:
    row = await session.get(Village, village_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Village not found")
    return row


async def create_village(session: AsyncSession, payload: VillageCreate) -> Village:
    row = Village(**payload.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def update_village(session: AsyncSession, village_id: int, payload: VillageUpdate) -> Village:
    row = await get_village(session, village_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row


async def delete_village(session: AsyncSession, village_id: int) -> None:
    row = await get_village(session, village_id)
    await session.delete(row)
    await session.commit()
