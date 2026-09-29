from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.rbac import require_permission
from app.database import get_db
from app.domain.stock import service
from app.domain.stock.schemas import (
    StockAnalytics,
    StockResponse,
    TraderStockResponse,
)

router = APIRouter(prefix="/api/v1/stock", tags=["stock"])


@router.get("", response_model=StockResponse)
async def list_stock(
    q: Optional[str] = Query(None),
    commodity_id: Optional[int] = Query(None),
    segment: Optional[str] = Query(None, pattern="^(trader|government)$"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("stock:read")),
):
    await record_audit("READ", "stock", "aggregate", actor=user["username"], request=request)
    return await service.get_stock(
        session, q=q, commodity_id=commodity_id, segment=segment,
        date_from=date_from, date_to=date_to,
    )


@router.get("/analytics", response_model=StockAnalytics)
async def get_analytics(
    days: int = Query(30, ge=1, le=365),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("stock:read")),
):
    await record_audit("READ", "stock", "analytics", actor=user["username"], request=request)
    return await service.get_stock_analytics(session, days=days)


@router.get("/traders/{trader_id}", response_model=TraderStockResponse)
async def get_trader_stock(
    trader_id: int,
    q: Optional[str] = Query(None),
    commodity_id: Optional[int] = Query(None),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("stock:read")),
):
    await record_audit("READ", "stock", f"trader:{trader_id}", actor=user["username"], request=request)
    return await service.get_trader_stock(session, trader_id, q=q, commodity_id=commodity_id)
