# PYTHON LAB —— 数据库迁移（alembic upgrade head）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\migrate.ps1 [-Revision head]
param(
    [string]$Revision = "head"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$BackendDir = Join-Path $Root "backend"
$VenvPy = Join-Path $BackendDir ".venv\Scripts\python.exe"
$AlembicIni = Join-Path $BackendDir "alembic.ini"

if (-not (Test-Path $VenvPy)) {
    Write-Host "[migrate] 未找到 backend\.venv，请先运行 scripts\setup.ps1" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $AlembicIni)) {
    Write-Host "[migrate] backend\alembic.ini 不存在，跳过迁移（数据库可能由 seed 直接建表）" -ForegroundColor Yellow
    exit 0
}

Set-Location $BackendDir
Write-Host "[migrate] alembic upgrade $Revision" -ForegroundColor Cyan
& $VenvPy -m alembic upgrade $Revision
if ($LASTEXITCODE -ne 0) {
    Write-Host "[migrate] 迁移失败（exit=$LASTEXITCODE）" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "[migrate] 完成" -ForegroundColor Cyan
