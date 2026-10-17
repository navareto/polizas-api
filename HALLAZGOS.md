# Hallazgos — Parte A

**Grupo:** individual · **Integrantes:** Edwing Navarrete

> No borren la fila de ejemplo hasta haber comprobado que su tabla se parsea
> (`python verificar_entrega.py`). El formato es rígido: ocho columnas, en este
> orden. Una tabla torcida se rechaza indicando la línea, no se «entiende igual».
>
> **Tuberías dentro de una celda:** si su comando lleva `|` —y varios lo llevarán,
> por `grep`, `head` o `jq`— escríbanlo `\|`. Sin escapar, Markdown lo lee como
> separador de columna y su fila pasa a tener nueve.

| ID | Síntoma observable | Causa | Módulo · Sección | SHA donde se observa | Comando de evidencia | Salida obtenida | Corrección aplicada |
|----|--------------------|-------|------------------|----------------------|----------------------|-----------------|---------------------|
| H1 | *(ejemplo de FORMATO, no un defecto de este repositorio)* `GET /health` responde sin cabecera `Cache-Control` | El handler no declara política de caché | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -sI localhost:8000/health \| grep -ci cache-control` | `0` | Se añade la cabecera en la respuesta |
| H2 | `config.py` guarda `SECRETO_FIRMA` y `CLAVE_API_REASEGURO` en claro y versionados en el repositorio | La configuración y los secretos están escritos como constantes en el código en vez de leerse del entorno; el propio archivo lo admite con un `TODO` | M8 · 3. De lo duro a lo flexible: variables de entorno | `v0-semilla` | `grep -cE "^(SECRETO_FIRMA\|CLAVE_API_REASEGURO) *=" config.py` | `2` | `Settings(BaseSettings)` lee los valores de `.env`, con `lru_cache` e inyección por `Depends`; `.env` queda fuera de git y `.env.example` trae valores de ejemplo |
| H3 | `requirements.txt` lista las ocho dependencias sin versión: una instalación nueva trae versiones distintas de las probadas | Nunca se fijaron las versiones (ninguna línea lleva `==`), así que el entorno no es reproducible | M10 · 7. Reproducibilidad sin Docker | `v0-semilla` | `grep -vc "==" requirements.txt` | `8` | `requirements.txt` con la versión exacta de cada dependencia, probada sobre Python 3.11.9 |
| H4 | Con `DATABASE_URL` apuntando a otra base, la aplicación sigue creando y usando `app.db`: no honra la variable | `config.py` fija `DATABASE_URL = "sqlite:///app.db"` como constante y `database.py` crea el motor al importarse, sin leer el entorno; además `app.db` está versionada | M8 · 3. De lo duro a lo flexible: variables de entorno | `v0-semilla` | `rm -f h_evidencia.db; DATABASE_URL=sqlite:///h_evidencia.db python -c "import main"; test -f h_evidencia.db && echo existe \|\| echo no-existe; rm -f h_evidencia.db` | `no-existe` | La URL sale de `Settings` (`DATABASE_URL`); `app.db` sale del índice de git y `.gitignore` cubre `.env`, `*.db` y el entorno virtual |
| H5 | Las respuestas incluyen `token_firma`, un campo interno derivado del secreto de firma | Las rutas devuelven el objeto ORM o un diccionario armado a mano sin `response_model`, así que se serializa todo lo que tenga el modelo | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s localhost:8000/polizas \| grep -c token_firma` | `1` | Esquemas de salida con `from_attributes=True` y `response_model` en todas las rutas; `token_firma` ya no se expone |
| H6 | Una póliza inexistente responde `200` con `{"error": ...}` (igual en `PUT` y en `/score`), y crear responde `200` en vez de `201` | Los handlers devuelven diccionarios de error y no declaran `status_code` ni lanzan `HTTPException` | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/polizas/999999` | `200` | `HTTPException(404)` cuando no existe, `status_code=201` al crear, 409 si el número ya existe y 422 por validación |
| H7 | Al crear una póliza con asegurado «Ana Rueda», la respuesta trae `"asegurado":null` | El `field_validator` `normalizar_asegurado` calcula el valor normalizado pero no lo devuelve: falta el `return`, y el campo queda en `None` | M7 · 4. Validadores de campo | `v0-semilla` | `curl -s -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"POL-VAL-$(date +%s)\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2026-01-15\",\"fecha_fin\":\"2027-01-14\"}" \| grep -o '"asegurado":[^,]*'` | `"asegurado":null` | El validador devuelve el valor normalizado |
| H8 | `PUT /polizas/1` enviando solo `prima` deja `asegurado`, `tipo` y `fecha_fin` en `null` | El `PUT` hace `model_dump()` sin `exclude_unset=True` y asigna con `setattr` todos los campos, incluidos los que el cliente no envió | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -X PUT localhost:8000/polizas/1 -H "Content-Type: application/json" -d '{"prima": 999000}' \| grep -oE '"(asegurado\|tipo\|fecha_fin)":null' \| wc -l \| tr -d ' '` | `3` | La actualización es parcial: `model_dump(exclude_unset=True)` y solo se asignan los campos enviados |
| H9 | Se acepta con `200` una póliza cuya `fecha_fin` es anterior a `fecha_inicio` | Solo se validan las fechas por separado; no existe un `model_validator` que compare los dos campos | M7 · 5. Modelos anidados y topología jerárquica | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"POL-FEC-$(date +%s)\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2027-01-14\",\"fecha_fin\":\"2026-01-15\"}"` | `200` | `model_validator(mode="after")` exige `fecha_fin` posterior a `fecha_inicio` y responde 422 si no |
| H10 | `POST /polizas` acepta con `200` un siniestro anidado con `monto: -50`; el monto, la fecha y la descripción no se validan | El campo `siniestros` se tipa como `list[dict]`, sin submodelo, así que los `Field` de `SiniestroEntrada` nunca se aplican a los siniestros anidados | M7 · 5. Modelos anidados y topología jerárquica | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"POL-SIN-$(date +%s)\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2026-01-15\",\"fecha_fin\":\"2027-01-14\",\"siniestros\":[{\"fecha\":\"2026-03-02\",\"monto\":-50,\"descripcion\":\"x\"}]}"` | `200` | `siniestros: list[SiniestroEntrada]`, con lo que el monto negativo da 422 |
| H11 | `POST /polizas/999999/siniestros` responde `200` y guarda un siniestro huérfano; después `GET /siniestros` responde `500` | SQLite no aplica claves foráneas por defecto (falta `PRAGMA foreign_keys=ON`), la ruta no comprueba que la póliza exista y `_siniestro` asume que `s.poliza` nunca es nulo | M9 · 7. SQLite local e integración con FastAPI | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code} " -X POST localhost:8000/polizas/999999/siniestros -H "Content-Type: application/json" -d '{"fecha":"2026-03-02","monto":850000,"descripcion":"Choque leve"}'; curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/siniestros` | `200 500` | `PRAGMA foreign_keys=ON` en cada conexión y 404 cuando la póliza no existe |
| H12 | `GET /polizas` emite una consulta por póliza más la consulta inicial: 1 + N | La relación `siniestros` se carga de forma perezosa (`lazy`, el valor por defecto) y el serializador la recorre dentro de un bucle | M9 · 6. Modelado de BD y migraciones con Alembic | `v0-semilla` | `python -W ignore -c "from sqlalchemy import event; from sqlalchemy.engine import Engine; n=[0]; event.listen(Engine, 'before_cursor_execute', lambda *a: n.__setitem__(0, n[0]+1)); from fastapi.testclient import TestClient; import main; c=TestClient(main.app); filas=c.get('/polizas').json(); n[0]=0; c.get('/polizas'); print('consultas == 1 + polizas:', n[0] == len(filas) + 1)"` | `consultas == 1 + polizas: True` | La estrategia de carga se decide y se mide por endpoint en la Parte C (ver `CONSULTAS.csv` y la sección «Parte C») |
| H13 | `pytest tests/test_api.py` pasa la primera vez y falla la segunda; los tests escriben en `app.db`, la base real | Los tests usan la aplicación y la base reales, sin `dependency_overrides` ni base temporal, y crean siempre la misma póliza (`POL-TEST-00001`) | M10 · 6. Fixtures en pytest | `v0-semilla` | `python -m pytest tests/test_api.py -q >/dev/null 2>&1; python -m pytest tests/test_api.py -q 2>&1 \| grep -c "^FAILED"` | `2` | Fixtures con base temporal y `app.dependency_overrides[get_db]`; la batería da el mismo resultado en dos corridas seguidas |
| H14 | El Dockerfile parte de `python:latest` y arranca con `--reload` escuchando solo en `127.0.0.1`: la imagen no es reproducible y el puerto no responde desde el host | Base sin versión fijada y un `CMD` copiado del modo desarrollo; además `COPY . .` sin `.dockerignore` mete `app.db`, y no hay `USER` ni `HEALTHCHECK`, así que corre como root | M11 · 7. Imagen base slim-bookworm | `v0-semilla` | `grep -cE "^FROM python:latest\|^CMD .*--reload.*127\.0\.0\.1" Dockerfile` | `2` | Dockerfile multietapa sobre `python:3.11.9-slim-bookworm`, con `.dockerignore`, usuario no root, `HEALTHCHECK` y `CMD` con `--host 0.0.0.0` y sin `--reload` |
| H15 | Tras crear dos pólizas con el mismo número, hasta `GET /polizas` responde `500`: el servicio queda inservible | Una sola sesión global (`sesion = SessionLocal()`) compartida por todas las peticiones: el commit fallido la deja pendiente de rollback y nadie la repara; el conflicto tampoco se captura (debería ser 409) | M8 · 4. Inyección de dependencias con Depends | `v0-semilla` | `N=POL-DUP-$(date +%s); for i in 1 2; do curl -s -o /dev/null -w "%{http_code} " -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"$N\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2026-01-15\",\"fecha_fin\":\"2027-01-14\"}"; done; curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/polizas` | `200 500 500` | `database.get_db` con `yield` y cierre en `finally`: una sesión por petición con `Depends(get_db)`; `IntegrityError` se convierte en 409 con `rollback` |

**Reglas que se verifican automáticamente:**

- `Módulo · Sección` debe citar una lección que exista en los módulos 6 a 11, con el
  título tal como aparece en el menú lateral del material.
- **`SHA donde se observa`** es el commit donde el defecto todavía está: normalmente
  `v0-semilla`, la etiqueta del repositorio tal como se les entregó. El calificador hace
  *checkout* de ese commit para reproducir la evidencia. Si lo dejan en el commit final
  —donde ya está corregido— el comando no reproducirá nada y la fila no cuenta.
- `Comando de evidencia` se ejecuta ahí, con el servicio levantado. Escríbanlo contra
  `localhost:8000`; el calificador sustituye el puerto por el que use. Un comando `docker`
  también vale: se reproduce si hay Docker en la máquina que califica.
- `Salida obtenida` es literal, copiada de su terminal. **Se compara con lo que salga de
  verdad**, así que una salida inventada se detecta.
- Entre 8 y 14 hallazgos. Una fila que no corresponda a un defecto real resta la mitad de
  lo que suma una correcta: el máximo se alcanza con precisión, no con volumen.

---

# Parte C — Interpretación de las consultas

> Un párrafo por endpoint. Expliquen **los conteos que ustedes obtuvieron** con
> `contar_consultas.py`: por qué ese número, por qué cambia o no entre 10 y 2000
> pólizas, y qué estrategia dejaron en el código. Si un resultado los sorprendió,
> díganlo: eso se premia.

## `/polizas`

## `/polizas/{id}`

## `/siniestros`

## `/resumen`
