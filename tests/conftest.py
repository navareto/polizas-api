"""Fixtures compartidas por las pruebas propias.

Cada prueba corre sobre una copia nueva de una base SQLite temporal cuyo esquema lo crean las
migraciones reales de Alembic (así también se prueba `alembic upgrade head`). La sesión de la
aplicación se sustituye con `app.dependency_overrides[get_db]`; la base de la aplicación no se toca.

`main` se importa dentro de las fixtures, no aquí arriba, para no fijar la configuración antes de
que cada módulo de pruebas decida su propio `DATABASE_URL`.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


@pytest.fixture(scope="session")
def plantilla_db(tmp_path_factory) -> Path:
    """Base vacía con el esquema aplicado por Alembic; se copia para cada prueba."""
    ruta = tmp_path_factory.mktemp("plantilla") / "plantilla.db"
    entorno = {**os.environ, "DATABASE_URL": f"sqlite:///{ruta}"}
    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=RAIZ, env=entorno, capture_output=True, text=True,
    )
    assert resultado.returncode == 0, resultado.stderr[-500:]
    return ruta


@pytest.fixture()
def cliente(plantilla_db, tmp_path):
    """TestClient sobre una base propia de esta prueba, con claves foráneas activas."""
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from database import crear_motor, get_db
    from main import app

    ruta = tmp_path / "prueba.db"
    shutil.copy(plantilla_db, ruta)
    motor = crear_motor(f"sqlite:///{ruta}")
    sesion = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)

    def _get_db():
        db = sesion()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        c.ruta_db = ruta  # para las pruebas que inspeccionan la base directamente
        yield c
    app.dependency_overrides.pop(get_db, None)
    motor.dispose()
