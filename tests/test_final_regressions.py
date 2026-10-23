"""Coordinator regressions for defects found in Harness's final read-only review."""
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def local(tmp_path,monkeypatch):
    import dotenv
    monkeypatch.setattr(dotenv,"load_dotenv",lambda *a,**k:False)
    for key in ("LLM_API_KEY","LLM_BASE_URL","LLM_MODEL"):
        monkeypatch.setenv(key,"")
    from wheat_assistant.api import create_app
    with TestClient(create_app(tmp_path),raise_server_exceptions=False) as client:
        yield client

def prepared(client):
    batch=client.post("/api/demo/load",json={"week":1}).json()
    flow=client.post(f"/api/batches/{batch['id']}/plan",json={"mode":"suggested"}).json()["flow"]
    flow["aliases"]={"Jasmine500":"TEA-001"};flow["unit_aliases"]={"carton":"box"}
    pre=client.post(f"/api/batches/{batch['id']}/preflight",json=flow).json()
    body={"flow":flow,"expected_input_hash":pre["input_hash"],"reviewed":["fields","statuses","products","units","duplicates","output"]}
    saved=client.post(f"/api/batches/{batch['id']}/approve",json=body).json()
    run=client.post("/api/runs",json={"batch_id":batch["id"],"flow_id":saved["id"]}).json()
    return batch,body,saved,run

def exported(client):
    batch,body,saved,run=prepared(client)
    done=client.post(f"/api/runs/{run['id']}/execute").json()
    request={"result_hash":done["result_hash"],"acknowledge_exceptions":True}
    response=client.post(f"/api/runs/{run['id']}/export-approval",json=request)
    assert response.status_code==200
    return batch,run,request,response.json()

def test_lost_approval_and_ready_run_responses_can_be_retried(local):
    batch,body,saved,run=prepared(local)
    again=local.post(f"/api/batches/{batch['id']}/approve",json=body).json()
    assert again["id"]==saved["id"]
    again_run=local.post("/api/runs",json={"batch_id":batch["id"],"flow_id":saved["id"]}).json()
    assert again_run["id"]==run["id"]
    assert len(local.app.state.store.list("approval"))==1

def test_legacy_sentinel_cannot_bypass_modern_artifact_hash(local):
    _,run,_,_=exported(local)
    store=local.app.state.store
    latest=store.get("run",run["id"])
    (store.root/"artifacts"/latest["artifact"]).write_bytes(b"tampered")
    assert local.get(f"/api/runs/{run['id']}/download").status_code==422
    assert local.get(f"/api/runs/{run['id']}/download?export_id=legacy").status_code==422

def test_missing_artifact_is_visible_and_cannot_be_handed_off(local):
    _,run,_,_=exported(local)
    store=local.app.state.store
    latest=store.get("run",run["id"])
    (store.root/"artifacts"/latest["artifact"]).unlink()
    assert local.get(f"/api/runs/{run['id']}/download").status_code==422
    assert local.post(f"/api/runs/{run['id']}/handoff").status_code==422
    assert store.list("handoff")==[]

def test_failed_new_export_keeps_default_old_download(local,monkeypatch):
    _,run,request,first=exported(local)
    url=f"/api/runs/{run['id']}/download"
    old=local.get(url).content
    from wheat_assistant import api
    monkeypatch.setattr(api.exporter_module,"EXPORTER_VERSION",3)
    def fail(*a,**k):raise ValueError("Synthetic new exporter failure")
    monkeypatch.setattr(api,"export_workbook",fail)
    assert local.post(f"/api/runs/{run['id']}/export-approval",json=request).status_code==422
    assert local.get(url).status_code==200
    assert local.get(url).content==old
    value=local.get(f"/api/runs/{run['id']}").json()
    assert value["export_state"]=="failed" and value["export_id"]==first["export_id"]

def test_current_run_activity_includes_handoff_but_no_later_duplicate_upload(local):
    _,run,_,_=exported(local)
    task=local.post(f"/api/runs/{run['id']}/handoff").json()
    assert local.post("/api/demo/load",json={"week":1}).status_code==200
    activities=local.get("/api/history/activity",params={"run_id":run["id"],"limit":200}).json()["rows"]
    assert any(x["subject"]==task["id"] and x["action"]=="orbyte_simulated_handoff" for x in activities)
    assert not any(x["action"]=="duplicate_upload" for x in activities)

def test_missing_revision_legacy_schema_is_migrated_after_verified_backup(tmp_path):
    from wheat_assistant.store import Store
    database=tmp_path/"wheat_assistant.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE entities (id VARCHAR PRIMARY KEY, kind VARCHAR, payload JSON, created VARCHAR)")
        connection.execute("INSERT INTO entities VALUES ('old','flow','{\"id\":\"old\",\"sentinel\":true}','2026-01-01')")
    store=Store(tmp_path)
    assert store.get("flow","old")["sentinel"] is True
    backup=next((tmp_path/"backups").glob("hardening-v2-*/wheat_assistant.sqlite"))
    with sqlite3.connect(backup) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert "revision" not in {x[1] for x in connection.execute("PRAGMA table_info(entities)")}

def test_input_diff_uses_source_structure_sets_and_reports_removed_source():
    from wheat_assistant.workflows import review_diff
    spec={"channels":{},"master_fields":{},"aliases":{},"unit_aliases":{},"output_columns":[]}
    def asset(name,source,headers):return {"role":"orders","name":name,"channel_id":source,"hash":name,"table":{"headers":headers}}
    before=[asset("a","same",["A","B"]),asset("b","same",["A","C"]),asset("gone","removed",["A"])]
    after=[asset("b2","same",["A","C"]),asset("a2","same",["A","B"])]
    diff=review_diff({"id":"old","spec":spec},spec,after,before)
    assert not any(x["kind"]=="structure" for x in diff["inputs"])
    assert any(x["kind"]=="removed_source" and "removed" in x["message"] for x in diff["inputs"])

def test_legacy_approval_status_and_retry_preserve_original_identity(local):
    batch,body,saved,_=prepared(local)
    store=local.app.state.store
    old={k:v for k,v in saved.items() if k not in {"approval_request_hash","workflow_id","rule_version","parent_flow_id","draft_id"}}
    store.put("flow",saved["id"],old)
    status=local.post(f"/api/batches/{batch['id']}/approval-status",json=body).json()
    assert status["flow"]["id"]==saved["id"]
    for _ in range(2):
        assert local.post(f"/api/batches/{batch['id']}/approve",json=body).json()["id"]==saved["id"]
    assert len(store.list("flow"))==1

def test_import_batch_idempotency_key_recovers_committed_batch(local):
    original=local.post("/api/demo/load",json={"week":1}).json()
    body={"label":"A deliberate import","file_ids":original["file_ids"],"idempotency_key":"synthetic-import-1"}
    first=local.post("/api/batches",json=body).json()
    second=local.post("/api/batches",json=body).json()
    assert first["id"]==second["id"]
    assert local.get("/api/batches/by-key/synthetic-import-1").json()["batch"]["id"]==first["id"]
    assert local.post("/api/batches",json={**body,"label":"Changed intent"}).status_code==422
    third=local.post("/api/batches",json={**body,"idempotency_key":"synthetic-import-2"}).json()
    assert third["id"]!=first["id"]
