"""test_pg_config.py — PGConfig 단위 테스트 + Property 테스트 (P5, P6)"""
from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from callbot.session.pg_config import ConfigurationError, PGConfig, _mask_dsn_password


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------

def test_missing_dsn_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("CALLBOT_DB_DSN", raising=False)
    with pytest.raises(ConfigurationError):
        PGConfig.from_env()


def test_default_pool_values(monkeypatch):
    monkeypatch.setenv("CALLBOT_DB_DSN", "postgresql://u:p@localhost/db")
    monkeypatch.delenv("CALLBOT_DB_POOL_MIN", raising=False)
    monkeypatch.delenv("CALLBOT_DB_POOL_MAX", raising=False)
    monkeypatch.delenv("CALLBOT_DB_POOL_TIMEOUT", raising=False)
    cfg = PGConfig.from_env()
    assert cfg.pool_min == 2
    assert cfg.pool_max == 10
    assert cfg.pool_timeout == 30.0


def test_custom_pool_values(monkeypatch):
    monkeypatch.setenv("CALLBOT_DB_DSN", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("CALLBOT_DB_POOL_MIN", "5")
    monkeypatch.setenv("CALLBOT_DB_POOL_MAX", "20")
    monkeypatch.setenv("CALLBOT_DB_POOL_TIMEOUT", "60.0")
    cfg = PGConfig.from_env()
    assert cfg.pool_min == 5
    assert cfg.pool_max == 20
    assert cfg.pool_timeout == 60.0


# ---------------------------------------------------------------------------
# Property 5: 환경변수 → PGConfig 설정값 매핑
# ---------------------------------------------------------------------------

@given(
    pool_min=st.integers(min_value=1, max_value=100),
    pool_max=st.integers(min_value=1, max_value=100),
    pool_timeout=st.floats(min_value=0.1, max_value=300.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_env_to_pgconfig_mapping(monkeypatch, pool_min, pool_max, pool_timeout):
    """Property 5: 임의 환경변수 값이 PGConfig에 그대로 반영된다."""
    monkeypatch.setenv("CALLBOT_DB_DSN", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("CALLBOT_DB_POOL_MIN", str(pool_min))
    monkeypatch.setenv("CALLBOT_DB_POOL_MAX", str(pool_max))
    monkeypatch.setenv("CALLBOT_DB_POOL_TIMEOUT", str(pool_timeout))
    cfg = PGConfig.from_env()
    assert cfg.pool_min == pool_min
    assert cfg.pool_max == pool_max
    assert abs(cfg.pool_timeout - pool_timeout) < 1e-6


# ---------------------------------------------------------------------------
# Property 6: DSN 비밀번호 마스킹
# ---------------------------------------------------------------------------

# 비밀번호에 @ 포함 시 파싱이 깨지므로 제외
_safe_text = st.text(
    alphabet=st.characters(blacklist_characters="@:/"),
    min_size=1,
    max_size=20,
)


@given(user=_safe_text, password=_safe_text, host=_safe_text)
@settings(max_examples=100)
def test_dsn_password_masking(user, password, host):
    """Property 6: 마스킹 결과에 원본 user:password@ 패턴이 포함되지 않는다."""
    dsn = f"postgresql://{user}:{password}@{host}/db"
    masked = _mask_dsn_password(dsn)
    # 원본 비밀번호가 credential 위치(user:pass@)에 남아있지 않아야 한다
    assert f":{password}@" not in masked
    assert "***" in masked
