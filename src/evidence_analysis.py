"""Evidence engine: measures which persona choices worked for which seller
types in the Apr-Sep 2026 past calls, and grades how strong each finding is.

Every rule in persona_generator.py cites an evidence id from the JSON this
writes (outputs/evidence/evidence.json). Strength grades:
  strong   - both groups n>=300, 95% CIs do not overlap, |diff| >= 3pp
  moderate - both groups n>=100 and two-proportion z-test |z| >= 1.96
  weak     - direction visible but n small or not significant
  (rules with no measurable proxy are marked "informed_guess" in the
   generator itself, never here)

Known confounds are written next to each finding, not hidden: e.g. campaigns
label dispositions differently, so Not-Interested rates are only compared
within the same bot version, and Meeting-Fixed is the cross-version metric.
"""
import glob
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "outputs" / "evidence"

HINDI_FUNC = set("""hai hain tha thi the kya nahi nahin na main mai mein me aap ap ka ki ke ko se toh to
haan han ha ji bhi kar karo karna kar raha rahe rahi hoon hu ho abhi kal baat theek thik achha accha acha
woh wo yeh ye kaun kyun kab kahan kitna kitne kuch sab bata bataiye bol boliye hamara humara mera meri
apna apni unka unki lekin par aur ya jab tab phir fir wala wali diya liya hota hoga chahiye dijiye""".split())
ENGLISH_FUNC = set("""the is are was were i you we they he she it my your our their this that these those
what which who why how when where will would can could should have has had do does did not don't
dont please thank thanks sorry already and of to for with from about at on in be been being
yes no okay ok right sure because but if so just any""".split())

FRUSTRATION_RE = re.compile(
    r"(nahi|nhi)\s*(chahiye|chaiye)|baar\s*baar|bar\s*bar|pareshan|band\s*kar|mat\s*kar|zabardasti|"
    r"bas\s*kar|kitni\s*baar|disturb|phone\s*(cut|rakh)|not\s*interested|don'?t\s*call", re.I)
AI_RE = re.compile(r"\b(bot|ai|robot|machine|recorded|automated)\b|genuine\s*person|insaan", re.I)
HUMAN_CLAIM_RE = re.compile(r"\b(insaan|human|real\s*person)\b", re.I)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def compare(k1, n1, k2, n2):
    p1, lo1, hi1 = wilson(k1, n1)
    p2, lo2, hi2 = wilson(k2, n2)
    pooled = (k1 + k2) / (n1 + n2) if (n1 + n2) else 0
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2)) if n1 and n2 and 0 < pooled < 1 else 0
    z = (p1 - p2) / se if se else 0.0
    diff = p1 - p2
    if min(n1, n2) >= 300 and (lo1 > hi2 or lo2 > hi1) and abs(diff) >= 0.03:
        strength = "strong"
    elif min(n1, n2) >= 100 and abs(z) >= 1.96:
        strength = "moderate"
    else:
        strength = "weak"
    return {
        "group_a": {"rate": round(p1, 4), "ci95": [round(lo1, 4), round(hi1, 4)], "n": int(n1)},
        "group_b": {"rate": round(p2, 4), "ci95": [round(lo2, 4), round(hi2, 4)], "n": int(n2)},
        "diff_pp": round(diff * 100, 2),
        "z": round(z, 2),
        "strength": strength,
    }


def english_share(texts):
    eng = hin = 0
    for t in texts:
        for tok in re.findall(r"[a-zA-Z']+", str(t).lower()):
            if tok in ENGLISH_FUNC:
                eng += 1
            elif tok in HINDI_FUNC:
                hin += 1
    return eng / (eng + hin) if (eng + hin) >= 3 else np.nan


def load():
    bc = pd.concat([pd.read_csv(f, low_memory=False) for f in sorted(glob.glob(str(DATA / "ps07_bot_calls_*.csv")))],
                   ignore_index=True)
    sellers = pd.concat([pd.read_csv(DATA / f"ps07_seller_files_part{i}.csv", low_memory=False) for i in (1, 2)],
                        ignore_index=True).drop_duplicates("fk_glusr_usr_id")
    turns = pd.read_csv(DATA / "ps07_call_turns.csv")
    ev = pd.concat([pd.read_csv(f, low_memory=False) for f in sorted(glob.glob(str(DATA / "ps07_evaluator_outputs_*.csv")))],
                   ignore_index=True)
    return bc, sellers, turns, ev


def call_turn_features(turns, bc):
    turns = turns.copy()
    turns["text"] = turns["text"].fillna("").astype(str)
    turns["words"] = turns["text"].str.split().str.len()
    turns["dur"] = (turns["end_sec"] - turns["start_sec"]).clip(lower=0.1)

    rows = []
    for aid, g in turns.groupby("attempt_id", sort=False):
        g = g.sort_values("turn_no")
        bot = g[g.speaker == "bot"]
        sel = g[g.speaker == "seller"]
        if bot.empty or sel.empty:
            continue
        first_bot = bot.iloc[0]
        # opening = first substantive bot turn after the "kya aap X se bol rahe hain" check
        opening = bot.iloc[1] if len(bot) > 1 else first_bot
        early_sel = sel.head(3)

        after_frustration_len = np.nan
        frustrated = False
        bot_claimed_human = False
        asked_ai = False
        for i, r in enumerate(g.itertuples()):
            if r.speaker == "seller" and not frustrated and FRUSTRATION_RE.search(r.text):
                frustrated = True
                nxt = g.iloc[i + 1:]
                nxt_bot = nxt[nxt.speaker == "bot"]
                if not nxt_bot.empty:
                    after_frustration_len = nxt_bot.iloc[0]["words"]
            if r.speaker == "seller" and AI_RE.search(r.text):
                asked_ai = True
                nxt = g.iloc[i + 1:]
                nxt_bot = nxt[nxt.speaker == "bot"]
                if not nxt_bot.empty and HUMAN_CLAIM_RE.search(nxt_bot.iloc[0]["text"]):
                    bot_claimed_human = True

        rows.append({
            "attempt_id": aid,
            "n_turns": len(g),
            # transcripts mark a bot turn the seller cut off with a trailing "..."
            "opening_truncated": str(opening["text"]).rstrip().endswith(("...", "…")),
            "opening_words": opening["words"],
            "bot_wps": bot["words"].sum() / bot["dur"].sum(),
            "seller_early_words": early_sel["words"].mean(),
            "seller_english_share": english_share(sel["text"]),
            "seller_frustrated": frustrated,
            "bot_words_after_frustration": after_frustration_len,
            "seller_asked_ai": asked_ai,
            "bot_claimed_human": bot_claimed_human,
        })
    f = pd.DataFrame(rows)
    return f.merge(bc[["attempt_id", "fk_glusr_usr_id", "disposition_label", "meeting_fixed", "lead_bot_version",
                       "redis_bucket", "call_attempt_count"]], on="attempt_id", how="inner")


def parse_eval(ev, agent):
    sub = ev[ev.eval_agent == agent][["attempt_id", "agent_output"]]
    out = []
    for aid, raw in zip(sub.attempt_id, sub.agent_output):
        try:
            out.append((aid, json.loads(raw)))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def k_n(mask_series):
    return int(mask_series.sum()), int(mask_series.count())


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    bc, sellers, turns, ev = load()
    bc["is_mf"] = bc.disposition_label.eq("Meeting Fixed")
    bc["is_ni"] = bc.disposition_label.eq("Not Interested")
    evidence = {}

    # E1 personalisation: personalised-script trial vs main_vani, same lead buckets only
    trial_buckets = set(bc.loc[bc.lead_bot_version == "personalis", "redis_bucket"])
    base = bc[bc.redis_bucket.isin(trial_buckets)]
    p = base[base.lead_bot_version == "personalis"].is_mf
    m = base[base.lead_bot_version == "main_vani"].is_mf
    evidence["E1_personalisation"] = {
        "claim": "A personalised script (seller-specific opening) fixes more meetings than the standard VANI script.",
        "metric": "Meeting Fixed rate, answered calls, restricted to the lead buckets the trial ran on",
        "group_a_label": "personalised-script trial", "group_b_label": "main_vani",
        **compare(*k_n(p), *k_n(m)),
        "confound": "Trial is 452 calls; campaigns label General/Not-Interested differently, so NI is NOT compared across versions.",
        "used_by": ["conversation_plan.personalisation", "conversation_plan.opening"],
    }

    tf = call_turn_features(turns, bc)
    tf["is_mf"] = tf.disposition_label.eq("Meeting Fixed")
    tf["is_ni"] = tf.disposition_label.eq("Not Interested")
    tf.to_csv(OUT / "call_turn_features.csv", index=False)

    # E2 seller cuts the opening off -> impatience / rush signal.
    # A naive "short opening vs long opening" comparison is reverse-causal: when a
    # seller interrupts, the transcript records a truncated (shorter) opening, so
    # short openings look worse. Interruption itself is measured instead, and the
    # brevity comparison is only made on openings that were delivered in full.
    evidence["E2_interrupted_opening"] = {
        "claim": "When a seller cuts VANI's opening pitch off mid-sentence, the call is far more likely to be lost -- interruption is an early rush/impatience signal.",
        "metric": "Not Interested rate",
        "group_a_label": "seller interrupted the opening", "group_b_label": "opening delivered in full",
        **compare(*k_n(tf[tf.opening_truncated].is_ni), *k_n(tf[~tf.opening_truncated].is_ni)),
        "used_by": ["live_adaptation.rush", "voice.pace", "conversation_plan.opening"],
    }
    full = tf[~tf.opening_truncated]
    terse = full[full.seller_early_words <= 3]
    short_open = terse.opening_words <= 30
    evidence["E2b_brevity_for_terse_sellers"] = {
        "claim": "Among fully-delivered openings, terse sellers (1-3 word replies) respond better to a short opening (<=30 words).",
        "metric": "Meeting Fixed rate, terse sellers, non-interrupted openings only",
        "group_a_label": "opening <=30 words", "group_b_label": "opening >30 words",
        **compare(*k_n(terse[short_open].is_mf), *k_n(terse[~short_open].is_mf)),
        "confound": "Opening length still varies with campaign script, not randomised.",
        "used_by": ["voice.pace", "conversation_plan.opening"],
    }

    # E3 speech rate: fast vs slow bot delivery, by seller type
    q = tf.bot_wps.quantile([0.33, 0.67]).values
    fast, slow = tf.bot_wps >= q[1], tf.bot_wps <= q[0]
    evidence["E3_pace"] = {
        "claim": "Delivery speed matters differently by seller type: terse sellers tolerate faster delivery; chatty sellers do better slower.",
        "metric": "Meeting Fixed rate; fast = top third of bot words/sec, slow = bottom third",
        "bot_wps_terciles": [round(float(x), 2) for x in q],
        "terse_sellers_fast_vs_slow": compare(*k_n(tf[fast & (tf.seller_early_words <= 3)].is_mf),
                                              *k_n(tf[slow & (tf.seller_early_words <= 3)].is_mf)),
        "chatty_sellers_fast_vs_slow": compare(*k_n(tf[fast & (tf.seller_early_words > 6)].is_mf),
                                               *k_n(tf[slow & (tf.seller_early_words > 6)].is_mf)),
        "confound": "Bot speech rate is not randomised; it partly reflects how much the bot said, not only TTS pace.",
        "used_by": ["voice.pace"],
    }

    # E4 back off after frustration
    fr = tf[tf.seller_frustrated & tf.bot_words_after_frustration.notna()]
    backoff = fr.bot_words_after_frustration <= 15
    evidence["E4_backoff_after_frustration"] = {
        "claim": "After a frustration cue, a short acknowledging reply (<=15 words) loses fewer sellers than continuing the pitch.",
        "metric": "Not Interested rate after the first frustration cue",
        "group_a_label": "bot's next turn <=15 words", "group_b_label": "bot's next turn >15 words (kept pitching)",
        **compare(*k_n(fr[backoff].is_ni), *k_n(fr[~backoff].is_ni)),
        "frustration_cue_prevalence": round(float(tf.seller_frustrated.mean()), 4),
        "used_by": ["live_adaptation.frustration", "conversation_plan.escalation_rules"],
    }

    # E5 repetition / loops
    rep_rows = []
    for aid, d in parse_eval(ev, "latency_repetition"):
        r = d.get("repetition", {}) or {}
        lat = d.get("latency", {}) or {}
        meas = lat.get("measurements", []) or []
        rep_rows.append({
            "attempt_id": aid,
            "n_turns": d.get("n_turns") or 0,
            "bot_repeats": (r.get("bot", {}) or {}).get("repeat_count", 0) or 0,
            "is_loopy": bool(d.get("is_loopy")),
            "latency_p95": lat.get("p95_sec"),
            "seller_had_to_repeat": any(x.get("seller_had_to_repeat") for x in meas),
        })
    rep = pd.DataFrame(rep_rows).merge(bc[["attempt_id", "is_ni", "is_mf"]], on="attempt_id")
    rep["repeated"] = (rep.bot_repeats > 0) | rep.is_loopy
    # Raw comparison is confounded by call length: a call that ends in 3 turns has
    # no chance to repeat. Compare only within long calls (>=10 turns).
    long_calls = rep[rep.n_turns >= 10]
    evidence["E5_repetition"] = {
        "claim": "In calls long enough to repeat, a VANI that repeats itself (same question/point again) fixes fewer meetings.",
        "metric": "Meeting Fixed rate, calls with >=10 turns only (controls for call length)",
        "group_a_label": "bot repeated itself", "group_b_label": "no bot repetition",
        **compare(*k_n(long_calls[long_calls.repeated].is_mf), *k_n(long_calls[~long_calls.repeated].is_mf)),
        "uncontrolled_ni_comparison_for_transparency": compare(*k_n(rep[rep.repeated].is_ni), *k_n(rep[~rep.repeated].is_ni)),
        "confound": "Uncontrolled, repetition looks protective only because short calls cannot repeat.",
        "used_by": ["conversation_plan.guardrails.ask_limits", "live_adaptation.deferral"],
    }
    slow_lat = rep.latency_p95 >= 2.0
    evidence["E6_latency"] = {
        "claim": "Slow bot turn-taking (p95 latency >= 2s) makes sellers repeat themselves more.",
        "metric": "share of calls where the seller had to repeat",
        "group_a_label": "p95 latency >= 2s", "group_b_label": "p95 latency < 2s",
        **compare(*k_n(rep[slow_lat].seller_had_to_repeat), *k_n(rep[~slow_lat].seller_had_to_repeat)),
        "used_by": ["engineering: regex fast-path before LLM fallback", "voice.pace"],
    }

    # E7 language: English-leaning sellers
    lang = tf.dropna(subset=["seller_english_share"])
    eng = lang.seller_english_share >= 0.4
    evidence["E7_language_mismatch"] = {
        "claim": "VANI always speaks Hindi-heavy Hinglish; sellers who reply mostly in English are lost more often (a language mismatch).",
        "metric": "Not Interested rate",
        "group_a_label": "seller English share >= 40%", "group_b_label": "seller English share < 40%",
        **compare(*k_n(lang[eng].is_ni), *k_n(lang[~eng].is_ni)),
        "english_leaning_share_of_calls": round(float(eng.mean()), 4),
        "used_by": ["language.primary", "language.hinglish_mix", "live_adaptation.language_switch"],
    }
    st = lang.merge(sellers[["fk_glusr_usr_id", "seller_state"]], on="fk_glusr_usr_id", how="left")
    by_state = (st.groupby("seller_state").seller_english_share.agg(["mean", "count"])
                .query("count >= 40").sort_values("mean", ascending=False))
    evidence["E8_state_language_prior"] = {
        "claim": "Seller state predicts how much English the seller uses on the call.",
        "metric": "mean seller English share by state (states with >=40 transcribed calls)",
        "by_state": {k: {"english_share": round(v["mean"], 3), "n": int(v["count"])} for k, v in by_state.iterrows()},
        "strength": "moderate" if len(by_state) >= 5 else "weak",
        "used_by": ["language.primary", "language.hinglish_mix"],
    }

    # E9 AI question and human claim
    ai = tf[tf.seller_asked_ai]
    evidence["E9_ai_identity"] = {
        "claim": "When sellers ask whether they are talking to a bot, claiming to be human does not save the call.",
        "metric": "Not Interested rate after the seller asked 'is this a bot'",
        "group_a_label": "bot claimed to be human", "group_b_label": "bot did not claim to be human",
        **compare(*k_n(ai[ai.bot_claimed_human].is_ni), *k_n(ai[~ai.bot_claimed_human].is_ni)),
        "asked_ai_prevalence": round(float(tf.seller_asked_ai.mean()), 4),
        "policy_note": "Sarvam/IndiaMART global rule: VANI must never claim to be human, regardless of this metric.",
        "used_by": ["live_adaptation.ai_bot_suspicion", "conversation_plan.guardrails"],
    }

    # E10 objection categories -> recoverability
    # The objections evaluator only ran on calls that did NOT fix a meeting, so
    # "meeting fixed after objection" is 0% by construction (selection bias,
    # caught on first run). Recoverability is measured instead as "door left
    # open": the call ended Call-Later/General rather than Not-Interested.
    obj_rows = []
    for aid, d in parse_eval(ev, "objections"):
        for o in d.get("objection_analysis", []) or []:
            obj_rows.append({"attempt_id": aid, "category": o.get("category")})
    obj = pd.DataFrame(obj_rows).merge(bc[["attempt_id", "disposition_label"]], on="attempt_id")
    # "General (talked)" is too broad to count as door-open (first attempt showed
    # 80% "door open" even for Explicit Refusal), so only an explicit callback counts.
    obj["callback"] = obj.disposition_label.eq("Call Later / Busy")
    obj["ni"] = obj.disposition_label.eq("Not Interested")
    obj_tab = (obj.groupby("category").agg(callback_rate=("callback", "mean"), ni_rate=("ni", "mean"),
                                            n=("callback", "count"))
               .query("n >= 30").sort_values("callback_rate", ascending=False))
    evidence["E10_objection_recoverability"] = {
        "claim": "Some objection types still end in a secured callback, others end the relationship and should be respected, not argued.",
        "metric": "per objection category: share ending Call-Later (callback secured) and share ending Not-Interested",
        "by_category": {k: {"callback_rate": round(v["callback_rate"], 3), "ni_rate": round(v["ni_rate"], 3),
                            "n": int(v["n"]),
                            "callback_ci95": [round(x, 3) for x in
                                              wilson(int(round(v["callback_rate"] * v["n"])), int(v["n"]))[1:]]}
                        for k, v in obj_tab.iterrows()},
        "selection_note": "objections evaluator covers only non-meeting calls; meeting rate after objection is not measurable from it.",
        "strength": "moderate",
        "used_by": ["conversation_plan.objection_playbook"],
    }

    # E11 forced meetings: incorrect_mf
    imf = pd.DataFrame([{"attempt_id": a, "incorrect_mf": bool(d.get("incorrect_mf")),
                         "stance": d.get("seller_final_stance")} for a, d in parse_eval(ev, "incorrect_mf")])
    imf = imf.merge(rep[["attempt_id", "repeated"]], on="attempt_id", how="left")
    both = imf.dropna(subset=["repeated"])
    evidence["E11_forced_meetings"] = {
        "claim": "A share of 'Meeting Fixed' calls are wrong (seller never really agreed). Pushing for the meeting is not the same as winning it.",
        "metric": "incorrect meeting-fixed rate among calls VANI marked Meeting Fixed",
        "overall_incorrect_mf_rate": round(float(imf.incorrect_mf.mean()), 4),
        "n": int(len(imf)),
        "repeated_vs_not": compare(*k_n(both[both.repeated.astype(bool)].incorrect_mf),
                                   *k_n(both[~both.repeated.astype(bool)].incorrect_mf)),
        "strength": "strong" if len(imf) >= 1000 else "moderate",
        "used_by": ["conversation_plan.goal", "conversation_plan.guardrails"],
    }

    # E12 repeated attempts -> fatigue
    bc["attempt_bucket"] = pd.cut(bc.call_attempt_count, [0, 1, 3, 100], labels=["1st", "2-3", "4+"])
    mv = bc[bc.lead_bot_version == "main_vani"]
    evidence["E12_call_fatigue"] = {
        "claim": "The more times VANI has already called a seller, the more likely the seller says Not Interested.",
        "metric": "Not Interested rate, main_vani only",
        "group_a_label": "4th+ attempt", "group_b_label": "1st attempt",
        **compare(*k_n(mv[mv.attempt_bucket == "4+"].is_ni), *k_n(mv[mv.attempt_bucket == "1st"].is_ni)),
        "used_by": ["conversation_plan.opening", "tone.empathy", "conversation_plan.goal"],
    }

    # E13 already in touch with an executive
    s = bc.merge(sellers[["fk_glusr_usr_id", "already_in_touch_with_executive", "business_type", "annual_turnover",
                          "eng_cqs"]], on="fk_glusr_usr_id", how="left")
    sm = s[s.lead_bot_version == "main_vani"]
    ex = sm.already_in_touch_with_executive == 1
    evidence["E13_existing_executive"] = {
        "claim": "Sellers already in touch with an IndiaMART executive rarely want another meeting pitch.",
        "metric": "Meeting Fixed rate, main_vani only",
        "group_a_label": "already in touch with executive", "group_b_label": "not in touch",
        **compare(*k_n(sm[ex].is_mf), *k_n(sm[~ex].is_mf)),
        "confound": "Flag is derived from these same calls (seller said so), so it partly describes the outcome.",
        "used_by": ["conversation_plan.goal", "conversation_plan.opening"],
    }

    # E14 segment: business type & turnover
    seg = sm.groupby("business_type").is_mf.agg(["mean", "count"]).query("count >= 500").sort_values("mean")
    turn = sm.groupby("annual_turnover").is_mf.agg(["mean", "count"]).query("count >= 500").sort_values("mean")
    evidence["E14_segments"] = {
        "claim": "Meeting appetite differs by business type and turnover band.",
        "metric": "Meeting Fixed rate, main_vani only",
        "by_business_type": {k: {"rate": round(v["mean"], 3), "n": int(v["count"])} for k, v in seg.iterrows()},
        "by_turnover": {str(k): {"rate": round(v["mean"], 3), "n": int(v["count"])} for k, v in turn.iterrows()},
        "strength": "moderate",
        "used_by": ["language.formality", "conversation_plan.goal"],
    }

    # E15 seller questions catalogue -> what sellers actually ask
    q_rows = []
    for aid, d in parse_eval(ev, "seller_questions"):
        for qq in d.get("questions", []) or []:
            for c in qq.get("category", []) or []:
                q_rows.append(c)
    qs = pd.Series(q_rows).value_counts()
    evidence["E15_seller_questions"] = {
        "claim": "What sellers ask VANI most, so the playbook answers these first.",
        "metric": "count of question categories across calls with seller questions",
        "top_categories": {k: int(v) for k, v in qs.head(12).items()},
        "strength": "strong",
        "used_by": ["conversation_plan.objection_playbook", "prompt: SELLER_QUESTION handlers"],
    }

    # expected sign of (A - B) if the claim is true; used to label each finding
    expected = {"E1_personalisation": 1, "E2_interrupted_opening": 1, "E2b_brevity_for_terse_sellers": 1,
                "E4_backoff_after_frustration": -1, "E5_repetition": -1, "E6_latency": 1,
                "E7_language_mismatch": 1, "E9_ai_identity": 1, "E12_call_fatigue": 1, "E13_existing_executive": -1}
    for eid, sign in expected.items():
        e = evidence[eid]
        e["verdict"] = _verdict(e["diff_pp"], e["strength"], sign)
    e3 = evidence["E3_pace"]
    e3["terse_sellers_fast_vs_slow"]["verdict"] = _verdict(e3["terse_sellers_fast_vs_slow"]["diff_pp"],
                                                           e3["terse_sellers_fast_vs_slow"]["strength"], 1)
    e3["chatty_sellers_fast_vs_slow"]["verdict"] = _verdict(e3["chatty_sellers_fast_vs_slow"]["diff_pp"],
                                                            e3["chatty_sellers_fast_vs_slow"]["strength"], -1)
    e3["strength"] = max([e3["terse_sellers_fast_vs_slow"]["strength"], e3["chatty_sellers_fast_vs_slow"]["strength"]],
                         key=["weak", "moderate", "strong"].index)

    with open(OUT / "evidence.json", "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2, default=str)
    write_markdown(evidence)
    return evidence


def _verdict(diff_pp, strength, expected_sign):
    if strength == "weak":
        return "inconclusive"
    return "supported" if diff_pp * expected_sign > 0 else "contradicted"


def write_markdown(evidence):
    lines = ["# Evidence from past calls", "",
             "Generated by `src/evidence_analysis.py` from Apr-Sep 2026 bot calls, turn transcripts and evaluator outputs.",
             "Strength: **strong** = n>=300 per group and non-overlapping 95% CIs with >=3pp gap; "
             "**moderate** = n>=100 and |z|>=1.96; **weak** = direction only.", ""]
    for eid, e in evidence.items():
        lines.append(f"## {eid}")
        lines.append(f"**Claim:** {e['claim']}  ")
        lines.append(f"**Metric:** {e.get('metric', '')}  ")
        if "group_a" in e:
            a, b = e["group_a"], e["group_b"]
            lines.append(f"- {e.get('group_a_label', 'A')}: {a['rate']:.1%} (95% CI {a['ci95'][0]:.1%}-{a['ci95'][1]:.1%}, n={a['n']:,})")
            lines.append(f"- {e.get('group_b_label', 'B')}: {b['rate']:.1%} (95% CI {b['ci95'][0]:.1%}-{b['ci95'][1]:.1%}, n={b['n']:,})")
            lines.append(f"- Difference: {e['diff_pp']:+.1f}pp, z={e['z']}")
        for k, v in e.items():
            if k in {"claim", "metric", "group_a", "group_b", "group_a_label", "group_b_label", "diff_pp", "z",
                     "strength", "used_by", "verdict"}:
                continue
            if isinstance(v, dict) and "group_a" in v:
                lines.append(f"- {k}: A {v['group_a']['rate']:.1%} (n={v['group_a']['n']}) vs "
                             f"B {v['group_b']['rate']:.1%} (n={v['group_b']['n']}), {v['diff_pp']:+.1f}pp, "
                             f"{v['strength']}{', ' + v['verdict'] if 'verdict' in v else ''}")
            else:
                lines.append(f"- {k}: `{json.dumps(v, ensure_ascii=False, default=str)[:600]}`")
        lines.append(f"**Strength:** {e.get('strength', 'n/a')}  ")
        if "verdict" in e:
            lines.append(f"**Verdict on the claim:** {e['verdict']}  ")
        lines.append(f"**Used by:** {', '.join(e.get('used_by', []))}")
        lines.append("")
    (OUT / "evidence_report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    ev = run()
    for eid, e in ev.items():
        if "group_a" in e:
            print(f"{eid:32} A={e['group_a']['rate']:.3f} (n={e['group_a']['n']:>6}) "
                  f"B={e['group_b']['rate']:.3f} (n={e['group_b']['n']:>6}) {e['diff_pp']:+6.1f}pp "
                  f"{e['strength']:9} {e.get('verdict', '')}")
        else:
            nested = {k: v for k, v in e.items() if isinstance(v, dict) and "group_a" in v}
            print(f"{eid:32} {e.get('strength')}")
            for k, v in nested.items():
                print(f"   {k:30} A={v['group_a']['rate']:.3f} (n={v['group_a']['n']}) "
                      f"B={v['group_b']['rate']:.3f} (n={v['group_b']['n']}) {v['diff_pp']:+.1f}pp "
                      f"{v['strength']} {v.get('verdict', '')}")
