import pandas as pd

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 50)

seller = pd.concat(
    [pd.read_csv("data/ps07_seller_files_part1.csv"), pd.read_csv("data/ps07_seller_files_part2.csv")],
    ignore_index=True,
)
print("=== seller_files ===", seller.shape)
print(seller.columns.tolist())
print(seller[["showed_frustration", "asked_if_talking_to_bot", "do_not_call_requested", "already_in_touch_with_executive"]].mean())
print(seller["bot_answer_rate"].describe())
print("---sample past_objections---")
print(seller["past_objections"].dropna().sample(5, random_state=1).tolist())
print("---sample past_questions_asked---")
print(seller["past_questions_asked"].dropna().sample(5, random_state=1).tolist())

rec = pd.read_csv("data/ps07_recording_sample_5000.csv")
print("\n=== recording_sample ===", rec.shape)
print(rec.columns.tolist())
print(rec["disposition_label"].value_counts())
print(rec["lead_bot_version"].value_counts())
print(rec[["call_recording_url"]].dropna().head(3))

turns = pd.read_csv("data/ps07_call_turns.csv", nrows=200000)
print("\n=== call_turns (sample read) ===", turns.shape)
print(turns.columns.tolist())
print(turns.head(10))
