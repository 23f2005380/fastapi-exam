from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import jwt

EMAIL = "23f2005380@ds.study.iitm.ac.in"
ISSUER = "https://idp.exam.local"
AUDIENCE = "tds-zeuep4ms.apps.exam.local"

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""

app = FastAPI()


class TokenRequest(BaseModel):
    token: str


class VerifyResponse(BaseModel):
    valid: bool
    email: str | None = None
    sub: str | None = None
    aud: str | None = None


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


@app.post("/verify")
async def verify_token(req: TokenRequest):
    try:
        payload = jwt.decode(
            req.token,
            PUBLIC_KEY,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "require": ["exp", "iss", "aud"],
            },
        )
        return {
            "valid": True,
            "email": payload.get("email", ""),
            "sub": payload.get("sub", ""),
            "aud": payload.get("aud", ""),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"valid": False})
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=401, detail={"valid": False})
    except jwt.InvalidIssuerError:
        raise HTTPException(status_code=401, detail={"valid": False})
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail={"valid": False})


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"valid": False},
    )
