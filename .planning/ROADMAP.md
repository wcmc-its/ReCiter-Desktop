# Roadmap: ReCiter Desktop

## Milestones

- ✅ **v1.0 Core Pipeline** - Phases 1-N (shipped 2026-04-04)
- 🚧 **v1.1 Statistics & Validation View** - Phases 1-3 (in progress)

## Phases

<details>
<summary>✅ v1.0 Core Pipeline — SHIPPED 2026-04-04</summary>

What shipped: Docker Compose app (Next.js + FastAPI + MariaDB), institution setup, researcher upload, PMID/assertion import, XGBoost scoring pipeline, per-researcher results, CSV export, sidebar navigation with prerequisite gates, incremental pipeline runs.

</details>

### 🚧 v1.1 Statistics & Validation View (In Progress)

**Milestone Goal:** Show pipeline scoring quality after a run using gold-standard assertions, benchmarked against WCM and Fred Hutch.

- [ ] **Phase 1: Backend Stats Endpoint** - Compute ROC, calibration, PR, score distribution, and disagreements server-side
- [ ] **Phase 2: Workflow Wiring and Navigation** - Gate stats page, add sidebar entry, add pipeline completion CTA
- [ ] **Phase 3: Stats Page Frontend** - Charts, benchmark overlays, disagreements table

## Phase Details

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
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Wave 0: Test suite scaffolding (15 unit tests for STATS-01 through STATS-06)
- [ ] 01-02-PLAN.md — Stats service implementation (all computation functions + data prep)
- [ ] 01-03-PLAN.md — Router + wiring (HTTP layer + main.py registration)

### Phase 2: Workflow Wiring and Navigation
**Goal**: The stats page is reachable from the sidebar and from pipeline completion, and is locked behind the correct gate condition
**Depends on**: Phase 1
**Requirements**: NAV-01, NAV-02, NAV-03
**Success Criteria** (what must be TRUE):
  1. Sidebar shows a "Statistics" item that is locked with a prerequisite message when no (score, assertion) joined pairs exist in the database, and unlocked otherwise
  2. Pipeline completion page displays a "View Statistics" CTA link when assertions exist; the link is absent when no assertions exist
  3. Navigating to `/stats` when the gate is not met shows the prerequisite gate UI; navigating when it is met renders the stats page
**Plans**: TBD
**UI hint**: yes

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

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Backend Stats Endpoint | v1.1 | 0/3 | Planning complete | - |
| 2. Workflow Wiring and Navigation | v1.1 | 0/TBD | Not started | - |
| 3. Stats Page Frontend | v1.1 | 0/TBD | Not started | - |
