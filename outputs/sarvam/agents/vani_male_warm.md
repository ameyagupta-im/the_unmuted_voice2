# VANI Rohan (male, warm)  (`vani_male_warm`)

Set up in the Sarvam dashboard (Build), or ask the MCP server's `configure_agent` to apply `vani_male_warm.json`.
After saving, commit a version and record its app_id and version in `outputs/sarvam/agent_ids.json`.

## Greeting (every call overrides it with the seller's own opening: `initial_bot_message`)
नमस्ते, मैं IndiaMART से Rohan बोल रहा हूँ। क्या मेरी बात {{company_name}} से हो रही है?

## Instruction
Paste the `instruction` field of `vani_male_warm.json`. Placeholders are written `{{name}}`: insert each as the
matching agent variable with `@` if the editor does not convert them.

## Input variables (one CSV column / agent_variables key each; "send to LLM" on)
| Name | Description | Default |
|---|---|---|
| `bot_name_voice` | SELLER CONTEXT: bot_name / voice | — |
| `opening_message` | SELLER CONTEXT: opening_message | — |
| `company_name` | SELLER CONTEXT: company_name | — |
| `city_state_locality` | SELLER CONTEXT: city / state / locality | — |
| `business` | SELLER CONTEXT: business | — |
| `deals_in` | SELLER CONTEXT: deals_in | — |
| `products_listed_gst_registered_since` | SELLER CONTEXT: products_listed / gst_registered_since | — |
| `why_we_are_calling` | SELLER CONTEXT: why_we_are_calling | — |
| `past_bot_calls` | SELLER CONTEXT: past_bot_calls | — |
| `past_outcomes` | SELLER CONTEXT: past_outcomes | — |
| `past_concerns` | SELLER CONTEXT: past_concerns | — |
| `past_questions` | SELLER CONTEXT: past_questions | — |
| `recent_call_summaries` | SELLER CONTEXT: recent_call_summaries | — |
| `exec_in_touch` | SELLER CONTEXT: exec_in_touch | — |
| `do_not_call` | SELLER CONTEXT: do_not_call | — |
| `language_observed` | SELLER CONTEXT: language_observed | — |
| `best_hour` | SELLER CONTEXT: best_hour | — |
| `seller_type` | SELLER CONTEXT: seller_type | — |
| `persona` | SELLER CONTEXT: persona | — |
| `call_goal` | SELLER CONTEXT: call_goal | — |
| `alt_number_last_digits` | SELLER CONTEXT: alt_number_last_digits | — |
| `area_enquiry_count` | SELLER CONTEXT: area_enquiry_count | — |
| `similar_sellers` | SELLER CONTEXT: similar_sellers | — |

## Output variables (extracted after the call)
| Name | Type | Values | Extraction prompt |
|---|---|---|---|
| `call_outcome` | enum | MEETING_FIXED, CALLBACK_SCHEDULED, INFO_SENT, COMPLAINT_LOGGED, EXEC_HANDOFF, CONTACT_UPDATED, RESPECTFUL_EXIT, DO_NOT_CALL, ESCALATED_EXIT, CALL_BACK_LATER, HUMAN_HANDOFF, NO_OUTCOME | How the call ended, by the master prompt's section 8. NO_OUTCOME if the call dropped or none was reached. A seller's question is never an agreement; a meeting needs the seller's clear yes to a day, time and format, and VANI's confirmation that it is fixed ('meeting ... fix ho gayi hai') makes it MEETING_FIXED even though the confirmation is sent on WhatsApp; INFO_SENT needs the seller to have asked for or agreed to WhatsApp details, or VANI to have closed with 'our meeting timings are fixed ... details on WhatsApp' because the seller insisted on hours outside 9 AM-6 PM. If the transcript ends on VANI's question that the seller has not answered, the outcome is NO_OUTCOME. |
| `slot` | string | — | The day and time the seller agreed to, in their words; empty if none. |
| `meeting_format` | enum | in_person, online, none | In person or online, as the seller chose; none if no meeting. |
| `do_not_call` | enum | yes, no | yes if the seller asked not to be called again, in any words. |
| `whatsapp_requested` | enum | yes, no | yes only if the seller asked for or agreed to WhatsApp details. |
| `seller_disposition` | enum | Interested, Open, Curious, Dissatisfied, Engaged with exec, Not right person, Not interested, Do not call, Frustrated, Unknown, Wants human | The seller disposition from the master prompt's section 8 table. |
| `complaint` | string | — | The seller's complaint about IndiaMART in their words; empty if none. |
| `seller_insights` | string | — | New facts the seller shared about their business, one line each. |

Successful when: `call_outcome = MEETING_FIXED`

## Voice (Speakers & voice, per-language voices on; model Bulbul V4)
| Starting language | Voice |
|---|---|
| Hindi | `shubh_enhi_companion` |
| English | `dev_en_conversational` |
| Telugu | `shubh_enhi_companion` |

our ids are bulbul:v4-flash TTS ids; pick the matching speaker names in the agent's catalog.

## Conversation settings
{
  "starting_language": "Hindi",
  "switch_language_during_call": true,
  "languages_allowed": [
    "Hindi",
    "English",
    "Telugu"
  ],
  "auto_detected_language_switch": true,
  "voicemail": false
}

## Pronunciation dictionary (Advanced)
```json
{
  "pronunciations": {
    "Hindi": {
      "IndiaMART": "इंडियामार्ट",
      "BuyLead": "बाय लीड",
      "WhatsApp": "व्हाट्सऐप"
    },
    "English": {
      "IndiaMART": "India Mart",
      "BuyLead": "Buy Lead"
    }
  }
}
```

## Core tools
End call, Call transfer (Phase B: request_human), Language switch
