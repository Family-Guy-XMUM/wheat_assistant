"""Package an explicit source allowlist and only the selected version's receipts."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from maizi import __version__
from maizi.release_evidence import candidate_info, manifest_digest, source_files as distributable_sources

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = {"source-release.json", "native-release.json", "performance.json", "browser-results.json", "final-checks.json", "eol-checkout.json"}


def source_files():
    return distributable_sources(ROOT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verification-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    target = args.output or ROOT/"dist"/("MaiZi-Windows-Source-v"+__version__+".zip")
    if target.exists():
        raise SystemExit("Source ZIP already exists. Preserve it and use --output for a new candidate.")
    target.parent.mkdir(parents=True, exist_ok=True)
    paths = source_files()
    snapshot = {path.relative_to(ROOT).as_posix(): path.read_bytes() for path in paths}
    manifest = {name: hashlib.sha256(content).hexdigest() for name, content in snapshot.items()}
    info = candidate_info(ROOT)
    if info["candidate_sha256"] != manifest_digest(manifest):
        raise SystemExit("Source changed while taking the packaging snapshot; freeze and retry")
    evidence = []
    if args.verification_dir:
        for name in sorted(EVIDENCE):
            path = args.verification_dir/name
            if path.is_file():
                content = path.read_bytes()
                receipt = json.loads(content)
                if receipt.get("version") != __version__:
                    raise SystemExit("A selected receipt belongs to another release version")
                if receipt.get("source_sha256") and receipt["source_sha256"] != info["source_sha256"]:
                    raise SystemExit("A selected receipt belongs to another runtime candidate")
                evidence.append((path,content))
    try:
        with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as archive:
            for path in paths:
                name = path.relative_to(ROOT).as_posix()
                entry = zipfile.ZipInfo.from_file(path,"MaiZi_Assistant/"+name)
                archive.writestr(entry,snapshot[name],compress_type=zipfile.ZIP_DEFLATED)
            for path, content in evidence:
                archive.writestr("MaiZi_Assistant/verification/"+path.name,content)
            archive.writestr("MaiZi_Assistant/SOURCE_MANIFEST.json",json.dumps(manifest,indent=2))
            archive.writestr("MaiZi_Assistant/CANDIDATE.json",json.dumps(info,indent=2))
        current = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files()}
        if current != manifest or any(path.read_bytes() != content for path, content in evidence):
            raise SystemExit("Source or evidence changed during packaging; partial ZIP removed, freeze and retry")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    print(json.dumps({"archive":target.name,"source_files":len(manifest),"sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
                      "source_sha256":info["source_sha256"],"candidate_sha256":info["candidate_sha256"],"windows_native_verified":False}))


if __name__=="__main__":
    main()
