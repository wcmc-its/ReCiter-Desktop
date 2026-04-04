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

## v1.1 — Statistics & Validation View (In Progress)

**Started:** 2026-04-04

Goal: Post-pipeline statistics page showing scoring quality benchmarked against WCM and Fred Hutch.
