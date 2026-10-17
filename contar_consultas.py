"""
Instrumento de la Parte C: cuenta las sentencias SQL que emite cada endpoint.

    python contar_consultas.py                      # 10 y 2000 pólizas, escribe CONSULTAS.csv
    python contar_consultas.py --tamanos 10 200     # para probar rápido
    python contar_consultas.py --alternativas       # mide las otras estrategias y las imprime (no escribe CSV)

Qué hace:
  1. Apunta la aplicación a una base de datos TEMPORAL poniendo DATABASE_URL
     antes de importarla, y aplica las migraciones si hay alembic.ini.
     Si la aplicación no honra DATABASE_URL, se avisa: entonces está
     sembrando en la base de datos de la aplicación, y eso es un hallazgo.
  2. Engancha un contador a `before_cursor_execute` del motor de SQLAlchemy —a
     nivel de clase, así que cuenta cualquier engine que exista— y levanta la
     aplicación en proceso con TestClient.
  3. Siembra por la API (sembrar_datos.sembrar) hasta cada tamaño, pide cada
     endpoint una vez para calentar y otra para contar, y escribe el CSV.

Modificaciones respecto al semilla (declaradas en HALLAZGOS.md, sección «Parte C»):
  · ESTRATEGIA_ELEGIDA rellena la columna `estrategia` con la que quedó en servicios.py.
  · `--alternativas` sustituye temporalmente, solo en este proceso, la consulta de cada
    endpoint por las otras estrategias (lazy, selectinload, joinedload, agregada) para
    medirlas antes de decidir. No toca el código del servicio.

Se califica `consultas_sql`, que es determinista; `tiempo_ms` cambia de una
máquina a otra y solo sirve para interpretar.
"""
import argparse
import csv
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ENDPOINTS = ["/polizas", "/polizas/{id}", "/siniestros", "/resumen"]
COLUMNAS = ["endpoint", "estrategia", "n_polizas", "consultas_sql", "tiempo_ms"]

# La estrategia que quedó en el código (servicios.py), decidida después de medir (ver `--alternativas`).
ESTRATEGIA_ELEGIDA = {
    "/polizas": "selectinload",
    "/polizas/{id}": "lazy",
    "/siniestros": "joinedload",
    "/resumen": "agregada",
}
ALTERNATIVAS = {
    "/polizas": ["lazy", "selectinload", "joinedload"],
    "/polizas/{id}": ["lazy", "selectinload", "joinedload"],
    "/siniestros": ["lazy", "selectinload", "joinedload"],
    "/resumen": ["lazy", "selectinload", "joinedload", "agregada"],
}


def variantes():
    """Implementaciones alternativas de cada consulta, para medirlas (solo con --alternativas)."""
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload, selectinload

    import servicios
    from modelos import Poliza, Siniestro

    resumen_agregado = servicios.resumen  # la implementación real, antes de que se sustituya nada

    def cargar(consulta, opcion, relacion):
        if opcion == "selectinload":
            return consulta.options(selectinload(relacion))
        if opcion == "joinedload":
            return consulta.options(joinedload(relacion))
        return consulta  # lazy: sin opciones, la relación se carga al tocarla

    def polizas(carga):
        return lambda db: list(db.scalars(cargar(select(Poliza).order_by(Poliza.id), carga, Poliza.siniestros)).unique())

    def poliza(carga):
        def obtener(db, id_poliza):
            consulta = cargar(select(Poliza).where(Poliza.id == id_poliza), carga, Poliza.siniestros)
            resultado = db.scalars(consulta).unique().first()
            if resultado is None:
                raise servicios.PolizaNoExiste(str(id_poliza))
            return resultado

        return obtener

    def siniestros(carga):
        return lambda db: list(db.scalars(cargar(select(Siniestro).order_by(Siniestro.id), carga, Siniestro.poliza)).unique())

    def resumen(carga):
        if carga == "agregada":
            return resumen_agregado

        def calcular(db):
            consulta = cargar(select(Poliza).order_by(Poliza.id), carga, Poliza.siniestros)
            return [{"numero": p.numero, "n_siniestros": len(p.siniestros),
                     "monto_total": round(sum(s.monto for s in p.siniestros), 2)}
                    for p in db.scalars(consulta).unique()]

        return calcular

    return {
        "/polizas": ("listar_polizas", polizas),
        "/polizas/{id}": ("obtener_poliza", poliza),
        "/siniestros": ("listar_siniestros", siniestros),
        "/resumen": ("resumen", resumen),
    }


REPETICIONES = 5


def medir(cliente, contador, ruta):
    """Devuelve (consultas, mediana de milisegundos). Una pasada para calentar y REPETICIONES para medir."""
    cliente.get(ruta)  # calentamiento
    tiempos = []
    for _ in range(REPETICIONES):
        contador["n"] = 0
        t0 = time.perf_counter()
        r = cliente.get(ruta)
        tiempos.append((time.perf_counter() - t0) * 1000)
        if r.status_code >= 400:
            raise SystemExit(f"\n{ruta} devolvió {r.status_code}. No se escribe el CSV: primero hay "
                             f"que dejar el servicio respondiendo. Cuerpo: {r.text[:300]}")
    tiempos.sort()
    return contador["n"], round(tiempos[len(tiempos) // 2], 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tamanos", nargs="+", type=int, default=[10, 2000])
    ap.add_argument("--por-poliza", type=int, default=3)
    ap.add_argument("--salida", default="CONSULTAS.csv")
    ap.add_argument("--alternativas", action="store_true")
    a = ap.parse_args()

    raiz = Path(__file__).parent.resolve()
    os.chdir(raiz)
    sys.path.insert(0, str(raiz))

    # 1 · base de datos temporal, ANTES de importar la aplicación
    carpeta = Path(tempfile.mkdtemp(prefix="consultas-"))
    db = carpeta / "consultas.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    if (raiz / "alembic.ini").exists():
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)

    # 2 · el contador, a nivel de clase
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    contador = {"n": 0}

    @event.listens_for(Engine, "before_cursor_execute")
    def _contar(conn, cursor, statement, parameters, context, executemany):
        contador["n"] += 1

    from fastapi.testclient import TestClient
    from main import app
    from sembrar_datos import sembrar

    alternativas = variantes() if a.alternativas else {}
    filas = []
    with TestClient(app, raise_server_exceptions=False) as cliente:
        sembradas, primer_id = 0, None
        for n in a.tamanos:
            ids = sembrar(cliente, n - sembradas, a.por_poliza, prefijo="POL-C", desde=sembradas + 1)
            primer_id = primer_id or ids[0]
            sembradas = n
            if not (db.exists() and db.stat().st_size > 0):
                print("AVISO: la aplicación NO honra DATABASE_URL. Se está sembrando en SU base "
                      "de datos, no en una temporal. Eso es un hallazgo, y conviene arreglarlo "
                      "antes de sembrar 2000 pólizas ahí.")
            for endpoint in ENDPOINTS:
                ruta = endpoint.replace("{id}", str(primer_id))
                if not a.alternativas:
                    consultas, ms = medir(cliente, contador, ruta)
                    fila = {"endpoint": endpoint, "estrategia": ESTRATEGIA_ELEGIDA[endpoint], "n_polizas": n,
                            "consultas_sql": consultas, "tiempo_ms": ms}
                    filas.append(fila)
                    print(f"  {endpoint:<16} {fila['estrategia']:<13} n={n:<5} consultas {consultas:>5}   {ms:>8.1f} ms")
                    continue
                import servicios

                nombre, fabrica = alternativas[endpoint]
                original = getattr(servicios, nombre)
                try:
                    for estrategia in ALTERNATIVAS[endpoint]:
                        setattr(servicios, nombre, fabrica(estrategia))
                        consultas, ms = medir(cliente, contador, ruta)
                        marca = "  <- elegida" if estrategia == ESTRATEGIA_ELEGIDA[endpoint] else ""
                        print(f"  {endpoint:<16} {estrategia:<13} n={n:<5} consultas {consultas:>5}   {ms:>8.1f} ms{marca}")
                finally:
                    setattr(servicios, nombre, original)

    if a.alternativas:
        print("\n(--alternativas no escribe el CSV.)")
        return
    with open(a.salida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)
    print(f"\n{a.salida} escrito con {len(filas)} filas. Base temporal: {db}")


if __name__ == "__main__":
    main()
