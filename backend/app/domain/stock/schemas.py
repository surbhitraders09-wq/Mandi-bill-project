from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StockRow(BaseModel):
    commodity_id: int
    commodity_name: str
    segment: str
    qty: float = Field(description="Total weight in kg")
    avg_rate: Optional[float] = Field(None, description="Weighted average rate ₹/qtl, null if no bill has a rate")
    value: float = Field(description="Total gross amount ₹")
    bill_count: int
    last_date: Optional[date]


class StockTotals(BaseModel):
    commodities: int
    rows: int
    qty: float
    value: float
    avg_rate: Optional[float]


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rows: list[StockRow]
    totals: StockTotals


class TraderStockRow(BaseModel):
    trader_id: int
    trader_name: str
    commodity_id: int
    commodity_name: str
    qty: float
    avg_rate: Optional[float]
    value: float
    bill_count: int
    last_date: Optional[date]


class TraderStockResponse(BaseModel):
    rows: list[TraderStockRow]
    totals: StockTotals


class StockTrendPoint(BaseModel):
    date: str
    qty: float = Field(description="Total weight in kg")
    value: float = Field(description="Total gross amount ₹")


class StockAnalytics(BaseModel):
    daily: list[StockTrendPoint]
    by_segment: list[dict]
    by_commodity: list[dict]
    top_commodity: Optional[str]
    total_value: float
    total_qty: float
