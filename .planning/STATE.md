# State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-04)

**Core value:** An institution can go from researcher list to scored publications in minutes, using the same production-validated models as Weill Cornell Medicine.
**Current focus:** Milestone v1.1 — Statistics & Validation View

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-04-04 — Milestone v1.1 started

## Accumulated Context

- Branch: `feature/desktop-v1` (29 commits ahead of main, not yet pushed to GitHub)
- DB schema: `retrieval_log` table added to ORM but NOT in `schema.sql` — needs fixing
- Score thresholds: ≥95 = accepted (green), 30–94 = review (yellow), <30 = unlikely (red)
- `curations` table: person_id + pmid + assertion (ACCEPTED/REJECTED) + source
- `person_article_score` table: person_id + pmid + score (0–100)
- Stats join: `SELECT pas.score, c.assertion FROM person_article_score pas JOIN curations c ON pas.person_id = c.person_id AND pas.pmid = c.pmid`
- WCM benchmarks: feedback AUC 0.9993, identity-only AUC 0.9776
- Fred Hutch: 868 researchers, feedback AUC 0.9993 (cross-site confirmed without retraining)
- No charting library installed yet — Recharts likely candidate
