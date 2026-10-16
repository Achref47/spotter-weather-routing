"""Manual live check: real geocoding + routing. Not part of the test suite."""
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(BACKEND), ".env"))

from trips.domain.checkpoints import METERS_PER_MILE  # noqa: E402
from trips.domain.route_selection import overlap_fraction  # noqa: E402
from trips.services.geocoding import geocode  # noqa: E402
from trips.services.routing import get_route_options  # noqa: E402

origin_q = sys.argv[1] if len(sys.argv) > 1 else "Houston, TX"
dest_q = sys.argv[2] if len(sys.argv) > 2 else "Atlanta, GA"

origin, dest = geocode(origin_q), geocode(dest_q)
routes = get_route_options(origin, dest)

print(f"{origin_q} -> {dest_q}: {len(routes)} route(s)")
for r in routes:
    print(f"  {r.label}: {r.distance_m / METERS_PER_MILE:.0f} mi, "
            f"{r.duration_s / 3600:.1f} h ({r.source})")
for a, b in itertools.combinations(routes, 2):
    pct = max(overlap_fraction(a.coords, b.coords), overlap_fraction(b.coords, a.coords))
    print(f"  overlap {a.label} vs {b.label}: {pct:.0%}")