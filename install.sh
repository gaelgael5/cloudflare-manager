#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/gaelgael5/cloudflare-manager.git"
INSTALL_DIR="/opt/cloudflare-manager"
CONF_DIR="/etc/cloudflare-manager"
BAK_DIR="${CONF_DIR}/backups"
ENV_FILE="${CONF_DIR}/.env"
SERVICE_FILE="/etc/systemd/system/cloudflare-manager.service"
PYTHON_BIN="python3"
PIP_BIN="pip3"

# ---------------------------------------------------------------------------
# Couleurs
# ---------------------------------------------------------------------------
GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; NC="\033[0m"
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---------------------------------------------------------------------------
# Root check
# ---------------------------------------------------------------------------
[ "$(id -u)" -eq 0 ] || error "Ce script doit être exécuté en root (sudo)"

# ---------------------------------------------------------------------------
# Dépendances système
# ---------------------------------------------------------------------------
info "Vérification des dépendances..."
apt-get update -qq

for pkg in python3 python3-pip git curl; do
    if ! dpkg -l "$pkg" &>/dev/null; then
        info "Installation de $pkg..."
        apt-get install -y -qq "$pkg"
    else
        info "$pkg déjà installé"
    fi
done

# ---------------------------------------------------------------------------
# Repo
# ---------------------------------------------------------------------------
if [ -d "${INSTALL_DIR}/.git" ]; then
    info "Mise à jour du repo existant..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    info "Clonage du repo..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# ---------------------------------------------------------------------------
# Dépendances Python
# ---------------------------------------------------------------------------
info "Installation des dépendances Python..."
$PIP_BIN install -q -r "${INSTALL_DIR}/requirements.txt" --break-system-packages

# ---------------------------------------------------------------------------
# Répertoires de conf
# ---------------------------------------------------------------------------
info "Création des répertoires de configuration..."
mkdir -p "$CONF_DIR" "$BAK_DIR"
chmod 750 "$CONF_DIR" "$BAK_DIR"

# ---------------------------------------------------------------------------
# Fichier .env (ne pas écraser si existe)
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
ExecStart=${PYTHON_BIN} -m uvicorn main:app --host 0.0.0.0 --port 8000
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
