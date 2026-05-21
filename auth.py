import json
import os
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import KEYS_FILE

security = HTTPBearer()


def _load_keys() -> list[dict]:
    if not os.path.exists(KEYS_FILE):
        return []
    with open(KEYS_FILE, "r") as f:
        return json.load(f)


def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    keys = _load_keys()
    for entry in keys:
        if entry.get("active", False) and entry.get("key") == token:
            return entry["label"]
    raise HTTPException(status_code=401, detail="Invalid or inactive API key")
