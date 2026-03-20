"""callbot.llm_engine.bedrock_service — AWS Bedrock Claude 연동 서비스"""
from __future__ import annotations

import datetime
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import boto3

from callbot.llm_engine.llm_engine import LLMServiceBase
from callbot.llm_engine.models import TokenUsage

logger = logging.getLogger(__name__)


@dataclass
class BedrockConfig:
    """AWS Bedrock 설정값 (환경변수 기반).

    Attributes:
        model_id: 사용할 Bedrock 모델 ID
        region: AWS 리전
        timeout_seconds: API 호출 타임아웃 (초)
        max_tokens: 최대 출력 토큰 수
        max_retries: 최대 재시도 횟수
    """
    model_id: str
    region: str
    timeout_seconds: int
    max_tokens: int
    max_retries: int

    @classmethod
    def from_env(cls) -> "BedrockConfig":
        """환경변수에서 설정값을 읽어 BedrockConfig 인스턴스를 생성한다."""
        return cls(
            model_id=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0"),
            region=os.environ.get("BEDROCK_REGION", "ap-northeast-2"),
            timeout_seconds=int(os.environ.get("BEDROCK_TIMEOUT_SECONDS", "30")),
            max_tokens=int(os.environ.get("BEDROCK_MAX_TOKENS", "16384")),
            max_retries=int(os.environ.get("BEDROCK_MAX_RETRIES", "3")),
        )


class RetryPolicy:
    """재시도 정책: 지수 백오프 대기 시간 및 재시도 가능 여부 판단."""

    NON_RETRYABLE_CODES: frozenset = frozenset({"ValidationException", "AccessDeniedException"})
    RETRYABLE_CODES: frozenset = frozenset({"ThrottlingException", "ServiceUnavailableException"})

    def wait_seconds(self, attempt: int) -> float:
        """재시도 대기 시간 계산: min(1.0 × 2^attempt, 3.0)."""
        return min(1.0 * (2 ** attempt), 3.0)

    def is_retryable(self, error_code: str) -> bool:
        """error_code가 재시도 가능한 예외인지 반환한다."""
        return error_code in self.RETRYABLE_CODES


class LLMServiceError(Exception):
    """AWS SDK 예외 래퍼. 원인 예외(cause)와 오류 메시지를 포함한다."""

    def __init__(self, message: str, cause: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.cause = cause


class LLMServiceTimeoutError(LLMServiceError):
    """API 호출 타임아웃 예외."""


class BedrockClaudeService(LLMServiceBase):
    """AWS Bedrock Claude 스트리밍 서비스."""

    def __init__(self, config=None, client=None):
        self._config = config or BedrockConfig.from_env()
        self._client = client or boto3.client(
            "bedrock-runtime",
            region_name=self._config.region,
        )
        self._retry_policy = RetryPolicy()

    def generate(self, system_prompt: str, user_message: str) -> str:
        payload = self._build_payload(system_prompt, user_message)
        return self._invoke_with_retry(payload)

    def _build_payload(self, system_prompt: str, user_message: str) -> dict:
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self._config.max_tokens,
            "messages": [{"role": "user", "content": user_message}],
        }
        if system_prompt:
            payload["system"] = system_prompt
        return payload

    def _extract_text(self, stream_response: dict) -> str:
        text_parts = []
        usage = {}
        for event in stream_response["body"]:
            chunk = json.loads(event["chunk"]["bytes"])
            chunk_type = chunk.get("type")
            if chunk_type == "content_block_delta":
                delta = chunk.get("delta", {})
                if delta.get("type") == "text_delta":
                    text_parts.append(delta.get("text", ""))
            elif chunk_type == "message_delta":
                usage = chunk.get("usage", {})
        if not text_parts:
            raise LLMServiceError("응답에서 텍스트를 추출할 수 없습니다.")
        self._log_token_usage(usage)
        return "".join(text_parts)

    def _log_token_usage(self, usage: dict) -> None:
        try:
            token_usage = TokenUsage(
                model_id=self._config.model_id,
                input_tokens=usage["inputTokens"],
                output_tokens=usage["outputTokens"],
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
            logger.info("token_usage: %s", token_usage)
        except (KeyError, TypeError) as e:
            logger.warning("토큰 사용량 추출 실패: %s", e)

    def _invoke_with_retry(self, payload: dict) -> str:
        from botocore.exceptions import ClientError

        last_error = None
        for attempt in range(self._config.max_retries + 1):
            try:
                response = self._client.invoke_model_with_response_stream(
                    modelId=self._config.model_id,
                    body=json.dumps(payload),
                )
                return self._extract_text(response)
            except Exception as e:
                # Timeout check
                if "Timeout" in type(e).__name__ or "timeout" in str(e).lower():
                    raise LLMServiceTimeoutError("API 호출 타임아웃", cause=e) from e

                # Extract error code for ClientError
                if isinstance(e, ClientError):
                    error_code = e.response["Error"]["Code"]
                else:
                    error_code = type(e).__name__

                # Non-retryable
                if error_code in self._retry_policy.NON_RETRYABLE_CODES:
                    raise LLMServiceError(f"재시도 불가 오류: {error_code}", cause=e) from e

                # Retryable
                if error_code in self._retry_policy.RETRYABLE_CODES:
                    last_error = e
                    if attempt < self._config.max_retries:
                        wait = self._retry_policy.wait_seconds(attempt)
                        time.sleep(wait)
                        continue
                    raise LLMServiceError(f"최대 재시도 횟수 초과: {error_code}", cause=e) from e

                # Unknown
                raise LLMServiceError(f"알 수 없는 오류: {e}", cause=e) from e

        raise LLMServiceError("최대 재시도 횟수 초과", cause=last_error)
