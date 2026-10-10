# Offline evaluation (test split by call)

1,418 labelled seller utterances from test calls.

## Signals (tier-1 regex)

| Signal | support | precision (lower bound) | recall |
|---|---|---|---|
| ai_bot_suspicion | 53 | 1.00 | 0.87 |
| identity_question | 335 | 0.97 | 0.43 |
| confusion | 341 | 0.47 | 0.10 |
| frustration | 43 | 0.86 | 0.14 |
| price_query | 123 | 0.94 | 0.42 |
| complaint | 37 | 0.64 | 0.19 |

## Dialogue acts

Weak labels: of 1,418 utterances IndiaMART's evaluator marks as seller questions, 95% are classified as question or request. Predicted: question 1325, statement 71, request 21, affirm 1.

Human labels: not yet filled (outputs/eval/act_labels.csv, column human_act).