# Milestone 3: One-Click Desktop App

## Status: Parked

**Decided 2026-05-12:** path A (Electron + bundled SQLite) rejected on cost. Apple Developer ID ($99/yr) + Windows code-signing certificate ($200–500/yr) are recurring out-of-pocket fees the project will not absorb. Without signing, the installer triggers Gatekeeper / SmartScreen friction that defeats the technophobic-user goal — making an unsigned installer strictly worse than the docker-compose flow for the target user.

**Pivoted to** `docs/feature-requests/launcher-scripts.md` — double-click launcher scripts on top of docker-compose. Lower bar (still requires Docker Desktop install) but ~one day of work and meaningfully reduces friction. Below is preserved for record.

---

## Goal

A technophobic user can run ReCiter Desktop end-to-end with no terminal, no Docker, no command line — download installer, double-click, app window opens, everything works.

Today's bar (`docker compose up`, Node + Python on the host, port collisions) is developer-friendly, not user-friendly. This milestone closes that gap.

## Status: Planning

## Why this path

Path picked from a five-way analysis (see `docs/feature-requests/sample-data-loader.md` thread, 2026-05-12):

- **Electron + bundled SQLite** — chosen. Smallest version of true one-click. SQLite handles the desktop's scale (10k–100k rows) without infra. Codebase already nods at this in `api/auth.py` ("Electron-style packaged shell").
- Electron + embedded MariaDB — keeps schema as-is, larger installer (~200 MB), more moving parts.
- Tauri + SQLite — smaller binary; team isn't on Rust.
- Docker Desktop wrapper — still requires Docker install + browser tab; not one-click for a technophobe.
- Hosted SaaS — different product (auth, multitenancy, data residency).

## What ships

A signed `.dmg` (macOS) and `.exe` (Windows) installer. After install:

- App launches into a native window (Electron BrowserWindow loading the bundled Next.js export).
- Backend (FastAPI) runs as a child process spawned by the Electron main process. Port chosen at runtime from a free range; no host conflicts possible.
- Database file is a SQLite file under `~/Library/Application Support/ReCiter Desktop/` (mac) / `%APPDATA%\ReCiter Desktop\` (win). Auto-created on first launch.
- Sample data button (this milestone's predecessor PR #24) still works — fetches PubMed metadata as before.
- API token continues to live in `~/.reciter-desktop/api-token`, scoped to the local install.

## Major work areas

### Phase 1: Database swap — MariaDB → SQLite
**Priority: Critical (blocks everything)**

- [ ] Audit `api/models.py` for MariaDB-specific column types: `Enum(...)`, `TIMESTAMP` server defaults, `ON DELETE CASCADE` FK behavior, `JSON` column type. SQLite handles each differently or not at all.
- [ ] Audit `api/routers/*.py` for raw SQL — none expected, but verify. Confirm `pipeline_runner.py` uses ORM only.
- [ ] Audit `core/` and `features/` for any database access outside SQLAlchemy. Likely clean but verify.
- [ ] Rewrite alembic migrations 001–004 against SQLite — most schema migrations port directly; `Enum` becomes `CHECK` constraint or `String` with app-level validation.
- [ ] Migration script for users who already ran the MariaDB version: dump from MariaDB → load into SQLite. One-shot, deletable after the first run.
- [ ] Decision: keep MariaDB support behind a `DATABASE_URL` env override (for ReCiterDB-like analytics consumers) or hard-delete? Recommend keep — minimal cost, useful for cross-database parity testing.

### Phase 2: Backend packaging
**Priority: High**

- [ ] Pick a Python packager: **PyInstaller** (most mature, single binary), Pyoxidizer (smaller, Rust-based, less mature), or Nuitka (fastest runtime, compile-heavy).
  - Recommendation: PyInstaller for the first cut. ~50 MB binary including Python runtime.
- [ ] Bundle `scikit-learn`, `xgboost`, `pandas`, `lxml`, etc. PyInstaller hidden-imports list will need iteration.
- [ ] Ship ML models (`models/wcm/*.joblib`) as resource files inside the bundle. Auto-discover relative to executable path, not CWD.
- [ ] Confirm `core/pubmed.py` HTTPS works without OS-level CA bundle issues (PyInstaller-frozen apps sometimes miss `certifi`).
- [ ] FastAPI binary should accept `--port` + `--db-path` flags from the Electron main process.

### Phase 3: Frontend bundling
**Priority: Medium**

- [ ] Switch `next build` from server-rendering to **static export** (`output: 'export'` in `next.config.js`). All current pages are client components — confirm no `headers()` / dynamic server reads block this.
- [ ] Route `NEXT_PUBLIC_API_URL` to a runtime value injected by Electron main into the renderer (since the port is dynamic). Replace the build-time env with a `window.RECITER_API_BASE` global.
- [ ] Re-test the SSE flow (`subscribeSSE` in `frontend/lib/sse.ts`) under Electron's chromium; should work but verify.
- [ ] Bundle static export as a `file://` load or via Electron's `protocol.handle` for `app://` scheme. Latter avoids CORS surprises.

### Phase 4: Electron shell
**Priority: High**

- [ ] Scaffold Electron app with **electron-vite** or **electron-forge**. Forge has better packaging story (notarization, code signing, auto-update).
- [ ] Main process responsibilities:
  - Pick a free port for the backend (`get-port` or equivalent).
  - Spawn the PyInstaller binary as child process with `--port` and `--db-path`.
  - Wait for `/api/health` to return 200 before showing the window.
  - Inject `window.RECITER_API_BASE` into the renderer before page load.
  - Tear down the backend cleanly on quit (catch `before-quit`, send SIGTERM, wait).
  - Crash recovery: if the backend dies, surface a "Backend crashed — restart?" dialog. Don't silently respawn.
- [ ] App icon, About panel, menu bar (minimal — File / Edit / View / Window / Help).
- [ ] First-run experience: detect empty DB, route directly to the institution setup page.

### Phase 5: Distribution
**Priority: Medium**

- [ ] macOS: Apple Developer ID signing + notarization. Without notarization the app is gatekept by Gatekeeper on every machine. Costs $99/yr.
- [ ] Windows: code-signing certificate ($200–500/yr from a recognized CA). Without it SmartScreen will flag the installer.
- [ ] Auto-update via electron-updater pointed at GitHub Releases (or S3). Decide release cadence.
- [ ] CI: GitHub Actions to build mac + win binaries on tag push, attach to release.
- [ ] Linux: out of scope for first cut. AppImage if requested later.

### Phase 6: Testing & rollout
**Priority: High (gates release)**

- [ ] Smoke test on a clean macOS VM (no Docker, no Homebrew, no Python). Install + setup + run pipeline + view results.
- [ ] Same on a clean Windows 11 VM.
- [ ] Migration test: existing user with MariaDB data runs the new installer → opt-in migration prompt → SQLite file populated → app continues working.
- [ ] Performance sanity: 800-researcher pipeline run on the bundled SQLite. Expect SQLite to be *faster* than networked MariaDB for this workload (no socket overhead, WAL mode handles concurrent reads).
- [ ] Documentation: short README section "Download" linking to releases; remove "docker compose up" as the primary install instruction once GA.

## Open questions

- **Multi-user on one machine?** SQLite is single-user-friendly; if two macOS users share a machine each gets their own DB under their own Application Support dir. Confirm acceptable.
- **Where do PubMed-retrieved articles cache?** Currently in the DB. Stays in the DB for SQLite — no separate file store. ~5 KB / article, 100k articles ≈ 500 MB max. Fine.
- **Do we still ship the docker-compose flow for developers?** Recommend yes — keeps the dev loop snappy without an Electron rebuild on every backend change. Just stop marketing it as the install path.
- **What about the existing in-flight branches** (`fix/article-import-run-state`, `feat/sample-data-loader`)? Land them on `main` first. This milestone starts after.
- **PubMed API key entry on first launch** — same UX as today (institution setup page asks). No change needed.

## Out of scope

- Cloud sync, multi-device.
- Real-time collaboration on curation.
- Bundled ReCiter Java engine (we already replaced it with the Python scoring path).
- Mobile.

## Displaces / postpones

This milestone is large enough that Milestone 2 (Pipeline Parity & Performance) and the in-flight feature work should finish first. Recommend ordering:

1. Land `fix/article-import-run-state` (#TBD)
2. Land `feat/sample-data-loader` (#24)
3. Complete Milestone 2 phases 1–5
4. Start Milestone 3

Picking up Milestone 3 before Milestone 2 risks rewriting the DB layer and then immediately re-touching it for the historical-runs work in Milestone 2 Phase 3.

## Estimate

Calendar-time, single developer, with code review and external signing/notarization waits: **6–10 weeks**. Phase 1 (DB swap) is the longest pole; Phase 4 (Electron shell) the most novel.
