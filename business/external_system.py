"""callbot.business.external_system — 외부 시스템 추상 인터페이스"""
from __future__ import annotations

from abc import ABC, abstractmethod

from callbot.business.enums import BillingOperation, CustomerDBOperation
from callbot.business.models import APIResult


class ExternalSystemBase(ABC):
    @abstractmethod
    def call_billing_api(
        self,
        operation: BillingOperation,
        params: dict,
        timeout_sec: float = 5.0,
    ) -> APIResult: ...

    @abstractmethod
    def call_customer_db(
        self,
        operation: CustomerDBOperation,
        params: dict,
        timeout_sec: float = 1.0,
    ) -> APIResult: ...
