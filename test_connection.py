import logging

from app.models.db_config import DBConfig
from app.db.connection import (
    create_db_engine,
    test_connection,
    get_table_names,
    execute_query,
)

# Show log messages from connection.py in the terminal
logging.basicConfig(level=logging.INFO)

# 1. Build a config for the demo SQLite database
config = DBConfig(db_type="sqlite", db_name="demo/demo_database.db")

# 2. Create the engine
engine = create_db_engine(config)

# 3. Test the connection
test_connection(engine)
print("Connected")

# 4. List the tables
print("Tables:", get_table_names(engine))

# 5. Run a safe SELECT query
result = execute_query(engine, "SELECT COUNT(*) AS total_users FROM users")
print("Result:", result)

# 6. Try a write query: the read-only mode should block it
try:
    execute_query(engine, "DELETE FROM users")
    print("WARNING: DELETE succeeded, read-only protection is NOT working")
except Exception as e:
    print("DELETE blocked:", type(e).__name__)
    print("Reason:", e)