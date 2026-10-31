"""Evaluación del modelo por escenario (sin oclusión, cubrebocas, lentes, etc.).

Lee un CSV de pares de fotos y calcula, para cada escenario:
  * Exactitud
  * FMR  (tasa de falsas coincidencias: impostores aceptados)
  * FNMR (tasa de falsos rechazos: personas genuinas rechazadas)
  * Similitud promedio de pares genuinos e impostores
  * Umbral que minimiza los errores en ese escenario

Formato del CSV (ver datos_evaluacion/pares_ejemplo.csv):
  referencia,prueba,misma_persona,escenario
  fotos/ana_1.jpg,fotos/ana_cubrebocas.jpg,1,cubrebocas
Para usar varias referencias, sepáralas con "|":
  fotos/ana_1.jpg|fotos/ana_cubrebocas.jpg,fotos/ana_ambos.jpg,1,cubrebocas_multiple

Uso dentro del contenedor de pruebas:
  docker run --rm -v "${PWD}/datos_evaluacion:/app/datos_evaluacion" vf-test \
      python scripts/evaluar.py datos_evaluacion/pares.csv
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import cargar_configuracion  # noqa: E402
from app.face_model import ErrorVerificacion, VerificadorFacial  # noqa: E402


def mejor_umbral(genuinos: list[float], impostores: list[float]) -> tuple[float, int]:
    candidatos = sorted(set(genuinos + impostores + [0.363]))
    mejor, errores_min = 0.363, len(genuinos) + len(impostores) + 1
    for u in candidatos:
        errores = sum(s < u for s in genuinos) + sum(s >= u for s in impostores)
        if errores < errores_min:
            mejor, errores_min = u, errores
    return round(mejor, 3), errores_min


def porcentaje(a: int, b: int) -> str:
    return f"{100 * a / b:.1f} %" if b else "N/D"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalúa el modelo por escenario")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--umbral", type=float, default=None)
    args = parser.parse_args()

    config = cargar_configuracion()
    umbral = args.umbral if args.umbral is not None else config.umbral_similitud
    modelo = VerificadorFacial(config.ruta_detector, config.ruta_reconocedor, umbral=umbral)
    base = args.csv.parent

    filas_salida = []
    por_escenario: dict[str, dict] = defaultdict(lambda: {"gen": [], "imp": [], "fallos": 0, "ms": []})

    with args.csv.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            escenario = fila["escenario"].strip()
            misma = fila["misma_persona"].strip() == "1"
            datos = por_escenario[escenario]
            try:
                refs = [(base / r.strip()).read_bytes() for r in fila["referencia"].split("|")]
                prueba = (base / fila["prueba"]).read_bytes()
                r = modelo.verificar(refs, prueba)
                (datos["gen"] if misma else datos["imp"]).append(r.similitud)
                datos["ms"].append(r.tiempo_ms)
                correcto = r.coincide == misma
                filas_salida.append({**fila, "similitud": r.similitud, "coincide": int(r.coincide),
                                     "correcto": int(correcto),
                                     "cubrebocas_detectado": r.rostro_prueba.posible_cubrebocas,
                                     "tiempo_ms": r.tiempo_ms, "error": ""})
            except (ErrorVerificacion, OSError) as exc:
                datos["fallos"] += 1
                filas_salida.append({**fila, "similitud": "", "coincide": "", "correcto": 0,
                                     "cubrebocas_detectado": "", "tiempo_ms": "", "error": str(exc)})

    salida_csv = base / "resultados_detalle.csv"
    if filas_salida:
        with salida_csv.open("w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=list(filas_salida[0].keys()))
            escritor.writeheader()
            escritor.writerows(filas_salida)

    lineas = [
        f"# Resultados de evaluación (umbral = {umbral})", "",
        "| Escenario | Pares | Exactitud | FMR | FNMR | Sim. genuinos | Sim. impostores "
        "| Sin rostro | Umbral óptimo | Tiempo prom. |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for escenario, d in sorted(por_escenario.items()):
        gen, imp = d["gen"], d["imp"]
        falsos_rechazos = sum(s < umbral for s in gen)
        falsas_coinc = sum(s >= umbral for s in imp)
        total = len(gen) + len(imp)
        aciertos = total - falsos_rechazos - falsas_coinc
        umbral_opt, _ = mejor_umbral(gen, imp) if gen and imp else ("N/D", 0)
        prom = lambda xs: f"{statistics.mean(xs):.3f}" if xs else "N/D"  # noqa: E731
        lineas.append(
            f"| {escenario} | {total + d['fallos']} | {porcentaje(aciertos, total)} "
            f"| {porcentaje(falsas_coinc, len(imp))} | {porcentaje(falsos_rechazos, len(gen))} "
            f"| {prom(gen)} | {prom(imp)} | {d['fallos']} | {umbral_opt} "
            f"| {prom(d['ms'])} ms |"
        )
    resumen = "\n".join(lineas)
    (base / "resultados_resumen.md").write_text(resumen + "\n", encoding="utf-8")
    print(resumen)
    print(f"\nDetalle guardado en {salida_csv}")


if __name__ == "__main__":
    main()
