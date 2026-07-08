import uuid
import time
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import statistics

EMAIL = "23f2005380@ds.study.iitm.ac.in"
ALLOWED_ORIGIN = "https://dash-9ftzez.example.com"

app = FastAPI()

# Custom CORS middleware that only allows our specific origin
@app.middleware("http")
async def custom_cors_and_headers(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time

    origin = request.headers.get("origin", "")

    if origin == ALLOWED_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
    elif request.method == "OPTIONS":
        # Reject preflight from non-allowed origins (no ACAO header)
        pass

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.6f}"

    return response


@app.options("/stats")
async def stats_preflight():
    return JSONResponse(content=None, status_code=204)


@app.get("/stats")
async def get_stats(values: str = Query(..., description="Comma-separated integers")):
    try:
        nums = [int(x.strip()) for x in values.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid integer values")

    if not nums:
        raise HTTPException(status_code=400, detail="At least one value required")

    count = len(nums)
    total = sum(nums)
    min_val = min(nums)
    max_val = max(nums)
    mean_val = total / count

    return {
        "email": EMAIL,
        "count": count,
        "sum": total,
        "min": min_val,
        "max": max_val,
        "mean": mean_val,
    }
