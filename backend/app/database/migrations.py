"""Small additive bootstrap migrations for local development databases.

Production schema changes should be promoted to versioned Alembic revisions. The
initial release only needs to add the indexing timing columns introduced after
the first indexing-job schema was created.
"""

from sqlalchemy import Engine, inspect

from backend.app.database.models import IndexingJob
from backend.app.database.session import Base


def initialize_schema(engine: Engine) -> None:
    """Create missing tables and add safe nullable/defaulted columns to old SQLite DBs."""

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    table = IndexingJob.__table__
    if table.name not in existing_tables:
        return
    existing_columns = {item["name"] for item in inspector.get_columns(table.name)}
    additions = [column for column in table.columns if column.name not in existing_columns]
    if not additions:
        return
    preparer = engine.dialect.identifier_preparer
    quoted_table = preparer.quote(table.name)
    with engine.begin() as connection:
        for column in additions:
            compiled_type = column.type.compile(dialect=engine.dialect)
            default = f" DEFAULT {column.server_default.arg}" if column.server_default is not None else ""
            nullable = " NOT NULL" if not column.nullable and column.server_default is not None else ""
            connection.exec_driver_sql(
                f"ALTER TABLE {quoted_table} ADD COLUMN {preparer.quote(column.name)} {compiled_type}{default}{nullable}"
            )
