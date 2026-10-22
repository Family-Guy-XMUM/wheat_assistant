"""Restore a chosen local backup into a temporary copy and verify legacy read access."""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

def verify(backup):
    for key in ("LLM_API_KEY","LLM_BASE_URL","LLM_MODEL"):
        os.environ[key]=""
    with patch("dotenv.load_dotenv",return_value=False):
        from maizi.api import create_app
    with tempfile.TemporaryDirectory(prefix="maizi-restore-check-") as folder:
        restored=Path(folder)/"restored"
        shutil.copytree(backup,restored,ignore=shutil.ignore_patterns("backups",".env"))
        with closing(sqlite3.connect(restored/"maizi.sqlite")) as database:
            assert database.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
            count=database.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        assets=downloads=completed=0
        with TestClient(create_app(restored)) as client:
            store=client.app.state.store
            for asset in store.list("file"):
                original=backup/"files"/asset["storage_name"]
                saved=restored/"files"/asset["storage_name"]
                assert hashlib.sha256(original.read_bytes()).hexdigest()==hashlib.sha256(saved.read_bytes()).hexdigest()==asset["hash"]
                assets+=1
            for run in store.list("run"):
                response=client.get("/api/runs/"+run["id"])
                assert response.status_code==200 and response.json()["status"]==run["status"]
                if run["status"]=="completed":
                    completed+=1
                if run.get("export_approved"):
                    result=client.get("/api/runs/"+run["id"]+"/download")
                    assert result.status_code==200
                    old=(backup/"artifacts"/run["artifact"]).read_bytes()
                    assert hashlib.sha256(result.content).hexdigest()==hashlib.sha256(old).hexdigest()
                    downloads+=1
        return {"passed":True,"sqlite_integrity":"ok","restored_entities":count,"verified_original_files":assets,
                "legacy_completed_runs":completed,"legacy_exports_downloaded":downloads,"ai_calls":0,
                "scope":"Actual chosen backup, temporary restored copy only; original backup was not changed"}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("backup",type=Path)
    parser.add_argument("--output",type=Path,default=Path("output/verification/backup-restore.json"))
    args=parser.parse_args()
    result=verify(args.backup)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result))
