# Saaras translit vs codemix (8 kHz phone-band audio)

200 real seller lines (20 with brand words), spoken by Bulbul and cut to 8 kHz.

| Mode | mean WER | median WER | brand words right | p50 ms | p95 ms |
|---|---|---|---|---|---|
| translit | 0.163 | 0.096 | 89% of 36 | 188 | 2096 |
| codemix | 0.217 | 0.167 | 83% of 36 | 899 | 2210 |

**Default: translit.** codemix wins only with mean WER at least 2 points lower, brand words no worse, p95 latency at most 300 ms higher (the regex layer needs Roman text, so codemix pays a transliteration call).

Caveat: synthetic Bulbul speech cut to 8 kHz: cleaner than a real phone line, so absolute WER is optimistic; the comparison between modes is what this measures.