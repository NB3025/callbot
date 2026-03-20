"""test_redis_config.py — RedisConfig 단위 테스트"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from callbot.session.redis_config import RedisConfig


def test_default_values():
    """Req 5.2: 기본값 host=localhost, port=6379, db=0, password=None, ssl=False."""
    cfg = RedisConfig()
    assert cfg.host == "localhost"
    assert cfg.port == 6379
    assert cfg.db == 0
    assert cfg.password is None
    assert cfg.ssl is False


def test_from_env_loads_host_port_db_ssl(monkeypatch):
    """Req 5.3, 5.4: 환경변수에서 host, port, db, ssl 설정 로드."""
    monkeypatch.setenv("CALLBOT_REDIS_HOST", "redis.example.com")
    monkeypatch.setenv("CALLBOT_REDIS_PORT", "6380")
    monkeypatch.setenv("CALLBOT_REDIS_DB", "2")
    monkeypatch.setenv("CALLBOT_REDIS_SSL", "true")
    monkeypatch.delenv("CALLBOT_USE_SECRETS_MANAGER", raising=False)
    monkeypatch.delenv("CALLBOT_REDIS_PASSWORD", raising=False)

    cfg = RedisConfig.from_env()

    assert cfg.host == "redis.example.com"
    assert cfg.port == 6380
    assert cfg.db == 2
    assert cfg.ssl is True


def test_from_env_uses_secrets_manager_for_password(monkeypatch):
    """Req 5.5: CALLBOT_USE_SECRETS_MANAGER=true → SecretsManager 조회."""
    monkeypatch.setenv("CALLBOT_USE_SECRETS_MANAGER", "true")
    monkeypatch.delenv("CALLBOT_REDIS_HOST", raising=False)
    monkeypatch.delenv("CALLBOT_REDIS_PORT", raising=False)
    monkeypatch.delenv("CALLBOT_REDIS_DB", raising=False)
    monkeypatch.delenv("CALLBOT_REDIS_SSL", raising=False)

    mock_sm_instance = MagicMock()
    mock_sm_instance.get_secret.return_value = "secret-from-sm"

    mock_sm_cls = MagicMock()
    mock_sm_cls.from_env.return_value = mock_sm_instance

    # Create a fake module with our mock SecretsManager
    import types
    import sys

    fake_module = types.ModuleType("callbot.security.secrets_manager")
    fake_module.SecretsManager = mock_sm_cls

    with patch.dict(sys.modules, {"callbot.security.secrets_manager": fake_module}):
        cfg = RedisConfig.from_env()

    mock_sm_cls.from_env.assert_called_once()
    mock_sm_instance.get_secret.assert_called_once_with("callbot/redis-password")
    assert cfg.password == "secret-from-sm"


def test_from_env_uses_env_var_for_password(monkeypatch):
    """Req 5.6: CALLBOT_USE_SECRETS_MANAGER=false → CALLBOT_REDIS_PASSWORD 사용."""
    monkeypatch.setenv("CALLBOT_USE_SECRETS_MANAGER", "false")
    monkeypatch.setenv("CALLBOT_REDIS_PASSWORD", "env-password")
    monkeypatch.delenv("CALLBOT_REDIS_HOST", raising=False)
    monkeypatch.delenv("CALLBOT_REDIS_PORT", raising=False)
    monkeypatch.delenv("CALLBOT_REDIS_DB", raising=False)
    monkeypatch.delenv("CALLBOT_REDIS_SSL", raising=False)

    cfg = RedisConfig.from_env()

    assert cfg.password == "env-password"
