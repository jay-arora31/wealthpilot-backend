import logging
from typing import AsyncGenerator

import logfire
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

# Supabase transaction-mode pooler endpoint:
#   postgresql+asyncpg://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres
#
# We use transaction mode because:
#   1. It resolves to IPv4 (the direct db.<ref>.supabase.co host is IPv6-only
#      and fails on most serverless/Cloud Run hosts).
#   2. pgbouncer multiplexes many clients onto few Postgres backends, so we
#      won't exhaust Supabase's connection limit when Cloud Run auto-scales.
#
# Trade-offs handled in connect_args below:
#   - Prepared statements are disabled (statement_cache_size=0) because each
#     transaction may land on a different backend — prepared statements would
#     fail with "prepared statement does not exist".
#   - jit=off removes 100-300ms of planning overhead on small OLTP queries.
#   - Short timeouts so a dead TCP connection fails fast instead of hanging.
#
# Alembic migrations should use the direct connection (port 5432), NOT this
# pooler — pgbouncer doesn't support advisory locks used by migrations.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=5,
    pool_timeout=10,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "timeout": 10,
        "command_timeout": 30,
        "server_settings": {"jit": "off"},
    },
)

try:
    logfire.instrument_sqlalchemy(engine=engine)
except Exception as exc:
    logger.warning("logfire SQLAlchemy instrumentation failed: %s", exc)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
