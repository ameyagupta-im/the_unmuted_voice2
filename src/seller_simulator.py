"""Plays a seller on the other end of a VANI call, so the voice demo can run
end to end without a human -- while keeping every mid-call switch LIVE.

The simulator is an LLM given the seller's real data, a temperament derived
from it, and the shared scenario beats. It writes each line in reaction to
what VANI actually just said (if VANI handles frustration well, the seller
calms down; if VANI repeats itself, the seller gets more annoyed). Its line
is then spoken by a Sarvam seller voice, transcribed by Saaras, and only that
transcript reaches the VANI engine -- so detection runs on real STT output,
exactly as on a phone call, and nothing about VANI's switch is pre-scripted.

For the judged live switch, a human plays the seller in the web demo
(src/web_app.py); this simulator is for reproducible side-by-side recordings.
"""
import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from config import client, LLM_MODEL

# Same scenario for every seller (brief 3.6): an outbound VANI call this week.
SCENARIO_BEATS = [
    "Answer the phone and ask who is calling and why.",
    "Answer VANI's question about your business in your own way (honestly, per your temperament).",
    "React in your own way to what VANI said (see your temperament); this is your key moment.",
    "Ask what this costs / whether it is paid.",
    "Decide: accept and give a day/time, or decline, in line with your temperament and how VANI treated you.",
    "Answer VANI's last question briefly (a time, a yes/no, a contact preference); if VANI is closing, just say thank you.",
    "If VANI asks whether you need anything else, say no and thank her (ask one short last question only if you truly have one).",
]


@dataclass
class SellerCharacter:
    seller_id: int
    description: str
    temperament: str
    key_moment: str
    start_language: str
    seller_voice: Dict[str, str]


SCRIPT_RULES = {
    "hi-IN": "Write in Roman-script Hinglish, the way a north-Indian trader speaks on the phone.",
    "en-IN": "Write in Indian English.",
    "te-IN": "Write in Telugu script, with English trade words (catalog, price, meeting) in Latin script.",
}


class SellerSimulator:
    def __init__(self, character: SellerCharacter, model: str = LLM_MODEL):
        self.c = character
        self.model = model
        self.beat = 0
        self.language = character.start_language
        self.history: List[Dict[str, str]] = []

    def _system(self) -> str:
        return f"""You are role-playing a real IndiaMART seller receiving an outbound call from VANI, IndiaMART's virtual assistant.
Seller profile (real data): {self.c.description}
Your temperament: {self.c.temperament}
Your key moment in this call: {self.c.key_moment}
Rules:
- Speak like a real busy business owner on the phone: short (3-18 words), natural, no stage directions, no quotes.
- React to what VANI actually said. If VANI respects you (short, apologises, stops pushing), soften. If VANI repeats itself or ignores your point, get more irritated.
- Do what the current beat says and only that; do not jump ahead (e.g. do not ask for a callback or end the call before the last beat).
- Stay in character.
- Language now: {self.language}. {SCRIPT_RULES[self.language]}
Return JSON: {{"line": "...", "language": "hi-IN|en-IN|te-IN"}}"""

    def next_line(self, vani_said: str) -> Optional[Dict[str, str]]:
        if self.beat >= len(SCENARIO_BEATS):
            return None
        beat = SCENARIO_BEATS[self.beat]
        if self.beat == 2 and self.c.key_moment.startswith("SWITCH_LANGUAGE:"):
            self.language = self.c.key_moment.split(":", 1)[1].strip()
        self.history.append({"role": "user", "content": f"VANI: {vani_said}\n[Beat {self.beat + 1}: {beat}]"})
        msgs = [{"role": "system", "content": self._system()}] + self.history
        line, lang = None, self.language
        for _ in range(2):
            try:
                resp = client().chat.completions(
                    messages=msgs, model=self.model, temperature=0.5, max_tokens=200,
                    response_format={"type": "json_object"})
                data = json.loads(resp.choices[0].message.content)
                line, lang = data["line"].strip(), data.get("language", self.language)
                break
            except Exception:
                continue
        if not line:
            line = {"hi-IN": "Haan ji, boliye.", "en-IN": "Yes, go on.", "te-IN": "చెప్పండి."}[self.language]
        self.history.append({"role": "assistant", "content": json.dumps({"line": line, "language": lang}, ensure_ascii=False)})
        self.beat += 1
        if lang not in SCRIPT_RULES:
            lang = self.language
        return {"line": line, "language": lang, "beat": beat}

    def voice_for(self, language: str) -> str:
        return self.c.seller_voice.get(language) or next(iter(self.c.seller_voice.values()))


def character_from_persona(persona: Dict, key_moment: str, temperament: str, seller_voice: Dict[str, str]) -> SellerCharacter:
    s = persona["seller_snapshot"]
    desc = (f"{s.get('business_type') or 'business'} in {s.get('city') or '?'}, {s.get('state') or '?'}; turnover "
            f"{s.get('turnover') or 'unknown'}; main product {s.get('category') or 'unknown'}; IndiaMART has called "
            f"{int(s.get('attempts') or 0)} times before; past objections: {s.get('past_objections') or 'none'}; "
            f"last call: {(s.get('last_summaries') or ['none'])[-1]}.")
    return SellerCharacter(persona["seller_id"], desc, temperament, key_moment,
                           persona["language"]["primary"]["value"], seller_voice)
