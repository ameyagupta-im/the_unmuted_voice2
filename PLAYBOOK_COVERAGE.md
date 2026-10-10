# Seller Call Scenarios playbook: coverage map

Every rule in `scenarios.pdf` (the Seller Call Scenarios: Persona and Goal Playbook), where it is implemented, and what proves it works. The playbook is encoded as data in [`src/playbook.py`](src/playbook.py), which the generator, engine, prompt and tests all read.

Since 10 Oct 2026, **IndiaMART's master prompt** ([`docs/master_prompt.md`](docs/master_prompt.md)) is the single source for what VANI says. It refines the playbook, and where the two differ the master prompt and IndiaMART's live-testing points win; those places are marked **(master)** or **(IndiaMART)** below. The main changes:
- Meetings only 9 AM–6 PM, with the slot chosen by the seller.
- WhatsApp details only when the seller agrees.
- No mid-call cut.
- No "ji".

The proof comes from three layers:
- **Offline**: `tests/test_offline.py`, `test_integrations.py`, `test_sarvam.py`. Deterministic, with a scripted LLM. **209/209 pass.**
- **Live scenario suite**: `tests/scenario_suite.py`, against the real Sarvam LLM. **35/35 scenarios, 90/90 checks** in the last full run. Report in `outputs/scenarios/scenario_report.md`.
- **Recording replay**: `tests/recording_replay.py`, which feeds the real seller lines from moments where the old bot broke the playbook through the new agent. **18/18 in two of three runs, 17/18 in the other**, in phase 2, before the master prompt. It has not been re-run since. Report in `outputs/recordings/replay_report.md`.

The Sarvam-hosted agent (the same master prompt, with none of the engine's code checks) is measured separately by `tests/prompt_only_suite.py`: **50/54 checks**.

## Pre-call: seller types (first match wins)
| # | Type | Trigger as implemented | Our count | Playbook count | Test |
|---|---|---|---|---|---|
| 1 | Fatigued repeat lead | 4+ past bot attempts | 51,451 | 52,363 | `test_seller_type[fatigued]` |
| 2 | English-preferring professional | 60%+ English in the seller's own past turns (12.8k transcribed calls), or TN/KA/KL/PY with no transcript | 2,164 | 4,491 | `test_seller_type[english]` |
| 3 | Cautious / burned | Past complaint/frustration/trust objection, **confirmed from past call summaries** | 1,088 | 731 | `test_seller_type[cautious]` |
| 4 | Already with an executive | Flag, answered executive calls Aug–Sep, or a summary says so | 6,435 | 5,488 | `test_seller_type[with_executive]` |
| 5 | Busy business owner | Turnover ≥ ₹5 Cr or average answered call < 20 s (thresholds calibrated to the playbook count) | 31,107 | 31,381 | `test_seller_type[busy]` |
| 6 | Warm, interested lead | Past meeting, pricing/benefit questions, or bucket NUR/PAM/SCHD | 19,295 | 17,690 | `test_seller_type[warm]` |
| 7 | Small local trader | Everything else | 36,645 | 37,219 | `test_seller_type[small]` |
| – | Do-not-call | Never dialled | 1,178 | 1,178 | `test_do_not_call_is_never_dialled` |

**Deviation:** Telangana and Andhra are *offered* Telugu but are not forced into the English type. Our evidence (E8) shows Telangana sellers replied mostly in Hindi.

**Per-seller personalisation** (`persona_generator.py`):
- **Language mix:** mirrors the seller's own past turns.
- **Pace:** halfway between VANI's measured rate (2.76 words/s) and the seller's own rate (population 2.36), plus the type's bias.
- **Formality and vocabulary:** from business size and digital activity.
- **Bot name:** Payal (female) / Rohan (male), with gendered Hindi verbs.
- **Callback slot:** the hour the seller most often talked in past calls.
- **Greeting (IndiaMART):** VANI's own name, then a check that it is the right business. "नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात {company} से हो रही है?" Company names come from IndiaMART (`data/company_names.csv`); without one, the line names the category. The greeting has no "ji" and no "virtual assistant".
- **First reply (master 3.2):** said word for word when the seller answers the greeting. Its parts, in order:
  - any apology first (a repeat seller, or a past complaint);
  - the reason for the call, from the lead bucket, as a soft observation;
  - a buyers line if the reason is not about enquiries (no numbers);
  - one light question.

## Goals (goal 0 "understand" always first)
| Goal | Chosen before the call when | Fallbacks | Ending | Test |
|---|---|---|---|---|
| Complaint recovery | Summaries/objections show dissatisfaction, trust/call-handling issues, frustration, budget denial | callback, respectful exit | COMPLAINT_LOGGED | `test_goal_order`, scenario 4 |
| Executive hand-off | Already with an executive | callback, data update | EXEC_HANDOFF | scenarios 8, 8b |
| Data update | Wrong number / not the decision maker | callback, respectful exit | CONTACT_UPDATED | scenario 7 |
| Respectful exit | 7+ attempts | WhatsApp, callback | RESPECTFUL_EXIT | scenario 9 |
| Info on WhatsApp | 4–6 attempts | callback, meeting | INFO_SENT | scenario 12 |
| Nurture | Past not-interested / budget, no interest | WhatsApp, respectful exit | – | `test_goal_order` |
| Meeting | Signs of interest, else no negative history | callback, WhatsApp | MEETING_FIXED | scenarios 13, 13d, 25 |
| Callback | Asked for a callback last time, or bucket OLP/PANF | meeting, WhatsApp | CALLBACK_SCHEDULED | `test_goal_order` |
| Human hand-off | Only mid-call | – | HUMAN_HANDOFF | scenario 11 |

**Deviation:** "Callback" is checked *before* "meeting by default (no negative history)". Otherwise the callback goal could never be chosen, since almost every seller has no negative history.

## Live signals (priority order) → persona mode / goal switch
| # | Signal | Persona mode | Goal switch / action | Detected by | Proof |
|---|---|---|---|---|---|
| 1 | Do-not-call (incl. Telugu "malli call cheyoddu") | – | ends DO_NOT_CALL | regex + LLM | scenario 1, `test_telugu_do_not_call` |
| 2 | Connectivity / silence | CLEAR_AUDIO (not held once the seller speaks) | Silence: "माफ़ कीजिए, आपकी आवाज़ ठीक से नहीं आ रही। क्या आप कुछ कह रहे थे?" **(IndiaMART)**; the 2nd time ends CALL_BACK_LATER | regex + LLM; the browser sends a silent turn after 8 s | scenarios 2, 13f |
| 3 | Frustration | CALM_EMPATHETIC (no pitch afterwards) | callback. A complaint about repeated calls → WhatsApp offer, never another call. The 2nd frustration ends ESCALATED_EXIT (COMPLAINT_LOGGED with a complaint), **except** when the seller is asking something real or says they are still talking: VANI apologises and gives them the floor **(IndiaMART)**. A 3rd ends the call | regex + LLM (high confidence only) | scenarios 3, 23, 24 |
| 4 | Complaint | CALM_EMPATHETIC | complaint recovery (always wins); support time asked | regex + LLM | scenario 4 |
| 5 | Are you a bot? | TRANSPARENT (one reply) | "virtual assistant" with VANI's name, only when the **seller's own words** ask | regex; the LLM's label alone is not enough | scenario 5, `test_llm_label_alone_never_unlocks_virtual_assistant` |
| 6 | Who is calling / why | TRANSPARENT | VANI's **name**, IndiaMART and the reason | regex + LLM, disclosure guard | scenario 6 |
| 7 | Not the right person | – | data update; the number closes CONTACT_UPDATED | regex + LLM | scenario 7 |
| 8 | Already with an executive | – | account-manager offer **(master)**; a described need → meeting (two slots); "nothing more" → EXEC_HANDOFF | regex + LLM | scenarios 8, 8b |
| 9 | Not interested | – | First no: one two-option reason question **(master)**. A reason, a second no, or a final phrase ("zaroorat nahi", "galti se dekh liya") → RESPECTFUL_EXIT with no WhatsApp | regex + LLM | scenarios 9, 9b |
| 10 | Busy | BRIEF | callback; "milne ka time nahi" during meeting setup → online meeting | regex + LLM | scenario 10, `test_no_time_to_meet_makes_it_online_not_a_callback` |
| 11 | Wants a human | – | human hand-off | regex + LLM | scenario 11 |
| 12 | Wants WhatsApp | – | INFO_SENT, confirmed and closed **(master 12)**. A question *about* the details is answered, not closed | regex + LLM (needs lexical evidence), dialogue act | scenarios 12, 12b |
| 13 | Gives a time | – | **Meeting (IndiaMART):** 9 AM–6 PM from tomorrow, the option the seller chose, then "मिलकर या online?", fixed only after that answer. A time outside the window → window stated, nearest slot offered; still insisting → "timings are fixed, details on WhatsApp" (INFO_SENT). Callbacks and support calls: any time | regex + meeting gate (`slots.py`) | scenarios 4, 11, 13, 13b, 13d, 13e |
| 14 | Language change | language changes, **voice stays the same** | – | explicit request, a full sentence, or two short lines in a row (hysteresis) | scenario 14, `test_short_lines_do_not_flip_the_language` |
| 15 | Need: few enquiries | – | meeting (two slots) | regex + LLM | scenario 15 |
| 15.5 | Buy-lead question **(IndiaMART)** | – | IndiaMART seller dashboard → BuyLeads (website or app), no meeting ask; a second question → WhatsApp offer | regex + LLM | scenario 13c |
| 16 | Price question | never quotes, never "free" | "Charges depend on the plan and leads; the executive explains for your category" **(master)**, answer before the question | regex + LLM + price guards | scenario 16 |
| 17 | Confusion | SIMPLE | – | regex + LLM | scenario 17 |
| 18 | Clear interest | ENGAGED (suppressed by a refusal in the same turn) | meeting | regex + LLM | scenario 18 |
| 19 | Hang-up risk | COMPRESSED | – | logistic model, test AUC 0.646 vs keyword 0.564 | `outputs/models/hangup_model.json` |
| 20 | Answer / context | – | captured in seller insights and the fact ledger, never re-asked; a real contradiction gets one clarifying question; an exaggerated flip after a pitch is sarcasm (= frustration) | LLM + rules (`facts.py`) | scenarios 20, 21, 22 |

**Switching rules:**
- A clear signal (regex, or LLM with high confidence) switches immediately.
- A medium-confidence LLM signal must repeat on the next turn. The exception is compliance/harm signals (`ACT_ON_MEDIUM`); frustration is deliberately excluded, because its second strike ends the call.
- A new mode is held for at least 2 turns, unless a higher-priority signal arrives. CLEAR_AUDIO is not held once the seller speaks.
- The voice identity never changes mid-call.
- **Not a turn (IndiaMART):** background voices, noise, or a listener's "haan / hmm" while VANI speaks. VANI resumes where she stopped. Over the greeting, "haan haan" still counts as an answer.

## Rules in every scenario: where they are enforced
Every reply passes deterministic guards (`live_engine._reply_problem`) before it is spoken.
- **Mechanical problems** are fixed in code with the LLM's own words, with no extra LLM call: script, verb gender, a banned phrase, an unasked "virtual assistant", Hindi in an English call, a missing name, words after a clarifying question.
- **Other problems** get up to two LLM retries with a correction; if they persist, the engine repairs the reply itself.

| Rule | Guard |
|---|---|
| Never claim to be human | `human` |
| Never quote prices/discounts/leads/results (learned: the old bot quoted ₹4,000/month, ₹32,000/year, "30–40% conversion"); never call the meeting "free" (master) | `price`, `price_unanswered`, `free_meeting` |
| Never pitch after a complaint or frustration; never repeat a declined pitch or WhatsApp offer | `pitch_after_complaint`, `pitch_after_no`, `repeat_declined_offer` |
| No meeting ask after a buy-lead question (IndiaMART) | `buylead_meeting` |
| Meeting slots: only 9 AM–6 PM from tomorrow, two concrete options, never decided by VANI (IndiaMART) | `bad_slot_offer` + the meeting gate |
| No call offer to a seller fed up with repeated calls | `call_offer` |
| Never "good to hear" after bad news or sarcasm | `glad_on_bad`, `sarcasm_literal` |
| Contradictions: one gentle clarifying question, ending on it | `clarify_missing`, `no_clarify`, `clarify_tail` |
| Understand first | `understand_first` |
| Say who is calling (with VANI's name) and why when asked; "virtual assistant" only when the seller asks | `disclosure`, `unasked_va` |
| One question per turn, end with a question unless closing | `no_question`, `drop_question` |
| Apologise once; no repeated sentence; short replies when busy | `repeat_sentence`, `too_long` |
| No filler phrases ("dhyan se sun rahi hoon", "aasan shabdon mein") | `banned_phrase` |
| Never say "ji" (IndiaMART) | `drop_ji()` on every spoken line, plus the prompt |
| Ask limits (understanding 2, goal step 3 / 2 for 7+ attempts, refusals 2, frustration 2, connectivity 2) — master section 7 | `drop_question` + engine counters + fallback goals |
| Never reveal labels/goals/variables | `internal` |
| No SMS or email offers: WhatsApp or a call only | `channel` |
| Language and script (Hindi in Devanagari, trade words in Latin), Hindi gender agreement | `translate`, `script`, `gender` |
| Closings are statements said once, from the master prompt's endings table | `closing_line()` |
| An ending must be earned (no false meetings, callbacks, WhatsApp sends or DNC); never closed while the seller is asking | `unsupported_outcome` + `_outcome_supported` + the meeting gate |
| WhatsApp only for what the seller agreed to: the details (INFO_SENT) or a confirmed meeting's date, time and format | `integrations.on_call_end` |
