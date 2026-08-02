---
phase: 36-mainline-reconciliation
plan: 04
status: complete
completed: 2026-08-02
requirements: [MAIN-07]
---

# Phase 36 Plan 04: pip Dependabot Set

## Outcome

The pip Dependabot set is resolved. One PR merged, two closed as genuinely superseded by the
PR #11 merge. Zero fix-forward attempts consumed.

## Execution Deviation: plan targets went stale mid-flight

This plan was written to merge PRs #16, #17 and #15 in that order. Between planning and
execution, the PR #11 merge landed and Dependabot reacted to it. The plan's PR list no longer
described reality, so the plan's **intent** was executed (resolve the pip set conflict-safely,
direction-check every PR before merging) rather than its literal task list.

The plan's mandatory direction check is what made this safe, and it was vindicated: a blind merge
of PR #16 would have downgraded `cryptography` from the `49.0.0` that wave 2 had just landed back
to `44.0.2`, silently reverting part of MAIN-02.

Like plan 03, this ran inline in the orchestrator's main thread rather than via a `gsd-executor`
subagent, because the harness auto-mode classifier denied that dispatch. Consequence: no
per-task commits.

## Dispositions

| PR | Planned | Actual outcome | Evidence |
|----|---------|----------------|----------|
| #16 cryptography 44.0.2 to 49.0.0 | merge | **CLOSED, superseded** | Closed by `dependabot[bot]` at 19:09:56Z: "Looks like cryptography is up-to-date now, so this is no longer needed." Master already carried `49.0.0` from the wave 2 union resolution. Exactly the outcome the plan predicted |
| #17 setuptools >=61 to >=83.0.0 | merge | **MERGED** at 19:15:55Z | Direction check passed: master was `setuptools>=61`, a genuine upgrade. `pyproject.toml` only, no collision. Master `486e5648` to `2da4d19` |
| #15 pip minor-and-patch group, 12 updates | merge | **CLOSED, superseded** | Closed by `dependabot[bot]` at 19:09:23Z: "Looks like these dependencies are updatable in another way, so this is no longer needed." Replaced by a new PR #21 carrying 10 updates against the post-merge master |

## New Out-of-Scope PR: #21

Dependabot opened PR #21 (`chore(deps): bump the minor-and-patch group across 1 directory with
10 updates`) as the successor to #15. It did not exist when MAIN-07 was written, which names
only #15 through #20.

**Decision: deliberately left open, not merged as part of Phase 36.**

Direction check result: the three MAIN-02 protected pins (`cryptography==49.0.0`,
`httpx==0.28.1`, `pydantic-settings[yaml]==2.14.2`) are untouched context lines, and every
change in the PR is an upgrade rather than a downgrade. So it is not unsafe on those grounds.

The reason for deferring is different. Its `pyproject.toml` half contains:

```
-    "fastapi==0.115.8"        +    "fastapi==0.141.1"
-    "uvicorn[standard]==0.30.6"   +    "uvicorn[standard]==0.52.0"
```

STATE.md records a v4.1 Phase 26 decision: "No new Python dependencies; raw
`StreamingResponse` from starlette (already transitive dep) covers all SSE needs; do NOT add
`sse-starlette`; do NOT upgrade FastAPI to 0.135+ in this milestone." That decision was scoped
to v4.1 and does not automatically bind v5.0, but it exists because the SSE dashboard is
sensitive to FastAPI and starlette churn.

Merging a `0.115 to 0.141` FastAPI jump plus a `0.30 to 0.52` uvicorn jump as the closing act of
the milestone's highest-risk phase would add real SSE regression exposure while satisfying no
requirement. Phase 36 is mainline reconciliation, not dependency upgrades.

Recommended owner: Phase 37 (Distributable Artifact) or Phase 39 (Quality Floor), whichever
first has a reason to touch the dependency surface. It should be merged behind a deliberate
check of the SSE tests (`tests/test_sse.py`, `tests/test_sse_wiring.py`), not merged blind.

## Safety Posture

No force operation. No `--squash`, `--rebase`, `--admin`, or `--auto`. No direct push to master.
`--delete-branch=false` on every merge. Master moved once in this plan, via `gh pr merge`.
Fix-forward attempts consumed: 0.
