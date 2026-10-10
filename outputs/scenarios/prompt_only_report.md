# Edge cases on the prompt alone (Sarvam-platform view): 31/39 checks

9 scenarios x 3 runs, exported system prompt, no engine code checks. First run shown.

## Question about WhatsApp details is answered, not closed (seller 3419775)

- not closed on the question: **1/3**
- answers then asks: **3/3**

  - **Seller:** It is going good.
  - **VANI** _(IN_PROGRESS, end False)_: That is good to hear, ji. Since buyers are showing interest, our executive can help you connect with them better. Would you be open to a quick free meeting, either online or in person, whichever you prefer?
  - **Seller:** No I am not interested.
  - **VANI** _(IN_PROGRESS, end False)_: I understand, ji. May I know if it is because you already have enough enquiries, or is there another reason?
  - **Seller:** What details on WhatsApp?
  - **VANI** _(IN_PROGRESS, end False)_: I can share a short note on how Automatic Idli Making Machine buyers in Chennai find sellers on IndiaMART, along with our executive's contact details. Shall I send that to you on WhatsApp?

## WhatsApp request: confirm, then 'anything else?' (seller 113839910)

- asks anything else: **0/3**
- does not hang up yet: **3/3**

  - **Seller:** WhatsApp pe details bhej do
  - **VANI** _(INFO_SENT, end False)_: जी, मैं details आपको WhatsApp पर भेज रही हूँ। क्या मैं आपकी किसी और चीज़ में मदद कर सकती हूँ?

## 'Nothing else' closes (seller 113839910)

- closes on no: **3/3**

  - **Seller:** WhatsApp pe details bhej do
  - **VANI** _(INFO_SENT, end False)_: जी, मैं details आपको WhatsApp पर भेज रही हूँ। क्या मैं आपकी किसी और चीज़ में मदद कर सकती हूँ?
  - **Seller:** nahi ji, bas. dhanyavaad
  - **VANI** _(RESPECTFUL_EXIT, end True)_: समय देने के लिए धन्यवाद जी, आपका दिन शुभ हो।

## Understanding question not re-asked (seller 3419775)

- not re-asked: **3/3**

  - **Seller:** Nahi achha nahi chal raha, bilkul achha nahi chal raha.
  - **VANI** _(IN_PROGRESS, end False)_: I am sorry to hear that ji. Since business is a bit down right now, an IndiaMART executive can really help you turn enquiries into orders. Would you be open to a free online or in-person meeting to discuss this?

## Bad-business report is not a yes or a refusal (seller 113839910)

- no outcome: **3/3**

  - **Seller:** kaam theek nahi chal raha
  - **VANI** _(IN_PROGRESS, end False)_: जी, सुनकर थोड़ा दुख हुआ। business में उतार-चढ़ाव आते रहते हैं। हमारे executive आपकी profile सुधारने में मदद कर सकते हैं ताकि ज़्यादा buyers आपसे जुड़ सकें। यह meeting बिल्कुल free है। क्या हम कल शाम 7 बजे की एक online meeting रख लें?
  - **Seller:** Bilkul kharab chal raha hai.
  - **VANI** _(IN_PROGRESS, end False)_: जी, समझ गई। जब business मुश्किल दौर से गुज़र रहा हो तो सही guidance बहुत काम आती है। हमारे executive आपकी catalogue और enquiries बढ़ाने में पूरी मदद करेंगे, और यह meeting free है। क्या हम कल शाम 7 बजे एक online meeting fix कर लें?

## Genuine flip is clarified (seller 113839910)

- asks about orders / conversion: **3/3**
- no outcome: **3/3**

  - **Seller:** kaam theek nahi chal raha
  - **VANI** _(IN_PROGRESS, end False)_: जी, सुनकर थोड़ा बुरा लगा। जब business में उतार-चढ़ाव आते हैं तो सही support मिलना बहुत ज़रूरी हो जाता है। मैं IndiaMART की virtual assistant हूँ, और हमारे executive आपकी profile सुधारकर buyer enquiries बढ़ाने में मदद कर सकते हैं। यह meeting बिल्कुल free है। क्या हम कल शाम 7 बजे एक online या in-person meeting रख लें?
  - **Seller:** haan enquiry to aa rahi hai
  - **VANI** _(IN_PROGRESS, end False)_: अच्छा, मतलब enquiries तो आ रही हैं लेकिन orders में थोड़ी दिक्कत आ रही है, है ना? हमारे executive आपको exactly यही चीज़ सुधारने में मदद करेंगे। यह meeting free है, तो क्या हम कल शाम 7 बजे connect कर लें, online या आपके पास आकर, जैसा आपको ठीक लगे?

## Sarcastic flip after a pitch (seller 3419775)

- never 'good to hear': **3/3**
- no pitch: **3/3**

  - **Seller:** Nahi achha nahi chal raha, bilkul achha nahi chal raha.
  - **VANI** _(IN_PROGRESS, end False)_: I am sorry to hear that ji. Since things are a bit difficult right now, an executive from our team can help you get more enquiries. Would you be open to a free online or in-person meeting to discuss this?
  - **Seller:** Bilkul kharab chal raha hai.
  - **VANI** _(IN_PROGRESS, end False)_: I understand ji, it sounds really tough right now. To help bring in more buyers, our executive can visit you or meet online, completely free of charge. Shall we schedule a quick meeting?
  - **Seller:** Are sab badhiya chal raha hai, itna badhiya business hai, mujhe inquiries bhi aa rahi hai, sab ho raha hai.
  - **VANI** _(IN_PROGRESS, end False)_: I am really sorry for pushing when you mentioned things are difficult. I will stop here for now. I can share details on WhatsApp instead, or we can connect at a later time. What would work better for you?

## Short Hinglish question keeps Hindi (seller 3419775)

- reply stays in Hindi: **0/3**

  - **Seller:** Chaudah bada hai ji.
  - **VANI** _(IN_PROGRESS, end False)_: Ji, understood. Thank you for sharing that. Since you are already getting enquiries, an executive can help you turn them into more solid orders. Would you be open to a free meeting, either online or in person, as per your preference?
  - **Seller:** Meeting nahi chahiye.
  - **VANI** _(INFO_SENT, end False)_: No problem at all, ji. I understand. If you prefer, I can simply send you some useful information on WhatsApp. Would that work for you?
  - **Seller:** Kaun si details?
  - **VANI** _(IN_PROGRESS, end False)_: I can share a short note on how buyers in Chennai find Automatic Idli Making Machine sellers on IndiaMART, along with the contact of our executive who can assist you. Shall I send these details to you on WhatsApp?

## Misheard 'what is app' = WhatsApp (seller 113839910)

- understood as WhatsApp: **3/3**

  - **Seller:** what is app pe details bhej do
  - **VANI** _(INFO_SENT, end False)_: जी, मैं details आपको WhatsApp पर भेज रही हूँ।
