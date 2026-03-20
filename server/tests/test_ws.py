"""server.tests.test_ws — WebSocket 엔드포인트 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def mock_pipeline():
    pipeline = AsyncMock()
    pipeline.process = AsyncMock(return_value={
        "session_id": "test-session-123",
        "response_text": "안녕하세요",
        "action_type": "PROCESS_BUSINESS",
        "context": {},
    })
    return pipeline


@pytest.fixture
def mock_session_manager():
    manager = MagicMock()
    session = MagicMock()
    session.session_id = "test-session-123"
    manager.create_session.return_value = session
    manager.get_session.return_value = session
    return manager


@pytest.fixture
def app_with_ws(mock_pipeline, mock_session_manager):
    from server.app import create_app

    app = create_app()
    app.state.pipeline = mock_pipeline
    app.state.session_manager = mock_session_manager
    app.state.healthy = True
    return app


class TestWebSocketTurnExchange:
    """WS 연결 → turn 메시지 → response 수신."""

    def test_ws_turn_exchange(self, app_with_ws, mock_pipeline):
        client = TestClient(app_with_ws)
        with client.websocket_connect("/api/v1/ws?caller_id=01012345678") as ws:
            ws.send_json({
                "type": "turn",
                "text": "요금 조회해주세요",
            })
            response = ws.receive_json()
            assert response["type"] == "response"
            assert response["session_id"] == "test-session-123"
            assert "response_text" in response


class TestWebSocketEndMessage:
    """end 메시지 → 연결 종료."""

    def test_ws_end_message_closes(self, app_with_ws):
        client = TestClient(app_with_ws)
        with client.websocket_connect("/api/v1/ws?caller_id=01012345678") as ws:
            ws.send_json({"type": "end"})
            # 서버가 close 보내면 다음 receive에서 disconnect
            with pytest.raises((WebSocketDisconnect, Exception)):
                ws.receive_json()


class TestWebSocketSessionCreation:
    """session_id 없이 연결 → 세션 자동 생성."""

    def test_ws_creates_session(self, app_with_ws, mock_session_manager):
        client = TestClient(app_with_ws)
        with client.websocket_connect("/api/v1/ws?caller_id=01012345678") as ws:
            ws.send_json({
                "type": "turn",
                "text": "안녕",
            })
            response = ws.receive_json()
            assert "session_id" in response
            mock_session_manager.create_session.assert_called_once()


class TestWebSocketWithSessionId:
    """기존 session_id로 연결 → 세션 조회."""

    def test_ws_reuses_session(self, app_with_ws, mock_session_manager):
        client = TestClient(app_with_ws)
        with client.websocket_connect(
            "/api/v1/ws?caller_id=01012345678&session_id=existing-session"
        ) as ws:
            ws.send_json({
                "type": "turn",
                "text": "이어서 할게요",
            })
            response = ws.receive_json()
            assert response["session_id"] is not None
