"""
Unit tests for STTEngine — Sub-task 2.1

Boundary tests for STT confidence threshold and failure_type mapping.
Validates: Requirements 1.5
"""
import pytest

from callbot.voice_io.models import STTResult
from callbot.voice_io.stt_engine import STTEngineBase, STT_CONFIDENCE_THRESHOLD_DEFAULT, VAD_SILENCE_SEC_DEFAULT


# ---------------------------------------------------------------------------
# Sub-task 2.1 — STT 확신도 임계값 경계 단위 테스트
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------

class TestSTTConfidenceThresholdBoundary:
    """threshold=0.5 기준 경계값 테스트"""

    def test_confidence_just_below_threshold_is_invalid(self):
        """confidence=0.499 → is_valid=False (threshold=0.5 미달)"""
        result = STTResult.create(
            text="테스트",
            confidence=0.499,
            processing_time_ms=100,
            threshold=0.5,
        )
        assert result.is_valid is False

    def test_confidence_at_threshold_is_valid(self):
        """confidence=0.5 → is_valid=True (threshold=0.5 정확히 일치)"""
        result = STTResult.create(
            text="테스트",
            confidence=0.5,
            processing_time_ms=100,
            threshold=0.5,
        )
        assert result.is_valid is True

    def test_confidence_just_above_threshold_is_valid(self):
        """confidence=0.501 → is_valid=True (threshold=0.5 초과)"""
        result = STTResult.create(
            text="테스트",
            confidence=0.501,
            processing_time_ms=100,
            threshold=0.5,
        )
        assert result.is_valid is True


class TestSTTFailureTypeMapping:
    """failure_type 매핑 테스트"""

    def test_failure_type_none_when_valid(self):
        """is_valid=True → failure_type=None"""
        result = STTResult.create(
            text="테스트",
            confidence=0.8,
            processing_time_ms=100,
            threshold=0.5,
        )
        assert result.failure_type is None

    def test_failure_type_no_result_when_empty_text(self):
        """text="" + confidence < threshold → failure_type="no_result" """
        result = STTResult.create(
            text="",
            confidence=0.0,
            processing_time_ms=100,
            threshold=0.5,
        )
        assert result.failure_type == "no_result"

    def test_failure_type_low_confidence_when_text_present(self):
        """text 있음 + confidence < threshold → failure_type="low_confidence" """
        result = STTResult.create(
            text="불명확한 발화",
            confidence=0.3,
            processing_time_ms=100,
            threshold=0.5,
        )
        assert result.failure_type == "low_confidence"


class TestSTTEngineBaseDefaults:
    """STTEngineBase 기본값 및 설정 범위 테스트"""

    def test_default_confidence_threshold(self):
        """기본 확신도 임계값은 0.5"""
        assert STT_CONFIDENCE_THRESHOLD_DEFAULT == 0.5

    def test_default_vad_silence_sec(self):
        """기본 VAD 침묵 임계값은 1.5초"""
        assert VAD_SILENCE_SEC_DEFAULT == 1.5

    def test_engine_uses_default_threshold(self):
        """STTEngineBase 인스턴스의 기본 threshold=0.5"""
        engine = STTEngineBase()
        assert engine.stt_confidence_threshold == 0.5

    def test_engine_uses_default_vad_silence(self):
        """STTEngineBase 인스턴스의 기본 vad_silence_sec=1.5"""
        engine = STTEngineBase()
        assert engine.vad_silence_sec == 1.5

    def test_threshold_range_min(self):
        """threshold 최솟값 0.3 설정 가능"""
        engine = STTEngineBase(stt_confidence_threshold=0.3)
        assert engine.stt_confidence_threshold == 0.3

    def test_threshold_range_max(self):
        """threshold 최댓값 0.7 설정 가능"""
        engine = STTEngineBase(stt_confidence_threshold=0.7)
        assert engine.stt_confidence_threshold == 0.7

    def test_threshold_below_range_raises(self):
        """threshold < 0.3 → ValueError"""
        with pytest.raises(ValueError):
            STTEngineBase(stt_confidence_threshold=0.29)

    def test_threshold_above_range_raises(self):
        """threshold > 0.7 → ValueError"""
        with pytest.raises(ValueError):
            STTEngineBase(stt_confidence_threshold=0.71)

    def test_vad_silence_range_min(self):
        """vad_silence_sec 최솟값 1.0 설정 가능"""
        engine = STTEngineBase(vad_silence_sec=1.0)
        assert engine.vad_silence_sec == 1.0

    def test_vad_silence_range_max(self):
        """vad_silence_sec 최댓값 3.0 설정 가능"""
        engine = STTEngineBase(vad_silence_sec=3.0)
        assert engine.vad_silence_sec == 3.0

    def test_vad_silence_below_range_raises(self):
        """vad_silence_sec < 1.0 → ValueError"""
        with pytest.raises(ValueError):
            STTEngineBase(vad_silence_sec=0.9)

    def test_vad_silence_above_range_raises(self):
        """vad_silence_sec > 3.0 → ValueError"""
        with pytest.raises(ValueError):
            STTEngineBase(vad_silence_sec=3.1)


class TestSTTEngineBaseStreamOperations:
    """STTEngineBase 스트림 동작 테스트"""

    def test_start_stream_returns_handle(self):
        """start_stream()은 StreamHandle을 반환한다"""
        from callbot.voice_io.models import StreamHandle
        engine = STTEngineBase()
        handle = engine.start_stream("session-001")
        assert isinstance(handle, StreamHandle)
        assert handle.session_id == "session-001"

    def test_process_audio_chunk_returns_partial_result(self):
        """process_audio_chunk()는 PartialResult를 반환한다"""
        from callbot.voice_io.models import PartialResult
        engine = STTEngineBase()
        handle = engine.start_stream("session-001")
        result = engine.process_audio_chunk(handle, b"\x00" * 160)
        assert isinstance(result, PartialResult)

    def test_get_final_result_returns_stt_result(self):
        """get_final_result()는 STTResult를 반환한다"""
        engine = STTEngineBase()
        handle = engine.start_stream("session-001")
        result = engine.get_final_result(handle)
        assert isinstance(result, STTResult)

    def test_get_final_result_uses_configured_threshold(self):
        """get_final_result()는 설정된 threshold를 사용한다"""
        engine = STTEngineBase(stt_confidence_threshold=0.6)
        handle = engine.start_stream("session-001")
        result = engine.get_final_result(handle)
        # STTResult의 is_valid는 threshold=0.6 기준으로 결정되어야 함
        expected_valid = result.confidence >= 0.6
        assert result.is_valid == expected_valid

    def test_activate_barge_in_does_not_raise(self):
        """activate_barge_in()은 예외 없이 실행된다"""
        engine = STTEngineBase()
        engine.activate_barge_in("session-001")  # should not raise
