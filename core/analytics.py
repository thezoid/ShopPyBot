"""core/analytics.py: PURE outcome-analytics computation (FC-02).

No DB, no fastapi, no models/service imports -- only stdlib datetime plus the
sentinel-prefix constant imported from core/confirmation.py (IN-01: shared,
not redefined, so the two modules can never drift apart). core/confirmation.py
is itself DB/fastapi-free, so this import does not compromise purity. Purity
makes the fixture assertion exact and testable without a database.

Metric definitions (RESEARCH.md "State of the Art"):
  attempted = rows where place_order_attempted_at IS NOT NULL OR order_id IS NOT NULL
  confirmed = attempted rows with a non-sentinel order_id (CONFIRMED-<ts> excluded)
  success_rate = confirmed / attempted (None when attempted == 0)
  time_to_checkout = confirmed_at - place_order_attempted_at, per confirmed row with
    BOTH timestamps present and a non-negative delta; averaged (None when no samples)

checkout_attempts is intentionally NEVER used as a denominator: it increments even
in test_mode (Pitfall 3) and would deflate the reported success rate.
"""

from datetime import datetime

from core.confirmation import _CONFIRMED_SENTINEL_PREFIX as _SENTINEL_PREFIX


def _is_confirmed(order_id) -> bool:
    """A row is 'confirmed' only if order_id is set and is NOT the unverified sentinel."""
    return bool(order_id) and not str(order_id).startswith(_SENTINEL_PREFIX)


def _summarize(bucket: dict) -> dict:
    """Reduce one {attempted, confirmed, durations} bucket to the reported metric dict.

    Every division is guarded against a zero denominator -- returns None, never raises.
    """
    attempted = bucket["attempted"]
    confirmed = bucket["confirmed"]
    durations = bucket["durations"]
    return {
        "attempted": attempted,
        "confirmed": confirmed,
        "success_rate": (confirmed / attempted) if attempted else None,
        "avg_time_to_checkout_secs": (sum(durations) / len(durations)) if durations else None,
        "sample_size": len(durations),
    }


def _merge(buckets: dict) -> dict:
    """Merge all per-plugin buckets into a single overall bucket."""
    merged = {"attempted": 0, "confirmed": 0, "durations": []}
    for bucket in buckets.values():
        merged["attempted"] += bucket["attempted"]
        merged["confirmed"] += bucket["confirmed"]
        merged["durations"].extend(bucket["durations"])
    return merged


def compute_analytics(rows, platform_of) -> dict:
    """Compute overall + per-plugin outcome analytics from order rows.

    Args:
        rows: iterable of dicts with keys name, link, order_id, confirmed_at,
            checkout_attempts, place_order_attempted_at, purchased.
        platform_of: Callable[[str], str] mapping link -> platform_key
            ("core" when no plugin matches). Called only inside this function --
            link never appears in the returned dict.

    Returns:
        {"overall": {attempted, confirmed, success_rate, avg_time_to_checkout_secs,
                     sample_size},
         "per_plugin": [{plugin, attempted, confirmed, success_rate,
                         avg_time_to_checkout_secs, sample_size}, ...]}
        sorted by plugin key. Safe on an empty dataset -- never raises ZeroDivisionError.
    """
    buckets: dict[str, dict] = {}

    for row in rows:
        attempted = (row["place_order_attempted_at"] is not None) or (row["order_id"] is not None)
        if not attempted:
            continue

        key = platform_of(row["link"])
        bucket = buckets.setdefault(key, {"attempted": 0, "confirmed": 0, "durations": []})
        bucket["attempted"] += 1

        if _is_confirmed(row["order_id"]):
            bucket["confirmed"] += 1
            confirmed_at = row["confirmed_at"]
            attempted_at = row["place_order_attempted_at"]
            if confirmed_at and attempted_at:
                delta = (
                    datetime.fromisoformat(confirmed_at) - datetime.fromisoformat(attempted_at)
                ).total_seconds()
                if delta >= 0:
                    bucket["durations"].append(delta)

    return {
        "overall": _summarize(_merge(buckets)),
        "per_plugin": [
            {"plugin": key, **_summarize(bucket)} for key, bucket in sorted(buckets.items())
        ],
    }
