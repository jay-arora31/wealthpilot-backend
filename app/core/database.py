import logging
from typing import AsyncGenerator

import logfire
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

# Supabase's PgBouncer pooler (port 6543) is required for serverless/Cloud Run
# deployments — direct connections (port 5432) get exhausted quickly.
# We also cap the SQLAlchemy pool small: Cloud Run may spin up many instances,
# each holding `pool_size` connections, so keep it low.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=2,
    max_overflow=3,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

try:
    logfire.instrument_sqlalchemy(engine=engine)
except Exception as exc:
    logger.warning("logfire SQLAlchemy instrumentation failed: %s", exc)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
