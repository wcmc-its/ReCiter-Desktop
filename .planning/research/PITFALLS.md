# Pitfalls Research

**Domain:** ML validation statistics added to an existing disambiguation scoring app (Next.js + FastAPI + XGBoost)
**Researched:** 2026-04-04
**Confidence:** HIGH for statistical pitfalls; HIGH for Next.js/Recharts pitfalls; MEDIUM for benchmark comparison pitfalls (domain-specific, less literature)

---

## Critical Pitfalls

### Pitfall 1: Calibration Plot Rendered with Too Few Samples per Bin

**What goes wrong:**
With fewer than ~50–100 curated assertions total, equal-width binning produces bins containing 0–3 samples each. The plotted calibration curve is dominated by noise: sharp spikes, empty bins, and zigzag patterns that look like model miscalibration but are pure sampling artifact. A user with 40 accepted/rejected assertions using 10 bins gets an average of 4 data points per bin — statistically meaningless. The plot visually implies the model is badly calibrated at WCM when it simply has no data.

**Why it happens:**
Calibration plots are imported from ML notebooks where 10,000+ samples are assumed. The code works; the output is misleading. Developers render it without validating n-per-bin.

**How to avoid:**
- Compute n-per-bin before rendering. If any bin has fewer than 10 samples, fall back to a simpler display: show a single Brier score and a plain-text note ("Not enough assertions for a calibration plot. Need at least 100 across the score range").
- Use quantile binning (equal-count) instead of equal-width binning when n < 500. Quantile binning guarantees every bin has observations.
- Display per-bin sample count as a bar chart below the calibration line (the "rug" pattern used by scikit-learn's CalibrationDisplay). This makes sparse bins visually obvious.
- Set a hard gate: render the calibration plot only when n_assertions >= 50. Below that, show a sample-size warning instead of an unreliable chart.

**Warning signs:**
- Calibration curve endpoint has only 1–2 samples in the highest-score bin (near 100).
- Plot is jagged rather than smooth or monotone.
- Any bin with zero samples appears as a gap in the line.

**Phase to address:** The phase that builds the Statistics page (v1.1 backend + frontend). Gate logic must be computed server-side, not client-side.

---

### Pitfall 2: ROC AUC Compared to WCM 0.9993 Without Sample Size Context

**What goes wrong:**
WCM's feedback model AUC was computed on ~900,000 curated pairs. A user institution with 100–500 assertions will compute an AUC with very wide confidence intervals — the 95% CI for AUC from 150 balanced pairs spans roughly ±0.05. Displaying their AUC as 0.94 next to WCM's 0.9993 implies the user's model is measurably worse. In reality, their AUC is statistically indistinguishable from 0.9993. Worse: if the 100 assertions are heavily imbalanced (90 accepted, 10 rejected), the AUC estimate itself is unreliable because a few wrong predictions swing the curve significantly.

**Why it happens:**
AUC is displayed as a point estimate. Confidence intervals are not shown. WCM's benchmark number looks precise and authoritative. Users (librarians, not statisticians) will read a gap as a real gap.

**How to avoid:**
- Always show AUC with a 95% bootstrap confidence interval (1000 bootstrap samples, easy with `sklearn.utils.resample` or `scipy.stats.bootstrap`).
- Display the sample size (n_assertions) prominently next to the AUC. "AUC: 0.941 (95% CI: 0.882–0.991, n=120)" communicates uncertainty correctly.
- Add a contextual note: "WCM benchmark computed on 900K pairs. Your result is based on N pairs; overlapping confidence intervals mean performance may be equivalent."
- Consider graying out or disabling the WCM reference line if the user's n < 200, replacing it with a note rather than a visual comparison that implies precision.

**Warning signs:**
- AUC displayed without CI.
- n_assertions < 200 but benchmark comparison reference lines shown as authoritative.
- All assertions are the same label (all accepted = AUC is undefined/degenerate).

**Phase to address:** Statistics API endpoint (FastAPI) — CIs must be computed server-side and returned alongside point estimates.

---

### Pitfall 3: PR Curve Baseline Not Anchored to Local Positive Rate

**What goes wrong:**
The precision-recall curve's random-classifier baseline is not 0.5 (like ROC) — it equals the positive rate (prevalence) of assertions in the data. If 80% of a user's imported assertions are ACCEPTED, the baseline PR-AUC is 0.80, not 0.5. Showing WCM's PR-AUC benchmark without knowing WCM's positive rate makes comparison meaningless. A user institution with 90% ACCEPTED assertions (highly biased toward acceptance, common in "we're validating our own researchers" workflows) will see a naturally high PR-AUC even with a mediocre model.

**Why it happens:**
PR curves are borrowed from class-balanced evaluation contexts. The prevalence-dependency of PR-AUC is not widely known outside ML practitioners. The WCM and Fred Hutch benchmarks were computed on large, balanced datasets; a small institution's data is rarely balanced.

**How to avoid:**
- Always display the "no-skill" baseline on the PR curve as a horizontal line at y = positive_rate (not 0.5).
- Show the positive rate (% accepted) as a labelled stat near the chart.
- Compute and display normalized lift: (AUPRC - baseline) / (1 - baseline). This makes cross-institution comparison valid regardless of class balance.
- In the benchmark overlay label, add the WCM positive rate if known, or note that direct comparison is approximate.

**Warning signs:**
- PR curve shows very high AUPRC (>0.95) but the model's calibration is poor — check positive rate; may be baseline effect.
- Benchmark reference line shown without corresponding prevalence note.

**Phase to address:** Same as Pitfall 2 — Statistics API endpoint and chart labeling.

---

### Pitfall 4: Recharts SSR Hydration Error Breaks the Entire Stats Page

**What goes wrong:**
Recharts uses browser-only APIs (ResizeObserver, DOM dimension queries) and d3 internals that cannot run in Node.js during server-side rendering. In Next.js 14 App Router, any component that imports Recharts without `"use client"` will throw a server-render error. Even with `"use client"`, the initial server HTML (empty SVG containers) differs from client-rendered SVGs, causing React hydration mismatch warnings. In some Recharts versions (2.1.13+), a CommonJS/ESM conflict with d3-shape causes a hard server crash (`require() of ES Module not supported`).

**Why it happens:**
The project currently has zero charting libraries installed (confirmed in package.json). The first developer to add Recharts will follow generic tutorials that don't account for the SSR context. App Router components default to Server Components; forgetting `"use client"` is a common first mistake.

**How to avoid:**
- Add `"use client"` to every file that imports Recharts — not just to a wrapper but to the chart files themselves.
- Wrap the chart container component with `next/dynamic` and `{ ssr: false }` as a belt-and-suspenders approach, especially if the component tree is complex: `const StatsCharts = dynamic(() => import("@/components/stats-charts"), { ssr: false })`.
- Use shadcn/ui's chart component (`npx shadcn@latest add chart`) which ships pre-wired for Recharts v3 with correct `"use client"` placement and avoids the d3-shape ESM conflict. This is the lowest-risk path given shadcn is already in the project.
- Pin Recharts version (no caret) in package.json to prevent silent upgrades that re-introduce the ESM conflict.

**Warning signs:**
- Browser console: "Hydration failed because the server rendered HTML didn't match the client."
- Server log: "require() of ES Module ... not supported."
- Charts render blank (zero-height SVG) on first load but appear on refresh.

**Phase to address:** Stats page frontend build phase — must be caught in the initial chart integration, not after the full page is built.

---

### Pitfall 5: Disagreements Section Surfaces Alarming Cases That Are Actually Correct

**What goes wrong:**
"Strongest Disagreements" is defined as articles where the model scored high but the user rejected, or scored low but the user accepted. These are presented ranked by score-assertion gap. However, many of the top disagreements will not be model errors — they are legitimate edge cases: a researcher published under a different name variant, co-authored with a famous homonym, or the institution's imported assertions contain a data entry mistake. Displaying them without context as "the model got these wrong" trains users to distrust the model unfairly and generates support requests.

**Why it happens:**
Disagreement analysis in research contexts assumes ground truth is reliable. In practice, imported assertions (curations) from prior systems are noisy — they often include bulk-imported decisions, not human-reviewed ones. The top disagreements by score gap are often the most ambiguous cases, not systematic model failures.

**How to avoid:**
- Label the section "Strongest Score-Assertion Disagreements" not "Model Errors."
- Add a one-sentence explanation in the UI: "These are articles where the score and your assertion differ most. Review them — some may be data entry issues; others may reveal edge cases worth investigating."
- Show the model's feature evidence (top 3 features) inline in the table for each disagreement so users can evaluate the reason.
- Limit the inline table to 5 rows — enough to be actionable, not enough to overwhelm.
- Do not present disagreement count as a "model accuracy" metric. It conflates assertion quality with model quality.

**Warning signs:**
- Top disagreement is a researcher with a very common name (John Lee, Wei Zhang) — expected disagreements, not model errors.
- More than 30% of top disagreements are ACCEPTED articles scored low — suggests assertions were bulk-imported at a liberal threshold.

**Phase to address:** The Disagreements section build phase — labeling and context copy must be written before UI review, not after.

---

### Pitfall 6: Gating Logic Checks Wrong Condition

**What goes wrong:**
The stats page gate should show stats only when curations/assertions exist. A naive implementation checks `curation_count > 0`. But this misses the join: stats require scored articles that also have an assertion. A user can import 500 assertions for researchers not yet run through the pipeline (no scores), or run the pipeline before importing assertions (scores exist, but no curations joined to scores). The API endpoint crashes or returns degenerate metrics (AUC = NaN, empty curves) when `JOIN(person_article_score, curations) = 0 rows` even though `curation_count > 0`.

**Why it happens:**
The gate logic and the stats computation logic are written independently. The frontend gate talks to the workflow state API; the stats API endpoint assumes data is already valid. Neither checks the intersection.

**How to avoid:**
- The stats API endpoint must return a `{ viable: bool, n_scored_with_assertions: int }` field regardless of whether other stats are requested.
- Gate the stats page (both sidebar visibility and page content) on `n_scored_with_assertions >= 1`, not just `curation_count > 0`.
- Add progressive disclosure: sidebar shows "Statistics (run pipeline to activate)" when assertions exist but no scores are joined.
- Compute and return the minimum viable n in the API: `SELECT COUNT(*) FROM person_article_score ps JOIN curations c ON ps.person_id = c.person_id AND ps.pmid = c.pmid`.

**Warning signs:**
- AUC or AUPRC returns NaN or 0.0.
- ROC curve shows a single point rather than a curve.
- Stats page is shown in sidebar but API returns 500 on first load.

**Phase to address:** The Statistics API endpoint build phase — data validation before computation.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Show AUC as point estimate only | Simpler UI, faster build | Users misread small gaps vs. WCM benchmark as significant | Never — add CI from the start |
| Equal-width bins regardless of n | One code path | Misleading calibration plots with small n | Never — implement n-check on first build |
| Compute stats on frontend from raw score data | No new API endpoint | Exposes all raw scores in browser, computation fails for large datasets | Never — compute server-side |
| Use `suppressHydrationWarning` to silence chart errors | Silences console noise | Masks real rendering failures, charts may be blank | Never — fix the SSR boundary properly |
| Skip WCM reference lines until later | Faster MVP | Reference lines are the whole point of the page; hard to add retroactively once charts are styled | Acceptable for a first internal build, not acceptable for user-facing release |
| Show disagreements without explanation copy | Saves writing effort | Users will interpret disagreements as pure model errors and file support tickets | Never — write the copy on first build |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| FastAPI → Next.js stats endpoint | Returning raw sklearn metric objects (dict with numpy types) causes JSON serialization error | Explicitly cast numpy float64/int64 to Python float/int before returning; use `float(auc_score)` not `auc_score` |
| MariaDB → Python stats computation | Loading all `person_article_score` rows into pandas for AUC computation at 100K rows causes memory spike | Use SQL aggregation for histograms; load only the joined (scored + asserted) rows for metric computation |
| Recharts + shadcn/ui existing install | Adding shadcn chart component to a project that already has `shadcn` in package.json may conflict | Run `npx shadcn@latest add chart` — shadcn chart is an add-on that brings Recharts; don't install Recharts separately |
| sklearn `roc_auc_score` with single-class assertions | Throws `ValueError: Only one class present in y_true` if all assertions are ACCEPTED or all REJECTED | Wrap in try/except, return `{ viable: false, reason: "need_both_classes" }` before attempting computation |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Computing bootstrap CIs synchronously in the HTTP request | Stats endpoint times out after 30s; request fails | Precompute stats after each pipeline run and cache in DB table; return cached values | At n_assertions >= 500, 1000 bootstraps takes 2–5s; at 5000 it takes 20–40s |
| Loading full score distribution for histogram in browser | Slow page load, large JSON payload for 50K rows | Return pre-aggregated histogram bins from API (array of `{ bin_start, bin_end, count, assertion_count }`) | At 10K+ scored articles the raw payload exceeds 1MB |
| Re-rendering all 4 charts on every page focus/tab switch | Charts flash and recalculate needlessly | Fetch stats once on mount; cache in component state or React Query; do not re-fetch on window focus | Not a scale issue — noticeable from the first use |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing ROC, PR, calibration, and score distribution all on one page without tabs or sections | Page is overwhelming; users don't know what to look at first | Use a clear section hierarchy: (1) Summary metrics card at top, (2) Score Distribution, (3) expandable advanced charts (ROC, PR, calibration) |
| WCM benchmark line with no explanation | "Why is my model being compared to a hospital?" Users don't know WCM trained the model | Add a one-line tooltip or footnote: "WCM trained the original model on 900K pairs. This line shows their measured performance as a reference." |
| Displaying AUC=1.0 or AUC=NaN without explanation | Looks like a bug or a perfect model; users assume it means the model is broken | Detect and display a specific message: "All assertions are the same label — cannot compute AUC. Add both accepted and rejected assertions." |
| Disagreements table shows only PMID and score delta | Users have no context to act | Show: researcher name, article title, assertion label, model score, and a link to that article in the Results page |

---

## "Looks Done But Isn't" Checklist

- [ ] **Calibration plot:** Has per-bin sample count overlay — verify bins with n<10 are either suppressed or visually flagged
- [ ] **AUC display:** Shows 95% bootstrap confidence interval alongside point estimate — verify CI is computed server-side and returned in API response
- [ ] **PR curve:** Has a "no-skill" baseline line at y = positive_rate — verify baseline is dynamic (computed from data), not hardcoded at 0.5
- [ ] **Recharts/chart bundle:** Charts render without hydration warnings in production build — verify with `next build && next start`, not just `next dev`
- [ ] **Stats gate:** Page is hidden in sidebar when `n_scored_with_assertions = 0` even if `curation_count > 0` — verify by importing assertions before running pipeline
- [ ] **Disagreements table:** Has explanatory copy framing disagreements as "worth investigating" not "model errors" — verify copy is present before user testing
- [ ] **Single-class assertions:** API handles `ValueError: Only one class present` gracefully — verify by creating a test fixture with only ACCEPTED assertions
- [ ] **Benchmark reference lines:** Labeled with WCM/Fred Hutch name and sample size context — verify label is visible at multiple viewport widths

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Calibration plot shipped without n-per-bin guard | LOW | Add server-side n_per_bin check to API; add fallback UI component for insufficient data; no DB migration needed |
| AUC point estimates shipped without CIs | LOW | Add bootstrap CI computation to stats endpoint; update API response schema; update frontend to display CI |
| Recharts hydration errors in production | MEDIUM | Wrap chart component in `dynamic(..., { ssr: false })`; switch to shadcn chart component; test production build |
| Stats page shows for users with assertions but no joined scores | LOW | Fix gate condition in workflow state API; one-line SQL change; no migration needed |
| Disagreements section misinterpreted by users in production | LOW-MEDIUM | Add explanatory copy; add feature evidence column; no structural change needed; requires user communication |
| PR baseline line missing; AUC comparison misleading | LOW | Add baseline line to chart config; add prevalence stat to API response; cosmetic change |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Calibration plot with insufficient samples | Stats API endpoint build | Test with fixture of 20 assertions — confirm plot is replaced by warning message |
| AUC displayed without confidence interval | Stats API endpoint build | Confirm API response includes `auc_lower`, `auc_upper` fields |
| PR curve baseline not at positive rate | Stats charts frontend build | Confirm baseline line y-value changes when assertion balance changes |
| Recharts SSR hydration error | Chart integration (first chart added) | Run `next build` and check for hydration warnings in browser console with production build |
| Disagreements section framing | Disagreements UI build | User review: show to one non-ML user and ask what it means; check for "model is broken" interpretation |
| Gate checks wrong condition | Stats gate/gating logic implementation | Automated test: import assertions, skip pipeline, verify stats page hidden; run pipeline, verify stats page appears |
| Single-class assertion crash | Stats API endpoint build | Unit test with all-ACCEPTED fixture; confirm `viable: false` returned, no 500 error |
| WCM benchmark context missing | Stats charts frontend build | Visual review: benchmark line must be labeled with institution name and sample size on every chart |

---

## Sources

- [Stable reliability diagrams for probabilistic classifiers (CORP method) — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7923594/)
- [Understanding Model Calibration (ICLR 2025 blog)](https://iclr-blogposts.github.io/2025/blog/calibration/)
- [CalibrationDisplay — scikit-learn docs](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibrationDisplay.html)
- [1.16. Probability calibration — scikit-learn docs](https://scikit-learn.org/stable/modules/calibration.html)
- [The Effect of Class Imbalance on Precision-Recall Curves — MIT Press](https://direct.mit.edu/neco/article/33/4/853/97475/The-Effect-of-Class-Imbalance-on-Precision-Recall)
- [ROC Curves and PR Curves for Imbalanced Classification — Machine Learning Mastery](https://machinelearningmastery.com/roc-curves-and-precision-recall-curves-for-imbalanced-classification/)
- [The receiver operating characteristic curve accurately assesses imbalanced datasets — PMC 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11240176/)
- [Error in Next.js with Recharts — GitHub Issue #2918](https://github.com/recharts/recharts/issues/2918)
- [Charts not working in next-15 — shadcn/ui GitHub Issue #5661](https://github.com/shadcn-ui/ui/issues/5661)
- [shadcn chart component docs](https://ui.shadcn.com/docs/components/radix/chart)
- [A comparison of AUC estimators in small-sample studies — PMLR](https://proceedings.mlr.press/v8/airola10a.html)

---
*Pitfalls research for: ML validation statistics (ROC, calibration, PR, disagreements) added to ReCiter Desktop*
*Researched: 2026-04-04*
