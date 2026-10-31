# Verificación facial con cubrebocas y lentes

![CI](https://github.com/pardo-salas/verificacion-facial/actions/workflows/ci.yml/badge.svg)

Sistema que verifica si dos fotografías corresponden a la **misma persona**, incluso cuando
usa **cubrebocas** o **lentes antirreflejantes**. Lo desarrollé como proyecto de la Fase 2 de
*Gestión de proyectos de inteligencia artificial* (Universidad Tecmilenio).

| Componente | Tecnología | Puerto local |
|---|---|---|
| Backend (API REST) | Python 3.11, FastAPI, OpenCV | `8000` |
| Modelo de detección | YuNet (ONNX, OpenCV Zoo) | — |
| Modelo de reconocimiento | SFace (ONNX, OpenCV Zoo) | — |
| Frontend | HTML + CSS + JavaScript, Nginx | `8080` |
| Contenedores | Docker, Docker Compose | — |
| Nube | Render (Docker Web Service + Static Site) | — |

---

## 1. Cómo funciona

```
Navegador (frontend)  --HTTP/JSON-->  API FastAPI  -->  YuNet: detecta rostro + 5 puntos
                                                    -->  SFace: alinea y genera vector de 128 valores
                                                    -->  Similitud coseno >= 0.363  =>  misma persona
```

1. **Detección (YuNet):** encuentra el rostro y cinco puntos de referencia (ojos, nariz y
   comisuras). Sigue detectando rostros parcialmente cubiertos.
2. **Alineación y embedding (SFace):** recorta y alinea el rostro a 112 × 112 px y genera un
   vector numérico que representa la identidad.
3. **Comparación:** calcula la similitud coseno. Si es mayor o igual al umbral (0.363 por
   defecto), las fotos son de la misma persona.
4. **Robustez ante oclusiones:**
   * Se aceptan **hasta 5 fotos de referencia** y se toma la similitud máxima. Registrar una
     foto con cubrebocas y otra sin él mejora mucho los resultados.
   * Una heurística de color detecta un **posible cubrebocas** y avisa al usuario.
   * Se reportan advertencias de calidad: poca luz, desenfoque, rostro pequeño, perfil o
     varias personas en la foto.

## 2. Estructura del repositorio

```
verificacion-facial/
├── app/                      # Backend
│   ├── main.py               # API FastAPI (endpoints)
│   ├── face_model.py         # Modelo: detección, embeddings y comparación
│   ├── schemas.py            # Esquemas de respuesta (Pydantic)
│   ├── config.py             # Configuración por variables de entorno
│   └── healthcheck.py        # Healthcheck del contenedor
├── frontend/                 # Interfaz web + Dockerfile de Nginx
├── tests/                    # Pruebas automatizadas (pytest)
├── scripts/
│   ├── descargar_modelos.py  # Descarga y valida los modelos ONNX
│   └── evaluar.py            # Métricas por escenario (FMR, FNMR, exactitud)
├── datos_evaluacion/         # CSV de pares para la evaluación
├── docs/evidencias/          # Capturas de pantalla del proyecto
├── Dockerfile                # Imagen multi-etapa (base / test / runtime)
├── docker-compose.yml        # Backend + frontend en local
├── render.yaml               # Despliegue en Render (infraestructura como código)
├── .github/workflows/ci.yml  # Integración continua
├── requirements.txt          # Dependencias de producción (versiones fijas)
└── requirements-dev.txt      # Dependencias de pruebas
```

## 3. Requerimientos

| Requisito | Versión mínima |
|---|---|
| Docker Desktop (Windows/macOS) o Docker Engine (Linux) | 24 |
| Docker Compose | v2 |
| Git | 2.30 |
| RAM libre | 2 GB |
| Espacio en disco | 1.5 GB |
| Internet | Solo para construir la imagen (descarga dependencias y modelos) |

Para ejecutar sin Docker: Python 3.11.

## 4. Ejecución local con Docker

### 4.1 Clonar

```bash
git clone https://github.com/pardo-salas/verificacion-facial.git
cd verificacion-facial
```

### 4.2 Opción A: sistema completo con Docker Compose (recomendado)

```bash
docker compose up --build -d
docker compose ps          # ambos servicios deben aparecer como "healthy"/"running"
```

* Frontend: <http://localhost:8080>
* Documentación interactiva de la API (Swagger): <http://localhost:8000/docs>
* Salud: <http://localhost:8000/api/v1/health>

Para detener: `docker compose down`

### 4.3 Opción B: solo el backend con Docker

```bash
docker build -t verificacion-facial-api:1.0.0 .
docker run -d --name vf-api -p 8000:8000 verificacion-facial-api:1.0.0
docker ps                  # la columna STATUS debe decir "(healthy)" tras ~20 s
docker logs vf-api         # debe aparecer "Modelo cargado correctamente"
```

### 4.4 Ejecutar las pruebas dentro de Docker

```bash
docker build --target test -t vf-test .
docker run --rm vf-test
# Con fotos reales (opcional, ver tests/data/LEEME.md):
docker run --rm -v "${PWD}/tests/data:/app/tests/data" vf-test
```

### 4.5 Ejecución sin Docker (desarrollo)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/descargar_modelos.py --destino models
uvicorn app.main:app --reload
pytest -v
```

## 5. API

| Método | Endpoint | Descripción | Respuestas |
|---|---|---|---|
| GET | `/api/v1/health` | Estado del servicio y del modelo | 200, 503 |
| GET | `/api/v1/info` | Modelos, umbral y límites | 200, 503 |
| POST | `/api/v1/detectar` | Detecta rostros en una imagen (`imagen`) | 200, 400, 413, 415 |
| POST | `/api/v1/verificar` | Compara `prueba` contra 1–5 `referencias` | 200, 400, 413, 415, 422 |
| GET | `/docs` | Swagger UI generado automáticamente | 200 |

### Ejemplo con curl

```bash
curl -X POST http://localhost:8000/api/v1/verificar \
  -F "referencias=@fotos/ana_sin_cubrebocas.jpg" \
  -F "referencias=@fotos/ana_con_cubrebocas.jpg" \
  -F "prueba=@fotos/ana_lentes_cubrebocas.jpg"
```

### Respuesta

```json
{
  "coincide": true,
  "similitud": 0.512,
  "umbral": 0.363,
  "nivel_confianza": "media",
  "indice_referencia": 1,
  "similitudes": [0.401, 0.512],
  "rostro_prueba": {
    "caja": {"x": 212, "y": 140, "ancho": 260, "alto": 318},
    "confianza_deteccion": 0.88,
    "posible_cubrebocas": true,
    "advertencias": []
  },
  "rostros_referencia": ["..."],
  "advertencias": ["Se detectó un posible cubrebocas: la similitud tiende a bajar..."],
  "tiempo_ms": 142.7
}
```

*Los valores numéricos del ejemplo son ilustrativos.*

## 6. Variables de entorno

| Variable | Defecto | Descripción |
|---|---|---|
| `PORT` | `8000` | Puerto del servidor (Render lo asigna automáticamente) |
| `UMBRAL_SIMILITUD` | `0.363` | Umbral de similitud coseno para aceptar |
| `CONFIANZA_DETECCION` | `0.6` | Confianza mínima de YuNet |
| `MAX_MB_IMAGEN` | `5` | Tamaño máximo por imagen |
| `MAX_REFERENCIAS` | `5` | Referencias máximas por solicitud |
| `LADO_MAXIMO_PX` | `1280` | Las fotos más grandes se reducen a este tamaño |
| `CORS_ORIGINS` | `*` | Orígenes permitidos, separados por comas |
| `API_URL` (frontend) | `http://localhost:8000` | URL de la API que usa el navegador |

## 7. Despliegue en la nube (Render)

**Estrategia:** contenedor Docker en una plataforma PaaS. Render construye la misma imagen
del `Dockerfile` que uso en local, así que el comportamiento es idéntico (portabilidad).

### Opción automática (Blueprint)

1. Sube el repositorio a GitHub.
2. Entra a <https://dashboard.render.com> → **New** → **Blueprint**.
3. Conecta tu cuenta de GitHub y elige este repositorio. Render lee `render.yaml` y crea:
   * `verificacion-facial-api` (Docker Web Service)
   * `verificacion-facial-web` (Static Site)
4. Pulsa **Apply** y espera a que la construcción termine (5–10 min la primera vez).
5. Si Render asignó URLs distintas a las de `render.yaml`, actualiza `CORS_ORIGINS` en la API
   y `API_URL` en el sitio estático (**Environment**) y vuelve a desplegar.
6. Verifica: `https://<tu-api>.onrender.com/api/v1/health` debe devolver `"estado": "ok"`.

### Opción manual

1. **New → Web Service** → elige el repositorio → Runtime **Docker** → Plan **Free**.
2. **Health Check Path:** `/api/v1/health`.
3. **Environment:** agrega `CORS_ORIGINS` con la URL del frontend.
4. **New → Static Site** → mismo repositorio → **Build Command:**
   `sh frontend/generar_config.sh frontend/config.js` → **Publish Directory:** `frontend`
   → variable `API_URL` con la URL de la API.

> En el plan gratuito, el servicio se suspende tras 15 minutos sin tráfico; la primera
> solicitud después tarda alrededor de un minuto en responder (arranque en frío).

### Alternativas evaluadas

La misma imagen funciona sin cambios en Google Cloud Run, Azure Container Apps o AWS App
Runner, porque toma el puerto de la variable `PORT` y no guarda estado.

## 8. Privacidad

Las imágenes se procesan **en memoria** y no se guardan. Los datos biométricos son datos
personales sensibles: solo uso fotos con consentimiento y las fotos de prueba están
excluidas del repositorio mediante `.gitignore`.

## 9. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `docker build` falla en la descarga de modelos | Sin internet o GitHub bloqueado | Revisa la conexión y reintenta |
| `/health` devuelve 503 | No se encontraron los modelos | Reconstruye la imagen sin caché: `docker build --no-cache .` |
| El frontend dice "API no disponible" | Backend apagado o `API_URL` incorrecta | `docker compose ps`; revisa `API_URL` |
| Error de CORS en la consola del navegador | `CORS_ORIGINS` no incluye la URL del frontend | Agrega la URL exacta (con `https://`) |
| Puerto 8000 ocupado | Otro programa lo usa | `docker run -p 8001:8000 ...` |
| La cámara no abre | El navegador exige HTTPS o `localhost` | Usa `localhost` o la URL `https` de Render |
| 422 "No se detectó ningún rostro" | Foto muy oscura, de perfil o sin rostro | Usa una foto frontal con buena luz |
