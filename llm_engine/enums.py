"""callbot.llm_engine.enums — LLM 엔진 열거형 정의"""
from __future__ import annotations

from enum import Enum


class VerificationStatus(Enum):
    PASS = "통과"      # 검증 통과 (비사실 기반 답변 우회 포함)
    REPLACED = "교체"  # 불일치 감지 → 템플릿 기반 교체
    BLOCKED = "차단"   # 확신도 미달 또는 DB 장애 → 상담사 연결


class ScopeType(Enum):
    NON_TELECOM = "통신_무관"           # 날씨, 뉴스 등
    UNSUPPORTED_TELECOM = "범위외_통신"  # 기지국, 단말기 AS 등
