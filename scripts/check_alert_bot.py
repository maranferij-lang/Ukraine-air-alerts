"""Offline checks for the Telegram alert bot, the keychain helper, the hourly job and the launchd scripts. No real network, keychain or launchd is touched.

    python scripts/check_alert_bot.py

Fakes (scripts/fakes/): a Telegram API, the Ukraine Alarm API (real saved days as of 2026-10-10 12:37 UTC) and a `security` with a JSON file as the keychain. All secrets used here are
made-up strings; at the end every output, log, state file and page the checks produced is searched for them.
1. config: defaults, other spellings of the names, every kind of mistake reported
2. the message: Ukrainian, short, the fields asked for, no long dash, the Kyiv hour right in summer and winter
3. the rule: below to at or above only, nothing while above, the cooldown, the first run, model change, per-oblast thresholds
4. the bot against the fake Telegram over real HTTP: sending, not handling a forecast twice, retry after a failed send, stale forecast, missing keychain items, wrong chat, no server,
   --test, --find-chat-id, --check, --dry-run
5. secrets: only status in the output; the keychain is asked without the secret on any command line; nothing secret in any file
6. the hourly job: order of steps, the bot skipped when the forecast failed, only status lines logged, the launchd property list
7. install and uninstall scripts with a fake launchctl and a fake keychain
8. end to end: the fake Alarm API -> predict.py --now with the token from the (fake) keychain -> last_forecast.json -> the bot -> the fake Telegram
"""
import contextlib
import io
import json
import os
import plistlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts import alert_bot as ab
from scripts import hourly_job as hj
from src import keychain
from src.i18n import OBLAST_UK

FAILS = []
SECRETS = {"telegram_token": "FAKE_TG_TOKEN_7c2d91:aaBBccDD", "telegram_chat": "424242424", "alarm_token": "FAKE_ALARM_TOKEN_5b1e77"}
LONG_DASH = re.compile("[‒-―−]")
TMP = Path(tempfile.mkdtemp(prefix="alertbot_"))
PROCS = []
OUTPUTS = []  # everything printed by anything under test


def check(ok, msg):
    print(("ok    " if ok else "FAIL  ") + msg)
    if not ok:
        FAILS.append(msg)


def capture(fn, *a, _keep=True, **kw):
    """Run fn with stdout and stderr captured; the text is kept to be searched for secrets at the end (_keep=False for the one command that prints the chat id on purpose)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            ret = fn(*a, **kw)
        except SystemExit as e:
            ret = e.code
    if _keep:
        OUTPUTS.extend([out.getvalue(), err.getvalue()])
    return ret, out.getvalue() + err.getvalue()


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def start(script, env=None):
    port = free_port()
    p = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "fakes" / script), str(port)], env={**os.environ, **(env or {})}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    PROCS.append(p)
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return port, p
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"{script} did not start")


def stop(p):
    p.terminate()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()


def telegram(mode="ok", updates=None):
    log = TMP / f"tg_{len(PROCS)}.jsonl"
    log.write_text("")
    port, p = start("fake_telegram.py", {"FAKE_TG_TOKEN": SECRETS["telegram_token"], "FAKE_TG_CHAT": SECRETS["telegram_chat"], "FAKE_TG_LOG": str(log), "FAKE_TG_MODE": mode,
                                         "FAKE_TG_UPDATES": json.dumps(updates or [])})
    os.environ["TELEGRAM_API_BASE"] = f"http://127.0.0.1:{port}"
    return log, p


def sent(log):
    return [json.loads(l) for l in Path(log).read_text(encoding="utf-8").splitlines() if l.strip()]


def fake_keychain(items=None, name="keychain"):
    path = TMP / f"{name}.json"
    path.write_text(json.dumps({keychain.SERVICES[k]: v for k, v in (items or SECRETS).items()}))
    os.environ["FAKE_KEYCHAIN"] = str(path)
    os.environ["FAKE_KEYCHAIN_LOG"] = str(TMP / f"{name}.log")
    keychain.SECURITY = str(ROOT / "scripts" / "fakes" / "fake_security.py")
    return path


def forecast_doc(p1, made="2026-10-10T12:37:00Z", origin="2026-10-10T12:00:00Z", version="frozen-v2-test", now_flags=None):
    """A last_forecast.json for all 24 oblasts; p1 = {oblast: probability for 1 h} for the ones that matter, the rest 5%."""
    rows = []
    for o in OBLAST_UK:
        v = p1.get(o, 0.05)
        rows.append({"oblast": o, "now": bool((now_flags or {}).get(o, False)), "p": {"1": v, "3": min(v * 1.5, 0.99), "6": min(v * 1.8, 0.99)}})
    return {"origin": origin, "made": made, "model": "v2", "version": version, "thresholds": {"1": 0.252, "3": 0.427, "6": 0.427}, "rows": rows}


def write_json(path, doc):
    Path(path).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


def conf(text, name="c.conf"):
    p = TMP / name
    p.write_text(text, encoding="utf-8")
    return p


NOW = pd.Timestamp("2026-10-10 12:40:00", tz="UTC")


# ------------------------------------------------------------------------------------------------------------------------------ 1 config
def config_checks():
    cfg = ab.load_config(ROOT / "config" / "alert_bot.conf")
    check([(o, t) for o, t, _ in cfg["watch"]] == [("Kyiv City", 0.5), ("Kyivska oblast", 0.5)] and cfg["cooldown"] == 3, "the committed config: м. Київ and Київська область at 50%, cooldown 3 h")
    # other spellings
    names = {k: ab.name_lookup().get(k.lower()) for k in ("Київ", "м. Київ", "Kyiv", "Kyiv City", "Київська", "Київська область", "Kyivska", "Харківська", "Kharkivska", "Kharkivska oblast", "Дніпропетровська")}
    want = {"Київ": "Kyiv City", "м. Київ": "Kyiv City", "Kyiv": "Kyiv City", "Kyiv City": "Kyiv City", "Київська": "Kyivska oblast", "Київська область": "Kyivska oblast", "Kyivska": "Kyivska oblast",
            "Харківська": "Kharkivska oblast", "Kharkivska": "Kharkivska oblast", "Kharkivska oblast": "Kharkivska oblast", "Дніпропетровська": "Dnipropetrovska oblast"}
    check(names == want, "names are read in Ukrainian and English, full and short")
    check(len({v for v in name_all()}) == 24, "every one of the 24 oblasts can be named in the config")
    c2 = ab.load_config(conf("[settings]\ncooldown_hours = 0\n[watch]\nKharkivska = 37,5%\nЛьвівська = 20\n"))
    check([(o, round(t, 4)) for o, t, _ in c2["watch"]] == [("Kharkivska oblast", 0.375), ("Lvivska oblast", 0.2)] and c2["cooldown"] == 0, "thresholds like 37,5% and 20 are read as percent; cooldown 0 is allowed")
    bad = {"unknown oblast": "[watch]\nAtlantis = 50\n", "threshold": "[watch]\nKharkivska = abc\n", "threshold ": "[watch]\nKharkivska = 0\n", "threshold  ": "[watch]\nKharkivska = 150\n",
           "twice": "[watch]\nKharkivska = 50\nХарківська = 60\n", "empty": "[watch]\n", "cooldown": "[settings]\ncooldown_hours = -1\n[watch]\nKharkivska = 50\n", "no file": None}
    for key, text in bad.items():
        try:
            ab.load_config(conf(text) if text is not None else TMP / "nope.conf")
            check(False, f"a config with a mistake ({key.strip()}) is refused")
        except ab.ConfigError as e:
            check(any(key.strip().split()[0] in p or key.strip() in p.lower() or "empty" in p or "exist" in p for p in e.args[0]), f"a config with a mistake ({key.strip()}) is refused with a reason: {e.args[0][0][:70]}")


def name_all():
    return [v for v in ab.name_lookup().values()]


# ------------------------------------------------------------------------------------------------------------------------------ 2 message
def message_checks():
    for origin, hm in (("2026-10-10T12:00:00Z", "15:00"), ("2026-12-10T12:00:00Z", "14:00")):
        text = ab.message("Kyivska oblast", 0.5, {1: 0.612, 3: 0.904, 6: 0.966}, False, pd.Timestamp(origin))
        lines = text.split("\n")
        check(len(lines) == 5 and "Київська область" in lines[0] and "50%" in lines[0] and lines[1] == "Протягом 1 год: 61%, 3 год: 90%, 6 год: 97%." and lines[2] == "Тривога на годину прогнозу: ні."
              and lines[3] == f"Година прогнозу: {hm} (Київ)." and lines[4] == "Навчальна модель, слідкуйте за офіційними тривогами.", f"the message ({origin[:10]}): oblast, threshold, 1/3/6 h in percent, alert state, origin hour {hm} Kyiv time, the study-model line")
    t2 = ab.message("Kyiv City", 0.375, {1: 0.4, 3: 0.5, 6: 0.6}, True, pd.Timestamp("2026-10-10T12:00:00Z"))
    check(t2.startswith("м. Київ:") and "поріг 37,5%." in t2 and "Тривога на годину прогнозу: так." in t2, "м. Київ, an alert running (так), a fractional threshold written with a comma (37,5%)")
    check(not LONG_DASH.search(text + t2 + ab.TEST_TEXT) and not re.search(r"\d\.\d{2}", text) and len(text) < 330 and re.search("[а-яіїєґ]", text) and not re.search("[A-Za-z]{4}", text), "short Ukrainian text, no long dash, no raw decimal, no Latin words")


# ------------------------------------------------------------------------------------------------------------------------------ 3 the rule
def rule_checks():
    cfg = {"cooldown": 3.0, "watch": [("Kyiv City", 0.5, "Київ"), ("Kyivska oblast", 0.5, "Київська")]}
    st = lambda p, v="frozen-v2-test", last=None: {"version": v, "oblasts": {"Kyiv City": {"p1": p[0], "last_sent": last}, "Kyivska oblast": {"p1": p[1], "last_sent": last}}}
    fc = lambda a, b: forecast_doc({"Kyiv City": a, "Kyivska oblast": b})

    def due(state, a, b, now=NOW):
        d, s, ns = ab.decide(cfg, fc(a, b), state, now)
        return [x[0] for x in d], s, ns
    check(due({}, 0.7, 0.7)[0] == [] and due({}, 0.7, 0.7)[2]["oblasts"]["Kyiv City"]["p1"] == 0.7, "the first run only records where each oblast stands (nothing sent even if above)")
    check(due(st((0.3, 0.3)), 0.55, 0.4)[0] == ["Kyiv City"], "below to above sends, only for the oblast that crossed")
    check(due(st((0.49, 0.1)), 0.5, 0.1)[0] == ["Kyiv City"], "exactly at the threshold counts as crossed (at or above)")
    check(due(st((0.5, 0.5)), 0.6, 0.9)[0] == [], "staying at or above sends nothing")
    check(due(st((0.7, 0.7)), 0.4, 0.4)[0] == [], "falling below sends nothing")
    d, s, ns = due(st((0.3, 0.3), last=f"{NOW - pd.Timedelta(hours=1):%Y-%m-%dT%H:%M:%SZ}"), 0.6, 0.6)
    check(d == [] and s == ["Kyiv City", "Kyivska oblast"], "inside the cooldown (1 h after the last message) a crossing is held back")
    check(due(st((0.3, 0.3), last=f"{NOW - pd.Timedelta(hours=3):%Y-%m-%dT%H:%M:%SZ}"), 0.6, 0.6)[0] == ["Kyiv City", "Kyivska oblast"], "after exactly 3 h the next crossing is sent again")
    check(due(st((0.3, 0.3), last=f"{NOW - pd.Timedelta(hours=2, minutes=59):%Y-%m-%dT%H:%M:%SZ}"), 0.6, 0.6)[0] == [], "2 h 59 min after the last message it is still held back")
    check(due(st((0.3, 0.3), v="frozen-v1-old"), 0.6, 0.6)[0] == [], "after the model changed the first run only records (a jump between two models is not a crossing)")
    cfg2 = {"cooldown": 3.0, "watch": [("Kyiv City", 0.3, "Київ"), ("Kyivska oblast", 0.8, "Київська")]}
    d, _, _ = ab.decide(cfg2, fc(0.4, 0.6), st((0.2, 0.7)), NOW)
    check([x[0] for x in d] == ["Kyiv City"], "every oblast has its own threshold (30% and 80%)")
    d, _, ns = ab.decide({"cooldown": 3.0, "watch": [("Lvivska oblast", 0.5, "Львівська")]}, forecast_doc({"Lvivska oblast": 0.6}), {"version": "frozen-v2-test", "oblasts": {"Lvivska oblast": {"p1": 0.2, "last_sent": None}}}, NOW)
    check(len(d) == 1 and set(ns["oblasts"]) == {"Lvivska oblast"}, "any oblast can be watched (Львівська)")
    old_state = lambda hours: {**st((0.3, 0.3)), "made": f"{pd.Timestamp('2026-10-10T12:37:00Z') - pd.Timedelta(hours=hours):%Y-%m-%dT%H:%M:%SZ}"}
    check(due(old_state(2), 0.6, 0.6)[0] == ["Kyiv City", "Kyivska oblast"], "a previous reading 2 h before still counts")
    check(due(old_state(5), 0.6, 0.6)[0] == [] and due(old_state(5), 0.6, 0.6)[2]["oblasts"]["Kyiv City"]["p1"] == 0.6, "after a gap of 5 h (the Mac slept) the reading only records: those hours are just missed")
    check(ns["origin"] == "2026-10-10T12:00:00Z" and ns["made"] == "2026-10-10T12:37:00Z", "the new state remembers which forecast it saw")


# ------------------------------------------------------------------------------------------------------------------------------ 4 the bot against the fake Telegram
def bot_checks():
    fake_keychain()
    cfgp = conf("[settings]\ncooldown_hours = 3\n[watch]\nм. Київ = 50\nКиївська область = 50\n", "bot.conf")
    d = TMP / "bot"
    d.mkdir(exist_ok=True)
    fcp, stp = d / "last_forecast.json", d / "state.json"
    log, srv = telegram()
    run = lambda *extra, now=NOW: capture(ab.cmd_run, cfgp, fcp, stp, False, now)
    # run 1: nothing known yet
    write_json(fcp, forecast_doc({"Kyiv City": 0.3, "Kyivska oblast": 0.3}))
    ret, out = run()
    check(ret == 0 and sent(log) == [] and "sent 0" in out and json.loads(stp.read_text())["oblasts"]["Kyivska oblast"]["p1"] == 0.3, f"run 1: nothing sent, the state is recorded ({out.strip()})")
    # run 2: Kyivska crosses
    write_json(fcp, forecast_doc({"Kyiv City": 0.3, "Kyivska oblast": 0.61}, made="2026-10-10T13:37:00Z", origin="2026-10-10T13:00:00Z", now_flags={"Kyivska oblast": True}))
    ret, out = run(now=NOW + pd.Timedelta(hours=1))
    msgs = sent(log)
    check(ret == 0 and len(msgs) == 1 and msgs[0]["text"].startswith("Київська область:") and "Тривога на годину прогнозу: так." in msgs[0]["text"] and "Година прогнозу: 16:00 (Київ)." in msgs[0]["text"] and str(msgs[0]["chat_id"]) == SECRETS["telegram_chat"],
          f"run 2: Kyivska 30% to 61%: one message to the right chat ({out.strip()})")
    check("sent 1" in out and json.loads(stp.read_text())["oblasts"]["Kyivska oblast"]["last_sent"] == "2026-10-10T13:40:00Z", "run 2: the state remembers when it was sent")
    # same forecast again
    ret, out = run(now=NOW + pd.Timedelta(hours=1, minutes=5))
    check(ret == 0 and len(sent(log)) == 1 and "already handled" in out, "the same forecast is never handled twice")
    # still above
    write_json(fcp, forecast_doc({"Kyiv City": 0.3, "Kyivska oblast": 0.7}, made="2026-10-10T14:37:00Z", origin="2026-10-10T14:00:00Z"))
    ret, out = run(now=NOW + pd.Timedelta(hours=2))
    check(len(sent(log)) == 1, "run 3: still above, nothing sent")
    # drop and cross again inside the cooldown, then after it
    write_json(fcp, forecast_doc({"Kyiv City": 0.3, "Kyivska oblast": 0.2}, made="2026-10-10T15:37:00Z", origin="2026-10-10T15:00:00Z"))
    run(now=NOW + pd.Timedelta(hours=3))
    write_json(fcp, forecast_doc({"Kyiv City": 0.3, "Kyivska oblast": 0.8}, made="2026-10-10T16:37:00Z", origin="2026-10-10T16:00:00Z"))
    ret, out = run(now=NOW + pd.Timedelta(hours=1, minutes=59, seconds=0) + pd.Timedelta(hours=1))   # 2 h 59 min after the message (13:40)
    check(len(sent(log)) == 1 and "held back by the cooldown 1" in out, f"crossed again 2 h 59 min after the message: held back ({out.strip()})")
    write_json(fcp, forecast_doc({"Kyiv City": 0.3, "Kyivska oblast": 0.2}, made="2026-10-10T17:37:00Z", origin="2026-10-10T17:00:00Z"))
    run(now=NOW + pd.Timedelta(hours=5))
    write_json(fcp, forecast_doc({"Kyiv City": 0.3, "Kyivska oblast": 0.8}, made="2026-10-10T18:37:00Z", origin="2026-10-10T18:00:00Z"))
    ret, out = run(now=NOW + pd.Timedelta(hours=6))
    check(len(sent(log)) == 2, "crossed again after the cooldown: a second message")
    # Kyiv City and Kyivska together: two messages (one per oblast)
    write_json(fcp, forecast_doc({"Kyiv City": 0.3, "Kyivska oblast": 0.2}, made="2026-10-11T00:37:00Z", origin="2026-10-11T00:00:00Z"))
    run(now=NOW + pd.Timedelta(hours=12))
    write_json(fcp, forecast_doc({"Kyiv City": 0.9, "Kyivska oblast": 0.9}, made="2026-10-11T01:37:00Z", origin="2026-10-11T01:00:00Z"))
    ret, out = run(now=NOW + pd.Timedelta(hours=13))
    check(len(sent(log)) == 4 and sent(log)[2]["text"].startswith("м. Київ") and sent(log)[3]["text"].startswith("Київська область"), "both watched oblasts crossing in one run: one message each")
    # stale forecast
    write_json(fcp, forecast_doc({"Kyiv City": 0.9, "Kyivska oblast": 0.9}, made="2026-10-11T01:00:00Z"))
    ret, out = run(now=pd.Timestamp("2026-10-11T01:30:00Z"))
    check(ret == 1 and "stale" in out and len(sent(log)) == 4, f"a forecast made 30 min ago is not used ({out.strip()})")
    ret, out = capture(ab.cmd_run, cfgp, d / "none.json", stp, False, NOW)
    check(ret == 1 and "no forecast" in out, "no forecast file: said so, exit 1")
    stop(srv)
    # a failed send is retried next time
    d2 = TMP / "bot2"
    d2.mkdir(exist_ok=True)
    fcp2, stp2 = d2 / "f.json", d2 / "s.json"
    write_json(stp2, {"version": "frozen-v2-test", "made": "2026-10-10T12:30:00Z", "oblasts": {"Kyiv City": {"p1": 0.3, "last_sent": None}, "Kyivska oblast": {"p1": 0.3, "last_sent": None}}})
    write_json(fcp2, forecast_doc({"Kyivska oblast": 0.7}))
    log500, srv500 = telegram("500")
    ret, out = capture(ab.cmd_run, cfgp, fcp2, stp2, False, NOW)
    s2 = json.loads(stp2.read_text())
    check(ret == 1 and "failed 1" in out and "HTTP 500" in out and s2["oblasts"]["Kyivska oblast"]["p1"] == 0.3 and s2["oblasts"]["Kyivska oblast"]["last_sent"] is None,
          f"Telegram answers 500: reported as a status only, and the oblast keeps its old state ({out.strip()})")
    stop(srv500)
    log2, srv2 = telegram()
    write_json(fcp2, forecast_doc({"Kyivska oblast": 0.7}, made="2026-10-10T12:38:00Z"))
    ret, out = capture(ab.cmd_run, cfgp, fcp2, stp2, False, NOW)
    check(ret == 0 and len(sent(log2)) == 1, "the next run tries again and the message goes out")
    # wrong chat in the keychain: 400; wrong token: 401
    for key, val, code in (("telegram_chat", "999", "400"), ("telegram_token", "FAKE_TG_TOKEN_wrong", "401")):
        fake_keychain({**SECRETS, key: val}, "wrongkc")
        write_json(stp2, {"version": "frozen-v2-test", "made": "2026-10-10T12:30:00Z", "oblasts": {"Kyivska oblast": {"p1": 0.3, "last_sent": None}}})
        write_json(fcp2, forecast_doc({"Kyivska oblast": 0.7}, made="2026-10-10T12:39:00Z"))
        ret, out = capture(ab.cmd_run, cfgp, fcp2, stp2, False, NOW)
        check(ret == 1 and f"HTTP {code}" in out and val not in out, f"a wrong {key.split('_')[1]} in the keychain: only 'HTTP {code}' is reported")
    # missing keychain items
    fake_keychain({"alarm_token": SECRETS["alarm_token"]}, "missingkc")
    write_json(stp2, {"version": "frozen-v2-test", "made": "2026-10-10T12:30:00Z", "oblasts": {"Kyivska oblast": {"p1": 0.3, "last_sent": None}}})
    write_json(fcp2, forecast_doc({"Kyivska oblast": 0.7}, made="2026-10-10T12:39:30Z"))
    ret, out = capture(ab.cmd_run, cfgp, fcp2, stp2, False, NOW)
    check(ret == 1 and "ukraine-air-alerts.telegram-bot-token" in out and "ukraine-air-alerts.telegram-chat-id" in out and json.loads(stp2.read_text())["oblasts"]["Kyivska oblast"]["p1"] == 0.3,
          "missing keychain items: named in the status, nothing sent, the crossing is kept for the next run")
    fake_keychain()
    # no server at all
    stop(srv2)
    os.environ["TELEGRAM_API_BASE"] = f"http://127.0.0.1:{free_port()}"
    write_json(stp2, {"version": "frozen-v2-test", "made": "2026-10-10T12:30:00Z", "oblasts": {"Kyivska oblast": {"p1": 0.3, "last_sent": None}}})
    write_json(fcp2, forecast_doc({"Kyivska oblast": 0.7}, made="2026-10-10T12:39:40Z"))
    ret, out = capture(ab.cmd_run, cfgp, fcp2, stp2, False, NOW)
    check(ret == 1 and "HTTP 0" in out and "127.0.0.1" not in out and "bot" not in out.replace("alert_bot", ""), f"no connection: 'HTTP 0', no address in the output ({out.strip()})")
    # dry run, test, find-chat-id, check
    log3, srv3 = telegram(updates=[{"update_id": 1, "message": {"message_id": 1, "chat": {"id": int(SECRETS["telegram_chat"]), "type": "private", "first_name": "Secret Name"}, "text": "/start"}}])
    write_json(stp2, {"version": "frozen-v2-test", "made": "2026-10-10T12:30:00Z", "oblasts": {"Kyivska oblast": {"p1": 0.3, "last_sent": None}}})
    before = stp2.read_text()
    ret, out = capture(ab.cmd_run, cfgp, fcp2, stp2, True, NOW)
    check(ret == 0 and "Київська область:" in out and sent(log3) == [] and stp2.read_text() == before, "--dry-run prints the message, sends nothing, leaves the state alone")
    ret, out = capture(ab.main, ["--test"])
    check(ret == 0 and len(sent(log3)) == 1 and sent(log3)[0]["text"] == ab.TEST_TEXT and "HTTP 200" in out, "--test sends one test message, needs no forecast")
    ret, out = capture(ab.main, ["--find-chat-id"], _keep=False)
    check(ret == 0 and f"chat id: {SECRETS['telegram_chat']}" in out and "private" in out and "Secret Name" not in out and SECRETS["telegram_token"] not in out and "security add-generic-password" in out and "-w" in out,
          "--find-chat-id prints the chat id (and the keychain command to store it), no name, never the token")
    fake_keychain({"telegram_token": SECRETS["telegram_token"]}, "kc_tokenonly")
    ret, out = capture(ab.main, ["--test"])
    check(ret == 1 and "missing keychain item" in out and len(sent(log3)) == 1, "--test with the chat id missing: says which item, sends nothing")
    stop(srv3)
    log4, srv4 = telegram(updates=[])
    fake_keychain()
    ret, out = capture(ab.main, ["--find-chat-id"])
    check(ret == 1 and "/start" in out, "--find-chat-id with no message to the bot yet: tells you to send /start")
    fake_keychain({**SECRETS, "telegram_token": "FAKE_TG_TOKEN_wrong"}, "kc_wrong")
    ret, out = capture(ab.main, ["--find-chat-id"])
    check(ret == 1 and "HTTP 401" in out and "FAKE_TG_TOKEN_wrong" not in out, "--find-chat-id with a wrong token: 'HTTP 401' only")
    stop(srv4)
    fake_keychain()
    ret, out = capture(ab.main, ["--check", "--config", str(cfgp)])
    check(ret == 0 and out.count("present, readable") == 3 and "MISSING" not in out and "config ok" in out, "--check: config read, the three keychain items present")
    fake_keychain({"telegram_token": "x"}, "kc_partial")
    ret, out = capture(ab.main, ["--check", "--config", str(cfgp)])
    check(ret == 1 and out.count("MISSING") == 2, "--check: two items missing are reported")
    fake_keychain()


# ------------------------------------------------------------------------------------------------------------------------------ 5 secrets
def secret_checks():
    kc_log = "".join(p.read_text() for p in TMP.glob("*.log"))
    lines = [l for l in kc_log.splitlines() if l.strip()]
    check(lines and all(l.startswith(("find-generic-password", "delete-generic-password")) for l in lines), f"the keychain was only asked to find (or, on uninstall, delete) items ({len(lines)} calls)")
    check(all((l.split()[-1] == "-w") or "-w" not in l.split() for l in lines) and not any(s in kc_log for s in SECRETS.values()),
          "every call that asks for a secret ends in a bare '-w': no secret is ever on a command line; no secret appears in the keychain call log")
    blob = "\n".join(OUTPUTS)
    found = [k for k, v in SECRETS.items() if v in blob]
    check(not found, f"nothing printed by the bot, the job or the helpers contains a secret ({len(OUTPUTS)} outputs searched)")
    skip = {"keychain.json", "wrongkc.json", "missingkc.json", "kc_tokenonly.json", "kc_wrong.json", "kc_partial.json", "inst_partial.json", "inst_all.json"}
    allf = [p for p in TMP.rglob("*") if p.is_file() and p.name not in skip and not p.name.startswith("tg_") and not p.is_symlink()]
    leaks = [str(p.relative_to(TMP)) for p in allf if any(v in p.read_bytes().decode("utf-8", "replace") for v in SECRETS.values())]
    check(not leaks, f"no state file, forecast file, page, prediction log or property list written by the checks contains a secret ({len(allf)} files searched)" + (f": {leaks}" if leaks else ""))
    src = {p: p.read_text(encoding="utf-8", errors="replace") for p in list((ROOT / "scripts").glob("*.py")) + list((ROOT / "scripts").glob("*.sh")) + list((ROOT / "src").glob("*.py")) + [ROOT / "config" / "alert_bot.conf"]}
    check(not [p.name for p, t in src.items() if "security add-generic-password" in t and re.search(r"-w\s+[\"'$A-Za-z0-9<]", t.split("security add-generic-password", 1)[1][:120]) and p.name != "check_alert_bot.py"],
          "the only keychain write in the repository is the hint '... -w' (hidden prompt), never '-w <value>'")
    check(not any(w in (ROOT / "config" / "alert_bot.conf").read_text().lower() for w in ("token", "chat_id", "password")) or "keychain" in (ROOT / "config" / "alert_bot.conf").read_text(), "the config file has no secret and says where they are")


# ------------------------------------------------------------------------------------------------------------------------------ 6 the hourly job
def job_checks():
    calls = []
    leak = "SECRETSHOULDNOTBELOGGED"
    old = (hj.run_predict, hj.run_bot)
    try:
        hj.run_predict = lambda: (calls.append("predict") or 0, f"forecast table ... {leak}")
        hj.run_bot = lambda: (calls.append("bot") or 0, f"{leak} line\nalert_bot: checked 2, crossed 1, sent 1, held back by the cooldown 0, failed 0")
        ret, out = capture(hj.main, [])
        check(calls == ["predict", "bot"] and ret == 0 and leak not in out and re.search(r"forecast step: exit 0", out) and "alert step: exit 0; alert_bot: checked 2, crossed 1, sent 1" in out and len(out.strip().splitlines()) == 2,
              f"the job runs the forecast, then the bot, and logs two status lines only: {out.strip().splitlines()[-1][:90]}")
        calls.clear()
        hj.run_predict = lambda: (calls.append("predict") or 1, f"Cannot forecast now {leak}")
        ret, out = capture(hj.main, [])
        check(calls == ["predict"] and ret == 1 and leak not in out and "exit 1" in out and "skipped" in out and len(out.strip().splitlines()) == 1, f"the forecast failed: the bot is not run, only the status is logged ({out.strip()[:90]})")
        calls.clear()
        hj.run_predict = lambda: (calls.append("predict") or 0, "")
        hj.run_bot = lambda: (calls.append("bot") or 1, "alert_bot: checked 2, crossed 1, sent 0, held back by the cooldown 0, failed 1 (Telegram HTTP 500)")
        ret, out = capture(hj.main, [])
        check(ret == 1 and "alert step: exit 1; alert_bot:" in out and "HTTP 500" in out, "a failed message: exit 1 and the bot's status line (a code, nothing else)")
    finally:
        hj.run_predict, hj.run_bot = old
    pl = plistlib.loads(subprocess.run([sys.executable, str(ROOT / "scripts" / "hourly_job.py"), "--print-plist", "--python", "/x/.venv/bin/python"], capture_output=True).stdout)
    xml = plistlib.dumps(pl).decode().lower()
    check(pl["Label"] == "local.ukraine-air-alerts.hourly" and pl["ProgramArguments"] == ["/x/.venv/bin/python", str(ROOT / "scripts" / "hourly_job.py")] and pl["StartCalendarInterval"] == {"Minute": 7}
          and pl["WorkingDirectory"] == str(ROOT) and set(pl["EnvironmentVariables"]) == {"PATH"} and pl["StandardOutPath"].endswith("ukraine-air-alerts/hourly.log"),
          "the launchd property list: every hour at minute 7, this repository, a status log under ~/Library/Logs, only PATH in the environment")
    check(not any(w in xml for w in ("token", "chat", "secret", "password", "ukraine-air-alerts.telegram", "-w")) and "runatload" in xml and pl["RunAtLoad"] is False, "no secret, no keychain item and no token option in the property list; it does not run at load")
    check(subprocess.run(["bash", "-n", str(ROOT / "scripts" / "install_hourly.sh")]).returncode == 0 and subprocess.run(["bash", "-n", str(ROOT / "scripts" / "uninstall_hourly.sh")]).returncode == 0, "both shell scripts parse (bash -n)")
    pred = (ROOT / "scripts" / "hourly_job.py").read_text()
    check("--token-from-keychain" in pred and "--now" in pred and "shell=True" not in pred, "the forecast step is predict.py --now --token-from-keychain, run without a shell")


# ------------------------------------------------------------------------------------------------------------------------------ 7 install / uninstall
def install_checks():
    home = TMP / "home"
    repo = TMP / "repo"
    (repo / ".venv" / "bin").mkdir(parents=True, exist_ok=True)
    (repo / ".venv" / "bin" / "python").symlink_to(sys.executable)
    (repo / "scripts").symlink_to(ROOT / "scripts") if not (repo / "scripts").exists() else None
    fakebin = TMP / "fakebin"
    fakebin.mkdir(exist_ok=True)
    lc_log = TMP / "launchctl.calls"
    (fakebin / "launchctl").write_text(f"#!/bin/bash\necho \"$@\" >> {lc_log}\nexit 0\n")
    (fakebin / "security").write_text(f"#!/bin/bash\nexec {sys.executable} {ROOT}/scripts/fakes/fake_security.py \"$@\"\n")
    for f in fakebin.iterdir():
        f.chmod(0o755)
    env = {**os.environ, "USER": os.environ.get("USER", "tester"), "HOME": str(home), "PATH": f"{fakebin}:/usr/bin:/bin", "ALERT_SECURITY_BIN": str(ROOT / "scripts" / "fakes" / "fake_security.py")}
    fake_keychain({"telegram_token": "a", "telegram_chat": "b"}, "inst_partial")
    env.update(FAKE_KEYCHAIN=os.environ["FAKE_KEYCHAIN"], FAKE_KEYCHAIN_LOG=os.environ["FAKE_KEYCHAIN_LOG"])
    r = subprocess.run(["bash", str(repo / "scripts" / "install_hourly.sh")], capture_output=True, text=True, env=env)
    plist_path = home / "Library" / "LaunchAgents" / "local.ukraine-air-alerts.hourly.plist"
    check(r.returncode == 1 and not plist_path.exists() and not (lc_log.exists() and "bootstrap" in lc_log.read_text()) and "MISSING" in r.stdout, "install with a keychain item missing: refuses, installs nothing")
    fake_keychain({"telegram_token": "a", "telegram_chat": "b", "alarm_token": "c"}, "inst_all")
    env.update(FAKE_KEYCHAIN=os.environ["FAKE_KEYCHAIN"], FAKE_KEYCHAIN_LOG=os.environ["FAKE_KEYCHAIN_LOG"])
    r = subprocess.run(["bash", str(repo / "scripts" / "install_hourly.sh")], capture_output=True, text=True, env=env)
    calls = lc_log.read_text().splitlines() if lc_log.exists() else []
    uid = str(os.getuid())
    pl = plistlib.loads(plist_path.read_bytes()) if plist_path.exists() else {}
    check(r.returncode == 0 and pl.get("ProgramArguments", [""])[0] == str(repo / ".venv" / "bin" / "python") and calls[-2:] == [f"bootout gui/{uid}/local.ukraine-air-alerts.hourly", f"bootstrap gui/{uid} {plist_path}"]
          and (home / "Library" / "Logs" / "ukraine-air-alerts").is_dir(), f"install with everything in place: the property list is written, the old job is booted out and the new one bootstrapped ({calls[-2:]})")
    r2 = subprocess.run(["bash", str(repo / "scripts" / "uninstall_hourly.sh")], capture_output=True, text=True, env=env)
    check(r2.returncode == 0 and not plist_path.exists() and f"bootout gui/{uid}/local.ukraine-air-alerts.hourly" in lc_log.read_text().splitlines()[-1], "uninstall: the job is booted out and the property list removed")
    open(os.environ["FAKE_KEYCHAIN_LOG"], "w").close()
    r3 = subprocess.run(["bash", str(repo / "scripts" / "uninstall_hourly.sh"), "--delete-secrets"], capture_output=True, text=True, env=env)
    kl = Path(os.environ["FAKE_KEYCHAIN_LOG"]).read_text().splitlines()
    check(r3.returncode == 0 and len([l for l in kl if l.startswith("delete-generic-password")]) == 3 and r3.stdout.count("Deleted keychain item") == 3, "uninstall --delete-secrets also deletes the three keychain items (and only then)")
    check("Deleted" not in r2.stdout, "plain uninstall leaves the keychain alone")
    OUTPUTS.extend([r.stdout, r.stderr, r2.stdout, r2.stderr, r3.stdout, r3.stderr])


# ------------------------------------------------------------------------------------------------------------------------------ 8 end to end
def end_to_end():
    if not (ROOT / "models" / "v2" / "info.json").exists() or not (ROOT / "data" / "api_archive" / "date_history" / "20261010.json").exists():
        print("skip  end to end: models/v2 or the saved API days are not there")
        return
    import numpy as np
    import src.ukrainealarm as ua
    import scripts.archive_api as arch
    import scripts.forecast_map as fm
    import scripts.live_api as live
    import scripts.predict as predict
    fake_keychain()
    alarm_port, alarm = start("fake_alarm_api.py", {"AS_OF": "2026-10-10 12:37"})
    log, tg = telegram()
    os.environ["UA_ALARM_BASE"] = f"http://127.0.0.1:{alarm_port}"
    os.environ.pop("UA_ALARM_TOKEN", None)  # the token must come from the keychain
    M = pd.Timestamp("2026-10-10 12:37", tz="UTC")
    work = TMP / "e2e"
    arc = work / "api_archive"
    (arc / "date_history").mkdir(parents=True)
    for f in sorted((ROOT / "data/api_archive/date_history").glob("*.json")):
        if "20260908" <= f.stem <= "20261004":
            shutil.copy(f, arc / "date_history" / f.name)
    orig_steps = (hj.run_predict, hj.run_bot)
    saved = (ua.Client.__init__.__defaults__, arch.OUT, live.ARCHIVE, live.now_utc, live.PRED_LOG, live.LAST_FORECAST, fm.OUT)
    ua.Client.__init__.__defaults__ = (0.0, None)
    arch.OUT, live.ARCHIVE, live.now_utc = arc, arc / "date_history", lambda: M
    live.PRED_LOG, live.LAST_FORECAST, fm.OUT = work / "predictions" / "log.csv", work / "last_forecast.json", work / "output" / "forecast_map.html"
    cfgp = conf("[settings]\ncooldown_hours = 3\n[watch]\nм. Київ = 50\nКиївська область = 50\nХарківська = 30\n", "e2e.conf")
    stp = work / "alert_state.json"
    try:
        def predict_step():
            sys.argv = ["predict.py", "--now", "--token-from-keychain"]
            ret, out = capture(predict.main)
            return (ret or 0), out

        def bot_step():
            ret, out = capture(ab.cmd_run, cfgp, live.LAST_FORECAST, stp, False, M + pd.Timedelta(minutes=2))
            return ret, out
        hj.run_predict, hj.run_bot = predict_step, bot_step
        ret, out = capture(hj.main, [])
        doc = json.loads(live.LAST_FORECAST.read_text(encoding="utf-8"))
        check(ret == 0 and "forecast step: exit 0" in out and "alert step: exit 0" in out and doc["origin"] == "2026-10-10T12:00:00Z" and doc["made"] == "2026-10-10T12:37:00Z" and doc["version"].startswith("frozen-v2-")
              and len(doc["rows"]) == 24 and fm.OUT.exists(), f"the job ran: the forecast (token from the fake keychain), last_forecast.json, the page, then the bot ({out.strip().splitlines()[-1][:100]})")
        check(sent(log) == [] and stp.exists(), "first run: nothing sent, the state recorded")
        rows = {r["oblast"]: r for r in doc["rows"]}
        # make the watched oblasts "below" in the state, as if the previous hour had been quiet, then run the bot on the same forecast again (a new made time)
        state = json.loads(stp.read_text())
        for o in state["oblasts"]:
            state["oblasts"][o]["p1"] = 0.01
        write_json(stp, state)
        doc["made"] = "2026-10-10T12:38:00Z"
        write_json(live.LAST_FORECAST, doc)
        ret, out = capture(ab.cmd_run, cfgp, live.LAST_FORECAST, stp, False, M + pd.Timedelta(minutes=3))
        want = [o for o, thr in (("Kyiv City", 0.5), ("Kyivska oblast", 0.5), ("Kharkivska oblast", 0.3)) if rows[o]["p"]["1"] >= thr]
        got = sent(log)
        check([m["text"].split(":")[0] for m in got] == [ab.full_name(o, "uk") for o in want] and want, f"the real forecast crosses for {want}: exactly those messages arrived ({[m['text'].split(':')[0] for m in got]})")
        for m, o in zip(got, want):
            p = {int(h): v for h, v in rows[o]["p"].items()}
            check(m["text"] == ab.message(o, {"Kyiv City": 0.5, "Kyivska oblast": 0.5, "Kharkivska oblast": 0.3}[o], p, rows[o]["now"], pd.Timestamp(doc["origin"])) and f"{100 * p[1]:.0f}%" in m["text"] and "Година прогнозу: 15:00 (Київ)." in m["text"],
                  f"the message for {ab.full_name(o, 'uk')} carries the forecast's own numbers and the origin hour 15:00 Kyiv time")
        check(not LONG_DASH.search("".join(m["text"] for m in got)), "no long dash in what was sent")
        # the page the job wrote
        page = fm.OUT.read_text(encoding="utf-8")
        check(SECRETS["alarm_token"] not in page and SECRETS["telegram_token"] not in page, "the page holds no secret")
    finally:
        hj.run_predict, hj.run_bot = orig_steps
        (ua.Client.__init__.__defaults__, arch.OUT, live.ARCHIVE, live.now_utc, live.PRED_LOG, live.LAST_FORECAST, fm.OUT) = saved
        stop(alarm)
        stop(tg)


def cleanup():
    for p in PROCS:
        if p.poll() is None:
            stop(p)


if __name__ == "__main__":
    original = (hj.run_predict, hj.run_bot)
    try:
        config_checks()
        message_checks()
        rule_checks()
        bot_checks()
        job_checks()
        install_checks()
        hj.run_predict, hj.run_bot = original
        end_to_end()
        secret_checks()
    finally:
        hj.run_predict, hj.run_bot = original
        cleanup()
    print()
    print("alert bot checks: " + ("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED"))
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1 if FAILS else 0)
