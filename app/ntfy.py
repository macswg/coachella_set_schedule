"""
ntfy.sh push notification sender.

Set NTFY_URL in .env to enable (e.g. https://ntfy.sh/your-topic).
All sends are fire-and-forget in a daemon thread.
"""

import threading
import urllib.request

from app.config import settings


def _send(title: str, message: str, priority: str = "default", tags: list[str] | None = None) -> None:
    if not settings.NTFY_URL:
        return
    headers = {
        "Title": title.encode(),
        "Priority": priority,
        "Content-Type": "text/plain",
    }
    if tags:
        headers["Tags"] = ",".join(tags)
    try:
        req = urllib.request.Request(
            settings.NTFY_URL,
            data=message.encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
        print(f"[ntfy] sent: {title!r}")
    except Exception as e:
        print(f"[ntfy] failed: {e}")


def notify(title: str, message: str, priority: str = "default", tags: list[str] | None = None) -> None:
    """Fire-and-forget ntfy push notification."""
    threading.Thread(target=_send, args=(title, message, priority, tags), daemon=True).start()
