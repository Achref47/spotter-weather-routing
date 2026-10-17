"""Manual check: does Open-Meteo speed up with fewer days or parallel requests? Not part of the tests."""
import time
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = (
    "https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}"
    "&hourly=wind_speed_10m,rain,showers,snowfall&wind_speed_unit=mph"
    "&precipitation_unit=inch&timeformat=unixtime&timezone=GMT&forecast_days={days}"
)


def url(n, days, offset=0.0):
    lats = ",".join(f"{25 + offset + i * 0.2:.2f}" for i in range(n))
    lons = ",".join(f"{-95 + i * 0.2:.2f}" for i in range(n))
    return BASE.format(lats=lats, lons=lons, days=days)


def timed(label, target):
    start = time.time()
    try:
        r = requests.get(target, timeout=90)
        print(f"{label}: HTTP {r.status_code}, {time.time() - start:.1f} s")
    except requests.RequestException as exc:
        print(f"{label}: failed after {time.time() - start:.1f} s: {exc!r}"[:160])


timed("25 locations, 3 days", url(25, 3))
timed("25 locations, 1 day ", url(25, 1))

start = time.time()
with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(lambda k: timed(f"  parallel #{k}", url(25, 3, offset=k * 6)), range(4)))
print(f"4 parallel requests of 25 locations (100 total): {time.time() - start:.1f} s overall")