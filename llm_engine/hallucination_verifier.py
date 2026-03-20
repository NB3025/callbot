"""callbot.llm_engine.hallucination_verifier — 환각_검증기 구현"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from callbot.llm_engine.enums import VerificationStatus
from callbot.llm_engine.models import LLMResponse, VerificationResult
from callbot.session.models import SessionContext

_DEFAULT_THRESHOLD = 0.7
_THRESHOLD_MIN = 0.5
_THRESHOLD_MAX = 0.9

_REPLACED_TEMPLATE = "죄송합니다, 정확한 정보를 안내해 드리겠습니다. {db_summary}"


class DBServiceBase(ABC):
    @abstractmethod
    def query(self, key: str) -> dict: ...


class MockDBService(DBServiceBase):
    def __init__(self, data: dict = None, raise_error: bool = False) -> None:
        self.data = data or {}
        self.raise_error = raise_error

    def query(self, key: str) -> dict:
        if self.raise_error:
            raise RuntimeError("DB 장애")
        return self.data.get(key, {})


class HallucinationVerifier:
    """LLM 답변 환각 검증기."""

    def __init__(
        self,
        confidence_threshold: float = _DEFAULT_THRESHOLD,
        db_service: Optional[DBServiceBase] = None,
    ) -> None:
        if not (_THRESHOLD_MIN <= confidence_threshold <= _THRESHOLD_MAX):
            raise ValueError(
                f"confidence_threshold must be in [{_THRESHOLD_MIN}, {_THRESHOLD_MAX}], "
                f"got {confidence_threshold}"
            )
        self.confidence_threshold = confidence_threshold
        self.db_service = db_service

    def verify(
        self,
        llm_response: LLMResponse,
        session: SessionContext,
        cached_data: Optional[dict] = None,
    ) -> VerificationResult:
        """LLM 답변 교차 검증.

        Step 1: 확신도 임계값 검증 (is_factual 여부 무관)
          - confidence < confidence_threshold -> BLOCKED, block_reason="확신도_미달"
        Step 2: is_factual 분기
          - is_factual=False -> PASS, is_skipped=True
          - is_factual=True  -> DB 교차 검증
        """
        # Step 1
        if llm_response.confidence < self.confidence_threshold:
            return VerificationResult(
                status=VerificationStatus.BLOCKED,
                original_response=llm_response.text,
                final_response=llm_response.text,
                discrepancies=[],
                processing_time_ms=0,
                is_skipped=False,
                block_reason="확신도_미달",
            )

        # Step 2: non-factual bypass
        if not llm_response.is_factual:
            return VerificationResult(
                status=VerificationStatus.PASS,
                original_response=llm_response.text,
                final_response=llm_response.text,
                discrepancies=[],
                processing_time_ms=0,
                is_skipped=True,
                block_reason=None,
            )

        # Step 2: factual — DB cross-validation
        if cached_data is None and self.db_service is not None:
            try:
                fetched = self.db_service.query(session.session_id)
                cached_data = {session.session_id: fetched} if fetched else {}
            except Exception:
                return VerificationResult(
                    status=VerificationStatus.BLOCKED,
                    original_response=llm_response.text,
                    final_response=llm_response.text,
                    discrepancies=[],
                    processing_time_ms=0,
                    is_skipped=False,
                    block_reason="DB_장애",
                )

        discrepancies = self._cross_validate(llm_response.text, cached_data)

        if discrepancies:
            final_response = _REPLACED_TEMPLATE.format(db_summary=discrepancies[0])
            return VerificationResult(
                status=VerificationStatus.REPLACED,
                original_response=llm_response.text,
                final_response=final_response,
                discrepancies=discrepancies,
                processing_time_ms=0,
                is_skipped=False,
                block_reason=None,
            )

        return VerificationResult(
            status=VerificationStatus.PASS,
            original_response=llm_response.text,
            final_response=llm_response.text,
            discrepancies=[],
            processing_time_ms=0,
            is_skipped=False,
            block_reason=None,
        )

    def _cross_validate(
        self, llm_response_text: str, cached_data: Optional[dict]
    ) -> list[str]:
        """DB 데이터와 LLM 응답 교차 검증. 불일치 설명 목록 반환."""
        if not cached_data:
            return []

        discrepancies: list[str] = []
        for key, data in cached_data.items():
            if not isinstance(data, dict):
                continue
            for field, value in data.items():
                if isinstance(value, (int, float)):
                    str_plain = str(value)
                    str_formatted = f"{value:,}" if isinstance(value, int) else f"{value:,}"
                    if str_plain not in llm_response_text and str_formatted not in llm_response_text:
                        discrepancies.append(
                            f"{key}.{field}: expected {value}, not found in response"
                        )
        return discrepancies

    def get_hallucination_metrics(
        self,
        period: str = "weekly",
        total_factual_responses: int = 0,
        auto_detected_count: int = 0,
        residual_sample_size: int = 0,
        residual_hallucination_count: int = 0,
    ):
        from callbot.llm_engine.models import HallucinationMetrics
        auto_hallucination_rate = (
            auto_detected_count / total_factual_responses
            if total_factual_responses > 0 else 0.0
        )
        residual_hallucination_rate = (
            residual_hallucination_count / residual_sample_size
            if residual_sample_size > 0 else 0.0
        )
        combined_rate = auto_hallucination_rate + residual_hallucination_rate
        return HallucinationMetrics(
            period=period,
            total_factual_responses=total_factual_responses,
            auto_detected_count=auto_detected_count,
            auto_hallucination_rate=auto_hallucination_rate,
            residual_sample_size=residual_sample_size,
            residual_hallucination_count=residual_hallucination_count,
            residual_hallucination_rate=residual_hallucination_rate,
            combined_rate=combined_rate,
        )
