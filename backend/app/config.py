import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of backend
BACKEND_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = BACKEND_DIR.parent

import sys
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Load .env if present
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Document Auto-Viewer SaaS")
    BASE_DIR: Path = BASE_DIR
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api")
    
    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'backend' / 'storage' / 'autoscroll.db'}")
    
    # Storage Paths
    STORAGE_DIR: Path = BASE_DIR / "backend" / "storage"
    TEMP_DIR: Path = STORAGE_DIR / "temp"
    UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
    CONVERTED_DIR: Path = STORAGE_DIR / "converted"
    
    # Auto-Viewer Defaults
    DEFAULT_SCROLL_SPEED: int = int(os.getenv("DEFAULT_SCROLL_SPEED", 50))  # px per second
    DEFAULT_REPEAT_COUNT: int = int(os.getenv("DEFAULT_REPEAT_COUNT", 3))   # cycles
    
    # Conversion Subprocess Timeout (seconds)
    CONVERSION_TIMEOUT_SECONDS: int = int(os.getenv("CONVERSION_TIMEOUT_SECONDS", 60))

    # Allowed Document Formats
    ALLOWED_EXTENSIONS: set = {
        # PDF Pass-through
        ".pdf",
        # Office Word
        ".docx", ".doc",
        # Office PowerPoint
        ".pptx", ".ppt",
        # Office Excel & Data
        ".xlsx", ".xls", ".csv",
        # Common Image Formats
        ".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp", ".gif"
    }

    # CORS Origins
    CORS_ORIGINS: list = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "*"
    ]

settings = Settings()

# Ensure storage directories exist
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.CONVERTED_DIR.mkdir(parents=True, exist_ok=True)
