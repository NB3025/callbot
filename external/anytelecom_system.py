"""AnyTelecomExternalSystem — 고수준 외부 시스템 어댑터."""

from __future__ import annotations

import time  # noqa: F401 — patched in tests

from callbot.business.api_wrapper import ExternalAPIWrapper
from callbot.business.enums import BillingOperation, CustomerDBOperation
from callbot.business.external_system import ExternalSystemBase
from callbot.business.models import APIResult
from callbot.external.anytelecom_client import AnyTelecomHTTPClient
from callbot.external.response_normalizer import ResponseNormalizer


class AnyTelecomExternalSystem(ExternalSystemBase):
    """external_system.ExternalSystemBase를 구현하는 고수준 어댑터.

    AnyTelecomHTTPClient를 주입받아 ExternalAPIWrapper로 재시도/서킷브레이커를
    활용하고, ResponseNormalizer로 응답을 정규화하여 APIResult를 반환한다.
    """

    def __init__(self, http_client: AnyTelecomHTTPClient) -> None:
        self._wrapper = ExternalAPIWrapper(external_system=http_client)
        self._normalizer = ResponseNormalizer()

    def call_billing_api(
        self,
        operation: BillingOperation,
        params: dict,
        timeout_sec: float = 5.0,
    ) -> APIResult:
        result = self._wrapper.call_billing_api(operation, params, timeout_sec)
        if result.is_success and result.data is not None:
            result = APIResult(
                is_success=True,
                data=self._normalizer.normalize(
                    "billing", operation.value, result.data
                ),
                error=None,
                response_time_ms=result.response_time_ms,
                retry_count=result.retry_count,
            )
        return result

    def call_customer_db(
        self,
        operation: CustomerDBOperation,
        params: dict,
        timeout_sec: float = 1.0,
    ) -> APIResult:
        result = self._wrapper.call_customer_db(operation, params, timeout_sec)
        if result.is_success and result.data is not None:
            result = APIResult(
                is_success=True,
                data=self._normalizer.normalize(
                    "customer_db", operation.value, result.data
                ),
                error=None,
                response_time_ms=result.response_time_ms,
                retry_count=result.retry_count,
            )
        return result
