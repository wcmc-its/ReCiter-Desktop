# Phase 10: Pipeline Page Polish + Number Formatting - Research

**Researched:** 2026-04-06
**Domain:** React/Next.js frontend — SSE event handling, CSS animation, Tailwind typography, number formatting
**Confidence:** HIGH

## Summary

Phase 10 is a pure frontend polish and bug-fix phase. All six changes are precisely scoped in CONTEXT.md with exact line numbers, exact class names, and exact decisions. No backend changes. No new libraries. The domain is well-understood React/Next.js with SSE event handlers, Tailwind utility classes, and CSS keyframes.

The most technically interesting change is the ETA countdown fix (PIPE-02). The current implementation uses `elapsed / completedCount` (cumulative average from run start), which means `avgTimePerResearcher` grows continuously as time passes between completions. The fix switches to a rolling average of actual inter-completion deltas captured via a `useRef` (`lastCompletionTime`). This is a standard React pattern: refs for values that affect computation but not rendering; functional setState to avoid stale closures.

The remaining five fixes are mechanical: two string swaps (heading/subtitle), one CSS keyframe swap (animation direction), one Tailwind class change (`text-sm` → `text-xs`) plus optional grid proportion review, and three `.toLocaleString()` additions at explicit call sites.

**Primary recommendation:** Implement in a single wave. All six changes are small, independent, and touch only three files plus one CSS file. No new dependencies, no schema changes, no backend work.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `<h2>` text: "Processing Pipeline" → "Retrieve & Score"
- **D-02:** Subtitle paragraph: "Retrieve articles and compute authorship likelihood scores for each researcher." → "Retrieve articles and compute authorship likelihood scores for each researcher's candidate articles."
- **D-03:** ETA approach: snapshot-at-completion. Track `lastCompletionTime` as a `useRef`. On each `complete_one` event, compute delta = `Date.now() - lastCompletionTime`, update `avgTimePerResearcher` as rolling average of that delta. Update `lastCompletionTime = Date.now()` after each completion.
- **D-04:** ETA display = `avgTimePerResearcher * (total - completed)`. Freezes between completions but never counts up. Show only after first completion.
- **D-05:** Initialize `lastCompletionTime` to `Date.now()` when `started` event fires (not when button is clicked).
- **D-06:** Swap `@keyframes pipeline-stripe`: `from { background-position: 0 0; } to { background-position: 40px 0; }`
- **D-07:** Status label text → `text-xs` (from `text-sm`); spinner stays `w-3.5 h-3.5` with `items-center` alignment; review grid proportions after font fix if needed.
- **D-08:** `isBottleneck` conditional logic in `pipeline/page.tsx` is structurally correct — no separate fix needed.
- **D-09:** PIPE-05 (false-positive "Taking longer than usual") is a symptom of the ETA bug, not a separate bug. No additional fix needed beyond D-03.
- **D-10:** Use inline `.toLocaleString()` at each call site — no new utility function.
- **D-11:** Three exact gaps to fix:
  - `frontend/app/pipeline/page.tsx` line ~348: `{totalArticles}` → `{totalArticles.toLocaleString()}`
  - `frontend/app/pipeline/page.tsx` line ~349: `{totalScored}` → `{totalScored.toLocaleString()}`
  - `frontend/components/pipeline-row.tsx` line ~138: `{articleCount ?? "—"}` → `{articleCount != null ? articleCount.toLocaleString() : "—"}`
- **D-12:** All other numeric displays (dashboard, stats, articles page, setup page) already use `.toLocaleString()` — no changes needed there.

### Claude's Discretion

- Exact rolling average formula for ETA (simple moving average is fine)
- Whether to tweak `grid-cols` proportions if font-size fix still leaves alignment off
- Whether PIPE-05 needs any additional conditional logic after verifying ETA fix resolves it

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PIPE-01 | Pipeline page heading reads "Retrieve & Score" with correct subtitle | D-01, D-02 — two string literal swaps in `pipeline/page.tsx` line 276 and 278 |
| PIPE-02 | ETA display decreases over time; recalculated from actual completion times | D-03, D-04, D-05 — replace cumulative elapsed with inter-completion delta via `useRef` |
| PIPE-03 | Pipeline row progress animation moves in correct direction | D-06 — swap keyframe `from`/`to` in `globals.css` |
| PIPE-04 | Status text uses consistent font size and aligns with column headers | D-07 — change `text-sm` → `text-xs` on status `<span>` in `pipeline-row.tsx` |
| PIPE-05 | "Taking longer than usual" appears only when researcher's time exceeds expected | D-08, D-09 — resolved as side-effect of ETA fix; verify after PIPE-02 is implemented |
| FMT-01 | All numeric values ≥ 1,000 display with commas throughout the application | D-10, D-11 — three `.toLocaleString()` additions at exact identified call sites |
</phase_requirements>

---

## Standard Stack

### Core (already installed — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 14.2.35 | App framework | Already in use |
| React | 18.x | UI rendering, hooks | Already in use |
| Tailwind CSS | 4.2.x | Utility classes (`text-xs`, `text-sm`) | Already in use |
| TypeScript | 5.x | Type safety | Already in use |

### Installation

No new packages required. All changes use existing stack.

---

## Architecture Patterns

### Recommended File Targets

```
frontend/
├── app/
│   ├── pipeline/
│   │   └── page.tsx          # H2 text, subtitle, ETA computation, totalArticles/totalScored formatting
│   └── globals.css            # @keyframes pipeline-stripe direction
└── components/
    └── pipeline-row.tsx       # text-sm → text-xs on status span, articleCount formatting
```

### Pattern 1: Inter-Completion Delta ETA (useRef for timestamps)

**What:** Track the wall-clock time of each researcher completion using a `useRef`. On `complete_one` SSE event, compute the time since the last completion (delta), update the rolling average, then reset the ref.

**When to use:** When you need a value that (a) participates in computation inside event handlers and (b) does NOT directly drive re-renders. `useRef` avoids stale closure issues that would occur with a plain `let` variable and avoids unnecessary re-renders that `useState` would trigger.

**Why not useState for lastCompletionTime:** `useState` updates are asynchronous — the new value won't be visible inside the same event handler callback that set it. `useRef` mutations are synchronous and immediately visible to subsequent reads in the same closure. This pattern is already used in `pipeline/page.tsx` for `personIdsRef` and `nextToStartRef`.

**Example:**
```typescript
// At component top level (alongside existing refs)
const lastCompletionTimeRef = useRef<number | null>(null);

// In startPipeline(), when 'started' event fires:
if (event.type === "started") {
  lastCompletionTimeRef.current = Date.now();  // D-05
  // ... existing started logic ...
}

// In 'complete_one' handler, replacing the existing avgTimePerResearcher computation:
} else if (event.type === "complete_one") {
  // ... existing state updates for completed, totalArticles, totalScored ...

  // New ETA computation (replaces setStartTime callback block)
  const now = Date.now();
  if (lastCompletionTimeRef.current !== null) {
    const delta = now - lastCompletionTimeRef.current;
    setAvgTimePerResearcher((prev) =>
      prev === 0 ? delta : (prev + delta) / 2  // simple moving average
    );
  }
  lastCompletionTimeRef.current = now;

  // ... existing processingSet and researcher state updates ...
}
```

**What to REMOVE:** The existing `setStartTime` callback block that computes `elapsed / completedCount`:
```typescript
// DELETE this block:
setStartTime((prevStart) => {
  if (prevStart !== null) {
    const elapsed = Date.now() - prevStart;
    setAvgTimePerResearcher(elapsed / completedCount);
  }
  return prevStart;
});
```
`startTime` ref itself is still needed for the "Elapsed" display — only the `avgTimePerResearcher` computation changes.

### Pattern 2: Functional setState in SSE Handlers

**What:** Use `setX(prev => ...)` form rather than reading current state directly inside SSE event callbacks.

**Why:** SSE callbacks are closures captured at subscription time. They see stale state unless you use the functional updater form, which always receives the latest state value.

**Already established:** `setTotalArticles((prev) => prev + artCount)` and `setTotalScored((prev) => prev + scoredCount)` already follow this pattern. The new `setAvgTimePerResearcher` call must also use it.

### Pattern 3: CSS Keyframe Animation Direction

**What:** Diagonal stripe animation uses `background-position` offset to simulate movement. Moving from `0→40px` makes stripes appear to move right; `40px→0` moves them left.

**Current (wrong — moves right-to-left):**
```css
@keyframes pipeline-stripe {
  from { background-position: 40px 0; }
  to   { background-position: 0 0; }
}
```

**Fixed (left-to-right):**
```css
@keyframes pipeline-stripe {
  from { background-position: 0 0; }
  to   { background-position: 40px 0; }
}
```

**No other changes needed** to `.pipeline-progress-animated` — background-size, colors, repeating-linear-gradient are all correct.

### Pattern 4: Tailwind Font Size for Status Column

**Current status span in `pipeline-row.tsx` line 139:**
```tsx
<span className={`text-sm flex items-center gap-2 ${PHASE_COLORS[phase]}`}>
```

**Fixed:**
```tsx
<span className={`text-xs flex items-center gap-2 ${PHASE_COLORS[phase]}`}>
```

Column headers use `text-[10px]` (custom size via bracket notation). The UID and article count cells use `text-xs` (12px). Status label moving from `text-sm` (14px) → `text-xs` (12px) aligns it more closely with peer cells. The column header font size (`text-[10px]`) is intentionally smaller than cell content — this is a standard table pattern where headers are uppercase tracking labels and body content is readable data.

### Pattern 5: Conditional toLocaleString for Nullable Numbers

**Current `articleCount` cell in `pipeline-row.tsx` line 138:**
```tsx
<span className="text-sm text-gray-500 tabular-nums">{articleCount ?? "\u2014"}</span>
```

**Fixed:**
```tsx
<span className="text-sm text-gray-500 tabular-nums">{articleCount != null ? articleCount.toLocaleString() : "\u2014"}</span>
```

Note: `?? "—"` cannot be refactored to use `.toLocaleString()` because the nullish coalescing operator short-circuits — `articleCount.toLocaleString()` would throw on `null`. The `!= null` check (which catches both `null` and `undefined`) is the correct pattern for nullable number formatting. The existing `?? "\u2014"` pattern must be replaced entirely.

**Non-nullable number formatting in `pipeline/page.tsx` lines 348-349:**
```tsx
// Current:
{totalArticles} articles &bull; {totalScored} scored
// Fixed:
{totalArticles.toLocaleString()} articles &bull; {totalScored.toLocaleString()} scored
```
These are initialized to `0` (non-nullable), so `.toLocaleString()` is safe without a null check.

### Anti-Patterns to Avoid

- **Don't use `startTime` for ETA computation:** `startTime` marks when the pipeline button was clicked. Using `elapsed / completedCount` inflates the average when researchers take different amounts of time — early completions make the average low, late completions spike it. Inter-completion deltas reflect actual throughput.
- **Don't add a utility function for formatting:** D-10 explicitly mandates inline `.toLocaleString()`. Every other site in the app already does this; a utility wrapper would be an inconsistency.
- **Don't remove `startTime` state:** It is still needed for the "Elapsed:" display on line 360. Only the `avgTimePerResearcher` derivation changes.
- **Don't add a third argument to toLocaleString():** No locale or options needed. `toLocaleString()` with no arguments uses the browser's locale, which is the correct behavior for a desktop app used at a single institution.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Number formatting with commas | Custom format function | `.toLocaleString()` | Native browser API, locale-aware, already used everywhere in this codebase |
| Rolling average | Accumulator class | Inline expression `(prev + delta) / 2` | Simple two-value running average is sufficient per Claude's Discretion; no library needed |
| CSS animation direction | JavaScript-driven position updates | CSS keyframe swap | One-line CSS change; no JS overhead |

---

## Common Pitfalls

### Pitfall 1: Stale Closure for lastCompletionTimeRef Initialization

**What goes wrong:** `lastCompletionTimeRef.current = Date.now()` is placed in `startPipeline()` at function call time (when button is clicked), not when the `started` SSE event fires. This inflates the first delta by the queue-setup time (typically 200-500ms).

**Why it happens:** The natural place to initialize is "when the pipeline starts" — but the SSE `started` event is the correct signal, not the function call.

**How to avoid:** Initialize inside the `if (event.type === "started")` branch. This is explicitly specified in D-05.

**Warning signs:** First researcher's delta is consistently ~300ms longer than subsequent deltas.

### Pitfall 2: avgTimePerResearcher Still 0 When First Researcher Completes Very Fast

**What goes wrong:** If `lastCompletionTimeRef.current` is `null` when `complete_one` fires (e.g., `started` event was missed), the delta computation is skipped and ETA never initializes.

**Why it happens:** SSE events can arrive out of order or `started` can be missed if the subscription is set up after the first event.

**How to avoid:** The existing `completed > 0` gate on the ETA display (line 365) already hides ETA until the first completion. The ref initialization in `started` event is reliable because `startPipeline()` sets up the SSE subscription synchronously before the server sends `started`. No additional guard needed.

### Pitfall 3: Grid Alignment After Font Size Fix

**What goes wrong:** Changing status cell from `text-sm` to `text-xs` may leave whitespace gaps if the column header proportions don't match cell content proportions. The column header grid is `grid-cols-[1.5fr_1fr_0.6fr_1.2fr_1fr]` and PipelineRow uses the same. Misalignment comes from cell content overflow or the spinner size, not the grid definition.

**Why it happens:** `text-sm` at 14px in the status cell may have caused implicit height differences vs. adjacent cells. The spinner (`w-3.5 h-3.5` = 14px) stays the same size regardless of text size.

**How to avoid:** After applying the `text-xs` fix, do a visual check with an active pipeline run. If the status column still appears wider than the header, the `1.2fr` fraction may need minor adjustment. Per Claude's Discretion, this is a judgment call at implementation time.

### Pitfall 4: toLocaleString on articleCount When it Equals 0

**What goes wrong:** `articleCount` can be `0` (researcher retrieved but found no articles). The current code `{articleCount ?? "—"}` renders `0` (falsy but not null/undefined). The fix `{articleCount != null ? articleCount.toLocaleString() : "—"}` correctly handles this — `0` is not null, so `(0).toLocaleString()` returns `"0"`.

**Why it happens:** Confusing nullish coalescing (`??`) with falsy checks. `??` only short-circuits on `null`/`undefined`, so `0 ?? "—"` renders `0` correctly — and `0 != null` is also true, so the `!= null` guard preserves the same behavior.

**How to avoid:** Use `!= null` (not `!== null` — intentional loose inequality to catch both `null` and `undefined`) rather than truthiness.

---

## Code Examples

### Complete ETA Ref Initialization in startPipeline()

```typescript
// At component top level (add alongside personIdsRef, nextToStartRef):
const lastCompletionTimeRef = useRef<number | null>(null);

// In startPipeline() — reset on each new run:
function startPipeline() {
  // ... existing resets ...
  lastCompletionTimeRef.current = null;  // reset before new run

  subscribeSSE("/api/pipeline/run", { person_ids: personIds, mode }, (event) => {
    if (event.type === "started") {
      lastCompletionTimeRef.current = Date.now();  // D-05: initialize on started
      // ... existing started logic ...
    } else if (event.type === "complete_one") {
      // ... existing artCount, scoredCount, completedCount extraction ...

      // Replace the setStartTime(prevStart => ...) block with:
      const now = Date.now();
      if (lastCompletionTimeRef.current !== null) {
        const delta = now - lastCompletionTimeRef.current;
        setAvgTimePerResearcher((prev) => prev === 0 ? delta : (prev + delta) / 2);
      }
      lastCompletionTimeRef.current = now;

      // ... rest of complete_one handler unchanged ...
    }
  });
}
```

### Fixed Keyframe (globals.css)

```css
@keyframes pipeline-stripe {
  from { background-position: 0 0; }
  to   { background-position: 40px 0; }
}
```

### Fixed Status Span (pipeline-row.tsx line 139)

```tsx
<span className={`text-xs flex items-center gap-2 ${PHASE_COLORS[phase]}`}>
```

### Fixed articleCount Cell (pipeline-row.tsx line 138)

```tsx
<span className="text-sm text-gray-500 tabular-nums">
  {articleCount != null ? articleCount.toLocaleString() : "\u2014"}
</span>
```

### Fixed Progress Stats (pipeline/page.tsx lines 348-349)

```tsx
{completed} of {total} researchers &bull; {totalArticles.toLocaleString()} articles
&bull; {totalScored.toLocaleString()} scored
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Cumulative elapsed / total completed | Inter-completion delta rolling average | Phase 10 (this phase) | ETA decreases rather than growing continuously |
| `background-position: 40px→0` | `background-position: 0→40px` | Phase 10 (this phase) | Animation moves left-to-right (physically forward direction) |

---

## Open Questions

1. **Rolling average formula choice**
   - What we know: Simple average `(prev + delta) / 2` is specified as acceptable per Claude's Discretion
   - What's unclear: Whether very slow early researchers skew the average enough to affect the ETA display meaningfully
   - Recommendation: Use simple average. If ETA proves inaccurate in practice, EMA (`0.7 * prev + 0.3 * delta`) is a one-line change and can be deferred to Phase 11.

2. **Grid proportion adjustment for PIPE-04**
   - What we know: `grid-cols-[1.5fr_1fr_0.6fr_1.2fr_1fr]` is used in both the column header div and `PipelineRow`
   - What's unclear: Whether `text-sm → text-xs` alone resolves the visual misalignment or whether `1.2fr` for the Status column needs adjustment
   - Recommendation: Apply the font-size fix first, then do a visual check with an active run. Change grid fractions only if misalignment persists. This is Claude's Discretion territory.

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — all changes are frontend code and CSS only, using already-installed packages).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (Python backend tests) |
| Config file | `pytest.ini` (project root — `asyncio_mode = auto`) |
| Quick run command | `cd /Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop && python -m pytest tests/ -x -q` |
| Full suite command | `cd /Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop && python -m pytest tests/ -v` |
| Frontend test framework | None — no jest/vitest config exists; no `*.test.*` files in `frontend/` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-01 | Heading and subtitle text is correct | manual | Visual inspection — string change only | N/A |
| PIPE-02 | ETA decreases as researchers complete | manual | Visual inspection during live pipeline run | N/A |
| PIPE-03 | Progress animation moves left-to-right | manual | Visual inspection during live pipeline run | N/A |
| PIPE-04 | Status text `text-xs` matches column headers | manual | Visual inspection | N/A |
| PIPE-05 | "Taking longer than usual" not shown prematurely | manual | Verify after PIPE-02 fix; no independent test | N/A |
| FMT-01 | `.toLocaleString()` applied at all three sites | unit/code-review | `grep -n "toLocaleString" frontend/app/pipeline/page.tsx frontend/components/pipeline-row.tsx` | No test needed — string search verifiable |

**Note on frontend testing:** The frontend has no test framework (no jest, no vitest, no playwright) installed. All Phase 10 acceptance criteria are visual/behavioral and require live pipeline runs or code review. The Python backend `tests/` directory covers backend logic; none of those tests are relevant to Phase 10 (pure frontend changes).

### Sampling Rate

- **Per task commit:** `python -m pytest tests/ -x -q` — ensures no backend regression (< 30 seconds)
- **Per wave merge:** `python -m pytest tests/ -v` — full suite
- **Phase gate:** Full suite green + visual verification checklist before `/gsd:verify-work`

### Wave 0 Gaps

None — existing test infrastructure (pytest for backend) is sufficient. Frontend changes require manual visual verification, not automated tests. No new test files needed.

---

## Sources

### Primary (HIGH confidence)

- Direct code reading: `frontend/app/pipeline/page.tsx` — full file read, line numbers confirmed
- Direct code reading: `frontend/components/pipeline-row.tsx` — full file read, line numbers confirmed
- Direct code reading: `frontend/app/globals.css` — `@keyframes pipeline-stripe` confirmed at lines 149-152
- `frontend/package.json` — dependency versions confirmed (Next.js 14.2.35, React 18, Tailwind 4.2.x)
- `.planning/phases/10-pipeline-page-polish-number-formatting/10-CONTEXT.md` — decisions D-01 through D-12 read verbatim

### Secondary (MEDIUM confidence)

- React `useRef` behavior (synchronous mutation, stale closure avoidance) — consistent with established patterns already in use in this codebase (`personIdsRef`, `nextToStartRef`)
- CSS `background-position` keyframe direction — standard CSS, confirmed by reading existing animation

### Tertiary (LOW confidence)

None. All findings derive from direct code inspection.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — read directly from package.json and existing files
- Architecture: HIGH — all patterns read from existing codebase; decisions pre-specified in CONTEXT.md
- Pitfalls: HIGH — derived from reading actual code (stale closure pattern, null vs falsy distinction, ref initialization timing)

**Research date:** 2026-04-06
**Valid until:** This is a code-specific research document tied to specific line numbers. Valid until the files change. Not time-sensitive in the library-staleness sense — no external libraries involved.

---

## Project Constraints (from CLAUDE.md)

Directives from `./CLAUDE.md` (project-level) that the planner must verify compliance with:

| Directive | Applies to Phase 10? | Compliance |
|-----------|---------------------|------------|
| No hardcoded credentials or localhost | No credentials in frontend UI | N/A — UI-only changes |
| XGBoost must be exactly 3.2.0 | Backend ML models | N/A — no backend changes |
| No new `.env` files committed | No secrets in scope | N/A |
| Port registry: frontend dev at 3001 (CViche) or Next.js at 3000 | Dev server port if running for verification | Use port 3000 per port registry (Next.js) |
| No "Co-Authored-By" or AI attribution in commits | All commits | Enforce in every commit |
| UI changes: describe exactly what changed, ask user to verify visually before proceeding | All five PIPE-xx fixes | Planner must include visual verification step per change |
| Do not assume spacing, sizing, colors without asking | PIPE-04 grid proportion question | Per Claude's Discretion: implement font fix, show result, ask about grid if needed |
