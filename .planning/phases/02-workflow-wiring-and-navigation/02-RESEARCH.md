# Phase 2: Workflow Wiring and Navigation — Research

**Researched:** 2026-04-04
**Domain:** Next.js App Router navigation, FastAPI endpoint extension, React context pattern
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Extend `/api/pipeline/status` to return an `assertion_count` field (count of joined `person_article_score` + `curation` pairs). Single source of truth for the gate condition.

**D-02:** `WorkflowContext` in `frontend/lib/workflow.tsx` consumes `assertion_count` from the pipeline status response and exposes it as `assertionCount`. All three surfaces (sidebar, pipeline CTA, /stats gate) read from `WorkflowContext`. No per-surface API calls.

**D-03:** Add a "Statistics" item to the `workflowItems` array in `frontend/components/sidebar.tsx`. Locked condition: `assertionCount === 0` (or null). Locked items render as `<Link>` with `text-gray-500` styling and `—` icon — exactly the same pattern as all other locked items.

**D-04:** No `pointer-events-none` or click prevention. Gate enforcement happens at the `/stats` page via `PrerequisiteGate`, not at the sidebar.

**D-05:** Add "View Statistics" CTA inside the existing `{pipelineFinished && summary && (...)}` block in `frontend/app/pipeline/page.tsx`, alongside the existing "View Results" link.

**D-06:** CTA is conditionally rendered based on `assertionCount > 0` from `WorkflowContext`. The link is completely absent (not grayed out) when no assertions exist.

**D-07:** Create `frontend/app/stats/page.tsx` as a `"use client"` component. Pattern mirrors `frontend/app/results/page.tsx`: wrap content in `PrerequisiteGate` (gate condition: `assertionCount === 0`), call `apiFetch("/api/stats")` in `useEffect` for data, show a loading state while fetching.

**D-08:** For this phase, the stats page body (after the gate) is a placeholder — heading and "Charts coming in Phase 3" note. No data fetch in Phase 2. Phase 3 replaces the placeholder.

### Claude's Discretion

- Exact prerequisite message text shown in the locked sidebar tooltip and the gate page
- Loading skeleton or spinner design for the /stats page data fetch
- Whether the pipeline CTA opens in the same tab or a new tab

### Deferred Ideas (OUT OF SCOPE)

- Tooltip on locked sidebar item (hovering shows prerequisite message inline) — NAV-01 is satisfied by the gate page; sidebar tooltip is additive, can go in Phase 3 if desired.
- Stats page data fetching and chart rendering — Phase 3 scope.
- Per-researcher stats link from the stats page — out of scope per PROJECT.md.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NAV-01 | Stats page is gated: sidebar item locked with prerequisite message when no joined (score, assertion) pairs exist; unlocked otherwise | `assertionCount` from WorkflowContext drives status; PrerequisiteGate renders gate page; sidebar uses same locked pattern as all other items |
| NAV-02 | Pipeline completion summary shows "View Statistics" CTA link when assertions exist in DB | `assertionCount` available in WorkflowContext after `refresh()` is called in `finished` handler; conditional render in existing `{pipelineFinished && summary && (...)}` block |
| NAV-03 | Stats page accessible at /stats route with "Statistics" label in sidebar nav | New file `frontend/app/stats/page.tsx`; one `workflowItems` entry in sidebar.tsx |
</phase_requirements>

---

## Summary

This phase wires three surfaces — the sidebar, the pipeline completion CTA, and the `/stats` route — to a single gate condition: whether at least one joined (score, assertion) pair exists in the database. The backend work is a small extension to an existing endpoint. The frontend work follows established patterns that are already in the codebase.

The primary complexity is a gap between what CONTEXT.md describes and what the current `pipeline/page.tsx` actually does: the CONTEXT states `refreshWorkflow()` is called in the `finished` event handler, but inspection of the file shows this is NOT yet wired. The `finished` handler calls `apiFetch("/api/pipeline/status")` directly to populate `summary`, but never calls `refresh` from `useWorkflow()`. The plan must include wiring this call so that `assertionCount` in `WorkflowContext` is current when the CTA renders.

All other patterns are in place and well-understood. The sidebar `StepStatus` type, `workflowItems` array, `statusIcon`/`statusColor` maps, `PrerequisiteGate` component, and `apiFetch` utility all exist and are ready for reuse without modification.

**Primary recommendation:** Implement in dependency order — backend (`assertion_count` field) → WorkflowContext extension → sidebar entry → pipeline `refresh()` wiring → pipeline CTA → stats page route.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js (App Router) | 14.2.35 (package.json) | File-based routing, `"use client"` components | Already in use for all pages |
| React | 18 (devDeps @types/react ^18) | Component model, hooks (useState, useEffect, useContext) | Project standard |
| FastAPI | Current in requirements.txt | Python REST API, SQLAlchemy dependency injection | Already in use for all API routes |
| SQLAlchemy | Current in requirements.txt | ORM, JOIN queries | Already in use in pipeline.py status endpoint |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shadcn Button, Card, CardContent | Already installed (components.json) | UI primitives for gate page and CTA | All new UI in this phase |
| lucide-react | Already installed | Icons (not needed for Phase 2 — status icons are Unicode strings) | Phase 3+ charts |
| `next/link` | Built-in | Client-side navigation | All `<Link>` elements in sidebar and CTA |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Extending `/api/pipeline/status` (D-01) | New `/api/stats/count` endpoint | D-01 is locked; single endpoint keeps WorkflowContext load() a single Promise.all call |
| WorkflowContext (D-02) | Per-surface fetch in sidebar/pipeline/stats | D-02 is locked; context avoids N separate API calls |

**Installation:** No new packages required for this phase.

---

## Architecture Patterns

### Recommended Project Structure

No new directories. One new file:

```
frontend/app/
├── stats/
│   └── page.tsx          # NEW — "use client", PrerequisiteGate, placeholder body
frontend/components/
├── sidebar.tsx           # MODIFIED — add Statistics to workflowItems
├── (prerequisite-gate.tsx — unchanged)
frontend/lib/
├── workflow.tsx          # MODIFIED — add assertionCount to interface + state
api/routers/
├── pipeline.py           # MODIFIED — add assertion_count to /status response
```

### Pattern 1: WorkflowContext Extension

**What:** Add `assertionCount: number` to the `WorkflowState` interface, the default context value, the state object shape, and map it from the API response field `assertion_count`.

**When to use:** Any new global gate condition driven by a count that comes from `/api/pipeline/status`.

**Exact extension points in `workflow.tsx`:**

```typescript
// 1. Interface — add to WorkflowState
assertionCount: number;

// 2. Default context value
assertionCount: 0,

// 3. State initial value (Omit<WorkflowState, "loading" | "refresh"> shape)
assertionCount: 0,

// 4. apiFetch type annotation for /api/pipeline/status
apiFetch<{
  total_researchers: number;
  total_articles: number;
  total_scores: number;
  scored_researchers: number;
  assertion_count: number;          // NEW
}>("/api/pipeline/status"),

// 5. setState mapping
assertionCount: status.assertion_count,
```

### Pattern 2: Sidebar workflowItems Entry

**What:** Add one object to the `workflowItems` array. The sidebar already destructures `scoreCount` from `useWorkflow()`; extend the destructure to include `assertionCount`, derive `hasAssertions`, and add the entry.

**When to use:** Any new workflow step in the sidebar.

**Exact extension in `sidebar.tsx`:**

```typescript
// Destructure (line 12 currently)
const { institution, researcherCount, scoreCount, assertionCount } = useWorkflow();

// Derived boolean
const hasAssertions = assertionCount > 0;

// New workflowItems entry — append after the "Results" entry
{
  href: "/stats",
  label: "Statistics",
  status: hasAssertions ? "next" : "locked",
},
```

The `StepStatus` type already includes `"next"` and `"locked"`. The `statusIcon` and `statusColor` maps already handle both values. No changes needed to the render loop or icon/color maps.

Note: `"complete"` is not used for Statistics because the stats page is a view, not a pipeline step to complete. `"next"` is the correct unlocked state (same visual treatment: orange dot).

### Pattern 3: PrerequisiteGate on /stats

**What:** The `PrerequisiteGate` component accepts `met: boolean`, `message`, `actionLabel`, `actionHref`, and `children`. When `met` is false it renders the amber gate card; when true it renders children.

**When to use:** Every gated page in this project.

**Exact usage for `stats/page.tsx`:**

```typescript
"use client";

import { useWorkflow } from "@/lib/workflow";
import { PrerequisiteGate } from "@/components/prerequisite-gate";
import { Card, CardContent } from "@/components/ui/card";

export default function StatsPage() {
  const { assertionCount } = useWorkflow();

  return (
    <PrerequisiteGate
      met={assertionCount > 0}
      message="Statistics require scored articles with accepted or rejected decisions. Run the pipeline and import assertions first."
      actionLabel="Go to Pipeline"
      actionHref="/pipeline"
    >
      <div className="max-w-4xl">
        <h2 className="text-2xl font-semibold mb-2 text-gray-900">Statistics</h2>
        <p className="text-gray-500 text-sm mb-6">
          Scoring quality metrics for your pipeline run.
        </p>
        <Card className="border-gray-200 bg-white shadow-sm">
          <CardContent className="p-5 text-center">
            <p className="text-sm text-gray-500 py-8">
              Charts are coming in Phase 3. Your stats data is ready.
            </p>
          </CardContent>
        </Card>
      </div>
    </PrerequisiteGate>
  );
}
```

Source: Copy text from `02-UI-SPEC.md` Copywriting Contract section. Structure mirrors `results/page.tsx`.

### Pattern 4: Pipeline CTA Wiring

**What:** The `finished` event handler must call `refresh()` from `useWorkflow()` so that `assertionCount` in WorkflowContext reflects the current DB state before the CTA renders.

**Gap identified:** Currently `pipeline/page.tsx` only destructures `researcherCount` from `useWorkflow()`. The `finished` handler calls `apiFetch("/api/pipeline/status")` directly but does NOT call `refresh()`. This means `WorkflowContext.assertionCount` remains 0 even after pipeline completes with assertions.

**Fix required (two parts):**

```typescript
// Part 1: extend destructure at top of PipelinePage
const { researcherCount, assertionCount, refresh } = useWorkflow();

// Part 2: call refresh() in the finished handler
} else if (event.type === "finished") {
  setRunning(false);
  setPipelineFinished(true);
  refresh();   // ADD THIS — updates assertionCount in WorkflowContext
  apiFetch<{ high_confidence: number; review_band: number; unlikely: number; }>(
    "/api/pipeline/status"
  ).then(setSummary).catch(() => {});
  apiFetch<typeof orcidReport>("/api/scores/orcid-report")
    .then((d) => { if (d && d.total_with_orcid > 0) setOrcidReport(d); })
    .catch(() => {});
}
```

**CTA conditional block** — add inside the existing "Next steps" `<div className="flex gap-3">` after the "View Results" button:

```typescript
{assertionCount > 0 && (
  <Link href="/stats">
    <Button className="bg-[#cf4520] hover:bg-[#a3381a] text-white">
      View Statistics
    </Button>
  </Link>
)}
```

Source: `02-UI-SPEC.md` Surface Specification §2. Same-tab navigation matches all other internal nav in the app.

### Pattern 5: Backend assertion_count JOIN

**What:** Add one COUNT query to the `/api/pipeline/status` endpoint in `api/routers/pipeline.py`. The count is the number of (person_id, pmid) pairs that exist in BOTH `PersonArticleScore` and `Curation`.

**SQLAlchemy pattern** (consistent with existing queries in the same function):

```python
from api.models import PersonArticleScore, Curation

assertion_count = (
    db.query(PersonArticleScore.person_id, PersonArticleScore.pmid)
    .join(
        Curation,
        (PersonArticleScore.person_id == Curation.person_id) &
        (PersonArticleScore.pmid == Curation.pmid)
    )
    .count()
)
```

Add `"assertion_count": assertion_count` to the return dict. This query is safe even when either table is empty (COUNT returns 0).

**Note on model_type composite PK:** `PersonArticleScore` has a composite primary key of (person_id, pmid, model_type). The JOIN on (person_id, pmid) may return duplicate pairs when both model types exist for a record. Use `.distinct()` if that scenario is possible:

```python
assertion_count = (
    db.query(PersonArticleScore.person_id, PersonArticleScore.pmid)
    .join(
        Curation,
        (PersonArticleScore.person_id == Curation.person_id) &
        (PersonArticleScore.pmid == Curation.pmid)
    )
    .distinct()
    .count()
)
```

Source: `api/models.py` — PersonArticleScore PK is (person_id, pmid, model_type), Curation PK is (person_id, pmid).

### Anti-Patterns to Avoid

- **Per-surface API calls:** Do not add separate `apiFetch("/api/pipeline/status")` calls in sidebar.tsx, stats/page.tsx, or the pipeline CTA. All three must read from WorkflowContext (D-02 locked).
- **pointer-events-none on locked sidebar link:** D-04 explicitly forbids this. The gate is on the /stats page, not the sidebar.
- **New shadcn installs:** UI-SPEC confirms all needed components (Button, Card, CardContent, PrerequisiteGate) are already installed.
- **Loading state in Phase 2 stats page:** D-08 specifies placeholder only — no data fetch, no spinner, in Phase 2.
- **`"complete"` status for Statistics sidebar item:** Statistics is a view, not a pipeline step. Use `"next"` for unlocked state.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gate UI rendering | Custom conditional div | `PrerequisiteGate` component | Already handles amber card, amber button, message, action — 0 lines of new gate UI code needed |
| Global state for gate condition | Per-component useState + useEffect | `WorkflowContext` / `useWorkflow()` | Context is already fetched on mount and on refresh; no additional fetch needed |
| JOIN count query | Raw SQL string | SQLAlchemy ORM query with `.join()` | Consistent with all other DB queries in the codebase; safe across DB environments |

---

## Common Pitfalls

### Pitfall 1: assertionCount stays 0 after pipeline finishes

**What goes wrong:** CTA never renders because `WorkflowContext.assertionCount` is still 0, even though the DB has assertions.

**Why it happens:** `pipeline/page.tsx` calls `apiFetch("/api/pipeline/status")` directly in the `finished` handler to populate `summary`, but this does NOT update WorkflowContext. The context was loaded on page mount and is stale.

**How to avoid:** Call `refresh()` (from `useWorkflow()`) in the `finished` handler, in addition to the existing `apiFetch` call. The `apiFetch` call is still needed for `summary` (for the tier cards), but `refresh()` updates the shared context including `assertionCount`.

**Warning signs:** CTA never appears even when assertions are in the DB; `/stats` page always shows the gate.

### Pitfall 2: Double-counting in assertion_count JOIN

**What goes wrong:** `assertion_count` is inflated because `PersonArticleScore` has a composite PK including `model_type` (identityOnly / feedbackIdentity), so one (person_id, pmid) pair can have two score rows.

**Why it happens:** JOIN on (person_id, pmid) hits both model_type rows for the same article when both models ran.

**How to avoid:** Add `.distinct()` to the SQLAlchemy JOIN query before `.count()`. This collapses multi-model rows to one per unique (person_id, pmid) pair.

**Warning signs:** `assertion_count` is roughly 2x the number of curated articles.

### Pitfall 3: WorkflowContext interface/state shape drift

**What goes wrong:** TypeScript compile error — `assertionCount` is in the interface but not in the state object shape (or vice versa), or the initial context default is missing it.

**Why it happens:** `WorkflowState` interface, the `createContext` default value, and the `useState` initial value are three separate declarations that must all be updated in sync.

**How to avoid:** Update all three locations in `workflow.tsx`: (1) `WorkflowState` interface, (2) `createContext<WorkflowState>(...)` default object, (3) `useState<Omit<WorkflowState, "loading" | "refresh">>` initial object.

### Pitfall 4: Sidebar StepStatus type rejection

**What goes wrong:** TypeScript error if the `status` value used for Statistics is not in the `StepStatus` union.

**Why it happens:** `StepStatus = "complete" | "next" | "locked" | "none"` — all four values are valid. The correct unlocked value is `"next"`, not a new value.

**How to avoid:** Use `"next"` for the unlocked state of Statistics. Do not add a new `"active"` or `"view"` status value.

---

## Code Examples

Verified patterns from the existing codebase:

### Existing PrerequisiteGate usage (results/page.tsx)

```typescript
// Source: frontend/app/results/page.tsx lines 29-35
<PrerequisiteGate
  met={scoreCount > 0}
  message="No results yet. Run the pipeline first to score articles."
  actionLabel="Go to Pipeline"
  actionHref="/pipeline"
>
```

### Existing workflowItems entry shape (sidebar.tsx)

```typescript
// Source: frontend/components/sidebar.tsx lines 52-55
{
  href: "/results",
  label: "Results",
  status: hasScores ? "complete" : "locked",
},
```

### Existing WorkflowState interface extension points (workflow.tsx)

```typescript
// Source: frontend/lib/workflow.tsx lines 6-14
interface WorkflowState {
  institution: string | null;
  researcherCount: number;
  articleCount: number;
  scoreCount: number;
  scoredResearchers: number;
  loading: boolean;
  refresh: () => void;
}
// Add: assertionCount: number;
```

### Existing pipeline status endpoint structure (pipeline.py)

```python
# Source: api/routers/pipeline.py lines 37-68
@router.get("/status")
def status(db: Session = Depends(get_db)):
    from sqlalchemy import func
    from api.models import PersonArticle, PersonArticleScore
    # ... existing counts ...
    return {
        "total_researchers": total_researchers,
        # ... existing fields ...
    }
    # Add: "assertion_count": assertion_count
```

---

## Runtime State Inventory

Not applicable — this is a greenfield navigation phase. No renames, refactors, or data migrations are involved. No stored data needs to change; the `assertion_count` field is a new computed value derived from existing rows.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Next.js dev server | Frontend development | Assumed (existing repo) | 14.2.35 | — |
| Python venv | Backend development | Confirmed | pytest 9.0.2 found in venv | — |
| pytest | Backend unit tests | Confirmed (venv) | 9.0.2 | — |
| SQLite | DB (local ~/.reciter-desktop/) | Confirmed (existing app) | System | — |

No missing blocking dependencies.

---

## Validation Architecture

`workflow.nyquist_validation` is not set to `false` in `.planning/config.json` (only `_auto_chain_active` is set). Validation section applies.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none — pytest auto-discovers `tests/` |
| Quick run command | `cd /Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop && venv/bin/pytest tests/test_pipeline_status.py -x` |
| Full suite command | `cd /Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop && venv/bin/pytest tests/ -x` |

No frontend test framework is installed (no jest/vitest in package.json devDependencies, no `__tests__` directory). Frontend behavior is verified manually or via Playwright.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NAV-01 (backend) | `assertion_count` in `/api/pipeline/status` response is 0 when no curation rows exist | unit | `venv/bin/pytest tests/test_pipeline_status.py::test_assertion_count_no_curations -x` | Wave 0 |
| NAV-01 (backend) | `assertion_count` equals count of distinct (person_id, pmid) pairs in both tables | unit | `venv/bin/pytest tests/test_pipeline_status.py::test_assertion_count_with_curations -x` | Wave 0 |
| NAV-02 | "View Statistics" button present in DOM when assertionCount > 0 | manual (Playwright) | Playwright snapshot after pipeline run | N/A |
| NAV-03 | `/stats` route returns 200, gate shows when no assertions, content shows when assertions present | manual (Playwright) | Playwright navigate + snapshot | N/A |

### Sampling Rate

- **Per task commit:** `venv/bin/pytest tests/test_pipeline_status.py -x`
- **Per wave merge:** `venv/bin/pytest tests/ -x`
- **Phase gate:** Full backend suite green + manual Playwright verification of all three surfaces before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_pipeline_status.py` — covers `assertion_count` field in /api/pipeline/status response; two cases: no curations (returns 0), with curations (returns correct distinct count)

---

## Open Questions

1. **Does `assertion_count` need to count distinct (person_id, pmid) pairs or total rows?**
   - What we know: `PersonArticleScore` has (person_id, pmid, model_type) as composite PK; a single article can have both identityOnly and feedbackIdentity scores. `Curation` has (person_id, pmid) as PK so at most one row per pair.
   - What's unclear: Whether stats use cases want "number of curated articles with a score" vs. "number of score records with a curation". For gate purposes (is the count > 0?), both are equivalent. For display purposes, distinct count is more meaningful.
   - Recommendation: Use `.distinct()` on (person_id, pmid) before `.count()` to return the count of curated articles, matching user mental model.

2. **Is `WorkflowContext.refresh` safe to call multiple times rapidly?**
   - What we know: `refresh` calls `load()` which does `Promise.all([apiFetch("/api/institution"), apiFetch("/api/pipeline/status")])` and updates state. No debounce or guard exists.
   - What's unclear: Whether rapid re-renders could cause a stale closure issue in the `finished` handler.
   - Recommendation: The `finished` handler fires once at pipeline end; rapid-call risk is negligible. No debounce needed for Phase 2.

---

## Sources

### Primary (HIGH confidence)

Direct file inspection of the live codebase — all findings are from reading the actual source:

- `frontend/lib/workflow.tsx` — WorkflowState interface, load() function, context shape
- `frontend/components/sidebar.tsx` — workflowItems array, StepStatus type, statusIcon/statusColor maps, render loop
- `frontend/app/pipeline/page.tsx` — finished handler, existing CTA location, summary state
- `frontend/app/results/page.tsx` — PrerequisiteGate usage pattern
- `frontend/components/prerequisite-gate.tsx` — component props interface, amber card rendering
- `api/routers/pipeline.py` — /api/pipeline/status endpoint, existing COUNT queries
- `api/models.py` — PersonArticleScore and Curation model definitions, composite PKs
- `api/routers/stats.py` — existing /api/stats endpoint (thin delegation)
- `frontend/app/layout.tsx` — Providers wrapper confirms WorkflowContext is app-wide
- `frontend/components/providers.tsx` — WorkflowProvider is the only provider
- `.planning/phases/02-workflow-wiring-and-navigation/02-CONTEXT.md` — locked decisions
- `.planning/phases/02-workflow-wiring-and-navigation/02-UI-SPEC.md` — approved visual contract
- `frontend/package.json` — Next.js 14.2.35, no test framework installed
- `.planning/config.json` — nyquist_validation not explicitly disabled

### Secondary (MEDIUM confidence)

- None required — all findings are sourced directly from the codebase.

---

## Metadata

**Confidence breakdown:**
- Backend change: HIGH — endpoint structure is known, SQLAlchemy JOIN pattern is standard, models are fully documented
- WorkflowContext extension: HIGH — interface and state shape are small, well-typed, pattern is established
- Sidebar entry: HIGH — `workflowItems` array and render logic are fully understood; StepStatus values are enumerated
- Pipeline CTA + refresh() gap: HIGH — gap confirmed by line-by-line inspection; fix is minimal and mechanical
- /stats page: HIGH — PrerequisiteGate pattern is established; placeholder body is trivial
- Frontend test gap: HIGH — no jest/vitest installed; backend pytest is confirmed in venv

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable patterns; no fast-moving dependencies)
