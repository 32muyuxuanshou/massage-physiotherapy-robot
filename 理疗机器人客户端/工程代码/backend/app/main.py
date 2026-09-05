from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import sys

from app.config import get_settings
from app.api.v1.router import router as api_router
from app.database import init_db


settings = get_settings()


def get_base_dir() -> str:
    """获取应用根目录，兼容 PyInstaller 打包后的运行环境。

    - 开发模式：取 app/ 的父目录（即 backend/）
    - 打包模式：取 sys._MEIPASS（PyInstaller 解压的临时目录）
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller --onefile 解压目录
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = get_base_dir()
STATIC_DIR = os.path.join(BASE_DIR, "static")


def create_app() -> FastAPI:
    app = FastAPI(
        title="颐本智能理疗系统",
        description="颐本智能理疗系统后端API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if os.path.exists(STATIC_DIR):
        app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    app.include_router(api_router, prefix="/api")

    @app.on_event("startup")
    async def startup_event():
        init_db()

    @app.get("/")
    async def root():
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {
            "message": "颐本智能理疗系统 API",
            "version": "0.1.0",
            "docs": "/docs"
        }

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file_path = os.path.join(STATIC_DIR, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "Not found"}

    return app


app = create_app()
