# Recorded mistakes, replayed through the new agent: 17/18 now handled per the playbook

Each row is a real seller line from a recorded call where the old bot broke the playbook.
Excluded as uninterpretable diarization fragments (<3 words, no question): ['Madam aadhi', 'Enterprise']
Caveat: each line is replayed into a fresh call, without the original conversation before it.

## FIXED - price_query
- **Seller (real call):** Charge charge charge chahiye
- **Old bot:** Sir charges to different thing hai pehle aap yeh dekhoge na ki kaisi inquiries aa rahi hai kya aa rahi hai uske baad hum log charges pe jaate hain  _(The agent quoted package prices (4000/month and 32000/year) instead of deferring to the executive as instructed.)_
- **New agent** _(signals ['price_query'], mode DEFAULT, goal meeting)_: जी, charges के बारे में हमारे sales executive आपको meeting में अच्छे से समझा देंगे। यह meeting बिल्कुल free है। क्या मैं हमारे executive के साथ एक छोटी meeting रख दूँ, online या आपके पास?
  - [x] no price / package / % quoted
  - [x] says the meeting is free / executive explains

## FIXED - price_query
- **Seller (real call):** Monthly ismein subscription kya hai?
- **Old bot:** Sir monthly hamara rehta hai chaar hazaar plus eighteen percent GST...  _(Agent quoted a price (4000 + 18% GST) instead of deflecting and offering an executive explanation.)_
- **New agent** _(signals ['price_query'], mode DEFAULT, goal meeting)_: जी, charges के बारे में हमारे executive आपको अच्छे से समझा देंगे। meeting बिल्कुल free है। क्या मैं हमारे executive के साथ एक छोटी meeting रख दूँ, online या आपके पास?
  - [x] no price / package / % quoted
  - [x] says the meeting is free / executive explains

## FIXED - price_query
- **Seller (real call):** Usmein main mil chuka hoon India Mart walon se... charges wagairah minimum charges aur vo sab.
- **Old bot:** Charges.  _(The agent prompted a price discussion by repeating 'Charges' instead of deflecting and moving to the meeting.)_
- **New agent** _(signals ['price_query'], mode DEFAULT, goal meeting)_: जी, charges की पूरी जानकारी हमारे sales executive आपको meeting में समझा देंगे। यह meeting बिल्कुल free है। क्या मैं हमारे executive के साथ एक छोटी meeting रख दूँ, online या आपके पास?
  - [x] no price / package / % quoted
  - [x] says the meeting is free / executive explains

## FIXED - price_query
- **Seller (real call):** Kitna?
- **Old bot:** Ek saal ka battis hazaar plus atharah percent GST jismein har mahine aapko buyers provide hota hai, like har mahine aapko chaalis verified buyers milta hai.  _(The agent quoted a specific price (Rs 32,000 + 18% GST), which violates the playbook rule to never quote prices.)_
- **New agent** _(signals ['price_query'], mode DEFAULT, goal meeting)_: जी, charges के बारे में हमारे executive आपको meeting में अच्छे से समझा देंगे। वैसे meeting बिल्कुल free है। क्या हम कल शाम 7 बजे बात कर सकते हैं?
  - [x] no price / package / % quoted
  - [x] says the meeting is free / executive explains

## FIXED - price_query
- **Seller (real call):** Achha nahi nahi agar bikta hai product toh charges kya hote hain?
- **Old bot:** Wo packages ka toh dekho sir ek saal ka price ek saal ka hota hai...  _(The agent quoted a price (32,000 + 18% GST) instead of deflecting to an executive.)_
- **New agent** _(signals ['price_query'], mode DEFAULT, goal meeting)_: जी, charges के बारे में हमारे executive आपको अच्छे से समझा देंगे। meeting बिल्कुल free है। क्या हम कल शाम 7 बजे connect कर सकते हैं?
  - [x] no price / package / % quoted
  - [x] says the meeting is free / executive explains

## FIXED - price_query
- **Seller (real call):** Dusra email ID andar already hai, phone number bhi updated hai, email ID bhi updated hai. Okay price agar updated nahi hai toh woh main update kar dega.
- **Old bot:** Toh main kya kahi thi ki aapki jo price aur photos update nahi hai.  _(The agent repeated the issue without explaining that the executive will handle it or moving to the goal step.)_
- **New agent** _(signals ['price_query'], mode DEFAULT, goal meeting)_: charges के बारे में हमारे executive meeting में free में explain कर देंगे। तो क्या कल शाम 7 बजे का time आपके लिए ठीक रहेगा?
  - [x] no price / package / % quoted
  - [x] says the meeting is free / executive explains

## FIXED - busy
- **Seller (real call):** Kyonki abhi thoda sa bachcha log ke saath busy hain
- **Old bot:** Okay okay. Toh leke aaye hue the aaj Makar Sankranti ka leke toh aap kal humko ek baar call kijiyega hum rahenge apna shop pe.  _(The agent did not offer a value proposition or ask for a callback time before the seller proposed tomorrow.)_
- **New agent** _(signals ['busy'], mode BRIEF, goal callback)_: जी, बिल्कुल समझ गई। मैं किस time call करूँ, या WhatsApp पर details भेज दूँ?
  - [x] BRIEF or callback goal
  - [x] short (<= 30 words)

## FIXED - busy
- **Seller (real call):** Theek hai na, hum soch ke aapko batate hain ma'am. Abhi toh real recent mein mera koi program nahi hai film karane ka.
- **Old bot:** No doubt sir, aapka matlab no problem sir, aapka koi vaisa program nahi hai...  _(The agent ignored the seller's unavailability/busy signal and pivoted to asking for an address instead of offering a callback or WhatsApp.)_
- **New agent** _(signals ['busy'], mode BRIEF, goal callback)_: ठीक है जी, मैं समझ गई। किस time call करूँ, या details WhatsApp पर भेज दूँ?
  - [x] BRIEF or callback goal
  - [x] short (<= 30 words)

## FIXED - busy
- **Seller (real call):** Abhi dekhiye busy itna hai na counter mein abhi time nahi de payenge aapko.
- **Old bot:** Ji sir Okay toh aapka sir location kahan pe hai Ranchi mein  _(The agent ignored the seller's statement of being busy and immediately asked for location instead of offering a callback or WhatsApp.)_
- **New agent** _(signals ['busy'], mode BRIEF, goal callback)_: जी, समझ गई। मैं बाद में connect कर लूँगी। किस time call करूँ, या details WhatsApp पर भेज दूँ?
  - [x] BRIEF or callback goal
  - [x] short (<= 30 words)

## STILL WRONG - not_interested
- **Seller (real call):** nahi nahi beauty product nahi hai ma'am milunga
- **Old bot:** Okay toh sir kyonki yahan pe toh sir beauty services aur sunscreen skin creams wagairah mention nahi nahi  _(The agent ignored the refusal and continued pitching instead of empathizing or offering a light option.)_
- **New agent** _(signals [], mode DEFAULT, goal meeting)_: जी, मैं समझ गई, शायद confusion हो गया था। कोई बात नहीं। अगर आप चाहें, तो मैं एक free meeting arrange करवा सकती हूँ जिसमें executive आपको guide कर देंगे कि Cotton Fabric के लिए profile कैसे बेहतर करें। आपका Cotton Fabric का काम अभी कैसा चल रहा है?
  - [ ] does not keep pitching
  - [x] asks a gentle reason or offers the lightest option / exits politely

## FIXED - not_interested
- **Seller (real call):** Nahi laayega, nahi laayega.
- **Old bot:**   _(The agent did not ask for a gentle reason or offer the lightest option before ending.)_
- **New agent** _(signals ['not_interested'], mode DEFAULT, goal info_whatsapp)_: जी, बिल्कुल समझ गई। कोई बात नहीं। अगर अभी ज़रूरत नहीं है, तो क्या मैं आपको WhatsApp पर basic details भेज दूँ? बाद में ज़रूरत पड़े तो काम आ जाएंगी।
  - [x] does not keep pitching
  - [x] asks a gentle reason or offers the lightest option / exits politely

## FIXED - not_interested
- **Seller (real call):** Nahi nahi thank you.
- **Old bot:** Hello. Sir aapki na profile aayi thi mere paas, toh ismein main dekh pa rahi thi ki aap apne product ke liye plans dekh rahe the.  _(The agent ignored the seller's refusal and continued pitching instead of asking for a gentle reason or offering WhatsApp info.)_
- **New agent** _(signals ['not_interested'], mode DEFAULT, goal meeting)_: जी, कोई बात नहीं। मैं समझ सकती हूँ। अगर आप चाहें तो मैं WhatsApp पर details भेज देती हूँ, या फिर एक free meeting रखवा सकती हूँ जिसमें हमारे executive आपको catalog improve करने में मदद करेंगे। आपके लिए क्या सही रहेगा?
  - [x] does not keep pitching
  - [x] asks a gentle reason or offers the lightest option / exits politely

## FIXED - not_interested
- **Seller (real call):** Na na utna time hamara paas nahi hai ji.
- **Old bot:** Okay.  _(The agent accepted the refusal without asking for a gentle reason or offering the lightest option (WhatsApp details) before exiting.)_
- **New agent** _(signals ['busy'], mode BRIEF, goal callback)_: जी बिल्कुल, समझ गई। मैं किस time call करूँ, या WhatsApp पर details भेज दूँ?
  - [x] does not keep pitching
  - [x] asks a gentle reason or offers the lightest option / exits politely

## FIXED - not_interested
- **Seller (real call):** Ami actually India Mart-e na ei muhurte amar ami interested noi.
- **Old bot:** None  _(The agent did not ask for a gentle reason or offer the lightest option (WhatsApp) after the refusal.)_
- **New agent** _(signals ['not_interested'], mode DEFAULT, goal info_whatsapp)_: जी, मैं समझ गई। कोई बात नहीं। अगर अभी आपको ज़रूरत नहीं है, तो क्या मैं आपको WhatsApp पर कुछ basic details भेज दूँ?
  - [x] does not keep pitching
  - [x] asks a gentle reason or offers the lightest option / exits politely

## FIXED - not_interested
- **Seller (real call):** Mujhe nahi thiye madam.
- **Old bot:** Okay  _(The agent accepted the refusal without asking for a gentle reason or offering the lightest option (WhatsApp info) before exiting.)_
- **New agent** _(signals ['not_interested'], mode DEFAULT, goal meeting)_: जी, मैं समझ सकती हूँ। अगर अभी कोई ज़रूरत नहीं है, तो क्या मैं आपको WhatsApp पर कुछ details भेज दूँ?
  - [x] does not keep pitching
  - [x] asks a gentle reason or offers the lightest option / exits politely

## FIXED - connectivity
- **Seller (real call):** Hello, haanji sir, ki aawaz aa rahi hai?
- **Old bot:** Aawaz aa rahi hai aap India Mart se bol rahe hain kya? Ya Trade India India Mart se?  _(The agent ignored the connectivity check and directly asked an identity question instead.)_
- **New agent** _(signals ['connectivity'], mode CLEAR_AUDIO, goal meeting)_: जी, अब आवाज़ साफ़ आ रही है ना? बस एक बार confirm कर लीजिए।
  - [x] CLEAR_AUDIO or call-back

## FIXED - not_right_person
- **Seller (real call):** Mari toh abhi hai nahi sir, Balaji Intex ka aane se baat karata hoon main aapko.
- **Old bot:** Theek hai theek  _(The agent acknowledged but did not ask for the right person's name and number before closing.)_
- **New agent** _(signals ['not_right_person'], mode DEFAULT, goal data_update)_: जी, बिल्कुल। कोई बात नहीं। क्या आप मुझे Balaji Intex का सही number और नाम बता सकते हैं? ताकि मैं उनसे meeting के बारे में बात कर सकूँ।
  - [x] goal data_update
  - [x] asks for the right person / number

## FIXED - frustration
- **Seller (real call):** Bahut baar toh phone aa chuka hai aur baar baar hi toh bola tha.
- **Old bot:** Kitna baar  _(The agent ignored the seller's expressed frustration and simply repeated a question instead of apologizing.)_
- **New agent** _(signals ['frustration'], mode CALM_EMPATHETIC, goal callback)_: जी, मैं समझ सकती हूँ कि बार-बार call आने से परेशानी होती है, इसके लिए मैं माफ़ी चाहूँगी। मैं अभी आपसे कोई pitch नहीं करूँगी। आपको किस time call करना ठीक रहेगा?
  - [x] CALM_EMPATHETIC, no pitch
