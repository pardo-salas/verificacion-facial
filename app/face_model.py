"""Núcleo del modelo de verificación facial.

Usa dos redes preentrenadas de OpenCV Zoo:
  * YuNet  -> detecta el rostro y 5 puntos de referencia (ojos, nariz, comisuras).
  * SFace  -> alinea el rostro a 112x112 y genera un vector (embedding) de 128 valores.

Dos fotos son de la misma persona cuando la similitud coseno entre sus
embeddings es mayor o igual al umbral configurado.
"""
from __future__ import annotations

import io
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

# Protección contra "bombas de descompresión" (imágenes con millones de píxeles).
Image.MAX_IMAGE_PIXELS = 25_000_000


class ErrorVerificacion(Exception):
    """Error base del modelo."""


class ImagenInvalidaError(ErrorVerificacion):
    """El archivo no es una imagen válida o no se puede leer."""


class RostroNoDetectadoError(ErrorVerificacion):
    """La imagen no contiene un rostro detectable."""


@dataclass
class Rostro:
    caja: tuple[int, int, int, int]
    confianza: float
    posible_cubrebocas: bool | None
    advertencias: list[str]
    fila: np.ndarray = field(repr=False)


@dataclass
class ResultadoVerificacion:
    coincide: bool
    similitud: float
    umbral: float
    nivel_confianza: str
    indice_referencia: int
    similitudes: list[float]
    rostro_prueba: Rostro
    rostros_referencia: list[Rostro]
    advertencias: list[str]
    tiempo_ms: float


def _recortar(img: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
    h, w = img.shape[:2]
    x0, x1 = int(max(0, x0)), int(min(w, x1))
    y0, y1 = int(max(0, y0)), int(min(h, y1))
    if x1 <= x0 or y1 <= y0:
        return img[0:0, 0:0]
    return img[y0:y1, x0:x1]


class VerificadorFacial:
    NOMBRE_DETECTOR = "YuNet (OpenCV Zoo, 2023mar)"
    NOMBRE_RECONOCEDOR = "SFace (OpenCV Zoo, 2021dec)"

    def __init__(
        self,
        ruta_detector: str | Path,
        ruta_reconocedor: str | Path,
        umbral: float = 0.363,
        confianza_deteccion: float = 0.6,
        lado_maximo: int = 1280,
        tamano_minimo: int = 40,
    ) -> None:
        for ruta in (ruta_detector, ruta_reconocedor):
            if not Path(ruta).is_file():
                raise FileNotFoundError(f"No se encontró el archivo del modelo: {ruta}")
        self.detector = cv2.FaceDetectorYN.create(
            str(ruta_detector), "", (320, 320), confianza_deteccion, 0.3, 5000
        )
        self.reconocedor = cv2.FaceRecognizerSF.create(str(ruta_reconocedor), "")
        self.umbral = umbral
        self.confianza_deteccion = confianza_deteccion
        self.lado_maximo = lado_maximo
        self.tamano_minimo = tamano_minimo
        # Las redes de OpenCV no son seguras entre hilos: serializo su uso.
        self._candado = threading.Lock()

    # ------------------------------------------------------------------ #
    # Preprocesamiento
    # ------------------------------------------------------------------ #
    @staticmethod
    def decodificar(datos: bytes) -> np.ndarray:
        """Convierte bytes (JPG, PNG, WEBP, BMP) a una imagen BGR de 3 canales.

        Corrige la orientación EXIF de fotos tomadas con celular y descarta el
        canal alfa o la escala de grises.
        """
        if not datos:
            raise ImagenInvalidaError("El archivo está vacío.")
        try:
            with Image.open(io.BytesIO(datos)) as original:
                imagen = ImageOps.exif_transpose(original).convert("RGB")
                arreglo = np.asarray(imagen)
        except Image.DecompressionBombError as exc:
            raise ImagenInvalidaError("La imagen tiene demasiados píxeles para procesarse.") from exc
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
            raise ImagenInvalidaError(
                "No se pudo leer la imagen. Usa un archivo JPG, PNG, WEBP o BMP."
            ) from exc
        return cv2.cvtColor(arreglo, cv2.COLOR_RGB2BGR)

    def preparar(self, img: np.ndarray) -> tuple[np.ndarray, list[str]]:
        """Ajusta el tamaño: reduce fotos enormes y amplía fotos diminutas."""
        advertencias: list[str] = []
        h, w = img.shape[:2]
        lado = max(h, w)
        if lado > self.lado_maximo:
            escala = self.lado_maximo / lado
            img = cv2.resize(img, (max(1, round(w * escala)), max(1, round(h * escala))),
                             interpolation=cv2.INTER_AREA)
        elif lado < 320:
            escala = 320 / lado
            img = cv2.resize(img, (max(1, round(w * escala)), max(1, round(h * escala))),
                             interpolation=cv2.INTER_CUBIC)
            advertencias.append("Imagen de baja resolución; se amplió para poder analizarla.")
        return img, advertencias

    # ------------------------------------------------------------------ #
    # Detección y calidad
    # ------------------------------------------------------------------ #
    def detectar_rostros(self, img: np.ndarray) -> list[Rostro]:
        h, w = img.shape[:2]
        with self._candado:
            self.detector.setInputSize((w, h))
            _, caras = self.detector.detect(img)
        if caras is None:
            return []
        caras = sorted(caras, key=lambda f: float(f[2] * f[3]), reverse=True)
        return [self._construir_rostro(img, f) for f in caras]

    def _construir_rostro(self, img: np.ndarray, f: np.ndarray) -> Rostro:
        x, y, w, h = (int(round(float(v))) for v in f[:4])
        return Rostro(
            caja=(x, y, w, h),
            confianza=round(float(f[14]), 4),
            posible_cubrebocas=self._estimar_cubrebocas(img, f),
            advertencias=self._evaluar_calidad(img, f),
            fila=f.astype(np.float32),
        )

    def _evaluar_calidad(self, img: np.ndarray, f: np.ndarray) -> list[str]:
        x, y, w, h = (float(v) for v in f[:4])
        advertencias: list[str] = []
        if min(w, h) < self.tamano_minimo:
            advertencias.append(
                f"Rostro muy pequeño ({int(min(w, h))} px); la precisión puede disminuir."
            )
        recorte = _recortar(img, x, y, x + w, y + h)
        if recorte.size:
            gris = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
            brillo = float(gris.mean())
            if brillo < 50:
                advertencias.append("Rostro con poca iluminación.")
            elif brillo > 210:
                advertencias.append("Rostro sobreexpuesto (demasiada luz).")
            if float(cv2.Laplacian(gris, cv2.CV_64F).var()) < 40:
                advertencias.append("Rostro borroso o desenfocado.")
        if float(f[14]) < 0.8:
            advertencias.append(
                "Confianza de detección baja (posible oclusión, perfil o mala iluminación)."
            )
        ojo_der_x, ojo_izq_x, nariz_x = float(f[4]), float(f[6]), float(f[8])
        distancia_ojos = abs(ojo_izq_x - ojo_der_x)
        centro_ojos = (ojo_der_x + ojo_izq_x) / 2
        if distancia_ojos > 0 and abs(nariz_x - centro_ojos) / distancia_ojos > 0.35:
            advertencias.append("Rostro girado (posible perfil); se recomienda una foto frontal.")
        return advertencias

    @staticmethod
    def _estimar_cubrebocas(img: np.ndarray, f: np.ndarray) -> bool | None:
        """Heurística: compara el color de la frente con la zona nariz-barbilla.

        Si menos del 35 % de la zona inferior tiene un color parecido a la piel de
        la frente, asumo que está cubierta (cubrebocas). Devuelve None si no hay
        información suficiente (por ejemplo, frente tapada por cabello o gorra).
        """
        x, y, w, h = (float(v) for v in f[:4])
        ojos_y = min(float(f[5]), float(f[7]))
        nariz_y = float(f[9])
        frente = _recortar(img, x + 0.3 * w, y + 0.05 * h, x + 0.7 * w, ojos_y - 0.15 * h)
        inferior = _recortar(img, x + 0.25 * w, nariz_y + 0.05 * h, x + 0.75 * w, y + 0.95 * h)
        if frente.shape[0] * frente.shape[1] < 50 or inferior.shape[0] * inferior.shape[1] < 50:
            return None
        lab_frente = cv2.cvtColor(frente, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
        lab_inferior = cv2.cvtColor(inferior, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
        referencia = np.median(lab_frente, axis=0)
        # La luminosidad pesa menos para tolerar sombras en la parte baja del rostro.
        diferencia = (lab_inferior - referencia) * np.array([0.5, 1.0, 1.0], np.float32)
        fraccion_piel = float((np.linalg.norm(diferencia, axis=1) < 20).mean())
        return fraccion_piel < 0.35

    # ------------------------------------------------------------------ #
    # Embeddings y comparación
    # ------------------------------------------------------------------ #
    def _embedding(self, img: np.ndarray, fila: np.ndarray) -> np.ndarray:
        with self._candado:
            alineado = self.reconocedor.alignCrop(img, fila)
            vector = self.reconocedor.feature(alineado)
        vector = np.asarray(vector, dtype=np.float32).flatten()
        return vector / (np.linalg.norm(vector) + 1e-10)

    def analizar(self, datos: bytes, etiqueta: str) -> tuple[Rostro, np.ndarray, list[str]]:
        """Decodifica, detecta el rostro principal y calcula su embedding."""
        img, advertencias = self.preparar(self.decodificar(datos))
        rostros = self.detectar_rostros(img)
        if not rostros:
            raise RostroNoDetectadoError(f"No se detectó ningún rostro en {etiqueta}.")
        if len(rostros) > 1:
            advertencias.append(
                f"Se detectaron {len(rostros)} rostros en {etiqueta}; se usó el de mayor tamaño."
            )
        principal = rostros[0]
        return principal, self._embedding(img, principal.fila), advertencias

    def _nivel_confianza(self, similitud: float) -> str:
        margen = abs(similitud - self.umbral)
        if margen >= 0.15:
            return "alta"
        if margen >= 0.05:
            return "media"
        return "baja"

    def verificar(self, referencias: list[bytes], prueba: bytes) -> ResultadoVerificacion:
        """Compara la foto de prueba contra 1..N fotos de referencia de la misma persona.

        Usar varias referencias (por ejemplo, una sin cubrebocas y otra con
        cubrebocas) es la estrategia principal para mejorar la robustez ante
        oclusiones: se toma la similitud máxima.
        """
        inicio = time.perf_counter()
        if not referencias:
            raise ImagenInvalidaError("Se necesita al menos una imagen de referencia.")
        rostro_prueba, emb_prueba, advertencias = self.analizar(prueba, "la imagen de prueba")
        rostros_ref: list[Rostro] = []
        similitudes: list[float] = []
        for i, datos in enumerate(referencias, start=1):
            rostro, emb, adv = self.analizar(datos, f"la referencia {i}")
            rostros_ref.append(rostro)
            advertencias.extend(adv)
            similitudes.append(round(float(np.dot(emb, emb_prueba)), 4))

        indice = int(np.argmax(similitudes))
        similitud = similitudes[indice]
        if rostro_prueba.posible_cubrebocas or any(r.posible_cubrebocas for r in rostros_ref):
            advertencias.append(
                "Se detectó un posible cubrebocas: la similitud tiende a bajar. "
                "Registra también una referencia con cubrebocas para mejorar el resultado."
            )
        for r in [rostro_prueba, *rostros_ref]:
            for a in r.advertencias:
                if a not in advertencias:
                    advertencias.append(a)

        return ResultadoVerificacion(
            coincide=similitud >= self.umbral,
            similitud=similitud,
            umbral=self.umbral,
            nivel_confianza=self._nivel_confianza(similitud),
            indice_referencia=indice,
            similitudes=similitudes,
            rostro_prueba=rostro_prueba,
            rostros_referencia=rostros_ref,
            advertencias=advertencias,
            tiempo_ms=round((time.perf_counter() - inicio) * 1000, 1),
        )

    def detectar(self, datos: bytes) -> tuple[list[Rostro], tuple[int, int], list[str]]:
        """Devuelve todos los rostros encontrados y el tamaño de la imagen analizada."""
        img, advertencias = self.preparar(self.decodificar(datos))
        h, w = img.shape[:2]
        return self.detectar_rostros(img), (w, h), advertencias

    def info(self) -> dict:
        return {
            "detector": self.NOMBRE_DETECTOR,
            "reconocedor": self.NOMBRE_RECONOCEDOR,
            "metrica": "similitud coseno",
            "umbral_similitud": self.umbral,
            "confianza_deteccion": self.confianza_deteccion,
            "lado_maximo_px": self.lado_maximo,
        }
