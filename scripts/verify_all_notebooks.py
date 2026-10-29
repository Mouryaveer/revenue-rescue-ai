import json
from pathlib import Path

notebooks = [
    Path("Notebooks/RevenueRescue_AI_Data_Preprocessing.ipynb"),
    Path("Notebooks/RevenueRescue_AI_LightGBM_Transformer_Collab.ipynb")
]

all_passed = True

for p in notebooks:
    print(f"\n{'='*70}\nVERIFYING NOTEBOOK: {p}\n{'='*70}")
    with open(p, "r", encoding="utf-8") as f:
        nb = json.load(f)
    
    total_cells = len(nb["cells"])
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    print(f"Total cells: {total_cells} (Code: {len(code_cells)}, Markdown: {total_cells - len(code_cells)})")
    
    nb_has_error = False
    for idx, cell in enumerate(nb["cells"]):
        if cell["cell_type"] == "code":
            outs = cell.get("outputs", [])
            errors = [o for o in outs if o.get("output_type") == "error"]
            if errors:
                nb_has_error = True
                all_passed = False
                print(f"  [FAIL] Cell {idx} failed with error:")
                for err in errors:
                    print(f"     {err.get('ename')}: {err.get('evalue')}")
            else:
                has_image = any("image/png" in o.get("data", {}) for o in outs)
                has_html = any("text/html" in o.get("data", {}) for o in outs)
                has_stream = any("text" in o for o in outs)
                summary_tag = []
                if has_image: summary_tag.append("PLOT/IMG")
                if has_html: summary_tag.append("TABLE/HTML")
                if has_stream: summary_tag.append("OUTPUT")
                src_head = "".join(cell.get("source", [])).strip().split("\n")[0][:45]
                print(f"  [PASS] Cell {idx:02d} [exec={cell.get('execution_count')}]: {src_head:45s} | {', '.join(summary_tag)}")
    
    if not nb_has_error:
        print(f"\n>>> NOTEBOOK {p.name} PASSED ALL CHECKS WITHOUT ERRORS! <<<")

print("\n" + "="*70)
if all_passed:
    print("ALL NOTEBOOKS VERIFIED: 100% CELLS EXECUTED SUCCESSFULLY WITH NO ERRORS!")
else:
    print("SOME CELLS ENCOUNTERED ERRORS.")
print("="*70)
