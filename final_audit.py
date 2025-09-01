import re
import math
import statistics
from typing import List, Tuple, Optional, Dict, Any

# --- Copied from parser_v2.py ---

# Configuration
KNOWN_QUOTES = {
    "USDT","USDC","USD","BUSD","BTC","ETH","BNB","TRY","TUSD","FDUSD","DAI","EUR","BIDR","BRL"
}
LONG_WORDS = [r"\bLONG\b", r"\bBUY\b", r"\bOPEN\s*LONG\b", r"\bGO\s*LONG\b", r"لانگ", r"خرید"]
SHORT_WORDS = [r"\bSHORT\b", r"\bSELL\b", r"\bOPEN\s*SHORT\b", r"\bGO\s*SHORT\b", r"شورت", r"فروش"]
ENTRY_KEYS = [
    "ENTRY", "ENTRIES", "ENTRY ZONE", "ENTRY PRICE", "ENTRY POINT",
    "BUY", "BUY ZONE", "BUY RANGE", "ENTER", "ENTRY TARGET", "ENTRY TARGETS",
    "ENTRY TARGET :", "ENTRY TARGETS :", "ENTRY:", "ENTRYs", "ENTRYs :", "CMP", "CURRENT ASK", "CURRENT PRICE", "MARKET"
]
TARGET_KEYS = [
    "TARGET", "TARGETS", "TAKE PROFIT", "TAKE-PROFIT", "TP", "SELL", "PROFIT", "PROFIT TARGET"
]
STOP_KEYS = [
    "STOP", "STOPLOSS", "STOP LOSS", "STOP-LOSS", "SL", "S/L", "STOP TARGET", "STOP TARGETS"
]
NOISY_LINE_HINTS = [
    "LEVERAGE", "LEV", "CROSS", "ISOLATED", "RISK", "R/R", "RR", "RISK-REWARD",
    "VOLUME", "STRENGTH", "PUBLISHED BY", "VIP", "JOIN", "LINK", "HTTP", "HTTPS",
    "ID:", "SIGNAL ID", "ACCURACY", "PORTFOLIO", "CAPITAL", "USE %", "MARGIN",
    "SCALP ONLY", "SCALPING", "BYBIT", "BINGX", "KUCOIN", "BINANCE", "MEXC", "GATE",
    "TREND", "SUPPORT", "RESISTANCE", "VWAP", "FVG", "ANALYSIS", "PLAN", "STRATEGY",
    "DISCLAIMER", "NOTE:", "NFA", "DYOR", "CURRENT PRICE", "CURRENT ASK"
]
SKIP_NON_BINANCE = False
BINANCE_COINS = {
    "BTC","ETH","BNB","XRP","ADA","DOGE","SOL","TRX","DOT","AVAX","LTC","LINK","MATIC","TON","BCH",
    "XLM","XMR","ATOM","ETC","FIL","VET","ICP","APT","ARB","OP","SUI",
    "HOT","SNEK","SCR","SEI","ENJ","APE","YFI","LINK","FIS","AXS","GHST","BTC","ZRX","BEL","YGG",
    "BRETT","KERNEL","ZIG","WAVES","JASMY","WAXP","BAND","MVL","NEAR","WAL","PORTAL","ORDI","CTK",
    "MKR","EPS","RNDR","FLOW","VIC","TRX","RESOLV","IOTX","ENA","ICX","LUNA","SKL","RAD","LPT","FIL",
    "QKC","POPCAT","BIGTIME","RSR","MKR","BTC","KSM","EGLD","XTZ","PERP","AVAX","DOGS","EIGEN","WOO",
    "SFP","COMP","IMX","MTL","DODO","SAND","APT","APTUSDT".replace("USDT","")
}
FALSE_PAIR_TOKEN = ("EN","TRY")
KNOWN_SINGLE_LETTER_COINS: set[str] = set()

# Utility Functions
def _norm(s: str) -> str:
    persian_arabic_digits = "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩"
    latin_digits = "01234567890123456789"
    digit_translation = str.maketrans(persian_arabic_digits, latin_digits)
    s = s.translate(digit_translation)
    s = s.replace("\u200c","").replace("\u200b","")
    s = s.replace("–","-").replace("—","-").replace("•"," ").replace("·"," ").replace("•"," ")
    s = s.replace("_"," ").replace("|"," ")
    s = re.sub(r'(\d)\s*-\s*(\d)', r'\1 \2', s)
    return s

def _float(tok: str) -> Optional[float]:
    tok = tok.strip()
    if not tok: return None
    tok = tok.replace(",", "")
    if tok in {"-","–"}: return None
    try:
        return float(tok)
    except Exception:
        tok2 = tok.replace("$","")
        try:
            return float(tok2)
        except Exception:
            return None

def _numbers_from(line: str) -> List[Tuple[float, str]]:
    nums: List[Tuple[float, str]] = []
    for m in re.finditer(r"(?<![A-Za-z])(-?\d+(?:[.,]\d+)?)(?![A-Za-z])", line):
        original_str = m.group(1)
        val = _float(original_str)
        if val is not None:
            nums.append((val, original_str))
    return nums

def _line_has_any(line: str, keys: List[str]) -> bool:
    U = line.upper()
    return any(k in U for k in keys)

def _line_is_noisy(line: str) -> bool:
    U = line.upper()
    return any(h in U for h in NOISY_LINE_HINTS)

def _numbers_and_weights_from(line: str) -> List[Tuple[float, Optional[float]]]:
    entries_with_weights: List[Tuple[float, Optional[float]]] = []
    cursor = 0
    while cursor < len(line):
        match = re.search(r"(?<![A-Za-z])(-?\d+(?:[.,]\d+)?)(?![A-Za-z])", line[cursor:])
        if not match:
            break
        price_str = match.group(1)
        price = _float(price_str)
        absolute_end_of_number = cursor + match.end()
        if price is None:
            cursor = absolute_end_of_number
            continue
        weight_match = re.match(r"\s*\(\s*(\d+(?:\.\d+)?)\s*%\s*\)", line[absolute_end_of_number:])
        weight = None
        if weight_match:
            weight = float(weight_match.group(1))
            cursor = absolute_end_of_number + weight_match.end()
        else:
            cursor = absolute_end_of_number
        entries_with_weights.append((price, weight))
    return entries_with_weights

# Parsing Functions
def _split_known_quote(sym: str) -> Optional[Tuple[str,str]]:
    S = sym.upper()
    for q in sorted(KNOWN_QUOTES, key=len, reverse=True):
        if S.endswith(q) and len(S) > len(q):
            return S[:-len(q)], q
    return None

def _clean_quote(q: str) -> str:
    Q = q.upper().replace("-", "")
    if Q == "USD": return "USD"
    if Q in KNOWN_QUOTES: return Q
    return Q

def extract_symbol(text: str) -> Tuple[Optional[str], Optional[str], Dict[str,str]]:
    U = text.upper()
    m = re.search(r"([#$]?\s*)?([A-Z0-9]{1,15})\s*/\s*([A-Z\-]{2,10})", U)
    if m:
        base = m.group(2).strip().upper()
        quote = _clean_quote(m.group(3))
        if base == FALSE_PAIR_TOKEN[0] and quote == FALSE_PAIR_TOKEN[1] and "ENTRY" in U:
            pass
        else:
            if quote in KNOWN_QUOTES and base.endswith(quote) and len(base) > len(quote):
                base = base[:-len(quote)]
            if quote in KNOWN_QUOTES:
                if len(base) == 1 and base not in KNOWN_SINGLE_LETTER_COINS:
                    return base, quote, {"mode":"slash_single_base"}
                return base, quote, {"mode":"slash"}
    candidates: List[str] = []
    for m in re.finditer(r"[#$]([A-Z][A-Z0-9]{1,15})", U):
        candidates.append(m.group(1))
    m = re.search(r"\bPAIR\s*[:\-]\s*([#$]?[A-Z0-9]{2,20})", U)
    if m: candidates.append(m.group(1).lstrip("#$"))
    m = re.search(r"\bCOIN\s*[:\-]\s*([#$]?[A-Z0-9]{2,20})", U)
    if m: candidates.append(m.group(1).lstrip("#$"))
    m = re.search(r"\bSYMBOL\s*[:\-]\s*([#$]?[A-Z0-9]{2,20})", U)
    if m: candidates.append(m.group(1).lstrip("#$"))
    for cand in candidates:
        sp = _split_known_quote(cand)
        if sp:
            b, q = sp
            if len(b) == 1 and b not in KNOWN_SINGLE_LETTER_COINS:
                return b, q, {"mode":"hashtag_or_label_concat_single_base"}
            return b, q, {"mode":"hashtag_or_label_concat"}
        m2 = re.search(rf"{re.escape(cand)}\s*/\s*([A-Z]{{2,6}})", U)
        if m2:
            q = _clean_quote(m2.group(1))
            if q in KNOWN_QUOTES:
                if len(cand) == 1 and cand not in KNOWN_SINGLE_LETTER_COINS:
                    return cand, q, {"mode":"hashtag_slash_single_base"}
                return cand, q, {"mode":"hashtag_slash"}
    if candidates:
        for cand in candidates:
            for q in KNOWN_QUOTES:
                if re.search(rf"\b{re.escape(cand)}\s+{q}\b", U):
                    if len(cand) == 1 and cand not in KNOWN_SINGLE_LETTER_COINS:
                        return cand, q, {"mode":"spaced_hashtag_single_base"}
                    return cand, q, {"mode":"spaced_hashtag"}
        first = candidates[0]
        if len(first) == 1 and first not in KNOWN_SINGLE_LETTER_COINS:
            return first, "USDT", {"mode":"hashtag_default_usdt_single_base"}
        return first, "USDT", {"mode":"hashtag_default_usdt"}
    for m in re.finditer(r"\b([A-Z0-9]{2,15})(USDT|USDC|BUSD|BTC|ETH|TRY|TUSD|FDUSD|USD)\b", U):
        token = m.group(0)
        if token == "ENTRY": continue
        b = m.group(1).upper()
        q = m.group(2).upper()
        if len(b) == 1 and b not in KNOWN_SINGLE_LETTER_COINS: continue
        if b == FALSE_PAIR_TOKEN[0] and q == FALSE_PAIR_TOKEN[1]: continue
        return b, q, {"mode":"concat"}
    m = re.search(r"\b([A-Z0-9]{2,15})\s*/\s*-\s*(USD|USDT)\b", U)
    if m:
        b = m.group(1).upper()
        q = m.group(2).upper()
        if len(b) == 1 and b not in KNOWN_SINGLE_LETTER_COINS:
            return b, q, {"mode":"concat_single_base"}
        return b, q, {"mode":"slash_hyphen_usd"}
    if "/" not in U:
        m = re.search(r'\b([A-Z0-9]+)\s+([A-Z]{2,5})\b', U)
        if m:
            base = m.group(1)
            quote = m.group(2)
            if quote in KNOWN_QUOTES:
                return base, quote, {"mode": "spaced_pair"}
    return None, None, {}

def detect_direction(text: str) -> str:
    U = text.upper()
    long_hit = any(re.search(p, U, flags=re.I) for p in LONG_WORDS)
    short_hit = any(re.search(p, U, flags=re.I) for p in SHORT_WORDS)
    if long_hit and short_hit:
        for ln in text.splitlines():
            LU = ln.upper()
            if _line_has_any(LU, ENTRY_KEYS):
                if any(re.search(p, LU, flags=re.I) for p in LONG_WORDS): return "LONG"
                if any(re.search(p, LU, flags=re.I) for p in SHORT_WORDS): return "SHORT"
        return "LONG"
    if short_hit: return "SHORT"
    if long_hit: return "LONG"
    m = re.search(r"Signal\s*Type\s*[-:]\s*(Short|Long)", text, flags=re.I)
    if m: return m.group(1).upper()
    return "LONG"

def parse_entries(text: str) -> Tuple[List[float], Optional[float], Dict[str,bool]]:
    entries_with_weights: List[Tuple[float, Optional[float]]] = []
    meta = {"used_cmp": False, "entry_detected": False}
    for ln in text.splitlines():
        if ln.strip().startswith('#') or _line_is_noisy(ln): continue
        LU = ln.upper()
        is_entry_line = _line_has_any(LU, ENTRY_KEYS) or re.search(r"\bENTRY\b", LU)
        is_cmp_line = any(k in LU for k in ("CMP", "CURRENT ASK", "CURRENT PRICE"))
        if is_entry_line:
            line_entries = _numbers_and_weights_from(ln)
            if line_entries:
                entries_with_weights.extend(line_entries)
                meta["entry_detected"] = True
        elif is_cmp_line:
            nums = _numbers_from(ln)
            if nums:
                entries_with_weights.append((nums[0][0], None))
                meta["used_cmp"] = True
    positive_entries = [(p, w) for p, w in entries_with_weights if p > 0]
    prices_only = [p for p, w in positive_entries]
    has_decimal = any(p != int(p) for p in prices_only)
    has_large_number = any(p >= 1000 for p in prices_only)
    if has_decimal or has_large_number:
        small_integer_max = 10
        filtered_entries_with_weights = [(p, w) for p, w in positive_entries if (p != int(p)) or not (1 <= p <= small_integer_max)]
    else:
        filtered_entries_with_weights = positive_entries
    if len(filtered_entries_with_weights) > 4:
        filtered_entries_with_weights = filtered_entries_with_weights[:4]
    out = [p for p, w in filtered_entries_with_weights]
    entry_avg = None
    if out:
        prices = [p for p, w in filtered_entries_with_weights]
        weights = [w for p, w in filtered_entries_with_weights]
        use_weighted_avg = False
        if all(w is not None for w in weights):
            total_weight = sum(weights)
            if 99 <= total_weight <= 101:
                use_weighted_avg = True
        if use_weighted_avg:
            entry_avg = sum(p * (w / 100.0) for p, w in filtered_entries_with_weights)
        else:
            entry_avg = sum(prices) / len(prices)
    return out, entry_avg, meta

def parse_targets(text: str, direction: str, entry_price: Optional[float]) -> List[float]:
    targets: List[float] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        LU = ln.upper()
        is_noisy = _line_is_noisy(ln)
        is_stop_line = _line_has_any(LU, STOP_KEYS)
        is_target_line = (_line_has_any(LU, TARGET_KEYS) and "ENTRY" not in LU) or re.match(r"^\s*\d+\)", ln)
        if is_noisy or is_stop_line:
            i += 1
            continue
        if is_target_line:
            while i < len(lines):
                current_line = lines[i]
                current_LU = current_line.upper()
                if not current_line.strip(): break
                if _line_has_any(current_LU, STOP_KEYS) or _line_has_any(current_LU, ENTRY_KEYS):
                    if not _line_has_any(current_LU, TARGET_KEYS): break
                if "%" in current_line and entry_price is not None:
                    pcts = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", current_line)]
                    for p in pcts:
                        if direction == "LONG": targets.append(round(entry_price * (1 + p / 100.0), 10))
                        else: targets.append(round(entry_price * (1 - p / 100.0), 10))
                line_without_pct = re.sub(r"(\d+(?:\.\d+)?)\s*%", "", current_line)
                nums_with_str = _numbers_from(line_without_pct)
                for n, n_str in nums_with_str:
                    is_decimal = '.' in n_str or ',' in n_str
                    if not is_decimal and n == int(n) and 1 <= n <= 10: continue
                    targets.append(abs(n))
                i += 1
            continue
        i += 1
    targets = list(dict.fromkeys(targets))
    if len(targets) >= 3:
        pos = [abs(x) for x in targets if x > 0]
        if pos:
            med = statistics.median(pos)
            if med > 0:
                changed = True
                while changed and len(targets) >= 3:
                    changed = False
                    mx = max(targets)
                    if abs(mx) > 50 * med:
                        targets.remove(mx); changed = True
    targets = [v for v in targets if v <= 1e7]
    return targets

def parse_stop(text: str, direction: str, entry_price: Optional[float]) -> Tuple[Optional[float], Optional[float], Dict[str,str]]:
    stop_val: Optional[float] = None
    stop_pct: Optional[float] = None
    meta: Dict[str,str] = {}
    lines = text.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        ln = lines[i]
        if _line_is_noisy(ln): i += 1; continue
        if not _line_has_any(ln.upper(), STOP_KEYS): i += 1; continue
        meta["raw"] = ln
        m_rng = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*%", ln)
        m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%", ln)
        lookahead_checked = False
        if not (m_rng or m_pct) and i+1 < n:
            nxt = lines[i+1]
            if not _line_is_noisy(nxt):
                m_rng = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*%", nxt) or m_rng
                m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%", nxt) or m_pct
                if m_rng or m_pct: meta["lookahead"] = "1"; lookahead_checked = True
        if m_rng:
            p1 = float(m_rng.group(1)); p2 = float(m_rng.group(2))
            worst = max(p1, p2)
            stop_pct = worst
            if entry_price is not None and stop_val is None:
                if direction == "LONG": stop_val = entry_price * (1 - worst/100.0)
                else: stop_val = entry_price * (1 + worst/100.0)
            elif entry_price is None: meta["percent_range_no_entry"] = "1"
        if m_pct:
            p = float(m_pct.group(1))
            stop_pct = p
            if entry_price is not None and stop_val is None:
                if direction == "LONG": stop_val = entry_price * (1 - p/100.0)
                else: stop_val = entry_price * (1 + p/100.0)
            elif entry_price is None: meta["percent_no_entry"] = "1"
        conditional_patterns = r"(?:stop-?loss\s*(?:on)?)?\s*(?:daily\s+close|\d+H\s*close|close\s*\d+H)\s+(?:under|below)\s+([\d.]+)"
        m_cond = re.search(conditional_patterns, ln, flags=re.I)
        if m_cond:
            val = _float(m_cond.group(1))
            if val is not None: stop_val = val; meta["mode"] = "conditional"
        line_without_pct = re.sub(r"(\d+(?:\.\d+)?)\s*%", "", ln)
        nums = _numbers_from(line_without_pct)
        if nums: stop_val = nums[-1][0]
        break
    if stop_val is None and stop_pct is None and entry_price is not None:
        stop_pct = 5.0
        if direction == "LONG": stop_val = entry_price * 0.95
        else: stop_val = entry_price * 1.05
        meta["auto_default_5pct"] = "1"
    if stop_val is not None: stop_val = round(stop_val, 10)
    return stop_val, stop_pct, meta

def parse_signal(signal_text: str) -> Optional[Dict]:
    raw = signal_text
    text = _norm(signal_text)
    base, quote, sym_meta = extract_symbol(text)
    if not base or not quote: return None
    if len(base) == 1 and base not in KNOWN_SINGLE_LETTER_COINS:
        return {"pair": f"{base}/{quote}", "skipped": True, "skip_reason":"single_letter_base"}
    if SKIP_NON_BINANCE and base not in BINANCE_COINS:
        return {"pair": f"{base}/{quote}", "skipped": True, "skip_reason":"not_binance_listed"}
    direction = detect_direction(text)
    entries, entry_avg, entry_meta = parse_entries(text)
    entry_ref = entry_avg if entry_avg is not None else (entries[0] if entries else None)
    targets = parse_targets(text, direction, entry_ref)
    stop_val, stop_pct, stop_meta = parse_stop(text, direction, entry_ref)
    direction_adjusted = False
    if entry_ref is not None and targets:
        hi_t = max(targets); lo_t = min(targets)
        if direction == "SHORT" and lo_t > entry_ref: direction = "LONG"; direction_adjusted = True
        elif direction == "LONG" and hi_t < entry_ref: direction = "SHORT"; direction_adjusted = True
    if targets:
        targets = sorted(set(targets), reverse=(direction=="SHORT"))
    warnings: List[str] = []
    if direction_adjusted: warnings.append("Direction auto-corrected based on price logic.")
    if entry_ref is not None and stop_val is not None:
        if direction == "LONG" and stop_val >= entry_ref: warnings.append("Stop-loss is not below entry for LONG.")
        if direction == "SHORT" and stop_val <= entry_ref: warnings.append("Stop-loss is not above entry for SHORT.")
    rr = None
    if entry_ref is not None and targets and stop_val is not None:
        t1 = targets[0] if direction == "LONG" else targets[-1] if len(targets)>1 else targets[0]
        risk = abs(entry_ref - stop_val)
        reward = abs(t1 - entry_ref)
        if risk > 0: rr = round(reward/risk, 4)
    result = {
        "pair": f"{base}/{quote}", "symbol_meta": sym_meta, "direction": direction,
        "entries": [round(x,10) for x in entries], "entry_avg": round(entry_avg,10) if entry_avg is not None else None,
        "targets": [round(x,10) for x in targets], "stop_loss": stop_val, "stop_loss_percent": stop_pct,
        "rr_first_target": rr, "entry_meta": entry_meta, "stop_meta": stop_meta, "warnings": warnings,
        "raw_text_excerpt": text[:240] + ("..." if len(text)>240 else ""),
    }
    return result

# --- Copied from tester_v2.py ---
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

# --- Main Audit Logic ---
def run_audit(paths):
    blocks = load_blocks(paths)
    total_signals = len(blocks)
    signals_with_target_keywords = 0
    signals_with_targets_parsed = 0

    print("="*80)
    print("Crypto Signal Parser - Final Target Audit")
    print("="*80)
    print(f"Processing {total_signals} signals from: {', '.join(paths)}\n")

    for i, block in enumerate(blocks, 1):
        print(f"\n--- Signal #{i} ---")
        print("RAW TEXT:")
        print(block)
        print("-" * 20)

        has_target_keyword = any(re.search(r'\b' + re.escape(key) + r'\b', block, re.IGNORECASE) for key in TARGET_KEYS)
        if has_target_keyword:
            signals_with_target_keywords += 1

        result = parse_signal(block)

        if result and result.get('targets'):
            parsed_targets = result['targets']
            signals_with_targets_parsed += 1
            print(f"PARSED TARGETS: {parsed_targets}")
        elif result:
            print("PARSED TARGETS: []")
            if has_target_keyword:
                print("VERIFICATION NOTE: Target keywords were present, but no targets were parsed.")
        else:
            print("PARSED TARGETS: Parsing failed entirely.")
        print("-" * 20)

    print("\n" + "="*80)
    print("AUDIT SUMMARY")
    print("="*80)
    print(f"Total signals processed: {total_signals}")
    print(f"Signals with target-related keywords: {signals_with_target_keywords}")
    print(f"Signals where targets were successfully parsed: {signals_with_targets_parsed}")

    if signals_with_target_keywords > 0:
        coverage = (signals_with_targets_parsed / signals_with_target_keywords) * 100
        print(f"Target Parsing Coverage (based on keywords): {coverage:.2f}%")
    else:
        print("No signals with target keywords were found.")

if __name__ == "__main__":
    run_audit(['signals.txt', 'signals2.txt'])
