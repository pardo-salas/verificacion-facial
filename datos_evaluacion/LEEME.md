# Datos de evaluación

1. Crea la carpeta `datos_evaluacion/fotos/` y coloca ahí las fotos (con consentimiento).
2. Copia `pares_ejemplo.csv` como `pares.csv` y agrega una fila por cada par:
   * `misma_persona`: 1 si es la misma persona, 0 si es otra.
   * `escenario`: nombre libre (sin_oclusion, lentes, cubrebocas, ...).
   * Varias referencias: sepáralas con `|` en la columna `referencia`.
3. Ejecuta:

```bash
docker build --target test -t vf-test .
docker run --rm -v "${PWD}/datos_evaluacion:/app/datos_evaluacion" vf-test \
    python scripts/evaluar.py datos_evaluacion/pares.csv
```

Se generan `resultados_resumen.md` y `resultados_detalle.csv` (no se suben a GitHub).
