"""Three uncached full-size synthetic API runs; never uses a live model or user data."""
import argparse
import csv
import io
import json
import os
import platform
import statistics
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import psutil
from fastapi.testclient import TestClient
from openpyxl import load_workbook

for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
    os.environ[key] = ""
with patch("dotenv.load_dotenv", return_value=False):
    from maizi.api import create_app

GROUPS = ["fields", "statuses", "products", "units", "duplicates", "output"]
SHEETS = ["Warehouse_Picklist", "Order_Detail", "Exceptions", "Excluded", "Duplicates", "SKU_Summary", "Lineage", "Run_Summary"]

def csv_file(headers, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")

def trial():
    peak = [0]
    memory_available = [True]
    stopped = threading.Event()
    process = psutil.Process()
    def sample():
        while not stopped.is_set():
            try:
                peak[0] = max(peak[0], sum(p.memory_info().rss for p in [process] + process.children(recursive=True) if p.is_running()))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            except PermissionError:
                memory_available[0] = False
            stopped.wait(.025)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        with tempfile.TemporaryDirectory(prefix="maizi-benchmark-") as folder, TestClient(create_app(Path(folder))) as client:
            def post(url, data):
                response = client.post(url, json=data)
                assert response.status_code == 200, response.text
                return response.json()
            def upload(name, data, role):
                response = client.post("/api/files", files={"file":(name,data)},data={"role":role,"channel_id":"bulk" if role=="orders" else ""})
                assert response.status_code == 200, response.text
                return response.json()["id"]
            start = time.perf_counter()
            file_ids=[]
            for part in range(5):
                rows=[[f"O{i}","1",f"S{i%5000:04}","2","piece","Confirmed"] for i in range(part*2000,(part+1)*2000)]
                file_ids.append(upload(f"synthetic-orders-{part}.csv",csv_file(["Order ID","Line","SKU","Qty","Unit","Status"],rows),"orders"))
            master=[[f"S{i:04}",f"Synthetic product {i}","piece","12","6"] for i in range(5000)]
            file_ids.append(upload("synthetic-master.csv",csv_file(["SKU","Name","Base unit","Box size","Pack size"],master),"master"))
            batch=post("/api/batches",{"file_ids":file_ids,"label":"Synthetic scale acceptance"})
            flow=post(f"/api/batches/{batch['id']}/plan",{"mode":"suggested"})["flow"]
            preflight=post(f"/api/batches/{batch['id']}/preflight",flow)
            saved=post(f"/api/batches/{batch['id']}/approve",{"flow":flow,"expected_input_hash":preflight["input_hash"],"reviewed":GROUPS})
            run=post("/api/runs",{"batch_id":batch["id"],"flow_id":saved["id"]})
            prepared=time.perf_counter()
            done=post(f"/api/runs/{run['id']}/execute",{})
            executed=time.perf_counter()
            assert done["summary"]=={"input":10000,"included":10000,"excluded":0,"duplicate":0,"exception":0,"totals_match":True}
            export=post(f"/api/runs/{run['id']}/export-approval",{"result_hash":done["result_hash"],"acknowledge_exceptions":True})
            exported=time.perf_counter()
            response=client.get(export["download_url"])
            assert response.status_code==200
            book=load_workbook(io.BytesIO(response.content),read_only=True,data_only=False)
            assert book.sheetnames==SHEETS
            counts={sheet.title:sheet.max_row-1 for sheet in book}
            assert counts=={"Warehouse_Picklist":5000,"Order_Detail":10000,"Exceptions":0,"Excluded":0,"Duplicates":0,"SKU_Summary":5000,"Lineage":10000,"Run_Summary":9}
            totals={r[0]:str(r[2]) for r in book["SKU_Summary"].iter_rows(min_row=2,values_only=True)}
            assert totals=={f"S{i:04}":"4" for i in range(5000)}
            lineage=list(book["Lineage"].iter_rows(min_row=2,values_only=True))
            assert len({r[0] for r in lineage})==10000
            assert not any(cell.data_type=="f" for sheet in book for row in sheet for cell in row)
            book.close()
            all_skus=[]
            for offset in range(0,5000,200):
                page=client.get(f"/api/runs/{run['id']}/sku-summary",params={"offset":offset,"limit":200}).json()
                assert page["total"]==5000
                all_skus.extend(x["sku"] for x in page["rows"])
            assert len(set(all_skus))==5000
            last=client.get(f"/api/runs/{run['id']}/rows",params={"offset":9900,"limit":100}).json()
            assert last["total"]==10000 and len(last["rows"])==100
            return {"prepare_seconds":round(prepared-start,3),"execute_seconds":round(executed-prepared,3),
                    "export_seconds":round(exported-executed,3),"memory_sampling_available":memory_available[0] and peak[0]>0,
                    "peak_parent_and_children_rss_mib":round(peak[0]/1024**2,1) if peak[0] else None,
                    "sheet_rows":counts,"unique_lineage":10000,"browsed_skus":len(set(all_skus)),"workbook_bytes":len(response.content)}
    finally:
        stopped.set();sampler.join(timeout=2)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=Path("output/verification/performance.json"))
    args=parser.parse_args()
    runs=[]
    for i in range(3):
        item=trial();runs.append(item)
        print(json.dumps({"trial":i+1,**item}),flush=True)
    median=statistics.median(x["export_seconds"] for x in runs)
    result={"passed":median<=10 and all(x["memory_sampling_available"] for x in runs),"orders":10000,"skus":5000,"files":5,"runs":runs,"export_median_seconds":median,
            "target_seconds":10,"os":platform.system(),"architecture":platform.machine(),"cpu_count":os.cpu_count(),
            "memory_sampling":"25 ms, parent plus live child RSS; sums shared pages, not an exact allocation measure","ai_calls":0}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"passed":result["passed"],"export_median_seconds":median}))
    raise SystemExit(0 if result["passed"] else 1)
