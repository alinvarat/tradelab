"""Probe public announcement and price endpoints from a GitHub runner (the Actions IPs are US based; some venues
refuse them). Prints status and the first bytes of each answer and writes <out>/probe.json. Workflow event_book.yml, mode probe."""
import json
import os
import sys
import time
from urllib.request import Request, urlopen

NOW = int(time.time())
T2025 = 1735689600
URLS = {
    "okx_ann_types": "https://www.okx.com/api/v5/support/announcement-types",
    "okx_ann_listings": "https://www.okx.com/api/v5/support/announcements?annType=announcements-new-listings&page=1",
    "okx_ann_listings_p40": "https://www.okx.com/api/v5/support/announcements?annType=announcements-new-listings&page=40",
    "okx_ann_delist": "https://www.okx.com/api/v5/support/announcements?annType=announcements-delistings&page=1",
    "okx_hist_1m": f"https://www.okx.com/api/v5/market/history-candles?instId=BTC-USDT-SWAP&bar=1m&after={T2025 * 1000}&limit=3",
    "okx_swap_instruments": "https://www.okx.com/api/v5/public/instruments?instType=SWAP",
    "bybit_ann_new": "https://api.bybit.com/v5/announcements/index?locale=en-US&type=new_crypto&limit=5&page=1",
    "bybit_ann_new_p30": "https://api.bybit.com/v5/announcements/index?locale=en-US&type=new_crypto&limit=20&page=30",
    "bybit_ann_delist": "https://api.bybit.com/v5/announcements/index?locale=en-US&type=delistings&limit=5&page=1",
    "bybit_kline_2025": f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval=1&start={T2025 * 1000}&limit=3",
    "bybit_instruments": "https://api.bybit.com/v5/market/instruments-info?category=linear&symbol=BTCUSDT",
    "bybit_tickers": "https://api.bybit.com/v5/market/tickers?category=linear",
    "coinbase_product": "https://api.exchange.coinbase.com/products/BTC-USD",
    "coinbase_brokerage": "https://api.coinbase.com/api/v3/brokerage/market/products?limit=2",
    "coinbase_blog": "https://www.coinbase.com/blog/landing",
    "coinbase_status": "https://status.coinbase.com/api/v2/incidents.json",
    "bithumb_notice_page": "https://feed.bithumb.com/notice",
    "bithumb_ticker": "https://api.bithumb.com/public/ticker/BTC_KRW",
    "kucoin_ann_new": "https://api.kucoin.com/api/v3/announcements?language=en_US&type=new-listings&pageSize=5&currentPage=1",
    "kucoin_ann_new_p20": "https://api.kucoin.com/api/v3/announcements?language=en_US&type=new-listings&pageSize=50&currentPage=20",
    "kucoin_ann_delist": "https://api.kucoin.com/api/v3/announcements?language=en_US&type=delistings&pageSize=5&currentPage=1",
    "kucoin_ann_range": f"https://api.kucoin.com/api/v3/announcements?language=en_US&type=new-listings&pageSize=5&startTime={T2025 * 1000}&endTime={(T2025 + 30 * 86400) * 1000}",
    "bitget_ann_list": "https://api.bitget.com/api/v2/public/annoucements?language=en_US&annType=coin_listings",
    "bitget_ann_delist": "https://api.bitget.com/api/v2/public/annoucements?language=en_US&annType=symbol_delisting",
    "bitget_ann_range": f"https://api.bitget.com/api/v2/public/annoucements?language=en_US&annType=coin_listings&startTime={T2025 * 1000}&endTime={(T2025 + 60 * 86400) * 1000}",
    "binance_vision_um_zip": "https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2025-01.zip",
    "binance_vision_spot_klines": f"https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={T2025 * 1000}&limit=2",
    "binance_fapi_klines": f"https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1m&startTime={T2025 * 1000}&limit=2",
    "binance_notice_funding_catalog": "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId=49&pageNo=1&pageSize=5",
    "binance_notice_catalog_161": "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId=161&pageNo=1&pageSize=3",
    "geckoterminal_pools": "https://api.geckoterminal.com/api/v2/networks/eth/trending_pools",
    "upbit_notices": "https://api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=3&category=trade",
}


def hit(name, url):
    t0 = time.time()
    try:
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0 tradelab-research"}), timeout=25) as r:
            body = r.read(400000)
            return {"status": r.status, "bytes": len(body), "head": body[:350].decode("utf-8", "replace"),
                    "seconds": round(time.time() - t0, 2)}
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", None)
        head = ""
        try:
            head = e.read(200).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
        return {"status": code, "error": repr(e)[:150], "head": head, "seconds": round(time.time() - t0, 2)}


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    res = {}
    for k, u in URLS.items():
        res[k] = hit(k, u)
        print(k, res[k].get("status"), res[k].get("bytes"), res[k]["head"][:160].replace("\n", " "), flush=True)
    with open(os.path.join(out, "probe.json"), "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
