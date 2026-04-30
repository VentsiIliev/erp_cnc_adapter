"""HTTP request/response logging middleware."""

import json
import logging
import time
from collections.abc import Callable

from fastapi import Request, Response

logger = logging.getLogger(__name__)

MAX_LOG_BODY_CHARS = 4000
EXCLUDED_PATHS = {
    "/",
    "/favicon.ico",
    "/api/config",
    "/api/health",
    "/api/logs",
    "/api/update/backups",
    "/api/cnc/job/status",
}
EXCLUDED_PATH_PREFIXES = (
    "/static/",
    "/api/cnc/monitor/",
)


async def log_http_request_response(request: Request, call_next: Callable) -> Response:
    """Log exactly what comes into and goes out of the API."""
    if _is_excluded_path(request.url.path):
        return await call_next(request)

    started = time.perf_counter()
    request_body = await request.body()
    request_path = request.url.path
    client_ip = _get_client_ip(request)
    if request.url.query:
        request_path = f"{request_path}?{request.url.query}"

    logger.info(
        "HTTP REQUEST %s %s client_ip=%s body=%s",
        request.method,
        request_path,
        client_ip,
        _format_body(request_body, request.headers.get("content-type", "")),
    )

    response = await call_next(request)
    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "HTTP RESPONSE %s %s client_ip=%s -> %d %.1fms body=%s",
        request.method,
        request_path,
        client_ip,
        response.status_code,
        elapsed_ms,
        _format_body(response_body, response.headers.get("content-type", "")),
    )

    return Response(
        content=response_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
        background=response.background,
    )


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"

    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip() or "unknown"

    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _format_body(body: bytes, content_type: str) -> str:
    if not body:
        return "<empty>"

    text = body.decode("utf-8", errors="replace")
    if "json" in content_type.lower():
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            text = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))

    if len(text) > MAX_LOG_BODY_CHARS:
        return f"{text[:MAX_LOG_BODY_CHARS]}...<truncated>"
    return text


def _is_excluded_path(path: str) -> bool:
    return path in EXCLUDED_PATHS or path.startswith(EXCLUDED_PATH_PREFIXES)
