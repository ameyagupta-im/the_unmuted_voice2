"""Sarvam Bulbul TTS + Saaras STT wrappers used by the live engine.

TTS-side fixes, each found while building:
  - Bulbul reads bare 5+ digit numbers digit-by-digit; format_numbers() adds
    thousands separators (documented in the SDK convert() docstring). Known
    gap: it would also reformat pincodes/phone numbers, which no VANI reply
    speaks, so it is left at that.
  - LLM replies occasionally carry markdown/emoji/JSON debris; sanitize()
    strips them because the Sarvam voice rules require plain spoken text.
  - Speaker ids must match the model (v3 short names vs v4-flash
    name_lang_style); validate_speaker() fails fast instead of a mid-call 400.
STT: Saaras `translit` mode returns Roman-script text AND the detected
language in one ~0.45s call, so the signal detector needs no extra
transliteration hop and language-switch detection is free.
"""
import base64
import hashlib
import io
import os
import re
import threading
import wave
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Tuple

from config import client, OUTPUTS, STT_MODE, STT_MODEL, TTS_MODEL

V3_SPEAKERS = {
    "shubh", "aditya", "ritu", "priya", "neha", "rahul", "pooja", "rohan", "simran", "kavya", "amit", "dev", "ishita",
    "shreya", "ratan", "varun", "manan", "sumit", "roopa", "kabir", "aayan", "ashutosh", "advait", "anand", "tanya",
    "tarun", "sunny", "mani", "gokul", "vijay", "shruti", "suhani", "mohit", "kavitha", "rehan", "soham", "rupali",
}
_V4_RE = re.compile(r"^[a-z]+_(hi|en|enhi|te|ta|bn|gu|kn|ml|mr|od|pa)_[a-z_]+$")

_NUMBER_RE = re.compile(r"(?<![\d,])(\d{5,})(?![\d,])")
_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F000-\U0001F2FF]")
_MARKDOWN_RE = re.compile(r"[*_`#>\[\]{}|~]")


def format_numbers(text: str) -> str:
    return _NUMBER_RE.sub(lambda m: f"{int(m.group(1)):,}", text)


def sanitize(text: str) -> str:
    text = _EMOJI_RE.sub("", text or "")
    text = _MARKDOWN_RE.sub("", text)
    # "11/100" was produced in a Telugu reply; spoken as "eleven slash hundred" otherwise
    text = re.sub(r"(\d+)\s*/\s*(\d+)", r"\1 out of \2", text)
    text = re.sub(r"\s+", " ", text).strip()
    return format_numbers(text)


# Bulbul reads the Latin "IndiaMART" as "India Art" (English) and "इंडिया एम आर्ट" (Hindi): checked by synthesising and
# transcribing without keyterms (10 Oct 2026, after a seller heard "India Art"). Spoken forms, speech only -- the
# transcript and the screen keep "IndiaMART".
SPOKEN = {
    "hi-IN": [(r"india\s*mart", "इंडियामार्ट"), (r"buy\s*leads", "बाय लीड्स"), (r"buy\s*lead", "बाय लीड")],
    "en-IN": [(r"india\s*mart", "India Mart"), (r"buy\s*leads", "Buy Leads"), (r"buy\s*lead", "Buy Lead")],
    "te-IN": [(r"india\s*mart", "ఇండియామార్ట్"), (r"buy\s*leads", "బై లీడ్స్"), (r"buy\s*lead", "బై లీడ్")],
}


def speakable(text: str, language_code: str) -> str:
    for pat, spoken in SPOKEN.get(language_code, SPOKEN["en-IN"]):
        text = re.sub(pat, spoken, text, flags=re.I)
    return text


def validate_speaker(speaker: str, model: str = TTS_MODEL) -> None:
    if model == "bulbul:v3" and speaker not in V3_SPEAKERS:
        raise ValueError(f"speaker '{speaker}' is not a bulbul:v3 voice")
    if model == "bulbul:v4-flash" and not _V4_RE.match(speaker):
        raise ValueError(f"speaker '{speaker}' is not a bulbul:v4-flash persona id (name_lang_style)")


# ---- speed (none of it changes the words or the voice) ----
# A reply of several sentences is synthesised sentence by sentence IN PARALLEL and joined with a pause: Bulbul's time
# grows with the text, so a 3-sentence reply came back in ~1.7 s instead of ~3 s (tests/latency_bench.py). Every clip
# is cached by (text, speaker, language, pace, model): fixed lines -- the first reply, the two-option question, the
# closings -- are synthesised once per voice, in memory and on disk (outputs/tts_cache, VANI_TTS_CACHE=0 disables).
SENTENCE_GAP_S = 0.3        # the pause Bulbul leaves between sentences in one request
_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix="tts")
_MEM: "OrderedDict[str, bytes]" = OrderedDict()
_MEM_MAX = 256
_LOCK = threading.Lock()
_INFLIGHT = {}
CACHE_DIR = OUTPUTS / "tts_cache"


def _key(text, speaker, language_code, pace, model, temperature) -> str:
    raw = f"{model}|{speaker}|{language_code}|{round(pace, 2)}|{temperature}|{text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _cache_on() -> bool:
    return os.environ.get("VANI_TTS_CACHE", "1") != "0"


def _cache_get(k: str) -> Optional[bytes]:
    with _LOCK:
        if k in _MEM:
            _MEM.move_to_end(k)
            return _MEM[k]
    p = CACHE_DIR / f"{k}.wav"
    if _cache_on() and p.exists():
        data = p.read_bytes()
        _cache_put(k, data, disk=False)
        return data
    return None


def _cache_put(k: str, data: bytes, disk: bool = True) -> None:
    with _LOCK:
        _MEM[k] = data
        _MEM.move_to_end(k)
        while len(_MEM) > _MEM_MAX:
            _MEM.popitem(last=False)
    if disk and _cache_on():
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            (CACHE_DIR / f"{k}.wav").write_bytes(data)
        except OSError:
            pass


def _synthesize_one(text: str, speaker: str, language_code: str, pace: float, model: str,
                    temperature: Optional[float]) -> bytes:
    k = _key(text, speaker, language_code, pace, model, temperature)
    hit = _cache_get(k)
    if hit is not None:
        return hit
    with _LOCK:  # the same clip already being made (a prefetch): wait for it instead of a second request
        fut = _INFLIGHT.get(k)
    if fut is not None:
        try:
            return fut.result(timeout=30)
        except Exception:
            pass
    kwargs = dict(text=speakable(sanitize(text), language_code), language_code=language_code, speaker=speaker,
                  pace=max(0.5, min(2.0, pace)), model=model, output_audio_codec="wav", speech_sample_rate=22050)
    if temperature is not None:
        kwargs["temperature"] = temperature
    resp = client().text_to_speech.convert(**kwargs)
    data = base64.b64decode(resp.audios[0])
    _cache_put(k, data)
    return data


def split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.?!।])\s+", text or "") if s.strip()]


def join_wavs(clips: List[bytes], gap_seconds: float = SENTENCE_GAP_S) -> bytes:
    """Clips of one voice (22050 Hz mono, 16-bit) joined with a pause, in memory."""
    if len(clips) == 1:
        return clips[0]
    frames, params = [], None
    for i, c in enumerate(clips):
        with wave.open(io.BytesIO(c)) as w:
            params = params or w.getparams()
            if i:
                frames.append(b"\x00" * (int(gap_seconds * w.getframerate()) * w.getsampwidth() * w.getnchannels()))
            frames.append(w.readframes(w.getnframes()))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setparams(params)
        w.writeframes(b"".join(frames))
    return buf.getvalue()


def synthesize(text: str, speaker: str, language_code: str, pace: float = 1.0, model: str = TTS_MODEL,
               temperature: Optional[float] = None) -> bytes:
    validate_speaker(speaker, model)
    k = _key(text, speaker, language_code, pace, model, temperature)
    hit = _cache_get(k)
    if hit is not None:
        return hit
    parts = split_sentences(text)
    if len(parts) <= 1 or os.environ.get("VANI_TTS_PARALLEL", "1") == "0":
        return _synthesize_one(text, speaker, language_code, pace, model, temperature)
    clips = list(_POOL.map(lambda s: _synthesize_one(s, speaker, language_code, pace, model, temperature), parts))
    data = join_wavs(clips)
    _cache_put(k, data, disk=False)  # the sentences are on disk already
    return data


def prefetch(text: str, speaker: str, language_code: str, pace: float = 1.0, model: str = TTS_MODEL) -> None:
    """Synthesise in the background (e.g. the first reply while the greeting plays); errors are ignored."""
    if not text:
        return
    try:
        validate_speaker(speaker, model)
    except Exception:
        return
    k = _key(text, speaker, language_code, pace, model, None)
    with _LOCK:
        if k in _MEM or k in _INFLIGHT:
            return
        fut = _POOL.submit(lambda: synthesize(text, speaker, language_code, pace, model))
        _INFLIGHT[k] = fut
    fut.add_done_callback(lambda _f: _INFLIGHT.pop(k, None))


_MIME = {"wav": "audio/wav", "webm": "audio/webm", "ogg": "audio/ogg", "mp3": "audio/mpeg", "m4a": "audio/mp4"}


# brand words Saaras must not split ("WhatsApp" was heard as "what is app" in the Chennai test). "VANI" is
# NOT a keyterm: sellers never say it, and it pulled "WhatsApp pe" to "VANI app pe" (compare_stt_modes.py;
# brand words 21/23 without it vs 20/23 with it on the phone-band brand lines)
KEYTERMS = ["IndiaMART", "WhatsApp", "BuyLead", "catalog", "catalogue", "enquiry"]


def transcribe(audio: bytes, filename: str = "turn.wav") -> Tuple[str, Optional[str]]:
    """Returns (roman_text, language_code). Accepts wav, or webm/ogg straight from a browser MediaRecorder."""
    mime = _MIME.get(filename.rsplit(".", 1)[-1].lower(), "audio/wav")
    resp = client().speech_to_text.transcribe(
        file=(filename, audio, mime), model=STT_MODEL, mode=STT_MODE, language_code="unknown", keyterms=KEYTERMS,
    )
    return resp.transcript or "", getattr(resp, "language_code", None)


def silence(seconds: float, framerate: int = 22050) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(b"\x00\x00" * int(seconds * framerate))
    return buf.getvalue()


def concat_wavs(clips: List[bytes], out_path: str, gap_seconds: float = 0.35) -> None:
    """Concatenate WAV clips (stdlib only), resampling-free: all clips are
    requested at 22050 Hz mono so formats always match."""
    readers = [wave.open(io.BytesIO(c), "rb") for c in clips if c]
    if not readers:
        raise ValueError("no audio to concatenate")
    p = readers[0].getparams()
    gap = wave.open(io.BytesIO(silence(gap_seconds, p.framerate)), "rb").readframes(10 ** 9)
    with wave.open(out_path, "wb") as out:
        out.setnchannels(p.nchannels)
        out.setsampwidth(p.sampwidth)
        out.setframerate(p.framerate)
        for r in readers:
            if (r.getnchannels(), r.getsampwidth(), r.getframerate()) != (p.nchannels, p.sampwidth, p.framerate):
                raise ValueError("WAV clips have mismatched formats")
            out.writeframes(r.readframes(r.getnframes()))
            out.writeframes(gap)
