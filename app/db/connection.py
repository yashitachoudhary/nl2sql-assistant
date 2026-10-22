import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, Engine

from app.models.db_config import DBConfig

logger = logging.getLogger(__name__)

# Maps our db_type to the SQLAlchemy driver name
DRIVERS = {
    "mysql": "mysql+pymysql",
    "postgresql": "postgresql+psycopg2",
}


def create_db_engine(config: DBConfig) -> Engine:
    """
    Build a SQLAlchemy engine from a DBConfig.
    One engine per user session, never a shared global.
    """
    if config.db_type == "sqlite":
        # mode=ro opens the file read-only: a second safety layer
        # behind sql_validator.
        url = f"sqlite:///file:{config.db_name}?mode=ro&uri=true"
        logger.info("Creating read-only SQLite engine")
        return create_engine(url)

    # URL.create escapes special characters in the password safely
    url = URL.create(
        drivername=DRIVERS[config.db_type],
        username=config.db_user,
        # get_secret_value() is the only place the real password is read
        password=config.db_password.get_secret_value()
        if config.db_password else None,
        host=config.db_host,
        port=config.db_port,
        database=config.db_name,
    )
    logger.info(f"Creating {config.db_type} engine for host {config.db_host}")
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},  # fail fast on bad hosts
    )


def test_connection(engine: Engine) -> None:
    """Run a trivial query. Raises an exception if the DB is unreachable."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("Connection test passed")


def get_table_names(engine: Engine) -> list[str]:
    """
    List all tables using SQLAlchemy's inspector.
    The inspector works the same way on MySQL, PostgreSQL and SQLite,
    which is why we use it instead of SHOW TABLES (MySQL-only).
    """
    return inspect(engine).get_table_names()


def execute_query(engine: Engine, sql: str) -> list[dict]:
    """Execute a validated SQL query and return rows as a list of dicts."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = [dict(row._mapping) for row in result]
            logger.info(f"Query returned {len(rows)} rows")
            return rows
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise