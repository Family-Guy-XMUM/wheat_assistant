from __future__ import annotations

import hashlib
import json
import os
import threading
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
from maizi.files import MAX_BYTES, extract_products, parse_table, profile
from maizi.models import ApproveRequest, ExportApproval, FlowSpec, PlanRequest, REVIEW_GROUPS, RunRequest
from maizi.planner import configured, propose_live, suggest_flow
from maizi.samples import demo_files
from maizi.store import Store, digest, now

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)

class BatchRequest(BaseModel):
    file_ids: list[str] = Field(min_length=2, max_length=7)
    label: str = Field(default="Weekly orders", max_length=100)

class DemoRequest(BaseModel):
    week: int = Field(ge=1, le=3)

def create_app(data_dir=None, frontend_dir=None):
    directory = Path(data_dir or os.getenv("MAIZI_DATA_DIR") or user_data_dir("MaiZi", appauthor=False)).resolve()
    store = Store(directory)
    execution_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        for run in store.list("run"):
            if run.get("status") == "running":
                store.put("run", run["id"], {**run, "status": "interrupted", "error": "The app restarted. Retry this immutable run."})
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
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "The requested object was not found"}, status_code=404)

    def assets_for(batch):
        assets = [store.get("file", key) for key in batch["file_ids"]]
        for asset in assets:
            path = store.root / "files" / asset["storage_name"]
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != asset["hash"]:
                raise ValueError("An original input file changed. Upload it as a new input and confirm again.")
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
        checksum = hashlib.sha256(content).hexdigest()
        for existing in store.list("file"):
            if (existing["hash"], existing["role"], existing["channel_id"], existing.get("selected_sheet")) == (checksum, role, channel_id, sheet_name):
                store.activity("duplicate_upload", existing["id"], {"name": filename, "action": "existing asset reused"})
                return existing
        table = parse_table(content, filename, role, sheet_name)
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
        batch = store.add("batch", {"label": request.label, "file_ids": [x["id"] for x in files], "input_hash": batch_hash(files)})
        store.activity("batch_created", batch["id"], {"label": request.label})
        return batch

    def public_file(asset):
        return {key: asset[key] for key in ("id", "name", "role", "channel_id", "hash", "size", "profile")}

    def inspect(batch, spec):
        from maizi.status_guard import check_status_coverage
        assets = assets_for(batch)
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
        return {"input_hash": batch_hash(assets), "row_count": len(rows), "errors": errors, "status_guard": guard,
                "unresolved_products": unresolved_products, "unresolved_units": unresolved_units,
                "products": products, "module": "Status Guard / Replit Free"}

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__, "ai_configured": bool(configured()),
                "model": os.getenv("LLM_MODEL", "") if configured() else None, "mode": "local"}

    @app.get("/api/state")
    def state():
        return {
            "batches": [{k: x[k] for k in ["id", "label", "input_hash", "created_at"]} for x in store.list("batch")],
            "flows": store.list("flow"),
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
        base = request.flow.model_dump() if request.flow else suggest_flow(assets)
        if request.mode == "live":
            proposed = propose_live(store, batch, assets, request.instructions, base)
        else:
            proposed = {"flow": base, "origin": "suggested_setup",
                        "explanation": "Header-name suggestions only. Confirm business meaning, status actions, aliases and units before running.",
                        "questions": [], "model": None}
        draft = store.add("draft", {**proposed, "batch_id": identifier, "input_hash": batch_hash(assets)})
        store.activity("plan_proposed", draft["id"], {"origin": draft["origin"], "batch_id": identifier})
        return draft

    @app.post("/api/batches/{identifier}/preflight")
    def preflight(identifier: str, flow: FlowSpec):
        return inspect(store.get("batch", identifier), flow.model_dump())

    @app.post("/api/batches/{identifier}/approve")
    def approve(identifier: str, request: ApproveRequest):
        batch = store.get("batch", identifier)
        spec = request.flow.model_dump()
        report = inspect(batch, spec)
        if request.expected_input_hash != report["input_hash"]:
            raise ValueError("Inputs changed since review; inspect them again")
        if report["errors"]:
            raise ValueError("; ".join(report["errors"]))
        if not REVIEW_GROUPS.issubset(request.reviewed):
            raise ValueError("Review each concrete rule group before approving")
        saved = store.add("flow", {"spec": spec, "spec_hash": digest(spec), "batch_id": identifier, "input_hash": report["input_hash"],
                                   "reviewed": sorted(REVIEW_GROUPS), "actor": "Local demo operator"})
        store.add("approval", {"stage": "rules", "decision": "approved", "flow_id": saved["id"],
                              "snapshot": digest({"input": report["input_hash"], "flow": saved["spec_hash"]}),
                              "actor": "Local demo operator"})
        store.activity("rules_approved", saved["id"], {"batch_id": identifier, "name": spec["name"]})
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
        for previous in store.list("run"):
            if previous["snapshot"] == snapshot and previous["status"] == "completed":
                return {key: value for key, value in previous.items() if key != "result"}
        run = store.add("run", {"batch_id": batch["id"], "flow_id": saved["id"], "snapshot": snapshot,
                               "status": "ready", "export_approved": False})
        return run

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
            run = store.put("run", identifier, {**run, "status": "running", "started_at": now()})
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
                "sku_summary": run.get("result", {}).get("sku_summary", [])}

    @app.get("/api/runs/{identifier}/rows")
    def run_rows(identifier: str, disposition: str = "", query: str = "", offset: int = 0, limit: int = 100):
        run = store.get("run", identifier)
        rows = run.get("result", {}).get("rows", [])
        if disposition:
            rows = [x for x in rows if x["disposition"] == disposition]
        if query:
            rows = [x for x in rows if query.casefold() in json.dumps(x, ensure_ascii=False).casefold()]
        return {"total": len(rows), "rows": rows[max(0, offset):max(0, offset) + min(200, max(1, limit))]}

    @app.post("/api/runs/{identifier}/export-approval")
    def export_approval(identifier: str, request: ExportApproval):
        run = store.get("run", identifier)
        if run["status"] != "completed" or request.result_hash != run["result_hash"]:
            raise ValueError("Review the current completed result before export")
        if run["summary"]["exception"] and not request.acknowledge_exceptions:
            raise ValueError("Acknowledge the exception rows excluded from the preparation sheet")
        saved = store.get("flow", run["flow_id"])
        batch = store.get("batch", run["batch_id"])
        assets = assets_for(batch)
        if digest({"batch": batch_hash(assets), "flow": saved["spec_hash"]}) != run["snapshot"]:
            raise ValueError("Inputs changed after the approved run")
        template = next((x for x in assets if x["role"] == "template"), None)
        template_bytes = (store.root / "files" / template["storage_name"]).read_bytes() if template else None
        filename = identifier + ".xlsx"
        export_workbook(run["result"], saved["spec"], run["snapshot"], store.root / "artifacts" / filename, template_bytes)
        run = store.put("run", identifier, {**run, "export_approved": True, "artifact": filename})
        store.add("approval", {"stage": "export", "decision": "approved", "run_id": identifier, "snapshot": run["result_hash"],
                              "acknowledge_exceptions": request.acknowledge_exceptions, "actor": "Local demo operator"})
        store.activity("export_approved", identifier, {"exceptions": run["summary"]["exception"]})
        return {"download_url": "/api/runs/" + identifier + "/download"}

    @app.get("/api/runs/{identifier}/download")
    def download(identifier: str):
        run = store.get("run", identifier)
        if not run.get("export_approved"):
            raise HTTPException(403, "Approve the reviewed result before downloading")
        return FileResponse(store.root / "artifacts" / run["artifact"], filename="MaiZi_Picking_Preparation.xlsx")

    @app.post("/api/runs/{identifier}/handoff")
    def handoff(identifier: str):
        run = store.get("run", identifier)
        if not run.get("export_approved"):
            raise ValueError("Approve the output before creating a simulated warehouse task")
        for existing in store.list("handoff"):
            if existing["run_id"] == identifier:
                return existing
        task = store.add("handoff", {"run_id": identifier, "type": "warehouse_preparation",
                                    "simulation": True, "status": "ready_for_review", "snapshot": run["result_hash"]})
        store.activity("orbyte_simulated_handoff", task["id"], {"run_id": identifier, "simulation": True})
        return task

    @app.get("/api/activity")
    def activities():
        return store.list("activity")[:100]

    web = Path(frontend_dir) if frontend_dir else PROJECT_ROOT / "frontend" / "dist"
    if web.is_dir():
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    return app
