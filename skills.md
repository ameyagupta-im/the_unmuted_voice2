# skills.md: build journey and tools

## Phase 3: live testing, IndiaMART's master prompt, Sarvam hosting and speed

### What was added
1. **A conversation layer that understands the seller's line** (`utterance.py`):
   - Every seller line gets a dialogue act: question, request, statement, yes, no or bye.
   - A question is answered and never taken as a yes, a no or a request. "What details on WhatsApp?" no longer closes the call as INFO_SENT.
   - Live audio uses Saaras v4 in `translit` mode with brand keyterms (IndiaMART, WhatsApp, BuyLead); `compare_stt_modes.py` measured the modes on 8 kHz audio.
2. **Hands-free calling in the browser**:
   - Voice activity detection on the echo-cancelled mic, and barge-in.
   - The engine keeps only the part of VANI's reply the seller actually heard (`heard_fraction`), so an unheard question doesn't count as asked.
3. **Contradictions, sarcasm and language stability** (`facts.py`):
   - A fact ledger records what the seller says about their business.
   - A real flip ("kaam theek nahi" → "enquiry to aa rahi hai") gets one gentle clarifying question ("kya enquiries aa rahi hain par order nahi ban rahe?").
   - An exaggerated "sab badhiya hai" right after a pitch is read as sarcasm, i.e. frustration.
   - The language switches only on a request, a full sentence in the other language, or two short lines in a row. Before this, "Kaun si details?" flipped a Hindi call to English.
4. **Integrations, dry run by default** (`integrations/`):
   - **Before the call:** suppression list, national DND and calling hours.
   - **After the call:** CRM write-back and WhatsApp messages.
   - Each turns live only with its own `.env` flag.
   - `build_eval_set.py` builds a held-out evaluation set from IndiaMART's evaluators.
5. **Hosting on Sarvam Voice Agents** (`sarvam_platform.py`, `sarvam_deploy.py`, `sarvam_api.py`, `build_campaign.py`):
   - One agent configuration per voice, holding the instruction, the input variables (the seller context), the output variables (outcome, slot, do-not-call, disposition) and per-language voices.
   - Campaign files for calling a list of sellers.
   - Agents are created in the dashboard or through Sarvam's MCP server; there is no REST endpoint for that.
   - `tests/prompt_only_suite.py` measures what the hosted instruction does on its own, with none of the engine's code checks.
6. **IndiaMART's master prompt became the single source** (`docs/master_prompt.md`, `master_prompt.py`):
   - The engine, the Sarvam agent and the plain export are all built from the same text; only section 9 (the output format) differs per target.
   - It replaced several earlier behaviours: the "anything else?" wrap-up, persuasion after a soft no, the contact-preference exit, calling the meeting "free", and the understanding-question opening.
   - IndiaMART's additions:
     - Buy-lead questions get the IndiaMART seller dashboard line, with no meeting ask; a second one gets a WhatsApp offer.
     - The greeting starts with VANI's own name and checks the company name.
     - "Virtual assistant" is said only when the seller asks; the rule reads the seller's own words, never the LLM's label.
     - IndiaMART is spelled for the TTS so Bulbul doesn't say "India Art" (`speakable()`).
7. **IndiaMART's live-testing points (10 Oct 2026)**, applied in the master text and enforced in code:
   - **Meetings:**
     - **Window:** 9 AM–6 PM on a calendar day from tomorrow (`slots.py`).
     - **Slot choice:** VANI offers two concrete slots and the seller chooses. "parso wala", "dusra wala" and "4 baje wala" are understood, and a plain yes means the first option. VANI says the slot back with "milkar ya online?" and fixes it only after that answer. The LLM may never decide a slot itself.
     - **Insisting on other hours:** the first time, VANI states the window and offers the nearest slot. If the seller still insists, VANI says the timings are fixed and the details will come on WhatsApp.
     - **Confirmation:** a confirmed meeting gets a WhatsApp confirmation with the real calendar date, time and in person / online.
   - **WhatsApp:** details are sent only when the seller asks for them or agrees.
   - **No mid-call cut:** the call is never ended while the seller is asking something real. A frustrated seller who says "abhi main bol raha hoon" gets "माफ़ी चाहती हूँ। आप बताइए।" instead of a hang-up.
   - **Repeated-call complaints:** never answered with another call offer.
   - **Silence:** "माफ़ कीजिए, आपकी आवाज़ ठीक से नहीं आ रही। क्या आप कुछ कह रहे थे?"; a second silence ends the call as CALL_BACK_LATER.
   - **Background voices:**
     - The browser gates speech against a running background-noise floor, and needs about 0.6 s of sustained near-mic speech before it stops VANI.
     - Nothing transcribed, or only "haan / hmm" over VANI, is not a turn; she resumes where she stopped.
   - **"ji":** VANI never says it. It was removed from the fixed lines, from VANI's lines in the master text, and by a final filter on everything she speaks (`drop_ji()`). The seller's "haan ji" is still understood.
   - **Executive sellers:** a seller who already has an executive gets the master's account-manager offer, and a described need becomes a meeting.
8. **Speed, with no change to what VANI says** (`tests/latency_bench.py`, real Sarvam calls on 65 scenario turns):

   | | Before | After |
   |---|---|---|
   | Median turn | 2.34 s | 0.82 s |
   | Slowest 10% of turns | 5.5 s | 3.4 s |
   | Worst turn | 8.5 s | 4.7 s |
   | LLM calls | 66 | 55 |

   - The LLM sometimes padded its JSON with blank lines up to the 800-token limit (about 1.6 s, then a retry). A stop sequence now ends the padding, and the three small trailing fields are filled with their defaults.
   - Mechanical problems (Hindi in Roman letters, verb gender, a banned phrase, an unasked "virtual assistant") are fixed in code instead of with another LLM call.
   - Multi-sentence replies are voiced in parallel with a 0.3 s pause between sentences.
   - Every voice clip is cached, and the first reply is voiced while the greeting plays.
   - Romanised-Hindi fragments are transliterated in one call instead of one per fragment.
9. **Validation now**:
   - 209 offline tests.
   - Live scenario suite: 35 of 35 scenarios (90/90 checks), including the master prompt's own meeting example, seller line for line.
   - The prompt-only measurement of the hosted agent: 50 of 54 checks.
   - The latency benchmark.

### Bugs found in this phase (each has a regression test)
| Bug | Found by | Fix |
|---|---|---|
| "What details on WhatsApp?" read as a request; the call hung up as INFO_SENT | live demo (Chennai) | Dialogue act first: a question is answered, never a request |
| "Kaun si details?" (one English word) flipped the call to English, and back on the next line | live session | Language hysteresis: short lines keep the current language |
| The LLM labelled "kaun bol raha hai?" and "Enna maadhiri?" as a bot question; VANI said "virtual assistant" unasked | live session | Disclosure depends only on the seller's own words |
| Bulbul read IndiaMART as "India Art" | live session | Speech-only spelling (इंडियामार्ट / India Mart) |
| With more schema fields, the LLM padded JSON with whitespace up to max_tokens; every retry fell back | scenario suite | New fields after the reply, kept small; later a stop sequence plus recovery of the cut JSON |
| Two stale server processes on port 5050 served old code during a demo | live session | Stopped them; one server, restarted after each change |
| The price answer came after the question ("क्या meeting रख दूँ? Charges…") | offline replay | The answer is inserted before the question |
| The fatigued seller's apology came after the reason | offline replay | Apology first (master 3.1, type 1) |
| The audio-check mode was held and outranked the frustration that followed it | session 125638 replay | CLEAR_AUDIO is not held once the seller speaks |
| "ठीक है जी। ठीक है जी, हम…": a short acknowledgement stacked on a closing that starts with it | scenario suite | Skip the acknowledgement when the closing already says it |
| "कैसा चल रहा है?" re-asked after "bilkul kharab chal raha hai" | offline replay | Business-question pattern dropped once the seller has answered |
| "यह जानकर अच्छा लगा" said to bad news | offline replay | "Good to hear" removed when the business is reported bad |
| A seller fed up with repeated calls was offered another call | session 125638 | Call-frequency complaints offer only WhatsApp details or the end |
| The second frustration hung up on a seller saying "abhi main bol raha hoon" | session 125638 | VANI apologises and gives the floor; a third frustration ends the call |
| "parso wala theek hai" was not recognised as choosing the second slot | offline test | `slots.chosen()`, and the choice goes to the meeting gate whatever the LLM proposed |
| "haan enquiry to aa rahi hai" (a contradiction opening with haan) taken as yes to 11 AM | scenario suite | A bare yes only; a contradiction or a business fact is never a yes |
| The LLM fixed a slot itself ("तो कल सुबह 11 बजे रख लेती हूँ") before the seller chose one | scenario suite | Replaced with the two-slot question |
| A plain "haan" to "11 बजे online, या WhatsApp?" closed as INFO_SENT | scenario suite | A yes to an either/or is never a WhatsApp yes; it takes the first option |
| A yes to a callback time ("कल शाम 6 बजे call करूँ?") was routed to the meeting window | offline test | The meeting gate needs a meeting question |
| The account-manager offer was missed because only the last sentence was checked | scenario suite | The whole of VANI's last turn is checked |
| "milne ka time nahi hai" became a callback instead of an online meeting | master example run | No time to meet keeps the meeting, online |
| "मिलकर या online?" after the slot question hid the offered slots | scenario suite | Slots are read from any question in VANI's last turn |
| Romanised Hindi ("iske baare mein") passed the script check | scenario suite | Wider Hindi-word list |
| Transliteration turned "charges" into चार्जेस and "baje" into बजाए | scenario suite | Trade words stay Latin; common words from a fixed table |
| The hosted agent's outcome extraction labelled a fixed meeting INFO_SENT ("confirmation on WhatsApp") | prompt-only suite | Extraction prompt: a confirmed meeting is MEETING_FIXED |
| "kaun bol raha hai?" was answered without VANI's name; any "IndiaMART" passed the check | scenario suite | The bot's name is required |
| The name line stacked on the LLM's own "मैं IndiaMART की virtual assistant हूँ" | scenario suite | Replaces a nameless self-introduction instead of adding one |
| A pitch sentence followed the clarifying question | scenario suite | Trimmed so the reply ends on the question |
| "नहीं जी।" kept its जी: the danda ( । ) sits inside the Devanagari range | offline test | Dandas are not counted as letters |

### Deviations and decisions (deliberate, documented)
- The meeting window in the master prompt (11 AM–5 PM) was replaced by IndiaMART's 9 AM–6 PM, inside the master text itself, so the model never sees two windows.
- The master prompt says a second frustration ends the call. That still holds, except when the seller is asking something real or says they are still talking; a third frustration then ends the call. This follows IndiaMART's "call should not be cut in between".
- Sending WhatsApp details unasked is allowed in one case only: the seller insists on hours outside the meeting window (IndiaMART's instruction).
- "ji" was removed from VANI's lines in the master text; the seller's quoted words keep it.
- The master prompt's examples were brought in line with IndiaMART's additions: the buy-lead example ends on the dashboard line, and the first reply does not introduce VANI again.
- The hosted-agent measurement is a measurement, not a gate. The engine's code checks exist because a prompt alone is not always followed.

---

## Phase 2: learning from 83 recordings and implementing the scenarios playbook

### What was added
1. **Transcribed all 83 unique bot recordings** (85 files, 2 duplicates found by hash). Saaras batch STT with **speaker diarization**, translit mode, 3,367 turns. The bot speaker is resolved by IndiaMART/agent cues in its words.
2. **An LLM reviewed every call against the playbook**: which of the 20 scenarios happened, the seller's exact words, whether the bot handled each one per the playbook, the outcome, and reusable lines. The main lessons:
   - The old bot **quoted prices in 6 of 18 price questions** (₹4,000/month, ₹32,000/year, even "30–40% conversion").
   - It **kept pitching after "not interested" in 6 of 10 cases**.
   - It missed "busy" in 5 of 14 cases and "not the right person" in both.
3. **Only verified lessons reach the agent** (`learned_examples.py`):
   - Quotes must appear verbatim in the transcripts.
   - Agent lines must use clean fillers, contain no prices, no human names, and come from situations the bot handled well.
   - 51 paraphrased or unclean items were dropped.
4. **The playbook is encoded as data** (`playbook.py`): 7 seller types, 9 goals with fallbacks, 20 signals in priority order, 8 persona modes, mid-call goal switches with exceptions, 11 endings with closing lines, and ask limits.
5. **Per-seller context from 5 sources** (`seller_context.py`): latest lead bucket, best calling hour, past summaries, own English share and speaking rate, and executive calls. The lead buckets were undocumented; their meaning was learned by reading summaries per bucket.
6. **Hang-up risk model**:
   - First label ("call ended within 2 turns") scored AUC 0.56, because it also counted polite endings.
   - Relabelled with the evaluator's "seller ended the call": **AUC 0.646 vs 0.564** for keywords on held-out calls, with **2.9× lift** at a 6% flag rate.
   - Reported as below the playbook's 0.71.
7. **The engine was rewritten as the playbook's two-layer state machine**, with deterministic guards for every playbook rule and endings validated against what the seller actually said.
8. **Validation**:
   - a live scenario suite (every playbook scenario, real LLM)
   - a replay of every real moment the old bot got wrong
   - 105 offline tests
   - the three-seller voice demo
   - the held-out signal evaluation

### Bugs found in this phase (each has a regression test)
| Bug | Found by | Fix |
|---|---|---|
| Time regex matched the "am" in "ma'am", so "hum soch ke batate hain ma'am" was closed as **MEETING_FIXED** | recording replay | Seller times come from the precise gives_time detector |
| "Busy" alone was accepted as CALLBACK_SCHEDULED | recording replay | A callback needs a time from the seller, or agreement to a proposed time |
| First frustration was closed as RESPECTFUL_EXIT | scenario suite | Exit only at the refusal limit; outcome checked inside the guard loop, before speaking |
| Complaint closed without asking when support may call | scenario suite + demo | COMPLAINT_LOGGED requires a support-time ask or a time from the seller |
| Who-is-calling ignored, VANI pitched instead | scenario suite | Disclosure guard in TRANSPARENT mode |
| Refusal limit exited without asking contact preference | scenario suite | Exit only after the preference is asked |
| Refusal counted twice (tier 1 + LLM) inside the guard loop | scenario suite | Count only LLM signals that tier 1 did not already count |
| "Refused with a reason" switched the goal after the reply, so the WhatsApp offer was never said | scenario suite | Detected before the LLM call |
| "nahi chahiye" alone flagged as a refusal with a reason | scenario suite | Reason must survive removing no-words and fillers |
| Repair asks were uncounted, and two guards ping-ponged (drop/re-add the same question) | offline test | Repairs set the question type; an already-asked question is not re-added |
| A stale goal was used to repair the reply before this turn's LLM signals were applied | recording replay | Pending LLM signals counted in outcome checks |
| "I am **not interested**" also fired *interest* (ENGAGED on a refusal) | voice demo | Negative lookbehind, and a refusal suppresses interest in the same turn |
| WhatsApp re-offered after "don't send anything" | voice demo | Declined offers are tracked before the reply is written |
| A medium-confidence LLM frustration ended a cooperative call (ESCALATED_EXIT) | voice demo | Frustration needs high confidence or repetition |
| A complaint in the same line as the second frustration was lost | voice demo | Ends COMPLAINT_LOGGED, with support follow-up |
| Telugu "malli call cheyoddu" (don't call again), "vaddu", "payment… entha" were missed | voice demo | Telugu patterns added |
| Telugu closing mistranslated ("sorry for the irritation *I* felt") | voice demo | Hand-written Telugu closings (ENDINGS_TE) |
| "ippudu call cheyoddu" (don't call *now*) read as do-not-call | voice demo | Do-not-call needs "again" (malli/inka/eppudu); "now" maps to busy |
| "Telugu lo matladandi… malli call cheyakandi" got a **Hindi** goodbye | voice demo | Language switch applied before any ending in the same turn |
| WhatsApp declined, then "no + reason" in the same turn pulled the goal back to WhatsApp; the call stalled | voice demo | The reason-switch is skipped once WhatsApp is declined or the refusal limit is reached |
| "Just send everything on WhatsApp. No more calls." read as *declining* WhatsApp | voice demo | A WhatsApp request is never a decline; with "no more calls" it ends INFO_SENT and records `do_not_call` |
| "kaam **theek** chal raha hai" taken as yes to a 7 pm meeting → false MEETING_FIXED | scenario suite | Agreement must open the reply ("haan ji, theek hai") |
| "Is there any cost?" skipped for a busy line; seller had to ask again | voice demo | Price-unanswered guard: the cost answer is given the same turn |
| "Call back tomorrow at 10 AM" got another question; the call never ended | voice demo | A time given in the goal step closes the slot for the active goal |
| Seller deflected the opening question; VANI's reply had no question | recording replay | Repair moves to the goal ask instead of a dead end |
| 31-word reply to a seller who said they had no time | recording replay | Length guard in BRIEF/COMPRESSED modes |
| Second frustration on a complaint-recovery call dropped the complaint (ESCALATED_EXIT) | voice demo | Ends COMPLAINT_LOGGED when the call is about a known complaint |
| Hindi WhatsApp offer appended to a Telugu call | voice demo | Repair questions come from the call's language |
| "vaddu, call cheyakandi" (don't call) missed; "utna time hamara paas nahi" missed | voice demo / replay | Telugu bare "call cheyakandi" = do-not-call unless "ippudu" (now); busy pattern added |
| After the contact-preference answer the LLM asked again; the call never closed | scenario suite | The answer closes the call once the exit is due |
| Apology and introduction repeated every turn | voice demo | Sentence-level repetition guard |
| A Hindi example line from the prompt leaked into an English call | voice demo | Language-neutral mode text, plus a wider Hindi-word check |
| "Tell me the details now" read as *wants WhatsApp*, closed INFO_SENT | voice demo | WhatsApp intent needs lexical evidence |
| Two demo sellers became the same type and voice | demo review | Picked a busy-owner Telangana seller for contrast |

### Deviations from the playbook (deliberate, documented)
- Telangana/Andhra are *offered* Telugu, not forced to English: evidence E8 shows Telangana sellers mostly replied in Hindi.
- Callback is checked before "meeting because of no negative history"; otherwise callback could never be chosen.
- "Busy owner: faster" is applied as at most +0.05 pace on a base below 1.0, because our E3 finding (slower deliveries fixed more meetings) points the other way. Brevity comes from shorter replies instead.
- Pace mirrors our measured rates (bot 2.76 / seller 2.36 words/s from 12.8k calls), not the playbook's 3.1 / 2.1.
- WhatsApp is used as a goal and ending, as the playbook specifies. The earlier buyer-side Sarvam doc said VANI has no WhatsApp access; the seller-side playbook overrides it here.

---

## Phase 1 (earlier build)

## Tools used
- **Sarvam AI** (Python SDK `sarvamai`)
  - Saaras STT: batch `saaras:v3` jobs to transcribe real call recordings (with diarization in phase 2); real-time `saaras:v4` in `translit` mode with keyterms for live turns.
  - `sarvam-105b-conversations` (JSON-schema output) for in-context signal classification plus VANI's reply, for the simulated seller, and for the evaluation.
  - Bulbul `bulbul:v4-flash`: 24 persona voices (gender × style × Hindi/English/Telugu), validated against the live API. In phase 3, sentences are voiced in parallel and every clip is cached.
  - `text.transliterate` / `text.translate` and language identification, used for script repair and normalisation.
  - The chat API's `stop` parameter (phase 3), which ends the LLM's blank-line padding early.
  - **Sarvam Voice Agents** (phase 3): agent bundles with input and output variables, campaign files and dry-run REST calls.
- **Python**: pandas and numpy (evidence and personas), Flask (live demo), pytest (regression tests), the stdlib `wave` module (audio concatenation), `concurrent.futures` (parallel TTS), SQLite (suppression list).
- **Browser**: Web Audio API for the hands-free voice detection, barge-in and background-noise gate; `node --check` to syntax-check the page's script.
- **pptxgenjs** (one-slide presentation) and PowerPoint (render check).
- **Claude Code** wrote, ran, tested and debugged every module against the real dataset and real Sarvam responses.

## Build journey
1. **Read the brief, the data dictionary and Sarvam's global instructions** (`base_context/Sarvam Prompt - Buyer Side VANI.docx`). The rules taken from that document and enforced in code:
   - never claim to be human
   - Hindi, English or Telugu only
   - respectful fillers
   - one question per turn, no echoing
   - ask limits (Collection Control)
   - no WhatsApp/SMS access
   - TTS-safe text and natural numbers
   - "five times nine six" for the help desk number
   - closings are statements, not questions
2. **Listened to real recordings** with Saaras and cross-checked them against the dataset transcripts. Saaras returns Hindi in Devanagari while the transcripts are Romanized, so a keyword detector would have matched nothing. Live audio now uses `translit` mode.
3. **Measured before designing** (`evidence_analysis.py`). Several hypotheses were overturned:
   - "Be faster and briefer with terse sellers" was contradicted. Slower delivery fixed more meetings for every seller type, so every persona runs below default pace, and "rush" shortens content rather than speeding up speech.
   - Three measurement confounds were caught and controlled:
     - **Opening length:** a truncated opening means the seller interrupted (reverse causality).
     - **Repetition:** short calls cannot repeat (controlled for call length).
     - **Objection outcomes:** the objections evaluator only covers non-meeting calls (selection bias).
   - Personalisation's lift (14.2% vs 11.5% meetings, n=452) is graded **inconclusive**, not claimed as proof.
4. **Persona generator** with reason, evidence and confidence on every field. Goals depend on the seller's history (callback, grievance, re-engage after a no, follow up on a meeting…), not always "fix a meeting".
5. **Live engine**: tier-1 regex, then a single LLM call that classifies and replies, then deterministic guards, then TTS. Tested turn by turn on real seller voices, which surfaced most of the bugs below.
6. **Evaluated detection against IndiaMART's own labels** (4,718 utterances, dev/test split). Regex alone has high precision but low recall. Mining patterns from dev data barely generalised (frustration recall 0.10 → 0.13), which showed that tier 2 has to carry frustration. Revising the shared signal definitions on dev errors raised held-out frustration recall from 0.38 to 0.69.
7. **Measured distinctness.** "Declined before" and "Warm / previously agreed" personas were nearly identical (distance 0.11). Adding history-specific goals took it to 0.38.
8. **Recorded the voice demo, built the live web demo, wrote 48 regression tests and the one-slide presentation.**

## Bugs found and fixed (each now has a regression test)
| # | Bug | How it was found | Fix |
|---|---|---|---|
| 1 | Persona injected "Main ek real insaan hoon" | Reading Sarvam's global rules | Disclosure as virtual assistant, plus a human-claim guard |
| 2 | Male voice reading feminine Hindi ("बोल रही हूँ") | Engine test | Gender-aware openings, plus a gender-agreement guard and repair |
| 3 | Language drifted back to Hinglish after an English switch | Engine test | Steering note each turn, a language guard, and translate repair |
| 4 | Hindi/Telugu written in Roman letters (less intelligible: 94–96% vs 100% STT recall) | STT round-trip test | Script guard, plus transliteration repair |
| 5 | Callback time asked 4–5 times | Engine test | LLM-declared `question_asks` for counting, limit of 3, drop-question repair |
| 6 | The guard accepted the 3rd bad attempt | Voice demo | Deterministic repair instead of acceptance |
| 7 | "Rush" undone by "interest" in the same turn | Engine test | Only one mode signal per turn, chosen by priority |
| 8 | "Haan ji boliye, kaun?" read as interest | Engine test | Tightened interest cues, added an identity signal |
| 9 | Seller turn sent to the LLM twice | Code review | Append to history after the LLM call |
| 10 | One-turn mode expired after the next reply | Code review | Expire at the start of the next turn |
| 11 | VANI offered WhatsApp | Voice demo | Channel guard and prompt rule |
| 12 | VANI pitched a meeting to a grievance seller | Voice demo | Goal guard |
| 13 | `do_not_call_registered` recorded before the seller agreed | Voice demo | Outcome validation against signals that actually fired, and a seller-stated time for callbacks |
| 14 | VANI ended the call after "OK, let's talk, in Telugu" | Voice demo | Premature-close guard |
| 15 | "my **machine**" (an idli-machine maker) flagged as bot suspicion | Voice demo | Bot context required |
| 16 | LLM labelled "send it on WhatsApp" as bot suspicion | Voice demo | Tier-2 identity signals need lexical support |
| 17 | Rule-ordering misattribution of seller evidence (v1) | Unit run | Reordered rules, evidence keyed by seller |
| 18 | `strict` JSON schema still returned malformed JSON | Repeat-call test | Retry, then safe fallback |
| 19 | `keyterms` rejected by saaras:v3 | API error | Moved to saaras:v4 |
| 20 | "11/100" read as "slash" | Transcript review | Sanitiser |

## Honest limits
See [APPROACH.md](APPROACH.md#honest-limits): informed-guess fields, no pitch control, the weakest signals (confusion, complaint), context-free evaluation, and latency.

Phase 3 additions:
- **Background voices:** the filtering is checked in code and by tests, not yet with a real microphone in a noisy room. The thresholds (`bargeConfirmMs`, the noise-floor factor in `src/static/index.html`) may need tuning.
- **The Sarvam-hosted agent has none of the engine's code checks.** On the prompt alone, it:
  - often writes Hindi in Roman letters;
  - rarely asks the clarifying question on a contradiction;
  - once closed early on a question about the WhatsApp details;
  - once offered a meeting after the buy-lead line.
- **Not re-measured:** the last prompt edits (the remaining "ji" line, the hosted agent's extraction prompt) were made after the credit pause.
- **Prompt length:** about 15,000 tokens; each LLM call is about 0.8 s, and the prompt was not shortened so that behaviour stays the same.
- **Live-only checks:** the WhatsApp, CRM, DND and Sarvam calling paths have been checked only as dry runs.
