import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alembic.config import Config
from alembic import command
from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("genius.migrations")

def run_migrations():
    """Runs all pending Alembic migrations up to head."""
    logger.info("Executing database migrations up to head...")
    try:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully.")
        return 0
    except Exception as e:
        logger.error(f"Migration execution failed: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(run_migrations())
