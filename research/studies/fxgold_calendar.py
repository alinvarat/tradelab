"""Release calendar for family 5 (Actions only). Free sources: BLS archived news-release lists (CPI, Employment Situation; 08:30 ET) and the
Fed FOMC calendar page (2021+, statement 14:00 ET); FOMC 2016-2020 scheduled decision dates are typed in below from the Fed's published
calendars (emergency meetings left out). Output CSV: utc_datetime,event,source_url. Usage: python -m research.studies.fxgold_calendar OUT.csv"""
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen

ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) tradelab-research"}
FOMC_2016_2020 = ["2016-01-27", "2016-03-16", "2016-04-27", "2016-06-15", "2016-07-27", "2016-09-21", "2016-11-02", "2016-12-14",
                  "2017-02-01", "2017-03-15", "2017-05-03", "2017-06-14", "2017-07-26", "2017-09-20", "2017-11-01", "2017-12-13",
                  "2018-01-31", "2018-03-21", "2018-05-02", "2018-06-13", "2018-08-01", "2018-09-26", "2018-11-08", "2018-12-19",
                  "2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19", "2019-07-31", "2019-09-18", "2019-10-30", "2019-12-11",
                  "2020-01-29", "2020-04-29", "2020-06-10", "2020-07-29", "2020-09-16", "2020-11-05", "2020-12-16"]
MONTHS = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September",
                                          "October", "November", "December"])}


UAS = [UA, {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}]


def page(u):
    import time
    last = None
    for k in range(8):
        try:
            with urlopen(Request(u, headers=UAS[k % 2]), timeout=40) as r:
                return r.read().decode("utf8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(4 * (k + 1))
    raise last


def utc(day, hh, mm):
    y, m, d = (int(x) for x in day.split("-"))
    return datetime(y, m, d, hh, mm, tzinfo=ET).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def main(out):
    rows = []
    for ev, u in (("CPI", "https://www.bls.gov/bls/news-release/cpi.htm"), ("NFP", "https://www.bls.gov/bls/news-release/empsit.htm")):
        t = page(u)
        key = "cpi" if ev == "CPI" else "empsit"
        days = sorted(set(f"{m[3]}-{m[1]}-{m[2]}" for m in re.finditer(key + r"_(\d{2})(\d{2})(\d{4})\.htm", t)))
        days = [d for d in days if "2018-01-01" <= d <= "2026-12-31"]
        print(ev, len(days), days[:2], days[-2:], file=sys.stderr)
        rows += [(utc(d, 8, 30), ev, u) for d in days]
    t = page("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    nf = 0
    for pm in re.finditer(r"(20\d\d) FOMC Meetings(.*?)(?=\d{4} FOMC Meetings|$)", t, re.S):
        y = int(pm.group(1))
        if y < 2021 or y > 2026:
            continue
        for mm in re.finditer(r"fomc-meeting__month[^>]*><strong>([A-Za-z/]+)</strong>.*?fomc-meeting__date[^>]*>\s*([0-9\-/*]+)", pm.group(2), re.S):
            mon = mm.group(1).split("/")[-1]
            dd = re.findall(r"\d+", mm.group(2))
            if mon not in MONTHS or not dd:
                continue
            rows.append((utc(f"{y}-{MONTHS[mon]:02d}-{int(dd[-1]):02d}", 14, 0), "FOMC", "federalreserve.gov/monetarypolicy/fomccalendars.htm"))
            nf += 1
    print("FOMC 2021+", nf, file=sys.stderr)
    rows += [(utc(d, 14, 0), "FOMC", "Fed scheduled calendars 2016-2020 (typed)") for d in FOMC_2016_2020]
    rows = sorted(set(rows))
    with open(out, "w") as f:
        f.write("utc_datetime,event,source_url\n")
        for r in rows:
            f.write(",".join(r) + "\n")
    print("events", len(rows), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
