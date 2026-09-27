# PYTHON LAB —— 一键 Docker 部署（docker compose up -d --build）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\docker-up.ps1 [-NoBuild] [-WithProxy] [-Logs]
param(
    [switch]$NoBuild,
    [switch]$WithProxy,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Host "[docker-up] 未安装 docker；本机无 Docker 请用 scripts\setup.ps1 + scripts\dev.ps1" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    Write-Host "[docker-up] 已从 .env.example 生成 .env，请检查密钥后再部署" -ForegroundColor Yellow
}

$ComposeArgs = @()
if (-not $NoBuild) { $ComposeArgs += "--build" }
if ($WithProxy) { $env:COMPOSE_PROFILES = "proxy" }

Write-Host "[docker-up] docker compose up -d $($ComposeArgs -join ' ')" -ForegroundColor Cyan
& docker compose up -d @ComposeArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "[docker-up] 启动失败（exit=$LASTEXITCODE）" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "[docker-up] 当前状态：" -ForegroundColor Cyan
& docker compose ps

Write-Host "[docker-up] 排查用：docker compose logs -f backend" -ForegroundColor Cyan
if ($Logs) { & docker compose logs -f }
