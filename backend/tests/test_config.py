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
