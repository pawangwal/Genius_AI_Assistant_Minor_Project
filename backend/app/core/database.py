"""Database engine, async session factory, and connectivity probes."""
from typing import AsyncGenerator, Tuple
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from backend.app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Base model for SQLAlchemy ORM
Base = declarative_base()

# Async database engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def check_database_health() -> Tuple[bool, str]:
    """Performs an explicit active probe against PostgreSQL and verifies schema readiness.
    
    Returns:
        (True, "connected") if healthy and required tables exist.
        (False, error_message) if unreachable or schema tables are missing.
    """
    try:
        async with engine.connect() as conn:
            # 1. Connectivity check
            result = await conn.execute(text("SELECT 1"))
            if result.scalar() != 1:
                return False, "Unexpected database ping response."

            # 2. Schema readiness verification
            def _check_tables(sync_conn):
                from sqlalchemy import inspect
                inspector = inspect(sync_conn)
                tables = set(inspector.get_table_names())
                required = {"users", "tasks", "reminders"}
                missing = required - tables
                return missing

            missing_tables = await conn.run_sync(_check_tables)
            if missing_tables:
                return False, f"Uninitialized schema (missing tables: {', '.join(sorted(missing_tables))}). Run alembic upgrade head."

            return True, "connected"
    except Exception as e:
        error_name = type(e).__name__
        logger.warning(f"Database health probe failed: {error_name}")
        return False, f"{error_name}: connection failed or database unreachable"

