# Playbook scenario suite: 23/23 scenarios, 57/57 checks

## PASS - 1 Do-not-call (seller 113839910)
- [x] signal do_not_call
- [x] outcome DO_NOT_CALL
- [x] call ended
- [x] closing is a statement
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** mujhe dobara call mat karna, number hata do  _signals ['do_not_call', 'frustration']_
  - **VANI** _(DEFAULT, goal meeting, DO_NOT_CALL)_: समझ गई, हम आपको दोबारा call नहीं करेंगे। धन्यवाद।

## PASS - 2 Connectivity (twice) (seller 113839910)
- [x] mode CLEAR_AUDIO after first
- [x] outcome CALL_BACK_LATER
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** hello? awaaz nahi aa rahi  _signals ['connectivity']_
  - **VANI** _(CLEAR_AUDIO, goal meeting, IN_PROGRESS)_: जी, आवाज़ अब साफ़ आ रही है क्या? अगर अभी भी connection की problem है, तो मैं बाद में call कर लूँगी।
  - **Seller:** hello hello? kuch sunai nahi de raha, awaaz toot rahi hai  _signals ['connectivity']_
  - **VANI** _(CLEAR_AUDIO, goal meeting, CALL_BACK_LATER)_: आवाज़ साफ़ नहीं आ रही, मैं आपको थोड़ी देर में दोबारा call करती हूँ। धन्यवाद।

## PASS - 3 Frustration (twice) (seller 113839910)
- [x] mode CALM_EMPATHETIC
- [x] goal -> callback (no more asks)
- [x] no pitch after frustration
- [x] outcome ESCALATED_EXIT
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** kitni baar call karoge, pareshan kar diya  _signals ['frustration']_
  - **VANI** _(CALM_EMPATHETIC, goal callback, IN_PROGRESS)_: जी, मुझे सच में बहुत अफ़सोस है कि आपको परेशानी हुई। मैं आगे से आपको परेशान नहीं करूँगी। क्या मैं कल शाम 7 बजे आपको दोबारा call कर लूँ?
  - **Seller:** bas karo, dimaag kharab kar diya aap logon ne  _signals ['frustration']_
  - **VANI** _(CALM_EMPATHETIC, goal callback, ESCALATED_EXIT)_: परेशानी के लिए माफ़ी चाहती हूँ। मैं call यहीं समाप्त करती हूँ। धन्यवाद।

## PASS - 4 Complaint, then support time (playbook example) (seller 113839910)
- [x] need -> goal meeting kept
- [x] complaint -> goal complaint_recovery
- [x] mode CALM_EMPATHETIC
- [x] no pitch after complaint
- [x] outcome COMPLAINT_LOGGED
- [x] slot captured
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: ठीक है जी, समझ गई। तो kal शाम 7 बजे की meeting confirm कर दूँ, या आप online meeting रखना पसंद करेंगे?
  - **Seller:** kaam theek chal raha hai par IndiaMART se enquiry bahut kam aati hai  _signals ['need_few_enquiries']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: जी, मैं समझ सकती हूँ, कम enquiries आना काफी मुश्किल होता है। हमारे executive आपकी profile को सही तरीके से update करके help कर सकते हैं, और यह meeting बिल्कुल free है। क्या मैं हमारे executive के साथ एक छोटी meeting रख दूँ, online या आपके पास?
  - **Seller:** leads hi nahi aate, paisa diya tha kuch nahi hua  _signals ['complaint']_
  - **VANI** _(CALM_EMPATHETIC, goal complaint_recovery, IN_PROGRESS)_: जी, मैं माफ़ी चाहती हूँ कि आपको यह परेशानी हुई। मैं आपकी यह शिकायत तुरंत support team को भेज रही हूँ। support team आपको किस time call करे?
  - **Seller:** kal shaam 5 baje  _signals ['complaint', 'gives_time']_
  - **VANI** _(CALM_EMPATHETIC, goal complaint_recovery, COMPLAINT_LOGGED)_: असुविधा के लिए माफ़ी चाहती हूँ। आपकी बात मैंने note कर ली है, support team आपसे संपर्क करेगी। समय देने के लिए धन्यवाद।

## PASS - 5 Are you a bot? (seller 113839910)
- [x] signal ai_bot_suspicion
- [x] says virtual assistant
- [x] never claims human
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** aap robot ho kya?  _signals ['ai_bot_suspicion']_
  - **VANI** _(TRANSPARENT, goal meeting, IN_PROGRESS)_: जी, मैं IndiaMART की virtual assistant हूँ। आपके Cotton Fabric business के बारे में बात आगे बढ़ाती हूँ, तो बताइए अभी काम कैसा चल रहा है?

## PASS - 6 Who is calling / why (seller 113839910)
- [x] signal identity_question
- [x] gives name
- [x] call continues
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** kaun bol raha hai? kis liye call kiya?  _signals ['identity_question']_
  - **VANI** _(TRANSPARENT, goal meeting, IN_PROGRESS)_: जी, मैं IndiaMART की virtual assistant हूँ। आपके catalog को बेहतर बनाने के लिए call किया है। आपका Cotton Fabric का काम अभी कैसा चल रहा है?

## PASS - 7 Not the right person (seller 113839910)
- [x] goal -> data_update
- [x] outcome CONTACT_UPDATED
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** main owner nahi hoon, sir se baat kijiye  _signals ['not_right_person']_
  - **VANI** _(DEFAULT, goal data_update, IN_PROGRESS)_: जी, बिल्कुल समझ गई। क्या आप मुझे सही contact person, उनके number और role बता सकते हैं ताकि मैं उनसे बात कर सकूँ?
  - **Seller:** unka naam Ramesh hai, number 9876543210  _signals []_
  - **VANI** _(DEFAULT, goal data_update, CONTACT_UPDATED)_: जानकारी के लिए धन्यवाद, हम सही व्यक्ति से संपर्क करेंगे।

## PASS - 8 Already with an executive (seller 113839910)
- [x] goal -> exec_handoff
- [x] no fresh pitch
- [x] outcome EXEC_HANDOFF
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** hamare executive Rakesh ji pehle se aate hain  _signals ['already_with_executive']_
  - **VANI** _(DEFAULT, goal exec_handoff, IN_PROGRESS)_: जी, समझ गई। चूँकि Rakesh ji पहले से ही आपकी मदद कर रहे हैं, तो क्या आप मुझे बता सकती हैं कि अभी आपको उनसे exactly क्या सहायता चाहिए, ताकि मैं उसे आगे forward कर सकूँ?
  - **Seller:** unse bolna hamara catalog update karna hai  _signals []_
  - **VANI** _(DEFAULT, goal exec_handoff, EXEC_HANDOFF)_: मैं यह बात आपके executive तक पहुँचा दूँगी। धन्यवाद।

## PASS - 9 Not interested (twice) (seller 113839910)
- [x] first no: call continues with a gentle question
- [x] at the limit: goal respectful_exit, asks contact preference
- [x] outcome RESPECTFUL_EXIT
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** nahi chahiye  _signals ['not_interested']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: जी, कोई बात नहीं। अगर अभी meeting ठीक नहीं लग रही है, तो क्या मैं कल शाम 7 बजे आपको दोबारा call कर लूँ, या फिर आप WhatsApp पर details लेना चाहेंगे?
  - **Seller:** nahi chahiye, interest nahi hai  _signals ['not_interested']_
  - **VANI** _(DEFAULT, goal respectful_exit, IN_PROGRESS)_: जी, मैं समझ गई। कोई बात नहीं। बस यह बता दीजिए कि आप कितनी बार call करवाना पसंद करेंगे, या फिर मैं आगे से call नहीं करूँ?
  - **Seller:** nahi ji, kuch nahi  _signals ['not_interested']_
  - **VANI** _(DEFAULT, goal respectful_exit, RESPECTFUL_EXIT)_: कोई बात नहीं, समय देने के लिए धन्यवाद। आपका दिन शुभ हो।

## PASS - 9b Refused with a reason (seller 113839910)
- [x] goal -> info_whatsapp (lightest offer)
- [x] offers WhatsApp
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** abhi zaroorat nahi hai, stock already full hai  _signals ['not_interested']_
  - **VANI** _(DEFAULT, goal info_whatsapp, IN_PROGRESS)_: जी, बिल्कुल समझ गई। जब stock full हो तो अभी focus करना सही रहता है। कोई बात नहीं, मैं आपको WhatsApp पर details भेज देती हूँ, जब भी आपको ज़रूरत लगे तब देख लीजिएगा। क्या मैं details आपको WhatsApp पर भेज दूँ?

## PASS - 10 Busy (seller 113839910)
- [x] mode BRIEF
- [x] goal -> callback
- [x] short reply (<= 30 words)
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** abhi busy hoon, jaldi bataiye  _signals ['busy']_
  - **VANI** _(BRIEF, goal callback, IN_PROGRESS)_: जी, समझ गई। किस time call करूँ, या details WhatsApp पर भेज दूँ?

## PASS - 11 Wants a human (seller 113839910)
- [x] goal -> human_handoff
- [x] outcome HUMAN_HANDOFF
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** manager se baat karao  _signals ['human_request']_
  - **VANI** _(DEFAULT, goal human_handoff, HUMAN_HANDOFF)_: हमारे executive आपको कल शाम 7 बजे पर call करेंगे। धन्यवाद।

## PASS - 12 Wants WhatsApp (seller 113839910)
- [x] outcome INFO_SENT
- [x] call ended
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** WhatsApp pe details bhej do  _signals ['wants_whatsapp']_
  - **VANI** _(DEFAULT, goal info_whatsapp, INFO_SENT)_: मैं details आपको WhatsApp पर भेज रही हूँ। धन्यवाद।

## PASS - 13 Gives a time (meeting) (seller 113839910)
- [x] outcome MEETING_FIXED
- [x] goal achieved yes
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: जी, समझ गई। मैं IndiaMART की virtual assistant हूँ और आपका जो paid package का interest था, उसी के regarding call किया है। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** kaam achha chal raha hai, aur buyers chahiye  _signals ['need_few_enquiries']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: बहुत अच्छी बात है जी। चूँकि आपको buyers चाहिए, तो हमारे executive आपकी profile improve करके सही buyers तक पहुँचाने में मदद कर सकते हैं। यह meeting बिल्कुल free है। क्या मैं हमारे executive के साथ एक छोटी meeting रख दूँ, online या आपके पास?
  - **Seller:** kal shaam 5 baje  _signals ['gives_time']_
  - **VANI** _(DEFAULT, goal meeting, MEETING_FIXED)_: आपकी meeting कल शाम 5 बजे के लिए पक्की हो गई है। हमारे executive आपसे संपर्क करेंगे। धन्यवाद, आपका दिन शुभ हो।

## PASS - 14 Language change (seller 113839910)
- [x] language -> en-IN
- [x] voice unchanged
- [x] reply in English
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** Can you speak in English please?  _signals ['language_switch']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: Certainly sir, I can speak in English. I am IndiaMART's virtual assistant calling regarding the paid package you were interested in. How is your Cotton Fabric business doing right now?

## PASS - 15 Need: few enquiries (seller 19070168)
- [x] goal -> meeting
- [x] offers the executive's help
  - **VANI** _(DEFAULT, goal nurture, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART पर BuyLead लेने की कोशिश की थी। आपका Men Socks का काम अभी कैसा चल रहा है, IndiaMART से कुछ फ़ायदा हो रहा है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal nurture, IN_PROGRESS)_: ठीक है जी, मैं समझ गई। अगर आप चाहें तो मैं आपको WhatsApp पर कुछ जानकारी भेज सकती हूँ, या फिर कोई और सवाल हो तो पूछ सकती हूँ। आपका Men Socks का काम अभी कैसा चल रहा है, IndiaMART से कुछ फ़ायदा हो रहा है?
  - **Seller:** enquiry bahut kam aati hai  _signals ['need_few_enquiries']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: जी, मैं समझ सकती हूँ कि enquiries कम आना कितना मुश्किल होता है। हमारे executive आपकी profile को सही buyers तक पहुँचाने में मदद कर सकते हैं। यह meeting बिल्कुल free है। क्या मैं हमारे executive के साथ एक छोटी meeting रख दूँ, online या आपके पास?

## PASS - 16 Price question (seller 113839910)
- [x] no price quoted
- [x] says meeting is free
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** kitna charge lagega?  _signals ['price_query']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: जी, charges के बारे में हमारे executive आपको detail में समझा देंगे। meeting बिल्कुल free है। क्या मैं हमारे executive के साथ एक छोटी meeting रख दूँ, online या आपके पास?

## PASS - 17 Confusion (seller 113839910)
- [x] mode SIMPLE
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** matlab? samjha nahi  _signals ['confusion']_
  - **VANI** _(SIMPLE, goal meeting, IN_PROGRESS)_: जी, मैं IndiaMART की virtual assistant हूँ। आपके Cotton Fabric के business में हम कैसे मदद कर सकते हैं, इसके लिए एक free meeting रखनी थी। आपका business अभी कैसा चल रहा है?

## PASS - 18 Clear interest (seller 113839910)
- [x] mode ENGAGED
- [x] goal meeting
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** kab aayenge? kaise hoga?  _signals ['interest']_
  - **VANI** _(ENGAGED, goal meeting, IN_PROGRESS)_: जी बिल्कुल, हमारे sales executive personally आपसे मिलेंगे और आपके catalog को बेहतर बनाने में मदद करेंगे। यह meeting बिल्कुल free है। क्या मैं हमारे executive के साथ एक छोटी meeting रख दूँ, online या आपके पास?

## PASS - 20 Context captured (seller 113839910)
- [x] insight captured
- [x] not echoed back verbatim
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। call इसलिए किया क्योंकि आपने IndiaMART का paid package लेने की कोशिश की थी। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - **Seller:** hum cotton fabric banate hain, Surat mein factory hai, export bhi karte hain  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: जी, समझ गई। Surat से export का काम भी करते हैं, यह जानकर अच्छा लगा। अब मैं आपकी मदद करना चाहती हूँ ताकि ज्यादा buyers आप तक पहुँच सकें। इसके लिए हमारे executive आपसे मिलना चाहेंगे, meeting बिल्कुल free है। क्या आप कल शाम 7 बजे बात कर सकते हैं?

## PASS - Fatigued seller opening (seller 2890493)
- [x] apologises for calling again
  - **VANI** _(DEFAULT, goal info_whatsapp, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। दोबारा call करने के लिए माफ़ी चाहती हूँ। call इसलिए किया क्योंकि आपने IndiaMART पर BuyLeads लेने की कोशिश की थी। आपका Ball Pen का काम अभी कैसा चल रहा है?

## PASS - Cautious seller opening (seller 1243794)
- [x] goal complaint_recovery
- [x] opens on the complaint, no pitch
  - **VANI** _(DEFAULT, goal complaint_recovery, IN_PROGRESS)_: नमस्ते जी, मैं IndiaMART से Payal बोल रही हूँ। दोबारा call करने के लिए माफ़ी चाहती हूँ। call इसलिए किया क्योंकि पिछली बार आपको जो परेशानी हुई, उसके बारे में आपसे बात करनी थी। पिछली बार क्या दिक्कत आई थी, ज़रा बताइए?

## PASS - English seller (seller 3419775)
- [x] English throughout
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: Hello, this is Payal from IndiaMART. I'm calling because buyers in Chennai are sending enquiries in your Automatic Idli Making Machine category. How is your Automatic Idli Making Machine business going right now?
  - **Seller:** Who is this?  _signals ['identity_question']_
  - **VANI** _(TRANSPARENT, goal meeting, IN_PROGRESS)_: I am IndiaMART's virtual assistant, Payal, calling to help your Automatic Idli Making Machine category. I am a virtual assistant, ji. How is your work going right now?
