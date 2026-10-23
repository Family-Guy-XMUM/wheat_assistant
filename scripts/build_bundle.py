"""Build a native bundle on the current OS. Never bundle runtime data or credentials."""
import json
import hashlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from wheat_assistant import __version__

ROOT = Path(__file__).resolve().parents[1]

def main():
    web = ROOT / "frontend" / "dist"
    if not (web / "index.html").is_file():
        raise SystemExit("Build the frontend first: npm --prefix frontend ci; npm --prefix frontend run build")
    # Fixed virtual co_filename paths keep private build paths out of Python bytecode.
    environment = os.environ.copy()
    environment["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build" / "pyinstaller-cache")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "--onedir",
                    "--name", "wheat_assistant", "--paths", str(ROOT / "backend"),
                    "--add-data", str(web) + ":web", "--collect-submodules", "wheat_assistant",
                    "--collect-submodules", "uvicorn", "--hidden-import", "sqlalchemy.dialects.sqlite",
                    "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / "pyinstaller"),
                    "--specpath", str(ROOT / "build"), str(ROOT / "scripts" / "frozen_entry.py")],
                   cwd=ROOT, check=True, env=environment)
    bundle = ROOT / "dist" / "wheat_assistant"
    shutil.copyfile(ROOT / ".env.example", bundle / ".env.example")
    shutil.copyfile(ROOT / "LICENSE", bundle / "LICENSE")
    for name in ("README.md", "ACCEPTANCE.md"):
        if (ROOT / name).is_file():
            shutil.copyfile(ROOT / name, bundle / name)
    (bundle / "START_HERE.txt").write_text(
        "wheat_assistant local spreadsheet workflow assistant\n\n"
        "Launch wheat_assistant.exe (Windows) or wheat_assistant (macOS). A local browser window opens.\n"
        "Synthetic demos and editable rules work without an API key.\n"
        "For live AI, copy .env.example to .env beside the executable and configure it locally.\n"
        "Never share that .env or runtime data. The app binds only to 127.0.0.1.\n"
        "macOS: this development build is not notarized. Use the source instructions if blocked.\n"
        "Close the terminal to stop the app. The warehouse task integration is simulated.\n", encoding="utf-8")
    sources = sorted(list((ROOT / "backend" / "wheat_assistant").rglob("*.py")) + [p for p in web.rglob("*") if p.is_file()])
    manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    info = {"version": __version__, "os": platform.system(), "architecture": platform.machine(),
            "python": platform.python_version(), "contains_credentials": False,
            "source_sha256": hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
            "integration": "Orbyte simulation; Status Guard developed on Replit Free"}
    (bundle / "build-info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    (bundle / "source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # An allowlist-built bundle still gets a second explicit credential/data filename check.
    forbidden = [p for p in bundle.rglob("*") if p.name == ".env" or p.suffix in {".sqlite", ".sqlite3", ".db"} or ".runtime" in p.parts]
    if forbidden:
        raise SystemExit("Bundle privacy check failed; do not distribute")
    archive = ROOT / "dist" / ("wheat_assistant-" + platform.system() + "-" + platform.machine() + "-v" + __version__)
    shutil.make_archive(str(archive), "zip", root_dir=bundle.parent, base_dir=bundle.name)
    print("Built:", archive.name + ".zip")

if __name__ == "__main__":
    main()
