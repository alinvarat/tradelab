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


def fetch_range(sym, start, end, path, workers=6, daydir=None):
    """Download every Mon-Fri and Sunday (UTC) from start to end (dates, inclusive) into one gzip file; returns dict(days, ok, closed, fail)."""
    from concurrent.futures import ThreadPoolExecutor
    days = []
    d = start
    while d <= end:
        if d.weekday() != 5:                           # Sunday evening sessions open at 21:00-22:00 UTC
            days.append(d)
        d += timedelta(days=1)
    t0, done = time.time(), [0]

    def one(x):
        dp = os.path.join(daydir, f"{sym}_{x.isoformat()}.bin") if daydir else None
        if dp and os.path.exists(dp):                  # finished earlier (cache of a failed or cancelled job): reuse
            b = open(dp, "rb").read()
            r = (b, "ok" if b else "closed")
        else:
            r = fetch_day(sym, x)
            if dp and r[1] != "fail":
                os.makedirs(daydir, exist_ok=True)
                open(dp, "wb").write(r[0])
        done[0] += 1
        if done[0] % 10 == 0 or done[0] == len(days):
            log(f"{sym} {start}..{end}: {done[0]}/{len(days)} days, {time.time() - t0:.0f}s, last status {r[1]}")
        return r
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(one, days))
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


def fetch_year_file(sym, year, path, workers=3, start=None, end=None):
    return fetch_range(sym, start or _date(year, 1, 1), end or _date(year, 12, 31), path, workers)


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


# ------------------------------------------------------------------ HistData.com source (tick quotes -> 1m bid/ask bars)
HD_BASE = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/tick-data-quotes/"
HD_EST_TO_UTC = 5 * 3600                  # HistData stamps are EST without DST (UTC-5 all year)


def hd_month(sym, y, m, tries=4):
    """-> (REC bytes of 1-minute bid/ask bars for the month, status 'ok' | 'closed' | 'fail'). Built from the free tick-quote file
    (bid, ask, ms stamps): one zip per month, form token scraped from the page. 'closed' = the page has no file (month not released)."""
    import io
    import re
    import zipfile
    from urllib.parse import urlencode
    page = f"{HD_BASE}{sym.lower()}/{y}/{m}"
    dv = DIV.get(sym, 1e5)
    for k in range(tries):
        try:
            with urlopen(Request(page, headers=UA), timeout=60) as r:
                t = r.read().decode("utf8", "replace")
            form = {}
            for nm in ("tk", "date", "datemonth", "platform", "timeframe", "fxpair"):
                mm = re.search(r'name="%s" id="%s" value="([^"]*)"' % (nm, nm), t)
                form[nm] = mm.group(1) if mm else ""
            if not form["tk"]:
                return b"", "closed"
            hdr = dict(UA)
            hdr.update({"Referer": page, "Content-Type": "application/x-www-form-urlencoded"})
            with urlopen(Request("https://www.histdata.com/get.php", data=urlencode(form).encode(), headers=hdr), timeout=300) as r:
                zbytes = r.read()
            z = zipfile.ZipFile(io.BytesIO(zbytes))
            name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
            out, bases = [], {}
            cur = None
            bo = bh = bl = bc = ao = ah = al = ac = 0
            with z.open(name) as f:
                for line in f:
                    p = line.split(b",")
                    if len(p) < 3:
                        continue
                    s = p[0]
                    ds = s[:8]
                    base = bases.get(ds)
                    if base is None:
                        base = bases[ds] = int(datetime(int(ds[:4]), int(ds[4:6]), int(ds[6:8]), tzinfo=timezone.utc).timestamp())
                    mn = base + int(s[9:11]) * 3600 + int(s[11:13]) * 60 + HD_EST_TO_UTC
                    bid, ask = float(p[1]), float(p[2])
                    if bid <= 0 or ask < bid:
                        continue
                    if mn != cur:
                        if cur is not None:
                            out.append(REC.pack(cur, round(bo * dv), round(bh * dv), round(bl * dv), round(bc * dv),
                                                round(ao * dv), round(ah * dv), round(al * dv), round(ac * dv)))
                        cur, bo, bh, bl, bc, ao, ah, al, ac = mn, bid, bid, bid, bid, ask, ask, ask, ask
                    else:
                        bh, bl, bc = max(bh, bid), min(bl, bid), bid
                        ah, al, ac = max(ah, ask), min(al, ask), ask
            if cur is not None:
                out.append(REC.pack(cur, round(bo * dv), round(bh * dv), round(bl * dv), round(bc * dv),
                                    round(ao * dv), round(ah * dv), round(al * dv), round(ac * dv)))
            return b"".join(out), ("ok" if out else "closed")
        except Exception as e:  # noqa: BLE001
            log("hd_month", sym, y, m, "try", k, type(e).__name__, str(e)[:100])
            time.sleep(5 * (k + 1))
    return b"", "fail"


def fetch_range_hd(sym, start, end, path, workers=2):
    """Chunk of whole months from HistData (the months touching [start, end]); rows are sorted by minute; same file format as fetch_range."""
    from concurrent.futures import ThreadPoolExecutor
    months, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(lambda ym: hd_month(sym, *ym), months))
    n = {"days": len(months), "ok": 0, "closed": 0, "fail": 0, "failed_days": []}
    buf = []
    for ym, (b, st) in zip(months, res):
        n[st] += 1
        if st == "fail":
            n["failed_days"].append("%d-%02d" % ym)
        buf.append(b)
        log(sym, ym, st, len(b) // REC.size, "bars")
    with gzip.open(path, "wb", 6) as f:
        f.write(b"".join(buf))
    return n
