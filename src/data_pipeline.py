"""Loads and assembles the seller-persona input table from the PS4 dataset.

The seller file (ps07_seller_files_part1/2.csv) is already the documented
"seller persona input" -- profile, engagement history and aggregated bot-call
outcomes per seller. This module just stacks the parts, fixes dtypes, and
exposes small lookup helpers used by the rest of the pipeline.
"""
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_MIXED_TYPE_COLS = ["past_objections", "past_questions_asked", "past_dispositions_detailed"]


def load_seller_master() -> pd.DataFrame:
    parts = [
        pd.read_csv(DATA_DIR / "ps07_seller_files_part1.csv", low_memory=False),
        pd.read_csv(DATA_DIR / "ps07_seller_files_part2.csv", low_memory=False),
    ]
    df = pd.concat(parts, ignore_index=True)
    for col in _MIXED_TYPE_COLS:
        df[col] = df[col].astype("string")
    df = df.drop_duplicates(subset="fk_glusr_usr_id", keep="first")
    # company names come from IndiaMART separately (not in the seller files): data/company_names.csv with
    # columns seller_id,company_name. The master opening confirms the company before giving the context.
    names = DATA_DIR / "company_names.csv"
    if names.exists():
        cn = pd.read_csv(names, dtype={"company_name": "string"}).rename(columns={"seller_id": "fk_glusr_usr_id"})
        df = df.merge(cn[["fk_glusr_usr_id", "company_name"]], on="fk_glusr_usr_id", how="left")
    return df


def get_seller(df: pd.DataFrame, fk_glusr_usr_id: int) -> dict:
    row = df.loc[df.fk_glusr_usr_id == fk_glusr_usr_id]
    if row.empty:
        raise KeyError(f"seller {fk_glusr_usr_id} not found")
    return row.iloc[0].to_dict()


def load_call_turns(attempt_ids=None) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "ps07_call_turns.csv")
    if attempt_ids is not None:
        df = df[df.attempt_id.isin(attempt_ids)]
    return df.sort_values(["attempt_id", "turn_no"])


if __name__ == "__main__":
    sellers = load_seller_master()
    print(f"loaded {len(sellers):,} sellers, {sellers.shape[1]} columns")
    print("do_not_call sellers:", int(sellers.do_not_call_requested.sum()))
    print("already_in_touch sellers:", int(sellers.already_in_touch_with_executive.sum()))
