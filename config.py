import os
from dotenv import load_dotenv

load_dotenv("/etc/cloudflare-manager/.env")

CONFIG_YML         = os.getenv("CONFIG_YML",  "/etc/cloudflared/config.yml")
KEYS_FILE          = os.getenv("KEYS_FILE",   "/etc/cloudflare-manager/keys.json")
BAK_DIR            = os.getenv("BAK_DIR",     "/etc/cloudflare-manager/backups")
BAK_RETENTION_DAYS = int(os.getenv("BAK_RETENTION_DAYS", "30"))
API_PORT           = int(os.getenv("API_PORT", "8000"))
CLOUDFLARED_SVC    = os.getenv("CLOUDFLARED_SVC", "cloudflared")
