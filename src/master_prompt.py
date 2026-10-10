"""IndiaMART's master prompt (docs/master_prompt.md) as the single source of VANI's behaviour.

The local engine (prompt_builder), the Sarvam agent (sarvam_platform) and the plain export (export_master_prompt) all
build their instruction from this file, so the text IndiaMART approved is the text every VANI runs. Each target only
swaps section 9 (the output format) for its own, and appends the additions and kept rules below the master text.
"""
from config import ROOT

PATH = ROOT / "docs" / "master_prompt.md"
_END = "<!-- END OF MASTER TEXT -->"
_S9 = "9. Output format (every turn)"
_S10 = "10. Guardrails and speaking style (always)"

# the master prompt's SELLER CONTEXT fields, in its order (section 2)
CONTEXT_FIELDS = ["bot_name / voice", "opening_message", "company_name", "city / state / locality", "business", "deals_in",
                  "products_listed / gst_registered_since", "why_we_are_calling", "past_bot_calls", "past_outcomes",
                  "past_concerns", "past_questions", "recent_call_summaries", "exec_in_touch", "do_not_call",
                  "language_observed", "best_hour", "seller_type", "persona", "call_goal", "alt_number_last_digits",
                  "area_enquiry_count", "similar_sellers"]


def _read() -> str:
    return PATH.read_text(encoding="utf-8")


def master_text(section9: str = None) -> str:
    """Sections 1-11 of the master prompt; section 9 replaced by `section9` when given."""
    text = _read().split(_END)[0].rstrip()
    if section9 is not None:
        head, rest = text.split(_S9, 1)
        tail = rest.split(_S10, 1)[1]
        text = f"{head}{section9.rstrip()}\n\n{_S10}{tail}"
    return text


def additions() -> str:
    """IndiaMART's additions and the rules kept from live testing (after the master text)."""
    return _read().split(_END, 1)[1].strip()


def var_name(field: str) -> str:
    """Field label -> agent variable name ("city / state / locality" -> city_state_locality)."""
    return field.replace(" / ", "_").replace(" ", "_")


def context_block(values: dict) -> str:
    """The SELLER CONTEXT block, master field names, empty fields left out (never invented)."""
    return "SELLER CONTEXT\n" + "\n".join(f"{f}: {values[f]}" for f in CONTEXT_FIELDS
                                          if values.get(f) not in (None, "", "None"))
