"""Tests for request/response HTTP logging middleware."""

import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.http_logging import log_http_request_response


pytestmark = pytest.mark.asyncio


async def test_logs_request_and_response_body(caplog):
    app = FastAPI()
    app.middleware("http")(log_http_request_response)

    @app.post("/echo")
    async def echo(payload: dict):
        return {"received": payload}

    with caplog.at_level(logging.INFO, logger="src.core.http_logging"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/echo", json={"job": "123456789012", "step": 10})

    assert resp.status_code == 200
    assert resp.json() == {"received": {"job": "123456789012", "step": 10}}

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "HTTP REQUEST" in message
        and "POST /echo" in message
        and '"job":"123456789012"' in message
        for message in messages
    )
    assert any(
        "HTTP RESPONSE" in message
        and "POST /echo -> 200" in message
        and '"received":{"job":"123456789012","step":10}' in message
        for message in messages
    )


async def test_logging_preserves_response_headers_and_body(caplog):
    app = FastAPI()
    app.middleware("http")(log_http_request_response)

    @app.get("/plain")
    async def plain():
        from fastapi.responses import Response

        return Response("ok", media_type="text/plain", headers={"x-test": "kept"})

    with caplog.at_level(logging.INFO, logger="src.core.http_logging"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/plain")

    assert resp.status_code == 200
    assert resp.text == "ok"
    assert resp.headers["x-test"] == "kept"
    assert any("body=ok" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/favicon.ico",
        "/static/app.css",
        "/api/health",
        "/api/logs",
        "/api/logs?lines=120",
        "/api/config",
        "/api/update/backups",
        "/api/cnc/job/status",
        "/api/cnc/monitor/status",
    ],
)
async def test_internal_polling_endpoints_are_not_logged(caplog, path):
    app = FastAPI()
    app.middleware("http")(log_http_request_response)

    @app.get("/")
    async def home():
        return "dashboard"

    @app.get("/favicon.ico")
    async def favicon():
        return ""

    @app.get("/static/app.css")
    async def static_css():
        return ""

    @app.get("/api/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/api/logs")
    async def logs():
        return {"lines": ["adapter log line"]}

    @app.get("/api/config")
    async def config():
        return {"machine_number": "CNC100"}

    @app.get("/api/update/backups")
    async def backups():
        return {"backups": []}

    @app.get("/api/cnc/job/status")
    async def job_status():
        return {"state": 2}

    @app.get("/api/cnc/monitor/status")
    async def monitor_status():
        return {"monitoring": False}

    with caplog.at_level(logging.INFO, logger="src.core.http_logging"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(path)

    assert resp.status_code == 200
    assert not [
        record
        for record in caplog.records
        if record.name == "src.core.http_logging" and "HTTP " in record.getMessage()
    ]


async def test_dashboard_log_sections_do_not_force_scroll():
    from pathlib import Path

    dashboard = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "web"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")

    assert "scrollTop = element.scrollHeight" not in dashboard


async def test_config_read_endpoint_is_not_info_logged():
    from pathlib import Path

    config_api = (
        Path(__file__).resolve().parent.parent / "src" / "api" / "config_api.py"
    ).read_text(encoding="utf-8")

    assert 'logger.info("GET /api/config - Retrieve current configuration")' not in config_api
