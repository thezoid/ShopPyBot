"""Order confirmation detection for post-checkout URL + DOM verification (BUY-03).

Detects order confirmation after auto_buy() returns True by applying a ~3s settle
delay, reading the live tab URL, and matching a per-platform confirmation fragment.
Extracts order id via URL query param (Amazon) or DOM selector. Returns a
CONFIRMED-<ts> sentinel when the URL matches but no id is extractable, ensuring
purchased is still written on a real confirmation (BUY-03).

No plugin or models imports -- this module only depends on the nodriver tab API
and the logger. writeLog is imported inside function bodies to avoid circular imports.
"""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_SETTLE_SECS = 3.0

# Prefix used when the confirmation URL matches but no order ID is extractable from
# query params or DOM.  The "CONFIRMED-" prefix makes sentinel values distinguishable
# from real Amazon order IDs (format XXX-XXXXXXX) and real BestBuy order numbers.
# Phase 21 retry (BUY-05) MUST NOT treat a sentinel as an idempotency key -- sentinel-
# prefixed order_id values indicate the order MAY have failed silently (e.g., Amazon
# /gp/buy/thankyou reached after a payment failure).  Live UAT must validate this path.
# UAT debt: a payment-failure page that still redirects to the thankyou URL will produce
# a sentinel-marked purchase with purchased=1 but no confirmed order.  Phase 21 must
# treat sentinel order_ids as requiring manual review.
_CONFIRMED_SENTINEL_PREFIX = "CONFIRMED-"

# ---------------------------------------------------------------------------
# Platform confirmation map
# Keys are plugin class names.  url_fragment is the PRIMARY signal (URL-first,
# HIGH confidence).  url_query_params lists query param names to try before DOM.
# selectors are MEDIUM confidence -- UAT debt (live pages not yet verified).
# ---------------------------------------------------------------------------

_PLATFORM_MAP: dict[str, dict] = {
    "AmazonPlugin": {
        "url_fragment": "/gp/buy/thankyou",
        "url_query_params": ["orderID", "orderId"],  # HIGH confidence; try before DOM
        "selectors": ["#confirmedOrderId"],           # MEDIUM confidence -- UAT debt
    },
    "BestBuyPlugin": {
        "url_fragment": "/checkout/r/thank-you",
        "url_query_params": [],
        "selectors": [".thank-you-order-number"],     # MEDIUM confidence -- UAT debt
    },
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _extract_order_id(tab, cfg: dict, current_url: str) -> str | None:
    """Try URL query params first, then DOM selectors.

    current_url must be the already-settled URL snapshot from detect_order_confirmation.
    Receiving it as an argument (rather than re-reading tab.target.url) ensures that the
    fragment check and the query-param extraction operate on the SAME URL -- preventing a
    stale-read race where a post-confirmation redirect moves the tab to a page where the
    orderID param no longer appears (CR-02).

    Returns the first non-empty string found, or None if nothing matches.
    Selector exceptions are logged at DEBUG with exc.__class__.__name__ only
    (never str(exc) -- T-19-05).
    """
    from logger import writeLog

    # URL query param extraction (Amazon orderID -- HIGH confidence)
    for param in cfg.get("url_query_params", []):
        try:
            qs = urllib.parse.parse_qs(
                urllib.parse.urlparse(current_url).query
            )
            val = qs.get(param, [None])[0]
            if val and val.strip():
                return val.strip()
        except Exception as exc:
            writeLog(
                f"[confirmation] url param {param!r} parse error: {exc.__class__.__name__}",
                "DEBUG",
            )

    # DOM selector fallback (MEDIUM confidence -- UAT debt)
    for selector in cfg.get("selectors", []):
        try:
            element = await tab.select(selector, timeout=5)
            if element is None:
                continue
            text = (getattr(element, "text", None) or "").strip()
            if text:
                return text
        except Exception as exc:
            writeLog(
                f"[confirmation] selector {selector!r} error: {exc.__class__.__name__}",
                "DEBUG",
            )

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def detect_order_confirmation(tab, platform: str) -> str | None:
    """Detect order confirmation; return order id str or None.

    URL-first with DOM backup (BUY-03).  Settle delay via tab.sleep() triggers
    browser.update_targets() so tab.target.url is fresh before the check.
    Unknown platforms return None (legacy fallback path, BUY-03 criterion 3).
    URL match without extractable id returns a CONFIRMED-<ts> sentinel so
    purchased is still written on a real confirmation.
    """
    from logger import writeLog

    cfg = _PLATFORM_MAP.get(platform)
    if cfg is None:
        return None  # unknown platform -- legacy fallback

    # Settle: triggers browser.update_targets(), refreshing tab.target.url.
    # Do NOT use `await tab` (calls tab.wait() / sleep(0.5) -- too short).
    await tab.sleep(_SETTLE_SECS)

    current_url = tab.target.url
    if cfg["url_fragment"] not in current_url:
        return None  # not on confirmation page

    order_id = await _extract_order_id(tab, cfg, current_url)
    if order_id:
        return order_id

    # URL matched but no order id extractable -- use sentinel so the
    # orchestrator still writes purchased on a real confirmation (BUY-03).
    # UAT debt: a payment-failure page reaching the thankyou URL also produces this
    # sentinel.  Phase 21 retry must treat _CONFIRMED_SENTINEL_PREFIX values as
    # requiring manual review, not as confirmed idempotency keys.
    ts = datetime.now(timezone.utc).isoformat()
    writeLog(
        f"[confirmation] URL matched for {platform} but no order id found -- "
        f"using sentinel {_CONFIRMED_SENTINEL_PREFIX}{ts}",
        "WARNING",
    )
    return f"{_CONFIRMED_SENTINEL_PREFIX}{ts}"
