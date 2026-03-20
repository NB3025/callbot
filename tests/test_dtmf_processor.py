"""
Tests for DTMFProcessor — Task 3

Sub-task 3.1: Property 3 — DTMF input_type 라운드트립 (hypothesis)
Sub-task 3.2: Property 4 — DTMF digits 숫자 문자 불변성 (hypothesis)
Sub-task 3.3: DTMF 완료/타임아웃 단위 테스트
"""
import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.voice_io.dtmf_processor import DTMFProcessor


# ---------------------------------------------------------------------------
# Sub-task 3.1 — Property 3: DTMF input_type 라운드트립
# Validates: Requirements 2.4
# ---------------------------------------------------------------------------

@given(
    input_type=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_")),
    expected_length=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_dtmf_input_type_roundtrip(input_type: str, expected_length: int):
    """
    **Validates: Requirements 2.4**

    Property 3: DTMF input_type 라운드트립
    임의의 input_type으로 start_capture 후 get_input 결과의 input_type이 동일한지 검증.
    """
    processor = DTMFProcessor()
    session_id = "test-session"
    processor.start_capture(session_id, expected_length, input_type=input_type)
    result = processor.get_input(session_id)
    assert result.input_type == input_type


# ---------------------------------------------------------------------------
# Sub-task 3.2 — Property 4: DTMF digits 숫자 문자 불변성
# Validates: Requirements 2.5
# ---------------------------------------------------------------------------

@given(
    raw_digits=st.text(
        min_size=0,
        max_size=10,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Po"), whitelist_characters="*#ABCD"),
    ),
    expected_length=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_dtmf_digits_only_numeric(raw_digits: str, expected_length: int):
    """
    **Validates: Requirements 2.5**

    Property 4: DTMF digits 숫자 문자 불변성
    임의의 DTMF 입력 시퀀스에 대해 digits가 항상 숫자 문자(0~9)만 포함하는지 검증.
    """
    processor = DTMFProcessor()
    session_id = "test-session"
    processor.start_capture(session_id, expected_length)
    for ch in raw_digits:
        processor.push_digit(session_id, ch)
    result = processor.get_input(session_id)
    assert all(c.isdigit() for c in result.digits), (
        f"digits={result.digits!r} contains non-numeric characters"
    )


# ---------------------------------------------------------------------------
# Sub-task 3.3 — DTMF 완료/타임아웃 단위 테스트
# Validates: Requirements 2.1, 2.2, 2.3, 2.4
# ---------------------------------------------------------------------------

class TestDTMFCompletion:
    """자릿수 완료 시 is_complete=True 테스트"""

    def test_birth_date_6_digits_complete(self):
        """6자리 생년월일 입력 완료 시 is_complete=True"""
        processor = DTMFProcessor()
        processor.start_capture("s1", expected_length=6, input_type="birth_date")
        for d in "901225":
            processor.push_digit("s1", d)
        result = processor.get_input("s1")
        assert result.is_complete is True
        assert result.is_timeout is False
        assert result.digits == "901225"
        assert result.input_type == "birth_date"

    def test_password_4_digits_complete(self):
        """4자리 비밀번호 입력 완료 시 is_complete=True"""
        processor = DTMFProcessor()
        processor.start_capture("s2", expected_length=4, input_type="password")
        for d in "1234":
            processor.push_digit("s2", d)
        result = processor.get_input("s2")
        assert result.is_complete is True
        assert result.is_timeout is False
        assert result.digits == "1234"
        assert result.input_type == "password"

    def test_satisfaction_1_digit_complete(self):
        """1자리 만족도 입력 완료 시 is_complete=True"""
        processor = DTMFProcessor()
        processor.start_capture("s3", expected_length=1, input_type="satisfaction")
        processor.push_digit("s3", "5")
        result = processor.get_input("s3")
        assert result.is_complete is True
        assert result.is_timeout is False
        assert result.digits == "5"
        assert result.input_type == "satisfaction"

    def test_non_numeric_digits_filtered(self):
        """숫자가 아닌 문자는 digits에서 필터링된다"""
        processor = DTMFProcessor()
        processor.start_capture("s4", expected_length=4, input_type="password")
        for ch in "1*2#":
            processor.push_digit("s4", ch)
        result = processor.get_input("s4")
        # Only '1' and '2' pass the filter — not complete yet
        assert result.digits == "12"
        assert result.is_complete is False


class TestDTMFTimeout:
    """타임아웃 처리 테스트"""

    def test_timeout_sets_is_timeout_true(self):
        """5초 타임아웃 시 is_timeout=True, is_complete=False"""
        processor = DTMFProcessor()
        # Use a very short timeout for testing
        processor.start_capture("s5", expected_length=6, input_type="birth_date", timeout_sec=0)
        # Simulate timeout by advancing time
        processor._sessions["s5"]["start_time"] -= 1  # force timeout
        result = processor.get_input("s5")
        assert result.is_timeout is True
        assert result.is_complete is False

    def test_partial_input_on_timeout(self):
        """타임아웃 시 부분 입력값이 digits에 포함된다"""
        processor = DTMFProcessor()
        processor.start_capture("s6", expected_length=6, input_type="birth_date", timeout_sec=5)
        for d in "901":
            processor.push_digit("s6", d)
        # Force timeout
        processor._sessions["s6"]["start_time"] -= 10
        result = processor.get_input("s6")
        assert result.is_timeout is True
        assert result.digits == "901"
        assert result.is_complete is False

    def test_complete_before_timeout_no_timeout(self):
        """완료 전 타임아웃이 발생하지 않으면 is_timeout=False"""
        processor = DTMFProcessor()
        processor.start_capture("s7", expected_length=4, input_type="password", timeout_sec=5)
        for d in "5678":
            processor.push_digit("s7", d)
        result = processor.get_input("s7")
        assert result.is_complete is True
        assert result.is_timeout is False
