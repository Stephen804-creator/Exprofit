"""Deployment configuration tests."""

from app.config import Settings


def test_render_postgres_url_uses_psycopg_driver() -> None:
    settings = Settings(
        database_url="postgresql://user:password@db.example.com/exprofit",
        _env_file=None,
    )
    assert settings.database_url == (
        "postgresql+psycopg://user:password@db.example.com/exprofit"
    )


def test_legacy_postgres_url_uses_psycopg_driver() -> None:
    settings = Settings(
        database_url="postgres://user:password@db.example.com/exprofit",
        _env_file=None,
    )
    assert settings.database_url == (
        "postgresql+psycopg://user:password@db.example.com/exprofit"
    )


def test_explicit_psycopg_url_is_unchanged() -> None:
    url = "postgresql+psycopg://user:password@localhost/exprofit"
    settings = Settings(database_url=url, _env_file=None)
    assert settings.database_url == url



def test_production_settings_reject_short_auth_secret() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="AUTH_SECRET_KEY"):
        Settings(
            app_env="production",
            auth_secret_key="too-short",
            database_url="postgresql+psycopg://user:pass@db.example.com/exprofit",
            _env_file=None,
        )


def test_production_settings_reject_placeholder_database() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(
            app_env="production",
            auth_secret_key="s" * 48,
            database_url="postgresql+psycopg://user:change-me@localhost/exprofit",
            _env_file=None,
        )


def test_production_settings_accept_strong_secret_and_remote_database() -> None:
    settings = Settings(
        app_env="production",
        auth_secret_key="s" * 48,
        database_url="postgresql+psycopg://user:pass@db.example.com/exprofit",
        _env_file=None,
    )
    assert settings.app_env == "production"
    assert len(settings.auth_secret_key) >= 32


def test_production_settings_reject_example_auth_secret() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="AUTH_SECRET_KEY"):
        Settings(
            app_env="production",
            auth_secret_key="replace-with-a-random-secret-at-least-32-bytes-long",
            database_url="postgresql+psycopg://user:pass@db.example.com/exprofit",
            _env_file=None,
        )


def test_production_settings_reject_wildcard_cors_origin() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            app_env="production",
            auth_secret_key="s" * 48,
            database_url="postgresql+psycopg://user:pass@db.example.com/exprofit",
            cors_origins="*",
            _env_file=None,
        )
