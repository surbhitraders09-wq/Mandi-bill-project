"""
Centralised logging service with database persistence.
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.log import Log


async def log(
    level: str,
    message: str,
    details: Optional[Any] = None,
    session: Optional[AsyncSession] = None,
) -> Log:
    entry = Log(level=level.upper(), message=message, details=details)

    if session is not None:
        session.add(entry)
        await session.flush()
    else:
        async with async_session_factory() as new_session:
            new_session.add(entry)
            await new_session.commit()
            entry_id = entry.id

    return entry


async def get_logs(
    level: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    async with async_session_factory() as session:
        query = select(Log).order_by(Log.created_at.desc())
        count_query = select(func.count(Log.id))

        if level:
            query = query.where(Log.level == level.upper())
            count_query = count_query.where(Log.level == level.upper())

        total_result = await session.execute(count_query)
        total: int = total_result.scalar_one()

        result = await session.execute(query.limit(limit).offset(offset))
        items: List[Log] = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }


async def clear_logs() -> int:
    async with async_session_factory() as session:
        result = await session.execute(delete(Log))
        await session.commit()
        return result.rowcount


@asynccontextmanager
async def operation_log(
    level: str,
    operation_name: str,
    details: Optional[Any] = None,
) -> AsyncIterator[None]:
    await log(level, f"{operation_name} — started", details)
    try:
        yield
        await log(level, f"{operation_name} — completed", details)
    except Exception as exc:
        await log("ERROR", f"{operation_name} — failed: {exc}", {
            "details": details,
            "error": str(exc),
        })
        raise
