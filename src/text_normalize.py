"""Devanagari -> Roman normalisation for tier-1 signal detection.

Found by listening to real recordings: Saaras in `transcribe` mode returns Hindi
in Devanagari, while the regex vocabulary (and the dataset's transcripts) are
Romanized Hinglish, so a Roman-only detector silently matches nothing. Live
audio now uses Saaras `translit` mode (Roman output directly); this module
covers the remaining path -- text typed in Devanagari into the web demo.
"""
import re

from config import client

_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")


# IndiaMART, 10 Oct 2026: VANI never says "ji" / "जी" (the seller may). जी as a whole word only: जीवन, ज़रूरी stay.
_JI = r"(?:(?<![A-Za-z])[Jj]i(?![A-Za-z])|(?<![\u0900-\u0963\u0966-\u097F])जी(?![\u0900-\u0963\u0966-\u097F]))"  # the dandas । ॥ are not letters
_JI_LEAD = re.compile(r"(^|(?<=[.?!।]\s))" + _JI + r"\s*[,،.।!]?\s*")        # "जी, समझ गई" / "जी। अच्छा" / "Ji, very good"
_JI_INNER = re.compile(r"\s+" + _JI + r"(?=[\s.,!?।]|$)")                # "कोई बात नहीं जी।" / "Sure ji,"


def drop_ji(text: str) -> str:
    """VANI's line without "ji": "जी, समझ गई।" -> "समझ गई।", "कोई बात नहीं जी।" -> "कोई बात नहीं।",
    "Sure ji, your..." -> "Sure, your...", "Namaste ji, main..." -> "Namaste, main..."."""
    if not text:
        return text
    out = _JI_LEAD.sub(lambda m: m.group(1), text)   # sentence-initial first: "Okay. Ji, noted." -> "Okay. Noted."
    out = _JI_INNER.sub("", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    out = re.sub(r"\s+([,.?!।])", r"\1", out)
    out = re.sub(r"^[,،]\s*", "", out)
    # an English sentence that started with "Ji, " starts with a capital again
    out = re.sub(r"(^|[.?!]\s)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)
    return out or ("ठीक है।" if _DEVANAGARI_RE.search(text) else "Okay.")   # a reply that was only "ji"


def is_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI_RE.search(text or ""))


def to_roman(text: str) -> str:
    if not text or not is_devanagari(text):
        return text or ""
    try:
        return client().text.transliterate(input=text, source_language_code="hi-IN",
                                           target_language_code="en-IN").transliterated_text
    except Exception:
        return text  # tier 2 (LLM) still reads the original text
