"""Regression tests for client-side frontend routes in the combined deployment."""

from fastapi.testclient import TestClient

import app.main as main_module


def test_accept_invitation_path_serves_frontend_entrypoint(tmp_path, monkeypatch) -> None:
    index_file = tmp_path / "index.html"
    index_file.write_text(
        '<!doctype html><html><body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    monkeypatch.setattr(main_module, "FRONTEND_DIST", tmp_path)

    response = TestClient(main_module.app).get(
        "/accept-invitation?token=example-invitation-token"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<div id="root"></div>' in response.text


def test_accept_invitation_path_reports_missing_frontend_build(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main_module, "FRONTEND_DIST", tmp_path)

    response = TestClient(main_module.app).get("/accept-invitation?token=example")

    assert response.status_code == 503
    assert response.json() == {"detail": "Frontend build is unavailable"}
