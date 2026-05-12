"""Tests for the per-run cancel event registry in pipeline_runner."""
import threading

from api.services.pipeline_runner import (
    _CANCEL_EVENTS,
    _register_cancel_event,
    _unregister_cancel_event,
    signal_cancel,
)


def test_register_creates_clear_event():
    run_id = 9001
    try:
        event = _register_cancel_event(run_id)
        assert isinstance(event, threading.Event)
        assert not event.is_set()
        assert _CANCEL_EVENTS.get(run_id) is event
    finally:
        _unregister_cancel_event(run_id)


def test_signal_cancel_sets_registered_event():
    run_id = 9002
    try:
        event = _register_cancel_event(run_id)
        propagated = signal_cancel(run_id)
        assert propagated is True
        assert event.is_set()
    finally:
        _unregister_cancel_event(run_id)


def test_signal_cancel_returns_false_when_unknown():
    propagated = signal_cancel(999_999_999)
    assert propagated is False


def test_unregister_removes_entry():
    run_id = 9003
    _register_cancel_event(run_id)
    _unregister_cancel_event(run_id)
    assert _CANCEL_EVENTS.get(run_id) is None
    assert signal_cancel(run_id) is False


def test_unregister_is_idempotent():
    _unregister_cancel_event(123_456_789)
    _unregister_cancel_event(123_456_789)
