# Phase 2: Workflow Wiring and Navigation - Context

**Gathered:** 2026-04-04 (assumptions mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the stats page reachable from the sidebar and from pipeline completion, locked behind the correct gate condition. No charts or stats data rendering in this phase — that is Phase 3. This phase is pure wiring: add the sidebar entry, add the pipeline CTA, create the /stats route with its gate page, and wire the gate condition through WorkflowContext.

</domain>

<decisions>
## Implementation Decisions

### Gate Data Source
- **D-01:** Extend `/api/pipeline/status` to return an `assertion_count` field (count of joined `person_article_score` + `curation` pairs). This is the single source of truth for the gate condition.
- **D-02:** `WorkflowContext` in `frontend/lib/workflow.tsx` consumes `assertion_count` from the pipeline status response and exposes it as `assertionCount`. All three surfaces (sidebar, pipeline CTA, /stats gate) read from `WorkflowContext` — consistent with how `scoreCount` and `researcherCount` are used throughout. No per-surface API calls.

### Sidebar Entry
- **D-03:** Add a "Statistics" item to the `workflowItems` array in `frontend/components/sidebar.tsx`. Locked condition: `assertionCount === 0` (or null). Locked items render as `<Link>` with `text-gray-500` styling and `—` icon — exactly the same pattern as all other locked items.
- **D-04:** No `pointer-events-none` or click prevention. Gate enforcement happens at the `/stats` page via `PrerequisiteGate`, not at the sidebar. This ensures NAV-03 works for direct URL navigation.

### Pipeline Completion CTA
- **D-05:** Add "View Statistics" CTA inside the existing `{pipelineFinished && summary && (...)}` block in `frontend/app/pipeline/page.tsx`, alongside the existing "View Results" link.
- **D-06:** The CTA is conditionally rendered based on `assertionCount > 0` from `WorkflowContext`. No separate fetch needed — `WorkflowContext` is already re-fetched after pipeline completion (the `finished` event handler calls `refreshWorkflow()`). The link is completely absent (not grayed out) when no assertions exist.

### /stats Route Structure
- **D-07:** Create `frontend/app/stats/page.tsx` as a `"use client"` component. Pattern mirrors `frontend/app/results/page.tsx`: wrap content in `PrerequisiteGate` (gate condition: `assertionCount === 0`), call `apiFetch("/api/stats")` in `useEffect` for data, show a loading state while fetching.
- **D-08:** For this phase, the stats page body (after the gate) is a placeholder — just a heading and a "Charts coming in Phase 3" note. Phase 3 will replace the placeholder with actual charts.

### Claude's Discretion
- Exact prerequisite message text shown in the locked sidebar tooltip and the gate page
- Loading skeleton or spinner design for the /stats page data fetch
- Whether the pipeline CTA opens in the same tab or a new tab

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §NAV-01, NAV-02, NAV-03 — exact definitions of gate, sidebar, and CTA conditions

### Frontend Patterns
- `frontend/lib/workflow.tsx` — WorkflowContext definition, `/api/pipeline/status` fetch, exposed fields (researcherCount, scoreCount, etc.) — extend this for assertionCount
- `frontend/components/sidebar.tsx` — `workflowItems` array, locked-item pattern (text-gray-500, — icon, <Link>)
- `frontend/app/pipeline/page.tsx` — pipeline completion block, finished event handler, existing "View Results" CTA location
- `frontend/app/results/page.tsx` — PrerequisiteGate usage pattern, "use client" page structure

### Backend
- `api/routers/pipeline.py` — `/api/pipeline/status` endpoint to extend with assertion_count
- `api/models.py` — PersonArticleScore and Curation models (for the JOIN query)
- `api/routers/stats.py` — `/api/stats` endpoint (Phase 1 output — for reference, not modified in Phase 2)

### Roadmap
- `.planning/ROADMAP.md` §Phase 2 — Goal, success criteria, NAV-01/02/03 references

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PrerequisiteGate` component: already used in `results/page.tsx` — reuse directly with a new `condition` and `message` prop
- `WorkflowContext` (`useWorkflow()` hook): already provides `researcherCount`, `scoreCount` to all pages — extend with `assertionCount`
- `apiFetch` utility: used by all pages for API calls — use for any additional fetches in stats page
- `sidebar.tsx` `workflowItems` array: add one object following the exact shape of existing items

### Established Patterns
- All pages: `"use client"` directive, `useWorkflow()` for gate state, `useEffect` + `apiFetch` for data
- `workflowItems` entries: `{ label, href, icon, locked: boolean, prerequisiteMessage: string }`
- Pipeline status response is already re-fetched after pipeline completion via `refreshWorkflow()` — no extra wiring needed for CTA to see updated assertionCount

### Integration Points
- `/api/pipeline/status` (FastAPI): add one COUNT query joining `PersonArticleScore` + `Curation` on (person_id, pmid)
- `WorkflowContext`: add `assertionCount: number` to the interface and map it from the status response
- Sidebar: one new entry in `workflowItems`
- Pipeline page: one conditional block in the completion section
- New file: `frontend/app/stats/page.tsx`

</code_context>

<specifics>
## Specific Ideas

- No specific visual references given — use existing locked/gate patterns exactly as they appear in other pages.

</specifics>

<deferred>
## Deferred Ideas

- Tooltip on locked sidebar item (hovering shows prerequisite message inline) — NAV-01 is satisfied by the gate page; sidebar tooltip is additive and can go in Phase 3 if desired.
- Stats page data fetching and chart rendering — Phase 3 scope.
- Per-researcher stats link from the stats page — out of scope per PROJECT.md.

</deferred>

---

*Phase: 02-workflow-wiring-and-navigation*
*Context gathered: 2026-04-04*
