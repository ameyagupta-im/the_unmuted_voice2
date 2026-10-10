"""Per-seller context the persona generator needs beyond the seller file,
learned from the other data sources (playbook "personalised per seller"):

  latest lead bucket         -> opening reason (bot calls)
  best hour                  -> callback slot: the hour the seller most often talked (answered bot calls)
  past call summaries        -> complaint / executive / wrong-contact / callback / interest flags
  own past turns             -> English share and speaking rate (call turns)
  executive calls Aug-Sep    -> already with an executive (executive calls)

Built once and cached to outputs/models/seller_context.pkl.
"""
import glob
import pickle
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ROOT, OUTPUTS  # noqa: E402
from signal_detector import english_share  # noqa: E402

CACHE = OUTPUTS / "models" / "seller_context.pkl"

# Summary flags. "Existing Engagement / Past Experience" mixes "already working with an
# executive" and "bad experience" (playbook note), so the summary text decides which.
SUMMARY_FLAGS = {
    "complaint": re.compile(r"complain|dissatisf|unhappy|not (getting|receiving) (any )?(inquir|enquir|lead|buyer)|no (inquir|enquir|lead)s?|"
                            r"money|refund|fraud|scam|cheat|wasted|bad experience|poor (service|experience)|fake", re.I),
    "exec_present": re.compile(r"(executive|representative|sales person|salesperson)[^.]{0,40}(already|present|visited|in (touch|contact)|"
                               r"has the number|met)|already (in touch|in contact|working) with|already have the executive", re.I),
    "wrong_contact": re.compile(r"wrong number|not the owner|not the (right|correct) person|decision maker|alternate number|"
                                r"another number|not (his|her) business", re.I),
    "callback": re.compile(r"call (back|later)|callback|busy|requested a call", re.I),
    "pricing": re.compile(r"price|pricing|cost|charges|package (cost|price)|how much|fees", re.I),
    "interest": re.compile(r"agreed|interested in|willing|confirmed (a|the) (meeting|visit)|scheduled", re.I),
    "budget": re.compile(r"budget|financial|afford|too expensive|costly", re.I),
}


def build():
    bc = pd.concat([pd.read_csv(f, usecols=["fk_glusr_usr_id", "redis_bucket", "call_start_time", "lead_call_duration",
                                            "lead_call_summary", "disposition_label"], low_memory=False)
                    for f in sorted(glob.glob(str(ROOT / "data" / "ps07_bot_calls_*.csv")))])
    bc["t"] = pd.to_datetime(bc.call_start_time, errors="coerce")
    bc = bc.sort_values("t")
    ctx = {}
    latest = bc.groupby("fk_glusr_usr_id").redis_bucket.last()
    talked = bc[bc.lead_call_duration.fillna(0) >= 20]
    best_hour = talked.groupby("fk_glusr_usr_id").t.agg(lambda s: int(s.dt.hour.mode().iloc[0]) if len(s) else None)
    summaries = bc.dropna(subset=["lead_call_summary"]).groupby("fk_glusr_usr_id").lead_call_summary.agg(
        lambda s: list(s)[-6:])
    for sid, b in latest.items():
        ctx[int(sid)] = {"bucket": b}
    for sid, h in best_hour.items():
        ctx.setdefault(int(sid), {})["best_hour"] = h
    for sid, ss in summaries.items():
        text = " ".join(ss)
        c = ctx.setdefault(int(sid), {})
        c["summaries"] = ss[-3:]
        c["summary_flags"] = sorted(k for k, p in SUMMARY_FLAGS.items() if p.search(text))

    turns = pd.read_csv(ROOT / "data" / "ps07_call_turns.csv")
    st = turns[turns.speaker == "seller"].copy()
    st["words"] = st.text.fillna("").str.split().str.len()
    st["dur"] = (st.end_sec - st.start_sec).clip(lower=0.2)
    for sid, g in st.groupby("fk_glusr_usr_id"):
        c = ctx.setdefault(int(sid), {})
        c["english_share"] = english_share(" ".join(g.text.fillna("")))
        c["own_words"] = int(g.words.sum())
        g2 = g[g.words >= 3]
        if g2.words.sum() >= 10:
            c["seller_wps"] = round(float(g2.words.sum() / g2.dur.sum()), 2)
    bt = turns[turns.speaker == "bot"].copy()
    bt["words"] = bt.text.fillna("").str.split().str.len()
    bt["dur"] = (bt.end_sec - bt.start_sec).clip(lower=0.2)
    pop = {"bot_wps": round(float(bt[bt.words >= 3].words.sum() / bt[bt.words >= 3].dur.sum()), 2),
           "seller_wps": round(float(st[st.words >= 3].words.sum() / st[st.words >= 3].dur.sum()), 2)}

    ex = pd.read_csv(ROOT / "data" / "ps07_executive_calls.csv")
    ans = ex[ex.status == "Answered"].groupby("fk_glusr_usr_id").size()
    for sid, n in ans.items():
        ctx.setdefault(int(sid), {})["exec_calls_answered"] = int(n)

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE, "wb") as f:
        pickle.dump({"sellers": ctx, "population": pop}, f)
    return {"sellers": ctx, "population": pop}


_CTX = None


def load():
    global _CTX
    if _CTX is None:
        if CACHE.exists():
            with open(CACHE, "rb") as f:
                _CTX = pickle.load(f)
        else:
            _CTX = build()
    return _CTX


def get(seller_id: int) -> dict:
    return load()["sellers"].get(int(seller_id), {})


def population() -> dict:
    return load()["population"]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    c = build()
    s = c["sellers"]
    print(f"context for {len(s):,} sellers; population rates {c['population']}")
    from collections import Counter
    print("summary flags:", Counter(f for v in s.values() for f in v.get("summary_flags", [])))
    print("with own turns:", sum("english_share" in v for v in s.values()), "| with best hour:",
          sum("best_hour" in v for v in s.values()), "| exec calls:", sum("exec_calls_answered" in v for v in s.values()))
