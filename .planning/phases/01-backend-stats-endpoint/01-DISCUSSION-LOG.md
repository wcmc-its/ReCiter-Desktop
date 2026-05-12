# Phase 1: Backend Stats Endpoint - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 01-backend-stats-endpoint
**Areas discussed:** Model type priority, Response score scale, Bootstrap performance, Endpoint architecture

---

## Model Type Priority

| Option | Description | Selected |
|--------|-------------|----------|
| feedbackIdentity always wins (per-researcher) | Use feedbackIdentity if available for that researcher, else identityOnly | ✓ |
| Separate stats per model type | Compute two full stat sets, return both | |
| Most recent model type wins | Use whichever model was used in last pipeline run | |

**User's choice:** feedbackIdentity wins per-researcher; mixed model types in aggregate is acceptable.

**Follow-up — per-researcher vs run-level consistency:**

| Option | Description | Selected |
|--------|-------------|----------|
| Per-researcher (mixed is fine) | Each researcher uses their best available model | ✓ |
| Run-level consistency | If any researcher has feedbackIdentity, use it for all | |

**Notes:** Mixed model types across researchers in the same stat aggregate is acceptable.

---

## Response Score Scale

| Option | Description | Selected |
|--------|-------------|----------|
| 0-100 everywhere | Multiply calibrated_score × 100 before all computations | ✓ |
| 0-1 for curves, 0-100 for distribution/disagreements | Mixed scale in response | |
| 0-1 everywhere | Keep raw scores, frontend converts | |

**User's choice:** 0–100 everywhere. Consistent with app-wide convention.

---

## Bootstrap Performance

| Option | Description | Selected |
|--------|-------------|----------|
| Always 1000, no cap | Exactly as specified, optimize later | |
| 1000 resamples, warn if slow | Run 1000; include ci_degraded flag if >~2s | ✓ |
| Auto-reduce for large n | 1000 when n<200, 500 when n>=200 | |

**User's choice:** Always 1000, add `ci_degraded: true` flag if runtime is slow.

**Follow-up — historical run storage:**

| Option | Description | Selected |
|--------|-------------|----------|
| Always compute fresh | No storage, recompute every request | ✓ |
| Cache in memory, invalidate on pipeline run | Store result in memory until next run | |
| Persist stats to DB per run | Stats snapshot table, compare runs over time | |

**Notes:** User raised this question mid-discussion. Chose simplest approach — always compute fresh.

---

## Endpoint Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| New stats.py router + stats_service.py | Follows existing routers/ + services/ pattern | ✓ |
| Add to existing scores.py | Extend current router | |
| Inline computation in router | All logic in router, no service file | |

**User's choice:** New files following existing pattern.

**Follow-up — service decomposition:**

| Option | Description | Selected |
|--------|-------------|----------|
| One stats_service.py | All computations in one service | ✓ |
| Split by stat type | Separate service per stat category | |

**Notes:** Shared DB join logic makes one service the natural choice.

---
