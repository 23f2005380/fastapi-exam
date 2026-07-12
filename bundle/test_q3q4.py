from main import app
from fastapi.testclient import TestClient
c = TestClient(app)

r = c.post("/extract", json={"invoice_text": "Invoice No: INV-001\nDate: 2026-03-10\nVendor: Test\nAmount: 3200.00\nGST: 640.00\nCurrency: EUR"})
print("Q3:", r.status_code, r.json())

r = c.post("/dynamic-extract", json={"text": "Rahul bought 3 notebooks for Rs. 240 on 12 June 2026 from Alpha Store.", "schema": {"customer_name":"string","quantity":"integer","amount":"float","purchase_date":"date","store":"string"}})
print("Q4:", r.status_code, r.json())

r = c.post("/extract", json={"text": "Invoice from Acme Corp. Amount: 1250.00 USD. Due: 2026-08-15"})
print("Q8:", r.status_code, r.json())
