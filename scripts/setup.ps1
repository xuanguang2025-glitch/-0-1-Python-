# PYTHON LAB —— 一键初始化（Windows / PowerShell 5.1 兼容）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 [-SkipFrontend] [-WithMigrate] [-WithSeed]
param(
    [switch]$SkipFrontend,
    [switch]$WithMigrate,
    [switch]$WithSeed
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$PipIndex = if ($env:PIP_INDEX) { $env:PIP_INDEX } else { "https://pypi.tuna.tsinghua.edu.cn/simple" }
$NpmRegistry = if ($env:NPM_REGISTRY) { $env:NPM_REGISTRY } else { "https://registry.npmmirror.com" }

function Write-Step([string]$Message) { Write-Host "[setup] $Message" -ForegroundColor Cyan }
function Write-Warn([string]$Message) { Write-Host "[setup] $Message" -ForegroundColor Yellow }

function Get-PythonTokens {
    if ($env:PYTHON) { return @($env:PYTHON) }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return @($py.Source, "-3") }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return @($python.Source) }
    throw "找不到 Python，请安装 Python 3.13+ 或设置环境变量 PYTHON"
}

function Invoke-Python {
    param([string[]]$Tokens, [string[]]$PythonArgs)
    $exe = $Tokens[0]
    $prefix = @()
    if ($Tokens.Length -gt 1) { $prefix = $Tokens[1..($Tokens.Length - 1)] }
    & $exe @prefix @PythonArgs
    if ($LASTEXITCODE -ne 0) { throw "Python 命令执行失败：$exe $($PythonArgs -join ' ')" }
}

# ---------------------------------------------------------------- 1. .env
if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    Write-Step "已生成 .env（来自 .env.example）—— 请按需修改密钥与 AI Key"
} else {
    Write-Step ".env 已存在，跳过"
}

# ---------------------------------------------------------- 2. 后端 venv
$BackendReq = Join-Path $Root "backend\requirements.txt"
$VenvDir = Join-Path $Root "backend\.venv"
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"

if (Test-Path $BackendReq) {
    if (-not (Test-Path $VenvPy)) {
        Write-Step "创建 backend\.venv"
        $tokens = Get-PythonTokens
        Invoke-Python -Tokens $tokens -PythonArgs @("-m", "venv", $VenvDir)
    }
    Write-Step "升级 pip 并安装后端依赖（国内源 $PipIndex）"
    & $VenvPy -m pip install --upgrade pip -i $PipIndex
    & $VenvPy -m pip install -r $BackendReq -i $PipIndex
    $DevReq = Join-Path $Root "backend\requirements-dev.txt"
    if (Test-Path $DevReq) { & $VenvPy -m pip install -r $DevReq -i $PipIndex }
    if ($LASTEXITCODE -ne 0) { throw "后端依赖安装失败" }
} else {
    Write-Warn "backend\requirements.txt 不存在，跳过后端依赖安装"
}

# -------------------------------------------------------- 3. 数据目录
foreach ($dir in @("data", "data\uploads", "logs")) {
    $path = Join-Path $Root $dir
    if (-not (Test-Path $path)) { New-Item -ItemType Directory -Path $path -Force | Out-Null }
}

# ---------------------------------------------------------- 4. 前端依赖
if (-not $SkipFrontend) {
    $PackageJson = Join-Path $Root "frontend\package.json"
    if (Test-Path $PackageJson) {
        Write-Step "安装前端依赖（registry=$NpmRegistry）"
        Push-Location (Join-Path $Root "frontend")
        try {
            & npm install --registry=$NpmRegistry
            if ($LASTEXITCODE -ne 0) { throw "npm install 失败" }
        } finally {
            Pop-Location
        }
    } else {
        Write-Warn "frontend\package.json 不存在，跳过前端依赖安装"
    }
} else {
    Write-Warn "按要求跳过前端依赖安装"
}

# ------------------------------------------------- 5. 可选：迁移与种子
if ($WithMigrate) {
    Write-Step "执行数据库迁移"
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "migrate.ps1")
}
if ($WithSeed) {
    Write-Step "导入种子数据"
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "seed.ps1")
}

Write-Step "完成。下一步：powershell -File scripts\dev.ps1 然后打开 http://localhost:3000"
