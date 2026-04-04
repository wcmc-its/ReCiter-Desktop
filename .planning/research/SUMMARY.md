# Project Research Summary

**Project:** ReCiter Desktop v1.1 — Statistics & Validation View
**Domain:** ML model validation statistics page — binary classifier, post-pipeline, Next.js 14 + FastAPI
**Researched:** 2026-04-04
**Confidence:** HIGH

## Executive Summary

The v1.1 statistics page adds a post-pipeline validation view for the CARE XGBoost author disambiguation model. This is a well-understood ML dashboard problem: compute ROC, precision-recall, and calibration curves server-side using scikit-learn (already installed), then render them client-side with Recharts inside the existing Next.js + FastAPI stack. The required stack additions are minimal — one npm package (recharts), one shadcn component (`npx shadcn@latest add chart`), and one new FastAPI router. No new infrastructure, no new database tables, no new services.

The recommended approach is strict separation of concerns: all metric computation happens in Python (FastAPI + sklearn), and the browser receives only pre-computed `[{x, y}]` arrays totaling roughly 15KB of JSON. The new `/api/stats` endpoint joins `person_article_score` + `curation`, runs `roc_curve`, `precision_recall_curve`, `calibration_curve`, computes histograms, and ranks disagreements — all in one pass. The frontend renders four chart types and a disagreements table using Recharts' `LineChart`, `BarChart`, and `ScatterChart` primitives plus `ReferenceLine` for WCM/Fred Hutch benchmarks. The existing `PrerequisiteGate` component and `WorkflowContext` wiring patterns handle gating cleanly with minimal modification to existing files.

The dominant risks are statistical, not technical: calibration plots become actively misleading with fewer than 50 curated pairs per bin, AUC point estimates misread as precise when compared to WCM's 0.9993 benchmark, and PR-curve baselines anchored at 0.5 rather than the actual positive rate. These pitfalls must be addressed at the API layer on first build — they cannot be patched cosmetically after the page ships. A secondary risk is Recharts SSR hydration errors in Next.js App Router, which is prevented by ensuring `"use client"` is on every chart file and using the shadcn chart wrapper.

## Key Findings

### Recommended Stack

The entire implementation fits within the existing dependency set plus recharts. scikit-learn is already installed in the FastAPI container for scoring; `roc_curve`, `precision_recall_curve`, `calibration_curve`, and `roc_auc_score` are stable sklearn APIs requiring no new Python dependencies. On the frontend, recharts v3.8.1 is the right choice: it ships TypeScript types natively, is React 18 / Next.js 14 compatible with `"use client"`, integrates with shadcn/ui's `ChartContainer` which is already used for Tailwind v4 CSS variable wiring, and has built-in `ReferenceLine` for benchmark overlays. No charting library is currently installed in the project, so there is no version conflict to navigate.

**Core technologies:**
- `recharts ^3.8.1`: React-native SVG charting — the standard for this stack, integrates with shadcn
- `shadcn chart component` (via `npx shadcn@latest add chart`): ChartContainer/ChartTooltip wrappers pre-wired for Tailwind v4 tokens, avoids d3-shape ESM conflicts
- `sklearn.metrics` (existing): `roc_curve`, `precision_recall_curve`, `calibration_curve`, `roc_auc_score` — compute server-side, zero new Python dependencies
- `FastAPI GET /api/stats` (new router): single endpoint returns all chart data, curve arrays downsampled to ~200 points, `numpy.float64` cast to `float` before serialization

### Expected Features

Research confirms a clear P1 set for v1.1 and a P2 set to add during implementation if time allows.

**Must have (table stakes):**
- Summary metric row (AUC, Average Precision, n_curations, n_accepted, n_rejected, model type badge) — users need scalar takeaways before charts
- Score distribution histogram colored by assertion (ACCEPTED=green, REJECTED=orange/red) — standard class separation visual
- ROC curve with AUC, diagonal chance line, WCM+Fred Hutch reference lines — universal binary classifier metric
- Precision-recall curve with prevalence-anchored baseline, WCM+Fred Hutch AP reference lines — required companion to ROC for imbalanced data
- Calibration plot with perfect-calibration diagonal, per-bin n= display, low-n warning — isotonic calibration was explicitly applied to these models; users who know the pipeline expect to see its effect
- Strongest Disagreements top 5 inline table with link to full list — most directly actionable feature
- Prerequisite gate on `n_scored_with_assertions >= 1` (not just `curation_count > 0`)

**Should have (competitive advantage):**
- WCM+Fred Hutch benchmark reference lines with sample-size context tooltip ("WCM trained on 900K pairs")
- Model type badge (feedbackIdentity vs. identityOnly) — different expected performance levels
- 95% bootstrap confidence interval displayed alongside AUC point estimate
- PR curve baseline anchored to local positive rate (not hardcoded 0.5)
- Per-bin sample count on calibration chart; dim dots with n < 10

**Defer (v2+):**
- Per-researcher ROC/calibration drilldown — statistically unreliable with typical per-researcher curation counts
- Bootstrap confidence intervals as a standalone feature (include in v1.1 AUC display, not as a toggle)
- Confidence intervals on calibration curve (academic use only)
- Custom benchmark upload
- Real-time stats during pipeline run

### Architecture Approach

The architecture follows the existing "thin client, fat backend" pattern already established by the pipeline summary cards. A single new FastAPI router (`api/routers/stats.py`) handles the SQL join, sklearn metric computation, numpy histogram binning, and disagreement ranking in one pass. Five existing files are modified by adding one to three lines each: `api/routers/pipeline.py` (add `curation_count` to the status response), `api/main.py` (register stats router), `frontend/lib/workflow.tsx` (add `curationCount` to WorkflowState), `frontend/components/sidebar.tsx` (add Statistics nav item with gate), and `frontend/app/pipeline/page.tsx` (add "View Statistics" CTA). Two new files are created: `api/routers/stats.py` and `frontend/app/stats/page.tsx`.

**Major components:**
1. `api/routers/stats.py` — JOIN query, sklearn metric computation, numpy serialization, returns StatsResponse JSON
2. `frontend/app/stats/page.tsx` — `"use client"` component; single `useEffect` fetch on mount; renders four Recharts charts and disagreements table
3. `api/routers/pipeline.py` (modified) — adds `curation_count` to existing `/api/pipeline/status` response, enabling sidebar gate and pipeline completion CTA without a new endpoint
4. `frontend/lib/workflow.tsx` (modified) — `curationCount` added to WorkflowContext, consumed by sidebar and PrerequisiteGate on stats page

### Critical Pitfalls

1. **Calibration plot with too few samples** — With fewer than 50 curated assertions, equal-width bins produce statistically meaningless curves. Implement server-side: check n-per-bin before serializing; if any bin has fewer than 10 samples, return a `calibration_viable: false` flag and a Brier score instead. Never render the calibration chart with sparse bins.

2. **AUC compared to WCM without confidence interval** — WCM's 0.9993 was computed on 900K pairs. A user with 150 assertions has a 95% CI of roughly ±0.05 on their AUC. Displaying a point estimate next to WCM's number implies a gap that is statistically meaningless. Compute 95% bootstrap CI in the FastAPI endpoint (1000 resamples) and display as "AUC: 0.941 (0.882–0.991, n=120)". Consider graying out benchmark reference lines when n < 200.

3. **PR curve baseline anchored to 0.5 instead of positive rate** — The PR random baseline is class prevalence, not 0.5. An institution with 90% ACCEPTED assertions has a natural AUPRC baseline of 0.90. Compute `positive_rate = n_accepted / n_curations` in the backend and return it as the `pr_baseline` field; the frontend `ReferenceLine` uses this dynamic value.

4. **Recharts SSR hydration error** — Recharts uses browser-only APIs. Every file importing Recharts needs `"use client"` at the top. Belt-and-suspenders: wrap the charts component with `dynamic(() => import(...), { ssr: false })`. Use the shadcn chart component to avoid the d3-shape ESM conflict. Verify with `next build && next start`, not just `next dev`.

5. **Gate checks `curation_count > 0` instead of the join** — A user can have 500 imported assertions with zero corresponding scores (pipeline not yet run). The stats API returns NaN or empty curves on a zero-row join. Gate the sidebar and page on `n_scored_with_assertions >= 1`, computed by the stats endpoint or piggybacked onto `/api/pipeline/status`. The endpoint must return a `viable` field even when other stats cannot be computed.

6. **Disagreements framing as "model errors"** — Top disagreements are often legitimate edge cases or noisy imported assertions, not model failures. Label the section "Strongest Score-Assertion Disagreements" with explanatory copy: "These articles had the largest gap between score and assertion. Review them — some may be data entry issues; others reveal edge cases worth investigating." Write this copy before UI review.

## Implications for Roadmap

Based on the strict dependency chain identified in ARCHITECTURE.md, implementation must proceed in a specific order. Backend work unblocks frontend work, and the gate logic must be established before the stats page can render anything meaningful.

### Phase 1: Backend Stats Endpoint
**Rationale:** Everything else depends on this. Frontend cannot render charts without the API. Gate logic requires the `curation_count` addition to `/api/pipeline/status`. This phase is also the highest-risk for statistical correctness errors (the pitfalls that cannot be fixed cosmetically post-launch).
**Delivers:** `GET /api/stats` returning full StatsResponse JSON; `curation_count` added to pipeline status; `n_scored_with_assertions` gate field; AUC with 95% bootstrap CI; calibration viability check; PR curve baseline anchored to positive rate.
**Implements:** `api/routers/stats.py` (new), `api/routers/pipeline.py` (modified), `api/main.py` (1 line)
**Avoids pitfalls:** Calibration with insufficient samples (Pitfall 1), AUC without CI (Pitfall 2), PR baseline at 0.5 (Pitfall 3), gate on wrong condition (Pitfall 5), single-class crash (integration gotcha)

### Phase 2: Workflow Wiring and Navigation
**Rationale:** Gate state and sidebar navigation must be in place before the stats page renders anything. WorkflowContext changes are small but affect every page load. Doing this before the frontend stats page prevents a second round of context refactoring.
**Delivers:** `curationCount` in WorkflowContext; Statistics nav item in sidebar (locked until gate met); "View Statistics" CTA on pipeline completion page.
**Implements:** `frontend/lib/workflow.tsx` (add field), `frontend/components/sidebar.tsx` (add nav item), `frontend/app/pipeline/page.tsx` (add CTA)
**Avoids pitfalls:** Gate on wrong condition (Pitfall 5), PRE-REQ gate logic verified before full page build

### Phase 3: Stats Page Frontend
**Rationale:** Depends on Phase 1 (API contract) and Phase 2 (navigation wiring). This is the largest single piece of frontend work. Doing it last means the API contract is stable and the navigation is already tested.
**Delivers:** `frontend/app/stats/page.tsx` with four Recharts charts (ROC, PR, calibration, distribution histogram), summary metric row, Strongest Disagreements table, PrerequisiteGate integration.
**Uses:** recharts ^3.8.1, shadcn chart component, `apiFetch`, WorkflowContext (`curationCount`)
**Implements:** All chart visualizations; WCM+Fred Hutch reference lines; per-bin n= on calibration chart; disagreements table with explanatory copy
**Avoids pitfalls:** Recharts SSR hydration (Pitfall 4 — `"use client"` + dynamic import), disagreements framing (Pitfall 6 — copy written before review)

### Phase Ordering Rationale

- The dependency chain from ARCHITECTURE.md is strict: API → workflow wiring → frontend. This order is not arbitrary; a developer who builds the frontend first will need to mock the API, then rework the types when the real contract differs.
- Statistical correctness pitfalls (Pitfalls 1–3) are in Phase 1 because they live in the backend. If they slip to Phase 3, fixing them requires changing the API contract and updating the frontend — double the work.
- WorkflowContext changes (Phase 2) are deliberately isolated before the page build because they affect the app-wide context provider. Testing them without the full stats page is faster and safer.
- npm install (`recharts`) and `npx shadcn@latest add chart` happen at the start of Phase 3, not earlier. No charting code is written until the API contract is verified.

### Research Flags

Phases likely needing validation during implementation:
- **Phase 1:** Bootstrap CI computation — verify 1000 resamples completes under 2 seconds for typical n (100–500 assertions). If not, consider precomputing after pipeline run or capping at 500 resamples. Performance trap documented in PITFALLS.md.
- **Phase 1:** `calibration_curve` bin behavior at low n — test with fixture of 20 assertions to confirm the viability gate fires correctly before any chart renders.
- **Phase 3:** `ReferenceLine` with `segment` prop for calibration diagonal — verify against current recharts 3.x docs; API changed from v2 to v3.

Phases with standard, well-documented patterns (no additional research needed):
- **Phase 2:** WorkflowContext additions and sidebar item — identical pattern to existing nav items; no research needed.
- **Phase 3:** `LineChart`, `BarChart`, `ScatterChart` usage — covered by recharts docs and shadcn chart examples; standard pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Verified against recharts GitHub, shadcn docs, sklearn docs, and direct codebase inspection of package.json and requirements.txt |
| Features | HIGH | Standard ML validation chart conventions verified against Azure AutoML, scikit-learn examples, Google ML Crash Course, and PNAS calibration research |
| Architecture | HIGH | Based on direct inspection of existing API routers, frontend components, and WorkflowContext; not speculative |
| Pitfalls | HIGH (statistical), MEDIUM (benchmark comparison) | Statistical pitfalls sourced from PMC, ICLR, MIT Press; benchmark comparison pitfalls are domain-specific with less external literature |

**Overall confidence:** HIGH

### Gaps to Address

- **WCM calibration curve data:** The calibration benchmark overlay (showing WCM's calibration curve as a reference, not just a scalar) would require the actual `(prob_pred, prob_true)` array from WCM's validation run. This data is not in PROJECT.md. For v1.1, use only the AUC scalar as a reference line; defer calibration curve overlay to v1.x.
- **WCM positive rate for PR benchmark:** Fred Hutch and WCM PR-AUC benchmarks were computed on datasets with unknown positive rates. Direct PR-AUC comparison is approximate. The PR chart should note this; exact WCM prevalence should be sourced from the original validation publication before adding a PR benchmark line.
- **Bootstrap CI performance at scale:** Documented in PITFALLS.md as a performance trap at n >= 500. For typical desktop users (100–300 assertions) this is not an issue; validate timing early in Phase 1 with a realistic fixture.
- **`calibrated_score` column scale:** ARCHITECTURE.md notes the DB stores scores as 0.0–1.0 float but the frontend displays 0–100. The stats endpoint must multiply by 100 before binning for histograms and calibration plots. Confirm with a live DB query before writing the endpoint.

## Sources

### Primary (HIGH confidence)
- sklearn.metrics docs (roc_curve, precision_recall_curve, calibration_curve, roc_auc_score) — scikit-learn 1.8.0 stable API
- shadcn/ui chart documentation — recharts v3 integration, ChartContainer wiring
- Recharts GitHub releases — v3.8.1 confirmed latest stable; ReferenceLine, ComposedChart, ScatterChart confirmed
- Stable reliability diagrams (PNAS, PMC) — calibration bin size and sample size requirements
- The Effect of Class Imbalance on Precision-Recall Curves (MIT Press) — PR baseline anchoring
- Direct codebase inspection: `api/models.py`, `api/routers/pipeline.py`, `frontend/package.json`, `frontend/lib/workflow.tsx`, `.planning/PROJECT.md`

### Secondary (MEDIUM confidence)
- Azure AutoML: Evaluate experiment results — classification chart layout conventions
- Google ML Crash Course: ROC and AUC — ROC visualization conventions
- Evidently AI: Explain ROC curve — web dashboard best practices
- A comparison of AUC estimators in small-sample studies (PMLR) — CI guidance for small n
- LogRocket: Best React chart libraries 2025 — comparative library assessment

### Tertiary (LOW confidence)
- abzu.ai calibration introduction — "10 bins is the common safe default"; corroborated by sklearn defaults but editorial source
- Recharts/Next.js GitHub issues (#2918, shadcn/ui #5661) — SSR hydration pitfall; confirmed by issue reports, validate against current recharts 3.x behavior

---
*Research completed: 2026-04-04*
*Ready for roadmap: yes*
