---
phase: 09-parallel-write-race-condition-fix
plan: "02"
subsystem: pipeline-runner
tags: [race-condition, upsert, mysql, sqlalchemy, db-01]
dependency_graph:
  requires: [09-01]
  provides: [race-condition-free _process_one_researcher with upsert pattern]
  affects: [api/services/pipeline_runner.py]
tech_stack:
  added: []
  patterns: [INSERT ... ON DUPLICATE KEY UPDATE, bulk upsert, mysql_insert, text('NOW()')]
key_files:
  created: []
  modified:
    - api/services/pipeline_runner.py
decisions:
  - "No-op upsert for article and person_article tables (on_duplicate_key_update preserves existing data)"
  - "Full-update upsert for person_article_score (overwrites score fields + refreshes scored_at on re-run)"
  - "created_at excluded from all on_duplicate_key_update clauses to preserve server-set INSERT timestamps"
  - "Phase 2 target_author_index ORM loop left as-is — safe because each worker processes a unique person_id"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-06"
  tasks_completed: 2
  files_changed: 1
---

# Phase 09 Plan 02: Upsert Implementation (Wave 1) Summary

**One-liner:** Replaced three SELECT+INSERT/UPDATE loops in `_process_one_researcher` with atomic `INSERT ... ON DUPLICATE KEY UPDATE` statements, eliminating the SQLAlchemy autoflush race condition (DB-01) for concurrent ThreadPoolExecutor workers.

## What Was Built

### Task 1: Upsert implementation in `_process_one_researcher`

Made three surgical replacements in `api/services/pipeline_runner.py`:

**1. New imports (2 lines added)**
```python
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy import text
```

**2. Article + PersonArticle loop replaced (Phase 1: Retrieve)**

Before: `for art in articles:` iterating with `db.query(Article).filter_by(pmid=...).first()` + conditional `db.add(Article(...))` + `db.query(PersonArticle).filter_by(...).first()` + conditional `db.add(PersonArticle(...))`

After: Build `article_rows` and `pa_rows` lists in one pass, then two bulk upserts:
- `mysql_insert(Article.__table__).values(article_rows).on_duplicate_key_update(pmid=stmt.inserted.pmid)` — no-op on duplicate
- `mysql_insert(PersonArticle.__table__).values(pa_rows).on_duplicate_key_update(source=stmt.inserted.source)` — no-op on duplicate

**3. PersonArticleScore loop replaced (Phase 4: Save scores)**

Before: `for _, row in scored_df.iterrows():` with `db.query(PersonArticleScore).filter_by(...).first()` + conditional update-in-place or `db.add(PersonArticleScore(...))`

After: Build `score_rows` list in one pass, then one bulk upsert:
- `mysql_insert(PersonArticleScore.__table__).values(score_rows).on_duplicate_key_update(calibrated_score, raw_score, features, run_id, scored_at=text('NOW()'))` — full update on duplicate

### Task 2: Full test suite regression verification

- `api/tests/test_upsert_writes.py` — 5/5 PASS (all GREEN including previously-RED `test_no_article_select_in_process`)
- `api/tests/test_pipeline_runner.py` — 5/5 PASS (async worker tests, no regression)
- `api/tests/test_models.py` — PASS
- `api/tests/test_column_mapper.py` — PASS
- `api/tests/test_institution_discovery.py` — PASS
- **Full suite: 31 passed, 0 failed**

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

```
db.query(Article).filter_by occurrences in _process_one_researcher:     0
db.query(PersonArticleScore).filter_by occurrences:                      0
mysql_insert call sites (upserts):                                       3
mysql_insert import lines:                                               1
Only api/services/pipeline_runner.py changed:                            YES
Full test suite: 31 passed, 0 failed
```

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 51a57af | feat | replace SELECT+INSERT loops with mysql upsert in _process_one_researcher |

## Known Stubs

None.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| api/services/pipeline_runner.py modified | FOUND |
| `from sqlalchemy.dialects.mysql import insert as mysql_insert` present | FOUND |
| `from sqlalchemy import text` present | FOUND |
| 0 occurrences of db.query(Article).filter_by in _process_one_researcher | CONFIRMED |
| 0 occurrences of db.query(PersonArticleScore).filter_by | CONFIRMED |
| 3 mysql_insert upsert call sites | CONFIRMED |
| All 5 upsert tests GREEN | CONFIRMED |
| Full suite 31 passed, 0 failed | CONFIRMED |
| Commit 51a57af exists | CONFIRMED |
| 09-02-SUMMARY.md exists | FOUND |
