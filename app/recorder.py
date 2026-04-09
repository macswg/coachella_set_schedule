"""
Recording trigger implementation for AJA Ki Pro Rack.

Sends HTTP commands to the Ki Pro at KIPRO_IP (set in .env).
Transport command values: 3 = Record, 4 = Stop.

Transport state query uses eParamID_TransportState.
The response JSON "value" field maps to: 0=Stop, 1=Play, 2=Record.
"""

import json
import threading
import urllib.request

from app.config import settings

_KIPRO_URL = "http://{ip}/config?action=set&paramid=eParamID_TransportCommand&value={value}"
_KIPRO_STATE_URL = "http://{ip}/config?action=get&paramid=eParamID_TransportState"
_TC_RECORD = 3
_TC_STOP = 4

# Transport state value that indicates the deck is recording.
# AJA Ki Pro: eParamID_TransportState returns "2" when rolling.
_STATE_RECORD = "2"


def _send(value: int) -> None:
    if not settings.KIPRO_IP:
        print("[recorder] KIPRO_IP not set, skipping command")
        return
    url = _KIPRO_URL.format(ip=settings.KIPRO_IP, value=value)
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            body = resp.read().decode()
            print(f"[recorder] Ki Pro response: {body}")
    except Exception as e:
        print(f"[recorder] Ki Pro command failed (value={value}): {e}")


def _fetch_transport_state() -> dict:
    """Query the Ki Pro for its current transport state. Returns a status dict."""
    if not settings.KIPRO_IP:
        return {"configured": False, "rolling": False, "raw": None, "error": None}
    url = _KIPRO_STATE_URL.format(ip=settings.KIPRO_IP)
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            body = resp.read().decode()
        data = json.loads(body)
        raw = str(data.get("value", ""))
        return {"configured": True, "rolling": raw == _STATE_RECORD, "raw": raw, "error": None}
    except Exception as e:
        return {"configured": True, "rolling": False, "raw": None, "error": str(e)}


def get_transport_state() -> dict:
    """Synchronous Ki Pro state query — run via asyncio.to_thread in async contexts."""
    return _fetch_transport_state()


def start_recording(act_name: str) -> None:
    threading.Thread(target=_send, args=(_TC_RECORD,), daemon=True).start()
    print(f"[recorder] start_recording: {act_name!r}")


def stop_recording(act_name: str) -> None:
    threading.Thread(target=_send, args=(_TC_STOP,), daemon=True).start()
    print(f"[recorder] stop_recording: {act_name!r}")
