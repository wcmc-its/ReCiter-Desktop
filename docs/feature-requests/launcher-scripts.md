# Feature: Double-Click Launcher Scripts

## Goal

A moderately patient non-technical user can install and run ReCiter Desktop without ever opening a terminal. Bar: install Docker Desktop once (vendor's signed installer), then double-click a script in the project folder to start the app — browser opens to the right URL automatically.

This is the realistic ceiling without paying for code-signing certificates. Not technophobe-grade — Docker Desktop itself has a learning curve if it errors — but a meaningful step up from the current `docker compose up` flow.

## Status: Proposed

## Why

True one-click (signed Electron installer) is blocked on $99 + $200–500/yr signing costs (see `docs/milestones/milestone-3-one-click-desktop.md`, parked). The launcher-script approach captures most of the friction reduction at ~one day of work.

## Scope

### In scope

1. **`Start ReCiter.command`** (macOS) — bash script, executable, double-clickable from Finder.
   - Verifies Docker Desktop is installed and running. If not: prints a friendly message and opens https://www.docker.com/products/docker-desktop in the default browser.
   - Finds a free port for the frontend (default 3002, fall through to 3003, 3004, …).
   - Finds a free port for the API (default 8090).
   - Finds a free port for the DB (default 3306, fall through to 3307 — fixes the collision Paul hit with Homebrew mariadb).
   - Exports these as env vars and runs `docker compose up -d`.
   - Polls `http://localhost:$API_PORT/api/health` until 200 or 60s timeout. Surfaces a clear error if the backend doesn't come up.
   - Opens the default browser to `http://localhost:$FRONTEND_PORT`.

2. **`Stop ReCiter.command`** — runs `docker compose down` in the project folder. Same shape, double-clickable.

3. **`Start ReCiter.bat`** (Windows) — equivalent logic in batch (or PowerShell, decide based on which is less hostile to a non-developer who right-clicks → Properties).

4. **`docker-compose.yml` port fix** — change hardcoded ports to env-var-driven so the launcher can override:
   ```yaml
   frontend: "${FRONTEND_PORT:-3002}:3000"
   api:      "${API_PORT:-8090}:8090"
   db:       "${DB_PORT:-3306}:3306"
   ```
   Update the api service's `DATABASE_URL` to use the same `DB_PORT` for the *internal* container network (or keep it on 3306 internally and only vary the host port — simpler).

5. **README update** — replace the current "Development" section's `docker compose up` instructions with a new "Install" section:
   > 1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop).
   > 2. Double-click **Start ReCiter**.
   > 3. The app opens in your browser.

   Move the existing developer-oriented `docker compose` content into a "For Developers" section.

### Out of scope

- Code-signing the scripts. `.command` and `.bat` files trigger fewer Gatekeeper / SmartScreen warnings than `.app` / `.exe` installers; first-run still asks for confirmation but the dialog is one click, not a hunt-for-the-hidden-button.
- Bundling Docker Desktop. Too large; user must install separately.
- Linux. Add later if anyone asks.
- Auto-update. The scripts live inside the cloned/downloaded repo — user gets updates by re-downloading or pulling. Acceptable for now.
- Application icon on the launcher file. Possible via macOS resource forks but fiddly; punt unless someone cares.

## Risks

- **Docker Desktop license cost** — Docker Desktop is free for individuals and small businesses (<$10M revenue, <250 employees) and free for personal/educational/non-commercial open-source use. Within those limits for a WCM-internal demo. If the audience expands to large enterprises, they need a paid license — flag in the README.
- **Port-finder edge case** — if all ports in the fallback range are taken the script needs to fail loudly with a clear message, not crash mid-startup.
- **Slow first start** — `docker compose up` on a cold install pulls the mariadb image (~150 MB). Show a "First-time setup, this may take a few minutes…" message before the long wait.
- **Working directory** — `.command` files on macOS launch with the user's home dir as CWD, not the script's dir. Script must `cd "$(dirname "$0")"` first or every relative path breaks.
- **Browser auto-open timing** — if we open the browser before the frontend is responding the user sees a connection-refused error. Health-poll the frontend (not just the API) before launching the browser.

## Test plan

- macOS clean machine (no Homebrew mariadb): double-click `Start ReCiter.command` → browser opens, app runs.
- macOS with Homebrew mariadb on 3306: same outcome, falls through to 3307.
- macOS with Docker Desktop not installed: friendly prompt, browser opens to Docker download page.
- macOS with Docker Desktop installed but not running: prompt user to start it; recheck after 10s.
- Windows 11 clean machine: equivalent.
- Stop script cleanly tears everything down; restart works.

## Estimate

~1 day. Mostly script-writing and testing on a clean VM.

## Open questions

- Place the scripts at the repo root, or under `bin/`? Repo root is more discoverable for a non-developer downloading a zip; `bin/` is cleaner. Lean repo root with `bin/` symlinks if devs prefer.
- Do the scripts assume the user cloned the repo, or do we ship a zip release with everything pre-arranged? Zip release is friendlier; means cutting a GitHub release for each version. Defer until launcher is working.
- The Stop script — separate file, or have the Start script offer a "Stop" mode when re-launched? Separate file is clearer for non-developers.
