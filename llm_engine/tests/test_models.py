"""callbot.llm_engine.tests.test_models — 데이터 모델 속성 기반 테스트

TDD Red phase: 모델 구현 전에 작성된 테스트.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.llm_engine.enums import VerificationStatus, ScopeType
from callbot.llm_engine.models import LLMResponse, VerificationResult, HallucinationMetrics


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def llm_response_strategy(is_factual: bool | None = None):
    """LLMResponse 생성 전략."""
    if is_factual is None:
        factual = st.booleans()
    else:
        factual = st.just(is_factual)

    return factual.flatmap(lambda f: st.builds(
        LLMResponse,
        text=st.text(min_size=1, max_size=50),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        is_factual=st.just(f),
        requires_verification=st.just(f),  # 불변 조건 준수
        is_legal_required=st.booleans(),
        remaining_legal_info=st.one_of(st.none(), st.text(min_size=1, max_size=30)),
        processing_time_ms=st.integers(min_value=0, max_value=10000),
    ))


def verification_result_pass_strategy():
    """status=PASS VerificationResult 생성 전략."""
    return st.builds(
        VerificationResult,
        status=st.just(VerificationStatus.PASS),
        original_response=st.text(min_size=1, max_size=50),
        final_response=st.text(min_size=1, max_size=50),
        discrepancies=st.lists(st.text(min_size=1), max_size=5),
        processing_time_ms=st.integers(min_value=0, max_value=500),
        is_skipped=st.booleans(),
        block_reason=st.none(),
    )


def verification_result_replaced_strategy():
    """status=REPLACED VerificationResult 생성 전략."""
    return st.text(min_size=1, max_size=50).flatmap(lambda orig: st.builds(
        VerificationResult,
        status=st.just(VerificationStatus.REPLACED),
        original_response=st.just(orig),
        final_response=st.text(min_size=1, max_size=50).filter(lambda r: r != orig),
        discrepancies=st.lists(st.text(min_size=1), min_size=1, max_size=5),
        processing_time_ms=st.integers(min_value=0, max_value=500),
        is_skipped=st.just(False),
        block_reason=st.none(),
    ))


def verification_result_blocked_strategy():
    """status=BLOCKED VerificationResult 생성 전략."""
    return st.builds(
        VerificationResult,
        status=st.just(VerificationStatus.BLOCKED),
        original_response=st.text(min_size=1, max_size=50),
        final_response=st.text(min_size=1, max_size=50),
        discrepancies=st.lists(st.text(min_size=1), max_size=5),
        processing_time_ms=st.integers(min_value=0, max_value=500),
        is_skipped=st.just(False),
        block_reason=st.text(min_size=1, max_size=30),
    )


def hallucination_metrics_strategy():
    """HallucinationMetrics 생성 전략 (불변 조건 준수)."""
    return st.integers(min_value=0, max_value=1000).flatmap(lambda total: (
        st.integers(min_value=0, max_value=total).flatmap(lambda auto_count: (
            st.integers(min_value=0, max_value=1000).flatmap(lambda sample: (
                st.integers(min_value=0, max_value=sample).flatmap(lambda residual_count: st.builds(
                    HallucinationMetrics,
                    period=st.just("weekly"),
                    total_factual_responses=st.just(total),
                    auto_detected_count=st.just(auto_count),
                    auto_hallucination_rate=st.just(
                        auto_count / total if total > 0 else 0.0
                    ),
                    residual_sample_size=st.just(sample),
                    residual_hallucination_count=st.just(residual_count),
                    residual_hallucination_rate=st.just(
                        residual_count / sample if sample > 0 else 0.0
                    ),
                    combined_rate=st.just(
                        (auto_count / total if total > 0 else 0.0)
                        + (residual_count / sample if sample > 0 else 0.0)
                    ),
                ))
            ))
        ))
    ))


# ---------------------------------------------------------------------------
# Property 1: LLMResponse is_factual ↔ requires_verification
# Validates: Requirements 1.5, 3.1
# ---------------------------------------------------------------------------

class TestLLMResponseProperty:
    """**Validates: Requirements 1.5, 3.1**"""

    @given(llm_response_strategy())
    @settings(max_examples=100)
    def test_is_factual_requires_verification_consistency(self, response: LLMResponse):
        """Property 1: is_factual=True ↔ requires_verification=True."""
        assert response.is_factual == response.requires_verification

    def test_is_factual_true_requires_verification_true(self):
        """is_factual=True이면 requires_verification=True."""
        r = LLMResponse(
            text="요금은 55,000원입니다.",
            confidence=0.9,
            is_factual=True,
            requires_verification=True,
            is_legal_required=False,
            remaining_legal_info=None,
            processing_time_ms=100,
        )
        assert r.is_factual is True
        assert r.requires_verification is True

    def test_is_factual_false_requires_verification_false(self):
        """is_factual=False이면 requires_verification=False."""
        r = LLMResponse(
            text="안녕하세요.",
            confidence=0.95,
            is_factual=False,
            requires_verification=False,
            is_legal_required=False,
            remaining_legal_info=None,
            processing_time_ms=80,
        )
        assert r.is_factual is False
        assert r.requires_verification is False

    def test_invariant_violated_raises_value_error(self):
        """is_factual=True, requires_verification=False → ValueError."""
        with pytest.raises(ValueError):
            LLMResponse(
                text="요금은 55,000원입니다.",
                confidence=0.9,
                is_factual=True,
                requires_verification=False,  # 불변 조건 위반
                is_legal_required=False,
                remaining_legal_info=None,
                processing_time_ms=100,
            )

    def test_invariant_violated_false_true_raises_value_error(self):
        """is_factual=False, requires_verification=True → ValueError."""
        with pytest.raises(ValueError):
            LLMResponse(
                text="안녕하세요.",
                confidence=0.9,
                is_factual=False,
                requires_verification=True,  # 불변 조건 위반
                is_legal_required=False,
                remaining_legal_info=None,
                processing_time_ms=100,
            )


# ---------------------------------------------------------------------------
# Property 2-4: VerificationResult 상태 일관성
# Validates: Requirements 3.2, 3.3, 3.4
# ---------------------------------------------------------------------------

class TestVerificationResultProperty:
    """**Validates: Requirements 3.2, 3.3, 3.4**"""

    @given(
        st.booleans().flatmap(lambda skipped: st.builds(
            VerificationResult,
            status=st.just(VerificationStatus.PASS),
            original_response=st.text(min_size=1, max_size=50),
            final_response=st.text(min_size=1, max_size=50),
            discrepancies=st.lists(st.text(min_size=1), max_size=5),
            processing_time_ms=st.integers(min_value=0, max_value=500),
            is_skipped=st.just(skipped),
            block_reason=st.none(),
        ))
    )
    @settings(max_examples=100)
    def test_property2_is_skipped_implies_pass(self, result: VerificationResult):
        """Property 2: is_skipped=True → status=PASS."""
        if result.is_skipped:
            assert result.status == VerificationStatus.PASS

    @given(verification_result_replaced_strategy())
    @settings(max_examples=100)
    def test_property3_replaced_implies_different_response_and_discrepancies(
        self, result: VerificationResult
    ):
        """Property 3: status=REPLACED → final_response != original_response AND len(discrepancies) >= 1."""
        assert result.status == VerificationStatus.REPLACED
        assert result.final_response != result.original_response
        assert len(result.discrepancies) >= 1

    @given(verification_result_blocked_strategy())
    @settings(max_examples=100)
    def test_property4_blocked_implies_block_reason(self, result: VerificationResult):
        """Property 4: status=BLOCKED → block_reason is not None."""
        assert result.status == VerificationStatus.BLOCKED
        assert result.block_reason is not None

    def test_is_skipped_true_must_be_pass(self):
        """is_skipped=True이면 status=PASS여야 한다."""
        r = VerificationResult(
            status=VerificationStatus.PASS,
            original_response="원본",
            final_response="원본",
            discrepancies=[],
            processing_time_ms=10,
            is_skipped=True,
            block_reason=None,
        )
        assert r.is_skipped is True
        assert r.status == VerificationStatus.PASS

    def test_is_skipped_true_with_non_pass_raises(self):
        """is_skipped=True, status=BLOCKED → ValueError."""
        with pytest.raises(ValueError):
            VerificationResult(
                status=VerificationStatus.BLOCKED,
                original_response="원본",
                final_response="원본",
                discrepancies=[],
                processing_time_ms=10,
                is_skipped=True,
                block_reason="확신도_미달",
            )

    def test_replaced_requires_different_response(self):
        """status=REPLACED이면 final_response != original_response."""
        with pytest.raises(ValueError):
            VerificationResult(
                status=VerificationStatus.REPLACED,
                original_response="동일한 응답",
                final_response="동일한 응답",  # 불변 조건 위반
                discrepancies=["금액 불일치"],
                processing_time_ms=100,
                is_skipped=False,
                block_reason=None,
            )

    def test_replaced_requires_discrepancies(self):
        """status=REPLACED이면 len(discrepancies) >= 1."""
        with pytest.raises(ValueError):
            VerificationResult(
                status=VerificationStatus.REPLACED,
                original_response="원본",
                final_response="교체된 응답",
                discrepancies=[],  # 불변 조건 위반
                processing_time_ms=100,
                is_skipped=False,
                block_reason=None,
            )

    def test_blocked_requires_block_reason(self):
        """status=BLOCKED이면 block_reason is not None."""
        with pytest.raises(ValueError):
            VerificationResult(
                status=VerificationStatus.BLOCKED,
                original_response="원본",
                final_response="원본",
                discrepancies=[],
                processing_time_ms=10,
                is_skipped=False,
                block_reason=None,  # 불변 조건 위반
            )


# ---------------------------------------------------------------------------
# Property 5: HallucinationMetrics 환각률 계산 정확성
# Validates: Requirements 3.5, 3.6, 3.7
# ---------------------------------------------------------------------------

class TestHallucinationMetricsProperty:
    """**Validates: Requirements 3.5, 3.6, 3.7**"""

    @given(hallucination_metrics_strategy())
    @settings(max_examples=100)
    def test_property5_rate_calculation_accuracy(self, metrics: HallucinationMetrics):
        """Property 5: 환각률 계산 정확성."""
        if metrics.total_factual_responses > 0:
            expected_auto = metrics.auto_detected_count / metrics.total_factual_responses
            assert abs(metrics.auto_hallucination_rate - expected_auto) < 1e-9

        if metrics.residual_sample_size > 0:
            expected_residual = metrics.residual_hallucination_count / metrics.residual_sample_size
            assert abs(metrics.residual_hallucination_rate - expected_residual) < 1e-9

        expected_combined = metrics.auto_hallucination_rate + metrics.residual_hallucination_rate
        assert abs(metrics.combined_rate - expected_combined) < 1e-9

    def test_auto_rate_calculation(self):
        """total=100, auto_count=3 → auto_rate=0.03."""
        m = HallucinationMetrics(
            period="weekly",
            total_factual_responses=100,
            auto_detected_count=3,
            auto_hallucination_rate=0.03,
            residual_sample_size=300,
            residual_hallucination_count=2,
            residual_hallucination_rate=2 / 300,
            combined_rate=0.03 + 2 / 300,
        )
        assert m.auto_hallucination_rate == pytest.approx(0.03)

    def test_residual_rate_calculation(self):
        """sample=300, residual_count=2 → residual_rate≈0.00667."""
        m = HallucinationMetrics(
            period="weekly",
            total_factual_responses=100,
            auto_detected_count=3,
            auto_hallucination_rate=0.03,
            residual_sample_size=300,
            residual_hallucination_count=2,
            residual_hallucination_rate=2 / 300,
            combined_rate=0.03 + 2 / 300,
        )
        assert m.residual_hallucination_rate == pytest.approx(2 / 300)

    def test_combined_rate_is_sum(self):
        """combined_rate = auto_rate + residual_rate."""
        auto = 0.03
        residual = 2 / 300
        m = HallucinationMetrics(
            period="weekly",
            total_factual_responses=100,
            auto_detected_count=3,
            auto_hallucination_rate=auto,
            residual_sample_size=300,
            residual_hallucination_count=2,
            residual_hallucination_rate=residual,
            combined_rate=auto + residual,
        )
        assert m.combined_rate == pytest.approx(auto + residual)

    def test_invalid_auto_rate_raises(self):
        """잘못된 auto_hallucination_rate → ValueError."""
        with pytest.raises(ValueError):
            HallucinationMetrics(
                period="weekly",
                total_factual_responses=100,
                auto_detected_count=3,
                auto_hallucination_rate=0.05,  # 3/100=0.03이어야 함
                residual_sample_size=300,
                residual_hallucination_count=2,
                residual_hallucination_rate=2 / 300,
                combined_rate=0.05 + 2 / 300,
            )

    def test_invalid_combined_rate_raises(self):
        """잘못된 combined_rate → ValueError."""
        with pytest.raises(ValueError):
            HallucinationMetrics(
                period="weekly",
                total_factual_responses=100,
                auto_detected_count=3,
                auto_hallucination_rate=0.03,
                residual_sample_size=300,
                residual_hallucination_count=2,
                residual_hallucination_rate=2 / 300,
                combined_rate=0.99,  # 잘못된 값
            )

    def test_zero_total_allows_zero_auto_rate(self):
        """total=0이면 auto_rate=0.0 허용."""
        m = HallucinationMetrics(
            period="weekly",
            total_factual_responses=0,
            auto_detected_count=0,
            auto_hallucination_rate=0.0,
            residual_sample_size=0,
            residual_hallucination_count=0,
            residual_hallucination_rate=0.0,
            combined_rate=0.0,
        )
        assert m.auto_hallucination_rate == 0.0
        assert m.combined_rate == 0.0
