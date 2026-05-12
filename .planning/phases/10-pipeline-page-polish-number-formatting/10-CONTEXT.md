# Phase 10: Pipeline Page Polish + Number Formatting - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the pipeline page heading/subtitle copy, ETA countdown bug, progress animation direction, status column font/alignment, and "Taking longer than usual" timing logic. Apply comma formatting to large numbers throughout the app. No new features — this is a polish and bug-fix phase only.

</domain>

<decisions>
## Implementation Decisions

### Heading and Subtitle Copy (PIPE-01)
- **D-01:** Change `<h2>` text from "Processing Pipeline" → "Retrieve & Score"
- **D-02:** Change subtitle paragraph from "Retrieve articles and compute authorship likelihood scores for each researcher." → "Retrieve articles and compute authorship likelihood scores for each researcher's candidate articles."

### ETA Countdown (PIPE-02)
- **D-03:** Snapshot-at-completion approach. Track `lastCompletionTime` as a ref. On each `complete_one` event, compute delta = `Date.now() - lastCompletionTime`, then update `avgTimePerResearcher` as a rolling average using that delta (not cumulative elapsed / total completed). Update `lastCompletionTime = Date.now()` after each completion.
- **D-04:** ETA display = `avgTimePerResearcher * (total - completed)`. This freezes between completions but never counts up. Only show ETA after at least one researcher completes (same gate as now).
- **D-05:** Initialize `lastCompletionTime` to `Date.now()` when the pipeline `started` event fires (when the first researcher begins, not when the button is clicked, to avoid inflating the first delta with queue-setup time).

### Progress Animation Direction (PIPE-03)
- **D-06:** Swap the `@keyframes pipeline-stripe` animation in `globals.css`:
  - Current (wrong): `from { background-position: 40px 0; } to { background-position: 0 0; }`
  - Fixed (left-to-right): `from { background-position: 0 0; } to { background-position: 40px 0; }`

### Status Column Font and Alignment (PIPE-04)
- **D-07:** The issue is multi-part: status label text is `text-sm` (14px), wider column proportions push elements out of alignment, and column font sizes are inconsistent. Fix:
  - Status column label text (`PHASE_LABELS[phase]`) → `text-xs` (matching UID and article count cells)
  - Spinner size stays `w-3.5 h-3.5` but ensure `items-center` alignment holds
  - "Taking longer than usual" badge stays `text-xs`
  - Review column header proportions against row content if cell widths appear imbalanced after font fix

### "Taking longer than usual" Timing (PIPE-05)
- **D-08:** The `isBottleneck` prop in `PipelineRow` is already conditionally computed in `pipeline/page.tsx` with `avgTimePerResearcher > 0` guard. The logic is structurally correct.
- **D-09:** Verify the bug: with the ETA fix (D-03), `avgTimePerResearcher` no longer grows continuously between completions. This may resolve the apparent PIPE-05 false-positive case (where `avgTimePerResearcher * 2` was effectively 0 or a tiny value due to cumulative elapsed drift, causing all researchers to be flagged as bottlenecks prematurely). No separate fix needed — PIPE-05 is likely a symptom of the ETA bug, not a separate bug.

### Number Comma Formatting (FMT-01)
- **D-10:** Use inline `.toLocaleString()` at each call site — no new utility function. Consistent with how stats page, completion summary, and dashboard already format numbers.
- **D-11:** Gaps to fix:
  - `frontend/app/pipeline/page.tsx` line ~348: `{totalArticles}` → `{totalArticles.toLocaleString()}`
  - `frontend/app/pipeline/page.tsx` line ~349: `{totalScored}` → `{totalScored.toLocaleString()}`
  - `frontend/components/pipeline-row.tsx` line ~138: `{articleCount ?? "—"}` → `{articleCount != null ? articleCount.toLocaleString() : "—"}`
- **D-12:** All other numeric displays across the app (dashboard, stats, articles page, setup page) already use `.toLocaleString()` — no changes needed there.

### Claude's Discretion
- Exact rolling average formula for ETA (simple moving average vs. exponential moving average — simple is fine)
- Whether to tweak `grid-cols` proportions in the column header/row if the font-size fix still leaves alignment off
- Whether PIPE-05 needs any additional conditional logic after verifying the ETA fix resolves it

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pipeline Page
- `frontend/app/pipeline/page.tsx` — heading, subtitle, ETA state logic (`avgTimePerResearcher`, `startTime`, `researcherStartTimes`), number formatting for progress bar text; SSE event handler `complete_one` is where ETA should be recalculated
- `frontend/components/pipeline-row.tsx` — status label text (`PHASE_LABELS`, `text-sm` class), `isBottleneck` rendering, `articleCount` display

### Animation CSS
- `frontend/app/globals.css` — `.pipeline-progress-animated` class and `@keyframes pipeline-stripe`

### Requirements
- `.planning/REQUIREMENTS.md` §v2.1 Pipeline Page — PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, FMT-01 define the acceptance criteria for each fix

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `formatDuration(ms)` in `pipeline/page.tsx` — already exists; used for elapsed and ETA display; no changes needed to the formatter itself
- `subscribeSSE()` in `lib/sse.ts` — SSE subscription utility; ETA logic sits inside the `complete_one` event handler, not in the SSE layer

### Established Patterns
- Numeric formatting: everywhere across the app uses `.toLocaleString()` directly at the render site (no utility wrapper). Pipeline row is the only outlier — bring it in line.
- State updates in SSE handlers: use functional setState (`setX(prev => ...)`) to avoid stale closure issues — this pattern is already used throughout `pipeline/page.tsx` and should be followed for the new `lastCompletionTime` ref.
- ETA state: `avgTimePerResearcher` is React state (number). `lastCompletionTime` should be a `useRef` (not state) since it doesn't drive rendering — consistent with how `personIdsRef` and `nextToStartRef` are handled.

### Integration Points
- ETA display at line ~360 in `pipeline/page.tsx`: `{completed > 0 && <span>Est. remaining: {formatDuration(avgTimePerResearcher * (total - completed))}</span>}` — this render expression stays the same; only the _computation_ of `avgTimePerResearcher` changes
- `bottleneckIds` set in `pipeline/page.tsx` depends on `avgTimePerResearcher` — verify after ETA fix that bottleneck detection still works correctly with the new avg formula
- No backend changes required for any of Phase 10

</code_context>

<specifics>
## Specific Ideas

- PIPE-04 user note: "wider columns and different font sizes" — suggests the column proportions may also need attention after the font size fix. Planner should include a step to visually verify grid alignment after shrinking status text to `text-xs`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 10-pipeline-page-polish-number-formatting*
*Context gathered: 2026-04-06*
