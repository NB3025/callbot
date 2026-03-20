"""server.tests.test_logging — 구조화 로깅 테스트."""

import json
import logging

import pytest
from starlette.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_pipeline():
    pipeline = AsyncMock()
    pipeline.process = AsyncMock(return_value={
        "session_id": "test-session-123",
        "response_text": "응답",
        "action_type": "PROCESS_BUSINESS",
        "context": {},
    })
    return pipeline


@pytest.fixture
def app_with_logging(mock_pipeline):
    from server.app import create_app

    app = create_app()
    app.state.pipeline = mock_pipeline
    app.state.session_manager = MagicMock()
    app.state.healthy = True
    return app


class TestCorrelationId:
    """응답 헤더에 X-Request-ID 포함."""

    def test_request_has_correlation_id(self, app_with_logging):
        client = TestClient(app_with_logging)
        response = client.get("/health/live")
        assert "x-request-id" in response.headers
        # UUID 형식 확인
        request_id = response.headers["x-request-id"]
        assert len(request_id) == 36  # UUID v4 length

    def test_custom_request_id_passthrough(self, app_with_logging):
        """클라이언트가 보낸 X-Request-ID를 그대로 사용."""
        client = TestClient(app_with_logging)
        custom_id = "my-custom-request-123"
        response = client.get("/health/live", headers={"X-Request-ID": custom_id})
        assert response.headers["x-request-id"] == custom_id


class TestJsonLogOutput:
    """로그 출력이 JSON 파싱 가능."""

    def test_log_output_is_json(self, app_with_logging, capfd):
        from server.logging_config import setup_logging

        setup_logging()
        logger = logging.getLogger("server.test")
        logger.info("test message", extra={"custom_field": "value"})

        captured = capfd.readouterr()
        # stderr에 JSON 로그가 출력되어야 함
        for line in captured.err.strip().split("\n"):
            if "test message" in line:
                parsed = json.loads(line)
                assert parsed["message"] == "test message"
                break
        else:
            pytest.fail("JSON log line with 'test message' not found")


class TestSessionContext:
    """턴 처리 로그에 session_id 포함."""

    def test_log_includes_session_context(self, app_with_logging, capfd):
        from server.logging_config import setup_logging

        setup_logging()
        client = TestClient(app_with_logging)
        client.post(
            "/api/v1/turn",
            json={"caller_id": "01012345678", "text": "테스트"},
        )
        captured = capfd.readouterr()
        # 로그에 request_id가 포함되어야 함
        found = False
        for line in captured.err.strip().split("\n"):
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
                if "request_id" in parsed:
                    found = True
                    break
            except json.JSONDecodeError:
                continue
        assert found, "No log line with request_id found"
