# cloudflare-manager

API légère pour gérer le fichier `config.yml` de `cloudflared` (tunnel Cloudflare en mode locally-managed).

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/gaelgael5/cloudflare-manager/main/install.sh | sudo bash
```

Le script :
1. Installe les dépendances système (python3, pip3, git, curl)
2. Clone ou met à jour le repo dans `/opt/cloudflare-manager`
3. Installe les dépendances Python
4. Crée `/etc/cloudflare-manager/.env` (si absent)
5. Installe et démarre le service systemd `cloudflare-manager`

---

## Configuration

Fichier : `/etc/cloudflare-manager/.env`

```env
CONFIG_YML=/etc/cloudflared/config.yml
KEYS_FILE=/etc/cloudflare-manager/keys.json
BAK_DIR=/etc/cloudflare-manager/backups
BAK_RETENTION_DAYS=30
API_PORT=8000
CLOUDFLARED_SVC=cloudflared
```

---

## Gestion des API keys (localhost uniquement)

Ces endpoints ne sont accessibles **que depuis la machine locale**.

### Créer une API key

```bash
curl -s -X POST http://127.0.0.1:8000/admin/keys \
  -H "Content-Type: application/json" \
  -d '{"label": "agflow"}'
```

Réponse :
```json
{
  "label": "agflow",
  "key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "active": true
}
```

> **La clé n'est affichée qu'une seule fois. Conservez-la.**

### Lister les API keys

```bash
curl -s http://127.0.0.1:8000/admin/keys
```

### Désactiver une API key

```bash
curl -s -X PATCH http://127.0.0.1:8000/admin/keys/agflow/deactivate
```

### Réactiver une API key

```bash
curl -s -X PATCH http://127.0.0.1:8000/admin/keys/agflow/activate
```

### Supprimer une API key

```bash
curl -s -X DELETE http://127.0.0.1:8000/admin/keys/agflow
```

---

## Endpoints /ingress

Tous les endpoints `/ingress` nécessitent un header `Authorization: Bearer <key>`.

### Voir tout le fichier config.yml

```bash
curl -s http://localhost:8000/ingress \
  -H "Authorization: Bearer <key>"
```

### Voir une règle spécifique

```bash
curl -s http://localhost:8000/ingress/wiki-projet1.yoops.org \
  -H "Authorization: Bearer <key>"
```

### Ajouter une règle

```bash
curl -s -X POST http://localhost:8000/ingress \
  -H "Authorization: Bearer <key>" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "wiki-projet1.yoops.org",
    "service": "http://192.168.10.50:3000"
  }'
```

Avec options avancées :

```bash
curl -s -X POST http://localhost:8000/ingress \
  -H "Authorization: Bearer <key>" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "app-projet2.yoops.org",
    "service": "https://192.168.10.51:8443",
    "path": "^/api",
    "originRequest": {
      "noTLSVerify": true,
      "connectTimeout": "10s"
    }
  }'
```

### Mettre à jour une règle (remplace entièrement)

```bash
curl -s -X PUT http://localhost:8000/ingress/wiki-projet1.yoops.org \
  -H "Authorization: Bearer <key>" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "wiki-projet1.yoops.org",
    "service": "http://192.168.10.50:3001"
  }'
```

> Les propriétés absentes du payload sont supprimées de la règle.

### Supprimer une règle

```bash
curl -s -X DELETE http://localhost:8000/ingress/wiki-projet1.yoops.org \
  -H "Authorization: Bearer <key>"
```

---

## Backups

Avant chaque modification, le fichier `config.yml` est sauvegardé dans :

```
/etc/cloudflare-manager/backups/config.yml.2026-05-21T14-32-00.bak
```

Les backups de plus de `BAK_RETENTION_DAYS` jours (défaut 30) sont supprimés automatiquement.

Pour restaurer manuellement :

```bash
cp /etc/cloudflare-manager/backups/config.yml.2026-05-21T14-32-00.bak \
   /etc/cloudflared/config.yml
systemctl restart cloudflared
```

---

## Propriétés disponibles par règle

| Propriété | Type | Description |
|---|---|---|
| `hostname` | string | Hostname public (ex: `app.yoops.org`) |
| `service` | string | Cible interne (ex: `http://192.168.10.x:8080`) |
| `path` | string | Regex sur le path (optionnel) |
| `originRequest.noTLSVerify` | bool | Désactive la vérification TLS |
| `originRequest.connectTimeout` | string | Timeout TCP (ex: `10s`) |
| `originRequest.tlsTimeout` | string | Timeout TLS (ex: `10s`) |
| `originRequest.httpHostHeader` | string | Force le header Host |
| `originRequest.http2Origin` | bool | Connexion HTTP/2 vers l'origine |
| `originRequest.originServerName` | string | Hostname attendu dans le certificat |

---

## Gestion du service

```bash
systemctl status cloudflare-manager
systemctl restart cloudflare-manager
journalctl -u cloudflare-manager -f
```

---

## Mise à jour

```bash
curl -fsSL https://raw.githubusercontent.com/gaelgael5/cloudflare-manager/main/install.sh | sudo bash
```

Le script détecte le repo existant et fait un `git pull`.
