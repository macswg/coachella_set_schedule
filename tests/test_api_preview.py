import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# --- /preview route smoke tests ---

def test_preview_returns_200(client):
    resp = client.get("/preview")
    assert resp.status_code == 200


def test_preview_returns_html(client):
    resp = client.get("/preview")
    assert "text/html" in resp.headers["content-type"]


def test_preview_contains_time_override_input(client):
    resp = client.get("/preview")
    assert 'type="time"' in resp.text


def test_preview_contains_live_button(client):
    resp = client.get("/preview")
    assert "Live" in resp.text


def test_preview_contains_operator_buttons(client):
    """The /preview page shows operator start/end buttons (view_only=False)."""
    resp = client.get("/preview")
    assert "Mark Set Start" in resp.text


def test_edit_has_no_time_override_input(client):
    """/edit must not contain the time override input."""
    resp = client.get("/edit")
    assert resp.status_code == 200
    # The time input is rendered only when show_time_override=True
    # Check the override container is absent (not just the input tag)
    assert 'class="time-override"' not in resp.text


def test_index_has_no_time_override_input(client):
    """/  (view-only) must not contain the time override input."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'class="time-override"' not in resp.text
