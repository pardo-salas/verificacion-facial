# Instrucciones rápidas de ejecución con Docker

## Sistema completo (backend + frontend)
```bash
docker compose up --build -d
```
* Frontend: http://localhost:8080
* API (Swagger): http://localhost:8000/docs
* Salud: http://localhost:8000/api/v1/health

## Solo el backend
```bash
docker build -t verificacion-facial-api:1.0.0 .
docker run -d --name vf-api -p 8000:8000 verificacion-facial-api:1.0.0
docker ps        # debe mostrar (healthy)
```

## Pruebas
```bash
docker build --target test -t vf-test .
docker run --rm vf-test
```

## Detener
```bash
docker compose down
docker rm -f vf-api
```

El manual completo está en README.md.
