"""callbot.external.tests.test_response_normalizer — ResponseNormalizer 테스트."""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.external.response_normalizer import ResponseNormalizer


# ---------------------------------------------------------------------------
# 8개 system/operation 쌍 (PBT에서 사용)
# ---------------------------------------------------------------------------
operations = [
    ("billing", "요금_조회"),
    ("billing", "납부_확인"),
    ("billing", "요금제_목록_조회"),
    ("billing", "요금제_변경"),
    ("billing", "요금제_변경_롤백"),
    ("customer_db", "고객_식별"),
    ("customer_db", "인증_검증"),
    ("customer_db", "고객_정보_조회"),
]


# ---------------------------------------------------------------------------
# Property 8: 응답 정규화 멱등성
# Feature: callbot-external-api-integration, Property 8: 응답 정규화 멱등성
# **Validates: Requirements 8.10**
# ---------------------------------------------------------------------------


@given(
    op=st.sampled_from(operations),
    data=st.dictionaries(st.text(), st.text()),
)
@settings(max_examples=100)
def test_normalize_idempotent(op: tuple[str, str], data: dict) -> None:
    """정규화를 두 번 적용해도 결과가 동일하다 (멱등성)."""
    system, operation = op
    once = ResponseNormalizer.normalize(system, operation, data)
    twice = ResponseNormalizer.normalize(system, operation, once)
    assert twice == once


# ---------------------------------------------------------------------------
# 개별 오퍼레이션 정규화 단위 테스트
# Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8
# ---------------------------------------------------------------------------


class TestIdentifyNormalization:
    """Req 8.1: 고객_식별 → {"customer_info": {...}}"""

    def test_raw_data_wrapped(self) -> None:
        raw = {"id": "C001", "name": "홍길동"}
        result = ResponseNormalizer.normalize("customer_db", "고객_식별", raw)
        assert result == {"customer_info": {"id": "C001", "name": "홍길동"}}

    def test_already_normalized(self) -> None:
        already = {"customer_info": {"id": "C001"}}
        result = ResponseNormalizer.normalize("customer_db", "고객_식별", already)
        assert result == already


class TestVerifyAuthNormalization:
    """Req 8.2: 인증_검증 → {"verified": bool, "has_password": bool}"""

    def test_raw_data_extracted(self) -> None:
        raw = {"verified": True, "has_password": False, "extra": "ignored"}
        result = ResponseNormalizer.normalize("customer_db", "인증_검증", raw)
        assert result == {"verified": True, "has_password": False}

    def test_missing_fields_default_false(self) -> None:
        raw = {"some_other": "data"}
        result = ResponseNormalizer.normalize("customer_db", "인증_검증", raw)
        assert result == {"verified": False, "has_password": False}

    def test_already_normalized(self) -> None:
        already = {"verified": True, "has_password": True}
        result = ResponseNormalizer.normalize("customer_db", "인증_검증", already)
        assert result == already


class TestQueryBillingNormalization:
    """Req 8.3: 요금_조회 → {"charges": [...]}"""

    def test_raw_data_wrapped(self) -> None:
        raw = {"charges": [{"amount": 50000}]}
        result = ResponseNormalizer.normalize("billing", "요금_조회", raw)
        assert result == {"charges": [{"amount": 50000}]}

    def test_missing_charges_defaults_empty(self) -> None:
        raw = {"other": "data"}
        result = ResponseNormalizer.normalize("billing", "요금_조회", raw)
        assert result == {"charges": []}

    def test_already_normalized(self) -> None:
        already = {"charges": []}
        result = ResponseNormalizer.normalize("billing", "요금_조회", already)
        assert result == already


class TestQueryPaymentNormalization:
    """Req 8.4: 납부_확인 → {"payments": [...]}"""

    def test_raw_data_wrapped(self) -> None:
        raw = {"payments": [{"date": "2024-01-01"}]}
        result = ResponseNormalizer.normalize("billing", "납부_확인", raw)
        assert result == {"payments": [{"date": "2024-01-01"}]}

    def test_missing_payments_defaults_empty(self) -> None:
        raw = {"other": "data"}
        result = ResponseNormalizer.normalize("billing", "납부_확인", raw)
        assert result == {"payments": []}


class TestQueryPlansNormalization:
    """Req 8.5: 요금제_목록_조회 → {"plans": [...]}"""

    def test_raw_data_wrapped(self) -> None:
        raw = {"plans": [{"name": "5G 프리미엄"}]}
        result = ResponseNormalizer.normalize("billing", "요금제_목록_조회", raw)
        assert result == {"plans": [{"name": "5G 프리미엄"}]}

    def test_missing_plans_defaults_empty(self) -> None:
        raw = {}
        result = ResponseNormalizer.normalize("billing", "요금제_목록_조회", raw)
        assert result == {"plans": []}


class TestChangePlanNormalization:
    """Req 8.6: 요금제_변경 → {"transaction_id": str, "result": str}"""

    def test_raw_data_extracted(self) -> None:
        raw = {"transaction_id": "TX001", "result": "success", "extra": "data"}
        result = ResponseNormalizer.normalize("billing", "요금제_변경", raw)
        assert result == {"transaction_id": "TX001", "result": "success"}

    def test_missing_fields_default_empty_str(self) -> None:
        raw = {"other": "data"}
        result = ResponseNormalizer.normalize("billing", "요금제_변경", raw)
        assert result == {"transaction_id": "", "result": ""}

    def test_already_normalized(self) -> None:
        already = {"transaction_id": "TX001", "result": "success"}
        result = ResponseNormalizer.normalize("billing", "요금제_변경", already)
        assert result == already


class TestRollbackPlanChangeNormalization:
    """Req 8.7: 요금제_변경_롤백 → {"transaction_id": str, "rollback_result": str}"""

    def test_raw_data_extracted(self) -> None:
        raw = {"transaction_id": "TX001", "rollback_result": "rolled_back", "extra": "x"}
        result = ResponseNormalizer.normalize("billing", "요금제_변경_롤백", raw)
        assert result == {"transaction_id": "TX001", "rollback_result": "rolled_back"}

    def test_missing_fields_default_empty_str(self) -> None:
        raw = {}
        result = ResponseNormalizer.normalize("billing", "요금제_변경_롤백", raw)
        assert result == {"transaction_id": "", "rollback_result": ""}

    def test_already_normalized(self) -> None:
        already = {"transaction_id": "TX001", "rollback_result": "ok"}
        result = ResponseNormalizer.normalize("billing", "요금제_변경_롤백", already)
        assert result == already


class TestQueryCustomerNormalization:
    """Req 8.8: 고객_정보_조회 → {"customer_info": {...}}"""

    def test_raw_data_wrapped(self) -> None:
        raw = {"id": "C002", "phone": "010-1234-5678"}
        result = ResponseNormalizer.normalize("customer_db", "고객_정보_조회", raw)
        assert result == {"customer_info": {"id": "C002", "phone": "010-1234-5678"}}

    def test_already_normalized(self) -> None:
        already = {"customer_info": {"id": "C002"}}
        result = ResponseNormalizer.normalize("customer_db", "고객_정보_조회", already)
        assert result == already
