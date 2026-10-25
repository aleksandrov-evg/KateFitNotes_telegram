"""Structured request diagnostics without bodies, credentials or query strings."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("uvicorn.error.request_audit")


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = perf_counter()
        status_code = 500
        completed = False
        error_type = None

        def emit(phase: str) -> None:
            route = scope.get("route")
            event = {
                "event": "api_request",
                "phase": phase,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "method": scope["method"],
                "route": getattr(route, "path", "UNMATCHED"),
                "actor": scope["state"].get("audit_actor"),
            }
            if phase != "started":
                event.update(
                    status_code=status_code,
                    completed=completed,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    error_type=error_type,
                )
            level = logging.ERROR if error_type else logging.WARNING if status_code >= 400 and phase != "started" else logging.INFO
            logger.log(level, json.dumps(event, ensure_ascii=True))

        async def logged_send(message: Message) -> None:
            nonlocal status_code, completed
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message = dict(message)
                headers = [(key, value) for key, value in message.get("headers", []) if key.lower() != b"x-request-id"]
                message["headers"] = [*headers, (b"x-request-id", request_id.encode("ascii"))]
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                completed = True

        emit("started")
        try:
            await self.app(scope, receive, logged_send)
        except BaseException as error:
            # Exception messages can contain upstream credentials or personal data.
            error_type = type(error).__name__
            raise
        finally:
            emit("finished")
