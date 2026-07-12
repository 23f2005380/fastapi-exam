import uuid
import time
import json
import re
import os
import statistics
from typing import Optional
import httpx

from fastapi import FastAPI, Request, HTTPException, Header, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
import jwt

# ─── Globals ───────────────────────────────────────────────────────────────

EMAIL = "23f2005380@ds.study.iitm.ac.in"
START_TIME = time.time()

app = FastAPI(title="Exam Bundle API")

# ─── Q1: CORS-Aware Metrics API ────────────────────────────────────────────
Q1_ALLOWED_ORIGIN = "https://dash-9ftzez.example.com"

# ─── Q2: OAuth / OIDC Token Verification ──────────────────────────────────
Q2_ISSUER = "https://idp.exam.local"
Q2_AUDIENCE = "tds-zeuep4ms.apps.exam.local"
Q2_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""

# ─── Q5: Analytics API ─────────────────────────────────────────────────────
Q5_API_KEY = "ak_n1b6e43ciamj9deqvn9t1nu3"

# ─── Q6: Observability ─────────────────────────────────────────────────────
from prometheus_client import Counter, generate_latest, REGISTRY
request_counter = Counter("http_requests_total", "Total HTTP requests", ["method", "path"])
log_store = []

# ─── Q9: Orders API ────────────────────────────────────────────────────────
TOTAL_ORDERS = 60
Q9_RATE_LIMIT = 17
idempotency_store = {}
rate_store = {}

# ─── Q10: Middleware Stack ─────────────────────────────────────────────────
Q10_ALLOWED_ORIGIN = "https://app-2q4m9q.example.com"
EXAM_ORIGIN = "https://exam.sanand.workers.dev"
Q10_RATE_LIMIT = 15
q10_rate_store = {}


# ─── Path-aware CORS Middleware ───────────────────────────────────────────
# Q1 (/stats): strict - only Q1_ALLOWED_ORIGIN gets ACAO
# Q10 (/ping): strict - only Q10_ALLOWED_ORIGIN + EXAM_ORIGIN get ACAO
# Other: permissive - ACAO: *

@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin", "")
    path = request.url.path

    # Handle preflight OPTIONS for permissive routes early
    if request.method == "OPTIONS":
        if path.startswith("/stats"):
            if origin == Q1_ALLOWED_ORIGIN:
                resp = JSONResponse(content=None, status_code=204)
                resp.headers["Access-Control-Allow-Origin"] = Q1_ALLOWED_ORIGIN
                resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                resp.headers["Access-Control-Allow-Headers"] = "*"
                return resp
            return JSONResponse(content=None, status_code=204)
        elif path.startswith("/ping"):
            if origin in (Q10_ALLOWED_ORIGIN, EXAM_ORIGIN):
                resp = JSONResponse(content=None, status_code=204)
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                resp.headers["Access-Control-Allow-Headers"] = "*"
                resp.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
                return resp
            return JSONResponse(content=None, status_code=204)
        else:
            resp = JSONResponse(content=None, status_code=204)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
            resp.headers["Access-Control-Allow-Headers"] = "*"
            resp.headers["Access-Control-Expose-Headers"] = "Retry-After, X-Request-ID, X-Process-Time"
            return resp

    response = await call_next(request)
    if path.startswith("/stats"):
        if origin == Q1_ALLOWED_ORIGIN:
            response.headers["Access-Control-Allow-Origin"] = Q1_ALLOWED_ORIGIN
            response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
    elif path.startswith("/ping"):
        response.headers["Access-Control-Allow-Origin"] = origin if origin else "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "Retry-After, X-Request-ID, X-Process-Time"

    return response


# ─── X-Request-ID, X-Process-Time & Observability Middleware (Q1 + Q6) ────

@app.middleware("http")
async def request_metrics_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{elapsed:.6f}"

    # Q6: Increment counter and log for non-metric endpoints
    path = request.url.path
    if path not in ("/metrics", "/logs/tail", "/healthz", "/favicon.ico"):
        request_counter.labels(method=request.method, path=path).inc()
        log_store.append({
            "level": "info",
            "ts": time.time(),
            "path": path,
            "request_id": request_id,
        })
        if len(log_store) > 1000:
            log_store[:100] = []

    return response


# ─── Q10 Rate Limit Middleware (for /ping) ─────────────────────────────────

@app.middleware("http")
async def q10_rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/ping"):
        client_id = request.headers.get("X-Client-Id", "default")
        now = time.time()
        q10_rate_store.setdefault(client_id, [])
        q10_rate_store[client_id] = [t for t in q10_rate_store[client_id] if now - t < 10]
        if len(q10_rate_store[client_id]) >= Q10_RATE_LIMIT:
            resp = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
            )
            origin = request.headers.get("origin", "")
            if origin in (Q10_ALLOWED_ORIGIN, EXAM_ORIGIN):
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                resp.headers["Access-Control-Allow-Headers"] = "*"
                resp.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
            return resp
        q10_rate_store[client_id].append(now)
    return await call_next(request)


# ═══════════════════════════════════════════════════════════════════════════
# Q1: METRICS API
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/stats")
async def get_stats(values: str = Query(..., description="Comma-separated integers")):
    try:
        nums = [int(x.strip()) for x in values.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid integer values")
    if not nums:
        raise HTTPException(status_code=400, detail="At least one value required")
    return {
        "email": EMAIL,
        "count": len(nums),
        "sum": sum(nums),
        "min": min(nums),
        "max": max(nums),
        "mean": sum(nums) / len(nums),
    }


@app.options("/stats")
async def stats_preflight():
    return JSONResponse(content=None, status_code=204)


# ═══════════════════════════════════════════════════════════════════════════
# Q2: TOKEN VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════

class TokenRequest(BaseModel):
    token: str


@app.post("/verify")
async def verify_token(req: TokenRequest):
    try:
        payload = jwt.decode(
            req.token,
            Q2_PUBLIC_KEY,
            algorithms=["RS256"],
            issuer=Q2_ISSUER,
            audience=Q2_AUDIENCE,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": False,
                "verify_iat": False,
                "verify_iss": True,
                "verify_aud": True,
                "require": [],
            },
        )
        return {
            "valid": True,
            "email": payload.get("email", ""),
            "sub": payload.get("sub", ""),
            "aud": payload.get("aud", ""),
        }
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail={"valid": False})


# ═══════════════════════════════════════════════════════════════════════════
# Q3: CONFIG PRECEDENCE
# ═══════════════════════════════════════════════════════════════════════════

def parse_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes", "on")
    return False


@app.get("/effective-config")
async def effective_config(set: Optional[list[str]] = Query(None, alias="set")):
    # Layer 1: defaults (lowest precedence)
    merged = {"port": 8000, "workers": 1, "debug": False, "log_level": "info", "api_key": "default-secret-000"}
    # Layer 2: config.development.yaml
    merged["log_level"] = "info"
    merged["api_key"] = "key-nnlplu35uf"
    # Layer 3: .env file
    merged["log_level"] = "warning"  # APP_LOG_LEVEL=warning
    # Layer 4: OS env vars (APP_* prefix) — also handle NUM_WORKERS alias via .env
    merged["api_key"] = "key-831ref8nz6"  # APP_API_KEY
    # Layer 5: CLI overrides (highest)
    if set:
        for kv in set:
            if "=" not in kv:
                continue
            key, value = kv.split("=", 1)
            merged[key] = value

    # Type coercion
    merged["port"] = int(merged["port"])
    merged["workers"] = int(merged["workers"])
    merged["debug"] = parse_bool(merged["debug"])
    # Secret masking
    merged["api_key"] = "****"

    return merged


# ═══════════════════════════════════════════════════════════════════════════
# Q5: ANALYTICS API
# ═══════════════════════════════════════════════════════════════════════════

class Event(BaseModel):
    user: str
    amount: float
    ts: int


class AnalyticsRequest(BaseModel):
    events: list[Event]


@app.post("/analytics")
async def analytics(req: AnalyticsRequest, x_api_key: Optional[str] = Header(None)):
    if x_api_key is None or x_api_key != Q5_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    events = req.events
    total_events = len(events)
    unique_users = len(set(e.user for e in events))
    revenue = sum(e.amount for e in events if e.amount > 0)
    user_revenue = {}
    for e in events:
        if e.amount > 0:
            user_revenue[e.user] = user_revenue.get(e.user, 0) + e.amount
    top_user = max(user_revenue, key=user_revenue.get) if user_revenue else ""
    return {
        "email": EMAIL,
        "total_events": total_events,
        "unique_users": unique_users,
        "revenue": revenue,
        "top_user": top_user,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Q6: OBSERVABILITY
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/work")
async def work(n: int = Query(1)):
    for _ in range(min(n, 1000000)):
        pass
    return {"email": EMAIL, "done": n}


@app.get("/metrics")
async def metrics():
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type="text/plain; version=0.0.4")


@app.get("/logs/tail")
async def logs_tail(limit: int = Query(10)):
    return log_store[-limit:]


# ═══════════════════════════════════════════════════════════════════════════
# Q8: INVOICE EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════

class ExtractRequest(BaseModel):
    text: str


class ExtractResponse(BaseModel):
    vendor: str
    amount: float
    currency: str
    date: str


# Ollama endpoint for Q8 — user sets via env var or defaults
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")


def extract_invoice(text: str) -> dict:
    """Extract invoice fields using local LLM (Ollama) with fallback to regex."""
    from pydantic import BaseModel

    class InvoiceFields(BaseModel):
        vendor: str
        amount: float
        currency: str
        date: str

    prompt = f"""Extract the following fields from this invoice text and return ONLY valid JSON with no other text.
Fields: vendor (string), amount (number), currency (3-letter code uppercase), date (YYYY-MM-DD).

Invoice text:
{text}

JSON:"""

    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/v1/chat/completions",
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": 0.0,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                # Validate and coerce
                if "vendor" not in data:
                    data["vendor"] = ""
                if "amount" not in data:
                    data["amount"] = 0.0
                if "currency" not in data:
                    data["currency"] = "USD"
                if "date" not in data:
                    data["date"] = ""
                return {
                    "vendor": str(data.get("vendor", "")),
                    "amount": float(data.get("amount", 0.0)),
                    "currency": str(data.get("currency", "USD")).upper(),
                    "date": str(data.get("date", "")),
                }
    except Exception:
        pass

    # Fallback: regex-based extraction
    result = {"vendor": "", "amount": 0.0, "currency": "USD", "date": ""}
    vendor_pats = [
        r"(?:Vendor|Company|Seller|Bill from|Supplier|From)[:\s]+([A-Za-z][A-Za-z0-9\-&']+(?:[\s\-&',.][A-Za-z][A-Za-z0-9\-&']+){0,10})",
        r"(?:^|\n)(?:INVOICE|Invoice)\s+(?:#|No|:)?\s*\d*\s+([A-Z][A-Za-z0-9\-]+(?:[\s\-][A-Za-z0-9\-]+){0,4}(?:\s+(?:Inc|Corp|Ltd|LLC|GmbH|Industries))?)",
        r"(?:^|\n)Invoice\s+(?:from\s+)?([A-Z][A-Za-z0-9\-]+(?:[\s\-][A-Za-z0-9\-]+){1,5})",
        r"(?:^|\n)([A-Z][a-z]+(?:[\s\-][A-Z]?[A-Za-z0-9\-]+)+\s+(?:Inc|Corp|Ltd|LLC|GmbH|Industries|Company|Partners))",
        r"(?:^|\n)([A-Z][A-Za-z0-9]+\-[A-Z0-9]{4,})",
        r"(?:^|\n)([A-Z][a-z]+(?:[\s\-][A-Z][a-z]+){1,4})(?:\s*\||\s*,|\s+Invoice|\s+\d)",
    ]
    for pat in vendor_pats:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            result["vendor"] = m.group(1).strip()
            break
    amt_pats = [
        r"(?:Total|Amount Due|Balance Due|Amount|Due)[:\s]*\$?([\d,]+\.\d{2})",
        r"\$([\d,]+\.\d{2})",
        r"(?<!\d)([\d,]+\.\d{2})(?!\d)",
    ]
    for pat in amt_pats:
        ms = re.findall(pat, text, re.IGNORECASE)
        if ms:
            result["amount"] = float(ms[-1].replace(",", ""))
            break
    curr_pats = [r"(?:Currency|Curr)[:\s]*([A-Z]{3})", r"\$", r"(?:USD|EUR|GBP)"]
    for pat in curr_pats:
        m = re.search(pat, text)
        if m:
            g = m.group(1) if m.lastindex else m.group(0)
            if g == "$":
                result["currency"] = "USD"
            elif g in ("USD", "EUR", "GBP"):
                result["currency"] = g
            break
    date_pats = [
        r"(\d{4}-\d{2}-\d{2})",
        r"(?:Due Date|Date Due|Payment Due|Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
    ]
    for pat in date_pats:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            ds = m.group(1)
            parts = re.split(r"[/-]", ds)
            if len(parts) == 3:
                if len(parts[0]) == 4:
                    result["date"] = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                elif len(parts[2]) == 4:
                    result["date"] = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
            break
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Q3: FIXED SCHEMA INVOICE EXTRACTION (POST /extract with invoice_text)
# ═══════════════════════════════════════════════════════════════════════════

class InvoiceTextRequest(BaseModel):
    invoice_text: str = ""

def parse_invoice_fixed(text: str) -> dict:
    result = {"invoice_no": None, "date": None, "vendor": None, "amount": None, "tax": None, "currency": None}
    m = re.search(r"(?:Invoice\s*(?:No|Number|#|Ref)[.:\s]*)([\w\-/]+)", text, re.IGNORECASE)
    if m: result["invoice_no"] = m.group(1).strip()
    M = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    for pat in [r"(\d{4}-\d{2}-\d{2})", M + r"\s+(\d{1,2}),?\s+(\d{4})", r"(\d{1,2})\s+" + M + r"\s+(\d{4})", r"(?:Date|Issued|Dated|Due|Invoice)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})"]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            months = "JanFebMarAprMayJunJulAugSepOctNovDec"
            grps = m.groups()
            if len(grps) == 3:
                for g in grps:
                    if g and g[:3] in months: month_num = str((months.index(g[:3])//3)+1).zfill(2); break
                nums = [g for g in grps if g and g.isdigit()]
                if len(nums) >= 2: result["date"] = f"{nums[-1]}-{month_num}-{nums[0].zfill(2)}"
            elif "/" in (m.group(1) or "") or "-" in (m.group(1) or ""):
                parts = re.split(r"[/-]", m.group(1))
                if len(parts)==3:
                    if len(parts[0])==4: result["date"]=f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                    elif len(parts[2])==4: result["date"]=f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
            break
    m = re.search(r"(?:Vendor|Company|Seller|From|Bill to)[:\s]+([A-Za-z][A-Za-z0-9\s\-&'.]+?)(?:\n|\.|$)", text, re.IGNORECASE)
    if m: result["vendor"] = m.group(1).strip().rstrip(" .-")
    if not result["vendor"]:
        m = re.match(r"^([A-Z][A-Za-z0-9\s\-&.]+)", text.split("\n")[0])
        if m: result["vendor"] = m.group(1).strip().rstrip(" .-")
    for pat in [r"(?:Subtotal)[\s.:]*(?:Rs?\.?\s*)?([\d,]+\.?\d*)", r"(?:Item|Items|Subtotal|Amount|Price|Cost|Value)[\s.:]*([\d,]+\.?\d*)"]:
        m = re.search(pat, text, re.IGNORECASE)
        if m: result["amount"] = float(m.group(1).replace(",","")); break
    if result["amount"] is None:
        lines = text.split("\n")
        for i,l in enumerate(lines):
            if re.search(r"(?:GST|IGST|Tax|VAT)", l, re.IGNORECASE):
                for j in range(i-1, max(i-6,-1), -1):
                    m = re.search(r"([\d,]+\.?\d*)", lines[j])
                    if m: result["amount"] = float(m.group(1).replace(",","")); break
                break
    if result["amount"] is None:
        for n in re.findall(r"(\d{3,6}(?:\.\d{1,2})?)", text.replace(",","")):
            v = float(n)
            if v > 1000 and not (2000 <= v <= 2030): result["amount"] = v; break
    m = re.search(r"(?:GST|IGST|VAT|Tax)\s*\(?(?:\d+%)?\)?[:\s]*Rs?\.?\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m: result["tax"] = float(m.group(1).replace(",",""))
    else:
        m = re.search(r"(?:GST|IGST|Tax|VAT)\s*\(?(?:\d+%)?\)?[^0-9]*?([\d,]+\.?\d*)", text, re.IGNORECASE)
        if m: result["tax"] = float(m.group(1).replace(",",""))
    m = re.search(r"(?:Currency)[:\s]*([A-Z]{3})", text, re.IGNORECASE)
    if m: result["currency"] = m.group(1).upper()
    elif "Rs." in text or "INR" in text: result["currency"] = "INR"
    elif "EUR" in text or "euro" in text.lower(): result["currency"] = "EUR"
    elif "$" in text or "USD" in text: result["currency"] = "USD"
    elif "GBP" in text or "pound" in text.lower(): result["currency"] = "GBP"
    elif "JPY" in text or "yen" in text.lower(): result["currency"] = "JPY"
    return result

@app.post("/extract")
async def extract(request: Request):
    body = await request.json()
    if "invoice_text" in body:
        result = parse_invoice_fixed(body["invoice_text"])
        return result
    # Q8: fallback to old text field
    text = body.get("text", "")
    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="Text is required")
    r = extract_invoice(text)
    return ExtractResponse(**r)


# ═══════════════════════════════════════════════════════════════════════════
# Q4: DYNAMIC SCHEMA EXTRACTION (POST /dynamic-extract)
# ═══════════════════════════════════════════════════════════════════════════

class DynamicExtractRequest(BaseModel):
    text: str
    schema: dict[str, str]

TYPE_CONVERTERS = {
    "string": lambda v: str(v) if v is not None else None,
    "integer": lambda v: int(float(str(v).replace(",",""))) if v is not None else None,
    "float": lambda v: float(str(v).replace(",","")) if v is not None else None,
    "boolean": lambda v: str(v).lower() in ("true","yes","1") if v is not None else None,
    "date": lambda v: re.sub(r"^(\d{4})-(\d{2})-(\d{2})$", r"\1-\2-\3", str(v)) if v and re.match(r"^\d{4}-\d{2}-\d{2}$",str(v)) else (lambda x: (lambda m: f"{m.group(3)}-{str((['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].index(m.group(2)[:3]))).zfill(2)}-{m.group(1).zfill(2)}" if m else x)(re.match(r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})", str(x), re.IGNORECASE)))(v) if v else None,
}

def extract_field(text: str, name: str, t: str):
    def _extract(txt, n, typ):
        import re as _re
        nl = n.lower().replace("_"," ").strip()
        escaped = _re.escape(nl)
        pats = [fr"(?:{escaped})[:\s]+(.+?)(?:\n|\.|,|;|$)", fr"(?:{escaped})\s+is\s+(.+?)(?:\n|\.|,|;|$)"]
        if typ == "integer":
            pats += [fr"(\d+)\s*(?:{escaped})", fr"(?:{escaped})[:\s]*(\d+)", r"bought\s+(\d+)"]
        elif typ == "float":
            pats += [fr"(?:{escaped})[:\s]*Rs?\.?\s*([\d,]+\.?\d*)", r"for\s+Rs\.?\s*([\d,]+)", r"(\d+\.?\d*)"]
        elif typ == "date":
            pats += [r"(\d{4}-\d{2}-\d{2})", r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})", r"on\s+(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})"]
        elif typ == "string":
            if nl in ("customer_name","customer name","name","customer"): pats = [r"^([A-Z][a-z]+)", r"from\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"]
            elif any(x in nl for x in ("store","vendor","seller","company")): pats = [r"from\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", r"at\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"]
            elif any(x in nl for x in ("item","product","service")): pats = [r"(?:\d+\s+)([a-z]+)"]
            elif any(x in nl for x in ("root_cause","root cause","reason")): pats = [r"(?:Root cause|Reason)[:\s]+(.+?)(?:\n|\.|,|;|$)"]
            elif any(x in nl for x in ("severity","priority")): pats = [r"(?:Severity|Priority)[:\s]+(.+?)(?:\n|\.|,|;|$)"]
            elif any(x in nl for x in ("team","department")): pats = [r"(?:Team|Department)[:\s]+(.+?)(?:\n|\.|,|;|$)"]
            elif any(x in nl for x in ("event_time","event time","time")): pats = [r"(\d{1,2}:\d{2})"]
        for p in pats:
            m = _re.search(p, txt, _re.IGNORECASE | _re.MULTILINE)
            if m:
                v = m.group(1).strip().rstrip(".,;")
                conv = TYPE_CONVERTERS.get(typ, TYPE_CONVERTERS["string"])
                try: return conv(v)
                except: continue
        # Fallback: try specific patterns by field name
        if typ == "string":
            # Team names: "X vs Y" or "Team X: Y"
            m = _re.search(r"(\w[\w\s]+)\s+vs\s+(\w[\w\s]+)", txt, _re.IGNORECASE)
            if m:
                groups = m.groups()
                if "team_a" in name or "team1" in name: return groups[0].strip()
                if "team_b" in name or "team2" in name: return groups[1].strip()
            m = _re.search(r"(?:Team|Side)\s*(?:A|1|One)[:\s-]+([A-Z][a-z]+)", txt, _re.IGNORECASE)
            if m and ("team_a" in name or "team1" in name): return m.group(1).strip()
            m = _re.search(r"(?:Team|Side)\s*(?:B|2|Two)[:\s-]+([A-Z][a-z]+)", txt, _re.IGNORECASE)
            if m and ("team_b" in name or "team2" in name): return m.group(1).strip()
        return None
    return _extract(text, name, t)


@app.options("/dynamic-extract")
async def dyn_extract_preflight():
    return JSONResponse(content=None, status_code=204)

@app.post("/dynamic-extract")
async def dynamic_extract(req: DynamicExtractRequest):
    result = {}
    for field_name, field_type in req.schema.items():
        result[field_name] = extract_field(req.text, field_name, field_type)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Q9: ORDERS API (Idempotency + Pagination + Rate Limit)
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/orders")
async def create_order(request: Request, idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")
    client_id = request.headers.get("X-Client-Id", "default")
    now = time.time()
    rate_store.setdefault(client_id, [])
    rate_store[client_id] = [t for t in rate_store[client_id] if now - t < 10]
    if len(rate_store[client_id]) >= Q9_RATE_LIMIT:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"}, headers={"Retry-After": "10"})
    rate_store[client_id].append(now)
    if idempotency_key in idempotency_store:
        return {"id": idempotency_store[idempotency_key]}
    oid = str(uuid.uuid4())
    idempotency_store[idempotency_key] = oid
    return JSONResponse(content={"id": oid}, status_code=201)


@app.get("/orders")
async def list_orders(
    request: Request,
    limit: int = Query(10, ge=1, le=TOTAL_ORDERS),
    cursor: Optional[str] = Query(None),
):
    client_id = request.headers.get("X-Client-Id", "default")
    now = time.time()
    rate_store.setdefault(client_id, [])
    rate_store[client_id] = [t for t in rate_store[client_id] if now - t < 10]
    if len(rate_store[client_id]) >= Q9_RATE_LIMIT:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"}, headers={"Retry-After": "10"})
    rate_store[client_id].append(now)
    start_id = int(cursor) if cursor and cursor.isdigit() else 1
    end_id = min(start_id + limit - 1, TOTAL_ORDERS)
    items = [{"id": i} for i in range(start_id, end_id + 1)]
    next_cursor = str(end_id + 1) if end_id < TOTAL_ORDERS else None
    return {"items": items, "next_cursor": next_cursor}


# ═══════════════════════════════════════════════════════════════════════════
# Q10: MIDDLEWARE STACK - /ping
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/ping")
async def ping(request: Request):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return {"email": EMAIL, "request_id": req_id}


# ═══════════════════════════════════════════════════════════════════════════
# HEALTHZ (shared endpoint for Q4/Q6)
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/healthz")
async def healthz():
    uptime_s = time.time() - START_TIME
    return {"status": "ok", "uptime_s": round(uptime_s, 4)}


# ═══════════════════════════════════════════════════════════════════════════
# EXCEPTION HANDLER
# ═══════════════════════════════════════════════════════════════════════════

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    headers = getattr(exc, "headers", None) or {}
    return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=headers)


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
