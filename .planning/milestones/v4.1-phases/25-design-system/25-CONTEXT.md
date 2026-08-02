# Phase 25: Design System - Context

**Gathered:** 2026-06-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Redesign the FastAPI dashboard on a coherent, vendored, zero-dependency design
system: CSS custom-property tokens + reusable component classes, automatic and
manual light/dark theming with no flash-of-unstyled-content, the existing XSS at
`dashboard.html` fixed via safe DOM construction, and the non-local warning
banner + CSRF origin protections preserved. Pure frontend / web-layer; zero
Python behavior changes. Covers UI-01, UI-02, UI-03, UI-04.

</domain>

<decisions>
## Implementation Decisions

### Design System Structure & Tokens
- 3-file CSS split: `tokens.css` (`:root` light + dark blocks), `components.css`
  (component rules using only `var(--xxx)`), `dashboard.css` reduced to layout +
  `@import` of the other two.
- Semantic token naming (`--color-bg`, `--color-surface`, `--color-text`,
  `--color-accent`, `--space-md`, etc.) over raw palette scales — survives theme
  swap cleanly.
- Keep system font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`)
  at 14px base. Zero external/vendored fonts (hard milestone constraint).
- 4px-based spacing scale (4/8/16/24/32) and 4px border-radius — matches current.

### Theming (Light/Dark)
- `data-theme` attribute on `<html>` + `prefers-color-scheme` auto default +
  persisted manual override in localStorage (UI-02 mandate).
- FOUC prevention: inline `<script>` as the FIRST child of `<head>` that reads
  localStorage and sets `data-theme` before any CSS paints.
- Theme toggle is a small button in a sticky top header bar; icon via unicode or
  inline SVG (no icon font).
- Default when no stored preference: follow `prefers-color-scheme` (auto).

### Visual Direction & Density
- Clean, minimal, utilitarian aesthetic (refined version of current look) — an
  operator tool, not a marketing page.
- Keep blue accent (`#2563eb`) with a dark-mode variant; retain green/amber/red
  semantic status colors.
- Single-column layout, max-width 900px, centered; add a sticky top status/header
  bar that hosts the theme toggle and reserves space for uptime (preps OBS-09).
- Comfortable density (14px type, 8px paddings).

### Charts & Security Scope
- Vendor uPlot 1.6.32 (MIT, ~52KB IIFE + ~1KB CSS) now for use in Phase 28 price
  charts — tooltips add real value on sparse data. Place in `web/static/vendor/`
  (`uplot.iife.min.js` + `uplot.min.css`), committed to the repo.
- XSS scope: fix the `loadItems()` `innerHTML` bug AND refactor all existing
  `innerHTML` usages in `dashboard.html` (items, credentials, config) to
  `textContent`/`createElement`; add an `escHtml()` helper for any unavoidable
  SVG string interpolation.
- Regression guard: existing MC-4 test (non-local banner + CSRF origin) is a
  done-condition for the phase; add a CI grep/assertion blocking `innerHTML =`
  on API-sourced data.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `web/static/dashboard.css` (181 lines) — existing minimal vendored CSS with
  hardcoded hex colors; becomes the layout file after tokens/components extracted.
- `web/templates/dashboard.html` (369 lines) — single Jinja2 template with inline
  `<script>`; four `card` sections (Controls, Items, Credentials, Config).
- Existing component vocabulary to preserve: `.card`, `.btn`/`.btn-accent`/
  `.btn-destructive`/`.btn-sm`/`.btn-text-destructive`, `.status-dot`, `.log-pre`,
  `.form-group`, `.field-error`/`.field-feedback`, `.banner-warning`,
  `.text-secondary`.

### Established Patterns
- Static served from `web/static/`; template from `web/templates/`.
- Jinja2 renders initial state; client JS (`loadItems`/`loadCredentials`/
  `loadConfig`) hydrates via `fetch` to `/api/*`.
- Non-local banner is gated by `{% if is_non_local %}` (MC-4).

### Integration Points
- `dashboard.html` `<head>` — add inline theme-init script + link new CSS files.
- `web/routes/pages.py` serves the template; no route changes expected.
- New `web/static/vendor/` directory for uPlot.

### Known Issues To Fix
- XSS: `dashboard.html` ~line 241 `tr.innerHTML` interpolates `item.name`/
  `item.link` (also creds ~255, config-safe). Fix to safe DOM.

</code_context>

<specifics>
## Specific Ideas

- Research SUMMARY (.planning/research/SUMMARY.md) is the authoritative spec for
  this phase; Phase A section pre-decides file split, chart pick, XSS fix, FOUC.
- Sticky header bar is the seam for OBS-09 uptime and SSE "Live/Reconnecting"
  indicator in later phases — build the slot now, populate later.

</specifics>

<deferred>
## Deferred Ideas

- Actual observability surfaces (health cards, charts, log viewer) — Phase 28.
- SSE wiring and live updates — Phases 27/29.
- Per-item price capture for non-Amazon plugins (PRC-01) — future milestone.

</deferred>
