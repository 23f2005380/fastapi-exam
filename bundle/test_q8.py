import main
from fastapi.testclient import TestClient

client = TestClient(main.app)

tests = [
    'INVOICE\nVendor: Acme-UXEC Industries Ltd.\nAmount Due: $550.00\nCurrency: GBP\nDue Date: 2026-07-15',
    'Invoice from MegaCorp-X Inc. Total: $1250.00 USD. Payment due: 2026-08-15.',
    'Bill from Smith & Co Ltd. Amount: $200.50 EUR. Due: 2026-09-01.',
    'garbage text no invoice',
    '',
]

for t in tests:
    r = client.post('/extract', json={'text': t})
    print(f"Input: {t[:40]}... -> {r.status_code} {r.json()}")
    print()
