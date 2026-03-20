"""callbot.session.enums — 세션 열거형 정의"""
from __future__ import annotations

from enum import Enum


class TurnType(Enum):
    BUSINESS = "업무"   # 업무 턴 (20턴 제한에 카운트)
    SYSTEM = "시스템"   # 시스템 턴 (재발화 요청, 인증, 만족도 조사 등 — 카운트 제외)


class EndReason(Enum):
    NORMAL = "정상종료"           # 만족도 조사 후 정상 종료
    AGENT_TRANSFER = "상담사연결"  # 상담사 연결로 종료
    TIMEOUT = "타임아웃"           # 무응답 타임아웃으로 종료
    DISCONNECTED = "통화끊김"      # 고객 통화 끊김
    TURN_LIMIT = "턴제한"          # 20턴 제한 도달
    TIME_LIMIT = "시간제한"        # 15분 시간 제한 도달
    SYSTEM_ERROR = "시스템오류"    # 시스템 장애로 종료


class AuthStatus(Enum):
    NOT_ATTEMPTED = "미시도"       # 인증 시도 전
    IN_PROGRESS = "진행중"         # 인증 진행 중
    SUCCESS = "인증성공"           # 인증 성공
    FAILED = "인증실패"            # 인증 실패 (최대 시도 초과)
    SKIPPED = "인증생략"           # 인증 생략 (비인증 업무)


class AuthType(Enum):
    BIRTHDATE = "생년월일"         # 생년월일 인증
    PASSWORD = "비밀번호"          # 비밀번호 인증
