# Dictamen sobre `ia_tests_propuesta.py` — Parte D

**Grupo:** individual · **Integrantes:** Edwing Navarrete

> Tres defectos. Las cuatro secciones de cada uno son obligatorias y se parsean.
> El peso está en **«Cómo lo comprobamos»**, y la comprobación tiene una forma
> concreta: **una mutación**. Introduzcan a propósito un defecto en el servicio,
> muestren que el test original sigue en verde y que el corregido se pone en rojo,
> y vuelvan a dejar el servicio como estaba. Afirmar que un test es malo no vale;
> demostrar que no detecta nada, sí.

**Cómo se hicieron las pruebas.** Cada mutación se aplicó en una copia temporal del commit (`git worktree`),
nunca sobre el árbol de trabajo: el servicio del repositorio quedó como estaba (`git status` limpio). La
propuesta de la IA se ejecutó con `DATABASE_URL=sqlite:///./real.db`, una base ya migrada con
`alembic upgrade head`, porque es la que usaría la aplicación. En las salidas solo se acortaron las rutas
absolutas. Sobre el servicio sano, la propuesta da `6 passed` y la corregida `35 passed`. Los tres
experimentos los reprodujo además Edwing a mano, en una copia nueva del repositorio, y obtuvo el mismo
comportamiento (ver `BITACORA_IA.md`, prompt 12).

**Cuánto detecta la batería corregida.** Además de las tres mutaciones de abajo, se midió con 21 mutantes en
todas las rutas (cada 404, cada `commit`, cada validador, los códigos 201, la fuga de `token_firma`,
`alto_riesgo`, `/health`...). La primera versión de `tests/test_ia_corregido.py`, ejecutada sola, detectaba solo
9 de los 21; se amplió a los nueve endpoints y ahora detecta **20 de 21**. El que sobrevive es un mutante
equivalente (añadir un valor por defecto a `numero` en un esquema de salida que ya lo lee del modelo: no cambia
ningún comportamiento observable).

## Defecto 1

- **Qué está mal**: las aserciones aceptan casi cualquier resultado: `status_code in (200, 201, 422)`, `in (200, 404)`, `< 500`, `"puntaje" in r.json() or "error" in r.json()` y `isinstance(r.json(), list)`. Una prueba así no puede fallar por la razón que dice vigilar: «consultar póliza inexistente» aprueba tanto con un 404 correcto como con un 200 erróneo.
- **Por qué es un defecto** (módulo · sección): M10 · 4. Framework pytest. Una aserción debe fijar el valor esperado; si admite varios resultados, incluido el defectuoso, no verifica el contrato (el taller exige 404 cuando la póliza no existe).
- **Cómo lo comprobamos**: mutación en el servicio: cualquier «no existe» deja de ser 404 y pasa a ser 200 (es el defecto H5 de la Parte A). La propuesta sigue en verde; la corregida se pone en rojo.

```diff
diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -36,3 +36,3 @@ def _responder(codigo: int):
-app.add_exception_handler(servicios.PolizaNoExiste, _responder(status.HTTP_404_NOT_FOUND))
+app.add_exception_handler(servicios.PolizaNoExiste, _responder(status.HTTP_200_OK))
 app.add_exception_handler(servicios.NumeroDuplicado, _responder(status.HTTP_409_CONFLICT))
```

```
$ python -m pytest ia_tests_propuesta.py -q -p no:cacheprovider --tb=line
6 passed, 1 warning in 1.55s
```

```
$ python -m pytest tests/test_ia_corregido.py -q -p no:cacheprovider --tb=line -rf
E   AssertionError: assert 200 == 404
FAILED tests/test_ia_corregido.py::test_consultar_poliza_inexistente_da_404
FAILED tests/test_ia_corregido.py::test_actualizar_poliza_inexistente_da_404
FAILED tests/test_ia_corregido.py::test_declarar_siniestro_en_poliza_inexistente_da_404_y_no_deja_huerfanos
FAILED tests/test_ia_corregido.py::test_score_de_poliza_inexistente_da_404_y_no_registra
4 failed, 31 passed, 1 warning in 2.68s
```

- **Corrección**: cada aserción fija el resultado esperado (`== 404` con su `detail`, `== 201`, `== 422`, `== 409`), y los listados se comparan con el contenido exacto en vez de con «no falla» (`tests/test_ia_corregido.py`).

## Defecto 2

- **Qué está mal**: la propuesta dice aislar la base con una sesión simulada (`MagicMock`), pero registra el override sobre una función local (`app.dependency_overrides[get_db] = get_db`, con un `get_db` definido en el propio archivo) y no sobre `database.get_db`: la aplicación nunca usa el doble y todo se escribe en la base real. Además no verifica ningún efecto: `test_score_de_poliza_recien_creada` solo busca la clave `puntaje` y jamás consulta `/predicciones`, y las pruebas de creación no leen lo que se guardó.
- **Por qué es un defecto** (módulo · sección): M10 · 5. TestClient de FastAPI. `dependency_overrides` solo sustituye la dependencia que la ruta realmente declara; con otra clave no se sustituye nada, la prueba no está aislada y deja efectos en la base.
- **Cómo lo comprobamos**: mutación en el servicio: `/score` deja de guardar la predicción (se quitan `db.add` y `db.commit`). La propuesta no lo nota porque nunca mira lo registrado; la corregida sí. Además, tras correr la propuesta sobre el servicio sano, la base real contiene 7 pólizas y 1 predicción que escribieron las pruebas, y la corregida no añade nada.

```diff
diff --git a/servicios.py b/servicios.py
--- a/servicios.py
+++ b/servicios.py
@@ -140,4 +140,2 @@ def puntuar(db: Session, modelo: Any, numero: str, umbral: float) -> tuple[str,
     prediccion = Prediccion(poliza_id=poliza.id, puntaje=puntaje, alto_riesgo=puntaje > umbral)
-    db.add(prediccion)
-    db.commit()
     return poliza.numero, round(puntaje, 4), prediccion.alto_riesgo
```

```
$ python -m pytest ia_tests_propuesta.py -q -p no:cacheprovider --tb=line
6 passed, 1 warning in 1.52s

# aislamiento falso (misma propuesta sobre el servicio sano): filas que quedaron en real.db
{'polizas': 7, 'siniestros': 0, 'predicciones': 1}
```

```
$ python -m pytest tests/test_ia_corregido.py -q -p no:cacheprovider --tb=line -rf
E   AssertionError: assert 0 == 2
FAILED tests/test_ia_corregido.py::test_score_de_poliza_recien_creada_registra_la_prediccion[500000]
FAILED tests/test_ia_corregido.py::test_score_de_poliza_recien_creada_registra_la_prediccion[4800000]
FAILED tests/test_ia_corregido.py::test_cada_score_agrega_una_prediccion
3 failed, 32 passed, 1 warning in 2.64s

# la corregida (servicio sano) sobre una real.db recién migrada: no escribe nada, sigue vacía
{'polizas': 0, 'siniestros': 0, 'predicciones': 0}
```

- **Corrección**: la fixture `cliente` (`tests/conftest.py`) sustituye exactamente `database.get_db` con una sesión sobre una base temporal cuyo esquema crea Alembic, y las pruebas comprueban el efecto: leen siempre el efecto en una petición nueva (la póliza creada o actualizada con `GET`, los siniestros guardados), comparan `/resumen` con los números exactos y exigen que `/predicciones` contenga la predicción con el número de su póliza, con `alto_riesgo` coherente con el umbral configurado.

## Defecto 3

- **Qué está mal**: los datos de prueba son aleatorios y sin semilla (`random.choice`, `random.uniform(1, 5_000_000)`, `uuid.uuid4`). Cada corrida prueba un caso distinto, así que el resultado cambia de una corrida a otra sin tocar el código y un fallo no se puede reproducir.
- **Por qué es un defecto** (módulo · sección): M10 · 7. Reproducibilidad sin Docker. La reproducibilidad exige semillas explícitas y datos deterministas: dos corridas del mismo código deben dar el mismo resultado.
- **Cómo lo comprobamos**: mutación en el servicio: el esquema rechaza primas superiores a 4 000 000 (un validador que rechaza lo que no debe). La propuesta, que sortea la prima entre 1 y 5 000 000, falló en 3 de 20 corridas idénticas, o sea que unas veces pasa y otras no; la corregida usa primas fijas, incluidas las que cruzan el límite, y se pone en rojo en todas las corridas.

```diff
diff --git a/esquemas.py b/esquemas.py
--- a/esquemas.py
+++ b/esquemas.py
@@ -20,3 +20,3 @@ class PolizaEntrada(BaseModel):
     tipo: str = Field(min_length=3, max_length=10, description="auto, hogar o vida")
-    prima: float = Field(gt=0, description="Prima anual, en pesos")
+    prima: float = Field(gt=0, le=4_000_000, description="Prima anual, en pesos")
     fecha_inicio: date
```

```
$ for i in $(seq 1 20); do python -m pytest ia_tests_propuesta.py -q -p no:cacheprovider --tb=line | tail -1; done
corrida 01: 6 passed        corrida 11: 6 passed
corrida 02: 6 passed        corrida 12: 6 passed
corrida 03: 6 passed        corrida 13: 1 failed, 5 passed
corrida 04: 6 passed        corrida 14: 6 passed
corrida 05: 6 passed        corrida 15: 6 passed
corrida 06: 6 passed        corrida 16: 6 passed
corrida 07: 6 passed        corrida 17: 1 failed, 5 passed
corrida 08: 6 passed        corrida 18: 6 passed
corrida 09: 6 passed        corrida 19: 6 passed
corrida 10: 1 failed, 5 passed   corrida 20: 6 passed
-> 17 corridas en verde y 3 en rojo, con el mismo código

# una corrida en rojo de otra tanda, con el detalle del fallo
ia_tests_propuesta.py::test_score_de_poliza_recien_creada - assert 404...
E   assert 404 == 200
1 failed, 5 passed, 1 warning in 2.01s
```

```
$ for i in 1 2 3; do python -m pytest tests/test_ia_corregido.py -q -p no:cacheprovider --tb=line | tail -1; done
corrida 1: 4 failed, 31 passed, 1 warning in 2.62s
corrida 2: 4 failed, 31 passed, 1 warning in 2.63s
corrida 3: 4 failed, 31 passed, 1 warning in 2.61s

FAILED tests/test_ia_corregido.py::test_primas_validas_son_aceptadas_con_201[4000000.5]
FAILED tests/test_ia_corregido.py::test_primas_validas_son_aceptadas_con_201[4800000]
FAILED tests/test_ia_corregido.py::test_primas_validas_son_aceptadas_con_201[5000000]
FAILED tests/test_ia_corregido.py::test_score_de_poliza_recien_creada_registra_la_prediccion[4800000]
```

- **Corrección**: se eliminan `random` y `uuid`: las primas salen de `pytest.mark.parametrize` con valores fijos que incluyen los bordes (0,01; 1; 4 000 000,5; 4 800 000; 5 000 000) y los números de póliza son constantes; así la misma mutación falla siempre, y sin mutación pasa siempre.
