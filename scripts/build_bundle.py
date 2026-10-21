"""Build a native bundle on the current OS. Never bundle runtime data or credentials."""
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    web = ROOT / "frontend" / "dist"
    if not (web / "index.html").is_file():
        raise SystemExit("Build the frontend first: npm --prefix frontend ci; npm --prefix frontend run build")
    # Fixed virtual co_filename paths keep private build paths out of Python bytecode.
    subprocess.run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "--onedir",
                    "--name", "MaiZi", "--paths", str(ROOT / "backend"),
                    "--add-data", str(web) + ":web", "--collect-submodules", "maizi",
                    "--collect-submodules", "uvicorn", "--hidden-import", "sqlalchemy.dialects.sqlite",
                    "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / "pyinstaller"),
                    "--specpath", str(ROOT / "build"), str(ROOT / "scripts" / "frozen_entry.py")],
                   cwd=ROOT, check=True)
    bundle = ROOT / "dist" / "MaiZi"
    shutil.copyfile(ROOT / ".env.example", bundle / ".env.example")
    shutil.copyfile(ROOT / "LICENSE", bundle / "LICENSE")
    (bundle / "START_HERE.txt").write_text(
        "MaiZi local spreadsheet workflow assistant\n\n"
        "Launch MaiZi.exe (Windows) or MaiZi (macOS). A local browser window opens.\n"
        "Synthetic demos and editable rules work without an API key.\n"
        "For live AI, copy .env.example to .env beside the executable and configure it locally.\n"
        "Never share that .env or runtime data. The app binds only to 127.0.0.1.\n"
        "macOS: this development build is not notarized. Use the source instructions if blocked.\n"
        "Close the terminal to stop the app. The warehouse task integration is simulated.\n", encoding="utf-8")
    info = {"version": "0.1.0", "os": platform.system(), "architecture": platform.machine(),
            "python": platform.python_version(), "contains_credentials": False,
            "integration": "Orbyte simulation; Status Guard developed on Replit Free"}
    (bundle / "build-info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    # An allowlist-built bundle still gets a second explicit credential/data filename check.
    forbidden = [p for p in bundle.rglob("*") if p.name == ".env" or p.suffix in {".sqlite", ".sqlite3", ".db"} or ".runtime" in p.parts]
    if forbidden:
        raise SystemExit("Bundle privacy check failed; do not distribute")
    archive = ROOT / "dist" / ("MaiZi-" + platform.system() + "-" + platform.machine())
    shutil.make_archive(str(archive), "zip", root_dir=bundle.parent, base_dir=bundle.name)
    print("Built:", archive.name + ".zip")

if __name__ == "__main__":
    main()
