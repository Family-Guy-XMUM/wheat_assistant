"""Make a minimal cloud upload, audit private markers locally, and omit Git metadata."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

from check_release_privacy import markers

ROOT = Path(__file__).resolve().parents[1]
FILES = {".replit", "pyproject.toml", "uv.lock", "LICENSE", "README.md", "ACCEPTANCE.md", "REPLIT_MODULE.json",
         "REPLIT_DEPLOYMENT.md", "frontend/index.html", "frontend/package.json", "frontend/package-lock.json",
         "frontend/tsconfig.json", "frontend/vite.config.ts", "scripts/replit_build.sh", "scripts/replit_start.sh",
         "scripts/replit_dev.sh", "tests/test_cloud_boundary.py", "tests/test_cloud_journey.py"}


def snapshot():
    paths = [ROOT / name for name in sorted(FILES)]
    for directory, pattern in [("backend/wheat_assistant", "*.py"), ("frontend/src", "*"), ("frontend/dist", "*")]:
        paths.extend(path for path in (ROOT / directory).rglob(pattern) if path.is_file())
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise SystemExit("Build the frontend before packaging")
    return {path.relative_to(ROOT).as_posix(): path.read_bytes() for path in paths}


def audit(files):
    signatures, _ = markers()
    matches = []
    checked = 0
    def inspect(name, content, depth=0):
        nonlocal checked
        checked += 1
        for category, signature in signatures:
            if signature in content:
                matches.append({"file": name, "category": category})
        if content.startswith(b"PK\x03\x04") and depth < 3:
            with zipfile.ZipFile(io.BytesIO(content)) as nested:
                for member in nested.infolist():
                    if not member.is_dir():
                        inspect(name + "!" + member.filename, nested.read(member), depth + 1)
    for name, content in files.items():
        if set(Path(name).parts).intersection({".git", ".env", ".venv", "node_modules", "__pycache__"}) or name.endswith((".map", ".pyc", ".sqlite", ".log")):
            matches.append({"file": name, "category": "forbidden_upload"})
        inspect(name, content)
    return {"passed": not matches, "checked_items": checked, "matches": matches, "git_metadata_included": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Preserve earlier upload archives; choose a new output name")
    files = snapshot()
    report = audit(files)
    if not report["passed"]:
        print(json.dumps(report))
        raise SystemExit("Upload blocked by privacy audit")
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        archive.writestr("CLOUD_SOURCE_MANIFEST.json", json.dumps(manifest, indent=2))
        archive.writestr("CLOUD_PRIVACY_AUDIT.json", json.dumps(report, indent=2))
    if files != snapshot():
        args.output.unlink()
        raise SystemExit("Source changed during packaging; freeze and retry")
    print(json.dumps({"archive": args.output.name, "source_files": len(files),
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(), "privacy": report}))


if __name__ == "__main__":
    main()
