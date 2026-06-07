# Phase 11: Cross-Platform Verification - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Verify every front-end command and all three credential backends work on Ubuntu (desktop + headless) and Windows; make OS-specific path handling correct (data/config/log resolve to OS-appropriate user locations, no hardcoded separators); document the verification matrix. Covers XPLAT-01, XPLAT-02. New dep allowed: `platformdirs`.

This is the final milestone phase. It both CHANGES code (path resolution + migration, smoke tests, a CI matrix) and DOCUMENTS verification (docs/PLATFORMS.md + a manual checklist matrix that absorbs the deferred live checks from Phases 8/9/10).

NOT in scope: new features, new platforms, or web-UI changes beyond path/smoke coverage.
</domain>

<decisions>
## Implementation Decisions

### Path Strategy (XPLAT-01)
- Adopt OS-standard per-user directories for data, config, and logs via a new pinned dependency `platformdirs`. A single helper module `core/paths.py` exposes the resolved data dir, config path, and log dir (e.g. `~/.local/share/shoppybot` on Linux, `%APPDATA%\shoppybot` (or platformdirs equivalent) on Windows). All path construction uses pathlib — no hardcoded `/` or `\` separators anywhere.
- Migrate existing project-relative state on first run: if the legacy `data/shop_py_bot.db`, `data/creds.bin`, `config.yml`, and/or `logs/` exist in the old project-relative locations, move (or copy) them ONCE into the new OS-standard locations and log the migration by path (never log secret values). Idempotent: a second run finds the new locations and does nothing.
- Fix the `models.py` CWD-relative DB bug: `DB_PATH = os.path.join('data', 'shop_py_bot.db')` is relative to the current working directory. Re-anchor the DB under the resolved data dir from `core/paths.py` so the bot finds the same DB regardless of where `shoppybot` is launched.
- Update the existing path anchors to route through `core/paths.py`: `core/credentials.py` `_DEFAULT_STORE_PATH` (creds.bin), `core/config_schema.py` `_DEFAULT_YAML_PATH` (config.yml), `logger.py` log dir, `models.py` DB path. The `credentials.data_dir` config override still wins when set.

### Smoke Tests & CI (XPLAT-02)
- Add an environment-independent pytest smoke module that asserts: package imports cleanly, `shoppybot --help` / `setup` (piped-stdin path) / `items` / `config show` run without error, path resolution returns OS-appropriate locations on the host OS, and credential-backend auto-selection picks the right backend. Runs on any OS, no real browser/keyring required.
- Add a GitHub Actions workflow with a matrix over `ubuntu-latest` and `windows-latest` that runs `pip install .[web]`, the full pytest suite, and the smoke module. This is the automated half of the verification matrix.
- Backend-per-OS assertion: a unit test that monkeypatches `_has_real_keyring()` true/false to prove the selection logic chooses the keyring backend when a real keyring is available and the encrypted-file backend when it is not (env-independent). Headless detection reuses the existing `_has_real_keyring()` guard (no active Secret Service → file backend) — no new display-probe code.

### Docs & Verification Matrix (XPLAT-01, XPLAT-02)
- Create `docs/PLATFORMS.md` containing: a per-OS table of the resolved data/config/log paths; the expected credential backend per environment (Windows → keyring, Ubuntu desktop → keyring, Ubuntu headless → encrypted-file); and step-by-step reproduction instructions for the verification matrix.
- Include a manual verification checklist matrix (Ubuntu desktop · Ubuntu headless · Windows × {`--help`, `setup`, `run` smoke, `items`, `config`, `web`} × {keyring, file, env backends}) for the maintainer to fill on real hardware.
- Fold the deferred live checks from prior phases into this matrix: Phase 8 (OS keyring secret survives process restart; headless Ubuntu auto-selects encrypted-file), Phase 9 (`setup` masked TTY entry on Windows PowerShell + Ubuntu), Phase 10 (dashboard renders in a browser; live Start/Stop + log polling; non-local warning banner).

### Claude's Discretion
- The exact `core/paths.py` API shape, the platformdirs app-name/author args, whether migration moves vs copies (recommend move with a kept backup or copy-then-mark), the CI workflow file name/triggers, and the precise smoke-test assertions — provided the locked decisions hold, no secret value is ever logged/migrated in plaintext to a less-protected location, and the existing 335-test suite stays green (path changes must not break tests that rely on project-relative fixtures — use the config override / monkeypatch the paths helper in tests).
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/config_schema.py:17` `_DEFAULT_YAML_PATH = Path(__file__).parent.parent / "config.yml"`; `CredentialsConfig.data_dir` override.
- `core/credentials.py:40` `_DEFAULT_STORE_PATH = Path(__file__).parent.parent / "data" / "creds.bin"`; `_has_real_keyring()` (Phase 8) is the headless-vs-desktop selection mechanism; `_build_store` precedence.
- `logger.py:42-45` log dir `os.path.join(_scriptdir, "logs")`, file `{strftime('%Y%B%d')}.log`.
- `models.py:5` `DB_PATH = os.path.join('data', 'shop_py_bot.db')` — CWD-relative (the bug to fix); `initialize_db` makes the dir.
- `core/cli/` handlers (Phase 9) + `web/` (Phase 10) are the front-end surface to smoke-test.

### Established Patterns
- pathlib + `Path(__file__).parent` anchoring is already used (no hardcoded separators except the CWD-relative models.py DB).
- INFRA-01: every dependency exact-pinned in requirements.txt; new deps need package-legitimacy approval.
- Secrets never logged — migration logs paths/key names only, never values.
- Tests inject paths via config override / monkeypatch (e.g. `yaml_file=` kwarg, `_DEFAULT_STORE_PATH` patching) — keep this seam so path changes don't break the suite.

### Integration Points
- `core/paths.py` (new) becomes the single source of truth consumed by models.py, config_schema.py, credentials.py, logger.py.
- First-run migration runs from a well-defined entry (e.g. BotService init or a paths.ensure() call) before any DB/store/log access.
- CI workflow under `.github/workflows/`.
</code_context>

<specifics>
## Specific Ideas

- SC1 guard: a test/grep asserting no hardcoded path separators remain (no string literals containing `\\` or a bare `/data/`/`/logs/` join) and that paths.py resolves OS-appropriate locations.
- SC3 guard: the mocked-`_has_real_keyring` backend-selection test (keyring vs file).
- Migration must be idempotent and never relocate a plaintext secret into a less-protected place (creds.bin stays encrypted; env-var backend has nothing to migrate).
- The manual matrix is the artifact that finally closes the deferred Phase 8/9/10 human-verification items.
</specifics>

<deferred>
## Deferred Ideas

- Actual execution of the manual matrix on real Ubuntu desktop/headless + Windows hardware — that is the maintainer's manual step (this Windows dev box can verify the Windows column + all automated/mocked checks; the Ubuntu columns require real Linux environments or the CI matrix).
- macOS support — not a target this milestone.
- A packaged installer / distribution — future.
</deferred>

---

*Phase: 11-cross-platform-verification*
*Context gathered: 2026-06-04 via smart discuss (autonomous)*
