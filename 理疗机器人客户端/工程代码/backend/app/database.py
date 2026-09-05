import os
import shutil
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    pass


def _is_frozen() -> bool:
    """是否运行在 PyInstaller 打包后的环境。"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _get_bundle_root() -> Path:
    """打包后返回 _MEIPASS（只读资源目录），否则返回 backend/ 目录。"""
    if _is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def _get_user_data_dir() -> Path:
    """用户可写的数据目录（数据库、日志）。

    - Linux/macOS: ~/.local/share/physiotherapy-client/
    - Windows:     %APPDATA%/physiotherapy-client/
    - 可通过环境变量 PHYSIOTHERAPY_DATA_DIR 覆盖
    """
    override = os.environ.get("PHYSIOTHERAPY_DATA_DIR")
    if override:
        return Path(override)

    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    target = base / "physiotherapy-client"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _ensure_db_template() -> None:
    """首次运行时，把打包内的模板数据库复制到用户数据目录。"""
    if not _is_frozen():
        return

    user_data = _get_user_data_dir()
    user_db = user_data / "physiotherapy.db"
    if user_db.exists():
        return

    bundle_db = _get_bundle_root() / "data" / "physiotherapy.db"
    if bundle_db.exists():
        user_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundle_db, user_db)


_ensure_db_template()


def get_db_url() -> str:
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "")
        if not path.startswith("/"):
            # 打包模式下：数据库始终走用户数据目录（即使 settings.DATABASE_URL 是相对路径）
            if _is_frozen():
                path = str(_get_user_data_dir() / "physiotherapy.db")
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                path = os.path.join(base_dir, path)
        path = os.path.normpath(path)
        return f"sqlite:///{path}"
    return db_url


engine = create_engine(
    get_db_url(),
    connect_args={"check_same_thread": False},
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

AsyncEngine = create_async_engine(
    get_db_url().replace("sqlite://", "sqlite+aiosqlite://"),
    echo=settings.DEBUG,
)

async_session_maker = async_sessionmaker(
    AsyncEngine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def get_db() -> Session:
    with Session(engine) as session:
        try:
            yield session
        finally:
            session.close()


async def get_async_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


def init_db():
    Base.metadata.create_all(bind=engine)
