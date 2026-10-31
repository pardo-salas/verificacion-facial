"""Backend FastAPI: expone el modelo de verificación facial mediante una API REST."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import cargar_configuracion
from .face_model import ImagenInvalidaError, Rostro, RostroNoDetectadoError, VerificadorFacial
from .schemas import (
    Caja,
    DeteccionRespuesta,
    InfoRespuesta,
    RostroRespuesta,
    SaludRespuesta,
    VerificacionRespuesta,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("verificacion_facial")
config = cargar_configuracion()
FORMATOS = ["jpg", "jpeg", "png", "webp", "bmp"]
PREFIJO = "/api/v1"


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Carga el modelo una sola vez al iniciar el contenedor."""
    app.state.verificador = None
    app.state.error_modelo = None
    try:
        app.state.verificador = VerificadorFacial(
            config.ruta_detector,
            config.ruta_reconocedor,
            umbral=config.umbral_similitud,
            confianza_deteccion=config.confianza_deteccion,
            lado_maximo=config.lado_maximo,
            tamano_minimo=config.tamano_minimo_rostro,
        )
        log.info("Modelo cargado correctamente. Umbral=%.3f", config.umbral_similitud)
    except Exception as exc:  # noqa: BLE001 - /health debe reportar cualquier falla
        app.state.error_modelo = str(exc)
        log.error("No se pudo cargar el modelo: %s", exc)
    yield


app = FastAPI(
    title="API de verificación facial",
    version=__version__,
    description=(
        "Verifica si dos fotografías corresponden a la misma persona, incluso con "
        "cubrebocas o lentes. Modelos: YuNet (detección) + SFace (reconocimiento)."
    ),
    lifespan=ciclo_de_vida,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def medir_tiempo(request: Request, call_next):
    inicio = time.perf_counter()
    respuesta = await call_next(request)
    ms = (time.perf_counter() - inicio) * 1000
    respuesta.headers["X-Tiempo-Proceso-ms"] = f"{ms:.1f}"
    log.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, respuesta.status_code, ms)
    return respuesta


@app.exception_handler(ImagenInvalidaError)
async def manejar_imagen_invalida(_: Request, exc: ImagenInvalidaError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RostroNoDetectadoError)
async def manejar_sin_rostro(_: Request, exc: RostroNoDetectadoError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def obtener_verificador(request: Request) -> VerificadorFacial:
    verificador = request.app.state.verificador
    if verificador is None:
        raise HTTPException(503, detail=f"Modelo no disponible: {request.app.state.error_modelo}")
    return verificador


async def leer_imagen(archivo: UploadFile, etiqueta: str) -> bytes:
    """Valida tipo, tamaño y contenido de un archivo subido."""
    tipo = (archivo.content_type or "").lower()
    es_imagen = tipo.startswith("image/") and "svg" not in tipo
    if tipo and not (es_imagen or tipo == "application/octet-stream"):
        raise HTTPException(415, detail=f"Tipo de archivo no soportado en {etiqueta}: {tipo}.")
    datos = await archivo.read(config.max_bytes + 1)
    if len(datos) > config.max_bytes:
        limite = config.max_bytes / (1024 * 1024)
        raise HTTPException(413, detail=f"{etiqueta} supera el límite de {limite:g} MB.")
    if not datos:
        raise HTTPException(400, detail=f"{etiqueta} está vacía.")
    return datos


def a_respuesta(rostro: Rostro) -> RostroRespuesta:
    x, y, w, h = rostro.caja
    return RostroRespuesta(
        caja=Caja(x=x, y=y, ancho=w, alto=h),
        confianza_deteccion=rostro.confianza,
        posible_cubrebocas=rostro.posible_cubrebocas,
        advertencias=rostro.advertencias,
    )


@app.get("/", include_in_schema=False)
def raiz():
    return {"servicio": "API de verificación facial", "documentacion": "/docs",
            "salud": f"{PREFIJO}/health"}


@app.get(f"{PREFIJO}/health", response_model=SaludRespuesta, tags=["Monitoreo"])
def salud(request: Request):
    cargado = request.app.state.verificador is not None
    cuerpo = SaludRespuesta(
        estado="ok" if cargado else "degradado",
        modelo_cargado=cargado,
        version=__version__,
        detalle=None if cargado else request.app.state.error_modelo,
    )
    return JSONResponse(status_code=200 if cargado else 503, content=cuerpo.model_dump())


@app.get(f"{PREFIJO}/info", response_model=InfoRespuesta, tags=["Monitoreo"])
def info(request: Request):
    verificador = obtener_verificador(request)
    return InfoRespuesta(
        version=__version__,
        modelo=verificador.info(),
        max_mb_imagen=config.max_bytes / (1024 * 1024),
        max_referencias=config.max_referencias,
        formatos=FORMATOS,
    )


@app.post(f"{PREFIJO}/detectar", response_model=DeteccionRespuesta, tags=["Modelo"])
async def detectar(request: Request,
                   imagen: UploadFile = File(..., description="Fotografía a analizar")):
    verificador = obtener_verificador(request)
    datos = await leer_imagen(imagen, "La imagen")
    rostros, (w, h), advertencias = await run_in_threadpool(verificador.detectar, datos)
    return DeteccionRespuesta(
        numero_rostros=len(rostros),
        ancho_imagen=w,
        alto_imagen=h,
        rostros=[a_respuesta(r) for r in rostros],
        advertencias=advertencias,
    )


@app.post(f"{PREFIJO}/verificar", response_model=VerificacionRespuesta, tags=["Modelo"])
async def verificar(
    request: Request,
    referencias: list[UploadFile] = File(..., description="1 a 5 fotos registradas de la persona"),
    prueba: UploadFile = File(..., description="Foto que se quiere verificar"),
):
    verificador = obtener_verificador(request)
    if len(referencias) > config.max_referencias:
        raise HTTPException(422, detail=f"Se permiten como máximo {config.max_referencias} referencias.")
    datos_ref = [await leer_imagen(r, f"La referencia {i}") for i, r in enumerate(referencias, start=1)]
    datos_prueba = await leer_imagen(prueba, "La imagen de prueba")
    resultado = await run_in_threadpool(verificador.verificar, datos_ref, datos_prueba)
    return VerificacionRespuesta(
        coincide=resultado.coincide,
        similitud=resultado.similitud,
        umbral=resultado.umbral,
        nivel_confianza=resultado.nivel_confianza,
        indice_referencia=resultado.indice_referencia,
        similitudes=resultado.similitudes,
        rostro_prueba=a_respuesta(resultado.rostro_prueba),
        rostros_referencia=[a_respuesta(r) for r in resultado.rostros_referencia],
        advertencias=resultado.advertencias,
        tiempo_ms=resultado.tiempo_ms,
    )
