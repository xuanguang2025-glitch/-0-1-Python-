# PYTHON LAB —— 一键启动开发环境：后端(8000) + 前端(3000) [+ 沙箱(8081)]
# 用法：powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 [-NoSandbox] [-NoFrontend]
param(
    [switch]$NoSandbox,
    [switch]$NoFrontend
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Write-Step([string]$Message) { Write-Host "[dev] $Message" -ForegroundColor Cyan }
function Write-Warn([string]$Message) { Write-Host "[dev] $Message" -ForegroundColor Yellow }

$Procs = @()

function Start-Service-Window {
    param([string]$Title, [string]$WorkDir, [string]$Command)
    $full = "`$host.UI.RawUI.WindowTitle='$Title'; Set-Location -LiteralPath '$WorkDir'; $Command"
    $proc = Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile", "-Command", $full) -PassThru -WindowStyle Minimized
    $script:Procs += $proc
    Write-Step "已启动 $Title (PID=$($proc.Id))"
}

$BackendVenv = Join-Path $Root "backend\.venv\Scripts\python.exe"
$SandboxVenv = Join-Path $Root "sandbox\.venv\Scripts\python.exe"
$FrontendDir = Join-Path $Root "frontend"
$BackendDir = Join-Path $Root "backend"
$SandboxDir = Join-Path $Root "sandbox"

# ------------------------------------------------------------- 后端
if (Test-Path $BackendVenv) {
    Start-Service-Window -Title "pythonlab-backend" -WorkDir $BackendDir `
        -Command "& '$BackendVenv' -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
} else {
    Write-Warn "未找到 backend\.venv，请先运行 scripts\setup.ps1"
}

# ------------------------------------------------------------- 沙箱（可选）
if (-not $NoSandbox) {
    if (Test-Path $SandboxVenv) {
        Start-Service-Window -Title "pythonlab-sandbox" -WorkDir $SandboxDir `
            -Command "& '$SandboxVenv' -m uvicorn app.main:app --host 127.0.0.1 --port 8081"
        Write-Step "沙箱安全等级见 http://127.0.0.1:8081/health"
    } else {
        Write-Warn "未找到 sandbox\.venv，跳过沙箱（后端将自动降级为 LocalRunner）"
    }
}

# ------------------------------------------------------------- 前端
if (-not $NoFrontend) {
    if (Test-Path (Join-Path $FrontendDir "package.json")) {
        Start-Service-Window -Title "pythonlab-frontend" -WorkDir $FrontendDir -Command "npm run dev"
    } else {
        Write-Warn "frontend\package.json 不存在，跳过前端启动"
    }
}

Write-Step "后端 http://127.0.0.1:8000 | 前端 http://localhost:3000"
Write-Step "健康检查：python scripts\healthcheck.py"
Write-Host ""
Write-Host "按回车键停止全部子进程并退出..." -ForegroundColor Yellow
[void][System.Console]::ReadLine()

foreach ($proc in $Procs) {
    if ($proc -and -not $proc.HasExited) {
        try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch { }
    }
}
Write-Step "已停止全部子进程"
