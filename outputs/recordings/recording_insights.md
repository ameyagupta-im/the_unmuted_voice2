# What the 83 call recordings teach

83 calls analysed (bot: 83), 3,367 diarized turns. Transcribed with Sarvam Saaras (batch, diarized, translit).

## Speaking rate (median words/sec)

- bot/bot: 3.44
- bot/seller: 3.31

## Scenarios that occurred, and whether the agent handled them per the playbook

| Scenario | occurrences | bot ok / missed | human ok / missed | example seller words |
|---|---|---|---|---|
| connectivity | 5 | 4 / 1 | 0 / 0 | Accha theek hai theek hai Accha kal call kariyega na |
| frustration | 1 | 0 / 1 | 0 / 0 | Bahut baar toh phone aa chuka hai aur baar baar hi toh bola tha. |
| complaint | 3 | 3 / 0 | 0 / 0 | Maine na kal complaint raise kiya jata hai. Jo mera mera jo profile ha |
| identity_question | 19 | 16 / 3 | 0 / 0 | Ji kahan se bol rahe hain |
| not_right_person | 2 | 0 / 2 | 0 / 0 | Mari toh abhi hai nahi sir, Balaji Intex ka aane se baat karata hoon m |
| already_with_executive | 4 | 3 / 1 | 0 / 0 | Ji ji ji haan good afternoon |
| not_interested | 10 | 4 / 6 | 0 / 0 | nahi nahi beauty product nahi hai ma'am milunga |
| busy | 14 | 9 / 5 | 0 / 0 | Raj ji main abhi auto pe station hoon |
| wants_whatsapp | 1 | 1 / 0 | 0 / 0 | Ee number WhatsApp pe rahe hain. |
| gives_time | 73 | 70 / 3 | 0 / 0 | Twenty one ke main aaunga |
| need_few_enquiries | 3 | 3 / 0 | 0 / 0 | Hmm. Try the |
| price_query | 18 | 12 / 6 | 0 / 0 | Charge charge charge chahiye |
| confusion | 2 | 2 / 0 | 0 / 0 | Achha chhote de raha hai |
| interest | 46 | 45 / 1 | 0 / 0 | Chalo theek hai aisa karte hain madam apan kal ka baat karte hain aapk |

## Most common agent mistakes

- quoted specific package prices (4000/month and 32000/year) instead of deferring to an executive. (1)
- failed to explain that the meeting is free of charge. (1)
- mispronounced 'indiamart' as 'india martins' (1)
- did not confirm the callback slot in a structured way (e.g., 'i will call you back in a week') (1)
- did not follow the 'busy' playbook by providing a one-line value proposition before asking for a callback time. (1)
- ignored seller's refusal of beauty products and mismatched profile. (1)
- failed to handle 'busy' signal by offering a callback or whatsapp alternative. (1)
- repeated the mismatch explanation multiple times without advancing the pitch. (1)
- did not use a concise value proposition before asking for time. (1)
- misinterpreted the seller's request to call back later ('baad mein baat kar loongi') as a request for a follow-up reminder instead of a direct callback. (1)
- failed to handle the seller's audio/connectivity issue ('ro nahi ro nahi aa rahi ho') with the standard 'kya aapko meri awaaz aa rahi hai?' script. (1)
- pitched pricing ('chaar hazaar ka charges') despite the playbook instructing to never quote a price. (1)
- failed to transition to the goal step after the seller expressed market slowdown interest. (1)
- quoted a specific conversion percentage (30 to 40%) and lead volume (70 leads) when the playbook strictly prohibits quoting prices or guaranteed metrics. (1)
- failed to confirm the callback slot explicitly after the seller gave a time. (1)

## Outcomes

- bot / CALLBACK_SCHEDULED: 35
- bot / MEETING_FIXED: 34
- bot / RESPECTFUL_EXIT: 7
- bot / UNCLEAR: 3
- bot / INFO_SENT: 2
- bot / EXEC_HANDOFF: 1
- bot / CALL_BACK_LATER: 1

## Phrasings worth reusing (by situation)

**busy**
- (bot) Accha accha abhi aap out of station hain... raat ki kab tak available rahoge sir aap
- (bot) Okay okay toh phir sir kal phir kitne baje tak connect kar lo iska
- (bot) No issue sir aap ek baar meeting mein chale jao aap mere ko
- (bot) Okay aap ek ghante ke baad free ho jaoge sir. Okay toh abhi sir time ho raha hai aapka ek bajne hi wala hai main do baje ke around aapko connect kar leti hoon do baje toh baat ho payegi na.
**gives_time**
- (bot) Twenty one agar sir aapko comfortable ho... ek online meeting hum log rakh sakte hain Zoom pe
- (bot) teen se chaar ke chaar baje ke tak sir free ho jaoge aap
- (bot) Parso ek baar subah mujhe itne baje phone kar lena hum log schedule kar lenge.
- (bot) Haan ji main haan kal aap morning mein free rahenge na main das saade das ke around aapko ek baar connect kar loongi
**identity_question**
- (bot) Ji sir main IndiaMart ka Vanshika baat kar rahi thi aapse IndiaMart se sir Ranchi branch se
- (bot) Haan ji, very good afternoon Arvind sir. Main Harshata baat kar rahi thi India Mart se.
- (bot) Nahi main Rajesh nahi ho raha. Jitna maine aapko pehle bhi bataya tha mera naam Abhinit hai.
- (bot) Haan ji sir main Ranchi branch se Harshita Business Growth Manager India Mart se baat kar rahi thi
**closing**
- (bot) Accha accha second half ke baad hi ek baar na theek hai sir main ek baar check aapko connect kar loongi theek hai thank you sir
- (bot) Ji ji theek hai kal second half okay sir kal second half mein hum log connect kar lenge mil lenge
- (bot) Okay sure sir theek hai but time mein zaroor nikaliyeega
- (bot) Okay sir thank you
**opening**
- (bot) Haan very good afternoon ma'am main India Mart team se baat kar rahi thi ye Homey Free Strides mein baat ho rahi hai na
- (bot) Ji sir, main India Mart team se baat kar rahi thi. Actually aapka ek firm tha sir, uske regarding kaafi queries wagairah thi customers ki.
- (bot) Very good evening sir main Harshita baat kar rahi thi Amar Sanjeevani Natural Bee Product Private Limited ke regarding connect kiya tha maine.
- (bot) Hello haan haan ji very good afternoon sir main Harshita baat kar rahi thi enrichment team India Mart Ranchi branch se aapka ek form registered hai India Mart ke upar Varanti Home Solution ke naam se uske regarding connect kiya hai maine
**already_with_executive**
- (bot) Haan aapka call aaya tha hum ek meeting mein the
- (bot) Haraadan sir hi process karte hain na saaro cheez. Okay okay theek hai sir main unse connect kar le rahi hoon abhi.
**understanding**
- (bot) Haan ji toh ismein sir jo aapka product wagairah hai yeh Ancol hai Ancol B wagairah hai Maan Tulsi Bees wagairah basically honey pe deal karte hain sir aap
- (bot) Okay okay koi baat nahi sir main teen baje available hainge ya phir saade teen mein sir
- (bot) Sei inquirygulo generate hochhilo segulo apnake ektu dekhiye ditam ebong profileta update kore ditam
- (bot) Aapki ye jo business profile registered hai, yeh aayi thi actually ismein aapka product alag hai aur product name alag bada hua hai
**not_interested**
- (bot) Haan sir atleast ek baar milne ka toh mauka dete kam se kam hum saamne se aakar ke apna India Mart what is India Mart actually hum kya provide kar rahe hain aapko woh toh hum aapko present kar paate hain na sir call pe
- (bot) I understand. May I know the reason, or would you prefer I just send some basic details on WhatsApp?
**price_query**
- (bot) Kyonki iske liye sir dekho meeting ke liye aur saari cheezein samajhne ke liye koi charges nahi lagte hain theek hai
- (bot) Nahi ab ye dekho aapki jo meeting hogi bilkul ekdam free of cost hai iska koi kharcha nahi hai hai na.
- (bot) Particular jisko jo requirement rahegi woh mujhe share karenge uski requirement toh uske hisab se rate decide hoga aur phir kya hai ki raw material ke prices mein bhi fluctuation rehta hai.
- (bot) is ekdam free of cost hai iska koi charges vagairah nahi hai
**complaint**
- (bot) Main aapki ye jo dikkat aa rahi hai aapke mobile ki, isko solve karane ke liye vigilance executive ke saath meeting kara deti hoon, vo aake aapke profile mein update kar denge jo bhi hoga, jo bhi dikkat badi hoogi guys, hai na?
**connectivity**
- (bot) Hello sir awaaz aa rahi hai aapko
**interest**
- (bot) Wahin se aapke liye koi banda aayega, aap mere ko ek time bata do main kis time par aapke liye bhejungi.
- (bot) Okay kya product purchase karna hai?
**need_few_enquiries**
- (bot) Mere ko ek baat bata dijiye, aap ye jaise near by ke aapke jo buyers hain, forty eight buyers hain, forty eight inquiries aayi hui hai matlab near by.
**not_right_person**
- (bot) I am sorry, it seems I reached the wrong contact. Could you please share the right person's name and number?