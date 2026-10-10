# VANI Seller-Fit Adaptive Persona

Problem 4 (Persona Design), IndiaMART × Sarvam Voice AI Hackathon 2.0.

Before each call, VANI builds a **persona** (how it speaks) and a **goal** (what this call should achieve) for that seller from the seller's data. During the call it adapts both live: 20 playbook signals plus IndiaMART's buy-lead question, mid-call goal switches, and 11 endings. What VANI says comes from IndiaMART's master prompt ([docs/master_prompt.md](docs/master_prompt.md)), with IndiaMART's live-testing changes applied inside it. It also learns from 83 real call recordings. Everything runs on Sarvam: Saaras v4 STT, sarvam-105b LLM, and Bulbul v4 TTS in Hindi, English and Telugu. It runs locally (`web_app.py`) or as Sarvam Voice Agents.

- [APPROACH.md](APPROACH.md) – approach note
- [PLAYBOOK_COVERAGE.md](PLAYBOOK_COVERAGE.md) – every playbook scenario → code → proof
- [skills.md](skills.md) – build journey, tools, every bug found and fixed
- [outputs/presentation/VANI_persona_one_slide.pptx](outputs/presentation/VANI_persona_one_slide.pptx) – the one slide

## Setup
```
python -m pip install -r requirements.txt
# .env in the project root:  SARVAM_API_KEY=<your key>
# unzip base_context/PS4_dataset_*.zip and the bot-recordings zip into data/
```

## Run
| What | Command | Output |
|---|---|---|
| Evidence from past calls | `python src/evidence_analysis.py` | `outputs/evidence/evidence_report.md` |
| Per-seller context (bucket, best hour, summaries, own speech) | `python src/seller_context.py` | `outputs/models/seller_context.pkl` |
| Transcribe the bot recordings (Saaras batch, diarized) | `python src/transcribe_recordings.py` | `outputs/recordings/turns.csv` |
| Learn from the recordings | `python src/analyze_recordings.py` then `python src/learned_examples.py` | `recording_insights.md`, `learned_examples.json` |
| Hang-up risk model | `python src/hangup_model.py` | `outputs/models/hangup_model.json` |
| Persona generator on the sample seller files | `python src/generate_personas.py` | `outputs/persona_specs/*.json/.md`, `distinctness.md` |
| …on your own seller file / all 149k sellers | `--input sellers.csv` / `--all --summary-only` | `index.csv` |
| Voice demo: same scenario, 3 contrasting sellers | `python src/run_live_demo.py` | `outputs/demo/<id>/call.wav`, `transcript.md`, `switch_log.json` |
| **Live demo: you play the seller** | `python src/web_app.py` → http://127.0.0.1:5050 | `outputs/live_sessions/<call>/` |
| The engine's full prompt per seller | `python src/export_agent_prompts.py` | `sarvam_agent/<seller_id>_system_prompt.txt`, `_initial_message.txt` |
| Playbook scenario suite (live LLM, uses Sarvam credits) | `python tests/scenario_suite.py` | `outputs/scenarios/scenario_report.md` (35 scenarios) |
| Old bot's recorded mistakes, replayed | `python tests/recording_replay.py` | `outputs/recordings/replay_report.md` |
| Signal detection vs IndiaMART labels | `python src/eval_signals.py` | `outputs/evidence/signal_eval.md` |
| Held-out evaluation set (split by call) | `python src/build_eval_set.py` | `outputs/eval/*.jsonl`, `act_labels.csv` (fill `human_act`) |
| Offline signal + dialogue-act report | `python src/eval_signals.py --offline` | `outputs/eval/eval_report.md` |
| STT mode comparison on 8 kHz audio | `python src/compare_stt_modes.py` | `outputs/eval/stt_mode_comparison.md` |
| Offline regression tests (no network) | `python -m pytest tests -q` | 209 tests |
| Turn latency by stage (LLM, retries, TTS) | `python tests/latency_bench.py --tts --tag <name>` | `outputs/perf/latency_<name>.json` |

## Hosting on Sarvam Voice Agents
Sarvam runs the calls (telephony, speech, barge-in); this repo supplies the agents and the seller data. Platform facts and open questions: [docs/sarvam_platform_notes.md](docs/sarvam_platform_notes.md).

| What | Command | Output |
|---|---|---|
| Agent configurations (one per voice) | `python src/sarvam_deploy.py` | `outputs/sarvam/agents/<agent>.json` + `.md` dashboard guide |
| Campaign contact lists for sellers | `python src/build_campaign.py --sellers 3419775,1243794 --phones phones.csv` | `outputs/sarvam/campaigns/<name>/` (CSV per agent, campaign body, report) |
| The deployed instruction, tested on the LLM alone | `python tests/prompt_only_suite.py --target platform` | `outputs/scenarios/prompt_only_platform.md` |
| IndiaMART master prompt + SELLER CONTEXT for any chat/voice AI | `python src/export_master_prompt.py 3419775` | `outputs/master_prompt/<seller_id>.txt` |

### Behaviour set by IndiaMART (10 Oct 2026)
- **Greeting:** VANI's own name, then the business check. Company names (from IndiaMART, not in the seller files) go in `data/company_names.csv` with the columns `seller_id,company_name`; with a name, VANI opens "नमस्ते, मैं IndiaMART से Payal बोल रही हूँ। क्या मेरी बात {company} से हो रही है?".
- **Disclosure:** "Virtual assistant" only when the seller asks.
- **Buy leads:** buy-lead questions get the IndiaMART seller dashboard line, with no meeting ask.
- **Meetings:**
  - Two concrete slots between 9 AM and 6 PM, from tomorrow.
  - The seller chooses one ("parso wala", "dusra wala"; a plain yes means the first). VANI says it back with "मिलकर या online?", and the meeting is fixed only after that answer.
  - A seller who insists on other hours is told the timings are fixed and gets the details on WhatsApp.
  - A confirmed meeting gets a WhatsApp confirmation with the calendar date.
- **WhatsApp:** nothing else is sent unless the seller asked for it or agreed.
- **No mid-call cut:** the call is never ended while the seller is still talking or asking. A seller fed up with repeated calls is never offered another call.
- **Silence:** "माफ़ कीजिए, आपकी आवाज़ ठीक से नहीं आ रही। क्या आप कुछ कह रहे थे?"
- **Background voices:** background voices, noise, or a "haan" over VANI don't interrupt her.
- **No "ji":** VANI never says "ji".

The master prompt, the additions and the decisions taken are in [docs/master_prompt.md](docs/master_prompt.md); the playbook coverage is in [PLAYBOOK_COVERAGE.md](PLAYBOOK_COVERAGE.md).

API calls (`src/sarvam_api.py`) are dry runs unless `VANI_SARVAM_LIVE=1`, with `SARVAM_ORG_ID`, `SARVAM_WORKSPACE_ID`, `SARVAM_CONNECTION_ID`, `SARVAM_AGENT_NUMBER` in `.env`. Agents themselves are created in the dashboard or through Sarvam's MCP server; record their ids in `outputs/sarvam/agent_ids.json`.

## Speed
Measured with `tests/latency_bench.py` on the 65 scenario-suite turns:

| | Before | After |
|---|---|---|
| Median turn | 2.34 s | 0.82 s |
| Slowest 10% of turns | 5.5 s | 3.4 s |
| Worst turn | 8.5 s | 4.7 s |
| LLM calls | 66 | 55 |

What changed (none of it alters what VANI says):
- Voice for multi-sentence replies is generated sentence by sentence in parallel, with a 0.3 s pause between sentences.
- Every voice clip is cached in memory and in `outputs/tts_cache`, so fixed lines are made once per voice. `VANI_TTS_CACHE=0` turns the cache off and `VANI_TTS_PARALLEL=0` turns parallel generation off.
- The first reply is generated while the greeting plays.
- A stop sequence ends the LLM's blank-line padding. Before, the padding ran to the 800-token limit and the turn was retried.
- Mechanical reply fixes (script, verb gender, a banned phrase, an unasked "virtual assistant" mention, Hindi in an English call) are done in code instead of with another LLM call.
- All romanised-Hindi fragments are transliterated in one call.

## Integrations (dry run unless switched on)
Every external action is logged to `outputs/integrations/*.jsonl` and nothing leaves the machine until its flag is set in `.env`:

| Integration | When | Live flag | Needs |
|---|---|---|---|
| WhatsApp details | call closes as INFO_SENT (the seller asked for or said yes to them) | `VANI_WHATSAPP_LIVE=1` | `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, optional `WHATSAPP_TEMPLATE` |
| WhatsApp meeting confirmation (date, time, in person / online) | call closes as MEETING_FIXED | `VANI_WHATSAPP_LIVE=1` | as above, optional `WHATSAPP_MEETING_TEMPLATE` (`{{1}}` date, `{{2}}` time, `{{3}}` format) |
| Lead write-back | every call end | `VANI_CRM_LIVE=1` | `CRM_URL`, `CRM_TOKEN` |
| Do-not-call list | before every call; written at DO_NOT_CALL | always on | — (SQLite in `outputs/integrations/`) |
| National DND scrub | before every call | `VANI_DND_LIVE=1` | `DND_CHECK_URL` |
| Calling hours (IST) | before every call | enforced with `VANI_TELEPHONY_LIVE=1` or `VANI_ENFORCE_CALL_HOURS=1`; else a warning | `VANI_CALL_HOURS` (default `09:00-21:00`) |
| Recording disclosure in the opening | persona build | `VANI_DISCLOSE_RECORDING=1` | — |

## Code map
| File | Role |
|---|---|
| `src/playbook.py` | The scenarios playbook as data: seller types, goals, fallbacks, 20 signals + buy-lead, persona modes, goal switches, endings (master prompt section 8), ask limits, bucket reasons |
| `src/seller_context.py` | Per-seller context from 5 data sources |
| `src/persona_generator.py` | Seller → persona + goal, with reason, evidence and confidence on every field |
| `docs/master_prompt.md`, `src/master_prompt.py` | IndiaMART's master prompt, the single source for every target (engine, Sarvam agent, plain export) |
| `src/prompt_builder.py` | The engine's prompt: master text with its JSON section 9, additions, live call state, SELLER CONTEXT |
| `src/slots.py` | Meeting slots: 9 AM–6 PM on a calendar day from tomorrow, the option the seller chose, the calendar date |
| `src/signal_detector.py` | Tier-1 signals (Hindi, English, Telugu) and language-switch detection |
| `src/hangup_model.py` | Hang-up risk model (scenario 19) |
| `src/live_engine.py` | Two-layer state machine: signals → persona mode / goal switches → fixed master lines or the LLM → guards → validated ending → TTS |
| `src/facts.py` | Fact ledger: contradictions (one clarifying question) and sarcasm |
| `src/voice_synth.py`, `src/text_normalize.py` | Bulbul / Saaras wrappers (parallel TTS, voice cache, IndiaMART pronunciation), script handling, `drop_ji()` |
| `src/transcribe_recordings.py`, `src/analyze_recordings.py`, `src/learned_examples.py` | Learning from the 83 recordings |
| `src/seller_simulator.py`, `src/run_live_demo.py` | Recorded side-by-side voice demo |
| `src/web_app.py`, `src/static/index.html` | Interactive live demo: hands-free voice detection, barge-in that ignores background voices, silence prompt |
| `src/sarvam_platform.py`, `src/sarvam_deploy.py`, `src/sarvam_api.py`, `src/build_campaign.py` | Sarvam Voice Agents: agent bundles, dry-run API calls, campaign files |
| `src/utterance.py` | Dialogue act of each seller line (question / request / yes / no / bye / statement) |
| `src/integrations/` | WhatsApp, lead write-back, suppression and calling hours (dry run by default) |
| `src/build_eval_set.py`, `src/compare_stt_modes.py` | Evaluation set from IndiaMART's evaluators; STT mode comparison |
| `src/evidence_analysis.py`, `src/eval_signals.py` | Evidence and detection evaluation |
| `tests/` | Offline tests; the live scenario suite, the hosted-agent prompt-only suite, the recording replay and the latency benchmark (these four use Sarvam credits) |

Data note: seller data, transcripts and recordings contain real names. Keep `data/` and `outputs/` inside IndiaMART systems.
