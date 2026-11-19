"""Compact review view of a conversation: what was said about money/changes vs what the tools did."""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
WRITES = {"book_reservation", "update_reservation_flights", "update_reservation_baggages",
          "update_reservation_passengers", "cancel_reservation", "send_certificate"}
TOPIC = re.compile(r"\$\s?\d|book|bag|certificate|cancel|upgrade|downgrade|change|passenger|refund|charge", re.I)

convs = {json.loads(l)["id"]: json.loads(l) for l in open(sys.argv[1], encoding="utf-8")}
for cid in sys.argv[2:]:
    c = convs[cid]
    print(f"\n######## {cid}  flags={c['reject_reasons']}  reward={c['reward']}")
    msgs = c["messages"]
    pay, pending = {}, []
    for i, m in enumerate(msgs):
        t = (m["content"] or "").replace("\n", " ")
        if m["role"] == "user":
            print(f"[{i}] USER: {t[:300]}")
        elif m["role"] == "assistant":
            if t:
                print(f"[{i}] AGENT: {t[:1000] if TOPIC.search(t) else t[:100]}")
            pending = list(m["tool_calls"])
            for call in pending:
                if call["name"] in WRITES:
                    print(f"[{i}] AGENT CALLS {call['name']}({json.dumps(call['arguments'])[:450]})")
        elif m["role"] == "tool":
            call = pending.pop(0) if pending else {"name": "?"}
            s = str(m["content"])
            if s.startswith("Error"):
                print(f"[{i}] TOOL ERROR ({call['name']}): {s[:150]}")
                continue
            try:
                r = json.loads(s)
            except ValueError:
                if call["name"] in WRITES:
                    print(f"[{i}] TOOL ({call['name']}): {s[:200]}")
                continue
            if isinstance(r, dict) and "payment_history" in r:
                rid = r.get("reservation_id")
                if call["name"] in WRITES:
                    before = pay.get(rid, [])
                    new = r["payment_history"] if call["name"] == "book_reservation" else r["payment_history"][len(before):]
                    extra = f" bags={r.get('total_baggages')}/{r.get('nonfree_baggages')} cabin={r.get('cabin')}"
                    print(f"[{i}] TOOL ({call['name']}) {rid}: new payments {new}{extra}")
                pay[rid] = r["payment_history"]
