"""tests/test_analytics.py: pure fixture-exact assertions for compute_analytics (FC-02).

No DB, no fastapi -- imports only core.analytics.compute_analytics. This is the
load-bearing test proving success_rate and time_to_checkout are correct against
a deterministic order set (overall + per-plugin), plus the divide-by-zero-safe
empty-dataset path.
"""

from core.analytics import compute_analytics


def _row(link, order_id=None, confirmed_at=None, attempted_at=None):
    return {
        "name": "x",
        "link": link,
        "order_id": order_id,
        "confirmed_at": confirmed_at,
        "checkout_attempts": 0,
        "place_order_attempted_at": attempted_at,
        "purchased": 1,
    }


def _platform_of(link):
    return "amazon" if "amazon" in link else "bestbuy"


def test_success_rate_and_time_to_checkout_exact():
    """4-row fixture: 3 confirmed (30s/50s/60s) + 1 sentinel (attempted, not confirmed)."""
    rows = [
        _row("amazon.com/a1", "ORD-A1", "2026-01-01T00:00:30+00:00", "2026-01-01T00:00:00+00:00"),  # +30s
        _row("amazon.com/a2", "ORD-A2", "2026-01-01T00:00:50+00:00", "2026-01-01T00:00:00+00:00"),  # +50s
        _row("bestbuy.com/b1", "ORD-B1", "2026-01-01T00:01:00+00:00", "2026-01-01T00:00:00+00:00"),  # +60s
        _row("bestbuy.com/b2", "CONFIRMED-2026-01-01T00:00:00", None, "2026-01-01T00:00:00+00:00"),  # sentinel
    ]

    out = compute_analytics(rows, _platform_of)

    assert out["overall"] == {
        "attempted": 4,
        "confirmed": 3,
        "success_rate": 0.75,
        "avg_time_to_checkout_secs": (30 + 50 + 60) / 3,
        "sample_size": 3,
    }

    amazon = next(p for p in out["per_plugin"] if p["plugin"] == "amazon")
    assert amazon == {
        "plugin": "amazon",
        "attempted": 2,
        "confirmed": 2,
        "success_rate": 1.0,
        "avg_time_to_checkout_secs": 40.0,
        "sample_size": 2,
    }

    bestbuy = next(p for p in out["per_plugin"] if p["plugin"] == "bestbuy")
    assert bestbuy["attempted"] == 2
    assert bestbuy["confirmed"] == 1
    assert bestbuy["success_rate"] == 0.5
    assert bestbuy["sample_size"] == 1


def test_empty_dataset_no_divide_by_zero():
    """No rows -> valid JSON-serializable dict, success_rate/avg None, never raises."""
    out = compute_analytics([], lambda link: "core")
    assert out == {
        "overall": {
            "attempted": 0,
            "confirmed": 0,
            "success_rate": None,
            "avg_time_to_checkout_secs": None,
            "sample_size": 0,
        },
        "per_plugin": [],
    }


def test_confirmed_row_missing_one_timestamp_excluded_from_duration_sample():
    """A confirmed row with only ONE of the two timestamps counts in confirmed
    but is excluded from the duration sample (sample_size stays exact)."""
    rows = [
        _row("amazon.com/a1", "ORD-A1", "2026-01-01T00:00:30+00:00", "2026-01-01T00:00:00+00:00"),  # +30s, full pair
        _row("amazon.com/a2", "ORD-A2", None, "2026-01-01T00:00:00+00:00"),  # confirmed, but no confirmed_at
    ]

    out = compute_analytics(rows, _platform_of)

    assert out["overall"]["attempted"] == 2
    assert out["overall"]["confirmed"] == 2
    assert out["overall"]["success_rate"] == 1.0
    assert out["overall"]["sample_size"] == 1
    assert out["overall"]["avg_time_to_checkout_secs"] == 30.0


def test_attempted_denominator_excludes_checkout_attempts():
    """A row with only checkout_attempts incremented (no marker, no order_id) is
    NOT counted as attempted -- checkout_attempts must never drive the denominator."""
    rows = [
        {
            "name": "x",
            "link": "amazon.com/a1",
            "order_id": None,
            "confirmed_at": None,
            "checkout_attempts": 5,
            "place_order_attempted_at": None,
            "purchased": 0,
        },
    ]

    out = compute_analytics(rows, _platform_of)

    assert out["overall"]["attempted"] == 0
    assert out["overall"]["confirmed"] == 0
    assert out["per_plugin"] == []
