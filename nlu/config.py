"""callbot.nlu.config — NLU 설정 클래스

Validates: Requirements 1.4, 2.5, 3.7
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NLUConfig:
    """NLU 모듈 통합 설정.

    Attributes:
        confidence_threshold: 확신도 임계값 (기본값 0.7, 범위 0.5~0.9)
        injection_patterns: 추가 탐지 패턴 목록
        masking_fallback_template: 복원 실패 시 사용할 템플릿명
    """
    confidence_threshold: float = 0.7
    injection_patterns: list[str] = field(default_factory=list)
    masking_fallback_template: str = "masking_fallback"
