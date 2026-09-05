# =============================================================================
# sync_frontend.ps1 - 把前端 dist 同步到 backend/static (Windows PowerShell)
#
# 用法（在项目根目录执行）：
#   .\sync_frontend.ps1
#
# 适用：路径 A（后端 serve 前端），改完前端代码后执行一次
# =============================================================================
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$FrontendDir = Join-Path $ScriptDir "frontend"
$BackendStatic = Join-Path $ScriptDir "backend\static"

if (-not (Test-Path $FrontendDir)) {
    Write-Error "找不到 $FrontendDir 目录"
    exit 1
}

Write-Host "[1/3] 构建前端 (npm run build) ..."
Set-Location $FrontendDir
if (-not (Test-Path "node_modules")) {
    Write-Host "[1/3] 首次运行，先安装依赖 (npm install) ..."
    npm install
}
npm run build
Set-Location $ScriptDir

if (-not (Test-Path "$FrontendDir\dist")) {
    Write-Error "构建失败，未生成 $FrontendDir\dist"
    exit 1
}

Write-Host "[2/3] 清理旧的 backend\static ..."
if (Test-Path $BackendStatic) {
    Remove-Item -Recurse -Force $BackendStatic
}

Write-Host "[3/3] 复制 dist 到 backend\static ..."
Copy-Item -Recurse "$FrontendDir\dist" $BackendStatic

Write-Host ""
Write-Host "✓ 前端已同步到 $BackendStatic" -ForegroundColor Green
Write-Host ""
Write-Host "下一步："
Write-Host "  - 如果 uvicorn 已在跑（带 --reload），刷新浏览器即可"
Write-Host "  - 如果 launcher 在跑，刷新浏览器即可"
Write-Host "  - 如果都没启动，执行："
Write-Host "      cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"