"""Fixtures compartidas por las pruebas."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.config import cargar_configuracion
from app.face_model import (
    ImagenInvalidaError,
    ResultadoVerificacion,
    Rostro,
    RostroNoDetectadoError,
)

DATOS = Path(__file__).parent / "data"


def imagen_bytes(ancho=200, alto=200, color=(200, 180, 160), formato="JPEG", modo="RGB") -> bytes:
    """Crea una imagen sintética en memoria."""
    if modo == "L":
        color = color[0]
    elif modo == "RGBA":
        color = (*color, 128)
    buffer = io.BytesIO()
    Image.new(modo, (ancho, alto), color).save(buffer, format=formato)
    return buffer.getvalue()


def _rostro_falso(cubrebocas=False) -> Rostro:
    return Rostro(caja=(10, 10, 100, 100), confianza=0.95, posible_cubrebocas=cubrebocas,
                  advertencias=[], fila=np.zeros(15, np.float32))


class VerificadorFalso:
    """Doble de prueba: permite probar la API sin cargar los modelos ONNX.

    Convención: si la imagen contiene los bytes b"SIN_ROSTRO" se simula que no
    hay rostro; si contiene b"CORRUPTA" se simula una imagen ilegible. Si la
    prueba y una referencia son idénticas, se simula una coincidencia.
    """

    umbral = 0.363

    def _revisar(self, datos: bytes, etiqueta: str) -> None:
        if b"CORRUPTA" in datos:
            raise ImagenInvalidaError("No se pudo leer la imagen.")
        if b"SIN_ROSTRO" in datos:
            raise RostroNoDetectadoError(f"No se detectó ningún rostro en {etiqueta}.")

    def verificar(self, referencias, prueba):
        self._revisar(prueba, "la imagen de prueba")
        for i, r in enumerate(referencias, start=1):
            self._revisar(r, f"la referencia {i}")
        similitudes = [0.92 if r == prueba else 0.08 for r in referencias]
        mejor = max(similitudes)
        return ResultadoVerificacion(
            coincide=mejor >= self.umbral, similitud=mejor, umbral=self.umbral,
            nivel_confianza="alta", indice_referencia=similitudes.index(mejor),
            similitudes=similitudes, rostro_prueba=_rostro_falso(),
            rostros_referencia=[_rostro_falso() for _ in referencias],
            advertencias=[], tiempo_ms=1.0,
        )

    def detectar(self, datos):
        self._revisar(datos, "la imagen")
        return [_rostro_falso(), _rostro_falso()], (640, 480), []

    def info(self):
        return {"detector": "falso", "reconocedor": "falso", "umbral_similitud": self.umbral}


@pytest.fixture
def cliente():
    """Cliente HTTP de la API con el verificador falso inyectado."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        app.state.verificador = VerificadorFalso()
        yield c


@pytest.fixture(scope="session")
def verificador_real():
    """Verificador con los modelos ONNX reales (se omite si no están descargados)."""
    from app.face_model import VerificadorFacial

    config = cargar_configuracion()
    if not (config.ruta_detector.is_file() and config.ruta_reconocedor.is_file()):
        pytest.skip("Modelos no descargados: ejecuta scripts/descargar_modelos.py")
    return VerificadorFacial(config.ruta_detector, config.ruta_reconocedor, umbral=config.umbral_similitud)


def foto(nombre: str) -> bytes:
    """Lee una foto real de tests/data o se omite la prueba si no existe."""
    for extension in (".jpg", ".jpeg", ".png"):
        ruta = DATOS / f"{nombre}{extension}"
        if ruta.is_file():
            return ruta.read_bytes()
    pytest.skip(f"Falta la foto de prueba tests/data/{nombre}.jpg")
