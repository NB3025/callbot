"""callbot.session.tests.test_state_management — SessionContext 상태 관리 단위 테스트

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from callbot.session.exceptions import SessionNotFoundError
from callbot.session.models import PlanListContext
from callbot.session.repository import CallbotDBRepository
from callbot.session.session_manager import SessionManager
from callbot.session.session_store import InMemorySessionStore


def make_manager() -> SessionManager:
    mock_repo = MagicMock(spec=CallbotDBRepository)
    store = InMemorySessionStore()
    return SessionManager(repository=mock_repo, session_store=store)


# ---------------------------------------------------------------------------
# injection_detection_count / masking_restore_failure_count
# ---------------------------------------------------------------------------

def test_increment_injection_count_increases_by_one() -> None:
    """increment_injection_count() 호출 시 injection_detection_count가 1 증가한다."""
    manager = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    assert ctx.injection_detection_count == 0

    result = manager.increment_injection_count(ctx.session_id)

    assert result == 1
    assert ctx.injection_detection_count == 1


def test_increment_injection_count_accumulates() -> None:
    """increment_injection_count() 여러 번 호출 시 누적된다."""
    manager = make_manager()
    ctx = manager.create_session(caller_id="01012345678")

    manager.increment_injection_count(ctx.session_id)
    manager.increment_injection_count(ctx.session_id)
    result = manager.increment_injection_count(ctx.session_id)

    assert result == 3
    assert ctx.injection_detection_count == 3


def test_increment_masking_failure_count_increases_by_one() -> None:
    """increment_masking_failure_count() 호출 시 masking_restore_failure_count가 1 증가한다."""
    manager = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    assert ctx.masking_restore_failure_count == 0

    result = manager.increment_masking_failure_count(ctx.session_id)

    assert result == 1
    assert ctx.masking_restore_failure_count == 1


# ---------------------------------------------------------------------------
# 10.1 과금 캐시 무효화 단위 테스트 (Validates: Requirements 5.3)
# ---------------------------------------------------------------------------

def test_update_cached_billing_data_stores_data() -> None:
    """update_cached_billing_data() 후 cached_billing_data가 저장된다."""
    manager = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    billing = {"plan": "5G_BASIC", "amount": 55000}

    manager.update_cached_billing_data(ctx.session_id, billing)

    assert ctx.cached_billing_data == billing


def test_invalidate_billing_cache_sets_none() -> None:
    """update_cached_billing_data() 후 invalidate_billing_cache() 호출 시 cached_billing_data=None.

    Validates: Requirements 5.3
    """
    manager = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    manager.update_cached_billing_data(ctx.session_id, {"plan": "5G_BASIC"})
    assert ctx.cached_billing_data is not None

    manager.invalidate_billing_cache(ctx.session_id)

    assert ctx.cached_billing_data is None


def test_invalidate_billing_cache_on_already_none_is_safe() -> None:
    """cached_billing_data가 이미 None일 때 invalidate_billing_cache() 호출해도 안전하다."""
    manager = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    assert ctx.cached_billing_data is None

    manager.invalidate_billing_cache(ctx.session_id)  # 예외 없이 실행

    assert ctx.cached_billing_data is None


# ---------------------------------------------------------------------------
# 10.2 pending_intent 라운드트립 단위 테스트 (Validates: Requirements 5.4)
# ---------------------------------------------------------------------------

def test_set_pending_intent_stores_intent_and_classification() -> None:
    """set_pending_intent() 후 pending_intent와 pending_classification이 저장된다."""
    manager = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    intent = "PLAN_CHANGE"
    classification = {"confidence": 0.95}

    manager.set_pending_intent(ctx.session_id, intent, classification)

    assert ctx.pending_intent == intent
    assert ctx.pending_classification == classification


def test_pop_pending_intent_returns_stored_values_and_clears() -> None:
    """set_pending_intent() 후 pop_pending_intent() 호출 시 저장된 값 반환 및 필드 초기화.

    Validates: Requirements 5.4
    """
    manager = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    intent = "PLAN_CHANGE"
    classification = {"confidence": 0.95}
    manager.set_pending_intent(ctx.session_id, intent, classification)

    returned_intent, returned_classification = manager.pop_pending_intent(ctx.session_id)

    assert returned_intent == intent
    assert returned_classification == classification
    # 초기화 확인
    assert ctx.pending_intent is None
    assert ctx.pending_classification is None


def test_pop_pending_intent_on_empty_returns_none_tuple() -> None:
    """pending_intent가 없을 때 pop_pending_intent()는 (None, None)을 반환한다."""
    manager = make_manager()
    ctx = manager.create_session(caller_id="01012345678")

    intent, classification = manager.pop_pending_intent(ctx.session_id)

    assert intent is None
    assert classification is None


def test_pop_pending_intent_is_idempotent() -> None:
    """pop_pending_intent() 두 번 호출 시 두 번째는 (None, None)을 반환한다."""
    manager = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    manager.set_pending_intent(ctx.session_id, "PLAN_CHANGE", {"confidence": 0.9})

    manager.pop_pending_intent(ctx.session_id)
    intent, classification = manager.pop_pending_intent(ctx.session_id)

    assert intent is None
    assert classification is None


# ---------------------------------------------------------------------------
# plan_list_context 관리 (Validates: Requirements 5.5)
# ---------------------------------------------------------------------------

def test_set_plan_list_context_stores_context() -> None:
    """set_plan_list_context() 후 plan_list_context가 저장된다."""
    manager = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    plan_ctx = PlanListContext(
        available_plans=[{"name": "5G_BASIC"}],
        current_page=0,
        page_size=3,
        current_plan={"name": "LTE_STANDARD"},
        is_exhausted=False,
    )

    manager.set_plan_list_context(ctx.session_id, plan_ctx)

    assert ctx.plan_list_context == plan_ctx


def test_clear_plan_list_context_sets_none() -> None:
    """set_plan_list_context() 후 clear_plan_list_context() 호출 시 None으로 초기화된다."""
    manager = make_manager()
    ctx = manager.create_session(caller_id="01012345678")
    plan_ctx = PlanListContext(
        available_plans=[],
        current_page=0,
        page_size=3,
        current_plan={},
        is_exhausted=False,
    )
    manager.set_plan_list_context(ctx.session_id, plan_ctx)
    assert ctx.plan_list_context is not None

    manager.clear_plan_list_context(ctx.session_id)

    assert ctx.plan_list_context is None


# ---------------------------------------------------------------------------
# 미존재 세션 오류 처리
# ---------------------------------------------------------------------------

def test_state_helpers_raise_session_not_found_for_unknown_session() -> None:
    """모든 상태 관리 헬퍼는 존재하지 않는 session_id에 대해 SessionNotFoundError를 발생시킨다."""
    manager = make_manager()
    sid = "nonexistent"

    with pytest.raises(SessionNotFoundError):
        manager.increment_injection_count(sid)

    with pytest.raises(SessionNotFoundError):
        manager.increment_masking_failure_count(sid)

    with pytest.raises(SessionNotFoundError):
        manager.update_cached_billing_data(sid, {})

    with pytest.raises(SessionNotFoundError):
        manager.invalidate_billing_cache(sid)

    with pytest.raises(SessionNotFoundError):
        manager.set_pending_intent(sid, None, None)

    with pytest.raises(SessionNotFoundError):
        manager.pop_pending_intent(sid)

    with pytest.raises(SessionNotFoundError):
        manager.clear_plan_list_context(sid)
