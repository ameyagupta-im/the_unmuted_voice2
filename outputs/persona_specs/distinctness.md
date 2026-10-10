# Persona distinctness

89 personas across 7 seller types. Distance: 0 = identical, 1 = every setting differs (60% categorical: goal, language, formality, gender, style, speaker; 40% numeric: pace, warmth, empathy, assertiveness, max_words).

- Mean distance between personas of DIFFERENT seller types: **0.50**
- Mean distance between personas of the SAME seller type: **0.12**
- Distinct full combinations (goal x language x formality x gender x style x speaker): **33**

## Type-level centroid distances

| | Already with an executive | Busy business owner | Cautious / burned seller | English-preferring professional | Fatigued repeat lead | Small local trader | Warm, interested lead |
|---|---|---|---|---|---|---|---|
| Already with an executive | 0.05 | 0.57 | 0.41 | 0.48 | 0.40 | 0.38 | 0.21 |
| Busy business owner | 0.57 | 0.13 | 0.58 | 0.59 | 0.56 | 0.59 | 0.52 |
| Cautious / burned seller | 0.41 | 0.58 | 0.00 | 0.54 | 0.15 | 0.38 | 0.47 |
| English-preferring professional | 0.48 | 0.59 | 0.54 | 0.13 | 0.54 | 0.53 | 0.51 |
| Fatigued repeat lead | 0.40 | 0.56 | 0.15 | 0.54 | 0.14 | 0.42 | 0.49 |
| Small local trader | 0.38 | 0.59 | 0.38 | 0.53 | 0.42 | 0.10 | 0.42 |
| Warm, interested lead | 0.21 | 0.52 | 0.47 | 0.51 | 0.49 | 0.42 | 0.06 |

## goal by seller type

| type                            |   callback |   complaint_recovery |   data_update |   exec_handoff |   info_whatsapp |   meeting |   nurture |   respectful_exit |
|:--------------------------------|-----------:|---------------------:|--------------:|---------------:|----------------:|----------:|----------:|------------------:|
| Already with an executive       |          0 |                    0 |             0 |              4 |               0 |         0 |         0 |                 0 |
| Busy business owner             |          4 |                    0 |             4 |              0 |               0 |         5 |         4 |                 0 |
| Cautious / burned seller        |          0 |                    4 |             0 |              0 |               0 |         0 |         0 |                 0 |
| English-preferring professional |          4 |                    0 |             3 |              4 |               0 |         5 |         1 |                 0 |
| Fatigued repeat lead            |          0 |                    2 |             3 |              5 |               5 |         0 |         0 |                 6 |
| Small local trader              |          4 |                    0 |             4 |              0 |               0 |         4 |         5 |                 0 |
| Warm, interested lead           |          0 |                    0 |             4 |              0 |               0 |         5 |         0 |                 0 |

## language by seller type

| type                            |   en-IN |   hi-IN |
|:--------------------------------|--------:|--------:|
| Already with an executive       |       0 |       4 |
| Busy business owner             |       0 |      17 |
| Cautious / burned seller        |       0 |       4 |
| English-preferring professional |      17 |       0 |
| Fatigued repeat lead            |       1 |      20 |
| Small local trader              |       0 |      17 |
| Warm, interested lead           |       0 |       9 |

## style by seller type

| type                            |   calm |   crisp |   neutral |   warm |   warmest |
|:--------------------------------|-------:|--------:|----------:|-------:|----------:|
| Already with an executive       |      0 |       0 |         0 |      4 |         0 |
| Busy business owner             |      0 |      17 |         0 |      0 |         0 |
| Cautious / burned seller        |      4 |       0 |         0 |      0 |         0 |
| English-preferring professional |      0 |       0 |        17 |      0 |         0 |
| Fatigued repeat lead            |     21 |       0 |         0 |      0 |         0 |
| Small local trader              |      0 |       0 |         0 |      0 |        17 |
| Warm, interested lead           |      0 |       0 |         0 |      9 |         0 |

## speaker by seller type

| type                            |   ishita_enhi_customer |   kavya_hi_conversational |   neha_en_customer |   sanchita_enhi_companion |   shubh_hi_customer |   simran_en_customer |
|:--------------------------------|-----------------------:|--------------------------:|-------------------:|--------------------------:|--------------------:|---------------------:|
| Already with an executive       |                      4 |                         0 |                  0 |                         0 |                   0 |                    0 |
| Busy business owner             |                      0 |                         0 |                  0 |                         0 |                  17 |                    0 |
| Cautious / burned seller        |                      0 |                         4 |                  0 |                         0 |                   0 |                    0 |
| English-preferring professional |                      0 |                         0 |                  0 |                         0 |                   0 |                   17 |
| Fatigued repeat lead            |                      0 |                        20 |                  1 |                         0 |                   0 |                    0 |
| Small local trader              |                      0 |                         0 |                  0 |                        17 |                   0 |                    0 |
| Warm, interested lead           |                      9 |                         0 |                  0 |                         0 |                   0 |                    0 |