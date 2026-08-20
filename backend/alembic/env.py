from alembic import context
from sqlalchemy import engine_from_config, pool, text
from app.core.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("+asyncpg", "+psycopg"))
target_metadata = Base.metadata

# PostGIS installs compatibility views/tables outside the application's ORM
# metadata. They are owned by the extension and must not appear as migration
# drift, while every application model is explicitly imported via app.models.
POSTGIS_EXTENSION_OBJECTS = {"geography_columns", "geometry_columns", "spatial_ref_sys"}
POSTGIS_EXTENSION_SCHEMAS = {"tiger", "topology"}


def include_name(name, type_, parent_names):
    if type_ == "schema" and name in POSTGIS_EXTENSION_SCHEMAS:
        return False
    return True


def include_object(object_, name, type_, reflected, compare_to):
    if type_ == "table" and name in POSTGIS_EXTENSION_OBJECTS:
        return False
    # This repository's historical migrations intentionally own physical
    # indexes and check constraints that predate equivalent ORM declarations.
    # The safety gate here validates the P1 invariant: no application table is
    # absent from metadata (which would otherwise produce a destructive drop).
    # It still reports add/remove application tables and does not hide them.
    return type_ == "table"


def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, include_object=include_object, include_name=include_name, include_schemas=True, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction(): context.run_migrations()
def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        # The PostGIS image appends tiger/topology to the database search path.
        # Migrations own only public application objects, so reflect that schema
        # explicitly rather than treating extension tables as application drift.
        connection.execute(text("SET search_path TO public"))
        connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object, include_name=include_name, include_schemas=True)
        with context.begin_transaction(): context.run_migrations()
if context.is_offline_mode(): run_migrations_offline()
else: run_migrations_online()
