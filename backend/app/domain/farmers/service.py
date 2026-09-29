from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.farmers.schemas import FarmerCreate, FarmerUpdate
from app.exceptions import AppError
from app.models.farmer import Farmer
from app.models.village import Village


def _village_name(row: Farmer, villages: dict[int, str]) -> Optional[str]:
    return villages.get(row.village_id) if row.village_id else None


def _to_out(row: Farmer, villages: dict[int, str]) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "aadhaar": row.aadhaar,
        "mobile": row.mobile,
        "village_id": row.village_id,
        "village_name": _village_name(row, villages),
        "land_area": row.land_area,
        "bank_name": row.bank_name,
        "account_number": row.account_number,
        "ifsc_code": row.ifsc_code,
        "created_at": row.created_at,
    }


async def _load_villages(session: AsyncSession) -> dict[int, str]:
    rows = (await session.execute(select(Village))).scalars().all()
    return {v.id: v.name for v in rows}


async def list_farmers(
    session: AsyncSession,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    query = select(Farmer).order_by(Farmer.created_at.desc())
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                Farmer.name.like(like),
                Farmer.aadhaar.like(like),
                Farmer.mobile.like(like),
            )
        )
    total = len((await session.execute(select(Farmer.id))).scalars().all())
    rows = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    villages = await _load_villages(session)
    return {
        "items": [_to_out(r, villages) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_farmer(session: AsyncSession, farmer_id: int) -> Farmer:
    row = await session.get(Farmer, farmer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Farmer not found")
    return row


async def get_farmer_out(session: AsyncSession, farmer_id: int) -> dict:
    row = await get_farmer(session, farmer_id)
    villages = await _load_villages(session)
    return _to_out(row, villages)


async def create_farmer(session: AsyncSession, payload: FarmerCreate) -> Farmer:
    row = Farmer(**payload.model_dump())
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise AppError("Farmer with this Aadhaar already exists", status_code=409)
    await session.refresh(row)
    return row


async def update_farmer(session: AsyncSession, farmer_id: int, payload: FarmerUpdate) -> Farmer:
    row = await get_farmer(session, farmer_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise AppError("Farmer with this Aadhaar already exists", status_code=409)
    await session.refresh(row)
    return row


async def delete_farmer(session: AsyncSession, farmer_id: int) -> None:
    row = await get_farmer(session, farmer_id)
    await session.delete(row)
    await session.commit()
