# %% [markdown]
# Polymarket: Tag search → Market dump (Gamma API) → Trade metrics (Data API)
# Works in Google Colab or locally.

# %% [code]
import requests, time, json, csv, unicodedata, sys
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set

# ---------- API endpoints ----------
GAMMA_BASE = "https://gamma-api.polymarket.com"
DATA_BASE  = "https://data-api.polymarket.com"

URL_TAGS     = f"{GAMMA_BASE}/tags"
URL_MARKETS  = f"{GAMMA_BASE}/markets"
URL_TRADES   = f"{DATA_BASE}/trades"   # key params: market=<conditionId>, takerOnly=false

# ---------- Network / pagination settings ----------
GAMMA_LIMIT = 250
DATA_LIMIT  = 1000
TIMEOUT     = 20
MAX_RETRIES = 5
BACKOFF     = 1.6   # exponential backoff

# ---------- Helpers ----------
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()

def _get_json(url: str, params: Dict[str, Any]) -> Any:
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:240]}")
            r.raise_for_status()
        except Exception as e:
            last = e
            time.sleep(BACKOFF ** (attempt - 1))
    raise RuntimeError(f"GET failed after {MAX_RETRIES} attempts: {last}")

# ---------- Tag search ----------
def find_tags_by_query(query: str) -> List[Dict[str, Any]]:
    q = _norm(query)
    out: List[Dict[str, Any]] = []
    offset = 0
    while True:
        data = _get_json(URL_TAGS, {"limit": GAMMA_LIMIT, "offset": offset})
        if not isinstance(data, list):
            data = data.get("data", []) if isinstance(data, dict) else []
        for t in data:
            label = _norm(t.get("label", ""))
            slug  = _norm(t.get("slug", ""))
            if q in label or q in slug:
                out.append(t)
        if len(data) < GAMMA_LIMIT:
            break
        offset += GAMMA_LIMIT
    return out

def print_tags(tags: List[Dict[str, Any]], max_rows: int = 120):
    if not tags:
        print("No matches found.")
        return
    print(f"Found {len(tags)} tags (showing up to {max_rows})")
    print("-" * 95)
    for i, t in enumerate(tags[:max_rows], 1):
        print(f"{i:3d}. id={t.get('id')} | label={t.get('label')} | slug={t.get('slug')}")
    print("-" * 95)

# ---------- Fetch markets by tag (Gamma API) ----------
def fetch_markets_by_tag(tag_id: int, closed_flag: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    offset = 0
    while True:
        params = {
            "tag_id": tag_id,
            "related_tags": "true",
            "closed": closed_flag,   # "false" (open) or "true" (closed)
            "limit": GAMMA_LIMIT,
            "offset": offset,
        }
        data = _get_json(URL_MARKETS, params)
        if not isinstance(data, list):
            data = data.get("data", []) if isinstance(data, dict) else []
        out.extend(data)
        if len(data) < GAMMA_LIMIT:
            break
        offset += GAMMA_LIMIT
    return out

# ---------- Trade metrics (Data API) ----------
def fetch_trades_metrics(condition_id: str) -> Dict[str, Any]:
    """
    Returns metrics for a market (conditionId) from Data API:
      - total_trades: number of trades
      - unique_traders: number of unique proxyWallet addresses
      - first_trade_ts / last_trade_ts: timestamps of first/last trade
    Supports both cursor and offset pagination.
    """
    traders: Set[str] = set()
    total = 0
    first_ts: Optional[int] = None
    last_ts: Optional[int]  = None

    params = {"market": condition_id, "limit": DATA_LIMIT, "takerOnly": "false"}

    next_cursor: Optional[str] = None
    used_cursor_mode = False
    while True:
        p = dict(params)
        if next_cursor:
            p["cursor"] = next_cursor
        resp = _get_json(URL_TRADES, p)

        if isinstance(resp, dict) and "data" in resp:
            used_cursor_mode = True
            items = resp.get("data", []) or []
            for it in items:
                addr = (it.get("proxyWallet") or "").lower()
                if addr:
                    traders.add(addr)
                ts = it.get("timestamp")
                if isinstance(ts, (int, float)):
                    if first_ts is None or ts < first_ts:
                        first_ts = ts
                    if last_ts is None or ts > last_ts:
                        last_ts = ts
            total += len(items)
            next_cursor = resp.get("next")
            if not next_cursor or not items:
                break
        else:
            items = resp if isinstance(resp, list) else []
            for it in items:
                addr = (it.get("proxyWallet") or "").lower()
                if addr:
                    traders.add(addr)
                ts = it.get("timestamp")
                if isinstance(ts, (int, float)):
                    if first_ts is None or ts < first_ts:
                        first_ts = ts
                    if last_ts is None or ts > last_ts:
                        last_ts = ts
            total += len(items)
            break

    if not used_cursor_mode:
        offset = total
        while True:
            p = dict(params)
            p["offset"] = offset
            resp = _get_json(URL_TRADES, p)
            items = resp if isinstance(resp, list) else resp.get("data", [])
            if not items:
                break
            for it in items:
                addr = (it.get("proxyWallet") or "").lower()
                if addr:
                    traders.add(addr)
                ts = it.get("timestamp")
                if isinstance(ts, (int, float)):
                    if first_ts is None or ts < first_ts:
                        first_ts = ts
                    if last_ts is None or ts > last_ts:
                        last_ts = ts
            total += len(items)
            if len(items) < DATA_LIMIT:
                break
            offset += DATA_LIMIT

    return {
        "total_trades": total,
        "unique_traders": len(traders),
        "first_trade_ts": first_ts,
        "last_trade_ts": last_ts,
    }

# ---------- Save results ----------
def save_markets_dump_for_tag(tag_id: int, markets: List[Dict[str, Any]], stamp: str) -> Dict[str, str]:
    jsonl_path = f"markets_tag_{tag_id}_{stamp}.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for m in markets:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    csv_path = f"markets_tag_{tag_id}_{stamp}.csv"
    fields = [
        "id","slug","question","category",
        "liquidity","volume",
        "condition_id","conditionId",
        "created_at","updated_at",
        "game_start_time","startDate","endDate",
        "num_traders","total_trades","first_trade_ts","last_trade_ts"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for m in markets:
            row = {
                "id": m.get("id",""),
                "slug": m.get("slug",""),
                "question": m.get("question",""),
                "category": m.get("category",""),
                "liquidity": m.get("liquidity",""),
                "volume": m.get("volume",""),
                "condition_id": m.get("condition_id",""),
                "conditionId": m.get("conditionId",""),
                "created_at": m.get("created_at",""),
                "updated_at": m.get("updated_at",""),
                "game_start_time": m.get("game_start_time",""),
                "startDate": m.get("startDate",""),
                "endDate": m.get("endDate",""),
                "num_traders": m.get("__num_traders",""),
                "total_trades": m.get("__total_trades",""),
                "first_trade_ts": m.get("__first_trade_ts",""),
                "last_trade_ts": m.get("__last_trade_ts",""),
            }
            w.writerow(row)
    return {"jsonl": jsonl_path, "csv": csv_path}

# ---------- Main workflow ----------
try:
    query = input("Enter keyword to search tags (e.g. argentina, soccer, primera): ").strip()
    if not query:
        print("Empty query. Please rerun and enter a word.")
        raise SystemExit

    tags = find_tags_by_query(query)
    print_tags(tags, max_rows=200)

    ids_raw = input("Enter one or more tag_id values separated by commas: ").strip()
    if not ids_raw:
        print("No tag_id provided. Exiting.")
        raise SystemExit
    tag_ids = [int(x.strip()) for x in ids_raw.split(",") if x.strip()]

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    combined_csv_rows: List[Dict[str, Any]] = []
    combined_fields = [
        "tag_id","id","slug","question","category",
        "liquidity","volume",
        "condition_id","conditionId",
        "created_at","updated_at",
        "game_start_time","startDate","endDate",
        "num_traders","total_trades","first_trade_ts","last_trade_ts"
    ]

    for tid in tag_ids:
        print(f"\n==== Processing tag_id={tid} ====")
        print("→ Fetching open markets (Gamma)...")
        open_mk = fetch_markets_by_tag(tid, "false")
        print(f"  Open markets: {len(open_mk)}")
        print("→ Fetching closed markets (Gamma)...")
        closed_mk = fetch_markets_by_tag(tid, "true")
        print(f"  Closed markets: {len(closed_mk)}")

        seen = set()
        all_mk: List[Dict[str, Any]] = []
        for m in open_mk + closed_mk:
            mid = str(m.get("id"))
            if mid not in seen:
                seen.add(mid)
                all_mk.append(m)

        print(f"Total markets for tag {tid}: {len(all_mk)}")

        missing_cond = 0
        for m in all_mk:
            cond = m.get("conditionId") or m.get("condition_id")
            if not cond:
                m["__num_traders"]   = 0
                m["__total_trades"]  = 0
                m["__first_trade_ts"] = ""
                m["__last_trade_ts"]  = ""
                missing_cond += 1
                continue
            try:
                metrics = fetch_trades_metrics(str(cond))
                m["__num_traders"]    = metrics["unique_traders"]
                m["__total_trades"]   = metrics["total_trades"]
                m["__first_trade_ts"] = metrics["first_trade_ts"]
                m["__last_trade_ts"]  = metrics["last_trade_ts"]
            except Exception as e:
                m["__num_traders"]   = ""
                m["__total_trades"]  = ""
                m["__first_trade_ts"] = ""
                m["__last_trade_ts"]  = ""
                print(f"   [warn] conditionId={cond}: {e}")

        if missing_cond:
            print(f"   [i] {missing_cond} markets have no conditionId — trade metrics set to 0/blank.")

        paths = save_markets_dump_for_tag(tid, all_mk, stamp)
        print(f"Files for tag {tid}:")
        print(f"  JSONL: {paths['jsonl']}")
        print(f"  CSV  : {paths['csv']}")

        for m in all_mk:
            combined_csv_rows.append({
                "tag_id": tid,
                "id": m.get("id",""),
                "slug": m.get("slug",""),
                "question": m.get("question",""),
                "category": m.get("category",""),
                "liquidity": m.get("liquidity",""),
                "volume": m.get("volume",""),
                "condition_id": m.get("condition_id",""),
                "conditionId": m.get("conditionId",""),
                "created_at": m.get("created_at",""),
                "updated_at": m.get("updated_at",""),
                "game_start_time": m.get("game_start_time",""),
                "startDate": m.get("startDate",""),
                "endDate": m.get("endDate",""),
                "num_traders": m.get("__num_traders",""),
                "total_trades": m.get("__total_trades",""),
                "first_trade_ts": m.get("__first_trade_ts",""),
                "last_trade_ts": m.get("__last_trade_ts",""),
            })

    combined_path = f"markets_all_selected_tags_{stamp}.csv"
    with open(combined_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=combined_fields)
        w.writeheader()
        for r in combined_csv_rows:
            w.writerow(r)
    print(f"\nCombined CSV for all selected tags saved as: {combined_path}")

except KeyboardInterrupt:
    print("\nStopped by user.", file=sys.stderr)
