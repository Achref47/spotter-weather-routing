"""Manual check: how long does Open-Meteo take for different batch sizes? Not part of the tests."""
import time

import requests

URL = (
    "https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}"
    "&hourly=wind_speed_10m,rain,showers,snowfall&wind_speed_unit=mph"
    "&precipitation_unit=inch&timeformat=unixtime&timezone=GMT&forecast_days=3"
)

for n in (1, 10, 25, 50):
    lats = ",".join(f"{25 + i * 0.2:.2f}" for i in range(n))
    lons = ",".join(f"{-95 + i * 0.2:.2f}" for i in range(n))
    start = time.time()
    try:
        r = requests.get(URL.format(lats=lats, lons=lons), timeout=60)
        print(f"{n:>2} locations: HTTP {r.status_code}, {time.time() - start:.1f} s, {len(r.content)} bytes")
    except requests.RequestException as exc:
        print(f"{n:>2} locations: failed after {time.time() - start:.1f} s: {exc!r}"[:200])