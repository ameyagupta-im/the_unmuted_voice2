# Live demo call - seller 56768582
Hyderabad rice-bran firm, Rs 25-100 Cr, busy owner  
Seller type: Busy business owner  
Primary goal: meeting  
Goal path: meeting  
Final outcome: DO_NOT_CALL (Do not call, goal achieved: no)  
Seller insights: {}

**VANI** _(speaker shubh_hi_customer, pace 0.98, mode DEFAULT)_: नमस्ते जी, मैं IndiaMART से Rohan बोल रहा हूँ। call इसलिए किया क्योंकि Hyderabad में आपकी De Oiled Rice Bran category में काफ़ी buyer enquiries आई हैं। आपका De Oiled Rice Bran का काम अभी कैसा चल रहा है?

**Seller** (hi-IN, beat: Answer the phone and ask who is calling and why.): कौन बोल रहा है? IndiaMART से है क्या? Hyderabad में buyers की enquiries आई हैं आपने कहा?  
_STT (hi-IN):_ Kaun bol raha hai IndiaMART se hai kya? Hyderabad mein buyers ki enquiries aayi hain aapne kaha.  _signals ['identity_question'], hang-up risk 0.569_

> **PERSONA SWITCH - identity_question** (detected by regex, t=4.2s): {"mode": ["DEFAULT", "TRANSPARENT"], "max_words": [17, 30], "empathy": [3, 4]} - Playbook scenario 6: identity_question -> TRANSPARENT.

**VANI** _(mode TRANSPARENT, goal meeting, pace 0.98, latency {'stt': 304, 'tier1': 2, 'llm': 1523, 'tts': 2823})_: जी sir, मैं IndiaMART का virtual assistant हूँ। Hyderabad में आपकी De Oiled Rice Bran category में buyer enquiries आई हैं, उसी के लिए call किया है। अगर आप चाहें तो हम Telugu में भी बात कर सकते हैं। क्या मैं हमारे executive के साथ एक छोटी meeting रख दूँ, online या आपके पास?

**Seller** (hi-IN, beat: Answer VANI's question about your business in your own way (honestly, per your temperament).): Business तो ठीक चल रहा है, पर मैं अभी कोई meeting नहीं कर सकती।  
_STT (hi-IN):_ Business toh theek chal raha hai par main abhi koi meeting nahi kar sakti.  _signals [], hang-up risk 0.553_

> **RECOVERY SWITCH - transparent_done** (detected by engine, t=10.2s): {"mode": ["TRANSPARENT", "DEFAULT"]} - TRANSPARENT lasts one reply; resume the previous mode.

**VANI** _(mode DEFAULT, goal meeting, pace 0.98, latency {'stt': 256, 'tier1': 1, 'llm': 1556, 'tts': 1878})_: जी sir, बिल्कुल। अगर अभी meeting नहीं हो पा रही है, तो क्या हम कल शाम 5 बजे के आसपास connect कर सकते हैं? या आप किस time पर बात करना पसंद करेंगे?

**Seller** (te-IN, beat: React in your own way to what VANI said (see your temperament); this is your key moment.): లేదు, మళ్ళీ call చేయకండి. నాకు time లేదు.  
_STT (te-IN):_ Ledu malli call cheyakandi naaku time ledu.  _signals ['busy', 'do_not_call', 'language_switch'], hang-up risk 0.764_

> **LANGUAGE SWITCH - language_switch** (detected by stt_language, t=19.0s): {"language": ["hi-IN", "te-IN"]} - Seller switched language: switch fully, repeat the pending point; the voice stays the same.

> **END SWITCH - do_not_call** (detected by regex, t=19.0s): {"outcome": ["IN_PROGRESS", "DO_NOT_CALL"]} - Seller asked not to be called: honour immediately.

**VANI** _(mode DEFAULT, goal meeting, pace 0.98, latency {'stt': 243, 'tier1': 0, 'tts': 749})_: అర్థమైంది, మేము మీకు మళ్ళీ call చేయము. ధన్యవాదాలు.