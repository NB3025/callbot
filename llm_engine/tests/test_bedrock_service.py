"""Property-based tests for BedrockConfig and RetryPolicy."""
from __future__ import annotations

import json
import logging.handlers
import os
import unittest.mock
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.llm_engine.bedrock_service import (
    BedrockClaudeService,
    BedrockConfig,
    LLMServiceError,
    LLMServiceTimeoutError,
    RetryPolicy,
)

# Feature: callbot-llm-integration, Property 2: 환경변수 기본값 불변성
# Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
_BEDROCK_ENV_KEYS = [
    "BEDROCK_MODEL_ID",
    "BEDROCK_REGION",
    "BEDROCK_TIMEOUT_SECONDS",
    "BEDROCK_MAX_TOKENS",
    "BEDROCK_MAX_RETRIES",
]


@given(st.just(None))
@settings(max_examples=100)
def test_bedrock_config_default_values_invariant(_: None) -> None:
    """환경변수가 없을 때 BedrockConfig.from_env()는 항상 지정된 기본값을 반환한다."""
    env_without_bedrock = {k: v for k, v in os.environ.items() if k not in _BEDROCK_ENV_KEYS}
    with unittest.mock.patch.dict(os.environ, env_without_bedrock, clear=True):
        config = BedrockConfig.from_env()
        assert config.model_id == "anthropic.claude-3-5-haiku-20241022-v1:0"
        assert config.region == "ap-northeast-2"
        assert config.timeout_seconds == 30
        assert config.max_tokens == 16384
        assert config.max_retries == 3


# Feature: callbot-llm-integration, Property 3: 재시도 대기 시간 상한 불변성
# Validates: Requirements 3.2
@given(st.integers(min_value=0, max_value=100))
@settings(max_examples=100)
def test_retry_wait_seconds_upper_bound(n: int) -> None:
    """RetryPolicy.wait_seconds(n)은 모든 n에 대해 3.0을 초과하지 않는다."""
    assert RetryPolicy().wait_seconds(n) <= 3.0


# Feature: callbot-llm-integration, Property 4: 재시도 대기 시간 단조 증가
# Validates: Requirements 3.2
@given(st.integers(min_value=0, max_value=50))
@settings(max_examples=100)
def test_retry_wait_seconds_monotonically_increasing(n: int) -> None:
    """RetryPolicy.wait_seconds는 단조 증가한다: wait(n+1) >= wait(n)."""
    policy = RetryPolicy()
    assert policy.wait_seconds(n + 1) >= policy.wait_seconds(n)


# ── Task 3.2 ──────────────────────────────────────────────────────────────────
# Feature: callbot-llm-integration, Property 1: 스트리밍 청크 누적 round-trip
# Validates: Requirements 1.3, 6.6
@given(chunks=st.lists(st.text(min_size=1), min_size=1))
@settings(max_examples=100)
def test_streaming_chunk_accumulation_roundtrip(chunks):
    """임의 청크 목록이 순서대로 이어붙여진 문자열로 반환된다."""
    events = []
    for chunk_text in chunks:
        events.append({
            "chunk": {
                "bytes": json.dumps({
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": chunk_text}
                }).encode()
            }
        })
    events.append({
        "chunk": {
            "bytes": json.dumps({
                "type": "message_delta",
                "usage": {"inputTokens": 10, "outputTokens": 5}
            }).encode()
        }
    })

    mock_client = MagicMock()
    mock_client.invoke_model_with_response_stream.return_value = {"body": events}

    config = BedrockConfig(
        model_id="test-model", region="us-east-1",
        timeout_seconds=30, max_tokens=100, max_retries=0
    )
    service = BedrockClaudeService(config=config, client=mock_client)
    result = service.generate("system", "user")
    assert result == "".join(chunks)


# ── Task 3.3 ──────────────────────────────────────────────────────────────────
# Feature: callbot-llm-integration, Property 6: system_prompt 페이로드 포함 여부
# Validates: Requirements 1.4, 1.5, 6.5
@given(system_prompt=st.text())
@settings(max_examples=100)
def test_system_prompt_payload_inclusion(system_prompt):
    """비어 있지 않은 system_prompt는 payload의 system 필드에 포함되고, 빈 문자열이면 system 필드가 없다."""
    config = BedrockConfig(
        model_id="test-model", region="us-east-1",
        timeout_seconds=30, max_tokens=100, max_retries=0
    )
    service = BedrockClaudeService(config=config, client=MagicMock())
    payload = service._build_payload(system_prompt, "user message")
    if system_prompt:
        assert "system" in payload
        assert payload["system"] == system_prompt
    else:
        assert "system" not in payload


# ── Task 3.4 ──────────────────────────────────────────────────────────────────
# Feature: callbot-llm-integration, Property 5: 재시도 불가 예외 즉시 실패
# Validates: Requirements 3.4
@given(st.sampled_from(sorted(RetryPolicy.NON_RETRYABLE_CODES)))
@settings(max_examples=100)
def test_non_retryable_error_fails_immediately(error_code):
    """NON_RETRYABLE_CODES 예외는 재시도 없이 즉시 LLMServiceError를 발생시킨다 (호출 횟수=1)."""
    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": error_code, "Message": "test"}}
    mock_client = MagicMock()
    mock_client.invoke_model_with_response_stream.side_effect = ClientError(error_response, "InvokeModel")

    config = BedrockConfig(
        model_id="test-model", region="us-east-1",
        timeout_seconds=30, max_tokens=100, max_retries=3
    )
    service = BedrockClaudeService(config=config, client=mock_client)

    with pytest.raises(LLMServiceError):
        service.generate("system", "user")

    assert mock_client.invoke_model_with_response_stream.call_count == 1


# ── Task 3.5 ──────────────────────────────────────────────────────────────────
def test_generate_returns_text_on_success():
    """정상 응답 시 텍스트를 올바르게 반환한다."""
    events = [
        {"chunk": {"bytes": json.dumps({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "안녕"}}).encode()}},
        {"chunk": {"bytes": json.dumps({"type": "message_delta", "usage": {"inputTokens": 5, "outputTokens": 2}}).encode()}},
    ]
    mock_client = MagicMock()
    mock_client.invoke_model_with_response_stream.return_value = {"body": events}
    config = BedrockConfig(model_id="m", region="r", timeout_seconds=30, max_tokens=100, max_retries=0)
    service = BedrockClaudeService(config=config, client=mock_client)
    assert service.generate("sys", "user") == "안녕"


@patch("callbot.llm_engine.bedrock_service.time.sleep")
def test_throttling_exception_retries_then_raises(mock_sleep):
    """ThrottlingException 발생 시 재시도 후 LLMServiceError를 발생시킨다."""
    from botocore.exceptions import ClientError
    error_response = {"Error": {"Code": "ThrottlingException", "Message": "throttled"}}
    mock_client = MagicMock()
    mock_client.invoke_model_with_response_stream.side_effect = ClientError(error_response, "InvokeModel")
    config = BedrockConfig(model_id="m", region="r", timeout_seconds=30, max_tokens=100, max_retries=2)
    service = BedrockClaudeService(config=config, client=mock_client)
    with pytest.raises(LLMServiceError):
        service.generate("sys", "user")
    assert mock_client.invoke_model_with_response_stream.call_count == 3  # initial + 2 retries


def test_validation_exception_raises_immediately():
    """ValidationException 발생 시 재시도 없이 즉시 LLMServiceError를 발생시킨다."""
    from botocore.exceptions import ClientError
    error_response = {"Error": {"Code": "ValidationException", "Message": "invalid"}}
    mock_client = MagicMock()
    mock_client.invoke_model_with_response_stream.side_effect = ClientError(error_response, "InvokeModel")
    config = BedrockConfig(model_id="m", region="r", timeout_seconds=30, max_tokens=100, max_retries=3)
    service = BedrockClaudeService(config=config, client=mock_client)
    with pytest.raises(LLMServiceError):
        service.generate("sys", "user")
    assert mock_client.invoke_model_with_response_stream.call_count == 1


def test_timeout_raises_llm_service_timeout_error():
    """타임아웃 발생 시 LLMServiceTimeoutError를 발생시킨다."""
    class FakeTimeoutError(Exception):
        pass

    mock_client = MagicMock()
    mock_client.invoke_model_with_response_stream.side_effect = FakeTimeoutError("ReadTimeoutError")
    config = BedrockConfig(model_id="m", region="r", timeout_seconds=30, max_tokens=100, max_retries=0)
    service = BedrockClaudeService(config=config, client=mock_client)
    with pytest.raises(LLMServiceTimeoutError):
        service.generate("sys", "user")


# ── Task 7.1 ──────────────────────────────────────────────────────────────────
# Feature: callbot-llm-integration, Property 9: 토큰 사용량 로그 필드 완전성
# Validates: Requirements 8.1, 8.2
@given(
    input_tokens=st.integers(min_value=0),
    output_tokens=st.integers(min_value=0),
)
@settings(max_examples=100)
def test_token_usage_log_field_completeness(input_tokens: int, output_tokens: int) -> None:
    """generate 성공 시 로깅된 TokenUsage는 model_id, input_tokens, output_tokens, timestamp를 모두 포함한다."""
    import logging
    from callbot.llm_engine.models import TokenUsage

    events = [
        {
            "chunk": {
                "bytes": json.dumps({
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "응답"}
                }).encode()
            }
        },
        {
            "chunk": {
                "bytes": json.dumps({
                    "type": "message_delta",
                    "usage": {"inputTokens": input_tokens, "outputTokens": output_tokens}
                }).encode()
            }
        },
    ]
    mock_client = MagicMock()
    mock_client.invoke_model_with_response_stream.return_value = {"body": events}

    config = BedrockConfig(
        model_id="test-model", region="us-east-1",
        timeout_seconds=30, max_tokens=100, max_retries=0
    )
    service = BedrockClaudeService(config=config, client=mock_client)

    logged_records = []
    handler = logging.handlers.MemoryHandler(capacity=100, flushLevel=logging.CRITICAL)

    class CapturingHandler(logging.Handler):
        def emit(self, record):
            logged_records.append(record)

    capturing = CapturingHandler()
    bedrock_logger = logging.getLogger("callbot.llm_engine.bedrock_service")
    bedrock_logger.addHandler(capturing)
    bedrock_logger.setLevel(logging.INFO)
    try:
        service.generate("system", "user")
    finally:
        bedrock_logger.removeHandler(capturing)

    # 로그 메시지에서 TokenUsage 인스턴스를 찾아 필드 완전성 검증
    token_usage_records = [r for r in logged_records if "token_usage" in r.getMessage()]
    assert len(token_usage_records) >= 1, "token_usage 로그가 기록되지 않았습니다"

    # 로그 args에서 TokenUsage 객체 추출
    record = token_usage_records[0]
    token_usage_obj = record.args[0] if record.args else None
    assert isinstance(token_usage_obj, TokenUsage), f"TokenUsage 인스턴스가 아닙니다: {token_usage_obj}"
    assert token_usage_obj.model_id == "test-model"
    assert token_usage_obj.input_tokens == input_tokens
    assert token_usage_obj.output_tokens == output_tokens
    assert token_usage_obj.timestamp is not None and len(token_usage_obj.timestamp) > 0
