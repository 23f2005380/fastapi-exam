import re
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

EMAIL = "23f2005380@ds.study.iitm.ac.in"

app = FastAPI()


class ExtractRequest(BaseModel):
    text: str


class ExtractResponse(BaseModel):
    vendor: str
    amount: float
    currency: str
    date: str


@app.middleware("http")
async def cors_middleware(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


def extract_invoice(text: str) -> dict:
    """Extract invoice fields from text using regex patterns."""
    result = {
        "vendor": "",
        "amount": 0.0,
        "currency": "USD",
        "date": "",
    }

    # Vendor: look for common patterns
    vendor_patterns = [
        r"(?:Vendor|Company|Seller|From|Bill from|Supplier)[:\s]+(.+)",
        r"(?:^|\n)([A-Z][A-Za-z0-9\s\-\.]+(?:Inc|Corp|Ltd|LLC|GmbH|Industries|Company))",
        r"(?:^|\n)([A-Z][a-z]+(?:[\s\-][A-Z][a-z]+)+(?:\s+(?:Inc|Corp|Ltd|LLC|GmbH|Industries))?)",
    ]
    for pattern in vendor_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            result["vendor"] = match.group(1).strip()
            break

    # If no vendor found, try to find the first capitalized business name
    if not result["vendor"]:
        match = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s(?:Inc|Corp|Ltd|LLC|GmbH|Industries))", text)
        if match:
            result["vendor"] = match.group(1).strip()

    # Amount: look for total/amount/due patterns
    amount_patterns = [
        r"(?:Total|Amount Due|Balance Due|Amount|Due)[:\s]*\$?([\d,]+\.?\d*)",
        r"\$([\d,]+\.\d{2})",
        r"(?:total|amount)[^$]*\$?([\d,]+\.?\d*)",
        r"([\d,]+\.\d{2})",
    ]
    for pattern in amount_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            val = float(matches[-1].replace(",", ""))
            result["amount"] = val
            break

    # Currency
    currency_patterns = [
        r"(?:Currency|Curr)[:\s]*([A-Z]{3})",
        r"\$",
        r"(?:USD|EUR|GBP)",
    ]
    for pattern in currency_patterns:
        match = re.search(pattern, text)
        if match:
            g = match.group(0) if pattern == r"\$" else match.group(1) if match.lastindex else match.group(0)
            if g == "$":
                result["currency"] = "USD"
            elif g in ("USD", "EUR", "GBP"):
                result["currency"] = g
            break

    # Date: look for dates in various formats
    date_patterns = [
        r"(\d{4}-\d{2}-\d{2})",
        r"(?:Due Date|Date Due|Payment Due|Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            # Normalize to YYYY-MM-DD
            parts = re.split(r"[/-]", date_str)
            if len(parts) == 3:
                if len(parts[0]) == 4:  # YYYY-MM-DD
                    result["date"] = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                elif len(parts[2]) == 4:  # MM/DD/YYYY or DD/MM/YYYY
                    result["date"] = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
            break

    return result


@app.post("/extract")
async def extract(req: ExtractRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=422, detail="Text is required")

    result = extract_invoice(req.text)
    return ExtractResponse(**result)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
