# Milestones

## v1.0 — Core Pipeline (Shipped)

**Shipped:** 2026-04-04
**Branch:** feature/desktop-v1

What shipped:
- Docker Compose application (Next.js + FastAPI + MariaDB)
- Institution setup with PubMed domain discovery
- Researcher upload with flexible column mapping
- PMID upload with assertion import
- Full scoring pipeline: identity-only (42 features) and feedback (72 features) XGBoost models
- Per-researcher results with score histogram, threshold slider, article list, CSV export
- Sidebar navigation with prerequisite gates and status indicators
- Incremental pipeline runs (only re-scores new articles)
- Validated E2E with Fred Hutch data: 20 researchers, 433 articles scored in 2 seconds

## v1.1 — Statistics & Validation View (Shipped)

**Started:** 2026-04-04
**Shipped:** 2026-04-05
**Branch:** feature/desktop-v1

What shipped:
- Backend stats endpoint: ROC/AUC with 95% bootstrap CI, calibration (10 fixed bins), PR curve with prevalence baseline, score distribution, top disagreements
- Stats page frontend: 4 interactive Recharts charts (ROC, calibration, score distribution, precision-recall), metric summary cards, disagreements table
- Workflow wiring: sidebar "Statistics" entry with prerequisite gate, pipeline completion CTA
- Viability flags: gates output when n=0, single-class, or n<50

## v2.0 — Pipeline Parity & Performance (In Progress)

**Started:** 2026-04-05

Goal: Make retrieval and scoring pipeline match ReCiter's exact behavior for paper validation.
