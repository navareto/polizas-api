"""Motor de base de datos y sesión por petición (M8 · M9)."""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings


class Base(DeclarativeBase):
    pass


def crear_motor(url: str) -> Engine:
    """Motor para `url`; en SQLite activa las claves foráneas en cada conexión."""
    es_sqlite = url.startswith("sqlite")
    motor = create_engine(url, connect_args={"check_same_thread": False} if es_sqlite else {})
    if es_sqlite:

        @event.listens_for(motor, "connect")
        def _activar_claves_foraneas(conexion, _registro):
            cursor = conexion.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return motor


engine = crear_motor(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Una sesión por petición: se abre al entrar y se cierra siempre al salir."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
