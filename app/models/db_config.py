from typing import Literal, Optional

from pydantic import BaseModel, SecretStr, model_validator

# Default ports so the user doesn't have to remember them
DEFAULT_PORTS = {"mysql": 3306, "postgresql": 5432}


class DBConfig(BaseModel):
    """Describes how to connect to a user's database."""

    # Literal means ONLY these three strings are accepted.
    # Anything else (e.g. "oracle") is rejected automatically.
    db_type: Literal["mysql", "postgresql", "sqlite"]

    # Optional because SQLite has no host, port, user or password
    db_host: Optional[str] = None
    db_port: Optional[int] = None
    db_user: Optional[str] = None

    # SecretStr hides the value when the object is printed or logged
    db_password: Optional[SecretStr] = None

    # For MySQL/PostgreSQL this is the database name.
    # For SQLite this is the path to the .db file.
    db_name: str

    # Empty list means "use all tables"
    selected_tables: list[str] = []

    @model_validator(mode="after")
    def check_required_fields(self) -> "DBConfig":
        """Cross-field rules: what's required depends on db_type."""
        if self.db_type in ("mysql", "postgresql"):
            if not self.db_host or not self.db_user:
                raise ValueError(
                    f"{self.db_type} requires db_host and db_user."
                )
            # Fill in the default port if the user left it blank
            if self.db_port is None:
                self.db_port = DEFAULT_PORTS[self.db_type]
        return self