# External Integrations

**Analysis Date:** 2026-04-19

## APIs & External Services

**URL Shortening:**
- TinyURL - Shortens product URLs for log output
  - Endpoint: `http://tinyurl.com/api-create.php?url={url}` (HTTP GET, no auth)
  - SDK/Client: `requests` (stdlib-style HTTP)
  - Auth: None required
  - Used in: `main.py:make_tiny()`

## Retail Sites (Selenium-Automated)

**Amazon:**
- Purpose: Stock availability check and automated purchase
- Sign-in URL: `https://www.amazon.com/ap/signin?...` (hardcoded in `amazon_bot.py:amz_sign_in()`)
- Availability detection: Presence of `#add-to-cart-button` or `#buy-now-button` DOM elements
- Purchase flow: quantity dropdown → Buy Now → Place Order (`#submitOrderButtonId`)
- CAPTCHA handling: Manual intervention prompted via `input()` when CAPTCHA XPath detected
- MFA handling: Manual OTP entry prompted via `input()` when `#auth-mfa-form` detected
- Passkey prompt: Manual dismissal required via `input()` between email and password steps
- Auth: `config.yml` keys `app.amz_email`, `app.amz_pwd`
- Purchase state tracked: Yes — `models.py:update_item_purchased()` sets `purchased=1` after order

**BestBuy:**
- Purpose: Stock availability check and automated purchase
- Sign-in URL: `https://www.bestbuy.com/identity/signin` (hardcoded in `bestbuy_bot.py:bb_sign_in()`)
- Availability detection: Presence of `.add-to-cart-button` DOM element
- Purchase flow: Add to cart → `/cart` → checkout → sign-in → CVV entry → `.button--place-order`
- CAPTCHA handling: None implemented
- MFA handling: None implemented
- Auth: `config.yml` keys `app.bb_email`, `app.bb_password`, `app.bb_cvv`
- Purchase state tracked: No — `update_item_purchased()` is NOT called after BestBuy orders

## Data Storage

**Databases:**
- SQLite (stdlib `sqlite3`)
  - File: `data/shop_py_bot.db`
  - Client: Raw SQL, no ORM
  - Schema: single `items` table (id, name, link, auto_buy, quantity, purchased)
  - Managed by: `models.py`

**File Storage:**
- Local filesystem only
  - Sound assets: `sounds/` — `available.mp3`, `buy.mp3`, `notification.mp3`
  - Log files: `logs/YYYY<Month>DD.log` — appended per day, auto-created

**Caching:**
- None

## Authentication & Identity

**Amazon Auth:**
- Implementation: Selenium form automation against Amazon's OpenID signin flow
- Credentials stored: plaintext in `config.yml`
- Session persistence: Relies on Chrome session cookies (not explicitly managed)
- MFA: Supported via manual user intervention pause

**BestBuy Auth:**
- Implementation: Selenium form automation against `https://www.bestbuy.com/identity/signin`
- Credentials stored: plaintext in `config.yml` (email, password, CVV)
- Session persistence: Relies on Chrome session cookies (not explicitly managed)
- MFA: Not supported

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, or equivalent)

**Logs:**
- Custom logger in `logger.py:writeLog()` — colorama-colored terminal output + daily append-log to `logs/`
- Log level controlled by `config.yml` `debug.logging_level` (0=ALWAYS only, 5=TRACE+all)
- Log levels: ALWAYS(0), ERROR(1), WARNING(2), SUCCESS(2), INFO(3), DEBUG(4), TRACE(5)
- Config file re-read on every `writeLog()` call — no caching of log level

**Audio Alerts:**
- pygame plays `sounds/notification.mp3` — CAPTCHA detected or Amazon passkey prompt
- pygame plays `sounds/available.mp3` — item detected in stock
- pygame plays `sounds/buy.mp3` — BestBuy purchase completed

## CI/CD & Deployment

**Hosting:**
- None; local desktop/server execution only

**CI Pipeline:**
- GitHub Actions present (inferred from repo structure); no workflow file read

## Environment Configuration

**Required config (all in `config.yml`, no env vars):**
- `selenium.driver_path` — path to ChromeDriver binary (falls back to webdriver-manager download if missing)
- `app.amz_email` — Amazon account email
- `app.amz_pwd` — Amazon account password
- `app.bb_email` — BestBuy account email
- `app.bb_password` — BestBuy account password
- `app.bb_cvv` — BestBuy payment CVV
- `app.open_browser` — bool; open system browser when item is available but auto_buy is false
- `debug.test_mode` — bool; prevents final purchase button click
- `debug.logging_level` — int 0-5
- `available.items[]` — list of {name, link, auto_buy, quantity} to monitor

**Secrets location:**
- `config.yml` at working directory root (plaintext, excluded from version control via `.gitignore`)
- Template provided: `sample.config.yml`

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None (TinyURL call is one-shot HTTP GET, not a webhook)

---

*Integration audit: 2026-04-19*
