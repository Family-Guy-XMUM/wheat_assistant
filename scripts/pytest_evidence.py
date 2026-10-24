"""Pytest plugin: publish outcomes and source locations, never captured data or locals."""
from __future__ import annotations

import json
import os
import platform
import re
from pathlib import Path


def pytest_addoption(parser):
    parser.addoption("--safe-report", help="Write a sanitized pytest JSON receipt")


def pytest_configure(config):
    target = config.getoption("--safe-report")
    if target:
        config.pluginmanager.register(SafeReport(config, Path(target)), "wheat-safe-report")


class SafeReport:
    def __init__(self, config, target):
        self.root, self.target = Path(config.rootpath).resolve(), target
        self.outcomes = {}
        self.ids = {}
        self.failures = []
        self.selected = 0
        self.write()

    def location(self, path):
        candidate = Path(str(path))
        if not candidate.is_absolute():
            candidate = self.root / candidate
        try:
            relative = candidate.resolve().relative_to(self.root).as_posix()
        except (ValueError, OSError):
            return "<external>"
        if not re.fullmatch(r"[A-Za-z0-9_./-]+\.py", relative):
            return "<external>"
        return relative

    def node(self, nodeid):
        if nodeid not in self.ids:
            parts = nodeid.split("::")
            names = []
            for part in parts[1:]:
                name = part.split("[", 1)[0]
                names.append(name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "<test>")
            value = "::".join([self.location(parts[0]), *names])
            if "[" in nodeid:
                value += "[case-" + str(len(self.ids) + 1) + "]"
            self.ids[nodeid] = value
        return self.ids[nodeid]

    def failure(self, report, phase):
        representation = report.longrepr
        crash = getattr(representation, "reprcrash", None)
        message = str(getattr(crash, "message", ""))
        match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)|AssertionError|Failed)\b", message)
        error_type = match.group(1) if match else ("CollectionError" if phase == "collection" else "AssertionError")
        frames = []
        for entry in getattr(getattr(representation, "reprtraceback", None), "reprentries", []):
            location = getattr(entry, "reprfileloc", None)
            if location:
                frames.append({"file": self.location(location.path), "line": int(location.lineno)})
        if not frames and crash:
            frames.append({"file": self.location(crash.path), "line": int(crash.lineno)})
        windows_error = re.search(r"\[WinError (\d+)\]", message)
        return {"test": self.node(report.nodeid), "phase": phase, "error_type": error_type,
                "winerror": int(windows_error.group(1)) if windows_error else None,
                "frames": frames[-12:]}

    def pytest_collection_finish(self, session):
        self.selected = len(session.items)
        self.write()

    def pytest_collectreport(self, report):
        if report.failed:
            self.failures.append(self.failure(report, "collection"))
            self.write()

    def pytest_runtest_logreport(self, report):
        self.node(report.nodeid)
        if report.failed:
            self.outcomes[report.nodeid] = "failed" if report.when == "call" else "error"
            self.failures.append(self.failure(report, report.when))
        elif self.outcomes.get(report.nodeid) not in {"failed", "error"}:
            if report.skipped:
                self.outcomes[report.nodeid] = "skipped"
            elif report.when == "call":
                self.outcomes[report.nodeid] = "passed"
        self.write()

    def pytest_sessionfinish(self, session, exitstatus):
        self.write(int(exitstatus))

    def write(self, exit_code=None):
        counts = {key: sum(value == key for value in self.outcomes.values())
                  for key in ("passed", "failed", "error", "skipped")}
        counts["collection_errors"] = sum(item["phase"] == "collection" for item in self.failures)
        data = {"schema_version": 1, "python": platform.python_version(), "os": platform.system(),
                "selected": self.selected, "counts": counts, "failures": self.failures,
                "completed": exit_code is not None, "exit_code": exit_code,
                "passed": exit_code == 0 and not self.failures,
                "scope": "Test names, phases, exception types and relative source locations only"}
        self.target.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.target.with_suffix(self.target.suffix + ".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temporary, self.target)
