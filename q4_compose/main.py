import os
from fastapi import FastAPI
import redis.asyncio as aioredis

EMAIL = "23f2005380@ds.study.iitm.ac.in"
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")

app = FastAPI()

redis_client = None


@app.on_event("startup")
async def startup():
    global redis_client
    redis_client = await aioredis.from_url(f"redis://{REDIS_HOST}:6379/0", decode_responses=True)


@app.on_event("shutdown")
async def shutdown():
    if redis_client:
        await redis_client.close()


@app.get("/healthz")
async def healthz():
    try:
        await redis_client.ping()
        redis_up = "up"
    except Exception:
        redis_up = "down"
    return {"status": "ok", "redis": redis_up}


@app.post("/hit/{key}")
async def hit(key: str):
    count = await redis_client.incr(key)
    return {"key": key, "count": count}


@app.get("/count/{key}")
async def get_count(key: str):
    val = await redis_client.get(key)
    count = int(val) if val is not None else 0
    return {"key": key, "count": count}
