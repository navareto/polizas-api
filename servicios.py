"""Lógica de negocio: las reglas de póliza, el resumen y el puntaje viven aquí, no en las rutas.

Cada función recibe la sesión que le entrega la ruta (`Depends(get_db)`); ninguna abre la suya.
La estrategia de carga de relaciones de cada consulta está decidida y medida en la Parte C
(ver `CONSULTAS.csv` y la sección «Parte C» de `HALLAZGOS.md`).
"""
import hashlib
import pickle
from datetime import date
from functools import lru_cache
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from config import get_settings
from esquemas import PolizaEntrada, SiniestroEntrada
from modelos import Poliza, Prediccion, Siniestro


class PolizaNoExiste(Exception):
    """La póliza pedida no está en la base (→ 404)."""


class NumeroDuplicado(Exception):
    """Ya hay una póliza con ese número (→ 409)."""


class FechasIncoherentes(Exception):
    """La fecha de fin no es posterior a la de inicio tras actualizar (→ 422)."""


def firmar(numero: str, secreto: str) -> str:
    return hashlib.sha256(f"{numero}:{secreto}".encode()).hexdigest()


@lru_cache
def get_modelo() -> Any:
    """El modelo se carga una vez por proceso. `modelo.pkl` es un artefacto propio del repositorio."""
    with open(get_settings().ruta_modelo, "rb") as fh:
        return pickle.load(fh)


# --- Pólizas ---------------------------------------------------------------


def crear_poliza(db: Session, datos: PolizaEntrada, secreto: str) -> Poliza:
    if db.scalar(select(Poliza.id).where(Poliza.numero == datos.numero)) is not None:
        raise NumeroDuplicado(f"ya existe la póliza {datos.numero}")
    poliza = Poliza(
        numero=datos.numero, asegurado=datos.asegurado, tipo=datos.tipo, prima=datos.prima,
        fecha_inicio=datos.fecha_inicio, fecha_fin=datos.fecha_fin, token_firma=firmar(datos.numero, secreto),
        siniestros=[Siniestro(**s.model_dump()) for s in datos.siniestros],
    )
    db.add(poliza)
    try:
        db.commit()
    except IntegrityError as exc:  # dos peticiones simultáneas con el mismo número
        db.rollback()
        raise NumeroDuplicado(f"ya existe la póliza {datos.numero}") from exc
    return poliza


def listar_polizas(db: Session) -> list[Poliza]:
    """Estrategia `selectinload`: 2 consultas, sin importar cuántas pólizas haya."""
    consulta = select(Poliza).options(selectinload(Poliza.siniestros)).order_by(Poliza.id)
    return list(db.scalars(consulta))


def obtener_poliza(db: Session, id_poliza: int) -> Poliza:
    """Estrategia `lazy`: una sola póliza → 2 consultas, las mismas que costaría `selectinload`."""
    poliza = db.get(Poliza, id_poliza)
    if poliza is None:
        raise PolizaNoExiste(f"no existe la póliza {id_poliza}")
    return poliza


def actualizar_poliza(db: Session, id_poliza: int, cambios: dict[str, Any]) -> Poliza:
    poliza = obtener_poliza(db, id_poliza)
    for campo, valor in cambios.items():
        setattr(poliza, campo, valor)
    if poliza.fecha_fin <= poliza.fecha_inicio:
        db.rollback()
        raise FechasIncoherentes("fecha_fin debe ser posterior a fecha_inicio")
    db.commit()
    return poliza


# --- Siniestros ------------------------------------------------------------


def declarar_siniestro(db: Session, id_poliza: int, datos: SiniestroEntrada) -> Siniestro:
    if db.scalar(select(Poliza.id).where(Poliza.id == id_poliza)) is None:
        raise PolizaNoExiste(f"no existe la póliza {id_poliza}")
    siniestro = Siniestro(poliza_id=id_poliza, **datos.model_dump())
    db.add(siniestro)
    db.commit()
    return siniestro


def listar_siniestros(db: Session) -> list[Siniestro]:
    """Estrategia `joinedload`: cada siniestro tiene UNA póliza, así que el JOIN no multiplica filas."""
    consulta = select(Siniestro).options(joinedload(Siniestro.poliza)).order_by(Siniestro.id)
    return list(db.scalars(consulta))


# --- Resumen y puntaje -----------------------------------------------------


def resumen(db: Session) -> list[dict[str, Any]]:
    """Estrategia `agregada`: la base cuenta y suma; no se traen los siniestros a Python."""
    consulta = (
        select(
            Poliza.numero,
            func.count(Siniestro.id).label("n_siniestros"),
            func.coalesce(func.sum(Siniestro.monto), 0.0).label("monto_total"),
        )
        .outerjoin(Siniestro, Siniestro.poliza_id == Poliza.id)
        .group_by(Poliza.id, Poliza.numero)
        .order_by(Poliza.id)
    )
    return [
        {"numero": f.numero, "n_siniestros": f.n_siniestros, "monto_total": round(float(f.monto_total), 2)}
        for f in db.execute(consulta)
    ]


def puntuar(db: Session, modelo: Any, numero: str, umbral: float) -> tuple[str, float, bool]:
    """Puntúa una póliza con el modelo y registra la predicción. Devuelve (numero, puntaje, alto_riesgo)."""
    poliza = db.scalar(select(Poliza).where(Poliza.numero == numero))
    if poliza is None:
        raise PolizaNoExiste(f"no existe la póliza {numero}")
    n_siniestros, monto_total = db.execute(
        select(func.count(Siniestro.id), func.coalesce(func.sum(Siniestro.monto), 0.0))
        .where(Siniestro.poliza_id == poliza.id)
    ).one()
    rasgos = [[poliza.prima, n_siniestros, float(monto_total), (date.today() - poliza.fecha_inicio).days]]
    puntaje = float(modelo.predict_proba(rasgos)[0][1])
    prediccion = Prediccion(poliza_id=poliza.id, puntaje=puntaje, alto_riesgo=puntaje > umbral)
    db.add(prediccion)
    db.commit()
    return poliza.numero, round(puntaje, 4), prediccion.alto_riesgo


def listar_predicciones(db: Session) -> list[Prediccion]:
    consulta = select(Prediccion).options(joinedload(Prediccion.poliza)).order_by(Prediccion.id)
    return list(db.scalars(consulta))
