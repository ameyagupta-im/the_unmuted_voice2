# VANI on Sarvam Voice Agents: platform notes

What Sarvam's platform does and does not offer, confirmed from its docs on 10 Oct 2026, and how VANI's deployment
uses it. Read this before changing `src/sarvam_platform.py`, `src/sarvam_deploy.py`, `src/build_campaign.py` or
`src/sarvam_api.py`.

## Confirmed

| Need | What Sarvam offers | How VANI uses it |
|---|---|---|
| Calls | Telephony via Exotel, Twilio, Plivo, Vobiz, Smartflo, Pulse, Intalk, or numbers rented from Sarvam; campaigns (contact list + schedule) and instant outbound calls | No telephony of our own |
| Agent setup | Dashboard, or the MCP server (`https://mcp.sarvam.ai/voice-agents`, `configure_agent`, OAuth sign-in renewed daily). **No public REST endpoint creates or edits an agent** | `sarvam_deploy.py` writes a complete bundle per agent (JSON + dashboard guide) |
| Instruction | Greeting + natural-language instructions (Persona, Objective, Context, Guardrails, Steps); reply is spoken | IndiaMART's master prompt with a spoken-output section 9, the additions and kept rules, and the SELLER CONTEXT as `{{variables}}`: the same text the engine runs |
| Per-call data | Input variables: from campaign CSV columns, instant-call `agent_variables`, or an on-start API hook; "send to LLM" toggle per variable | 23 input variables per seller, the master prompt's SELLER CONTEXT fields (`INPUT_VARIABLES`) |
| Per-call overrides | `initial_bot_message`, `initial_language_name`, `initial_state_name` | The persona's own opening line and starting language |
| Outcome | Output variables (String or Enum with an extraction prompt), filled after the call; a "Successful when" rule | `call_outcome` (enum of the 11 endings + NO_OUTCOME), `slot`, `meeting_format`, `do_not_call`, `whatsapp_requested`, `seller_disposition`, `complaint`, `seller_insights`. The extraction prompt follows the 10 Oct rules: a meeting needs the seller's yes to day, time and format; INFO_SENT needs the seller's request or agreement, or the fixed-timings close |
| Ending the call | "End call" core tool | Right after a section-8 closing line, never while the seller is still talking, asking or explaining |
| Voice | One default voice per agent, optional voice per starting language; one speaking speed and pitch per agent; Bulbul V3/V4 | One agent per (gender, voice style): 9 agents |
| Language | Starting language; "switch language during call" (follows the caller), allowed languages, auto-detected switch | Hindi, English, Telugu allowed; the instruction's language rule (kept rule 4) guards against flipping on short lines |
| Barge-in | Built in: the agent stops when the caller talks over it | Set the interruption sensitivity / minimum interruption duration and background-noise suppression as high as the agent settings allow, so background voices and a "haan" do not stop VANI (IndiaMART, 10 Oct 2026); the instruction (rule 7) also tells VANI to carry on over them |
| Silence | Platform silence timeout | The instruction (rule 7): "Maaf kijiye, aapki awaaz theek se nahi aa rahi. Kya aap kuch keh rahe the?"; a second silence closes with CALL_BACK_LATER |
| Tools | API tools (in-call, on_start, on_end) with call-context variables: caller number, transcript so far, interaction id, call length; secrets in workspace Secrets; up to 30 s timeout | Phase B: record_outcome, send_whatsapp_details, mark_do_not_call, request_human |
| Transfer | "Call transfer" core tool to a number or SIP URI | Phase B: `request_human` |
| Webhook | Instant-call and campaign webhooks after each attempt: `attempt_id`, `status`, `duration`, `interaction_id`, `final_agent_variables`, `interaction_transcript` [{role, en_text}], `webhook_config.metadata` | Phase C post-call checks |
| DND | An org-wide suppression list, excluded from every campaign; addable in the UI or through a DND API | Our suppression list must be synced to it (Phase C) |
| Pronunciation | Per-language dictionary JSON (`"pronunciations"`), Indic-script spellings recommended | IndiaMART, BuyLead and WhatsApp in each bundle |
| Tests | Test suites and evals through the API | Possible later: our scenario lines as Sarvam tests |

## Gaps to confirm on the account

1. **Placeholder syntax in stored instructions.** The editor inserts variables with `@`; the docs show `{{field}}` only in tool response templates. The bundles use `{{name}}`: check that it binds, or re-insert with `@`.
2. **Cohort transformation file.** Uploading a cohort needs a JSON that maps CSV columns to the phone number, variables and overrides, but its format is not documented. `build_campaign.py` writes our best guess; use **Download Sample** in the campaign wizard and adapt it.
3. **Example vs schema disagreements.** `connection_configs` uses `agent_phone_number` in the schema but `phone_numbers` + `weight` in examples, and `webhook_config` is top-level in the campaign schema but inside `app_config` in the example. `sarvam_api.py` follows the schema.
4. **Webhook transcript is English.** `interaction_transcript` holds `en_text` (translated). The post-call checks read Hinglish, so Phase C needs the original-language transcript (Analytics `GET .../transcripts/{interaction_id}`: response schema not documented) or must run on English.
5. **Webhook authentication.** No signing scheme is documented: the Phase C endpoint needs its own secret (for example in `webhook_config.metadata` or the URL).
6. **Voice catalog names.** Our voice ids are bulbul:v4-flash TTS ids (e.g. `kavya_hi_conversational`); the agent's voice picker may list display names (e.g. "Shubh"). Map them in the dashboard.
7. **National DND (NCPR).** The docs do not say Sarvam scrubs against the national registry; compliance is stated to be the customer's responsibility.
8. **Campaign schedule timezone.** The API takes `allowed_schedule.timezone`; the wizard does not show one.

## What VANI loses on the platform (compared with the local engine)

- **Per-turn code checks.** The engine's guards (price, human claim, repeat questions, outcome validation, contradiction ledger) do not run in the call. Phase B moves the important ones into tools; Phase C re-checks every call afterwards.
- **Pace changes mid-call.** Speaking speed is per agent, so busy/confused/upset modes change wording and length only.
- **Persona voice per seller.** It still comes from the seller type, through the choice of agent.

Measured on the prompt alone (`python tests/prompt_only_suite.py --target platform`, 15 scenarios × 2 runs, 10 Oct 2026): **50/54 checks**. Passing:
- the meeting flow, the 9 AM–6 PM window and the fixed-timings close;
- refusals, buy leads, disclosure;
- the venting seller.

Misses:
- no clarifying question on a contradiction;
- an early close on a question about the WhatsApp details;
- one meeting offer after the buy-lead line.

The hosted agent also often writes Hindi in Roman letters (the engine converts it to Devanagari in code). After VANI's lines in the master prompt lost their "ji", 2 of 100 replies still had it, both from one rule line that has since been fixed. Not re-measured yet.

## Sources
- [Variables & Personalization](https://docs.sarvam.ai/conversations/build/variables-personalization.md)
- [Run-time](https://docs.sarvam.ai/conversations/build/run-time.md)
- [Speakers & voice](https://docs.sarvam.ai/conversations/build/voice-language.md)
- [Instruction](https://docs.sarvam.ai/conversations/build/system-prompt.md)
- [Core tools](https://docs.sarvam.ai/conversations/build/tools/core-tools.md)
- [API tool](https://docs.sarvam.ai/conversations/build/tools/https-tool.md)
- [On-start & on-end hooks](https://docs.sarvam.ai/conversations/build/on-start-on-end-hooks.md)
- [MCP server](https://docs.sarvam.ai/conversations/mcp.md)
- [Deploy with code](https://docs.sarvam.ai/conversations/deploy/deploy-with-code.md)
- [API introduction](https://docs.sarvam.ai/api-reference/conversations.md)
- [Create deployment](https://docs.sarvam.ai/conversations/api/deployments/create.md)
- [Create outbound call](https://docs.sarvam.ai/conversations/api/instant-outbound/create.md)
- [Instant outbound webhook payload](https://docs.sarvam.ai/conversations/api/instant-outbound/webhook-payload.md)
- [Create campaign (API)](https://docs.sarvam.ai/conversations/api/campaigns/create.md)
- [Create a campaign (guide)](https://docs.sarvam.ai/conversations/deploy/campaigns/create-campaign.md)
- [Upload cohort](https://docs.sarvam.ai/conversations/api/campaigns/cohorts/upload.md)
- [DND](https://docs.sarvam.ai/conversations/deploy/campaigns/dnd.md)
- [Get transcripts](https://docs.sarvam.ai/conversations/api/analytics/transcripts.md)
