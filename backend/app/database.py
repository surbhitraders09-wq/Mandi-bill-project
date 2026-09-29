"""
SQLAlchemy async database setup with SQLite (aiosqlite).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    async with engine.begin() as conn:
        from app.models import (  # noqa: F401
            activity_log,
            bill,
            commodity,
            farmer,
            log,
            settings as settings_model,
            trader,
            user,
            village,
        )
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_bill_columns(conn)


async def _ensure_bill_columns(conn) -> None:
    """SQLite create_all does not ALTER existing tables; add new Bill columns if missing."""
    rows = (
        await conn.run_sync(
            lambda sync_conn: sync_conn.exec_driver_sql("PRAGMA table_info(bills)").fetchall()
        )
    )
    existing = {row[1] for row in rows}
    additions = {
        "segment": "VARCHAR(20) NOT NULL DEFAULT 'trader'",
        "commodity_id": "INTEGER",
        "farmer_id": "INTEGER",
    }
    for column, ddl in additions.items():
        if column not in existing:
            await conn.run_sync(
                lambda sync_conn, c=column, d=ddl: sync_conn.exec_driver_sql(
                    f"ALTER TABLE bills ADD COLUMN {c} {d}"
                )
            )
