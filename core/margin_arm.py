"""L1f margin arm (protocol research/studies/protocol_l1f_margin_arm_20261127.md): paper short of a Binance delist-notice coin through
cross margin, priced on Binance spot, with the borrow cost MEASURED from Binance's public margin data at the notice and at the exit.
Pure functions plus thin network readers; no API key (the signed margin endpoints are never used). Called by core/market_collect.py."""
import math

SPEC_URL = "https://www.binance.com/bapi/margin/v1/friendly/margin/vip/spec/list-all"
FAPI_BOOK = "https://fapi.binance.com/fapi/v1/ticker/bookTicker?symbol="
SPOT_BOOK = "https://api.binance.com/api/v3/ticker/bookTicker?symbol="
PERP_PREFIXES = ("", "1000", "1000000")
HEARTBEAT_S = 30 * 60


def spec_rows(doc) -> dict:
    """vip/spec/list-all answer -> {asset: {'daily_rate': VIP 0 daily interest (fraction), 'limit': VIP 0 borrow limit in coins}}.
    The list holds the assets that are borrowable TODAY; an asset that is absent is not borrowable now."""
    out = {}
    for a in ((doc or {}).get("data") or []):
        for s in a.get("specs") or []:
            if str(s.get("vipLevel")) == "0":
                try:
                    out[a["assetName"]] = {"daily_rate": float(s["dailyInterestRate"]), "limit": float(s["borrowLimit"])}
                except (KeyError, TypeError, ValueError):
                    pass
    return out


def snapshot(rows: dict, coin: str, now: float) -> dict:
    """What the public margin data says about `coin` at `now`: borrowable (listed in the spec list), daily rate, limit."""
    r = rows.get(coin)
    return {"t": round(now, 1), "borrowable": r is not None, "daily_rate": r and r["daily_rate"], "limit": r and r["limit"],
            "assets_listed": len(rows)}


def borrow_cost(daily_rates, held_s: float) -> float:
    """Cost fraction of notional for a short held `held_s`: the mean of the measured daily rates (entry, exit) x the hours charged / 24.
    Binance accrues interest per started hour, so the hours are ceil(held) + 1 (an entry and an exit that straddle hour marks)."""
    r = [x for x in daily_rates if x is not None]
    if not r:
        return 0.0
    hours = math.ceil(held_s / 3600) + 1
    return sum(r) / len(r) * hours / 24


def limit_ok(snap: dict, stake_usd: float, price: float) -> bool:
    """The borrow limit (coins) covers the stake at the entry price."""
    return bool(snap.get("borrowable")) and (snap.get("limit") or 0) * price >= stake_usd


def has_perp(get, coin: str):
    """True/False/None: a Binance USDT-M perp exists now for the coin (symbol, 1000 or 1000000 prefix); None when every call failed."""
    failed = 0
    for p in PERP_PREFIXES:
        try:
            d = get(FAPI_BOOK + f"{p}{coin}USDT")
            if d.get("bidPrice"):
                return True
        except Exception as e:  # noqa: BLE001  an HTTP 400 means no such symbol; anything else is a failure
            if getattr(e, "code", None) != 400:
                failed += 1
    return None if failed == len(PERP_PREFIXES) else False


def binance_quote(get, coin: str):
    """('binance', bid, ask) of COINUSDT on Binance spot (the book the margin short trades on), or None."""
    try:
        d = get(SPOT_BOOK + f"{coin}USDT")
        if d.get("bidPrice") and float(d["bidPrice"]) > 0 and float(d["askPrice"]) > 0:
            return "binance", float(d["bidPrice"]), float(d["askPrice"])
    except Exception:  # noqa: BLE001
        pass
    return None


def heartbeat(now: float, st: dict, extra=None) -> dict:
    return {"type": "heartbeat", "t": round(now, 1), "pending": len(st["pending"]), "closed": len(st["closed"]),
            "traded": sum(1 for c in st["closed"] if "net" in c), "equity": st["equity"], **(extra or {})}
