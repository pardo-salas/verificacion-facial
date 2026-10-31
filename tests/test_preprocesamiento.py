"""Pruebas del preprocesamiento de imágenes (no requieren los modelos)."""
import io

import numpy as np
import pytest
from PIL import Image

from app.face_model import ImagenInvalidaError, VerificadorFacial
from tests.conftest import imagen_bytes

decodificar = VerificadorFacial.decodificar


def test_jpeg_valido_se_convierte_a_bgr():
    img = decodificar(imagen_bytes(120, 80))
    assert img.shape == (80, 120, 3)
    assert img.dtype == np.uint8


@pytest.mark.parametrize("formato", ["PNG", "WEBP", "BMP"])
def test_formatos_soportados(formato):
    assert decodificar(imagen_bytes(formato=formato)).shape[2] == 3


def test_escala_de_grises_se_convierte_a_tres_canales():
    assert decodificar(imagen_bytes(modo="L", formato="PNG")).shape[2] == 3


def test_png_con_transparencia():
    assert decodificar(imagen_bytes(modo="RGBA", formato="PNG")).shape[2] == 3


def test_orientacion_exif_de_celular_se_corrige():
    imagen = Image.new("RGB", (300, 100), (120, 100, 90))
    exif = imagen.getexif()
    exif[0x0112] = 6  # foto girada 90°, típico de celulares
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", exif=exif)
    assert decodificar(buffer.getvalue()).shape[:2] == (300, 100)


@pytest.mark.parametrize("datos", [b"", b"esto no es una imagen", b"\xff\xd8\xff\xe0truncado"])
def test_datos_invalidos(datos):
    with pytest.raises(ImagenInvalidaError):
        decodificar(datos)


def test_bomba_de_descompresion_rechazada(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(ImagenInvalidaError):
        decodificar(imagen_bytes(200, 200, formato="PNG"))
