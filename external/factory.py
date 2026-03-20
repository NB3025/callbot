"""callbot.external.factory — 외부 시스템 구현체 팩토리.

CALLBOT_EXTERNAL_BACKEND 환경변수에 따라 적절한 ExternalSystemBase 구현체를 생성한다.
- "anytelecom" (기본): AnyTelecomExternalSystem (mTLS + API 키 필요)
- "fake": FakeExternalSystem (외부 의존성 불필요)
"""
from __future__ import annotations

import os

from callbot.business.external_system import ExternalSystemBase


def create_external_system() -> ExternalSystemBase:
    """환경변수에 따라 ExternalSystemBase 구현체를 생성한다."""
    backend = os.environ.get("CALLBOT_EXTERNAL_BACKEND", "anytelecom")

    if backend == "fake":
        from callbot.external.fake_system import FakeExternalSystem

        return FakeExternalSystem()

    # anytelecom (default)
    from callbot.external.anytelecom_client import AnyTelecomHTTPClient
    from callbot.external.anytelecom_system import AnyTelecomExternalSystem
    from callbot.security.secrets_manager import SecretsManager

    sm = SecretsManager.from_env()
    client = AnyTelecomHTTPClient.from_env(sm)
    return AnyTelecomExternalSystem(client)
