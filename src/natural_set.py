"""Q4: natural (unplanted) test set -> data/natural_set.jsonl

26 real mismatches from data/natural_labels.jsonl, the same number of "hard" fine chats (judged fine there,
but flagged by select_clean.py or a failed task), and the same number of clean chats never used by any run.
"""

import json
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEED = 0


def main():
    convs = {c["id"]: c for c in map(json.loads, open(ROOT / "data" / "conversations.jsonl", encoding="utf-8"))}
    labels = [json.loads(l) for l in open(ROOT / "data" / "natural_labels.jsonl", encoding="utf-8")]
    # clean chats never shown to the monitor in any run (as themselves or as a planted copy)
    used = {json.loads(l)["id"].split("|")[0] for p in (ROOT / "results").glob("*.jsonl")
            for l in open(p, encoding="utf-8")}

    pos = [l for l in labels if l["label"] == 1]
    rng = random.Random(SEED)
    hard = rng.sample(sorted((l for l in labels if l["label"] == 0), key=lambda l: l["id"]), len(pos))
    clean_pool = sorted(c for c, v in convs.items() if v["clean"] and v["has_write"] and c not in used)
    clean = rng.sample(clean_pool, len(pos))

    rows = ([(l["id"], 1, "natural_mismatch", l["evidence"]) for l in pos]
            + [(l["id"], 0, "natural_hard_fine", l["evidence"]) for l in hard]
            + [(c, 0, "natural_clean", None) for c in clean])
    with open(ROOT / "data" / "natural_set.jsonl", "w", encoding="utf-8") as f:
        for cid, label, mtype, note in rows:
            c = convs[cid]
            f.write(json.dumps({"id": f"{cid}|natural", "source_id": cid, "task_id": c["task_id"],
                                "source_model": c["source_model"], "label": label, "mtype": mtype, "edit": None,
                                "edit_at": None, "label_note": note, "messages": c["messages"]}, ensure_ascii=False) + "\n")
    print(f"natural set: {len(pos)} mismatches, {len(hard)} hard fine, {len(clean)} clean (pool {len(clean_pool)})")


if __name__ == "__main__":
    main()
