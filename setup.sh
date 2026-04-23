#!/usr/bin/env bash
# =============================================================================
# setup.sh – Demo-Umgebung für Plate & Face Recognition starten
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$REPO_ROOT/docker/homeassistant"
FACES_DIR="$REPO_ROOT/docker/faces"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   Plate & Face Recognition – Demo Setup                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# --- Voraussetzungen prüfen ---
COMPOSE_CMD=""
if docker compose version &>/dev/null; then
  COMPOSE_CMD="docker compose"
  echo "✓ docker compose (plugin) gefunden"
elif command -v docker-compose &>/dev/null; then
  COMPOSE_CMD="docker-compose"
  echo "✓ docker-compose gefunden"
else
  echo "✗ Weder 'docker compose' noch 'docker-compose' gefunden."
  echo "  Bitte Docker Desktop installieren: https://www.docker.com/products/docker-desktop"
  exit 1
fi

if ! command -v docker &>/dev/null; then
  echo "✗ 'docker' nicht gefunden. Bitte Docker Desktop installieren."
  exit 1
fi
echo "✓ docker gefunden"

# --- Verzeichnisse anlegen ---
echo ""
echo "→ Verzeichnisse anlegen …"
mkdir -p "$CONFIG_DIR" "$FACES_DIR"

# --- Docker Images bauen und Container starten ---
echo "→ Docker Images bauen …"
cd "$REPO_ROOT"
$COMPOSE_CMD build

echo "→ Container starten …"
$COMPOSE_CMD up -d

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   ✓ Demo-Umgebung läuft!                                ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║   Home Assistant:  http://localhost:8123                ║"
echo "║   Demo-Kamera:     http://localhost:8554/snapshot       ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║   Beim ersten Start: Onboarding im Browser abschließen  ║"
echo "║   (Benutzer anlegen, Standort konfigurieren – ca. 2min) ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║   Nächste Schritte nach dem Onboarding:                 ║"
echo "║   1. Einstellungen → Geräte & Dienste                   ║"
echo "║   2. '+ Integration hinzufügen'                         ║"
echo "║   3. 'Plate & Face Recognition' suchen & einrichten     ║"
echo "║   4. Demo-Kameras auswählen                             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Logs anzeigen:  docker logs -f ha-plate-face-demo"
echo "Stoppen:        $COMPOSE_CMD down"
echo ""
