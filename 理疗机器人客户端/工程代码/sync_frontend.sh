#!/usr/bin/env bash
# =============================================================================
# sync_frontend.sh - 把前端 dist 同步到 backend/static
#
# 用法（在项目根目录执行）：
#   chmod +x sync_frontend.sh
#   ./sync_frontend.sh
#
# 适用：路径 A（后端 serve 前端），改完前端代码后执行一次
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

FRONTEND_DIR="frontend"
BACKEND_STATIC="backend/static"

if [ ! -d "$FRONTEND_DIR" ]; then
    echo "错误：找不到 $FRONTEND_DIR 目录" >&2
    exit 1
fi

echo "[1/3] 构建前端 (npm run build) ..."
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    echo "[1/3] 首次运行，先安装依赖 (npm install) ..."
    npm install
fi
npm run build
cd "$SCRIPT_DIR"

if [ ! -d "$FRONTEND_DIR/dist" ]; then
    echo "错误：构建失败，未生成 $FRONTEND_DIR/dist" >&2
    exit 1
fi

echo "[2/3] 清理旧的 backend/static ..."
rm -rf "$BACKEND_STATIC"

echo "[3/3] 复制 dist 到 backend/static ..."
mkdir -p "$BACKEND_STATIC"
cp -r "$FRONTEND_DIR/dist/." "$BACKEND_STATIC/"

echo ""
echo "✓ 前端已同步到 $BACKEND_STATIC/"
echo ""
echo "下一步："
echo "  - 如果 uvicorn 已在跑（带 --reload），刷新浏览器即可"
echo "  - 如果 launcher 在跑，刷新浏览器即可"
echo "  - 如果都没启动，执行："
echo "      cd backend && python -m uvicorn app.main:app --reload --port 8000"