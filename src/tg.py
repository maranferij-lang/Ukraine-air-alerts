"""A small Telegram Bot API client (sendMessage, getUpdates) with the same discipline as src/ukrainealarm.py: the bot token is held in memory only, it is part of the
request URL (that is how Telegram works) and so a failed call is reduced to a status code: no URL, no response text and no exception message is ever passed on.
Standard library only. TELEGRAM_API_BASE may point at the real API or at http://127.0.0.1 (the offline tests' fake server).
"""
import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE = "https://api.telegram.org"
BASE_ENV = "TELEGRAM_API_BASE"


class Telegram:
    def __init__(self, token):
        if not token:
            raise ValueError("no token")
        base = os.environ.get(BASE_ENV, DEFAULT_BASE).rstrip("/")
        if base != DEFAULT_BASE and not base.startswith("http://127.0.0.1"):
            raise SystemExit(f"{BASE_ENV} may only point at {DEFAULT_BASE} or at http://127.0.0.1 (the token is part of the address).")
        self._url = f"{base}/bot{token}/"

    def call(self, method, payload=None):
        """(HTTP status, parsed JSON or None). Status 0: no answer at all (network, TLS, timeout)."""
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self._url + method, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, None
        except Exception:  # noqa: BLE001  (never let an exception text, which may contain the address, travel on)
            return 0, None
        try:
            return status, json.loads(raw.decode("utf-8"))
        except ValueError:
            return status, None

    def send_message(self, chat_id, text):
        """The HTTP status of sendMessage (200 = sent)."""
        status, body = self.call("sendMessage", {"chat_id": chat_id, "text": text, "disable_web_page_preview": True})
        return status if status != 200 or (isinstance(body, dict) and body.get("ok")) else 502

    def chats_seen(self):
        """(status, [(chat id, chat type)] of the chats that wrote to the bot recently); ids only, no names."""
        status, body = self.call("getUpdates", {"timeout": 0, "allowed_updates": ["message"]})
        out = []
        if status == 200 and isinstance(body, dict):
            for u in body.get("result", []):
                chat = (u.get("message") or {}).get("chat") or {}
                if "id" in chat and (chat["id"], chat.get("type", "?")) not in out:
                    out.append((chat["id"], chat.get("type", "?")))
        return status, out
