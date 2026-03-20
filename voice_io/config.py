"""callbot.voice_io.config — VoiceIOConfig 설정 클래스"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VoiceIOConfig:
    """음성 I/O 계층 통합 설정 클래스.

    모든 컴포넌트(STT, TTS, DTMF)의 임계값 및 타임아웃 설정을 통합한다.

    Attributes:
        stt_confidence_threshold: STT 확신도 임계값 (기본 0.5, 범위 0.3~0.7)
        vad_silence_sec: VAD 침묵 감지 시간 (기본 1.5초, 범위 1.0~3.0)
        dtmf_timeout_sec: DTMF 입력 타임아웃 (기본 5초)
        tts_speed_factor: TTS 말하기 속도 배율 (기본 1.0, 범위 0.7~1.3)
    """
    stt_confidence_threshold: float = 0.5
    vad_silence_sec: float = 1.5
    dtmf_timeout_sec: int = 5
    tts_speed_factor: float = 1.0
