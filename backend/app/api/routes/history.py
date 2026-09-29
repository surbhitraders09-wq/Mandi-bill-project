from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.bill import Bill
from app.schemas.bill import BillListResponse, BillOut

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=BillListResponse)
async def get_history(
    printed_only: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> BillListResponse:
    query = select(Bill).order_by(Bill.created_at.desc())
    if printed_only:
        query = query.where(Bill.printed.is_(True))
    items = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    return BillListResponse(
        items=[BillOut.model_validate(b) for b in items],
        total=len(items),
        limit=limit,
        offset=offset,
    )
