"""Windows operator handoff: locked source checks, native build, and real HTTP journeys.

No live model requests. Share windows-validation.json and the two release JSON
reports; the detailed local log can contain local paths and must stay private.
"""
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    if os.name!="nt":
        raise SystemExit("Run this validator on Windows x64; macOS cannot validate Windows binaries.")
    report_dir=ROOT/"output"/"verification"
    report_dir.mkdir(parents=True,exist_ok=True)
    private=ROOT/".runtime"/"windows-validation-private.log"
    private.parent.mkdir(parents=True,exist_ok=True)
    report={"version":"0.2.0","os":platform.system(),"architecture":platform.machine(),"python":platform.python_version(),
            "ai_calls":0,"steps":[],"passed":False,"manual_start_stop":"pending_operator_confirmation"}
    steps=[("python_tests",[sys.executable,"-m","pytest","-q"]),
           ("typescript_and_build",["npm.cmd","--prefix","frontend","run","build"]),
           ("source_http_journey",[sys.executable,"scripts/verify_release.py","--output","output/verification/windows-source-release.json"]),
           ("native_build",[sys.executable,"scripts/build_bundle.py"]),
           ("native_http_journey",[sys.executable,"scripts/verify_release.py","--bundle","dist/MaiZi-Windows-"+platform.machine()+"-v0.2.0.zip","--output","output/verification/windows-native-release.json"])]
    environment=os.environ.copy()
    environment.update({"LLM_API_KEY":"","LLM_MODEL":"","LLM_BASE_URL":"","PYTHONUTF8":"1"})
    with private.open("w",encoding="utf-8") as log:
        for name,command in steps:
            print("Checking: "+name,flush=True)
            try:
                completed=subprocess.run(command,cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT,timeout=900)
                ok=completed.returncode==0
                report["steps"].append({"check":name,"passed":ok,"exit_code":completed.returncode})
            except (OSError,subprocess.TimeoutExpired) as error:
                ok=False
                report["steps"].append({"check":name,"passed":False,"error_type":type(error).__name__})
            if not ok:
                break
    report["passed"]=len(report["steps"])==len(steps) and all(x["passed"] for x in report["steps"])
    if report["passed"]:
        bundle=ROOT/"dist"/("MaiZi-Windows-"+platform.machine()+"-v0.2.0.zip")
        report["bundle"]={"name":bundle.name,"sha256":hashlib.sha256(bundle.read_bytes()).hexdigest()}
    (report_dir/"windows-validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("Automated validation: "+("PASS" if report["passed"] else "FAIL"))
    print("Report: output/verification/windows-validation.json")
    print("Keep .runtime/windows-validation-private.log private; it may contain local paths.")
    print("Also perform and record the manual launch / Ctrl+C / restart checklist in WINDOWS_VALIDATION.md.")
    return 0 if report["passed"] else 1

if __name__=="__main__":
    raise SystemExit(main())
