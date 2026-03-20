"""Token Store: JWT 폐기 상태 추적 저장소."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod


class TokenStoreBase(ABC):
    """Token_Store 추상 인터페이스.

    JWT의 폐기 상태를 추적한다. 인메모리 구현체를 기본으로 제공하며,
    Redis 등 외부 저장소 구현체로 교체 가능하도록 설계한다.
    """

    @abstractmethod
    def revoke(self, jti: str, exp: float) -> None:
        """jti를 폐기 목록에 등록한다.

        Args:
            jti: 폐기할 JWT의 고유 토큰 ID.
            exp: 해당 JWT의 만료 시각 (Unix timestamp).
        """

    @abstractmethod
    def is_revoked(self, jti: str) -> bool:
        """jti가 폐기되었는지 확인한다.

        Args:
            jti: 확인할 JWT의 고유 토큰 ID.

        Returns:
            폐기된 경우 True, 아닌 경우 False.
        """


class InMemoryTokenStore(TokenStoreBase):
    """인메모리 Token_Store 구현체.

    Lazy cleanup: is_revoked() 호출 시 만료 항목을 자동 제거한다.
    purge_expired()를 명시적으로 호출해 전체 정리도 가능하다.
    """

    def __init__(self) -> None:
        self._revoked: dict[str, float] = {}

    def revoke(self, jti: str, exp: float) -> None:
        """jti → exp 매핑을 저장하여 폐기 등록한다."""
        self._revoked[jti] = exp

    def is_revoked(self, jti: str) -> bool:
        """jti가 폐기되었는지 확인한다.

        만료된 항목(exp <= 현재 시각)은 자동 제거 후 False를 반환한다.
        """
        exp = self._revoked.get(jti)
        if exp is None:
            return False
        if exp <= time.time():
            del self._revoked[jti]
            return False
        return True

    def purge_expired(self) -> int:
        """만료된 항목을 모두 제거하고 제거된 개수를 반환한다."""
        now = time.time()
        expired_jtis = [jti for jti, exp in self._revoked.items() if exp <= now]
        for jti in expired_jtis:
            del self._revoked[jti]
        return len(expired_jtis)
