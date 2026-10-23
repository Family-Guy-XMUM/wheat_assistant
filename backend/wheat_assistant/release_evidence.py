"""Credential-free candidate fingerprints and non-overwriting release receipts."""
import hashlib
import json
import os
import platform
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from wheat_assistant import __version__

ROOT_FILES = {"README.md", "LICENSE", "AGENTS.md", "CONTRACT.md", "REPLIT_MODULE.json", ".env.example", ".gitignore", ".gitattributes",
              "pyproject.toml", "uv.lock", "Start_wheat_assistant.command", "Start_wheat_assistant.bat", "Setup_Windows.bat", "Validate_Windows.bat",
              "WINDOWS_VALIDATION.md", "ACCEPTANCE.md"}
TREES = ("backend/wheat_assistant", "frontend/src", "frontend/public", "frontend/e2e", "frontend/dist", "tests", "scripts", ".github/workflows")
IGNORED = {"__pycache__", ".pytest_cache", ".hypothesis", ".DS_Store", "node_modules", ".venv", ".env", ".git", ".runtime"}


def source_files(root):
    root = Path(root)
    files = {root / name for name in ROOT_FILES if (root / name).is_file()}
    for tree in TREES:
        files.update(p for p in (root / tree).rglob("*") if p.is_file() and not IGNORED.intersection(p.relative_to(root).parts))
    if (root / "frontend").is_dir():
        files.update(p for p in (root / "frontend").iterdir() if p.is_file() and p.suffix in {".json", ".ts", ".html", ".js"})
    return sorted(files)


def runtime_manifest(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted([*(root / "backend" / "wheat_assistant").rglob("*.py"),
                             *[p for p in (root / "frontend" / "dist").rglob("*") if p.is_file()]])}


def manifest_digest(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def candidate_info(root):
    root = Path(root)
    result = {"version": __version__, "os": platform.system(), "architecture": platform.machine(),
              "python": platform.python_version(), "base_commit": None, "working_tree_dirty": None,
              "source_sha256": manifest_digest(runtime_manifest(root)),
              "candidate_sha256": manifest_digest({p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                                   for p in source_files(root)}), "ai_calls": 0}
    if (root / ".git").exists():
        try:
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
            if re.fullmatch(r"[0-9a-f]{40,64}", head):
                result["base_commit"] = head
            result["working_tree_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, stderr=subprocess.DEVNULL))
        except (OSError, subprocess.SubprocessError):
            pass
    elif (root / "CANDIDATE.json").is_file():
        packaged = json.loads((root / "CANDIDATE.json").read_text(encoding="utf-8"))
        result["packaged_candidate_matches"] = packaged.get("candidate_sha256") == result["candidate_sha256"]
        head = packaged.get("base_commit", "")
        if isinstance(head, str) and re.fullmatch(r"[0-9a-f]{40,64}", head):
            result["base_commit"] = head
            result["base_commit_origin"] = "source_package_metadata"
    return result


def attempt_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]


def report_path(root, name, requested=None):
    path = Path(requested) if requested else Path(root) / "output" / "verification" / ("v" + __version__) / attempt_id() / name
    if path.exists():
        path = path.with_name(path.stem + "-" + attempt_id() + path.suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_report(path, result):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
