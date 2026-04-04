# Phase 1: Backend Stats Endpoint - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the `GET /api/stats` FastAPI endpoint that joins `person_article_score` + `curation` tables and computes ROC curve, calibration plot, PR curve, score distribution, and top-10 disagreements. Returns viability flags when data is insufficient. No frontend work in this phase.

</domain>

<decisions>
## Implementation Decisions

### Model Type Priority
- **D-01:** Per-researcher: use `feedbackIdentity` scores if they exist for that researcher, else fall back to `identityOnly`. Mixed model types across researchers in the same aggregate stat set is acceptable.
- **D-02:** No run-level consistency enforcement — best available model per researcher.

### Response Score Scale
- **D-03:** Use **0–100 everywhere** in the API response. Multiply `calibrated_score × 100` at data load time before all stat computations. Consistent with the rest of the app (scores.py already does this). Calibration bins become `[0, 10, 20, ..., 100]`.

### Bootstrap Performance
- **D-04:** Always run **1000 resamples** as specified in STATS-01.
- **D-05:** If bootstrap runtime exceeds ~2 seconds, include `"ci_degraded": true` in the response (alongside the CI result — don't skip the CI). This surfaces real-world performance data without deviating from spec.
- **D-06:** No caching — always compute fresh from current DB state on every request.

### Endpoint Architecture
- **D-07:** New `api/routers/stats.py` (HTTP layer) + `api/services/stats_service.py` (all computation). Follows existing routers/ + services/ pattern.
- **D-08:** One combined `stats_service.py` for all stat computations — the shared DB JOIN and data prep make a single service natural. Split later if it grows unwieldy.
- **D-09:** Register new router in `api/main.py` following the same pattern as the other routers.

### Claude's Discretion
- Exact bootstrap implementation (numpy vs scipy.stats.bootstrap — either is fine)
- How to detect "single-class" error condition (all assertions the same label)
- Internal data structures for passing joined data between functions
- Error response format (consistent with other routers in the project)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — STATS-01 through STATS-06 exact definitions (ROC, calibration, PR, distribution, disagreements, viability flags)

### Database
- `api/schema.sql` — `person_article_score` (calibrated_score FLOAT 0.0–1.0, model_type ENUM) and `curation` (assertion ENUM ACCEPTED/REJECTED) table definitions
- `api/models.py` — SQLAlchemy models: `PersonArticleScore`, `Curation`, `Identity`

### Codebase Patterns
- `api/routers/scores.py` — Router pattern to replicate (APIRouter, Depends(get_db), return dicts)
- `api/main.py` — Where to register the new stats router
- `api/services/pipeline_runner.py` — Service pattern (class or module-level functions, db session usage)

### Roadmap
- `.planning/ROADMAP.md` § Phase 1 — Goal, success criteria, and requirement IDs

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PersonArticleScore` model: has `person_id`, `pmid`, `model_type`, `calibrated_score` (0.0–1.0)
- `Curation` model: has `person_id`, `pmid`, `assertion` (ACCEPTED/REJECTED)
- `Identity` model: has `person_id`, `first_name`, `last_name` (needed for disagreements response)
- `api/database.py`: `get_db` dependency already in place

### Established Patterns
- All routers return plain dicts (not Pydantic models)
- DB sessions injected via `Depends(get_db)`
- SQLAlchemy ORM queries with `.join()` and `.filter()` — no raw SQL
- Score display convention: `round(calibrated_score * 100)` — same multiply-by-100 pattern to use here

### Integration Points
- New router must be imported and registered in `api/main.py` (6 routers already there, add stats as 7th)
- `scikit-learn`, `scipy`, `numpy` already in `api/requirements.txt` — no new dependencies needed

</code_context>

<specifics>
## Specific Ideas

- STATE.md concern: score column might be 0.0–1.0 float (confirmed by scores.py pattern); stats endpoint must multiply by 100 before binning — do NOT assume 0–100 in DB.
- STATE.md concern: bootstrap CI — verify completes under ~2 seconds for n=100–500; `ci_degraded` flag handles the case where it doesn't.
- `retrieval_log` table is in ORM but NOT in `schema.sql` — pre-existing inconsistency, not in scope for this phase.

</specifics>

<deferred>
## Deferred Ideas

- Historical run comparison (stats snapshots per pipeline run) — user explicitly chose "always compute fresh"
- Per-researcher stats drill-down — out of scope per PROJECT.md (aggregate only)
- In-memory cache invalidated on pipeline run — could be added in Phase 2 or 3 if performance is a concern

</deferred>

---

*Phase: 01-backend-stats-endpoint*
*Context gathered: 2026-04-04*
