# Phase 10: Pipeline Page Polish + Number Formatting - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-04-06
**Phase:** 10-pipeline-page-polish-number-formatting
**Mode:** discuss
**Areas discussed:** ETA countdown, font/alignment, number formatting scope

## Gray Areas Presented

### ETA Countdown (PIPE-02)
| Area | Options Presented | Chosen |
|------|------------------|--------|
| ETA formula | A) Snapshot at completion (delta-based) vs B) Real-time countdown with tick subtraction | A) Snapshot at completion |

**Root cause analysis:** `avgTimePerResearcher = elapsedSinceStart / completedCount` is recomputed every tick via the 1s interval. Between researcher completions, `completedCount` is fixed while `elapsedSinceStart` grows → ETA grows. Fix: compute avg only on `complete_one` SSE events using delta from previous completion timestamp (stored in a `useRef`).

### Status Column Alignment (PIPE-04)
| Area | Options Presented | Chosen |
|------|------------------|--------|
| What's wrong | A) Text too large, B) Vertical alignment off, C) Both + column widths | C — text size + alignment, and wider column proportions |

**User note:** "3 and wider columns and different font sizes" — column width proportions also contribute to the misalignment. Planner should include visual verification step.

### Number Formatting (FMT-01)
| Area | Options Presented | Chosen |
|------|------------------|--------|
| Implementation | A) Inline .toLocaleString() everywhere vs B) Shared formatCount() utility | A) Inline everywhere |

## Corrections Made

No corrections — all three decisions were user's first selection.

## Scope notes

- PIPE-01 (copy), PIPE-03 (animation direction), PIPE-05 (bottleneck timing) were clear enough from codebase analysis that no discussion was needed. PIPE-05 is likely a symptom of the ETA bug resolved by D-03/D-04/D-05.
- All other number displays (dashboard, stats, articles, setup pages) already use `.toLocaleString()` — only pipeline row and progress bar text are gaps.
- No backend changes required for any item in this phase.
