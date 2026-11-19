"""Compare tattlescan runs against the answer key.

Usage: python src/compare_tattlescan.py results/RUN1.jsonl [results/RUN2.jsonl ...]
"""

import json
import math
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
UNQUOTED = {"gpt-5:12:3", "gpt-5:37:0"}


def wilson(k, n, z=1.96):
    if not n:
        return "-"
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return f"{round(100 * (c - h))}-{round(100 * (c + h))}%"


def groups(rows):
    fresh = [r for r in rows if r["set"] == "fresh"]
    pos = [r for r in fresh if r["label"] == 1]
    return {
        "real mistakes (17)": pos,
        "  wrong amount, price quoted (10)": [r for r in pos if r["type"] == "amount" and r["id"] not in UNQUOTED],
        "  wrong amount, price never said (2)": [r for r in pos if r["id"] in UNQUOTED],
        "  wrong details (4)": [r for r in pos if r["type"] == "details"],
        "  no consent (1)": [r for r in pos if r["type"] == "no_consent"],
        "planted wrong amount (60)": [r for r in rows if r["set"] == "planted"],
        "FALSE ALARMS on fine chats (117)": [r for r in fresh if r["label"] == 0],
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    review = {i["id"]: i for i in json.load(open(ROOT / "results/fresh_human_review.json", encoding="utf-8"))["items"]}
    runs = {pathlib.Path(p).stem: [json.loads(l) for l in open(p, encoding="utf-8")] for p in sys.argv[1:]}
    table = defaultdict(dict)
    for name, rows in runs.items():
        for g, rs in groups(rows).items():
            k, n, empty = sum(r["verdict"] is True for r in rs), sum(r["verdict"] is not None for r in rs), sum(r["verdict"] is None for r in rs)
            table[g][name] = f"{k}/{n} ({100 * k / n:.0f}%, {wilson(k, n)})" + (f" +{empty} empty" if empty else "") if n else "-"
    print(f"{'':40}" + "".join(f"{n:36}" for n in runs))
    for g, cells in table.items():
        print(f"{g:40}" + "".join(f"{cells[n]:36}" for n in runs))
    for name, rows in runs.items():
        caught = [r for r in rows if r["set"] == "fresh" and r["label"] == 1 and r["verdict"] and r["id"] in review]
        right = sum(r["direction"] == review[r["id"]]["direction"] for r in caught)
        by_bot = defaultdict(lambda: [0, 0])
        for r in rows:
            if r["set"] == "fresh" and r["label"] == 0:
                bot = r["id"].split(":")[0]
                by_bot[bot][0] += r["verdict"] is True
                by_bot[bot][1] += 1
        print(f"\n{name}: direction matches your review on {right}/{len(caught)} caught real mistakes; "
              f"false alarms by bot: " + ", ".join(f"{b} {k}/{n}" for b, (k, n) in sorted(by_bot.items())))
        print("  caught:", sorted(r["id"] for r in rows if r["set"] == "fresh" and r["label"] == 1 and r["verdict"]))


if __name__ == "__main__":
    main()
