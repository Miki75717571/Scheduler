"""Production-safety net: dev-only defaults (auto-generated secrets, sqlite)
must never reach a real deployment. Runs in a subprocess - app.core.config
builds its `settings` singleton at import time via an `lru_cache`d
get_settings(), so the only reliable way to test "what happens on a fresh
process with APP_ENV=production and nothing else set" is to actually start one.
"""

import os
import subprocess
import sys

from app.core.config import BACKEND_DIR

_SECRET_ENV_NAMES = (
    "DATABASE_URL",
    "JWT_ACCESS_SECRET",
    "JWT_REFRESH_SECRET",
    "INVITATION_TOKEN_SECRET",
    "ADMIN_BOOTSTRAP_PASSWORD",
)


def _run_with_env(extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND_DIR)
    for name in _SECRET_ENV_NAMES:
        env.pop(name, None)
    env.update(extra_env)

    return subprocess.run(
        [sys.executable, "-c", "import app.core.config"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_production_startup_fails_with_missing_secrets() -> None:
    result = _run_with_env({"APP_ENV": "production"})

    assert result.returncode != 0
    assert "ConfigurationError" in result.stderr
    assert "Missing required settings for APP_ENV='production'" in result.stderr
    for name in _SECRET_ENV_NAMES:
        assert name in result.stderr


def test_production_startup_succeeds_with_every_secret_provided() -> None:
    result = _run_with_env(
        {
            "APP_ENV": "production",
            "DATABASE_URL": "postgresql://user:pass@example.com:5432/db",
            "JWT_ACCESS_SECRET": "real-access-secret",
            "JWT_REFRESH_SECRET": "real-refresh-secret",
            "INVITATION_TOKEN_SECRET": "real-invitation-secret",
            "ADMIN_BOOTSTRAP_PASSWORD": "real-admin-password",
        }
    )

    assert result.returncode == 0, result.stderr


def test_development_startup_needs_nothing() -> None:
    result = _run_with_env({"APP_ENV": "development"})

    assert result.returncode == 0, result.stderr
