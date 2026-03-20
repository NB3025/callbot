"""callbot.business.auth_module — 본인 인증 모듈 (식별 및 DTMF 검증)"""
from __future__ import annotations

from callbot.business.enums import AuthType, CustomerDBOperation
from callbot.business.external_system import ExternalSystemBase
from callbot.business.models import AuthResult, DTMFValidationResult, IdentificationResult

MAX_ATTEMPTS = 3


class AuthenticationModule:
    """발신번호 기반 고객 식별 및 DTMF 입력 검증을 담당한다."""

    def __init__(self, api_wrapper: ExternalSystemBase) -> None:
        self._api = api_wrapper
        # session_id → lookup 횟수 추적 (최대 1회)
        self._lookup_counts: dict[str, int] = {}
        # session_id → 누적 인증 실패 횟수 (수단 무관 합산)
        self._failure_counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # 1차 식별: 발신번호 기반
    # ------------------------------------------------------------------

    def identify_by_caller_id(self, phone_number: str) -> IdentificationResult:
        """발신번호로 고객_DB를 조회하고 IdentificationResult를 반환한다.

        고객_DB 장애 시 is_db_error=True를 포함한 결과를 반환한다.
        """
        api_result = self._api.call_customer_db(
            CustomerDBOperation.IDENTIFY,
            {"phone": phone_number},
        )

        if not api_result.is_success:
            return IdentificationResult(
                is_found=False,
                customer_info=None,
                is_db_error=True,
                lookup_count=0,
            )

        customer_info = api_result.data.get("customer_info") if api_result.data else None
        is_found = customer_info is not None

        return IdentificationResult(
            is_found=is_found,
            customer_info=customer_info if is_found else None,
            is_db_error=False,
            lookup_count=0,
        )

    # ------------------------------------------------------------------
    # 미등록 번호 재조회: 세션당 1회 제한
    # ------------------------------------------------------------------

    def lookup_by_provided_number(
        self, session_id: str, phone_number: str
    ) -> IdentificationResult:
        """고객이 제공한 번호로 재조회한다. 세션당 1회만 허용한다.

        2회 이상 시도 시 is_found=False, is_db_error=False, lookup_count=1을 반환한다.
        """
        count = self._lookup_counts.get(session_id, 0)

        if count >= 1:
            return IdentificationResult(
                is_found=False,
                customer_info=None,
                is_db_error=False,
                lookup_count=1,
            )

        self._lookup_counts[session_id] = count + 1

        api_result = self._api.call_customer_db(
            CustomerDBOperation.IDENTIFY,
            {"phone": phone_number},
        )

        if not api_result.is_success:
            return IdentificationResult(
                is_found=False,
                customer_info=None,
                is_db_error=True,
                lookup_count=1,
            )

        customer_info = api_result.data.get("customer_info") if api_result.data else None
        is_found = customer_info is not None

        return IdentificationResult(
            is_found=is_found,
            customer_info=customer_info if is_found else None,
            is_db_error=False,
            lookup_count=1,
        )

    # ------------------------------------------------------------------
    # 추가 인증: 생년월일 또는 비밀번호
    # ------------------------------------------------------------------

    def authenticate(
        self, session_id: str, auth_type: AuthType, input_value: str
    ) -> AuthResult:
        """추가 본인 인증을 수행한다.

        실패 횟수는 수단에 관계없이 세션 단위로 합산한다.
        누적 실패 횟수가 MAX_ATTEMPTS(3)에 도달하면 is_authenticated=False를 반환한다.
        """
        current_count = self._failure_counts.get(session_id, 0)

        api_result = self._api.call_customer_db(
            CustomerDBOperation.VERIFY_AUTH,
            {"session_id": session_id, "auth_type": auth_type.value, "value": input_value},
        )

        has_password = False
        if api_result.is_success and api_result.data:
            has_password = api_result.data.get("has_password", False)

        verified = (
            api_result.is_success
            and api_result.data is not None
            and api_result.data.get("verified") is True
        )

        if verified:
            can_switch = False
            return AuthResult(
                is_authenticated=True,
                failure_count=current_count,
                max_attempts=MAX_ATTEMPTS,
                has_password=has_password,
                can_switch_method=can_switch,
                alternative_method=None,
            )

        # 인증 실패 — 횟수 증가
        new_count = current_count + 1
        self._failure_counts[session_id] = new_count

        if new_count >= MAX_ATTEMPTS:
            return AuthResult(
                is_authenticated=False,
                failure_count=MAX_ATTEMPTS,
                max_attempts=MAX_ATTEMPTS,
                has_password=has_password,
                can_switch_method=False,
                alternative_method=None,
            )

        can_switch = (
            has_password
            and auth_type == AuthType.BIRTHDATE
            and new_count < MAX_ATTEMPTS
        )
        return AuthResult(
            is_authenticated=False,
            failure_count=new_count,
            max_attempts=MAX_ATTEMPTS,
            has_password=has_password,
            can_switch_method=can_switch,
            alternative_method=AuthType.PASSWORD if can_switch else None,
        )

    # ------------------------------------------------------------------
    # DTMF 입력 검증
    # ------------------------------------------------------------------

    def validate_dtmf_input(
        self, digits: str, input_type: AuthType
    ) -> DTMFValidationResult:
        """DTMF 입력 형식을 검증한다.

        BIRTHDATE: 6자리 + 유효한 날짜 (월 1-12, 일 1-31)
        PASSWORD:  4자리 숫자
        """
        if input_type == AuthType.BIRTHDATE:
            return self._validate_birthdate(digits)
        elif input_type == AuthType.PASSWORD:
            return self._validate_password(digits)
        else:
            return DTMFValidationResult(
                is_valid=False,
                error_type="incomplete",
                error_message="지원하지 않는 인증 수단입니다.",
            )

    def _validate_birthdate(self, digits: str) -> DTMFValidationResult:
        if len(digits) != 6:
            return DTMFValidationResult(
                is_valid=False,
                error_type="incomplete",
                error_message="생년월일은 6자리(YYMMDD)로 입력해 주세요.",
            )

        month = int(digits[2:4])
        day = int(digits[4:6])

        if month < 1 or month > 12 or day < 1 or day > 31:
            return DTMFValidationResult(
                is_valid=False,
                error_type="invalid_date",
                error_message="유효하지 않은 날짜입니다. 다시 입력해 주세요.",
            )

        return DTMFValidationResult(is_valid=True, error_type=None, error_message=None)

    def _validate_password(self, digits: str) -> DTMFValidationResult:
        if len(digits) != 4:
            return DTMFValidationResult(
                is_valid=False,
                error_type="incomplete",
                error_message="비밀번호는 4자리로 입력해 주세요.",
            )

        return DTMFValidationResult(is_valid=True, error_type=None, error_message=None)
