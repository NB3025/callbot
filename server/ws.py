"""server.ws — WebSocket 엔드포인트."""

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/api/v1/ws")
async def ws_endpoint(
    websocket: WebSocket,
    caller_id: str = Query(...),
    session_id: str | None = Query(None),
) -> None:
    """WebSocket 턴 처리 엔드포인트.

    1. 연결 accept
    2. session_id 있으면 조회, 없으면 생성
    3. 메시지 루프: turn → pipeline.process() → response
    4. end 메시지 또는 disconnect → 종료
    """
    await websocket.accept()

    app = websocket.app
    pipeline: Any = getattr(app.state, "pipeline", None)
    session_manager: Any = getattr(app.state, "session_manager", None)

    # 세션 생성/조회
    current_session_id = session_id
    if session_id and session_manager:
        try:
            session = session_manager.get_session(session_id)
            current_session_id = session.session_id
        except Exception:
            session = session_manager.create_session(caller_id=caller_id)
            current_session_id = session.session_id
    elif session_manager:
        session = session_manager.create_session(caller_id=caller_id)
        current_session_id = session.session_id

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "end":
                await websocket.close()
                break

            if msg_type == "turn":
                text = data.get("text", "")

                if pipeline:
                    result = await pipeline.process(
                        caller_id=caller_id,
                        text=text,
                        session_id=current_session_id,
                    )
                    # result can be dict or TurnResult dataclass
                    if hasattr(result, 'session_id'):
                        resp = {
                            "type": "response",
                            "session_id": result.session_id or current_session_id,
                            "response_text": result.response_text or "",
                            "action_type": result.action_type or "",
                            "context": result.context or {},
                        }
                    else:
                        resp = {
                            "type": "response",
                            "session_id": result.get("session_id", current_session_id),
                            "response_text": result.get("response_text", ""),
                            "action_type": result.get("action_type", ""),
                            "context": result.get("context", {}),
                        }
                    await websocket.send_json(resp)
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Pipeline not initialized",
                    })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: caller_id=%s session_id=%s", caller_id, current_session_id)
    except Exception as exc:
        logger.exception("WebSocket error: %s", exc)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
