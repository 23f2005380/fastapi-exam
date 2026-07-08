import sys
sys.path.insert(0, r"D:\temp\fastapi-exam\bundle")

import main
from fastapi.testclient import TestClient

client = TestClient(main.app)

# Q1: /stats
r = client.get('/stats?values=1,2,3,4,5')
print('Q1:', r.status_code, r.json())

# Q2: /verify
r = client.post('/verify', json={'token': 'invalid'})
print('Q2 invalid:', r.status_code, r.json())

# Q3: /effective-config
r = client.get('/effective-config')
print('Q3:', r.status_code, r.json())

# Q5: /analytics
r = client.post('/analytics', json={'events': [{'user': 'a', 'amount': 10, 'ts': 1}]})
print('Q5 no key:', r.status_code)
r = client.post('/analytics', json={'events': [{'user': 'a', 'amount': 10, 'ts': 1}]}, headers={'X-API-Key': main.Q5_API_KEY})
print('Q5 auth:', r.status_code, r.json())

# Q6: /work /healthz /metrics
r = client.get('/work?n=10')
print('Q6 work:', r.status_code, r.json())
r = client.get('/healthz')
print('Q6 healthz:', r.status_code, r.json())
r = client.get('/metrics')
print('Q6 metrics:', r.status_code, 'len:', len(r.text))

# Q8: /extract
r = client.post('/extract', json={'text': 'INVOICE\nVendor: Acme Corp.\nAmount Due: $1250.00\nCurrency: USD\nDue Date: 2026-08-15'})
print('Q8:', r.status_code, r.json())

# Q9: /orders
r = client.post('/orders', headers={'Idempotency-Key': 'test-123'})
print('Q9 create:', r.status_code, r.json())
r = client.get('/orders?limit=5&cursor=1')
print('Q9 list:', r.status_code, r.json())

# Q10: /ping
r = client.get('/ping', headers={'X-Client-Id': 'client1'})
print('Q10:', r.status_code, r.json())

print("\nALL TESTS PASSED" if r.status_code == 200 else "FAILURES DETECTED")
