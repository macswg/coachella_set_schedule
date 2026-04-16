"""
Bitfocus Companion HTTP API integration.

Set COMPANION_URL in .env to enable (e.g. http://192.168.1.100:19267).
All presses are fire-and-forget in a daemon thread.
"""

import threading
import urllib.request

from app.config import settings


def _press(page: int, row: int, col: int) -> None:
    if not settings.COMPANION_URL:
        return
    url = f"{settings.COMPANION_URL}/api/location/{page}/{row}/{col}/press"
    try:
        req = urllib.request.Request(url, data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=5):
            pass
        print(f"[companion] pressed {page}/{row}/{col}")
    except Exception as e:
        print(f"[companion] press failed {page}/{row}/{col}: {e}")


def _fire(page: int, row: int, col: int) -> None:
    threading.Thread(target=_press, args=(page, row, col), daemon=True).start()


def trigger_set_mv_rec() -> None:
    """Fire the multiview recording button (mark set start)."""
    _fire(15, 3, 4)


def trigger_changeover_rec() -> None:
    """Fire the changeover recording button (mark set stop)."""
    _fire(15, 3, 2)
