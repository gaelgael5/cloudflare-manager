from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from auth import verify_api_key
from ingress import (
    list_ingress,
    get_ingress,
    add_ingress,
    update_ingress,
    delete_ingress,
)
from admin import router as admin_router

app = FastAPI(
    title="Cloudflare Manager",
    description="API locale pour gérer le fichier config.yml de cloudflared",
    version="1.0.0",
)

app.include_router(admin_router)


# ---------------------------------------------------------------------------
# Routes /ingress
# ---------------------------------------------------------------------------

@app.get("/ingress", tags=["ingress"])
def route_list_ingress(_: str = Depends(verify_api_key)):
    """Retourne le contenu complet du fichier config.yml."""
    return list_ingress()


@app.get("/ingress/{hostname:path}", tags=["ingress"])
def route_get_ingress(hostname: str, _: str = Depends(verify_api_key)):
    """Retourne la règle ingress pour un hostname donné."""
    rule = get_ingress(hostname)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"No rule found for '{hostname}'")
    return rule


@app.post("/ingress", status_code=201, tags=["ingress"])
def route_add_ingress(payload: dict, _: str = Depends(verify_api_key)):
    """
    Ajoute une règle ingress.
    Les propriétés absentes ou null ne sont pas écrites dans le fichier.
    """
    try:
        rule = add_ingress(payload)
        return rule
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/ingress/{hostname:path}", tags=["ingress"])
def route_update_ingress(hostname: str, payload: dict, _: str = Depends(verify_api_key)):
    """
    Remplace entièrement la règle ingress pour un hostname.
    Les propriétés absentes ou null sont supprimées du fichier.
    """
    try:
        rule = update_ingress(hostname, payload)
        return rule
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/ingress/{hostname:path}", tags=["ingress"])
def route_delete_ingress(hostname: str, _: str = Depends(verify_api_key)):
    """Supprime la règle ingress pour un hostname."""
    try:
        removed = delete_ingress(hostname)
        return {"deleted": hostname, "rule": removed}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Health check (pas d'auth)
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}
