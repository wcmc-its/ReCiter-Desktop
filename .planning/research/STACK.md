# Stack Research

**Domain:** Statistical visualization in a Next.js 14 App Router + FastAPI app
**Researched:** 2026-04-04
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| recharts | ^3.8.1 | ROC, calibration, PR, histogram charts | 3.6M+ weekly downloads, React-native SVG components, already used by shadcn/ui chart primitives present in this project |
| shadcn/ui chart | latest (via `npx shadcn@latest add chart`) | ChartContainer + ChartTooltip wrappers | Project already uses shadcn/ui and Base UI; shadcn chart component ships the correct ChartContainer that wraps recharts ResponsiveContainer and wires CSS variable tokens to Tailwind v4 |
| sklearn.metrics (existing) | already in api/requirements.txt | Compute AUC, PR, calibration curve server-side | scikit-learn is already installed in the FastAPI container; all curve computation belongs in Python, not JS |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sklearn.calibration.calibration_curve | (sklearn >=1.3.0, already pinned) | Returns `prob_true`, `prob_pred` arrays for reliability diagram | Always — do not recompute calibration in JS |
| sklearn.metrics.roc_curve | (sklearn >=1.3.0, already pinned) | Returns `fpr`, `tpr`, `thresholds` arrays | Always — used for ROC chart data |
| sklearn.metrics.roc_auc_score | (sklearn >=1.3.0, already pinned) | Scalar AUC for headline KPI | Always — single number, display as badge |
| sklearn.metrics.precision_recall_curve | (sklearn >=1.3.0, already pinned) | Returns `precision`, `recall`, `thresholds` arrays | Always — used for PR chart data |
| sklearn.metrics.average_precision_score | (sklearn >=1.3.0, already pinned) | Scalar AP (area under PR curve) | Always — single number, display as badge |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| npx shadcn@latest add chart | Generates `components/ui/chart.tsx` in the frontend | Run once; copies ChartContainer, ChartTooltip, ChartConfig type into the project — do not hand-write these |
| TypeScript strict mode (already enabled) | Catches recharts prop mismatches at build time | ChartConfig type from shadcn enforces label/color keys |

## Installation

```bash
# Frontend — recharts + shadcn chart wrapper
cd /Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop/frontend
npm install recharts@^3.8.1

# Generate the shadcn chart component (copies chart.tsx into components/ui/)
npx shadcn@latest add chart

# Python — no new dependencies needed
# sklearn.metrics and sklearn.calibration are already present via scikit-learn>=1.3.0
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| recharts 3.x | chart.js + react-chartjs-2 | When targeting Canvas rendering for 10K+ data points; not relevant here — ROC/calibration curves have at most a few hundred points |
| recharts 3.x | visx (Airbnb) | When building highly custom, bespoke visualizations requiring direct D3 control; adds significant complexity for a stats page with 4 standard chart types |
| recharts 3.x | nivo | When SSR is required for chart markup; nivo has ResizeObserver issues with Next.js App Router and needs `dynamic(() => import(...), { ssr: false })` anyway — no SSR advantage over recharts |
| sklearn (backend) | JS computation in the frontend | Never for this project — scores are in MariaDB, the FastAPI layer already joins `person_article_score` + `curations`, and sklearn functions produce exact results with zero additional JS dependencies |
| shadcn chart wrapper | Bare recharts ResponsiveContainer | Only if the project dropped shadcn/ui entirely; the wrapper wires Tailwind v4 CSS variable tokens automatically, removing manual color mapping |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| recharts 2.x | Project already uses shadcn/ui chart which now requires recharts v3; mixing versions causes peer dep conflicts | recharts ^3.8.1 |
| roc-chart (npm package) | Last published 9 years ago, abandoned | recharts ComposedChart with ReferenceLine |
| Plotly.js / react-plotly.js | 3MB+ bundle, heavyweight for 4 charts; LGPL license complications | recharts (SVG, ~150KB gzipped) |
| D3 directly | 40+ hours of custom rendering work for no user-visible benefit over recharts | recharts wraps D3 already |
| Computing AUC/calibration in the Next.js layer | Requires shipping numeric arrays from DB to browser, then running approximations; sklearn's exact implementations are already on the server | FastAPI `/stats` endpoint returning pre-computed JSON |

## Stack Patterns by Variant

**For all four chart types (ROC, calibration, PR curve, histogram):**
- Mark each chart component file with `'use client'` at the top — recharts uses browser APIs and cannot render in React Server Components
- Wrap each chart in `ChartContainer` from `components/ui/chart.tsx` with an explicit `h-*` or `aspect-*` Tailwind class — `ResponsiveContainer` requires a measured DOM node
- Use `dynamic(() => import('./MyChart'), { ssr: false })` only if a chart is below the fold and bundle splitting is a concern; for a dedicated stats page this is optional

**For the ROC curve:**
- Use `ComposedChart` with a `Line` series for the model curve and a `ReferenceLine` with `segment` prop for the diagonal (random classifier baseline)
- Add two additional `ReferenceLine` annotations for WCM (AUC 0.9993) and Fred Hutch (AUC 0.9993) horizontal markers

**For the calibration plot (reliability diagram):**
- Use `ComposedChart` with a `Line` for the model's `prob_pred` vs `prob_true` points and a `ReferenceLine y={x}` diagonal for perfect calibration
- The API returns the `calibration_curve` arrays directly; no client-side computation

**For the score distribution histogram:**
- Use `BarChart` with two stacked or side-by-side `Bar` series — one for ACCEPTED articles, one for REJECTED articles, bucketed into score bins
- Binning (e.g., 5-point buckets: 0–4, 5–9, …) is done in the FastAPI endpoint before returning JSON; the frontend renders pre-bucketed data

**For the precision-recall curve:**
- Use `ComposedChart` with a `Line` series for the model PR curve and a `ReferenceLine` for the random classifier baseline (horizontal at class prevalence rate)
- Average Precision scalar returned alongside the curve data

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| recharts ^3.8.1 | react ^18, react-dom ^18 | Project uses React 18; confirmed peer dep |
| recharts ^3.8.1 | next 14.2.35 | Requires `'use client'` directive on chart files; dynamic import with `ssr: false` as an option but not required |
| recharts ^3.8.1 | tailwindcss ^4.2.2 | Recharts SVG elements accept inline `fill`/`stroke` props; Tailwind classes can be applied to wrapper divs and SVG text via `className` on Axis/Legend; CSS variables from shadcn chart config resolve via Tailwind v4 |
| shadcn chart (recharts v3 version) | shadcn ^4.1.2 | shadcn chart component updated to recharts v3 in early 2025; `npx shadcn@latest add chart` installs the v3-compatible version |
| scikit-learn >=1.3.0 | sklearn.calibration.calibration_curve | `calibration_curve` has been stable since 0.22; `n_bins` and `strategy` params available since 1.0 |

## Sources

- [Recharts GitHub releases — v3.8.1 confirmed latest stable](https://github.com/recharts/recharts/releases) — HIGH confidence
- [Recharts 3.0 migration guide](https://github.com/recharts/recharts/wiki/3.0-migration-guide) — HIGH confidence
- [shadcn/ui chart documentation — recharts v3 integration](https://ui.shadcn.com/docs/components/chart) — HIGH confidence
- [sklearn.calibration.calibration_curve — scikit-learn 1.8.0](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.calibration_curve.html) — HIGH confidence
- [sklearn.metrics.roc_curve — scikit-learn 1.8.0](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_curve.html) — HIGH confidence
- [sklearn.metrics.precision_recall_curve — scikit-learn 1.8.0](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_curve.html) — HIGH confidence
- [LogRocket: Best React chart libraries 2025](https://blog.logrocket.com/best-react-chart-libraries-2025/) — MEDIUM confidence (editorial, secondary source)
- [Nivo SSR issues with Next.js 13+](https://github.com/plouc/nivo/issues/2626) — HIGH confidence (confirms recharts as better fit for this App Router project)

---
*Stack research for: ReCiter Desktop v1.1 — Statistics & Validation View*
*Researched: 2026-04-04*
