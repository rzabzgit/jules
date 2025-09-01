
# -*- coding: utf-8 -*-
import argparse, os, json, csv
from typing import List, Dict, Any
from parser_v2 import parse_signal

BOUNDARY = "%%--SIGNAL_BOUNDARY--%%"

def split_blocks(txt: str) -> List[str]:
    if BOUNDARY in txt:
        parts = [p.strip() for p in txt.split(BOUNDARY)]
        return [p for p in parts if p]
    # fallback: split on blank lines with numbers in them
    parts = [p.strip() for p in txt.split("\n\n")]
    return [p for p in parts if any(ch.isdigit() for ch in p) and len(p)>20]

def load_blocks(paths: List[str]) -> List[str]:
    blocks: List[str] = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            blocks.extend(split_blocks(f.read()))
    return blocks

def as_row(i: int, block: str, parsed: Dict[str, Any] | None) -> Dict[str, Any]:
    base: Dict[str, Any] = {"idx": i, "raw_len": len(block)}
    if not parsed:
        base.update({"pair":"", "direction":"", "entries":[], "entry_avg":None,
                     "targets":[], "stop_loss":None, "stop_loss_percent":None,
                     "rr_first_target": None, "warnings": ["PARSE_FAILED"], "skipped": False})
        return base
    # flatten lists for CSV readability
    row = {
        "idx": i,
        "pair": parsed.get("pair"),
        "direction": parsed.get("direction"),
        "entries": parsed.get("entries", []),
        "entry_avg": parsed.get("entry_avg"),
        "targets": parsed.get("targets", []),
        "stop_loss": parsed.get("stop_loss"),
        "stop_loss_percent": parsed.get("stop_loss_percent"),
        "rr_first_target": parsed.get("rr_first_target"),
        "skipped": parsed.get("skipped", False),
        "warnings": parsed.get("warnings", []),
    }
    return row

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", nargs="+", required=True, help="Input signal text files")
    ap.add_argument("--outdir", default=None, help="Output directory (default: alongside first input)")
    args = ap.parse_args()

    blocks = load_blocks(args.input)
    rows: List[Dict[str, Any]] = []
    for i, b in enumerate(blocks, 1):
        try:
            parsed = parse_signal(b)
        except Exception as e:
            parsed = None
        rows.append(as_row(i, b, parsed))

    outdir = args.outdir or os.path.dirname(os.path.abspath(args.input[0]))
    os.makedirs(outdir, exist_ok=True)
    csv_path = os.path.join(outdir, "parsed_signals_v2.csv")
    jsonl_path = os.path.join(outdir, "parsed_signals_v2.jsonl")

    # CSV
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        cols = ["idx","pair","direction","entries","entry_avg","targets","stop_loss",
                "stop_loss_percent","rr_first_target","skipped","warnings"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            row = {k: r.get(k) for k in cols}
            # lists as JSON strings for readability
            for k in ("entries","targets","warnings"):
                if isinstance(row.get(k), (list, tuple)):
                    row[k] = json.dumps(row[k], ensure_ascii=False)
            w.writerow(row)

    # JSONL
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} rows")
    print("CSV:", csv_path)
    print("JSONL:", jsonl_path)

if __name__ == "__main__":
    main()
