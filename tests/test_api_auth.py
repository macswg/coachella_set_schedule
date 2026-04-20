"""Tests that the four high-risk action endpoints require EDIT_PASSWORD when set."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


GATED_PATHS = (
    "/api/reset",
    "/api/reload",
    "/api/show/advance",
    "/api/recording/toggle",
)


@pytest.fixture
def client_with_auth(monkeypatch):
    """Boot a fresh app instance with EDIT_PASSWORD configured."""
    monkeypatch.setenv("EDIT_PASSWORD", "sekret")
    # The settings singleton is already instantiated in main — mutate it in place
    # so the dependency sees the password without rebuilding the whole app.
    import main as main_module
    from app.config import settings as app_settings

    prior = app_settings.EDIT_PASSWORD
    app_settings.EDIT_PASSWORD = "sekret"
    try:
        with TestClient(main_module.app) as c:
            yield c
    finally:
        app_settings.EDIT_PASSWORD = prior


@pytest.mark.parametrize("path", GATED_PATHS)
def test_gated_endpoints_return_401_without_auth(client_with_auth, path):
    resp = client_with_auth.post(path)
    assert resp.status_code == 401, f"{path} should require auth"
    assert resp.headers.get("WWW-Authenticate", "").startswith("Basic")


def test_reset_allowed_with_correct_password(client_with_auth):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        resp = client_with_auth.post("/api/reset", auth=("", "sekret"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "reset"


def test_reload_allowed_with_correct_password(client_with_auth):
    with patch("main.manager") as mock_manager:
        mock_manager.broadcast_reload = AsyncMock()
        resp = client_with_auth.post("/api/reload", auth=("", "sekret"))
    assert resp.status_code == 200


def test_recording_toggle_allowed_with_correct_password(client_with_auth):
    with patch("main.manager") as mock_manager:
        mock_manager.broadcast_recording_state = AsyncMock()
        resp = client_with_auth.post("/api/recording/toggle", auth=("", "sekret"))
    assert resp.status_code == 200


def test_wrong_password_still_401(client_with_auth):
    resp = client_with_auth.post("/api/reset", auth=("", "wrong"))
    assert resp.status_code == 401


def test_endpoints_open_when_password_unset(monkeypatch):
    """Sanity: when EDIT_PASSWORD is empty, these endpoints accept unauthenticated
    requests (preserves existing dev-mode behavior)."""
    from app.config import settings as app_settings
    import main as main_module

    prior = app_settings.EDIT_PASSWORD
    app_settings.EDIT_PASSWORD = ""
    try:
        with TestClient(main_module.app) as c:
            with patch("main.manager") as mock_manager:
                mock_manager.broadcast_reload = AsyncMock()
                resp = c.post("/api/reload")
        assert resp.status_code == 200
    finally:
        app_settings.EDIT_PASSWORD = prior
