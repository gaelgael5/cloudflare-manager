"""
Tests de l'API cloudflare-manager.
Utilise un config.yml temporaire et des mocks pour systemctl.
"""
import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Setup environnement de test avant import des modules
# ---------------------------------------------------------------------------
TEMP_DIR = tempfile.mkdtemp()
CONFIG_YML  = os.path.join(TEMP_DIR, "config.yml")
KEYS_FILE   = os.path.join(TEMP_DIR, "keys.json")
BAK_DIR     = os.path.join(TEMP_DIR, "backups")

os.environ["CONFIG_YML"]  = CONFIG_YML
os.environ["KEYS_FILE"]   = KEYS_FILE
os.environ["BAK_DIR"]     = BAK_DIR
os.environ["BAK_RETENTION_DAYS"] = "30"
os.environ["API_PORT"]    = "8000"
os.environ["CLOUDFLARED_SVC"] = "cloudflared"
os.environ["TESTING"]     = "1"

# Config.yml initial
INITIAL_CONFIG = """tunnel: test-tunnel-id
credentials-file: /root/.cloudflared/test-tunnel-id.json
ingress:
  - hostname: existing.yoops.org
    service: http://192.168.10.10:3000
  - service: http_status:404
"""

# API key de test
TEST_KEY   = "test-api-key-1234"
TEST_LABEL = "test-client"

def _reset_state():
    """Réinitialise config.yml et keys.json avant chaque test."""
    os.makedirs(BAK_DIR, exist_ok=True)
    with open(CONFIG_YML, "w") as f:
        f.write(INITIAL_CONFIG)
    with open(KEYS_FILE, "w") as f:
        json.dump([{"key": TEST_KEY, "label": TEST_LABEL, "active": True}], f)

# Import après setup des env vars
import importlib, config as cfg
importlib.reload(cfg)

from main import app

client = TestClient(app)
AUTH   = {"Authorization": f"Bearer {TEST_KEY}"}
LOCAL  = {"x-forwarded-for": "127.0.0.1"}


def mock_restart():
    """Mock systemctl restart — ne fait rien."""
    pass


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_no_auth_returns_401():
    _reset_state()
    r = client.get("/ingress")
    assert r.status_code == 401


def test_invalid_key_returns_401():
    _reset_state()
    r = client.get("/ingress", headers={"Authorization": "Bearer wrong-key"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /ingress
# ---------------------------------------------------------------------------

def test_list_ingress():
    _reset_state()
    r = client.get("/ingress", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert "ingress" in data
    assert len(data["ingress"]) == 2  # 1 règle + catch-all


def test_get_existing_rule():
    _reset_state()
    r = client.get("/ingress/existing.yoops.org", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["hostname"] == "existing.yoops.org"
    assert r.json()["service"] == "http://192.168.10.10:3000"


def test_get_unknown_rule_returns_404():
    _reset_state()
    r = client.get("/ingress/unknown.yoops.org", headers=AUTH)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /ingress
# ---------------------------------------------------------------------------

def test_add_rule():
    _reset_state()
    with patch("ingress._restart_cloudflared", side_effect=mock_restart):
        r = client.post("/ingress", headers=AUTH, json={
            "hostname": "new.yoops.org",
            "service": "http://192.168.10.20:8080"
        })
    assert r.status_code == 201
    assert r.json()["hostname"] == "new.yoops.org"

    # Vérifie que la règle est bien dans le fichier
    r2 = client.get("/ingress/new.yoops.org", headers=AUTH)
    assert r2.status_code == 200


def test_add_rule_with_origin_request():
    _reset_state()
    with patch("ingress._restart_cloudflared", side_effect=mock_restart):
        r = client.post("/ingress", headers=AUTH, json={
            "hostname": "secure.yoops.org",
            "service": "https://192.168.10.30:8443",
            "originRequest": {
                "noTLSVerify": True,
                "connectTimeout": "10s"
            }
        })
    assert r.status_code == 201
    data = r.json()
    assert data["originRequest"]["noTLSVerify"] is True
    assert data["originRequest"]["connectTimeout"] == "10s"


def test_add_rule_null_properties_excluded():
    _reset_state()
    with patch("ingress._restart_cloudflared", side_effect=mock_restart):
        r = client.post("/ingress", headers=AUTH, json={
            "hostname": "minimal.yoops.org",
            "service": "http://192.168.10.40:9000",
            "path": None,
            "originRequest": None
        })
    assert r.status_code == 201
    data = r.json()
    assert "path" not in data
    assert "originRequest" not in data


def test_add_duplicate_rule_returns_409():
    _reset_state()
    with patch("ingress._restart_cloudflared", side_effect=mock_restart):
        r = client.post("/ingress", headers=AUTH, json={
            "hostname": "existing.yoops.org",
            "service": "http://192.168.10.10:3000"
        })
    assert r.status_code == 409


def test_catchall_always_last():
    _reset_state()
    with patch("ingress._restart_cloudflared", side_effect=mock_restart):
        client.post("/ingress", headers=AUTH, json={
            "hostname": "a.yoops.org",
            "service": "http://192.168.10.50:1000"
        })
        client.post("/ingress", headers=AUTH, json={
            "hostname": "b.yoops.org",
            "service": "http://192.168.10.51:2000"
        })

    r = client.get("/ingress", headers=AUTH)
    rules = r.json()["ingress"]
    last = rules[-1]
    assert "hostname" not in last, "Le catch-all doit toujours être en dernière position"


# ---------------------------------------------------------------------------
# PUT /ingress
# ---------------------------------------------------------------------------

def test_update_rule():
    _reset_state()
    with patch("ingress._restart_cloudflared", side_effect=mock_restart):
        r = client.put("/ingress/existing.yoops.org", headers=AUTH, json={
            "hostname": "existing.yoops.org",
            "service": "http://192.168.10.10:9999"
        })
    assert r.status_code == 200
    assert r.json()["service"] == "http://192.168.10.10:9999"


def test_update_unknown_rule_returns_404():
    _reset_state()
    with patch("ingress._restart_cloudflared", side_effect=mock_restart):
        r = client.put("/ingress/ghost.yoops.org", headers=AUTH, json={
            "hostname": "ghost.yoops.org",
            "service": "http://192.168.10.99:1234"
        })
    assert r.status_code == 404


def test_update_removes_absent_properties():
    """Un PUT sans originRequest doit supprimer originRequest si présent."""
    _reset_state()
    # D'abord on ajoute une règle avec originRequest
    with patch("ingress._restart_cloudflared", side_effect=mock_restart):
        client.post("/ingress", headers=AUTH, json={
            "hostname": "tls.yoops.org",
            "service": "https://192.168.10.60:443",
            "originRequest": {"noTLSVerify": True}
        })
        # Puis on la met à jour sans originRequest
        r = client.put("/ingress/tls.yoops.org", headers=AUTH, json={
            "hostname": "tls.yoops.org",
            "service": "https://192.168.10.60:443"
        })
    assert r.status_code == 200
    assert "originRequest" not in r.json()


# ---------------------------------------------------------------------------
# DELETE /ingress
# ---------------------------------------------------------------------------

def test_delete_rule():
    _reset_state()
    with patch("ingress._restart_cloudflared", side_effect=mock_restart):
        r = client.delete("/ingress/existing.yoops.org", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["deleted"] == "existing.yoops.org"

    r2 = client.get("/ingress/existing.yoops.org", headers=AUTH)
    assert r2.status_code == 404


def test_delete_unknown_rule_returns_404():
    _reset_state()
    with patch("ingress._restart_cloudflared", side_effect=mock_restart):
        r = client.delete("/ingress/ghost.yoops.org", headers=AUTH)
    assert r.status_code == 404


def test_delete_preserves_catchall():
    _reset_state()
    with patch("ingress._restart_cloudflared", side_effect=mock_restart):
        client.delete("/ingress/existing.yoops.org", headers=AUTH)

    r = client.get("/ingress", headers=AUTH)
    rules = r.json()["ingress"]
    last = rules[-1]
    assert "hostname" not in last


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def test_backup_created_on_add():
    _reset_state()
    with patch("ingress._restart_cloudflared", side_effect=mock_restart):
        client.post("/ingress", headers=AUTH, json={
            "hostname": "bak-test.yoops.org",
            "service": "http://192.168.10.70:5000"
        })
    baks = [f for f in os.listdir(BAK_DIR) if f.endswith(".bak")]
    assert len(baks) >= 1


# ---------------------------------------------------------------------------
# Admin — localhost only
# ---------------------------------------------------------------------------

def test_admin_list_keys_localhost():
    _reset_state()
    r = client.get("/admin/keys")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # Les clés ne sont pas exposées
    for entry in data:
        assert "key" not in entry


def test_admin_create_key_localhost():
    _reset_state()
    r = client.post("/admin/keys", json={"label": "new-client"})
    assert r.status_code == 200
    data = r.json()
    assert "key" in data
    assert data["label"] == "new-client"
    assert data["active"] is True


def test_admin_create_duplicate_key_returns_409():
    _reset_state()
    client.post("/admin/keys", json={"label": "dup-client"})
    r = client.post("/admin/keys", json={"label": "dup-client"})
    assert r.status_code == 409


def test_admin_delete_key():
    _reset_state()
    client.post("/admin/keys", json={"label": "to-delete"})
    r = client.delete("/admin/keys/to-delete")
    assert r.status_code == 200


def test_admin_deactivate_and_activate_key():
    _reset_state()
    client.post("/admin/keys", json={"label": "toggle-client"})

    r = client.patch("/admin/keys/toggle-client/deactivate")
    assert r.status_code == 200
    assert r.json()["active"] is False

    # La clé désactivée ne doit plus authentifier
    with open(KEYS_FILE) as f:
        keys = json.load(f)
    toggle_key = next(k["key"] for k in keys if k["label"] == "toggle-client")
    r2 = client.get("/ingress", headers={"Authorization": f"Bearer {toggle_key}"})
    assert r2.status_code == 401

    r3 = client.patch("/admin/keys/toggle-client/activate")
    assert r3.status_code == 200
    assert r3.json()["active"] is True
