#!/usr/bin/env python3
"""
refresh_portfolio.py  —  v8  (ISIN-verified AMFI-code-based)
v4/v5: LOCK rows now refresh (use --respect-lock for old behaviour), real AMFI NAV dates,
    Current%/Need% become live formulas, stale/failed report, optional LibreOffice recalc.
    v5/v6/v7: writes the matched AMFI scheme name into LivePrices col D and flags suspect codes;
        `--check` prints a code-verification table and changes nothing.
        v6: LivePrices col G = ISIN. A code whose AMFI ISINs do not include that ISIN is never written
            (and neither is any other row sharing that code); the correct code for the ISIN is shown.
        v7: rows WITHOUT an ISIN are also blocked when the AMFI scheme name shares almost no words
            with the sheet name (e.g. a Quantum Gold row resolving to a Quant Flexi Cap fund).

How it works:
  1. AMFI daily history is parsed with its scheme-code, ISIN, NAV and date columns.
  2. LivePrices col E is verified/corrected from the scheme ISIN where available;
     no-ISIN rows require an unambiguous Direct Growth scheme-name match.
  3. NAVs are fetched from AMFI (or mfapi.in as fallback) using the verified codes.
  4. MF sheet LTPs are updated by normalized exact-name match against LivePrices identifiers.

Usage:
    python3 refresh_portfolio.py

Requirements:
    pip install openpyxl requests
"""

import re, time, sys, shutil, subprocess, requests
from datetime import date, datetime, timedelta
from openpyxl import load_workbook
from typing import Optional, Tuple

# ── Config ───────────────────────────────────────────────────────
WORKBOOK    = "portfolio_final.xlsx"
MF_SHEET    = "📊 Mutual Funds"
ST_SHEET    = "📈 Stocks"
SM_SHEET    = "📋 Summary"
LP_SHEET    = "LivePrices"
CODE_SHEET  = "MF_Codes"

AMFI_URLS   = [
    "https://www.amfiindia.com/spages/NAVAll.txt",
    "https://www.amfiindia.com/spages/NAVopen.txt",
]
AMFI_HISTORY_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
MFAPI_URL   = "https://api.mfapi.in/mf/{code}/latest"
MFAPI_SEARCH_URL = "https://api.mfapi.in/mf/search"
YF_URLS     = [
    "https://query1.finance.yahoo.com/v8/finance/chart/{t}.NS",
    "https://query2.finance.yahoo.com/v8/finance/chart/{t}.NS",
]
HEADERS     = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
NavData = Tuple[float, str, str, set[str]]
NavMap = dict[str, NavData]

# ── Retry helper ─────────────────────────────────────────────────
def get(url, retries=3, timeout=20, delay=3, params=None):
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout, headers=HEADERS)
            r.raise_for_status()
            return r
        except requests.exceptions.Timeout:
            print(f"    timeout (attempt {attempt}/{retries})")
        except requests.exceptions.ConnectionError as e:
            print(f"    connection error (attempt {attempt}/{retries}): {e}")
        except requests.exceptions.HTTPError as e:
            print(f"    HTTP {e.response.status_code} — skipping")
            return None
        if attempt < retries:
            time.sleep(delay * attempt)
    return None

# ── 1. Bulk NAV fetch from AMFI ──────────────────────────────────
def parse_amfi_record(line: str) -> Optional[Tuple[str, NavData]]:
    parts = [part.strip() for part in line.strip().split(";")]
    if len(parts) < 6 or not parts[0].isdigit():
        return None
    if len(parts) >= 8:
        code, scheme_name = parts[:2]
        isin_values, nav_text, nav_date = parts[4:6], parts[6], parts[7]
        name_words = set(re.findall(r"[a-z]+", scheme_name.lower()))
        plan_words = re.findall(r"[a-z]+", parts[2].lower())
        missing_plan = [word for word in plan_words if word not in name_words]
        if missing_plan:
            scheme_name = f"{scheme_name} {' '.join(missing_plan)}"
            name_words.update(missing_plan)
        option_words = [word for word in re.findall(r"[a-z]+", parts[3].lower())
                        if word != "option"]
        if any(word not in name_words for word in option_words):
            scheme_name = f"{scheme_name} {parts[3]}"
    else:
        code, scheme_name = parts[:2]
        isin_values, nav_text, nav_date = parts[2:4], parts[4], parts[5]
    try:
        nav = float(nav_text)
    except ValueError:
        return None
    return code, (nav, nav_date, scheme_name,
                  {value for value in isin_values if value not in ("", "-")})


def fetch_amfi_history() -> Optional[NavMap]:
    """Merge recent AMFI daily reports, retaining each scheme's newest NAV."""
    day = date.today()
    navs = {}
    days_checked = 0
    while days_checked < 5:
        if day.weekday() < 5:
            day_text = day.strftime("%d-%b-%Y")
            print(f"  Trying AMFI history for {day_text} ...", end=" ", flush=True)
            resp = get(AMFI_HISTORY_URL, retries=1, timeout=25,
                       params={"frmdt": day_text, "todt": day_text})
            if resp:
                day_count = 0
                for line in resp.text.splitlines():
                    record = parse_amfi_record(line)
                    if record:
                        code, nav_data = record
                        navs.setdefault(code, nav_data)
                        day_count += 1
                print(f"OK ({day_count:,} records)")
            else:
                print("FAILED")
            days_checked += 1
        day -= timedelta(days=1)
    return navs or None


def fetch_amfi_bulk() -> Optional[NavMap]:
    history = fetch_amfi_history()
    if history:
        return history
    for url in AMFI_URLS:
        print(f"  Trying {url.split('/')[-1]} ...", end=" ", flush=True)
        resp = get(url, retries=1, timeout=20)
        if resp:
            navs = {}
            for line in resp.text.splitlines():
                record = parse_amfi_record(line)
                if record:
                    code, nav_data = record
                    navs[code] = nav_data
            if navs:
                print(f"OK  ({len(navs):,} records)")
                return navs
            print("empty")
        else:
            print("FAILED")
    return None

# ── 2. Per-fund fallback via mfapi.in ───────────────────────────
def fetch_mfapi(code):
    resp = get(MFAPI_URL.format(code=code), retries=2, timeout=10, delay=1)
    if resp:
        try:
            data = resp.json()
            latest = data["data"][0]
            return (float(latest["nav"]), latest.get("date", ""),
                    data.get("meta", {}).get("scheme_name", ""), None)
        except (KeyError, IndexError, TypeError, ValueError):
            return None
    return None


_NAME_ALIASES = (
    (re.compile(r"\bABSL\b", re.I), "Aditya Birla Sun Life"),
    (re.compile(r"\bPru\b", re.I), "Prudential"),
    (re.compile(r"\bL\s*&\s*M\b", re.I), "Large and Midcap"),
    (re.compile(r"\bNatural\s+Res\b", re.I), "Natural Resources"),
    (re.compile(r"\bFin\s+Svc\b", re.I), "Financial Services"),
    (re.compile(r"\bEW\b", re.I), "Equal Weight"),
    (re.compile(r"\bLMC250\b", re.I), "LargeMidcap 250"),
    (re.compile(r"\bLargemdcap\b", re.I), "LargeMidcap"),
    (re.compile(r"\bN30\b", re.I), "Next 30"),
    (re.compile(r"\bSBI Contra\s*\(Comma\)", re.I), "SBI Comma Fund"),
    (re.compile(r"\bICICI Prudential Equity\s*&\s*Debt(?: Fund)?\b", re.I),
     "ICICI Prudential Aggressive Hybrid Fund"),
    (re.compile(r"\bICICI Prudential Flexi Cap Fund\b", re.I),
     "ICICI Prudential Flexicap Fund"),
    (re.compile(r"\bICICI Prudential Multi[- ]Asset(?: Allocation)?(?: Fund)?\b", re.I),
     "ICICI Prudential Multi Asset Allocation Fund"),
    (re.compile(r"\bQuantum Gold Savings(?: Fund)?\b", re.I),
     "Quantum Gold ETF FOF"),
    (re.compile(r"\bSBI ELSS(?: Tax Saver)?(?: Fund)?\b", re.I),
     "SBI Long Term Equity Fund"),
)
_MATCH_STOP = {
    "and", "the", "of", "fund", "direct", "plan", "growth", "option",
    "regular", "funds", "mutual", "lot1", "lot2",
}
_DISTINGUISHING_WORDS = {
    "large", "mid", "small", "flexi", "multi", "balanced", "aggressive", "etf", "fof",
    "contra", "value", "gold", "silver", "index", "international", "global",
    "emerging", "banking", "financial", "technology", "manufacturing",
    "infrastructure", "defence", "defense", "energy", "resources", "equity",
    "debt", "hybrid", "momentum", "nifty", "sensex", "psu", "focused",
}


def _search_names(identifier):
    name = str(identifier or "").strip()
    for pattern, replacement in _NAME_ALIASES:
        name = pattern.sub(replacement, name)
    return [name]


def _fund_tokens(name):
    normalized = str(name).lower()
    normalized = re.sub(r"\bfunds?\s+of\s+funds?\b", "fof", normalized)
    normalized = re.sub(r"\bmidcap\b", "mid cap", normalized)
    return {token for token in re.findall(r"[a-z0-9]+", normalized)
            if token not in _MATCH_STOP and len(token) > 1}


def _is_direct_growth(name):
    lowered = str(name or "").lower()
    return ("direct" in lowered and ("growth" in lowered or "cumulative" in lowered)
            and not any(word in lowered for word in ("idcw", "dividend", "payout", "bonus")))


def _scheme_matches(identifier, scheme_name):
    """Only accept a search result when all identifying fund words match."""
    wanted = _fund_tokens(_search_names(identifier)[0])
    actual = _fund_tokens(scheme_name)
    return len(wanted) >= 2 and wanted.issubset(actual) and _is_direct_growth(scheme_name)


def configured_scheme_name(wb, identifier):
    """Return the most specific AMFI name configured for a LivePrices label."""
    if CODE_SHEET not in wb.sheetnames:
        return ""
    wanted = _fund_tokens(_search_names(identifier)[0])
    if len(wanted) < 2:
        return ""
    matches = []
    for row in wb[CODE_SHEET].iter_rows(min_row=2, values_only=True):
        if len(row) < 4 or str(row[3] or "").strip().upper() != "MF":
            continue
        fund_name, scheme_name = str(row[0] or "").strip(), str(row[2] or "").strip()
        fund_tokens = _fund_tokens(fund_name)
        if scheme_name and wanted.issubset(fund_tokens):
            matches.append((len(fund_tokens), scheme_name))
    if not matches:
        return ""
    best_size = min(size for size, _name in matches)
    best_names = {name for size, name in matches if size == best_size}
    if len(best_names) != 1:
        return ""
    return best_names.pop()


def find_amfi_scheme(identifier, expected_scheme_name=""):
    """Find a direct-growth scheme by name; never choose a weak/ambiguous match."""
    queries = []
    for name in (identifier, expected_scheme_name):
        if not str(name or "").strip():
            continue
        for query in _search_names(name):
            if query not in queries:
                queries.append(query)
    for query in queries:
        response = get(MFAPI_SEARCH_URL, retries=2, timeout=15, delay=1,
                       params={"q": query})
        if response is None:
            continue
        try:
            candidates = response.json()
        except ValueError as exc:
            print(f"    scheme search failed for {query!r}: {exc}")
            continue
        matches = [(str(item["schemeCode"]), item["schemeName"])
                   for item in candidates
                   if item.get("schemeCode") and item.get("schemeName")
                   and _scheme_matches(query, item["schemeName"])]
        if matches:
            wanted = _fund_tokens(query)
            extra_words = [(_fund_tokens(name) - wanted) for _code, name in matches]
            scores = [(len(extra & _DISTINGUISHING_WORDS), len(extra))
                      for extra in extra_words]
            best_score = min(scores)
            best = [match for match, score in zip(matches, scores) if score == best_score]
            if len(best) == 1:
                return best[0]
            print(f"    ambiguous AMFI scheme search for {query!r}; trying other scheme names")
            continue
    return None


def find_amfi_scheme_in_bulk(identifier, navs_bulk, expected_scheme_name=""):
    """Resolve ambiguous/renamed labels directly against the dated AMFI feed."""
    names = (identifier, expected_scheme_name)
    queries = []
    for name in names:
        if not str(name or "").strip():
            continue
        for query in _search_names(name):
            if query not in queries:
                queries.append(query)
    for query in queries:
        matches = [(code, data[2]) for code, data in navs_bulk.items()
                   if _scheme_matches(query, data[2])]
        if not matches:
            continue
        wanted = _fund_tokens(query)
        extra_words = [_fund_tokens(name) - wanted for _code, name in matches]
        scores = [(len(extra & _DISTINGUISHING_WORDS), len(extra))
                  for extra in extra_words]
        best_score = min(scores)
        best = [match for match, score in zip(matches, scores) if score == best_score]
        if len(best) == 1:
            return best[0]
    return None

# ── 3. Update LivePrices using col E AMFI codes ──────────────────
# Col F = "LOCK": by default v4 REFRESHES locked rows too (that was why LTPs
# stayed stale). Pass --respect-lock to skip them again.
# Safety net: any NAV differing >30% from stored value is rejected (wrong code).
_STOP = {"fund","plan","growth","direct","the","of","and","fof","index","option","regular"}
def suspect(idf, amfi_name):
    """Return a list of reasons this AMFI scheme may not be the fund named in the sheet."""
    if not amfi_name:
        return []
    n, flags = amfi_name.lower(), []
    if "direct" not in n:
        flags.append("not a Direct plan")
    if any(w in n for w in ("idcw", "dividend", "payout", "bonus")):
        flags.append("IDCW/Dividend option (need Growth)")
    toks = [t for t in re.findall(r"[a-z0-9&]+", idf.lower().replace("(zerodha)", "").replace("(direct)", "").replace("(sbi)", ""))
            if t not in _STOP and len(t) > 1]
    miss = [t for t in toks if t not in n and t.replace("&", "and") not in n]
    if toks and len(miss) / len(toks) > 0.5:
        flags.append(f"name mismatch (sheet words not in AMFI name: {', '.join(miss)})")
        if len(miss) / len(toks) >= 0.75:
            flags.append("almost no words in common with the sheet name")
    return flags

def isin_audit(ws, navs_bulk: Optional[NavMap]) -> Tuple[dict[str, str], dict[str, str]]:
    """-> (bad_codes {code: msg}, isin_to_code {isin: code})"""
    bad, i2c = {}, {}
    if not navs_bulk:
        return bad, i2c
    for code, v in navs_bulk.items():
        for i in v[3]:
            i2c[i] = code
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0] or len(row) < 7 or not row[6]:
            continue
        idf, code, isin = str(row[0]).strip(), str(row[4] or "").strip(), str(row[6]).strip()
        hit = navs_bulk.get(code)
        if code and hit and isin not in hit[3]:
            bad[code] = (f"{idf}: code {code} is '{hit[2][:45]}' but your ISIN {isin} is "
                         f"AMFI code {i2c.get(isin, 'not found in AMFI file')}")
    return bad, i2c

def check_codes(wb, navs_bulk: NavMap):
    ws = wb[LP_SHEET]
    _, i2c = isin_audit(ws, navs_bulk)
    print(f"{'Sheet name':42} {'Code':8} {'NAV':>9} {'Date':11}  AMFI scheme name / flags")
    seen = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0]:
            continue
        idf, code = str(row[0]).strip(), str(row[4] or "").strip()
        seen.setdefault(code, []).append(idf)
        if not code:
            print(f"{idf[:42]:42} {'-':8} {'':>9} {'':11}  ⚠️ NO CODE"); continue
        hit = navs_bulk.get(code) if navs_bulk else None
        if not hit:
            print(f"{idf[:42]:42} {code:8} {'':>9} {'':11}  ⚠️ CODE NOT FOUND in AMFI file"); continue
        nav, d, nm, isins = hit
        fl = suspect(idf, nm)
        isin = str(row[6]).strip() if len(row) > 6 and row[6] else ""
        if isin and isin not in isins:
            fl.append(f"ISIN MISMATCH — {isin} is AMFI code {i2c.get(isin, 'not found')}")
        print(f"{idf[:42]:42} {code:8} {nav:9.4f} {d:11}  {nm[:60]}" + (f"  ⚠️ {'; '.join(fl)}" if fl else ""))
    for c, names in seen.items():
        if c and len(names) > 1:
            print(f"  ℹ️ code {c} shared by: {' | '.join(names)}  (fine only if they are the same Direct plan)")

def _fmt(d):
    for f in ("%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(d, f).strftime("%d-%b-%Y")
        except ValueError:
            pass
    return str(d or "")

def update_liveprices(wb, navs_bulk: Optional[NavMap], respect_lock=False):
    ws = wb[LP_SHEET]
    up = fb = skip = locked = 0
    problems = []
    _, isin_to_code = isin_audit(ws, navs_bulk)

    for row in ws.iter_rows(min_row=2):
        idf = str(row[0].value or "").strip()
        if not idf:
            continue
        lock = str(row[5].value or "").strip().upper()
        if lock == "LOCK" and respect_lock:
            locked += 1
            continue

        code = str(row[4].value or "").strip()
        original_code = code
        sheet_isin = str(row[6].value or "").strip()
        hit = navs_bulk.get(code) if navs_bulk else None
        if sheet_isin and (hit is None or sheet_isin not in hit[3]):
            code = isin_to_code.get(sheet_isin, "")
            hit = navs_bulk.get(code) if navs_bulk and code else None

        nav = nav_date = amfi_name = None
        if hit is not None and (sheet_isin in hit[3] if sheet_isin else _scheme_matches(idf, hit[2])):
            nav, nav_date, amfi_name, _isins = hit
        elif sheet_isin and not navs_bulk:
            result = fetch_mfapi(code) if code else None
            if result:
                nav, nav_date, amfi_name, _unused = result
                if _scheme_matches(idf, amfi_name):
                    fb += 1
                else:
                    nav = None
        else:
            expected_name = configured_scheme_name(wb, idf)
            found = find_amfi_scheme_in_bulk(idf, navs_bulk, expected_name) if navs_bulk else None
            if not found:
                found = find_amfi_scheme(idf, expected_name)
            if found:
                new_code, expected_name = found
                candidate = navs_bulk.get(new_code) if navs_bulk else None
                if sheet_isin and candidate is None:
                    problems.append(f"{idf[:45]}: cannot verify discovered code {new_code} against ISIN; unchanged")
                    skip += 1
                    continue
                if candidate is not None and sheet_isin and sheet_isin not in candidate[3]:
                    problems.append(f"{idf[:45]}: found {expected_name!r}, but its ISIN does not match; unchanged")
                    skip += 1
                    continue
                if candidate is not None:
                    nav, nav_date, amfi_name, _isins = candidate
                else:
                    result = fetch_mfapi(new_code)
                    if result:
                        nav, nav_date, amfi_name, _unused = result
                        fb += 1
                if amfi_name and not _scheme_matches(idf, amfi_name):
                    nav = None
                if nav is not None:
                    code = new_code
            elif code:
                result = fetch_mfapi(code)
                if result:
                    nav, nav_date, amfi_name, _unused = result
                    if sheet_isin or not _scheme_matches(idf, amfi_name):
                        nav = None
                    else:
                        fb += 1

        if nav is None or not amfi_name or not _is_direct_growth(amfi_name):
            problems.append(f"{idf[:45]}: no verified Direct Growth NAV found (kept ₹{row[1].value}, {row[2].value})")
            skip += 1
            continue

        prev = row[1].value
        if code == original_code and prev and isinstance(prev, (int, float)) and float(prev) > 0:
            ratio = abs(nav - float(prev)) / float(prev)
            if ratio > 0.30:
                problems.append(f"{idf[:45]}: REJECTED stored ₹{float(prev):.4f} vs AMFI ₹{nav:.4f} "
                                f"({ratio*100:.0f}% diff — wrong AMFI code?)")
                skip += 1
                continue
        row[1].value = float(nav)
        row[2].value = _fmt(nav_date)
        row[3].value = amfi_name
        row[4].value = str(code)
        up += 1

    print(f"  LivePrices: {up} updated, {locked} locked/skipped, {fb} via mfapi, {skip} not updated")
    for p in problems:
        print(f"    ⚠️  {p}")
    # staleness report (NAV older than 7 days)
    cutoff = datetime.now() - timedelta(days=7)
    stale = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] and row[2]:
            try:
                if datetime.strptime(str(row[2]), "%d-%b-%Y") < cutoff:
                    stale.append(f"{str(row[0])[:40]} ({row[2]})")
            except ValueError:
                pass
    if stale:
        print(f"  ⚠️  {len(stale)} NAVs older than 7 days:")
        for x in stale:
            print("      ", x)

# ── 4. MF sheet — EXACT name match (no fuzzy tokens) ────────────
def normalize(s):
    expanded = _search_names(s)[0]
    return " ".join(re.findall(r"[a-z0-9]+", expanded.lower()))


def update_mf_ltps(wb):
    ws_lp = wb[LP_SHEET]
    ws_mf = wb[MF_SHEET]

    live_lookup = {}

    for row in ws_lp.iter_rows(min_row=2, values_only=True):

        identifier = row[0]
        nav        = row[1]
        code       = row[4]
        isin       = row[6]

        if not nav:
            continue

        nav = float(nav)

        if identifier:
            live_lookup[f"NAME:{normalize(identifier)}"] = nav

        if code:
            live_lookup[f"CODE:{str(code).strip()}"] = nav

        if isin:
            live_lookup[f"ISIN:{str(isin).strip()}"] = nav

    updates = 0
    misses = []

    for r in range(3, ws_mf.max_row + 1):

        fund_name = str(ws_mf.cell(r, 1).value or "").strip()

        if not fund_name:
            continue

        if "──" in fund_name:
            continue

        if "GRAND TOTAL" in fund_name.upper():
            continue

        nav = None

        nav = live_lookup.get(f"NAME:{normalize(fund_name)}")

        if nav is not None:
            ws_mf.cell(r, 6).value = nav
            updates += 1
        else:
            misses.append(fund_name)

    print(
        f"  MF LTPs : {updates} updated, "
        f"{len(misses)} missing"
    )

    if misses:
        print("\n  Missing mappings:")
        for m in misses:
            print("    ", m)

# ── 5. Stock prices from Yahoo Finance ───────────────────────────
def update_stock_ltps(wb):
    ws = wb[ST_SHEET]
    up = fail = 0
    for row in ws.iter_rows(min_row=3):
        ticker = str(row[0].value or "").strip()
        if not ticker or "GRAND" in ticker:
            continue
        nav = None
        for tmpl in YF_URLS:
            resp = get(tmpl.format(t=ticker), retries=2, timeout=10, delay=2)
            if resp:
                try:
                    nav = resp.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]
                    break
                except Exception:
                    pass
        if nav is not None:
            row[4].value = round(float(nav), 2)
            up += 1
        else:
            fail += 1
            print(f"    no price for {ticker}")
    print(f"  Stock LTPs: {up} updated, {fail} unchanged")

# ── 5b. Make Current% / Need% live formulas ─────────────────────
def fix_formulas(wb):
    mf, st = wb[MF_SHEET], wb[ST_SHEET]
    base = f"'{SM_SHEET}'!$B$6"          # grand total (MF + stocks + cash)
    last = None
    for r in range(3, mf.max_row + 1):
        n = str(mf.cell(r, 1).value or "")
        if "GRAND" in n:
            last = r
    for r in range(3, (last or mf.max_row)):
        n = str(mf.cell(r, 1).value or "").strip()
        if not n or "──" in n:
            continue
        mf.cell(r, 10).value = f"=G{r}/{base}"                 # Current %
        mf.cell(r, 12).value = f"=N(K{r})-J{r}"                # Need ↑↓ %
    for r in range(3, st.max_row + 1):
        n = str(st.cell(r, 1).value or "").strip()
        if not n or "GRAND" in n:
            continue
        st.cell(r, 9).value = f"=F{r}/{base}"                  # Current %
    if last:
        mf.cell(1, 1).value = (f'="📊  ALL MUTUAL FUNDS — Consolidated  |  Updated: {date.today():%d-%b-%Y}'
                               f'  |  Grand Total ₹"&TEXT(G{last}/100000,"0.0")&"L  |  Target ₹85L"')
    print("  Formulas:   Current% / Need% / MF title now live")

# ── 6. Stamp today's date in all sheet headers ───────────────────
def update_dates(wb):
    today = date.today().strftime("%d-%b-%Y")
    date_pat = re.compile(r"\d{2}-[A-Za-z]{3}-\d{4}")
    for sheet_name in [SM_SHEET, ST_SHEET]:
        cell = wb[sheet_name].cell(row=1, column=1)
        if cell.value:
            cell.value = date_pat.sub(today, str(cell.value))
    print(f"  Dates:      all headers → {today}")


def request_recalculation(wb):
    wb.calculation.calcMode = "auto"
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True


# ── MAIN ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    w = 55
    print(f"\n{'='*w}")
    print(f"  Portfolio Refresh  —  {date.today().strftime('%d %b %Y')}")
    print(f"{'='*w}\n")

    try:
        wb = load_workbook(WORKBOOK)
    except FileNotFoundError:
        sys.exit(f"ERROR: '{WORKBOOK}' not found in current folder.")

    # MF NAVs
    print("── Mutual Fund NAVs ──────────────────────────────────────")
    navs = fetch_amfi_bulk()
    if not navs:
        print("  AMFI bulk unavailable — using mfapi.in per-fund fallback")
    if "--check" in sys.argv:
        if not navs:
            sys.exit("AMFI bulk file unavailable — cannot verify codes right now.")
        check_codes(wb, navs)
        sys.exit(0)
    update_liveprices(wb, navs, respect_lock="--respect-lock" in sys.argv)
    update_mf_ltps(wb)

    # Stock prices
    print("\n── Stock Prices ──────────────────────────────────────────")
    update_stock_ltps(wb)

    # Dates
    print("\n── Headers ───────────────────────────────────────────────")
    update_dates(wb)
    fix_formulas(wb)
    request_recalculation(wb)

    wb.save(WORKBOOK)
    # openpyxl saves no cached values -> recalc so every viewer shows fresh numbers
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        try:
            subprocess.run([soffice, "--headless", "--convert-to", "xlsx", "--outdir", ".recalc", WORKBOOK],
                           check=True, capture_output=True, timeout=120)
            shutil.move(f".recalc/{WORKBOOK}", WORKBOOK)
            print("  Recalculated via LibreOffice")
        except Exception as e:
            print(f"  (LibreOffice recalc skipped: {e}) — open in Excel and it will recalc")
    else:
        print("  (open in Excel to recalc — formulas have no cached values yet)")
    print(f"\n✅  Saved → {WORKBOOK}")
    print(f"{'='*w}\n")
