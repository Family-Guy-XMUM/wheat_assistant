"""Cloud boundary: explicit hosts, same-origin writes and unguessable browser cookies."""
from __future__ import annotations

import asyncio
import hashlib
import re
import secrets
import time
from collections import defaultdict, deque
from http.cookies import SimpleCookie

from starlette.requests import Request
from starlette.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from wheat_assistant.cloud_store import workspace_context

COOKIE = "__Host-wheat_demo"
SAFE = {"GET", "HEAD"}


class ReplitPolicy:
    def __init__(self, hosts):
        self.hosts = {x.strip().lower() for x in hosts if x.strip()}
        if not self.hosts or any(not re.fullmatch(r"[a-z0-9][a-z0-9.-]*(?::[0-9]+)?", x) for x in self.hosts):
            raise ValueError("Configure the exact Replit deployment and preview hosts")

    def validate(self, request):
        host = request.headers.get("host", "").lower()
        if host not in self.hosts:
            return JSONResponse({"detail": "This host is not enabled for the demo"}, status_code=403)
        if request.method not in SAFE:
            origin = request.headers.get("origin", "")
            if origin != "https://" + host or request.headers.get("x-wheat-request") != "1":
                return JSONResponse({"detail": "Open the demo directly and submit from the same site"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site" and request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Cross-site access is not allowed"}, status_code=403)
        return None


class CloudGateway:
    def __init__(self, app, database, policy, *, max_requests=180):
        self.app, self.database, self.policy = app, database, policy
        self.max_requests = max_requests
        self.requests = defaultdict(deque)
        self.mutations = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope, receive)
        failure = self.policy.validate(request)
        if failure is not None:
            return await failure(scope, receive, send)
        path = scope["path"]
        if path in {"/healthz", "/api/health"} or not path.startswith("/api/"):
            return await self.app(scope, receive, send)
        cookie = SimpleCookie()
        try:
            cookie.load(request.headers.get("cookie", ""))
            value = cookie[COOKIE].value if COOKIE in cookie else ""
        except Exception:
            value = ""
        identifier = hashlib.sha256(value.encode()).hexdigest() if re.fullmatch(r"[a-f0-9]{64}", value) else None
        try:
            valid = identifier is not None and await asyncio.to_thread(self.database.exists, identifier)
        except SQLAlchemyError:
            return await JSONResponse({"detail": "Persistent storage is temporarily unavailable"}, status_code=503)(scope, receive, send)
        if path == "/api/session" and request.method == "POST":
            if not valid:
                value = secrets.token_hex(32)
                identifier = hashlib.sha256(value.encode()).hexdigest()
                try:
                    await asyncio.to_thread(self.database.new_workspace, identifier)
                except ValueError as exc:
                    return await JSONResponse({"detail": str(exc)}, status_code=429)(scope, receive, send)
                except SQLAlchemyError:
                    return await JSONResponse({"detail": "Persistent storage is temporarily unavailable"}, status_code=503)(scope, receive, send)
            response = JSONResponse({"mode": "cloud", "workspace": "browser-private", "synthetic_only": True})
            response.set_cookie(COOKIE, value, max_age=14 * 86400, secure=True, httponly=True, samesite="lax", path="/")
            response.headers["Cache-Control"] = "no-store"
            return await response(scope, receive, send)
        if not valid:
            return await JSONResponse({"detail": "Reload the demo to start your browser workspace"}, status_code=401)(scope, receive, send)
        recent = self.requests[identifier]
        current = time.monotonic()
        while recent and recent[0] < current - 60:
            recent.popleft()
        if len(recent) >= self.max_requests:
            return await JSONResponse({"detail": "Please pause briefly before trying again"}, status_code=429,
                                      headers={"Retry-After": "60"})(scope, receive, send)
        recent.append(current)
        lock = self.mutations.setdefault(identifier, asyncio.Lock())
        mutation = request.method not in SAFE
        if mutation and lock.locked():
            return await JSONResponse({"detail": "A step is still running. Refresh its saved status before retrying."}, status_code=409)(scope, receive, send)
        if mutation:
            await lock.acquire()
        token = workspace_context.set(identifier)
        async def safe_send(message):
            if message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []),
                    (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer")]}
            await send(message)
        try:
            await self.app(scope, receive, safe_send)
        finally:
            workspace_context.reset(token)
            if mutation:
                lock.release()
