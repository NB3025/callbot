"""
Integration tests for callbot-voice-io — Sub-task 7.1

Tests the end-to-end flows between components.
Validates: Requirements 1.5, 2.1, 2.2
"""
from callbot.voice_io import (
    STTEngine,
    STTEngineBase,
    TTSEngine,
    TTSEngineBase,
    DTMFProcessor,
    BargeInHandler,
    VoiceIOConfig,
    STTResult,
    DTMFResult,
    AudioStream,
)


# ---------------------------------------------------------------------------
# Test 1: STT → 오케스트레이터 콜백 흐름 통합 테스트
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------

class TestSTTOrchestratorFlow:
    """STT → 오케스트레이터 콜백 흐름 통합 테스트"""

    def test_stt_stream_returns_valid_stt_result_structure(self):
        """start_stream → process_audio_chunk × 3 → get_final_result 흐름이 올바른 STTResult를 반환한다"""
        engine = STTEngineBase()
        session_id = "integration-session-001"

        handle = engine.start_stream(session_id)
        engine.process_audio_chunk(handle, b"\x00" * 160)
        engine.process_audio_chunk(handle, b"\x00" * 160)
        engine.process_audio_chunk(handle, b"\x00" * 160)
        result = engine.get_final_result(handle)

        assert isinstance(result, STTResult)

    def test_stt_result_is_valid_and_failure_type_consistent(self):
        """STTResult의 is_valid와 failure_type은 항상 일관성을 유지한다"""
        engine = STTEngineBase()
        handle = engine.start_stream("session-002")
        result = engine.get_final_result(handle)

        # is_valid=True → failure_type=None, is_valid=False → failure_type is not None
        if result.is_valid:
            assert result.failure_type is None
        else:
            assert result.failure_type is not None

    def test_stt_result_confidence_in_valid_range(self):
        """STTResult.confidence는 항상 [0.0, 1.0] 범위 내에 있다"""
        engine = STTEngineBase()
        handle = engine.start_stream("session-003")
        result = engine.get_final_result(handle)

        assert 0.0 <= result.confidence <= 1.0

    def test_stt_result_processing_time_non_negative(self):
        """STTResult.processing_time_ms는 음수가 아니다"""
        engine = STTEngineBase()
        handle = engine.start_stream("session-004")
        result = engine.get_final_result(handle)

        assert result.processing_time_ms >= 0


# ---------------------------------------------------------------------------
# Test 2: DTMF 캡처 → 결과 수신 통합 테스트
# Validates: Requirements 2.1, 2.2
# ---------------------------------------------------------------------------

class TestDTMFCaptureFlow:
    """DTMF 캡처 → 결과 수신 통합 테스트"""

    def test_dtmf_4_digit_password_complete(self):
        """4자리 비밀번호 입력 완료 시 DTMFResult(is_complete=True, digits='1234', input_type='password')"""
        processor = DTMFProcessor()
        session_id = "dtmf-session-001"

        processor.start_capture(session_id, expected_length=4, input_type="password")
        for digit in "1234":
            processor.push_digit(session_id, digit)
        result = processor.get_input(session_id)

        assert isinstance(result, DTMFResult)
        assert result.is_complete is True
        assert result.digits == "1234"
        assert result.input_type == "password"
        assert result.is_timeout is False

    def test_dtmf_6_digit_birth_date_complete(self):
        """6자리 생년월일 입력 완료 시 DTMFResult(is_complete=True)"""
        processor = DTMFProcessor()
        session_id = "dtmf-session-002"

        processor.start_capture(session_id, expected_length=6, input_type="birth_date")
        for digit in "901225":
            processor.push_digit(session_id, digit)
        result = processor.get_input(session_id)

        assert result.is_complete is True
        assert result.digits == "901225"
        assert result.input_type == "birth_date"

    def test_dtmf_incomplete_input_not_complete(self):
        """자릿수 미달 입력 시 is_complete=False"""
        processor = DTMFProcessor()
        session_id = "dtmf-session-003"

        processor.start_capture(session_id, expected_length=4, input_type="password")
        for digit in "12":
            processor.push_digit(session_id, digit)
        result = processor.get_input(session_id)

        assert result.is_complete is False
        assert result.digits == "12"


# ---------------------------------------------------------------------------
# Test 3: 바지인 통합 흐름 테스트
# Validates: Requirements 4.1, 4.3
# ---------------------------------------------------------------------------

class TestBargeInIntegrationFlow:
    """TTS + STT 바지인 통합 흐름 테스트"""

    def test_barge_in_flow_completes_without_error(self):
        """TTSEngineBase를 barge_in_handler로 등록한 STT에서 activate_barge_in() 호출 시 오류 없이 완료된다"""
        tts = TTSEngineBase()
        stt = STTEngineBase(barge_in_handler=tts)

        # TTS synthesize
        audio = tts.synthesize("안녕하세요", "session-barge-001")
        assert isinstance(audio, AudioStream)

        # STT activate barge-in → calls tts.stop_playback()
        stt.activate_barge_in("session-barge-001")  # should not raise

    def test_barge_in_stop_playback_called_on_tts(self):
        """activate_barge_in() 호출 시 TTS의 stop_playback()이 실행된다"""
        from unittest.mock import MagicMock

        mock_tts = MagicMock()
        stt = STTEngineBase(barge_in_handler=mock_tts)

        stt.activate_barge_in("session-barge-002")

        mock_tts.stop_playback.assert_called_once_with("session-barge-002")


# ---------------------------------------------------------------------------
# Test 4: VoiceIOConfig 설정 통합 테스트
# ---------------------------------------------------------------------------

class TestVoiceIOConfig:
    """VoiceIOConfig 설정 클래스 테스트"""

    def test_voice_io_config_default_values(self):
        """VoiceIOConfig 기본값이 스펙과 일치한다"""
        config = VoiceIOConfig()

        assert config.stt_confidence_threshold == 0.5
        assert config.vad_silence_sec == 1.5
        assert config.dtmf_timeout_sec == 5
        assert config.tts_speed_factor == 1.0

    def test_voice_io_config_custom_values(self):
        """VoiceIOConfig에 커스텀 값을 설정할 수 있다"""
        config = VoiceIOConfig(
            stt_confidence_threshold=0.6,
            vad_silence_sec=2.0,
            dtmf_timeout_sec=10,
            tts_speed_factor=1.2,
        )

        assert config.stt_confidence_threshold == 0.6
        assert config.vad_silence_sec == 2.0
        assert config.dtmf_timeout_sec == 10
        assert config.tts_speed_factor == 1.2

    def test_voice_io_config_used_to_create_stt_engine(self):
        """VoiceIOConfig 값으로 STTEngineBase를 생성할 수 있다"""
        config = VoiceIOConfig(stt_confidence_threshold=0.6, vad_silence_sec=2.0)
        engine = STTEngineBase(
            stt_confidence_threshold=config.stt_confidence_threshold,
            vad_silence_sec=config.vad_silence_sec,
        )

        assert engine.stt_confidence_threshold == 0.6
        assert engine.vad_silence_sec == 2.0

    def test_voice_io_config_used_to_create_dtmf_processor(self):
        """VoiceIOConfig의 dtmf_timeout_sec으로 DTMFProcessor를 설정할 수 있다"""
        config = VoiceIOConfig(dtmf_timeout_sec=10)
        processor = DTMFProcessor()
        processor.start_capture(
            "session-config-001",
            expected_length=4,
            input_type="password",
            timeout_sec=config.dtmf_timeout_sec,
        )
        for digit in "1234":
            processor.push_digit("session-config-001", digit)
        result = processor.get_input("session-config-001")

        assert result.is_complete is True
