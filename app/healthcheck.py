"""Healthcheck usado por Docker: termina con código 0 si la API responde 200."""
import os
import sys
import urllib.request

URL = f"http://127.0.0.1:{os.getenv('PORT', '8000')}/api/v1/health"

try:
    with urllib.request.urlopen(URL, timeout=4) as respuesta:
        sys.exit(0 if respuesta.status == 200 else 1)
except Exception:  # noqa: BLE001
    sys.exit(1)
