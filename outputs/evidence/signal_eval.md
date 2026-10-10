# Live-signal detection vs IndiaMART evaluator labels (held-out test split)

4,718 real seller utterances labelled by IndiaMART's `seller_questions` evaluator; 1,843 in the held-out test split. Tier 2 scored on a stratified test sample of 193.

| Signal | test support | tier-1 regex P | tier-1 regex R | tier-2 v1 R | tier-2 v2 R | tier-2 v2 P | live (tier-1 ∪ tier-2 v2) P | live R |
|---|---|---|---|---|---|---|---|---|
| ai_bot_suspicion | 58 | 1.00 | 0.84 | 0.96 | 0.96 | 0.86 | 0.86 | 0.96 |
| identity_question | 483 | 0.95 | 0.50 | 0.87 | 0.84 | 0.59 | 0.59 | 0.84 |
| confusion | 396 | 0.44 | 0.11 | 0.56 | 0.25 | 0.39 | 0.36 | 0.28 |
| frustration | 67 | 0.69 | 0.13 | 0.34 | 0.50 | 0.84 | 0.84 | 0.50 |
| price_query | 167 | 0.96 | 0.41 | 0.94 | 0.97 | 0.79 | 0.79 | 0.97 |
| complaint | 45 | 0.62 | 0.11 | 0.31 | 0.39 | 0.71 | 0.75 | 0.46 |

Caveats:
- precision is a lower bound (labels are not exhaustive: e.g. 'aap kahan se bol rahe ho' is labelled Location, not Identity)
- IndiaMART's 'Clarification' label also covers logistics questions ('kal kis time?') which VANI's confusion signal deliberately excludes, so confusion recall is understated
- utterances scored without the preceding VANI turn; the live engine's tier 2 sees the full call
- tier 2 scored on a stratified test sample, not every test utterance
- 8 example misses per class were viewed from the full set before the split was introduced (minor test contamination)