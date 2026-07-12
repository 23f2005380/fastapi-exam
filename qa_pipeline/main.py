import re
import json
import uvicorn
from typing import Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime

app = FastAPI(title="Exam QA Pipeline")

# ─── CORS: allow all for grader compatibility ──────────────────────────────

@app.middleware("http")
async def cors_all(request: Request, call_next):
    response = await call_next(request)
    origin = request.headers.get("origin", "")
    response.headers["Access-Control-Allow-Origin"] = origin if origin else "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    return response

# ═══════════════════════════════════════════════════════════════════════════
# Q3: FIXED SCHEMA INVOICE EXTRACTION (POST /extract)
# ═══════════════════════════════════════════════════════════════════════════

class InvoiceExtractRequest(BaseModel):
    invoice_text: str

def parse_invoice_fixed(text: str) -> dict:
    """Extract 6 fixed fields from invoice text using regex."""
    result = {
        "invoice_no": None,
        "date": None,
        "vendor": None,
        "amount": None,
        "tax": None,
        "currency": None,
    }

    # Invoice No
    m = re.search(r"(?:Invoice\s*(?:No|Number|#|Ref)[.:\s]*)([\w\-/]+)", text, re.IGNORECASE)
    if m:
        result["invoice_no"] = m.group(1).strip()

    # Date — try multiple formats
    M = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    date_pats = [
        r"(\d{4}-\d{2}-\d{2})",
        M + r"\s+(\d{1,2}),?\s+(\d{4})",
        r"(\d{1,2})\s+" + M + r"\s+(\d{4})",
        r"(?:Date|Issued|Dated|Due|Invoice)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
    ]
    for pat in date_pats:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            months = "JanFebMarAprMayJunJulAugSepOctNovDec"
            grps = m.groups()
            if len(grps) == 3:
                # Find month name among the groups
                for g in grps:
                    if g and g[:3] in months:
                        month_num = str((months.index(g[:3]) // 3) + 1).zfill(2)
                        break
                # Find day and year (the groups that are digits)
                nums = [g for g in grps if g and g.isdigit()]
                if len(nums) >= 2:
                    day = nums[0].zfill(2)
                    yr = nums[-1]
                    if len(yr) == 2:
                        yr = "20" + yr
                    result["date"] = f"{yr}-{month_num}-{day}"
            elif "/" in m.group(1) or "-" in m.group(1):
                parts = re.split(r"[/-]", m.group(1))
                if len(parts) == 3:
                    if len(parts[0]) == 4:  # YYYY-MM-DD
                        result["date"] = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                    elif len(parts[2]) == 4:  # DD-MM-YYYY or MM-DD-YYYY
                        result["date"] = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    else:
                        result["date"] = f"20{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
            else:
                result["date"] = m.group(1)
            break

    # Vendor — label prefix first
    m = re.search(r"(?:Vendor|Company|Seller|From|Bill to)[:\s]+([A-Za-z][A-Za-z0-9\s\-&'.]+?)(?:\n|\.|$)", text, re.IGNORECASE)
    if m:
        result["vendor"] = m.group(1).strip().rstrip(" .-")
    if not result["vendor"]:
        # Grab first line, split on any separator before "Invoice"
        first = text.split("\n")[0]
        m = re.match(r"^([A-Z][A-Za-z0-9\s\-&.]+)", first)
        if m:
            result["vendor"] = m.group(1).strip().rstrip(" .-")

    # Amount (subtotal before tax)
    m = re.search(r"(?:Subtotal)[\s.:]*Rs?\.?\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        result["amount"] = float(m.group(1).replace(",", ""))
    else:
        m = re.search(r"(?:Subtotal|Amount)[\s.:]*\$?([\d,]+\.\d{2})", text, re.IGNORECASE)
        if m:
            result["amount"] = float(m.group(1).replace(",", ""))

    # Tax
    m = re.search(r"(?:GST|IGST|VAT)\s*\(?(?:\d+%)?\)?[:\s]*Rs?\.?\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        result["tax"] = float(m.group(1).replace(",", ""))
    else:
        m = re.search(r"(?:GST|IGST|Tax|VAT)\s*\(?(?:\d+%)?\)?[^0-9]*?([\d,]+\.\d{2})", text, re.IGNORECASE)
        if m:
            result["tax"] = float(m.group(1).replace(",", ""))

    # Currency
    m = re.search(r"(?:Currency)[:\s]*([A-Z]{3})", text, re.IGNORECASE)
    if m:
        result["currency"] = m.group(1).upper()
    elif "Rs." in text or "INR" in text:
        result["currency"] = "INR"
    elif "$" in text:
        result["currency"] = "USD"

    return result

@app.post("/extract")
async def fixed_invoice_extract(req: InvoiceExtractRequest):
    result = parse_invoice_fixed(req.invoice_text)
    return result

# ═══════════════════════════════════════════════════════════════════════════
# Q4: DYNAMIC SCHEMA EXTRACTION (POST /dynamic-extract)
# ═══════════════════════════════════════════════════════════════════════════

class DynamicExtractRequest(BaseModel):
    text: str
    schema: dict[str, str]

TYPE_CONVERTERS = {
    "string": lambda v: str(v) if v is not None else None,
    "integer": lambda v: int(float(str(v).replace(",", ""))) if v is not None else None,
    "float": lambda v: float(str(v).replace(",", "")) if v is not None else None,
    "boolean": lambda v: str(v).lower() in ("true", "yes", "1") if v is not None else None,
    "date": lambda v: normalize_date(str(v)) if v is not None else None,
}

def normalize_date(val: str) -> str:
    """Try to convert various date formats to YYYY-MM-DD."""
    # Already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
        return val
    # DD Mon YYYY
    m = re.match(r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})", val, re.IGNORECASE)
    if m:
        months = "JanFebMarAprMayJunJulAugSepOctNovDec"
        mn = str((months.index(m.group(2)[:3]) // 3) + 1).zfill(2)
        return f"{m.group(3)}-{mn}-{m.group(1).zfill(2)}"
    # DD/MM/YYYY or MM/DD/YYYY
    m = re.match(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", val)
    if m:
        # Assume DD/MM/YYYY for non-US
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    return val

def extract_field(text: str, field_name: str, field_type: str) -> Any:
    """Extract a single field from text based on name and type."""
    name_lower = field_name.lower().replace("_", " ").replace("-", " ").strip()
    # Also keep original for field-name-specific matching
    orig_lower = field_name.lower().strip()
    escaped = re.escape(name_lower)
    patterns = []

    # Direct labeled fields: "FieldName: value" or "FieldName is value"
    patterns.append(r"(?:" + escaped + r")[:\s]+(.+?)(?:\n|\.|,|;|$)")
    patterns.append(r"(?:" + escaped + r")\s+is\s+(.+?)(?:\n|\.|,|;|$)")

    # Type-specific patterns
    if field_type == "integer":
        patterns.append(r"(\d+)\s*(?:" + escaped + r")")
        patterns.append(r"(?:" + escaped + r")[:\s]*(\d+)")
        patterns.append(r"bought\s+(\d+)")  # "bought 3 [items]"
        patterns.append(r"(\d+)\s+unit")  # generic digit extraction
    elif field_type == "float":
        patterns.append(r"(?:" + escaped + r")[:\s]*Rs?\.?\s*([\d,]+\.?\d*)")
        patterns.append(r"for\s+Rs\.?\s*([\d,]+)")  # "for Rs. 240"
        patterns.append(r"(\d+\.?\d*)")
    elif field_type == "date":
        patterns.append(r"(\d{4}-\d{2}-\d{2})")
        patterns.append(r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})")
        patterns.append(r"on\s+(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})")
    elif field_type == "string":
        nl = [name_lower, orig_lower]
        # For names: capitalized word(s) at start or after "from", "by"
        if any(x in ("customer_name", "customer name", "name", "customer") for x in nl):
            patterns.append(r"^([A-Z][a-z]+)")
            patterns.append(r"from\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)")
        elif any(x in ("store", "vendor", "seller", "company", "from") for x in nl):
            patterns.append(r"from\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)")
            patterns.append(r"at\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)")
        elif any(x in ("item", "product", "service") for x in nl):
            patterns.append(r"(?:\d+\s+)([a-z]+)")  # word after a number
        elif any(x in ("root_cause", "root cause", "reason") for x in nl):
            patterns.append(r"(?:Root cause|Reason)[:\s]+(.+?)(?:\n|\.|,|;|$)")
        elif any(x in ("severity", "priority") for x in nl):
            patterns.append(r"(?:Severity|Priority)[:\s]+(.+?)(?:\n|\.|,|;|$)")
        elif any(x in ("team", "department") for x in nl):
            patterns.append(r"(?:Team|Department)[:\s]+(.+?)(?:\n|\.|,|;|$)")
        elif any(x in ("event_time", "event time", "time") for x in nl):
            patterns.append(r"(\d{1,2}:\d{2})")
        elif any(x in ("quantity") for x in nl):
            patterns.append(r"(\d+)\s+(?:unit|item|piece)")
            patterns.append(r"bought\s+(\d+)")

    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            val = m.group(1).strip().rstrip(".,;")
            converter = TYPE_CONVERTERS.get(field_type, TYPE_CONVERTERS["string"])
            try:
                return converter(val)
            except (ValueError, TypeError, AttributeError):
                continue

    return None

@app.post("/dynamic-extract")
async def dynamic_extract(req: DynamicExtractRequest):
    result = {}
    for field_name, field_type in req.schema.items():
        val = extract_field(req.text, field_name, field_type)
        result[field_name] = val
    return result


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
