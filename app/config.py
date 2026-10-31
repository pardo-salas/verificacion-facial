"""Configuración de la aplicación leída desde variables de entorno."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ARCHIVO_DETECTOR = "face_detection_yunet_2023mar.onnx"
ARCHIVO_RECONOCEDOR = "face_recognition_sface_2021dec.onnx"
DIR_MODELOS_DEFECTO = Path(__file__).resolve().parent.parent / "models"


@dataclass(frozen=True)
class Configuracion:
    dir_modelos: Path
    umbral_similitud: float
    confianza_deteccion: float
    lado_maximo: int
    tamano_minimo_rostro: int
    max_bytes: int
    max_referencias: int
    cors_origins: list[str]

    @property
    def ruta_detector(self) -> Path:
        return self.dir_modelos / ARCHIVO_DETECTOR

    @property
    def ruta_reconocedor(self) -> Path:
        return self.dir_modelos / ARCHIVO_RECONOCEDOR


def cargar_configuracion() -> Configuracion:
    origenes = os.getenv("CORS_ORIGINS", "*")
    return Configuracion(
        dir_modelos=Path(os.getenv("MODELS_DIR", str(DIR_MODELOS_DEFECTO))),
        # 0.363 es el umbral de similitud coseno recomendado por OpenCV para SFace.
        umbral_similitud=float(os.getenv("UMBRAL_SIMILITUD", "0.363")),
        confianza_deteccion=float(os.getenv("CONFIANZA_DETECCION", "0.6")),
        lado_maximo=int(os.getenv("LADO_MAXIMO_PX", "1280")),
        tamano_minimo_rostro=int(os.getenv("TAMANO_MINIMO_ROSTRO_PX", "40")),
        max_bytes=int(float(os.getenv("MAX_MB_IMAGEN", "5")) * 1024 * 1024),
        max_referencias=int(os.getenv("MAX_REFERENCIAS", "5")),
        cors_origins=[o.strip() for o in origenes.split(",") if o.strip()],
    )
