"""Batería corregida de `ia_tests_propuesta.py` (Parte D). Cada prueba pasa sobre el servicio sano y se
pone en rojo cuando se le introduce una mutación (ver DICTAMEN_IA.md).

Lo que cambia respecto a la propuesta de la IA:
  1. Cada aserción fija el resultado esperado (201, 404, 422...), no un conjunto de resultados aceptables.
  2. Se verifica el EFECTO (lo guardado, lo listado, lo registrado), no solo que la ruta responda.
  3. Los datos son deterministas (parametrizados), sin `random` ni `uuid` sin semilla.
  4. El aislamiento es real: la sesión se sustituye con `app.dependency_overrides[database.get_db]`
     (fixture `cliente` de conftest.py), sobre una base temporal con el esquema de Alembic.

    pytest tests/test_ia_corregido.py -v
"""
import pytest

BASE = {
    "numero": "POL-IA-000001",
    "asegurado": "Prueba Automatica",
    "tipo": "auto",
    "prima": 1_250_000,
    "fecha_inicio": "2026-01-01",
    "fecha_fin": "2026-12-31",
}
SINIESTRO = {"fecha": "2026-03-02", "monto": 850_000, "descripcion": "Choque leve", "estado": "abierto"}


def _crear(cliente, **extra):
    r = cliente.post("/polizas", json={**BASE, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_crear_poliza_devuelve_201_y_queda_guardada(cliente):
    creada = _crear(cliente)
    leida = cliente.get(f"/polizas/{creada['id']}")
    assert leida.status_code == 200
    assert leida.json() == creada
    assert [p["numero"] for p in cliente.get("/polizas").json()] == [BASE["numero"]]


@pytest.mark.parametrize("prima", [0.01, 1, 1_000_000, 4_000_000.5, 4_800_000, 5_000_000])
def test_primas_validas_son_aceptadas_con_201(cliente, prima):
    r = cliente.post("/polizas", json={**BASE, "prima": prima})
    assert r.status_code == 201, r.text
    assert r.json()["prima"] == prima


@pytest.mark.parametrize("prima", [0, -1, -1_000_000])
def test_primas_no_positivas_dan_422_y_no_guardan_nada(cliente, prima):
    assert cliente.post("/polizas", json={**BASE, "prima": prima}).status_code == 422
    assert cliente.get("/polizas").json() == []


def test_consultar_poliza_inexistente_da_404(cliente):
    r = cliente.get("/polizas/999999")
    assert r.status_code == 404
    assert "error" not in r.json() and "999999" in r.json()["detail"]


def test_listar_polizas_devuelve_exactamente_las_creadas(cliente):
    creadas = [_crear(cliente, numero=f"POL-IA-00000{i}") for i in (1, 2, 3)]
    assert cliente.get("/polizas").json() == creadas


def test_numero_duplicado_da_409_y_no_duplica(cliente):
    _crear(cliente)
    assert cliente.post("/polizas", json=BASE).status_code == 409
    assert len(cliente.get("/polizas").json()) == 1


def test_resumen_tiene_los_numeros_exactos(cliente):
    _crear(cliente, siniestros=[SINIESTRO, {**SINIESTRO, "monto": 150_000}])
    _crear(cliente, numero="POL-IA-000002")
    assert cliente.get("/resumen").json() == [
        {"numero": "POL-IA-000001", "n_siniestros": 2, "monto_total": 1_000_000.0},
        {"numero": "POL-IA-000002", "n_siniestros": 0, "monto_total": 0.0},
    ]


@pytest.mark.parametrize("prima", [500_000, 4_800_000])
def test_score_de_poliza_recien_creada_registra_la_prediccion(cliente, prima):
    _crear(cliente, prima=prima, siniestros=[SINIESTRO])
    r = cliente.post("/score", json={"numero": BASE["numero"]})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["numero"] == BASE["numero"]
    assert 0.0 <= cuerpo["puntaje"] <= 1.0
    assert isinstance(cuerpo["alto_riesgo"], bool)
    registradas = cliente.get("/predicciones").json()
    assert len(registradas) == 1
    assert registradas[0]["numero"] == BASE["numero"]
    assert registradas[0]["puntaje"] == pytest.approx(cuerpo["puntaje"], abs=1e-4)


def test_score_de_poliza_inexistente_da_404_y_no_registra(cliente):
    assert cliente.post("/score", json={"numero": "POL-NO-EXISTE"}).status_code == 404
    assert cliente.get("/predicciones").json() == []


def test_el_aislamiento_es_real_la_sesion_sustituida_es_database_get_db(cliente):
    """Si el override apuntara a otra función (como en la propuesta de la IA), la aplicación usaría su
    sesión real. Se comprueba que la clave del override es exactamente `database.get_db`."""
    import database
    from main import app

    assert database.get_db in app.dependency_overrides
