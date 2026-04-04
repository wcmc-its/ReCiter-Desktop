# Feature Research

**Domain:** ML model validation statistics page — binary classification, post-pipeline
**Researched:** 2026-04-04
**Confidence:** HIGH (core chart conventions verified against Azure AutoML, scikit-learn, Google ML Crash Course; charting library verified against recharts docs/npm)

---

## Feature Landscape

### Table Stakes (Users Expect These)

These are standard features of any ML validation view. Missing one makes the page feel
incomplete or unprofessional to anyone with ML training.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| ROC curve with AUC scalar | Universal metric for binary classifiers; AUC is the headline number users cite when comparing models | LOW | FPR on x-axis, TPR on y-axis; axes labeled 0–1; AUC displayed prominently near or on the chart as a badge/callout |
| Diagonal chance line on ROC | Every ROC tutorial shows the y=x random-classifier baseline; its absence looks like a bug | LOW | Dashed gray line from (0,0) to (1,1); labeled "Random" or "No skill" |
| Precision-recall curve | Expected companion to ROC; PR curves expose performance on imbalanced data that ROC can hide | MEDIUM | Recall on x-axis, Precision on y-axis; horizontal baseline at prevalence rate |
| Calibration plot (reliability diagram) | Isotonic calibration was explicitly applied to these models; users who know the pipeline expect to see its effect | MEDIUM | Predicted probability (x) vs. fraction positive (y); diagonal y=x = perfect calibration; each bin shown as a point; see conventions below |
| Score distribution histogram colored by assertion | Standard way to visually confirm class separation; already partially built for per-researcher view | LOW | Overlapping histograms; green=ACCEPTED, red/orange=REJECTED; x-axis 0–100; bins 10 wide; well-separated = good model |
| Summary metric row (AUC, AP, count) | Users need scalar takeaways above the charts; headline numbers before diving into curves | LOW | AUC for ROC, Average Precision for PR curve, N curations used, N accepted vs. N rejected |
| Gate: only shown when curations exist | Users with no assertions would see meaningless flat/empty charts; gate prevents confusion | LOW | Already implemented as a pattern via `PrerequisiteGate`; need curation count check, not just score count |

### Differentiators (Competitive Advantage)

These raise ReCiter Desktop above generic ML dashboards and are directly tied to the project's
institutional positioning.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| WCM benchmark reference lines on ROC and PR curves | Lets institutions immediately see how they compare to a production-validated system; turns abstract charts into actionable context | LOW | Horizontal reference lines at known AUC values: feedbackIdentity=0.9993, identityOnly=0.9776; Fred Hutch external validation at 0.9993; label each line in legend |
| WCM benchmark reference lines on calibration plot | Same positioning rationale — calibration quality is non-obvious without a reference point | MEDIUM | Requires WCM calibration curve data, not just a scalar; or simplify to a callout note: "WCM model well-calibrated at this range" |
| Strongest Disagreements section | Directly actionable: users can find and fix miscurated articles, which improves future model training | MEDIUM | See full definition below |
| Model type indicator | feedbackIdentity vs. identityOnly have different expected performance levels; showing which model produced the stats prevents misinterpretation | LOW | Badge next to headline: "feedbackIdentity model" or "identityOnly model" |
| Bin count display on calibration chart | Shows users how many (person_id, pmid) pairs fall in each bin — critical for interpreting noisy bins | LOW | Display n= inside or below each calibration dot; dim dots with n < threshold (e.g., n < 5) |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Per-researcher ROC/calibration drilldown | Seems like useful granularity | Individual researchers have too few curated articles for stable curves; calibration is undefined with <20 samples per bin; results would be misleading and noisy | Explicitly scope the stats page to aggregate only; note this in the UI with copy like "across all researchers" |
| Interactive threshold slider on ROC curve | Familiar from per-researcher results page | Adds complexity without insight; the ROC curve is threshold-agnostic by definition; a slider implies the user should tune the threshold here, which conflicts with the slider on the per-researcher page | Show the current operating threshold as a dot on the ROC curve, not a draggable control |
| Confusion matrix | Natural pairing with ROC | The stats page already shows the histogram; a confusion matrix requires picking a single threshold and is less expressive than the full curve; also harder to read for non-ML users | If needed, derive TP/FP/FN/TN counts in the summary row at the current default threshold (70), not as a full matrix UI |
| Real-time stats during pipeline run | Feels dynamic | Stats require the join of `person_article_score` + `curations`; during a run, scores are partial; incremental stats are misleading | Compute stats post-hoc after pipeline completes; stats page is post-pipeline only |
| Custom benchmark upload | Flexibility | Adds file parsing, validation, and UI complexity; the two known benchmarks (WCM, Fred Hutch) are the only meaningful comparisons for this model | Hard-code WCM and Fred Hutch as named reference lines; label them clearly |
| Confidence intervals on ROC curve | Academically rigorous | Requires bootstrap resampling (computationally expensive on backend) and more complex frontend rendering; calibration note about small n is sufficient | Note sample size in the summary row; mention that small N reduces reliability instead of computing CIs |
| Average precision vs. AUROC debate copy | Some users will ask "which is better?" | Not a UI feature; turns into documentation/tooltip sprawl | One sentence tooltip on each chart explaining when it's most meaningful |

---

## Feature Dependencies

```
[Stats Page]
    └──requires──> [Curations in DB] (person_id + pmid + assertion)
                       └──requires──> [Scoring pipeline has run] (person_article_score rows exist)
                                          └──requires──> [Researchers uploaded] (identity rows)

[Strongest Disagreements]
    └──requires──> [Stats join query: person_article_score + curation + article + identity]
    └──enhances──> [Results page per-researcher] (disagreements link to /results/[personId] filtered)

[Benchmark reference lines]
    └──requires──> [Recharts ReferenceLine component] (or equivalent SVG overlay)
    └──independent of──> [user data] (hardcoded WCM/Fred Hutch scalars)

[Calibration plot]
    └──requires──> [Backend endpoint] computing calibration_curve via scikit-learn
    └──requires──> [Score stored as raw probability OR normalized 0-100 converted back to 0-1]
    Note: calibrated_score in DB is stored as float (0.0–1.0 pre-*100); confirm before backend work

[Score distribution histogram by assertion]
    └──requires──> [Join: person_article_score + curation on (person_id, pmid)]
    └──builds on──> [Existing per-researcher histogram] (same shape, new coloring logic)
```

### Dependency Notes

- **Stats page requires curations:** The gate should check `SELECT COUNT(*) FROM curation` > 0, not just score count. This is a different check than the existing `scoreCount > 0` gate on the Results page.
- **Calibration requires probability not integer scores:** The `calibrated_score` column is FLOAT (0.0–1.0) before the frontend multiplies by 100. The backend stats endpoint must use the raw float, not the `round(score * 100)` integer shown in the UI.
- **Strongest Disagreements links to per-researcher Results:** The disagreements table should deep-link to `/results/[personId]` with the specific PMID highlighted or pre-filtered. This already exists as a page; no new route needed.

---

## Strongest Disagreements — Full Definition

This section needs precise specification because it is the most novel and domain-specific feature.

### What It Is

A ranked table of (person_id, pmid) pairs where the model score and the human assertion diverge most. Two disagreement types:

- **High score, REJECTED** — Model says "likely match" (score ≥ threshold), human says "not this person's article." These are false positives. The model is overconfident.
- **Low score, ACCEPTED** — Model says "unlikely match" (score < threshold), human says "this is theirs." These are false negatives. The model missed something.

### Ranking Approach

Rank by absolute disagreement magnitude: `|score - assertion_value|` where assertion_value = 100 for ACCEPTED and 0 for REJECTED. This simplifies to:
- For REJECTED articles: rank by `score DESC` (highest score first = worst FP)
- For UPDATED/ACCEPTED articles: rank by `score ASC` (lowest score first = worst FN)

Combine both lists, re-rank by magnitude, take top N.

### What to Show Per Row

| Column | Content |
|--------|---------|
| Researcher | first_name + last_name |
| Article | Truncated title (link to PubMed) |
| Score | Score badge (same component as results page) |
| Assertion | "ACCEPTED" or "REJECTED" badge |
| Gap | Numeric gap (e.g., "Score 91, Rejected" or "Score 12, Accepted") |
| Link | "View" → /results/[personId] |

### Inline vs. Full View

- **Inline (Stats page):** Top 5 rows. "View all X disagreements →" link filters the Results page.
- **Full view:** Use existing Results page filtered to disagreement set. No new page needed for v1.1.

### Threshold for "disagreement"

Use the same default threshold (70) stored in config. A REJECTED article scoring 69 is barely a disagreement and should rank lower than a REJECTED article scoring 95. The gap metric handles this automatically.

---

## Calibration Plot Conventions

Research-backed conventions that must be followed to avoid misleading the user:

**Bin size:** 10 bins (n_bins=10) using uniform strategy is the standard for scikit-learn `calibration_curve`. Use 10 unless curation count is < 50, in which case fall back to 5 bins and display a warning "Limited samples — calibration plot may be noisy."

**Strategy:** Uniform (equal-width bins) is the default and most interpretable for users. Quantile binning better handles uneven score distributions but produces unequal x-axis spacing which confuses non-ML users. Use uniform.

**Diagonal reference:** The y=x line is mandatory. It represents perfect calibration. Label it "Perfect calibration" in the legend.

**Bin sample count:** Display n= for each bin point. Research shows that bins with very few samples produce unreliable calibration estimates. Dim or mark dots with n < 5 as "low confidence."

**Axis labels:** x-axis = "Mean predicted score", y-axis = "Fraction of positives (ACCEPTED rate)". Never use raw probability language like "0.0 to 1.0" when the UI shows scores 0–100; normalize internally but display consistently with the rest of the app.

**Over/under calibration interpretation:** If points are above the diagonal, the model under-predicts (conservative); below = over-predicts (overconfident). This is standard. A note in the chart title or tooltip should explain this in plain English: "Points above the line: model is conservative. Points below: model is overconfident."

---

## MVP Definition

### Launch With (v1.1 milestone)

- [ ] Summary metric row — AUC, Average Precision, N curations, N accepted vs. rejected, model type badge
- [ ] Score distribution histogram colored by assertion (ACCEPTED=green, REJECTED=red)
- [ ] ROC curve with AUC, diagonal chance line, WCM+Fred Hutch reference lines
- [ ] Precision-recall curve with baseline reference, WCM+Fred Hutch AP reference lines
- [ ] Calibration plot with diagonal, bin counts displayed, low-n warning
- [ ] Strongest Disagreements: top 5 inline table + "View all" link
- [ ] Gate: page hidden (prerequisite gate) when curation count = 0

### Add After Validation (v1.x)

- [ ] Current operating threshold dot on ROC curve — only after user testing confirms value
- [ ] Calibration plot for WCM as an overlay (requires WCM calibration curve data, not just scalar)
- [ ] Export stats as PNG or CSV — useful for institutional reports, low priority until requested

### Future Consideration (v2+)

- [ ] Per-researcher mini-stats (requires many more curations per researcher than typical users have)
- [ ] Confidence intervals via bootstrap (expensive computation, academic use only)
- [ ] Custom benchmark upload

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Summary metric row (AUC, AP, counts) | HIGH | LOW | P1 |
| Score distribution histogram by assertion | HIGH | LOW | P1 |
| ROC curve + AUC + reference lines | HIGH | MEDIUM | P1 |
| PR curve + reference lines | HIGH | MEDIUM | P1 |
| Calibration plot | MEDIUM | MEDIUM | P1 |
| Strongest Disagreements top 5 | HIGH | MEDIUM | P1 |
| Prerequisite gate (curation count) | HIGH | LOW | P1 |
| Model type badge | MEDIUM | LOW | P1 |
| Bin counts on calibration | MEDIUM | LOW | P2 |
| Low-n calibration warning | MEDIUM | LOW | P2 |
| Operating threshold dot on ROC | LOW | LOW | P2 |
| "View all" disagreements filtered link | MEDIUM | LOW | P2 |

**Priority key:**
- P1: Must have for v1.1 launch
- P2: Should have, add during v1.1 implementation if time allows
- P3: Nice to have, future milestone

---

## Backend Computation Notes

All curve data must be computed server-side in FastAPI (Python), not in the browser. The browser
only receives arrays of (x, y) points. This is correct because:

1. scikit-learn's `roc_curve`, `precision_recall_curve`, and `calibration_curve` are already
   available (scikit-learn is in requirements.txt for the scoring pipeline).
2. The join query (`person_article_score` + `curation`) is a SQL operation best done in Python.
3. Frontend charting libraries (Recharts) expect pre-computed arrays, not raw data tables.

**New API endpoint needed:** `GET /api/stats` returning:
```json
{
  "model_type": "feedbackIdentity",
  "n_curations": 342,
  "n_accepted": 287,
  "n_rejected": 55,
  "auc_roc": 0.9921,
  "average_precision": 0.9874,
  "roc_curve": [{"fpr": 0.0, "tpr": 0.0}, ...],
  "pr_curve": [{"recall": 0.0, "precision": 1.0}, ...],
  "calibration_curve": [{"prob_pred": 0.05, "prob_true": 0.04, "n": 12}, ...],
  "score_distribution": [
    {"bin_start": 0, "accepted": 1, "rejected": 8},
    ...
  ],
  "strongest_disagreements": [
    {"person_id": "...", "pmid": "...", "score": 91, "assertion": "REJECTED", "gap": 91, "title": "...", "first_name": "...", "last_name": "..."},
    ...
  ]
}
```

**Charting library:** Recharts (recharts@3.x, current as of 2026). Use:
- `LineChart` + `Line` for ROC and PR curves
- `ReferenceLine` for diagonal (y=x) and benchmark horizontal lines — confirmed supported
- `BarChart` + `Bar` for score distribution histogram (two stacked bars per bin: accepted + rejected)
- `ScatterChart` + `Scatter` for calibration plot dots (each bin = one point)
- `ReferenceLine` with `segment` prop for the perfect calibration diagonal on scatter chart

Recharts is the correct choice: it is lightweight, React-native, has no peer dependency conflicts
with the existing stack (Next.js 14, Tailwind, shadcn), and supports all required chart primitives.
No alternative is needed.

---

## Sources

- [Azure AutoML: Evaluate experiment results](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-understand-automated-ml?view=azureml-api-2) — authoritative reference for classification chart layout and conventions (ROC, PR, calibration)
- [scikit-learn: calibration_curve](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.calibration_curve.html) — n_bins parameter, strategy options, return values
- [scikit-learn: Precision-Recall](https://scikit-learn.org/stable/auto_examples/model_selection/plot_precision_recall.html) — PR curve conventions
- [scikit-learn: roc_auc_score](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_auc_score.html) — AUC computation
- [Google ML Crash Course: ROC and AUC](https://developers.google.com/machine-learning/crash-course/classification/roc-and-auc) — ROC visualization conventions
- [Evidently AI: Explain ROC curve](https://www.evidentlyai.com/classification-metrics/explain-roc-curve) — ROC best practices for web dashboards
- [Stable reliability diagrams — PNAS](https://www.pnas.org/doi/10.1073/pnas.2016191118) — calibration bin size research
- [abzu.ai: Calibration introduction](https://www.abzu.ai/data-science/calibration-introduction-part-1/) — "10 bins is the common safe default" sourced here
- [recharts npm](https://www.npmjs.com/package/recharts) — version 3.x confirmed current; ReferenceLine, ComposedChart, ScatterChart confirmed supported
- [Recharts: Line Chart With Reference Lines](https://recharts.github.io/en-US/examples/LineChartWithReferenceLines/) — confirms ReferenceLine works in LineChart context
- [MachineLearningMastery: ROC vs PR Curves for Imbalanced Classification](https://machinelearningmastery.com/roc-curves-and-precision-recall-curves-for-imbalanced-classification/) — anti-pattern: ROC alone is insufficient for imbalanced data

---
*Feature research for: ML validation statistics page (ReCiter Desktop v1.1)*
*Researched: 2026-04-04*
