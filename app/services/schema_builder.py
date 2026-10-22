import logging
from typing import Optional

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Above this many tables, ask the user to select a subset
MAX_TABLES = 25

# Columns whose names contain these words are never sent to the LLM
SENSITIVE_KEYWORDS = (
    "password", "passwd", "token", "secret",
    "api_key", "private_key", "ssn", "credit_card", "card_number",
)

# Binary columns are useless for analytics and waste tokens
SKIPPED_TYPES = ("BLOB", "BYTEA", "BINARY")


def is_sensitive(column_name: str) -> bool:
    """True if the column name suggests it holds secrets."""
    name = column_name.lower()
    return any(keyword in name for keyword in SENSITIVE_KEYWORDS)


def is_skipped_type(column_type: str) -> bool:
    """True if the column holds binary data."""
    return any(t in column_type.upper() for t in SKIPPED_TYPES)


def build_schema(
    engine: Engine,
    selected_tables: Optional[list[str]] = None,
    business_context: str = "",
) -> str:
    """
    Read the database structure and return it as text for the LLM prompt.

    Args:
        engine: Connected SQLAlchemy engine
        selected_tables: Tables to include. None or empty means all tables.
        business_context: Optional notes from the user, e.g.
            "status 1 = accepted connection"

    Raises:
        ValueError: If no tables are found, or too many tables with no selection
    """
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()

    if selected_tables:
        tables = [t for t in all_tables if t in selected_tables]
        missing = set(selected_tables) - set(tables)
        if missing:
            logger.warning(f"Selected tables not found: {missing}")
    else:
        tables = all_tables

    if not tables:
        raise ValueError("No tables found in this database.")

    if len(tables) > MAX_TABLES:
        raise ValueError(
            f"This database has {len(tables)} tables. "
            f"Please select up to {MAX_TABLES} to keep answers accurate."
        )

    # The dialect tells the LLM which SQL flavor to write
    lines = [f"Database dialect: {engine.dialect.name}", ""]

    for table in tables:
        primary_keys = set(
            inspector.get_pk_constraint(table).get("constrained_columns", [])
        )
        lines.append(f"Table: {table}")
        lines.append("Columns:")

        for column in inspector.get_columns(table):
            name = column["name"]
            col_type = str(column["type"])

            if is_sensitive(name) or is_skipped_type(col_type):
                logger.info(f"Skipping column {table}.{name}")
                continue

            pk_note = " [primary key]" if name in primary_keys else ""
            lines.append(f"  - {name} ({col_type}){pk_note}")

        # Foreign keys help the LLM write correct JOINs
        for fk in inspector.get_foreign_keys(table):
            local = ", ".join(fk["constrained_columns"])
            remote = ", ".join(fk["referred_columns"])
            lines.append(
                f"  Foreign key: {local} -> {fk['referred_table']}({remote})"
            )

        lines.append("")

    if business_context.strip():
        lines.append("Business context provided by the user:")
        lines.append(business_context.strip())

    logger.info(f"Built schema for {len(tables)} tables")
    return "\n".join(lines)