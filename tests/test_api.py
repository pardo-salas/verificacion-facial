"""Pruebas de integración de la API (contrato HTTP entre frontend y backend)."""
from tests.conftest import imagen_bytes

JPG = "image/jpeg"


def archivos(refs, prueba, tipo=JPG):
    lista = [("referencias", (f"ref{i}.jpg", r, tipo)) for i, r in enumerate(refs)]
    lista.append(("prueba", ("prueba.jpg", prueba, tipo)))
    return lista


def test_health_responde_ok(cliente):
    r = cliente.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"
    assert r.json()["modelo_cargado"] is True


def test_health_sin_modelo_responde_503(cliente):
    from app.main import app

    app.state.verificador = None
    app.state.error_modelo = "prueba"
    r = cliente.get("/api/v1/health")
    assert r.status_code == 503
    assert r.json()["estado"] == "degradado"


def test_info_expone_umbral(cliente):
    r = cliente.get("/api/v1/info")
    assert r.status_code == 200
    assert r.json()["modelo"]["umbral_similitud"] == 0.363
    assert "jpg" in r.json()["formatos"]


def test_documentacion_openapi_disponible(cliente):
    r = cliente.get("/openapi.json")
    rutas = r.json()["paths"]
    assert "/api/v1/verificar" in rutas
    assert "/api/v1/detectar" in rutas


def test_verificar_misma_persona(cliente):
    img = imagen_bytes()
    r = cliente.post("/api/v1/verificar", files=archivos([img], img))
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["coincide"] is True
    assert cuerpo["similitud"] >= cuerpo["umbral"]
    for campo in ("nivel_confianza", "similitudes", "rostro_prueba", "advertencias", "tiempo_ms"):
        assert campo in cuerpo


def test_verificar_persona_distinta(cliente):
    r = cliente.post("/api/v1/verificar",
                     files=archivos([imagen_bytes(color=(10, 10, 10))], imagen_bytes()))
    assert r.status_code == 200
    assert r.json()["coincide"] is False


def test_verificar_varias_referencias_toma_la_maxima(cliente):
    prueba = imagen_bytes()
    refs = [imagen_bytes(color=(1, 2, 3)), prueba, imagen_bytes(color=(9, 9, 9))]
    r = cliente.post("/api/v1/verificar", files=archivos(refs, prueba))
    assert r.json()["indice_referencia"] == 1
    assert len(r.json()["similitudes"]) == 3


def test_sin_rostro_devuelve_422(cliente):
    r = cliente.post("/api/v1/verificar", files=archivos([imagen_bytes()], b"SIN_ROSTRO"))
    assert r.status_code == 422
    assert "rostro" in r.json()["detail"]


def test_imagen_corrupta_devuelve_400(cliente):
    r = cliente.post("/api/v1/verificar", files=archivos([b"CORRUPTA"], imagen_bytes()))
    assert r.status_code == 400


def test_archivo_vacio_devuelve_400(cliente):
    r = cliente.post("/api/v1/verificar", files=archivos([imagen_bytes()], b""))
    assert r.status_code in (400, 422)


def test_tipo_no_soportado_devuelve_415(cliente):
    r = cliente.post("/api/v1/verificar", files=archivos([b"hola"], b"hola", tipo="text/plain"))
    assert r.status_code == 415


def test_svg_rechazado(cliente):
    r = cliente.post("/api/v1/detectar",
                     files={"imagen": ("x.svg", b"<svg></svg>", "image/svg+xml")})
    assert r.status_code == 415


def test_archivo_demasiado_grande_devuelve_413(cliente):
    grande = b"0" * (5 * 1024 * 1024 + 10)
    r = cliente.post("/api/v1/verificar", files=archivos([imagen_bytes()], grande))
    assert r.status_code == 413


def test_mas_de_cinco_referencias_devuelve_422(cliente):
    img = imagen_bytes()
    r = cliente.post("/api/v1/verificar", files=archivos([img] * 6, img))
    assert r.status_code == 422


def test_falta_imagen_de_prueba_devuelve_422(cliente):
    r = cliente.post("/api/v1/verificar",
                     files=[("referencias", ("r.jpg", imagen_bytes(), JPG))])
    assert r.status_code == 422


def test_detectar_varios_rostros(cliente):
    r = cliente.post("/api/v1/detectar", files={"imagen": ("g.jpg", imagen_bytes(), JPG)})
    assert r.status_code == 200
    assert r.json()["numero_rostros"] == 2


def test_cors_permite_al_frontend(cliente):
    r = cliente.options("/api/v1/verificar", headers={
        "Origin": "http://localhost:8080",
        "Access-Control-Request-Method": "POST",
    })
    assert r.status_code == 200
    assert "access-control-allow-origin" in r.headers


def test_cabecera_de_tiempo(cliente):
    r = cliente.get("/api/v1/health")
    assert "x-tiempo-proceso-ms" in r.headers
