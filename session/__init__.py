"""callbot.session — 세션 생명주기 관리 모듈 공개 API"""
from __future__ import annotations

from callbot.session.enums import AuthStatus, AuthType, EndReason, TurnType
from callbot.session.exceptions import (
    RedisConnectionError,
    SessionNotFoundError,
    SessionSerializationError,
)
from callbot.session.session_store import InMemorySessionStore, SessionStoreBase
from callbot.session.models import (
    AuthAttempt,
    ConversationSession,
    ConversationTurn,
    PlanListContext,
    SessionContext,
    SessionLimitStatus,
    Turn,
)
from callbot.session.repository import (
    CallbotDBRepository,
    DBConnectionBase,
    DBOperationError,
    InMemoryDBConnection,
    SessionFKError,
)
from callbot.session.session_manager import SessionManager

__all__ = [
    # 세션 관리자
    "SessionManager",
    # 세션 저장소 인터페이스
    "SessionStoreBase",
    "InMemorySessionStore",
    # DB 저장소
    "CallbotDBRepository",
    "DBConnectionBase",
    "DBOperationError",
    "InMemoryDBConnection",
    "SessionFKError",
    # 런타임 모델
    "SessionContext",
    "SessionLimitStatus",
    "Turn",
    "PlanListContext",
    # 영속 모델
    "ConversationSession",
    "ConversationTurn",
    "AuthAttempt",
    # 열거형
    "TurnType",
    "EndReason",
    "AuthStatus",
    "AuthType",
    # 예외
    "SessionNotFoundError",
    "RedisConnectionError",
    "SessionSerializationError",
]
