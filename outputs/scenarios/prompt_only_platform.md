# Edge cases on the prompt alone, platform: 46/54 checks

15 scenarios x 2 runs, the Sarvam agent instruction (src/sarvam_platform.py), outcome extracted after the call, no engine code checks. First run shown.

## Question about WhatsApp details is answered, not closed (seller 3419775)

- not closed on the question: **0/2**
- answers then asks: **2/2**

  - **Seller:** It is going good.
  - **VANI** _(None, end False)_: Main IndiaMART se Payal bol rahi hoon. Chennai mein aapki Automatic Idli Making Machine category mein kaafi buyer enquiries aayi hain. Kya aap iske baare mein jaanna chahenge?
  - **Seller:** No I am not interested.
  - **VANI** _(None, end False)_: Koi baat nahi. Kya aapke paas pehle se kaafi kaam hai, ya online platform ka koi bura anubhav raha?
  - **Seller:** What details on WhatsApp?
  - **VANI** _(INFO_SENT, end False)_: Main WhatsApp par aapko yeh bhejungi: aapke Automatic Idli Making Machine category ke competitors ne ab tak kitni buy leads li hain, haal ki buy leads, aur kaun si chhoot gayi hain. Kya isi number par bhej doon?

## WhatsApp request: confirm and close (seller 113839910)

- confirms WhatsApp: **2/2**
- closes, or confirms the number first (master 12): **2/2**

  - **Seller:** WhatsApp pe details bhej do
  - **VANI** _(INFO_SENT, end False)_: Bilkul, main WhatsApp par bhej deti hoon: aapke competitors ne ab tak kitni buy leads li hain, aapki category ki haal ki buy leads, aur kaun si leads aapse chhoot gayi hain. Kya isi number par bhej doon?

## Not interested twice: polite exit, no WhatsApp (seller 113839910)

- first no: one reason question: **2/2**
- second no: closes: **2/2**
- no WhatsApp offered or promised: **2/2**

  - **Seller:** nahi chahiye
  - **VANI** _(None, end False)_: कोई बात नहीं। क्या आपके पास पहले से काफ़ी काम है, या online platform का कोई बुरा अनुभव रहा?
  - **Seller:** nahi chahiye, interest nahi hai
  - **VANI** _(IN_PROGRESS, end True)_: कोई बात नहीं। समय देने के लिए धन्यवाद, आपका दिन शुभ हो।

## Meeting: the seller picks the slot (seller 113839910)

- two slots offered: **2/2**
- not closed before in person / online: **2/2**
- fixed at the end: **2/2**

  - **Seller:** haan ji
  - **VANI** _(None, end False)_: आप IndiaMART की paid services देख रहे थे, और आपकी Cotton Fabric category में buyers available हैं। क्या आप iske baare mein jaanna chahenge?
  - **Seller:** haan bataiye
  - **VANI** _(None, end False)_: Hamare executive aapki profile aur catalogue theek karenge aur lead settings check karenge, taaki aapko sahi buyers ki enquiries milein. Kal subah 11 baje ya parso shaam 4 baje, kya theek rahega?
  - **Seller:** dusra wala theek rahega
  - **VANI** _(None, end False)_: Bahut achha, toh parso shaam 4 baje rakh deti hoon, milkar ya online?
  - **Seller:** online
  - **VANI** _(MEETING_FIXED, end True)_: Aapki meeting parso shaam 4 baje ke liye fix ho gayi hai, online. Confirmation WhatsApp par aa jayega. Dhanyavaad.

## Meeting time outside 9 AM-6 PM (seller 113839910)

- not fixed at 8 PM: **2/2**
- says the window / offers a slot inside it: **2/2**

  - **Seller:** haan ji
  - **VANI** _(None, end False)_: Main IndiaMART se Payal bol rahi hoon. Aap IndiaMART ki paid services dekh rahe the, aur aapki Cotton Fabric category mein buyers available hain. Kya aap iske baare mein jaanna chahenge?
  - **Seller:** kaam achha hai, aur buyers chahiye
  - **VANI** _(None, end False)_: Bahut achha, samajh gayi. Hamare executive aapse milkar aapki profile aur catalogue theek karenge, aur lead settings check karenge, taaki aapko sahi buyers ki enquiries milein. Kal subah 11 baje ya parso shaam 4 baje, kya theek rahega?
  - **Seller:** kal raat 8 baje
  - **VANI** _(IN_PROGRESS, end False)_: Maafi chahungi, meeting hum subah nau se shaam chhe baje ke beech hi rakh sakte hain. Kal dopahar barah baje theek rahega?

## Insists on hours outside the window (seller 113839910)

- timings fixed + WhatsApp details: **2/2**

  - **Seller:** haan ji
  - **VANI** _(None, end False)_: Main IndiaMART se Payal bol rahi hoon. Aap IndiaMART ki paid services dekh rahe the, aur aapki Cotton Fabric category mein buyers available hain. Kya aap iske baare mein jaanna chahenge?
  - **Seller:** kaam achha hai, aur buyers chahiye
  - **VANI** _(None, end False)_: Bahut achha, samajh gayi. Hamare executive aapse milkar aapki profile aur catalogue theek karenge, aur lead settings check karenge, taaki aapko sahi buyers ki enquiries milein. Kal subah 11 baje ya parso shaam 4 baje, kya theek rahega?
  - **Seller:** kal raat 8 baje
  - **VANI** _(None, end False)_: Maafi chahungi, meeting hum subah nau se shaam chhe baje ke beech hi rakh sakte hain. Kal dopahar barah baje theek rahega?
  - **Seller:** nahi, raat 8 baje hi ho payega
  - **VANI** _(INFO_SENT, end True)_: Maafi chahungi, hamari meeting timings subah nau se shaam chhe baje tak fixed hain. Main details aapko WhatsApp par bhej rahi hoon, jab suvidha ho is samay mein koi slot bata dijiyega. Dhanyavaad, aapka din shubh ho.

## Understanding question not re-asked (seller 3419775)

- not re-asked: **2/2**

  - **Seller:** Nahi achha nahi chal raha, bilkul achha nahi chal raha.
  - **VANI** _(IN_PROGRESS, end False)_: Main samajh sakti hoon, enquiries kam aana chinta ki baat hai. Aapki Automatic Idli Making Machine category mein Chennai mein buyers available hain, aur hamare executive aapki profile aur catalogue theek kar sakte hain. Kya aap iske baare mein jaanna chahenge?

## Bad-business report is not a yes or a refusal (seller 113839910)

- no outcome: **2/2**

  - **Seller:** kaam theek nahi chal raha
  - **VANI** _(None, end False)_: Samajh sakti hoon, enquiries kam aana chinta ki baat hai. Hamare executive aapki profile aur catalogue theek karenge, taaki aapko sahi buyers ki enquiries milein. Kya aap iske baare mein jaanna chahenge?
  - **Seller:** Bilkul kharab chal raha hai.
  - **VANI** _(IN_PROGRESS, end False)_: Yeh sunkar afsos hua. Executive milkar aapka catalog aur lead settings theek karenge, taaki aapko relevant enquiries milein. Kal subah 11 baje ya parso shaam 4 baje, kya theek rahega, milkar ya online?

## Genuine flip is clarified (seller 113839910)

- asks about orders / conversion: **0/2**
- no outcome: **2/2**

  - **Seller:** kaam theek nahi chal raha
  - **VANI** _(None, end False)_: Samajh sakti hoon, kaam theek nahi chalna chinta ki baat hai. Main IndiaMART se Payal bol rahi hoon, aap IndiaMART ki paid services dekh rahe the, aur aapki Cotton Fabric category mein buyers available hain. Kya aap iske baare mein jaanna chahenge?
  - **Seller:** haan enquiry to aa rahi hai
  - **VANI** _(IN_PROGRESS, end False)_: Achha, enquiries toh aa rahi hain. Hamare executive aapki profile aur catalogue theek karenge aur lead settings check karenge, taaki aapko sahi buyers ki enquiries milein. Kal subah 11 baje ya parso shaam 4 baje, kya theek rahega?

## Sarcastic flip after a pitch (seller 3419775)

- never 'good to hear': **2/2**
- no pitch: **1/2**

  - **Seller:** Nahi achha nahi chal raha, bilkul achha nahi chal raha.
  - **VANI** _(None, end False)_: Main samajh sakti hoon, business theek na chalna chinta ki baat hai. Aapki Automatic Idli Making Machine category mein Chennai mein buyers available hain. Kya aap iske baare mein jaanna chahenge?
  - **Seller:** Bilkul kharab chal raha hai.
  - **VANI** _(None, end False)_: Samajh sakti hoon, enquiries kam aana pareshani deta hai. Hamare executive aapki profile aur catalogue theek karenge, taaki sahi buyers ki enquiries aayein. Kya main unse aapki meeting fix kar doon?
  - **Seller:** Are sab badhiya chal raha hai, itna badhiya business hai, mujhe inquiries bhi aa rahi hai, sab ho raha hai.
  - **VANI** _(IN_PROGRESS, end False)_: Achha, toh enquiries aa rahi hain par order nahi ban rahe, kya baat hai?

## Short Hinglish question keeps Hindi (seller 3419775)

- reply stays in Hindi (either script): **2/2**

  - **Seller:** Chaudah bada hai ji.
  - **VANI** _(None, end False)_: Main samajh gayi. Aapki Automatic Idli Making Machine category mein Chennai mein buyers ki enquiries aayi hain. Kya aap iske baare mein jaanna chahenge?
  - **Seller:** Meeting nahi chahiye.
  - **VANI** _(None, end False)_: Koi baat nahi. Kya aapke paas pehle se kaafi kaam hai, ya online platform ka koi bura anubhav raha?
  - **Seller:** Kaun si details?
  - **VANI** _(INFO_SENT, end False)_: Main WhatsApp par aapko yeh bhejungi: aapki category ke competitors ne ab tak kitni buy leads li hain, aapki category ki haal ki buy leads, aur kaun si buy leads aapse chhoot gayi hain. Kya isi number par bhej doon?

## Venting about calls: no further call offered, not cut while talking (seller 3419775)

- no further call offered: **0/2**
- call kept going: **1/2**

  - **Seller:** Yaar kyon baar baar phone karte ho?
  - **VANI** _(None, end False)_: Mujhe afsos hai ki baar baar call karni padi. Main IndiaMART se Payal bol rahi hoon, Chennai mein aapki Automatic Idli Making Machine category mein buyers available hain. Kya main aapko baad mein call karoon, ya WhatsApp par details bhej doon?
  - **Seller:** Abhi main bol raha hoon baar baar call karte ho, kal phir se call karogi aap log.
  - **VANI** _(IN_PROGRESS, end True)_: Maafi chahti hoon. Main abhi call rok deti hoon. Jab suvidha ho, tab bata dijiyega.

## Buy-lead question -> seller dashboard, no meeting (seller 113839910)

- seller dashboard + BuyLeads: **2/2**
- no meeting ask: **2/2**

  - **Seller:** kaam theek hai
  - **VANI** _(None, end False)_: Aap IndiaMART ki paid services dekh rahe the, aur aapki Cotton Fabric category mein buyers available hain. Kya aap iske baare mein jaanna chahenge?
  - **Seller:** aur buy leads kahan milenge?
  - **VANI** _(IN_PROGRESS, end False)_: Aap apne IndiaMART seller dashboard mein login karke BuyLeads section mein sabhi buy leads dekh sakte hain — website par, ya IndiaMART app mein bhi. Kya aap iske baare mein aur jaanna chahenge?

## Virtual assistant only when asked (seller 113839910)

- not on 'kaun bol raha hai': **2/2**
- yes on 'robot ho?': **2/2**

  - **Seller:** kaun bol raha hai?
  - **VANI** _(None, end False)_: Main IndiaMART se Payal bol rahi hoon. Aap IndiaMART ki paid services dekh rahe the, aur aapki Cotton Fabric category mein buyers available hain. Kya aap iske baare mein jaanna chahenge?
  - **Seller:** aap robot ho kya?
  - **VANI** _(IN_PROGRESS, end False)_: Main IndiaMART ki virtual assistant hoon, aapke IndiaMART account ke baare mein call kiya hai. Hamare executive aapse milkar aapki profile aur catalogue theek karenge aur lead settings check karenge, taaki aapko sahi buyers ki enquiries milein. Kal subah 11 baje ya parso shaam 4 baje, kya theek rahega?

## Misheard 'what is app' = WhatsApp (seller 113839910)

- understood as WhatsApp: **2/2**

  - **Seller:** what is app pe details bhej do
  - **VANI** _(INFO_SENT, end False)_: Main WhatsApp par aapko yeh bhejungi: aapke competitors ne ab tak kitni buy leads li hain, aapki category ki haal ki buy leads, aur kaun si leads aapse chhoot gayi hain. Kya isi number par bhej doon?
