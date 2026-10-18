"""Personal Telegram alert bot: after a `predict.py --now` forecast, a message when an oblast of your watch list crosses its threshold for the next hour.

    python scripts/alert_bot.py                 read output/last_forecast.json (written by predict.py --now), send what is due
    python scripts/alert_bot.py --dry-run       the same, but print the messages instead of sending them and do not touch the state
    python scripts/alert_bot.py --test          send one test message (no forecast needed)
    python scripts/alert_bot.py --find-chat-id  print the chat id(s) that wrote to your bot (send it /start first); the token is never printed
    python scripts/alert_bot.py --check         read the config and see which keychain items exist (nothing is sent, no secret is read)

The rule (config/alert_bot.conf, edit it freely; defaults: м. Київ and Київська область at 50%): for each watched oblast, the probability of a new alert within 1 hour in the last
forecast against the one the bot saw the previous time (output/alert_state.json). A message is sent only when it went from BELOW the threshold to AT OR ABOVE it. Nothing while it
stays above or below; at most one message per oblast per cooldown_hours (default 3); the first observation of an oblast (after the model changed, or after a gap of more than 2.5 hours because the Mac slept) only records it. A message that
could not be sent leaves the oblast's earlier state alone, so the next run tries again. A forecast older than 20 minutes (the --now step failed) is not used, and the same forecast
is never handled twice. The message is Ukrainian, short: oblast, 1/3/6 h in percent, whether an alert is running at the origin hour, the origin hour in Kyiv time, and the
line that this is a study model.

Secrets (src/keychain.py): the Telegram bot token and chat id come only from the macOS keychain, in memory, and are never printed, written or put on a command line. What this
script prints is status only (counts and HTTP status codes), because it runs unattended and its output goes to a log.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src import keychain
from src.i18n import OBLAST_UK, full_name, short_name
from src.tg import Telegram

CONFIG = ROOT / "config" / "alert_bot.conf"
FORECAST = ROOT / "output" / "last_forecast.json"
STATE = ROOT / "output" / "alert_state.json"
MAX_AGE = pd.Timedelta(minutes=20)  # a forecast made longer ago than this is not used
MAX_GAP = pd.Timedelta(hours=2, minutes=30)  # the previous reading of an oblast counts only if it is at most this much older than the forecast (a Mac that slept: those hours are just missed)
HORIZONS = (1, 3, 6)
LINE_STUDY = "Навчальна модель, слідкуйте за офіційними тривогами."
TEST_TEXT = "Тестове повідомлення: бот працює і може писати в цей чат. " + LINE_STUDY


class ConfigError(Exception):
    pass


# ---------------------------------------------------------------------------------------------------------------- config
def name_lookup():
    """Every way of writing an oblast that the config accepts -> our unit name: Ukrainian full and short ("Київська область", "Київська", "м. Київ", "Київ"), English ("Kyivska oblast", "Kyivska", "Kyiv City", "Kyiv")."""
    out = {}
    for ours in OBLAST_UK:
        for text in {ours, ours.replace(" oblast", ""), full_name(ours, "uk"), short_name(ours, "uk")}:
            out.setdefault(text.lower().strip(), ours)
    out["київ"] = "Kyiv City"
    out["kyiv"] = "Kyiv City"
    return out


def load_config(path=None):
    """{"cooldown": hours, "watch": [(our unit name, threshold as a probability, the name as written)]}; ConfigError with every problem found."""
    import configparser
    path = Path(path or CONFIG)
    if not path.exists():
        raise ConfigError([f"{path} does not exist"])
    cp = configparser.RawConfigParser(inline_comment_prefixes=None)
    cp.optionxform = str  # keep the names as written
    try:
        cp.read(path, encoding="utf-8")
    except configparser.Error:
        raise ConfigError(["the config file cannot be read (a line without name = value?)"])
    problems, watch = [], []
    cool = 3.0
    if cp.has_option("settings", "cooldown_hours"):
        try:
            cool = float(cp.get("settings", "cooldown_hours"))
            if cool < 0:
                raise ValueError
        except ValueError:
            problems.append("cooldown_hours must be a number of hours, 0 or more")
    if not cp.has_section("watch") or not cp.items("watch"):
        problems.append("[watch] is empty: add lines like  м. Київ = 50")
    lookup = name_lookup()
    seen = set()
    for key, value in (cp.items("watch") if cp.has_section("watch") else []):
        ours = lookup.get(key.lower().strip())
        if ours is None:
            problems.append(f'unknown oblast "{key}" (use e.g. м. Київ, Київська область, Kharkivska)')
            continue
        try:
            thr = float(value.strip().rstrip("%").replace(",", ".")) / 100
            if not 0 < thr <= 1:
                raise ValueError
        except ValueError:
            problems.append(f'"{key}": the threshold must be a percent between 0 and 100 (got "{value}")')
            continue
        if ours in seen:
            problems.append(f'"{key}" is listed twice')
            continue
        seen.add(ours)
        watch.append((ours, thr, key))
    if problems:
        raise ConfigError(problems)
    return {"cooldown": cool, "watch": watch}


# ---------------------------------------------------------------------------------------------------------------- message
def pct(p):
    return f"{100 * p:.0f}%"


def thr_text(thr):
    """The configured threshold as written in the message: 50%, 37,5%."""
    return f"{100 * thr:g}".replace(".", ",") + "%"


def message(oblast, thr, p, now_flag, origin):
    """The Ukrainian message for one oblast. p: {1: ., 3: ., 6: .}; origin: a Timestamp."""
    kyiv = pd.Timestamp(origin).tz_convert("Europe/Kyiv")
    return "\n".join([
        f"{full_name(oblast, 'uk')}: ймовірність нової тривоги протягом 1 год перейшла поріг {thr_text(thr)}.",
        "Протягом " + ", ".join(f"{h} год: {pct(p[h])}" for h in HORIZONS) + ".",
        f"Тривога на годину прогнозу: {'так' if now_flag else 'ні'}.",
        f"Година прогнозу: {kyiv:%H:%M} (Київ).",
        LINE_STUDY])


# ---------------------------------------------------------------------------------------------------------------- state and decision
def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_json(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def decide(cfg, forecast, state, now):
    """What is due. Returns (due, suppressed, new_state): `due` = [(oblast, threshold, text)] to send; `suppressed` = [oblast] that crossed inside the cooldown. new_state has the
    probabilities of this forecast for every watched oblast (the caller keeps an oblast's old entry if its message could not be sent)."""
    rows = {r["oblast"]: r for r in forecast["rows"]}
    origin = pd.Timestamp(forecast["origin"])
    old = state.get("oblasts", {}) if state and state.get("version") == forecast["version"] else {}
    if old and state.get("made"):  # a reading from long ago (the Mac slept, runs were missed) is not a "before": the first reading after a gap only records
        gap = pd.Timestamp(forecast["made"]) - pd.Timestamp(state["made"])
        if gap > MAX_GAP or gap < pd.Timedelta(0):
            old = {}
    last_sent_all = {k: v.get("last_sent") for k, v in (state or {}).get("oblasts", {}).items()}
    cool = pd.Timedelta(hours=cfg["cooldown"])
    due, suppressed, new = [], [], {}
    for oblast, thr, _ in cfg["watch"]:
        r = rows.get(oblast)
        if r is None:
            continue
        p = {int(h): v for h, v in r["p"].items()}
        prev = old.get(oblast, {}).get("p1")
        last = last_sent_all.get(oblast)
        new[oblast] = {"p1": p[1], "last_sent": last}
        if prev is not None and prev < thr <= p[1]:
            if last is not None and pd.Timestamp(now) - pd.Timestamp(last) < cool:
                suppressed.append(oblast)
            else:
                due.append((oblast, thr, message(oblast, thr, p, r["now"], origin)))
    return due, suppressed, {"version": forecast["version"], "made": forecast["made"], "origin": forecast["origin"], "oblasts": new}


# ---------------------------------------------------------------------------------------------------------------- commands
def credentials(need_chat=True):
    token = keychain.get("telegram_token")
    chat = keychain.get("telegram_chat") if need_chat else None
    missing = [keychain.SERVICES[k] for k, v in (("telegram_token", token), ("telegram_chat", chat if need_chat else "x")) if not v]
    return token, chat, missing


def chat_value(chat):
    return int(chat) if chat.lstrip("-").isdigit() else chat


def cmd_test():
    token, chat, missing = credentials()
    if missing:
        print("alert_bot: test not sent, missing keychain item(s): " + ", ".join(missing))
        return 1
    status = Telegram(token).send_message(chat_value(chat), TEST_TEXT)
    print(f"alert_bot: test message, Telegram HTTP {status}" + (" (sent)" if status == 200 else " (not sent)"))
    return 0 if status == 200 else 1


def cmd_find_chat_id():
    token = keychain.get("telegram_token")
    if not token:
        print(f"alert_bot: missing keychain item {keychain.SERVICES['telegram_token']} (put the bot token there first)")
        return 1
    status, chats = Telegram(token).chats_seen()
    if status != 200:
        print(f"alert_bot: Telegram HTTP {status}")
        return 1
    if not chats:
        print("alert_bot: nobody has written to the bot yet. Open the bot in Telegram, send it /start, then run this again.")
        return 1
    for cid, kind in chats:
        print(f"chat id: {cid}  ({kind})")
    print(f"Put it in the keychain (type it at the hidden prompt):\n  security add-generic-password -a \"$USER\" -s {keychain.SERVICES['telegram_chat']} -w")
    return 0


def cmd_check(config):
    ok = True
    try:
        cfg = load_config(config)
        print(f"config ok: cooldown {cfg['cooldown']:g} h; watching " + ", ".join(f"{full_name(o, 'uk')} at {100 * t:g}%" for o, t, _ in cfg["watch"]))
    except ConfigError as e:
        ok = False
        for p in e.args[0]:
            print("config problem: " + p)
    for key, service in keychain.SERVICES.items():
        here = keychain.present(key)
        readable = here and bool(keychain.get(key))  # reads the secret into memory and drops it; the first time macOS may ask you to allow it: choose "Always Allow"
        ok &= readable
        print(f"keychain {service}: " + ("present, readable" if readable else "present but NOT readable (macOS may need your permission: run this in Terminal and choose Always Allow)" if here else "MISSING"))
    return 0 if ok else 1


def cmd_run(config, forecast_path, state_path, dry_run, now=None):
    try:
        cfg = load_config(config)
    except ConfigError as e:
        print("alert_bot: config problem: " + "; ".join(e.args[0]))
        return 1
    fc = load_json(forecast_path)
    if not fc or "rows" not in fc:
        print("alert_bot: no forecast to read (output/last_forecast.json)")
        return 1
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    age = now - pd.Timestamp(fc["made"])
    if age > MAX_AGE:
        print(f"alert_bot: the forecast is stale (made {age.total_seconds() / 60:.0f} min ago), nothing sent")
        return 1
    state = load_json(state_path) or {}
    if state.get("made") == fc["made"] and not dry_run:
        print("alert_bot: this forecast was already handled")
        return 0
    due, suppressed, new_state = decide(cfg, fc, state, now)
    if dry_run:
        for oblast, thr, text in due:
            print(f"--- would send for {full_name(oblast, 'uk')}:\n{text}")
        print(f"alert_bot (dry run): checked {len(cfg['watch'])}, due {len(due)}, held back by the cooldown {len(suppressed)}")
        return 0
    sent, failed, codes = 0, 0, []
    if due:
        token, chat, missing = credentials()
        if missing:
            print("alert_bot: cannot send, missing keychain item(s): " + ", ".join(missing))
            failed = len(due)
            for oblast, _, _ in due:  # try again next run: keep the earlier state of this oblast
                new_state["oblasts"][oblast] = {**new_state["oblasts"][oblast], "p1": (state.get("oblasts", {}).get(oblast) or {}).get("p1", new_state["oblasts"][oblast]["p1"])}
            save_json(state_path, new_state)
            return 1
        tg = Telegram(token)
        for oblast, thr, text in due:
            status = tg.send_message(chat_value(chat), text)
            if status == 200:
                sent += 1
                new_state["oblasts"][oblast]["last_sent"] = f"{now:%Y-%m-%dT%H:%M:%SZ}"
            else:
                failed += 1
                codes.append(status)
                prev = (state.get("oblasts", {}).get(oblast) or {}).get("p1")
                if prev is not None and state.get("version") == fc["version"]:
                    new_state["oblasts"][oblast]["p1"] = prev  # still "below": the next run crosses again and tries again
    save_json(state_path, new_state)
    print(f"alert_bot: checked {len(cfg['watch'])}, crossed {len(due) + len(suppressed)}, sent {sent}, held back by the cooldown {len(suppressed)}, failed {failed}"
          + (f" (Telegram HTTP {', '.join(map(str, codes))})" if codes else ""))
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Personal Telegram alert bot: a message when a watched oblast crosses its threshold for the next hour.")
    ap.add_argument("--test", action="store_true", help="send one test message and nothing else")
    ap.add_argument("--find-chat-id", action="store_true", help="print the chat id(s) that wrote to your bot (the bot token comes from the keychain and is never printed)")
    ap.add_argument("--check", action="store_true", help="read the config and report which keychain items exist")
    ap.add_argument("--dry-run", action="store_true", help="print the messages that would be sent; send nothing, change nothing")
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--forecast", default=str(FORECAST))
    ap.add_argument("--state", default=str(STATE))
    a = ap.parse_args(argv)
    if a.test:
        return cmd_test()
    if a.find_chat_id:
        return cmd_find_chat_id()
    if a.check:
        return cmd_check(a.config)
    return cmd_run(a.config, a.forecast, a.state, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
