"""callbot.llm_engine.models — LLM 엔진 핵심 데이터 모델"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from callbot.llm_engine.enums import VerificationStatus

# 기본 확신도 임계값
CONFIDENCE_THRESHOLD = 0.7


@dataclass
class LLMResponse:
    """LLM 엔진 응답.

    Invariants:
    - is_factual=True  ↔  requires_verification=True
    - is_factual=False ↔  requires_verification=False
    """
    text: str
    confidence: float
    is_factual: bool
    requires_verification: bool
    is_legal_required: bool
    remaining_legal_info: Optional[str]
    processing_time_ms: int

    def __post_init__(self) -> None:
        if self.is_factual != self.requires_verification:
            raise ValueError(
                f"is_factual({self.is_factual}) must equal requires_verification({self.requires_verification})"
            )


@dataclass
class VerificationResult:
    """환각 검증기 결과.

    Invariants:
    - status=REPLACED → final_response != original_response AND len(discrepancies) >= 1
    - status=BLOCKED  → block_reason is not None
    - is_skipped=True → status=PASS
    """
    status: VerificationStatus
    original_response: str
    final_response: str
    discrepancies: list[str]
    processing_time_ms: int
    is_skipped: bool
    block_reason: Optional[str]

    def __post_init__(self) -> None:
        if self.is_skipped and self.status != VerificationStatus.PASS:
            raise ValueError(
                f"is_skipped=True requires status=PASS, got status={self.status}"
            )
        if self.status == VerificationStatus.REPLACED:
            if self.final_response == self.original_response:
                raise ValueError(
                    "status=REPLACED requires final_response != original_response"
                )
            if len(self.discrepancies) < 1:
                raise ValueError(
                    "status=REPLACED requires len(discrepancies) >= 1"
                )
        if self.status == VerificationStatus.BLOCKED and self.block_reason is None:
            raise ValueError(
                "status=BLOCKED requires block_reason is not None"
            )


@dataclass
class HallucinationMetrics:
    """환각률 측정 지표.

    Invariants:
    - total_factual_responses > 0 → auto_hallucination_rate == auto_detected_count / total_factual_responses
    - residual_sample_size > 0    → residual_hallucination_rate == residual_hallucination_count / residual_sample_size
    - combined_rate == auto_hallucination_rate + residual_hallucination_rate
    """
    period: str
    total_factual_responses: int
    auto_detected_count: int
    auto_hallucination_rate: float
    residual_sample_size: int
    residual_hallucination_count: int
    residual_hallucination_rate: float
    combined_rate: float

    _TOLERANCE = 1e-9

    def __post_init__(self) -> None:
        if self.total_factual_responses > 0:
            expected = self.auto_detected_count / self.total_factual_responses
            if abs(self.auto_hallucination_rate - expected) > self._TOLERANCE:
                raise ValueError(
                    f"auto_hallucination_rate({self.auto_hallucination_rate}) != "
                    f"auto_detected_count/total_factual_responses({expected})"
                )
        if self.residual_sample_size > 0:
            expected = self.residual_hallucination_count / self.residual_sample_size
            if abs(self.residual_hallucination_rate - expected) > self._TOLERANCE:
                raise ValueError(
                    f"residual_hallucination_rate({self.residual_hallucination_rate}) != "
                    f"residual_hallucination_count/residual_sample_size({expected})"
                )
        expected_combined = self.auto_hallucination_rate + self.residual_hallucination_rate
        if abs(self.combined_rate - expected_combined) > self._TOLERANCE:
            raise ValueError(
                f"combined_rate({self.combined_rate}) != "
                f"auto_hallucination_rate + residual_hallucination_rate({expected_combined})"
            )


@dataclass
class TokenUsage:
    """LLM 토큰 사용량 기록.

    Attributes:
        model_id: 사용된 모델 식별자
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        timestamp: ISO 8601 형식의 타임스탬프
    """
    model_id: str
    input_tokens: int
    output_tokens: int
    timestamp: str
