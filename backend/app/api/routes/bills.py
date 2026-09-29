from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import NotFoundError
from app.models.bill import Bill
from app.schemas.bill import BillListResponse, BillOut, BillPaymentUpdate
from app.services.logging_service import log as db_log

router = APIRouter(prefix="/api/bills", tags=["bills"])


@router.get("", response_model=BillListResponse)
async def list_bills(
    printed: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> BillListResponse:
    query = select(Bill).order_by(Bill.created_at.desc())
    count_query = select(func.count(Bill.id))
    if printed is not None:
        query = query.where(Bill.printed == printed)
        count_query = count_query.where(Bill.printed == printed)
    total = (await session.execute(count_query)).scalar_one()
    items = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    return BillListResponse(
        items=[BillOut.model_validate(b) for b in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{bill_id}", response_model=BillOut)
async def get_bill(
    bill_id: int,
    session: AsyncSession = Depends(get_db),
) -> BillOut:
    bill = await session.get(Bill, bill_id)
    if not bill:
        raise NotFoundError(f"Bill #{bill_id} not found")
    return BillOut.model_validate(bill)


@router.patch("/{bill_id}/payment", response_model=BillOut)
async def update_payment_info(
    bill_id: int,
    payload: BillPaymentUpdate,
    session: AsyncSession = Depends(get_db),
) -> BillOut:
    bill = await session.get(Bill, bill_id)
    if not bill:
        raise NotFoundError(f"Bill #{bill_id} not found")
    bill.account_holder = payload.account_holder
    bill.bank_name = payload.bank_name
    bill.account_number = payload.account_number
    bill.ifsc_code = payload.ifsc_code
    await session.commit()
    await db_log("INFO", f"Payment info updated for bill #{bill_id}")
    return BillOut.model_validate(bill)
