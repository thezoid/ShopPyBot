# Stack Research

**Domain:** Remote plugin manager for a Python retail-bot plugin framework (fetch, pin, verify, install, capability-limit, and index third-party `RetailerPlugin` subclasses) — ShopPyBot v5.0 workstream H / SEED-003
**Researched:** 2026-08-02
**Confidence:** HIGH (all version claims verified against PyPI JSON metadata and official docs; sandboxing claims cross-checked against PEP text and CPython issue tracker)

## Context: What Already Exists

This is not greenfield. The extensibility framework thread of SEED-003 is already built:

- `core/registry.py` `_discover_plugins` walks a directory for `shopbot_plugin_*.py`, isolates import failures (log + skip), and only requires the file live in `plugins_dir`. **A plugin manager's "install" step is: write a validated file into a directory. No new discovery mechanism is needed.**
- `core/plugin_base.py` `RetailerPlugin` has 2 abstract methods, `PLUGIN_API_VERSION = 2`, `__init_subclass__` import-time validation, and `difficulty`/`requires_proxy`/`requires_captcha` metadata attributes already meant to be registry-surfaced.
- `core/paths.py` already wraps `platformdirs.PlatformDirs("shoppybot", appauthor=False)` for `data_dir()`/`log_dir()`, with a `SHOPBOT_DATA_DIR` env override used by tests. The same pattern extends cleanly to a plugin install directory.
- `docs/PLUGIN_REGISTRY.md` defines a 9-column schema today rendered by hand onto a GitHub wiki page (REG-01, still outstanding). This is the natural ancestor of a machine-readable index.
- `requests==2.33.1`, `cryptography==49.0.0`, `platformdirs==4.10.0`, `pydantic==2.13.3` are already pinned dependencies. `pyproject.toml` pins `platformdirs==4.10.0` at the package level too.

Everything recommended below is scoped to close the **distribution** gap (fetch/pin/verify/install/list/update/remove from a repo the maintainer never reviewed), not to rebuild the framework.

## Recommended Stack

### Core Technologies (zero new PyPI dependencies for the core mechanism)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `requests` | 2.33.1 (pinned; 2.34.2 current on PyPI) | Fetch plugin file(s) and manifest over HTTPS from GitHub | Already a pinned dependency. Covers 100% of the fetch need via GitHub's REST Contents API and `raw.githubusercontent.com` — no `git` binary required. |
| `hashlib` (stdlib) | n/a | Compute SHA-256 of fetched bytes for the local pin/lockfile | Zero new dependency. This is the actual trust anchor — see Integrity section. |
| `json` (stdlib) | n/a | Registry index format, per-plugin manifest format, per-install lockfile | Matches existing `plugins list --json` CLI convention (`core/cli/plugins.py`); symmetric stdlib read/write (unlike `tomllib`, which is read-only in stdlib). |
| `pydantic` | 2.13.3 (pinned) | Validate the third-party plugin manifest and registry entries before they touch disk or render in CLI/dashboard | Already pinned. Mirrors the exact pattern `get_platform_config()` already uses for another untrusted-shaped input (CFG-02). A fetched manifest is attacker-controlled data; never `json.loads()` it directly into an f-string or template. |
| `platformdirs` | 4.10.0 (pinned; 4.11.0 current on PyPI) | Resolve the user-writable plugin install directory, per OS | Already pinned and already wrapped by `core/paths.py`. See Paths section for the exact extension. |
| `sys.addaudithook` (stdlib, PEP 578) | n/a (CPython 3.8+) | Best-effort runtime detection/logging of a plugin's sensitive operations | Zero new dependency. Not a sandbox — see Capability Limiting section for exactly what this does and does not stop. |

**No new runtime PyPI dependency is required to fetch, pin, verify, place, or index a plugin.** The only new dependency surface is optional and downstream: `pip` (already ships with the interpreter) invoked via `subprocess` for the *plugin's own declared dependencies* (question 6), never for the plugin fetch itself.

### Supporting Libraries (only if the project wants signature verification later)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `cryptography.hazmat.primitives.asymmetric.ed25519` (already pinned `cryptography==49.0.0`) | n/a — part of the existing pin | Verify a maintainer-signed registry entry (Ed25519 `verify()`/`sign()`) | Only if the project later builds a maintainer-signed central registry (an evolution of REG-01). Not needed for v1. Zero new dependency since `cryptography` is already pinned. |
| `sigstore` (sigstore-python) | 4.5.0 current on PyPI | Keyless signing/verification via Sigstore's transparency log (Rekor) + OIDC identity | **Not recommended — see What NOT to Use.** |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| GitHub REST API — Contents endpoint (`GET /repos/{owner}/{repo}/contents/{path}?ref={sha}`) | Fetch a single plugin file or list a directory at an exact commit, with the git blob `sha` returned alongside content | Base64 content is only returned for files ≤1 MB; for 1–100 MB files, request with header `Accept: application/vnd.github.v3.raw` or use the `download_url` field. A `shopbot_plugin_*.py` file will never approach this limit in practice. |
| `raw.githubusercontent.com/{owner}/{repo}/{40-char-sha}/{path}` | Simpler alternative fetch for plain file bytes, same content-addressing guarantee as the Contents API when the ref is a full commit SHA | No JSON envelope, no base64 decode step, CDN-served. Use as the primary fetch path; treat the Contents API as the source of the git blob `sha` for an extra integrity cross-check. |
| `pip install --target <dir> --no-deps <pkg>==<version>` invoked via `subprocess.run([sys.executable, "-m", "pip", ...])` | Install a plugin's own declared dependencies into a plugin-private directory | Never installs into the app's own environment. See Dependency Isolation section. |

## Installation

```bash
# No new packages for the core plugin-manager mechanism.
# requirements.txt is unchanged for fetch/pin/verify/paths/registry.

# The only NEW invocation is pip itself, already present as part of the
# Python installation, called as a subprocess — not a new pyproject/requirements.txt entry:
python -m pip install --target <plugin_vendor_dir> --no-deps <name>==<version>
```

If the project later adds maintainer-signed registry entries:
```bash
# still zero new deps — Ed25519 is already inside the pinned cryptography package
# no pip install line needed
```

---

## 1. Fetching a plugin from a third-party source

**Recommendation: GitHub REST Contents API / `raw.githubusercontent.com`, both via the already-pinned `requests`. Do not use `git clone`/`git archive` subprocess, `pip install <vcs-url>`, or a generic "plain HTTPS download."**

Rationale against each alternative, given this project's constraints:

- **`git clone`/`git archive` via subprocess** — requires a `git` executable on the user's `PATH`. ShopPyBot's target user is "technically capable individuals," not necessarily developers with a dev toolchain installed; the project has zero existing dependency on `git` being present (its own CI/build/runtime never shells out to git). Adding this would be a new, unverifiable environmental precondition, and it would need per-OS error handling (Windows `git.exe` may or may not be on PATH depending on install method) for a capability `requests` already has.
- **`pip install git+https://github.com/...@<sha>`** — pulls in the *entire* package install machinery: this executes the target repo's build backend (`setup.py`/`pyproject.toml` build-system hooks) during install, which is a **second, earlier** arbitrary-code-execution surface *before* the plugin is even imported (currently the only RCE surface is import time, per `PLUGIN_DEV.md` section 9). It also still shells out to `git` under the hood for the VCS URL. This is strictly worse than the status quo, not better.
- **"Plain HTTPS download"** (e.g., a tarball URL with no structure) — under-specifies the actual mechanism; in practice this collapses to "download a GitHub archive," which has the reproducibility problem covered in the Pinning section below. The Contents/raw API is the structured version of the same idea and is free.
- **GitHub REST Contents API / raw.githubusercontent.com** — `requests.get()`, already-pinned dependency, no external binary, no build-backend execution, works identically for install/update/list/remove.

**Scope decision this implies:** v1 of the plugin manager should be **GitHub-only** (matches REG-01's existing GitHub-wiki-based registry and this repo's own GitHub-native tooling — Dependabot, CodeQL, PVR). Generic Git-host support (GitLab, self-hosted Gitea) is the point at which `git` subprocess would become unavoidable, because those hosts don't expose GitHub's Contents/raw API shape. Treat that as an explicit deferred item, not silently unsupported.

**Confidence: HIGH** — verified against GitHub REST API docs (Contents/blob endpoints) and current rate-limit changelog.

## 2. Pinning to a commit SHA and verifying fetched bytes match the pin

**Pin the commit SHA (40-char, never a branch/tag name) in the fetch URL itself. Do not hash-pin GitHub's tarball/zip *archive* bytes — GitHub does not guarantee those are stable.**

This is the one place training-data intuition is actively wrong and needed verification: GitHub has publicly stated it does **not** guarantee byte-stable checksums for `codeload.github.com` archives (`.../archive/<ref>.tar.gz`) — the compression layer changed once already (Git 2.38's gzip→zlib default change in Jan 2023) and broke every downstream project that had hash-pinned an archive checksum. GitHub's own recommended fix is exactly what this project should do: **fetch by commit SHA, not by hash-of-archive.**

Two fetch shapes, both content-addressed by the commit SHA rather than by archive compression:

1. **`raw.githubusercontent.com/{owner}/{repo}/{commit_sha}/{path}`** — returns the exact file bytes (git blob content), no archive wrapper, no compression-format variability. This is what makes byte-for-byte reproducibility possible: the URL path itself pins the commit, and the response is the raw blob, not a re-serialized archive.
2. **GitHub Contents API `GET /repos/{owner}/{repo}/contents/{path}?ref={commit_sha}`** — returns the same bytes (base64-encoded) *plus* the git blob `sha` (a git object hash of that exact content) in the same response, giving a free cross-check: decode, recompute, compare to the returned `sha` field.

**What each option makes easy or impossible, concretely:**

| Fetch option | Pin to exact SHA? | Byte-stable re-fetch? | Free content hash from the source? |
|---|---|---|---|
| `codeload.github.com/.../archive/<ref>.tar.gz` (or `/tarball/`, `/zipball/`) | Yes (SHA accepted as ref) | **No** — GitHub does not guarantee archive checksum stability, even for the same commit | No (would have to hash the archive itself, which is the thing that isn't stable) |
| `raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}` | Yes (SHA is literally in the URL) | Yes — raw blob bytes, no compression/format layer | No (bytes only, no accompanying hash) |
| GitHub Contents API `?ref={sha}` | Yes | Yes (same underlying blob) | **Yes** — response includes git blob `sha` |

**Recommendation:** fetch via raw.githubusercontent.com for simplicity, cross-verify the git blob `sha` via one Contents API call at install time (cheap — unauthenticated rate limit is 60 req/hour, and an install is a handful of calls), then compute the project's **own** SHA-256 over the received bytes and record *that* in the install lockfile. Don't trust GitHub's blob `sha` (SHA-1, and it's GitHub attesting to its own data) as the sole pin — record an independently computed SHA-256 as the durable local record. See Integrity section.

**Confidence: HIGH** for the archive-instability claim (GitHub's own blog post + LWN + multiple downstream project issues, e.g. spack#5411, easybuild#5151, bazel#3722, libgit2#4343, all describing the same 2023 breakage). **HIGH** for Contents API blob-sha behavior (GitHub REST docs, Contents/blobs pages).

## 3. Integrity and authenticity

**SHA-256 pinning (via stdlib `hashlib`, already-implicit dependency) plus an explicit install-time consent gate is the honest stopping point for this project. Sigstore is not worth it.**

What the lockfile should record (one JSON file per installed plugin, e.g. `<user_data_dir>/plugins/<name>/.shoppybot-install.json`):

```json
{
  "repo": "someuser/shoppybot-plugin-newegg2",
  "commit_sha": "a1b2c3d4e5f6...(40 hex chars)",
  "files": {
    "shopbot_plugin_newegg2.py": "sha256:6f3d...",
    "shoppybot-plugin.json": "sha256:91ab..."
  },
  "plugin_api_version_at_install": 2,
  "registry_verified": false,
  "consented_at": "2026-08-02T18:04:11Z",
  "installed_at": "2026-08-02T18:04:12Z"
}
```

- **Install-time:** fetch bytes, compute SHA-256 locally, show the user the repo, the commit SHA, the file list, and (if the plugin declares any) its dependency list — then require a typed confirmation before writing anything. This directly implements the seed's "explicit install-time consent, naming the source repo and requiring a typed confirm" option.
- **Update-time:** re-resolve the target ref (registry `default_ref`, or a user-supplied new ref), fetch, recompute SHA-256, and **re-run the same consent flow** rather than silently swapping bytes — an update is a new trust decision, not a background refresh.
- **Verify-on-load (optional but cheap):** before `_discover_plugins` imports a third-party file, recompute its SHA-256 and compare to the lockfile. A mismatch means the file was altered on disk after install (tampering, a corrupted write, or a manual edit) — refuse to import and warn, rather than silently executing altered bytes. This is a few lines of `hashlib` code, not a library.

**Why not Sigstore (`sigstore-python` 4.5.0, verified current on PyPI):**

Sigstore proves *who published an artifact* via keyless OIDC-bound signing plus a public transparency log (Rekor). That's the right tool when *this project* wants to prove *its own* releases weren't tampered with in the supply chain (e.g., signing ShopPyBot's own PyPI wheel). It is the wrong tool for verifying *arbitrary third-party plugin authors the maintainer has never vetted*, because:

1. Sigstore verification only tells you the signature matches *some* identity (an email or a repo's OIDC claim) — it says nothing about whether that identity is trustworthy. For a curated central registry, a maintainer-controlled Ed25519 key check (see below) gives the same "did the registry curator vouch for this" answer with zero new dependencies.
2. The dependency cost is real: `sigstore==4.5.0`'s `requires_dist` pulls in `tuf`, `pyOpenSSL`, `rfc3161-client`, `rfc8785`, `pyasn1`, `sigstore-models`, `sigstore-rekor-types`, `pyjwt`, `rich`, `id` — roughly ten new transitive dependencies for a project whose stated posture is "adds new dependencies reluctantly" and exact-pins everything. That is disproportionate to what a hobbyist tool's third-party plugin flow actually needs.
3. Almost no third-party plugin author in this ecosystem will have Sigstore-signed their commits; requiring it would make the feature unusable, and treating its absence as "unverified" is exactly what an explicit consent-gate warning already communicates for free.

**If the project wants something beyond SHA-256 + consent later:** use Ed25519 via the *already-pinned* `cryptography` package to let the maintainer sign entries in the central registry (question 7) — e.g., the registry curator signs `sha256(commit_sha + file_hashes)` for each vetted entry, and the CLI shows "signed by registry maintainer" vs. "unverified third-party" in the consent prompt. This adds zero new dependencies and directly reuses `REG-01` as the trust root, exactly as the seed suggests. This is a **v2 idea**, not a blocker for v1.

**Confidence: HIGH** for sigstore's dependency tree (verified via PyPI JSON `requires_dist` for 4.5.0). **HIGH** for `cryptography`'s Ed25519 support (`hazmat.primitives.asymmetric.ed25519.Ed25519PrivateKey`/`Ed25519PublicKey`, documented in the pyca/cryptography docs, stable since `cryptography` 2.6).

## 4. Where an installed plugin should live on disk

**Add a second, user-writable plugin directory under `platformdirs.user_data_dir`, alongside the existing repo-relative `plugins/` directory, and merge both at discovery time with a provenance tag.**

`core/paths.py` already resolves `data_dir()` via `PlatformDirs("shoppybot", appauthor=False).user_data_dir`, giving `%LOCALAPPDATA%\shoppybot` on Windows, `~/.local/share/shoppybot` on Linux, `~/Library/Application Support/shoppybot` on macOS (all confirmed by the existing `appauthor=False` comment and platformdirs' documented per-OS mapping). The correct extension is a `plugins_dir()` accessor mirroring `data_dir()`/`log_dir()`:

```python
def plugins_dir() -> Path:
    """Return the user-writable third-party plugin directory, honouring SHOPBOT_DATA_DIR."""
    return data_dir() / "plugins"
```

This is a **second** plugin source, not a replacement for the in-repo `plugins/` directory:

- **Bundled `plugins/`** (repo-relative, ships with the package/wheel): the 7 first-party/community plugins already reviewed and shipped. Read-only in the sense that installing the package doesn't let a user write here without editing the install.
- **`<user_data_dir>/plugins/`**: writable at runtime by the plugin manager's `install`/`update`/`remove` commands. Never touched by `pip install shoppybot` itself.

`_discover_plugins(plugins_dir: Path)` already takes a `Path` argument and has no dependency on it being the repo directory — it just needs to be called **twice** (once per source) and the results merged, tagging each discovered plugin with its origin so the CLI/dashboard can render "bundled" vs. "third-party, installed from `<repo>` at `<sha>`" distinctly. This is additive to `PluginRegistry.__init__`, which already takes a single `plugins_dir: Path`; extend it to accept an iterable of `(Path, str)` (dir, source_label) pairs, or call `_discover_plugins` per source and concatenate before constructing instances — either is a small, localized change, not a redesign.

**Why this is safe:** `platformdirs.user_data_dir` is per-user by construction (no elevated permissions needed, no risk of writing into a shared/system location), which is the same safety property that already lets `CredentialStore`'s encrypted-file fallback and the SQLite DB live there without a permissions story. `appauthor=False` is already set project-wide, so the new directory is `.../shoppybot/plugins`, not `.../shoppybot/shoppybot/plugins`.

**Confidence: HIGH** — verified `platformdirs` 4.11.0 is current on PyPI (project pins 4.10.0, one minor behind — no compatibility concern, no urgent need to bump for this feature) and cross-checked the per-OS path semantics against the existing, working `core/paths.py` implementation.

## 5. Capability limiting for imported third-party code in CPython

**Survey conclusion, stated bluntly: nothing available in pure Python, at reasonable cost, stops a malicious plugin from reading the credential store once it is imported. The honest position is that none of the in-process options are a real security boundary here — the seed already says this ("process isolation... is the real fix... by far the most expensive"), and this research confirms it rather than contradicting it.**

| Approach | What it actually stops | What it cannot stop | True cost here |
|---|---|---|---|
| **Import hooks / restricted globals** (e.g. RestrictedPython, custom `exec()` with a stripped `__builtins__`) | Accidental use of a few blocked names if the plugin author isn't trying to get around it | Python's own introspection (`object.__subclasses__()`, `type.__mro__` traversal, `getattr` chains) provides well-documented gadgets to reach unrestricted builtins from a "restricted" namespace; this is exactly why RestrictedPython pairs itself with a real OS sandbox (Zope's historical usage) rather than standing alone. It is also fundamentally the wrong shape for this project: a `RetailerPlugin` legitimately *needs* full filesystem, network, and subprocess access (it drives a real Chrome browser via nodriver/CDP) — restricting the globals a plugin can see would have to allowlist almost everything a malicious plugin would also want, i.e. it protects against almost nothing while adding real breakage risk. | High effort, low payoff, actively wrong for this plugin shape. |
| **`sys.addaudithook`** (PEP 578) | Nothing, by design, unless a hook author explicitly raises inside a hook for a specific audited event (e.g., blocking `os.system`). Its real value here is **detection/logging**, not enforcement: it is documented as "not sandboxing," and CPython's own tracker (bpo-43438 / gh-87604) has an open issue specifically about the docs needing to be clearer that it is not one. | Coverage is incomplete — not every sensitive operation raises an audit event, and pure-Python code paths that don't touch an audited C-level operation (e.g., reading a file via a library that itself doesn't emit `open` in a hook-visible way, or raw `ctypes` calls) are invisible to it. A hook, once added, cannot be removed within the process, but that only protects the hook's own presence — it does not create a boundary. | Very low cost (stdlib, ~10 lines), and worth doing anyway as a **detection** layer — see recommendation below. |
| **Subprocess isolation** (run `check_availability`/`auto_buy` in a child process) | Crash containment (a segfault or hang in one plugin doesn't take down the whole event loop) | Nothing security-relevant on its own: a bare subprocess running as the same OS user has the same filesystem permissions, the same OS keyring access, and the same network access as the parent. It does not stop credential theft; it only isolates *availability*, not *confidentiality*. | Moderate — real IPC/serialization work for a false sense of security unless paired with the next row. |
| **seccomp (Linux) / Landlock (Linux, kernel 5.13+) / AppContainer or Job Objects (Windows)** | A genuine OS-enforced boundary: a correctly configured seccomp/Landlock policy *can* deny filesystem paths and syscalls outright, which is a real answer to "stop this plugin from reading the credential store." | Cross-platform parity is the killer: seccomp/Landlock are Linux-only with no equivalent code path; Windows would need an entirely separate AppContainer/Job Object implementation. ShopPyBot explicitly targets Windows-first (its own `platformdirs`/CI-matrix history treats Windows as a first-class target, and this very research session is running on Windows 11). Building and maintaining two OS-specific sandboxing implementations is a project of its own. | High — this is the "real fix," and it is exactly as expensive as the seed already flags it. Correctly deferred. |
| **WASM (Pyodide or similar)** | Genuine memory/syscall sandboxing (Wasm's own security model) | Fundamentally incompatible with this plugin's job: a `RetailerPlugin` needs a real Chrome process reachable over CDP, real filesystem access to chromedriver/session files, and real outbound network sockets. None of that is available inside a Wasm sandbox without punching a hole through the sandbox for exactly the capabilities that matter — at which point the sandbox provides no protection for the things that actually need protecting. | Not viable for this plugin shape at all — not a cost tradeoff, a category mismatch. |

**What is worth doing anyway, given that real isolation is out of scope for v1:**

1. **`sys.addaudithook` as a detection/forensics layer**, not enforcement. Register a hook before `_discover_plugins` imports any third-party file, log (at WARNING) any audited event matching a short list of interesting names (`os.system`, `subprocess.Popen`, `socket.connect` to non-plugin-domain hosts, `open` outside the plugin's own directory tree or the app's documented data dirs) tagged with the plugin's name. This does not stop anything, but it means a malicious plugin's behavior leaves a trail the user or the maintainer can review after the fact — proportionate to "SHA-pin + explicit consent" being the stated trust model, and it costs a dozen lines of stdlib code.
2. **Consent gate that specifically names the risk** (question 3/seed thread 2): the install-time prompt should say, in plain language, that a plugin can read the encrypted credential store, browser session cookies, and everything else the main process can reach — not just "do you trust this repo?" generically.
3. **Do not represent any of the above as a security boundary in user-facing copy.** The audit-hook logging and the consent gate are honest about being detection and informed-consent, respectively — neither is containment. Overstating either would be worse than not building them.

**Confidence: HIGH** — PEP 578 text itself states "this is not sandboxing"; CPython issue tracker confirms ongoing acknowledgment that docs under-communicate this; RestrictedPython's own documented pairing with OS-level sandboxes for real security is consistent across multiple sources; Landlock's 5.13+ kernel requirement and Linux-only scope is documented in the kernel's own Landlock docs and PEP 684/554 discussion threads about subinterpreter isolation limits (subinterpreters were also checked and explicitly are not a security boundary either — untrusted code escapes them too, per the PEP 684 discussion thread).

## 6. Plugin-declared dependencies without polluting the app's environment

**Yes, a plugin should be able to declare pinned dependencies, installed via `pip install --target <plugin-private dir> --no-deps <name>==<version>` per declared entry, run as a subprocess, never into the app's own site-packages/venv.**

Mechanism:

1. The plugin's own manifest (question 7) declares a flat list of pinned dependencies, e.g. `["lxml==5.3.0", "beautifulsoup4==4.13.0"]` — no VCS URLs, no unpinned ranges (mirrors this project's own "exact-pinned, added reluctantly" posture, now extended to third-party plugin authors).
2. At install-consent time, show the user the exact dependency list alongside the plugin's own repo/SHA — a plugin declaring a dependency is a second thing the user is consenting to, not a hidden side effect.
3. Install each into a plugin-private directory: `<user_data_dir>/plugins/<name>/_vendor/`, via:
   ```python
   subprocess.run(
       [sys.executable, "-m", "pip", "install",
        "--target", str(vendor_dir), "--no-deps", f"{pkg_name}=={pkg_version}"],
       check=True,
   )
   ```
   `--no-deps` is deliberate: install exactly the pinned version the manifest declared, nothing pip decides to pull in transitively without the user having seen it in the consent prompt. If a declared dependency itself has required sub-dependencies, the manifest should declare those explicitly too (flat list, no surprises) — this is a stricter posture than a normal `requirements.txt`, appropriate given the trust level.
4. At import time, extend `sys.path` with `_vendor/` **only while importing that specific plugin's module**, and **append** (never `insert(0, ...)`) so the plugin's private copy can never shadow one of the app's own already-pinned dependencies (e.g., a malicious plugin declaring `cryptography==0.0.1` cannot cause the app's own `import cryptography` to resolve to that copy, because the app's own dependency resolves first via normal `sys.path` order / `sys.modules` caching).

This is the same shape `pip install --target` is documented to solve (isolated per-project dependency directories) applied per-plugin instead of per-project, using only `pip` itself (which already ships with the interpreter — not a new `requirements.txt`/`pyproject.toml` line) as a subprocess, invoked by the app rather than by the user.

**Explicitly not `pip install -e`, not installing into the app's active environment, not a VCS URL as a dependency source (a plugin's dependency should come from PyPI via a pinned version, not "yet another arbitrary repo" — chaining trust decisions through a plugin's own dependency graph is exactly the kind of transitive trust problem a hobbyist tool should refuse to take on).**

**Confidence: MEDIUM-HIGH** — `pip install --target` behavior and its PYTHONPATH/sys.path implications are well-documented pip functionality (pip.pypa.io); the per-plugin sys.path-scoping pattern (append-only, import-time-scoped) is a reasoned design applying that primitive, not something separately citable — flagged here as the recommended design, not a verified third-party pattern.

## 7. Machine-readable registry index format

**Two-tier JSON, modeled directly on the closest real-world analog: Home Assistant's HACS and Obsidian's community plugin registry — both solve exactly this problem (import-and-execute third-party code, installed from GitHub repos the core maintainers never reviewed, indexed by a central machine-readable file).**

Both surveyed systems converge on the same shape, which maps cleanly onto what already exists in this repo:

| Layer | HACS | Obsidian | ShopPyBot equivalent |
|---|---|---|---|
| Central index (curated, one file, lists known plugins) | HACS's own default-repositories list | `community-plugins.json` — array of `{id, name, author, description, repo}` | A new `docs/plugin_registry.json` — the machine-readable evolution of the existing `docs/PLUGIN_REGISTRY.md` 9-column spec, replacing the human-only GitHub wiki (REG-01) |
| Per-plugin manifest (lives in the third-party repo itself, root of the repo) | `hacs.json` (name, content_in_root, filename, etc.) + the integration's own `manifest.json` (name, version, min core version) | `manifest.json` (id, name, version, minAppVersion, author, description) | A new `shoppybot-plugin.json` at the third-party repo's root |

**Central index schema (`docs/plugin_registry.json`, lives in *this* repo, PR-reviewable, git-diffable — an explicit improvement over the wiki, which nothing diffs today):**

```json
[
  {
    "name": "AmazonPlugin",
    "repo": "shoppybot-org/shoppybot",
    "platform": "Amazon",
    "domain_patterns": ["amazon.com", "amazon.co.uk", "amazon.ca"],
    "maintainer": "maintainer-username",
    "difficulty": "hard",
    "methods_implemented": ["setup", "teardown", "login", "detect_captcha"],
    "last_verified": "2026-06-09",
    "requires_proxy": false,
    "requires_captcha": false,
    "plugin_api_version": 2,
    "default_ref": "a1b2c3d4e5f6...(commit sha the registry curator vouches for)",
    "bundled": true
  }
]
```

This is a 1:1 field mapping from the existing `docs/PLUGIN_REGISTRY.md` table plus two additions this feature needs: `plugin_api_version` (compatibility gate against `PLUGIN_API_VERSION = 2`) and `default_ref` (a **commit SHA**, never a branch — consistent with the Pinning section above; the registry curator's vouching is only meaningful if it's pinned).

**Per-plugin manifest schema (`shoppybot-plugin.json`, lives in the third-party repo, fetched at install time via the same content-addressed mechanism as the plugin file — treat this as untrusted, attacker-controlled input and validate with `pydantic` before it touches disk or a UI):**

```json
{
  "name": "NewEgg2Plugin",
  "entry_file": "shopbot_plugin_newegg2.py",
  "platform_key": "newegg2",
  "domain_patterns": ["newegg.com"],
  "plugin_api_version": 2,
  "version": "0.3.1",
  "dependencies": ["lxml==5.3.0"],
  "difficulty": "medium",
  "requires_proxy": false,
  "requires_captcha": false,
  "repo": "someuser/shoppybot-plugin-newegg2"
}
```

**Both are JSON, not TOML or YAML, deliberately:** `json` is fully symmetric in the stdlib (read *and* write); `tomllib` (stdlib since 3.11, already the project's Python floor) is read-only — writing TOML would need a third-party `tomli-w` or similar. `pyyaml` is already pinned and would work too, but JSON is simplest for a fetched-over-HTTP, machine-authored, machine-read structure, and matches the CLI's existing `--json` convention (`core/cli/plugins.py`) — pick one format, and this project already leans JSON for exactly this kind of surface.

**A plugin not present in the central index is still installable** (that is the entire point of thread 1 — third-party repos the maintainer never reviewed) — but the CLI consent prompt should render differently for a registry-known entry (shows the curator-recorded difficulty/proxy/captcha metadata inline) versus an unknown one ("NOT in the ShopPyBot plugin registry — fully unverified source, proceed at your own risk").

**Confidence: MEDIUM-HIGH** — HACS's `hacs.json`/`manifest.json` split and Obsidian's `community-plugins.json`/`manifest.json` split are both confirmed via their own developer docs (hacs.xyz, docs.obsidian.md/Reference/Manifest); the specific field names proposed for ShopPyBot's own schema are a reasoned adaptation of the existing `docs/PLUGIN_REGISTRY.md` spec, not an independently-verified external standard.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| GitHub REST Contents API + `raw.githubusercontent.com` via `requests` | `git clone`/`git archive` subprocess | Only if the project later supports non-GitHub hosts (GitLab, self-hosted Gitea) — those don't expose GitHub's Contents API shape, so generic Git-host support genuinely needs `git`. Not needed for v1's GitHub-only scope. |
| SHA-256 pin (stdlib `hashlib`) + explicit consent gate | Ed25519-signed registry entries via existing `cryptography` pin | Once a maintainer-curated, actively-signed registry exists (a v2 evolution of REG-01). Zero new dependency either way since `cryptography` is already pinned — a genuine "when trust model matures" upgrade, not a cost tradeoff. |
| SHA-256 pin + consent gate | Sigstore (`sigstore-python`) | Only if this project starts *publishing its own signed releases* (a different problem — proving ShopPyBot's own PyPI wheel wasn't tampered with) — not for verifying arbitrary third-party plugin authors who almost certainly haven't Sigstore-signed anything. |
| `pip install --target` per-plugin, subprocess-invoked, append-only `sys.path` | Full per-plugin `venv` + subprocess-isolated plugin execution | Only if the project commits to real process isolation for plugin *execution* (not just dependency install) — the "real fix" the seed already flags as expensive and out of scope for v1. |
| `sys.addaudithook` for detection/logging only | seccomp/Landlock (Linux) + AppContainer/Job Objects (Windows) for real enforcement | Only as part of a dedicated, budgeted process-isolation milestone — cross-platform parity work this size does not fit inside v5.0 workstream H. |
| Two-tier JSON registry (central index + per-repo manifest) | Single flat JSON registry with everything centrally maintained | If the project decides it will only ever support registry-known plugins (no arbitrary third-party install) — but that contradicts the seed's explicit goal ("without that plugin ever being merged into this one"). |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|--------------|
| `git clone`/`git archive` subprocess as the primary fetch mechanism | Requires an external `git` binary on the user's PATH with no existing project dependency on one; adds per-OS PATH-detection error handling for a capability `requests` already covers | GitHub REST Contents API / `raw.githubusercontent.com` via `requests` |
| `pip install git+https://...@<sha>` as the plugin fetch mechanism | Executes the target repo's build backend during install (a second RCE surface *before* import-time execution); still requires `git` under the hood for the VCS URL | Direct content fetch (raw/Contents API) of a plain `.py` file (or small file set); reserve `pip` for the plugin's own *declared PyPI dependencies* only (question 6), never for fetching the plugin itself |
| Hash-pinning a GitHub archive (`codeload.github.com/.../archive/<ref>.tar.gz`) | GitHub does not guarantee archive byte-stability across re-downloads of the same ref — publicly documented, has broken multiple downstream projects (spack, easybuild, bazel, libgit2) | Pin the commit SHA in the fetch URL itself (raw content or Contents API), not a hash of a re-compressed archive |
| `sigstore-python` (4.5.0) | ~10 new transitive dependencies (`tuf`, `pyOpenSSL`, `rfc3161-client`, `rfc8785`, `pyasn1`, `sigstore-models`, `sigstore-rekor-types`, `pyjwt`, `rich`, `id`) for a trust model (OIDC-bound publisher identity) that doesn't fit "arbitrary unvetted third-party plugin author"; disproportionate for a project that adds dependencies reluctantly | SHA-256 pin + explicit consent gate now; optional Ed25519 via the already-pinned `cryptography` package later, only for maintainer-signed registry entries |
| RestrictedPython / AST-level sandboxing of plugin code | A `RetailerPlugin` legitimately needs full filesystem/network/subprocess access to drive a real browser — a restricted namespace would have to allowlist nearly everything a malicious plugin would also want, providing near-zero real protection while adding real breakage risk; known introspection-based escapes (`__subclasses__()`, `getattr` chains) are well documented | Consent gate + SHA pin + audit-hook logging (detection, not enforcement); defer real isolation |
| seccomp/Landlock/container sandboxing for v1 | Real protection, but Linux-only (Landlock needs kernel 5.13+), no native Windows equivalent, and this project is Windows-first; the seed itself already flags this as "the real fix... by far the most expensive" — a dedicated milestone, not a workstream-H line item | Ship consent + SHA pin + capability *logging* now; scope process isolation as its own future milestone if it's ever prioritized |
| WASM / Pyodide sandboxing | Category mismatch, not a cost tradeoff — a plugin needs a real Chrome process over CDP, real sockets, real filesystem access; none of that is available inside a Wasm sandbox without defeating the sandbox's purpose | N/A — not viable for this plugin shape |
| TOML for the registry index or per-plugin manifest | `tomllib` is stdlib-read-only (3.11+); writing TOML needs a third-party library the project doesn't otherwise need; no benefit here since neither file is meant to be hand-edited by a human in this project's own repo workflow the way `config.yml` is | JSON — matches existing `--json` CLI convention, fully symmetric stdlib read/write |
| `packaging` library for `PLUGIN_API_VERSION` comparison | `PLUGIN_API_VERSION` is a plain int (currently `2`) — a semver-parsing dependency solves a problem that doesn't exist here | Plain integer comparison (`plugin_api_version >= MIN_SUPPORTED`) |
| GitPython / pygit2 | Heavier bindings (pygit2 statically links libgit2 — a large new binary dependency) that only generalize to "any Git host," which isn't this project's v1 scope (GitHub-only, per REG-01); gives no capability the GitHub REST/raw endpoints don't already provide more simply for the GitHub-hosted case | GitHub REST Contents API / raw content fetch via `requests` |

## Stack Patterns by Variant

**If the plugin manager stays GitHub-only (recommended for v1):**
- Use `raw.githubusercontent.com` + GitHub Contents API exclusively via `requests`.
- Because it needs zero new dependencies and matches this repo's own GitHub-native tooling (Dependabot, CodeQL, PVR) — the whole project already assumes GitHub as the host.

**If the project later wants a maintainer-curated "verified" tier distinct from "arbitrary install":**
- Use Ed25519 signing of registry entries via the already-pinned `cryptography` package.
- Because it reuses REG-01 as the trust root exactly as the seed suggests, at zero new dependency cost, without pretending to solve the harder problem Sigstore solves (publisher identity for the project's *own* releases).

**If a future milestone commits real budget to process isolation:**
- Revisit seccomp/Landlock (Linux) and AppContainer/Job Objects (Windows) as a dedicated cross-platform sandboxing milestone, not a line item here.
- Because it is the only option surveyed that is an actual security boundary rather than detection/consent — but it is expensive and platform-fragmented enough to deserve its own scoping pass, exactly as PROJECT.md's "Future Candidate Directions" already lists it separately from v5.0.

## Version Compatibility

| Package | Pinned | Current on PyPI | Notes |
|---------|--------|------------------|-------|
| `requests` | 2.33.1 | 2.34.2 | No functional gap for this feature; both support everything needed (`requests.get`, JSON decode, custom headers for the raw-media-type fallback). Bumping is a housekeeping item, not a blocker. |
| `cryptography` | 49.0.0 | 50.0.0 | `hazmat.primitives.asymmetric.ed25519` has been stable since `cryptography` 2.6 — no version-specific gap for the optional Ed25519 path. |
| `platformdirs` | 4.10.0 | 4.11.0 | `PlatformDirs(...).user_data_dir` behavior unchanged across this range; no compatibility risk for the new `plugins_dir()` accessor. |
| `pydantic` | 2.13.3 | (not separately re-verified this session; already current per v4.2 close) | Used identically to the existing `get_platform_config()` pattern — no new API surface required. |
| `sigstore` | not pinned (NOT recommended) | 4.5.0 | Documented here only to support the "why not" analysis; do not add. |
| Python | `>=3.11` (project floor, per `pyproject.toml`) | n/a | `tomllib` (stdlib) would be available if TOML were chosen; not needed since JSON is recommended. |

## Sources

- https://docs.github.com/en/rest/repos/contents — Contents API endpoint shapes, 1 MB base64 threshold, `Accept: application/vnd.github.v3.raw` fallback (HIGH)
- https://docs.github.com/en/rest/git/blobs — blob endpoint, base64 content + `sha` field, integrity cross-check mechanics (HIGH)
- https://github.blog/open-source/git/update-on-the-future-stability-of-source-code-archives-and-hashes/ — GitHub's own statement that archive checksums are not guaranteed stable (HIGH)
- https://lwn.net/Articles/921787/ — "Git archive generation meets Hyrum's law," Git 2.38 gzip→zlib default change breaking archive checksums (HIGH)
- Multiple downstream project issues confirming the same archive-instability breakage: spack#5411, easybuild-easyconfigs#5151, bazel#3722, libgit2#4343 (MEDIUM-HIGH, corroborating community reports)
- https://github.blog/changelog/2025-05-08-updated-rate-limits-for-unauthenticated-requests/ — current unauthenticated rate limit (60 req/hr) applying to both `api.github.com` and `raw.githubusercontent.com` (HIGH)
- https://peps.python.org/pep-0578/ — PEP 578 text, explicit "this is not sandboxing" framing (HIGH)
- https://github.com/python/cpython/issues/87604 — open issue on `sys.addaudithook` docs needing clearer non-sandbox framing (HIGH)
- https://peps.python.org/pep-0684/ and the associated discuss.python.org thread on extending subinterpreters with sandboxing — subinterpreters are not a security boundary either (MEDIUM, discussion-thread sourced)
- https://pypi.org/pypi/sigstore/json — `sigstore` 4.5.0 current, full `requires_dist` transitive dependency list (HIGH)
- https://pypi.org/pypi/cryptography/json — `cryptography` 50.0.0 current on PyPI vs. 49.0.0 pinned (HIGH)
- https://pypi.org/pypi/requests/json — `requests` 2.34.2 current on PyPI vs. 2.33.1 pinned (HIGH)
- https://pypi.org/pypi/platformdirs/json — `platformdirs` 4.11.0 current on PyPI vs. 4.10.0 pinned (HIGH)
- https://github.com/pyca/cryptography — Ed25519 signing/verification API (`Ed25519PrivateKey`/`Ed25519PublicKey`, `sign()`/`verify()`, `from_public_bytes()`) (HIGH)
- https://pip.pypa.io/en/stable/cli/pip_install/ — `--target` isolation semantics, PYTHONPATH implications (HIGH)
- https://hacs.xyz/docs/publish/start/ — `hacs.json` manifest shape, repository structure convention (MEDIUM-HIGH)
- https://docs.obsidian.md/Reference/Manifest — `manifest.json` schema; `community-plugins.json` central index shape (MEDIUM-HIGH)
- In-repo: `E:\repos\ShopPyBot\core\registry.py`, `core/plugin_base.py`, `core/paths.py`, `core/cli/plugins.py`, `docs/PLUGIN_REGISTRY.md`, `plugins/PLUGIN_DEV.md`, `.planning/seeds/SEED-003-remote-plugin-manager-and-extensibility-framework.md`, `requirements.txt`, `pyproject.toml` (existing implementation surveyed directly, not inferred)

---
*Stack research for: ShopPyBot v5.0 workstream H — Remote plugin manager (SEED-003)*
*Researched: 2026-08-02*
