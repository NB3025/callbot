"""callbot.business.tests.test_models — 비즈니스 데이터 모델 속성 기반 테스트"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.business.enums import APIErrorType, AuthType
from callbot.business.models import (
    APIError,
    APIResult,
    AuthResult,
    ConsentResult,
    DTMFValidationResult,
    IdentificationResult,
    RollbackResult,
)


# ---------------------------------------------------------------------------
# 공통 전략
# ---------------------------------------------------------------------------

auth_type_st = st.sampled_from(AuthType)
api_error_type_st = st.sampled_from(APIErrorType)

api_error_st = st.builds(
    APIError,
    error_type=api_error_type_st,
    message=st.text(min_size=1, max_size=100),
    is_retryable=st.booleans(),
)


# ---------------------------------------------------------------------------
# Property 1: AuthResult 실패 횟수-인증 상태 일관성
# Validates: Requirements 1.2, 1.3
# ---------------------------------------------------------------------------

@given(
    max_attempts=st.integers(min_value=1, max_value=10),
    failure_count=st.integers(min_value=0, max_value=10),
    is_authenticated=st.booleans(),
)
@settings(max_examples=200)
def test_auth_result_failure_count_consistency(
    max_attempts: int,
    failure_count: int,
    is_authenticated: bool,
) -> None:
    """**Property 1: AuthResult 실패 횟수-인증 상태 일관성**

    is_authenticated=True → failure_count < max_attempts
    failure_count >= max_attempts → is_authenticated=False

    Validates: Requirements 1.2, 1.3
    """
    # 불변 조건 위반 케이스는 ValueError가 발생해야 한다
    violates_invariant = (
        (is_authenticated and failure_count >= max_attempts)
    )

    if violates_invariant:
        with pytest.raises(ValueError):
            AuthResult(
                is_authenticated=is_authenticated,
                failure_count=failure_count,
                max_attempts=max_attempts,
                has_password=False,
                can_switch_method=False,
                alternative_method=None,
            )
    else:
        result = AuthResult(
            is_authenticated=is_authenticated,
            failure_count=failure_count,
            max_attempts=max_attempts,
            has_password=False,
            can_switch_method=False,
            alternative_method=None,
        )
        # 불변 조건 검증
        if result.is_authenticated:
            assert result.failure_count < result.max_attempts
        if result.failure_count >= result.max_attempts:
            assert not result.is_authenticated


# ---------------------------------------------------------------------------
# Property 2: IdentificationResult is_found-customer_info 일관성
# Validates: Requirements 1.1
# ---------------------------------------------------------------------------

@given(
    is_found=st.booleans(),
    customer_info=st.one_of(st.none(), st.fixed_dictionaries({"id": st.text(min_size=1)})),
    is_db_error=st.booleans(),
    lookup_count=st.integers(min_value=0, max_value=1),
)
@settings(max_examples=200)
def test_identification_result_consistency(
    is_found: bool,
    customer_info: dict | None,
    is_db_error: bool,
    lookup_count: int,
) -> None:
    """**Property 2: IdentificationResult is_found-customer_info 일관성**

    is_found=True ↔ customer_info is not None
    is_found=False ↔ customer_info is None

    Validates: Requirements 1.1
    """
    violates_invariant = (
        (is_found and customer_info is None)
        or (not is_found and customer_info is not None)
    )

    if violates_invariant:
        with pytest.raises(ValueError):
            IdentificationResult(
                is_found=is_found,
                customer_info=customer_info,
                is_db_error=is_db_error,
                lookup_count=lookup_count,
            )
    else:
        result = IdentificationResult(
            is_found=is_found,
            customer_info=customer_info,
            is_db_error=is_db_error,
            lookup_count=lookup_count,
        )
        if result.is_found:
            assert result.customer_info is not None
        else:
            assert result.customer_info is None


# ---------------------------------------------------------------------------
# Property 3: DTMFValidationResult 유효성-오류유형 일관성
# Validates: Requirements 1.4
# ---------------------------------------------------------------------------

@given(
    is_valid=st.booleans(),
    error_type=st.one_of(st.none(), st.sampled_from(["incomplete", "invalid_date"])),
    error_message=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
)
@settings(max_examples=200)
def test_dtmf_validation_result_consistency(
    is_valid: bool,
    error_type: str | None,
    error_message: str | None,
) -> None:
    """**Property 3: DTMFValidationResult 유효성-오류유형 일관성**

    is_valid=True → error_type is None
    is_valid=False → error_type is not None

    Validates: Requirements 1.4
    """
    violates_invariant = (
        (is_valid and error_type is not None)
        or (not is_valid and error_type is None)
    )

    if violates_invariant:
        with pytest.raises(ValueError):
            DTMFValidationResult(
                is_valid=is_valid,
                error_type=error_type,
                error_message=error_message,
            )
    else:
        result = DTMFValidationResult(
            is_valid=is_valid,
            error_type=error_type,
            error_message=error_message,
        )
        if result.is_valid:
            assert result.error_type is None
        else:
            assert result.error_type is not None


# ---------------------------------------------------------------------------
# Property 4: APIResult 성공-데이터 일관성
# Validates: Requirements 4.1
# ---------------------------------------------------------------------------

@given(
    is_success=st.booleans(),
    data=st.one_of(st.none(), st.fixed_dictionaries({"value": st.integers()})),
    has_error=st.booleans(),
    response_time_ms=st.integers(min_value=0, max_value=10000),
    retry_count=st.integers(min_value=0, max_value=2),
)
@settings(max_examples=200)
def test_api_result_success_data_consistency(
    is_success: bool,
    data: dict | None,
    has_error: bool,
    response_time_ms: int,
    retry_count: int,
) -> None:
    """**Property 4: APIResult 성공-데이터 일관성**

    is_success=True → data is not None and error is None
    is_success=False → error is not None

    Validates: Requirements 4.1
    """
    error = APIError(
        error_type=APIErrorType.SERVER_ERROR,
        message="error",
        is_retryable=False,
    ) if has_error else None

    violates_invariant = (
        (is_success and data is None)
        or (is_success and error is not None)
        or (not is_success and error is None)
    )

    if violates_invariant:
        with pytest.raises(ValueError):
            APIResult(
                is_success=is_success,
                data=data,
                error=error,
                response_time_ms=response_time_ms,
                retry_count=retry_count,
            )
    else:
        result = APIResult(
            is_success=is_success,
            data=data,
            error=error,
            response_time_ms=response_time_ms,
            retry_count=retry_count,
        )
        if result.is_success:
            assert result.data is not None
            assert result.error is None
        else:
            assert result.error is not None


# ---------------------------------------------------------------------------
# Property 5: RollbackResult 수동처리-재시도 일관성
# Validates: Requirements 4.3
# ---------------------------------------------------------------------------

@given(
    is_success=st.booleans(),
    requires_manual=st.booleans(),
    retry_count=st.integers(min_value=0, max_value=5),
    error_message=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
)
@settings(max_examples=200)
def test_rollback_result_manual_retry_consistency(
    is_success: bool,
    requires_manual: bool,
    retry_count: int,
    error_message: str | None,
) -> None:
    """**Property 5: RollbackResult 수동처리-재시도 일관성**

    requires_manual=True → is_success=False and retry_count == 3

    Validates: Requirements 4.3
    """
    violates_invariant = (
        (is_success and requires_manual)
        or (requires_manual and not is_success and retry_count != 3)
        or (requires_manual and is_success)
    )

    if violates_invariant:
        with pytest.raises(ValueError):
            RollbackResult(
                is_success=is_success,
                requires_manual=requires_manual,
                retry_count=retry_count,
                error_message=error_message,
            )
    else:
        result = RollbackResult(
            is_success=is_success,
            requires_manual=requires_manual,
            retry_count=retry_count,
            error_message=error_message,
        )
        if result.requires_manual:
            assert not result.is_success
            assert result.retry_count == 3


# ---------------------------------------------------------------------------
# Property 6: ConsentResult 동의-거부 상호 배타성
# Validates: Requirements 3.3
# ---------------------------------------------------------------------------

@given(
    consent_given=st.booleans(),
    is_rejected=st.booleans(),
)
@settings(max_examples=200)
def test_consent_result_mutual_exclusivity(
    consent_given: bool,
    is_rejected: bool,
) -> None:
    """**Property 6: ConsentResult 동의-거부 상호 배타성**

    consent_given=True → is_rejected=False
    is_rejected=True   → consent_given=False

    Validates: Requirements 3.3
    """
    violates_invariant = consent_given and is_rejected

    if violates_invariant:
        with pytest.raises(ValueError):
            ConsentResult(consent_given=consent_given, is_rejected=is_rejected)
    else:
        result = ConsentResult(consent_given=consent_given, is_rejected=is_rejected)
        if result.consent_given:
            assert not result.is_rejected
        if result.is_rejected:
            assert not result.consent_given
