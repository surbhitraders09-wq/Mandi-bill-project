"""
Pure aggregation helpers for the mobile Summary feature.

No I/O here — these take parsed bills / fees / stock rows and produce the
grouped numbers the mobile page renders. Unit-testable without a browser.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

SOYABEAN_KEYWORDS = ("सोयाबीन", "soyabean", "soybean", "सोयाबिन")


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (ValueError, TypeError):
        return 0.0


def is_soyabean(commodity: str) -> bool:
    return any(kw in (commodity or "").lower() for kw in SOYABEAN_KEYWORDS)


def group_crops(bills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group parsed bills by commodity → weight/amount/avg_rate."""
    weight_by = defaultdict(float)
    amount_by = defaultdict(float)
    for b in bills:
        comm = (b.get("commodity") or "").strip() or "(अन्य)"
        weight_by[comm] += _num(b.get("weight"))
        amount_by[comm] += _num(b.get("gross_amount")) or _num(b.get("weight")) * _num(b.get("rate"))
    crops = []
    for comm in sorted(weight_by):
        weight = round(weight_by[comm], 3)
        amount = round(amount_by[comm], 2)
        crops.append({
            "commodity": comm,
            "total_weight": weight,
            "total_amount": amount,
            "avg_rate": round(amount / weight, 2) if weight > 0 else 0.0,
        })
    return crops


def group_daily(bills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group parsed bills by auction_date → weight/bill_count."""
    weight_by = defaultdict(float)
    count_by = defaultdict(int)
    for b in bills:
        d = (b.get("auction_date") or "").strip() or "(कोई तारीख नहीं)"
        weight_by[d] += _num(b.get("weight"))
        count_by[d] += 1
    daily = []
    for d in sorted(weight_by):
        daily.append({
            "date": d,
            "total_weight": round(weight_by[d], 3),
            "bill_count": count_by[d],
        })
    return daily


def soyabean_row(crops: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find the soyabean crop row (flagged) if present."""
    for c in crops:
        if is_soyabean(c.get("commodity", "")):
            return c
    return None


def base_crop(commodity: str) -> str:
    """Normalize a crop name so the trend lines group cleanly.

    Portal names come in two forms:
      - crop-wise report: "सोयाबीन/Yellow", "चना/चना" (variety after '/')
      - stock/group form: "ग्रुप - फसल" or "सोयाबीन - सोयाबीन"

    We strip the variety ('/...') and any " - " group prefix so
    "सोयाबीन/Yellow" and "सोयाबीन" are treated as the same crop.
    """
    name = (commodity or "").strip()
    if "/" in name:
        name = name.split("/", 1)[0].strip()
    if " - " in name:
        name = name.split(" - ", 1)[-1].strip()
    return name


def _cumulative_to_daily(cumulative_runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert cumulative crop-wise runs to per-day totals.

    The crop-wise report (RPT_BhugtanPatrak_CropwiseTD.aspx) returns
    cumulative data from From_Date to today. To get per-day data,
    subtract consecutive runs: day_i = cumulative(i) - cumulative(i+1).

    The oldest run is treated as its own per-day total (nothing before it).
    Returns runs in the same format as input, but with per-day values.
    """
    if not cumulative_runs:
        return []

    daily: List[Dict[str, Any]] = []
    for i, run in enumerate(cumulative_runs):
        day = run.get("date")
        crops_now = run.get("crops") or []

        if i < len(cumulative_runs) - 1:
            # Subtract next (newer) cumulative from this one
            next_crops = cumulative_runs[i + 1].get("crops") or []
            next_by_comm = {
                base_crop(c.get("commodity", "")): c for c in next_crops
            }
            day_crops = []
            for c in crops_now:
                comm = c.get("commodity", "")
                base = base_crop(comm)
                weight = _num(c.get("total_weight"))
                amount = _num(c.get("total_amount"))
                nxt = next_by_comm.get(base)
                if nxt:
                    weight -= _num(nxt.get("total_weight"))
                    amount -= _num(nxt.get("total_amount"))
                if weight > 0 and amount > 0:
                    day_crops.append({
                        "commodity": comm,
                        "total_weight": round(weight, 3),
                        "total_amount": round(amount, 2),
                        "avg_rate": round(amount / weight, 2),
                    })
        else:
            # Oldest day — cumulative IS the per-day total
            day_crops = [
                c for c in crops_now
                if _num(c.get("total_weight")) > 0
            ]

        daily.append({"date": day, "crops": day_crops})
    return daily


def build_price_trend(daily_runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build per-day average rates from daily runs.

    Each run is ``{"date": ..., "crops": [{commodity, total_weight,
    total_amount, avg_rate}]}`` where the crops are already the *per-day* totals.

    Returns oldest→newest points: ``[{date, rates: {crop: avg_rate}}]``.
    A day with no data at all is omitted (chart gap).
    """
    points: List[Dict[str, Any]] = []
    for run in daily_runs:
        if not isinstance(run, dict):
            continue
        day = run.get("date")
        if day is None:
            continue
        rates: Dict[str, float] = {}
        for c in run.get("crops") or []:
            name = base_crop(c.get("commodity", ""))
            if not name:
                continue
            rate = _num(c.get("avg_rate"))
            if rate > 0:
                rates[name] = round(rate, 2)
        if rates:
            points.append({"date": day, "rates": rates})
    return points


def build_crop_trends(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Summarize each crop's rise/fall across the price-trend points.

    For every crop that appears, take the first and last available rate
    (>= 0.5% change counts as up/down, otherwise flat).
    """
    if not points:
        return []
    first_rates = points[0].get("rates") or {}
    last_rates = points[-1].get("rates") or {}
    crops = sorted(set(first_rates) | set(last_rates))
    trends: List[Dict[str, Any]] = []
    for crop in crops:
        start = _num(first_rates.get(crop))
        end = _num(last_rates.get(crop))
        change_pct = 0.0
        direction = "flat"
        if start > 0:
            change_pct = round((end - start) / start * 100, 2)
            if change_pct > 0.5:
                direction = "up"
            elif change_pct < -0.5:
                direction = "down"
        trends.append({
            "commodity": crop,
            "start_rate": round(start, 2),
            "end_rate": round(end, 2),
            "change_pct": change_pct,
            "direction": direction,
        })
    return trends
