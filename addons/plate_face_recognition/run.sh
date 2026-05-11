#!/usr/bin/with-contenv bashio
# ==============================================================================
# Home Assistant Add-on: Plate & Face Recognition
# Startet den FastAPI REST-Server auf dem konfigurierten Port.
# ==============================================================================
set -e

PORT=$(bashio::config 'port')
DATA_DIR="/share/plate_face_recognition"

bashio::log.info "Plate & Face Recognition Add-on v1.0.0 startet..."
bashio::log.info "API Port : ${PORT}"
bashio::log.info "Datenpfad: ${DATA_DIR}"

# Datenpfad sicherstellen
mkdir -p "${DATA_DIR}"

# Datenverzeichnis als Umgebungsvariable übergeben
export PFR_DATA_DIR="${DATA_DIR}"

cd /app
exec uvicorn server:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --workers 1 \
    --log-level info
# Triggering GHCR build
# Trigger retry 2
