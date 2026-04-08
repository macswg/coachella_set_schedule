"""
Recording trigger implementation for AJA Ki Pro Rack.

Sends HTTP commands to the Ki Pro at KIPRO_IP (set in .env).
Transport command values: 3 = Record, 4 = Stop.
"""

import threading
import urllib.request

from app.config import settings

_KIPRO_URL = "http://{ip}/config?action=set&paramid=eParamID_TransportCommand&value={value}"
_TC_RECORD = 3
_TC_STOP = 4


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


def start_recording(act_name: str) -> None:
    threading.Thread(target=_send, args=(_TC_RECORD,), daemon=True).start()
    print(f"[recorder] start_recording: {act_name!r}")


def stop_recording(act_name: str) -> None:
    threading.Thread(target=_send, args=(_TC_STOP,), daemon=True).start()
    print(f"[recorder] stop_recording: {act_name!r}")
