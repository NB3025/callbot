"""callbot.session.redis_config — Redis 연결 설정 관리"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class RedisConfig:
    """Redis 연결 설정.

    from_env()로 환경변수에서 로드.
    CALLBOT_USE_SECRETS_MANAGER=true 시 SecretsManager에서 비밀번호 조회.
    """

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False

    @classmethod
    def from_env(cls) -> "RedisConfig":
        """환경변수에서 설정 로드.

        환경변수:
        - CALLBOT_REDIS_HOST (기본: localhost)
        - CALLBOT_REDIS_PORT (기본: 6379)
        - CALLBOT_REDIS_DB (기본: 0)
        - CALLBOT_REDIS_SSL (기본: false)
        - CALLBOT_REDIS_PASSWORD (CALLBOT_USE_SECRETS_MANAGER=false 시)
        - callbot/redis-password (CALLBOT_USE_SECRETS_MANAGER=true 시, SecretsManager)
        """
        host = os.environ.get("CALLBOT_REDIS_HOST", "localhost")
        port = int(os.environ.get("CALLBOT_REDIS_PORT", "6379"))
        db = int(os.environ.get("CALLBOT_REDIS_DB", "0"))
        ssl = os.environ.get("CALLBOT_REDIS_SSL", "false").lower() == "true"

        use_secrets = os.environ.get("CALLBOT_USE_SECRETS_MANAGER", "false").lower() == "true"
        if use_secrets:
            from callbot.security.secrets_manager import SecretsManager

            sm = SecretsManager.from_env()
            password = sm.get_secret("callbot/redis-password")
        else:
            password = os.environ.get("CALLBOT_REDIS_PASSWORD")

        return cls(host=host, port=port, db=db, password=password, ssl=ssl)
