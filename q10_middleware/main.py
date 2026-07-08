import uuid
import time
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional

EMAIL = "23f2005380@ds.study.iitm.ac.in"
ALLOWED_ORIGIN = "https://app-2q4m9q.example.com"
EXAM_ORIGIN = "https://dash-9ftzez.example.com"  # exam page origin
RATE_LIMIT = 15  # requests per 10s window

app = FastAPI()

rate_store: dict[str, list[float]] = {}


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Middleware 1: Request context - handle X-Request-ID."""
    req_id = request.headers.get("X-Request-ID")
    if not req_id:
        req_id = str(uuid.uuid4())

    # Store in request scope so downstream can access it
    request.state.request_id = req_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Middleware 3: Per-client rate limiting (applied last in chain, runs first inbound)."""
    client_id = request.headers.get("X-Client-Id", "default")
    now = time.time()
    window = 10  # seconds

    if client_id not in rate_store:
        rate_store[client_id] = []

    # Clean old entries
    rate_store[client_id] = [t for t in rate_store[client_id] if now - t < window]

    if len(rate_store[client_id]) >= RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(window)},
        )

    rate_store[client_id].append(now)

    response = await call_next(request)
    return response


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    """Middleware 2: Scoped CORS."""
    response = await call_next(request)
    origin = request.headers.get("origin", "")

    if origin in (ALLOWED_ORIGIN, EXAM_ORIGIN):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"

    return response


@app.get("/ping")
async def ping(request: Request):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return {"email": EMAIL, "request_id": request_id}


@app.options("/ping")
async def ping_preflight():
    return JSONResponse(content=None, status_code=204)
