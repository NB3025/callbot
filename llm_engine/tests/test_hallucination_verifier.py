"""callbot.llm_engine.tests.test_hallucination_verifier — 환각_검증기 단위 테스트

TDD Red phase: 구현 전에 작성된 테스트.
**Validates: Requirements 2.1, 2.2, 2.3, 2.5, 2.8, 2.10**
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.llm_engine.enums import VerificationStatus
from callbot.llm_engine.models import LLMResponse, VerificationResult
from callbot.llm_engine.hallucination_verifier import HallucinationVerifier, MockDBService
from callbot.session.models import SessionContext
from callbot.session.enums import AuthStatus
from datetime import datetime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def verifier() -> HallucinationVerifier:
    return HallucinationVerifier(confidence_threshold=0.7)


@pytest.fixture
def session() -> SessionContext:
    return SessionContext(
        session_id="test-session-001",
        caller_id="010-1234-5678",
        is_authenticated=True,
        customer_info=None,
        auth_status=AuthStatus.SUCCESS,
        turns=[],
        business_turn_count=0,
        start_time=datetime.now(),
        tts_speed_factor=1.0,
        cached_billing_data=None,
        injection_detection_count=0,
        masking_restore_failure_count=0,
        plan_list_context=None,
        pending_intent=None,
        pending_classification=None,
    )


def make_llm_response(
    confidence: float,
    is_factual: bool = True,
    text: str = "요금은 55,000원입니다.",
) -> LLMResponse:
    return LLMResponse(
        text=text,
        confidence=confidence,
        is_factual=is_factual,
        requires_verification=is_factual,
        is_legal_required=False,
        remaining_legal_info=None,
        processing_time_ms=100,
    )


# ---------------------------------------------------------------------------
# Task 7: confidence_threshold 유효성 검증
# ---------------------------------------------------------------------------

class TestConfidenceThresholdValidation:
    """confidence_threshold 범위 [0.5, 0.9] 검증."""

    def test_valid_threshold_0_5(self):
        v = HallucinationVerifier(confidence_threshold=0.5)
        assert v.confidence_threshold == 0.5

    def test_valid_threshold_0_7(self):
        v = HallucinationVerifier(confidence_threshold=0.7)
        assert v.confidence_threshold == 0.7

    def test_valid_threshold_0_9(self):
        v = HallucinationVerifier(confidence_threshold=0.9)
        assert v.confidence_threshold == 0.9

    def test_threshold_below_0_5_raises(self):
        with pytest.raises(ValueError):
            HallucinationVerifier(confidence_threshold=0.49)

    def test_threshold_above_0_9_raises(self):
        with pytest.raises(ValueError):
            HallucinationVerifier(confidence_threshold=0.91)

    def test_threshold_0_0_raises(self):
        with pytest.raises(ValueError):
            HallucinationVerifier(confidence_threshold=0.0)

    def test_threshold_1_0_raises(self):
        with pytest.raises(ValueError):
            HallucinationVerifier(confidence_threshold=1.0)

    def test_default_threshold_is_0_7(self):
        v = HallucinationVerifier()
        assert v.confidence_threshold == 0.7


# ---------------------------------------------------------------------------
# Task 7.1: Property 6 — 확신도 미달 시 반드시 BLOCKED
# **Validates: Requirements 2.2**
# ---------------------------------------------------------------------------

class TestConfidenceThresholdBlocking:
    """확신도 임계값 경계 단위 테스트."""

    def test_confidence_below_threshold_is_blocked(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """threshold=0.7, confidence=0.699 → BLOCKED."""
        response = make_llm_response(confidence=0.699)
        result = verifier.verify(response, session)
        assert result.status == VerificationStatus.BLOCKED

    def test_confidence_equal_threshold_is_not_blocked(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """threshold=0.7, confidence=0.7 → NOT BLOCKED (passes step 1)."""
        response = make_llm_response(confidence=0.7)
        result = verifier.verify(response, session)
        assert result.status != VerificationStatus.BLOCKED

    def test_confidence_above_threshold_is_not_blocked(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """threshold=0.7, confidence=0.701 → NOT BLOCKED."""
        response = make_llm_response(confidence=0.701)
        result = verifier.verify(response, session)
        assert result.status != VerificationStatus.BLOCKED

    def test_is_factual_true_confidence_below_threshold_is_blocked(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """is_factual=True, confidence < threshold → BLOCKED."""
        response = make_llm_response(confidence=0.5, is_factual=True)
        result = verifier.verify(response, session)
        assert result.status == VerificationStatus.BLOCKED

    def test_is_factual_false_confidence_below_threshold_is_blocked(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """is_factual=False, confidence < threshold → BLOCKED (is_factual doesn't matter for step 1)."""
        response = make_llm_response(confidence=0.5, is_factual=False)
        result = verifier.verify(response, session)
        assert result.status == VerificationStatus.BLOCKED

    def test_block_reason_is_confidence_insufficient_when_blocked(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """BLOCKED 시 block_reason은 '확신도_미달'이어야 한다."""
        response = make_llm_response(confidence=0.3)
        result = verifier.verify(response, session)
        assert result.status == VerificationStatus.BLOCKED
        assert result.block_reason == "확신도_미달"

    def test_blocked_result_has_original_response(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """BLOCKED 결과에 original_response가 포함된다."""
        response = make_llm_response(confidence=0.3, text="요금은 55,000원입니다.")
        result = verifier.verify(response, session)
        assert result.original_response == "요금은 55,000원입니다."


# ---------------------------------------------------------------------------
# Task 7.1: Property 6 — Hypothesis 속성 테스트
# **Validates: Requirements 2.2**
# ---------------------------------------------------------------------------

def llm_response_below_threshold_strategy(threshold: float = 0.7):
    """confidence < threshold인 LLMResponse 생성 전략."""
    is_factual = st.booleans()
    return is_factual.flatmap(lambda f: st.builds(
        LLMResponse,
        text=st.text(min_size=1, max_size=50),
        confidence=st.floats(min_value=0.0, max_value=threshold - 1e-10, allow_nan=False),
        is_factual=st.just(f),
        requires_verification=st.just(f),
        is_legal_required=st.booleans(),
        remaining_legal_info=st.none(),
        processing_time_ms=st.integers(min_value=0, max_value=10000),
    ))


class TestProperty6ConfidenceBelowThresholdAlwaysBlocked:
    """**Property 6: 확신도 미달 시 반드시 BLOCKED**
    **Validates: Requirements 2.2**
    """

    @given(llm_response_below_threshold_strategy(threshold=0.7))
    @settings(max_examples=100)
    def test_any_response_below_threshold_is_blocked(self, llm_response: LLMResponse):
        """For any LLMResponse with confidence < threshold → verify() returns status=BLOCKED."""
        session = SessionContext(
            session_id="prop-test-session",
            caller_id="010-0000-0000",
            is_authenticated=True,
            customer_info=None,
            auth_status=AuthStatus.SUCCESS,
            turns=[],
            business_turn_count=0,
            start_time=datetime.now(),
            tts_speed_factor=1.0,
            cached_billing_data=None,
            injection_detection_count=0,
            masking_restore_failure_count=0,
            plan_list_context=None,
            pending_intent=None,
            pending_classification=None,
        )
        verifier = HallucinationVerifier(confidence_threshold=0.7)
        result = verifier.verify(llm_response, session)
        assert result.status == VerificationStatus.BLOCKED
        assert result.block_reason == "확신도_미달"


# ---------------------------------------------------------------------------
# Task 8.1: Property 7 — 비사실 기반 답변 검증 우회
# **Validates: Requirements 2.3**
# ---------------------------------------------------------------------------

class TestNonFactualResponseBypass:
    """is_factual=False, confidence >= threshold → PASS, is_skipped=True."""

    def test_non_factual_response_is_skipped(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """is_factual=False, confidence=0.9 → status=PASS, is_skipped=True."""
        response = make_llm_response(confidence=0.9, is_factual=False, text="안녕하세요.")
        result = verifier.verify(response, session)
        assert result.status == VerificationStatus.PASS
        assert result.is_skipped is True

    def test_non_factual_response_at_threshold_is_skipped(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """is_factual=False, confidence=0.7 (exactly at threshold) → PASS, is_skipped=True."""
        response = make_llm_response(confidence=0.7, is_factual=False, text="안녕하세요.")
        result = verifier.verify(response, session)
        assert result.status == VerificationStatus.PASS
        assert result.is_skipped is True


def llm_response_non_factual_above_threshold_strategy(threshold: float = 0.7):
    """is_factual=False, confidence >= threshold인 LLMResponse 생성 전략."""
    return st.builds(
        LLMResponse,
        text=st.text(min_size=1, max_size=50),
        confidence=st.floats(min_value=threshold, max_value=1.0, allow_nan=False),
        is_factual=st.just(False),
        requires_verification=st.just(False),
        is_legal_required=st.booleans(),
        remaining_legal_info=st.none(),
        processing_time_ms=st.integers(min_value=0, max_value=10000),
    )


class TestProperty7NonFactualAlwaysBypass:
    """**Property 7: 비사실 기반 답변 검증 우회**
    **Validates: Requirements 2.3**
    """

    @given(llm_response_non_factual_above_threshold_strategy(threshold=0.7))
    @settings(max_examples=100)
    def test_any_non_factual_above_threshold_is_pass_skipped(self, llm_response: LLMResponse):
        """For any is_factual=False with confidence >= threshold → PASS + is_skipped=True."""
        session = SessionContext(
            session_id="prop7-session",
            caller_id="010-0000-0000",
            is_authenticated=True,
            customer_info=None,
            auth_status=AuthStatus.SUCCESS,
            turns=[],
            business_turn_count=0,
            start_time=datetime.now(),
            tts_speed_factor=1.0,
            cached_billing_data=None,
            injection_detection_count=0,
            masking_restore_failure_count=0,
            plan_list_context=None,
            pending_intent=None,
            pending_classification=None,
        )
        verifier = HallucinationVerifier(confidence_threshold=0.7)
        result = verifier.verify(llm_response, session)
        assert result.status == VerificationStatus.PASS
        assert result.is_skipped is True


# ---------------------------------------------------------------------------
# Task 8.2: 불일치 감지 교체 테스트
# **Validates: Requirements 2.5**
# ---------------------------------------------------------------------------

class TestDiscrepancyDetectionReplaced:
    """LLM 답변 금액 ≠ DB 실제 금액 → status=REPLACED."""

    def test_amount_discrepancy_returns_replaced(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """cached_data amount=55000, LLM says '45,000원' → REPLACED."""
        cached_data = {"billing_202607": {"amount": 55000}}
        response = make_llm_response(
            confidence=0.9, is_factual=True, text="요금은 45,000원입니다."
        )
        result = verifier.verify(response, session, cached_data=cached_data)
        assert result.status == VerificationStatus.REPLACED

    def test_replaced_final_response_differs_from_original(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """REPLACED 시 final_response != original_response."""
        cached_data = {"billing_202607": {"amount": 55000}}
        response = make_llm_response(
            confidence=0.9, is_factual=True, text="요금은 45,000원입니다."
        )
        result = verifier.verify(response, session, cached_data=cached_data)
        assert result.final_response != result.original_response

    def test_replaced_has_discrepancies(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """REPLACED 시 discrepancies 목록에 불일치 항목이 있다."""
        cached_data = {"billing_202607": {"amount": 55000}}
        response = make_llm_response(
            confidence=0.9, is_factual=True, text="요금은 45,000원입니다."
        )
        result = verifier.verify(response, session, cached_data=cached_data)
        assert len(result.discrepancies) >= 1

    def test_no_discrepancy_when_amount_matches(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """cached_data amount=55000, LLM says '55,000원' → PASS."""
        cached_data = {"billing_202607": {"amount": 55000}}
        response = make_llm_response(
            confidence=0.9, is_factual=True, text="요금은 55,000원입니다."
        )
        result = verifier.verify(response, session, cached_data=cached_data)
        assert result.status == VerificationStatus.PASS

    def test_no_discrepancy_when_amount_matches_without_comma(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """cached_data amount=55000, LLM says '55000원' (no comma) → PASS."""
        cached_data = {"billing_202607": {"amount": 55000}}
        response = make_llm_response(
            confidence=0.9, is_factual=True, text="요금은 55000원입니다."
        )
        result = verifier.verify(response, session, cached_data=cached_data)
        assert result.status == VerificationStatus.PASS


# ---------------------------------------------------------------------------
# Task 8.3: DB 장애 차단 테스트
# **Validates: Requirements 2.8**
# ---------------------------------------------------------------------------

class TestDBFailureBlocked:
    """DB 조회 장애 시 status=BLOCKED, block_reason='DB_장애'."""

    def test_db_error_returns_blocked(self, session: SessionContext):
        """db_service raises → BLOCKED, block_reason='DB_장애'."""
        db_service = MockDBService(raise_error=True)
        verifier = HallucinationVerifier(confidence_threshold=0.7, db_service=db_service)
        # is_factual=True, cached_data=None → verifier attempts db_service.query()
        response = make_llm_response(confidence=0.9, is_factual=True, text="요금은 55,000원입니다.")
        result = verifier.verify(response, session, cached_data=None)
        assert result.status == VerificationStatus.BLOCKED
        assert result.block_reason == "DB_장애"

    def test_db_error_block_reason_is_db_failure(self, session: SessionContext):
        """BLOCKED 시 block_reason은 정확히 'DB_장애'이어야 한다."""
        db_service = MockDBService(raise_error=True)
        verifier = HallucinationVerifier(confidence_threshold=0.7, db_service=db_service)
        response = make_llm_response(confidence=0.9, is_factual=True)
        result = verifier.verify(response, session, cached_data=None)
        assert result.block_reason == "DB_장애"


# ---------------------------------------------------------------------------
# Task 8.4: 복합 의도 COMPARISON 검증 테스트
# **Validates: Requirements 2.10**
# ---------------------------------------------------------------------------

class TestComparisonMultiKeyValidation:
    """cached_data 복수 키 지원 — 한 건 불일치 → 전체 교체."""

    def test_one_discrepancy_in_multi_key_returns_replaced(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """billing_202607 amount=55000 (present), billing_202606 amount=33000 (absent) → REPLACED."""
        cached_data = {
            "billing_202607": {"amount": 55000},
            "billing_202606": {"amount": 33000},
        }
        # LLM mentions 55,000 but not 33,000
        response = make_llm_response(
            confidence=0.9, is_factual=True,
            text="이번 달 요금은 55,000원이고 지난 달은 다릅니다."
        )
        result = verifier.verify(response, session, cached_data=cached_data)
        assert result.status == VerificationStatus.REPLACED

    def test_all_keys_present_returns_pass(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """billing_202607 amount=55000 and billing_202606 amount=33000 both present → PASS."""
        cached_data = {
            "billing_202607": {"amount": 55000},
            "billing_202606": {"amount": 33000},
        }
        # LLM mentions both amounts
        response = make_llm_response(
            confidence=0.9, is_factual=True,
            text="이번 달 요금은 55,000원이고 지난 달은 33,000원입니다."
        )
        result = verifier.verify(response, session, cached_data=cached_data)
        assert result.status == VerificationStatus.PASS

    def test_empty_cached_data_returns_pass(
        self, verifier: HallucinationVerifier, session: SessionContext
    ):
        """cached_data={} → no discrepancies → PASS."""
        response = make_llm_response(confidence=0.9, is_factual=True, text="요금 정보입니다.")
        result = verifier.verify(response, session, cached_data={})
        assert result.status == VerificationStatus.PASS


# ---------------------------------------------------------------------------
# Task 9.1: 환각률 계산 단위 테스트
# **Validates: Requirements 2.9, 3.5, 3.6, 3.7**
# ---------------------------------------------------------------------------

class TestGetHallucinationMetrics:
    """get_hallucination_metrics() 환각률 계산 단위 테스트."""

    def test_auto_hallucination_rate_calculation(self, verifier: HallucinationVerifier):
        """total=100, auto_count=3 → auto_hallucination_rate=0.03."""
        metrics = verifier.get_hallucination_metrics(
            period="weekly",
            total_factual_responses=100,
            auto_detected_count=3,
            residual_sample_size=0,
            residual_hallucination_count=0,
        )
        assert metrics.auto_hallucination_rate == pytest.approx(0.03)

    def test_residual_hallucination_rate_calculation(self, verifier: HallucinationVerifier):
        """sample=300, residual_count=2 → residual_hallucination_rate≈0.00667."""
        metrics = verifier.get_hallucination_metrics(
            period="weekly",
            total_factual_responses=0,
            auto_detected_count=0,
            residual_sample_size=300,
            residual_hallucination_count=2,
        )
        assert metrics.residual_hallucination_rate == pytest.approx(2 / 300)

    def test_combined_rate_is_sum_of_auto_and_residual(self, verifier: HallucinationVerifier):
        """combined_rate = auto_rate + residual_rate."""
        metrics = verifier.get_hallucination_metrics(
            period="weekly",
            total_factual_responses=100,
            auto_detected_count=3,
            residual_sample_size=300,
            residual_hallucination_count=2,
        )
        expected_combined = 3 / 100 + 2 / 300
        assert metrics.combined_rate == pytest.approx(expected_combined)

    def test_auto_rate_zero_when_total_is_zero(self, verifier: HallucinationVerifier):
        """total=0 → auto_hallucination_rate=0.0 (no division by zero)."""
        metrics = verifier.get_hallucination_metrics(
            period="weekly",
            total_factual_responses=0,
            auto_detected_count=0,
            residual_sample_size=0,
            residual_hallucination_count=0,
        )
        assert metrics.auto_hallucination_rate == 0.0

    def test_residual_rate_zero_when_sample_is_zero(self, verifier: HallucinationVerifier):
        """sample=0 → residual_hallucination_rate=0.0 (no division by zero)."""
        metrics = verifier.get_hallucination_metrics(
            period="weekly",
            total_factual_responses=0,
            auto_detected_count=0,
            residual_sample_size=0,
            residual_hallucination_count=0,
        )
        assert metrics.residual_hallucination_rate == 0.0

    def test_combined_rate_zero_when_both_are_zero(self, verifier: HallucinationVerifier):
        """total=0, sample=0 → combined_rate=0.0."""
        metrics = verifier.get_hallucination_metrics(
            period="weekly",
            total_factual_responses=0,
            auto_detected_count=0,
            residual_sample_size=0,
            residual_hallucination_count=0,
        )
        assert metrics.combined_rate == 0.0

    def test_period_is_preserved_in_metrics(self, verifier: HallucinationVerifier):
        """period 값이 반환된 metrics에 그대로 포함된다."""
        metrics = verifier.get_hallucination_metrics(
            period="monthly",
            total_factual_responses=0,
            auto_detected_count=0,
            residual_sample_size=0,
            residual_hallucination_count=0,
        )
        assert metrics.period == "monthly"
