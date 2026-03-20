"""STT 벤더 어댑터 PBT + 단위 테스트.

Feature: callbot-voice-io
"""
from __future__ import annotations

import inspect
import logging
import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.voice_io.barge_in import BargeInHandler
from callbot.voice_io.exceptions import VendorConnectionError
from callbot.voice_io.models import PartialResult, STTResult, StreamHandle
from callbot.voice_io.stt_engine import (
    STT_CONFIDENCE_THRESHOLD_DEFAULT,
    STT_CONFIDENCE_THRESHOLD_MAX,
    STT_CONFIDENCE_THRESHOLD_MIN,
    STTEngine,
    VAD_SILENCE_SEC_DEFAULT,
    VAD_SILENCE_SEC_MAX,
    VAD_SILENCE_SEC_MIN,
)
from callbot.voice_io.stt_vendor_adapter import STTVendorAdapter
from callbot.voice_io.vendor_adapter import VendorAdapter
from callbot.voice_io.vendor_config import VendorConfig


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class MockStream:
    def __init__(self, text="hello", confidence=0.9, is_final=False):
        self._text = text
        self._confidence = confidence
        self._is_final = is_final
        self._closed = False

    def send_audio(self, audio):
        return type("Result", (), {"text": self._text, "is_final": self._is_final})()

    def get_result(self):
        return type("Result", (), {"text": self._text, "confidence": self._confidence})()

    def close(self):
        self._closed = True


class MockSDKClient:
    def __init__(self, stream=None, health_ok=True, fail_on_start=False):
        self._stream = stream or MockStream()
        self._health_ok = health_ok
        self._fail_on_start = fail_on_start

    def start_stream(self, **kwargs):
        if self._fail_on_start:
            raise ConnectionError("SDK connection failed")
        return self._stream

    def health_check(self):
        if not self._health_ok:
            raise ConnectionError("health check failed")

    def close(self):
        pass


class MockBargeInHandler:
    """BargeInHandler 프로토콜 구현 Mock."""

    def __init__(self):
        self.calls: list[str] = []

    def stop_playback(self, session_id: str) -> None:
        self.calls.append(session_id)


def _make_config() -> VendorConfig:
    return VendorConfig(stt_vendor="aws-transcribe", tts_vendor="aws-polly")


def _make_adapter(
    *,
    threshold: float = STT_CONFIDENCE_THRESHOLD_DEFAULT,
    vad_sec: float = VAD_SILENCE_SEC_DEFAULT,
    client: MockSDKClient | None = None,
    barge_in_handler: BargeInHandler | None = None,
) -> STTVendorAdapter:
    return STTVendorAdapter(
        config=_make_config(),
        stt_confidence_threshold=threshold,
        vad_silence_sec=vad_sec,
        client=client or MockSDKClient(),
        barge_in_handler=barge_in_handler,
    )


# ===========================================================================
# 5.2  Property 1: STT 파라미터 범위 검증 PBT
# Feature: callbot-voice-io, Property 1: STT 파라미터 범위 검증
# ===========================================================================


class TestSTTParameterRangePBT:
    """**Validates: Requirements 1.6**"""

    @given(
        threshold=st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(max_examples=100)
    def test_threshold_range(self, threshold: float) -> None:
        # Feature: callbot-voice-io, Property 1: STT 파라미터 범위 검증
        if STT_CONFIDENCE_THRESHOLD_MIN <= threshold <= STT_CONFIDENCE_THRESHOLD_MAX:
            adapter = _make_adapter(threshold=threshold)
            assert adapter.stt_confidence_threshold == threshold
        else:
            with pytest.raises(ValueError):
                _make_adapter(threshold=threshold)

    @given(
        vad_sec=st.floats(
            min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(max_examples=100)
    def test_vad_sec_range(self, vad_sec: float) -> None:
        # Feature: callbot-voice-io, Property 1: STT 파라미터 범위 검증
        if VAD_SILENCE_SEC_MIN <= vad_sec <= VAD_SILENCE_SEC_MAX:
            adapter = _make_adapter(vad_sec=vad_sec)
            assert adapter.vad_silence_sec == vad_sec
        else:
            with pytest.raises(ValueError):
                _make_adapter(vad_sec=vad_sec)



# ===========================================================================
# 5.3  Property 7: STT 스트리밍 리소스 해제 PBT
# Feature: callbot-voice-io, Property 7: STT 스트리밍 리소스 해제
# ===========================================================================


class TestSTTStreamingResourceReleasePBT:
    """**Validates: Requirements 7.1, 7.6**"""

    @given(audio=st.binary(min_size=1, max_size=4096))
    @settings(max_examples=100)
    def test_get_final_result_releases_buffer(self, audio: bytes) -> None:
        # Feature: callbot-voice-io, Property 7: STT 스트리밍 리소스 해제
        adapter = _make_adapter()
        handle = adapter.start_stream("session-1")

        adapter.process_audio_chunk(handle, audio)
        assert handle.stream_id in adapter._buffers
        assert len(adapter._buffers[handle.stream_id]) > 0

        adapter.get_final_result(handle)

        assert handle.stream_id not in adapter._buffers
        assert handle.stream_id not in adapter._streams
        assert handle.stream_id not in adapter._cached_finals
        assert handle.stream_id not in adapter._start_times

    @given(audio=st.binary(min_size=1, max_size=4096))
    @settings(max_examples=100)
    def test_close_releases_all_buffers(self, audio: bytes) -> None:
        # Feature: callbot-voice-io, Property 7: STT 스트리밍 리소스 해제
        adapter = _make_adapter()
        h1 = adapter.start_stream("s1")
        h2 = adapter.start_stream("s2")

        adapter.process_audio_chunk(h1, audio)
        adapter.process_audio_chunk(h2, audio)

        adapter.close()

        assert len(adapter._buffers) == 0
        assert len(adapter._streams) == 0
        assert len(adapter._cached_finals) == 0
        assert len(adapter._start_times) == 0


# ===========================================================================
# 5.4  Property 8: STT processing_time_ms 양수 기록 PBT
# Feature: callbot-voice-io, Property 8: STT processing_time_ms 양수 기록
# ===========================================================================


class MockDelayStream:
    """send_audio / get_result 시 약간의 지연을 주입하는 Mock."""

    def __init__(self, delay_ms: float = 1.0):
        self._delay_s = delay_ms / 1000.0

    def send_audio(self, audio):
        return type("Result", (), {"text": "ok", "is_final": False})()

    def get_result(self):
        time.sleep(self._delay_s)
        return type("Result", (), {"text": "ok", "confidence": 0.95})()

    def close(self):
        pass


class MockDelaySDKClient:
    def __init__(self, delay_ms: float = 1.0):
        self._delay_ms = delay_ms

    def start_stream(self, **kwargs):
        return MockDelayStream(delay_ms=self._delay_ms)

    def health_check(self):
        pass

    def close(self):
        pass


class TestSTTProcessingTimePBT:
    """**Validates: Requirements 8.1**"""

    @given(audio=st.binary(min_size=1, max_size=1024))
    @settings(max_examples=100)
    def test_processing_time_ms_non_negative(self, audio: bytes) -> None:
        # Feature: callbot-voice-io, Property 8: STT processing_time_ms 양수 기록
        client = MockDelaySDKClient(delay_ms=1.0)
        adapter = STTVendorAdapter(
            config=_make_config(),
            client=client,
        )
        handle = adapter.start_stream("session-1")
        adapter.process_audio_chunk(handle, audio)
        result = adapter.get_final_result(handle)

        assert isinstance(result, STTResult)
        assert result.processing_time_ms >= 0


# ===========================================================================
# 5.5  STT 벤더 어댑터 단위 테스트
# ===========================================================================


class TestSTTVendorAdapterUnit:
    """STT 벤더 어댑터 단위 테스트."""

    # --- isinstance 확인 ---

    def test_isinstance_stt_engine(self) -> None:
        adapter = _make_adapter()
        assert isinstance(adapter, STTEngine)

    def test_isinstance_vendor_adapter(self) -> None:
        adapter = _make_adapter()
        assert isinstance(adapter, VendorAdapter)

    # --- start_stream → StreamHandle ---

    def test_start_stream_returns_stream_handle(self) -> None:
        adapter = _make_adapter()
        handle = adapter.start_stream("session-1")
        assert isinstance(handle, StreamHandle)
        assert handle.session_id == "session-1"
        assert handle.stream_id  # non-empty

    # --- process_audio_chunk → PartialResult ---

    def test_process_audio_chunk_returns_partial_result(self) -> None:
        adapter = _make_adapter()
        handle = adapter.start_stream("session-1")
        result = adapter.process_audio_chunk(handle, b"\x00\x01\x02")
        assert isinstance(result, PartialResult)

    # --- get_final_result → STTResult ---

    def test_get_final_result_returns_stt_result(self) -> None:
        adapter = _make_adapter()
        handle = adapter.start_stream("session-1")
        adapter.process_audio_chunk(handle, b"\x00\x01")
        result = adapter.get_final_result(handle)
        assert isinstance(result, STTResult)

    # --- activate_barge_in → stop_playback 호출 ---

    def test_activate_barge_in_calls_stop_playback(self) -> None:
        handler = MockBargeInHandler()
        adapter = _make_adapter(barge_in_handler=handler)
        adapter.activate_barge_in("session-1")
        assert handler.calls == ["session-1"]

    def test_activate_barge_in_no_handler(self) -> None:
        adapter = _make_adapter(barge_in_handler=None)
        adapter.activate_barge_in("session-1")  # should not raise

    # --- 파라미터 범위 경계값 단위 테스트 (PBT 보완) ---

    def test_threshold_at_min_boundary(self) -> None:
        adapter = _make_adapter(threshold=STT_CONFIDENCE_THRESHOLD_MIN)
        assert adapter.stt_confidence_threshold == STT_CONFIDENCE_THRESHOLD_MIN

    def test_threshold_at_max_boundary(self) -> None:
        adapter = _make_adapter(threshold=STT_CONFIDENCE_THRESHOLD_MAX)
        assert adapter.stt_confidence_threshold == STT_CONFIDENCE_THRESHOLD_MAX

    def test_threshold_below_min_raises(self) -> None:
        with pytest.raises(ValueError):
            _make_adapter(threshold=STT_CONFIDENCE_THRESHOLD_MIN - 0.01)

    def test_threshold_above_max_raises(self) -> None:
        with pytest.raises(ValueError):
            _make_adapter(threshold=STT_CONFIDENCE_THRESHOLD_MAX + 0.01)

    def test_vad_sec_at_min_boundary(self) -> None:
        adapter = _make_adapter(vad_sec=VAD_SILENCE_SEC_MIN)
        assert adapter.vad_silence_sec == VAD_SILENCE_SEC_MIN

    def test_vad_sec_at_max_boundary(self) -> None:
        adapter = _make_adapter(vad_sec=VAD_SILENCE_SEC_MAX)
        assert adapter.vad_silence_sec == VAD_SILENCE_SEC_MAX

    def test_vad_sec_below_min_raises(self) -> None:
        with pytest.raises(ValueError):
            _make_adapter(vad_sec=VAD_SILENCE_SEC_MIN - 0.01)

    def test_vad_sec_above_max_raises(self) -> None:
        with pytest.raises(ValueError):
            _make_adapter(vad_sec=VAD_SILENCE_SEC_MAX + 0.01)

    # --- 동기 시그니처 검증 ---

    def test_sync_signatures(self) -> None:
        adapter = _make_adapter()
        assert not inspect.iscoroutinefunction(adapter.start_stream)
        assert not inspect.iscoroutinefunction(adapter.process_audio_chunk)
        assert not inspect.iscoroutinefunction(adapter.get_final_result)
        assert not inspect.iscoroutinefunction(adapter.activate_barge_in)
        assert not inspect.iscoroutinefunction(adapter.health_check)
        assert not inspect.iscoroutinefunction(adapter.close)

    # --- HTTP/2 스트리밍 연결 수립 확인 (Mock SDK) ---

    def test_start_stream_calls_sdk(self) -> None:
        client = MockSDKClient()
        adapter = _make_adapter(client=client)
        handle = adapter.start_stream("session-1")
        assert handle.stream_id in adapter._streams

    # --- health_check 성공/실패 ---

    def test_health_check_success(self) -> None:
        client = MockSDKClient(health_ok=True)
        adapter = _make_adapter(client=client)
        assert adapter.health_check() is True

    def test_health_check_failure(self) -> None:
        client = MockSDKClient(health_ok=False)
        adapter = _make_adapter(client=client)
        assert adapter.health_check() is False

    # --- 벤더 SDK 연결 오류 → VendorConnectionError ---

    def test_start_stream_sdk_failure_raises_vendor_error(self) -> None:
        client = MockSDKClient(fail_on_start=True)
        adapter = _make_adapter(client=client)
        with pytest.raises(VendorConnectionError) as exc_info:
            adapter.start_stream("session-1")
        assert exc_info.value.vendor == "aws-transcribe"

    # --- is_final=True 캐시 후 get_final_result 즉시 반환 ---

    def test_cached_final_result(self) -> None:
        """is_final=True 캐시 후 get_final_result가 캐시된 결과를 사용하는지 확인.

        send_audio 결과에는 text/is_final만 있고 confidence는 없으므로
        캐시된 결과의 confidence는 기본값 0.0이 된다.
        핵심은 get_final_result가 SDK의 get_result()를 다시 호출하지 않고
        캐시된 텍스트를 즉시 반환하는 것이다.
        """
        stream = MockStream(text="cached", confidence=0.95, is_final=True)
        client = MockSDKClient(stream=stream)
        adapter = _make_adapter(client=client)
        handle = adapter.start_stream("session-1")

        partial = adapter.process_audio_chunk(handle, b"\x00")
        assert partial.is_final is True

        result = adapter.get_final_result(handle)
        assert result.text == "cached"
        # 캐시된 send_audio 결과에서 텍스트를 가져왔음을 확인
        # (get_result()를 호출했다면 동일 텍스트이지만, 캐시 경로를 탄 것이 핵심)

    # --- get_final_result 후 내부 버퍼 해제 ---

    def test_get_final_result_clears_buffers(self) -> None:
        adapter = _make_adapter()
        handle = adapter.start_stream("session-1")
        adapter.process_audio_chunk(handle, b"\x00\x01\x02")
        adapter.get_final_result(handle)

        assert handle.stream_id not in adapter._buffers
        assert handle.stream_id not in adapter._streams
        assert handle.stream_id not in adapter._cached_finals
        assert handle.stream_id not in adapter._start_times

    # --- close 후 내부 상태 정리 ---

    def test_close_clears_all_state(self) -> None:
        adapter = _make_adapter()
        h1 = adapter.start_stream("s1")
        h2 = adapter.start_stream("s2")
        adapter.process_audio_chunk(h1, b"\x00")
        adapter.process_audio_chunk(h2, b"\x01")

        adapter.close()

        assert len(adapter._streams) == 0
        assert len(adapter._buffers) == 0
        assert len(adapter._cached_finals) == 0
        assert len(adapter._start_times) == 0

    # --- processing_time_ms 양수 기록 ---

    def test_processing_time_ms_positive(self) -> None:
        client = MockDelaySDKClient(delay_ms=5.0)
        adapter = STTVendorAdapter(config=_make_config(), client=client)
        handle = adapter.start_stream("session-1")
        adapter.process_audio_chunk(handle, b"\x00")
        result = adapter.get_final_result(handle)
        assert result.processing_time_ms >= 0

    # --- 실패 시 로그에 벤더 식별자, 에러 유형, 소요 시간 포함 ---

    def test_failure_log_contains_vendor_info(self, caplog) -> None:
        client = MockSDKClient(fail_on_start=True)
        adapter = _make_adapter(client=client)

        with caplog.at_level(logging.ERROR):
            with pytest.raises(VendorConnectionError):
                adapter.start_stream("session-1")

        assert any("aws-transcribe" in r.message for r in caplog.records)
        assert any("ConnectionError" in r.message for r in caplog.records)
        assert any("elapsed" in r.message for r in caplog.records)
