"""Independent API journey tests for the three synthetic demo weeks.

All data comes from ``wheat_assistant.samples.demo_files`` or synthetic uploads. The tests
use a real FastAPI TestClient with an isolated ``tmp_path`` data directory. They
never call an external model: the three LLM environment variables are cleared,
dotenv loading is monkeypatched off, and ``propose_live`` is replaced with a
hard failure. Only suggested/local planning is exercised.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REVIEW_GROUPS = ["fields", "statuses", "products", "units", "duplicates", "output"]
ALIASES = {"Jasmine500": "TEA-001"}
UNIT_ALIASES = {"carton": "box"}
LLM_ENV = ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY")


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for name in LLM_ENV:
        monkeypatch.setenv(name, "")

    # api.py calls load_dotenv at import time. Block that before importing it so
    # no local .env or credential file is read during the test session.
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)

    from wheat_assistant import api

    def forbidden_live(*args, **kwargs):
        raise AssertionError("Live model calls are forbidden in these tests")

    monkeypatch.setattr(api, "propose_live", forbidden_live)
    app = api.create_app(data_dir=tmp_path)
    with TestClient(app) as test_client:
        yield test_client


def load_week(client: TestClient, week: int) -> dict:
    response = client.post("/api/demo/load", json={"week": week})
    assert response.status_code == 200, response.text
    return response.json()


def plan_suggested(client: TestClient, batch_id: str) -> tuple[dict, dict]:
    response = client.post(f"/api/batches/{batch_id}/plan", json={"mode": "suggested"})
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["origin"] == "suggested_setup"
    assert plan["model"] is None
    flow = copy.deepcopy(plan["flow"])
    flow["aliases"] = dict(ALIASES)
    flow["unit_aliases"] = dict(UNIT_ALIASES)
    return plan, flow


def preflight(client: TestClient, batch_id: str, flow: dict) -> dict:
    response = client.post(f"/api/batches/{batch_id}/preflight", json=flow)
    assert response.status_code == 200, response.text
    return response.json()


def approve(
    client: TestClient,
    batch_id: str,
    flow: dict,
    input_hash: str,
    reviewed: list[str] | None = None,
    *,
    hold_review: dict | None = None,
) -> dict:
    response = client.post(
        f"/api/batches/{batch_id}/approve",
        json={
            "flow": flow,
            "reviewed": list(REVIEW_GROUPS if reviewed is None else reviewed),
            "expected_input_hash": input_hash,
            **({"held_statuses": [{key: x[key] for key in ("channel_id", "field", "value")} for x in hold_review["groups"]],
                "hold_review_hash": hold_review["snapshot_hash"]} if hold_review else {}),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def execute(client: TestClient, batch_id: str, flow_id: str) -> dict:
    response = client.post(
        "/api/runs",
        json={"batch_id": batch_id, "flow_id": flow_id},
    )
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "ready"

    response = client.post(f"/api/runs/{run['id']}/execute")
    assert response.status_code == 200, response.text
    completed = response.json()
    assert completed["status"] == "completed"
    return completed


def assert_summary(
    run: dict,
    *,
    input_rows: int,
    included: int,
    excluded: int,
    duplicate: int,
    exception: int,
) -> None:
    summary = run["summary"]
    assert summary["input"] == input_rows
    assert summary["included"] == included
    assert summary["excluded"] == excluded
    assert summary["duplicate"] == duplicate
    assert summary["exception"] == exception
    assert summary["totals_match"] is True
    assert included + excluded + duplicate + exception == input_rows


def sku_quantities(client: TestClient, run_id: str) -> dict[str, str]:
    response = client.get(f"/api/runs/{run_id}")
    assert response.status_code == 200, response.text
    return {entry["sku"]: entry["quantity"] for entry in response.json()["sku_summary"]}


def test_week1_demo_end_to_end(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["ai_configured"] is False

    batch = load_week(client, 1)
    assert batch["label"] == "Synthetic week 1"
    roles = [asset["role"] for asset in batch["files"]]
    assert roles.count("orders") == 3
    assert roles.count("master") == 1
    assert roles.count("template") == 1

    _, flow = plan_suggested(client, batch["id"])
    assert set(flow["channels"]) == {"channel-a", "channel-b", "manual"}
    assert flow["aliases"] == ALIASES
    assert flow["unit_aliases"] == UNIT_ALIASES

    report = preflight(client, batch["id"], flow)
    assert report["input_hash"] == batch["input_hash"]
    assert report["row_count"] == 36
    assert report["errors"] == []
    assert report["status_guard"]["covered"] is True
    assert report["status_guard"]["unknown_values"] == []
    # Aliases resolve Jasmine500 and carton; the intentionally bad source rows
    # remain visible in preflight instead of being silently accepted.
    assert report["unresolved_products"] == {"NOT-IN-MASTER": 1}
    assert report["unresolved_units"] == {"bundle / SOAP-002": 1}

    saved = approve(client, batch["id"], flow, report["input_hash"])
    assert set(saved["reviewed"]) == set(REVIEW_GROUPS)
    assert saved["input_hash"] == report["input_hash"]
    assert saved["spec"]["aliases"]["Jasmine500"] == "TEA-001"
    assert saved["spec"]["unit_aliases"]["carton"] == "box"

    run = execute(client, batch["id"], saved["id"])
    assert_summary(
        run,
        input_rows=36,
        included=24,
        excluded=3,
        duplicate=3,
        exception=6,
    )
    assert sku_quantities(client, run["id"]) == {
        "TEA-001": "21",
        "SOAP-002": "33",
        "RICE-003": "84",
    }

    blocked = client.get(f"/api/runs/{run['id']}/download")
    assert blocked.status_code == 403, blocked.text

    no_ack = client.post(
        f"/api/runs/{run['id']}/export-approval",
        json={"result_hash": run["result_hash"], "acknowledge_exceptions": False},
    )
    assert no_ack.status_code == 422, no_ack.text
    assert "Acknowledge" in no_ack.json()["detail"]

    approved = client.post(
        f"/api/runs/{run['id']}/export-approval",
        json={"result_hash": run["result_hash"], "acknowledge_exceptions": True},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["download_url"] == f"/api/runs/{run['id']}/download"

    artifact = client.get(approved.json()["download_url"])
    assert artifact.status_code == 200, artifact.text
    assert artifact.content.startswith(b"PK")
    assert artifact.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "wheat_assistant_Picking_Preparation.xlsx" in artifact.headers["content-disposition"]

    handed_off = client.post(f"/api/runs/{run['id']}/handoff")
    assert handed_off.status_code == 200, handed_off.text
    task = handed_off.json()
    assert task["run_id"] == run["id"]
    assert task["simulation"] is True
    assert task["status"] == "ready_for_review"
    assert task["snapshot"] == run["result_hash"]


@pytest.mark.parametrize("host_mime", ["application/zip", "application/octet-stream"])
def test_xlsx_download_ignores_host_mime_configuration(client, monkeypatch, host_mime):
    import mimetypes

    # Windows MIME mappings can be supplied by its registry. The application's
    # generated XLSX response must keep its format even when that map is wrong.
    mimetypes.init()
    monkeypatch.setitem(mimetypes.types_map, ".xlsx", host_mime)
    assert mimetypes.guess_type("synthetic.xlsx")[0] == host_mime
    test_week1_demo_end_to_end(client)


def test_week2_new_status_stays_exception_until_explicitly_excluded(
    client: TestClient,
) -> None:
    batch = load_week(client, 2)
    _, flow = plan_suggested(client, batch["id"])

    report = preflight(client, batch["id"], flow)
    assert report["row_count"] == 39
    assert report["errors"] == []
    assert report["status_guard"]["covered"] is False
    assert len(report["status_guard"]["unknown_values"]) == 1
    unknown = report["status_guard"]["unknown_values"][0]
    assert unknown["channel_id"] == "channel-b"
    assert unknown["field"] == "Status"
    assert unknown["value"] == "Partially shipped"
    assert unknown["count"] == 3
    assert len(unknown["row_ids"]) == 3

    # v0.2.1 strengthens approval: implicit Hold must be rejected, while the
    # original isolated-result assertions below remain unchanged.
    blocked = client.post(f"/api/batches/{batch['id']}/approve", json={
        "flow": flow, "reviewed": REVIEW_GROUPS, "expected_input_hash": report["input_hash"]})
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "STATUS_REVIEW_REQUIRED"
    assert client.app.state.store.list("approval") == []
    saved_without_rule = approve(client, batch["id"], flow, report["input_hash"], hold_review=report["hold_review"])
    first_run = execute(client, batch["id"], saved_without_rule["id"])
    assert_summary(
        first_run,
        input_rows=39,
        included=24,
        excluded=3,
        duplicate=3,
        exception=9,
    )

    partial_rows = client.get(
        f"/api/runs/{first_run['id']}/rows",
        params={"query": "Partially shipped", "limit": 200},
    )
    assert partial_rows.status_code == 200, partial_rows.text
    page = partial_rows.json()
    assert page["total"] == 3
    for row in page["rows"]:
        assert row["disposition"] == "exception"
        assert row["source_id"] == "channel-b"
        assert row["raw"]["Status"] == "Partially shipped"

    excluded_flow = copy.deepcopy(flow)
    excluded_flow["channels"]["channel-b"]["status_actions"]["Partially shipped"] = "exclude"
    second_report = preflight(client, batch["id"], excluded_flow)
    assert second_report["input_hash"] == report["input_hash"]
    assert second_report["status_guard"]["covered"] is True
    assert second_report["status_guard"]["unknown_values"] == []

    saved_with_rule = approve(
        client,
        batch["id"],
        excluded_flow,
        second_report["input_hash"],
    )
    assert saved_with_rule["id"] != saved_without_rule["id"]
    second_run = execute(client, batch["id"], saved_with_rule["id"])
    assert_summary(
        second_run,
        input_rows=39,
        included=24,
        excluded=6,
        duplicate=3,
        exception=6,
    )

    partial_rows = client.get(
        f"/api/runs/{second_run['id']}/rows",
        params={"query": "Partially shipped", "limit": 200},
    )
    assert partial_rows.status_code == 200, partial_rows.text
    page = partial_rows.json()
    assert page["total"] == 3
    for row in page["rows"]:
        assert row["disposition"] == "excluded"
        assert row["source_id"] == "channel-b"


def test_week3_reordered_columns_are_mapped_by_name(client: TestClient) -> None:
    batch = load_week(client, 3)
    channel_a = next(
        asset
        for asset in batch["files"]
        if asset["role"] == "orders" and asset["channel_id"] == "channel-a"
    )
    headers = channel_a["profile"]["headers"]
    assert headers[0] == "Order Status"
    assert headers[-1] == "Notes"
    assert "Item Code" in headers

    _, flow = plan_suggested(client, batch["id"])
    fields = flow["channels"]["channel-a"]["fields"]
    assert fields["order_id"] == "Order ID"
    assert fields["product"] == "Item Code"
    assert fields["status"] == "Order Status"

    report = preflight(client, batch["id"], flow)
    assert report["row_count"] == 24
    assert report["errors"] == []
    assert report["status_guard"]["covered"] is True
    assert report["unresolved_products"] == {}
    assert report["unresolved_units"] == {}

    saved = approve(client, batch["id"], flow, report["input_hash"])
    run = execute(client, batch["id"], saved["id"])
    assert_summary(
        run,
        input_rows=24,
        included=24,
        excluded=0,
        duplicate=0,
        exception=0,
    )

    rows = client.get(
        f"/api/runs/{run['id']}/rows",
        params={"limit": 200},
    )
    assert rows.status_code == 200, rows.text
    page = rows.json()
    assert page["total"] == 24
    assert {row["disposition"] for row in page["rows"]} == {"included"}
