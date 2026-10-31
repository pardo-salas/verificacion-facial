#!/bin/sh
# Genera config.js a partir de la variable de entorno API_URL.
# Uso: sh generar_config.sh <ruta_salida>
SALIDA="${1:-/usr/share/nginx/html/config.js}"
URL="${API_URL:-http://localhost:8000}"
echo "window.APP_CONFIG = { API_URL: \"${URL}\" };" > "$SALIDA"
echo "config.js generado con API_URL=${URL}"
