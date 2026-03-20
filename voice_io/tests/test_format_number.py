# Feature: callbot-voice-io, Property 3: format_number 위임 일관성
"""Property 3: format_number 위임 일관성

TTSEngineBase.format_number(value, number_type)의 반환값이
tts_engine.py의 공개 헬퍼 함수를 직접 호출한 결과와 동일한지 검증한다.

**Validates: Requirements 2.5**
"""
from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given, settings

from callbot.voice_io.enums import NumberType
from callbot.voice_io.tts_engine import (
    TTSEngineBase,
    format_amount,
    format_date,
    format_ordinal,
    format_phone,
)


# ---------------------------------------------------------------------------
# 전략(Strategy): NumberType별 유효한 value 생성
# ---------------------------------------------------------------------------

_HELPER_MAP = {
    NumberType.AMOUNT: format_amount,
    NumberType.DATE: format_date,
    NumberType.PHONE: format_phone,
    NumberType.ORDINAL: format_ordinal,
}


def _amount_strategy() -> st.SearchStrategy[str]:
    """AMOUNT: 0~999,999,999 범위 정수 → str."""
    return st.integers(min_value=0, max_value=999_999_999).map(str)


def _date_strategy() -> st.SearchStrategy[str]:
    """DATE: 유효한 YYYYMMDD 문자열."""
    return st.dates().map(lambda d: d.strftime("%Y%m%d"))


def _phone_strategy() -> st.SearchStrategy[str]:
    """PHONE: 9~11자리 숫자 문자열."""
    return st.integers(min_value=9, max_value=11).flatmap(
        lambda length: st.text(
            alphabet="0123456789", min_size=length, max_size=length
        )
    )


def _ordinal_strategy() -> st.SearchStrategy[str]:
    """ORDINAL: 1~100 범위 양의 정수 → str."""
    return st.integers(min_value=1, max_value=100).map(str)


@st.composite
def number_type_and_value(draw: st.DrawFn):
    """(NumberType, value) 쌍을 생성한다."""
    nt = draw(st.sampled_from(NumberType))
    if nt == NumberType.AMOUNT:
        value = draw(_amount_strategy())
    elif nt == NumberType.DATE:
        value = draw(_date_strategy())
    elif nt == NumberType.PHONE:
        value = draw(_phone_strategy())
    else:  # ORDINAL
        value = draw(_ordinal_strategy())
    return nt, value


# ---------------------------------------------------------------------------
# Property 3: format_number 위임 일관성
# ---------------------------------------------------------------------------

@given(data=number_type_and_value())
@settings(max_examples=100)
def test_format_number_delegates_to_public_helpers(data: tuple[NumberType, str]) -> None:
    """TTSEngineBase.format_number()는 공개 헬퍼 함수에 위임하며 결과가 동일하다.

    **Validates: Requirements 2.5**
    """
    number_type, value = data
    engine = TTSEngineBase()

    # TTSEngineBase.format_number() 호출
    engine_result = engine.format_number(value, number_type)

    # 공개 헬퍼 함수 직접 호출
    helper_fn = _HELPER_MAP[number_type]
    direct_result = helper_fn(value)

    assert engine_result == direct_result, (
        f"Mismatch for {number_type.name} with value={value!r}: "
        f"engine={engine_result!r}, helper={direct_result!r}"
    )
