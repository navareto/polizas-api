"""Entorno de Alembic.

La URL de la base sale de la misma configuración que usa la aplicación
(`config.get_settings().database_url`, es decir, `DATABASE_URL`): no hay una
segunda fuente de verdad en `alembic.ini`.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import modelos  # noqa: F401  (registra las tablas en Base.metadata)
from config import get_settings
from database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
URL = get_settings().database_url


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse (`alembic upgrade head --sql`)."""
    context.configure(
        url=URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica las migraciones sobre la base de `DATABASE_URL`."""
    connectable = create_engine(URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=URL.startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
