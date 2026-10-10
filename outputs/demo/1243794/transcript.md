# Live demo call - seller 1243794
Delhi clamps trader, called 20 times, past complaint about executive service  
Seller type: Fatigued repeat lead  
Primary goal: complaint_recovery  
Goal path: complaint_recovery  
Final outcome: COMPLAINT_LOGGED (Dissatisfied, goal achieved: yes)  
Seller insights: {}

**VANI** _(speaker kavya_hi_conversational, pace 0.93, mode DEFAULT)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। दोबारा call करने के लिए माफ़ी चाहती हूँ। call इसलिए किया क्योंकि पिछली बार आपको जो परेशानी हुई, उसके बारे में आपसे बात करनी थी। पिछली बार क्या दिक्कत आई थी, ज़रा बताइए?

**Seller** (hi-IN, beat: Answer the phone and ask who is calling and why.): कौन बोल रहा है? IndiaMART से बार बार क्यों call कर रहे हो?  
_STT (hi-IN):_ Kaun bol raha hai IndiaMART se baar baar kyon call kar rahe ho?  _signals ['frustration', 'identity_question'], hang-up risk 0.818_

> **PERSONA SWITCH - frustration** (detected by regex, t=4.0s): {"mode": ["DEFAULT", "CALM_EMPATHETIC"], "pace": [0.93, 0.87], "max_words": [18, 20]} - Playbook scenario 3: frustration -> CALM_EMPATHETIC.

**VANI** _(mode CALM_EMPATHETIC, goal complaint_recovery, pace 0.87, latency {'stt': 208, 'tier1': 4, 'llm': 1417, 'tts': 1943})_: जी, मैं IndiaMART की virtual assistant Payal हूँ। पिछली बार जो परेशानी हुई उसके लिए माफ़ी चाहती हूँ। support team आपको किस time call करे?

**Seller** (hi-IN, beat: Answer VANI's question about your business in your own way (honestly, per your temperament).): Business तो clamps ka hai, but leads hi nahi aate yaar. Paisa diya tha, kuch nahi hua.  
_STT (hi-IN):_ Business toh VANI ka hai but leads hi nahi aate yaar, paisa diya tha kuch nahi hua.  _signals ['complaint'], hang-up risk 0.8_

> **END SWITCH - llm_outcome** (detected by llm, t=9.7s): {"outcome": ["IN_PROGRESS", "COMPLAINT_LOGGED"]} - LLM proposed COMPLAINT_LOGGED; supported by what the seller said.

**VANI** _(mode CALM_EMPATHETIC, goal complaint_recovery, pace 0.87, latency {'stt': 653, 'tier1': 3, 'llm': 544, 'tts': 1728})_: असुविधा के लिए माफ़ी चाहती हूँ। आपकी बात मैंने note कर ली है, support team आपसे संपर्क करेगी। समय देने के लिए धन्यवाद।