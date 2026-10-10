"""Turns the recording analysis (outputs/recordings/lessons.json) into examples
the live agent can safely use. Nothing reaches the prompt unless it passes:

  - VERIFIED: the quote appears (near-)verbatim in the diarized transcripts,
    so LLM-paraphrased or invented "good lines" are dropped
  - CLEAN: agent lines must use respectful fillers only (no dekho/suno/yaar/arre),
    must not quote prices, leads or results, and must not give a human name
    as if VANI were a person
  - for agent lines: the analyst marked that scenario handled per the playbook

Writes outputs/recordings/learned_examples.json:
  seller_phrasings  {signal: [real seller words]}   -> tier-2 classification examples
  agent_lines       {situation: [lines that worked]} -> reply style examples
  mistakes          [what real calls got wrong]       -> "never do" list
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUTPUTS  # noqa: E402

REC = OUTPUTS / "recordings"
BANNED = re.compile(r"\b(dekho|suno|yaar|arre|abe)\b", re.I)
PRICE_OR_RESULT = re.compile(r"(hazaar|hazar|lakh|rupe|rupaye|rs\.?\s*\d|₹|\bgst\b|percent|%|\d+\s*(leads|inquiries|enquiries))", re.I)
AGENT_NAMES = re.compile(r"\b(harsh\w*|namrata|awanshika|shivanshika|vanshika|prerna|premna|riya|abhinit|rajesh)\b", re.I)
# Agent lines are only reused for situations where the real calls' lines matched the
# playbook. Excluded after review: not_interested (the "good" line was a re-pitch),
# identity_question (gave human names), understanding / already_with_executive (noise).
ALLOWED_SITUATIONS = {"price_query", "connectivity", "busy", "gives_time", "closing", "interest", "opening"}


def _norm(s):
    return re.sub(r"[^a-z0-9ऀ-ॿఀ-౿ ]", "", str(s).lower()).strip()


def main():
    lessons = json.loads((REC / "lessons.json").read_text(encoding="utf-8"))
    turns = pd.read_csv(REC / "turns.csv")
    corpus = {sp: " || ".join(_norm(t) for t in g.text.fillna("")) for sp, g in turns.groupby("speaker")}
    corpus_all = corpus.get("bot", "") + " || " + corpus.get("seller", "")

    def verified(q):
        n = _norm(q)
        return len(n) >= 6 and (n in corpus_all or n[:40] in corpus_all)

    seller_phrasings, dropped = {}, 0
    for sig, exs in lessons["scenario_examples"].items():
        keep = []
        for e in exs:
            q = (e.get("seller_quote") or "").strip()
            if q and verified(q) and q not in keep:
                keep.append(q)
            else:
                dropped += 1
        if keep:
            seller_phrasings[sig] = keep[:6]

    agent_lines = {}
    for sit, items in lessons["good_phrasings"].items():
        if sit not in ALLOWED_SITUATIONS:
            dropped += len(items)
            continue
        keep = []
        for it in items:
            line = (it.get("line") or "").strip()
            if (line and verified(line) and not BANNED.search(line) and not PRICE_OR_RESULT.search(line)
                    and not AGENT_NAMES.search(line) and line not in keep):
                keep.append(line)
            else:
                dropped += 1
        if keep:
            agent_lines[sit] = keep[:4]

    mistakes = [m for m, _ in lessons["common_mistakes"]][:15]
    out = {"source": f"{lessons['n_calls']} recorded IndiaMART bot calls, transcribed with Sarvam Saaras",
           "seller_phrasings": seller_phrasings, "agent_lines": agent_lines, "mistakes": mistakes,
           "speaking_rate_median_wps": lessons["speaking_rate_median_wps"], "dropped_unverified_or_unclean": dropped}
    (REC / "learned_examples.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"kept {sum(map(len, seller_phrasings.values()))} seller phrasings, {sum(map(len, agent_lines.values()))} agent lines; "
          f"dropped {dropped} unverified or unclean")
    return out


_CACHE = None


def load():
    global _CACHE
    if _CACHE is None:
        p = REC / "learned_examples.json"
        _CACHE = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"seller_phrasings": {}, "agent_lines": {}, "mistakes": []}
    return _CACHE


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    o = main()
    for k, v in o["agent_lines"].items():
        print("##", k, *[f"\n  - {x[:120]}" for x in v])
