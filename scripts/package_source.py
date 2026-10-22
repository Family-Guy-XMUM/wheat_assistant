"""Package source and sanitized acceptance evidence from an explicit allowlist."""
import hashlib
import json
import zipfile
from pathlib import Path
from maizi import __version__

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={"README.md","LICENSE","AGENTS.md","CONTRACT.md","REPLIT_MODULE.json",".env.example",".gitignore",
            "pyproject.toml","uv.lock","Start_MaiZi.command","Start_MaiZi.bat","Setup_Windows.bat","Validate_Windows.bat",
            "WINDOWS_VALIDATION.md","ACCEPTANCE.md"}
TREES=["backend/maizi","frontend/src","frontend/public","frontend/e2e","frontend/dist","tests","scripts",".github/workflows"]
IGNORED={"__pycache__",".pytest_cache",".hypothesis",".DS_Store","node_modules",".venv",".env",".git",".runtime"}
EVIDENCE={"source-release.json","native-release.json","performance.json","planner-live.json","backup-restore.json","final-checks.json","privacy.json"}

def source_files():
    files={ROOT/name for name in ROOT_FILES if (ROOT/name).is_file()}
    for tree in TREES:
        files.update(p for p in (ROOT/tree).rglob("*") if p.is_file() and not IGNORED.intersection(p.relative_to(ROOT).parts))
    files.update(p for p in (ROOT/"frontend").iterdir() if p.is_file() and p.suffix in {".json",".ts",".html",".js"} and not p.name.endswith(".tsbuildinfo"))
    return sorted(files)

def main():
    target=ROOT/"dist"/("MaiZi-Windows-Source-v"+__version__+".zip")
    target.parent.mkdir(exist_ok=True)
    manifest={}
    with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as archive:
        for path in source_files():
            name=path.relative_to(ROOT).as_posix()
            manifest[name]=hashlib.sha256(path.read_bytes()).hexdigest()
            archive.write(path,"MaiZi_Assistant/"+name)
        for name in sorted(EVIDENCE):
            path=ROOT/"output"/"verification"/name
            if path.is_file():
                archive.write(path,"MaiZi_Assistant/verification/"+name)
        archive.writestr("MaiZi_Assistant/SOURCE_MANIFEST.json",json.dumps(manifest,indent=2))
    print(json.dumps({"archive":target.name,"source_files":len(manifest),"sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
                      "windows_native_verified":False}))

if __name__=="__main__":main()
