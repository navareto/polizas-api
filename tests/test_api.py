"""Pruebas propias del servicio. Cada una corre sobre su propia base temporal (ver conftest.py).

    pytest tests/test_api.py -v
"""
import hashlib
from pathlib import Path

import pytest

POLIZA = {
    "numero": "POL-TEST-00001",
    "asegurado": "Prueba Interna",
    "tipo": "auto",
    "prima": 1_000_000,
    "fecha_inicio": "2026-01-01",
    "fecha_fin": "2026-12-31",
}
SINIESTRO = {"fecha": "2026-03-02", "monto": 850_000, "descripcion": "Choque leve", "estado": "abierto"}


def _crear(cliente, **extra):
    r = cliente.post("/polizas", json={**POLIZA, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_health_indica_que_la_base_responde(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_crear_poliza_devuelve_201_y_no_expone_el_token(cliente):
    cuerpo = _crear(cliente)
    assert cuerpo["numero"] == POLIZA["numero"] and cuerpo["id"] >= 1
    assert "token_firma" not in cuerpo


def test_asegurado_se_normaliza_y_se_conserva(cliente):
    cuerpo = _crear(cliente, asegurado="  carla   ibáñez ")
    assert cuerpo["asegurado"] == "Carla Ibáñez"


def test_numero_duplicado_da_409_y_el_servicio_sigue_vivo(cliente):
    _crear(cliente)
    r = cliente.post("/polizas", json=POLIZA)
    assert r.status_code == 409
    assert cliente.get("/polizas").status_code == 200  # la sesión es por petición: nada queda roto


def test_entrada_invalida_da_422(cliente):
    assert cliente.post("/polizas", json={**POLIZA, "prima": 0}).status_code == 422
    invertidas = {**POLIZA, "fecha_inicio": "2027-01-14", "fecha_fin": "2026-01-15"}
    assert cliente.post("/polizas", json=invertidas).status_code == 422
    negativo = {**POLIZA, "siniestros": [{**SINIESTRO, "monto": -50}]}
    assert cliente.post("/polizas", json=negativo).status_code == 422


def test_poliza_inexistente_da_404_en_get_put_y_siniestros(cliente):
    assert cliente.get("/polizas/999999").status_code == 404
    assert cliente.put("/polizas/999999", json={"prima": 10}).status_code == 404
    assert cliente.post("/polizas/999999/siniestros", json=SINIESTRO).status_code == 404
    assert cliente.get("/siniestros").status_code == 200  # no queda ningún siniestro huérfano


def test_put_parcial_conserva_lo_que_no_se_envia(cliente):
    creada = _crear(cliente, asegurado="Bruno Celis", tipo="hogar")
    r = cliente.put(f"/polizas/{creada['id']}", json={"prima": 999_000})
    assert r.status_code == 200
    assert r.json()["prima"] == 999_000
    assert (r.json()["asegurado"], r.json()["tipo"], r.json()["fecha_fin"]) == ("Bruno Celis", "hogar", "2026-12-31")


def test_put_no_permite_dejar_la_fecha_fin_antes_del_inicio(cliente):
    creada = _crear(cliente)
    assert cliente.put(f"/polizas/{creada['id']}", json={"fecha_fin": "2025-01-01"}).status_code == 422
    assert cliente.get(f"/polizas/{creada['id']}").json()["fecha_fin"] == "2026-12-31"


def test_siniestro_se_declara_con_201_y_aparece_en_la_poliza(cliente):
    creada = _crear(cliente)
    r = cliente.post(f"/polizas/{creada['id']}/siniestros", json=SINIESTRO)
    assert r.status_code == 201 and r.json()["poliza_id"] == creada["id"]
    assert len(cliente.get(f"/polizas/{creada['id']}").json()["siniestros"]) == 1


def test_listados_traen_las_relaciones(cliente):
    _crear(cliente, siniestros=[SINIESTRO, {**SINIESTRO, "monto": 100_000}])
    polizas = cliente.get("/polizas").json()
    assert [len(p["siniestros"]) for p in polizas] == [2]
    siniestros = cliente.get("/siniestros").json()
    assert {s["numero_poliza"] for s in siniestros} == {POLIZA["numero"]}


def test_resumen_cuenta_y_suma_por_poliza_incluida_la_que_no_tiene(cliente):
    _crear(cliente, siniestros=[SINIESTRO, {**SINIESTRO, "monto": 150_000}])
    _crear(cliente, numero="POL-TEST-00002")
    resumen = {f["numero"]: f for f in cliente.get("/resumen").json()}
    assert resumen["POL-TEST-00001"]["n_siniestros"] == 2
    assert resumen["POL-TEST-00001"]["monto_total"] == 1_000_000
    assert resumen["POL-TEST-00002"] == {"numero": "POL-TEST-00002", "n_siniestros": 0, "monto_total": 0.0}


def test_score_devuelve_puntaje_y_registra_la_prediccion(cliente):
    _crear(cliente, siniestros=[SINIESTRO])
    r = cliente.post("/score", json={"numero": POLIZA["numero"]})
    assert r.status_code == 200
    cuerpo = r.json()
    assert 0.0 <= cuerpo["puntaje"] <= 1.0 and isinstance(cuerpo["alto_riesgo"], bool)
    registradas = cliente.get("/predicciones").json()
    assert [p["numero"] for p in registradas] == [POLIZA["numero"]]
    # /score redondea a 4 decimales; el histórico guarda el valor completo
    assert registradas[0]["puntaje"] == pytest.approx(cuerpo["puntaje"], abs=1e-4)


def test_score_de_poliza_inexistente_da_404_y_no_registra_nada(cliente):
    assert cliente.post("/score", json={"numero": "POL-NO-EXISTE"}).status_code == 404
    assert cliente.get("/predicciones").json() == []


def test_el_token_se_firma_con_el_secreto_de_la_configuracion(cliente):
    """El token no sale por la API, pero queda guardado y se calcula con el secreto configurado."""
    import sqlite3

    from config import get_settings

    _crear(cliente)
    conexion = sqlite3.connect(cliente.ruta_db)
    (token,) = conexion.execute("SELECT token_firma FROM polizas WHERE numero = ?", (POLIZA["numero"],)).fetchone()
    conexion.close()
    esperado = hashlib.sha256(f"{POLIZA['numero']}:{get_settings().secreto_firma.get_secret_value()}".encode()).hexdigest()
    assert token == esperado


def test_las_pruebas_no_tocan_la_base_de_la_aplicacion(cliente):
    """La base que usaría la aplicación (DATABASE_URL) no se crea ni se modifica al correr las pruebas."""
    from config import get_settings

    url = get_settings().database_url
    assert url.startswith("sqlite:///")
    base_app = Path(url.removeprefix("sqlite:///"))
    antes = base_app.stat().st_mtime_ns if base_app.exists() else None
    _crear(cliente)
    despues = base_app.stat().st_mtime_ns if base_app.exists() else None
    assert antes == despues
