"""Unit tests for strict environment-based configuration and credentials validation."""
import pytest
from pydantic import ValidationError
from sqlalchemy import make_url
from backend.app.core.config import Settings

VALID_BASE_CONFIG = {
    "SECRET_KEY": "mock_secret_key_minimum_16_chars",
    "POSTGRES_USER": "mock_test_user",
    "POSTGRES_PASSWORD": "mock_test_password_123",
    "POSTGRES_DB": "mock_test_db",
    "POSTGRES_TEST_USER": "mock_test_user_test",
    "POSTGRES_TEST_PASSWORD": "mock_test_password_test",
    "POSTGRES_TEST_DB": "mock_test_db_test",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": 5433,
}


def test_missing_required_secret_key_fails_validation(monkeypatch):
    """Omitting SECRET_KEY must raise ValidationError."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    cfg = VALID_BASE_CONFIG.copy()
    cfg.pop("SECRET_KEY")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **cfg)
    errors = exc_info.value.errors()
    field_names = [e["loc"][0] for e in errors]
    assert "SECRET_KEY" in field_names

def test_missing_required_postgres_credentials_fails_validation(monkeypatch):
    """Omitting any of POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB must raise ValidationError."""
    for required_key in ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"]:
        monkeypatch.delenv(required_key, raising=False)
        cfg = VALID_BASE_CONFIG.copy()
        cfg.pop(required_key)
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None, **cfg)
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert required_key in field_names


def test_empty_string_required_settings_fail_validation():
    """Required fields passed as empty strings or whitespace must fail fast with no secrets leaked."""
    for required_key in ["SECRET_KEY", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"]:
        for bad_value in ["", "   "]:
            cfg = VALID_BASE_CONFIG.copy()
            cfg[required_key] = bad_value
            with pytest.raises(ValidationError) as exc_info:
                Settings(_env_file=None, **cfg)
            err_msg = str(exc_info.value)
            # Verify the required field was flagged
            assert required_key in err_msg
            # Verify secret values are not leaked in error messages
            assert "mock_test_password_123" not in err_msg
            assert "mock_secret_key" not in err_msg

def test_valid_configuration_loads_and_constructs_database_url():
    """Valid configuration loads cleanly and constructs safe asyncpg database URL."""
    s = Settings(_env_file=None, **VALID_BASE_CONFIG)
    assert s.SECRET_KEY == "mock_secret_key_minimum_16_chars"
    assert s.POSTGRES_USER == "mock_test_user"
    assert s.POSTGRES_PASSWORD == "mock_test_password_123"
    assert s.POSTGRES_DB == "mock_test_db"
    assert s.POSTGRES_PORT == 5433
    assert s.POSTGRES_HOST == "localhost"

    # URL must be valid asyncpg connection string
    url = make_url(s.DATABASE_URL)
    assert url.drivername == "postgresql+asyncpg"
    assert url.username == "mock_test_user"
    assert url.password == "mock_test_password_123"
    assert url.host == "localhost"
    assert url.port == 5433
    assert url.database == "mock_test_db"

def test_special_characters_in_postgres_password_are_safely_escaped():
    """Passwords with URL-breaking characters (@, :, /, ?, #, %, &, $, !) must be escaped safely."""
    special_password = "p@ss:w/ord#1?%&!$*()"
    cfg = VALID_BASE_CONFIG.copy()
    cfg["POSTGRES_PASSWORD"] = special_password

    s = Settings(_env_file=None, **cfg)
    # The raw DATABASE_URL string must escape special characters
    assert "%40" in s.DATABASE_URL  # @
    assert "%3A" in s.DATABASE_URL  # :
    assert "%2F" in s.DATABASE_URL  # /
    assert "%23" in s.DATABASE_URL  # #
    assert "%3F" in s.DATABASE_URL  # ?

    # SQLAlchemy make_url should decode it back to the exact original password
    url = make_url(s.DATABASE_URL)
    assert url.password == special_password

def test_secrets_masked_in_repr_and_str():
    """repr(settings) and str(settings) must never print plaintext secrets or unmasked database URL."""
    s = Settings(_env_file=None, **VALID_BASE_CONFIG)
    repr_str = repr(s)
    str_val = str(s)

    for output in [repr_str, str_val]:
        # Plaintext secrets must NEVER appear
        assert "mock_test_password_123" not in output
        assert "mock_secret_key_minimum_16_chars" not in output
        # Masked indicators should be present
        assert "**********" in output or "***" in output


def test_docker_networking_configuration_support():
    """Host and port can be configured for Docker bridge networking (postgres:5432)."""
    cfg = VALID_BASE_CONFIG.copy()
    cfg["POSTGRES_HOST"] = "postgres"
    cfg["POSTGRES_PORT"] = 5432

    s = Settings(_env_file=None, **cfg)
    url = make_url(s.DATABASE_URL)
    assert url.host == "postgres"
    assert url.port == 5432

def test_explicit_database_url_override():
    """Explicit DATABASE_URL override takes precedence if supplied and valid."""
    cfg = VALID_BASE_CONFIG.copy()
    custom_url = "postgresql+asyncpg://custom_u:custom_p@custom_host:5432/custom_db"
    cfg["DATABASE_URL"] = custom_url

    s = Settings(_env_file=None, **cfg)
    assert s.DATABASE_URL == custom_url
    url = make_url(s.DATABASE_URL)
    assert url.username == "custom_u"
    assert url.password == "custom_p"
    assert url.host == "custom_host"

def test_invalid_explicit_database_url_fails():
    """Malformed explicit DATABASE_URL must raise a clear validation error."""
    cfg = VALID_BASE_CONFIG.copy()
    cfg["DATABASE_URL"] = "not-a-valid-database-url"

    with pytest.raises((ValueError, ValidationError)):
        Settings(_env_file=None, **cfg)

def test_non_free_openrouter_model_rejected():
    """Configuring a non-:free OpenRouter model must be strictly rejected at startup with ValidationError."""
    cfg = VALID_BASE_CONFIG.copy()
    cfg["OPENROUTER_MODEL"] = "openai/gpt-4o"

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **cfg)
    assert "Only free-tier models ending with ':free' are permitted" in str(exc_info.value)

def test_non_postgres_database_url_rejected():
    """Configuring a non-PostgreSQL database URL (e.g. SQLite) must be strictly rejected at startup."""
    cfg = VALID_BASE_CONFIG.copy()
    cfg["DATABASE_URL"] = "sqlite+aiosqlite:///local.db"

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **cfg)
    assert "Genius AI Assistant requires exact 'postgresql+asyncpg' driver" in str(exc_info.value)

def test_non_asyncpg_postgres_driver_rejected():
    """Configuring a PostgreSQL URL with a non-asyncpg driver (e.g. psycopg2 or plain postgresql) is rejected."""
    cfg = VALID_BASE_CONFIG.copy()
    for bad_url in [
        "postgresql://genius:password@localhost:5432/genius_ai",
        "postgresql+psycopg2://genius:password@localhost:5432/genius_ai",
        "postgresql+pg8000://genius:password@localhost:5432/genius_ai"
    ]:
        cfg["DATABASE_URL"] = bad_url
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None, **cfg)
        assert "Genius AI Assistant requires exact 'postgresql+asyncpg' driver" in str(exc_info.value)

def test_test_database_targeting_primary_db_rejected():
    """Test database targeting the primary application database must be strictly rejected."""
    cfg = VALID_BASE_CONFIG.copy()
    cfg["DATABASE_URL_TEST"] = f"postgresql+asyncpg://mock_user:mock_pw@localhost:5432/{cfg['POSTGRES_DB']}"

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **cfg)
    assert "DATABASE_URL_TEST targets the primary application database" in str(exc_info.value)

def test_test_database_without_test_in_name_rejected():
    """Test database name must contain 'test' to guarantee isolation."""
    cfg = VALID_BASE_CONFIG.copy()
    cfg["DATABASE_URL_TEST"] = "postgresql+asyncpg://mock_user:mock_pw@localhost:5432/other_production_db"

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **cfg)
    assert "must contain 'test' to guarantee isolation" in str(exc_info.value)

def test_test_database_remote_host_rejected():
    """Test database targeting non-loopback / remote hosts is strictly rejected."""
    cfg = VALID_BASE_CONFIG.copy()
    for remote_host in ["customer-db.internal", "192.168.1.150", "prod-sql.cloud.google.com"]:
        cfg["DATABASE_URL_TEST"] = f"postgresql+asyncpg://mock_user:mock_pw@{remote_host}:5432/genius_test"
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None, **cfg)
        assert "Unsafe test database host" in str(exc_info.value)

def test_test_database_is_none_in_production():
    """In production environments, DATABASE_URL_TEST always evaluates to None to ensure test isolation."""
    cfg = VALID_BASE_CONFIG.copy()
    cfg["APP_ENV"] = "production"
    cfg["AUTH_REQUIRED"] = True
    cfg["SECRET_KEY"] = "secure_production_secret_key_minimum_32_chars_long"
    cfg["DATABASE_URL_TEST"] = "postgresql+asyncpg://genius_test:pw@localhost:5432/genius_ai_test"

    s = Settings(_env_file=None, **cfg)
    assert s.DATABASE_URL_TEST is None


def test_postgres_test_password_has_no_hardcoded_default():
    """POSTGRES_TEST_PASSWORD must default to None rather than a hardcoded string."""
    cfg = VALID_BASE_CONFIG.copy()
    cfg.pop("POSTGRES_TEST_PASSWORD", None)
    s = Settings(_env_file=None, **cfg)
    assert s.POSTGRES_TEST_PASSWORD is None
    # When omitted, DATABASE_URL_TEST cleanly uses POSTGRES_PASSWORD
    assert s.DATABASE_URL_TEST is not None
    parsed = make_url(s.DATABASE_URL_TEST)
    assert parsed.password == cfg["POSTGRES_PASSWORD"]


