"""Small client for the Ukraine Alarm API (https://api.ukrainealarm.com, swagger in docs/api/).

The token is read only from the environment variable UA_ALARM_TOKEN and sent as the `Authorization` header (the swagger's
apiKey scheme: the value is the token itself). It is never printed, logged or saved, and a failed call is reduced to a status
code: no response text and no exception message is passed on. Standard library only (Python 3.9 is fine).
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_ENV = "UA_ALARM_TOKEN"
BASE_ENV = "UA_ALARM_BASE"  # for offline tests against a local fake server only
DEFAULT_BASE = "https://api.ukrainealarm.com"
USER_AGENT = "ukraine-air-alerts-course-project/1.0 (+https://github.com/maranferij-lang/Ukraine-air-alerts)"
MIN_GAP = 6.0          # seconds between calls to start with; the swagger states no limit and 2.5 s drew HTTP 429 on 21 of 43 calls
MAX_GAP = 60.0
RETRY_429 = 3          # retries after HTTP 429
WAIT_429 = 30.0        # seconds, when the reply has no Retry-After

# Ukrainian state names as the API writes them -> the oblast names in data/raw (src/load.py). Crimea and Sevastopol are not in our data.
UK_TO_OURS = {
    "вінницька область": "Vinnytska oblast", "волинська область": "Volynska oblast",
    "дніпропетровська область": "Dnipropetrovska oblast", "донецька область": "Donetska oblast",
    "житомирська область": "Zhytomyrska oblast", "закарпатська область": "Zakarpatska oblast",
    "запорізька область": "Zaporizka oblast", "івано-франківська область": "Ivano-Frankivska oblast",
    "київська область": "Kyivska oblast", "м. київ": "Kyiv City", "кіровоградська область": "Kirovohradska oblast",
    "луганська область": "Luhanska oblast", "львівська область": "Lvivska oblast",
    "миколаївська область": "Mykolaivska oblast", "одеська область": "Odeska oblast",
    "полтавська область": "Poltavska oblast", "рівненська область": "Rivnenska oblast",
    "сумська область": "Sumska oblast", "тернопільська область": "Ternopilska oblast",
    "харківська область": "Kharkivska oblast", "херсонська область": "Khersonska oblast",
    "хмельницька область": "Khmelnytska oblast", "черкаська область": "Cherkaska oblast",
    "чернівецька область": "Chernivetska oblast", "чернігівська область": "Chernihivska oblast",
}


# Raion names the API writes differently from our (older) official feed. Sheptytskyi raion (Lviv oblast) is the former Chervonohradskyi raion:
# our list has 7 raions for Lviv oblast, six of them appear in the API under the same name, and this is the seventh.
RAION_ALIASES = {"Sheptytskyi raion": "Chervonohradskyi raion"}


def our_name(uk_name):
    """Our oblast name for an API state name, or None (Crimea, Sevastopol, or a spelling we did not expect)."""
    return UK_TO_OURS.get(" ".join(str(uk_name).lower().split()))


class Client:
    def __init__(self, min_gap=MIN_GAP):
        self.token = os.environ.get(TOKEN_ENV, "")
        if not self.token:
            raise SystemExit(f"{TOKEN_ENV} is not set in the environment. Set it in your shell first (it is never read from a file).")
        base = os.environ.get(BASE_ENV, DEFAULT_BASE).rstrip("/")
        if base != DEFAULT_BASE and not base.startswith("http://127.0.0.1"):
            raise SystemExit(f"{BASE_ENV} may only point at the real API or at http://127.0.0.1 (the token would be sent there).")
        self.base, self.min_gap, self.gap, self._last = base, min_gap, min_gap, 0.0
        self.calls = 0
        self.n429 = 0
        self.retry_after_seen = []  # the Retry-After values (seconds) the server sent with HTTP 429, if any
        self._ok_streak = 0

    def get(self, path, params=None):
        """GET one endpoint. Returns (status, data, raw_bytes). status 0 = no HTTP answer (network/TLS problem);
        data is the parsed JSON for status 200, else None. Never raises on HTTP or network errors."""
        url = self.base + path + ("?" + urllib.parse.urlencode(params) if params else "")
        for attempt in range(RETRY_429 + 1):
            wait = self._last + self.gap - time.time()
            if wait > 0:
                time.sleep(wait)
            req = urllib.request.Request(url, headers={"Authorization": self.token, "User-Agent": USER_AGENT,
                                                       "Accept": "application/json"})
            retry_after = None
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    status, raw = r.status, r.read()
            except urllib.error.HTTPError as e:
                status, raw = e.code, b""
                retry_after = e.headers.get("Retry-After")
            except Exception:
                status, raw = 0, b""
            self._last = time.time()
            self.calls += 1
            if status == 429:
                self.n429 += 1
                self._ok_streak = 0
                try:
                    pause = min(float(retry_after), 120.0)
                    self.retry_after_seen.append(pause)
                except (TypeError, ValueError):
                    pause = WAIT_429
                self.gap = min(max(self.gap * 1.5, pause / 2), MAX_GAP)  # slow down for the rest of the run
                if attempt < RETRY_429:
                    time.sleep(pause)
                    continue
            elif status == 200:
                self._ok_streak += 1
                if self._ok_streak >= 10:  # a long clean run: speed up a little, never below the starting gap
                    self.gap, self._ok_streak = max(self.min_gap, self.gap / 1.25), 0
            break
        data = None
        if status == 200:
            try:
                data = json.loads(raw.decode("utf-8"))
            except ValueError:
                status, data = 598, None  # 200 but not JSON (for example a challenge page)
        return status, data, raw


def region_index(regions_json):
    """{regionId: (name, type, state_id)} for every node of the /api/v3/regions tree (states, districts, communities, ...)."""
    out = {}

    def walk(node, state_id):
        rid = node.get("regionId")
        sid = state_id or rid  # top-level nodes are the states; everything below belongs to its state
        out[rid] = (node.get("regionName"), node.get("regionType"), sid)
        for ch in node.get("regionChildIds") or []:
            walk(ch, sid)

    for st in (regions_json or {}).get("states") or []:
        walk(st, None)
    return out
