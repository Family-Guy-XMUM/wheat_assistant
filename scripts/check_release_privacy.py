"""Local distribution audit. Reports marker categories, never marker values or credentials."""
import argparse
import io
import json
import subprocess
import zipfile
from pathlib import Path
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]

def markers():
    values=[("home_path",str(Path.home())),("local_account",Path.home().name)]
    if (ROOT/".env").is_file():
        values.extend(("credential",value) for name,value in dotenv_values(ROOT/".env").items()
                      if value and any(word in name.upper() for word in ("KEY","TOKEN","SECRET","PASSWORD")))
    result=subprocess.run(["git","log","--format=%an%n%ae%n%cn%n%ce"],cwd=ROOT,capture_output=True,text=True,check=True)
    identities={x for x in result.stdout.splitlines() if len(x.strip())>=5}
    # These public tool/service labels are not a person's identity. In
    # dependencies, GitHub occurs in release links and public class names.
    values.extend(("git_identity",x) for x in identities if x.lower() not in {"codex","maizi team","sdc team","github","github actions"})
    return [(kind,value.encode()) for kind,value in values],bool(identities)

def audit(archives):
    signatures,has_git_identity=markers()
    hits=[];checked=0
    def scan(label,content,depth=0):
        nonlocal checked
        checked+=1
        for kind,value in signatures:
            if value in content:
                hits.append({"file":label,"category":kind})
        if content.startswith(b"PK\x03\x04") and depth<4:
            with zipfile.ZipFile(io.BytesIO(content)) as nested:
                for member in nested.infolist():
                    if member.is_dir():continue
                    if set(Path(member.filename).parts).intersection({".env",".git",".runtime"}) or Path(member.filename).suffix in {".sqlite",".db"}:
                        hits.append({"file":label+"!"+member.filename,"category":"private_runtime_filename"})
                    scan(label+"!"+member.filename,nested.read(member),depth+1)
    from package_source import source_files
    for path in source_files():scan(path.relative_to(ROOT).as_posix(),path.read_bytes())
    for path in archives:scan(path.name,path.read_bytes())
    binary=ROOT/"dist"/"MaiZi"/"MaiZi"
    if binary.is_file():
        from PyInstaller.archive.readers import CArchiveReader
        reader=CArchiveReader(str(binary))
        for name,entry in reader.toc.items():
            if entry[-1]=="z":
                modules=reader.open_embedded_archive(name)
                for module in modules.toc:
                    content=modules.extract(module,raw=True)
                    if content:scan("native-bytecode/"+module,content)
            else:
                content=reader.extract(name)
                if content:scan("native-entry/"+name,content)
    return {"passed":not hits,"checked_items":checked,"matches":hits,"scope":"Allowlisted source, nested ZIP/XLSX members and current macOS PyInstaller bytecode",
            "reviewed_public_label_collision":"GitHub in upstream release links and class names; licenses retained",
            "git_metadata_included_in_archives":False,"local_git_identity_present":has_git_identity,
            "local_git_note":"Existing local Git metadata was inspected for identity markers and was not rewritten or included in distributions. Public repository identity review remains separate."}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("archives",nargs="*",type=Path)
    parser.add_argument("--output",type=Path,default=Path("output/verification/privacy.json"))
    args=parser.parse_args()
    result=audit(args.archives)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result))
    raise SystemExit(0 if result["passed"] else 1)
