"""
polizas-api — Gestión de pólizas y siniestros.
Aseguradora Santo Tomás.

Las rutas solo traducen HTTP: validan la entrada, llaman a `servicios` y declaran
el esquema de salida. La lógica y el acceso a datos viven en `servicios.py`.
"""
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import servicios
from config import Settings, get_settings
from database import get_db
from esquemas import (
    PolizaActualizacion, PolizaEntrada, PolizaSalida, PrediccionSalida, PuntuacionEntrada,
    PuntuacionSalida, ResumenSalida, SaludSalida, SiniestroConPoliza, SiniestroEntrada, SiniestroSalida,
)

app = FastAPI(title="Pólizas API", version="0.2.0")

Db = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]


def _responder(codigo: int):
    async def manejador(_peticion: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=codigo, content={"detail": str(exc)})

    return manejador


app.add_exception_handler(servicios.PolizaNoExiste, _responder(status.HTTP_404_NOT_FOUND))
app.add_exception_handler(servicios.NumeroDuplicado, _responder(status.HTTP_409_CONFLICT))
app.add_exception_handler(servicios.FechasIncoherentes, _responder(422))


@app.get("/health", response_model=SaludSalida)
def health(db: Db) -> Any:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "la base de datos no responde") from exc
    return SaludSalida(status="ok", database="ok")


@app.post("/polizas", response_model=PolizaSalida, status_code=status.HTTP_201_CREATED)
def crear_poliza(datos: PolizaEntrada, db: Db, config: Config) -> Any:
    return servicios.crear_poliza(db, datos, config.secreto_firma.get_secret_value())


@app.get("/polizas", response_model=list[PolizaSalida])
def listar_polizas(db: Db) -> Any:
    return servicios.listar_polizas(db)


@app.get("/polizas/{id_poliza}", response_model=PolizaSalida)
def obtener_poliza(id_poliza: int, db: Db) -> Any:
    return servicios.obtener_poliza(db, id_poliza)


@app.put("/polizas/{id_poliza}", response_model=PolizaSalida)
def actualizar_poliza(id_poliza: int, datos: PolizaActualizacion, db: Db) -> Any:
    cambios = datos.model_dump(exclude_unset=True, exclude_none=True)
    return servicios.actualizar_poliza(db, id_poliza, cambios)


@app.post("/polizas/{id_poliza}/siniestros", response_model=SiniestroSalida, status_code=status.HTTP_201_CREATED)
def declarar_siniestro(id_poliza: int, datos: SiniestroEntrada, db: Db) -> Any:
    return servicios.declarar_siniestro(db, id_poliza, datos)


@app.get("/siniestros", response_model=list[SiniestroConPoliza])
def listar_siniestros(db: Db) -> Any:
    return servicios.listar_siniestros(db)


@app.get("/resumen", response_model=list[ResumenSalida])
def resumen(db: Db) -> Any:
    return servicios.resumen(db)


@app.post("/score", response_model=PuntuacionSalida)
def puntuar(datos: PuntuacionEntrada, db: Db, config: Config, modelo: Annotated[Any, Depends(servicios.get_modelo)]) -> Any:
    numero, puntaje, alto_riesgo = servicios.puntuar(db, modelo, datos.numero, config.umbral_alto_riesgo)
    return PuntuacionSalida(numero=numero, puntaje=puntaje, alto_riesgo=alto_riesgo)


@app.get("/predicciones", response_model=list[PrediccionSalida])
def listar_predicciones(db: Db) -> Any:
    return servicios.listar_predicciones(db)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000)
