"""callbot.session.exceptions — 세션 관련 예외 정의"""
from __future__ import annotations


class SessionNotFoundError(Exception):
    """존재하지 않는 session_id로 접근 시 발생."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session not found: {session_id}")
        self.session_id = session_id


class RedisConnectionError(Exception):
    """Redis 연결 실패 시 발생."""


class SessionSerializationError(Exception):
    """SessionContext 직렬화/역직렬화 실패 시 발생."""
