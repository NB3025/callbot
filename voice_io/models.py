"""callbot.voice_io.models — 핵심 데이터 모델"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Default STT confidence threshold
STT_DEFAULT_THRESHOLD = 0.5


@dataclass
class STTResult:
    """STT 엔진 인식 결과.

    Validation rules:
    - confidence ∈ [0.0, 1.0]
    - is_valid = confidence >= threshold
    - failure_type is None iff is_valid is True
    """
    text: str
    confidence: float           # 0.0~1.0
    is_valid: bool              # confidence >= STT_확신도_임계값
    processing_time_ms: int
    failure_type: Optional[str] # None=성공, "no_result", "low_confidence"

    @classmethod
    def create(
        cls,
        text: str,
        confidence: float,
        processing_time_ms: int,
        threshold: float = STT_DEFAULT_THRESHOLD,
        failure_type: Optional[str] = None,
    ) -> "STTResult":
        """팩토리 메서드: confidence와 threshold로 is_valid와 failure_type을 자동 결정."""
        is_valid = confidence >= threshold

        if is_valid:
            resolved_failure_type = None
        else:
            # failure_type이 명시적으로 전달된 경우 그대로 사용, 아니면 기본값
            if failure_type is not None:
                resolved_failure_type = failure_type
            elif text == "" or text is None:
                resolved_failure_type = "no_result"
            else:
                resolved_failure_type = "low_confidence"

        return cls(
            text=text,
            confidence=confidence,
            is_valid=is_valid,
            processing_time_ms=processing_time_ms,
            failure_type=resolved_failure_type,
        )


@dataclass
class DTMFResult:
    """DTMF 처리기 입력 결과.

    Validation rules:
    - is_complete = len(digits) == expected_length
    - is_complete와 is_timeout은 동시에 True일 수 없음
    - digits는 숫자 문자(0~9)만 포함
    """
    digits: str
    is_complete: bool    # len(digits) == expected_length
    is_timeout: bool
    expected_length: int
    input_type: str      # "birth_date", "password", "satisfaction", "unknown"

    @classmethod
    def create(
        cls,
        digits: str,
        expected_length: int,
        is_timeout: bool = False,
        input_type: str = "unknown",
    ) -> "DTMFResult":
        """팩토리 메서드: digits와 expected_length로 is_complete를 자동 결정."""
        is_complete = len(digits) == expected_length

        # is_complete와 is_timeout은 동시에 True일 수 없음
        if is_complete:
            is_timeout = False

        return cls(
            digits=digits,
            is_complete=is_complete,
            is_timeout=is_timeout,
            expected_length=expected_length,
            input_type=input_type,
        )


@dataclass
class StreamHandle:
    """STT 스트리밍 세션 핸들."""
    session_id: str
    stream_id: str


@dataclass
class PartialResult:
    """STT 중간 인식 결과."""
    text: str
    is_final: bool = False


@dataclass
class AudioStream:
    """TTS 오디오 스트림."""
    session_id: str
    data: bytes = field(default_factory=bytes)
    sample_rate: int = 16000
    encoding: str = "pcm"
