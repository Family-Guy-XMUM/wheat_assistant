"""Minimal authenticated connectivity test. Never prints credentials or raw headers."""
from pathlib import Path
import json
import os
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
base = os.getenv("LLM_BASE_URL", "").rstrip("/")
model = os.getenv("LLM_MODEL", "")
key = os.getenv("LLM_API_KEY", "")
if not base or not model or not key:
    raise SystemExit("Missing local model configuration")
try:
    response = httpx.post(base + "/chat/completions", headers={"Authorization": "Bearer " + key},
                          json={"model": model, "messages": [{"role": "user", "content": 'Return only {"status":"ok"}'}],
                                "max_tokens": 32}, timeout=45)
    print("HTTP", response.status_code, "| model", model)
    if response.status_code == 200:
        body = response.json()
        content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        print("Nonempty completion:", bool(content), "| usage:", json.dumps(body.get("usage", {})))
    else:
        print("Connectivity failed. Provider response body withheld to avoid leaking credentials.")
except httpx.HTTPError as exc:
    print("Connectivity failed:", type(exc).__name__)
