"""RedisSessionStore 단위 테스트 및 속성 기반 테스트 (Mock Redis)"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings

from callbot.session.exceptions import RedisConnectionError
from callbot.session.redis_session_store import RedisSessionStore
from callbot.session.tests.conftest import session_contexts


# ---------------------------------------------------------------------------
# dict 기반 Mock Redis (PBT 루프 내 I/O 없음)
# ---------------------------------------------------------------------------

class DictRedis:
    """dict 기반 Mock Redis — PBT에서 실제 I/O 없이 사용."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def set(self, key, value, ex=None):
        self._store[key] = value

    def get(self, key):
        return self._store.get(key)

    def delete(self, key):
        self._store.pop(key, None)

    def exists(self, key):
        return 1 if key in self._store else 0

    def ping(self):
        return True


# ---------------------------------------------------------------------------
# Property 4: RedisSessionStore save-load 라운드트립 (Mock Redis)
# Validates: Requirements 4.1, 4.6
# ---------------------------------------------------------------------------

@given(ctx=session_contexts())
@settings(max_examples=100)
def test_property_save_load_roundtrip(ctx):
    """**Validates: Requirements 4.1, 4.6**

    For any valid SessionContext, save → load returns an equal SessionContext.
    """
    store = RedisSessionStore(redis_client=DictRedis(), ttl_seconds=1200)
    store.save(ctx)
    loaded = store.load(ctx.session_id)
    assert loaded == ctx


# ---------------------------------------------------------------------------
# Property 5: RedisSessionStore save 시 TTL 설정
# Validates: Requirements 4.3, 4.4, 4.5
# ---------------------------------------------------------------------------

@given(ctx=session_contexts())
@settings(max_examples=100)
def test_property_save_sets_ttl(ctx):
    """**Validates: Requirements 4.3, 4.4, 4.5**

    For any valid SessionContext and positive TTL, save passes the TTL to Redis SET.
    """
    mock_redis = MagicMock()
    ttl = 900
    store = RedisSessionStore(redis_client=mock_redis, ttl_seconds=ttl)
    store.save(ctx)

    mock_redis.set.assert_called_once()
    call_kwargs = mock_redis.set.call_args
    # Verify key format
    assert call_kwargs[0][0] == f"callbot:session:{ctx.session_id}"
    # Verify TTL passed via ex keyword
    assert call_kwargs[1]["ex"] == ttl


# ---------------------------------------------------------------------------
# 단위 테스트 (Task 8.4)
# ---------------------------------------------------------------------------

class TestRedisSessionStoreUnit:
    """RedisSessionStore 단위 테스트."""

    def test_key_format(self):
        """_key() → callbot:session:{id} (Req 4.2)"""
        store = RedisSessionStore(redis_client=DictRedis())
        assert store._key("abc-123") == "callbot:session:abc-123"

    def test_default_ttl_is_1200(self):
        """기본 TTL 1200초 (Req 4.4)"""
        store = RedisSessionStore(redis_client=DictRedis())
        assert store._ttl == 1200

    def test_save_redis_error_raises_redis_connection_error(self):
        """SET 실패 → RedisConnectionError (Req 4.9)"""
        mock_redis = MagicMock()
        mock_redis.set.side_effect = ConnectionError("connection refused")
        store = RedisSessionStore(redis_client=mock_redis)

        from callbot.session.models import SessionContext
        from callbot.session.enums import AuthStatus
        from datetime import datetime

        ctx = SessionContext(
            session_id="test-id",
            caller_id="010",
            is_authenticated=False,
            customer_info=None,
            auth_status=AuthStatus.NOT_ATTEMPTED,
            turns=[],
            business_turn_count=0,
            start_time=datetime(2025, 1, 1),
            tts_speed_factor=1.0,
            cached_billing_data=None,
            injection_detection_count=0,
            masking_restore_failure_count=0,
            plan_list_context=None,
            pending_intent=None,
            pending_classification=None,
        )
        with pytest.raises(RedisConnectionError):
            store.save(ctx)

    def test_load_redis_error_raises_redis_connection_error(self):
        """GET 실패 → RedisConnectionError (Req 4.9)"""
        mock_redis = MagicMock()
        mock_redis.get.side_effect = ConnectionError("connection refused")
        store = RedisSessionStore(redis_client=mock_redis)

        with pytest.raises(RedisConnectionError):
            store.load("some-id")

    def test_load_nonexistent_returns_none(self):
        """GET → None 시 None 반환 (Req 4.6)"""
        store = RedisSessionStore(redis_client=DictRedis())
        assert store.load("nonexistent") is None

    def test_delete_calls_redis_del(self):
        """DEL 호출 검증 (Req 4.7)"""
        mock_redis = MagicMock()
        store = RedisSessionStore(redis_client=mock_redis)
        store.delete("sess-1")
        mock_redis.delete.assert_called_once_with("callbot:session:sess-1")

    def test_exists_calls_redis_exists(self):
        """EXISTS 호출 검증 (Req 4.8)"""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1
        store = RedisSessionStore(redis_client=mock_redis)
        result = store.exists("sess-1")
        mock_redis.exists.assert_called_once_with("callbot:session:sess-1")
        assert result is True

    def test_health_check_success(self):
        """PING 성공 → True (Req 7.2)"""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        store = RedisSessionStore(redis_client=mock_redis)
        assert store.health_check() is True

    def test_health_check_failure(self):
        """PING 실패 → False (Req 7.3)"""
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = ConnectionError("connection refused")
        store = RedisSessionStore(redis_client=mock_redis)
        assert store.health_check() is False
