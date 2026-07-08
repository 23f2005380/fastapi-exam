import os
import re
from fastapi import FastAPI, Query
from typing import Optional

EMAIL = "23f2005380@ds.study.iitm.ac.in"

app = FastAPI()

# 1. Defaults (lowest precedence)
defaults = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

# 2. config.development.yaml
config_yaml = {
    "log_level": "info",
    "api_key": "key-nnlplu35uf",
}


def parse_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes", "on")
    return False


def load_dotenv(path=".env"):
    """Load a .env file and return a dict."""
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return env


def load_os_env():
    """Load APP_* prefixed OS env vars, stripping the prefix."""
    env = {}
    for k, v in os.environ.items():
        if k.startswith("APP_"):
            key = k[4:].lower()  # strip APP_ prefix
            env[key] = v
    return env


@app.middleware("http")
async def cors_middleware(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response


@app.get("/effective-config")
async def effective_config(set: Optional[list[str]] = Query(None, alias="set")):
    # Merge low to high: defaults -> yaml -> .env -> os env -> CLI overrides

    # Start with defaults
    merged = dict(defaults)

    # Apply YAML overrides
    for k, v in config_yaml.items():
        merged[k] = v

    # Apply .env overrides
    dotenv = load_dotenv()
    if "APP_LOG_LEVEL" in dotenv:
        merged["log_level"] = dotenv["APP_LOG_LEVEL"]
    if "NUM_WORKERS" in dotenv:
        merged["workers"] = int(dotenv["NUM_WORKERS"])

    # Apply OS env (APP_* prefix)
    osenv = load_os_env()
    for k, v in osenv.items():
        merged[k] = v

    # Apply CLI overrides (highest precedence)
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
