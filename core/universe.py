"""Tradable universe for the paper traders.

`TICKERS` stays the 104 large-cap US stocks used by the news-shock scans. The DeepSeek trader (protocol v4) also sees
liquid ETFs, commodity futures, FX and crypto so it can follow news, attention and macro moves across the whole market.
Every symbol here is a Yahoo Finance symbol (crypto also has a Binance fallback in core/data.py)."""
TICKERS = """AAPL MSFT NVDA AMZN GOOGL META TSLA BRK-B JPM V MA UNH XOM JNJ PG HD COST ABBV MRK LLY AVGO PEP KO WMT
BAC CVX ORCL CRM ADBE NFLX AMD INTC CSCO QCOM TXN IBM DIS NKE MCD SBUX BA CAT GE HON MMM UPS FDX LMT RTX GS MS C
WFC AXP BLK SCHW PFE BMY AMGN GILD CVS CI TMO DHR ABT MDT ISRG VRTX REGN T VZ CMCSA TMUS PYPL INTU NOW AMAT MU
LRCX ADI KLAC SNPS CDNS PANW F GM UBER ABNB BKNG MAR LOW TGT DG DLTR KR EL CL KHC MO PM SLB COP OXY DE""".split()

# Liquid growth/mid caps that are not in the large-cap news list.
STOCKS = TICKERS + """PLTR SNOW CRWD DDOG NET ZS MDB TEAM SHOP COIN HOOD SOFI AFRM UPST AI SMCI ARM MRVL ON
ENPH FSLR RIVN LCID NIO XPEV LI TSM ASML SAP MELI SE BABA JD PDD NVO SPOT RBLX U ROKU TTD TWLO OKTA MSTR IBKR""".split()

ETFS = """SPY QQQ IWM DIA SMH XLE XLF XLK XLV XLI XLY XLP XLU XLB XLRE GLD SLV USO UNG TLT IEF HYG LQD EEM EFA
FXI EWJ EWZ IBIT ARKK XBI IBB KRE XOP""".split()

COMMODITIES = "GC=F SI=F CL=F BZ=F NG=F HG=F ZC=F ZW=F ZS=F KC=F SB=F CT=F PL=F PA=F LE=F HE=F".split()
FX = "EURUSD=X GBPUSD=X USDJPY=X AUDUSD=X USDCAD=X USDCHF=X NZDUSD=X USDCNY=X".split()
CRYPTO = "BTC-USD ETH-USD SOL-USD XRP-USD ADA-USD DOGE-USD AVAX-USD LINK-USD DOT-USD LTC-USD BCH-USD".split()


def _dedupe(rows):
    out, seen = [], set()
    for s in rows:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


STOCKS = _dedupe(STOCKS)
ASSETS = {"stock": STOCKS, "etf": _dedupe(ETFS), "commodity": _dedupe(COMMODITIES),
          "fx": _dedupe(FX), "crypto": _dedupe(CRYPTO)}
CLASS = {s: c for c, rows in ASSETS.items() for s in rows}
# Round-robin the classes so a rotating slice of the scan always contains every asset class, not only stocks.
ALL = _dedupe([rows[i] for i in range(max(len(r) for r in ASSETS.values())) for rows in ASSETS.values() if i < len(rows)])
# A move this large in a session counts as a shock; stocks/ETFs also need unusual volume.
SHOCK_PCT = {"stock": 5.0, "etf": 3.0, "commodity": 2.0, "fx": 1.0, "crypto": 5.0}


def asset_class(symbol: str) -> str:
    return CLASS.get(symbol, "stock")
