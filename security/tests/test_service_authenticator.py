"""ServiceAuthenticator 속성 기반 테스트 및 단위 테스트."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import jwt
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.security.exceptions import (
    InvalidTokenError,
    RevokedTokenError,
    SecretNotFoundError,
    TokenExpiredError,
)
from callbot.security.secrets_manager import SecretsManager
from callbot.security.service_authenticator import ServiceAuthenticator
from callbot.security.token_store import InMemoryTokenStore

SIGNING_KEY = "test-signing-key-32bytes-pad!!!!"


def _make_mock_sm(signing_key: str = SIGNING_KEY) -> SecretsManager:
    mock_sm = MagicMock(spec=SecretsManager)
    mock_sm.get_secret.return_value = signing_key
    return mock_sm


# ---------------------------------------------------------------------------
# Property 1: JWT 클레임 완전성
# Feature: callbot-security, Property 1: JWT 클레임 완전성
# ---------------------------------------------------------------------------


@given(service_identity=st.text(min_size=1, max_size=50))
@settings(max_examples=100)
def test_property1_jwt_claim_completeness(service_identity: str) -> None:
    """발급된 JWT에 sub, iat, exp, jti 클레임 모두 존재 검증.

    **Validates: Requirements 1.2**
    """
    mock_sm = _make_mock_sm()
    auth = ServiceAuthenticator(mock_sm, InMemoryTokenStore())
    token = auth.issue_token(service_identity)

    payload = jwt.decode(token, SIGNING_KEY, algorithms=["HS256"])
    assert "sub" in payload
    assert "iat" in payload
    assert "exp" in payload
    assert "jti" in payload


# ---------------------------------------------------------------------------
# Property 2: JWT TTL 적용
# Feature: callbot-security, Property 2: JWT TTL 적용
# ---------------------------------------------------------------------------


@given(ttl=st.integers(min_value=1, max_value=86400))
@settings(max_examples=100)
def test_property2_jwt_ttl_applied(ttl: int) -> None:
    """exp - iat == TTL 검증.

    **Validates: Requirements 1.6**
    """
    mock_sm = _make_mock_sm()
    auth = ServiceAuthenticator(mock_sm, InMemoryTokenStore(), jwt_ttl_seconds=ttl)
    token = auth.issue_token("test-service")

    payload = jwt.decode(token, SIGNING_KEY, algorithms=["HS256"])
    assert payload["exp"] - payload["iat"] == ttl


# ---------------------------------------------------------------------------
# Property 3: JWT 발급-검증 라운드트립
# Feature: callbot-security, Property 3: JWT 발급-검증 라운드트립
# ---------------------------------------------------------------------------


@given(service_identity=st.text(min_size=1, max_size=50))
@settings(max_examples=100)
def test_property3_jwt_issue_verify_roundtrip(service_identity: str) -> None:
    """Mock SecretsManager 주입, issue → verify → 동일 service_identity 검증.

    **Validates: Requirements 2.5, 2.6**
    """
    mock_sm = _make_mock_sm()
    store = InMemoryTokenStore()
    auth = ServiceAuthenticator(mock_sm, store)

    token = auth.issue_token(service_identity)
    result = auth.verify_token(token)
    assert result == service_identity


# ---------------------------------------------------------------------------
# Property 4: 폐기된 JWT 검증 거부
# Feature: callbot-security, Property 4: 폐기된 JWT 검증 거부
# ---------------------------------------------------------------------------


@given(service_identity=st.text(min_size=1, max_size=50))
@settings(max_examples=100)
def test_property4_revoked_jwt_rejected(service_identity: str) -> None:
    """issue → revoke → verify 시 RevokedTokenError 검증.

    **Validates: Requirements 3.1, 3.2**
    """
    mock_sm = _make_mock_sm()
    store = InMemoryTokenStore()
    auth = ServiceAuthenticator(mock_sm, store)

    token = auth.issue_token(service_identity)
    auth.revoke(token)

    with pytest.raises(RevokedTokenError):
        auth.verify_token(token)


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------


class TestServiceAuthenticatorUnit:
    """ServiceAuthenticator 단위 테스트."""

    def test_signing_key_not_found_raises_error(self) -> None:
        """서명 키 조회 실패 → SecretNotFoundError (Req 1.4)."""
        mock_sm = MagicMock(spec=SecretsManager)
        mock_sm.get_secret.side_effect = SecretNotFoundError("key not found")
        auth = ServiceAuthenticator(mock_sm, InMemoryTokenStore())

        with pytest.raises(SecretNotFoundError):
            auth.issue_token("some-service")

    def test_default_ttl_is_3600(self) -> None:
        """기본 TTL 3600초 (Req 1.5)."""
        mock_sm = _make_mock_sm()
        auth = ServiceAuthenticator(mock_sm, InMemoryTokenStore())
        token = auth.issue_token("test-service")

        payload = jwt.decode(token, SIGNING_KEY, algorithms=["HS256"])
        assert payload["exp"] - payload["iat"] == 3600

    def test_tampered_jwt_raises_invalid_token(self) -> None:
        """변조된 JWT → InvalidTokenError (Req 2.2)."""
        mock_sm = _make_mock_sm()
        auth = ServiceAuthenticator(mock_sm, InMemoryTokenStore())
        token = auth.issue_token("test-service")

        # 토큰 페이로드 변조
        tampered = token[:-4] + "XXXX"

        with pytest.raises(InvalidTokenError):
            auth.verify_token(tampered)

    def test_expired_jwt_raises_token_expired(self) -> None:
        """만료된 JWT → TokenExpiredError (Req 2.3)."""
        mock_sm = _make_mock_sm()
        auth = ServiceAuthenticator(mock_sm, InMemoryTokenStore(), jwt_ttl_seconds=0)

        # TTL=0이면 발급 즉시 만료
        token = auth.issue_token("test-service")
        # 약간의 시간 경과 보장
        time.sleep(1)

        with pytest.raises(TokenExpiredError):
            auth.verify_token(token)

    def test_revoked_jti_raises_revoked_token(self) -> None:
        """폐기된 jti → RevokedTokenError (Req 2.4)."""
        mock_sm = _make_mock_sm()
        store = InMemoryTokenStore()
        auth = ServiceAuthenticator(mock_sm, store)

        token = auth.issue_token("test-service")
        auth.revoke(token)

        with pytest.raises(RevokedTokenError):
            auth.verify_token(token)
