"""Independent acceptance tests for the local hardening API.

Synthetic data only. Each test uses a temporary Store and a real FastAPI
TestClient. The API module is imported only after dotenv loading is disabled and
the three LLM variables are cleared; live model calls are replaced with a hard
failure. Expectations below are fixed independently from response bodies.
"""

from __future__ import annotations

import copy
import csv
import io
import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REVIEW_GROUPS = ["fields", "statuses", "products", "units", "duplicates", "output"]
ALIASES = {"Jasmine500": "TEA-001"}
UNIT_ALIASES = {"carton": "box"}
LLM_ENV = ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY")

ORDER_HEADERS = ["Order", "Line", "SKU", "Qty", "Unit", "Status"]
MASTER_HEADERS = ["SKU", "Name", "Base unit", "Box size", "Pack size"]
DEFAULT_MASTER_FIELDS = {
    "sku": "SKU",
    "name": "Name",
    "base_unit": "Base unit",
    "box": "Box size",
    "pack": "Pack size",
}


@pytest.fixture()
def api_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for name in LLM_ENV:
        monkeypatch.setenv(name, "")

    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)

    from maizi import api

    def forbidden_live(*args, **kwargs):
        raise AssertionError("Live model calls are forbidden in acceptance tests")

    monkeypatch.setattr(api, "propose_live", forbidden_live)
    return api


@pytest.fixture()
def app_factory(api_module, tmp_path: Path):
    def build():
        return api_module.create_app(data_dir=tmp_path)

    return build


@pytest.fixture()
def client(app_factory):
    with TestClient(app_factory()) as test_client:
        yield test_client


def csv_bytes(headers: list[str], rows: list[list[str]]) -> bytes:
    target = io.StringIO()
    writer = csv.writer(target)
    writer.writerow(headers)
    writer.writerows(rows)
    return target.getvalue().encode("utf-8-sig")


def upload(
    client: TestClient,
    filename: str,
    content: bytes,
    *,
    role: str,
    channel_id: str = "",
) -> dict:
    response = client.post(
        "/api/files",
        files={"file": (filename, content, "application/octet-stream")},
        data={"role": role, "channel_id": channel_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_batch(
    client: TestClient,
    orders: list[tuple[str, str, bytes]],
    master: tuple[str, bytes],
) -> dict:
    file_ids = [
        upload(client, name, content, role="orders", channel_id=channel)["id"]
        for name, channel, content in orders
    ]
    file_ids.append(upload(client, master[0], master[1], role="master")["id"])
    response = client.post(
        "/api/batches",
        json={"file_ids": file_ids, "label": "Synthetic acceptance"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def demo_batch(client: TestClient, week: int = 1) -> dict:
    response = client.post("/api/demo/load", json={"week": week})
    assert response.status_code == 200, response.text
    return response.json()


def suggested_flow(client: TestClient, batch_id: str) -> tuple[dict, dict]:
    response = client.post(
        f"/api/batches/{batch_id}/plan",
        json={"mode": "suggested"},
    )
    assert response.status_code == 200, response.text
    plan = response.json()
    flow = copy.deepcopy(plan["flow"])
    flow["aliases"] = dict(ALIASES)
    flow["unit_aliases"] = dict(UNIT_ALIASES)
    return plan, flow


def custom_flow(
    *,
    channel: str = "bulk",
    status_actions: dict | None = None,
    master_fields: dict | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "name": "Synthetic acceptance flow",
        "channels": {
            channel: {
                "fields": {
                    "order_id": "Order",
                    "line_id": "Line",
                    "product": "SKU",
                    "quantity": "Qty",
                    "unit": "Unit",
                    "status": "Status",
                    "date": None,
                },
                "status_actions": dict(
                    status_actions or {"INCLUDE": "include", "EXCLUDE": "exclude"}
                ),
                "dedup_mode": "business_key",
            }
        },
        "aliases": {},
        "unit_aliases": {},
        "master_fields": dict(master_fields or DEFAULT_MASTER_FIELDS),
        "output_columns": [
            {"header": "SKU", "field": "sku"},
            {"header": "Description", "field": "name"},
            {"header": "Pick quantity", "field": "quantity"},
            {"header": "Unit", "field": "unit"},
        ],
        "date_from": None,
        "date_to": None,
    }


def preflight(
    client: TestClient,
    batch_id: str,
    flow: dict,
    source_flow_id: str | None = None,
) -> dict:
    params = {"source_flow_id": source_flow_id} if source_flow_id else None
    response = client.post(
        f"/api/batches/{batch_id}/preflight",
        params=params,
        json=flow,
    )
    assert response.status_code == 200, response.text
    return response.json()


def approve(
    client: TestClient,
    batch_id: str,
    flow: dict,
    input_hash: str,
    source_flow_id: str | None = None,
    *,
    hold_review: dict | None = None,
) -> dict:
    response = client.post(
        f"/api/batches/{batch_id}/approve",
        json={
            "flow": flow,
            "reviewed": REVIEW_GROUPS,
            "expected_input_hash": input_hash,
            "source_flow_id": source_flow_id,
            **({"held_statuses": [{key: x[key] for key in ("channel_id", "field", "value")} for x in hold_review["groups"]],
                "hold_review_hash": hold_review["snapshot_hash"]} if hold_review else {}),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_run(client: TestClient, batch_id: str, flow_id: str) -> dict:
    response = client.post(
        "/api/runs",
        json={"batch_id": batch_id, "flow_id": flow_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def execute(client: TestClient, run_id: str) -> dict:
    response = client.post(f"/api/runs/{run_id}/execute")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "completed"
    return result


def ready_demo_run(client: TestClient, week: int = 1) -> tuple[dict, dict, dict]:
    batch = demo_batch(client, week)
    _, flow = suggested_flow(client, batch["id"])
    report = preflight(client, batch["id"], flow)
    assert report["errors"] == []
    confirmation = report["hold_review"] if report["hold_review"]["required"] else None
    if confirmation:
        blocked = client.post(f"/api/batches/{batch['id']}/approve", json={
            "flow": flow, "reviewed": REVIEW_GROUPS, "expected_input_hash": report["input_hash"]})
        assert blocked.status_code == 409, blocked.text
        assert blocked.json()["code"] == "STATUS_REVIEW_REQUIRED"
    saved = approve(client, batch["id"], flow, report["input_hash"], hold_review=confirmation)
    run = create_run(client, batch["id"], saved["id"])
    return batch, saved, run


def completed_demo_run(client: TestClient, week: int = 1) -> tuple[dict, dict, dict]:
    batch, saved, run = ready_demo_run(client, week)
    return batch, saved, execute(client, run["id"])


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
    assert summary == {
        "input": input_rows,
        "included": included,
        "excluded": excluded,
        "duplicate": duplicate,
        "exception": exception,
        "totals_match": True,
    }


def simple_batch(client: TestClient) -> tuple[dict, dict]:
    order_content = csv_bytes(
        ORDER_HEADERS,
        [
            ["SYN-SIMPLE-1", "1", "SKU-0001", "2", "piece", "INCLUDE"],
            ["SYN-SIMPLE-2", "1", "SKU-0001", "1", "piece", "INCLUDE"],
        ],
    )
    master_content = csv_bytes(
        MASTER_HEADERS,
        [["SKU-0001", "Synthetic product", "piece", "12", "6"]],
    )
    batch = create_batch(
        client,
        [("synthetic_orders.csv", "bulk", order_content)],
        ("synthetic_master.csv", master_content),
    )
    return batch, custom_flow()


def test_source_flow_reuse_and_rule_versioning(client: TestClient) -> None:
    batch_a = demo_batch(client, 1)
    _, flow_a = suggested_flow(client, batch_a["id"])
    report_a = preflight(client, batch_a["id"], flow_a)
    saved_a = approve(client, batch_a["id"], flow_a, report_a["input_hash"])
    assert saved_a["workflow_id"] == saved_a["id"]
    assert saved_a["rule_version"] == 1
    assert saved_a["parent_flow_id"] is None
    store = client.app.state.store
    snapshot_a = copy.deepcopy(store.get("flow", saved_a["id"]))

    batch_b = demo_batch(client, 1)
    plan_response = client.post(
        f"/api/batches/{batch_b['id']}/plan",
        json={"mode": "suggested", "source_flow_id": saved_a["id"]},
    )
    assert plan_response.status_code == 200, plan_response.text
    plan_b = plan_response.json()
    assert plan_b["source_flow_id"] == saved_a["id"]
    assert plan_b["flow"] == flow_a

    report_b = preflight(
        client,
        batch_b["id"],
        plan_b["flow"],
        source_flow_id=saved_a["id"],
    )
    assert report_b["diff"]["source_flow_id"] == saved_a["id"]
    assert all(not group["changed"] for group in report_b["diff"]["groups"])
    saved_b = approve(
        client,
        batch_b["id"],
        plan_b["flow"],
        report_b["input_hash"],
        source_flow_id=saved_a["id"],
    )
    assert saved_b["id"] != saved_a["id"]
    assert saved_b["batch_id"] == batch_b["id"]
    assert saved_b["workflow_id"] == saved_a["workflow_id"]
    assert saved_b["rule_version"] == 1
    assert saved_b["parent_flow_id"] == saved_a["id"]

    changed = copy.deepcopy(flow_a)
    changed["channels"]["channel-a"]["status_actions"]["Shipped"] = "exclude"
    report_c = preflight(
        client,
        batch_b["id"],
        changed,
        source_flow_id=saved_a["id"],
    )
    groups = {group["group"]: group for group in report_c["diff"]["groups"]}
    assert groups["statuses"]["changed"] is True
    assert report_c["diff"]["source_flow_id"] == saved_a["id"]
    saved_c = approve(
        client,
        batch_b["id"],
        changed,
        report_c["input_hash"],
        source_flow_id=saved_a["id"],
    )
    assert saved_c["workflow_id"] == saved_a["workflow_id"]
    assert saved_c["rule_version"] == 2
    assert saved_c["parent_flow_id"] == saved_a["id"]
    assert saved_c["id"] not in {saved_a["id"], saved_b["id"]}

    assert store.get("flow", saved_a["id"]) == snapshot_a
    assert store.get("flow", saved_b["id"])["rule_version"] == 1
    approvals = [
        item for item in store.list("approval") if item.get("stage") == "rules"
    ]
    assert len(approvals) == 3
    assert {item["flow_id"] for item in approvals} == {
        saved_a["id"],
        saved_b["id"],
        saved_c["id"],
    }


def test_unknown_source_flow_and_unknown_channel_are_blocked(client: TestClient) -> None:
    batch = demo_batch(client, 1)
    _, flow = suggested_flow(client, batch["id"])
    unknown_flow = client.post(
        f"/api/batches/{batch['id']}/preflight",
        params={"source_flow_id": "missing-synthetic-flow"},
        json=flow,
    )
    assert unknown_flow.status_code == 404, unknown_flow.text
    assert "not found" in unknown_flow.json()["detail"]

    order_content = csv_bytes(
        ORDER_HEADERS,
        [["SYN-GHOST-1", "1", "SKU-0001", "1", "piece", "INCLUDE"]],
    )
    master_content = csv_bytes(
        MASTER_HEADERS,
        [["SKU-0001", "Synthetic product", "piece", "12", "6"]],
    )
    ghost_batch = create_batch(
        client,
        [("synthetic_ghost.csv", "GHOST-SOURCE", order_content)],
        ("synthetic_master.csv", master_content),
    )
    flow_for_known = custom_flow(channel="known-source")
    report = preflight(client, ghost_batch["id"], flow_for_known)
    assert any("Missing channel rule: GHOST-SOURCE" in item for item in report["errors"])

    blocked = client.post(
        f"/api/batches/{ghost_batch['id']}/approve",
        json={
            "flow": flow_for_known,
            "reviewed": REVIEW_GROUPS,
            "expected_input_hash": report["input_hash"],
        },
    )
    assert blocked.status_code == 422, blocked.text
    assert "Missing channel rule: GHOST-SOURCE" in blocked.json()["detail"]


def test_observed_statuses_across_files_and_actual_master_units(
    client: TestClient,
) -> None:
    master_fields = {
        **DEFAULT_MASTER_FIELDS,
        "crate": "Crate size",
    }
    master_content = csv_bytes(
        MASTER_HEADERS + ["Crate size"],
        [
            ["SKU-0001", "Synthetic product one", "piece", "12", "6", "24"],
            ["SKU-0002", "Synthetic product two", "piece", "10", "5", "20"],
        ],
    )
    first_statuses = [f"S{index:03d}" for index in range(1, 41)]
    second_statuses = [f"S{index:03d}" for index in range(41, 76)]
    rows_first = [
        [f"SYN-MULTI-A-{index:03d}", "1", "SKU-0001", "1", "piece", status]
        for index, status in enumerate(first_statuses, 1)
    ]
    rows_second = [
        [f"SYN-MULTI-B-{index:03d}", "1", "SKU-0002", "1", "piece", status]
        for index, status in enumerate(second_statuses, 1)
    ]
    batch = create_batch(
        client,
        [
            ("multi_first.csv", "multi", csv_bytes(ORDER_HEADERS, rows_first)),
            ("multi_second.csv", "multi", csv_bytes(ORDER_HEADERS, rows_second)),
        ],
        ("multi_master.csv", master_content),
    )
    flow = custom_flow(
        channel="multi",
        status_actions={"S001": "include"},
        master_fields=master_fields,
    )
    report = preflight(client, batch["id"], flow)
    assert report["errors"] == []
    observed = report["observed_statuses"]["multi"]
    assert len(observed) == 75
    assert sum(observed.values()) == 75
    assert observed["S001"] == 1
    assert observed["S075"] == 1
    assert report["available_units"] == ["box", "crate", "pack", "piece"]

    detail = client.get(f"/api/batches/{batch['id']}")
    assert detail.status_code == 200, detail.text
    order_files = [
        item for item in detail.json()["files"] if item["role"] == "orders"
    ]
    assert len(order_files) == 2
    assert all(
        len(item["profile"]["columns"]["Status"]["values"]) < 60
        for item in order_files
    )


def pagination_run(client: TestClient) -> tuple[dict, dict, dict]:
    master_rows = [
        [f"SKU-{index:04d}", f"Synthetic product {index}", "piece", "12", "6"]
        for index in range(1, 56)
    ]
    order_rows = []
    for index in range(1, 126):
        if index <= 110:
            status, quantity = "INCLUDE", "1"
        elif index <= 120:
            status, quantity = "INCLUDE", "0"
        else:
            status, quantity = "EXCLUDE", "1"
        sku = f"SKU-{(index - 1) % 55 + 1:04d}"
        order_rows.append(
            [f"SYN-PAGE-{index:03d}", "1", sku, quantity, "piece", status]
        )
    batch = create_batch(
        client,
        [("pagination_orders.csv", "bulk", csv_bytes(ORDER_HEADERS, order_rows))],
        ("pagination_master.csv", csv_bytes(MASTER_HEADERS, master_rows)),
    )
    flow = custom_flow(
        status_actions={"INCLUDE": "include", "EXCLUDE": "exclude"},
    )
    report = preflight(client, batch["id"], flow)
    assert report["errors"] == []
    saved = approve(client, batch["id"], flow, report["input_hash"])
    run = create_run(client, batch["id"], saved["id"])
    return batch, saved, execute(client, run["id"])


def test_rows_and_sku_summary_pagination_search_and_filters(
    client: TestClient,
) -> None:
    _, _, run = pagination_run(client)
    assert_summary(
        run,
        input_rows=125,
        included=110,
        excluded=5,
        duplicate=0,
        exception=10,
    )

    first = client.get(
        f"/api/runs/{run['id']}/rows",
        params={"limit": 100, "offset": 0},
    )
    assert first.status_code == 200, first.text
    first_page = first.json()
    assert first_page["total"] == 125
    assert first_page["offset"] == 0
    assert first_page["limit"] == 100
    assert len(first_page["rows"]) == 100

    second = client.get(
        f"/api/runs/{run['id']}/rows",
        params={"limit": 100, "offset": 100},
    )
    second_page = second.json()
    assert second_page["total"] == 125
    assert second_page["offset"] == 100
    assert len(second_page["rows"]) == 25

    end = client.get(
        f"/api/runs/{run['id']}/rows",
        params={"offset": 125, "limit": 100},
    ).json()
    assert end["total"] == 125
    assert end["rows"] == []

    clamped = client.get(
        f"/api/runs/{run['id']}/rows",
        params={"limit": 999, "offset": 0},
    ).json()
    assert clamped["limit"] == 200
    assert len(clamped["rows"]) == 125

    search = client.get(
        f"/api/runs/{run['id']}/rows",
        params={"query": "SYN-PAGE-105"},
    ).json()
    assert search["total"] == 1
    assert search["rows"][0]["raw"]["Order"] == "SYN-PAGE-105"

    reason = client.get(
        f"/api/runs/{run['id']}/rows",
        params={"reason_code": "INVALID_QUANTITY", "limit": 100},
    ).json()
    assert reason["total"] == 10
    assert all(
        any(item["code"] == "INVALID_QUANTITY" for item in row["reasons"])
        for row in reason["rows"]
    )

    row_id = first_page["rows"][0]["source_row_id"]
    exact = client.get(
        f"/api/runs/{run['id']}/rows",
        params={"source_row_id": row_id},
    ).json()
    assert exact["total"] == 1
    assert exact["rows"][0]["source_row_id"] == row_id

    sku_first = client.get(
        f"/api/runs/{run['id']}/sku-summary",
        params={"limit": 50, "offset": 0},
    ).json()
    assert sku_first["total"] == 55
    assert sku_first["offset"] == 0
    assert sku_first["limit"] == 50
    assert len(sku_first["rows"]) == 50
    assert sku_first["rows"][0]["sku"] == "SKU-0001"

    sku_second = client.get(
        f"/api/runs/{run['id']}/sku-summary",
        params={"limit": 50, "offset": 50},
    ).json()
    assert sku_second["total"] == 55
    assert len(sku_second["rows"]) == 5
    assert sku_second["rows"][-1]["sku"] == "SKU-0055"

    sku_query = client.get(
        f"/api/runs/{run['id']}/sku-summary",
        params={"query": "SKU-0055"},
    ).json()
    assert sku_query["total"] == 1
    assert sku_query["rows"][0]["sku"] == "SKU-0055"

    sku_clamped = client.get(
        f"/api/runs/{run['id']}/sku-summary",
        params={"limit": 999},
    ).json()
    assert sku_clamped["total"] == 55
    assert sku_clamped["limit"] == 200
    assert len(sku_clamped["rows"]) == 55

    total_quantity = sum(
        Decimal(item["quantity"]) for item in sku_first["rows"] + sku_second["rows"]
    )
    assert total_quantity == Decimal("110")


def test_history_pagination_and_run_id_activity_isolation(client: TestClient) -> None:
    batch_one, flow_one, run_one = completed_demo_run(client, 1)
    batch_two, flow_two, run_two = completed_demo_run(client, 2)

    runs_page_one = client.get(
        "/api/history/runs",
        params={"limit": 1, "offset": 0},
    ).json()
    assert runs_page_one["total"] == 2
    assert runs_page_one["offset"] == 0
    assert runs_page_one["limit"] == 1
    assert len(runs_page_one["rows"]) == 1
    assert "result" not in runs_page_one["rows"][0]

    runs_page_two = client.get(
        "/api/history/runs",
        params={"limit": 1, "offset": 1},
    ).json()
    assert runs_page_two["total"] == 2
    assert len(runs_page_two["rows"]) == 1
    assert runs_page_one["rows"][0]["id"] != runs_page_two["rows"][0]["id"]

    runs_end = client.get(
        "/api/history/runs",
        params={"limit": 1, "offset": 2},
    ).json()
    assert runs_end["total"] == 2
    assert runs_end["rows"] == []

    all_activity = client.get(
        "/api/history/activity",
        params={"limit": 200},
    ).json()
    filtered = client.get(
        "/api/history/activity",
        params={"run_id": run_one["id"], "limit": 200},
    ).json()
    assert filtered["total"] > 0
    assert filtered["total"] <= all_activity["total"]
    assert any(
        row["action"] == "run_completed" and row["subject"] == run_one["id"]
        for row in filtered["rows"]
    )

    related_one = {
        run_one["id"],
        batch_one["id"],
        flow_one["id"],
        *batch_one["file_ids"],
    }
    related_two = {
        run_two["id"],
        batch_two["id"],
        flow_two["id"],
        *batch_two["file_ids"],
    }
    exclusive_two = related_two - related_one
    assert all(row["subject"] not in exclusive_two for row in filtered["rows"])

    activity_page_one = client.get(
        "/api/history/activity",
        params={"run_id": run_one["id"], "limit": 2, "offset": 0},
    ).json()
    activity_page_two = client.get(
        "/api/history/activity",
        params={"run_id": run_one["id"], "limit": 2, "offset": 2},
    ).json()
    assert activity_page_one["total"] == filtered["total"]
    assert activity_page_two["total"] == filtered["total"]
    assert len(activity_page_one["rows"]) <= 2
    assert len(activity_page_two["rows"]) <= 2
    assert {
        row["id"] for row in activity_page_one["rows"]
    }.isdisjoint({row["id"] for row in activity_page_two["rows"]})

    unknown = client.get("/api/history/unknown-kind")
    assert unknown.status_code == 404


def test_failed_run_retries_on_same_run(
    client: TestClient, api_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, run = ready_demo_run(client)
    original = api_module.execute_isolated

    def fail_worker(*args, **kwargs):
        raise RuntimeError("synthetic worker failure")

    monkeypatch.setattr(api_module, "execute_isolated", fail_worker)
    failed = client.post(f"/api/runs/{run['id']}/execute")
    assert failed.status_code == 422, failed.text
    assert "synthetic worker failure" in failed.json()["detail"]

    failed_state = client.get(f"/api/runs/{run['id']}").json()
    assert failed_state["status"] == "failed"
    assert "synthetic worker failure" in failed_state["error"]

    monkeypatch.setattr(api_module, "execute_isolated", original)
    retried = execute(client, run["id"])
    assert retried["id"] == run["id"]
    assert_summary(
        retried,
        input_rows=36,
        included=24,
        excluded=3,
        duplicate=3,
        exception=6,
    )


def test_interrupted_run_recovers_on_same_run(app_factory) -> None:
    with TestClient(app_factory()) as first:
        _, _, run = ready_demo_run(first)
        store = first.app.state.store
        current = store.get("run", run["id"])
        store.put("run", run["id"], {**current, "status": "running"})

    with TestClient(app_factory()) as second:
        interrupted = second.get(f"/api/runs/{run['id']}").json()
        assert interrupted["status"] == "interrupted"
        assert "restarted" in interrupted["error"].lower()
        recovered = execute(second, run["id"])
        assert recovered["id"] == run["id"]
        assert_summary(
            recovered,
            input_rows=36,
            included=24,
            excluded=3,
            duplicate=3,
            exception=6,
        )


def test_export_failure_is_visible_and_retryable(
    client: TestClient, api_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, run = completed_demo_run(client)
    original = api_module.export_workbook

    def fail_export(*args, **kwargs):
        raise ValueError("synthetic export failure")

    monkeypatch.setattr(api_module, "export_workbook", fail_export)
    failed = client.post(
        f"/api/runs/{run['id']}/export-approval",
        json={"result_hash": run["result_hash"], "acknowledge_exceptions": True},
    )
    assert failed.status_code == 422, failed.text
    assert "synthetic export failure" in failed.json()["detail"]

    failed_state = client.get(f"/api/runs/{run['id']}").json()
    assert failed_state["export_state"] == "failed"
    assert "synthetic export failure" in failed_state["export_error"]

    exports_before = client.get(f"/api/runs/{run['id']}/exports").json()
    failed_export = next(
        item for item in exports_before if item["status"] == "failed"
    )

    monkeypatch.setattr(api_module, "export_workbook", original)
    retried = client.post(
        f"/api/runs/{run['id']}/export-approval",
        json={"result_hash": run["result_hash"], "acknowledge_exceptions": True},
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["export_id"] != failed_export["id"]

    ready_state = client.get(f"/api/runs/{run['id']}").json()
    assert ready_state["export_state"] == "ready"
    assert ready_state["export_error"] is None
    assert client.get(f"/api/runs/{run['id']}/download").status_code == 200

    exports_after = client.get(f"/api/runs/{run['id']}/exports").json()
    assert any(item["id"] == failed_export["id"] for item in exports_after)
    assert any(
        item["id"] == retried.json()["export_id"] and item["status"] == "ready"
        for item in exports_after
    )


def test_export_idempotency_and_legacy_artifact_retention(client: TestClient) -> None:
    _, _, run = completed_demo_run(client)
    store = client.app.state.store
    current = store.get("run", run["id"])
    old_name = "synthetic_legacy_export.xlsx"
    old_bytes = b"SYNTHETIC-LEGACY-ARTIFACT"
    old_path = store.root / "artifacts" / old_name
    old_path.write_bytes(old_bytes)
    store.put(
        "run",
        run["id"],
        {
            **current,
            "export_approved": True,
            "artifact": old_name,
            "export_state": "ready",
            "export_stage": "ready",
        },
    )

    approved = client.post(
        f"/api/runs/{run['id']}/export-approval",
        json={"result_hash": run["result_hash"], "acknowledge_exceptions": True},
    )
    assert approved.status_code == 200, approved.text
    new_export_id = approved.json()["export_id"]

    exports = client.get(f"/api/runs/{run['id']}/exports").json()
    legacy = next(item for item in exports if item.get("legacy") is True)
    current_export = next(
        item for item in exports if item["id"] == new_export_id
    )
    assert legacy["version"] == 1
    assert legacy["artifact"] == old_name
    assert current_export["version"] == 2
    assert old_path.read_bytes() == old_bytes

    legacy_download = client.get(
        f"/api/runs/{run['id']}/download",
        params={"export_id": legacy["id"]},
    )
    assert legacy_download.status_code == 200, legacy_download.text
    assert legacy_download.content == old_bytes

    current_download = client.get(f"/api/runs/{run['id']}/download")
    assert current_download.status_code == 200, current_download.text
    assert current_download.content.startswith(b"PK")
    assert current_download.content != old_bytes
    assert old_path.read_bytes() == old_bytes

    repeated = client.post(
        f"/api/runs/{run['id']}/export-approval",
        json={"result_hash": run["result_hash"], "acknowledge_exceptions": True},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["export_id"] == new_export_id
    assert len(client.get(f"/api/runs/{run['id']}/exports").json()) == 2
    assert old_path.read_bytes() == old_bytes

    old_path.write_bytes(b"TAMPERED-LEGACY-ARTIFACT")
    tampered = client.get(
        f"/api/runs/{run['id']}/download",
        params={"export_id": legacy["id"]},
    )
    assert tampered.status_code == 422, tampered.text
    assert "exported file changed" in tampered.json()["detail"]


def test_legacy_parser_table_can_continue_when_identical(client: TestClient) -> None:
    batch, flow = simple_batch(client)
    store = client.app.state.store
    asset_id = batch["file_ids"][0]
    asset = store.get("file", asset_id)
    legacy_table = copy.deepcopy(asset["table"])
    legacy_table.pop("parser_version", None)
    for record in legacy_table["records"]:
        record.pop("row_end_number", None)
    store.put("file", asset_id, {**asset, "table": legacy_table})

    report = preflight(client, batch["id"], flow)
    assert report["errors"] == []
    saved = approve(client, batch["id"], flow, report["input_hash"])
    run = execute(client, create_run(client, batch["id"], saved["id"])["id"])
    assert_summary(
        run,
        input_rows=2,
        included=2,
        excluded=0,
        duplicate=0,
        exception=0,
    )


def test_legacy_parser_table_mismatch_requires_new_batch(client: TestClient) -> None:
    batch, flow = simple_batch(client)
    store = client.app.state.store
    asset_id = batch["file_ids"][0]
    asset = store.get("file", asset_id)
    legacy_table = copy.deepcopy(asset["table"])
    legacy_table.pop("parser_version", None)
    for record in legacy_table["records"]:
        record.pop("row_end_number", None)
    legacy_table["records"][0]["data"]["Order"] = "SYNTHETIC-TAMPERED"
    store.put("file", asset_id, {**asset, "table": legacy_table})

    response = client.post(
        f"/api/batches/{batch['id']}/preflight",
        json=flow,
    )
    assert response.status_code == 422, response.text
    assert "Legacy input parsing changed" in response.json()["detail"]
    assert "new batch" in response.json()["detail"]

    blocked = client.post(
        f"/api/batches/{batch['id']}/approve",
        json={
            "flow": flow,
            "reviewed": REVIEW_GROUPS,
            "expected_input_hash": batch["input_hash"],
        },
    )
    assert blocked.status_code == 422, blocked.text
    assert "Legacy input parsing changed" in blocked.json()["detail"]


def test_store_backup_integrity_before_upgrade(
    tmp_path: Path, app_factory
) -> None:
    database = tmp_path / "maizi.sqlite"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE sentinel (value TEXT)")
    connection.execute("INSERT INTO sentinel VALUES ('synthetic-pre-upgrade')")
    connection.commit()
    connection.close()

    with TestClient(app_factory()) as client:
        health = client.get("/api/health")
        assert health.status_code == 200

    backups = sorted((tmp_path / "backups").glob("hardening-v2-*"))
    assert len(backups) == 1
    marker = json.loads((tmp_path / "backups" / "hardening-v2.json").read_text("utf-8"))
    assert marker["verified"] is True
    assert marker["backup"] == backups[0].name

    backup_db = backups[0] / "maizi.sqlite"
    with sqlite3.connect(backup_db) as mirrored:
        assert mirrored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert mirrored.execute("SELECT value FROM sentinel").fetchone()[0] == (
            "synthetic-pre-upgrade"
        )

    with TestClient(app_factory()) as client:
        assert client.get("/api/health").status_code == 200
    assert len(sorted((tmp_path / "backups").glob("hardening-v2-*"))) == 1
