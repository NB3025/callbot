"""test_session_store.py — InMemorySessionStore 속성 기반 테스트 및 단위 테스트"""
from __future__ import annotations

from hypothesis import given, settings

from callbot.session.session_store import InMemorySessionStore
from callbot.session.tests.conftest import session_contexts


# ---------------------------------------------------------------------------
# Property 1: save-load 라운드트립
# Validates: Requirements 2.2
# ---------------------------------------------------------------------------

@given(ctx=session_contexts())
@settings(max_examples=100)
def test_save_load_roundtrip(ctx):
    """save 후 load를 수행하면 동일한 SessionContext가 반환되어야 한다."""
    store = InMemorySessionStore()
    store.save(ctx)
    loaded = store.load(ctx.session_id)
    assert loaded is ctx


# ---------------------------------------------------------------------------
# Property 2: delete 후 load → None
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

@given(ctx=session_contexts())
@settings(max_examples=100)
def test_delete_then_load_returns_none(ctx):
    """save 후 delete를 수행하고 load를 호출하면 None이 반환되어야 한다."""
    store = InMemorySessionStore()
    store.save(ctx)
    store.delete(ctx.session_id)
    assert store.load(ctx.session_id) is None


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------

from datetime import datetime

from callbot.session.enums import AuthStatus, TurnType
from callbot.session.models import SessionContext, Turn


def _make_context(session_id: str = "sess-1") -> SessionContext:
    """테스트용 최소 SessionContext 생성."""
    return SessionContext(
        session_id=session_id,
        caller_id="010-0000-0000",
        is_authenticated=False,
        customer_info=None,
        auth_status=AuthStatus.NOT_ATTEMPTED,
        turns=[],
        business_turn_count=0,
        start_time=datetime(2025, 1, 1, 12, 0, 0),
        tts_speed_factor=1.0,
        cached_billing_data=None,
        injection_detection_count=0,
        masking_restore_failure_count=0,
        plan_list_context=None,
        pending_intent=None,
        pending_classification=None,
    )


def test_delete_then_exists_returns_false():
    """delete 후 exists → False (Req 2.4)"""
    store = InMemorySessionStore()
    ctx = _make_context()
    store.save(ctx)
    store.delete(ctx.session_id)
    assert store.exists(ctx.session_id) is False


def test_load_nonexistent_returns_none():
    """미존재 session_id → None (Req 1.3)"""
    store = InMemorySessionStore()
    assert store.load("nonexistent-id") is None


def test_exists_nonexistent_returns_false():
    """미존재 session_id → False (Req 1.5)"""
    store = InMemorySessionStore()
    assert store.exists("nonexistent-id") is False


def test_save_overwrites_existing():
    """동일 session_id로 save 2회 → 마지막 값 유지"""
    store = InMemorySessionStore()
    ctx1 = _make_context("sess-1")
    ctx2 = _make_context("sess-1")
    ctx2.caller_id = "010-9999-9999"

    store.save(ctx1)
    store.save(ctx2)

    loaded = store.load("sess-1")
    assert loaded is ctx2
    assert loaded.caller_id == "010-9999-9999"
