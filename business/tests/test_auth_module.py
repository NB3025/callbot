"""callbot.business.tests.test_auth_module — 본인_인증_모듈 단위 테스트"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from callbot.business.auth_module import AuthenticationModule
from callbot.business.enums import APIErrorType, AuthType, CustomerDBOperation
from callbot.business.models import APIError, APIResult


# ---------------------------------------------------------------------------
# 헬퍼: mock api_wrapper 생성
# ---------------------------------------------------------------------------

def _make_success_result(customer_info: dict | None) -> APIResult:
    data = {"customer_info": customer_info} if customer_info is not None else {"customer_info": None}
    return APIResult(
        is_success=True,
        data=data,
        error=None,
        response_time_ms=50,
        retry_count=0,
    )


def _make_error_result() -> APIResult:
    return APIResult(
        is_success=False,
        data=None,
        error=APIError(
            error_type=APIErrorType.TIMEOUT,
            message="DB 연결 실패",
            is_retryable=True,
        ),
        response_time_ms=1000,
        retry_count=2,
    )


def _make_auth_module(api_result: APIResult) -> AuthenticationModule:
    wrapper = MagicMock()
    wrapper.call_customer_db.return_value = api_result
    return AuthenticationModule(api_wrapper=wrapper)


# ---------------------------------------------------------------------------
# 2.1 발신번호 식별 단위 테스트
# ---------------------------------------------------------------------------

def test_identify_by_caller_id_found() -> None:
    """등록된 번호 → is_found=True, customer_info is not None"""
    customer = {"id": "C001", "name": "홍길동"}
    module = _make_auth_module(_make_success_result(customer))

    result = module.identify_by_caller_id("01012345678")

    assert result.is_found is True
    assert result.customer_info is not None
    assert result.customer_info["id"] == "C001"
    assert result.is_db_error is False


def test_identify_by_caller_id_not_found() -> None:
    """미등록 번호 → is_found=False, customer_info is None"""
    module = _make_auth_module(_make_success_result(None))

    result = module.identify_by_caller_id("01099999999")

    assert result.is_found is False
    assert result.customer_info is None
    assert result.is_db_error is False


def test_identify_by_caller_id_db_error() -> None:
    """고객_DB 장애 → is_db_error=True"""
    module = _make_auth_module(_make_error_result())

    result = module.identify_by_caller_id("01012345678")

    assert result.is_found is False
    assert result.customer_info is None
    assert result.is_db_error is True


# ---------------------------------------------------------------------------
# 2.2 DTMF 입력 검증 단위 테스트
# ---------------------------------------------------------------------------

def test_validate_dtmf_birthdate_valid() -> None:
    """생년월일 6자리 유효 → is_valid=True"""
    wrapper = MagicMock()
    module = AuthenticationModule(api_wrapper=wrapper)

    result = module.validate_dtmf_input("900101", AuthType.BIRTHDATE)

    assert result.is_valid is True
    assert result.error_type is None


def test_validate_dtmf_birthdate_incomplete() -> None:
    """생년월일 5자리 → error_type='incomplete'"""
    wrapper = MagicMock()
    module = AuthenticationModule(api_wrapper=wrapper)

    result = module.validate_dtmf_input("90010", AuthType.BIRTHDATE)

    assert result.is_valid is False
    assert result.error_type == "incomplete"


def test_validate_dtmf_birthdate_invalid_month() -> None:
    """생년월일 13월 → error_type='invalid_date'"""
    wrapper = MagicMock()
    module = AuthenticationModule(api_wrapper=wrapper)

    result = module.validate_dtmf_input("901301", AuthType.BIRTHDATE)

    assert result.is_valid is False
    assert result.error_type == "invalid_date"


def test_validate_dtmf_birthdate_invalid_day() -> None:
    """생년월일 32일 → error_type='invalid_date'"""
    wrapper = MagicMock()
    module = AuthenticationModule(api_wrapper=wrapper)

    result = module.validate_dtmf_input("900132", AuthType.BIRTHDATE)

    assert result.is_valid is False
    assert result.error_type == "invalid_date"


def test_validate_dtmf_password_valid() -> None:
    """비밀번호 4자리 → is_valid=True"""
    wrapper = MagicMock()
    module = AuthenticationModule(api_wrapper=wrapper)

    result = module.validate_dtmf_input("1234", AuthType.PASSWORD)

    assert result.is_valid is True
    assert result.error_type is None


# ---------------------------------------------------------------------------
# 2.3 재조회 1회 제한 단위 테스트
# ---------------------------------------------------------------------------

def test_lookup_by_provided_number_second_call_returns_error() -> None:
    """같은 session_id로 2회 호출 시 오류 결과 반환"""
    customer = {"id": "C002", "name": "김철수"}
    module = _make_auth_module(_make_success_result(customer))

    # 1회 호출 — 정상
    first = module.lookup_by_provided_number("session-abc", "01011112222")
    assert first.lookup_count == 1

    # 2회 호출 — 오류 결과
    second = module.lookup_by_provided_number("session-abc", "01011112222")
    assert second.is_found is False
    assert second.customer_info is None
    assert second.is_db_error is False
    assert second.lookup_count == 1


# ---------------------------------------------------------------------------
# 헬퍼: authenticate mock 결과 생성
# ---------------------------------------------------------------------------

def _make_auth_failure_result(has_password: bool = False) -> APIResult:
    return APIResult(
        is_success=True,
        data={"verified": False, "has_password": has_password},
        error=None,
        response_time_ms=50,
        retry_count=0,
    )


def _make_auth_success_result(has_password: bool = False) -> APIResult:
    return APIResult(
        is_success=True,
        data={"verified": True, "has_password": has_password},
        error=None,
        response_time_ms=50,
        retry_count=0,
    )


# ---------------------------------------------------------------------------
# 3.1 인증 실패 횟수 합산 단위 테스트
# ---------------------------------------------------------------------------

def test_authenticate_failure_count_accumulates_across_methods() -> None:
    """생년월일 2회 실패 + 비밀번호 1회 실패 = 3회 → is_authenticated=False, failure_count=3"""
    wrapper = MagicMock()
    wrapper.call_customer_db.side_effect = [
        _make_auth_failure_result(),  # 생년월일 1회 실패
        _make_auth_failure_result(),  # 생년월일 2회 실패
        _make_auth_failure_result(),  # 비밀번호 1회 실패 (누적 3회)
    ]
    module = AuthenticationModule(api_wrapper=wrapper)

    module.authenticate("sess-1", AuthType.BIRTHDATE, "900101")
    module.authenticate("sess-1", AuthType.BIRTHDATE, "900102")
    result = module.authenticate("sess-1", AuthType.PASSWORD, "1234")

    assert result.is_authenticated is False
    assert result.failure_count == 3


def test_authenticate_success_after_two_failures() -> None:
    """2회 실패 후 성공 → is_authenticated=True, failure_count=2"""
    wrapper = MagicMock()
    wrapper.call_customer_db.side_effect = [
        _make_auth_failure_result(),  # 1회 실패
        _make_auth_failure_result(),  # 2회 실패
        _make_auth_success_result(),  # 성공
    ]
    module = AuthenticationModule(api_wrapper=wrapper)

    module.authenticate("sess-2", AuthType.BIRTHDATE, "900101")
    module.authenticate("sess-2", AuthType.BIRTHDATE, "900102")
    result = module.authenticate("sess-2", AuthType.BIRTHDATE, "900103")

    assert result.is_authenticated is True
    assert result.failure_count == 2


# ---------------------------------------------------------------------------
# 3.2 인증 수단 전환 단위 테스트
# ---------------------------------------------------------------------------

def test_authenticate_can_switch_method_when_has_password() -> None:
    """생년월일 실패 + has_password=True → can_switch_method=True, alternative_method=PASSWORD"""
    wrapper = MagicMock()
    wrapper.call_customer_db.return_value = _make_auth_failure_result(has_password=True)
    module = AuthenticationModule(api_wrapper=wrapper)

    result = module.authenticate("sess-3", AuthType.BIRTHDATE, "900101")

    assert result.is_authenticated is False
    assert result.can_switch_method is True
    assert result.alternative_method == AuthType.PASSWORD


def test_authenticate_cannot_switch_method_when_no_password() -> None:
    """has_password=False → can_switch_method=False"""
    wrapper = MagicMock()
    wrapper.call_customer_db.return_value = _make_auth_failure_result(has_password=False)
    module = AuthenticationModule(api_wrapper=wrapper)

    result = module.authenticate("sess-4", AuthType.BIRTHDATE, "900101")

    assert result.is_authenticated is False
    assert result.can_switch_method is False
    assert result.alternative_method is None
