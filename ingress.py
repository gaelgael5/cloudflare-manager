import os
import shutil
import subprocess
import yaml
from datetime import datetime, timedelta
from config import CONFIG_YML, BAK_DIR, BAK_RETENTION_DAYS, CLOUDFLARED_SVC


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def _backup_config():
    os.makedirs(BAK_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    bak_path = os.path.join(BAK_DIR, f"config.yml.{ts}.bak")
    shutil.copy2(CONFIG_YML, bak_path)
    _purge_old_backups()
    return bak_path


def _purge_old_backups():
    cutoff = datetime.now() - timedelta(days=BAK_RETENTION_DAYS)
    for fname in os.listdir(BAK_DIR):
        if not fname.endswith(".bak"):
            continue
        fpath = os.path.join(BAK_DIR, fname)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime < cutoff:
            os.remove(fpath)


# ---------------------------------------------------------------------------
# Lecture / écriture config.yml
# ---------------------------------------------------------------------------

def _read_config() -> dict:
    with open(CONFIG_YML, "r") as f:
        return yaml.safe_load(f) or {}


def _write_config(data: dict):
    _backup_config()
    with open(CONFIG_YML, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def _restart_cloudflared() -> str:
    result = subprocess.run(
        ["systemctl", "restart", CLOUDFLARED_SVC],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"systemctl restart failed: {result.stderr.strip()}")
    return "restarted"


# ---------------------------------------------------------------------------
# Helpers sur les règles ingress
# ---------------------------------------------------------------------------

def _get_rules(data: dict) -> list:
    return data.get("ingress", [])


def _catchall_rule() -> dict:
    return {"service": "http_status:404"}


def _is_catchall(rule: dict) -> bool:
    return "hostname" not in rule


def _find_rule_index(rules: list, hostname: str) -> int | None:
    for i, rule in enumerate(rules):
        if rule.get("hostname") == hostname:
            return i
    return None


def _clean_rule(payload: dict) -> dict:
    """Supprime les clés None récursivement."""
    result = {}
    for k, v in payload.items():
        if v is None:
            continue
        if isinstance(v, dict):
            cleaned = _clean_rule(v)
            if cleaned:
                result[k] = cleaned
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Opérations publiques
# ---------------------------------------------------------------------------

def list_ingress() -> dict:
    return _read_config()


def get_ingress(hostname: str) -> dict:
    data = _read_config()
    rules = _get_rules(data)
    idx = _find_rule_index(rules, hostname)
    if idx is None:
        return None
    return rules[idx]


def add_ingress(payload: dict) -> dict:
    hostname = payload.get("hostname")
    if not hostname:
        raise ValueError("hostname is required")

    data = _read_config()
    rules = _get_rules(data)

    if _find_rule_index(rules, hostname) is not None:
        raise ValueError(f"Rule for '{hostname}' already exists. Use PUT to update.")

    # Sépare les catch-all des règles nommées
    named  = [r for r in rules if not _is_catchall(r)]
    others = [r for r in rules if _is_catchall(r)]

    new_rule = _clean_rule(payload)
    named.append(new_rule)

    # Garantit toujours un catch-all en fin de fichier
    if not others:
        others = [_catchall_rule()]

    data["ingress"] = named + others
    _write_config(data)
    _restart_cloudflared()
    return new_rule


def update_ingress(hostname: str, payload: dict) -> dict:
    data = _read_config()
    rules = _get_rules(data)
    idx = _find_rule_index(rules, hostname)
    if idx is None:
        raise ValueError(f"Rule for '{hostname}' not found.")

    payload["hostname"] = hostname
    new_rule = _clean_rule(payload)
    rules[idx] = new_rule

    data["ingress"] = rules
    _write_config(data)
    _restart_cloudflared()
    return new_rule


def delete_ingress(hostname: str) -> dict:
    data = _read_config()
    rules = _get_rules(data)
    idx = _find_rule_index(rules, hostname)
    if idx is None:
        raise ValueError(f"Rule for '{hostname}' not found.")

    removed = rules.pop(idx)

    # Garantit toujours un catch-all
    named  = [r for r in rules if not _is_catchall(r)]
    others = [r for r in rules if _is_catchall(r)]
    if not others:
        others = [_catchall_rule()]

    data["ingress"] = named + others
    _write_config(data)
    _restart_cloudflared()
    return removed
