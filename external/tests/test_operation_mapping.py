"""callbot.external.tests.test_operation_mapping — OperationMapping 테스트."""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.business.enums import BillingOperation, CustomerDBOperation
from callbot.external.operation_mapping import EndpointInfo, OperationMapping


# ---------------------------------------------------------------------------
# Property 4: 오퍼레이션 매핑 완전성
# Feature: callbot-external-api-integration, Property 4: 오퍼레이션 매핑 완전성
# **Validates: Requirements 3.9, 3.10**
# ---------------------------------------------------------------------------


@given(op=st.sampled_from(BillingOperation))
@settings(max_examples=100)
def test_billing_operation_mapping_completeness(op: BillingOperation) -> None:
    """모든 BillingOperation 열거형 값에 대해 resolve()가 유효한 EndpointInfo를 반환한다."""
    info = OperationMapping.resolve("billing", op.value)
    assert isinstance(info, EndpointInfo)
    assert isinstance(info.method, str)
    assert info.method in ("GET", "POST")
    assert isinstance(info.path_template, str)
    assert info.path_template.startswith("/")


@given(op=st.sampled_from(CustomerDBOperation))
@settings(max_examples=100)
def test_customer_db_operation_mapping_completeness(op: CustomerDBOperation) -> None:
    """모든 CustomerDBOperation 열거형 값에 대해 resolve()가 유효한 EndpointInfo를 반환한다."""
    info = OperationMapping.resolve("customer_db", op.value)
    assert isinstance(info, EndpointInfo)
    assert isinstance(info.method, str)
    assert info.method in ("GET", "POST")
    assert isinstance(info.path_template, str)
    assert info.path_template.startswith("/")


# ---------------------------------------------------------------------------
# 개별 매핑 단위 테스트
# Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8
# ---------------------------------------------------------------------------


class TestBillingOperationMapping:
    """Billing 시스템 오퍼레이션 매핑 검증."""

    def test_query_billing(self) -> None:
        """Req 3.1: QUERY_BILLING → GET /api/v1/billing/charges"""
        info = OperationMapping.resolve("billing", "요금_조회")
        assert info == EndpointInfo(method="GET", path_template="/api/v1/billing/charges")

    def test_query_payment(self) -> None:
        """Req 3.2: QUERY_PAYMENT → GET /api/v1/billing/payments"""
        info = OperationMapping.resolve("billing", "납부_확인")
        assert info == EndpointInfo(method="GET", path_template="/api/v1/billing/payments")

    def test_query_plans(self) -> None:
        """Req 3.3: QUERY_PLANS → GET /api/v1/billing/plans"""
        info = OperationMapping.resolve("billing", "요금제_목록_조회")
        assert info == EndpointInfo(method="GET", path_template="/api/v1/billing/plans")

    def test_change_plan(self) -> None:
        """Req 3.4: CHANGE_PLAN → POST /api/v1/billing/plans/change"""
        info = OperationMapping.resolve("billing", "요금제_변경")
        assert info == EndpointInfo(method="POST", path_template="/api/v1/billing/plans/change")

    def test_rollback_plan_change(self) -> None:
        """Req 3.5: ROLLBACK_PLAN_CHANGE → POST /api/v1/billing/plans/rollback"""
        info = OperationMapping.resolve("billing", "요금제_변경_롤백")
        assert info == EndpointInfo(method="POST", path_template="/api/v1/billing/plans/rollback")


class TestCustomerDBOperationMapping:
    """Customer DB 시스템 오퍼레이션 매핑 검증."""

    def test_identify(self) -> None:
        """Req 3.6: IDENTIFY → GET /api/v1/customers/identify"""
        info = OperationMapping.resolve("customer_db", "고객_식별")
        assert info == EndpointInfo(method="GET", path_template="/api/v1/customers/identify")

    def test_verify_auth(self) -> None:
        """Req 3.7: VERIFY_AUTH → POST /api/v1/customers/verify"""
        info = OperationMapping.resolve("customer_db", "인증_검증")
        assert info == EndpointInfo(method="POST", path_template="/api/v1/customers/verify")

    def test_query_customer(self) -> None:
        """Req 3.8: QUERY_CUSTOMER → GET /api/v1/customers/{customer_id}"""
        info = OperationMapping.resolve("customer_db", "고객_정보_조회")
        assert info == EndpointInfo(method="GET", path_template="/api/v1/customers/{customer_id}")


class TestUnregisteredOperation:
    """미등록 operation에 대한 ValueError 발생 검증."""

    def test_unknown_system_raises(self) -> None:
        info_call = lambda: OperationMapping.resolve("unknown_system", "요금_조회")
        with pytest.raises(ValueError):
            info_call()

    def test_unknown_operation_raises(self) -> None:
        info_call = lambda: OperationMapping.resolve("billing", "존재하지_않는_오퍼레이션")
        with pytest.raises(ValueError):
            info_call()

    def test_empty_system_raises(self) -> None:
        with pytest.raises(ValueError):
            OperationMapping.resolve("", "요금_조회")

    def test_empty_operation_raises(self) -> None:
        with pytest.raises(ValueError):
            OperationMapping.resolve("billing", "")
