"""server.middleware — 요청 미들웨어."""

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """X-Request-ID 헤더 미들웨어.

    - 클라이언트가 보낸 X-Request-ID가 있으면 그대로 사용
    - 없으면 UUID v4 생성
    - 응답 헤더에 X-Request-ID 추가
    - 로그에 request_id 포함
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        # request state에 저장
        request.state.request_id = request_id

        # 로그에 request_id 포함
        logger.info(
            "Request: %s %s",
            request.method,
            request.url.path,
            extra={"request_id": request_id},
        )

        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
