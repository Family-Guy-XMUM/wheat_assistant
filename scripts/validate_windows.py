"""One immutable Windows acceptance attempt; raw logs always stay local."""
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from wheat_assistant import __version__
from wheat_assistant.release_evidence import attempt_id, candidate_info, write_report

ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.name != "nt" or platform.machine().upper() not in {"AMD64", "X86_64"}:
        raise SystemExit("Run this validator on Windows x64; another platform cannot validate Windows binaries.")
    attempt = attempt_id()
    report_dir = ROOT / "output" / "verification" / ("v"+__version__) / attempt
    report_dir.mkdir(parents=True, exist_ok=False)
    private = ROOT / ".runtime" / "windows-validation" / (attempt+".log")
    private.parent.mkdir(parents=True, exist_ok=True)
    bundle = ROOT / "dist" / ("wheat_assistant-Windows-"+platform.machine()+"-v"+__version__+".zip")
    source_report = report_dir / "windows-source-release.json"
    native_report = report_dir / "windows-native-release.json"
    performance_report = report_dir / "windows-performance.json"
    steps = [
        ("python_tests", [sys.executable,"-m","pytest","-q"]),
        ("typescript_and_build", ["npm.cmd","--prefix","frontend","run","build"]),
        ("browser_install", ["npm.cmd","--prefix","frontend","exec","--","playwright","install","chromium"]),
        ("browser_acceptance", ["npm.cmd","--prefix","frontend","test"]),
        ("source_http_journey", [sys.executable,"scripts/verify_release.py","--output",str(source_report)]),
        ("native_build", [sys.executable,"scripts/build_bundle.py"]),
        ("native_http_journey", [sys.executable,"scripts/verify_release.py","--bundle",str(bundle),"--output",str(native_report)]),
        ("performance", [sys.executable,"scripts/benchmark_release.py","--output",str(performance_report)]),
    ]
    report = {**candidate_info(ROOT), "attempt_id":attempt, "steps":[{"check":name,"status":"not_run","passed":False} for name,_ in steps],
              "passed":False, "automated_passed":False, "acceptance_status":"pending_operator_confirmation",
              "manual_start_stop":"pending_operator_confirmation", "manual_excel":"pending_operator_confirmation"}
    target = report_dir / "windows-validation.json"
    environment = os.environ.copy()
    environment.update({"LLM_API_KEY":"", "LLM_MODEL":"", "LLM_BASE_URL":"", "PYTHONUTF8":"1", "WHEAT_ASSISTANT_BROWSER_CHANNEL":"chromium"})
    write_report(target, report)
    with private.open("w", encoding="utf-8") as log:
        for index, (name, command) in enumerate(steps):
            print("Checking: "+name, flush=True)
            step = report["steps"][index]
            step["status"] = "running"
            write_report(target, report)
            try:
                completed = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=900)
                step.update({"passed":completed.returncode == 0, "exit_code":completed.returncode,
                             "status":"passed" if completed.returncode == 0 else "failed"})
            except (OSError, subprocess.TimeoutExpired) as exc:
                step.update({"passed":False, "status":"failed", "error_type":type(exc).__name__,
                             "winerror":getattr(exc,"winerror",None)})
            # Recompute after the build: frontend output belongs to this attempt.
            report.update(candidate_info(ROOT))
            write_report(target, report)
            if not step["passed"]:
                for pending in report["steps"][index+1:]:
                    pending["reason"] = "Stopped after "+name+" failed"
                break
    for key, path in (("source_http_journey",source_report),("native_http_journey",native_report),("performance",performance_report)):
        if path.is_file():
            child = json.loads(path.read_text(encoding="utf-8"))
            report.setdefault("receipts", {})[key] = {"file":path.name,"passed":child.get("passed",False),
                                                     "source_sha256":child.get("source_sha256"),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    if bundle.is_file() and next(x for x in report["steps"] if x["check"]=="native_build")["passed"]:
        report["bundle"] = {"name":bundle.name,"sha256":hashlib.sha256(bundle.read_bytes()).hexdigest()}
    receipts = report.get("receipts", {})
    report["passed"] = (all(x["passed"] for x in report["steps"]) and len(receipts) == 3
                        and all(x["passed"] and x["source_sha256"] == report["source_sha256"] for x in receipts.values()))
    report["automated_passed"] = report["passed"]
    write_report(target, report)
    print("Automated validation: "+("PASS" if report["passed"] else "FAIL"))
    print("Report:", target.relative_to(ROOT).as_posix())
    print("Keep .runtime/windows-validation logs private. New attempts never overwrite earlier receipts.")
    print("Record actual launch / Ctrl+C / restart / Excel results separately in WINDOWS_VALIDATION.md.")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
