"""Download Binance spot daily history without using the current exchange list as the universe."""
import csv
import gzip
import io
import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zipfile import ZipFile

from research.listings import STABLE

HERE = Path(__file__).resolve().parent
START = date(2020, 1, 1)
END = date(2026, 10, 31)
EPOCH = date(1970, 1, 1)
ARCHIVE = "https://data.binance.vision"
BUCKET = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
PREFIX = "data/spot/monthly/klines/"
API_HOSTS = ("https://api.binance.com", "https://data-api.binance.vision")
EXCLUDED = STABLE | {
    "USDT", "USDE", "USDF", "USD1", "BIFIUSD", "USDD", "USDL", "USDQ", "USDG", "USYC",
    "USTC", "USDC", "XUSD", "USD", "NGN", "UAH", "ZAR", "JPY", "PLN", "RUB", "ARS", "MXN",
    "IDRT", "BIDR", "BVND", "VAI", "XAUT", "PAXG", "EURI", "USDP", "AEUR",
}
LEVERAGED = re.compile(r"(?:ADA|AAVE|AXS|BCH|BNB|BTC|DOT|EOS|ETH|FIL|LINK|LTC|MATIC|SUSHI|TRX|UNI|XLM|XRP|XTZ|YFI|1INCH)(?:UP|DOWN|BULL|BEAR)")


def download(url):
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=14) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            wait = exc.headers.get("Retry-After", "")
            time.sleep(min(30, int(wait)) if wait.isdecimal() else (2 + attempt))
        except (URLError, TimeoutError):
            if attempt == 2:
                raise


def list_bucket(prefix, delimiter=False):
    params = {"list-type": 2, "prefix": prefix, "max-keys": 1000}
    if delimiter:
        params["delimiter"] = "/"
    while True:
        root = ElementTree.fromstring(download(f"{BUCKET}?{urlencode(params)}"))
        path = ".//{*}CommonPrefixes/{*}Prefix" if delimiter else ".//{*}Contents/{*}Key"
        yield from (element.text for element in root.findall(path))
        token = root.findtext("{*}NextContinuationToken")
        if not token:
            break
        params["continuation-token"] = token


def symbols():
    result = []
    for key in list_bucket(PREFIX, delimiter=True):
        symbol = key.removeprefix(PREFIX).rstrip("/")
        if symbol.endswith("USDT") and symbol[:-4] not in EXCLUDED and not LEVERAGED.fullmatch(symbol[:-4]):
            result.append(symbol)
    return sorted(set(result))


def millis(day):
    return (day - EPOCH).days * 86_400_000


def normalize(rows):
    bars = {}
    for row in rows:
        if not str(row[0]).isdigit():
            continue
        timestamp = int(row[0])
        if timestamp >= 10**14:
            timestamp //= 1_000
        if timestamp % 86_400_000:
            raise ValueError(f"non-UTC daily interval: {timestamp}")
        day = EPOCH + timedelta(days=timestamp // 86_400_000)
        o, h, low, c = map(float, row[1:5])
        volume, trades = float(row[7]), int(row[8])
        if START <= day <= END and 0 < low <= min(o, c) <= max(o, c) <= h and trades > 0 and volume > 0:
            bars[day.isoformat()] = [o, h, low, c, volume, trades]
    return bars


def from_api(symbol, host):
    rows = []
    cursor = START
    while cursor <= END:
        # 1,000 calendar days per request, disjoint even for sparse/delisted symbols.
        stop = min(cursor + timedelta(days=1000), END + timedelta(days=1))
        params = urlencode({"symbol": symbol, "interval": "1d", "startTime": millis(cursor),
                            "endTime": millis(stop) - 1, "limit": 1000})
        result = json.loads(download(f"{host}/api/v3/klines?{params}"))
        if not isinstance(result, list):
            raise ValueError(f"{symbol}: unexpected response")
        rows.extend(result)
        cursor = stop
    return normalize(rows)


def from_archive(symbol):
    keys = list(list_bucket(f"{PREFIX}{symbol}/1d/"))
    rows = []
    for key in keys:
        if not key.endswith(".zip") or not "2020-01" <= key[-11:-4] <= "2026-10":
            continue
        with ZipFile(io.BytesIO(download(f"{ARCHIVE}/{quote(key)}"))) as archive:
            with archive.open(archive.namelist()[0]) as csvfile:
                rows.extend(csv.reader(io.TextIOWrapper(csvfile, encoding="utf-8")))
    return normalize(rows)


def get_pair(symbol):
    errors = []
    for host in API_HOSTS:
        try:
            series = from_api(symbol, host)
            if series:
                return symbol, series, host
            errors.append("no data in period")
            break
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            errors.append(str(exc))
    try:
        series = from_archive(symbol)
        if series:
            return symbol, series, ARCHIVE
        return symbol, {}, "no archived bars in period"
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        errors.append(str(exc))
        return symbol, {}, "error: " + " | ".join(errors)


def main():
    universe = symbols()
    print(f"Archived USDT symbols in scope: {len(universe)}", flush=True)
    markets, acquisition = {}, {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        tasks = [pool.submit(get_pair, symbol) for symbol in universe]
        for i, future in enumerate(as_completed(tasks), start=1):
            symbol, series, source = future.result()
            acquisition[symbol] = source
            if series:
                markets[symbol] = series
            if i % 100 == 0:
                print(f"Loaded {i}/{len(universe)} symbols", flush=True)
    if "BTCUSDT" not in markets or len(markets) < 200:
        raise RuntimeError("Unexpectedly small archive coverage")
    output = HERE / "spot_inputs.json.gz"
    snapshot = {"start": START.isoformat(), "end": END.isoformat(),
                "universe_source": BUCKET + "?" + urlencode({"list-type": 2, "prefix": PREFIX, "delimiter": "/"}),
                "acquisition": dict(sorted(acquisition.items())), "markets": dict(sorted(markets.items()))}
    payload = json.dumps(snapshot, separators=(",", ":")).encode()
    output.write_bytes(gzip.compress(payload, compresslevel=6, mtime=0))
    print(f"Saved {len(markets)} markets and {sum(map(len, markets.values()))} bars", flush=True)
    print(Counter(acquisition.values()), flush=True)


if __name__ == "__main__":
    main()
