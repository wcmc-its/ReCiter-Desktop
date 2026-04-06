# Requirements: ReCiter Desktop

**Defined:** 2026-04-05
**Core Value:** An institution can go from researcher list to scored publications in minutes, using the same production-validated models as Weill Cornell Medicine.

## v2.0 Requirements

Requirements for Pipeline Parity & Performance milestone. Each maps to roadmap phases.

### Retrieval Parity

- [ ] **RETR-01**: Pipeline uses affiliation-filtered PubMed search (institution keywords from config) when lenient result count exceeds threshold
- [ ] **RETR-02**: Pipeline detects compound/derived names (hyphenated, multi-word, middle-as-first) and sets strict-only search mode before retrieval
- [ ] **RETR-03**: `retrieve_known` mode fetches full PubMed XML for uploaded PMIDs before scoring
- [ ] **RETR-04**: `update` mode uses correct mindate from last retrieval (ON UPDATE CURRENT_TIMESTAMP removed; score_only does not touch retrieval_log)
- [ ] **RETR-05**: `update` mode passes end-to-end integration test with known researcher on second run
- [ ] **RETR-06**: Name quoting handles non-ASCII characters and apostrophes without producing zero-result queries

### Parallel Processing

- [ ] **PARA-01**: Pipeline yields SSE events in completion order via asyncio.as_completed (not submission order)
- [ ] **PARA-02**: MAX_WORKERS is 8 when PubMed API key is configured, 3 without

### Historical Runs

- [ ] **HIST-01**: `pipeline_run` table records run metadata (run_id, mode, status, timestamps, counts)
- [ ] **HIST-02**: `person_article_score` and `retrieval_log` have nullable `run_id` FK; existing scores migrate as run #1
- [ ] **HIST-03**: `GET /api/pipeline/runs` endpoint lists historical runs
- [ ] **HIST-04**: Run selector dropdown on Results and Stats pages scopes data to a specific run

### Results Refinement

- [ ] **RSLT-01**: Results listing supports text search (researcher name) and score range filter
- [ ] **RSLT-02**: Per-researcher export button downloads CSV for a single researcher
- [ ] **RSLT-03**: Results detail shows source label (candidate search vs known/uploaded) per article

### UI Polish

- [ ] **UIPOL-01**: Setup page stores and displays original institution name (not keyword reconstruction)
- [ ] **UIPOL-02**: Pipeline page shows last run type per researcher in completed table
- [ ] **UIPOL-03**: SSE reconnection with exponential backoff recovers pipeline progress on page reload
- [ ] **UIPOL-04**: Dashboard shows key metrics (total researchers, articles, last run date, overall AUC)

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Extended Retrieval Strategies

- **RETR-F01**: Full 8-strategy retrieval cascade (grants, departments, known relationships, second initial)
- **RETR-F02**: DepartmentRetrievalStrategy using organizational_units field
- **RETR-F03**: OrcidRetrievalStrategy for researchers with ORCID identifiers

### Run Comparison

- **HIST-F01**: Run comparison view — side-by-side score deltas, overlaid ROC curves
- **HIST-F02**: Pre-computed per-run stats (AUC-ROC, AUC-PR) at completion time

### Stats Enhancements

- **STATS-F01**: WCM/Fred Hutch benchmark reference lines overlaid on ROC and PR charts
- **STATS-F02**: "View all disagreements" link navigates to filtered Results page

## Out of Scope

| Feature | Reason |
|---------|--------|
| Per-researcher stats drill-down | Individual researchers have too few curations for stable AUC; aggregate is sufficient |
| Real-time calibration updates during pipeline | Stats are post-hoc; partial results produce unstable estimates |
| Custom benchmark upload | WCM/Fred Hutch are the reference institutions |
| Automatic re-score after curation import | Couples two distinct operations; keep import and pipeline as separate explicit user actions |
| Unlimited retmax (no threshold cap) | Strict fallback is the correct mechanism for high-volume names; thresholds match Java's behavior |
| Grant matching / co-authorship network / Scopus enrichment | Features set to 0.0 with minimal accuracy impact; would require external data sources not available in Desktop |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| RETR-01 | Phase 5 | Pending |
| RETR-02 | Phase 5 | Pending |
| RETR-03 | Phase 5 | Pending |
| RETR-04 | Phase 5 | Pending |
| RETR-05 | Phase 5 | Pending |
| RETR-06 | Phase 5 | Pending |
| PARA-01 | Phase 4 | Pending |
| PARA-02 | Phase 4 | Pending |
| HIST-01 | Phase 4 | Pending |
| HIST-02 | Phase 4 | Pending |
| HIST-03 | Phase 6 | Pending |
| HIST-04 | Phase 6 | Pending |
| RSLT-01 | Phase 7 | Pending |
| RSLT-02 | Phase 7 | Pending |
| RSLT-03 | Phase 7 | Pending |
| UIPOL-01 | Phase 8 | Pending |
| UIPOL-02 | Phase 8 | Pending |
| UIPOL-03 | Phase 8 | Pending |
| UIPOL-04 | Phase 8 | Pending |

**Coverage:**
- v2.0 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0

---
*Requirements defined: 2026-04-05*
*Last updated: 2026-04-05 — all 19 requirements mapped to Phases 4-8*
