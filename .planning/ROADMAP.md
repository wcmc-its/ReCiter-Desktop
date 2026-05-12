# Roadmap: ReCiter Desktop

## Milestones

- ✅ **v1.0 Core Pipeline** - Phases 1-N (shipped 2026-04-04)
- ✅ **v1.1 Statistics & Validation View** - Phases 1-3 (shipped 2026-04-05)
- 🚧 **v2.0 Pipeline Parity & Performance** - Phases 4-8 (in progress)
- 📋 **v2.1 Retrieve & Score — UX, Bugs & Robustness** - Phases 9-11 (planned)

## Phases

<details>
<summary>✅ v1.0 Core Pipeline — SHIPPED 2026-04-04</summary>

What shipped: Docker Compose app (Next.js + FastAPI + MariaDB), institution setup, researcher upload, PMID/assertion import, XGBoost scoring pipeline, per-researcher results, CSV export, sidebar navigation with prerequisite gates, incremental pipeline runs.

</details>

<details>
<summary>✅ v1.1 Statistics & Validation View — SHIPPED 2026-04-05</summary>

What shipped: Backend stats endpoint (ROC/AUC with bootstrap CI, calibration, PR curve, score distribution, disagreements), Stats page frontend (4 Recharts charts, metric cards, disagreements table), workflow wiring (sidebar entry with prerequisite gate, pipeline completion CTA).

### Phase 1: Backend Stats Endpoint
**Goal**: The `/api/stats` endpoint exists, returns statistically correct chart data for all four visualizations, and exposes viability flags that prevent misleading output
**Depends on**: Nothing (first phase)
**Requirements**: STATS-01, STATS-02, STATS-03, STATS-04, STATS-05, STATS-06
**Success Criteria** (what must be TRUE):
  1. `GET /api/stats` returns ROC curve points, AUC scalar, and 95% bootstrap CI (1000 resamples) when at least one (score, assertion) join pair exists
  2. Calibration bins use 10 uniform buckets; response includes n-per-bin counts and a `calibration_viable: false` flag when fewer than 50 joined pairs exist
  3. PR curve includes `pr_baseline` anchored to the actual positive rate (`n_accepted / n_total`), not hardcoded 0.5
  4. Score distribution response contains ACCEPTED and REJECTED counts per 10-point bucket covering 0–100
  5. Top-10 disagreements are ranked by `|score - assertion_value|` (ACCEPTED=100, REJECTED=0) and returned with person_id, pmid, score, assertion
  6. Response includes `viable` flag and `below_n_threshold` warning when n < 50; returns a structured error when all assertions are the same label (single-class)
**Plans:** 3/3 plans complete

Plans:
- [x] 01-01-PLAN.md — Wave 0: Test suite scaffolding (15 unit tests for STATS-01 through STATS-06)
- [x] 01-02-PLAN.md — Stats service implementation (all computation functions + data prep)
- [x] 01-03-PLAN.md — Router + wiring (HTTP layer + main.py registration)

### Phase 2: Workflow Wiring and Navigation
**Goal**: The stats page is reachable from the sidebar and from pipeline completion, and is locked behind the correct gate condition
**Depends on**: Phase 1
**Requirements**: NAV-01, NAV-02, NAV-03
**Success Criteria** (what must be TRUE):
  1. Sidebar shows a "Statistics" item that is locked with a prerequisite message when no (score, assertion) joined pairs exist in the database, and unlocked otherwise
  2. Pipeline completion page displays a "View Statistics" CTA link when assertions exist; the link is absent when no assertions exist
  3. Navigating to `/stats` when the gate is not met shows the prerequisite gate UI; navigating when it is met renders the stats page
**Plans:** 2/2 plans complete

Plans:
- [x] 02-01-PLAN.md — Backend assertion_count field + WorkflowContext extension
- [x] 02-02-PLAN.md — Sidebar entry, pipeline CTA, /stats route with gate

### Phase 3: Stats Page Frontend
**Goal**: Users can view four charts, benchmark reference lines, and a strongest-disagreements table on a single stats page that accurately represents their pipeline run quality
**Depends on**: Phase 2
**Requirements**: CHART-01, CHART-02, CHART-03, CHART-04, BENCH-01, BENCH-02, BENCH-03, DISAG-01, DISAG-02
**Success Criteria** (what must be TRUE):
  1. ROC curve renders with diagonal chance reference line, AUC headline value with 95% CI, and WCM/Fred Hutch AUC reference lines overlaid; calibration plot renders with n-per-bin overlay and a warning banner when `calibration_viable: false`
  2. Score distribution histogram shows ACCEPTED bars in green and REJECTED bars in red per 10-point bucket; PR curve renders with a prevalence-anchored no-skill baseline line and WCM/Fred Hutch AUC-PR reference lines
  3. Summary row at top of page shows institution AUC, WCM AUC, and Fred Hutch AUC as a three-column comparison
  4. Strongest Score-Assertion Disagreements section shows the top 5 as an inline table with score, assertion, researcher name, article title, and PubMed link
  5. "View all disagreements" link navigates to the Results page filtered to disagreement cases; page uses `"use client"` on all Recharts files and loads correctly in production build without SSR hydration errors
**Plans**: TBD
**UI hint**: yes

</details>

### v2.0 Pipeline Parity & Performance (In Progress)

**Milestone Goal:** Make ReCiter Desktop's retrieval and scoring pipeline match ReCiter's exact behavior, suitable for validating accuracy claims in the paper.

- [ ] **Phase 4: Schema Foundation + Parallel Processing** - Add pipeline_run table, nullable run_id columns, and fix asyncio completion ordering
- [ ] **Phase 5: Retrieval Strategy Parity** - Implement affiliation search, compound name detection, retrieve_known mode, update mode fix, and name quoting hardening
- [ ] **Phase 6: Historical Pipeline Runs** - Wire run_id through pipeline, expose run list API, add run selector on Results and Stats pages
- [ ] **Phase 7: Results Refinement** - Add search/filter bar, per-researcher export, and source labeling to Results page
- [ ] **Phase 8: Stats Scoping + UI Polish** - Scope stats to run_id, add SSE reconnect, institution name display, last run type badge, and dashboard metrics

### v2.1 Retrieve & Score — UX, Bugs & Robustness (Planned)

**Milestone Goal:** Fix critical bugs on the pipeline page, polish visual consistency, and add reliability improvements.

- [ ] **Phase 9: Parallel Write Race Condition Fix** - Eliminate SQLAlchemy autoflush race condition errors in concurrent pipeline workers
- [ ] **Phase 10: Pipeline Page Polish + Number Formatting** - Correct pipeline page copy, fix ETA countdown, animation direction, font/alignment, and status logic; apply comma formatting app-wide
- [ ] **Phase 11: SSE Reconnection + Cancel** - Add reliable pipeline state restoration on navigation return and a graceful cancel button for active runs

## Phase Details

### Phase 4: Schema Foundation + Parallel Processing
**Goal**: The database schema has a `pipeline_run` table and nullable `run_id` FKs on score and retrieval tables, and the pipeline UI shows researchers completing in true arrival order
**Depends on**: Phase 3
**Requirements**: PARA-01, PARA-02, HIST-01, HIST-02
**Success Criteria** (what must be TRUE):
  1. A `pipeline_run` table exists in the database with columns for run_id, mode, status, timestamps, and article/researcher counts; existing installations can upgrade without losing data
  2. `person_article_score` and `retrieval_log` rows carry a nullable `run_id` column; existing scores from before the migration appear as run #1
  3. When four or more researchers are scored in parallel, the pipeline UI shows researchers finishing out of submission order (completion order), not one at a time
  4. With a PubMed API key configured, the pipeline uses 8 parallel workers; without one, it uses 3 workers
**Plans:** 2 plans

Plans:
- [x] 04-01-PLAN.md — Alembic setup + PipelineRun model + run_id columns + migrations
- [ ] 04-02-PLAN.md — Pipeline as_completed refactor + adaptive workers + frontend update

### Phase 5: Retrieval Strategy Parity
**Goal**: PubMed retrieval behavior matches Java ReCiter for affiliation filtering, compound/special names, known-PMID workflows, update mode date tracking, and non-ASCII name handling
**Depends on**: Phase 4
**Requirements**: RETR-01, RETR-02, RETR-03, RETR-04, RETR-05, RETR-06
**Success Criteria** (what must be TRUE):
  1. A researcher with a common name whose lenient result count exceeds 2000 automatically receives an affiliation-filtered PubMed search using institution keywords from config; the Pipeline page shows which strategy was used
  2. A researcher with a hyphenated or multi-word last name (e.g., "Garcia Lopez") is detected before retrieval and run in strict-only mode, avoiding noisy lenient results
  3. Researchers uploaded via PMID import have their full PubMed XML fetched before scoring, so their scored article list reflects the actual publications rather than zero results
  4. Running the pipeline twice on the same researcher in `update` mode retrieves only articles published after the first run's retrieval date; the second run does not duplicate articles already in the database
  5. An `update` mode end-to-end integration test passes with a known researcher on a second run without returning zero articles or crashing
  6. Researcher names containing apostrophes (O'Brien), Unicode diacritics (Lopez), or brackets produce valid PubMed queries that return results
**Plans**: TBD

### Phase 6: Historical Pipeline Runs
**Goal**: Every pipeline execution creates a persistent run record, and users can scope Results and Stats to a specific historical run via a dropdown selector
**Depends on**: Phase 4
**Requirements**: HIST-03, HIST-04
**Success Criteria** (what must be TRUE):
  1. `GET /api/pipeline/runs` returns a list of all past runs with run_id, mode, status, start time, and article/researcher counts
  2. The Results page has a run selector dropdown that scopes the researcher listing and article scores to the selected run; switching runs updates the displayed data without a full page reload
  3. The Stats page has a run selector dropdown that recomputes all statistics (ROC, calibration, PR, score distribution, disagreements) scoped to the selected run
**Plans**: TBD
**UI hint**: yes

### Phase 7: Results Refinement
**Goal**: Users can search and filter the Results listing, download a single researcher's results as a CSV, and see whether each article came from a candidate search or a known PMID upload
**Depends on**: Phase 6
**Requirements**: RSLT-01, RSLT-02, RSLT-03
**Success Criteria** (what must be TRUE):
  1. The Results page search bar filters the researcher listing by name in real time; a score range filter narrows results to only researchers with articles scoring in the selected range — both filters operate server-side without keystroke lag at 2000+ articles
  2. Each researcher row on the Results listing has an export button that downloads a CSV containing only that researcher's scored articles
  3. The article detail view for each researcher shows a "Candidate Search" or "Known Upload" label per article indicating how it entered the system
**Plans**: TBD
**UI hint**: yes

### Phase 8: Stats Scoping + UI Polish
**Goal**: Statistics are scoped to specific pipeline runs, the pipeline recovers gracefully from page reloads, and the app surface reflects real institution identity and run context throughout
**Depends on**: Phase 6
**Requirements**: UIPOL-01, UIPOL-02, UIPOL-03, UIPOL-04
**Success Criteria** (what must be TRUE):
  1. The Setup page stores and displays the institution's original name as entered (e.g., "Weill Cornell Medicine"), not a reconstructed keyword string; the sidebar header shows this name
  2. The Pipeline page completed-researchers table shows the run type (full, update, retrieve_known) used for each researcher in the most recent run
  3. Reloading the browser during an active pipeline run reconnects the SSE stream with exponential backoff (up to 3 retries); in-progress researcher rows restore their prior state rather than resetting to blank
  4. The Dashboard shows total researchers, total scored articles, date of last pipeline run, and overall AUC (when assertions exist)
**Plans**: TBD
**UI hint**: yes

### Phase 9: Parallel Write Race Condition Fix
**Goal**: Concurrent pipeline workers write scores to the database without triggering SQLAlchemy autoflush errors or MariaDB stale-record failures
**Depends on**: Phase 8
**Requirements**: DB-01
**Success Criteria** (what must be TRUE):
  1. Running the pipeline with 8 parallel workers against a researcher set large enough to produce concurrent writes completes without any SQLAlchemy autoflush errors or MariaDB error 1020 in the backend logs
  2. All scored articles are present in `person_article_score` after a parallel run — no records silently dropped due to session conflicts
  3. The fix does not regress single-worker pipeline runs or change any observable scoring output
**Plans:** 2 plans

Plans:
- [x] 09-01-PLAN.md — Wave 0: Test infrastructure (pytest.ini, pytest-asyncio, RED-state upsert test stubs)
- [x] 09-02-PLAN.md — Wave 1: Replace SELECT+INSERT loops with INSERT ... ON DUPLICATE KEY UPDATE

### Phase 10: Pipeline Page Polish + Number Formatting
**Goal**: The pipeline page presents accurate copy, correct visual behavior, and consistent number formatting throughout the application
**Depends on**: Phase 9
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, FMT-01
**Success Criteria** (what must be TRUE):
  1. The pipeline page heading reads "Retrieve & Score" and the subtitle accurately describes the operation; the previous incorrect copy is no longer visible anywhere on the page
  2. The ETA display counts down as researchers complete — each completion updates the estimate based on actual throughput; the timer does not count up or freeze
  3. The progress bar animation moves in the correct direction (left to right); no visual regression on already-correct rows
  4. Status text in pipeline rows ("Retrieving from PubMed", "Scoring") uses the same font size as column headers and aligns with them; no misaligned or oversized status labels remain
  5. "Taking longer than usual" appears only in the row of a researcher whose elapsed time exceeds the expected duration — not statically pre-populated in every last-column cell at pipeline start
  6. All numeric values at or above 1,000 display with comma separators throughout the application (pipeline page article counts, results page counts, stats page counts, dashboard metrics)
**Plans:** 2 plans

Plans:
- [ ] 10-01-PLAN.md — Heading/subtitle copy, ETA inter-completion delta, animation direction, progress number formatting
- [ ] 10-02-PLAN.md — Status font size fix, articleCount formatting, visual verification checkpoint

### Phase 11: SSE Reconnection + Cancel
**Goal**: Users can navigate away from and return to an active pipeline run without losing progress, and can cancel a run in flight
**Depends on**: Phase 10
**Requirements**: PIPE-06, PIPE-07
**Success Criteria** (what must be TRUE):
  1. Navigating away from the pipeline page during an active run and returning reconnects to the SSE stream; all researcher rows that completed while the user was away render with their completed state, and in-progress rows resume their animated state
  2. The pipeline page shows a Cancel button while a run is active; clicking it stops all in-progress workers gracefully (no orphaned processes) and marks the run as cancelled in the database
  3. After a cancellation, the pipeline page shows the partial results for researchers that did complete before cancellation, and the Cancel button disappears
  4. SSE reconnection survives at least one browser tab hide/show cycle (e.g., switching to another tab and returning) without requiring a full page reload
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Backend Stats Endpoint | v1.1 | 3/3 | Complete | 2026-04-04 |
| 2. Workflow Wiring and Navigation | v1.1 | 2/2 | Complete | 2026-04-05 |
| 3. Stats Page Frontend | v1.1 | TBD | Complete | 2026-04-05 |
| 4. Schema Foundation + Parallel Processing | v2.0 | 0/2 | Planning | - |
| 5. Retrieval Strategy Parity | v2.0 | 0/TBD | Not started | - |
| 6. Historical Pipeline Runs | v2.0 | 0/TBD | Not started | - |
| 7. Results Refinement | v2.0 | 0/TBD | Not started | - |
| 8. Stats Scoping + UI Polish | v2.0 | 0/TBD | Not started | - |
| 9. Parallel Write Race Condition Fix | v2.1 | 2/2 | Complete | 2026-04-06 |
| 10. Pipeline Page Polish + Number Formatting | v2.1 | 0/2 | Planning | - |
| 11. SSE Reconnection + Cancel | v2.1 | 0/TBD | Not started | - |
