"""Convert a place name into coordinates using OpenStreetMap Nominatim."""
import os
from functools import lru_cache

import requests

from trips.errors import GeocodingError

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_USER_AGENT = (
    "spotter-weather-routing-assessment/1.0 "
    "(+https://github.com/Achref47/spotter-weather-routing)"
)
TIMEOUT_S = 10


def _user_agent() -> str:
    return os.environ.get("NOMINATIM_USER_AGENT", DEFAULT_USER_AGENT)


@lru_cache(maxsize=256)
def _lookup(query: str) -> tuple:
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "jsonv2", "limit": 1},
            headers={"User-Agent": _user_agent()},
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise GeocodingError("The geocoding service is unavailable.") from exc

    if not data:
        raise GeocodingError(f"No match found for '{query}'.")

    try:
        item = data[0]
        lat = float(item["lat"])
        lon = float(item["lon"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise GeocodingError("Unexpected response from geocoding service.") from exc

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise GeocodingError("Geocoding service returned invalid coordinates.")

    return item.get("display_name", query), lat, lon


def geocode(query: str) -> dict:
    """Return {"label", "lat", "lon"} for a place name, or raise GeocodingError."""
    cleaned = " ".join((query or "").split())
    if len(cleaned) < 2:
        raise GeocodingError("Enter a place name of at least 2 characters.")
    label, lat, lon = _lookup(cleaned.lower())
    return {"label": label, "lat": lat, "lon": lon}