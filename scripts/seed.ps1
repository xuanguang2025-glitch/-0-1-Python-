# PYTHON LAB —— 导入种子数据（18 阶段课程 / 题库 / 项目 / 知识点 / 成就 ...）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\seed.ps1 [-Only courses,problems]
param(
    [string]$Only = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "backend"
$VenvPy = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPy)) {
    Write-Host "[seed] 未找到 backend\.venv，请先运行 scripts\setup.ps1" -ForegroundColor Red
    exit 1
}

$SeedArgs = @()
if ($Only -ne "") { $SeedArgs += @("--only", $Only) }

Set-Location $BackendDir
$ScriptSeed = Join-Path $BackendDir "scripts\seed_data.py"
$ModuleSeed = Join-Path $BackendDir "app\db\seed\loader.py"

if (Test-Path $ScriptSeed) {
    Write-Host "[seed] python scripts\seed_data.py $($SeedArgs -join ' ')" -ForegroundColor Cyan
    & $VenvPy "scripts\seed_data.py" @SeedArgs
} elseif (Test-Path $ModuleSeed) {
    Write-Host "[seed] python -m app.db.seed.loader $($SeedArgs -join ' ')" -ForegroundColor Cyan
    & $VenvPy -m "app.db.seed.loader" @SeedArgs
} else {
    Write-Host "[seed] 未找到种子导入脚本（backend\scripts\seed_data.py 或 backend\app\db\seed\loader.py）" -ForegroundColor Red
    exit 1
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[seed] 导入失败（exit=$LASTEXITCODE）" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "[seed] 完成" -ForegroundColor Cyan
