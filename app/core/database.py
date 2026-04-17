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
#   - Short timeouts so a dead TCP connection fails fast instead of hanging.
#
# Note: do NOT pass server_settings (e.g. jit=off) here — pgbouncer only
# allows a small whitelist of startup parameters and rejects the connection
# otherwise ("unsupported startup parameter"). Set such tuning via
# ALTER ROLE / ALTER DATABASE in Postgres directly if needed.
#
# Alembic migrations should use the direct connection (port 5432), NOT this
# pooler — pgbouncer doesn't support advisory locks used by migrations.
# Pool sizing:
#   - pool_size=5, max_overflow=15 → up to 20 concurrent DB connections per
#     Cloud Run instance. Background tasks (Excel/audio upload processing)
#     can hold a connection for minutes while calling OpenAI, so we need
#     headroom above pool_size for concurrent web requests.
#   - pool_pre_ping is intentionally OFF. With pgbouncer transaction mode the
#     pre-ping lands on a different backend than the real query, adding an
#     extra network round-trip per checkout without actually validating
#     anything. pool_recycle handles staleness instead.
#   - pool_recycle=600 (10 min) is well below pgbouncer's idle timeout so we
#     recycle proactively and avoid picking up a server-closed connection.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=15,
    pool_timeout=10,
    pool_recycle=600,
    pool_pre_ping=False,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "timeout": 10,
        "command_timeout": 30,
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
