import os
from datetime import datetime, timedelta, timezone

import pytest
from rest_framework.test import APIClient

from config import settings as project_settings
from trips.domain.route_selection import Candidate
from trips.services import analysis
from trips.throttling import wait_text

URL = "/api/trips/analyze"
DEPARTURE = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)


def body(**changes):
    data = {
        "origin": "Origin City",
        "destination": "Destination City",
        "departure_time": DEPARTURE.isoformat(),
        "load_weight_lb": 42_000,
    }
    data.update(changes)
    return data


@pytest.fixture
def upstream_calls(monkeypatch):
    """Fake geocoding and routing that count how often the app reaches for an outside service."""
    calls = {"geocode": 0, "routing": 0}

    def geocode(query):
        calls["geocode"] += 1
        return {"label": query, "lat": 0.0, "lon": 0.0}

    def routes(origin, destination):
        calls["routing"] += 1
        return [Candidate("Fastest route", "alternative", 111_000.0, 3600.0, [[0.0, 0.0], [1.0, 0.0]])]

    monkeypatch.setattr(analysis, "geocode", geocode)
    monkeypatch.setattr(analysis, "get_route_options", routes)
    return calls


def limit(settings, burst="100000/min", hour="100000/hour"):
    settings.ANALYZE_THROTTLE_RATES = {"analyze_burst": burst, "analyze_hour": hour}


def post(client=None, **headers):
    return (client or APIClient()).post(URL, body(), format="json", **headers)


def test_the_burst_limit_allows_the_rate_then_refuses(settings, upstream_calls):
    limit(settings, burst="3/min")
    client = APIClient()
    assert [post(client).status_code for _ in range(3)] == [200, 200, 200]
    refused = post(client)
    assert refused.status_code == 429


def test_the_sustained_limit_is_checked_separately(settings, upstream_calls):
    limit(settings, burst="100/min", hour="2/hour")
    client = APIClient()
    assert [post(client).status_code for _ in range(2)] == [200, 200]
    assert post(client).status_code == 429


def test_a_refusal_uses_the_apis_error_shape_and_tells_the_client_how_long_to_wait(settings, upstream_calls):
    limit(settings, burst="1/min")
    client = APIClient()
    post(client)
    refused = post(client)
    data = refused.json()
    assert refused.status_code == 429
    assert set(data) == {"error", "retry_after_s"}
    assert 1 <= data["retry_after_s"] <= 60
    assert "Too many analyses" in data["error"] and "Please wait" in data["error"]
    assert int(refused["Retry-After"]) == data["retry_after_s"]


def test_a_refused_request_never_reaches_geocoding_routing_or_weather(settings, upstream_calls, monkeypatch):
    limit(settings, burst="1/min")
    client = APIClient()
    assert post(client).status_code == 200
    assert upstream_calls == {"geocode": 2, "routing": 1}  # origin and destination, one routing call

    monkeypatch.setattr(
        analysis, "series_for_points", lambda *a, **k: pytest.fail("the weather service was called")
    )
    for _ in range(5):
        assert post(client).status_code == 429
    assert upstream_calls == {"geocode": 2, "routing": 1}  # unchanged: nothing leaked through


def test_each_client_address_has_its_own_allowance(settings, upstream_calls):
    limit(settings, burst="1/min")
    first, second = APIClient(), APIClient()
    assert post(first, REMOTE_ADDR="10.0.0.1").status_code == 200
    assert post(first, REMOTE_ADDR="10.0.0.1").status_code == 429
    assert post(second, REMOTE_ADDR="10.0.0.2").status_code == 200  # a different visitor is unaffected


def test_the_health_check_is_never_throttled(settings, upstream_calls):
    limit(settings, burst="1/min", hour="1/hour")
    client = APIClient()
    assert all(client.get("/api/health").status_code == 200 for _ in range(30))


def test_invalid_requests_count_too_so_bad_input_cannot_be_used_to_hammer_the_server(settings, upstream_calls):
    limit(settings, burst="2/min")
    client = APIClient()
    bad = {"origin": "x"}
    assert [client.post(URL, bad, format="json").status_code for _ in range(2)] == [400, 400]
    assert client.post(URL, bad, format="json").status_code == 429


def test_behind_a_proxy_the_client_is_the_address_the_proxy_added(settings, upstream_calls):
    limit(settings, burst="1/min")
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    client = APIClient()
    # The last entry is the one the trusted proxy appended; the first can be forged by the client.
    assert post(client, HTTP_X_FORWARDED_FOR="9.9.9.9, 1.1.1.1").status_code == 200
    assert post(client, HTTP_X_FORWARDED_FOR="8.8.8.8, 1.1.1.1").status_code == 429  # same visitor
    assert post(client, HTTP_X_FORWARDED_FOR="9.9.9.9, 2.2.2.2").status_code == 200  # a different one


def test_wait_text_is_readable():
    assert wait_text(1) == "1 second"
    assert wait_text(45) == "45 seconds"
    assert wait_text(89) == "89 seconds"
    assert wait_text(90) == "2 minutes"
    assert wait_text(600) == "10 minutes"
    assert wait_text(3500) == "59 minutes"


def test_the_default_limits_are_generous_for_a_person_but_cap_a_runaway_client():
    if "ANALYZE_RATE_BURST" in os.environ or "ANALYZE_RATE_HOUR" in os.environ:
        pytest.skip("rates are overridden by the environment")
    assert project_settings.ANALYZE_THROTTLE_RATES == {"analyze_burst": "10/min", "analyze_hour": "30/hour"}
