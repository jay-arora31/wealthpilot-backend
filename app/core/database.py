import logging
from typing import AsyncGenerator

import logfire
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False)

try:
    logfire.instrument_sqlalchemy(engine=engine)
except Exception as exc:
    logger.warning("logfire SQLAlchemy instrumentation failed: %s", exc)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
