"""Application configuration. Loads DATABASE_URL from environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:AUktambek012@localhost:5432/Choco_factory",
)
