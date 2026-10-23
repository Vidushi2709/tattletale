"""Normalise tau2-bench airline conversations and mark the clean ones -> data/conversations.jsonl"""

import json
import pathlib
import re
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "conversations.jsonl"

CONSENT_WRITES = {
    "book_reservation",
    "update_reservation_flights",
    "update_reservation_baggages",
    "update_reservation_passengers",
}
WRITES = CONSENT_WRITES | {"cancel_reservation", "send_certificate"}

AGREE = re.compile(
    r"\b(yes|yeah|yep|proceed|go ahead|confirm(ed)?|please do|do it|book it|"
    r"that'?s fine|sounds good|okay|ok|correct)\b",
    re.IGNORECASE,
)
THINK = re.compile(r"<think>|</think>", re.IGNORECASE)
LEAK = re.compile(
    r"\bWait, I|let me re-read|re-read the policy|\bthe user (is|wants|requested|asked)\b",
    re.IGNORECASE,
)
SUCCESS = re.compile(
    r"successfully|has been (updated|cancell?ed|booked|changed|added|processed)|"
    r"is confirmed|all set|\bdone\b",
    re.IGNORECASE,
)
FAILURE = re.compile(r"error|unable|could not|couldn't|failed|issue|problem|not able", re.IGNORECASE)
LABELLED = re.compile(
    r"(refund|charge|total|difference|cost|pay|credit)[^$\n]{0,40}\$\s?(\d[\d,]*(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
MENTION = {
    "book_reservation": r"book",
    "update_reservation_flights": r"flight|cabin|class|upgrade|downgrade|economy|business",
    "update_reservation_baggages": r"bag",
    "update_reservation_passengers": r"passenger|name",
    "cancel_reservation": r"cancel",
    "send_certificate": r"certificate|compensation|voucher",
}


def flatten(value, indent=""):
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{indent}{k.replace('_', ' ')}:")
                lines.append(flatten(v, indent + "  "))
            else:
                lines.append(f"{indent}{k.replace('_', ' ')}: {v}")
        return "\n".join(lines)
    if isinstance(value, list):
        return "\n".join(f"{indent}- {flatten(v, indent + '  ').lstrip()}" for v in value)
    return f"{indent}{value}"


def clean_text(text):
    """Strip model-specific layout (GPT-5.2 JSON replies, Qwen leading blank lines)."""
    if text is None:
        return None
    s = text.strip()
    if s.startswith("{"):
        try:
            obj = json.loads(s)
        except ValueError:
            return s
        if isinstance(obj, dict):
            msg = obj.pop("message", None)
            parts = [msg.strip()] if isinstance(msg, str) else []
            if obj:
                parts.append(flatten(obj))
            s = "\n\n".join(parts)
    return s


def normalise(sim, model):
    msgs = []
    for m in sim["messages"]:
        calls = [{"name": c["name"], "arguments": c["arguments"]} for c in (m.get("tool_calls") or [])]
        content = m.get("content")
        if m["role"] != "tool":
            content = clean_text(content)
        msgs.append({"role": m["role"], "content": content, "tool_calls": calls})
    return {
        "id": f"{model}:{sim['task_id']}:{sim['trial']}",
        "source_model": model,
        "task_id": str(sim["task_id"]),
        "trial": sim["trial"],
        "reward": sim["reward_info"]["reward"],
        "db_match": (sim["reward_info"].get("db_check") or {}).get("db_match"),
        "messages": msgs,
    }


def labelled_amounts(text):
    return {round(float(a.replace(",", ""))) for _, a in LABELLED.findall(text or "")}


def matches_quote(moved, quoted):
    """Moved money matches a quoted amount, a difference of two, or (summed) a total."""
    near = lambda a, b: abs(a - b) <= 1
    diffs = {abs(x - y) for x in quoted for y in quoted}
    if any(near(sum(moved), q) for q in quoted):
        return True
    return all(any(near(a, q) for q in quoted | diffs) for a in moved)


def pair_calls(msgs):
    calls = [(i, c) for i, m in enumerate(msgs) for c in m["tool_calls"]]
    results = [m["content"] for m in msgs if m["role"] == "tool"]
    if len(calls) != len(results):
        return None
    return [(i, c, r) for (i, c), r in zip(calls, results)]


def check(conv):
    reasons = []
    if conv["reward"] != 1.0:
        reasons.append("reward<1")
    if conv["db_match"] is not True:
        reasons.append("db_mismatch")
    msgs = conv["messages"]
    agent_text = [(i, m["content"]) for i, m in enumerate(msgs) if m["role"] == "assistant" and m["content"]]

    for i, m in enumerate(msgs):
        if m["role"] == "tool" and str(m["content"]).lstrip().lower().startswith("error"):
            reasons.append("tool_error")
        if m["role"] == "assistant" and m["content"] and (THINK.search(m["content"]) or LEAK.search(m["content"])):
            reasons.append("reasoning_leak")
        if (m["role"] == "user" and m["content"] and i + 1 < len(msgs) and msgs[i + 1]["role"] == "assistant"
                and msgs[i + 1]["content"] and m["content"][:200] == msgs[i + 1]["content"][:200]):
            reasons.append("role_confusion")

    paired = pair_calls(msgs)
    if paired is None:
        reasons.append("unpaired_calls")
        paired = []
    last_payments, last_flights = {}, {}
    for i, call, result in paired:
        name, args = call["name"], call["arguments"]
        try:
            res = json.loads(result)
        except (TypeError, ValueError):
            res = None

        if name in WRITES:
            prev_user = next((j for j in range(i - 1, -1, -1) if msgs[j]["role"] == "user"), None)
            asked = next((t for j, t in reversed(agent_text) if prev_user is not None and j < prev_user), None)
            said_before = " ".join(t for j, t in agent_text if j <= i)

            if name in CONSENT_WRITES and (
                prev_user is None or asked is None or not AGREE.search(str(msgs[prev_user]["content"]))
            ):
                reasons.append("no_consent")

            if name in ("book_reservation", "update_reservation_flights"):
                kept = last_flights.get(args.get("reservation_id"), set())
                for f in args.get("flights") or []:
                    num = f.get("flight_number")
                    if num and num not in kept and num not in said_before:
                        reasons.append("detail_mismatch")

            if isinstance(res, dict) and "payment_history" in res:
                before = last_payments.get(res.get("reservation_id"), [])
                new = res["payment_history"][len(before):] if name != "book_reservation" else res["payment_history"]
                moved = {abs(round(p["amount"])) for p in new} - {0}
                quoted = labelled_amounts(asked)
                if quoted and moved and not matches_quote(moved, quoted):
                    reasons.append("quote_mismatch")

            if str(result).lstrip().lower().startswith("error"):
                nxt = next((t for j, t in agent_text if j > i), "")
                if SUCCESS.search(nxt) and not FAILURE.search(nxt):
                    reasons.append("false_success")

            if not any(re.search(MENTION[name], t, re.IGNORECASE) for _, t in agent_text):
                reasons.append("unmentioned_write")

        if isinstance(res, dict) and "payment_history" in res and "reservation_id" in res:
            last_payments[res["reservation_id"]] = res["payment_history"]
            last_flights[res["reservation_id"]] = {f.get("flight_number") for f in res.get("flights") or []}

    conv["has_write"] = any(c["name"] in WRITES for m in msgs for c in m["tool_calls"])
    conv["reject_reasons"] = sorted(set(reasons))
    conv["clean"] = not reasons


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    convs = []
    for path in sorted(RAW.glob("*_airline.json")):
        model = path.name.removesuffix("_airline.json")
        convs += [normalise(s, model) for s in json.loads(path.read_text(encoding="utf-8"))["simulations"]]
    for c in convs:
        check(c)
    with OUT.open("w", encoding="utf-8") as f:
        for c in convs:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    clean = [c for c in convs if c["clean"]]
    print(f"total {len(convs)}, clean {len(clean)} (with a write: {sum(c['has_write'] for c in clean)})")
    print("clean by model:", dict(Counter(c["source_model"] for c in clean)))
    print("reject reasons:", dict(Counter(r for c in convs for r in c["reject_reasons"])))
    writers = [c for c in convs if c["has_write"]]
    for t in ("false_success", "no_consent", "quote_mismatch", "detail_mismatch", "unmentioned_write"):
        hits = [c for c in writers if t in c["reject_reasons"]]
        print(f"  {t:18s} {len(hits):4d} / {len(writers)}   graded a pass: {sum(c['reward'] == 1.0 for c in hits)}")


if __name__ == "__main__":
    main()
