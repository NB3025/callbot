"""
Tests for TTSEngine — Task 5

Sub-task 5.1: Property 5 — TTS 속도 팩터 적용 불변성 (hypothesis)
Sub-task 5.2: Property 6 — TTS 속도 복원 라운드트립 (hypothesis)
Sub-task 5.3: Property 7 — TTS replay_last_response 라운드트립 (hypothesis)
Sub-task 5.4: format_number 단위 테스트
"""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.voice_io.tts_engine import TTSEngineBase, TTS_SPEED_MIN, TTS_SPEED_MAX, TTS_SPEED_DEFAULT
from callbot.voice_io.enums import NumberType
from callbot.voice_io.models import AudioStream


# ---------------------------------------------------------------------------
# Sub-task 5.1 — Property 5: TTS 속도 팩터 적용 불변성
# Validates: Requirements 3.3, 3.4, 3.5
# ---------------------------------------------------------------------------

@given(
    speed_factor=st.floats(min_value=TTS_SPEED_MIN, max_value=TTS_SPEED_MAX, allow_nan=False),
)
@settings(max_examples=100)
def test_tts_speed_factor_invariant(speed_factor: float):
    """
    **Validates: Requirements 3.3, 3.4, 3.5**

    Property 5: TTS 속도 팩터 적용 불변성
    임의의 speed_factor ∈ [0.7, 1.3]에 대해 set_speed 후 세션 속도가 해당 값으로 설정되는지 검증.
    """
    engine = TTSEngineBase()
    session_id = "session-prop5"
    engine.set_speed(session_id, speed_factor)
    assert engine._session_speeds[session_id] == speed_factor


# ---------------------------------------------------------------------------
# Sub-task 5.2 — Property 6: TTS 속도 복원 라운드트립
# Validates: Requirements 3.5
# ---------------------------------------------------------------------------

@given(
    speed_factor=st.floats(min_value=TTS_SPEED_MIN, max_value=TTS_SPEED_MAX, allow_nan=False),
)
@settings(max_examples=100)
def test_tts_speed_restore_roundtrip(speed_factor: float):
    """
    **Validates: Requirements 3.5**

    Property 6: TTS 속도 복원 라운드트립
    임의의 speed_factor로 set_speed 후 set_speed(1.0) 호출 시 기본 속도로 복원되는지 검증.
    """
    engine = TTSEngineBase()
    session_id = "session-prop6"
    engine.set_speed(session_id, speed_factor)
    engine.set_speed(session_id, TTS_SPEED_DEFAULT)
    assert engine._session_speeds[session_id] == TTS_SPEED_DEFAULT


# ---------------------------------------------------------------------------
# Sub-task 5.3 — Property 7: TTS replay_last_response 라운드트립
# Validates: Requirements 3.8
# ---------------------------------------------------------------------------

@given(
    text=st.text(min_size=1, max_size=200),
)
@settings(max_examples=100)
def test_tts_replay_last_response_roundtrip(text: str):
    """
    **Validates: Requirements 3.8**

    Property 7: TTS replay_last_response 라운드트립
    임의의 텍스트로 synthesize 후 replay_last_response 호출 시 동일 텍스트가 반환되는지 검증.
    """
    engine = TTSEngineBase()
    session_id = "session-prop7"
    engine.synthesize(text, session_id)
    assert engine._last_response[session_id] == text
    replayed = engine.replay_last_response(session_id)
    assert isinstance(replayed, AudioStream)
    assert replayed.session_id == session_id


# ---------------------------------------------------------------------------
# Sub-task 5.4 — format_number 단위 테스트
# Validates: Requirements 3.6
# ---------------------------------------------------------------------------

class TestFormatNumberAmount:
    """AMOUNT 타입 숫자 한국어 변환 테스트"""

    def test_amount_52000(self):
        """52000 → '오만 이천'"""
        engine = TTSEngineBase()
        assert engine.format_number("52000", NumberType.AMOUNT) == "오만 이천"

    def test_amount_1000(self):
        """1000 → '천'"""
        engine = TTSEngineBase()
        assert engine.format_number("1000", NumberType.AMOUNT) == "천"

    def test_amount_10000(self):
        """10000 → '만'"""
        engine = TTSEngineBase()
        assert engine.format_number("10000", NumberType.AMOUNT) == "만"

    def test_amount_100000(self):
        """100000 → '십만'"""
        engine = TTSEngineBase()
        assert engine.format_number("100000", NumberType.AMOUNT) == "십만"

    def test_amount_1(self):
        """1 → '일'"""
        engine = TTSEngineBase()
        assert engine.format_number("1", NumberType.AMOUNT) == "일"


class TestFormatNumberDate:
    """DATE 타입 숫자 한국어 변환 테스트"""

    def test_date_20240115(self):
        """20240115 → '이천이십사년 일월 십오일'"""
        engine = TTSEngineBase()
        assert engine.format_number("20240115", NumberType.DATE) == "이천이십사년 일월 십오일"

    def test_date_20000101(self):
        """20000101 → '이천년 일월 일일'"""
        engine = TTSEngineBase()
        assert engine.format_number("20000101", NumberType.DATE) == "이천년 일월 일일"

    def test_date_19991231(self):
        """19991231 → '천구백구십구년 십이월 삼십일일'"""
        engine = TTSEngineBase()
        assert engine.format_number("19991231", NumberType.DATE) == "천구백구십구년 십이월 삼십일일"


class TestFormatNumberPhone:
    """PHONE 타입 숫자 한국어 변환 테스트"""

    def test_phone_01012345678(self):
        """01012345678 → '공일공 일이삼사 오육칠팔'"""
        engine = TTSEngineBase()
        assert engine.format_number("01012345678", NumberType.PHONE) == "공일공 일이삼사 오육칠팔"

    def test_phone_0212345678(self):
        """0212345678 → '공이 일이삼사 오육칠팔'"""
        engine = TTSEngineBase()
        assert engine.format_number("0212345678", NumberType.PHONE) == "공이 일이삼사 오육칠팔"

    def test_phone_zero_digit(self):
        """0 → '공'"""
        engine = TTSEngineBase()
        assert engine.format_number("0", NumberType.PHONE) == "공"


class TestFormatNumberOrdinal:
    """ORDINAL 타입 숫자 한국어 변환 테스트"""

    def test_ordinal_3(self):
        """3 → '세 번째'"""
        engine = TTSEngineBase()
        assert engine.format_number("3", NumberType.ORDINAL) == "세 번째"

    def test_ordinal_1(self):
        """1 → '첫 번째'"""
        engine = TTSEngineBase()
        assert engine.format_number("1", NumberType.ORDINAL) == "첫 번째"

    def test_ordinal_2(self):
        """2 → '두 번째'"""
        engine = TTSEngineBase()
        assert engine.format_number("2", NumberType.ORDINAL) == "두 번째"


class TestTTSEngineBaseSetSpeed:
    """set_speed 범위 검증 테스트"""

    def test_set_speed_min_boundary(self):
        """speed_factor=0.7 설정 가능"""
        engine = TTSEngineBase()
        engine.set_speed("s1", 0.7)
        assert engine._session_speeds["s1"] == 0.7

    def test_set_speed_max_boundary(self):
        """speed_factor=1.3 설정 가능"""
        engine = TTSEngineBase()
        engine.set_speed("s1", 1.3)
        assert engine._session_speeds["s1"] == 1.3

    def test_set_speed_default(self):
        """speed_factor=1.0 설정 가능"""
        engine = TTSEngineBase()
        engine.set_speed("s1", 1.0)
        assert engine._session_speeds["s1"] == 1.0

    def test_set_speed_below_range_raises(self):
        """speed_factor < 0.7 → ValueError"""
        engine = TTSEngineBase()
        with pytest.raises(ValueError):
            engine.set_speed("s1", 0.69)

    def test_set_speed_above_range_raises(self):
        """speed_factor > 1.3 → ValueError"""
        engine = TTSEngineBase()
        with pytest.raises(ValueError):
            engine.set_speed("s1", 1.31)

    def test_set_speed_persists_across_sessions(self):
        """서로 다른 세션의 속도는 독립적으로 관리된다"""
        engine = TTSEngineBase()
        engine.set_speed("s1", 0.7)
        engine.set_speed("s2", 1.3)
        assert engine._session_speeds["s1"] == 0.7
        assert engine._session_speeds["s2"] == 1.3


class TestTTSEngineBaseSynthesize:
    """synthesize 및 replay_last_response 테스트"""

    def test_synthesize_returns_audio_stream(self):
        """synthesize()는 AudioStream을 반환한다"""
        engine = TTSEngineBase()
        result = engine.synthesize("안녕하세요", "s1")
        assert isinstance(result, AudioStream)
        assert result.session_id == "s1"

    def test_synthesize_stores_last_response(self):
        """synthesize() 후 _last_response에 텍스트가 저장된다"""
        engine = TTSEngineBase()
        engine.synthesize("안녕하세요", "s1")
        assert engine._last_response["s1"] == "안녕하세요"

    def test_replay_last_response_returns_audio_stream(self):
        """replay_last_response()는 AudioStream을 반환한다"""
        engine = TTSEngineBase()
        engine.synthesize("테스트 텍스트", "s1")
        result = engine.replay_last_response("s1")
        assert isinstance(result, AudioStream)
        assert result.session_id == "s1"

    def test_replay_last_response_no_prior_synthesize_raises(self):
        """synthesize() 없이 replay_last_response() 호출 시 KeyError 또는 ValueError"""
        engine = TTSEngineBase()
        with pytest.raises((KeyError, ValueError)):
            engine.replay_last_response("s-unknown")

    def test_stop_playback_does_not_raise(self):
        """stop_playback()은 예외 없이 실행된다"""
        engine = TTSEngineBase()
        engine.stop_playback("s1")  # should not raise
