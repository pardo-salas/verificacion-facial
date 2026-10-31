"""Descarga y valida los modelos ONNX preentrenados de OpenCV Zoo.

Uso:  python scripts/descargar_modelos.py --destino models
Se ejecuta automáticamente durante `docker build`; si un modelo no se descarga
o no carga en OpenCV, la construcción de la imagen falla (validación temprana).
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

BASE_GITHUB = "https://github.com/opencv/opencv_zoo/raw/main/models"
BASE_LFS = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"
MODELOS = {
    "face_detection_yunet_2023mar.onnx": "face_detection_yunet",
    "face_recognition_sface_2021dec.onnx": "face_recognition_sface",
}
TAMANO_MINIMO = 100_000  # bytes; un puntero LFS sin contenido pesa menos de 1 KB


def descargar(nombre: str, carpeta: str, destino: Path) -> None:
    ruta = destino / nombre
    if ruta.is_file() and ruta.stat().st_size > TAMANO_MINIMO:
        print(f"[ok] {nombre} ya existe ({ruta.stat().st_size:,} bytes)")
        return
    for base in (BASE_GITHUB, BASE_LFS):
        url = f"{base}/{carpeta}/{nombre}"
        try:
            print(f"[..] Descargando {url}")
            urllib.request.urlretrieve(url, ruta)
            if ruta.stat().st_size > TAMANO_MINIMO:
                print(f"[ok] {nombre} ({ruta.stat().st_size:,} bytes)")
                return
            print("[!!] Archivo demasiado pequeño, intento con la siguiente URL")
        except Exception as exc:  # noqa: BLE001
            print(f"[!!] Falló la descarga: {exc}")
    sys.exit(f"No se pudo descargar {nombre}")


def validar(destino: Path) -> None:
    import cv2

    cv2.FaceDetectorYN.create(str(destino / "face_detection_yunet_2023mar.onnx"), "", (320, 320))
    cv2.FaceRecognizerSF.create(str(destino / "face_recognition_sface_2021dec.onnx"), "")
    print(f"[ok] Modelos cargados correctamente con OpenCV {cv2.__version__}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destino", default="models")
    args = parser.parse_args()
    carpeta_destino = Path(args.destino)
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    for archivo, carpeta in MODELOS.items():
        descargar(archivo, carpeta, carpeta_destino)
    validar(carpeta_destino)
