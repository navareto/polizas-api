# polizas-api

Servicio de gestión de pólizas de la Aseguradora Santo Tomás. Registra pólizas y los siniestros que se les
declaran, resume la cartera y puntúa el riesgo de cada póliza con un modelo, guardando cada predicción.

Taller del Corte II (USTA, Python para APIs e IA, 2026-II): este repositorio es el servicio del semilla
`polizas-api-v0` ya diagnosticado y corregido. Los hallazgos están en [HALLAZGOS.md](HALLAZGOS.md).

## Requisitos

- Python **3.11.9** (la misma versión que usa el `Dockerfile`; las versiones de `requirements.txt` están probadas ahí).
- Docker, solo si se quiere ejecutar en contenedor.

## Arranque local (uvicorn)

```bash
python -m venv .venv
source .venv/bin/activate            # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # valores de ejemplo con los que el servicio arranca
alembic upgrade head                 # crea el esquema en la base de DATABASE_URL
uvicorn main:app --host 127.0.0.1 --port 8000
```

Comprobación: `curl localhost:8000/health` responde `{"status":"ok","database":"ok"}`.
La documentación interactiva está en `http://localhost:8000/docs`.

La base de datos se elige con `DATABASE_URL` (por defecto `sqlite:///./polizas.db`). El esquema **no** se crea
al arrancar: lo crea Alembic. `--reload` es solo para desarrollo; en un servidor se arranca sin él.

## En contenedor (Docker)

```bash
docker build -t polizas-api .
docker run -p 8000:8000 polizas-api
curl localhost:8000/health
```

La imagen se construye en dos etapas sobre `python:3.11.9-slim-bookworm`, corre como usuario sin privilegios
(`app`), trae un `HEALTHCHECK` y no contiene `.env` ni bases de datos. Al arrancar aplica
`alembic upgrade head` sobre `/data/polizas.db` y escucha en `0.0.0.0:8000`.

**Qué pasa con los datos.** La base vive en `/data`, que es un volumen:

| Acción | ¿Se conservan los datos? |
|---|---|
| `docker restart <contenedor>` | Sí: es el mismo contenedor y el mismo volumen. |
| Borrar el contenedor y levantar otro desde la misma imagen | No: el nuevo contenedor recibe un volumen vacío. |
| Montar un volumen con nombre: `docker run -p 8000:8000 -v polizas-data:/data polizas-api` | Sí, también entre contenedores distintos. |

Para pasar configuración propia: `docker run --env-file .env ...` (por ejemplo `SECRETO_FIRMA`). Si no se define, el
proceso genera un secreto efímero.

## Endpoints

| Método | Ruta | Qué hace | Códigos |
|---|---|---|---|
| GET | `/health` | Indica si el servicio y la base responden | 200 · 503 |
| POST | `/polizas` | Crea una póliza, con sus siniestros si ya tiene | 201 · 409 si el número existe · 422 |
| GET | `/polizas` | Lista las pólizas con sus siniestros | 200 |
| GET | `/polizas/{id}` | Consulta una póliza | 200 · 404 |
| PUT | `/polizas/{id}` | Actualización parcial: solo cambia lo que se envía | 200 · 404 · 422 |
| POST | `/polizas/{id}/siniestros` | Declara un siniestro | 201 · 404 · 422 |
| GET | `/siniestros` | Lista los siniestros con el número de su póliza | 200 |
| GET | `/resumen` | Siniestros y monto total por póliza | 200 |
| POST | `/score` | Puntúa el riesgo de una póliza y guarda la predicción | 200 · 404 · 422 |
| GET | `/predicciones` | Histórico de predicciones, con el número de la póliza | 200 |

### Ejemplo

```bash
curl -X POST localhost:8000/polizas -H "Content-Type: application/json" \
  -d '{"numero": "POL-2026-09001", "asegurado": "Ana Rueda", "tipo": "auto", "prima": 1250000,
       "fecha_inicio": "2026-01-15", "fecha_fin": "2027-01-14"}'
curl -X POST localhost:8000/score -H "Content-Type: application/json" -d '{"numero": "POL-2026-09001"}'
```

## Configuración

Se lee del entorno y de `.env` con `pydantic-settings` (ver `.env.example`). `.env` no se versiona.

| Variable | Para qué | Por defecto |
|---|---|---|
| `DATABASE_URL` | Base de datos de la aplicación y de Alembic | `sqlite:///./polizas.db` |
| `SECRETO_FIRMA` | Firma del token interno de cada póliza | un valor efímero por proceso |
| `UMBRAL_ALTO_RIESGO` | Probabilidad desde la que `/score` marca `alto_riesgo` | `0.6` |
| `RUTA_MODELO` | Modelo serializado | `modelo.pkl` junto a `main.py` |

## Estructura

| Archivo | Responsabilidad |
|---|---|
| `main.py` | Rutas HTTP: validan la entrada, llaman a `servicios` y declaran el esquema de salida |
| `servicios.py` | Reglas de negocio, resumen, puntaje y estrategia de carga de relaciones |
| `esquemas.py` | Modelos Pydantic v2 de entrada y de salida |
| `modelos.py` / `database.py` | Tablas SQLAlchemy 2.0, motor y sesión por petición (`get_db`) |
| `config.py` | `Settings` (BaseSettings) con caché |
| `alembic/` | Migraciones; `env.py` toma la URL de `DATABASE_URL` |

## Pruebas

```bash
pytest                               # contrato, pruebas propias y batería corregida de la Parte D
```

Cada prueba corre sobre una base SQLite temporal con el esquema de Alembic y sustituye `database.get_db` con
`app.dependency_overrides`: la base de la aplicación no se toca y dos corridas seguidas dan el mismo resultado.

## Utilidades

- `sembrar_datos.py` crea pólizas de ejemplo a través de la API: `python sembrar_datos.py --polizas 12`.
- `contar_consultas.py` cuenta las sentencias SQL de cada endpoint y escribe `CONSULTAS.csv`
  (`python contar_consultas.py`); con `--alternativas` mide las otras estrategias de carga.
- `verificar_entrega.py` comprueba que el repositorio tiene la forma que espera el calificador.
