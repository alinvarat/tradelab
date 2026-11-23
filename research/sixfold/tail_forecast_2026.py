"""Validate original weather forecast errors on new Central Park observations."""
import csv
import gzip
import hashlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from statistics import NormalDist, mean, stdev
from urllib.parse import urlencode

from .spot_inputs import download
from .tail import ROOT, RUNS, SNAPSHOT, TEMP, choose_dates

BEGIN, END = date(2026, 1, 1), date(2026, 10, 31)
STATION = "USW00094728"
NOAA = "https://www.ncei.noaa.gov/access/services/data/v1?" + urlencode(
    dict(dataset="daily-summaries", stations=STATION, startDate=BEGIN, endDate=END,
         dataTypes="TMAX", units="standard", format="csv", includeAttributes="true"))
LEADS = (TEMP.replace("day2", "day1"), TEMP)
FORECAST = RUNS + "?" + urlencode(dict(latitude=40.779, longitude=-73.969, timezone="GMT",
    start_date=BEGIN, end_date=END + timedelta(days=1), hourly=",".join(LEADS),
    temperature_unit="fahrenheit", models="gfs_global"))
INPUT = ROOT / "tail_forecast_2026_inputs.json.gz"


def acquire():
    with ThreadPoolExecutor(2) as pool:
        forecast, actual = pool.map(download, (FORECAST, NOAA))
    hourly = json.loads(forecast)["hourly"]
    observed = {}
    for row in csv.DictReader(actual.decode("utf-8-sig").splitlines()):
        if row["STATION"] == STATION and row.get("TMAX") and not row["TMAX_ATTRIBUTES"].split(",")[1]:
            observed[row["DATE"]] = float(row["TMAX"])
    values = {lead: dict(zip(hourly["time"], hourly[lead])) for lead in LEADS}
    results = {}
    for day in choose_dates(BEGIN, END):
        start = datetime.combine(day, time(5), timezone.utc)
        highs = {}
        for lead, series in values.items():
            temps = [series.get((start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M")) for h in range(24)]
            highs[lead] = max(temps) if all(t is not None for t in temps) else None
        results[day.isoformat()] = {"forecast": highs, "observed": observed.get(day.isoformat())}
    payload = {"rows": results, "source_sha256": {u: hashlib.sha256(raw).hexdigest()
              for u, raw in ((FORECAST, forecast), (NOAA, actual))}}
    INPUT.write_bytes(gzip.compress(json.dumps(payload).encode(), mtime=0))


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    sample = json.loads(raw)["rows"]
    fit = json.loads(gzip.decompress(SNAPSHOT.read_bytes()))["fit"]
    model = NormalDist(fit["mean_error_f"], fit["sd_error_f"])
    errors = {lead: [] for lead in LEADS}
    months = Counter()
    for day, row in sample.items():
        if row["observed"] is not None and all(t is not None for t in row["forecast"].values()):
            months[day[:7]] += 1
            for lead in LEADS:
                errors[lead].append(row["observed"] - row["forecast"][lead])
    results = {}
    for lead, values in errors.items():
        residual = [v - model.mean for v in values]
        results[lead] = {"paired_days": len(values), "raw_bias_f": mean(values), "error_sd_f": stdev(values),
                         "bias_corrected_mae_f": mean(map(abs, residual)),
                         "bias_corrected_rmse_f": mean(x*x for x in residual)**.5,
                         "coverage": {str(c): mean(model.inv_cdf((1-c)/2) <= x <= model.inv_cdf((1+c)/2)
                                                   for x in values) for c in (.8,.95)}}
    out = {"input_sha256": hashlib.sha256(raw).hexdigest(), "days": len(sample), "paired_by_month": dict(months), "leads": results, "fit": fit}
    (ROOT / "tail_forecast_2026_results.json").write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
