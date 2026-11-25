"""Read any data.binance.vision bulk zip (spot or futures/um, monthly or daily) and list every symbol ever listed.

Contract for every fetch: a parsed list on success, [] when the file is a 404 (no data for that symbol/date: not listed
yet, delisted, or not published), None when every retry failed (count it as a gap, never as "no data").
Header rows are skipped; millisecond and microsecond timestamps (spot files from 2025 use microseconds) become seconds.
Pass `period` explicitly: fundingRate exists monthly only, metrics daily only, and the current month has only daily
files. Runs on GitHub Actions only (AGENTS.md rule 3).

    vision_url(market, period, kind, symbol, date, interval=None)
    fetch(market, period, kind, symbol, date, interval=None, parse=None) -> list | [] | None
    iter_file(market, period, kind, symbol, date, interval=None, parse=None) -> iterator | [] | None   (aggTrades)
    series(market, kind, symbol, start_s, end_s, interval=None, period="monthly", parse=None) -> (rows, failed_dates)
    klines / funding / metrics / premium_index / mark_price: series() with the right parser
    list_symbols(market="spot", quote="USDT") -> sorted symbols that ever had monthly klines
"""
import calendar
import io
import re
import shutil
import tempfile
import time
import zipfile
from datetime import datetime, timezone

BASE = "https://data.binance.vision/data"
LISTING = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
UA = {"User-Agent": "Mozilla/5.0 tradelab-research"}
MARKETS = ("spot", "futures/um")
PERIODS = ("monthly", "daily")
INTERVAL_KINDS = ("klines", "premiumIndexKlines", "markPriceKlines", "indexPriceKlines")
PLAIN_KINDS = ("fundingRate", "metrics", "aggTrades", "trades", "bookTicker", "BVOLIndex")


def _date_str(period, date):
    """'YYYY-MM' (monthly) or 'YYYY-MM-DD' (daily) from a string, (y, m[, d]) tuple or epoch seconds."""
    if isinstance(date, (int, float)):
        t = time.gmtime(date)
        date = (t.tm_year, t.tm_mon, t.tm_mday)
    if isinstance(date, tuple):
        date = f"{date[0]:04d}-{date[1]:02d}" + (f"-{date[2]:02d}" if period == "daily" else "")
    want = r"\d{4}-\d{2}" if period == "monthly" else r"\d{4}-\d{2}-\d{2}"
    if not re.fullmatch(want, date):
        raise ValueError(f"{period} date must look like {'YYYY-MM' if period == 'monthly' else 'YYYY-MM-DD'}: {date}")
    return date


def vision_url(market, period, kind, symbol, date, interval=None):
    if market not in MARKETS:
        raise ValueError(f"market must be one of {MARKETS}")
    if period not in PERIODS:
        raise ValueError(f"period must be one of {PERIODS}")
    if not re.fullmatch(r"[A-Z0-9_]+", symbol or ""):
        raise ValueError(f"bad symbol {symbol!r}")
    d = _date_str(period, date)
    if kind in INTERVAL_KINDS:
        if not interval:
            raise ValueError(f"{kind} needs an interval")
        return f"{BASE}/{market}/{period}/{kind}/{symbol}/{interval}/{symbol}-{interval}-{d}.zip"
    if not re.fullmatch(r"[A-Za-z]+", kind or ""):
        raise ValueError(f"bad kind {kind!r}")
    return f"{BASE}/{market}/{period}/{kind}/{symbol}/{symbol}-{kind}-{d}.zip"


def to_seconds(t):
    """Epoch ms or us (int or numeric string) -> float seconds."""
    t = int(float(t))
    return t / 1e6 if t > 10**14 else t / 1e3


def is_header(fields):
    return bool(fields) and bool(re.fullmatch(r"[A-Za-z_ ]+", fields[0].strip()))


def _num(x):
    x = x.strip()
    return float(x) if x else None


def parse_kline(f):
    """klines / premiumIndexKlines / markPriceKlines / indexPriceKlines row ->
    (open_s, open, high, low, close, volume, close_s, quote_volume, trades, taker_buy_base, taker_buy_quote)."""
    return (int(to_seconds(f[0])), float(f[1]), float(f[2]), float(f[3]), float(f[4]), float(f[5]),
            int(to_seconds(f[6])), float(f[7]), int(float(f[8])), float(f[9]), float(f[10]))


def parse_funding(f):
    """futures/um fundingRate (calc_time, funding_interval_hours, last_funding_rate) -> (ts_s, rate)."""
    return (to_seconds(f[0]), float(f[-1]))


METRIC_FIELDS = ("sum_open_interest", "sum_open_interest_value", "count_toptrader_long_short_ratio",
                 "sum_toptrader_long_short_ratio", "count_long_short_ratio", "sum_taker_long_short_vol_ratio")


def parse_metrics(f):
    """futures/um metrics (create_time 'YYYY-MM-DD HH:MM:SS' UTC, symbol, six numbers) -> dict with ts (seconds)."""
    t = f[0].strip()
    ts = to_seconds(t) if t.isdigit() else calendar.timegm(datetime.strptime(t, "%Y-%m-%d %H:%M:%S").timetuple())
    out = {"ts": float(ts), "symbol": f[1].strip()}
    out.update({k: _num(v) for k, v in zip(METRIC_FIELDS, f[2:])})
    return out


def parse_aggtrade(f):
    """aggTrades row (spot or futures: agg id, price, qty, first id, last id, time, is_buyer_maker[, best match]) ->
    (ts_s, price, qty, buyer_is_maker). Spot writes True/False capitalised, futures true/false."""
    return (to_seconds(f[5]), float(f[1]), float(f[2]), f[6].strip().lower() == "true")


def parse_raw(f):
    return f


def _download(url, tries, timeout, opener, sleep):
    """('ok', seekable file) | ('missing', None) on 404 | ('failed', None) after `tries` attempts."""
    if opener is None:
        from urllib.request import Request, urlopen
        opener = lambda u, t: urlopen(Request(u, headers=UA), timeout=t)  # noqa: E731
    for k in range(tries):
        try:
            buf = tempfile.SpooledTemporaryFile(max_size=64 << 20)
            with opener(url, timeout) as r:
                shutil.copyfileobj(r, buf)
            buf.seek(0)
            zipfile.ZipFile(buf).testzip()
            buf.seek(0)
            return "ok", buf
        except Exception as e:  # noqa: BLE001
            if getattr(e, "code", None) == 404:
                return "missing", None
            if k + 1 < tries:
                sleep(2 * (k + 1))
    return "failed", None


def _lines(buf, parse):
    with zipfile.ZipFile(buf) as z:
        for name in z.namelist():
            if not name.endswith(".csv"):
                continue
            with z.open(name) as fh:
                for line in io.TextIOWrapper(fh, encoding="utf-8", newline=""):
                    fields = line.rstrip("\r\n").split(",")
                    if not line.strip() or is_header(fields):
                        continue
                    yield parse(fields)
    buf.close()


def iter_file(market, period, kind, symbol, date, interval=None, parse=None, tries=4, timeout=60, opener=None,
              sleep=time.sleep):
    """Download one zip, then stream its parsed rows (for large files such as aggTrades). [] on 404, None on failure."""
    status, buf = _download(vision_url(market, period, kind, symbol, date, interval), tries, timeout, opener, sleep)
    if status == "missing":
        return []
    if status == "failed":
        return None
    return _lines(buf, parse or parse_raw)


def fetch(market, period, kind, symbol, date, interval=None, parse=None, **kw):
    """One zip as a list of parsed rows (default: raw string fields). [] on 404, None after retries failed."""
    it = iter_file(market, period, kind, symbol, date, interval, parse, **kw)
    return it if it is None or it == [] else list(it)


def months(start_s, end_s):
    """(y, m) of every month that overlaps [start_s, end_s)."""
    a, b = time.gmtime(start_s), time.gmtime(end_s - 1)
    y, m, out = a.tm_year, a.tm_mon, []
    while (y, m) <= (b.tm_year, b.tm_mon):
        out.append((y, m))
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    return out


def days(start_s, end_s):
    """(y, m, d) of every UTC day that overlaps [start_s, end_s)."""
    t = int(start_s) - int(start_s) % 86400
    out = []
    while t < end_s:
        g = time.gmtime(t)
        out.append((g.tm_year, g.tm_mon, g.tm_mday))
        t += 86400
    return out


def _ts(row):
    if isinstance(row, dict):
        return row["ts"]
    return row[0] if isinstance(row[0], (int, float)) else to_seconds(row[0])


def series(market, kind, symbol, start_s, end_s, interval=None, period="monthly", parse=None, **kw):
    """Every file of one symbol over [start_s, end_s). Returns (rows sorted and de-duplicated by timestamp, kept only
    inside the window, failed_dates). Missing files (404) are skipped; failed ones are listed so callers count gaps."""
    dates = months(start_s, end_s) if period == "monthly" else days(start_s, end_s)
    rows, failed = {}, []
    for d in dates:
        got = fetch(market, period, kind, symbol, d, interval, parse, **kw)
        if got is None:
            failed.append(_date_str(period, d))
            continue
        for r in got:
            rows[_ts(r)] = r
    return [rows[t] for t in sorted(rows) if start_s <= t < end_s], failed


def klines(symbol, start_s, end_s, interval="1d", market="spot", period="monthly", **kw):
    return series(market, "klines", symbol, start_s, end_s, interval, period, parse_kline, **kw)


def premium_index(symbol, start_s, end_s, interval="1h", period="monthly", **kw):
    return series("futures/um", "premiumIndexKlines", symbol, start_s, end_s, interval, period, parse_kline, **kw)


def mark_price(symbol, start_s, end_s, interval="1h", period="monthly", **kw):
    return series("futures/um", "markPriceKlines", symbol, start_s, end_s, interval, period, parse_kline, **kw)


def funding(symbol, start_s, end_s, **kw):
    """Settled funding of a USDT perp; fundingRate is published monthly only."""
    return series("futures/um", "fundingRate", symbol, start_s, end_s, None, "monthly", parse_funding, **kw)


def metrics(symbol, start_s, end_s, **kw):
    """Open interest and long/short ratios (5-minute rows); metrics are published daily only."""
    return series("futures/um", "metrics", symbol, start_s, end_s, None, "daily", parse_metrics, **kw)


def parse_listing(xml, prefix):
    """Names directly under `prefix` in one S3 listing page, and the next marker (None when the listing is complete)."""
    names = re.findall(r"<Prefix>%s([A-Z0-9_]+)/</Prefix>" % re.escape(prefix), xml)
    nxt = re.search(r"<NextMarker>([^<]+)</NextMarker>", xml)
    more = "<IsTruncated>true</IsTruncated>" in xml
    return names, (nxt.group(1) if more and nxt else None)


def list_symbols(market="spot", quote="USDT", kind="klines", period="monthly", tries=4, timeout=60, opener=None,
                 sleep=time.sleep):
    """Every symbol that ever had a file of `kind` (delisted ones included), filtered by quote suffix.
    Raises RuntimeError if a page fails after retries: a partial universe would bias the study."""
    if opener is None:
        from urllib.request import Request, urlopen
        opener = lambda u, t: urlopen(Request(u, headers=UA), timeout=t)  # noqa: E731
    prefix = f"data/{market}/{period}/{kind}/"
    out, marker = [], ""
    for _ in range(500):
        url = f"{LISTING}?delimiter=/&prefix={prefix}" + (f"&marker={marker}" if marker else "")
        for k in range(tries):
            try:
                with opener(url, timeout) as r:
                    xml = r.read().decode()
                break
            except Exception as e:  # noqa: BLE001
                if k + 1 == tries:
                    raise RuntimeError(f"S3 listing failed for {prefix} after {tries} tries") from e
                sleep(2 * (k + 1))
        names, marker = parse_listing(xml, prefix)
        out += [n for n in names if n.endswith(quote)]
        if not marker:
            break
    return sorted(set(out))


def utc(y, m=1, d=1):
    return datetime(y, m, d, tzinfo=timezone.utc).timestamp()
