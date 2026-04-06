---
phase: 10
slug: pipeline-page-polish-number-formatting
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-06
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (Python backend); no frontend test framework exists |
| **Config file** | `pytest.ini` (project root — `asyncio_mode = auto`) |
| **Quick run command** | `cd /Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd /Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop && python -m pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green + visual verification checklist complete
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| PIPE-01 | 01 | 1 | PIPE-01 | — | N/A | manual | Visual inspection — heading/subtitle text change | N/A | ⬜ pending |
| PIPE-02 | 01 | 1 | PIPE-02 | — | N/A | manual | Visual inspection during live pipeline run (ETA counts down) | N/A | ⬜ pending |
| PIPE-03 | 01 | 1 | PIPE-03 | — | N/A | manual | Visual inspection — animation direction (left to right) | N/A | ⬜ pending |
| PIPE-04 | 01 | 1 | PIPE-04 | — | N/A | manual | Visual inspection — status text `text-xs` aligns with column headers | N/A | ⬜ pending |
| PIPE-05 | 01 | 1 | PIPE-05 | — | N/A | manual | Verify after PIPE-02 fix — "Taking longer" not shown prematurely | N/A | ⬜ pending |
| FMT-01 | 01 | 1 | FMT-01 | — | N/A | code-review | `grep -n "toLocaleString" frontend/app/pipeline/page.tsx frontend/components/pipeline-row.tsx frontend/app/results/*/page.tsx frontend/app/stats/page.tsx` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

None — existing infrastructure covers all phase requirements.

The Python backend test suite covers backend regression; Phase 10 changes are pure frontend (3 files). No new test files or framework installation needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Heading reads "Retrieve & Score" | PIPE-01 | String-only change; no test framework | Inspect pipeline page in browser; confirm heading and subtitle text |
| ETA counts down as researchers complete | PIPE-02 | Requires live pipeline run with multiple researchers | Start a multi-researcher pipeline run; observe ETA decreases with each completion |
| Progress animation moves left-to-right | PIPE-03 | Visual behavior; no frontend test framework | Start a pipeline run; observe stripe animation direction |
| Status text size matches column headers | PIPE-04 | Visual/layout; no frontend test framework | Inspect pipeline rows during run; confirm `text-xs` font size consistency |
| "Taking longer" only for overdue researchers | PIPE-05 | Requires live run with timing threshold | Start run; confirm last column is blank at start; appears only after threshold exceeded |
| Numbers ≥ 1000 show commas throughout app | FMT-01 | Partial automation (grep); visual for accuracy | Use `grep -n "toLocaleString"` to confirm all sites patched; verify display in browser |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
