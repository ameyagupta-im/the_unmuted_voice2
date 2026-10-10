"""Persona generator CLI: seller file in -> one persona spec per seller out.

  python src/generate_personas.py                         # stratified sample of the provided seller files
  python src/generate_personas.py --input my_sellers.csv  # any CSV with the ps07_seller_files columns
  python src/generate_personas.py --all --summary-only    # every seller, summary CSV only

Writes outputs/persona_specs/<seller_id>.json and .md, index.csv, and
distinctness.md, which measures how different the personas are across seller
types (a judged criterion), instead of asserting it.
"""
import argparse
import itertools
import json
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUTPUTS  # noqa: E402
from data_pipeline import load_seller_master  # noqa: E402
from persona_generator import generate_persona, persona_to_markdown  # noqa: E402

DEMO_IDS = [3419775, 1243794, 56768582, 2890493, 113839910, 19070168, 42896003, 263553634, 269277443]
CATEGORICAL = ["goal", "language", "formality", "gender", "style", "speaker"]
NUMERIC = ["pace", "warmth", "empathy", "assertiveness", "max_words"]


def flat(p) -> dict:
    if p.blocked:
        return {"seller_id": p.seller_id, "seller_type": p.seller_type_label, "blocked": True}
    return {
        "seller_id": p.seller_id, "seller_type": p.seller_type_label, "blocked": False,
        "goal": p.goal.value, "fallbacks": ";".join(p.fallback_goals), "language": p.language["primary"].value,
        "formality": p.language["formality"].value, "english_share": p.language["english_share"].value,
        "gender": p.voice["gender"].value, "bot_name": p.voice["bot_name"].value, "style": p.voice["style"].value,
        "speaker": p.voice["speaker"].value, "pace": p.voice["pace"].value, "warmth": p.tone["warmth"].value,
        "empathy": p.tone["empathy"].value, "assertiveness": p.tone["assertiveness"].value,
        "max_words": p.tone["max_words"].value, "callback_slot": p.conversation_plan["callback_slot"].value,
        "low_confidence_fields": sum(1 for sec in (p.voice, p.language, p.tone) for f in sec.values() if f.confidence == "low"),
        "missing_fields": ";".join(p.missing_fields),
        "opening": p.conversation_plan["opening"].value,
    }


def distance(a: dict, b: dict) -> float:
    """0 = identical persona, 1 = different on every setting (categorical mismatch, numeric range-normalised)."""
    cat = sum(a[k] != b[k] for k in CATEGORICAL) / len(CATEGORICAL)
    rng = {"pace": 0.3, "warmth": 4, "empathy": 4, "assertiveness": 4, "max_words": 18}
    num = sum(min(1.0, abs(a[k] - b[k]) / rng[k]) for k in NUMERIC) / len(NUMERIC)
    return round(0.6 * cat + 0.4 * num, 3)


def distinctness_report(rows: list) -> str:
    live = [r for r in rows if not r["blocked"]]
    types = sorted({r["seller_type"] for r in live})
    lines = ["# Persona distinctness", "",
             f"{len(live)} personas across {len(types)} seller types. Distance: 0 = identical, 1 = every setting differs "
             f"(60% categorical: {', '.join(CATEGORICAL)}; 40% numeric: {', '.join(NUMERIC)}).", ""]
    within, between = [], []
    for a, b in itertools.combinations(live, 2):
        (within if a["seller_type"] == b["seller_type"] else between).append(distance(a, b))
    if within and between:
        lines.append(f"- Mean distance between personas of DIFFERENT seller types: **{sum(between) / len(between):.2f}**")
        lines.append(f"- Mean distance between personas of the SAME seller type: **{sum(within) / len(within):.2f}**")
        lines.append(f"- Distinct full combinations ({' x '.join(CATEGORICAL)}): "
                     f"**{len({tuple(r[k] for k in CATEGORICAL) for r in live})}**")
    lines += ["", "## Type-level centroid distances", "",
              "| | " + " | ".join(types) + " |", "|---|" + "---|" * len(types)]
    for t1 in types:
        cells = []
        for t2 in types:
            ds = [distance(a, b) for a in live for b in live if a["seller_type"] == t1 and b["seller_type"] == t2
                  and a["seller_id"] != b["seller_id"]]
            cells.append(f"{sum(ds) / len(ds):.2f}" if ds else "-")
        lines.append(f"| {t1} | " + " | ".join(cells) + " |")
    for k in ["goal", "language", "style", "speaker"]:
        lines += ["", f"## {k} by seller type", ""]
        tab = pd.crosstab(pd.Series([r["seller_type"] for r in live], name="type"),
                          pd.Series([r[k] for r in live], name=k))
        lines.append(tab.to_markdown() if hasattr(tab, "to_markdown") else tab.to_string())
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="CSV in ps07_seller_files format (default: the provided seller files)")
    ap.add_argument("--sample-per-type", type=int, default=8)
    ap.add_argument("--all", action="store_true", help="process every seller")
    ap.add_argument("--summary-only", action="store_true", help="write index.csv only, no per-seller files")
    ap.add_argument("--out", default=str(OUTPUTS / "persona_specs"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sellers = pd.read_csv(args.input, low_memory=False) if args.input else load_seller_master()
    t0 = time.time()
    if args.all or args.input:
        chosen = sellers
    else:
        typed = [(generate_persona(r), r) for r in sellers.sample(min(20000, len(sellers)), random_state=11).to_dict("records")]
        per = Counter()
        keep_ids = set(DEMO_IDS)
        for p, r in typed:  # stratify by seller type AND goal, so every goal appears in the sample
            key = (p.seller_type, p.goal.value)
            if per[key] < max(4, args.sample_per_type // 2) and per[p.seller_type] < args.sample_per_type * 2:
                per[key] += 1
                per[p.seller_type] += 1
                keep_ids.add(p.seller_id)
        chosen = sellers[sellers.fk_glusr_usr_id.isin(keep_ids)]

    rows = []
    for r in chosen.to_dict("records"):
        p = generate_persona(r)
        rows.append(flat(p))
        if not args.summary_only:
            (out / f"{p.seller_id}.json").write_text(json.dumps(p.to_dict(), ensure_ascii=False, indent=2, default=str),
                                                    encoding="utf-8")
            (out / f"{p.seller_id}.md").write_text(persona_to_markdown(p), encoding="utf-8")
    elapsed = time.time() - t0
    pd.DataFrame(rows).to_csv(out / "index.csv", index=False, encoding="utf-8")
    if not args.summary_only:
        (out / "distinctness.md").write_text(distinctness_report(rows), encoding="utf-8")
    print(f"{len(rows):,} personas in {elapsed:.1f}s ({len(rows) / max(elapsed, 1e-9):,.0f}/s) -> {out}")
    print(Counter(r["seller_type"] for r in rows))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
