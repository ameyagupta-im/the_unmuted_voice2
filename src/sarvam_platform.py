"""VANI on Sarvam's Voice Agents platform (docs.sarvam.ai/conversations), built on IndiaMART's master prompt
(docs/master_prompt.md): the same text the local engine runs, with section 9 replaced by the voice-platform rules,
then the additions and kept rules, then a SELLER CONTEXT block whose fields are agent INPUT variables ({{name}}),
filled per contact (campaign CSV column / instant-call agent_variables). Platform facts: docs/sarvam_platform_notes.md.

  - the reply is spoken text; the call ends through the platform's End call core tool, right after a closing line;
  - the outcome, slot and do-not-call flag are agent OUTPUT variables the platform extracts after the call;
  - voice and speaking speed are per agent, so there is one agent per (voice gender, voice style);
  - the greeting and starting language are per-call overrides (initial_bot_message, initial_language_name).
"""
from typing import Any, Dict, List

from master_prompt import CONTEXT_FIELDS, additions, master_text, var_name
from persona_generator import VOICES, VOICES_EN
from playbook import BOT_NAME, OUTCOMES

VAR = "{{%s}}"  # placeholder syntax; the platform's Response templates use {{field}} -- confirm for instructions
LANGUAGE_NAME = {"hi-IN": "Hindi", "en-IN": "English", "te-IN": "Telugu"}

# input variables: the master prompt's SELLER CONTEXT fields, one variable each
INPUT_VARIABLES = {var_name(f): (f"SELLER CONTEXT: {f}", "") for f in CONTEXT_FIELDS}
# output variables the platform extracts after the call: name -> (type, enum values or None, extraction prompt)
OUTPUT_VARIABLES = {
    "call_outcome": ("enum", OUTCOMES + ["NO_OUTCOME"],
                     "How the call ended, by the master prompt's section 8. NO_OUTCOME if the call dropped or none was "
                     "reached. A seller's question is never an agreement; a meeting needs the seller's clear yes to a day, "
                     "time and format, and VANI's confirmation that it is fixed ('meeting ... fix ho gayi hai') makes it MEETING_FIXED even "
                     "though the confirmation is sent on WhatsApp; INFO_SENT needs the seller to have asked for or agreed "
                     "to WhatsApp details, or VANI to have closed with 'our meeting timings are fixed ... details on "
                     "WhatsApp' because the seller insisted on hours outside 9 AM-6 PM. If the "
                     "transcript ends on VANI's question that the seller has not answered, the outcome is NO_OUTCOME."),
    "slot": ("string", None, "The day and time the seller agreed to, in their words; empty if none."),
    "meeting_format": ("enum", ["in_person", "online", "none"], "In person or online, as the seller chose; none if no meeting."),
    "do_not_call": ("enum", ["yes", "no"], "yes if the seller asked not to be called again, in any words."),
    "whatsapp_requested": ("enum", ["yes", "no"], "yes only if the seller asked for or agreed to WhatsApp details."),
    "seller_disposition": ("enum", ["Interested", "Open", "Curious", "Dissatisfied", "Engaged with exec", "Not right person",
                                    "Not interested", "Do not call", "Frustrated", "Unknown", "Wants human"],
                           "The seller disposition from the master prompt's section 8 table."),
    "complaint": ("string", None, "The seller's complaint about IndiaMART in their words; empty if none."),
    "seller_insights": ("string", None, "New facts the seller shared about their business, one line each."),
}

PLATFORM_SECTION_9 = """9. Output on this voice platform
Speak only plain spoken sentences: no JSON, no lists, no labels. When you say a closing line from section 8, use the
End call tool right after it -- and only then (never end while the seller is still talking, asking or explaining).
The platform records persona and goal switches and extracts the call outcome, slot, format, do-not-call and
disposition after the call, so never say them as labels."""


def voice_agents() -> Dict[str, Dict[str, Any]]:
    """One platform agent per (gender, voice style), with a voice per starting language."""
    agents = {}
    for (gender, style), hi_voice in VOICES.items():
        agents[f"vani_{gender}_{style}"] = {
            "gender": gender, "style": style, "bot_name": BOT_NAME[gender],
            "voices": {"Hindi": hi_voice, "English": VOICES_EN.get((gender, style), hi_voice), "Telugu": hi_voice}}
    return agents


def agent_key(persona: Dict[str, Any]) -> str:
    return f"vani_{persona['voice']['gender']['value']}_{persona['voice']['style']['value']}"


def seller_variables(persona: Dict[str, Any]) -> Dict[str, str]:
    """The per-contact values: the master SELLER CONTEXT fields (empty when the data does not have them)."""
    ctx = persona["conversation_plan"].get("seller_context") or {}
    return {var_name(f): str(ctx.get(f) or "") for f in CONTEXT_FIELDS}


def call_overrides(persona: Dict[str, Any]) -> Dict[str, str]:
    """Per-call overrides: the master greeting and the starting language."""
    return {"initial_bot_message": persona["conversation_plan"]["opening"]["value"],
            "initial_language_name": LANGUAGE_NAME[persona["language"]["primary"]["value"]]}


def build_instruction(gender: str) -> str:
    """The agent's instruction: the master prompt (section 9 for voice), additions, and the SELLER CONTEXT variables."""
    voice = ("You are Rohan (male voice: bol raha hoon, samajh gaya, kar dunga)." if gender == "male"
             else "You are Payal (female voice: bol rahi hoon, samajh gayi, kar dungi).")
    ctx = "SELLER CONTEXT\n" + "\n".join(f"{f}: {VAR % var_name(f)}" for f in CONTEXT_FIELDS)
    return f"""{master_text(PLATFORM_SECTION_9)}

{additions()}

{voice} The greeting (opening_message) has already been spoken: it gave your name and IndiaMART, so never introduce
yourself again unless the seller asks who is calling. Fields left empty below are not known: never invent them.

{ctx}"""


def greeting(gender: str) -> str:
    """Fallback greeting; every call overrides it with the seller's own (initial_bot_message)."""
    return (f"नमस्ते, मैं IndiaMART से {BOT_NAME[gender]} {'बोल रहा हूँ' if gender == 'male' else 'बोल रही हूँ'}। "
            f"क्या मेरी बात {VAR % 'company_name'} से हो रही है?")


def agent_bundle(key: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Everything needed to configure one agent (dashboard or the MCP server's configure_agent)."""
    return {
        "agent_key": key, "name": f"VANI {spec['bot_name']} ({spec['gender']}, {spec['style']})",
        "greeting": greeting(spec["gender"]), "instruction": build_instruction(spec["gender"]),
        "variables": {"input": [{"name": n, "description": d, "default": df} for n, (d, df) in INPUT_VARIABLES.items()],
                      "output": [{"name": n, "type": t, "values": vals, "extraction_prompt": p}
                                 for n, (t, vals, p) in OUTPUT_VARIABLES.items()],
                      "successful_when": "call_outcome = MEETING_FIXED"},
        "voice": {"model": "Bulbul V4", "per_language_voices": spec["voices"],
                  "note": "our ids are bulbul:v4-flash TTS ids; pick the matching speaker names in the agent's catalog"},
        "conversation_settings": {"starting_language": "Hindi", "switch_language_during_call": True,
                                  "languages_allowed": ["Hindi", "English", "Telugu"],
                                  "auto_detected_language_switch": True, "voicemail": False},
        "pronunciations": {"Hindi": {"IndiaMART": "इंडियामार्ट", "BuyLead": "बाय लीड", "WhatsApp": "व्हाट्सऐप"},
                           "English": {"IndiaMART": "India Mart", "BuyLead": "Buy Lead"}},
        "core_tools": ["End call", "Call transfer (Phase B: request_human)", "Language switch"],
    }


def agent_variables_for(persona: Dict[str, Any]) -> Dict[str, Any]:
    """What one call needs: which agent, its variables, and the per-call overrides."""
    return {"agent_key": agent_key(persona), "agent_variables": seller_variables(persona),
            "app_overrides": call_overrides(persona)}


def missing_placeholders(text: str) -> List[str]:
    import re
    used = set(re.findall(r"\{\{(\w+)\}\}", text))
    return sorted(used - set(INPUT_VARIABLES))
