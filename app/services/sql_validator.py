import logging
import re

logger = logging.getLogger(__name__)

def validate_sql(query: str) -> str:
    """
    Validates that a SQL query is safe to execute.
    Only SELECT statements are allowed.
    Returns the query if valid, raises ValueError if not.
    """
    cleaned = query.strip().upper()

    if not cleaned.startswith("SELECT"):
        logger.warning(f"Rejected non-SELECT query: {query}")
        raise ValueError("Only SELECT queries are allowed.")

    dangerous_keywords = [
        "DROP", "DELETE", "INSERT", "UPDATE",
        "ALTER", "TRUNCATE", "CREATE", "EXEC", "EXECUTE",
        "INTO OUTFILE",    # exports data to file
    "INTO DUMPFILE",   # exports data to file
    "LOAD_FILE",       # reads files from server
    "SLEEP",           # time-based SQL injection
    "BENCHMARK",       # CPU exhaustion attack
    "INFORMATION_SCHEMA",  # reveals DB structure,
    "DECLARE",  # used in stored procedures
    
    ]

    if any(re.search(rf"\b{keyword}\b", cleaned) for keyword in dangerous_keywords):        
        logger.warning(f"Rejected query with dangerous keyword: {query}")
        raise ValueError("Query contains forbidden keywords.")

        # Prevent accidentally fetching millions of rows
    if "LIMIT" not in cleaned:
        query = query.rstrip().rstrip(";") + " LIMIT 500;"

    logger.info("SQL validation passed.")
    return query