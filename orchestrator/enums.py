"""callbot.orchestrator.enums — 오케스트레이터 열거형 정의"""
from __future__ import annotations

from enum import Enum


class ActionType(Enum):
    PROCESS_BUSINESS = "업무_처리"
    SYSTEM_CONTROL = "시스템_제어"
    ESCALATE = "상담사_연결"
    SURVEY = "만족도_조사"
    AUTH_REQUIRED = "인증_필요"
    SESSION_END = "세션_종료"


class SwitchDecision(Enum):
    PROCEED = "proceed"
    ROLLBACK = "rollback"
    EXTEND = "extend"
    MANUAL = "manual"
