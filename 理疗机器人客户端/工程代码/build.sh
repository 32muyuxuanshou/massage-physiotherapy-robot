#!/usr/bin/env bash
# =============================================================================
# 颐本智能理疗系统 - Linux 一键打包脚本
#
# 流程：
#   1. 检查环境（python3, venv, 前端 dist）
#   2. 把 frontend/dist 复制到 backend/static（让 FastAPI 一起 serve）
#   3. 用 PyInstaller --onefile 把 launcher.py + 后端 + 前端打成单文件
#   4. 用 appimagetool 包装成 AppImage
#   5. 输出到 dist/
#
# 用法：
#   chmod +x build.sh
#   ./build.sh                      # 全流程
#   ./build.sh --skip-frontend      # 跳过前端复制（dist 已就位时用）
#   ./build.sh --skip-appimage      # 只生成 ELF，不打 AppImage
# =============================================================================
set -euo pipefail

# -------- 路径配置 --------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

FRONTEND_DIST="frontend/dist"
BACKEND_STATIC="backend/static"
BACKEND_VENV="backend/.venv"
LAUNCHER="launcher.py"
ICON_PNG="app_icon.png"

DIST_DIR="dist"
BUILD_DIR="build"
APPDIR="$DIST_DIR/AppDir"
APP_NAME="physiotherapy-client"
DISPLAY_NAME="颐本智能理疗系统"

# -------- 参数解析 --------
SKIP_FRONTEND=0
SKIP_APPIMAGE=0
for arg in "$@"; do
    case "$arg" in
        --skip-frontend) SKIP_FRONTEND=1 ;;
        --skip-appimage) SKIP_APPIMAGE=1 ;;
        -h|--help)
            echo "用法: $0 [--skip-frontend] [--skip-appimage]"
            exit 0
            ;;
        *) echo "未知参数: $arg"; exit 1 ;;
    esac
done

# -------- 颜色 --------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)]${NC} $*"; }
err()  { echo -e "${RED}[$(date +%H:%M:%S)]${NC} $*" >&2; }

# -------- 前置检查 --------
log "=== 1. 环境检查 ==="

if ! command -v python3 >/dev/null 2>&1; then
    err "找不到 python3，请先安装 Python 3.10+"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
log "Python 版本: $PY_VERSION"

if [ ! -d "$BACKEND_VENV" ]; then
    err "找不到 $BACKEND_VENV，请先创建后端虚拟环境："
    err "  cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

if [ ! -f "$LAUNCHER" ]; then
    err "找不到 $LAUNCHER"
    exit 1
fi

# -------- 步骤 2：嵌入前端 --------
if [ $SKIP_FRONTEND -eq 0 ]; then
    log "=== 2. 嵌入前端 dist 到 backend/static ==="
    if [ ! -d "$FRONTEND_DIST" ]; then
        err "找不到 $FRONTEND_DIST，请先构建前端："
        err "  cd frontend && npm install && npm run build"
        exit 1
    fi

    # 清理旧的，复制新的
    rm -rf "$BACKEND_STATIC"
    mkdir -p "$BACKEND_STATIC"
    cp -r "$FRONTEND_DIST/." "$BACKEND_STATIC/"
    log "前端已复制到 $BACKEND_STATIC"
else
    log "=== 2. 跳过前端嵌入（--skip-frontend）==="
fi

# -------- 步骤 3：准备打包 venv --------
log "=== 3. 准备打包环境 ==="

# 用 backend/.venv 装 pyinstaller，避免污染
source "$BACKEND_VENV/bin/activate"

if ! python -c "import PyInstaller" 2>/dev/null; then
    log "安装 pyinstaller..."
    pip install --quiet pyinstaller
fi

PYI_VERSION=$(python -c "import PyInstaller; print(PyInstaller.__version__)")
log "PyInstaller 版本: $PYI_VERSION"

# -------- 步骤 4：清理旧的构建产物 --------
log "=== 4. 清理旧产物 ==="
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$DIST_DIR"

# -------- 步骤 5：PyInstaller 打包 --------
log "=== 5. PyInstaller 打包 launcher.py ==="

# 数据打包：
#   - backend/static  -> 后端/static（前端资源）
#   - backend/data/physiotherapy.db -> 后端/data/（首次运行的模板数据库）
#   - backend/.env.example -> 后端/.env.example
# 注意：分号 ; 是 PyInstaller 在 Linux 上的路径分隔符
ADD_DATA_ARGS=(
    "--add-data=backend/static:backend/static"
)

if [ -f "backend/data/physiotherapy.db" ]; then
    ADD_DATA_ARGS+=("--add-data=backend/data/physiotherapy.db:backend/data")
fi

if [ -f "backend/.env.example" ]; then
    ADD_DATA_ARGS+=("--add-data=backend/.env.example:backend/")
fi

# 隐藏导入：覆盖 PyInstaller 静态分析漏掉的动态导入
HIDDEN_IMPORTS=(
    "--hidden-import=uvicorn"
    "--hidden-import=uvicorn.logging"
    "--hidden-import=uvicorn.loops"
    "--hidden-import=uvicorn.loops.auto"
    "--hidden-import=uvicorn.protocols"
    "--hidden-import=uvicorn.protocols.http"
    "--hidden-import=uvicorn.protocols.http.auto"
    "--hidden-import=uvicorn.protocols.websockets"
    "--hidden-import=uvicorn.protocols.websockets.auto"
    "--hidden-import=uvicorn.lifespan"
    "--hidden-import=uvicorn.lifespan.on"
    "--hidden-import=fastapi"
    "--hidden-import=fastapi.routing"
    "--hidden-import=fastapi.middleware"
    "--hidden-import=fastapi.middleware.cors"
    "--hidden-import=sqlalchemy"
    "--hidden-import=sqlalchemy.dialects.sqlite"
    "--hidden-import=aiosqlite"
    "--hidden-import=jose"
    "--hidden-import=jose.jwt"
    "--hidden-import=jose.jwk"
    "--hidden-import=jose.jws"
    "--hidden-import=jose.jwe"
    "--hidden-import=passlib"
    "--hidden-import=passlib.context"
    "--hidden-import=passlib.hash"
    "--hidden-import=passlib.handlers.bcrypt"
    "--hidden-import=bcrypt"
    "--hidden-import=pydantic"
    "--hidden-import=pydantic_settings"
    "--hidden-import=loguru"
    "--hidden-import=multipart"
    "--hidden-import=app"
    "--hidden-import=app.api"
    "--hidden-import=app.api.v1"
    "--hidden-import=app.api.v1.router"
    "--hidden-import=app.api.v1.auth"
    "--hidden-import=app.api.v1.users"
    "--hidden-import=app.api.v1.devices"
    "--hidden-import=app.api.v1.therapy"
    "--hidden-import=app.api.v1.ai"
    "--hidden-import=app.core.security"
    "--hidden-import=app.core.cache"
    "--hidden-import=app.core.exceptions"
    "--hidden-import=app.crud"
    "--hidden-import=app.crud.user_crud"
    "--hidden-import=app.crud.device_crud"
    "--hidden-import=app.crud.therapy_crud"
    "--hidden-import=app.crud.ai_crud"
    "--hidden-import=app.crud.base"
    "--hidden-import=app.models"
    "--hidden-import=app.models.user"
    "--hidden-import=app.models.device"
    "--hidden-import=app.models.therapy"
    "--hidden-import=app.models.ai"
    "--hidden-import=app.schemas"
    "--hidden-import=app.schemas.user"
    "--hidden-import=app.schemas.auth"
    "--hidden-import=app.schemas.device"
    "--hidden-import=app.schemas.therapy"
    "--hidden-import=app.schemas.ai"
    "--hidden-import=app.services"
    "--hidden-import=app.services.user_service"
    "--hidden-import=app.services.auth_service"
    "--hidden-import=app.services.device_service"
    "--hidden-import=app.services.therapy_service"
    "--hidden-import=app.services.ai_service"
    "--hidden-import=app.utils"
    "--hidden-import=app.utils.responses"
    "--hidden-import=app.utils.validators"
    "--collect-all=aiosqlite"
    "--collect-all=sqlalchemy"
    "--collect-all=passlib"
)

# 排除：用不到的巨型模块，减小体积
EXCLUDES=(
    "--exclude-module=tkinter"
    "--exclude-module=matplotlib"
    "--exclude-module=numpy"
    "--exclude-module=pandas"
    "--exclude-module=scipy"
    "--exclude-module=PIL"
    "--exclude-module=pytest"
    "--exclude-module=test"
    "--exclude-module=unittest"
    "--exclude-module=IPython"
    "--exclude-module=notebook"
    "--exclude-module=jupyter"
)

ICON_ARG=()
if [ -f "$ICON_PNG" ]; then
    ICON_ARG=("--icon=$ICON_PNG")
fi

pyinstaller \
    --noconfirm \
    --clean \
    --onefile \
    --name "$APP_NAME" \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    --specpath "$BUILD_DIR" \
    "${ICON_ARG[@]}" \
    "${ADD_DATA_ARGS[@]}" \
    "${HIDDEN_IMPORTS[@]}" \
    "${EXCLUDES[@]}" \
    "$LAUNCHER"

ELF_FILE="$DIST_DIR/$APP_NAME"
if [ ! -f "$ELF_FILE" ]; then
    err "PyInstaller 失败：未生成 $ELF_FILE"
    exit 1
fi

# 加可执行权限（PyInstaller 在 Linux 上一般已经是 +x，保险起见再设一次）
chmod +x "$ELF_FILE"

ELF_SIZE=$(du -h "$ELF_FILE" | cut -f1)
log "✓ PyInstaller 完成: $ELF_FILE ($ELF_SIZE)"

deactivate || true

# -------- 步骤 6：打包 AppImage --------
if [ $SKIP_APPIMAGE -eq 0 ]; then
    log "=== 6. 打包 AppImage ==="

    # 检查 appimagetool
    APPIMAGETOOL=""
    if command -v appimagetool >/dev/null 2>&1; then
        APPIMAGETOOL="appimagetool"
    elif [ -x "$HOME/bin/appimagetool" ]; then
        APPIMAGETOOL="$HOME/bin/appimagetool"
    elif [ -x "./appimagetool" ]; then
        APPIMAGETOOL="./appimagetool"
    else
        warn "找不到 appimagetool，跳过 AppImage 打包"
        warn "（如需 AppImage，请下载：https://github.com/AppImage/AppImageKit/releases）"
        warn "  并放到 PATH 或 $HOME/bin/ 或当前目录下"
        SKIP_APPIMAGE=1
    fi
fi

if [ $SKIP_APPIMAGE -eq 0 ]; then
    # 构造 AppDir
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin"
    mkdir -p "$APPDIR/usr/share/applications"
    mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

    # 复制 ELF
    cp "$ELF_FILE" "$APPDIR/usr/bin/$APP_NAME"
    chmod +x "$APPDIR/usr/bin/$APP_NAME"

    # 复制图标
    if [ -f "$ICON_PNG" ]; then
        cp "$ICON_PNG" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
        cp "$ICON_PNG" "$APPDIR/$APP_NAME.png"
    fi

    # AppRun 脚本（入口）
    cat > "$APPDIR/AppRun" <<'APPRUN_EOF'
#!/usr/bin/env bash
# AppImage 入口：执行内嵌的 physiotherapy-client
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/usr/bin/physiotherapy-client" "$@"
APPRUN_EOF
    chmod +x "$APPDIR/AppRun"

    # 桌面文件
    cat > "$APPDIR/usr/share/applications/$APP_NAME.desktop" <<DESKTOP_EOF
[Desktop Entry]
Type=Application
Name=颐本智能理疗系统
Name[en]=Physiotherapy Client
GenericName=Medical Therapy System
Comment=颐本智能理疗系统 - 桌面客户端
Comment[en]=Physiotherapy Management Desktop Client
Exec=physiotherapy-client %u
Icon=physiotherapy-client
Terminal=false
Categories=Medical;Health;
StartupNotify=true
StartupWMClass=physiotherapy-client
DESKTOP_EOF

    # 顶层也放一份 .desktop（AppImage 规范要求）
    cp "$APPDIR/usr/share/applications/$APP_NAME.desktop" "$APPDIR/$APP_NAME.desktop"

    # 生成 AppImage
    ARCH=x86_64 "$APPIMAGETOOL" \
        --no-appstream \
        "$APPDIR" \
        "$DIST_DIR/${DISPLAY_NAME}-x86_64.AppImage"

    APPIMAGE_FILE="$DIST_DIR/${DISPLAY_NAME}-x86_64.AppImage"
    if [ -f "$APPIMAGE_FILE" ]; then
        chmod +x "$APPIMAGE_FILE"
        APPIMAGE_SIZE=$(du -h "$APPIMAGE_FILE" | cut -f1)
        log "✓ AppImage 完成: $APPIMAGE_FILE ($APPIMAGE_SIZE)"
    else
        warn "AppImage 生成失败"
    fi
fi

# -------- 7. 收尾 --------
log "=== 完成 ==="
echo ""
log "产物："
ls -lh "$DIST_DIR/" 2>/dev/null || true
echo ""
log "测试方法："
echo "  1. 直接运行 ELF:   $DIST_DIR/$APP_NAME"
echo "  2. 或运行 AppImage: $DIST_DIR/${DISPLAY_NAME}-x86_64.AppImage"
echo ""
log "用户机器要求："
echo "  - 任意现代 Linux 发行版（Ubuntu 22.04+ / Debian 12+ / Arch 等）"
echo "  - 装了任意浏览器（Firefox / Chromium / Chrome）"
echo "  - 零 Python 依赖"