import uuid
import time

from logging import getLogger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.context import request_id_var


log = getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)

        log.info(f"Request ID: [{request_id}] Request started: {request.url.path}")

        start = time.perf_counter()

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        elapsed_time = time.perf_counter() - start
        elapsed_time = "{0:.0f}".format(1_000 * elapsed_time)

        log.info(f"Request ID: [{request_id}] Request completed with status {response.status_code}")
        log.info(f"Request ID: [{request_id}] Elapsed time ms {elapsed_time}")

        return response
