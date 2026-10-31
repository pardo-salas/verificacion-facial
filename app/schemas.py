"""Esquemas de respuesta de la API (se documentan automáticamente en /docs)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Caja(BaseModel):
    x: int
    y: int
    ancho: int
    alto: int


class RostroRespuesta(BaseModel):
    caja: Caja
    confianza_deteccion: float = Field(..., description="Confianza de YuNet (0 a 1)")
    posible_cubrebocas: bool | None = Field(
        None, description="Estimación heurística; null si no hay información suficiente"
    )
    advertencias: list[str] = []


class VerificacionRespuesta(BaseModel):
    coincide: bool = Field(..., description="True si las fotos son de la misma persona")
    similitud: float = Field(..., description="Similitud coseno máxima entre prueba y referencias")
    umbral: float
    nivel_confianza: str = Field(..., description="alta, media o baja según la distancia al umbral")
    indice_referencia: int = Field(..., description="Referencia con mayor similitud (base 0)")
    similitudes: list[float]
    rostro_prueba: RostroRespuesta
    rostros_referencia: list[RostroRespuesta]
    advertencias: list[str]
    tiempo_ms: float


class DeteccionRespuesta(BaseModel):
    numero_rostros: int
    ancho_imagen: int
    alto_imagen: int
    rostros: list[RostroRespuesta]
    advertencias: list[str]


class SaludRespuesta(BaseModel):
    estado: str
    modelo_cargado: bool
    version: str
    detalle: str | None = None


class InfoRespuesta(BaseModel):
    version: str
    modelo: dict
    max_mb_imagen: float
    max_referencias: int
    formatos: list[str]
