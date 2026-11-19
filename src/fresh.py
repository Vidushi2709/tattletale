"""Unseen tau2 airline runs (data/fresh/raw) -> data/fresh/conversations.jsonl, same checks as select_clean.py.
Used only to test check 5 (MONEY_CHECK), which was written from the original 26 natural mismatches."""

import json
import sys
from collections import Counter

from select_clean import ROOT, check, normalise

FRESH = ROOT / "data" / "fresh"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    convs = []
    for path in sorted((FRESH / "raw").glob("*_airline.json")):
        model = path.name.removesuffix("_airline.json")
        convs += [normalise(s, model) for s in json.loads(path.read_text(encoding="utf-8"))["simulations"]
                  if s.get("reward_info")]
    for c in convs:
        check(c)
    with (FRESH / "conversations.jsonl").open("w", encoding="utf-8") as f:
        for c in convs:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    writers = [c for c in convs if c["has_write"]]
    print(f"total {len(convs)}, with a write {len(writers)}, clean {sum(c['clean'] for c in convs)}")
    print("reject reasons:", dict(Counter(r for c in convs for r in c["reject_reasons"])))
    print("quote_mismatch by model:", dict(Counter(c["source_model"] for c in writers if "quote_mismatch" in c["reject_reasons"])))


if __name__ == "__main__":
    main()
