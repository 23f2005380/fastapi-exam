import json
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# ─── Q3: Fixed Invoice Extraction ──────────────────────────────────────────

with open("../q-invoice-extract-server_sample.json") as f:
    samples = json.load(f)["samples"]

for i, s in enumerate(samples):
    r = client.post("/extract", json={"invoice_text": s["invoice_text"]})
    print(f"Q3 Sample #{i+1}: {r.status_code} {r.json()}")

# ─── Q4: Dynamic Schema Extraction ────────────────────────────────────────

with open("../q-dynamic-extract-server_sample.json") as f:
    dynamic_samples = json.load(f)["samples"]

for i, s in enumerate(dynamic_samples):
    r = client.post("/dynamic-extract", json={"text": s["text"], "schema": s["schema"]})
    print(f"Q4 Sample #{i+1}: {r.status_code} {r.json()}")
