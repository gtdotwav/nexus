# ═══════════════════════════════════════════════════════
#  NEXUS — Windows Installer
#
#  Installs NEXUS on Windows 10/11.
#  Handles: Python check, dependencies, config, shortcuts.
#
#  Usage (PowerShell as Administrator):
#    Set-ExecutionPolicy Bypass -Scope Process
#    .\scripts\install_windows.ps1
# ═══════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

$NEXUS_VERSION = "0.5.0"
$NEXUS_HOME = "$env:USERPROFILE\NEXUS"
$MIN_PYTHON_MAJOR = 3
$MIN_PYTHON_MINOR = 10

function Write-Banner {
    Write-Host ""
    Write-Host "    ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗" -ForegroundColor Cyan
    Write-Host "    ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝" -ForegroundColor Cyan
    Write-Host "    ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗" -ForegroundColor Cyan
    Write-Host "    ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║" -ForegroundColor Cyan
    Write-Host "    ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║" -ForegroundColor Cyan
    Write-Host "    ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝╚══════╝" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "    Autonomous Gaming Agent v$NEXUS_VERSION" -ForegroundColor DarkGray
    Write-Host "    Windows Installer" -ForegroundColor DarkGray
    Write-Host ""
}

function Write-Ok   { param($msg) Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  ! $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "  ✗ $msg" -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "  → $msg" -ForegroundColor Cyan }

# ─── Check Windows Version ───────────────────────────

function Test-WindowsVersion {
    $os = [System.Environment]::OSVersion.Version
    if ($os.Major -ge 10) {
        Write-Ok "Windows $($os.Major).$($os.Minor) detected"
    } else {
        Write-Fail "Windows 10+ required"
        exit 1
    }
}

# ─── Check/Find Python ──────────────────────────────

function Find-Python {
    $candidates = @(
        "python3.13", "python3.12", "python3.11", "python3", "python",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe"
    )

    foreach ($cmd in $candidates) {
        try {
            $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver) {
                $parts = $ver.Split('.')
                $major = [int]$parts[0]
                $minor = [int]$parts[1]
                if ($major -ge $MIN_PYTHON_MAJOR -and $minor -ge $MIN_PYTHON_MINOR) {
                    $fullVer = & $cmd --version 2>&1
                    Write-Ok "Python found: $fullVer"
                    return $cmd
                }
            }
        } catch {
            continue
        }
    }

    Write-Fail "Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ not found"
    Write-Host ""
    Write-Info "Install Python from: https://python.org/downloads/"
    Write-Info "Make sure to check 'Add Python to PATH' during installation!"
    Write-Host ""

    $response = Read-Host "  Open Python download page? (y/n)"
    if ($response -eq 'y') {
        Start-Process "https://python.org/downloads/"
    }

    exit 1
}

# ─── Create Virtual Environment ──────────────────────

function New-VirtualEnv {
    param($PythonCmd)

    New-Item -ItemType Directory -Force -Path $NEXUS_HOME | Out-Null
    New-Item -ItemType Directory -Force -Path "$NEXUS_HOME\data" | Out-Null
    New-Item -ItemType Directory -Force -Path "$NEXUS_HOME\logs" | Out-Null
    New-Item -ItemType Directory -Force -Path "$NEXUS_HOME\skills" | Out-Null

    $venvPath = "$NEXUS_HOME\venv"

    if (-not (Test-Path "$venvPath\Scripts\python.exe")) {
        Write-Info "Creating virtual environment..."
        & $PythonCmd -m venv $venvPath
        Write-Ok "Virtual environment created"
    } else {
        Write-Ok "Virtual environment exists"
    }

    # Activate
    & "$venvPath\Scripts\Activate.ps1"
    Write-Ok "Virtual environment activated"
}

# ─── Install Dependencies ────────────────────────────

function Install-Dependencies {
    Write-Info "Upgrading pip..."
    python -m pip install --upgrade pip --quiet 2>$null

    $repoDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

    if (Test-Path "$repoDir\pyproject.toml") {
        Write-Info "Installing NEXUS from local source..."
        pip install -e $repoDir --quiet 2>$null
        Write-Ok "NEXUS installed from local source"
    } else {
        Write-Info "Installing core dependencies..."
        pip install `
            opencv-python numpy Pillow pynput `
            anthropic pyyaml structlog rich `
            aiohttp click dxcam `
            --quiet 2>$null
        Write-Ok "Core dependencies installed"
    }

    # Windows-specific: dxcam for DirectX capture
    try {
        pip install dxcam --quiet 2>$null
        Write-Ok "DirectX screen capture (dxcam) installed"
    } catch {
        Write-Warn "dxcam installation failed (will use fallback capture)"
    }
}

# ─── Create Config ───────────────────────────────────

function New-Config {
    $configFile = "$NEXUS_HOME\config.yaml"

    if (Test-Path $configFile) {
        Write-Ok "Config already exists: $configFile"
        return
    }

    Write-Info "Creating default config..."

    $config = @"
# NEXUS Configuration — Windows
# Edit this file to customize your agent.

agent:
  game: tibia
  character_name: YourCharacter
  server: YourServer

perception:
  capture:
    method: dxcam  # Windows uses DirectX capture
    fps: 30
    game_window_title: Tibia

reactive:
  tick_rate_ms: 25
  healing:
    critical_hp: 30
    medium_hp: 60
    mana_threshold: 50
  hotkeys:
    heal_critical: F1
    heal_medium: F2
    mana_potion: F3
    haste: F4
    attack_spell: F5
    area_spell: F6

ai:
  model_strategic: claude-sonnet-4-20250514
  strategic_cycle_seconds: 3
  max_tokens: 1024
  temperature: 0.2
  api_key_env: ANTHROPIC_API_KEY

input:
  human_delay_min_ms: 30
  human_delay_max_ms: 80
  click_variance_px: 3

skills:
  directory: skills/tibia
  auto_create: true
  auto_improve: true

dashboard:
  enabled: true
  host: 127.0.0.1
  port: 8420
"@

    $config | Out-File -FilePath $configFile -Encoding UTF8
    Write-Ok "Config created: $configFile"
}

# ─── Create Desktop Shortcut ────────────────────────

function New-DesktopShortcut {
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = "$desktopPath\NEXUS Agent.lnk"

    # Create a batch file that the shortcut will run
    $batchFile = "$NEXUS_HOME\start_nexus.bat"
    $batchContent = @"
@echo off
title NEXUS - Autonomous Gaming Agent
call "$NEXUS_HOME\venv\Scripts\activate.bat"
nexus start
pause
"@
    $batchContent | Out-File -FilePath $batchFile -Encoding ASCII

    # Create shortcut
    try {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $batchFile
        $shortcut.WorkingDirectory = $NEXUS_HOME
        $shortcut.Description = "NEXUS Autonomous Gaming Agent"
        $shortcut.Save()
        Write-Ok "Desktop shortcut created: NEXUS Agent"
    } catch {
        Write-Warn "Could not create desktop shortcut"
        Write-Info "You can start NEXUS manually: $batchFile"
    }

    # Also create a start menu entry
    $startMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
    try {
        $shortcut2 = $shell.CreateShortcut("$startMenuPath\NEXUS Agent.lnk")
        $shortcut2.TargetPath = $batchFile
        $shortcut2.WorkingDirectory = $NEXUS_HOME
        $shortcut2.Description = "NEXUS Autonomous Gaming Agent"
        $shortcut2.Save()
        Write-Ok "Start Menu entry created"
    } catch {
        # Not critical
    }
}

# ─── Create PATH Entry ──────────────────────────────

function Add-ToPath {
    $venvBin = "$NEXUS_HOME\venv\Scripts"

    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($currentPath -notlike "*$venvBin*") {
        [Environment]::SetEnvironmentVariable(
            "PATH",
            "$venvBin;$currentPath",
            "User"
        )
        Write-Ok "'nexus' command added to PATH (restart terminal to use)"
    } else {
        Write-Ok "'nexus' command already in PATH"
    }
}

# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════

Write-Banner

Write-Host "  Checking system..." -ForegroundColor White
Write-Host ""
Test-WindowsVersion

Write-Host ""
Write-Host "  Setting up Python..." -ForegroundColor White
Write-Host ""
$pythonCmd = Find-Python

Write-Host ""
Write-Host "  Creating environment..." -ForegroundColor White
Write-Host ""
New-VirtualEnv -PythonCmd $pythonCmd

Write-Host ""
Write-Host "  Installing dependencies..." -ForegroundColor White
Write-Host ""
Install-Dependencies

Write-Host ""
Write-Host "  Configuring NEXUS..." -ForegroundColor White
Write-Host ""
New-Config

Write-Host ""
Write-Host "  Setting up shortcuts..." -ForegroundColor White
Write-Host ""
New-DesktopShortcut
Add-ToPath

Write-Host ""
Write-Host "  ═══════════════════════════════════════════" -ForegroundColor Green
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host "  ═══════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Quick start:" -ForegroundColor White
Write-Host "    1. Set your API key:" -ForegroundColor Gray
Write-Host "       `$env:ANTHROPIC_API_KEY = 'your_key'" -ForegroundColor Cyan
Write-Host "    2. Edit config:" -ForegroundColor Gray
Write-Host "       $NEXUS_HOME\config.yaml" -ForegroundColor Cyan
Write-Host "    3. Start NEXUS:" -ForegroundColor Gray
Write-Host "       nexus start" -ForegroundColor Cyan
Write-Host "    4. Open dashboard:" -ForegroundColor Gray
Write-Host "       http://127.0.0.1:8420" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Or double-click 'NEXUS Agent' on your Desktop." -ForegroundColor DarkGray
Write-Host ""

Read-Host "  Press Enter to finish"
