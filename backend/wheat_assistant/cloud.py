"""Replit entry point. One VM, one worker; no desktop launcher or local database."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from wheat_assistant.api import create_app
from wheat_assistant.cloud_gateway import CloudGateway, ReplitPolicy
from wheat_assistant.cloud_store import CloudDatabase


def configured_hosts():
    hosts = []
    for key in ("WHEAT_PUBLIC_HOSTS", "REPLIT_DOMAINS", "REPLIT_DEV_DOMAIN"):
        hosts.extend(os.getenv(key, "").split(","))
    return [host.strip() for host in hosts if host.strip()]


def create_cloud_app(*, database=None, hosts=None, frontend_dir=None):
    policy = ReplitPolicy(hosts if hosts is not None else configured_hosts())
    database = database or CloudDatabase(os.getenv("DATABASE_URL"),
        Path(tempfile.mkdtemp(prefix="wheat-cloud-cache-")),
        daily_calls=max(0, min(60, int(os.getenv("WHEAT_CLOUD_DAILY_CALL_LIMIT", "20")))))
    database.recover()
    app = create_app(data_dir=database.cache_root, frontend_dir=frontend_dir, store_override=database,
                     request_policy=policy, recover_on_start=False, mode="cloud",
                     live_ai=os.getenv("WHEAT_CLOUD_LIVE_AI", "0") == "1")

    @app.exception_handler(SQLAlchemyError)
    async def storage_unavailable(request, exc):
        return JSONResponse({"detail": "Persistent storage is temporarily unavailable. Check saved status before retrying."}, status_code=503)

    # Mount the gateway around every API route, including original file downloads.
    return CloudGateway(app, database, policy)


def main():
    import uvicorn
    try:
        app = create_cloud_app()
    except Exception:
        # Connection errors can contain credentials; never print their repr or URL.
        raise SystemExit("Cloud startup failed. Check PostgreSQL DATABASE_URL and exact WHEAT_PUBLIC_HOSTS in Replit.") from None
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "3000")),
                workers=1, proxy_headers=False, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
