"""TTS 벤더 어댑터 PBT + 단위 테스트.

Feature: callbot-voice-io
"""
from __future__ import annotations

import inspect
import logging

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.voice_io.enums import NumberType
from callbot.voice_io.exceptions import VendorConnectionError
from callbot.voice_io.models import AudioStream
from callbot.voice_io.tts_engine import (
    TTS_SPEED_DEFAULT,
    TTS_SPEED_MAX,
    TTS_SPEED_MIN,
    TTSEngine,
    format_amount,
    format_date,
    format_ordinal,
    format_phone,
)
from callbot.voice_io.tts_vendor_adapter import TTSVendorAdapter
from callbot.voice_io.vendor_adapter import VendorAdapter
from callbot.voice_io.vendor_config import VendorConfig


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockPollyClient:
    def __init__(
        self,
        audio_data: bytes = b"\x00\x01",
        health_ok: bool = True,
        fail_on_synthesize: bool = False,
    ):
        self._audio_data = audio_data
        self._health_ok = health_ok
        self._fail_on_synthesize = fail_on_synthesize
        self.last_synthesize_call: dict | None = None

    def synthesize_speech(self, **kwargs):
        if self._fail_on_synthesize:
            raise ConnectionError("Polly connection failed")
        self.last_synthesize_call = kwargs
        return {"AudioStream": self._audio_data}

    def describe_voices(self, **kwargs):
        if not self._health_ok:
            raise ConnectionError("health check failed")
        return {"Voices": []}

    def close(self):
        pass



def _make_config() -> VendorConfig:
    return VendorConfig(stt_vendor="aws-transcribe", tts_vendor="aws-polly")


def _make_adapter(
    *,
    client: MockPollyClient | None = None,
) -> TTSVendorAdapter:
    return TTSVendorAdapter(
        config=_make_config(),
        client=client or MockPollyClient(),
    )


# ===========================================================================
# 7.2  Property 2: TTS 속도 팩터 범위 검증 PBT
# Feature: callbot-voice-io, Property 2: TTS 속도 팩터 범위 검증
# ===========================================================================


class TestTTSSpeedFactorRangePBT:
    """**Validates: Requirements 2.4**"""

    @given(
        speed_factor=st.floats(
            min_value=0.0, max_value=3.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(max_examples=100)
    def test_speed_factor_range(self, speed_factor: float) -> None:
        # Feature: callbot-voice-io, Property 2: TTS 속도 팩터 범위 검증
        adapter = _make_adapter()
        session_id = "session-pbt"

        if TTS_SPEED_MIN <= speed_factor <= TTS_SPEED_MAX:
            adapter.set_speed(session_id, speed_factor)
            assert adapter._session_speeds[session_id] == speed_factor
        else:
            with pytest.raises(ValueError):
                adapter.set_speed(session_id, speed_factor)


# ===========================================================================
# 7.3  Property 4: replay_last_response 텍스트 라운드트립 PBT
# Feature: callbot-voice-io, Property 4: replay_last_response 텍스트 라운드트립
# ===========================================================================


class TestReplayLastResponseRoundtripPBT:
    """**Validates: Requirements 2.6**"""

    @given(text=st.text(min_size=1))
    @settings(max_examples=100)
    def test_replay_sends_same_text(self, text: str) -> None:
        # Feature: callbot-voice-io, Property 4: replay_last_response 텍스트 라운드트립
        client = MockPollyClient()
        adapter = _make_adapter(client=client)
        session_id = "session-replay"

        adapter.synthesize(text, session_id)
        client.last_synthesize_call = None  # reset tracking

        adapter.replay_last_response(session_id)

        assert client.last_synthesize_call is not None
        ssml = client.last_synthesize_call["Text"]
        speed = adapter._session_speeds.get(session_id, TTS_SPEED_DEFAULT)
        rate_pct = int(speed * 100)
        expected_ssml = f'<speak><prosody rate="{rate_pct}%">{text}</prosody></speak>'
        assert ssml == expected_ssml


# ===========================================================================
# 7.4  TTS 벤더 어댑터 단위 테스트
# ===========================================================================


class TestTTSVendorAdapterUnit:
    """TTS 벤더 어댑터 단위 테스트."""

    # --- isinstance 확인 ---

    def test_isinstance_tts_engine(self) -> None:
        adapter = _make_adapter()
        assert isinstance(adapter, TTSEngine)

    def test_isinstance_vendor_adapter(self) -> None:
        adapter = _make_adapter()
        assert isinstance(adapter, VendorAdapter)

    # --- synthesize → AudioStream ---

    def test_synthesize_returns_audio_stream(self) -> None:
        adapter = _make_adapter()
        result = adapter.synthesize("안녕하세요", "session-1")
        assert isinstance(result, AudioStream)
        assert result.session_id == "session-1"
        assert len(result.data) > 0

    # --- stop_playback → 리소스 해제 ---

    def test_stop_playback_clears_session(self) -> None:
        adapter = _make_adapter()
        adapter.synthesize("hello", "session-1")
        adapter.set_speed("session-1", 1.1)

        adapter.stop_playback("session-1")

        assert "session-1" not in adapter._session_speeds
        assert "session-1" not in adapter._last_response

    # --- set_speed 범위 검증: 경계값 단위 테스트 (PBT 보완) ---

    def test_set_speed_at_min_boundary(self) -> None:
        adapter = _make_adapter()
        adapter.set_speed("s1", TTS_SPEED_MIN)
        assert adapter._session_speeds["s1"] == TTS_SPEED_MIN

    def test_set_speed_at_max_boundary(self) -> None:
        adapter = _make_adapter()
        adapter.set_speed("s1", TTS_SPEED_MAX)
        assert adapter._session_speeds["s1"] == TTS_SPEED_MAX

    def test_set_speed_below_min_raises(self) -> None:
        adapter = _make_adapter()
        with pytest.raises(ValueError):
            adapter.set_speed("s1", TTS_SPEED_MIN - 0.01)

    def test_set_speed_above_max_raises(self) -> None:
        adapter = _make_adapter()
        with pytest.raises(ValueError):
            adapter.set_speed("s1", TTS_SPEED_MAX + 0.01)

    # --- format_number 위임 호출 확인 ---

    def test_format_number_amount(self) -> None:
        adapter = _make_adapter()
        result = adapter.format_number("52000", NumberType.AMOUNT)
        assert result == format_amount("52000")

    def test_format_number_date(self) -> None:
        adapter = _make_adapter()
        result = adapter.format_number("20240115", NumberType.DATE)
        assert result == format_date("20240115")

    def test_format_number_phone(self) -> None:
        adapter = _make_adapter()
        result = adapter.format_number("01012345678", NumberType.PHONE)
        assert result == format_phone("01012345678")

    def test_format_number_ordinal(self) -> None:
        adapter = _make_adapter()
        result = adapter.format_number("3", NumberType.ORDINAL)
        assert result == format_ordinal("3")

    # --- replay_last_response → 직전 synthesize 텍스트 재합성 ---

    def test_replay_last_response(self) -> None:
        client = MockPollyClient()
        adapter = _make_adapter(client=client)
        adapter.synthesize("다시 말씀해 주세요", "session-1")

        result = adapter.replay_last_response("session-1")

        assert isinstance(result, AudioStream)
        assert result.session_id == "session-1"
        ssml = client.last_synthesize_call["Text"]
        assert "다시 말씀해 주세요" in ssml

    def test_replay_no_prior_synthesize_raises(self) -> None:
        adapter = _make_adapter()
        with pytest.raises(KeyError):
            adapter.replay_last_response("no-such-session")

    # --- 동기 시그니처 검증 ---

    def test_sync_signatures(self) -> None:
        adapter = _make_adapter()
        assert not inspect.iscoroutinefunction(adapter.synthesize)
        assert not inspect.iscoroutinefunction(adapter.stop_playback)
        assert not inspect.iscoroutinefunction(adapter.set_speed)
        assert not inspect.iscoroutinefunction(adapter.format_number)
        assert not inspect.iscoroutinefunction(adapter.replay_last_response)
        assert not inspect.iscoroutinefunction(adapter.health_check)
        assert not inspect.iscoroutinefunction(adapter.close)

    # --- health_check 성공/실패 ---

    def test_health_check_success(self) -> None:
        client = MockPollyClient(health_ok=True)
        adapter = _make_adapter(client=client)
        assert adapter.health_check() is True

    def test_health_check_failure(self) -> None:
        client = MockPollyClient(health_ok=False)
        adapter = _make_adapter(client=client)
        assert adapter.health_check() is False

    # --- 벤더 SDK 연결 오류 → VendorConnectionError ---

    def test_synthesize_sdk_failure_raises_vendor_error(self) -> None:
        client = MockPollyClient(fail_on_synthesize=True)
        adapter = _make_adapter(client=client)
        with pytest.raises(VendorConnectionError) as exc_info:
            adapter.synthesize("test", "session-1")
        assert exc_info.value.vendor == "aws-polly"

    # --- close 후 내부 상태 정리 ---

    def test_close_clears_all_state(self) -> None:
        adapter = _make_adapter()
        adapter.synthesize("hello", "s1")
        adapter.set_speed("s1", 1.1)
        adapter.synthesize("world", "s2")

        adapter.close()

        assert len(adapter._session_speeds) == 0
        assert len(adapter._last_response) == 0

    # --- synthesize 소요 시간 로그 기록 ---

    def test_synthesize_logs_elapsed_time(self, caplog) -> None:
        adapter = _make_adapter()
        with caplog.at_level(logging.INFO):
            adapter.synthesize("test", "session-1")

        assert any(
            "aws-polly" in r.message and "ms" in r.message
            for r in caplog.records
        )

    # --- 실패 시 로그에 벤더 식별자, 에러 유형, 소요 시간 포함 ---

    def test_failure_log_contains_vendor_info(self, caplog) -> None:
        client = MockPollyClient(fail_on_synthesize=True)
        adapter = _make_adapter(client=client)

        with caplog.at_level(logging.ERROR):
            with pytest.raises(VendorConnectionError):
                adapter.synthesize("test", "session-1")

        assert any("aws-polly" in r.message for r in caplog.records)
        assert any("ConnectionError" in r.message for r in caplog.records)
        assert any("elapsed" in r.message for r in caplog.records)
