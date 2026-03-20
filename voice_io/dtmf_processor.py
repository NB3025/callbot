"""callbot.voice_io.dtmf_processor — DTMF 처리기"""
from __future__ import annotations

import time
from typing import Any

from callbot.voice_io.models import DTMFResult

# Default timeout in seconds
DTMF_DEFAULT_TIMEOUT_SEC: int = 5


class DTMFProcessor:
    """DTMF 키패드 입력 처리기.

    세션별 캡처 상태를 내부적으로 관리한다.
    start_capture() → push_digit() × N → get_input() 순서로 사용한다.
    """

    def __init__(self) -> None:
        # session_id → capture state dict
        self._sessions: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_capture(
        self,
        session_id: str,
        expected_length: int,
        input_type: str = "unknown",
        timeout_sec: int = DTMF_DEFAULT_TIMEOUT_SEC,
    ) -> None:
        """DTMF 입력 캡처 시작. 지정 자릿수 입력 시 자동 완료."""
        self._sessions[session_id] = {
            "digits": "",
            "expected_length": expected_length,
            "input_type": input_type,
            "timeout_sec": timeout_sec,
            "start_time": time.monotonic(),
        }

    def push_digit(self, session_id: str, digit: str) -> None:
        """DTMF 신호 한 자리 추가. 숫자(0~9)만 저장하고 나머지는 무시한다."""
        state = self._sessions[session_id]
        # Filter: only 0-9
        if digit.isdigit():
            state["digits"] += digit

    def get_input(self, session_id: str) -> DTMFResult:
        """캡처된 DTMF 입력 반환."""
        state = self._sessions[session_id]
        digits = state["digits"]
        expected_length = state["expected_length"]
        input_type = state["input_type"]
        timeout_sec = state["timeout_sec"]
        start_time = state["start_time"]

        elapsed = time.monotonic() - start_time
        is_timeout = elapsed >= timeout_sec and len(digits) < expected_length

        return DTMFResult.create(
            digits=digits,
            expected_length=expected_length,
            is_timeout=is_timeout,
            input_type=input_type,
        )
