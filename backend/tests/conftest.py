"""Pytest configuration and async test fixtures for the Genius AI backend.
Standardized exclusively on PostgreSQL (asyncpg) with isolated session fixtures and dedicated test database.
Zero SQLite, zero create_all fallback, zero development database truncation.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text, make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from backend.app.main import app
from backend.app.ml.ipl_pipeline import ipl_service
from backend.app.core.config import settings
from backend.app.core.database import get_db

# Enforce PostgreSQL test engine; fallback or SQLite is strictly prohibited
if settings.is_production:
    raise RuntimeError(
        "FATAL SECURITY VIOLATION: Test suite execution is strictly forbidden in production environments (APP_ENV=production). "
        "Refusing to execute tests against a production profile."
    )

if not settings.DATABASE_URL_TEST:
    raise RuntimeError("PostgreSQL integration testing requires settings.DATABASE_URL_TEST to be configured.")

parsed_test = make_url(settings.DATABASE_URL_TEST)
parsed_main = make_url(settings.DATABASE_URL)

if parsed_test.drivername != "postgresql+asyncpg":
    raise RuntimeError(
        f"PostgreSQL integration testing requires exact 'postgresql+asyncpg' driver. "
        f"Found: {parsed_test.drivername}"
    )

if parsed_test.database == parsed_main.database:
    raise RuntimeError(
        f"FATAL SAFETY VIOLATION: Test database '{parsed_test.database}' cannot target the primary application database '{parsed_main.database}'."
    )

if "test" not in (parsed_test.database or "").lower():
    raise RuntimeError(
        f"FATAL SAFETY VIOLATION: Test database name '{parsed_test.database}' must contain 'test' to guarantee isolation."
    )

test_engine = create_async_engine(
    settings.DATABASE_URL_TEST,
    echo=False,
    poolclass=NullPool
)

@pytest.fixture(scope="session", autouse=True)
def apply_test_database_migrations():
    """Applies Alembic migrations against the dedicated PostgreSQL test database.
    Integration tests execute strictly against migration-verified schema,
    never calling Base.metadata.create_all().
    """
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL_TEST)
    command.upgrade(alembic_cfg, "head")

@pytest_asyncio.fixture
async def async_client():
    """Provides an asynchronous HTTP test client bound to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

@pytest_asyncio.fixture
async def test_db():
    """Provides an isolated PostgreSQL async database session.
    Guarantees deterministic test isolation by truncating tables before and after execution.
    Strictly verifies that the target is the isolated test database before issuing TRUNCATE.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        # Runtime database identity check
        db_name = (await session.execute(text("SELECT current_database();"))).scalar()
        if "test" not in db_name.lower() or db_name == make_url(settings.DATABASE_URL).database:
            raise RuntimeError(f"FATAL SAFETY PREVENTED: Attempted to truncate non-test database: {db_name}")

        # Clean state prior to test execution
        await session.execute(text("TRUNCATE TABLE tasks, reminders, users RESTART IDENTITY CASCADE;"))
        await session.commit()
        try:
            yield session
        finally:
            try:
                await session.rollback()
                await session.execute(text("TRUNCATE TABLE tasks, reminders, users RESTART IDENTITY CASCADE;"))
                await session.commit()
            except Exception:
                pass

@pytest_asyncio.fixture
async def test_db_session(test_db):
    """Alias for test_db providing compatibility with persistence test suites."""
    yield test_db

@pytest_asyncio.fixture
async def client_with_db(test_db):
    """Provides test client overriding get_db dependency with the isolated PostgreSQL test database session."""
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def ensure_model_loaded():
    """Ensures the IPL ML model is loaded for unit and integration tests."""
    if not ipl_service.is_ready:
        ipl_service.load()
