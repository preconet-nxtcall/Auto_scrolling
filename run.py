import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import settings

if __name__ == "__main__":
    print(f"Launching Document Auto-Viewer SaaS on http://{settings.HOST}:{settings.PORT}")
    print(f"API Documentation available on http://{settings.HOST}:{settings.PORT}/api/docs")
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
