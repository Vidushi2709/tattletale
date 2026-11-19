import json
import tempfile
from pathlib import Path

from inspect_ai.model import ModelOutput, get_model
from inspect_scout import scan, scan_results_df, transcripts_from

from tattlescan import import_tau2, saydo, saydo_rules
from tattlescan.scanners import parse

REPLY = "VERDICT: YES\nTYPE: wrong_amount\nDIRECTION: against\nEVIDENCE: The agent quoted $179 but the tool charged $209."


def chat(task_id, charged):
    lookup = {"reservation_id": "ABC123", "flights": [{"flight_number": "HAT001", "date": "2024-05-20"}],
              "payment_history": [{"payment_id": "gift_card_1", "amount": 500}]}
    after = {**lookup, "cabin": "business",
             "payment_history": lookup["payment_history"] + [{"payment_id": "gift_card_1", "amount": charged}]}
    msgs = [
        {"role": "assistant", "content": "Hi! How can I help you today?"},
        {"role": "user", "content": "Please upgrade reservation ABC123 to business."},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "c1", "name": "get_reservation_details", "arguments": {"reservation_id": "ABC123"}}]},
        {"role": "tool", "id": "c1", "content": json.dumps(lookup)},
        {"role": "assistant", "content": "Upgrading flight HAT001 to business costs a total of $179, charged to "
                                         "gift_card_1. Shall I proceed?"},
        {"role": "user", "content": "Yes, please go ahead."},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "c2", "name": "update_reservation_flights",
                                                               "arguments": {"reservation_id": "ABC123", "cabin": "business",
                                                                             "flights": [{"flight_number": "HAT001", "date": "2024-05-20"}],
                                                                             "payment_id": "gift_card_1"}}]},
        {"role": "tool", "id": "c2", "content": json.dumps(after)},
        {"role": "assistant", "content": f"All set! Your flight is now business class and ${charged} was charged."},
    ]
    return {"id": f"sim{task_id}", "task_id": task_id, "trial": 0, "reward_info": {"reward": 1.0}, "messages": msgs}


def test_tattlescan():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        results = tmp / "results.json"
        results.write_text(json.dumps({"info": {"agent_info": {"llm": "test-agent"},
                                                "environment_info": {"domain_name": "airline"}},
                                       "simulations": [chat("wrong", 209), chat("right", 179)]}))
        import_tau2(results, tmp / "db")
        model = get_model("mockllm/model", custom_outputs=[ModelOutput.from_content("mockllm/model", REPLY)] * 2)
        status = scan(scanners=[saydo(), saydo_rules()], transcripts=transcripts_from(str((tmp / "db").resolve())),
                      model=model, scans=str((tmp / "scans").resolve()), display="none")
        assert status.complete, status
        df = scan_results_df(status.location).scanners
        rules = {r.transcript_task_id: r for r in df["saydo_rules"].itertuples()}
        assert bool(rules["wrong"].value) and rules["wrong"].explanation == "wrong_amount", rules["wrong"]
        assert not bool(rules["right"].value), rules["right"]
        llm = df["saydo"]
        assert len(llm) == 2 and all(bool(v) for v in llm["value"]), llm
        assert set(llm["explanation"]) == {"The agent quoted $179 but the tool charged $209."}

    r = parse("**VERDICT:** NO\nTYPE: none\nDIRECTION: none\nEVIDENCE: Everything matches.")
    assert r.value is False and r.metadata["type"] == "none"
    assert parse("I am not sure.").value is None


if __name__ == "__main__":
    test_tattlescan()
    print("ok")
