import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app
from app import store


ONDECK_ACT = "On Deck - Sunrise Collective"


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


# --- POST /acts/{name}/screentime/start ---

def test_screentime_start_returns_ok(client):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        resp = client.post("/acts/On%20Deck%20-%20Sunrise%20Collective/screentime/start")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_screentime_start_sets_session(client):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        client.post("/acts/On%20Deck%20-%20Sunrise%20Collective/screentime/start")

    acts = store.get_schedule()
    act = next(a for a in acts if a.act_name == ONDECK_ACT)
    assert act.screentime_session_start is not None


def test_screentime_start_broadcasts(client):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock) as mock_broadcast:
        client.post("/acts/On%20Deck%20-%20Sunrise%20Collective/screentime/start")
    mock_broadcast.assert_called_once()


def test_screentime_start_unknown_act_does_not_broadcast(client):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock) as mock_broadcast:
        resp = client.post("/acts/Unknown%20Act/screentime/start")
    assert resp.status_code == 200
    mock_broadcast.assert_not_called()


# --- POST /acts/{name}/screentime/stop ---

def test_screentime_stop_returns_ok(client):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        client.post("/acts/On%20Deck%20-%20Sunrise%20Collective/screentime/start")
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        resp = client.post("/acts/On%20Deck%20-%20Sunrise%20Collective/screentime/stop")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_screentime_stop_clears_session(client):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        client.post("/acts/On%20Deck%20-%20Sunrise%20Collective/screentime/start")
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        client.post("/acts/On%20Deck%20-%20Sunrise%20Collective/screentime/stop")

    acts = store.get_schedule()
    act = next(a for a in acts if a.act_name == ONDECK_ACT)
    assert act.screentime_session_start is None


def test_screentime_stop_accumulates_total(client):
    from datetime import time
    start = time(14, 0, 0)
    stop = time(14, 0, 45)

    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        with patch("app.store.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = start
            client.post("/acts/On%20Deck%20-%20Sunrise%20Collective/screentime/start")

    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        with patch("app.store.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = stop
            client.post("/acts/On%20Deck%20-%20Sunrise%20Collective/screentime/stop")

    acts = store.get_schedule()
    act = next(a for a in acts if a.act_name == ONDECK_ACT)
    assert act.screentime_total_seconds == 45


# --- POST /acts/{name}/end ---

def test_end_records_time(client):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        client.post("/acts/Sunrise%20Collective/start")
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        resp = client.post("/acts/Sunrise%20Collective/end")

    assert resp.status_code == 200
    acts = store.get_schedule()
    act = next(a for a in acts if a.act_name == "Sunrise Collective")
    assert act.actual_end is not None


def test_end_unknown_act_no_broadcast(client):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock) as mock_broadcast:
        resp = client.post("/acts/Unknown%20Act/end")
    assert resp.status_code == 200
    mock_broadcast.assert_not_called()


# --- POST /acts/{name}/clear ---

def test_clear_removes_times(client):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        client.post("/acts/Sunrise%20Collective/start")
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        client.post("/acts/Sunrise%20Collective/end")
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock):
        resp = client.post("/acts/Sunrise%20Collective/clear")

    assert resp.status_code == 200
    acts = store.get_schedule()
    act = next(a for a in acts if a.act_name == "Sunrise Collective")
    assert act.actual_start is None
    assert act.actual_end is None


def test_clear_unknown_act_no_broadcast(client):
    with patch("main.broadcast_schedule_update", new_callable=AsyncMock) as mock_broadcast:
        resp = client.post("/acts/Unknown%20Act/clear")
    assert resp.status_code == 200
    mock_broadcast.assert_not_called()
