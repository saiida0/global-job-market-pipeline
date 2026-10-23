import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when required runtime configuration is missing or invalid."""


REQUIRED_ENV_VARS = (
    "POSTGRES_HOST",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)


def _missing_env_message(missing_vars: list[str]) -> str:
    missing = "\n".join(f"  {name}" for name in missing_vars)
    return f"""Missing required environment variables:

{missing}

Setup:
  1. Copy .env.example to .env
  2. Edit .env with your PostgreSQL credentials
  3. Run: python -m src.main

Your .env should contain:
  POSTGRES_USER=your_username
  POSTGRES_PASSWORD=your_password
  POSTGRES_DB=job_market
  POSTGRES_HOST=localhost
  POSTGRES_PORT=5432
"""


@dataclass(frozen=True)
class Config:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    log_level: str = "INFO"

    @classmethod
    def load(cls) -> "Config":
        load_dotenv()

        missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
        if missing:
            raise ConfigError(_missing_env_message(missing))

        db_port_raw = os.getenv("POSTGRES_PORT", "5432")
        try:
            db_port = int(db_port_raw)
        except ValueError as exc:
            raise ConfigError(
                f"POSTGRES_PORT must be an integer, got {db_port_raw!r}."
            ) from exc

        return cls(
            db_host=os.environ["POSTGRES_HOST"],
            db_port=db_port,
            db_name=os.environ["POSTGRES_DB"],
            db_user=os.environ["POSTGRES_USER"],
            db_password=os.environ["POSTGRES_PASSWORD"],
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def get_db_connection_string(self, mask_password: bool = True) -> str:
        password = "****" if mask_password else self.db_password
        return (
            f"postgresql://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


config = Config.load()
