# ReCiter Desktop

## What This Is

Standalone web application for author name disambiguation. Librarians and research administrators upload a researcher roster, retrieve candidate articles from PubMed, and score each article using pre-trained XGBoost models — without needing the full ReCiter Java stack. Runs locally via Docker Compose (Next.js + FastAPI + MariaDB).

## Core Value

An institution can go from researcher list to scored publications in minutes, using the same production-validated models as Weill Cornell Medicine.

## Current Milestone: v2.0 Pipeline Parity & Performance

**Goal:** Make ReCiter Desktop's retrieval and scoring pipeline match ReCiter's exact behavior, suitable for validating accuracy claims in the paper.

**Target features:**
- Retrieval Strategy Parity: strict/relaxed PubMed search, esearch count check, affiliation filtering, compound name handling
- Parallel Researcher Processing: dynamic MAX_WORKERS, asyncio.as_completed, concurrent pipeline UI
- Historical Pipeline Runs: run table with run_id, run selector on Results/Stats, comparison view
- Results Page Refinement: search/filter, per-researcher export, source labeling
- UI Polish: institution name display, last run type, reconnection, dashboard metrics

## Requirements

### Validated

- ✓ Institution setup with PubMed domain discovery — v1.0
- ✓ Researcher upload with flexible column mapping (30+ variations) — v1.0
- ✓ PMID upload with assertion import (ACCEPTED/REJECTED → curations) — v1.0
- ✓ Scoring pipeline: identity-only (42 features) and feedback (72 features) models — v1.0
- ✓ Per-researcher results: score histogram, adjustable threshold slider, article list — v1.0
- ✓ CSV export of all scored results — v1.0
- ✓ Sidebar navigation with prerequisite gates and status indicators — v1.0
- ✓ Incremental pipeline (only re-scores new articles on subsequent runs) — v1.0
- ✓ Backend stats endpoint: ROC/AUC with bootstrap CI, calibration, PR curve, score distribution, disagreements — v1.1
- ✓ Stats page frontend: 4 charts (ROC, calibration, score distribution, precision-recall), metric cards, disagreements table — v1.1
- ✓ Stats workflow wiring: sidebar entry with prerequisite gate, pipeline completion CTA — v1.1

### Active

- [ ] Retrieval strategy parity with ReCiter: strict/relaxed search, esearch count, affiliation filtering, compound names
- [ ] Parallel researcher processing: dynamic workers, asyncio.as_completed, concurrent pipeline UI
- [ ] Historical pipeline runs: run table, run selector, comparison view
- [ ] Results page refinement: search/filter, per-researcher export, source labeling
- [ ] UI polish: institution name display, last run type, reconnection, dashboard metrics

### Out of Scope

- Per-researcher stats drill-down — aggregate across run is sufficient
- Real-time calibration updates during pipeline run — stats are post-hoc
- Custom benchmark upload — WCM/Fred Hutch are the reference institutions

## Context

- Stack: Next.js 14 (App Router) + FastAPI + MariaDB, Docker Compose
- ML: XGBoost 3.2.0 with isotonic calibration; models in `models/wcm/`
- Scoring data: `person_article_score` table stores pmid, person_id, score (0–100)
- Curation data: `curations` table stores person_id, pmid, assertion (ACCEPTED/REJECTED)
- WCM benchmarks: feedback model AUC 0.9993; identity-only AUC 0.9776
- Fred Hutch external validation: feedback AUC 0.9993, confirmed cross-site generalization
- Charts: no charting library currently installed; will need to add one (Recharts likely)
- Stats require joining `person_article_score` + `curations` on (person_id, pmid)

## Constraints

- **Tech stack**: Python 3.12 (Docker), Node 20, XGBoost 3.2.0 pinned — no version changes
- **Scope**: Stats are aggregate across a pipeline run, not per-researcher
- **Gate**: Stats page only shown when at least one curation/assertion exists in DB

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MariaDB over SQLite | Future compatibility with ReCiter Publication Manager | ✓ Good |
| Docker Compose (3 containers) | Isolation, consistent environment, easy install | ✓ Good |
| SSE for long-running operations | Real-time progress without polling complexity | ✓ Good |
| FastAPI wrapping Python scoring engine | Reuse production code without rewrite | ✓ Good |
| Assertions imported as curations | Activates feedback model, enables stats | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-05 after milestone v2.0 started*
