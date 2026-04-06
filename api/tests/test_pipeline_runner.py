# api/tests/test_pipeline_runner.py
"""
Tests for pipeline_runner.py:
- as_completed ordering (completion order, not submission order)
- Adaptive worker count (8 with API key, 3 without)
- run_id flows through started event
- No processing event emitted
"""
import asyncio
import time
from unittest.mock import patch, MagicMock

import pytest

# Ensure the institution module is imported so we can patch its get_pubmed_api_key
import api.routers.institution  # noqa: F401


# Helper to collect all events from the async generator
async def collect_events(gen):
    events = []
    async for event in gen:
        events.append(event)
    return events


def _make_mock_researcher(delay_map: dict):
    """Return a mock _process_one_researcher that sleeps based on person_id."""
    def _mock(person_id, mode, config, model_dir, run_id=None):
        time.sleep(delay_map.get(person_id, 0.0))
        return {
            "person_id": person_id,
            "article_count": 1,
            "scored_count": 1,
        }
    return _mock


def _make_mock_db():
    """Return a mock SessionLocal that returns a mock session."""
    mock_session = MagicMock()
    mock_session.query.return_value.all.return_value = []
    mock_session.close.return_value = None
    mock_session_local = MagicMock(return_value=mock_session)
    return mock_session_local


@pytest.mark.asyncio
async def test_as_completed_order():
    """
    Events should arrive in completion order (fastest first), not submission order.
    A=0.3s, B=0.1s, C=0.2s  ->  expected order: B, C, A
    """
    delay_map = {"A": 0.3, "B": 0.1, "C": 0.2}
    mock_processor = _make_mock_researcher(delay_map)

    with (
        patch("api.services.pipeline_runner._process_one_researcher", side_effect=mock_processor),
        patch("api.services.pipeline_runner.SessionLocal", _make_mock_db()),
        patch("api.services.pipeline_runner.load_config", return_value={}),
        patch("api.routers.institution.get_pubmed_api_key", return_value=""),
    ):
        from api.services.pipeline_runner import run_pipeline
        events = await collect_events(run_pipeline(["A", "B", "C"], mode="full", run_id=1))

    complete_events = [e for e in events if e.get("type") == "complete_one"]
    order = [e["person_id"] for e in complete_events]
    assert order == ["B", "C", "A"], f"Expected completion order B,C,A but got {order}"


@pytest.mark.asyncio
async def test_worker_count_with_api_key():
    """When PubMed API key is present, started event should have max_workers == 8."""
    mock_processor = _make_mock_researcher({"X": 0.0})

    with (
        patch("api.services.pipeline_runner._process_one_researcher", side_effect=mock_processor),
        patch("api.services.pipeline_runner.SessionLocal", _make_mock_db()),
        patch("api.services.pipeline_runner.load_config", return_value={}),
        patch("api.routers.institution.get_pubmed_api_key", return_value="test_api_key"),
    ):
        from api.services import pipeline_runner
        import importlib
        importlib.reload(pipeline_runner)
        with patch("api.routers.institution.get_pubmed_api_key", return_value="test_api_key"):
            events = await collect_events(pipeline_runner.run_pipeline(["X"], mode="full", run_id=1))

    started = next(e for e in events if e.get("type") == "started")
    assert started["max_workers"] == 8, f"Expected max_workers=8 with API key, got {started.get('max_workers')}"


@pytest.mark.asyncio
async def test_worker_count_without_api_key():
    """When PubMed API key is absent, started event should have max_workers == 3."""
    mock_processor = _make_mock_researcher({"X": 0.0})

    with (
        patch("api.services.pipeline_runner._process_one_researcher", side_effect=mock_processor),
        patch("api.services.pipeline_runner.SessionLocal", _make_mock_db()),
        patch("api.services.pipeline_runner.load_config", return_value={}),
        patch("api.routers.institution.get_pubmed_api_key", return_value=""),
    ):
        from api.services.pipeline_runner import run_pipeline
        events = await collect_events(run_pipeline(["X"], mode="full", run_id=1))

    started = next(e for e in events if e.get("type") == "started")
    assert started["max_workers"] == 3, f"Expected max_workers=3 without API key, got {started.get('max_workers')}"


@pytest.mark.asyncio
async def test_started_event_has_run_id():
    """The started event must carry the run_id passed to run_pipeline."""
    mock_processor = _make_mock_researcher({"X": 0.0})

    with (
        patch("api.services.pipeline_runner._process_one_researcher", side_effect=mock_processor),
        patch("api.services.pipeline_runner.SessionLocal", _make_mock_db()),
        patch("api.services.pipeline_runner.load_config", return_value={}),
        patch("api.routers.institution.get_pubmed_api_key", return_value=""),
    ):
        from api.services.pipeline_runner import run_pipeline
        events = await collect_events(run_pipeline(["X"], mode="full", run_id=42))

    started = next(e for e in events if e.get("type") == "started")
    assert started.get("run_id") == 42, f"Expected run_id=42 in started event, got {started.get('run_id')}"


@pytest.mark.asyncio
async def test_no_processing_event():
    """No event with type='processing' should be emitted (removed per D-13)."""
    mock_processor = _make_mock_researcher({"X": 0.0})

    with (
        patch("api.services.pipeline_runner._process_one_researcher", side_effect=mock_processor),
        patch("api.services.pipeline_runner.SessionLocal", _make_mock_db()),
        patch("api.services.pipeline_runner.load_config", return_value={}),
        patch("api.routers.institution.get_pubmed_api_key", return_value=""),
    ):
        from api.services.pipeline_runner import run_pipeline
        events = await collect_events(run_pipeline(["X"], mode="full", run_id=1))

    processing_events = [e for e in events if e.get("type") == "processing"]
    assert len(processing_events) == 0, f"Expected no 'processing' events but found: {processing_events}"
