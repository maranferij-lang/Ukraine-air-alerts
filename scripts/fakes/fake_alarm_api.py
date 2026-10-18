"""Fake Ukraine Alarm API for the offline tests: serves the real saved day files (data/api_archive/) as the API would have answered at AS_OF.
    AS_OF="2026-10-10 12:37" [FAIL=20261009=500] python scripts/fakes/fake_alarm_api.py PORT
It only answers requests whose Authorization header is the fake token FAKE_ALARM_TOKEN_5b1e77. Nothing here is real."""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts.live_api import as_of

TOKEN = "FAKE_ALARM_TOKEN_5b1e77"
ARCH = ROOT / "data" / "api_archive" / "date_history"
AS_OF = pd.Timestamp(os.environ["AS_OF"], tz="UTC")
FAIL = dict(x.split("=") for x in os.environ.get("FAIL", "").split(",") if x)  # e.g. FAIL=20261009=500


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj=None):
        b = json.dumps(obj, ensure_ascii=False).encode() if obj is not None else b""
        self.send_response(code)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.headers.get("Authorization") != TOKEN:
            return self.send(401, {"message": "no"})
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/v3/alerts/dateHistory":
            d = q["date"][0]
            if d in FAIL:
                return self.send(int(FAIL[d]))
            if pd.Timestamp(d, tz="UTC") > AS_OF:
                return self.send(200, [])
            return self.send(200, as_of(json.load(open(ARCH / f"{d}.json")), AS_OF))
        if u.path == "/api/v3/alerts":
            ids = {}
            for f in sorted(os.listdir(ARCH))[-40:]:
                for a in as_of(json.load(open(ARCH / f)), AS_OF):
                    if a["isContinue"]:
                        ids[a["regionId"]] = a["regionName"]
            return self.send(200, [{"regionId": k, "regionName": v, "lastUpdate": AS_OF.strftime("%Y-%m-%dT%H:%M:%SZ"), "activeAlerts": []} for k, v in ids.items()])
        return self.send(404)


HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
