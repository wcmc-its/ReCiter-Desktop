# Requirements: ReCiter Desktop

**Defined:** 2026-04-04
**Milestone:** v1.1 — Statistics & Validation View
**Core Value:** An institution can go from researcher list to scored publications in minutes, using the same production-validated models as Weill Cornell Medicine.

## v1.1 Requirements

### Stats API

- [x] **STATS-01**: Backend computes ROC curve points, AUC scalar value, and bootstrap 95% CI for AUC
- [x] **STATS-02**: Backend computes calibration bins (10 uniform bins, n-per-bin counts included), gated at n≥50 joined (score, assertion) pairs
- [x] **STATS-03**: Backend computes PR curve points, AUC-PR scalar, and prevalence-anchored no-skill baseline value
- [x] **STATS-04**: Backend returns score distribution binned by assertion (ACCEPTED/REJECTED counts per 10-point bucket, 0–100)
- [x] **STATS-05**: Backend returns top-10 strongest disagreements ranked by |score − assertion_value| (ACCEPTED→100, REJECTED→0)
- [x] **STATS-06**: API returns viability flags (below-n-threshold warning when n<50, single-class-only error when all assertions are the same label)

### Charts

- [ ] **CHART-01**: User sees ROC curve with mandatory y=x diagonal reference line, AUC headline value, and bootstrap 95% CI displayed
- [ ] **CHART-02**: User sees calibration plot (reliability diagram) with n-per-bin overlay; warning banner shown when n<50
- [ ] **CHART-03**: User sees score distribution histogram with ACCEPTED bars in green and REJECTED bars in red, stacked per 10-point bucket
- [ ] **CHART-04**: User sees precision-recall curve with prevalence-anchored no-skill baseline line

### Benchmarks

- [ ] **BENCH-01**: WCM and Fred Hutch AUC reference lines overlaid on ROC curve
- [ ] **BENCH-02**: WCM and Fred Hutch AUC-PR reference lines overlaid on PR curve
- [ ] **BENCH-03**: User sees summary row at top of page: institution AUC | WCM AUC | Fred Hutch AUC

### Disagreements

- [ ] **DISAG-01**: User sees top-5 strongest disagreements as inline table (score, assertion, researcher name, article title, PubMed link)
- [ ] **DISAG-02**: "View all disagreements" link navigates to Results page filtered to disagreement cases (high-score+REJECTED and low-score+ACCEPTED)

### Navigation & Gating

- [ ] **NAV-01**: Stats page is gated: sidebar item locked with prerequisite message when no joined (score, assertion) pairs exist; unlocked otherwise
- [ ] **NAV-02**: Pipeline completion summary shows "View Statistics" CTA link when assertions exist in DB
- [ ] **NAV-03**: Stats page accessible at /stats route with "Statistics" label in sidebar nav

## v2 Requirements

### Enhanced Benchmarks

- **BENCH-04**: Calibration curve overlay from WCM benchmark data (requires WCM calibration curve export — not currently available)
- **BENCH-05**: PR curve benchmark overlay from Fred Hutch validation run

### Per-Researcher Stats

- **RESR-01**: Per-researcher stats drill-down (deferred — aggregate across run is sufficient for v1.1)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time calibration updates during pipeline run | Stats are post-hoc; computing during run adds complexity with no UX benefit |
| Custom benchmark upload | WCM/Fred Hutch are the reference institutions; custom upload is v3+ |
| Per-researcher stats drill-down | Aggregate is sufficient; individual drill-down deferred to v2 |
| Isotonic calibration comparison chart | Requires WCM calibration data export — not available |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| STATS-01 | Phase 1 | Complete |
| STATS-02 | Phase 1 | Complete |
| STATS-03 | Phase 1 | Complete |
| STATS-04 | Phase 1 | Complete |
| STATS-05 | Phase 1 | Complete |
| STATS-06 | Phase 1 | Complete |
| NAV-01 | Phase 2 | Pending |
| NAV-02 | Phase 2 | Pending |
| NAV-03 | Phase 2 | Pending |
| CHART-01 | Phase 3 | Pending |
| CHART-02 | Phase 3 | Pending |
| CHART-03 | Phase 3 | Pending |
| CHART-04 | Phase 3 | Pending |
| BENCH-01 | Phase 3 | Pending |
| BENCH-02 | Phase 3 | Pending |
| BENCH-03 | Phase 3 | Pending |
| DISAG-01 | Phase 3 | Pending |
| DISAG-02 | Phase 3 | Pending |

**Coverage:**
- v1.1 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-04*
*Last updated: 2026-04-04 — initial definition*
