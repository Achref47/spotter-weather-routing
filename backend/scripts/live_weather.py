"""Manual live check against the real Open-Meteo API. Not part of the test suite."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trips.domain.weather_match import weather_at  # noqa: E402
from trips.services.weather import forecast_days_for, series_for_points  # noqa: E402

POINTS = [(29.76, -95.37), (32.78, -90.10), (33.75, -84.39)]  # Houston, Mississippi, Atlanta

now = datetime.now(timezone.utc)
series = series_for_points(POINTS, forecast_days_for(now + timedelta(hours=48), now))

for point, s in zip(POINTS, series):
    first = datetime.fromtimestamp(s.times[0], timezone.utc)
    print(f"{point}: {len(s.times)} hourly values, first {first:%Y-%m-%d %H:%M}Z")
    for hours in (0, 6, 24, 47):
        print(f"   +{hours:>2}h", weather_at(s, now + timedelta(hours=hours)))