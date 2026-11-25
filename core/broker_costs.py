"""Broker cost models (pure functions, no network). Sources, dates and which numbers are ESTIMATES: research/brokers/costs.md.

Simulated money only. Nothing here talks to a broker.

    webull_option_cost(contracts, side, premium=None)  -> USD for one US equity-option order (Webull)
    xm_cfd_cost(symbol, size, account, nights, ...)     -> breakdown of the cost of one XM MT5 CFD round trip
    xm_cfd_cost_fraction(symbol, account, price, nights) -> same, as a fraction of notional

Every number below marked EST is not confirmed from an official page; change it only together with costs.md.
"""

# ------------------------------------------------------------------ Webull (US options, per contract)
WEBULL_COMMISSION = 0.0        # Webull page 2026-11-25: no commission on US-listed stock/ETF options
WEBULL_ORF = 0.02685           # EST: options regulatory fee, buys and sells (Webull FAQ 2026-11-25; other copies 0.02675-0.02695)
WEBULL_OCC = 0.025             # EST: OCC clearing, buys and sells (third-party copies of the Webull schedule)
WEBULL_CAT = 0.000003          # Webull pricing page 2026-11-25: CAT fee, buys and sells, per unit of volume
WEBULL_SEC_RATE = 0.0000206    # Webull pricing page 2026-11-25: SEC fee on sale proceeds (USD), sells only
WEBULL_FINRA_TAF = 0.00279     # EST: FINRA TAF per contract sold, capped per trade below (not itemised on the page)
WEBULL_FINRA_TAF_CAP = 8.38    # EST
WEBULL_OVERSIZE_FROM = 500     # "all option orders above 500 contracts" (webull.com/options 2026-11-25)
WEBULL_OVERSIZE_FEE = 0.10     # per contract, orders above 500 contracts


def webull_option_cost(contracts, side, premium=None):
    """USD fees for one US equity-option order on Webull. side 'buy' or 'sell'.

    premium: option price per share (USD), only needed for the SEC fee on a sell (rate x proceeds); when None the
    SEC part is left out and the result is a floor. Excludes the bid/ask spread. Index options ($0.50/contract) are
    not covered: this module is for single-stock options."""
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
    if contracts < 0:
        raise ValueError("contracts must be >= 0")
    n = contracts
    fee = n * (WEBULL_COMMISSION + WEBULL_ORF + WEBULL_OCC + WEBULL_CAT)
    if n > WEBULL_OVERSIZE_FROM:
        fee += n * WEBULL_OVERSIZE_FEE
    if side == "sell":
        fee += min(WEBULL_FINRA_TAF * n, WEBULL_FINRA_TAF_CAP)
        if premium is not None:
            fee += WEBULL_SEC_RATE * premium * 100 * n
    return fee


# ------------------------------------------------------------------ XM MT5 CFDs
# Typical (average) spread in PRICE units and contract size per 1.00 lot. Pip rows: EURUSD-type 0.0001, USDJPY 0.01.
# Sourced: EURUSD Standard avg 2.0 pips / Ultra Low from 0.8 (fxrecap 2026-09-30); USDJPY Standard from 2 (tradergulf
# 2026-11-19); Zero EURUSD about 0.1 avg (tradelytic 2026-09-07); silver 0.025 (brokerchooser 2026-05-06, account not
# stated). Everything else EST (no XM page could be read: xm.com answers 403 to automated clients). Gold: pips taken as
# 0.10 USD (EST). Re-measure on an XM demo MT5 before treating these as costs.
XM_SPREAD = {                      # symbol: {account: spread in price units}
    "EURUSD": {"standard": 0.00020, "ultralow": 0.00010, "zero": 0.00001},
    "GBPUSD": {"standard": 0.00025, "ultralow": 0.00013, "zero": 0.00003},   # EST
    "USDJPY": {"standard": 0.020, "ultralow": 0.010, "zero": 0.002},         # EST except Standard
    "AUDUSD": {"standard": 0.00025, "ultralow": 0.00013, "zero": 0.00003},   # EST
    "XAUUSD": {"standard": 0.55, "ultralow": 0.30, "zero": 0.10},            # EST (5.5 / 3.0 pips of 0.10)
    "XAGUSD": {"standard": 0.030, "ultralow": 0.025, "zero": 0.010},         # EST
    "WTI": {"standard": 0.05, "ultralow": 0.04, "zero": 0.02},               # EST
    "BRENT": {"standard": 0.05, "ultralow": 0.04, "zero": 0.02},             # EST
    "NATGAS": {"standard": 0.008, "ultralow": 0.006, "zero": 0.003},         # EST
    "COPPER": {"standard": 0.004, "ultralow": 0.003, "zero": 0.0015},        # EST
}
XM_CONTRACT = {"EURUSD": 100_000, "GBPUSD": 100_000, "USDJPY": 100_000, "AUDUSD": 100_000, "XAUUSD": 100,
               "XAGUSD": 5_000, "WTI": 1_000, "BRENT": 1_000, "NATGAS": 10_000, "COPPER": 25_000}   # units per lot, EST
XM_ZERO_COMMISSION_SIDE_LOT = 3.50     # USD per lot per side ($7 round turn); third-party sources, Zero availability unverified
XM_SWAP_ANNUAL = 0.03                  # EST: financing cost as a fraction of notional per year (cost only, no carry credit)
XM_MIN_LOT = 0.01                      # EST (micro: 1,000 units)
XM_LEVERAGE_MAX = 1000                 # third-party; EU (CySEC) entity capped lower (1:30 on major FX)
ACCOUNTS = ("standard", "ultralow", "zero")
ALIASES = {"XAUUSD=X": "XAUUSD", "GOLD": "XAUUSD", "GC=F": "XAUUSD", "SILVER": "XAGUSD", "SI=F": "XAGUSD",
           "CL=F": "WTI", "OIL": "WTI", "BZ=F": "BRENT", "NG=F": "NATGAS", "HG=F": "COPPER",
           "EURUSD=X": "EURUSD", "GBPUSD=X": "GBPUSD", "USDJPY=X": "USDJPY", "AUDUSD=X": "AUDUSD"}


def _norm(symbol, account):
    sym = ALIASES.get(str(symbol).upper(), str(symbol).upper())
    acct = str(account).lower().replace(" ", "").replace("_", "").replace("-", "")
    if sym not in XM_SPREAD:
        raise KeyError(f"no XM cost row for {symbol!r}")
    if acct not in ACCOUNTS:
        raise KeyError(f"unknown XM account {account!r}; use one of {ACCOUNTS}")
    return sym, acct


def xm_cfd_cost_fraction(symbol, account, price, nights=0, swap_annual=None, mult=1.0, commission_lot_side=None):
    """Round-trip cost as a fraction of notional: full spread / price + commission + financing for `nights`.

    Per-side trading cost (what a backtest charges on entry and on exit) is trade_per_side. mult scales spread and
    swap (2.0 for the pre-registered 2x stress). The Zero commission is converted with the notional of one lot."""
    sym, acct = _norm(symbol, account)
    if price <= 0:
        raise ValueError("price must be > 0")
    spread = XM_SPREAD[sym][acct] / price * mult
    notional_lot = XM_CONTRACT[sym] * price if sym != "USDJPY" else XM_CONTRACT[sym]    # USD notional of one lot
    comm_side = XM_ZERO_COMMISSION_SIDE_LOT if (acct == "zero" and commission_lot_side is None) else (commission_lot_side or 0.0)
    comm = 2 * comm_side / notional_lot
    swap = (XM_SWAP_ANNUAL if swap_annual is None else swap_annual) * nights / 365.0 * mult
    return {"spread": spread, "commission": comm, "swap": swap, "trade_per_side": (spread + comm) / 2,
            "round_trip": spread + comm + swap}


def xm_cfd_cost(symbol, lots_or_notional, account="standard", nights=0, *, unit="lots", price=None,
                swap_annual=None, mult=1.0):
    """Round-trip USD cost of one XM MT5 CFD trade: {'spread_usd','commission_usd','swap_usd','total_usd','notional_usd'}.

    unit 'lots' (size is lots; price = quote needed) or 'notional' (size is USD notional; price = quote needed).
    Spread is paid once per round trip (half on entry, half on exit). Financing is a flat cost estimate per night
    (XM_SWAP_ANNUAL) because real swap rates live in the MT5 symbol specification, not on a readable page."""
    if price is None:
        raise ValueError("price is required (quote of the symbol at entry)")
    sym, _ = _norm(symbol, account)
    if unit == "lots":
        lots = float(lots_or_notional)
        notional = lots * XM_CONTRACT[sym] * (1.0 if sym == "USDJPY" else price)
    elif unit == "notional":
        notional = float(lots_or_notional)
        lots = notional / (XM_CONTRACT[sym] * (1.0 if sym == "USDJPY" else price))
    else:
        raise ValueError("unit must be 'lots' or 'notional'")
    f = xm_cfd_cost_fraction(symbol, account, price, nights, swap_annual, mult)
    spread_usd, swap_usd = f["spread"] * notional, f["swap"] * notional
    comm_usd = 2 * lots * (XM_ZERO_COMMISSION_SIDE_LOT if _norm(symbol, account)[1] == "zero" else 0.0)
    return {"spread_usd": spread_usd, "commission_usd": comm_usd, "swap_usd": swap_usd, "notional_usd": notional,
            "total_usd": spread_usd + comm_usd + swap_usd}
