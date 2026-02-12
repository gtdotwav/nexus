@echo off
chcp 65001 >nul
title NEXUS - Instalador Automatico
color 0B

echo.
echo     ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
echo     ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
echo     ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
echo     ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
echo     ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║
echo     ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝╚══════╝
echo.
echo     Instalador Automatico v0.4.2
echo     ─────────────────────────────────────────────
echo.

:: ──────────────────────────────────────────────────
:: STEP 1: Verificar Python
:: ──────────────────────────────────────────────────
echo   [1/5] Verificando Python...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    python3 --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo   ✗ Python nao encontrado!
        echo.
        echo   Vai abrir a pagina de download do Python.
        echo   IMPORTANTE: Marca "Add Python to PATH" na instalacao!
        echo.
        start https://python.org/downloads/
        echo   Depois de instalar o Python, roda este arquivo de novo.
        echo.
        pause
        exit /b 1
    )
    set PYTHON_CMD=python3
) else (
    set PYTHON_CMD=python
)

%PYTHON_CMD% -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" 2>nul
if %errorlevel% neq 0 (
    echo   ✗ Python 3.10+ necessario. Atualiza em python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PYVER=%%i
echo   ✓ %PYVER% encontrado

:: ──────────────────────────────────────────────────
:: STEP 2: Verificar Git
:: ──────────────────────────────────────────────────
echo   [2/5] Verificando Git...

git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   ✗ Git nao encontrado!
    echo.
    echo   Vai abrir a pagina de download do Git.
    echo   Instala com as opcoes padrao.
    echo.
    start https://git-scm.com/download/win
    echo   Depois de instalar o Git, roda este arquivo de novo.
    echo.
    pause
    exit /b 1
)

echo   ✓ Git encontrado

:: ──────────────────────────────────────────────────
:: STEP 3: Clonar ou atualizar repositorio
:: ──────────────────────────────────────────────────
echo   [3/5] Baixando NEXUS...

set "NEXUS_DIR=%USERPROFILE%\NEXUS"

if exist "%NEXUS_DIR%\.git" (
    echo   → Atualizando NEXUS existente...
    cd /d "%NEXUS_DIR%"
    git pull --quiet
    echo   ✓ NEXUS atualizado
) else (
    if exist "%NEXUS_DIR%" (
        echo   → Pasta NEXUS existe sem git, removendo...
        rmdir /s /q "%NEXUS_DIR%" 2>nul
    )
    echo   → Clonando repositorio...
    git clone https://github.com/gtdotwav/nexus.git "%NEXUS_DIR%" --quiet
    if %errorlevel% neq 0 (
        echo   ✗ Erro ao clonar. Verifica tua internet.
        pause
        exit /b 1
    )
    echo   ✓ NEXUS baixado em %NEXUS_DIR%
)

cd /d "%NEXUS_DIR%"

:: ──────────────────────────────────────────────────
:: STEP 4: Instalar dependencias
:: ──────────────────────────────────────────────────
echo   [4/5] Instalando dependencias (pode demorar 1-2 min)...

%PYTHON_CMD% -m pip install --upgrade pip --quiet 2>nul
%PYTHON_CMD% -m pip install -e . --quiet 2>nul

if %errorlevel% neq 0 (
    echo   ! Tentando instalar sem modo editavel...
    %PYTHON_CMD% -m pip install . --quiet 2>nul
)

:: Tenta instalar dxcam (Windows DirectX capture - opcional)
%PYTHON_CMD% -m pip install dxcam --quiet 2>nul
if %errorlevel% equ 0 (
    echo   ✓ Dependencias instaladas (com DirectX capture)
) else (
    echo   ✓ Dependencias instaladas (sem DirectX - vai usar fallback)
)

:: ──────────────────────────────────────────────────
:: STEP 5: Criar config e atalhos
:: ──────────────────────────────────────────────────
echo   [5/5] Configurando...

:: Criar config se nao existe
if not exist "%NEXUS_DIR%\config\settings.yaml" (
    if exist "%NEXUS_DIR%\config\settings.yaml.example" (
        copy "%NEXUS_DIR%\config\settings.yaml.example" "%NEXUS_DIR%\config\settings.yaml" >nul
        echo   ✓ Config criado (edite config\settings.yaml com seus hotkeys)
    )
) else (
    echo   ✓ Config ja existe
)

:: Criar diretorio de dados
if not exist "%NEXUS_DIR%\data" mkdir "%NEXUS_DIR%\data"

:: Criar INICIAR.bat na pasta do NEXUS
(
echo @echo off
echo chcp 65001 ^>nul
echo title NEXUS - Autonomous Gaming Agent
echo color 0B
echo cd /d "%NEXUS_DIR%"
echo echo.
echo echo   Iniciando NEXUS...
echo echo   Abre o Tibia e loga no seu personagem antes!
echo echo.
echo nexus start
echo if %%errorlevel%% neq 0 ^(
echo     echo.
echo     echo   Tentando modo alternativo...
echo     %PYTHON_CMD% -m nexus_cli start
echo ^)
echo pause
) > "%NEXUS_DIR%\INICIAR.bat"

:: Criar atalho na area de trabalho
set "DESKTOP=%USERPROFILE%\Desktop"
(
echo @echo off
echo cd /d "%NEXUS_DIR%"
echo call INICIAR.bat
) > "%DESKTOP%\NEXUS Agent.bat"

echo   ✓ Atalho criado na Area de Trabalho

:: ──────────────────────────────────────────────────
:: DONE!
:: ──────────────────────────────────────────────────
echo.
echo   ═══════════════════════════════════════════════
echo   ✓ INSTALACAO COMPLETA!
echo   ═══════════════════════════════════════════════
echo.
echo   Arquivos em: %NEXUS_DIR%
echo.
echo   COMO USAR:
echo   ──────────
echo   1. Edita config\settings.yaml com seu personagem e hotkeys
echo   2. Abre o Tibia e loga
echo   3. Double-click em "NEXUS Agent" na Area de Trabalho
echo      (ou roda "nexus start" no terminal)
echo.
echo   OPCIONAL (IA estrategica):
echo   ──────────────────────────
echo   Se quiser o cerebro estrategico (Claude pensando junto):
echo   Cria uma variavel de ambiente ANTHROPIC_API_KEY com sua chave
echo   Sem isso, o bot funciona normal (so sem a parte de IA avancada)
echo.
pause
