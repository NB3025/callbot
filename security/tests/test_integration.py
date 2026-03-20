"""기존 컴포넌트 통합 단위 테스트.

PostgreSQLConnection.from_env가 SecretsManager 설정에 따라
올바르게 DSN을 구성하는지 검증한다.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


class TestPgConnectionSecretsManagerIntegration:
    """PostgreSQLConnection.from_env의 SecretsManager 통합 테스트."""

    @patch("callbot.session.pg_connection.ThreadedConnectionPool")
    @patch("callbot.security.secrets_manager.SecretsManager.from_env")
    def test_pg_connection_uses_secrets_manager_when_enabled(
        self, mock_sm_from_env, mock_pool
    ):
        """CALLBOT_USE_SECRETS_MANAGER=true 시 SecretsManager로 DSN 구성.

        Validates: Requirements 8.1, 8.2
        """
        mock_sm = MagicMock()
        mock_sm.get_secret.return_value = "s3cret-pw"
        mock_sm_from_env.return_value = mock_sm

        env = {
            "CALLBOT_USE_SECRETS_MANAGER": "true",
            "CALLBOT_DB_HOST": "db.example.com",
            "CALLBOT_DB_PORT": "5433",
            "CALLBOT_DB_NAME": "mydb",
            "CALLBOT_DB_USER": "admin",
        }
        with patch.dict(os.environ, env, clear=False):
            from callbot.session.pg_connection import PostgreSQLConnection

            conn = PostgreSQLConnection.from_env()

        mock_sm.get_secret.assert_called_once_with("callbot/db-password")
        expected_dsn = "postgresql://admin:s3cret-pw@db.example.com:5433/mydb"
        mock_pool.assert_called_once_with(2, 10, expected_dsn)

    @patch("callbot.session.pg_connection.ThreadedConnectionPool")
    def test_pg_connection_uses_env_dsn_when_disabled(self, mock_pool):
        """CALLBOT_USE_SECRETS_MANAGER 미설정 시 기존 CALLBOT_DB_DSN 방식.

        Validates: Requirements 8.3
        """
        env = {
            "CALLBOT_DB_DSN": "postgresql://user:pass@localhost:5432/callbot",
        }
        # CALLBOT_USE_SECRETS_MANAGER가 없는 상태를 보장
        cleaned = {
            k: v for k, v in os.environ.items() if k != "CALLBOT_USE_SECRETS_MANAGER"
        }
        cleaned.update(env)
        with patch.dict(os.environ, cleaned, clear=True):
            from callbot.session.pg_connection import PostgreSQLConnection

            conn = PostgreSQLConnection.from_env()

        expected_dsn = "postgresql://user:pass@localhost:5432/callbot"
        mock_pool.assert_called_once_with(2, 10, expected_dsn)

    @patch("callbot.session.pg_connection.ThreadedConnectionPool")
    def test_pg_connection_uses_env_dsn_when_false(self, mock_pool):
        """CALLBOT_USE_SECRETS_MANAGER=false 시 기존 방식 유지.

        Validates: Requirements 8.3
        """
        env = {
            "CALLBOT_USE_SECRETS_MANAGER": "false",
            "CALLBOT_DB_DSN": "postgresql://user:pass@localhost:5432/callbot",
        }
        with patch.dict(os.environ, env, clear=False):
            from callbot.session.pg_connection import PostgreSQLConnection

            conn = PostgreSQLConnection.from_env()

        expected_dsn = "postgresql://user:pass@localhost:5432/callbot"
        mock_pool.assert_called_once_with(2, 10, expected_dsn)
