"""Run the tattlescan `saydo` scanner on the planted wrong-amount chats and the labelled fresh chats -> results/<run>.jsonl

Usage: python src/score_tattlescan.py --run NAME [--n 5] [--model M --provider P --quant Q --max-tokens N --env FILE]
       python src/score_tattlescan.py --run NAME --retry      (re-asks only the chats in results/NAME.jsonl with no answer)
"""

import argparse
import asyncio
import json
import os
import pathlib
import random
import shutil
import sys
import urllib.request
from collections import Counter

from inspect_ai.model import ChatMessageAssistant, ChatMessageTool, ChatMessageUser, GenerateConfig, get_model
from inspect_ai.tool import ToolCall
from inspect_scout import Transcript, scan, scan_results_df, transcripts_db, transcripts_from

from tattlescan import saydo

ROOT = pathlib.Path(__file__).resolve().parent.parent


def rows():
    labels = {json.loads(l)["id"]: json.loads(l) for l in open(ROOT / "data/fresh/natural_labels.jsonl", encoding="utf-8")}
    for l in open(ROOT / "data/fresh/conversations.jsonl", encoding="utf-8"):
        c = json.loads(l)
        if c["id"] in labels:
            lab = labels[c["id"]]
            yield {"id": c["id"], "set": "fresh", "label": lab["label"], "type": lab["type"],
                   "model": c["source_model"], "messages": c["messages"]}
    for l in open(ROOT / "data/eval_wrong_amount.jsonl", encoding="utf-8"):
        r = json.loads(l)
        yield {"id": r["id"], "set": "planted", "label": 1, "type": "amount", "model": r["source_model"],
               "messages": r["messages"]}


def to_messages(msgs):
    out, pending = [], []
    for i, m in enumerate(msgs):
        if m["role"] == "assistant":
            calls = [ToolCall(id=f"c{i}_{j}", function=c["name"], arguments=c["arguments"])
                     for j, c in enumerate(m.get("tool_calls") or [])]
            pending = [c.id for c in calls]
            out.append(ChatMessageAssistant(content=m["content"] or "", tool_calls=calls or None))
        elif m["role"] == "user":
            out.append(ChatMessageUser(content=m["content"] or ""))
        elif m["role"] == "tool":
            out.append(ChatMessageTool(content=m["content"] or "", tool_call_id=pending.pop(0) if pending else None))
    return out


def tid(row_id):
    return row_id.replace("|", "_").replace(":", "_").replace(".", "-")


def spent():
    req = urllib.request.Request("https://openrouter.ai/api/v1/key",
                                 headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
    return json.load(urllib.request.urlopen(req, timeout=30))["data"]["usage"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--n", type=int, default=0)
    p.add_argument("--model", default="openrouter/openai/gpt-oss-20b")
    p.add_argument("--provider", default="deepinfra")
    p.add_argument("--quant", default="bf16")
    p.add_argument("--max-tokens", type=int, default=3000)
    p.add_argument("--env", default=str(ROOT / ".env"))
    p.add_argument("--retry", action="store_true")
    a = p.parse_args()
    from dotenv import load_dotenv
    load_dotenv(a.env, override=True)
    picked = list(rows())
    out_path = ROOT / "results" / f"{a.run}.jsonl"
    old = [json.loads(l) for l in open(out_path, encoding="utf-8")] if a.retry else []
    if a.retry:
        empty = {o["id"] for o in old if o["verdict"] is None}
        picked = [r for r in picked if r["id"] in empty]
    elif a.n:
        rng = random.Random(0)
        groups = [[r for r in picked if r["set"] == "fresh" and r["label"] == 1],
                  [r for r in picked if r["set"] == "fresh" and r["label"] == 0],
                  [r for r in picked if r["set"] == "planted"]]
        picked = [r for g, k in zip(groups, (2, 2, 1)) for r in rng.sample(g, k)][:a.n]
    by_tid = {tid(r["id"]): r for r in picked}
    work = (ROOT / "results" / "scout" / (a.run + ("_retry" if a.retry else ""))).resolve()
    shutil.rmtree(work, ignore_errors=True)

    async def build():
        async def items():
            for t, r in by_tid.items():
                msgs = to_messages(r["messages"])
                yield Transcript(transcript_id=t, source_type="tau2-airline", source_id=r["id"], task_id=r["id"],
                                 model=r["model"], message_count=len(msgs), messages=msgs)
        async with transcripts_db(str(work / "db")) as db:
            await db.insert(items())

    asyncio.run(build())
    before = spent()
    provider = {"order": [a.provider], "allow_fallbacks": False, **({"quantizations": [a.quant]} if a.quant else {})}
    model = get_model(a.model, config=GenerateConfig(max_tokens=a.max_tokens), provider=provider)
    status = scan(scanners=[saydo()], transcripts=transcripts_from(str(work / "db")), model=model,
                  scans=str(work / "scans"), display="none")
    cost = spent() - before
    df = scan_results_df(status.location).scanners["saydo"]
    out = []
    for r in df.to_dict("records"):
        row = by_tid[r["transcript_id"]]
        meta = r["metadata"] if isinstance(r["metadata"], dict) else json.loads(r["metadata"] or "{}")
        usage = json.loads(r["scan_model_usage"] or "{}") if isinstance(r["scan_model_usage"], str) else {}
        out.append({"id": row["id"], "set": row["set"], "label": row["label"], "type": row["type"],
                    "verdict": {"true": True, "false": False}.get(str(r["value"]).lower()),
                    "said_type": meta.get("type"), "direction": meta.get("direction"),
                    "evidence": r["explanation"], "raw": meta.get("raw"), "error": r.get("scan_error"),
                    "model": a.model, "max_tokens": a.max_tokens,
                    "output_tokens": sum(u.get("output_tokens", 0) for u in usage.values())})
    if a.retry:
        redone = {o["id"]: o for o in out}
        out = [redone.get(o["id"], o) for o in old]
    with open(out_path, "w", encoding="utf-8") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False, default=str) + "\n")
    print(f"{len(out)} chats, cost ${cost:.4f} (${cost / max(len(out), 1):.5f} per chat)")
    print("unparsed answers:", sum(o["verdict"] is None for o in out))
    tally = Counter((o["set"], o["label"], o["type"], o["verdict"]) for o in out)
    for k in sorted(tally, key=str):
        print(" ", k, tally[k])


if __name__ == "__main__":
    main()
