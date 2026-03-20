"""Tests for create_external_system() factory function.

Covers:
- Property 9: 팩토리 반환 타입 보장 (PBT)
- Unit tests for factory behavior with different backends
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.business.external_system import ExternalSystemBase


# ===========================================================================
# Property 9: 팩토리 반환 타입 보장
# Feature: callbot-external-api-integration, Property 9: 팩토리 반환 타입 보장
# ===========================================================================


class TestFactoryReturnTypePBT:
    """**Validates: Requirements 9.3**"""

    @given(backend=st.sampled_from(["fake"]))
    @settings(max_examples=100)
    def test_factory_returns_external_system_base_instance(self, backend: str) -> None:
        """For any valid CALLBOT_EXTERNAL_BACKEND value (fake),
        create_external_system() returns an ExternalSystemBase instance."""
        from callbot.external.factory import create_external_system

        with patch.dict(os.environ, {"CALLBOT_EXTERNAL_BACKEND": backend}):
            result = create_external_system()

        assert isinstance(result, ExternalSystemBase)


# ===========================================================================
# Unit tests for factory
# ===========================================================================


class TestFactoryUnit:
    """Unit tests for create_external_system() factory."""

    def test_fake_backend_returns_fake_system(self) -> None:
        """CALLBOT_EXTERNAL_BACKEND=fake 시 FakeExternalSystem 반환.

        Requirements: 9.1
        """
        from callbot.external.factory import create_external_system
        from callbot.external.fake_system import FakeExternalSystem

        with patch.dict(os.environ, {"CALLBOT_EXTERNAL_BACKEND": "fake"}):
            result = create_external_system()

        assert isinstance(result, FakeExternalSystem)

    def test_default_backend_is_anytelecom(self) -> None:
        """환경변수 미설정 시 기본값 anytelecom — SecretsManager/from_env 호출 검증.

        Requirements: 9.2
        """
        from callbot.external.factory import create_external_system

        with patch.dict(os.environ, {}, clear=True), \
             patch("callbot.security.secrets_manager.SecretsManager.from_env") as mock_sm_from_env, \
             patch("callbot.external.anytelecom_client.AnyTelecomHTTPClient.from_env") as mock_client_from_env, \
             patch("callbot.external.anytelecom_system.AnyTelecomExternalSystem") as mock_system_cls:
            mock_sm = mock_sm_from_env.return_value
            mock_client = mock_client_from_env.return_value

            result = create_external_system()

            mock_sm_from_env.assert_called_once()
            mock_client_from_env.assert_called_once_with(mock_sm)
            mock_system_cls.assert_called_once_with(mock_client)

    def test_fake_backend_no_env_required(self) -> None:
        """fake 모드에서 mTLS/API 키/URL 환경변수 불필요.

        Requirements: 9.4
        """
        from callbot.external.factory import create_external_system

        # Clear all potentially required env vars, only set backend=fake
        env = {"CALLBOT_EXTERNAL_BACKEND": "fake"}
        with patch.dict(os.environ, env, clear=True):
            # Should not raise any errors about missing env vars
            result = create_external_system()

        assert isinstance(result, ExternalSystemBase)
