import logging

from sqlalchemy import create_engine, text

from app.models.db_config import DBConfig
from app.db.connection import create_db_engine
from app.services.schema_builder import build_schema

logging.basicConfig(level=logging.INFO)

# 1. Schema for the demo database
config = DBConfig(db_type="sqlite", db_name="demo/demo_database.db")
engine = create_db_engine(config)
print(build_schema(engine))

print("=" * 60)

# 2. Only selected tables
print(build_schema(engine, selected_tables=["users", "revenue"]))

print("=" * 60)

# 3. Sensitive and binary columns must be skipped
mem = create_engine("sqlite://")
with mem.begin() as conn:
    conn.execute(text(
        "CREATE TABLE accounts ("
        "id INTEGER PRIMARY KEY, email TEXT, password TEXT, "
        "push_auth_token TEXT, avatar BLOB)"
    ))
print(build_schema(mem))