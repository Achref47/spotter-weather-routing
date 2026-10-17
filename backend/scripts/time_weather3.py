"""Manual check: does choosing a single forecast model make Open-Meteo faster? Not part of the tests."""
import time

import requests

BASE = (
    "https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}"
    "&hourly=wind_speed_10m,rain,showers,snowfall&wind_speed_unit=mph"
    "&precipitation_unit=inch&timeformat=unixtime&timezone=GMT&forecast_days=3{extra}"
)
N = 25
lats = ",".join(f"{25 + i * 0.2:.2f}" for i in range(N))
lons = ",".join(f"{-95 + i * 0.2:.2f}" for i in range(N))

for label, extra in [
    ("default (best match)", ""),
    ("gfs_global", "&models=gfs_global"),
    ("icon_global", "&models=icon_global"),
    ("ecmwf_ifs025", "&models=ecmwf_ifs025"),
]:
    start = time.time()
    try:
        r = requests.get(BASE.format(lats=lats, lons=lons, extra=extra), timeout=90)
        elapsed = time.time() - start
        if r.status_code != 200:
            print(f"{label}: HTTP {r.status_code}, {elapsed:.1f} s, {r.text[:120]}")
            continue
        hourly = r.json()[0]["hourly"]
        gaps = {k: sum(v is None for v in hourly[k]) for k in ("wind_speed_10m", "rain", "showers", "snowfall")}
        print(f"{label}: HTTP 200, {elapsed:.1f} s, missing values: {gaps} of {len(hourly['time'])}")
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        print(f"{label}: failed after {time.time() - start:.1f} s: {exc!r}"[:160])