"""callbot.session.pg_config — PostgreSQL 연결 설정 관리"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


class ConfigurationError(Exception):
    """CALLBOT_DB_DSN 환경변수 미설정 시 발생."""
    pass


class PoolTimeoutError(Exception):
    """커넥션 풀 타임아웃 초과 시 발생."""
    pass


def _mask_dsn_password(dsn: str) -> str:
    """DSN 문자열에서 비밀번호를 ***로 마스킹한다.

    postgresql://user:password@host:port/db → postgresql://user:***@host:port/db
    """
    return re.sub(r"(://[^:]+:)[^@]+(@)", r"\1***\2", dsn)


@dataclass
class PGConfig:
    """PostgreSQL 연결 설정."""
    dsn: str
    pool_min: int = 2
    pool_max: int = 10
    pool_timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "PGConfig":
        """환경변수에서 설정을 읽어 PGConfig를 생성한다.

        Raises:
            ConfigurationError: CALLBOT_DB_DSN 환경변수가 설정되지 않은 경우
        """
        dsn = os.environ.get("CALLBOT_DB_DSN")
        if not dsn:
            raise ConfigurationError(
                "CALLBOT_DB_DSN 환경변수가 설정되지 않았습니다."
            )
        pool_min = int(os.environ.get("CALLBOT_DB_POOL_MIN", "2"))
        pool_max = int(os.environ.get("CALLBOT_DB_POOL_MAX", "10"))
        pool_timeout = float(os.environ.get("CALLBOT_DB_POOL_TIMEOUT", "30.0"))
        return cls(dsn=dsn, pool_min=pool_min, pool_max=pool_max, pool_timeout=pool_timeout)

    def masked_dsn(self) -> str:
        """로그 출력용 비밀번호 마스킹된 DSN."""
        return _mask_dsn_password(self.dsn)
