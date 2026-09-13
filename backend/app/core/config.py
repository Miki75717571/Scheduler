"""Settings.

Zero-setup development: every secret and DATABASE_URL has a working default
when APP_ENV=development (the default), so `uv run uvicorn app.main:app`
works with no .env file at all. Dev secrets are generated once and cached in
DEV_DIR / "secrets.json" (gitignored) so restarts don't invalidate sessions.

Production safety: when APP_ENV is anything else, none of that applies - every
secret must be provided explicitly (real env vars, or a real .env), or
get_settings() raises ConfigurationError with a readable list of what's
missing. See _resolve_environment and get_settings below, and
tests/unit/test_config.py, which asserts this.

Path resolution: every path here (.env, the sqlite files, the secrets cache)
is computed from this file's own location, never from the process's current
working directory - a relative path resolves differently depending on
whether you run uvicorn/alembic/pytest from backend/, the repo root, or
anywhere else, which is exactly what caused prior setup failures.
"""

import json
import secrets as secrets_module
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import PrivateAttr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

# backend/app/core/config.py -> core -> app -> backend -> repo root
_THIS_FILE = Path(__file__).resolve()
BACKEND_DIR = _THIS_FILE.parents[2]
REPO_ROOT = BACKEND_DIR.parent
ENV_FILE_PATH = REPO_ROOT / ".env"
DEV_DIR = BACKEND_DIR / ".dev"
DEV_SECRETS_PATH = DEV_DIR / "secrets.json"

# Hosts that never speak TLS in this project's setups (local Postgres, whether
# reached from the host or from another container on the compose network).
_NO_TLS_HOSTS = {None, "localhost", "127.0.0.1", "postgres"}


class ConfigurationError(RuntimeError):
    """Raised instead of a raw pydantic ValidationError so startup failures
    are readable: what's missing, which file was checked, what to do."""


# --- dev-only: sqlite defaults + cached generated secrets ------------------


def _default_sqlite_url(filename: str) -> str:
    DEV_DIR.mkdir(parents=True, exist_ok=True)
    return URL.create("sqlite+aiosqlite", database=str(DEV_DIR / filename)).render_as_string(
        hide_password=False
    )


def _load_dev_secrets() -> dict[str, str]:
    if not DEV_SECRETS_PATH.exists():
        return {}
    try:
        return dict(json.loads(DEV_SECRETS_PATH.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return {}


def _dev_secret(name: str, *, short: bool = False) -> str:
    """Return a cached dev-only secret, generating and persisting one on first
    use so it survives restarts (JWTs signed with a secret that changes every
    restart would invalidate every session immediately).
    """
    cache = _load_dev_secrets()
    if name in cache:
        return cache[name]

    value = secrets_module.token_urlsafe(16 if short else 32)
    cache[name] = value
    DEV_DIR.mkdir(parents=True, exist_ok=True)
    DEV_SECRETS_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    return value


# --- dialect-aware URL helpers (Postgres fully supported, unchanged if set) -


def _ssl_required(url: URL) -> bool:
    sslmode = url.query.get("sslmode")
    if sslmode is not None:
        return str(sslmode).lower() not in ("disable", "allow")
    return url.host not in _NO_TLS_HOSTS


def _async_url(raw_url: str) -> str:
    url = make_url(raw_url)
    if url.get_backend_name() == "sqlite":
        return url.set(drivername="sqlite+aiosqlite").render_as_string(hide_password=False)
    # asyncpg's connect() has no `sslmode` kwarg (that's a libpq/psycopg
    # concept) and raises on it; SSL is configured instead via connect_args.
    url = url.set(drivername="postgresql+asyncpg")
    if "sslmode" in url.query:
        url = url.difference_update_query(["sslmode"])
    return url.render_as_string(hide_password=False)


def _sync_url(raw_url: str) -> str:
    """Used by Alembic, which runs synchronously regardless of what the app uses."""
    url = make_url(raw_url)
    if url.get_backend_name() == "sqlite":
        return url.set(drivername="sqlite").render_as_string(hide_password=False)
    return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


def _connect_args(raw_url: str) -> dict[str, Any]:
    url = make_url(raw_url)
    if url.get_backend_name() == "sqlite":
        return {}
    # statement_cache_size / prepared_statement_cache_size: disable both
    # asyncpg's and SQLAlchemy's client-side prepared-statement caches.
    # Required behind a PgBouncer-style pooler (e.g. Supabase's poolers) - a
    # cached statement can be prepared against one backend connection and
    # reused against another, which the server rejects.
    args: dict[str, Any] = {"statement_cache_size": 0, "prepared_statement_cache_size": 0}
    if _ssl_required(url):
        args["ssl"] = "require"
    return args


def describe_database(async_url: str) -> str:
    """Human-readable, credential-free description for startup logging."""
    url = make_url(async_url)
    if url.get_backend_name() == "sqlite":
        return f"sqlite at {url.database}"
    netloc = url.host or "?"
    if url.port:
        netloc += f":{url.port}"
    return f"{url.get_backend_name()} at {netloc}/{url.database or ''}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE_PATH), extra="ignore")

    # Database - one raw URL, unset in dev (defaulted to a local sqlite file),
    # required in production. Whatever scheme/driver your provider gives you
    # (e.g. Supabase's plain `postgresql://...`) works unchanged - the async
    # app engine and Alembic each derive the driver-specific URL they need
    # from it; see the properties below.
    database_url: str | None = None
    test_database_url: str | None = None

    # Auth - None in dev means "generate and cache one"; None in production
    # means "refuse to start" (see _resolve_environment).
    jwt_access_secret: str | None = None
    jwt_refresh_secret: str | None = None
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    invitation_token_secret: str | None = None
    invitation_token_expire_hours: int = 72

    # Email
    email_provider: str = "console"
    resend_api_key: str | None = None
    email_from: str = "Cafeteria Scheduler <no-reply@example.com>"

    # Bootstrap admin
    admin_bootstrap_email: str = "admin@example.com"
    admin_bootstrap_password: str | None = None
    admin_bootstrap_full_name: str = "Cafeteria Owner"

    # CORS
    cors_origins: str = "http://localhost:5173"

    # App
    app_env: str = "development"
    frontend_base_url: str = "http://localhost:5173"
    # Off by default everywhere, including a fresh dev clone (start.ps1 never
    # sets it) - fake employees/periods/scores are opt-in only, via
    # `SEED_DEMO_DATA=1 uv run python -m app.seed`. See app/seed.py.
    seed_demo_data: bool = False

    _missing_in_production: list[str] = PrivateAttr(default_factory=list)

    @model_validator(mode="after")
    def _resolve_environment(self) -> "Settings":
        is_dev = self.app_env == "development"
        missing: list[str] = []

        if self.database_url is None:
            if is_dev:
                self.database_url = _default_sqlite_url("db.sqlite3")
            else:
                missing.append("DATABASE_URL")

        if self.test_database_url is None and is_dev:
            self.test_database_url = _default_sqlite_url("test.sqlite3")

        for field, env_name in (
            ("jwt_access_secret", "JWT_ACCESS_SECRET"),
            ("jwt_refresh_secret", "JWT_REFRESH_SECRET"),
            ("invitation_token_secret", "INVITATION_TOKEN_SECRET"),
        ):
            if getattr(self, field) is None:
                if is_dev:
                    setattr(self, field, _dev_secret(field))
                else:
                    missing.append(env_name)

        if self.admin_bootstrap_password is None:
            if is_dev:
                self.admin_bootstrap_password = _dev_secret("admin_bootstrap_password", short=True)
            else:
                missing.append("ADMIN_BOOTSTRAP_PASSWORD")

        self._missing_in_production = missing
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_test_database_url(self) -> str:
        assert self.test_database_url is not None  # guaranteed once get_settings() returns
        return self.test_database_url

    # --- App (async) ---
    @property
    def async_database_url(self) -> str:
        assert self.database_url is not None  # guaranteed once get_settings() returns
        return _async_url(self.database_url)

    @property
    def asyncpg_connect_args(self) -> dict[str, Any]:
        assert self.database_url is not None
        return _connect_args(self.database_url)

    # --- Alembic (sync) ---
    @property
    def sync_database_url(self) -> str:
        assert self.database_url is not None
        return _sync_url(self.database_url)

    # --- Tests (async, against resolved_test_database_url) ---
    @property
    def async_test_database_url(self) -> str:
        return _async_url(self.resolved_test_database_url)

    @property
    def test_asyncpg_connect_args(self) -> dict[str, Any]:
        return _connect_args(self.resolved_test_database_url)


def _format_pydantic_error(exc: ValidationError) -> str:
    lines = [f"  - {'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()]
    found = "found" if ENV_FILE_PATH.exists() else "not found"
    return (
        "Invalid configuration:\n"
        + "\n".join(lines)
        + f"\n\nChecked for a .env file at: {ENV_FILE_PATH} ({found})"
        + "\n\nFix: correct the values above as real environment variables, or in that .env file."
    )


def _format_missing_production_secrets(app_env: str, missing: list[str]) -> str:
    found = "found" if ENV_FILE_PATH.exists() else "not found"
    return (
        f"Missing required settings for APP_ENV={app_env!r}:\n"
        + "\n".join(f"  - {name}" for name in missing)
        + f"\n\nChecked for a .env file at: {ENV_FILE_PATH} ({found})"
        + "\n\nFix: set these as real environment variables (e.g. your deploy platform's secret"
        " manager), or add them to that .env file. They are only auto-generated when"
        " APP_ENV=development (the default) - production always requires them explicitly."
    )


@lru_cache
def get_settings() -> Settings:
    try:
        settings = Settings()
    except ValidationError as exc:
        raise ConfigurationError(_format_pydantic_error(exc)) from None

    if settings._missing_in_production:  # noqa: SLF001 - internal to this module's own class
        raise ConfigurationError(
            _format_missing_production_secrets(settings.app_env, settings._missing_in_production)
        )

    return settings


settings = get_settings()
