"""Pruebas del modelo real (YuNet + SFace).

Las que usan fotos reales se omiten si no existen en tests/data. Nombres esperados:
  persona_a_1.jpg, persona_a_2.jpg       -> misma persona, fotos distintas
  persona_a_cubrebocas.jpg               -> persona A con cubrebocas
  persona_a_lentes.jpg                   -> persona A con lentes antirreflejantes
  persona_a_cubrebocas_lentes.jpg        -> persona A con ambos
  persona_b_1.jpg                        -> otra persona
  grupo.jpg                              -> foto con varias personas
"""
import time

import pytest

from app.face_model import RostroNoDetectadoError
from tests.conftest import foto, imagen_bytes

pytestmark = pytest.mark.modelo


def test_imagen_en_blanco_no_tiene_rostro(verificador_real):
    with pytest.raises(RostroNoDetectadoError):
        verificador_real.verificar([imagen_bytes()], imagen_bytes())


def test_imagen_negra_no_tiene_rostro(verificador_real):
    with pytest.raises(RostroNoDetectadoError):
        verificador_real.analizar(imagen_bytes(color=(0, 0, 0)), "la imagen")


def test_imagen_enorme_se_redimensiona(verificador_real):
    rostros, (w, h), _ = verificador_real.detectar(imagen_bytes(6000, 4000))
    assert max(w, h) == verificador_real.lado_maximo
    assert rostros == []


def test_imagen_diminuta_se_amplia(verificador_real):
    _, (w, h), advertencias = verificador_real.detectar(imagen_bytes(40, 40))
    assert max(w, h) == 320
    assert advertencias


def test_misma_foto_similitud_casi_uno(verificador_real):
    img = foto("persona_a_1")
    assert verificador_real.verificar([img], img).similitud > 0.95


def test_misma_persona_coincide(verificador_real):
    assert verificador_real.verificar([foto("persona_a_1")], foto("persona_a_2")).coincide


def test_persona_distinta_no_coincide(verificador_real):
    assert not verificador_real.verificar([foto("persona_a_1")], foto("persona_b_1")).coincide


def test_lentes_antirreflejantes(verificador_real):
    assert verificador_real.verificar([foto("persona_a_1")], foto("persona_a_lentes")).coincide


def test_cubrebocas_con_referencia_multiple(verificador_real):
    refs = [foto("persona_a_1"), foto("persona_a_cubrebocas")]
    resultado = verificador_real.verificar(refs, foto("persona_a_cubrebocas_lentes"))
    assert resultado.coincide


def test_cubrebocas_se_detecta(verificador_real):
    rostro, _, _ = verificador_real.analizar(foto("persona_a_cubrebocas"), "la imagen")
    assert rostro.posible_cubrebocas is True


def test_impostor_con_cubrebocas_no_coincide(verificador_real):
    refs = [foto("persona_a_1"), foto("persona_a_cubrebocas")]
    assert not verificador_real.verificar(refs, foto("persona_b_1")).coincide


def test_foto_grupal_usa_rostro_mas_grande(verificador_real):
    _, _, advertencias = verificador_real.analizar(foto("grupo"), "la imagen")
    assert any("rostros" in a for a in advertencias)


def test_tiempo_de_respuesta_menor_a_2_segundos(verificador_real):
    img = foto("persona_a_1")
    inicio = time.perf_counter()
    verificador_real.verificar([img], img)
    assert time.perf_counter() - inicio < 2.0
