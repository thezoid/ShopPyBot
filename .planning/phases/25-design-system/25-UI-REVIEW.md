---
phase: 25
slug: design-system
type: ui-review
status: advisory
overall_score: 20
max_score: 24
baseline: 25-UI-SPEC.md
screenshots: none (code-only audit; Playwright MCP unavailable)
reviewed: 2026-06-25
---

# Phase 25 — UI Audit (6-Pillar)

**Overall: 20/24** (advisory, non-blocking)

| Pillar | Score | Note |
|--------|-------|------|
| 1. Copywriting | 3/4 | All 17 spec strings exact; orphan/missing class drift noted |
| 2. Visuals | 3/4 | Missing `.btn:focus-visible`, undefined `.app-header-title`, orphan `.btn-remove` |
| 3. Color | 4/4 | Zero hardcoded hex; 14 light+dark tokens exact; 60/30/10 correct |
| 4. Typography | 4/4 | 4 sizes / 2 weights / system stack; all via var() |
| 5. Spacing | 4/4 | 7 tokens on scale; px exceptions all documented |
| 6. Experience Design | 2/4 | loadItems/loadCredentials/loadConfig/removeItem lack try/catch; no loading states |

## Resolved this phase (commit follows)

- **Visuals — `.btn:focus-visible` missing** (spec Theme Toggle Contract; WCAG 2.4.7):
  added `.btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }`
  to `components.css`.
- **Visuals — `.app-header-title` undefined** (spec Header Bar Contract: --text-body / weight 600):
  added the rule to `components.css`.

## Deferred (out of Phase 25 scope — design system / UI-01..04)

- **Experience Design — async error handling**: `loadItems()`, `loadCredentials()`,
  `loadConfig()`, `removeItem()` have no try/catch (pre-existing pattern, predates Phase 25).
  Not a UI-01..04 requirement. Candidate for a future robustness pass; tracked here so it is
  not lost. Phase 28 rebuilds several of these surfaces and is the natural place to add
  graceful error/loading states.
- **`.btn-remove` orphan class** on the server-rendered Remove button — harmless (the working
  `.btn-text-destructive` is also applied); cosmetic naming drift between SSR and JS paths.
- **Loading/pending states** for async loads — quality nicety, not in the contract.

## Investigated — not a defect

- **Jinja2 SSR `{{ item[1] }}` "potential XSS"**: FastAPI/Starlette `Jinja2Templates` enables
  autoescaping for `.html` templates by default, so server-rendered cells escape HTML
  (`<b>bold</b>` renders as literal text). The JS path was the real vector and is fixed (UI-03).
- **aria-label initial flash** for dark-mode users: `syncThemeToggle()` corrects the toggle
  label/glyph on load; the sub-frame window before the body script runs is negligible.

*Advisory audit; phase verification already passed 5/5. Two contract gaps fixed inline.*
