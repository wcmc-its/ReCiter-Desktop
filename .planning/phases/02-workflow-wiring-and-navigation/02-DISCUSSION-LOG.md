# Phase 2: Workflow Wiring and Navigation - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-04-04
**Phase:** 02-workflow-wiring-and-navigation
**Mode:** assumptions
**Areas analyzed:** Gate Data Source, Sidebar Locked-Item Behavior, Pipeline Completion CTA, /stats Route Structure

## Assumptions Presented

### Gate Data Source
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Stats gate requires a new field in WorkflowContext — /api/pipeline/status never queries Curation table | Confident | `frontend/lib/workflow.tsx` (WorkflowContext fetch), `api/routers/pipeline.py` lines 37–68 |

Alternatives presented:
- A: Extend pipeline/status response with assertion_count → read from WorkflowContext (recommended)
- B: Each surface calls /api/stats independently and reads viable flag

### Sidebar Locked-Item Behavior
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Locked items remain navigable <Link> components; gate enforced at /stats page via PrerequisiteGate | Confident | `frontend/components/sidebar.tsx` lines 99–120, `frontend/app/results/page.tsx` lines 29–35 |

### Pipeline Completion CTA
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| "View Statistics" CTA added to completion block; conditioned on assertionCount > 0, not pipelineFinished alone | Likely | `frontend/app/pipeline/page.tsx` completion block, `finished` event handler pattern |

Alternatives presented:
- A: Fetch /api/stats in finished handler, store viable flag in local state (recommended)
- B: Add assertion-pair count to /api/pipeline/status → no extra fetch (chosen via D-01/D-02)

### /stats Route Structure
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| frontend/app/stats/page.tsx as "use client" component following results/page.tsx pattern | Confident | All existing pages use "use client", ROADMAP Phase 3 note explicitly requires it |

## Corrections Made

No corrections — all assumptions confirmed by user.

## External Research

None performed — codebase provided sufficient evidence.
