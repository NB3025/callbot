"""PIIMasker 테스트 — Property 10 (PII 마스킹 완전성) + 단위 테스트."""

import copy

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.external.pii_masker import PIIMasker

PII_FIELDS = [
    "phone",
    "birthdate",
    "name",
    "address",
    "account_number",
    "card_number",
    "customer_id",
]


# ---------------------------------------------------------------------------
# Property 10: PII 마스킹 완전성
# Feature: callbot-external-api-integration, Property 10: PII 마스킹 완전성
# **Validates: Requirements 10.4**
# ---------------------------------------------------------------------------


@given(st.dictionaries(st.sampled_from(PII_FIELDS), st.text(min_size=1)))
@settings(max_examples=100)
def test_pii_masking_completeness(data: dict) -> None:
    """마스킹 결과에 원본 PII 값이 포함되지 않고, 원본 dict가 변경되지 않음을 검증."""
    original = copy.deepcopy(data)
    masked = PIIMasker.mask(data)

    # 마스킹 결과에 원본 PII 값이 포함되지 않아야 함
    for key, value in original.items():
        if value != "***":
            assert masked[key] != value, (
                f"PII field '{key}' was not masked: {masked[key]}"
            )

    # 원본 dict가 변경되지 않아야 함
    assert data == original, "Original dict was mutated"


# ---------------------------------------------------------------------------
# 단위 테스트 — Requirements: 10.4
# ---------------------------------------------------------------------------


class TestMaskFlatDict:
    """평면 dict에서 PII 필드 마스킹 검증."""

    def test_mask_flat_dict(self) -> None:
        data = {
            "phone": "010-1234-5678",
            "birthdate": "1990-01-01",
            "name": "홍길동",
            "status": "active",
        }
        masked = PIIMasker.mask(data)
        assert masked["phone"] == "***"
        assert masked["birthdate"] == "***"
        assert masked["name"] == "***"
        assert masked["status"] == "active"


class TestMaskNestedDict:
    """중첩 dict에서 재귀 마스킹 검증."""

    def test_mask_nested_dict(self) -> None:
        data = {
            "customer": {
                "name": "홍길동",
                "address": "서울시 강남구",
                "account_number": "123-456-789",
            },
            "request_id": "req-001",
        }
        masked = PIIMasker.mask(data)
        assert masked["customer"]["name"] == "***"
        assert masked["customer"]["address"] == "***"
        assert masked["customer"]["account_number"] == "***"
        assert masked["request_id"] == "req-001"


class TestMaskNoPiiFields:
    """PII 필드 없는 dict는 그대로 반환."""

    def test_mask_no_pii_fields(self) -> None:
        data = {"status": "active", "code": "200", "message": "OK"}
        masked = PIIMasker.mask(data)
        assert masked == data


class TestMaskDoesNotMutateOriginal:
    """원본 dict 불변 검증."""

    def test_mask_does_not_mutate_original(self) -> None:
        data = {
            "phone": "010-1234-5678",
            "card_number": "1234-5678-9012-3456",
            "nested": {"customer_id": "C001"},
        }
        original = copy.deepcopy(data)
        PIIMasker.mask(data)
        assert data == original
