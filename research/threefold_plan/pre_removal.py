"""Test a fixed lead-in rebound before a confirmed Bybit spot removal."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import random
from statistics import median

from research.sixfold.delist_delayed import STOP
from research.sixfold.delisting import fetch

HERE = Path(__file__).parent
CATALOG = HERE.parent / "sixfold/delist_rebound_articles.json"
INPUT = HERE / "pre_removal_inputs.json.gz"
RESULT = HERE / "pre_removal_results.json"
HOUR = 3600000


def capture(job):
    symbol, entry = job
    req = dict(category="spot", symbol=symbol+"USDT", interval="60", limit=30,
               start=entry-12*HOUR, end=entry+12*HOUR-1)
    try:
        rows = fetch("/v5/market/kline", **req)["list"]
    except (OSError,ValueError) as exc:
        return symbol, entry, {}, str(exc)
    bars = {int(ts): [float(op),float(close)] for ts,op,_,_,close,v,_ in rows if float(v)>0}
    return symbol, entry, bars, None


def acquire():
    catalog = CATALOG.read_bytes()
    jobs = set()
    for notice in json.loads(catalog)["accepted"]:
        day = next(value for key,value in STOP.items() if key in notice["url"])
        removal = datetime.fromisoformat(day).replace(hour=8,tzinfo=timezone.utc)
        entry = int(removal.timestamp()*1000)-24*HOUR
        jobs.update((s,entry) for s in notice["symbols"])
    with ThreadPoolExecutor(6) as workers:
        raw = list(workers.map(capture, sorted(jobs)))
    INPUT.write_bytes(gzip.compress(json.dumps({"catalog_sha256":hashlib.sha256(catalog).hexdigest(),
                                                 "rows":raw}).encode(),mtime=0))


def opportunities(rows):
    by_time = {}
    coverage = {"pairs":len(rows),"signal_history":0,"request_errors":0}
    for symbol,entry,raw,error in rows:
        bars = {int(k):v for k,v in raw.items()}
        if error:
            coverage["request_errors"]+=1
        if any(entry+i*HOUR not in bars for i in range(-12,0)):
            continue
        coverage["signal_history"]+=1
        strength = bars[entry-HOUR][1]/bars[entry-12*HOUR][0]-1
        gross = None
        if entry in bars:
            gross = (bars[entry+11*HOUR][1]/bars[entry][0] if all(
                     entry+i*HOUR in bars for i in range(12)) else 0)
        by_time.setdefault(entry,[]).append((strength,symbol,gross))
    return by_time,coverage


def replay(dates, fee, rng=None):
    monthly = dict.fromkeys((f"2026-{m:02}" for m in range(1,11)),1.)
    equity = peak = 5000.
    dd = 0.
    trades = []
    for stamp,menu in sorted(dates.items()):
        qualified = [x for x in menu if x[0]>=.05]
        if not qualified:
            continue
        strength,symbol,gross = rng.choice(menu) if rng else min(qualified,key=lambda x:(-x[0],x[1]))
        date = datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat()
        if gross is None:
            trades.append({"date":date,"symbol":symbol,"signal":strength,"status":"no_entry"})
            continue
        if gross==0:
            return {"ending_thb":None,"monthly":monthly,"trades":trades+[{
                "date":date,"symbol":symbol,"signal":strength,"status":"exit_unverified"}]}
        net = gross*(1-fee)/(1+fee)
        equity *= net
        peak = max(peak,equity)
        dd = max(dd,1-equity/peak)
        monthly[date[:7]] *= net
        trades.append({"date":date,"symbol":symbol,"signal":strength,"net":net,"status":"proxy"})
    return {"ending_thb":equity,"monthly":monthly,"drawdown_trade_closes":dd,
            "3x_months":sum(x>=3 for x in monthly.values()),"trades":trades}


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    dates, coverage = opportunities(json.loads(raw)["rows"])
    output = {"input_sha256":hashlib.sha256(raw).hexdigest(),"coverage":coverage,"cases":{}}
    for label,fee in (("base",.0035),("higher",.01)):
        model = output["cases"][label] = replay(dates,fee)
        rng = random.Random(20071)
        controls = [replay(dates,fee,rng)["ending_thb"] for _ in range(1000)]
        values = [x for x in controls if x is not None]
        model["random_unverified"] = len(controls)-len(values)
        model["random_median_thb"] = median(values) if values else None
    RESULT.write_text(json.dumps(output,indent=2)+"\n")


if __name__=="__main__":
    main()
