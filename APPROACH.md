# Approach note: Problem 4, Persona Design

## The problem, as we read it
VANI calls every seller with one voice and one script and never adapts. The fix is not just a better voice: VANI must **understand the seller first**, then pursue the **one next step that fits them**. A meeting is only one of several good outcomes; the others are a callback, details on WhatsApp, a logged complaint, an executive hand-off, a corrected contact, or a respected exit. The Seller Call Scenarios playbook (`scenarios.pdf`) defines this as two layers, both set before the call and both switchable on any seller turn:
- **Persona**: how VANI speaks.
- **Goal**: what the call tries to achieve.

IndiaMART's **master prompt** ([`docs/master_prompt.md`](docs/master_prompt.md)) later fixed the exact words for the opening, the counter-answers and the closings. It is now the single source for everything VANI says, with IndiaMART's additions from live testing applied inside it.

## What we built
1. **Persona + goal generator** (`persona_generator.py`, rules in `playbook.py`). Seller data from five sources (seller file, past bot calls and summaries, the seller's own past turns, executive calls, lead bucket) feeds:
   - one of **7 seller types** (first match wins);
   - the persona: voice/bot name (Payal or Rohan), pace mirrored halfway to the seller's own speaking rate, language mix mirrored from the seller's own turns, formality, empathy and assertiveness on 1–5, turn length;
   - the **primary goal** (9 goals, checked in playbook order) with fallbacks;
   - the conversation plan:
     - a greeting that starts with VANI's name and checks the company name;
     - a first reply built from the lead bucket (apology if needed, the reason, one light question);
     - a callback slot at the hour the seller usually talks;
     - ask limits and guardrails;
     - the master prompt's 23 seller-context fields.

   Every setting carries a reason, evidence ids and a confidence level; missing data lowers the confidence. Our type distribution over all 149,363 sellers lands within a few percent of the playbook's own counts.
2. **Learning from 83 real recordings** (`transcribe_recordings.py` → `analyze_recordings.py` → `learned_examples.py`).
   - Saaras batch STT with diarization produced 3,367 turns.
   - An LLM checked each call against the playbook.
   - Only verified, clean lessons reach the agent.
   - The biggest lessons: the old bot **quoted prices in 6 of 18 price questions** and **kept pitching after "not interested" in 6 of 10**.
3. **Live engine** (`live_engine.py`), a two-layer state machine:
   - **Understanding the line:**
     - Saaras v4 STT in `translit` mode with brand keyterms.
     - Each seller line gets a **dialogue act** (question, request, statement, yes, no, bye; `utterance.py`), so a question is answered and never taken as agreement.
     - Tier-1 detection: Hindi/English/Telugu patterns, the language detector with hysteresis, and the **hang-up risk model** (AUC 0.646 vs 0.564 for keywords on held-out calls).
     - A **fact ledger** (`facts.py`) catches contradictions (one gentle clarifying question) and sarcasm.
   - **Signal handling:** the playbook's 20 signals plus IndiaMART's buy-lead question are handled in priority order. Each one can switch the persona mode, switch the goal, count against an ask limit, or end the call.
   - **Reply:**
     - Set master-prompt lines are said word for word with no LLM call: the first reply, the refusal question, the buy-lead line, the account-manager offer, the meeting steps, the closings.
     - Otherwise one sarvam-105b call classifies the turn in context and writes the reply under the master prompt and the live state.
   - **Guards:** every reply passes deterministic guards before it is spoken:
     - never human;
     - no prices, nothing called free;
     - no pitch after a complaint or a no;
     - meeting slots only 9 AM–6 PM and chosen by the seller;
     - no call offer to a seller fed up with calls;
     - disclosure only when asked;
     - one question;
     - language, script and gender;
     - never "ji".

     Mechanical fixes happen in code; others get an LLM retry.
   - **Endings:**
     - An ending must be earned by what the seller actually said.
     - The call is never cut while the seller is asking or still talking.
     - The closing line comes from the master prompt's endings table.
4. **Calling in the browser** (`web_app.py`, `static/index.html`):
   - **Hands-free:** voice activity detection gated against the background-noise level, and barge-in that needs sustained near-mic speech.
   - **Background sound:** voices, noise or a "haan" over VANI is ignored, and she resumes where she stopped.
   - **Silence:** an 8 s silence gets "क्या आप कुछ कह रहे थे?".
   - `run_live_demo.py` records the same scenario for three contrasting real sellers, with each seller played by an LLM and voiced by Bulbul.
5. **Integrations, dry run until switched on** (`integrations/`):
   - **Before the call:** suppression list, national DND and calling hours.
   - **After the call:** CRM write-back, and WhatsApp only for what the seller agreed to: the details (INFO_SENT) or a confirmed meeting's calendar date, time and format.
6. **Hosting on Sarvam Voice Agents** (`sarvam_platform.py`, `sarvam_deploy.py`, `build_campaign.py`):
   - One agent per voice, built from the same master prompt.
   - Input variables carry the seller context; output variables capture the outcome, slot, format, do-not-call and disposition.
   - Campaign files for calling seller lists.
7. **Speed** (`tests/latency_bench.py`): the median turn went from 2.34 s to 0.82 s with no change to what VANI says. The four changes:
   - parallel sentence-level TTS, with a voice cache;
   - the first reply voiced while the greeting plays;
   - a stop sequence for the LLM's whitespace padding;
   - mechanical fixes in code instead of LLM retries.

## How we know it works
- **Playbook scenario suite** (`tests/scenario_suite.py`): every playbook scenario plus IndiaMART's live-testing points, run on the live LLM. **35/35 scenarios, 90/90 checks** in the last full run. This includes the master prompt's own meeting example, seller line for line. Results in `outputs/scenarios/`.
- **The hosted agent's prompt alone** (`tests/prompt_only_suite.py`): **50/54 checks** with none of the engine's code checks. The misses are listed under limits.
- **Recording replay** (`tests/recording_replay.py`): every real moment the old bot broke the playbook, replayed through the new agent. **18/18 in two of three runs, 17/18 in the third**, measured in phase 2, before the master prompt. It has not been re-run since. Results in `outputs/recordings/replay_report.md`.
- **Signal detection vs IndiaMART's evaluator labels** on 4,718 real utterances, held-out split (`outputs/evidence/signal_eval.md`). Recall / precision: ai_bot 0.96/0.86, price 0.97/0.79, identity 0.84/0.59, frustration 0.50/0.84, complaint 0.46/0.75, confusion 0.28/0.36.
- **209 offline regression tests**: each one is a playbook or master-prompt rule, or a bug found while building.
- **Distinctness, measured**: personas across seller types are 0.50 apart vs 0.12 within a type, with 33 distinct voice/language/goal combinations.
- **Real live sessions**: 63 calls played into the browser, by microphone and by text. Most of phase 3's bugs were found there (see [skills.md](skills.md)).

## Honest limits
- **Informed guesses, not measured** (marked low confidence): voice gender per type, pitch (Bulbul v4 has no pitch control), Telugu-first behaviour, and the "busy owner: faster" bias. The past data never varied these.
- **Hang-up model:** AUC 0.646 is a real lift over keywords but below the playbook's 0.71.
- **Frustration recall is 0.50** (precision 0.84): a calm "nahi chahiye" counts as not_interested, and medium-confidence frustration never ends a call on its own. The held-out samples are small.
- **Weakest signals:** confusion and complaint recall. The evaluation scores utterances without the preceding VANI turn, which the live engine does have.
- **Latency:** about 0.8 s per LLM call (the prompt is about 15,000 tokens and was not shortened, to keep behaviour unchanged), plus voice generation for new text. Speaking the first sentence while the rest is checked would be the next step.
- **The Sarvam-hosted agent has none of the engine's code checks.** On the prompt alone it:
  - often writes Hindi in Roman letters;
  - rarely asks the clarifying question on a contradiction;
  - once closed early on a question about the WhatsApp details;
  - once offered a meeting after the buy-lead line.
- **Background voices:** the filtering is checked in code, not yet in a noisy room. Its thresholds may need tuning.
- **Not re-measured:** the last few prompt edits were made while Sarvam credits were paused.
- **Simulated sellers vary** between runs, so the voice demo's exact path changes. The scenario suite is the stable check.
- **Integrations:** WhatsApp, CRM, DND and Sarvam calling have run only as dry runs.
- **WhatsApp:** used as a goal per the seller-side playbook and IndiaMART's master prompt. This deliberately overrides the buyer-side doc's "no WhatsApp" rule.
