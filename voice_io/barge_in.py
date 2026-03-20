"""callbot.voice_io.barge_in — 바지인 콜백 인터페이스"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BargeInHandler(Protocol):
    """STT가 TTS의 재생을 중단시키기 위한 의존성 주입 프로토콜.

    STT_엔진은 TTS_엔진을 직접 임포트하지 않고 이 프로토콜을 통해
    stop_playback()을 호출한다.
    """

    def stop_playback(self, session_id: str) -> None:
        """바지인 감지 시 TTS 재생을 즉시 중단한다 (P95 200ms)."""
        ...
