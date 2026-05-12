# Feature: Load Sample Data

## Goal

Let a new user evaluate ReCiter Desktop end-to-end without sourcing their own CSVs. After completing institutional-profile setup, the user clicks **Load sample data** and gets five real WCM researchers plus their ACCEPTED/REJECTED PMID assertions loaded into the local DB. Retrieve & Score then runs against real data with a real feedback signal.

## Cohort

Pulled from production `reciterdb.identity` and `reciterdb.person_article` (RDS, `~/.my.cnf`):

| person_id | Name | Department | Title |
|---|---|---|---|
| ccole | Curtis Cole | Medicine | Professor of Clinical Medicine |
| dcl2001 | David Lyden | Pediatrics | Professor of Pediatrics |
| paa2013 | Paul Albert | Library | (title from identity) |
| tew2004 | Terrie Wheeler | Library | Librarian |
| xim2002 | Xiaojing Ma | Microbiology and Immunology | Professor of Microbiology and Immunology |

`primary_institution` = "Weill Cornell Medicine" for all five.
`primary_email`, `orcid`, `bachelor_year`, `doctoral_year`, `middle_name` left blank — institutional profile lookup fills the rest at run time, matching the normal user flow.

## Assertions

Pulled from `person_article` where `userAssertion IN ('ACCEPTED','REJECTED')`.

- **REJECTED:** keep all rows. Rejects are high-signal for the feedback model and we don't want to distort the negative-class distribution.
- **ACCEPTED:** drop the 2 oldest and 2 newest per researcher (ordered by `publicationDateStandardized`, ties broken by `pmid`). Trims bleeding-edge curations (still mutable upstream) and earliest career-edge papers.

Expected row counts:

| CWID | ACCEPTED kept | REJECTED kept | Total |
|---|---|---|---|
| ccole | 27 | 15 | 42 |
| dcl2001 | 156 | 0 | 156 |
| paa2013 | 9 | 46 | 55 |
| tew2004 | 6 | 24 | 30 |
| xim2002 | 124 | 614 | 738 |
| **Total** | **322** | **699** | **1,021** |

## Scope

### In scope

1. **Build script** `scripts/build_sample_data.py`
   - Reads from reciterdb via `~/.my.cnf` (no creds in code).
   - Writes two files to `frontend/public/sample/`:
     - `sample-researchers.csv` — schema matches `frontend/public/researcher-template.csv`.
     - `sample-articles.csv` — schema matches `frontend/public/articles-template.csv`.
   - One-shot. Re-run regenerates files. Not invoked at runtime.

2. **Backend endpoint** `POST /api/researchers/load-sample`
   - Reads the two CSVs from `frontend/public/sample/` server-side (path resolved relative to repo root or container mount).
   - Reuses the existing parse+import pipeline (`column_mapper` → `/researchers/import` logic) — no new write paths.
   - Loads researchers into `identity`, assertions into `curations` (source=`"import"`).
   - Returns `{identity_count, curation_count}` matching the upload-flow response shape.
   - Returns 409 if researchers already exist, unless `?replace=true` is passed; replace path mirrors the existing replace flow on `/researchers/import`.
   - Behind the same auth shared-secret as other `/api/*` routes.

3. **Frontend** — `frontend/app/researchers/page.tsx`
   - New secondary button **Load sample data** next to the existing upload card. Tooltip explains what loads.
   - Gated by `PrerequisiteGate` on `institution` (same gate as upload) — institutional-profile setup must complete first.
   - Confirm dialog if researchers already exist ("Replace current researchers?"), then POST `?replace=true`.
   - On success: refresh workflow state, route to `/articles` so the user sees the assertion counts.

### Out of scope

- No auto-seed at boot. User runs institutional-profile setup first.
- No new CSV ingest path. Sample data flows through the existing column-mapping importer.
- No fixture for PubMed retrieval results — Retrieve & Score still hits PubMed at run time, as designed.
- No fixture for scores — running the pipeline computes them.

## File layout

```
frontend/public/sample/
  sample-researchers.csv     # 5 rows + header
  sample-articles.csv        # ~961 rows + header
scripts/
  build_sample_data.py       # one-shot generator
api/routers/researchers.py   # +load-sample endpoint
frontend/app/researchers/page.tsx  # +button + handler
```

## Open questions answered

- **CWID for Paul Albert:** `paa2013` (confirmed; `paa2023` was a typo).
- **Volume:** ship all real assertions in the 2000–2024 window (~961 rows, <100 KB).
- **No institutional profile pre-load:** user still goes through profile setup.

## Risks

- `frontend/public/sample/` is bundled with the frontend image and ships publicly. The 5 CWIDs + PMID assertions are already public (cwids are on WCM directory pages; PMIDs are public). No PII concern. Confirm acceptable before merge.
- xim2002 has 104 ACCEPTED / 604 REJECTED — class-imbalanced for the feedback model. Real data; reflects the actual production distribution.
- Re-running `build_sample_data.py` against a future reciterdb snapshot may produce drift if curations change. Plan: regenerate the files only when intentionally refreshing the sample.

## Test plan

- `scripts/build_sample_data.py` produces both CSVs; row counts match the table above ±5%.
- `POST /api/researchers/load-sample` on an empty DB: returns 200, identity_count=5, curation_count≈961.
- Second call: returns 409.
- Second call with `?replace=true`: returns 200, replaces.
- UI: button is disabled when institution profile incomplete; enabled after; click loads, navigates to /articles.
- E2E sanity: after load, Retrieve & Score runs on the 5 researchers and produces non-empty results.

## Branch & PR

- Branch off `main`: `feat/sample-data-loader`.
- Single PR. Existing `fix/article-import-run-state` left untouched.
