"""Probe 3 for family 5: HistData.com free 1-minute ASCII files (second candle source). Availability only: status, size, first rows."""
import io
import json
import re
import sys
import zipfile
from urllib.parse import urlencode
from urllib.request import Request, urlopen

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) tradelab-research", "Accept": "*/*"}


def call(url, data=None, headers=None):
    h = dict(UA)
    h.update(headers or {})
    try:
        with urlopen(Request(url, data=data, headers=h), timeout=60) as r:
            return r.status, r.read(), dict(r.headers)
    except Exception as e:  # noqa: BLE001
        b = b""
        try:
            b = e.read()[:200]
        except Exception:  # noqa: BLE001
            pass
        return getattr(e, "code", type(e).__name__), b or str(e).encode()[:200], {}


out = {}
CASES = [("xauusd", 2024, None, "1-minute-bar-quotes"), ("xauusd", 2025, None, "1-minute-bar-quotes"), ("xauusd", 2026, 10, "1-minute-bar-quotes"),
         ("eurusd", 2024, None, "1-minute-bar-quotes"), ("xauusd", 2024, 1, "tick-data-quotes")]
for pair, y, m, kind in CASES:
    page = f"https://www.histdata.com/download-free-forex-historical-data/?/ascii/{kind}/{pair}/{y}" + (f"/{m}" if m else "")
    st, body, _ = call(page)
    r = {"page_status": st, "page_len": len(body) if st == 200 else 0}
    if st == 200:
        t = body.decode("utf8", "replace")
        form = {}
        for nm in ("tk", "date", "datemonth", "platform", "timeframe", "fxpair"):
            mm = re.search(r'name="%s" id="%s" value="([^"]*)"' % (nm, nm), t)
            form[nm] = mm.group(1) if mm else ""
        r["form"] = form
        if form["tk"]:
            st2, b2, hd = call("https://www.histdata.com/get.php", urlencode(form).encode(), {"Referer": page, "Content-Type": "application/x-www-form-urlencoded"})
            r["get_status"], r["get_bytes"] = st2, len(b2) if st2 == 200 else 0
            if st2 == 200:
                try:
                    z = zipfile.ZipFile(io.BytesIO(b2))
                    names = z.namelist()
                    csvn = [n for n in names if n.lower().endswith((".csv", ".txt")) and "status" not in n.lower()]
                    with z.open(csvn[0]) as f:
                        head = [f.readline().decode() for _ in range(3)]
                    r.update(files=names, head=head)
                except Exception as e:  # noqa: BLE001
                    r["zip_err"] = str(e)[:120]
                    r["head_bytes"] = b2[:120].decode("latin1")
            else:
                r["get_head"] = b2[:150].decode("latin1")
    out[f"{pair}_{y}_{m}_{kind}"] = r
json.dump(out, sys.stdout, indent=1, default=str)
