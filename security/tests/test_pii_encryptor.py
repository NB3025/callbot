"""PIIEncryptor 속성 기반 테스트 및 단위 테스트.

Property 6~9 (Hypothesis) + 단위 테스트 3개.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.security.exceptions import DecryptionError, TokenNotFoundError
from callbot.security.pii_encryptor import PIIEncryptor
from callbot.security.secrets_manager import SecretsManager
from callbot.security.token_mapping_store import InMemoryTokenMappingStore

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

# 32-byte key for AES-256
TEST_KEY = "a" * 32  # 32 bytes when encoded to UTF-8


def _make_mock_sm(key: str = TEST_KEY) -> SecretsManager:
    mock_sm = MagicMock(spec=SecretsManager)
    mock_sm.get_secret.return_value = key
    return mock_sm


# ---------------------------------------------------------------------------
# Property 6: PII 암호화-복호화 라운드트립
# Feature: callbot-security, Property 6: PII 암호화-복호화 라운드트립
# ---------------------------------------------------------------------------


@given(pii=st.text(min_size=1, max_size=200))
@settings(max_examples=100)
def test_encrypt_decrypt_roundtrip(pii: str):
    """encrypt → decrypt → 원본 일치 검증.

    **Validates: Requirements 4.1, 4.6**
    """
    mock_sm = _make_mock_sm()
    store = InMemoryTokenMappingStore()
    encryptor = PIIEncryptor(mock_sm, store)

    ciphertext = encryptor.encrypt(pii)
    decrypted = encryptor.decrypt(ciphertext)
    assert decrypted == pii


# ---------------------------------------------------------------------------
# Property 7: 암호화 결과 비결정성 (IV 고유성)
# Feature: callbot-security, Property 7: 암호화 결과 비결정성 (IV 고유성)
# ---------------------------------------------------------------------------


@given(pii=st.text(min_size=1, max_size=200))
@settings(max_examples=100)
def test_encrypt_nondeterministic_iv(pii: str):
    """동일 PII 2회 encrypt → 서로 다른 암호문 검증.

    **Validates: Requirements 4.3, 4.7**
    """
    mock_sm = _make_mock_sm()
    store = InMemoryTokenMappingStore()
    encryptor = PIIEncryptor(mock_sm, store)

    ct1 = encryptor.encrypt(pii)
    ct2 = encryptor.encrypt(pii)
    assert ct1 != ct2


# ---------------------------------------------------------------------------
# Property 8: Tokenize-Detokenize 라운드트립
# Feature: callbot-security, Property 8: Tokenize-Detokenize 라운드트립
# ---------------------------------------------------------------------------


@given(pii=st.text(min_size=1, max_size=200))
@settings(max_examples=100)
def test_tokenize_detokenize_roundtrip(pii: str):
    """Mock SecretsManager 주입, tokenize → detokenize → 원본 일치 검증.

    **Validates: Requirements 5.1, 5.2, 5.4**
    """
    mock_sm = _make_mock_sm()
    store = InMemoryTokenMappingStore()
    encryptor = PIIEncryptor(mock_sm, store)

    token = encryptor.tokenize(pii)
    result = encryptor.detokenize(token)
    assert result == pii


# ---------------------------------------------------------------------------
# Property 9: 동일 PII → 동일 토큰 (1:1 매핑)
# Feature: callbot-security, Property 9: 동일 PII → 동일 토큰 (1:1 매핑)
# ---------------------------------------------------------------------------


@given(pii=st.text(min_size=1, max_size=200))
@settings(max_examples=100)
def test_tokenize_same_pii_same_token(pii: str):
    """동일 PII 2회 tokenize → 동일 Masking_Token 검증.

    **Validates: Requirements 5.5**
    """
    mock_sm = _make_mock_sm()
    store = InMemoryTokenMappingStore()
    encryptor = PIIEncryptor(mock_sm, store)

    token1 = encryptor.tokenize(pii)
    token2 = encryptor.tokenize(pii)
    assert token1 == token2


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------


class TestPIIEncryptorUnit:
    """PIIEncryptor 단위 테스트."""

    def test_tampered_ciphertext_raises_decryption_error(self):
        """변조된 암호문 → DecryptionError (Req 4.5)."""
        mock_sm = _make_mock_sm()
        store = InMemoryTokenMappingStore()
        encryptor = PIIEncryptor(mock_sm, store)

        ciphertext = encryptor.encrypt("010-1234-5678")
        # 암호문의 마지막 바이트를 변조
        tampered = ciphertext[:-1] + bytes([(ciphertext[-1] + 1) % 256])

        with pytest.raises(DecryptionError):
            encryptor.decrypt(tampered)

    def test_nonexistent_token_raises_token_not_found(self):
        """존재하지 않는 토큰 → TokenNotFoundError (Req 5.3)."""
        mock_sm = _make_mock_sm()
        store = InMemoryTokenMappingStore()
        encryptor = PIIEncryptor(mock_sm, store)

        with pytest.raises(TokenNotFoundError):
            encryptor.detokenize("nonexistent-token-id")

    def test_encryption_key_wrong_length_raises_value_error(self):
        """32바이트가 아닌 키 → ValueError."""
        mock_sm = _make_mock_sm(key="short-key")  # 9 bytes, not 32
        store = InMemoryTokenMappingStore()
        encryptor = PIIEncryptor(mock_sm, store)

        with pytest.raises(ValueError, match="32 bytes"):
            encryptor.encrypt("some-pii")
