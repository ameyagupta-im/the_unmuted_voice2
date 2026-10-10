"""IndiaMART's master prompt for any chat or voice AI: the master text (with its own section-9 JSON output), the
additions, and a filled SELLER CONTEXT block for one seller. Fields our data does not have (alt_number_last_digits,
area_enquiry_count, similar_sellers; company_name until IndiaMART supplies data/company_names.csv) are left out.

  python src/export_master_prompt.py 3419775 [1243794 ...]  -> outputs/master_prompt/<seller_id>.txt
"""
import sys

from config import OUTPUTS
from data_pipeline import load_seller_master
from master_prompt import additions, context_block, master_text
from persona_generator import generate_persona

OUT = OUTPUTS / "master_prompt"


def render(row) -> str:
    p = generate_persona(row).to_dict()
    if p["blocked"]:
        return "SELLER CONTEXT\ndo_not_call: yes\n(say only the DO_NOT_CALL closing.)"
    return f"{master_text()}\n\n{additions()}\n\n{context_block(p['conversation_plan']['seller_context'])}\n"


def main(ids):
    OUT.mkdir(parents=True, exist_ok=True)
    sellers = load_seller_master()
    for sid in ids:
        row = sellers.loc[sellers.fk_glusr_usr_id == sid].iloc[0].to_dict()
        (OUT / f"{sid}.txt").write_text(render(row), encoding="utf-8")
        print(f"{sid}: outputs/master_prompt/{sid}.txt")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main([int(x) for x in sys.argv[1:]] or [3419775, 1243794, 56768582])
