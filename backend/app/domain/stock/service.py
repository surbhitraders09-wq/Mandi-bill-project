from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.stock.schemas import (
    StockAnalytics,
    StockResponse,
    StockRow,
    StockTotals,
    TraderStockResponse,
    TraderStockRow,
)
from app.models.bill import Bill
from app.models.commodity import Commodity


def _filters(
    q: Optional[str] = None,
    commodity_id: Optional[int] = None,
    segment: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    conds = []
    if commodity_id is not None:
        conds.append(Bill.commodity_id == commodity_id)
    if segment:
        conds.append(Bill.segment == segment)
    if date_from:
        conds.append(func.date(Bill.created_at) >= date_from.isoformat())
    if date_to:
        conds.append(func.date(Bill.created_at) <= date_to.isoformat())
    return conds


async def get_stock(
    db: AsyncSession,
    q: Optional[str] = None,
    commodity_id: Optional[int] = None,
    segment: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> StockResponse:
    conds = _filters(q, commodity_id, segment, date_from, date_to)
    if q:
        conds.append(Commodity.name.ilike(f"%{q}%"))
    rows_stmt = (
        select(
            Commodity.id.label("commodity_id"),
            Commodity.name.label("commodity_name"),
            Bill.segment.label("segment"),
            func.sum(Bill.weight).label("qty"),
            func.sum(Bill.gross_amount).label("value"),
            func.count(Bill.id).label("bill_count"),
            func.max(func.date(Bill.created_at)).label("last_date"),
        )
        .join(Bill, Bill.commodity_id == Commodity.id)
        .where(and_(*conds))
        .group_by(Commodity.id, Commodity.name, Bill.segment)
        .order_by(func.sum(Bill.gross_amount).desc())
    )
    rows = (await db.execute(rows_stmt)).all()
    result_rows: list[StockRow] = []
    for r in rows:
        avg = None
        if r.qty:
            avg = (r.value * 100.0) / r.qty
        result_rows.append(
            StockRow(
                commodity_id=r.commodity_id,
                commodity_name=r.commodity_name,
                segment=r.segment,
                qty=float(r.qty or 0),
                avg_rate=round(avg, 2) if avg is not None else None,
                value=float(r.value or 0),
                bill_count=r.bill_count,
                last_date=r.last_date,
            )
        )
    totals = StockTotals(
        commodities=len({r.commodity_id for r in result_rows}),
        rows=len(result_rows),
        qty=round(sum(r.qty for r in result_rows), 2),
        value=round(sum(r.value for r in result_rows), 2),
        avg_rate=round((sum(r.value for r in result_rows) * 100.0) / sum(r.qty for r in result_rows), 2)
        if sum(r.qty for r in result_rows)
        else None,
    )
    return StockResponse(rows=result_rows, totals=totals)


async def get_trader_stock(
    db: AsyncSession,
    trader_id: int,
    q: Optional[str] = None,
    commodity_id: Optional[int] = None,
) -> TraderStockResponse:
    from app.models.trader import Trader

    conds = [Bill.segment == "trader", Bill.farmer_id == trader_id]
    if commodity_id is not None:
        conds.append(Bill.commodity_id == commodity_id)
    if q:
        conds.append(Commodity.name.ilike(f"%{q}%"))
    rows_stmt = (
        select(
            Trader.id.label("trader_id"),
            Trader.name.label("trader_name"),
            Commodity.id.label("commodity_id"),
            Commodity.name.label("commodity_name"),
            func.sum(Bill.weight).label("qty"),
            func.sum(Bill.gross_amount).label("value"),
            func.count(Bill.id).label("bill_count"),
            func.max(func.date(Bill.created_at)).label("last_date"),
        )
        .select_from(Bill)
        .join(Trader, Trader.id == Bill.farmer_id)
        .join(Commodity, Commodity.id == Bill.commodity_id)
        .where(and_(*conds))
        .group_by(Trader.id, Trader.name, Commodity.id, Commodity.name)
        .order_by(func.sum(Bill.gross_amount).desc())
    )
    rows = (await db.execute(rows_stmt)).all()
    result_rows: list[TraderStockRow] = []
    for r in rows:
        avg = None
        if r.qty:
            avg = (r.value * 100.0) / r.qty
        result_rows.append(
            TraderStockRow(
                trader_id=r.trader_id,
                trader_name=r.trader_name,
                commodity_id=r.commodity_id,
                commodity_name=r.commodity_name,
                qty=float(r.qty or 0),
                avg_rate=round(avg, 2) if avg is not None else None,
                value=float(r.value or 0),
                bill_count=r.bill_count,
                last_date=r.last_date,
            )
        )
    totals = StockTotals(
        commodities=len({r.commodity_id for r in result_rows}),
        rows=len(result_rows),
        qty=round(sum(r.qty for r in result_rows), 2),
        value=round(sum(r.value for r in result_rows), 2),
        avg_rate=round((sum(r.value for r in result_rows) * 100.0) / sum(r.qty for r in result_rows), 2)
        if sum(r.qty for r in result_rows)
        else None,
    )
    return TraderStockResponse(rows=result_rows, totals=totals)


async def get_stock_analytics(
    db: AsyncSession,
    days: int = 30,
) -> StockAnalytics:
    since = datetime.utcnow().date() - timedelta(days=days)
    conds = [func.date(Bill.created_at) >= since.isoformat(), Bill.commodity_id.is_not(None)]
    by_segment_stmt = (
        select(
            Bill.segment.label("segment"),
            func.sum(Bill.weight).label("qty"),
            func.sum(Bill.gross_amount).label("value"),
            func.count(Bill.id).label("bills"),
        )
        .where(and_(*conds))
        .group_by(Bill.segment)
        .order_by(func.sum(Bill.gross_amount).desc())
    )
    by_segment = [
        {
            "name": r.segment,
            "qty": float(r.qty or 0),
            "value": float(r.value or 0),
            "bills": r.bills,
        }
        for r in (await db.execute(by_segment_stmt)).all()
    ]
    by_commodity_stmt = (
        select(
            Commodity.name.label("name"),
            func.sum(Bill.weight).label("qty"),
            func.sum(Bill.gross_amount).label("value"),
        )
        .join(Bill, Bill.commodity_id == Commodity.id)
        .where(and_(*conds))
        .group_by(Commodity.id, Commodity.name)
        .order_by(func.sum(Bill.gross_amount).desc())
    )
    by_commodity = [
        {
            "name": r.name,
            "qty": float(r.qty or 0),
            "value": float(r.value or 0),
        }
        for r in (await db.execute(by_commodity_stmt)).all()
    ]
    total_value = round(sum(b["value"] for b in by_segment), 2)
    total_qty = round(sum(b["qty"] for b in by_segment), 2)
    daily_stmt = (
        select(
            func.date(Bill.created_at).label("day"),
            func.sum(Bill.weight).label("qty"),
            func.sum(Bill.gross_amount).label("value"),
        )
        .where(and_(*conds))
        .group_by(func.date(Bill.created_at))
        .order_by(func.date(Bill.created_at))
    )
    daily = [
        {"date": r.day, "qty": float(r.qty or 0), "value": float(r.value or 0)}
        for r in (await db.execute(daily_stmt)).all()
    ]
    return StockAnalytics(
        daily=daily,
        by_segment=by_segment,
        by_commodity=by_commodity,
        top_commodity=by_commodity[0]["name"] if by_commodity else None,
        total_value=total_value,
        total_qty=total_qty,
    )
