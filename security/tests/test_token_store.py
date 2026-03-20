"""TokenStore 테스트: Property 5 + 단위 테스트."""

from __future__ import annotations

import time
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.security.token_store import InMemoryTokenStore


# ---------------------------------------------------------------------------
# Property 5: 만료된 폐기 항목 자동 제거
# Feature: callbot-security, Property 5: 만료된 폐기 항목 자동 제거
# ---------------------------------------------------------------------------


@given(
    jti=st.text(min_size=1, max_size=50),
    seconds_ago=st.floats(min_value=1.0, max_value=1_000_000.0),
)
@settings(max_examples=100)
def test_expired_revoked_entry_returns_false(jti: str, seconds_ago: float) -> None:
    """과거 시각 exp로 revoke 후 is_revoked → False.

    **Validates: Requirements 3.3**
    """
    store = InMemoryTokenStore()
    past_exp = time.time() - seconds_ago
    store.revoke(jti, past_exp)
    assert store.is_revoked(jti) is False


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------


def test_revoke_and_is_revoked() -> None:
    """revoke 후 is_revoked → True (Req 3.1)."""
    store = InMemoryTokenStore()
    future_exp = time.time() + 3600.0
    store.revoke("test-jti-001", future_exp)
    assert store.is_revoked("test-jti-001") is True


def test_purge_expired_removes_old_entries() -> None:
    """purge_expired()가 만료된 항목을 제거하고 개수를 반환한다 (Req 3.5)."""
    store = InMemoryTokenStore()
    now = time.time()

    # 만료된 항목 3개
    store.revoke("expired-1", now - 100.0)
    store.revoke("expired-2", now - 200.0)
    store.revoke("expired-3", now - 300.0)

    # 아직 유효한 항목 1개
    store.revoke("valid-1", now + 3600.0)

    removed = store.purge_expired()
    assert removed == 3
    assert store.is_revoked("valid-1") is True
    assert store.is_revoked("expired-1") is False


def test_not_revoked_returns_false() -> None:
    """등록되지 않은 jti → False."""
    store = InMemoryTokenStore()
    assert store.is_revoked("never-registered") is False
