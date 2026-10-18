"""Fake Telegram Bot API for the offline tests.
    FAKE_TG_TOKEN=... FAKE_TG_CHAT=... FAKE_TG_LOG=file.jsonl [FAKE_TG_MODE=ok|500] [FAKE_TG_UPDATES='[...]'] python scripts/fakes/fake_telegram.py PORT
sendMessage (POST /bot<token>/sendMessage): 401 if the token in the path is not FAKE_TG_TOKEN, 400 if chat_id is not FAKE_TG_CHAT, 500 in mode 500, else 200 and one JSON line
{chat_id, text} appended to FAKE_TG_LOG (the token is never written). getUpdates: the updates in FAKE_TG_UPDATES. Nothing here is real."""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys

TOKEN, CHAT, LOG = os.environ["FAKE_TG_TOKEN"], os.environ["FAKE_TG_CHAT"], os.environ["FAKE_TG_LOG"]
MODE = os.environ.get("FAKE_TG_MODE", "ok")
UPDATES = json.loads(os.environ.get("FAKE_TG_UPDATES", "[]"))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj=None):
        b = json.dumps(obj).encode() if obj is not None else b""
        self.send_response(code)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        parts = self.path.strip("/").split("/")
        if len(parts) != 2 or parts[0] != "bot" + TOKEN:
            return self.send(401, {"ok": False})
        if parts[1] == "sendMessage":
            if MODE == "500":
                return self.send(500, {"ok": False})
            if str(body.get("chat_id")) != CHAT:
                return self.send(400, {"ok": False, "description": "chat not found"})
            with open(LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"chat_id": body["chat_id"], "text": body["text"]}, ensure_ascii=False) + "\n")
            return self.send(200, {"ok": True, "result": {"message_id": 1}})
        if parts[1] == "getUpdates":
            return self.send(200, {"ok": True, "result": UPDATES})
        return self.send(404)


HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
