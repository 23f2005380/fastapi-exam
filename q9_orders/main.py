import uuid
import time
from fastapi import FastAPI, Request, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

EMAIL = "23f2005380@ds.study.iitm.ac.in"
TOTAL_ORDERS = 60
RATE_LIMIT = 17  # requests per 10s window

app = FastAPI()

# Idempotency store: key -> order_id
idempotency_store = {}

# Rate limit store: client_id -> [(timestamp, ...)]
rate_store = {}


class CreateOrderResponse(BaseModel):
    id: str


class OrderItem(BaseModel):
    id: int


class PaginatedOrders(BaseModel):
    items: list[OrderItem]
    next_cursor: Optional[str] = None


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    return response


@app.post("/orders")
async def create_order(
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")

    # Check rate limit
    client_id = request.headers.get("X-Client-Id", "default")
    _check_rate_limit(client_id)

    # Check if we've seen this key before
    if idempotency_key in idempotency_store:
        return {"id": idempotency_store[idempotency_key]}

    order_id = str(uuid.uuid4())
    idempotency_store[idempotency_key] = order_id
    return JSONResponse(content={"id": order_id}, status_code=201)


@app.get("/orders")
async def list_orders(
    request: Request,
    limit: int = Query(10, ge=1, le=TOTAL_ORDERS),
    cursor: Optional[str] = Query(None),
):
    # Check rate limit
    client_id = request.headers.get("X-Client-Id", "default")
    _check_rate_limit(client_id)

    start_id = int(cursor) if cursor and cursor.isdigit() else 1
    end_id = min(start_id + limit - 1, TOTAL_ORDERS)

    items = [{"id": i} for i in range(start_id, end_id + 1)]
    next_cursor = str(end_id + 1) if end_id < TOTAL_ORDERS else None

    return {"items": items, "next_cursor": next_cursor}


def _check_rate_limit(client_id: str):
    now = time.time()
    window = 10  # seconds

    if client_id not in rate_store:
        rate_store[client_id] = []

    # Clean old entries
    rate_store[client_id] = [t for t in rate_store[client_id] if now - t < window]

    if len(rate_store[client_id]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(window)},
        )

    rate_store[client_id].append(now)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    headers = getattr(exc, "headers", None) or {}
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )
