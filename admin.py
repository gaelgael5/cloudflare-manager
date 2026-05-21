import json
import os
import secrets
from fastapi import APIRouter, HTTPException, Request
from config import KEYS_FILE

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_localhost(request: Request):
    if os.getenv("TESTING") == "1":
        return
    client_ip = request.client.host
    if client_ip not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="Admin endpoints are localhost only")


def _load_keys() -> list[dict]:
    if not os.path.exists(KEYS_FILE):
        return []
    with open(KEYS_FILE, "r") as f:
        return json.load(f)


def _save_keys(keys: list[dict]):
    os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)


@router.get("/keys")
def list_keys(request: Request):
    _require_localhost(request)
    keys = _load_keys()
    # Ne retourne jamais la valeur de la clé
    return [{"label": k["label"], "active": k["active"]} for k in keys]


@router.post("/keys")
def create_key(request: Request, body: dict):
    _require_localhost(request)
    label = body.get("label", "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="label is required")

    keys = _load_keys()
    if any(k["label"] == label for k in keys):
        raise HTTPException(status_code=409, detail=f"Label '{label}' already exists")

    new_key = secrets.token_urlsafe(32)
    keys.append({"key": new_key, "label": label, "active": True})
    _save_keys(keys)
    # Seule occasion où la clé est retournée en clair
    return {"label": label, "key": new_key, "active": True}


@router.delete("/keys/{label}")
def delete_key(label: str, request: Request):
    _require_localhost(request)
    keys = _load_keys()
    updated = [k for k in keys if k["label"] != label]
    if len(updated) == len(keys):
        raise HTTPException(status_code=404, detail=f"Label '{label}' not found")
    _save_keys(updated)
    return {"deleted": label}


@router.patch("/keys/{label}/deactivate")
def deactivate_key(label: str, request: Request):
    _require_localhost(request)
    keys = _load_keys()
    for k in keys:
        if k["label"] == label:
            k["active"] = False
            _save_keys(keys)
            return {"label": label, "active": False}
    raise HTTPException(status_code=404, detail=f"Label '{label}' not found")


@router.patch("/keys/{label}/activate")
def activate_key(label: str, request: Request):
    _require_localhost(request)
    keys = _load_keys()
    for k in keys:
        if k["label"] == label:
            k["active"] = True
            _save_keys(keys)
            return {"label": label, "active": True}
    raise HTTPException(status_code=404, detail=f"Label '{label}' not found")
