import hashlib
import shutil

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from wheat_assistant.cloud_gateway import COOKIE, CloudGateway, ReplitPolicy
from wheat_assistant.cloud_store import CloudDatabase, workspace_context

HOST = "wheat-demo.replit.app"
HEADERS = {"Origin": "https://" + HOST, "X-Wheat-Request": "1"}


@pytest.fixture
def database(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "cloud-test.sqlite"), connect_args={"check_same_thread": False})
    db = CloudDatabase(None, tmp_path / "cache", engine=engine)
    yield db
    db.close()


def app(database):
    inner = FastAPI()
    @inner.post("/api/items")
    def add():
        return database.add("test", {"text": "synthetic"})
    @inner.get("/api/items/{identifier}")
    def get(identifier: str):
        try:
            return database.get("test", identifier)
        except KeyError:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not found"}, status_code=404)
    return CloudGateway(inner, database, ReplitPolicy([HOST]))


def test_browser_scopes_and_forged_cookie(database):
    gateway = app(database)
    first = TestClient(gateway, base_url="https://" + HOST)
    second = TestClient(gateway, base_url="https://" + HOST)
    assert first.post("/api/items", headers=HEADERS).status_code == 401
    session = first.post("/api/session", headers=HEADERS)
    assert session.status_code == 200
    assert all(x in session.headers["set-cookie"].lower() for x in ["httponly", "secure", "samesite=lax", "path=/"])
    item = first.post("/api/items", headers=HEADERS).json()
    second.post("/api/session", headers=HEADERS)
    assert second.get("/api/items/" + item["id"]).status_code == 404
    assert first.get("/api/items/" + item["id"]).json()["text"] == "synthetic"
    first.cookies.set(COOKIE, "a" * 64, domain=HOST, path="/")
    assert first.get("/api/items/" + item["id"]).status_code == 401


@pytest.mark.parametrize("headers", [{}, {"Origin": "https://attacker.example", "X-Wheat-Request": "1"},
    {"Origin": "https://" + HOST}, {**HEADERS, "Sec-Fetch-Site": "cross-site"}])
def test_cross_origin_bootstrap_cannot_create_workspaces(database, headers):
    client = TestClient(app(database), base_url="https://" + HOST)
    assert client.post("/api/session", headers=headers).status_code == 403


def test_host_validation_and_no_cors_preflight(database):
    client = TestClient(app(database), base_url="https://attacker.example")
    assert client.post("/api/session", headers=HEADERS).status_code == 403
    client = TestClient(app(database), base_url="https://" + HOST)
    assert client.options("/api/session", headers={"Origin": "https://attacker.example"}).status_code == 403


def test_files_and_records_survive_cache_loss_and_remain_scoped(database):
    first, second = "a" * 64, "b" * 64
    database.new_workspace(first)
    database.new_workspace(second)
    saved = database.scope(first).add("run", {"status": "completed"})
    original = b"sku,quantity\nSYNTHETIC-1,5\n"
    database.scope(first).write_blob("files", "orders.csv", original)
    database.scope(first).write_blob("artifacts", "export.xlsx", b"synthetic export")
    shutil.rmtree(database.cache_root)
    assert database.scope(first).get("run", saved["id"])["status"] == "completed"
    assert database.scope(first).blob_path("files", "orders.csv").read_bytes() == original
    assert database.scope(first).blob_path("artifacts", "export.xlsx").read_bytes() == b"synthetic export"
    assert not database.scope(second).blob_path("files", "orders.csv").exists()
    with pytest.raises(KeyError):
        database.scope(second).get("run", saved["id"])
    with pytest.raises(ValueError, match="immutable"):
        database.scope(first).write_blob("files", "orders.csv", b"changed")


def test_storage_quota_rolls_back_linked_updates(database):
    database.new_workspace("a" * 64)
    store = database.scope("a" * 64)
    saved = store.add("run", {"status": "ready"})
    database.max_bytes = 300
    with pytest.raises(ValueError, match="storage limit"):
        store.commit_bundle(updates=[("run", saved["id"], {"status": "completed"})], additions=[("activity", {"data": "x" * 400})])
    assert store.get("run", saved["id"])["status"] == "ready"
    assert store.list("activity") == []


def test_recovery_preserves_other_browser_data(database):
    database.new_workspace("a" * 64)
    store = database.scope("a" * 64)
    run = store.add("run", {"status": "running", "export_state": "building"})
    export = store.add("export", {"status": "building"})
    database.recover()
    assert store.get("run", run["id"])["status"] == "interrupted"
    assert store.get("run", run["id"])["export_state"] == "interrupted"
    assert store.get("export", export["id"])["status"] == "interrupted"


def test_sqlite_url_is_not_a_cloud_fallback(tmp_path):
    with pytest.raises(ValueError, match="PostgreSQL"):
        CloudDatabase("sqlite:///unsafe.sqlite", tmp_path)


def test_session_capacity_is_bounded(database):
    database.max_workspaces = 1
    first = TestClient(app(database), base_url="https://" + HOST)
    second = TestClient(app(database), base_url="https://" + HOST)
    assert first.post("/api/session", headers=HEADERS).status_code == 200
    assert second.post("/api/session", headers=HEADERS).status_code == 429
    assert first.post("/api/items", headers=HEADERS).status_code == 200


def test_ai_budget_is_shared_across_browsers_and_persistent(database):
    database.daily_calls = 2
    database.new_workspace("a" * 64)
    database.new_workspace("b" * 64)
    first, second = database.scope("a" * 64), database.scope("b" * 64)
    first.add("usage", {"status": "requested"})
    second.add("usage", {"status": "requested"})
    database.close()
    with pytest.raises(ValueError, match="daily AI-call limit"):
        second.add("usage", {"status": "requested"})
    assert len(first.list("usage")) == 1
    assert len(second.list("usage")) == 1
