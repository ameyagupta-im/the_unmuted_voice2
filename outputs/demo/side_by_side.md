# Same scenario, three contrasting sellers

| | 3419775 | 1243794 | 56768582 |
|---|---|---|---|
| Seller | Chennai idli-machine maker, first contact | Delhi clamps trader, called 20 times, past complaint about executive service | Hyderabad rice-bran firm, Rs 25-100 Cr, busy owner |
| Seller type | English-preferring professional | Fatigued repeat lead | Busy business owner |
| Bot / voice | Payal / simran_en_customer | Payal / kavya_hi_conversational | Rohan / shubh_hi_customer |
| Start language / pace | en-IN / 0.93 | hi-IN / 0.93 | hi-IN / 0.98 |
| Empathy / assertiveness | 3 / 3 | 5 / 1 | 3 / 4 |
| Primary goal | meeting | complaint_recovery | meeting |
| Goal path | meeting -> info_whatsapp -> respectful_exit -> info_whatsapp | complaint_recovery | meeting |
| Live switches | t1 persona:identity_question (regex); t2 persona:confusion (regex); t5 goal:refused_with_reason (regex); t6 goal:not_interested (regex); t6 goal:wants_whatsapp (llm); t6 end:wants_whatsapp (llm) | t1 persona:frustration (regex); t2 end:llm_outcome (llm) | t1 persona:identity_question (regex); t3 language:language_switch (stt_language); t3 end:do_not_call (regex) |
| End voice / language | simran_en_customer / en-IN | kavya_hi_conversational / hi-IN | shubh_hi_customer / te-IN |
| Outcome (goal achieved) | INFO_SENT (partly) | COMPLAINT_LOGGED (yes) | DO_NOT_CALL (no) |