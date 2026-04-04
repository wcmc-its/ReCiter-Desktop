# Architecture Research

**Domain:** Statistics & Validation page — FastAPI + Next.js 14 App Router
**Researched:** 2026-04-04
**Confidence:** HIGH (based on direct codebase inspection, no speculation)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────┐
│  Next.js 14 App Router (port 3002)   "use client" pages      │
│                                                               │
│  /pipeline page  ──── SSE ────→  POST /api/pipeline/run      │
│       │                                                       │
│       └── pipelineFinished=true                              │
│               │                                               │
│       "View Statistics" link  ─────→  /stats page (NEW)      │
│                                           │                   │
│                              apiFetch("/api/stats")  ──────── │
├───────────────────────────────────────────────────────────────┤
│  FastAPI (port 8090)                                          │
│                                                               │
│  GET /api/stats  (NEW router: api/routers/stats.py)          │
│       │                                                       │
│       └── JOIN person_article_score + curation                │
│               │                                               │
│       sklearn.metrics: roc_curve, auc, precision_recall_curve │
│       numpy: histogram bins                                   │
│               │                                               │
│       → StatsResponse JSON (serialized, no numpy types)      │
├───────────────────────────────────────────────────────────────┤
│  MariaDB                                                      │
│  person_article_score (person_id, pmid, model_type,          │
│                        calibrated_score)                      │
│  curation            (person_id, pmid, assertion)            │
└──────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Status |
|-----------|----------------|--------|
| `api/routers/stats.py` | SQL join, metric computation via sklearn, JSON serialization | NEW |
| `frontend/app/stats/page.tsx` | Client component: fetch stats, render charts | NEW |
| `frontend/components/sidebar.tsx` | Add Stats nav item with curation gate | MODIFIED |
| `frontend/lib/workflow.tsx` | Add `curationCount` to WorkflowState | MODIFIED |
| `api/routers/researchers.py` | Likely already exposes curation count; verify | VERIFY |
| `api/routers/pipeline.py` | POST-pipeline "View Statistics" link injection | MODIFIED (UI only) |

---

## Computation Location Decision: Python Backend (sklearn)

**Recommendation: Compute everything in the FastAPI backend. Do not compute metrics in the browser.**

**Rationale:**

1. **sklearn is already a dependency.** `core/scoring.py` uses `IsotonicRegression` from sklearn and `StandardScaler`. The library is already in the container. Adding `roc_curve`, `auc`, `precision_recall_curve` requires zero new dependencies.

2. **Type safety on the hard part.** ROC/PR curves require careful handling of edge cases (all-same-label, threshold ordering, NaN guards). sklearn's implementations are battle-tested. Reimplementing in JavaScript adds bug surface with no gain.

3. **Data volume.** The joined dataset (scores + curations) can be thousands of rows. Sending raw rows to the browser for client-side computation wastes bandwidth. Returning ~50 precomputed curve points is negligible.

4. **No charting library does metric computation.** Recharts, Chart.js, and Nivo are rendering libraries, not analytics libraries. They expect `[{x, y}]` data, not raw score arrays.

5. **Consistent with existing pattern.** The pipeline summary cards (`high_confidence`, `review_band`, `unlikely`) are already computed in Python at `/api/pipeline/status`. Stats follow the same pattern.

---

## API Contract

### Endpoint

```
GET /api/stats
```

**Gate:** Returns `{"error": "no_curations"}` with HTTP 200 (not 404) if `COUNT(curation) = 0`. The frontend gate checks `curationCount > 0` before rendering the page at all, but defensive handling is good.

**Query parameter (optional):**
```
GET /api/stats?model_type=feedbackIdentity
```
Defaults to whichever model type is present. If both are present, prefer `feedbackIdentity` (the more powerful model). The response includes a `model_type` field so the frontend can display which model was used.

### Response Shape

```json
{
  "model_type": "feedbackIdentity",
  "n_scored": 4821,
  "n_curated": 1203,
  "n_accepted": 891,
  "n_rejected": 312,

  "auc_roc": 0.9993,
  "auc_pr": 0.9988,

  "roc_curve": [
    {"fpr": 0.0, "tpr": 0.0},
    {"fpr": 0.0, "tpr": 0.42},
    ...
    {"fpr": 1.0, "tpr": 1.0}
  ],

  "pr_curve": [
    {"recall": 0.0, "precision": 1.0},
    ...
    {"recall": 1.0, "precision": 0.47}
  ],

  "calibration_bins": [
    {"bin_center": 5,  "fraction_positive": 0.03, "count": 142},
    {"bin_center": 15, "fraction_positive": 0.14, "count": 88},
    ...
    {"bin_center": 95, "fraction_positive": 0.97, "count": 641}
  ],

  "score_distribution": [
    {"bin_start": 0,  "bin_end": 10,  "accepted": 12, "rejected": 98,  "unreviewed": 301},
    {"bin_start": 10, "bin_end": 20,  "accepted": 8,  "rejected": 41,  "unreviewed": 220},
    ...
    {"bin_start": 90, "bin_end": 100, "accepted": 644, "rejected": 3,  "unreviewed": 1823}
  ],

  "strongest_disagreements": [
    {
      "person_id": "jdoe",
      "pmid": "38471029",
      "score": 12,
      "assertion": "ACCEPTED",
      "title": "Myocardial infarction outcomes...",
      "first_name": "Jane",
      "last_name": "Doe"
    }
  ],

  "benchmarks": {
    "wcm_feedback_auc": 0.9993,
    "wcm_identity_auc": 0.9776,
    "fredh_feedback_auc": 0.9993
  }
}
```

**Notes on curve downsampling:** sklearn's `roc_curve` can return thousands of threshold points. Downsample to ~200 points in the backend using numpy stride slicing before serializing. This keeps the JSON payload under 20KB.

**Notes on calibration bins:** Use 10 equal-width bins over [0, 100] score range. `calibrated_score` in DB is stored as 0–1 float (see `scores.py` line 42 where it multiplies by 100 for display). Account for this: the backend should multiply by 100 before binning, or bin on the raw 0–1 float and label as percentages.

**Notes on numpy type serialization:** sklearn/numpy return `numpy.float64` which FastAPI cannot serialize. Wrap all float values with `float()` before returning. Same pattern is already used in `pipeline_runner.py` lines 229–232.

**Notes on strongest disagreements:** "Disagreement" = high score + REJECTED, or low score + ACCEPTED. Rank by `|score - assertion_threshold|`. Top 5 in the inline table; full list accessible via link to `/results?filter=disagreements` (or a simpler query param the results page can filter on).

### Benchmark Values (hardcoded, from PROJECT.md)

These are known from validation publications and do not need to be fetched:

```python
BENCHMARKS = {
    "wcm_feedback_auc": 0.9993,
    "wcm_identity_auc": 0.9776,
    "fredh_feedback_auc": 0.9993,
}
```

---

## Caching Strategy

**Recommendation: No server-side caching. Recompute on every request.**

**Rationale:**

- Stats are post-hoc (only called after pipeline completes). The user hits the stats page once or twice per pipeline run. Computation takes under 100ms for typical datasets (a few thousand joined rows). Caching adds complexity with no measurable benefit.
- If a second pipeline run adds new curations, cached data would be stale. Cache invalidation on the stats endpoint requires hooking pipeline completion, which is disproportionate complexity for a rarely-called endpoint.
- The pipeline completion page already calls `/api/pipeline/status` synchronously — stats can follow the same pattern.

**What to NOT cache:**

- Do not cache in the Next.js data layer (`fetch` with `cache: 'force-cache'`). Stats must reflect the current DB state.
- Do not store computed stats in a new DB table. MariaDB query + sklearn computation on join results is fast enough.

**What IS appropriate:**

- React `useState` on the stats page. Fetch once on mount, store in component state. No refetch on tab focus or interval. User can manually refresh by navigating away and back.

---

## Wiring into Post-Pipeline Flow

The pipeline completion UI already has a "Next steps" section (pipeline/page.tsx lines 544–553). The "View Statistics" link appears conditionally there when curations exist.

### Integration Points in Existing Code

**1. `frontend/app/pipeline/page.tsx` — completion summary (MODIFIED)**

Currently shows:
```tsx
<Link href="/results"><Button>View Results</Button></Link>
```

Add after that, conditionally:
```tsx
{hasCurations && (
  <Link href="/stats"><Button variant="outline">View Statistics</Button></Link>
)}
```

`hasCurations` is fetched from the API at the same time as `summary` (line 166–170). Add a parallel call to `/api/stats` or a lightweight `/api/curations/count` endpoint. Simpler: add `curation_count` to the existing `/api/pipeline/status` response.

**2. `frontend/lib/workflow.tsx` — WorkflowState (MODIFIED)**

Add `curationCount: number` to the state. Fetch from the same `/api/pipeline/status` endpoint (add `curation_count` field there) or from a dedicated `/api/curations/count`. This powers the sidebar gate.

**3. `frontend/components/sidebar.tsx` — nav item (MODIFIED)**

Add a "Statistics" item to `workflowItems`:
```tsx
{
  href: "/stats",
  label: "Statistics",
  status: hasCurations ? (hasScores ? "complete" : "locked") : "locked",
}
```

Gate: locked unless both `hasScores` and `hasCurations` are true.

**4. `/api/pipeline/status` router (MODIFIED)**

Add `curation_count` to the existing status response. One additional `db.query(Curation).count()` call. This is the least-friction way to propagate curation existence to the frontend without a new endpoint.

---

## Recommended File Structure (New + Modified)

```
api/
└── routers/
    └── stats.py              # NEW — GET /api/stats

frontend/
└── app/
    └── stats/
        └── page.tsx          # NEW — stats page component
```

**Modified files:**
- `api/routers/pipeline.py` — add `curation_count` to `/api/pipeline/status`
- `frontend/lib/workflow.tsx` — add `curationCount` to WorkflowState
- `frontend/components/sidebar.tsx` — add Statistics nav item
- `frontend/app/pipeline/page.tsx` — add "View Statistics" link in completion summary

---

## Charting Library Decision

**Recommendation: Recharts.**

No charting library is currently installed (confirmed from `package.json`). Recharts is the right choice for this stack because:

1. It is the standard React charting library for App Router projects. Composable, declarative, integrates naturally with `"use client"` components.
2. Required charts (`LineChart` for ROC/PR/calibration, `BarChart` for score distribution, `ResponsiveContainer`) are all first-class Recharts components.
3. Reference lines (for WCM/Fred Hutch benchmarks on ROC/PR charts) are a built-in `<ReferenceLine>` component.
4. Active community, maintained, compatible with React 18.

**Install:**
```bash
npm install recharts
```

Do not install `@types/recharts` — Recharts ships its own TypeScript types since v2.

**Alternatives considered and rejected:**

- `Chart.js` + `react-chartjs-2`: Imperative API requires refs and canvas manipulation; worse DX in RSC-adjacent code.
- `Nivo`: Excellent but large bundle, slower install, more opinionated styling that conflicts with Tailwind approach.
- `Visx` (Airbnb): Low-level D3 wrapper, significant boilerplate for charts this team doesn't need to customize deeply.

---

## Architectural Patterns

### Pattern 1: Thin Client, Fat Backend (Apply Here)

**What:** Backend does all data transformation, metric computation, and aggregation. Frontend receives ready-to-render data structures.
**When to use:** When backend already has the right libraries (sklearn), when computation involves domain logic (ROC curve edge cases), when data is large relative to computed output.
**Trade-offs:** Backend owns more logic; frontend is purely presentational. Harder to do client-side drill-downs, but stats page is aggregate-only.

### Pattern 2: PrerequisiteGate for Stats Access

**What:** Reuse the existing `PrerequisiteGate` component pattern on the stats page. Gate condition: `curationCount > 0 && scoreCount > 0`.
**When to use:** All pages in this app that depend on prior workflow steps already use this pattern.
**Trade-offs:** Consistent UX, no new component needed.

```tsx
<PrerequisiteGate
  met={curationCount > 0 && scoreCount > 0}
  message="Statistics require both scored articles and imported assertions."
  actionLabel="Go to Researchers"
  actionHref="/researchers"
>
  {/* stats content */}
</PrerequisiteGate>
```

### Pattern 3: Single Fetch on Mount, No Polling

**What:** `useEffect` + `apiFetch` once on component mount. Stats are static post-pipeline. No SSE, no polling, no React Query.
**When to use:** When data doesn't change while the user is on the page. The pipeline must be re-run to update stats; user navigates back to pipeline page to do that.
**Trade-offs:** Stale if user runs pipeline in another tab, but that's an acceptable edge case for a local desktop app.

```tsx
const [stats, setStats] = useState<StatsResponse | null>(null);
useEffect(() => {
  apiFetch<StatsResponse>("/api/stats").then(setStats).catch(() => {});
}, []);
```

---

## Data Flow

### Stats Request Flow

```
User clicks "View Statistics" on pipeline completion page
    ↓
Navigate to /stats (Next.js App Router)
    ↓
stats/page.tsx mounts, useEffect fires
    ↓
apiFetch("http://localhost:8090/api/stats")
    ↓
FastAPI GET /api/stats
    ↓
SQLAlchemy JOIN person_article_score + curation ON (person_id, pmid)
    (filter to most recent model_type per researcher)
    ↓
pandas DataFrame: columns [calibrated_score, assertion (0/1)]
    ↓
sklearn: roc_curve(), auc(), precision_recall_curve()
numpy: histogram()
pandas: groupby for disagreements
    ↓
Serialize to StatsResponse (all numpy.float64 → float())
    ↓
JSON response (~15KB)
    ↓
React state: setStats(data)
    ↓
Recharts renders ROC, PR, calibration, distribution charts
```

### Gate Check Flow

```
WorkflowProvider loads on app mount
    ↓
GET /api/pipeline/status → { ..., curation_count: 47 }
    ↓
WorkflowContext.curationCount = 47
    ↓
Sidebar: Statistics item → status "next" (not locked)
Pipeline completion: "View Statistics" button → visible
Stats page: PrerequisiteGate met=true → renders
```

---

## Anti-Patterns

### Anti-Pattern 1: Computing Metrics in JavaScript

**What people do:** Send raw score/assertion arrays to the browser, compute ROC curve in a custom JS function.
**Why it's wrong:** sklearn handles edge cases (single class, ties in scores, threshold ordering) that are non-obvious to reimplement correctly. AUC calculation via trapezoidal integration has numeric precision issues in floating point. The backend already has sklearn.
**Do this instead:** Compute in Python, send `[{fpr, tpr}]` arrays to the browser.

### Anti-Pattern 2: New `curation_count` Endpoint

**What people do:** Create `GET /api/curations/count` as a new endpoint just to check the gate.
**Why it's wrong:** The `WorkflowProvider` already calls `/api/pipeline/status` on every page load. Adding a second API call for a single integer wastes a round-trip and adds a new endpoint to maintain.
**Do this instead:** Add `curation_count` to the existing `/api/pipeline/status` response. One line: `db.query(Curation).count()`.

### Anti-Pattern 3: Caching Stats in a New DB Table

**What people do:** After pipeline completes, write computed stats to a `pipeline_stats` table and serve from there.
**Why it's wrong:** Adds a write step to the pipeline, requires cache invalidation logic, and the query + sklearn computation is fast enough (< 100ms) to not warrant it.
**Do this instead:** Compute on demand from the live join. If performance becomes an issue at >50K curations (unlikely for this tool's target users), revisit.

### Anti-Pattern 4: Strongest Disagreements as a Separate Endpoint

**What people do:** Create a second endpoint `GET /api/stats/disagreements` for the inline table and the "View all" link.
**Why it's wrong:** All disagreement data comes from the same join. Computing it in one pass alongside the other metrics is cheaper than two trips to the DB.
**Do this instead:** Include `strongest_disagreements` (top 5, with all fields needed for display) in the main `/api/stats` response. For "View all", pass a query param to the existing `/results` page: `/results?personId=&disagreements=true`.

### Anti-Pattern 5: Chart Components as Server Components

**What people do:** Mark the stats page or chart wrapper as a React Server Component to avoid `"use client"`.
**Why it's wrong:** Recharts requires browser APIs (ResizeObserver for ResponsiveContainer). All chart components must be inside a `"use client"` boundary. Every other page in this app is `"use client"` already; the stats page should follow the same pattern.
**Do this instead:** `"use client"` at the top of `stats/page.tsx`. No special wrapping needed.

---

## Integration Points

### Existing Code Touched

| File | Change Type | What Changes |
|------|-------------|--------------|
| `api/routers/pipeline.py` | Add field | `curation_count` added to `/api/pipeline/status` response body |
| `api/main.py` | Add router | `include_router(stats.router)` — 1 line |
| `frontend/lib/workflow.tsx` | Add field | `curationCount: number` in WorkflowState + fetch from status |
| `frontend/components/sidebar.tsx` | Add nav item | Statistics entry with curation gate |
| `frontend/app/pipeline/page.tsx` | Add CTA link | "View Statistics" button in pipelineFinished summary block |

### New Code Added

| File | What It Is |
|------|------------|
| `api/routers/stats.py` | FastAPI router with single GET endpoint, sklearn metric computation |
| `frontend/app/stats/page.tsx` | Client component: fetch + Recharts charts + disagreements table |

### External Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Next.js → FastAPI | `apiFetch()` via `NEXT_PUBLIC_API_URL` | Same pattern as all other pages |
| FastAPI → MariaDB | SQLAlchemy ORM JOIN query | Same `get_db` dependency injection |
| FastAPI → sklearn | Direct function call | No HTTP; same process |
| Sidebar → WorkflowContext | React Context (`useWorkflow()`) | `curationCount` added to existing context |

---

## Suggested Build Order

Dependencies flow strictly in this order. Each step unblocks the next.

1. **`api/routers/pipeline.py` — add `curation_count` to status response**
   Unblocks: WorkflowProvider change, sidebar gate, pipeline page CTA visibility.

2. **`api/routers/stats.py` — new stats endpoint**
   Unblocks: frontend stats page. Can be built and tested with `curl` independently.

3. **`frontend/lib/workflow.tsx` — add `curationCount`**
   Unblocks: sidebar gate condition, PrerequisiteGate on stats page.

4. **`frontend/components/sidebar.tsx` — add Statistics nav item**
   Unblocks: user navigation to stats page.

5. **`npm install recharts` in frontend/**
   Unblocks: chart rendering in stats page.

6. **`frontend/app/stats/page.tsx` — stats page**
   Final step. Depends on all of the above.

7. **`frontend/app/pipeline/page.tsx` — add "View Statistics" CTA**
   Independent of step 6, can be done alongside it. Cosmetic integration only.

---

## Sources

- Direct inspection: `api/models.py`, `api/routers/pipeline.py`, `api/routers/scores.py`, `api/services/pipeline_runner.py`
- Direct inspection: `frontend/app/pipeline/page.tsx`, `frontend/components/sidebar.tsx`, `frontend/lib/workflow.tsx`, `frontend/lib/api.ts`, `frontend/package.json`
- Direct inspection: `.planning/PROJECT.md`
- sklearn docs: `roc_curve`, `precision_recall_curve`, `auc` — HIGH confidence (standard API, unchanged for years)
- Recharts docs: https://recharts.org — MEDIUM confidence (verify install command and `ResponsiveContainer` API on current version)

---
*Architecture research for: ReCiter Desktop v1.1 Statistics & Validation page*
*Researched: 2026-04-04*
