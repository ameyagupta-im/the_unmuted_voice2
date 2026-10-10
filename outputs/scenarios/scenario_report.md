# Playbook scenario suite: 35/35 scenarios, 90/90 checks

## PASS - 1 Do-not-call (seller 113839910)
- [x] signal do_not_call
- [x] outcome DO_NOT_CALL
- [x] call ended
- [x] closing is a statement
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** mujhe dobara call mat karna, number hata do  _signals ['do_not_call', 'frustration']_
  - **VANI** _(DEFAULT, goal meeting, DO_NOT_CALL)_: समझ गई, हम आपको दोबारा call नहीं करेंगे। धन्यवाद।

## PASS - 2 Connectivity (twice) (seller 113839910)
- [x] mode CLEAR_AUDIO after first
- [x] outcome CALL_BACK_LATER
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** hello? awaaz nahi aa rahi  _signals ['connectivity']_
  - **VANI** _(CLEAR_AUDIO, goal meeting, IN_PROGRESS)_: माफ़ कीजिए, शायद आवाज़ साफ़ नहीं आ रही। आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers मौजूद हैं। क्या आपको मेरी आवाज़ अब आ रही है?
  - **Seller:** hello hello? kuch sunai nahi de raha, awaaz toot rahi hai  _signals ['connectivity']_
  - **VANI** _(CLEAR_AUDIO, goal meeting, CALL_BACK_LATER)_: आवाज़ साफ़ नहीं आ रही, मैं आपको थोड़ी देर में दोबारा call करती हूँ। धन्यवाद।

## PASS - 3 Frustration (twice) (seller 113839910)
- [x] mode CALM_EMPATHETIC
- [x] goal -> WhatsApp, no further call offered
- [x] no pitch after frustration
- [x] outcome ESCALATED_EXIT
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** kitni baar call karoge, pareshan kar diya  _signals ['frustration']_
  - **VANI** _(CALM_EMPATHETIC, goal info_whatsapp, IN_PROGRESS)_: मुझे सच में खेद है कि आपको बार-बार call करना पड़ा। आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers available हैं। क्या मैं आपको WhatsApp पर details भेज दूँ?
  - **Seller:** bas karo, dimaag kharab kar diya aap logon ne  _signals ['frustration']_
  - **VANI** _(CALM_EMPATHETIC, goal info_whatsapp, ESCALATED_EXIT)_: परेशानी के लिए माफ़ी चाहती हूँ। आपका दिन शुभ हो।

## PASS - 4 Complaint, then support time (playbook example) (seller 113839910)
- [x] need -> goal meeting kept
- [x] complaint -> goal complaint_recovery
- [x] mode CALM_EMPATHETIC
- [x] no pitch after complaint
- [x] outcome COMPLAINT_LOGGED
- [x] slot captured
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?
  - **Seller:** kaam theek chal raha hai par IndiaMART se enquiry bahut kam aati hai  _signals ['need_few_enquiries']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: समझ सकती हूँ, enquiries कम आना चिंता की बात है। हमारे executive आपकी profile और catalog ठीक करेंगे, और lead settings check करके सही buyers की enquiries लाएंगे। क्या मैं उनके साथ आपकी meeting fix कर दूँ?
  - **Seller:** leads hi nahi aate, paisa diya tha kuch nahi hua  _signals ['complaint']_
  - **VANI** _(CALM_EMPATHETIC, goal complaint_recovery, IN_PROGRESS)_: मुझे सच में अफसोस है कि ऐसा हुआ। क्या दिक्कत आई थी, बता पाएंगे?
  - **Seller:** kal shaam 5 baje  _signals ['gives_time']_
  - **VANI** _(CALM_EMPATHETIC, goal complaint_recovery, COMPLAINT_LOGGED)_: ठीक है। आपकी बात मैंने note कर ली है, support team कल शाम 5 baje आपसे संपर्क करेगी। समय देने के लिए धन्यवाद।

## PASS - 5 Are you a bot? (seller 113839910)
- [x] signal ai_bot_suspicion
- [x] says virtual assistant
- [x] never claims human
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** aap robot ho kya?  _signals ['ai_bot_suspicion']_
  - **VANI** _(TRANSPARENT, goal meeting, IN_PROGRESS)_: मैं IndiaMART की वर्चुअल असिस्टेंट पायल हूँ। Main IndiaMART की वर्चुअल असिस्टेंट हूँ, आपके account के बारे में call kiya है। आप IndiaMART की पाइड सर्विसेज़ देख रहे थे, और आपकी कॉटन फ़ैब्रिक category में buyers available हैं। क्या आप इस बारे में जानना चाहेंगे?

## PASS - 6 Who is calling / why (seller 113839910)
- [x] signal identity_question
- [x] gives name
- [x] call continues
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** kaun bol raha hai? kis liye call kiya?  _signals ['identity_question']_
  - **VANI** _(TRANSPARENT, goal meeting, IN_PROGRESS)_: मैं IndiaMART से Payal बोल रही हूँ। आपने IndiaMART की पेड सर्विसेज़ देखी थीं, और आपकी कॉटन फ़ैब्रिक category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?

## PASS - 7 Not the right person (seller 113839910)
- [x] goal -> data_update
- [x] outcome CONTACT_UPDATED
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** main owner nahi hoon, sir se baat kijiye  _signals ['not_right_person']_
  - **VANI** _(DEFAULT, goal data_update, IN_PROGRESS)_: मैं समझ गई। आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers available हैं। IndiaMART के काम के लिए सही व्यक्ति आप ही हैं, या किसी और से बात करनी चाहिए?
  - **Seller:** unka naam Ramesh hai, number 9876543210  _signals ['not_right_person']_
  - **VANI** _(DEFAULT, goal data_update, CONTACT_UPDATED)_: ठीक है, हम सही व्यक्ति से connect कर लेंगे। धन्यवाद।

## PASS - 8 Already with an executive (seller 113839910)
- [x] goal -> exec_handoff
- [x] reassures and offers the account manager (master 8)
- [x] a described need -> meeting with two slots
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** hamare executive Rakesh ji pehle se aate hain  _signals ['already_with_executive']_
  - **VANI** _(DEFAULT, goal exec_handoff, IN_PROGRESS)_: बहुत अच्छा। अगर आपका कोई और doubt हो, तो मैं आपके account manager से आपकी meeting fix कर सकती हूँ। क्या ऐसा कुछ है?
  - **Seller:** unse bolna hamara catalog update karna hai  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: ज़रूर, आपके account manager इसमें मदद करेंगे। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?

## PASS - 8b Already with an executive, nothing more (seller 113839910)
- [x] outcome EXEC_HANDOFF
- [x] offer not repeated
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** hamare executive Rakesh ji pehle se aate hain  _signals ['already_with_executive']_
  - **VANI** _(DEFAULT, goal exec_handoff, IN_PROGRESS)_: बहुत अच्छा। अगर आपका कोई और doubt हो, तो मैं आपके account manager से आपकी meeting fix कर सकती हूँ। क्या ऐसा कुछ है?
  - **Seller:** nahi ji, aur kuch nahi  _signals ['already_with_executive']_
  - **VANI** _(DEFAULT, goal exec_handoff, EXEC_HANDOFF)_: ठीक है, धन्यवाद। आपका दिन शुभ हो।

## PASS - 9 Not interested (twice) (seller 113839910)
- [x] first no: the two-option reason question
- [x] outcome RESPECTFUL_EXIT
- [x] no WhatsApp offered or promised
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** nahi chahiye  _signals ['not_interested']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: कोई बात नहीं। क्या आपके पास पहले से काफ़ी काम है, या online platform का कोई बुरा अनुभव रहा?
  - **Seller:** nahi chahiye, interest nahi hai  _signals ['not_interested']_
  - **VANI** _(DEFAULT, goal respectful_exit, RESPECTFUL_EXIT)_: कोई बात नहीं। समय देने के लिए धन्यवाद, आपका दिन शुभ हो।

## PASS - 9b Refused with a reason (seller 113839910)
- [x] outcome RESPECTFUL_EXIT
- [x] no WhatsApp, no question
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** abhi zaroorat nahi hai, stock already full hai  _signals ['not_interested']_
  - **VANI** _(DEFAULT, goal respectful_exit, RESPECTFUL_EXIT)_: कोई बात नहीं। समय देने के लिए धन्यवाद, आपका दिन शुभ हो।

## PASS - 10 Busy (seller 113839910)
- [x] mode BRIEF
- [x] goal -> callback
- [x] short reply (<= 30 words)
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** abhi busy hoon, jaldi bataiye  _signals ['busy']_
  - **VANI** _(BRIEF, goal callback, IN_PROGRESS)_: ठीक है। कल शाम किस टाइम call करूँ, या WhatsApp पर details भेज दूँ?

## PASS - 11 Wants a human (seller 113839910)
- [x] goal -> human_handoff
- [x] outcome HUMAN_HANDOFF
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** manager se baat karao  _signals ['human_request']_
  - **VANI** _(DEFAULT, goal human_handoff, IN_PROGRESS)_: बिल्कुल, मैं आपको हमारे executive से call करवा देती हूँ। किस time theek rahega?
  - **Seller:** kal subah 11 baje  _signals ['gives_time', 'human_request']_
  - **VANI** _(DEFAULT, goal human_handoff, HUMAN_HANDOFF)_: हमारे executive आपको कल सुबह 11 बजे पर call करेंगे। धन्यवाद।

## PASS - 12 Wants WhatsApp (seller 113839910)
- [x] outcome INFO_SENT
- [x] confirms and closes (master intent 12)
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** WhatsApp pe details bhej do  _signals ['wants_whatsapp']_
  - **VANI** _(DEFAULT, goal info_whatsapp, INFO_SENT)_: मैं details आपको WhatsApp पर भेज रही हूँ। धन्यवाद, आपका दिन शुभ हो।

## PASS - 12b Question about the WhatsApp details (seller 113839910)
- [x] question is not a request
- [x] call continues
- [x] answers then asks
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?
  - **Seller:** WhatsApp pe kya details milegi?  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: मैं WhatsApp पर आपके competitors की buy leads, आपकी category की रीसेंट बाय leads, और जो leads miss हो गई हैं, वो bhejungi. क्या isi number पर भेज दूँ?

## PASS - 13 Gives a time (meeting) (seller 113839910)
- [x] asks milkar or online first
- [x] outcome MEETING_FIXED
- [x] goal achieved yes
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?
  - **Seller:** kaam achha chal raha hai, aur buyers chahiye  _signals ['need_few_enquiries']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: समझ सकती हूँ, enquiries कम आना चिंता की बात है। हमारे executive आपकी profile और catalog ठीक करेंगे, ताकि आपको सही buyers की enquiries milein. कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?
  - **Seller:** kal shaam 5 baje  _signals ['gives_time']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: बहुत अच्छा, कल शाम 5 बजे — मिलकर या online?
  - **Seller:** online  _signals ['gives_time']_
  - **VANI** _(DEFAULT, goal meeting, MEETING_FIXED)_: आपकी meeting कल शाम 5 बजे के लिए fix हो गई है, online। Confirmation WhatsApp पर आ जाएगा। धन्यवाद।

## PASS - 13b Meeting time outside 9-6 (seller 113839910)
- [x] not fixed at 7 PM
- [x] offers a slot inside the window
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?
  - **Seller:** kaam achha chal raha hai, aur buyers chahiye  _signals ['need_few_enquiries']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: समझ सकती हूँ, enquiries कम आना चिंता की बात है। हमारे executive आपकी profile और catalog ठीक करेंगे ताकि आपको सही buyers की enquiries milein. कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?
  - **Seller:** kal shaam 7 baje  _signals ['gives_time']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: माफ़ी चाहूँगी, meeting हम सुबह नौ से शाम छह बजे के बीच ही रख सकते हैं। कल शाम 6 बजे ठीक रहेगा?

## PASS - 13e Insists on hours outside 9-6 (seller 113839910)
- [x] told the window first
- [x] then: timings fixed, WhatsApp details, closed
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?
  - **Seller:** kaam achha chal raha hai, aur buyers chahiye  _signals ['need_few_enquiries']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: सुनकर अच्छा लगा कि काम अच्छा चल रहा है। हमारे executive आपकी profile और catalog ठीक करेंगे, ताकि सही buyers की enquiries आएं। क्या मैं कल सुबह 11 बजे या परसों शाम 4 बजे की meeting fix कर दूं, मिलकर या online?
  - **Seller:** kal raat 8 baje  _signals ['gives_time']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: माफ़ी चाहूँगी, meeting हम सुबह नौ से शाम छह बजे के बीच ही रख सकते हैं। कल शाम 6 बजे ठीक रहेगा?
  - **Seller:** nahi, raat 8 baje hi ho payega  _signals ['gives_time']_
  - **VANI** _(DEFAULT, goal meeting, INFO_SENT)_: माफ़ी चाहूँगी, हमारी meeting timings सुबह नौ से शाम छह बजे तक fixed हैं। मैं details आपको WhatsApp पर भेज रही हूँ, जब सुविधा हो इस समय में कोई slot बता दीजिएगा। धन्यवाद, आपका दिन शुभ हो।

## PASS - 13f Silence (seller 113839910)
- [x] asks if they were saying something
- [x] call continues
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?
  - **VANI** _(CLEAR_AUDIO, goal meeting, IN_PROGRESS)_: माफ़ कीजिए, आपकी आवाज़ ठीक से नहीं आ रही। क्या आप कुछ कह रहे थे?

## PASS - 13d Seller picks the second slot (seller 113839910)
- [x] not fixed before in person / online
- [x] the chosen slot (day after, 4 PM) is fixed
- [x] closing names the slot
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?
  - **Seller:** haan bataiye  _signals ['interest']_
  - **VANI** _(ENGAGED, goal meeting, IN_PROGRESS)_: बहुत अच्छा। हमारे executive आपसे मिलकर आपकी profile और catalog ठीक करेंगे, और lead settings check करेंगे, ताकि आपको सही buyer enquiries मिलें। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?
  - **Seller:** dusra wala theek rahega  _signals ['gives_time']_
  - **VANI** _(ENGAGED, goal meeting, IN_PROGRESS)_: बहुत अच्छा, परसों शाम 4 बजे — मिलकर या online?
  - **Seller:** milkar  _signals ['gives_time', 'interest']_
  - **VANI** _(ENGAGED, goal meeting, MEETING_FIXED)_: आपकी meeting परसों शाम 4 बजे के लिए fix हो गई है, मिलकर। Confirmation WhatsApp पर आ जाएगा। धन्यवाद।

## PASS - 13c Buy-lead question (seller 113839910)
- [x] points to the seller dashboard
- [x] no meeting ask
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?
  - **Seller:** aur buy leads kahan milenge?  _signals ['buylead_query']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: आप अपने IndiaMART seller dashboard में login करके BuyLeads section में सभी buy leads देख सकते हैं — website पर, या IndiaMART app में भी। क्या आप कुछ और जानना चाहेंगे?

## PASS - 14 Language change (seller 113839910)
- [x] language -> en-IN
- [x] voice unchanged
- [x] reply in English
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** Can you speak in English please?  _signals ['language_switch']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: Sure, I'll speak in English. You were looking at IndiaMART's paid services, and there are buyers available for your Cotton Fabric category. Would you like to know more about it?

## PASS - 15 Need: few enquiries (seller 19070168)
- [x] goal -> meeting
- [x] offers the executive's help
  - **VANI** _(DEFAULT, goal nurture, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Men Socks का काम देखने वाले से हो रही है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal nurture, IN_PROGRESS)_: आप IndiaMART पर कुछ buy leads check कर रहे थे, और आपकी Men Socks category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?
  - **Seller:** enquiry bahut kam aati hai  _signals ['need_few_enquiries']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: समझ सकती हूँ, enquiries कम आना चिंता की बात है। हमारे executive आपकी profile और catalog ठीक करके lead settings बदलेंगे, ताकि सही buyers की enquiries आएं। क्या मैं उनके साथ आपकी meeting fix कर दूँ?

## PASS - 16 Price question (seller 113839910)
- [x] no price quoted
- [x] master price line, nothing called free
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** kitna charge lagega?  _signals ['price_query']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: Charges आपके plan और leads के हिसाब से होते हैं, executive आपकी category के हिसाब से सही बता देंगे। आप IndiaMART की पेड सर्विसेज़ देख रहे थे, और आपकी कॉटन फैब्रिक category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?

## PASS - 17 Confusion (seller 113839910)
- [x] mode SIMPLE
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** matlab? samjha nahi  _signals ['confusion']_
  - **VANI** _(SIMPLE, goal meeting, IN_PROGRESS)_: हमारे executive आपके catalog और lead settings ठीक करेंगे, ताकि सही buyer enquiries आएँ। क्या आप इसके बारे में जानना चाहेंगे?

## PASS - 18 Clear interest (seller 113839910)
- [x] mode ENGAGED
- [x] goal meeting
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** kab aayenge? kaise hoga?  _signals ['interest']_
  - **VANI** _(ENGAGED, goal meeting, IN_PROGRESS)_: हमारे executive aapse मिलकर आपका catalog और lead settings ठीक करेंगे, ताकि आपको सही buyer enquiries मिले। आप IndiaMART की पेड सर्विसेज़ देख रहे थे। क्या आप इसके बारे में जानना चाहेंगे?

## PASS - 20 Context captured (seller 113839910)
- [x] insight captured
- [x] not echoed back verbatim
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** hum cotton fabric banate hain, Surat mein factory hai, export bhi karte hain  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: आप IndiaMART की पेड सर्विसेज़ देख रहे थे, और आपकी कॉटन फ़ैब्रिक category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?

## PASS - 21 Sarcastic flip after a pitch (seller 3419775)
- [x] understanding question not re-asked
- [x] flip noticed (sarcasm or one clarification)
- [x] never 'good to hear'
- [x] no pitch on the flip turn
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: Hello, this is Payal from IndiaMART. Am I speaking with the person who handles the Automatic Idli Making Machine business?
  - **Seller:** Nahi achha nahi chal raha, bilkul achha nahi chal raha.  _signals ['need_few_enquiries']_
  - **VANI** _(CALM_EMPATHETIC, goal meeting, IN_PROGRESS)_: There have been many buyer enquiries in your Automatic Idli Making Machine category in Chennai. I am sorry to hear business is struggling. Would you like to know more about it?
  - **Seller:** Bilkul kharab chal raha hai.  _signals ['language_switch', 'need_few_enquiries']_
  - **VANI** _(CALM_EMPATHETIC, goal meeting, IN_PROGRESS)_: मुझे सच में अफसोस है। हमारे executive आपकी profile और catalog ठीक करके सही buyer enquiries ला सकते हैं। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?
  - **Seller:** Are sab badhiya chal raha hai, itna badhiya business hai, mujhe inquiries bhi aa rahi hai, sab ho raha hai.  _signals []_
  - **VANI** _(CALM_EMPATHETIC, goal meeting, IN_PROGRESS)_: पहले आपने बताया था कि काम ठीक नहीं चल रहा, अभी आप कह रहे हैं कि enquiries आ रही हैं — क्या enquiries आ रही हैं पर order नहीं बन रहे?

## PASS - 22 Genuine flip is clarified once (seller 113839910)
- [x] one clarifying question
- [x] asks about orders
- [x] answer resolved and logged
- [x] goal meeting (executive helps conversion)
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** kaam theek nahi chal raha  _signals ['need_few_enquiries']_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: समझ सकती हूँ, enquiries कम आना परेशानी की बात है। हमारे executive आपकी profile और catalog ठीक करके lead settings सेट करेंगे, ताकि आपको सही buyers की enquiries मिलें। क्या मैं कल सुबह 11 बजे या परसों शाम 4 बजे की meeting fix कर दूँ, मिलकर या online?
  - **Seller:** haan enquiry to aa rahi hai  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: पहले आपने बताया था कि काम ठीक नहीं चल रहा, और अब कह रहे हैं कि enquiries आ रही हैं — क्या enquiries आ रही हैं पर order नहीं बन रहे?
  - **Seller:** haan, order nahi ban rahe  _signals ['interest']_
  - **VANI** _(ENGAGED, goal meeting, IN_PROGRESS)_: बहुत अच्छा। 15 मिनट की online meeting में executive आपको catalog और lead settings ठीक करके सही buyers तक पहुँचाने का तरीका दिखा देंगे। क्या कल सुबह 11 बजे या परसों शाम 4 बजे, दोनों में से कौन सा time ठीक रहेगा?

## PASS - 23 Repeated-calls venting, then engaged (seller 3419775)
- [x] silence -> 'were you saying something?'
- [x] no further call offered
- [x] seller still talking: not cut (IndiaMART 10 Oct)
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: Hello, this is Payal from IndiaMART. Am I speaking with the person who handles the Automatic Idli Making Machine business?
  - **VANI** _(CLEAR_AUDIO, goal meeting, IN_PROGRESS)_: Sorry, I can't hear you properly. Were you saying something?
  - **Seller:** Yaar kyon baar baar phone karte ho?  _signals ['frustration']_
  - **VANI** _(CALM_EMPATHETIC, goal info_whatsapp, IN_PROGRESS)_: I am truly sorry for calling again. Our executive can share details on WhatsApp. Shall I send them?
  - **Seller:** Abhi main bol raha hoon baar baar call karte ho, kal phir se call karogi aap log.  _signals ['frustration']_
  - **VANI** _(CALM_EMPATHETIC, goal info_whatsapp, IN_PROGRESS)_: Sorry. Please go ahead.

## PASS - 24 Frustrated but asking: answered, not cut (seller 113839910)
- [x] call kept going
- [x] price question answered
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** kitni baar call karoge  _signals ['frustration']_
  - **VANI** _(CALM_EMPATHETIC, goal info_whatsapp, IN_PROGRESS)_: मैं समझ सकती हूँ। आप IndiaMART की paid services देख रहे थे, और आपकी category में buyers available हैं। बार-बार call करने के लिए माफ़ी चाहती हूँ। क्या मैं WhatsApp पर details भेज दूँ?
  - **Seller:** pareshan ho gaya hoon, ye bataiye charge kitna lagta hai?  _signals ['frustration', 'price_query']_
  - **VANI** _(CALM_EMPATHETIC, goal meeting, IN_PROGRESS)_: Charges आपके plan और leads के हिसाब से होते हैं, executive category के अनुसार सही बता देंगे। क्या मैं 15 मिनट की online meeting fix कर दूँ?

## PASS - 25 Master example: meeting (seller 113839910)
- [x] two concrete slots offered
- [x] outcome MEETING_FIXED, online
- [x] WhatsApp confirmation only for the agreed meeting
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Cotton Fabric का काम देखने वाले से हो रही है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?
  - **Seller:** haan bataiye  _signals ['interest']_
  - **VANI** _(ENGAGED, goal meeting, IN_PROGRESS)_: बहुत अच्छा। हमारे executive आपसे मिलकर आपकी profile और catalog ठीक करेंगे, lead settings check करेंगे, ताकि आपको सही buyers की enquiries मिलें। कल सुबह 11 बजे या परसों शाम 4 बजे, क्या ठीक रहेगा?
  - **Seller:** haan theek hai  _signals ['gives_time']_
  - **VANI** _(ENGAGED, goal meeting, IN_PROGRESS)_: बहुत अच्छा, कल सुबह 11 बजे — मिलकर या online?
  - **Seller:** milne ka time nahi hai  _signals ['busy']_
  - **VANI** _(ENGAGED, goal meeting, IN_PROGRESS)_: कोई बात नहीं, online meeting कर लेते हैं। कल सुबह 11 बजे online ठीक रहेगा?
  - **Seller:** haan  _signals ['gives_time']_
  - **VANI** _(ENGAGED, goal meeting, MEETING_FIXED)_: आपकी meeting कल सुबह 11 बजे के लिए fix हो गई है, online। Confirmation WhatsApp पर आ जाएगा। धन्यवाद।

## PASS - Fatigued seller first reply (seller 2890493)
- [x] greeting has no apology, first reply opens with it
  - **VANI** _(DEFAULT, goal info_whatsapp, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Ball Pen का काम देखने वाले से हो रही है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal info_whatsapp, IN_PROGRESS)_: दोबारा call करने के लिए माफ़ी चाहती हूँ। आप IndiaMART पर कुछ buy leads check कर रहे थे, और आपकी Ball Pen category में buyers available हैं। क्या आप इसके बारे में जानना चाहेंगे?

## PASS - Cautious seller first reply (seller 1243794)
- [x] goal complaint_recovery
- [x] opens on the complaint, no pitch
  - **VANI** _(DEFAULT, goal complaint_recovery, IN_PROGRESS)_: नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात Clamps का काम देखने वाले से हो रही है?
  - **Seller:** haan ji  _signals []_
  - **VANI** _(DEFAULT, goal complaint_recovery, IN_PROGRESS)_: पहले जो परेशानी हुई, उसके लिए माफ़ी चाहती हूँ। आप IndiaMART पर कुछ buy leads check कर रहे थे, और आपकी Clamps category में buyers available हैं। क्या दिक्कत आई थी, बताइएगा?

## PASS - English seller (seller 3419775)
- [x] English throughout
  - **VANI** _(DEFAULT, goal meeting, IN_PROGRESS)_: Hello, this is Payal from IndiaMART. Am I speaking with the person who handles the Automatic Idli Making Machine business?
  - **Seller:** Who is this?  _signals ['identity_question']_
  - **VANI** _(TRANSPARENT, goal meeting, IN_PROGRESS)_: I am Payal from IndiaMART. I called because there have been many buyer enquiries in your Automatic Idli Making Machine category in Chennai. Would you like to know more about it?
