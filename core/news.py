"""News from public RSS feeds (Yahoo Finance per symbol, Google News search, CNBC, MarketWatch, CoinDesk)
with a finance-lexicon headline sentiment score. English sources only."""
import email.utils
import html
import re
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

from . import data

GENERAL_FEEDS = {
    "CNBC Top News": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "CNBC Markets": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "CNBC Tech": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
    "CNBC World": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
    "CNBC Earnings": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Seeking Alpha": "https://seekingalpha.com/market_currents.xml",
    "Benzinga": "https://www.benzinga.com/feed",
    "Nasdaq": "https://www.nasdaq.com/feed/rssoutbound?category=Markets",
    "PR Newswire": "https://www.prnewswire.com/rss/news-releases-list.rss",
    "BBC Business": "http://feeds.bbci.co.uk/news/business/rss.xml",
    "Guardian Business": "https://www.theguardian.com/business/rss",
    "Fed press": "https://www.federalreserve.gov/feeds/press_all.xml",
    "SEC press": "https://www.sec.gov/news/pressreleases.rss",
    "EIA energy": "https://www.eia.gov/rss/todayinenergy.xml",
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "CoinTelegraph": "https://cointelegraph.com/rss",
    "Decrypt": "https://decrypt.co/feed",
    "Google News Business": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en",
}
# Sources that legitimately publish only a few items per week; the others should show something within hours.
LOW_FREQUENCY = {"CNBC Markets", "CNBC Earnings", "Fed press", "SEC press", "EIA energy"}
# Checked 2026-11-23 and removed: Yahoo Finance rssindex (0 items), MarketWatch marketpulse (stale since 2025),
# Investing.com (stale).

POS = {"beat", "surge", "soar", "skyrocket", "jump", "rally", "gain", "record", "upgrade", "outperform", "bullish",
       "growth", "profit", "rise", "rising", "strong", "stronger", "boost", "approval", "approve", "buyback",
       "dividend", "raise", "top", "exceed", "optimism", "recover", "recovery", "rebound", "high", "breakthrough",
       "expand", "win", "partnership", "climb", "upbeat", "positive", "spike", "boom", "lift", "advance", "extend",
       "reinstate", "rescue", "relieve", "relief", "bounce", "accelerate", "ahead", "best", "momentum", "deal",
       "wins", "thrive", "improve", "easing", "ease", "cheer", "stellar", "blowout", "outpace", "robust"}
NEG = {"miss", "plunge", "drop", "fall", "falling", "slump", "tumble", "sink", "downgrade", "bearish", "loss",
       "weak", "weaker", "cut", "lawsuit", "probe", "investigation", "fraud", "recall", "warning", "warn",
       "layoff", "bankruptcy", "default", "crash", "fear", "recession", "decline", "lower", "low", "selloff",
       "sell-off", "risk", "slide", "hack", "fine", "tariff", "inflation", "concern", "negative", "plummet",
       "slash", "rout", "turmoil", "crisis", "sue", "ban", "halt", "delay", "shortfall", "struggle", "dive",
       "collapse", "scandal", "charge", "slowdown", "worry", "pressure", "sanction", "breach", "outage", "tank"}
NEGATORS = {"not", "no", "never", "without", "despite"}


def _stem_hit(w: str, vocab: set) -> bool:
    """Match a word or a simple inflection of a vocabulary word (soars, soared, soaring, plunges, losses...)."""
    if w in vocab:
        return True
    for suf in ("ing", "ed", "es", "s", "d"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            base = w[: -len(suf)]
            if base in vocab or base + "e" in vocab or (len(base) > 3 and base[-1] == base[-2] and base[:-1] in vocab):
                return True
    return False


def sentiment(text: str) -> float:
    """Lexicon score in [-1, 1]; a negator flips the next word."""
    words = re.findall(r"[a-z\-]+", text.lower())
    s, n, flip = 0, 0, False
    for w in words:
        if w in NEGATORS:
            flip = True
            continue
        v = 1 if _stem_hit(w, POS) else -1 if _stem_hit(w, NEG) else 0
        if v:
            s += -v if flip else v
            n += 1
        flip = False
    return max(-1.0, min(1.0, s / max(n, 1) * min(n, 3) / 3)) if n else 0.0


def _clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(s or ""))).strip()


def parse_feed(url: str, source: str, ttl=900) -> list:
    try:
        root = ET.fromstring(data.http_get(url, ttl=ttl))
    except Exception:
        return []
    out = []
    for it in root.iter("item"):
        title = _clean(it.findtext("title"))
        if not title:
            continue
        src = source
        s_el = it.find("source")
        if s_el is not None and s_el.text:
            src = s_el.text
            title = re.sub(rf"\s+-\s+{re.escape(src)}$", "", title)
        ts = 0
        pd = it.findtext("pubDate")
        if pd:
            try:
                ts = email.utils.parsedate_to_datetime(pd).timestamp()
            except Exception:
                ts = 0
        summary = _clean(it.findtext("description"))[:280]
        out.append({"title": title, "link": (it.findtext("link") or "").strip(), "source": src, "ts": ts,
                    "summary": summary if summary != title else "", "sentiment": round(sentiment(title + " " + summary), 2)})
    return out


def _dedupe(items):
    seen, out = set(), []
    for x in sorted(items, key=lambda x: -x["ts"]):
        key = re.sub(r"\W+", "", x["title"].lower())[:60]
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def symbol_news(symbol: str, name: str = "", limit=40) -> dict:
    q = symbol.replace("-USD", "").replace("=X", "").replace("=F", "").lstrip("^")
    terms = f'"{name}"' if name and len(name) > 3 else q
    feeds = [
        (f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={urllib.parse.quote(symbol)}&region=US&lang=en-US", "Yahoo Finance"),
        ("https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": f"{terms} stock OR shares OR price when:7d", "hl": "en-US", "gl": "US", "ceid": "US:en"}), "Google News"),
    ]
    with ThreadPoolExecutor(4) as ex:
        items = [x for res in ex.map(lambda f: parse_feed(*f), feeds) for x in res]
    keys = {q.lower()} | {w.lower() for w in re.findall(r"[A-Za-z]{3,}", name or "")[:1]}
    keys -= {"inc", "corp", "the"}
    rel = [x for x in items if any(k in (x["title"] + " " + x["summary"]).lower() for k in keys)]
    items = _dedupe(rel if len(rel) >= 5 else items)[:limit]
    return {"items": items, "summary": summarize(items)}


def market_news(limit=80) -> dict:
    with ThreadPoolExecutor(6) as ex:
        items = [x for res in ex.map(lambda kv: parse_feed(kv[1], kv[0]), GENERAL_FEEDS.items()) for x in res]
    items = _dedupe(items)[:limit]
    return {"items": items, "summary": summarize(items), "sources": list(GENERAL_FEEDS)}


def summarize(items) -> dict:
    if not items:
        return {"count": 0, "avg": 0, "positive": 0, "negative": 0, "neutral": 0, "label": "No news"}
    sc = [x["sentiment"] for x in items]
    pos = sum(1 for v in sc if v > 0.1)
    neg = sum(1 for v in sc if v < -0.1)
    avg = sum(sc) / len(sc)
    label = "Positive" if avg > 0.08 else "Negative" if avg < -0.08 else "Mixed / neutral"
    return {"count": len(sc), "avg": round(avg, 3), "positive": pos, "negative": neg,
            "neutral": len(sc) - pos - neg, "label": label}
