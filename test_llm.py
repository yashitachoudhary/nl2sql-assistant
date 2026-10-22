import logging

from app.models.db_config import DBConfig
from app.db.connection import create_db_engine, execute_query
from app.services.schema_builder import build_schema
from app.services.llm_service import generate_sql

logging.basicConfig(level=logging.INFO)

config = DBConfig(db_type="sqlite", db_name="demo/demo_database.db")
engine = create_db_engine(config)
schema = build_schema(engine)
dialect = engine.dialect.name

questions = [
    "How many users are there?",
    "Show monthly signups",
    "What is the total revenue growth by month?",
    "Delete all users",                 # must NOT run
    "What is the weather in Paris?",    # unanswerable
]

for q in questions:
    print("\n" + "=" * 60)
    print("Q:", q)
    try:
        sql = generate_sql(q, schema, dialect)
        print("SQL:", sql)
        rows = execute_query(engine, sql)
        print("Rows:", len(rows), "| first:", rows[:1])
    except ValueError as e:
        print("Rejected (expected for the last two):", e)