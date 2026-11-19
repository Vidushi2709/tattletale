# tattlescan

A scanner that flag when an AI agent's words and its tool actions disagree: it tells the customer one thing, and its tool calls do another.

It looks for five kinds of mistake:

| Type | Example |
|---|---|
| `false_success` | Says "done", but the tool call returned an error |
| `no_consent` | Changes a booking before the customer said yes |
| `wrong_details` | Tells the customer "no bags", but the booking adds bags |
| `unmentioned_action` | Makes a change it never tells the customer about |
| `wrong_amount` | Quotes $179, and the system charges $209 |

## Scanners

- `saydo` asks a model to read the whole transcript and answer with a verdict, the mistake type, whether it went against the customer or in their favour, and one line of evidence.
- `saydo_rules` uses plain code and no model. It is free and fast. On 597 real τ²-bench chats, 46 of its 60 flags were wrong amounts.

Both are written for τ²-bench airline conversations. The money check reads the airline tools' `payment_history` records, so on other agents only the model's other four checks apply.

## Use

```bash
pip install -e .
```

```python
from inspect_scout import scan, transcripts_from
from tattlescan import import_tau2, saydo, saydo_rules

import_tau2("gpt-5_airline.json", "db")
scan(scanners=[saydo(), saydo_rules()], transcripts=transcripts_from("db"),
     model="openrouter/anthropic/claude-haiku-5.5")
```

For an open model, use `openrouter/openai/gpt-oss-120b`. `saydo` needs room to reason: give reasoning models `GenerateConfig(max_tokens=8000)`, because at 3,000 about 1 chat in 10 came back empty.

`import_tau2` reads a τ²-bench results file. Transcripts from Inspect eval logs work directly with `transcripts_from`.

On Windows, give Scout absolute paths: with a relative database path, scans in inspect-scout 0.6.2 fail silently. `import_tau2` resolves its path for you.

## Results

`saydo` was measured on 194 τ²-bench airline chats the prompt was never tuned on: 134 hand-labelled chats from Claude Opus 4.5, Gemini 3 Pro and GPT-5 (17 real mistakes, 117 fine), plus 60 chats with a planted wrong amount.

| Monitor | Real mistakes caught (17) | Planted wrong amounts (60) | False alarms (117 fine chats) | Cost per chat |
|---|---|---|---|---|
| `claude-haiku-5.5` | 14 (82%) | 60 | 7 (6%) | ~$0.0006 |
| `gpt-oss-120b` | 10 (59%) | 59 | 7 (6%) | ~$0.0003 |
| `gpt-oss-20b` | 9 (53%) | 59 | 18 (15%) | ~$0.0001 |

With 17 real mistakes the ranges are wide: Haiku's 82% has a 95% interval of 59–94%. All three catch wrong amounts best, and mostly miss a charge whose price the agent never stated. Only Haiku catches most wrong details (3 of 4).

## Test

```bash
python test_tattlescan.py
```

It runs both scanners on two small made-up chats with Inspect's mock model, so it needs no API key.
