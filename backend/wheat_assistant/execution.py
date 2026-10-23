import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil
from wheat_assistant.runtime_environment import child_environment

def execute_isolated(rows, products, flow):
    with tempfile.TemporaryDirectory(prefix="wheat_assistant-run-") as folder:
        source, target = Path(folder) / "request.json", Path(folder) / "result.json"
        source.write_text(json.dumps({"rows": rows, "products": products, "flow": flow}, ensure_ascii=False), encoding="utf-8")
        source.chmod(0o400)
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--worker", str(source), str(target)]
        else:
            command = [sys.executable, "-m", "wheat_assistant.worker", str(source), str(target)]
        environment = child_environment()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        process = subprocess.Popen(command, cwd=folder, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        monitor = psutil.Process(process.pid)
        started = time.monotonic()
        try:
            while process.poll() is None:
                if time.monotonic() - started > 30:
                    raise RuntimeError("Processing exceeded the 30-second step limit")
                try:
                    cpu = monitor.cpu_times()
                    if monitor.memory_info().rss > 512 * 1024 * 1024 or cpu.user + cpu.system > 20:
                        raise RuntimeError("Processing exceeded the resource limit")
                except psutil.NoSuchProcess:
                    break
                time.sleep(0.04)
            _, error = process.communicate(timeout=2)
            if process.returncode != 0 or not target.exists():
                raise RuntimeError("The processing step failed; inspect the validated inputs and rules")
            return json.loads(target.read_text(encoding="utf-8"))
        except BaseException:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            raise
