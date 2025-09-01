
# -*- coding: utf-8 -*-
"""
Tester v2 (fixed) — generates a readable report with nicer float formatting,
direction sanity notes, and basic coverage metrics.
"""
import argparse, os, json
from typing import List, Dict, Any
from parser_v2 import parse_signal

BOUNDARY = "%%--SIGNAL_BOUNDARY--%%"

def split_blocks(txt: str) -> List[str]:
    if BOUNDARY in txt:
        parts = [p.strip() for p in txt.split(BOUNDARY)]
        return [p for p in parts if p]
    parts = [p.strip() for p in txt.split("\n\n")]
    return [p for p in parts if any(ch.isdigit() for ch in p) and len(p)>20]

def load_blocks(paths: List[str]) -> List[str]:
    blocks: List[str] = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            blocks.extend(split_blocks(f.read()))
    return blocks

def fmt_price(x: Any) -> str:
    if x is None:
        return "None"
    try:
        val = float(x)
    except Exception:
        return str(x)
    # fixed-point, suppress scientific notation; adaptive decimals
    absval = abs(val)
    if absval >= 100000:
        s = f"{val:,.2f}"
    elif absval >= 1:
        s = f"{val:.4f}"
    else:
        s = f"{val:.8f}"
    # strip trailing zeros
    s = s.rstrip('0').rstrip('.') if '.' in s else s
    return s

def list_fmt(xs: List[float]) -> str:
    return "[" + ", ".join(fmt_price(x) for x in xs) + "]"

def evaluate(paths: List[str], out_report: str) -> Dict[str, Any]:
    blocks = load_blocks(paths)
    parsed: List[Dict[str, Any]] = []
    for b in blocks:
        try:
            parsed.append(parse_signal(b))
        except Exception:
            parsed.append(None)

    # Coverage metrics
    total = len(blocks)
    cov = {"pair":0,"direction":0,"entries":0,"targets":0,"stop":0}
    for r in parsed:
        if not r: continue
        if r.get("pair"): cov["pair"] += 1
        if r.get("direction"): cov["direction"] += 1
        if r.get("entries"): cov["entries"] += 1
        if r.get("targets"): cov["targets"] += 1
        if r.get("stop_loss") is not None or r.get("stop_loss_percent") is not None: cov["stop"] += 1

    with open(out_report, "w", encoding="utf-8") as rep:
        rep.write("Crypto Trading Signal Parser — Test Report (v2 fixed)\n")
        rep.write("="*70 + "\n\n")
        for i, (raw, r) in enumerate(zip(blocks, parsed), 1):
            rep.write(f"Signal #{i}\n")
            if not r:
                rep.write("  Parsing failed.\n\n")
                continue
            pair = r.get("pair","")
            direction = r.get("direction","")
            entries = r.get("entries") or []
            entry_avg = r.get("entry_avg")
            targets = r.get("targets") or []
            sl = r.get("stop_loss")
            slp = r.get("stop_loss_percent")
            rr = r.get("rr_first_target")

            rep.write(f" Pair: {pair}\n")
            rep.write(f" Direction: {direction}\n")
            rep.write(f" Entries: {list_fmt(entries)}\n")
            rep.write(f" Entry avg: {fmt_price(entry_avg)}\n")
            rep.write(f" Targets: {list_fmt(targets)}\n")
            sl_info = fmt_price(sl)
            if slp is not None:
                sl_info += f" ({fmt_price(slp)}%)"
            rep.write(f" Stop-loss: {sl_info}\n")
            if rr is not None:
                rep.write(f" RR (1st target): {fmt_price(rr)}\n")
            if r.get("skipped"):
                rep.write(f" Skipped: True ({r.get('skip_reason','')})\n")
            if r.get("warnings"):
                rep.write(f" Warnings: {', '.join(r['warnings'])}\n")
            rep.write("\n")

        rep.write("Summary\n-------\n")
        rep.write(f"Total signals processed: {total}\n")
        rep.write(f"Coverage: {cov}\n")
        # Present coverage percentage per field
        rep.write("Accuracy (coverage %): " + json.dumps({k: round((cov[k]/total)*100,2) for k in cov}, ensure_ascii=False) + "\n")

    return {"total": total, "coverage": cov, "report_path": out_report}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", nargs="+", required=True)
    ap.add_argument("--report", default=None)
    a = ap.parse_args()
    out = a.report or os.path.join(os.path.dirname(os.path.abspath(a.input[0])), "test_report_v2_fixed.txt")
    stats = evaluate(a.input, out)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
