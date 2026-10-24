"""Application configuration and settings management using Pydantic Settings."""
from typing import List, Union, Optional, Any
from pydantic import field_validator, model_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, make_url
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Application Settings
    APP_ENV: str = Field(default="development", description="Application runtime environment")
    APP_HOST: str = Field(default="127.0.0.1", description="Application bind host")
    APP_PORT: int = Field(default=8000, description="Application bind port")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Security & CORS
    CORS_ORIGINS: Union[List[str], str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        description="Allowed CORS origin hosts"
    )
    AUTH_REQUIRED: bool = Field(default=False, description="Whether authentication is strictly enforced")
    SECRET_KEY: str = Field(..., description="Cryptographic secret key for token validation")

    # PostgreSQL Credentials & Configuration (Strictly Environment-Driven)
    POSTGRES_USER: str = Field(..., description="PostgreSQL database user")
    POSTGRES_PASSWORD: str = Field(..., description="PostgreSQL database password")
    POSTGRES_DB: str = Field(..., description="PostgreSQL database name")
    POSTGRES_TEST_USER: Optional[str] = Field(default="genius_test", description="Dedicated PostgreSQL test user role")
    POSTGRES_TEST_PASSWORD: Optional[str] = Field(default=None, description="Dedicated PostgreSQL test user password")
    POSTGRES_TEST_DB: str = Field(default="genius_ai_test", description="Dedicated PostgreSQL test database name")
    POSTGRES_HOST: str = Field(default="localhost", description="PostgreSQL host (localhost or docker postgres service)")
    POSTGRES_PORT: int = Field(default=5433, description="PostgreSQL port (5433 local mapped, 5432 container internal)")
    DATABASE_URL: Optional[str] = Field(default=None, description="Constructed or explicitly provided database URL")
    DATABASE_URL_TEST: Optional[str] = Field(default=None, description="Constructed or explicitly provided test database URL")

    # LLM Provider Configuration (OpenRouter / Ollama)
    LLM_PROVIDER: str = Field(default="openrouter", description="Active AI provider: 'openrouter' or 'ollama'")
    OPENROUTER_API_KEY: Optional[str] = Field(default=None, description="OpenRouter API Key")
    OPENROUTER_MODEL: str = Field(default="nvidia/nemotron-3.5-lightning:free", description="OpenRouter free model identifier")
    OPENROUTER_BASE_URL: str = Field(default="https://openrouter.ai/api/v1", description="OpenRouter API base URL")

    # Local Ollama AI Settings (Alternative local provider)
    OLLAMA_BASE_URL: str = Field(default="http://127.0.0.1:11434")
    OLLAMA_CHAT_MODEL: str = Field(default="llama3.2")
    OLLAMA_TIMEOUT_SECONDS: int = Field(default=30)
    OLLAMA_MAX_ITERATIONS: int = Field(default=5)

    # Local Speech-to-Text Settings
    STT_BACKEND: str = Field(default="faster-whisper")
    STT_MODEL_SIZE: str = Field(default="base")
    STT_DEVICE: str = Field(default="cpu")
    STT_COMPUTE_TYPE: str = Field(default="int8")
    STT_MAX_UPLOAD_BYTES: int = Field(default=10 * 1024 * 1024)  # 10 MB
    STT_MAX_DURATION_SECONDS: int = Field(default=120)
    STT_MAX_CONCURRENT_JOBS: int = Field(default=2)

    # IPL ML Model Artifact & Trusted Trust Anchor
    IPL_MODEL_PATH: str = Field(default="pipe.pkl")
    IPL_MODEL_TRUSTED_SHA256: str = Field(
        default="011445c41ac5de9072cca85cb821e880b5bd91622964842dae538b6a2c82d1d4",
        description="Cryptographic trust anchor for pipe.pkl artifact verification"
    )

    @field_validator("IPL_MODEL_TRUSTED_SHA256", mode="before")
    @classmethod
    def validate_trusted_sha256(cls, v: Any) -> str:
        """Enforces that the trusted SHA-256 anchor cannot be empty, null, or malformed."""
        if not v or not isinstance(v, str):
            raise ValueError("IPL_MODEL_TRUSTED_SHA256 is required and cannot be empty.")
        clean = v.strip().lower()
        if len(clean) != 64 or not all(c in "0123456789abcdef" for c in clean):
            raise ValueError("IPL_MODEL_TRUSTED_SHA256 must be a valid 64-character hexadecimal SHA-256 string.")
        return clean

    @field_validator("OPENROUTER_MODEL", mode="before")
    @classmethod
    def validate_openrouter_free_model(cls, v: Any) -> str:
        """Enforces using exclusively free models on OpenRouter.
        Strictly rejects non-free model selections at startup rather than mutating them.
        """
        if not v or not isinstance(v, str) or not v.strip():
            return "nvidia/nemotron-3.5-lightning:free"
        clean = v.strip()
        if not clean.endswith(":free"):
            raise ValueError(
                f"Invalid OpenRouter model '{clean}'. Only free-tier models ending with ':free' "
                f"are permitted (e.g. 'nvidia/nemotron-3.5-lightning:free'). Non-free models are rejected at startup."
            )
        return clean

    @field_validator("SECRET_KEY", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", mode="before")
    @classmethod
    def validate_non_empty_secret(cls, v: Any, info) -> str:
        """Enforces that required credentials cannot be empty, whitespace, or null."""
        if v is None:
            raise ValueError(f"'{info.field_name}' is required and cannot be None.")
        if not isinstance(v, str):
            v = str(v)
        stripped = v.strip()
        if not stripped:
            raise ValueError(f"'{info.field_name}' is required and cannot be empty or whitespace.")
        return stripped

    @field_validator("POSTGRES_TEST_PASSWORD", mode="before")
    @classmethod
    def validate_optional_test_password(cls, v: Any) -> Optional[str]:
        """Ensures that if POSTGRES_TEST_PASSWORD is provided, it is not blank whitespace."""
        if v is None:
            return None
        if not isinstance(v, str):
            v = str(v)
        stripped = v.strip()
        if not stripped:
            return None
        return stripped

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def assemble_and_validate(self) -> "Settings":
        """Constructs database URLs safely and executes fail-fast security validation."""
        # 1. Safely construct or validate DATABASE_URL (exact postgresql+asyncpg driver required)
        if not self.DATABASE_URL or not self.DATABASE_URL.strip():
            # Safely encode credentials using SQLAlchemy's URL.create to prevent URL injection/parsing issues
            url_obj = URL.create(
                drivername="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                database=self.POSTGRES_DB,
            )
            self.DATABASE_URL = url_obj.render_as_string(hide_password=False)
        else:
            try:
                parsed = make_url(self.DATABASE_URL)
                if not parsed.drivername:
                    raise ValueError("DATABASE_URL missing driver protocol.")
                if parsed.drivername != "postgresql+asyncpg":
                    raise ValueError(
                        f"Unsupported database driver '{parsed.drivername}'. Genius AI Assistant requires exact 'postgresql+asyncpg' driver (postgresql+asyncpg://...)."
                    )
            except Exception as e:
                if "Unsupported database driver" in str(e):
                    raise
                raise ValueError("Invalid DATABASE_URL format provided.") from None

        # 2. Safely construct or validate DATABASE_URL_TEST (dedicated test database)
        if self.is_production:
            self.DATABASE_URL_TEST = None
        else:
            if not self.DATABASE_URL_TEST or not self.DATABASE_URL_TEST.strip():
                test_user = self.POSTGRES_TEST_USER or self.POSTGRES_USER
                test_password = self.POSTGRES_TEST_PASSWORD or self.POSTGRES_PASSWORD
                test_url_obj = URL.create(
                    drivername="postgresql+asyncpg",
                    username=test_user,
                    password=test_password,
                    host=self.POSTGRES_HOST,
                    port=self.POSTGRES_PORT,
                    database=self.POSTGRES_TEST_DB,
                )
                self.DATABASE_URL_TEST = test_url_obj.render_as_string(hide_password=False)
            else:
                try:
                    parsed_test = make_url(self.DATABASE_URL_TEST)
                    if not parsed_test.drivername:
                        raise ValueError("DATABASE_URL_TEST missing driver protocol.")
                    if parsed_test.drivername != "postgresql+asyncpg":
                        raise ValueError(
                            f"Unsupported test database driver '{parsed_test.drivername}'. Genius AI Assistant requires exact 'postgresql+asyncpg' driver."
                        )
                except Exception as e:
                    if "Unsupported test database driver" in str(e):
                        raise
                    raise ValueError("Invalid DATABASE_URL_TEST format provided.") from None

            # 3. Test Database Isolation & Safety Guards
            parsed_main = make_url(self.DATABASE_URL)
            parsed_test = make_url(self.DATABASE_URL_TEST)

            if parsed_test.database == parsed_main.database:
                raise ValueError(
                    f"Unsafe test database configuration: DATABASE_URL_TEST targets the primary application database '{parsed_main.database}'. "
                    "Tests must run against a distinct dedicated test database (e.g. 'genius_ai_test')."
                )

            if "test" not in (parsed_test.database or "").lower():
                raise ValueError(
                    f"Unsafe test database name '{parsed_test.database}'. Test database name must contain 'test' to guarantee isolation."
                )

            # Safety Guard: Ensure test database host is strictly a local loopback or safe container host
            SAFE_TEST_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres", "host.docker.internal"}
            test_host = (parsed_test.host or "").lower()
            if test_host not in SAFE_TEST_HOSTS:
                raise ValueError(
                    f"Unsafe test database host '{test_host}'. Integration tests must run strictly against local loopback or container networks ({', '.join(sorted(SAFE_TEST_HOSTS))})."
                )

        # 4. Enforce fail-fast security profile checks
        self.validate_security_profile()
        return self

    @property
    def masked_database_url(self) -> str:
        """Returns database URL with password safely masked for logging or diagnostics."""
        try:
            return make_url(self.DATABASE_URL).render_as_string(hide_password=True)
        except Exception:
            return "postgresql+asyncpg://***"

    @property
    def masked_test_database_url(self) -> str:
        """Returns test database URL with password safely masked for logging or diagnostics."""
        try:
            if not self.DATABASE_URL_TEST:
                return "None"
            return make_url(self.DATABASE_URL_TEST).render_as_string(hide_password=True)
        except Exception:
            return "postgresql+asyncpg://***"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() in ("production", "prod")

    def validate_security_profile(self) -> None:
        """Enforces Profile B (Public/Production) security constraints."""
        if self.is_production:
            if not self.AUTH_REQUIRED:
                raise ValueError("Security Profile B Violation: AUTH_REQUIRED must be True in production environments.")
            if not self.SECRET_KEY or self.SECRET_KEY in (
                "dev-secret-key-change-in-production",
                "change-this-to-a-secure-random-secret-key-in-production"
            ):
                raise ValueError("Security Profile B Violation: Insecure default SECRET_KEY detected in production.")
            if len(self.SECRET_KEY) < 32:
                raise ValueError("Security Profile B Violation: SECRET_KEY must be at least 32 characters in production.")

            if any("*" in origin for origin in self.CORS_ORIGINS):
                raise ValueError("Security Profile B Violation: Wildcard CORS origins are forbidden in production.")

    def __repr__(self) -> str:
        fields = []
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            if k in ("SECRET_KEY", "POSTGRES_PASSWORD", "POSTGRES_TEST_PASSWORD", "OPENROUTER_API_KEY"):
                fields.append(f"{k}='**********'")
            elif k == "DATABASE_URL":
                fields.append(f"{k}='{self.masked_database_url}'")
            elif k == "DATABASE_URL_TEST":
                fields.append(f"{k}='{self.masked_test_database_url}'")
            else:
                fields.append(f"{k}={v!r}")
        return f"{self.__class__.__name__}({', '.join(fields)})"

    def __str__(self) -> str:
        return self.__repr__()

settings = Settings()

