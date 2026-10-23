"""Windows v0.2.1 frozen-contract acceptance tests.

Synthetic data only. The API is imported only after dotenv loading is disabled
and the LLM variables are cleared. This module tests the frozen v0.2.1
interfaces independently of the production implementation.
"""

from __future__ import annotations

import copy
import csv
import io
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REVIEW_GROUPS = ["fields", "statuses", "products", "units", "duplicates", "output"]
LLM_ENV = ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY")
STATUS_FIELD = "Status"
ORDER_HEADERS = ["Order", "Line", "SKU", "Qty", "Unit", "Status"]
MASTER_HEADERS = ["SKU", "Name", "Base unit", "Box size", "Pack size"]
MASTER_FIELDS = {
    "sku": "SKU",
    "name": "Name",
    "base_unit": "Base unit",
    "box": "Box size",
    "pack": "Pack size",
}
UNSET = object()


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch):
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    for name in LLM_ENV:
        monkeypatch.setenv(name, "")


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from wheat_assistant import api

    def forbidden_provider(*args, **kwargs):
        raise AssertionError("Provider calls are forbidden in this test module")

    monkeypatch.setattr(api, "propose_live", forbidden_provider)
    with TestClient(api.create_app(data_dir=tmp_path)) as test_client:
        yield test_client


def csv_bytes(headers: list[str], rows: list[list[str]]) -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def master_content() -> bytes:
    return csv_bytes(
        MASTER_HEADERS,
        [["SKU-0001", "Synthetic product", "piece", "12", "6"]],
    )


def upload(client: TestClient, name: str, content: bytes, role: str, channel: str = "") -> dict:
    response = client.post(
        "/api/files",
        files={"file": (name, content, "text/csv")},
        data={"role": role, "channel_id": channel},
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_batch(
    client: TestClient,
    order_files: list[tuple[str, bytes]],
    *,
    channel: str = "source",
    label: str = "Synthetic Windows v0.2.1 batch",
) -> dict:
    file_ids = [
        upload(client, name, content, "orders", channel)["id"]
        for name, content in order_files
    ]
    file_ids.append(upload(client, "synthetic_master.csv", master_content(), "master")["id"])
    response = client.post(
        "/api/batches",
        json={"file_ids": file_ids, "label": label},
    )
    assert response.status_code == 200, response.text
    return response.json()


def make_flow(status_actions: dict[str, str], *, channel: str = "source", name: str = "Synthetic flow") -> dict:
    return {
        "schema_version": 1,
        "name": name,
        "channels": {
            channel: {
                "fields": {
                    "order_id": "Order",
                    "line_id": "Line",
                    "product": "SKU",
                    "quantity": "Qty",
                    "unit": "Unit",
                    "status": STATUS_FIELD,
                    "date": None,
                },
                "status_actions": dict(status_actions),
                "dedup_mode": "business_key",
            }
        },
        "aliases": {},
        "unit_aliases": {},
        "master_fields": dict(MASTER_FIELDS),
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
    *,
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


def approval_body(
    flow: dict,
    input_hash: str,
    *,
    held=UNSET,
    hold_review_hash=UNSET,
    source_flow_id: str | None = None,
) -> dict:
    body = {
        "flow": flow,
        "reviewed": REVIEW_GROUPS,
        "expected_input_hash": input_hash,
    }
    if source_flow_id:
        body["source_flow_id"] = source_flow_id
    if held is not UNSET:
        body["held_statuses"] = held
    if hold_review_hash is not UNSET:
        body["hold_review_hash"] = hold_review_hash
    return body


def hold_entries(report: dict) -> list[dict[str, str]]:
    return [
        {
            "channel_id": group["channel_id"],
            "field": group["field"],
            "value": group["value"],
        }
        for group in report["hold_review"]["groups"]
    ]


def approve(client: TestClient, batch_id: str, body: dict):
    return client.post(f"/api/batches/{batch_id}/approve", json=body)


def create_run(client: TestClient, batch_id: str, flow_id: str):
    response = client.post(
        "/api/runs",
        json={"batch_id": batch_id, "flow_id": flow_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def execute(client: TestClient, run_id: str) -> dict:
    response = client.post(f"/api/runs/{run_id}/execute")
    assert response.status_code == 200, response.text
    return response.json()


def counts(client: TestClient) -> tuple[int, int, int, int]:
    store = client.app.state.store
    return tuple(
        len(store.list(kind))
        for kind in ("flow", "approval", "run", "activity")
    )


def make_legacy(client: TestClient, flow_id: str) -> None:
    store = client.app.state.store
    flow = copy.deepcopy(store.get("flow", flow_id))
    for key in ("approval_policy_version", "held_statuses", "hold_review_hash"):
        flow.pop(key, None)
    store.put("flow", flow_id, flow)
    for approval in store.list("approval"):
        if approval.get("flow_id") != flow_id:
            continue
        legacy = copy.deepcopy(approval)
        for key in ("approval_policy_version", "held_statuses", "hold_review_hash"):
            legacy.pop(key, None)
        store.put("approval", approval["id"], legacy)


def test_lf_crlf_multiline_preserves_content_and_physical_rows() -> None:
    from wheat_assistant.files import parse_table

    lf = b'Order,Note\nSYN-LF,"first\nsecond"\nSYN-LF-2,plain\n'
    crlf = b'Order,Note\r\nSYN-CR,"first\r\nsecond"\r\nSYN-CR-2,plain\r\n'

    lf_table = parse_table(lf, "synthetic_lf.csv", "orders")
    crlf_table = parse_table(crlf, "synthetic_crlf.csv", "orders")

    assert lf_table["records"][0]["data"]["Note"] == "first\nsecond"
    assert lf_table["records"][0]["row_number"] == 2
    assert lf_table["records"][0]["row_end_number"] == 3
    assert lf_table["records"][1]["row_number"] == 4

    assert crlf_table["records"][0]["data"]["Note"] == "first\r\nsecond"
    assert crlf_table["records"][0]["row_number"] == 2
    assert crlf_table["records"][0]["row_end_number"] == 3
    assert crlf_table["records"][1]["row_number"] == 4


def test_child_environment_windows_native_allowlist_and_secrets() -> None:
    from wheat_assistant.runtime_environment import child_environment

    root = r"C:\Windows"
    environment = {
        "systemroot": root,
        "windir": root,
        "Path": r"C:\Synthetic\Tools",
        "TEMP": r"C:\Synthetic\Temp",
        "LLM_API_KEY": "synthetic-secret-key",
        "OPENAI_API_KEY": "synthetic-openai-key",
        "AWS_SECRET_ACCESS_KEY": "synthetic-aws-key",
        "WHEAT_ASSISTANT_DATA_DIR": r"C:\Synthetic\Private",
    }
    result = child_environment(environment, native=True, windows=True)
    lower_keys = {key.casefold() for key in result}

    assert result["SystemRoot"] == root
    assert "systemroot" not in result
    assert "PATH" in result
    expected_path = (root + r"\System32").casefold()
    assert result["PATH"].replace("/", "\\").strip("\\;").casefold() == expected_path
    assert not lower_keys.intersection(
        {"llm_api_key", "openai_api_key", "aws_secret_access_key", "wheat_assistant_data_dir"}
    )
    assert "synthetic-secret-key" not in {str(value) for value in result.values()}
    assert "synthetic-openai-key" not in {str(value) for value in result.values()}


def test_child_environment_windows_worker_path_and_case_insensitive_keys() -> None:
    from wheat_assistant.runtime_environment import child_environment

    result = child_environment(
        {
            "SYSTEMROOT": r"C:\Windows",
            "path": r"C:\Synthetic\Tools",
            "llm_model": "synthetic-model",
        },
        native=False,
        windows=True,
    )
    assert result["SystemRoot"] == r"C:\Windows"
    assert result["PATH"].casefold() == r"c:\synthetic\tools".casefold()
    assert not any(key.casefold() == "llm_model" for key in result)


def test_child_environment_windows_requires_systemroot_and_posix_native_path() -> None:
    from wheat_assistant.runtime_environment import child_environment

    with pytest.raises(ValueError) as caught:
        child_environment({"PATH": r"C:\Synthetic\Tools"}, native=True, windows=True)
    assert "systemroot" in str(caught.value).casefold()
    assert "synthetic-secret" not in str(caught.value)

    posix = child_environment(
        {
            "PATH": "/synthetic/tools",
            "HOME": "/synthetic/home",
            "LLM_API_KEY": "synthetic-secret-key",
        },
        native=True,
        windows=False,
    )
    assert posix["PATH"] == "/usr/bin:/bin"
    assert not any(key.casefold() == "llm_api_key" for key in posix)
    assert "synthetic-secret-key" not in {str(value) for value in posix.values()}


def test_store_close_is_idempotent_and_closes_raw_sqlite_connections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from wheat_assistant.store import Store

    database = tmp_path / "wheat_assistant.sqlite"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "CREATE TABLE entities (id VARCHAR PRIMARY KEY, kind VARCHAR, payload JSON, created VARCHAR)"
        )
        connection.execute(
            "INSERT INTO entities VALUES ('old', 'flow', '{\"id\":\"old\",\"sentinel\":true}', '2026-01-01')"
        )
        connection.commit()
    finally:
        connection.close()

    real_connect = sqlite3.connect
    opened = []

    def tracking_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr("wheat_assistant.store.sqlite3.connect", tracking_connect)
    store = Store(tmp_path)
    assert opened

    store.close()
    store.close()

    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")


def test_lifespan_closes_store_on_normal_exit_and_startup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from wheat_assistant.api import create_app
    from wheat_assistant.store import Store

    calls = []
    original_close = getattr(Store, "close", None)

    def recording_close(self):
        calls.append(self)
        if original_close is not None:
            original_close(self)

    monkeypatch.setattr(Store, "close", recording_close, raising=False)

    with TestClient(create_app(data_dir=tmp_path / "normal")) as client:
        assert client.get("/api/health").status_code == 200
    assert calls

    calls.clear()
    original_list = Store.list

    def failing_list(self, kind):
        if kind == "run":
            raise RuntimeError("synthetic startup failure")
        return original_list(self, kind)

    monkeypatch.setattr(Store, "list", failing_list)
    raised = False
    try:
        with TestClient(create_app(data_dir=tmp_path / "startup-failure")) as client:
            client.get("/api/health")
    except Exception:
        raised = True
    assert raised
    assert calls


def hold_batch(client: TestClient) -> tuple[dict, dict, dict]:
    content = csv_bytes(
        ORDER_HEADERS,
        [
            ["SYN-HOLD-1", "1", "SKU-0001", "1", "piece", "INCLUDE"],
            ["SYN-HOLD-2", "1", "SKU-0001", "2", "piece", "EXCLUDE"],
            ["SYN-HOLD-3", "1", "SKU-0001", "3", "piece", "HELD"],
            ["SYN-HOLD-4", "1", "SKU-0001", "4", "piece", ""],
        ],
    )
    batch = create_batch(client, [("synthetic_hold.csv", content)], channel="source")
    flow = make_flow({"INCLUDE": "include", "EXCLUDE": "exclude"})
    report = preflight(client, batch["id"], flow)
    return batch, flow, report


def test_hold_review_requires_exact_confirmation_and_is_isolated(
    client: TestClient,
) -> None:
    batch, flow, report = hold_batch(client)
    review = report["hold_review"]
    assert review["required"] is True
    groups = {
        (group["channel_id"], group["field"], group["value"], group["count"])
        for group in review["groups"]
    }
    assert groups == {
        ("source", STATUS_FIELD, "HELD", 1),
        ("source", STATUS_FIELD, "", 1),
    }
    held = hold_entries(report)
    assert len(held) == 2

    body = approval_body(flow, report["input_hash"])
    before = counts(client)
    missing = approve(client, batch["id"], body)
    assert missing.status_code == 409, missing.text
    assert missing.json()["code"] == "STATUS_REVIEW_REQUIRED"
    assert counts(client) == before

    duplicate = approve(
        client,
        batch["id"],
        approval_body(
            flow,
            report["input_hash"],
            held=held + [held[0]],
            hold_review_hash=review["snapshot_hash"],
        ),
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "STATUS_REVIEW_REQUIRED"
    assert counts(client) == before

    extraneous = held + [
        {"channel_id": "source", "field": STATUS_FIELD, "value": "NOT-OBSERVED"}
    ]
    extra = approve(
        client,
        batch["id"],
        approval_body(
            flow,
            report["input_hash"],
            held=extraneous,
            hold_review_hash=review["snapshot_hash"],
        ),
    )
    assert extra.status_code == 409, extra.text
    assert extra.json()["code"] == "STATUS_REVIEW_REQUIRED"
    assert counts(client) == before

    stale = approve(
        client,
        batch["id"],
        approval_body(
            flow,
            report["input_hash"],
            held=held,
            hold_review_hash="0" * 64,
        ),
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "STATUS_REVIEW_REQUIRED"
    assert counts(client) == before

    partial = approve(
        client,
        batch["id"],
        approval_body(
            flow,
            report["input_hash"],
            held=held[:1],
            hold_review_hash=review["snapshot_hash"],
        ),
    )
    assert partial.status_code == 409, partial.text
    assert partial.json()["code"] == "STATUS_REVIEW_REQUIRED"
    assert counts(client) == before

    good_body = approval_body(
        flow,
        report["input_hash"],
        held=held,
        hold_review_hash=review["snapshot_hash"],
    )
    accepted = approve(client, batch["id"], good_body)
    assert accepted.status_code == 200, accepted.text
    saved = accepted.json()
    assert saved["approval_policy_version"] == 2
    assert saved["hold_review_hash"] == review["snapshot_hash"]
    assert {
        (item["channel_id"], item["field"], item["value"])
        for item in saved["held_statuses"]
    } == {(item["channel_id"], item["field"], item["value"]) for item in held}
    assert saved["spec"]["channels"]["source"]["status_actions"] == {
        "INCLUDE": "include",
        "EXCLUDE": "exclude",
    }
    store = client.app.state.store
    approval = next(
        item for item in store.list("approval") if item.get("flow_id") == saved["id"]
    )
    assert approval["approval_policy_version"] == 2
    assert approval["hold_review_hash"] == review["snapshot_hash"]
    assert {
        (item["channel_id"], item["field"], item["value"])
        for item in approval["held_statuses"]
    } == {(item["channel_id"], item["field"], item["value"]) for item in held}

    after_approval = counts(client)
    status = client.post(
        f"/api/batches/{batch['id']}/approval-status",
        json=good_body,
    )
    assert status.status_code == 200, status.text
    assert status.json()["flow"]["id"] == saved["id"]
    assert counts(client) == after_approval

    run = create_run(client, batch["id"], saved["id"])
    completed = execute(client, run["id"])
    assert completed["summary"] == {
        "input": 4,
        "included": 1,
        "excluded": 1,
        "duplicate": 0,
        "exception": 2,
        "totals_match": True,
    }
    rows = client.get(
        f"/api/runs/{run['id']}/rows",
        params={"limit": 200},
    ).json()["rows"]
    by_status = {row["raw"][STATUS_FIELD]: row["disposition"] for row in rows}
    assert by_status["INCLUDE"] == "included"
    assert by_status["EXCLUDE"] == "excluded"
    assert by_status["HELD"] == "exception"
    assert by_status[""] == "exception"


def test_no_holds_keeps_original_approval_shape(client: TestClient) -> None:
    content = csv_bytes(
        ORDER_HEADERS,
        [
            ["SYN-CLEAN-1", "1", "SKU-0001", "1", "piece", "INCLUDE"],
            ["SYN-CLEAN-2", "1", "SKU-0001", "1", "piece", "EXCLUDE"],
        ],
    )
    batch = create_batch(client, [("synthetic_clean.csv", content)], channel="source")
    flow = make_flow({"INCLUDE": "include", "EXCLUDE": "exclude"})
    report = preflight(client, batch["id"], flow)
    assert report["hold_review"]["required"] is False
    assert report["hold_review"]["groups"] == []

    accepted = approve(client, batch["id"], approval_body(flow, report["input_hash"]))
    assert accepted.status_code == 200, accepted.text
    saved = accepted.json()
    assert saved["approval_policy_version"] == 2
    assert saved["held_statuses"] == []

    run = create_run(client, batch["id"], saved["id"])
    completed = execute(client, run["id"])
    assert completed["summary"]["included"] == 1
    assert completed["summary"]["excluded"] == 1
    assert completed["summary"]["exception"] == 0


@pytest.mark.parametrize(
    ("action", "included", "excluded"),
    [("include", 2, 1), ("exclude", 1, 2)],
    ids=["explicit-include", "explicit-exclude"],
)
def test_explicit_status_action_replaces_hold_and_controls_disposition(
    client: TestClient, action: str, included: int, excluded: int
) -> None:
    batch, flow, _ = hold_batch(client)
    changed = copy.deepcopy(flow)
    changed["channels"]["source"]["status_actions"]["HELD"] = action
    report = preflight(client, batch["id"], changed)
    groups = report["hold_review"]["groups"]
    assert [(group["value"], group["count"]) for group in groups] == [("", 1)]

    accepted = approve(
        client,
        batch["id"],
        approval_body(
            changed,
            report["input_hash"],
            held=hold_entries(report),
            hold_review_hash=report["hold_review"]["snapshot_hash"],
        ),
    )
    assert accepted.status_code == 200, accepted.text
    saved = accepted.json()
    assert saved["spec"]["channels"]["source"]["status_actions"]["HELD"] == action
    run = create_run(client, batch["id"], saved["id"])
    completed = execute(client, run["id"])
    assert completed["summary"]["included"] == included
    assert completed["summary"]["excluded"] == excluded
    assert completed["summary"]["exception"] == 1
    rows = client.get(
        f"/api/runs/{run['id']}/rows",
        params={"limit": 200},
    ).json()["rows"]
    by_status = {row["raw"][STATUS_FIELD]: row["disposition"] for row in rows}
    assert by_status["HELD"] == ("included" if action == "include" else "excluded")
    assert by_status[""] == "exception"


def test_hold_groups_cover_multi_file_same_source_and_more_than_60_values(
    client: TestClient,
) -> None:
    statuses = [f"S{index:03d}" for index in range(1, 76)] + [""]
    first = statuses[:38]
    second = statuses[38:]
    first_rows = [
        [f"SYN-MULTI-A-{index:03d}", "1", "SKU-0001", "1", "piece", status]
        for index, status in enumerate(first, 1)
    ]
    second_rows = [
        [f"SYN-MULTI-B-{index:03d}", "1", "SKU-0001", "1", "piece", status]
        for index, status in enumerate(second, 1)
    ]
    batch = create_batch(
        client,
        [
            ("synthetic_multi_a.csv", csv_bytes(ORDER_HEADERS, first_rows)),
            ("synthetic_multi_b.csv", csv_bytes(ORDER_HEADERS, second_rows)),
        ],
        channel="source",
    )
    flow = make_flow({})
    report = preflight(client, batch["id"], flow)
    review = report["hold_review"]
    assert review["required"] is True
    assert report["row_count"] == 76
    actual = {
        (group["channel_id"], group["field"], group["value"], group["count"])
        for group in review["groups"]
    }
    expected = {
        ("source", STATUS_FIELD, status, 1)
        for status in statuses
    }
    assert actual == expected
    assert len(actual) == 76
    assert report["status_guard"]["rows_checked"] == 76
    assert review["snapshot_hash"]


def test_hold_hash_invalidated_by_batch_rule_and_source_changes(
    client: TestClient,
) -> None:
    batch, flow, report = hold_batch(client)
    review = report["hold_review"]
    held = hold_entries(report)

    copied = client.post(
        "/api/batches",
        json={"file_ids": batch["file_ids"], "label": "Synthetic copied batch"},
    )
    assert copied.status_code == 200, copied.text
    copied_batch = copied.json()
    copied_report = preflight(client, copied_batch["id"], flow)
    assert copied_report["hold_review"]["snapshot_hash"] != review["snapshot_hash"]

    wrong_batch = approve(
        client,
        copied_batch["id"],
        approval_body(
            flow,
            copied_report["input_hash"],
            held=hold_entries(copied_report),
            hold_review_hash=review["snapshot_hash"],
        ),
    )
    assert wrong_batch.status_code == 409, wrong_batch.text
    assert wrong_batch.json()["code"] == "STATUS_REVIEW_REQUIRED"

    changed_rules = copy.deepcopy(flow)
    changed_rules["name"] = "Synthetic changed rules"
    wrong_rules = approve(
        client,
        batch["id"],
        approval_body(
            changed_rules,
            report["input_hash"],
            held=held,
            hold_review_hash=review["snapshot_hash"],
        ),
    )
    assert wrong_rules.status_code == 409, wrong_rules.text
    assert wrong_rules.json()["code"] == "STATUS_REVIEW_REQUIRED"

    clean_batch = create_batch(
        client,
        [
            (
                "synthetic_source.csv",
                csv_bytes(
                    ORDER_HEADERS,
                    [["SYN-SOURCE-1", "1", "SKU-0001", "1", "piece", "INCLUDE"]],
                ),
            )
        ],
        channel="source",
        label="Synthetic source batch",
    )
    clean_flow = make_flow({"INCLUDE": "include"})
    clean_report = preflight(client, clean_batch["id"], clean_flow)
    source_a = approve(
        client,
        clean_batch["id"],
        approval_body(clean_flow, clean_report["input_hash"]),
    ).json()
    source_a_flow = copy.deepcopy(clean_flow)
    source_a_flow["name"] = "Synthetic source v2"
    source_a_report = preflight(client, clean_batch["id"], source_a_flow)
    source_b = approve(
        client,
        clean_batch["id"],
        approval_body(
            source_a_flow,
            source_a_report["input_hash"],
            source_flow_id=source_a["id"],
        ),
    ).json()

    report_a = preflight(
        client,
        batch["id"],
        flow,
        source_flow_id=source_a["id"],
    )
    report_b = preflight(
        client,
        batch["id"],
        flow,
        source_flow_id=source_b["id"],
    )
    assert report_a["hold_review"]["snapshot_hash"] != report_b["hold_review"]["snapshot_hash"]

    wrong_source = approve(
        client,
        batch["id"],
        approval_body(
            flow,
            report_a["input_hash"],
            held=hold_entries(report_a),
            hold_review_hash=report_a["hold_review"]["snapshot_hash"],
            source_flow_id=source_b["id"],
        ),
    )
    assert wrong_source.status_code == 409, wrong_source.text
    assert wrong_source.json()["code"] == "STATUS_REVIEW_REQUIRED"


def test_approval_status_does_not_reuse_legacy_approval_without_policy(
    client: TestClient,
) -> None:
    batch, flow, report = hold_batch(client)
    review = report["hold_review"]
    held = hold_entries(report)
    body = approval_body(
        flow,
        report["input_hash"],
        held=held,
        hold_review_hash=review["snapshot_hash"],
    )
    first = approve(client, batch["id"], body)
    assert first.status_code == 200, first.text
    old = first.json()
    make_legacy(client, old["id"])
    store = client.app.state.store

    status = client.post(f"/api/batches/{batch['id']}/approval-status", json=body)
    assert status.status_code == 200, status.text
    assert status.json()["flow"] is None

    again = approve(client, batch["id"], body)
    assert again.status_code == 200, again.text
    new = again.json()
    assert new["id"] != old["id"]
    assert new["approval_policy_version"] == 2
    assert store.get("flow", old["id"]).get("approval_policy_version") is None


def test_legacy_run_without_policy_can_still_recover(client: TestClient) -> None:
    batch, flow, report = hold_batch(client)
    review = report["hold_review"]
    saved = approve(
        client,
        batch["id"],
        approval_body(
            flow,
            report["input_hash"],
            held=hold_entries(report),
            hold_review_hash=review["snapshot_hash"],
        ),
    )
    assert saved.status_code == 200, saved.text
    flow_record = saved.json()
    store = client.app.state.store
    make_legacy(client, flow_record["id"])

    run = create_run(client, batch["id"], flow_record["id"])
    completed = execute(client, run["id"])
    assert completed["status"] == "completed"
    assert completed["summary"]["exception"] == 2
    assert completed["summary"]["included"] == 1
    assert completed["summary"]["excluded"] == 1
