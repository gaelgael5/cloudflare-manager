#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# PATH complet — LXC minimal peut avoir un PATH tronqué
# ---------------------------------------------------------------------------
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

REPO_URL="https://github.com/gaelgael5/cloudflare-manager.git"
INSTALL_DIR="/opt/cloudflare-manager"
CONF_DIR="/etc/cloudflare-manager"
BAK_DIR="${CONF_DIR}/backups"
ENV_FILE="${CONF_DIR}/.env"
SERVICE_FILE="/etc/systemd/system/cloudflare-manager.service"
VENV_DIR="${INSTALL_DIR}/.venv"

# ---------------------------------------------------------------------------
# Couleurs
# ---------------------------------------------------------------------------
GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; NC="\033[0m"
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---------------------------------------------------------------------------
# Root check
# ---------------------------------------------------------------------------
[ "$(id -u)" -eq 0 ] || error "Ce script doit être exécuté en root (sudo)"

# ---------------------------------------------------------------------------
# Dépendances système
# ---------------------------------------------------------------------------
info "Installation des paquets système..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl

# Vérifie que les binaires sont bien dans le PATH
for bin in python3 git curl; do
    command -v "$bin" &>/dev/null || error "Binaire '$bin' introuvable après installation"
done
info "Dépendances système OK"

# ---------------------------------------------------------------------------
# Repo — clone ou pull
# ---------------------------------------------------------------------------
if [ -d "${INSTALL_DIR}/.git" ]; then
    info "Mise à jour du repo existant..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    info "Clonage du repo..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# ---------------------------------------------------------------------------
# Virtualenv Python
# ---------------------------------------------------------------------------
info "Création du virtualenv Python..."
python3 -m venv "$VENV_DIR"

info "Installation des dépendances Python..."
"${VENV_DIR}/bin/pip" install -q -r "${INSTALL_DIR}/requirements.txt"

# ---------------------------------------------------------------------------
# Répertoires de conf
# ---------------------------------------------------------------------------
info "Création des répertoires de configuration..."
mkdir -p "$CONF_DIR" "$BAK_DIR"
chmod 750 "$CONF_DIR" "$BAK_DIR"

# ---------------------------------------------------------------------------
# Fichier .env — ne pas écraser si existe
# ---------------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
    info "Création du fichier .env..."
    cat > "$ENV_FILE" <<EOF
CONFIG_YML=/etc/cloudflared/config.yml
KEYS_FILE=${CONF_DIR}/keys.json
BAK_DIR=${BAK_DIR}
BAK_RETENTION_DAYS=30
API_PORT=8000
CLOUDFLARED_SVC=cloudflared
EOF
    chmod 640 "$ENV_FILE"
    info "Fichier .env créé : ${ENV_FILE}"
else
    warn "Fichier .env existant conservé : ${ENV_FILE}"
fi

# ---------------------------------------------------------------------------
# Service systemd
# ---------------------------------------------------------------------------
info "Installation du service systemd..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Cloudflare Manager API
After=network.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_DIR}/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable cloudflare-manager
systemctl restart cloudflare-manager

# ---------------------------------------------------------------------------
# Vérification
# ---------------------------------------------------------------------------
sleep 2
if systemctl is-active --quiet cloudflare-manager; then
    info "Service cloudflare-manager démarré avec succès"
else
    error "Le service n'a pas démarré. Vérifiez : journalctl -u cloudflare-manager -n 50"
fi

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Installation terminée${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  API disponible sur : http://$(hostname -I | awk '{print $1}'):8000"
echo "  Docs Swagger       : http://$(hostname -I | awk '{print $1}'):8000/docs"
echo ""
echo "  Première API key (en local sur cette machine) :"
echo "  curl -s -X POST http://127.0.0.1:8000/admin/keys \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"label\": \"agflow\"}'"
echo ""