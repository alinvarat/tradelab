"""Tiny reachability probe for the forward crypto-spike test: which public market-data hosts answer from this machine
(GitHub Actions runners are often geo-blocked, e.g. Binance fapi returns 451). Prints one line per endpoint."""
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) tradelab-research", "Accept": "application/json"}
URLS = {
    "binance_fapi_info": "https://fapi.binance.com/fapi/v1/exchangeInfo",
    "binance_fapi_funding": "https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=3",
    "binance_spot_klines": "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=3",
    "vision_spot_klines": "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=3",
    "vision_spot_info": "https://data-api.binance.vision/api/v3/exchangeInfo?symbol=BTCUSDT",
    "bybit_linear_info": "https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000",
    "bybit_funding": "https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=3",
    "okx_swap_info": "https://www.okx.com/api/v5/public/instruments?instType=SWAP",
    "okx_funding_hist": "https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=3",
}


def main():
    for name, url in URLS.items():
        t = time.time()
        try:
            with urlopen(Request(url, headers=UA), timeout=20) as r:
                body = r.read()
                print(f"{name}: {r.status} {len(body)}B {time.time() - t:.1f}s {body[:90]!r}")
        except HTTPError as e:
            print(f"{name}: HTTP {e.code}")
        except Exception as e:   # noqa: BLE001
            print(f"{name}: ERR {type(e).__name__} {e}")


if __name__ == "__main__":
    main()
