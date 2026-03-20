"""AnyTelecomHTTPClient 테스트 — PBT + 단위 테스트."""

from __future__ import annotations

import logging
import logging.handlers
import os
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import requests
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.security.exceptions import SecretNotFoundError
from callbot.security.secrets_manager import SecretsManager
from callbot.external.anytelecom_client import AnyTelecomHTTPClient


# ---------------------------------------------------------------------------
# 공통 헬퍼
# ---------------------------------------------------------------------------

valid_system_operation_pairs = [
    ("billing", "요금_조회"),
    ("billing", "납부_확인"),
    ("billing", "요금제_목록_조회"),
    ("billing", "요금제_변경"),
    ("billing", "요금제_변경_롤백"),
    ("customer_db", "고객_식별"),
    ("customer_db", "인증_검증"),
    ("customer_db", "고객_정보_조회"),
]


def _make_client() -> AnyTelecomHTTPClient:
    mock_sm = MagicMock(spec=SecretsManager)
    mock_sm.get_secret.return_value = "test-api-key"
    client = AnyTelecomHTTPClient(
        secrets_manager=mock_sm,
        billing_base_url="https://billing.example.com",
        customer_db_base_url="https://customerdb.example.com",
        cert_provider=None,
        ca_bundle_path=None,
    )
    return client


def _mock_response(status_code: int = 200, json_data: dict | None = None, text: str = "error") -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {"result": "ok"}
    resp.text = text
    elapsed = MagicMock()
    elapsed.total_seconds.return_value = 0.05
    resp.elapsed = elapsed
    return resp


# ---------------------------------------------------------------------------
# Property 3: 필수 HTTP 헤더 포함
# Feature: callbot-external-api-integration, Property 3: 필수 HTTP 헤더 포함
# **Validates: Requirements 2.1, 2.4**
# ---------------------------------------------------------------------------


@given(
    pair=st.sampled_from(valid_system_operation_pairs),
)
@settings(max_examples=100)
def test_required_http_headers_included(pair: tuple[str, str]) -> None:
    """모든 유효한 system/operation에 대해 X-API-Key와 Content-Type 헤더 포함."""
    system, operation = pair
    client = _make_client()

    mock_resp = _mock_response(200)
    client._session = MagicMock()
    client._session.request.return_value = mock_resp

    client.call(system, operation, {}, timeout_sec=5.0)

    call_args = client._session.request.call_args
    headers = call_args.kwargs.get("headers", {})
    assert headers.get("X-API-Key") == "test-api-key", f"X-API-Key missing or wrong: {headers}"
    assert headers.get("Content-Type") == "application/json", f"Content-Type missing or wrong: {headers}"



# ---------------------------------------------------------------------------
# Property 5: HTTP 상태 코드-예외 매핑
# Feature: callbot-external-api-integration, Property 5: HTTP 상태 코드-예외 매핑
# **Validates: Requirements 4.3, 4.4, 4.5**
# ---------------------------------------------------------------------------


@given(status_code=st.integers(min_value=200, max_value=599))
@settings(max_examples=100)
def test_status_code_exception_mapping(status_code: int) -> None:
    """HTTP 상태 코드에 따라 올바른 반환/예외 매핑."""
    client = _make_client()

    mock_resp = _mock_response(status_code)
    client._session = MagicMock()
    client._session.request.return_value = mock_resp

    if 200 <= status_code <= 299:
        result = client.call("billing", "요금_조회", {}, timeout_sec=5.0)
        assert isinstance(result, dict), f"Expected dict for {status_code}, got {type(result)}"
    elif 400 <= status_code <= 499:
        with pytest.raises(ValueError):
            client.call("billing", "요금_조회", {}, timeout_sec=5.0)
    elif 500 <= status_code <= 599:
        with pytest.raises(ConnectionError):
            client.call("billing", "요금_조회", {}, timeout_sec=5.0)


# ---------------------------------------------------------------------------
# Property 11: 요청/응답 구조화 로깅
# Feature: callbot-external-api-integration, Property 11: 요청/응답 구조화 로깅
# **Validates: Requirements 10.1, 10.2**
# ---------------------------------------------------------------------------


@given(pair=st.sampled_from(valid_system_operation_pairs))
@settings(max_examples=100)
def test_structured_logging_request_response(pair: tuple[str, str]) -> None:
    """요청 로그에 HTTP 메서드, URL 경로, 타임아웃 포함. 응답 로그에 상태 코드, 응답 시간(ms) 포함."""
    system, operation = pair
    client = _make_client()

    mock_resp = _mock_response(200)
    client._session = MagicMock()
    client._session.request.return_value = mock_resp

    log_handler = logging.handlers.MemoryHandler(capacity=1024)
    log_handler.setLevel(logging.DEBUG)
    target_logger = logging.getLogger("callbot.external.anytelecom_client")
    target_logger.addHandler(log_handler)
    target_logger.setLevel(logging.DEBUG)
    try:
        client.call(system, operation, {}, timeout_sec=5.0)
        log_text = " ".join(
            log_handler.format(record) for record in log_handler.buffer
        )
    finally:
        target_logger.removeHandler(log_handler)

    # 요청 로그: HTTP 메서드, URL 경로, 타임아웃
    assert "GET" in log_text or "POST" in log_text, f"HTTP method not in log: {log_text}"
    assert "/api/v1/" in log_text, f"URL path not in log: {log_text}"
    assert "5.0" in log_text, f"timeout not in log: {log_text}"

    # 응답 로그: 상태 코드, 응답 시간(ms)
    assert "200" in log_text, f"status code not in log: {log_text}"
    assert "ms" in log_text, f"response time (ms) not in log: {log_text}"



# ---------------------------------------------------------------------------
# 단위 테스트
# Requirements: 1.6, 2.2, 2.3, 4.6, 4.7, 6.6, 6.7, 7.1, 7.2, 7.3, 10.3
# ---------------------------------------------------------------------------


def test_api_key_from_secrets_manager() -> None:
    """SecretsManager에서 API 키 조회 검증."""
    mock_sm = MagicMock(spec=SecretsManager)
    mock_sm.get_secret.return_value = "my-secret-key"
    client = AnyTelecomHTTPClient(
        secrets_manager=mock_sm,
        billing_base_url="https://billing.example.com",
        customer_db_base_url="https://customerdb.example.com",
    )
    mock_sm.get_secret.assert_called_with("callbot/anytelecom-api-key")
    assert client._api_key == "my-secret-key"


def test_api_key_not_found_raises() -> None:
    """API 키 조회 실패 시 SecretNotFoundError."""
    mock_sm = MagicMock(spec=SecretsManager)
    mock_sm.get_secret.side_effect = SecretNotFoundError("not found")
    with pytest.raises(SecretNotFoundError):
        AnyTelecomHTTPClient(
            secrets_manager=mock_sm,
            billing_base_url="https://billing.example.com",
            customer_db_base_url="https://customerdb.example.com",
        )


def test_timeout_raises_timeout_error() -> None:
    """타임아웃 시 TimeoutError 발생."""
    client = _make_client()
    client._session = MagicMock()
    client._session.request.side_effect = requests.Timeout("timed out")

    with pytest.raises(TimeoutError):
        client.call("billing", "요금_조회", {}, timeout_sec=5.0)


def test_connection_failure_raises_connection_error() -> None:
    """연결 실패 시 ConnectionError 발생."""
    client = _make_client()
    client._session = MagicMock()
    client._session.request.side_effect = requests.ConnectionError("connection refused")

    with pytest.raises(ConnectionError):
        client.call("billing", "요금_조회", {}, timeout_sec=5.0)


def test_from_env_missing_billing_url_raises() -> None:
    """CALLBOT_BILLING_API_BASE_URL 미설정 시 ValueError."""
    mock_sm = MagicMock(spec=SecretsManager)
    mock_sm.get_secret.return_value = "key"
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="CALLBOT_BILLING_API_BASE_URL"):
            AnyTelecomHTTPClient.from_env(mock_sm)


def test_from_env_missing_customer_db_url_raises() -> None:
    """CALLBOT_CUSTOMER_DB_API_BASE_URL 미설정 시 ValueError."""
    mock_sm = MagicMock(spec=SecretsManager)
    mock_sm.get_secret.return_value = "key"
    env = {"CALLBOT_BILLING_API_BASE_URL": "https://billing.example.com"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="CALLBOT_CUSTOMER_DB_API_BASE_URL"):
            AnyTelecomHTTPClient.from_env(mock_sm)


def test_health_check_success() -> None:
    """양쪽 /health 성공 시 {"billing": True, "customer_db": True}."""
    client = _make_client()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    client._session = MagicMock()
    client._session.get.return_value = mock_resp

    result = client.health_check()
    assert result == {"billing": True, "customer_db": True}


def test_health_check_failure_logs_and_raises(caplog) -> None:
    """헬스체크 실패 시 로깅 후 예외 전파."""
    client = _make_client()
    client._session = MagicMock()
    client._session.get.side_effect = requests.ConnectionError("refused")

    with caplog.at_level(logging.ERROR, logger="callbot.external.anytelecom_client"):
        with pytest.raises(requests.ConnectionError):
            client.health_check()

    assert "Health check failed" in caplog.text


def test_error_response_logged(caplog) -> None:
    """실패 시 에러 유형과 메시지 로깅 검증."""
    client = _make_client()
    mock_resp = _mock_response(500, text="Internal Server Error")
    client._session = MagicMock()
    client._session.request.return_value = mock_resp

    with caplog.at_level(logging.ERROR, logger="callbot.external.anytelecom_client"):
        with pytest.raises(ConnectionError):
            client.call("billing", "요금_조회", {}, timeout_sec=5.0)

    assert "500" in caplog.text or "ConnectionError" in caplog.text or "error" in caplog.text.lower()
