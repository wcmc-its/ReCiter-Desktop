# ReCiter Desktop

## What This Is

Standalone web application for author name disambiguation. Librarians and research administrators upload a researcher roster, retrieve candidate articles from PubMed, and score each article using pre-trained XGBoost models — without needing the full ReCiter Java stack. Runs locally via Docker Compose (Next.js + FastAPI + MariaDB).

## Core Value

An institution can go from researcher list to scored publications in minutes, using the same production-validated models as Weill Cornell Medicine.

## Current Milestone: v1.1 Statistics & Validation View

**Goal:** Show pipeline scoring quality after a run using gold standard assertions, benchmarked against WCM and Fred Hutch.

**Target features:**
- Post-pipeline stats page (gated: only shown when assertions were imported)
- ROC curve with AUC + WCM/Fred Hutch reference lines
- Calibration plot (reliability diagram) + reference lines
- Score distribution histogram colored by assertion outcome
- Precision-recall curve + reference lines
- Strongest Disagreements: top 5 inline table + "View all" link to filtered Results

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

### Active

- [ ] Post-pipeline statistics page with AUC, calibration, score distribution, precision-recall
- [ ] Benchmark reference lines from WCM and Fred Hutch overlaid on charts
- [ ] Strongest Disagreements section: top 5 inline + link to filtered Results page

### Validated in Phase 1: Backend Stats Endpoint

- ✓ `GET /api/stats` endpoint computes ROC/AUC + 95% bootstrap CI (1000 resamples) — STATS-01
- ✓ Calibration: exactly 10 fixed bins via `np.digitize`, n-per-bin counts — STATS-02
- ✓ PR curve: baseline = actual positive rate (not 0.5) — STATS-03
- ✓ Score distribution: 10-bucket histogram split by ACCEPTED/REJECTED — STATS-04
- ✓ Strongest disagreements: ranked by |score − assertion_value| — STATS-05
- ✓ Viability flags: gate output when n=0, single-class, or n<50 — STATS-06

### Out of Scope

- Per-researcher stats drill-down — aggregate across run is sufficient for v1.1
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
*Last updated: 2026-04-04 — Phase 1 complete: `/api/stats` endpoint live*
