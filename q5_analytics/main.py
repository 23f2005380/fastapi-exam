from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

EMAIL = "23f2005380@ds.study.iitm.ac.in"
API_KEY = "ak_n1b6e43ciamj9deqvn9t1nu3"

app = FastAPI()


class Event(BaseModel):
    user: str
    amount: float
    ts: int


class AnalyticsRequest(BaseModel):
    events: list[Event]


class AnalyticsResponse(BaseModel):
    email: str
    total_events: int
    unique_users: int
    revenue: float
    top_user: str


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


@app.post("/analytics")
async def analytics(req: AnalyticsRequest, x_api_key: Optional[str] = Header(None)):
    if x_api_key is None or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    events = req.events
    total_events = len(events)
    unique_users = len(set(e.user for e in events))
    revenue = sum(e.amount for e in events if e.amount > 0)

    # Find top_user: user with highest sum of positive amounts
    user_revenue = {}
    for e in events:
        if e.amount > 0:
            user_revenue[e.user] = user_revenue.get(e.user, 0) + e.amount

    top_user = max(user_revenue, key=user_revenue.get) if user_revenue else ""

    return AnalyticsResponse(
        email=EMAIL,
        total_events=total_events,
        unique_users=unique_users,
        revenue=revenue,
        top_user=top_user,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
