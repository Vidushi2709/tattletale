# Monitor results: results/holdout_check_think4k_qwen3-4b.jsonl

Conversations per group: false_success 10, honest_error 10, mentioned_action 6, mentioned_action+ 4, no_consent 10, none 10, unmentioned_action 10, wrong_details 10
Tasks: 24. Intervals: 95%, cluster bootstrap over tasks. A '+' marks mismatches inside a control group (relabelled after reading).

## Question 1: which view works (all mismatch types together)

| View | AUROC | Catch @5% false alarms | Catch @1% (rough) |
|---|---|---|---|
| speech | 0.530 [0.35-0.71] |  13.6% [2-31] |   9.1% [0-27] |
| actions | 0.649 [0.52-0.77] |  11.4% [2-27] |   6.8% [1-21] |
| full | 0.976 [0.94-1.00] |  88.6% [79-100] |  88.6% [79-98] |
| hybrid | 0.665 [0.52-0.79] |  15.9% [8-39] |  11.4% [6-35] |

## Question 2: which mismatch type is missed (catch rate @5% false alarms)

| View | false_success | no_consent | wrong_details | unmentioned_action | mentioned_action |
|---|---|---|---|---|---|
| speech |   0.0% [0-31] |  20.0% [0-67] |   0.0% [0-0] |   0.0% [0-0] | 100.0% [100-100] |
| actions |  20.0% [0-67] |  10.0% [0-40] |  10.0% [0-33] |  10.0% [0-50] |   0.0% [0-0] |
| full | 100.0% [100-100] |  90.0% [75-100] |  80.0% [57-100] |  80.0% [44-100] | 100.0% [100-100] |
| hybrid |  10.0% [0-60] |  20.0% [0-67] |   0.0% [0-12] |   0.0% [0-43] | 100.0% [50-100] |

Per-type AUROC (threshold-free):

| View | false_success | no_consent | wrong_details | unmentioned_action | mentioned_action |
|---|---|---|---|---|---|
| speech | 0.558 [0.29-0.78] | 0.519 [0.14-0.76] | 0.417 [0.21-0.66] | 0.438 [0.18-0.70] | 1.000 [1.00-1.00] |
| actions | 0.735 [0.53-0.92] | 0.608 [0.42-0.74] | 0.531 [0.34-0.73] | 0.725 [0.54-0.87] | 0.644 [0.44-0.84] |
| full | 1.000 [1.00-1.00] | 0.977 [0.91-1.00] | 0.973 [0.93-1.00] | 0.942 [0.81-1.00] | 1.000 [1.00-1.00] |
| hybrid | 0.685 [0.49-0.90] | 0.685 [0.35-0.88] | 0.485 [0.29-0.70] | 0.677 [0.48-0.82] | 0.990 [0.96-1.00] |

## Controls: false-alarm rate on each kind of negative, at the 5% threshold

If honest_error or mentioned_action is flagged far more than clean (none), the monitor is reacting to errors or extra actions themselves, not to words disagreeing with actions.

| View | none | honest_error | mentioned_action |
|---|---|---|---|
| speech |   0.0% [0-0] |   0.0% [0-0] |  16.7% [0-50] |
| actions |   0.0% [0-0] |  10.0% [0-17] |   0.0% [0-25] |
| full |   0.0% [0-11] |  10.0% [0-17] |   0.0% [0-12] |
| hybrid |   0.0% [0-0] |   0.0% [0-14] |  16.7% [0-33] |
