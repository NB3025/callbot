"""callbot.nlu.models — NLU 핵심 데이터 모델"""
from __future__ import annotations

from dataclasses import dataclass, field

from callbot.nlu.enums import (
    ClassificationStatus,
    EntityType,
    Intent,
    RelationType,
    SYSTEM_CONTROL_INTENTS,
    ESCALATION_INTENTS,
)

# 기본 확신도 임계값
CONFIDENCE_THRESHOLD = 0.7


@dataclass
class FilterResult:
    """프롬프트_인젝션_필터 결과.

    Invariants:
    - is_safe=True  ↔  detected_patterns == []
    - is_safe=False ↔  len(detected_patterns) >= 1
    """
    is_safe: bool
    detected_patterns: list[str]
    original_text: str
    processing_time_ms: int

    @classmethod
    def safe(cls, original_text: str, processing_time_ms: int) -> "FilterResult":
        """안전한 결과 팩토리."""
        return cls(
            is_safe=True,
            detected_patterns=[],
            original_text=original_text,
            processing_time_ms=processing_time_ms,
        )

    @classmethod
    def unsafe(
        cls,
        detected_patterns: list[str],
        original_text: str,
        processing_time_ms: int,
    ) -> "FilterResult":
        """인젝션 탐지 결과 팩토리."""
        if not detected_patterns:
            raise ValueError("unsafe FilterResult must have at least one detected pattern")
        return cls(
            is_safe=False,
            detected_patterns=detected_patterns,
            original_text=original_text,
            processing_time_ms=processing_time_ms,
        )


@dataclass
class Entity:
    """추출된 엔티티."""
    type: EntityType
    value: str
    confidence: float


@dataclass
class IntentRelation:
    """복합 의도 간 관계."""
    primary_intent: Intent
    secondary_intent: Intent
    relation_type: RelationType


@dataclass
class ClassificationResult:
    """의도_분류기 결과.

    Invariants:
    - classification_status=SUCCESS  ↔  confidence >= CONFIDENCE_THRESHOLD
    - is_system_control=True         ↔  primary_intent ∈ SYSTEM_CONTROL_INTENTS
    - requires_immediate_escalation=True ↔ primary_intent ∈ ESCALATION_INTENTS
    """
    primary_intent: Intent
    secondary_intents: list[Intent]
    intent_relations: list[IntentRelation]
    entities: list[Entity]
    confidence: float
    is_system_control: bool
    classification_status: ClassificationStatus
    requires_immediate_escalation: bool

    @classmethod
    def create(
        cls,
        primary_intent: Intent,
        confidence: float,
        secondary_intents: list[Intent] | None = None,
        intent_relations: list[IntentRelation] | None = None,
        entities: list[Entity] | None = None,
        threshold: float = CONFIDENCE_THRESHOLD,
    ) -> "ClassificationResult":
        """팩토리 메서드: 불변 조건을 자동으로 결정."""
        is_system_control = primary_intent in SYSTEM_CONTROL_INTENTS
        requires_immediate_escalation = primary_intent in ESCALATION_INTENTS

        if primary_intent == Intent.UNCLASSIFIED:
            status = ClassificationStatus.UNCLASSIFIED
        elif confidence >= threshold:
            status = ClassificationStatus.SUCCESS
        else:
            status = ClassificationStatus.FAILURE

        return cls(
            primary_intent=primary_intent,
            secondary_intents=secondary_intents or [],
            intent_relations=intent_relations or [],
            entities=entities or [],
            confidence=confidence,
            is_system_control=is_system_control,
            classification_status=status,
            requires_immediate_escalation=requires_immediate_escalation,
        )


@dataclass
class MaskedText:
    """마스킹/복원_모듈 마스킹 결과.

    Invariant:
    - token_mapping의 모든 키는 masked_text에 포함
    """
    masked_text: str
    token_mapping: dict[str, str]
    masked_fields: list[str]


@dataclass
class RestoreResult:
    """마스킹/복원_모듈 복원 결과.

    Invariants:
    - is_success=True  ↔  unrestored_tokens == []
    - is_success=False ↔  len(unrestored_tokens) >= 1
    """
    text: str
    is_success: bool
    unrestored_tokens: list[str]

    @classmethod
    def success(cls, text: str) -> "RestoreResult":
        """완전 복원 성공 팩토리."""
        return cls(text=text, is_success=True, unrestored_tokens=[])

    @classmethod
    def failure(cls, text: str, unrestored_tokens: list[str]) -> "RestoreResult":
        """복원 실패 팩토리."""
        if not unrestored_tokens:
            raise ValueError("failure RestoreResult must have at least one unrestored token")
        return cls(text=text, is_success=False, unrestored_tokens=unrestored_tokens)


@dataclass
class DetectionStats:
    """세션별 인젝션 탐지 통계."""
    session_id: str
    detection_count: int
    detected_patterns: list[str] = field(default_factory=list)
