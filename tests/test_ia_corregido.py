"""Batería corregida de `ia_tests_propuesta.py` (Parte D). Cada prueba pasa sobre el servicio sano y se
pone en rojo cuando se le introduce una mutación (ver DICTAMEN_IA.md).

Lo que cambia respecto a la propuesta de la IA:
  1. Cada aserción fija el resultado esperado (201, 404, 422...), no un conjunto de resultados aceptables.
  2. Se verifica el EFECTO (lo guardado, lo listado, lo registrado), siempre leyéndolo en una petición
     NUEVA: cada petición usa su propia sesión, así que lo que no se confirmó con `commit` no se ve.
  3. Los datos son deterministas (parametrizados), sin `random` ni `uuid` sin semilla.
  4. El aislamiento es real: la sesión se sustituye con `app.dependency_overrides[database.get_db]`
     (fixture `cliente` de conftest.py), sobre una base temporal con el esquema de Alembic.
  5. Cubre los nueve endpoints del contrato más /health: los 404, los 409, los 422, los commits y los
     validadores de cada ruta, para que una mutación en cualquiera de ellas deje alguna prueba en rojo.

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


# --- Creación y lectura ----------------------------------------------------


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


def test_el_asegurado_se_normaliza_y_no_queda_vacio(cliente):
    creada = _crear(cliente, asegurado="  ana   rueda ")
    assert creada["asegurado"] == "Ana Rueda"
    assert cliente.get(f"/polizas/{creada['id']}").json()["asegurado"] == "Ana Rueda"


def test_ninguna_respuesta_expone_el_token_de_firma(cliente):
    creada = _crear(cliente)
    respuestas = [creada, cliente.get(f"/polizas/{creada['id']}").json(), cliente.get("/polizas").json()]
    assert all("token_firma" not in str(cuerpo) for cuerpo in respuestas)


def test_listar_polizas_devuelve_exactamente_las_creadas(cliente):
    creadas = [_crear(cliente, numero=f"POL-IA-00000{i}") for i in (1, 2, 3)]
    assert cliente.get("/polizas").json() == creadas


def test_numero_duplicado_da_409_y_no_duplica(cliente):
    _crear(cliente)
    assert cliente.post("/polizas", json=BASE).status_code == 409
    assert len(cliente.get("/polizas").json()) == 1


# --- Validación: la entrada inválida da 422 y no guarda nada ---------------


@pytest.mark.parametrize("prima", [0, -1, -1_000_000])
def test_primas_no_positivas_dan_422_y_no_guardan_nada(cliente, prima):
    assert cliente.post("/polizas", json={**BASE, "prima": prima}).status_code == 422
    assert cliente.get("/polizas").json() == []


@pytest.mark.parametrize("inicio, fin", [("2027-01-14", "2026-01-15"), ("2026-06-01", "2026-06-01")])
def test_fechas_invertidas_o_iguales_dan_422(cliente, inicio, fin):
    r = cliente.post("/polizas", json={**BASE, "fecha_inicio": inicio, "fecha_fin": fin})
    assert r.status_code == 422
    assert cliente.get("/polizas").json() == []


@pytest.mark.parametrize("siniestro", [
    {**SINIESTRO, "monto": -50},
    {**SINIESTRO, "monto": 0},
    {**SINIESTRO, "descripcion": "x"},
])
def test_siniestro_anidado_invalido_da_422_y_no_guarda_la_poliza(cliente, siniestro):
    assert cliente.post("/polizas", json={**BASE, "siniestros": [siniestro]}).status_code == 422
    assert cliente.get("/polizas").json() == []


def test_falta_un_campo_obligatorio_da_422(cliente):
    sin_numero = {k: v for k, v in BASE.items() if k != "numero"}
    assert cliente.post("/polizas", json=sin_numero).status_code == 422


# --- No existe: 404 en todas las rutas con identificador -------------------


def test_consultar_poliza_inexistente_da_404(cliente):
    r = cliente.get("/polizas/999999")
    assert r.status_code == 404
    assert "error" not in r.json() and "999999" in r.json()["detail"]


def test_actualizar_poliza_inexistente_da_404(cliente):
    assert cliente.put("/polizas/999999", json={"prima": 10}).status_code == 404


def test_declarar_siniestro_en_poliza_inexistente_da_404_y_no_deja_huerfanos(cliente):
    assert cliente.post("/polizas/999999/siniestros", json=SINIESTRO).status_code == 404
    assert cliente.get("/siniestros").json() == []


def test_score_de_poliza_inexistente_da_404_y_no_registra(cliente):
    assert cliente.post("/score", json={"numero": "POL-NO-EXISTE"}).status_code == 404
    assert cliente.get("/predicciones").json() == []


# --- Actualización parcial (PUT) -------------------------------------------


def test_put_parcial_cambia_solo_lo_enviado_y_queda_guardado(cliente):
    creada = _crear(cliente, asegurado="Bruno Celis", tipo="hogar")
    r = cliente.put(f"/polizas/{creada['id']}", json={"prima": 999_000})
    assert r.status_code == 200 and r.json()["prima"] == 999_000
    leida = cliente.get(f"/polizas/{creada['id']}").json()  # petición nueva: solo se ve lo confirmado
    assert (leida["prima"], leida["asegurado"], leida["tipo"], leida["fecha_fin"]) == (
        999_000, "Bruno Celis", "hogar", "2026-12-31")


def test_put_invalido_da_422_y_no_cambia_nada(cliente):
    creada = _crear(cliente)
    assert cliente.put(f"/polizas/{creada['id']}", json={"prima": 0}).status_code == 422
    assert cliente.put(f"/polizas/{creada['id']}", json={"fecha_fin": "2025-01-01"}).status_code == 422
    assert cliente.get(f"/polizas/{creada['id']}").json() == creada


# --- Siniestros ------------------------------------------------------------


def test_siniestro_se_declara_con_201_y_queda_guardado(cliente):
    creada = _crear(cliente)
    r = cliente.post(f"/polizas/{creada['id']}/siniestros", json=SINIESTRO)
    assert r.status_code == 201
    assert r.json()["poliza_id"] == creada["id"] and r.json()["monto"] == SINIESTRO["monto"]
    guardados = cliente.get(f"/polizas/{creada['id']}").json()["siniestros"]
    assert [s["id"] for s in guardados] == [r.json()["id"]]


def test_siniestro_invalido_da_422_y_no_guarda_nada(cliente):
    creada = _crear(cliente)
    assert cliente.post(f"/polizas/{creada['id']}/siniestros", json={**SINIESTRO, "monto": -1}).status_code == 422
    assert cliente.get(f"/polizas/{creada['id']}").json()["siniestros"] == []


def test_listar_siniestros_trae_el_numero_de_su_poliza(cliente):
    _crear(cliente, siniestros=[SINIESTRO, {**SINIESTRO, "monto": 100_000}])
    siniestros = cliente.get("/siniestros").json()
    assert [s["numero_poliza"] for s in siniestros] == [BASE["numero"]] * 2
    assert sorted(s["monto"] for s in siniestros) == [100_000, 850_000]


# --- Resumen ---------------------------------------------------------------


def test_resumen_tiene_los_numeros_exactos(cliente):
    _crear(cliente, siniestros=[SINIESTRO, {**SINIESTRO, "monto": 150_000}])
    _crear(cliente, numero="POL-IA-000002")
    assert cliente.get("/resumen").json() == [
        {"numero": "POL-IA-000001", "n_siniestros": 2, "monto_total": 1_000_000.0},
        {"numero": "POL-IA-000002", "n_siniestros": 0, "monto_total": 0.0},
    ]


# --- Puntuación e histórico de predicciones --------------------------------


@pytest.mark.parametrize("prima", [500_000, 4_800_000])
def test_score_de_poliza_recien_creada_registra_la_prediccion(cliente, prima):
    from config import get_settings

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
    # alto_riesgo es exactamente «puntaje por encima del umbral configurado»
    esperado = registradas[0]["puntaje"] > get_settings().umbral_alto_riesgo
    assert cuerpo["alto_riesgo"] is esperado and registradas[0]["alto_riesgo"] is esperado


def test_cada_score_agrega_una_prediccion(cliente):
    _crear(cliente)
    for _ in range(2):
        assert cliente.post("/score", json={"numero": BASE["numero"]}).status_code == 200
    assert len(cliente.get("/predicciones").json()) == 2


# --- Salud y aislamiento ---------------------------------------------------


def test_health_responde_200_y_dice_que_la_base_responde(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_el_aislamiento_es_real_la_sesion_sustituida_es_database_get_db(cliente):
    """Si el override apuntara a otra función (como en la propuesta de la IA), la aplicación usaría su
    sesión real. Se comprueba que la clave del override es exactamente `database.get_db`."""
    import database
    from main import app

    assert database.get_db in app.dependency_overrides
