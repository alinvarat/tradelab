"""Family 5 data layer: Dukascopy bi5 downloads (1m BID/ASK candles, hourly ticks) and the compact on-disk format.
Network helpers run on GitHub Actions only. Dukascopy answers 503 / timeouts under load, so every request retries with backoff
and a day is only written when BOTH sides came back (200 with data, or 404 / empty body = the market was closed)."""
import gzip
import lzma
import os
import struct
import sys
import time
from datetime import date as _date, datetime, timedelta, timezone
from urllib.request import Request, urlopen

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) tradelab-research", "Accept": "*/*"}
DIV = {"XAUUSD": 1000.0, "USDJPY": 1000.0}          # price integer divisor (everything else 1e5)
CAN = struct.Struct(">IIIIIf")                       # seconds in UTC day, open, close, low, high, volume
TIK = struct.Struct(">IIIff")                        # ms in hour, ask, bid, ask vol, bid vol
REC = struct.Struct("<9I")                           # ts, bid o h l c, ask o h l c (integers)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(url, tries=6, timeout=25):
    """(status, body): 200 body, 404 / 200-empty means no data (closed market) -> (404, b''); None status = gave up."""
    last = None
    for k in range(tries):
        try:
            with urlopen(Request(url, headers=UA), timeout=timeout) as r:
                return r.status, r.read()
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            if code == 404:
                return 404, b""
            last = code or type(e).__name__
            time.sleep(min(30, 1.5 * 2 ** k) + 0.1 * k)
    return None, str(last).encode()


def url(sym, d, what):
    return f"https://datafeed.dukascopy.com/datafeed/{sym}/{d.year}/{d.month - 1:02d}/{d.day:02d}/{what}"


def parse_candles(body):
    raw = lzma.decompress(body)
    return [CAN.unpack(raw[i:i + 24]) for i in range(0, len(raw) - 23, 24)]


def fetch_day(sym, d):
    """-> (packed bytes, status) ; status 'ok' | 'closed' | 'fail'."""
    out = {}
    for side in ("BID", "ASK"):
        st, body = get(url(sym, d, f"{side}_candles_min_1.bi5"))
        if st is None:
            return b"", "fail"
        if st == 404 or not body:
            out[side] = []
        else:
            try:
                out[side] = parse_candles(body)
            except Exception:  # noqa: BLE001
                return b"", "fail"
    day0 = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())
    ask = {r[0]: r for r in out["ASK"]}
    recs = []
    for r in out["BID"]:
        a = ask.get(r[0])
        if a:
            recs.append(REC.pack(day0 + r[0], r[1], r[4], r[3], r[2], a[1], a[4], a[3], a[2]))
    return b"".join(recs), ("ok" if recs else "closed")


def fetch_year_file(sym, year, path, workers=4, start=None, end=None):
    """Download every weekday of `year` (UTC) for sym into one gzip file; returns dict(days, ok, closed, fail)."""
    from concurrent.futures import ThreadPoolExecutor
    d0, d1 = _date(year, 1, 1), _date(year, 12, 31)
    days = []
    d = d0
    while d <= d1:
        if d.weekday() < 5 or (d.weekday() == 6):      # Sunday evening sessions open at 21:00-22:00 UTC
            if (start is None or d >= start) and (end is None or d <= end):
                days.append(d)
        d += timedelta(days=1)
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(lambda x: fetch_day(sym, x), days))
    for k, (d, (b, st)) in enumerate(zip(days, res)):          # second pass, one at a time, for days that gave up
        if st == "fail":
            res[k] = fetch_day(sym, d)
    n = {"days": len(days), "ok": 0, "closed": 0, "fail": 0, "failed_days": []}
    buf = []
    for d, (b, st) in zip(days, res):
        n[st] += 1
        if st == "fail":
            n["failed_days"].append(d.isoformat())
        buf.append(b)
    with gzip.open(path, "wb", 6) as f:
        f.write(b"".join(buf))
    return n


def fetch_ticks_window(sym, t0, before=120, after=1200):
    """Per-second (bid, ask) series from [t0-before, t0+after] built from hourly tick files, forward filled.
    Returns (list of [dt, bid, ask] for dt in -before..after, status). Ticks carry the exact bid and ask."""
    dv = DIV.get(sym, 1e5)
    a, b = t0 - before, t0 + after
    hours = sorted({int(a // 3600) * 3600, int(b // 3600) * 3600})
    ticks = []
    for h in hours:
        dt = datetime.fromtimestamp(h, timezone.utc)
        st, body = get(f"https://datafeed.dukascopy.com/datafeed/{sym}/{dt.year}/{dt.month - 1:02d}/{dt.day:02d}/{dt.hour:02d}h_ticks.bi5")
        if st is None:
            return None, "fail"
        if st == 404 or not body:
            continue
        try:
            raw = lzma.decompress(body)
        except Exception:  # noqa: BLE001
            return None, "fail"
        for i in range(0, len(raw) - 19, 20):
            ms, ask, bid, _, _ = TIK.unpack(raw[i:i + 20])
            ticks.append((h + ms / 1000.0, bid / dv, ask / dv))
    if not ticks:
        return None, "closed"
    ticks.sort()
    out, k, last = [], 0, None
    n = len(ticks)
    while k < n and ticks[k][0] < a:
        last = ticks[k]
        k += 1
    for dtc in range(-before, after + 1):
        tt = t0 + dtc + 1.0                       # second bucket [t0+dtc, t0+dtc+1): value = last tick before its end
        while k < n and ticks[k][0] < tt:
            last = ticks[k]
            k += 1
        out.append([dtc, last[1], last[2]] if last else [dtc, None, None])
    return out, "ok"


def load_bars(paths, sym):
    """Concatenate year files -> dict of array('d') columns + array('q') ts, sorted, crossed/zero quotes dropped."""
    from array import array
    dv = DIV.get(sym, 1e5)
    cols = ("ts", "bo", "bh", "bl", "bc", "ao", "ah", "al", "ac")
    D = {"ts": array("q")}
    for c in cols[1:]:
        D[c] = array("d")
    bad = 0
    last = 0
    for p in sorted(paths):
        with gzip.open(p, "rb") as f:
            data = f.read()
        for r in REC.iter_unpack(data):
            if r[0] <= last or r[1] == 0 or r[5] == 0 or r[5] < r[1] * 0 or r[8] < r[4]:
                bad += 1
                continue
            last = r[0]
            D["ts"].append(r[0])
            for c, v in zip(cols[1:], r[1:]):
                D[c].append(v / dv)
    D["bad"] = bad
    return D
