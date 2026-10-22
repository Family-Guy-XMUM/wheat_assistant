"""Independent review counterexamples for Windows v0.2.1 frozen boundaries.

Synthetic data only; the API is imported after dotenv is disabled and provider
configuration is cleared. These tests complement tests/test_windows_v021.py.
"""

from __future__ import annotations

import copy
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REVIEW_GROUPS = ["fields", "statuses", "products", "units", "duplicates", "output"]
LLM_ENV = ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY")


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch):
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    for name in LLM_ENV:
        monkeypatch.setenv(name, "")


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from maizi import api

    monkeypatch.setattr(api, "propose_live", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no provider")))
    with TestClient(api.create_app(data_dir=tmp_path)) as test_client:
        yield test_client


def test_policy2_execution_without_confirmation_returns_409(client: TestClient) -> None:
    batch = client.post("/api/demo/load", json={"week": 2}).json()
    plan = client.post(
        f"/api/batches/{batch['id']}/plan",
        json={"mode": "suggested"},
    ).json()
    flow = copy.deepcopy(plan["flow"])
    flow["aliases"] = {"Jasmine500": "TEA-001"}
    flow["unit_aliases"] = {"carton": "box"}
    preflight = client.post(
        f"/api/batches/{batch['id']}/preflight",
        json=flow,
    ).json()
    groups = preflight["hold_review"]["groups"]
    assert groups and any(group["value"] == "Partially shipped" for group in groups)
    held = [
        {"channel_id": group["channel_id"], "field": group["field"], "value": group["value"]}
        for group in groups
    ]
    saved = client.post(
        f"/api/batches/{batch['id']}/approve",
        json={
            "flow": flow,
            "expected_input_hash": preflight["input_hash"],
            "reviewed": REVIEW_GROUPS,
            "held_statuses": held,
            "hold_review_hash": preflight["hold_review"]["snapshot_hash"],
        },
    ).json()
    run = client.post(
        "/api/runs",
        json={"batch_id": batch["id"], "flow_id": saved["id"]},
    ).json()

    store = client.app.state.store
    policy2 = copy.deepcopy(store.get("flow", saved["id"]))
    policy2["held_statuses"] = []
    policy2["hold_review_hash"] = None
    store.put("flow", saved["id"], policy2)

    rejected = client.post(f"/api/runs/{run['id']}/execute")
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "STATUS_REVIEW_REQUIRED"
    assert client.get(f"/api/runs/{run['id']}").json()["status"] == "ready"


def test_health_instance_id_stable_within_app_and_changes_after_restart(
    tmp_path: Path,
) -> None:
    from maizi.api import create_app

    with TestClient(create_app(data_dir=tmp_path)) as first:
        one = first.get("/api/health").json()["instance_id"]
        again = first.get("/api/health").json()["instance_id"]
        assert one == again

    with TestClient(create_app(data_dir=tmp_path)) as second:
        two = second.get("/api/health").json()["instance_id"]
        assert two != one


def test_child_environment_exact_allowlist_and_fixed_pythonutf8() -> None:
    from maizi.runtime_environment import child_environment

    source = {
        "systemroot": r"C:\Windows",
        "windir": r"C:\Windows",
        "path": r"C:\Tools",
        "temp": r"C:\Temp",
        "tmp": r"C:\Tmp",
        "tmpdir": r"C:\TmpDir",
        "lang": "en_GB.UTF-8",
        "lc_all": "en_GB.UTF-8",
        "LLM_API_KEY": "synthetic-secret",
        "OPENAI_API_KEY": "synthetic-secret",
        "MAIZI_DATA_DIR": r"C:\Private",
    }
    result = child_environment(source, native=True, windows=True)
    assert set(result) == {
        "PATH",
        "SystemRoot",
        "WINDIR",
        "TEMP",
        "TMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "PYTHONUTF8",
    }
    assert result["SystemRoot"] == r"C:\Windows"
    assert result["PYTHONUTF8"] == "1"
    assert result["PATH"].replace("/", "\\").rstrip("\\").casefold() == (
        r"c:\windows\system32"
    )
    assert "synthetic-secret" not in {str(value) for value in result.values()}


def test_bind_loopback_rejects_active_listener_and_accepts_after_close() -> None:
    from maizi.local_network import bind_loopback

    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    port = holder.getsockname()[1]
    try:
        with socket.socket() as probe:
            with pytest.raises(OSError):
                bind_loopback(probe, port)
    finally:
        holder.close()

    with socket.socket() as probe:
        bind_loopback(probe, port)
        assert probe.getsockname()[1] == port
