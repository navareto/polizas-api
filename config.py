"""Configuración del servicio: se lee del entorno y de `.env`, nunca del código (M8).

Los valores de ejemplo viven en `.env.example`; el `.env` real no se versiona.
"""
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./polizas.db"
    ruta_modelo: str = str(RAIZ / "modelo.pkl")
    umbral_alto_riesgo: float = Field(default=0.6, ge=0.0, le=1.0)
    # Sin valor por defecto fijo: si no se configura, el proceso genera uno efímero
    # (útil para desarrollo; en producción se define SECRETO_FIRMA en el entorno).
    secreto_firma: SecretStr = Field(default_factory=lambda: SecretStr(secrets.token_hex(32)))
    clave_api_reaseguro: Optional[SecretStr] = None


@lru_cache
def get_settings() -> Settings:
    """Una sola instancia por proceso; se inyecta con `Depends(get_settings)`."""
    return Settings()
