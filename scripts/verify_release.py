"""Actual source/native HTTP journeys, owned process shutdown and restart evidence."""
import argparse
import errno
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import httpx
from openpyxl import load_workbook
from maizi.process_control import ManagedProcess
from maizi.local_network import bind_loopback
from maizi.release_evidence import attempt_id, candidate_info, report_path, write_report
from maizi.runtime_environment import child_environment

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def await_health(managed, client, version, previous_ids=()):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        managed.family()
        if managed.process.poll() is not None:
            raise RuntimeError("App exited before its health check")
        try:
            response = client.get("/api/health", timeout=1)
            if response.status_code == 200:
                health = response.json()
                require(health["version"] == version, "Health belongs to another candidate version")
                require(health.get("instance_id") and health["instance_id"] not in previous_ids,
                        "Health belongs to an earlier app instance")
                require(health["ai_configured"] is False, "No-key verification unexpectedly configured AI")
                return health["instance_id"]
        except httpx.HTTPError:
            pass
        time.sleep(.1)
    raise RuntimeError("App startup deadline exceeded")


def released_port(port, timeout=10):
    deadline = time.monotonic() + timeout
    last_code = None
    last_bind_error = None
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            probe.settimeout(.25)
            last_code = probe.connect_ex(("127.0.0.1", port))
        if last_code in {errno.EACCES, errno.EPERM, 10013}:
            raise RuntimeError("Port release check was denied by the operating system")
        if last_code in {errno.ECONNREFUSED, 61, 111, 10061}:
            try:
                with socket.socket() as probe:
                    bind_loopback(probe, port)
                return {"released": True, "connection_error": last_code, "bind_succeeded": True}
            except OSError as exc:
                last_bind_error = exc.errno
                if exc.errno not in {errno.EADDRINUSE, 10048}:
                    raise
        time.sleep(.05)
    error = RuntimeError("Port did not become refused and bindable before the deadline")
    error.port_diagnostics = {"last_connection_error": last_code, "last_bind_error": last_bind_error}
    raise error


def journey(client):
    def post(path, data=None, expected=200):
        response = client.post(path, json=data) if data is not None else client.post(path)
        require(response.status_code == expected, "Verification request failed: " + path.split("?")[0])
        return response.json()
    source = None
    runs = []
    for week, expected in [(1, (36,24,3,3,6)), (2, (39,24,6,3,6)), (3, (24,24,0,0,0))]:
        batch = post("/api/demo/load", {"week": week})
        draft = post("/api/batches/" + batch["id"] + "/plan", {"mode": "suggested", "source_flow_id": source})
        spec = draft["flow"]
        spec["aliases"]["Jasmine500"] = "TEA-001"
        spec["unit_aliases"]["carton"] = "box"
        if week == 2:
            pre = post("/api/batches/" + batch["id"] + "/preflight", spec)
            require(len(pre["status_guard"]["affected_row_ids"]) == 3, "New status rows were not detected")
            blocked = post("/api/batches/" + batch["id"] + "/approve", {"flow": spec, "source_flow_id": source,
                "expected_input_hash": pre["input_hash"], "reviewed": ["fields","statuses","products","units","duplicates","output"]}, expected=409)
            require(blocked["code"] == "STATUS_REVIEW_REQUIRED", "Implicit Hold was not blocked")
            spec["channels"]["channel-b"]["status_actions"]["Partially shipped"] = "exclude"
        pre = post("/api/batches/" + batch["id"] + "/preflight", spec)
        saved = post("/api/batches/" + batch["id"] + "/approve", {"flow": spec, "source_flow_id": source,
            "expected_input_hash": pre["input_hash"], "reviewed": ["fields","statuses","products","units","duplicates","output"]})
        source = saved["id"]
        run = post("/api/runs", {"batch_id": batch["id"], "flow_id": source})
        done = post("/api/runs/" + run["id"] + "/execute")
        require(tuple(done["summary"][key] for key in ["input","included","excluded","duplicate","exception"]) == expected,
                "Three-week disposition counts changed")
        approved = post("/api/runs/" + run["id"] + "/export-approval", {"result_hash": done["result_hash"], "acknowledge_exceptions": True})
        content = client.get(approved["download_url"])
        require(content.status_code == 200, "Verified export could not be downloaded")
        book = load_workbook(io.BytesIO(content.content), read_only=True)
        try:
            require(len(book.sheetnames) == 8 and book["Lineage"].max_row == expected[0]+1, "Export sheets or lineage changed")
            quantities = {row[0]: row[2] for row in book["SKU_Summary"].iter_rows(min_row=2, values_only=True)}
            require(quantities == {"RICE-003":84,"SOAP-002":33,"TEA-001":21}, "Picking quantities changed")
        finally:
            book.close()
        task = post("/api/runs/" + run["id"] + "/handoff")
        require(task["simulation"] is True and post("/api/runs/" + run["id"] + "/handoff")["id"] == task["id"], "Simulated handoff is not idempotent")
        runs.append({"week": week, "summary": done["summary"], "rule_version": saved["rule_version"]})
    require([x["rule_version"] for x in runs] == [1,2,2], "Rule version reuse changed")
    return runs, approved["download_url"], hashlib.sha256(content.content).hexdigest()


def verify(bundle=None):
    result = {**candidate_info(ROOT), "passed": False, "mode": "native" if bundle else "source",
              "attempt_id": attempt_id(), "phase": "preparing", "stops": [], "restart_cycles": []}
    private = ROOT / ".runtime" / "release-private" / (result["attempt_id"] + ".log")
    private.parent.mkdir(parents=True, exist_ok=True)
    managed = None
    started = time.monotonic()
    try:
        if bundle:
            result["bundle_sha256"] = hashlib.sha256(Path(bundle).read_bytes()).hexdigest()
        with private.open("wb") as log, tempfile.TemporaryDirectory(prefix="maizi release 合成 ") as temporary:
            folder = Path(temporary)
            if bundle:
                with zipfile.ZipFile(bundle) as archive:
                    require(not any(Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name or ":" in name for name in archive.namelist()), "Unsafe bundle member")
                    archive.extractall(folder / "native")
                binary = folder / "native" / "MaiZi" / ("MaiZi.exe" if os.name == "nt" else "MaiZi")
                if os.name != "nt":
                    binary.chmod(0o755)
                info = json.loads((binary.parent / "build-info.json").read_text(encoding="utf-8"))
                require(info["source_sha256"] == result["source_sha256"] and info["version"] == result["version"], "Native bundle does not match the current source candidate")
                command = [str(binary)]
                environment = child_environment(native=True)
            else:
                command = [sys.executable, "-m", "maizi.launcher"]
                environment = child_environment()
                environment["PYTHONPATH"] = str(ROOT / "backend")
            environment.update({"LLM_API_KEY":"", "LLM_BASE_URL":"", "LLM_MODEL":""})
            result["phase"] = "choosing_port"
            port = free_port()
            def args(chosen_port=port, data="data"):
                return [*command, "--no-browser", "--strict-port", "--port", str(chosen_port), "--data-dir", str(folder/data)]
            def start(chosen_port=port, data="data"):
                return ManagedProcess(args(chosen_port, data), cwd=folder, env=environment, stdout=log, stderr=subprocess.STDOUT)
            def stop(stage):
                nonlocal managed
                evidence = {"stage": stage, **managed.stop()}
                result["stops"].append(evidence)
                managed = None
                require(evidence["graceful"], "Graceful stop failed; owned process cleanup was required or could not be verified")
                evidence["port"] = released_port(port)
            try:
                result["phase"] = "startup"
                managed = start()
                with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=60) as client:
                    instance = await_health(managed, client, result["version"])
                    instances = [instance]
                    result["phase"] = "data_directory_lock"
                    duplicate = start(free_port())
                    try:
                        require(duplicate.process.wait(timeout=30) != 0, "Duplicate data-directory instance was not blocked")
                        require(client.get("/api/health").json()["instance_id"] == instance, "Original instance changed during duplicate launch")
                    finally:
                        duplicate_stop = duplicate.stop()
                    require(duplicate_stop["remaining_processes"] == 0 and not duplicate_stop["forced_cleanup"], "Duplicate launch left an owned process")
                    result["duplicate_instance_blocked"] = True
                    result["phase"] = "strict_port"
                    occupied = start(port, "different-data-directory")
                    try:
                        require(occupied.process.wait(timeout=30) != 0, "Strict port unexpectedly selected a fallback")
                    finally:
                        occupied_stop = occupied.stop()
                    require(occupied_stop["remaining_processes"] == 0 and not occupied_stop["forced_cleanup"], "Occupied-port launch left an owned process")
                    result["occupied_port_rejected"] = True
                    result["phase"] = "three_week_journey"
                    weeks, download_url, download_hash = journey(client)
                    result.update({"weeks": weeks, "unknown_status_approval_blocked": True})
                    for cycle in range(1, 4):
                        result["phase"] = "stop_cycle_" + str(cycle)
                        stop(result["phase"])
                        result["phase"] = "restart_cycle_" + str(cycle)
                        managed = start()
                        instance = await_health(managed, client, result["version"], instances)
                        instances.append(instance)
                        history = client.get("/api/history/runs").json()
                        require(history["total"] == 3 and all(x["status"] == "completed" for x in history["rows"]), "Restart did not retain three completed runs")
                        download = client.get(download_url)
                        require(download.status_code == 200 and hashlib.sha256(download.content).hexdigest() == download_hash, "Restart changed the historical download")
                        result["restart_cycles"].append({"cycle": cycle, "new_instance": True, "history_and_download": True})
                result["phase"] = "final_shutdown"
                stop("final_shutdown")
                result.update({"stop_and_port_release": True, "restart_history_and_download": True})
            finally:
                if managed:
                    result["stops"].append({"stage":"failure_cleanup", **managed.stop()})
                    managed = None
            result["phase"] = "temporary_directory_cleanup"
        result.update({"passed": True, "phase":"complete", "seconds":round(time.monotonic()-started, 3)})
    except Exception as exc:
        result.update({"passed":False, "error_type":type(exc).__name__, "os_error":getattr(exc,"errno",None),
                       "winerror":getattr(exc,"winerror",None),
                       "port_diagnostics":getattr(exc,"port_diagnostics",None),
                       "message": str(exc) if isinstance(exc, RuntimeError) else "Release verification failed; inspect the private local log for this attempt."})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    target = report_path(ROOT, "native-release.json" if args.bundle else "source-release.json", args.output)
    result = verify(args.bundle)
    write_report(target, result)
    print(json.dumps(result))
    print("Report:", target.relative_to(ROOT) if target.is_relative_to(ROOT) else target.name)
    raise SystemExit(0 if result["passed"] else 1)
