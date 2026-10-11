"""Human check of the Telegram parser: 50 random posts with the oblasts assigned, the words that triggered them
and the threat flags, then every post containing a substring trap, then coverage.

    python scripts/telegram_parser_check.py [--csv path] [--n 50] [--seed 0]

Writes results/telegram/parser_check_50.md.
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.telegram_features import POSTS_CSV, THREATS, load_posts
from src.telegram_oblasts import explain

SHORT = lambda u: u.replace(" oblast", "").replace("Kyivska", "Kyiv obl.")
TRAPS = [("поділ", "Podilskyi / Podilsk: the old bug sent it to Lviv; no unit may come from 'поділ' alone"),
         ("прилуц", "Pryluky is Chernihiv: the old bug sent 'прилуцький' to Volyn (via 'луцьк')"),
         ("луцьк", "Lutsk (Volyn), and 'луцьк' inside other words"),
         ("київ", "Kyiv city vs Kyiv oblast"), ("дніпр", "Dnipro city / river / Kyiv district"),
         ("хмельницьк", "Khmelnytskyi vs Pereiaslav-Khmelnytskyi"), ("франківськ", "Ivano-Frankivsk")]


def row(p):
    hits = explain(p["text"])
    units = ", ".join(sorted({SHORT(u) for u, _ in hits})) or "-"
    why = ", ".join(sorted({f"{w}→{SHORT(u)}" for u, w in hits})) or ""
    flags = ",".join(n[3:] for n in THREATS if p[n]) or "-"
    text = p["text"].replace("|", "/")
    return f"| {p['id']} | {p['time'].strftime('%m-%d %H:%M')} | {text[:150]} | {units} | {why} | {flags} |"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(POSTS_CSV))
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    posts = load_posts(args.csv)
    head = "| id | UTC | text (first 150 chars) | oblasts assigned | triggered by | threat flags |\n|---|---|---|---|---|---|"
    sample = posts.sample(args.n, random_state=args.seed).sort_values("id")
    lines = [f"# Parser check: {args.n} random posts (seed {args.seed}) of {len(posts)}, "
             f"{posts['time'].min():%Y-%m-%d} .. {posts['time'].max():%Y-%m-%d}", "", head] + [row(p) for _, p in sample.iterrows()]
    lines += ["", "# Substring traps: every post containing the string (up to 12 each), with what the parser assigned", ""]
    for needle, why in TRAPS:
        hit = posts[posts["text"].str.lower().str.contains(needle, regex=False)]
        lines += [f"## '{needle}': {len(hit)} posts. {why}", "", head] + [row(p) for _, p in hit.head(12).iterrows()] + [""]
    none = posts[posts["units"].map(len) == 0]
    words = Counter(w for t in none["text"].str.lower() for w in set(re.findall(r"[а-яіїєґ'’]{5,}", t)))
    lines += ["# Coverage", "",
              f"- posts naming at least one oblast: {len(posts) - len(none)} of {len(posts)} ({1 - len(none) / len(posts):.1%})",
              f"- units per post: {dict(posts['units'].map(len).value_counts().sort_index())}",
              f"- threat flags (share of posts): " + ", ".join(f"{n[3:]} {posts[n].mean():.1%}" for n in THREATS),
              f"- most common words in the {len(none)} posts naming no oblast: {sorted(words.items(), key=lambda kv: (-kv[1], kv[0]))[:40]}"]
    out = ROOT / "results" / "telegram" / "parser_check_50.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
