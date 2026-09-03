import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.auth import get_or_create_default_user
from app.router import router as api_router

logger = logging.getLogger("uvicorn.error")

# Auto-create SQLAlchemy database tables on startup
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # Auto-seed default user on startup
    db = SessionLocal()
    try:
        get_or_create_default_user(db)
    except Exception as e:
        logger.warning(f"Default user seeding notice: {e}")
    finally:
        db.close()
    yield

app = FastAPI(
    title=settings.APP_NAME,
    description="Production-Ready Document Auto-Viewer SaaS Backend & Storage Streamer",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"An internal server error occurred: {str(exc)}"}
    )

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Frontend Static Mounting
FRONTEND_DIR = settings.BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

@app.get("/")
def read_root():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, headers=NO_CACHE_HEADERS)
    return JSONResponse({"status": "running", "app_name": settings.APP_NAME})

@app.get("/css/{file_name:path}")
def serve_css(file_name: str):
    css_path = FRONTEND_DIR / "css" / file_name
    if css_path.exists():
        return FileResponse(css_path, headers=NO_CACHE_HEADERS)
    return JSONResponse({"detail": "CSS file not found"}, status_code=404)

@app.get("/js/{file_name:path}")
def serve_js(file_name: str):
    js_path = FRONTEND_DIR / "js" / file_name
    if js_path.exists():
        return FileResponse(js_path, headers=NO_CACHE_HEADERS)
    return JSONResponse({"detail": "JS file not found"}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
