"""mTLSCertificateProvider 테스트 — PBT + 단위 테스트."""

from __future__ import annotations

import os
import stat
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.security.exceptions import SecretNotFoundError
from callbot.security.secrets_manager import SecretsManager
from callbot.external.mtls_provider import mTLSCertificateProvider

# 서로게이트 문자를 제외한 텍스트 전략 (UTF-8 인코딩 가능한 문자만)
_safe_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
)


# ---------------------------------------------------------------------------
# Property 1: mTLS 임시 파일 권한 및 내용 일치
# Feature: callbot-external-api-integration, Property 1: mTLS 임시 파일 권한 및 내용 일치
# **Validates: Requirements 1.4**
# ---------------------------------------------------------------------------


@given(
    cert_content=_safe_text,
    key_content=_safe_text,
)
@settings(max_examples=20)
def test_temp_file_permissions_and_content(cert_content: str, key_content: str) -> None:
    """임의 인증서/키 문자열에 대해 임시 파일 권한이 0o600이고 내용이 원본과 동일."""
    mock_sm = MagicMock(spec=SecretsManager)
    mock_sm.get_secret.side_effect = lambda name: {
        "callbot/anytelecom-mtls-cert": cert_content,
        "callbot/anytelecom-mtls-key": key_content,
    }[name]

    provider = mTLSCertificateProvider(mock_sm)
    try:
        # 권한 검증: 소유자만 읽기/쓰기 (0o600)
        cert_mode = stat.S_IMODE(os.stat(provider.cert_path).st_mode)
        key_mode = stat.S_IMODE(os.stat(provider.key_path).st_mode)
        assert cert_mode == 0o600, f"cert permission {oct(cert_mode)} != 0o600"
        assert key_mode == 0o600, f"key permission {oct(key_mode)} != 0o600"

        # 내용 검증 (바이너리 모드로 읽어 원본 바이트와 비교)
        with open(provider.cert_path, "rb") as f:
            assert f.read() == cert_content.encode()
        with open(provider.key_path, "rb") as f:
            assert f.read() == key_content.encode()
    finally:
        provider.cleanup()


# ---------------------------------------------------------------------------
# Property 2: mTLS 임시 파일 정리
# Feature: callbot-external-api-integration, Property 2: mTLS 임시 파일 정리
# **Validates: Requirements 1.5**
# ---------------------------------------------------------------------------


@given(
    cert_content=_safe_text,
    key_content=_safe_text,
)
@settings(max_examples=20)
def test_temp_files_cleaned_after_context_manager(cert_content: str, key_content: str) -> None:
    """context manager 종료 후 임시 파일이 파일 시스템에 존재하지 않음."""
    mock_sm = MagicMock(spec=SecretsManager)
    mock_sm.get_secret.side_effect = lambda name: {
        "callbot/anytelecom-mtls-cert": cert_content,
        "callbot/anytelecom-mtls-key": key_content,
    }[name]

    with mTLSCertificateProvider(mock_sm) as provider:
        cert_path = provider.cert_path
        key_path = provider.key_path
        # 파일이 존재해야 함
        assert os.path.exists(cert_path)
        assert os.path.exists(key_path)

    # context manager 종료 후 파일이 삭제되어야 함
    assert not os.path.exists(cert_path), f"cert file still exists: {cert_path}"
    assert not os.path.exists(key_path), f"key file still exists: {key_path}"


# ---------------------------------------------------------------------------
# 단위 테스트
# Requirements: 1.3, 1.5
# ---------------------------------------------------------------------------


def _make_mock_sm(cert: str = "CERT", key: str = "KEY") -> MagicMock:
    mock_sm = MagicMock(spec=SecretsManager)
    mock_sm.get_secret.side_effect = lambda name: {
        "callbot/anytelecom-mtls-cert": cert,
        "callbot/anytelecom-mtls-key": key,
    }[name]
    return mock_sm


def test_secret_not_found_raises() -> None:
    """SecretsManager 조회 실패 시 SecretNotFoundError 전파."""
    mock_sm = MagicMock(spec=SecretsManager)
    mock_sm.get_secret.side_effect = SecretNotFoundError("not found")

    with pytest.raises(SecretNotFoundError):
        mTLSCertificateProvider(mock_sm)


def test_cleanup_removes_files() -> None:
    """cleanup() 호출 후 파일 삭제 확인."""
    mock_sm = _make_mock_sm()
    provider = mTLSCertificateProvider(mock_sm)
    cert_path = provider.cert_path
    key_path = provider.key_path

    assert os.path.exists(cert_path)
    assert os.path.exists(key_path)

    provider.cleanup()

    assert not os.path.exists(cert_path)
    assert not os.path.exists(key_path)


def test_del_calls_cleanup() -> None:
    """__del__ 호출 시 cleanup 실행 확인."""
    mock_sm = _make_mock_sm()
    provider = mTLSCertificateProvider(mock_sm)
    cert_path = provider.cert_path
    key_path = provider.key_path

    assert os.path.exists(cert_path)
    assert os.path.exists(key_path)

    provider.__del__()

    assert not os.path.exists(cert_path)
    assert not os.path.exists(key_path)
