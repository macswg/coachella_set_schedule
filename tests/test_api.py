import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app
from app import store


def _clear_all():
    for act in store.get_schedule():
        store.clear_actual_times(act.act_name)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_store():
    _clear_all()
    yield
    _clear_all()


# --- POST /acts/{name}/start ---

def test_start_records_time_when_nothing_in_progress(client):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        resp = client.post("/acts/Sunrise%20Collective/start")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    acts = store.get_schedule()
    sunrise = next(a for a in acts if a.act_name == "Sunrise Collective")
    assert sunrise.actual_start is not None
    assert sunrise.actual_end is None


def test_start_auto_completes_in_progress_act(client):
    # Start first act
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        client.post("/acts/Sunrise%20Collective/start")

    # Start second act — first should be auto-completed
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        client.post("/acts/Desert%20Echoes/start")

    acts = store.get_schedule()
    sunrise = next(a for a in acts if a.act_name == "Sunrise Collective")
    desert = next(a for a in acts if a.act_name == "Desert Echoes")

    assert sunrise.actual_end is not None  # auto-completed
    assert desert.actual_start is not None
    assert desert.actual_end is None  # still in progress


def test_start_unknown_act_returns_ok_no_state_change(client):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock) as mock_broadcast:
        resp = client.post("/acts/Unknown%20Act/start")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    # broadcast was NOT called because update_actual_start returned None
    mock_broadcast.assert_not_called()

    # No act was modified
    for act in store.get_schedule():
        assert act.actual_start is None
