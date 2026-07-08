import uuid
import time
import json
import os
from fastapi import FastAPI, Query, Request
from fastapi.responses import Response, JSONResponse
from prometheus_client import Counter, generate_latest, REGISTRY
from typing import Optional

EMAIL = "23f2005380@ds.study.iitm.ac.in"
START_TIME = time.time()

app = FastAPI()

# Prometheus counter
request_counter = Counter("http_requests_total", "Total HTTP requests", ["method", "path"])

# In-memory structured log store
log_store = []


def log(level, path, request_id):
    entry = {
        "level": level,
        "ts": time.time(),
        "path": path,
        "request_id": request_id,
    }
    log_store.append(entry)
    # Keep only last 1000 logs
    if len(log_store) > 1000:
        log_store[:100] = []


@app.middleware("http")
async def middlewares(request: Request, call_next):
    request_id = str(uuid.uuid4())

    # Record the request
    request_counter.labels(method=request.method, path=request.url.path).inc()
    log("info", request.url.path, request_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/work")
async def work(n: int = Query(1, description="Units of work")):
    # Simulate work
    for _ in range(min(n, 1000000)):
        pass
    return {"email": EMAIL, "done": n}


@app.get("/metrics")
async def metrics():
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type="text/plain; version=0.0.4")


@app.get("/healthz")
async def healthz():
    uptime_s = time.time() - START_TIME
    return {"status": "ok", "uptime_s": round(uptime_s, 4)}


@app.get("/logs/tail")
async def logs_tail(limit: int = Query(10, description="Number of log entries")):
    return log_store[-limit:]
