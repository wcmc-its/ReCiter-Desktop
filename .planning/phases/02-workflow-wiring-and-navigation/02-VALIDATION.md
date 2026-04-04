---
phase: 2
slug: workflow-wiring-and-navigation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (confirmed in venv) |
| **Config file** | `pytest.ini` or `pyproject.toml` (check root) |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-W0-01 | 01 | 0 | NAV-01 | — | N/A | unit stub | `python -m pytest tests/test_pipeline_status.py -x -q` | ❌ W0 | ⬜ pending |
| 2-01-01 | 01 | 1 | NAV-01 | — | N/A | unit | `python -m pytest tests/test_pipeline_status.py -x -q` | ✅ | ⬜ pending |
| 2-01-02 | 01 | 1 | NAV-02 | — | N/A | unit | `python -m pytest tests/test_pipeline_status.py -x -q` | ✅ | ⬜ pending |
| 2-02-01 | 02 | 2 | NAV-02 | — | N/A | manual | Visual: sidebar locked/unlocked states | ✅ | ⬜ pending |
| 2-02-02 | 02 | 2 | NAV-03 | — | N/A | manual | Visual: /stats gate renders correctly | ✅ | ⬜ pending |
| 2-03-01 | 03 | 2 | NAV-02 | — | N/A | manual | Visual: pipeline CTA present/absent | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline_status.py` — stubs for NAV-01 (assertion_count field in /pipeline/status endpoint)

*Existing pytest infrastructure covers all other phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sidebar "Statistics" locked/unlocked | NAV-02 | No frontend test framework installed | Navigate app, check sidebar with 0 assertions vs. some assertions |
| Pipeline CTA "View Statistics" present/absent | NAV-02 | No frontend test framework installed | Complete pipeline, verify CTA appears; check without assertions |
| /stats gate UI renders | NAV-03 | No frontend test framework installed | Navigate to /stats with and without assertions in DB |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
