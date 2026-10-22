from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from platformdirs import user_data_dir
from pydantic import BaseModel, Field

from maizi import __version__
from maizi.execution import execute_isolated
from maizi.exporter import export_workbook
from maizi import exporter as exporter_module
from maizi.files import MAX_BYTES, extract_products, parse_table, profile
from maizi.models import ApproveRequest, ExportApproval, FlowSpec, PlanRequest, REVIEW_GROUPS, RunRequest
from maizi.planner import configured, propose_live, suggest_flow
from maizi.samples import demo_files
from maizi.store import Store, digest, now
from maizi.workflows import metadata, review_diff, table_identity

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)

class BatchRequest(BaseModel):
    file_ids: list[str] = Field(min_length=2, max_length=7)
    label: str = Field(default="Weekly orders", max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=100)

class DemoRequest(BaseModel):
    week: int = Field(ge=1, le=3)

def create_app(data_dir=None, frontend_dir=None):
    directory = Path(data_dir or os.getenv("MAIZI_DATA_DIR") or user_data_dir("MaiZi", appauthor=False)).resolve()
    store = Store(directory)
    execution_lock = threading.Lock()
    export_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        for run in store.list("run"):
            if run.get("status") == "running":
                store.put("run", run["id"], {**run, "status": "interrupted", "error": "The app restarted. Retry this immutable run."})
            current = store.get("run", run["id"])
            if current.get("export_state") == "building":
                store.put("run", run["id"], {**current, "export_state": "interrupted", "export_error": "The app restarted during export. Retry export."})
        for export in store.list("export"):
            if export["status"] == "building":
                store.put("export", export["id"], {**export, "status": "interrupted", "error": "Export interrupted by restart"})
        yield

    app = FastAPI(title="MaiZi Assistant", version=__version__, lifespan=lifespan)
    app.state.store = store

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        if host not in {"127.0.0.1", "localhost", "[", "testserver"}:
            return JSONResponse({"detail": "This build accepts local requests only"}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin not in {"http://127.0.0.1:" + request.url.port.__str__(), "http://localhost:" + request.url.port.__str__()}:
                return JSONResponse({"detail": "Cross-origin writes are not allowed"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc), "code": getattr(exc, "code", "INVALID_INPUT"),
                             "line_number": getattr(exc, "line_number", None)}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "The requested object was not found"}, status_code=404)

    def assets_for(batch, validate_parser=False):
        assets = [store.get("file", key) for key in batch["file_ids"]]
        for asset in assets:
            path = store.root / "files" / asset["storage_name"]
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != asset["hash"]:
                raise ValueError("An original input file changed. Upload it as a new input and confirm again.")
            if validate_parser and asset["table"].get("parser_version", 1) < 2:
                try:
                    checked = parse_table(path.read_bytes(), asset["name"], asset["role"], asset.get("selected_sheet"))
                except ValueError as exc:
                    raise ValueError("Legacy input needs a new upload and approval: " + asset["name"] + ". " + str(exc)) from exc
                if digest(table_identity(checked)) != digest(table_identity(asset["table"])):
                    raise ValueError("Legacy input parsing changed. Upload a new batch and approve again: " + asset["name"])
        return assets

    def batch_hash(assets):
        return digest([{"id": x["id"], "hash": x["hash"], "role": x["role"], "channel": x["channel_id"]} for x in assets])

    def all_rows(assets):
        rows = []
        for asset in assets:
            if asset["role"] != "orders":
                continue
            for record in asset["table"]["records"]:
                rows.append({**record, "source_id": asset["channel_id"], "source_name": asset["name"],
                             "sheet": asset["table"]["sheet"],
                             "source_row_id": asset["id"] + ":" + asset["table"]["sheet"] + ":" + str(record["row_number"])})
        return rows

    def register_file(content, name, role, channel_id, sheet_name=None):
        if role not in {"orders", "master", "template"}:
            raise ValueError("Choose orders, master or template")
        if role == "orders" and not channel_id.strip():
            raise ValueError("An order file needs a channel identifier")
        filename = Path(name).name
        channel_id = channel_id.strip()
        checksum = hashlib.sha256(content).hexdigest()
        table = parse_table(content, filename, role, sheet_name)
        for existing in store.list("file"):
            if (existing["hash"], existing["role"], existing["channel_id"], existing.get("selected_sheet"), existing["table"].get("parser_version", 1)) == (checksum, role, channel_id, sheet_name, table.get("parser_version", 1)):
                store.activity("duplicate_upload", existing["id"], {"name": filename, "action": "existing asset reused"})
                return existing
        storage_name = checksum + Path(filename).suffix.lower()
        destination = store.root / "files" / storage_name
        if not destination.exists():
            destination.write_bytes(content)
            destination.chmod(0o400)
        asset = store.add("file", {"name": filename, "role": role, "channel_id": channel_id.strip(), "hash": checksum,
                                   "storage_name": storage_name, "selected_sheet": sheet_name,
                                   "size": len(content), "table": table, "profile": profile(table)})
        store.activity("file_uploaded", asset["id"], {"name": filename, "role": role, "rows": len(table["records"])})
        return asset

    def register_batch(request):
        files = [store.get("file", key) for key in dict.fromkeys(request.file_ids)]
        orders = [x for x in files if x["role"] == "orders"]
        if not 1 <= len(orders) <= 5:
            raise ValueError("A batch requires one to five order files")
        if sum(len(x["table"]["records"]) for x in orders) > 10000:
            raise ValueError("The batch exceeds 10,000 order lines")
        if len([x for x in files if x["role"] == "master"]) != 1:
            raise ValueError("Choose exactly one product master")
        if len([x for x in files if x["role"] == "template"]) > 1:
            raise ValueError("Choose at most one warehouse template")
        with store.lock:
            fingerprint = digest({"label": request.label, "files": sorted(x["id"] for x in files)})
            if request.idempotency_key:
                previous = next((x for x in store.list("batch") if x.get("idempotency_key") == request.idempotency_key), None)
                if previous:
                    if previous.get("request_hash") != fingerprint:
                        raise ValueError("Import inputs changed for this request. Start a new import attempt.")
                    return previous
            batch = store.add("batch", {"label": request.label, "file_ids": [x["id"] for x in files], "input_hash": batch_hash(files),
                                        "idempotency_key": request.idempotency_key, "request_hash": fingerprint})
            store.activity("batch_created", batch["id"], {"label": request.label})
        return batch

    def public_file(asset):
        return {key: asset[key] for key in ("id", "name", "role", "channel_id", "hash", "size", "profile")}

    def inspect(batch, spec, source_flow_id=None):
        from maizi.status_guard import check_status_coverage
        assets = assets_for(batch, validate_parser=True)
        rows = all_rows(assets)
        errors = []
        for asset in assets:
            if asset["role"] == "orders":
                channel = spec["channels"].get(asset["channel_id"])
                if not channel:
                    errors.append("Missing channel rule: " + asset["channel_id"])
                    continue
                missing_fields = [name for name in channel["fields"].values() if name and name not in asset["table"]["headers"]]
                if missing_fields:
                    errors.append(asset["name"] + ": missing mapped columns " + ", ".join(missing_fields))
                if any(not channel["fields"].get(field) for field in ["order_id", "product", "quantity", "unit", "status"]):
                    errors.append(asset["name"] + ": required field mappings are incomplete")
                if (spec.get("date_from") or spec.get("date_to")) and not channel["fields"].get("date"):
                    errors.append(asset["name"] + ": date filtering requires a date field")
        products = []
        try:
            master = next(x for x in assets if x["role"] == "master")
            products = extract_products(master["table"], spec["master_fields"])
        except ValueError as exc:
            errors.append(str(exc))
        sku_set = {x["sku"] for x in products}
        for alias, sku in spec.get("aliases", {}).items():
            if not alias.strip() or sku not in sku_set:
                errors.append("Every confirmed alias must reference an existing master SKU")
        template = next((x for x in assets if x["role"] == "template"), None)
        if template and [x["header"] for x in spec["output_columns"]] != template["table"]["headers"]:
            errors.append("Confirm an output mapping for every warehouse template header, in order")
        guard = check_status_coverage(spec["channels"], rows)
        observed_statuses = {}
        for channel_id, rule in spec["channels"].items():
            observed_statuses[channel_id] = dict(Counter(str(row["data"].get(rule["fields"]["status"], "") or "").strip()
                                                       for row in rows if row["source_id"] == channel_id))
        if any(not value.strip() for rule in spec["channels"].values() for value in rule["status_actions"]):
            errors.append("Missing statuses must remain held; provide a corrected input rather than including blank statuses")
        unresolved_products, unresolved_units = {}, {}
        master_map = {x["sku"]: x for x in products}
        for row in rows:
            rule = spec["channels"].get(row["source_id"])
            if not rule:
                continue
            fields = rule["fields"]
            status = str(row["data"].get(fields["status"], "") or "").strip()
            if rule["status_actions"].get(status) != "include":
                continue
            raw_product = str(row["data"].get(fields["product"], "") or "").strip()
            sku = raw_product if raw_product in master_map else spec.get("aliases", {}).get(raw_product)
            if sku not in master_map:
                unresolved_products[raw_product] = unresolved_products.get(raw_product, 0) + 1
                continue
            raw_unit = str(row["data"].get(fields["unit"], "") or "").strip()
            unit = spec.get("unit_aliases", {}).get(raw_unit, raw_unit)
            if unit not in master_map[sku]["unit_factors"]:
                key = raw_unit + " / " + sku
                unresolved_units[key] = unresolved_units.get(key, 0) + 1
        source = store.get("flow", source_flow_id) if source_flow_id else None
        old_assets = [store.get("file", key) for key in store.get("batch", source["batch_id"])["file_ids"]] if source else []
        return {"input_hash": batch_hash(assets), "row_count": len(rows), "errors": list(dict.fromkeys(errors)), "status_guard": guard,
                "unresolved_products": unresolved_products, "unresolved_units": unresolved_units,
                "observed_statuses": observed_statuses,
                "available_units": sorted({unit for item in products for unit in item["unit_factors"]}),
                "diff": review_diff(source, spec, assets, old_assets),
                "products": products, "module": "Status Guard / Replit Free"}

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__, "ai_configured": bool(configured()),
                "model": os.getenv("LLM_MODEL", "") if configured() else None, "mode": "local"}

    @app.get("/api/state")
    def state():
        return {
            "batches": [{k: x[k] for k in ["id", "label", "input_hash", "created_at"]} for x in store.list("batch")],
            "flows": [metadata(x) for x in store.list("flow")],
            "runs": [{k: x.get(k) for k in ["id", "batch_id", "flow_id", "status", "summary", "created_at", "export_approved", "error"]} for x in store.list("run")],
            "activity": store.list("activity")[:80],
        }

    @app.post("/api/files")
    async def upload(file: UploadFile = File(...), role: str = Form(...), channel_id: str = Form(""), sheet_name: str = Form("")):
        content = await file.read(MAX_BYTES + 1)
        asset = register_file(content, file.filename or "input.csv", role, channel_id, sheet_name or None)
        return public_file(asset)

    @app.get("/api/files/{identifier}/download")
    def download_original(identifier: str):
        asset = store.get("file", identifier)
        return FileResponse(store.root / "files" / asset["storage_name"], filename=asset["name"])

    @app.post("/api/batches")
    def create_batch(request: BatchRequest):
        return register_batch(request)

    @app.get("/api/batches/by-key/{idempotency_key}")
    def batch_status(idempotency_key: str):
        return {"batch": next((x for x in store.list("batch") if x.get("idempotency_key") == idempotency_key), None)}

    @app.get("/api/batches/{identifier}")
    def get_batch(identifier: str):
        batch = store.get("batch", identifier)
        assets = assets_for(batch)
        return {**batch, "files": [public_file(x) for x in assets], "input_hash": batch_hash(assets)}

    @app.post("/api/demo/load")
    def load_demo(request: DemoRequest):
        files = [register_file(x["content"], x["name"], x["role"], x["channel_id"]) for x in demo_files(request.week)]
        batch = register_batch(BatchRequest(file_ids=[x["id"] for x in files], label="Synthetic week " + str(request.week)))
        return {**batch, "files": [public_file(x) for x in files]}

    @app.post("/api/batches/{identifier}/plan")
    def plan(identifier: str, request: PlanRequest):
        batch = store.get("batch", identifier)
        assets = assets_for(batch)
        source = store.get("flow", request.source_flow_id) if request.source_flow_id else None
        base = request.flow.model_dump() if request.flow else source["spec"] if source else suggest_flow(assets)
        if request.mode == "live":
            proposed = propose_live(store, batch, assets, request.instructions, base)
        else:
            proposed = {"flow": base, "origin": "suggested_setup",
                        "explanation": "Header-name suggestions only. Confirm business meaning, status actions, aliases and units before running.",
                        "questions": [], "model": None}
        draft = store.add("draft", {**proposed, "batch_id": identifier, "input_hash": batch_hash(assets),
                                    "source_flow_id": request.source_flow_id})
        store.activity("plan_proposed", draft["id"], {"origin": draft["origin"], "batch_id": identifier})
        return draft

    @app.post("/api/batches/{identifier}/preflight")
    def preflight(identifier: str, flow: FlowSpec, source_flow_id: str | None = None):
        return inspect(store.get("batch", identifier), flow.model_dump(), source_flow_id)

    def existing_approval(identifier, request):
        spec = request.flow.model_dump()
        request_hash = digest({"batch": identifier, "input": request.expected_input_hash, "spec": spec,
                               "source_flow_id": request.source_flow_id})
        source = metadata(store.get("flow", request.source_flow_id)) if request.source_flow_id else None
        if source and source["batch_id"] == identifier and source["input_hash"] == request.expected_input_hash and source["spec_hash"] == digest(spec):
            return source
        return next((metadata(x) for x in store.list("flow") if x.get("approval_request_hash") == request_hash or
                    (not x.get("approval_request_hash") and x["batch_id"] == identifier and
                     x["input_hash"] == request.expected_input_hash and x["spec_hash"] == digest(spec) and
                     x.get("parent_flow_id") == request.source_flow_id)), None)

    @app.post("/api/batches/{identifier}/approval-status")
    def approval_status(identifier: str, request: ApproveRequest):
        store.get("batch", identifier)
        return {"flow": existing_approval(identifier, request)}

    @app.post("/api/batches/{identifier}/approve")
    def approve(identifier: str, request: ApproveRequest):
        batch = store.get("batch", identifier)
        spec = request.flow.model_dump()
        report = inspect(batch, spec, request.source_flow_id)
        if request.expected_input_hash != report["input_hash"]:
            raise ValueError("Inputs changed since review; inspect them again")
        if report["errors"]:
            raise ValueError("; ".join(report["errors"]))
        if not REVIEW_GROUPS.issubset(request.reviewed):
            raise ValueError("Review each concrete rule group before approving")
        if request.draft_id and store.get("draft", request.draft_id)["batch_id"] != identifier:
            raise ValueError("The selected draft belongs to another batch")
        with store.lock:
            previous = existing_approval(identifier, request)
            if previous:
                return previous
            request_hash = digest({"batch": identifier, "input": report["input_hash"], "spec": spec,
                                   "source_flow_id": request.source_flow_id})
            source = metadata(store.get("flow", request.source_flow_id)) if request.source_flow_id else None
            identifier_flow = uuid.uuid4().hex
            workflow_id = source["workflow_id"] if source else identifier_flow
            same = source and source["spec_hash"] == digest(spec)
            version = source["rule_version"] if same else 1 + max(
                [metadata(x)["rule_version"] for x in store.list("flow") if metadata(x)["workflow_id"] == workflow_id], default=0)
            saved = {"id": identifier_flow, "spec": spec, "spec_hash": digest(spec), "batch_id": identifier,
                     "input_hash": report["input_hash"], "reviewed": sorted(REVIEW_GROUPS), "actor": "Local demo operator",
                     "workflow_id": workflow_id, "rule_version": version, "parent_flow_id": request.source_flow_id,
                     "approval_request_hash": request_hash, "draft_id": request.draft_id}
            saved = store.commit_bundle(additions=[("flow", saved), ("approval", {
                "stage": "rules", "decision": "approved", "flow_id": identifier_flow,
                "snapshot": digest({"input": report["input_hash"], "flow": saved["spec_hash"]}), "actor": "Local demo operator"}),
                ("activity", {"action": "rules_approved", "subject": identifier_flow,
                              "detail": {"batch_id": identifier, "name": spec["name"], "rule_version": version}})])[0]
        return saved

    @app.post("/api/runs")
    def create_run(request: RunRequest):
        batch = store.get("batch", request.batch_id)
        saved = store.get("flow", request.flow_id)
        assets = assets_for(batch)
        if saved["input_hash"] != batch_hash(assets) or saved["batch_id"] != batch["id"]:
            raise ValueError("Confirm this flow against the current batch before running")
        snapshot = digest({"batch": batch_hash(assets), "flow": saved["spec_hash"]})
        if request.expected_snapshot and request.expected_snapshot != snapshot:
            raise ValueError("The run snapshot changed")
        with store.lock:
            for previous in store.list("run"):
                if previous["snapshot"] == snapshot and previous["batch_id"] == batch["id"] and previous["flow_id"] == saved["id"]:
                    return {key: value for key, value in previous.items() if key != "result"}
            run = store.add("run", {"batch_id": batch["id"], "flow_id": saved["id"], "snapshot": snapshot,
                                   "status": "ready", "export_approved": False})
        return run

    @app.get("/api/flows/{identifier}")
    def get_flow(identifier: str):
        return metadata(store.get("flow", identifier))

    @app.post("/api/runs/{identifier}/execute")
    def execute(identifier: str):
        if not execution_lock.acquire(blocking=False):
            raise HTTPException(409, "Another local processing step is running")
        try:
            run = store.get("run", identifier)
            if run["status"] == "completed":
                return {key: value for key, value in run.items() if key != "result"}
            if run["status"] not in {"ready", "failed", "interrupted"}:
                raise ValueError("This run is not ready")
            batch = store.get("batch", run["batch_id"])
            saved = store.get("flow", run["flow_id"])
            assets = assets_for(batch)
            if digest({"batch": batch_hash(assets), "flow": saved["spec_hash"]}) != run["snapshot"]:
                raise ValueError("Inputs changed after approval")
            report = inspect(batch, saved["spec"])
            if report["errors"]:
                raise ValueError("; ".join(report["errors"]))
            run = store.put("run", identifier, {**run, "status": "running", "error": None, "started_at": now()})
            try:
                result = execute_isolated(all_rows(assets), report["products"], saved["spec"])
                result_hash = digest({"snapshot": run["snapshot"], "result": result})
                run = store.put("run", identifier, {**run, "status": "completed", "result": result,
                                                   "summary": result["summary"], "result_hash": result_hash, "finished_at": now()})
                store.activity("run_completed", identifier, result["summary"])
                return {key: value for key, value in run.items() if key != "result"}
            except Exception as exc:
                store.put("run", identifier, {**run, "status": "failed", "error": str(exc)})
                raise HTTPException(422, str(exc))
        finally:
            execution_lock.release()

    @app.get("/api/runs/{identifier}")
    def get_run(identifier: str):
        run = store.get("run", identifier)
        return {**{key: value for key, value in run.items() if key != "result"},
                "export_state": run.get("export_state", "ready" if run.get("export_approved") else "not_started"),
                "sku_summary": run.get("result", {}).get("sku_summary", [])}

    @app.get("/api/runs/{identifier}/rows")
    def run_rows(identifier: str, disposition: str = "", query: str = "", offset: int = 0, limit: int = 100,
                 reason_code: str = "", source_row_id: str = ""):
        run = store.get("run", identifier)
        rows = run.get("result", {}).get("rows", [])
        if disposition:
            rows = [x for x in rows if x["disposition"] == disposition]
        if query:
            rows = [x for x in rows if query.casefold() in json.dumps(x, ensure_ascii=False).casefold()]
        if reason_code:
            rows = [x for x in rows if any(reason["code"] == reason_code for reason in x["reasons"])]
        if source_row_id:
            rows = [x for x in rows if x["source_row_id"] == source_row_id]
        return page(rows, offset, limit)

    def page(rows, offset=0, limit=20):
        offset, limit = max(0, offset), min(200, max(1, limit))
        return {"total": len(rows), "rows": rows[offset:offset + limit], "offset": offset, "limit": limit}

    @app.get("/api/runs/{identifier}/sku-summary")
    def sku_summary(identifier: str, query: str = "", offset: int = 0, limit: int = 50):
        rows = store.get("run", identifier).get("result", {}).get("sku_summary", [])
        if query:
            rows = [x for x in rows if query.casefold() in json.dumps(x, ensure_ascii=False).casefold()]
        return page(sorted(rows, key=lambda x: x["sku"]), offset, limit)

    @app.get("/api/runs/{identifier}/exception-groups")
    def exception_groups(identifier: str):
        rows = store.get("run", identifier).get("result", {}).get("rows", [])
        return dict(Counter(reason["code"] for row in rows if row["disposition"] == "exception" for reason in row["reasons"]))

    def retain_legacy_export(run):
        if not run.get("export_approved") or not run.get("artifact"):
            return
        records = [x for x in store.list("export") if x["run_id"] == run["id"]]
        if any(x.get("artifact") == run["artifact"] for x in records):
            return
        path = store.root / "artifacts" / run["artifact"]
        if not path.is_file():
            raise ValueError("The exported file is missing. Retry export to create a verified workbook.")
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if run.get("artifact_hash") and run["artifact_hash"] != checksum:
            raise ValueError("The exported file changed. Generate a new approved export.")
        store.add("export", {"run_id": run["id"], "result_hash": run["result_hash"], "version": 1,
                             "status": "ready", "legacy": True, "artifact": run["artifact"], "artifact_hash": checksum})

    def approved_artifact(run, explicit_id=None):
        if not run.get("export_approved"):
            raise HTTPException(403, "Approve the reviewed result before downloading")
        retain_legacy_export(run)
        records = [x for x in store.list("export") if x["run_id"] == run["id"]]
        if explicit_id == "legacy":
            record = next((x for x in records if x.get("legacy") and x["status"] == "ready"), None)
            if record is None:
                raise ValueError("No verified historical export exists for this run")
        elif explicit_id:
            record = store.get("export", explicit_id)
        else:
            record = next((x for x in records if x["id"] == run.get("export_id") and x["status"] == "ready"), None)
            record = record or next((x for x in records if x["status"] == "ready"), None)
        if not record or record["run_id"] != run["id"] or record["status"] != "ready":
            raise HTTPException(403, "This export is not ready for download")
        path = store.root / "artifacts" / record["artifact"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record["artifact_hash"]:
            raise ValueError("The exported file changed or is missing. Generate a new approved export.")
        return path, record

    @app.post("/api/runs/{identifier}/export-approval")
    def export_approval(identifier: str, request: ExportApproval):
        run = store.get("run", identifier)
        if run["status"] != "completed" or request.result_hash != run["result_hash"]:
            raise ValueError("Review the current completed result before export")
        if run["summary"]["exception"] and not request.acknowledge_exceptions:
            raise ValueError("Acknowledge the exception rows excluded from the preparation sheet")
        if not export_lock.acquire(blocking=False):
            raise HTTPException(409, "Another workbook is being generated. Refresh its status.")
        export = None
        try:
            saved = store.get("flow", run["flow_id"])
            assets = assets_for(store.get("batch", run["batch_id"]))
            if digest({"batch": batch_hash(assets), "flow": saved["spec_hash"]}) != run["snapshot"]:
                raise ValueError("Inputs changed after the approved run")
            version = getattr(exporter_module, "EXPORTER_VERSION", 2)
            if run.get("export_approved") and not run.get("export_id"):
                # Older versions did not store artifact checksums. Register their
                # first v2 observation once; every later download checks it.
                try:
                    retain_legacy_export(run)
                except ValueError:
                    # An absent historical artifact must not prevent a fresh
                    # approved export from the still-valid immutable result.
                    pass
            for old in store.list("export"):
                if (old["run_id"], old["result_hash"], old["version"], old["status"]) == (identifier, run["result_hash"], version, "ready"):
                    artifact = store.root / "artifacts" / old["artifact"]
                    if artifact.is_file() and hashlib.sha256(artifact.read_bytes()).hexdigest() == old["artifact_hash"]:
                        store.put("run", identifier, {**store.get("run", identifier), "export_id": old["id"],
                                  "artifact": old["artifact"], "artifact_hash": old["artifact_hash"], "export_approved": True,
                                  "export_state": "ready", "export_stage": "ready", "export_error": None, "pending_export_id": None})
                        return {"export_id": old["id"], "download_url": f"/api/runs/{identifier}/download"}
            template = next((x for x in assets if x["role"] == "template"), None)
            content = (store.root / "files" / template["storage_name"]).read_bytes() if template else None
            export = store.add("export", {"run_id": identifier, "result_hash": run["result_hash"], "version": version,
                                          "status": "building", "stage": "validating"})
            def stage(value):
                latest = store.get("run", identifier)
                store.put("run", identifier, {**latest, "export_state": "building", "export_stage": value,
                                              "export_error": None, "pending_export_id": export["id"]})
                current = store.get("export", export["id"])
                store.put("export", export["id"], {**current, "stage": value})
            stage("validating")
            filename = export["id"] + ".xlsx"
            target = store.root / "artifacts" / filename
            export_workbook(run["result"], saved["spec"], run["snapshot"], target, content,
                            template_sheet_name=template["table"]["sheet"] if template else None, on_stage=stage)
            ready = {**store.get("export", export["id"]), "status": "ready", "artifact": filename,
                     "artifact_hash": hashlib.sha256(target.read_bytes()).hexdigest(), "finished_at": now()}
            updated = {**store.get("run", identifier), "export_approved": True, "artifact": filename,
                       "artifact_hash": ready["artifact_hash"], "export_id": export["id"], "pending_export_id": None,
                       "export_state": "ready", "export_stage": "ready", "export_error": None}
            store.commit_bundle(updates=[("export", export["id"], ready), ("run", identifier, updated)], additions=[
                ("approval", {"stage": "export", "decision": "approved", "run_id": identifier, "snapshot": run["result_hash"],
                              "export_id": export["id"], "acknowledge_exceptions": request.acknowledge_exceptions, "actor": "Local demo operator"}),
                ("activity", {"action": "export_approved", "subject": identifier,
                              "detail": {"exceptions": run["summary"]["exception"], "export_id": export["id"]}})])
            return {"export_id": export["id"], "download_url": f"/api/runs/{identifier}/download"}
        except Exception as exc:
            if export:
                message = str(exc) if isinstance(exc, ValueError) else "Workbook generation failed. Retry or review the template."
                store.put("export", export["id"], {**store.get("export", export["id"]), "status": "failed", "error": message})
                store.put("run", identifier, {**store.get("run", identifier), "export_state": "failed", "export_error": message,
                                              "pending_export_id": None})
                store.activity("export_failed", identifier, {"export_id": export["id"], "error": message})
                raise ValueError(message) from exc
            raise
        finally:
            export_lock.release()

    @app.get("/api/runs/{identifier}/exports")
    def exports(identifier: str):
        run = store.get("run", identifier)
        if run.get("export_approved") and not run.get("export_id"):
            try:
                retain_legacy_export(run)
            except ValueError:
                return [{"id": "legacy", "status": "failed", "version": 1, "legacy": True,
                         "error": "Historical export missing or changed. Retry export."}]
        rows = [x for x in store.list("export") if x["run_id"] == identifier]
        return rows

    @app.get("/api/runs/{identifier}/download")
    def download(identifier: str, export_id: str | None = None):
        run = store.get("run", identifier)
        path, _ = approved_artifact(run, export_id)
        return FileResponse(path, filename="MaiZi_Picking_Preparation.xlsx")

    @app.post("/api/runs/{identifier}/handoff")
    def handoff(identifier: str):
        run = store.get("run", identifier)
        if not run.get("export_approved"):
            raise ValueError("Approve the output before creating a simulated warehouse task")
        _, artifact = approved_artifact(run)
        for existing in store.list("handoff"):
            if existing["run_id"] == identifier:
                return existing
        task = store.add("handoff", {"run_id": identifier, "type": "warehouse_preparation",
                                    "simulation": True, "status": "ready_for_review", "snapshot": run["result_hash"],
                                    "export_id": artifact["id"], "artifact_hash": artifact["artifact_hash"]})
        store.activity("orbyte_simulated_handoff", task["id"], {"run_id": identifier, "simulation": True})
        return task

    @app.get("/api/activity")
    def activities():
        return store.list("activity")[:100]

    @app.get("/api/history/{kind}")
    def history(kind: str, offset: int = 0, limit: int = 20, query: str = "", run_id: str = "", workflow_id: str = "", flow_id: str = ""):
        entity_kind = {"batches": "batch", "flows": "flow", "runs": "run", "activity": "activity"}.get(kind)
        if not entity_kind:
            raise HTTPException(404, "Unknown history category")
        rows = store.list(entity_kind)
        if kind == "flows":
            rows = [metadata(x) for x in rows]
            if workflow_id:
                rows = [x for x in rows if x["workflow_id"] == workflow_id]
        if kind == "runs":
            if flow_id:
                rows = [x for x in rows if x["flow_id"] == flow_id]
            rows = [{key: value for key, value in x.items() if key != "result"} for x in rows]
        if kind == "batches":
            rows = [{key: value for key, value in x.items() if key != "file_ids"} for x in rows]
        if kind == "activity" and run_id:
            selected = store.get("run", run_id)
            batch = store.get("batch", selected["batch_id"])
            approved = store.get("flow", selected["flow_id"])
            related = {run_id, batch["id"], selected["flow_id"]}
            related.update(x["id"] for x in store.list("handoff") if x["run_id"] == run_id)
            if approved.get("draft_id"):
                related.add(approved["draft_id"])
            else:
                related.update(x["id"] for x in store.list("draft") if x["batch_id"] == batch["id"] and
                               x["created_at"] <= approved["created_at"] and digest(x["flow"]) == approved["spec_hash"])
            rows = [x for x in rows if x["subject"] in related or
                    (x["action"] == "file_uploaded" and x["subject"] in batch["file_ids"] and x["created_at"] <= batch["created_at"])]
        if query:
            rows = [x for x in rows if query.casefold() in json.dumps(x, ensure_ascii=False).casefold()]
        rows.sort(key=lambda x: (x["created_at"], x["id"]), reverse=True)
        return page(rows, offset, limit)

    web = Path(frontend_dir) if frontend_dir else PROJECT_ROOT / "frontend" / "dist"
    if web.is_dir():
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    return app
