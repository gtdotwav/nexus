#!/bin/bash
# ═══════════════════════════════════════════════════════
#  NEXUS — macOS Installer v0.5.1
#
#  Fully autonomous installer for macOS (Intel + Apple Silicon).
#  Auto-installs: Homebrew, Python 3.12, Git, all dependencies.
#
#  Usage:
#    bash <(curl -fsSL https://raw.githubusercontent.com/gtdotwav/nexus/main/scripts/install_macos.sh)
#
#  Or locally:
#    bash scripts/install_macos.sh
# ═══════════════════════════════════════════════════════

# ─── CONFIG ──────────────────────────────────────────

NEXUS_VERSION="0.5.2"
NEXUS_DIR="$HOME/NEXUS"
NEXUS_REPO="https://github.com/gtdotwav/nexus.git"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10
INSTALL_START_TIME=""

# Global: set by find_python()
PYTHON_CMD=""

# ─── COLORS (auto-disable if not a terminal) ────────

if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    DIM='\033[2m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' CYAN='' BOLD='' DIM='' NC=''
fi

# ─── LOGGING ─────────────────────────────────────────

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

die() {
    echo ""
    fail "$1"
    if [[ -n "${2:-}" ]]; then
        info "$2"
    fi
    echo ""
    echo "  Pressione Enter para fechar."
    read -r </dev/tty 2>/dev/null || true
    exit 1
}

# Simple spinner for long operations
# Usage: long_command & spinner $! "Mensagem..."
spinner() {
    local pid=$1
    local msg="${2:-Aguarde...}"
    local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local i=0

    # Only show spinner if we have a terminal
    if [[ ! -t 1 ]]; then
        wait "$pid" 2>/dev/null
        return $?
    fi

    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${CYAN}%s${NC} %s" "${frames[$i]}" "$msg"
        i=$(( (i + 1) % ${#frames[@]} ))
        sleep 0.12
    done

    # Clear spinner line
    printf "\r\033[K"

    # Return the exit code of the background process
    wait "$pid" 2>/dev/null
    return $?
}

# ─── HELPERS ─────────────────────────────────────────

# Compare Python version correctly: (major > min) OR (major == min AND minor >= min)
# Returns 0 (true) if version is acceptable, 1 (false) otherwise
check_python_version() {
    local cmd="$1"

    # First verify the binary actually runs
    if ! "$cmd" -c "import sys; sys.exit(0)" 2>/dev/null; then
        return 1
    fi

    local ver
    ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null) || return 1

    # Validate output is actually X.Y format
    if [[ ! "$ver" =~ ^[0-9]+\.[0-9]+$ ]]; then
        return 1
    fi

    local major minor
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)

    # Correct version comparison: major > min OR (major == min AND minor >= min)
    if [[ "$major" -gt "$MIN_PYTHON_MAJOR" ]]; then
        return 0
    elif [[ "$major" -eq "$MIN_PYTHON_MAJOR" && "$minor" -ge "$MIN_PYTHON_MINOR" ]]; then
        return 0
    fi

    return 1
}

# Check if we have internet
check_internet() {
    # Try multiple endpoints in case one is down
    curl -sfSL --max-time 5 "https://github.com" -o /dev/null 2>/dev/null && return 0
    curl -sfSL --max-time 5 "https://raw.githubusercontent.com" -o /dev/null 2>/dev/null && return 0
    curl -sfSL --max-time 5 "https://brew.sh" -o /dev/null 2>/dev/null && return 0
    return 1
}

# Ensure we're on macOS and detect architecture
# Sets global: MACOS_ARCH
MACOS_ARCH=""

# ═══════════════════════════════════════════════════════
#  STEP FUNCTIONS
# ═══════════════════════════════════════════════════════

# ─── STEP 1: Check macOS + internet ─────────────────

step_preflight() {
    if [[ "$(uname)" != "Darwin" ]]; then
        die "Este instalador e para macOS." "Para Windows, use: INSTALAR.bat"
    fi

    MACOS_ARCH=$(uname -m)
    local macos_ver
    macos_ver=$(sw_vers -productVersion 2>/dev/null || echo "desconhecido")

    if [[ "$MACOS_ARCH" == "arm64" ]]; then
        ok "macOS $macos_ver — Apple Silicon (M1/M2/M3/M4)"
    else
        ok "macOS $macos_ver — Intel (x86_64)"
    fi

    # Internet check
    info "Verificando conexao com a internet..."
    if check_internet; then
        ok "Internet OK"
    else
        die "Sem conexao com a internet." "Conecta no Wi-Fi e roda o instalador de novo."
    fi
}

# ─── STEP 2: Homebrew ───────────────────────────────

step_homebrew() {
    # Check if already available
    if command -v brew &>/dev/null; then
        ok "Homebrew encontrado: $(brew --version 2>/dev/null | head -1)"
        return 0
    fi

    # Also check known paths in case it's installed but not in PATH
    local brew_bin=""
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        brew_bin="/opt/homebrew/bin/brew"
    elif [[ -f "/usr/local/bin/brew" ]]; then
        brew_bin="/usr/local/bin/brew"
    fi

    if [[ -n "$brew_bin" ]]; then
        eval "$("$brew_bin" shellenv)"
        if command -v brew &>/dev/null; then
            ok "Homebrew encontrado (PATH corrigido)"
            _persist_homebrew_path "$brew_bin"
            return 0
        fi
    fi

    # Install Homebrew
    warn "Homebrew nao encontrado — instalando..."
    info "Homebrew e o gerenciador de pacotes padrao do macOS"
    info "Pode pedir tua senha de administrador do Mac"
    echo ""

    # Download and install (NONINTERACTIVE skips "press return" prompt)
    NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" 2>&1
    local brew_exit=$?

    if [[ $brew_exit -ne 0 ]]; then
        die "Erro ao instalar Homebrew (exit code: $brew_exit)." "Tenta manualmente: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    fi

    # After install, add to PATH for this session
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        brew_bin="/opt/homebrew/bin/brew"
    elif [[ -f "/usr/local/bin/brew" ]]; then
        brew_bin="/usr/local/bin/brew"
    fi

    if [[ -n "$brew_bin" ]]; then
        eval "$("$brew_bin" shellenv)"
        _persist_homebrew_path "$brew_bin"
    fi

    if command -v brew &>/dev/null; then
        ok "Homebrew instalado com sucesso"
    else
        die "Homebrew instalou mas nao esta no PATH." "Fecha o terminal, abre de novo, e roda o instalador outra vez."
    fi
}

# Persist Homebrew path to shell profile for future sessions
_persist_homebrew_path() {
    local brew_bin="$1"

    # Determine shell profile (macOS default is zsh since Catalina)
    local shell_profile=""
    if [[ -f "$HOME/.zshrc" ]]; then
        shell_profile="$HOME/.zshrc"
    elif [[ -f "$HOME/.zprofile" ]]; then
        shell_profile="$HOME/.zprofile"
    elif [[ -f "$HOME/.bash_profile" ]]; then
        shell_profile="$HOME/.bash_profile"
    elif [[ -f "$HOME/.profile" ]]; then
        shell_profile="$HOME/.profile"
    else
        # Create .zprofile for fresh Macs (macOS default shell is zsh)
        shell_profile="$HOME/.zprofile"
        touch "$shell_profile" 2>/dev/null || return
    fi

    # Only add if not already present (check for brew shellenv specifically)
    if ! grep -q 'brew shellenv' "$shell_profile" 2>/dev/null; then
        {
            echo ''
            echo '# Homebrew (added by NEXUS installer)'
            echo "eval \"\$(${brew_bin} shellenv)\""
        } >> "$shell_profile"
        info "Homebrew adicionado ao $(basename "$shell_profile")"
    fi
}

# ─── STEP 3: Python ─────────────────────────────────

step_python() {
    PYTHON_CMD=""

    # Search for existing Python (prefer newer versions)
    for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$cmd" &>/dev/null; then
            if check_python_version "$cmd"; then
                PYTHON_CMD="$cmd"
                break
            fi
        fi
    done

    if [[ -n "$PYTHON_CMD" ]]; then
        ok "Python encontrado: $("$PYTHON_CMD" --version 2>&1)"
        return 0
    fi

    # Python not found — install via Homebrew
    warn "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ nao encontrado"
    info "Instalando Python 3.12 via Homebrew..."

    brew install python@3.12 2>&1
    local brew_exit=$?

    if [[ $brew_exit -ne 0 ]]; then
        die "Erro ao instalar Python via Homebrew (exit $brew_exit)." "Instala manualmente: https://python.org/downloads/"
    fi

    # Re-search after install — include Homebrew's direct paths in case
    # the shell hash table hasn't refreshed
    hash -r 2>/dev/null  # Force shell to re-scan PATH

    for cmd in python3.12 python3 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3 /usr/local/bin/python3.12 /usr/local/bin/python3; do
        if [[ -x "$cmd" ]] || command -v "$cmd" &>/dev/null; then
            if check_python_version "$cmd"; then
                PYTHON_CMD="$cmd"
                break
            fi
        fi
    done

    if [[ -n "$PYTHON_CMD" ]]; then
        ok "Python instalado: $("$PYTHON_CMD" --version 2>&1)"
    else
        die "Python instalou mas nao foi encontrado no PATH." "Fecha o terminal, abre de novo, e roda o instalador."
    fi
}

# ─── STEP 4: Git ────────────────────────────────────

step_git() {
    if command -v git &>/dev/null; then
        ok "Git encontrado: $(git --version 2>&1)"
        return 0
    fi

    warn "Git nao encontrado"

    # Try Homebrew first (faster, no GUI popup)
    if command -v brew &>/dev/null; then
        info "Instalando Git via Homebrew..."
        if brew install git 2>&1; then
            if command -v git &>/dev/null; then
                ok "Git instalado via Homebrew"
                return 0
            fi
        fi
    fi

    # Fallback: Xcode Command Line Tools (includes git)
    info "Instalando Xcode Command Line Tools (inclui Git)..."
    info "Uma janela pode aparecer — aceita e espera terminar."
    xcode-select --install 2>/dev/null || true

    # Wait for installation (poll every 5s, max 15 min)
    local waited=0
    local max_wait=900
    while [[ $waited -lt $max_wait ]]; do
        if command -v git &>/dev/null; then
            ok "Git instalado via Xcode Command Line Tools"
            return 0
        fi
        sleep 5
        waited=$((waited + 5))
        if [[ $((waited % 60)) -eq 0 ]]; then
            info "Ainda esperando Xcode CLT... (${waited}s / ${max_wait}s)"
        fi
    done

    die "Git nao foi instalado apos $(( max_wait / 60 )) minutos." "Instala manualmente: xcode-select --install"
}

# ─── STEP 5: Clone or update repo ───────────────────

step_download() {
    if [[ -d "$NEXUS_DIR/.git" ]]; then
        # Existing installation — update it
        if ! cd "$NEXUS_DIR" 2>/dev/null; then
            die "Nao conseguiu acessar $NEXUS_DIR." "Verifica permissoes da pasta."
        fi

        info "Atualizando NEXUS existente..."
        git pull --quiet 2>/dev/null || warn "Pull falhou (sem internet?), continuando com versao local..."
        ok "NEXUS atualizado"
    else
        # Fresh install — protect existing user data
        if [[ -d "$NEXUS_DIR" ]]; then
            # Backup user data if it exists
            if [[ -d "$NEXUS_DIR/data" ]] || [[ -d "$NEXUS_DIR/skills" ]] || [[ -f "$NEXUS_DIR/config/settings.yaml" ]]; then
                local backup_dir="$HOME/NEXUS_backup_$(date +%Y%m%d_%H%M%S)"
                warn "Pasta NEXUS existe sem git — fazendo backup..."
                mkdir -p "$backup_dir"
                cp -r "$NEXUS_DIR/data" "$backup_dir/" 2>/dev/null || true
                cp -r "$NEXUS_DIR/skills" "$backup_dir/" 2>/dev/null || true
                cp "$NEXUS_DIR/config/settings.yaml" "$backup_dir/" 2>/dev/null || true
                info "Backup salvo em: $backup_dir"
            fi
            rm -rf "$NEXUS_DIR"
        fi

        info "Clonando repositorio..."
        if ! git clone "$NEXUS_REPO" "$NEXUS_DIR" --quiet 2>&1; then
            die "Erro ao clonar repositorio." "Verifica tua internet e tenta de novo."
        fi

        # Validate clone has required files
        if [[ ! -f "$NEXUS_DIR/pyproject.toml" ]]; then
            die "Repositorio clonado parece incompleto." "Deleta ~/NEXUS e roda o instalador de novo."
        fi

        ok "NEXUS baixado em $NEXUS_DIR"
    fi

    if ! cd "$NEXUS_DIR" 2>/dev/null; then
        die "Nao conseguiu acessar $NEXUS_DIR." "Verifica permissoes da pasta."
    fi
}

# ─── STEP 6: Install dependencies ───────────────────

step_deps() {
    local VENV_DIR="$NEXUS_DIR/.venv"

    # ── Create virtual environment ──
    # Python 3.12+ via Homebrew is "externally managed" (PEP 668).
    # pip install outside a venv is BLOCKED by design.
    # A venv is the ONLY correct approach — not --break-system-packages.
    info "Criando ambiente virtual Python..."

    if [[ -d "$VENV_DIR" ]]; then
        # Existing venv — recreate cleanly to avoid stale packages
        "$PYTHON_CMD" -m venv --clear "$VENV_DIR" 2>&1 || {
            warn "Recriacao do venv falhou, removendo e tentando de novo..."
            rm -rf "$VENV_DIR"
            "$PYTHON_CMD" -m venv "$VENV_DIR" 2>&1
        }
    else
        "$PYTHON_CMD" -m venv "$VENV_DIR" 2>&1
    fi

    # Validate venv was created and works
    if [[ ! -f "$VENV_DIR/bin/python" ]]; then
        die "Falha ao criar ambiente virtual." \
            "Tenta manualmente: $PYTHON_CMD -m venv $VENV_DIR"
    fi

    # Switch ALL subsequent operations to the venv Python/pip
    PYTHON_CMD="$VENV_DIR/bin/python"
    local PIP_CMD="$VENV_DIR/bin/pip"

    if ! "$PYTHON_CMD" -c "import sys; sys.exit(0)" 2>/dev/null; then
        die "Python do ambiente virtual nao funciona." \
            "Deleta $VENV_DIR e roda o instalador de novo."
    fi

    ok "Ambiente virtual criado"

    # ── Install dependencies ──
    info "Instalando dependencias (pode demorar 2-3 min)..."

    # Upgrade pip inside venv (safe — no PEP 668 here)
    "$PIP_CMD" install --upgrade pip --quiet 2>/dev/null || warn "Upgrade do pip falhou (continuando...)"

    # Install from pyproject.toml
    local pip_ok=false
    local pip_output=""

    pip_output=$("$PIP_CMD" install -e . --quiet 2>&1) && pip_ok=true

    if [[ "$pip_ok" != "true" ]]; then
        warn "Modo editavel falhou, tentando instalacao normal..."
        pip_output=$("$PIP_CMD" install . --quiet 2>&1) && pip_ok=true
    fi

    if [[ "$pip_ok" != "true" ]]; then
        fail "Instalacao das dependencias falhou."
        echo ""
        echo "  ─── pip output ───"
        echo "$pip_output" | tail -20 | sed 's/^/  /'
        echo "  ──────────────────"
        echo ""
        die "Erro no pip install." "Tenta manualmente: cd $NEXUS_DIR && $PIP_CMD install -e ."
    fi

    # macOS-specific extras (inside venv — no PEP 668 issue)
    "$PIP_CMD" install mss --quiet 2>/dev/null || warn "mss (screen capture) falhou"

    if "$PIP_CMD" install pyobjc-framework-Quartz --quiet 2>/dev/null; then
        ok "Dependencias instaladas (com captura nativa macOS)"
    else
        ok "Dependencias instaladas (captura via mss)"
    fi

    # Verify core imports work inside the venv
    if ! "$PYTHON_CMD" -c "import mss" 2>/dev/null; then
        warn "Modulo mss nao importou corretamente — captura de tela pode falhar"
    fi
}

# ─── STEP 7: Create config and directories ──────────

step_config() {
    mkdir -p "$NEXUS_DIR/data" 2>/dev/null || true
    mkdir -p "$NEXUS_DIR/skills" 2>/dev/null || true

    if [[ ! -f "$NEXUS_DIR/config/settings.yaml" ]]; then
        if [[ -f "$NEXUS_DIR/config/settings.yaml.example" ]]; then
            mkdir -p "$NEXUS_DIR/config" 2>/dev/null || true
            if cp "$NEXUS_DIR/config/settings.yaml.example" "$NEXUS_DIR/config/settings.yaml" 2>/dev/null; then
                # Patch config for macOS: change backend from dxcam to mss
                if command -v sed &>/dev/null; then
                    sed -i '' 's/backend: "dxcam"/backend: "mss"/' "$NEXUS_DIR/config/settings.yaml" 2>/dev/null || true
                fi
                ok "Config criado — edita config/settings.yaml com teus hotkeys"
            else
                warn "Nao conseguiu criar config (permissao?)"
            fi
        else
            warn "settings.yaml.example nao encontrado no repositorio"
        fi
    else
        ok "Config ja existe (mantendo o teu)"
    fi
}

# ─── STEP 8: Create launcher shortcuts ──────────────

step_shortcuts() {
    local venv_dir="$NEXUS_DIR/.venv"

    # Create INICIAR_MAC.command in NEXUS directory
    # CRITICAL: Must activate the venv before running NEXUS.
    # Without this, Python won't find any installed packages.
    cat > "$NEXUS_DIR/INICIAR_MAC.command" << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo ""
echo -e "  \033[0;36mIniciando NEXUS...\033[0m"
echo -e "  \033[2mAbre o Tibia e loga no teu personagem antes!\033[0m"
echo ""

NEXUS_DIR="$(pwd)"
VENV_DIR="$NEXUS_DIR/.venv"

# Activate virtual environment
if [[ -f "$VENV_DIR/bin/activate" ]]; then
    source "$VENV_DIR/bin/activate"
else
    echo "  ERRO: Ambiente virtual nao encontrado em $VENV_DIR"
    echo "  Roda o instalador de novo: bash scripts/install_macos.sh"
    echo ""
    echo "  Pressione Enter para fechar."
    read -r </dev/tty 2>/dev/null || true
    exit 1
fi

PYTHON="$VENV_DIR/bin/python"

if [[ -x "$VENV_DIR/bin/nexus" ]]; then
    "$VENV_DIR/bin/nexus" start
elif "$PYTHON" -m nexus_cli start 2>/dev/null; then
    true
elif [[ -f launcher.py ]]; then
    "$PYTHON" launcher.py
else
    echo "  ERRO: Nao encontrou o NEXUS. Roda o instalador de novo."
fi

echo ""
echo "  NEXUS encerrado. Pressione Enter para fechar."
read -r </dev/tty 2>/dev/null || true
LAUNCHER_EOF
    chmod +x "$NEXUS_DIR/INICIAR_MAC.command"
    xattr -d com.apple.quarantine "$NEXUS_DIR/INICIAR_MAC.command" 2>/dev/null || true

    # Desktop shortcut
    local desktop="$HOME/Desktop"
    if [[ -d "$desktop" ]]; then
        cat > "$desktop/NEXUS Agent.command" << DESKTOP_EOF
#!/bin/bash
cd "${NEXUS_DIR}" || exit 1
exec bash "${NEXUS_DIR}/INICIAR_MAC.command"
DESKTOP_EOF
        chmod +x "$desktop/NEXUS Agent.command"
        xattr -d com.apple.quarantine "$desktop/NEXUS Agent.command" 2>/dev/null || true
        ok "Atalho criado na Area de Trabalho"
    else
        info "Pasta Desktop nao encontrada — cria o atalho manualmente"
    fi
}

# ─── STEP 9: Post-install verification ──────────────

step_verify() {
    local errors=0

    # Check venv exists
    if [[ ! -d "$NEXUS_DIR/.venv/bin" ]]; then
        fail "Ambiente virtual nao encontrado em .venv/"
        errors=$((errors + 1))
    fi

    # Check Python (should be the venv python by this point)
    if ! "$PYTHON_CMD" -c "import sys; sys.exit(0)" 2>/dev/null; then
        fail "Python ($PYTHON_CMD) nao funciona"
        errors=$((errors + 1))
    fi

    # Check critical files exist
    for f in pyproject.toml launcher.py config/settings.yaml; do
        if [[ ! -f "$NEXUS_DIR/$f" ]]; then
            fail "Arquivo faltando: $f"
            errors=$((errors + 1))
        fi
    done

    # Check core imports inside venv
    if ! "$PYTHON_CMD" -c "import mss" 2>/dev/null; then
        warn "mss nao importa — captura de tela pode nao funcionar"
    fi

    if ! "$PYTHON_CMD" -c "import structlog, yaml, click" 2>/dev/null; then
        fail "Dependencias core nao importam (structlog/yaml/click)"
        errors=$((errors + 1))
    fi

    # Check launcher exists and is executable
    if [[ ! -x "$NEXUS_DIR/INICIAR_MAC.command" ]]; then
        fail "Launcher nao e executavel"
        errors=$((errors + 1))
    fi

    if [[ $errors -gt 0 ]]; then
        warn "Instalacao completa com $errors problema(s) — pode nao funcionar 100%"
        return 1
    else
        ok "Tudo verificado — instalacao limpa"
        return 0
    fi
}

# ─── macOS Permissions Guide ────────────────────────

show_permissions_guide() {
    echo ""
    echo -e "  ${YELLOW}╔═══════════════════════════════════════════════╗${NC}"
    echo -e "  ${YELLOW}║       PERMISSOES IMPORTANTES DO macOS         ║${NC}"
    echo -e "  ${YELLOW}╚═══════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}O NEXUS precisa de 2 permissoes no macOS:${NC}"
    echo ""
    echo -e "  ${CYAN}1. Gravacao de Tela (Screen Recording)${NC}"
    echo -e "     ${DIM}Para capturar a tela do jogo${NC}"
    echo -e "     Ajustes do Sistema > Privacidade e Seguranca"
    echo -e "     > Gravacao de Tela > Adiciona o Terminal"
    echo ""
    echo -e "  ${CYAN}2. Acessibilidade (Accessibility)${NC}"
    echo -e "     ${DIM}Para controlar teclado e mouse${NC}"
    echo -e "     Ajustes do Sistema > Privacidade e Seguranca"
    echo -e "     > Acessibilidade > Adiciona o Terminal"
    echo ""
    echo -e "  ${DIM}Se usar iTerm2, Warp, ou outro terminal, adiciona ele${NC}"
    echo -e "  ${DIM}ao inves do Terminal padrao do macOS.${NC}"
    echo ""

    # Offer to open System Preferences
    info "Quer abrir as Configuracoes de Privacidade agora? (s/n)"
    local response=""
    if read -r -n 1 response </dev/tty 2>/dev/null; then
        echo ""
        if [[ "$response" == "s" || "$response" == "S" || "$response" == "y" || "$response" == "Y" ]]; then
            open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture" 2>/dev/null || \
            open "x-apple.systempreferences:com.apple.preference.security" 2>/dev/null || true
            info "Janela de Configuracoes aberta"
        fi
    else
        echo ""
    fi
}

# ═══════════════════════════════════════════════════════
#  BANNER
# ═══════════════════════════════════════════════════════

banner() {
    echo ""
    echo -e "${CYAN}    ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗${NC}"
    echo -e "${CYAN}    ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝${NC}"
    echo -e "${CYAN}    ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗${NC}"
    echo -e "${CYAN}    ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║${NC}"
    echo -e "${CYAN}    ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║${NC}"
    echo -e "${CYAN}    ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝╚══════╝${NC}"
    echo ""
    echo -e "    ${DIM}Instalador Automatico v${NEXUS_VERSION} — macOS${NC}"
    echo -e "    ${DIM}─────────────────────────────────────────────${NC}"
    echo ""
}

# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════

main() {
    INSTALL_START_TIME=$(date +%s)

    banner

    echo -e "  ${BOLD}[1/8] Pre-flight check...${NC}"
    step_preflight
    echo ""

    echo -e "  ${BOLD}[2/8] Homebrew...${NC}"
    step_homebrew
    echo ""

    echo -e "  ${BOLD}[3/8] Python...${NC}"
    step_python
    echo ""

    echo -e "  ${BOLD}[4/8] Git...${NC}"
    step_git
    echo ""

    echo -e "  ${BOLD}[5/8] Baixando NEXUS...${NC}"
    step_download
    echo ""

    echo -e "  ${BOLD}[6/8] Ambiente virtual + dependencias...${NC}"
    step_deps
    echo ""

    echo -e "  ${BOLD}[7/8] Configurando...${NC}"
    step_config
    step_shortcuts
    echo ""

    echo -e "  ${BOLD}[8/8] Verificando instalacao...${NC}"
    step_verify
    echo ""

    # Calculate elapsed time
    local elapsed=""
    if [[ -n "$INSTALL_START_TIME" ]]; then
        local end_time
        end_time=$(date +%s)
        local secs=$(( end_time - INSTALL_START_TIME ))
        if [[ $secs -ge 60 ]]; then
            elapsed="$(( secs / 60 ))min $(( secs % 60 ))s"
        else
            elapsed="${secs}s"
        fi
    fi

    echo -e "  ${GREEN}═══════════════════════════════════════════${NC}"
    echo -e "  ${GREEN}✓ INSTALACAO COMPLETA!${NC}${elapsed:+ ${DIM}(${elapsed})${NC}}"
    echo -e "  ${GREEN}═══════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Arquivos em: ${CYAN}$NEXUS_DIR${NC}"
    echo -e "  Ambiente:    ${CYAN}$NEXUS_DIR/.venv${NC}"
    echo ""
    echo -e "  ${BOLD}COMO USAR:${NC}"
    echo -e "  1. Edita ${CYAN}config/settings.yaml${NC} com teu personagem e hotkeys"
    echo -e "  2. Abre o Tibia e loga"
    echo -e "  3. Double-click em ${CYAN}\"NEXUS Agent\"${NC} na Area de Trabalho"
    echo -e "     (ou no terminal: ${CYAN}cd ~/NEXUS && source .venv/bin/activate && nexus start${NC})"
    echo ""
    echo -e "  ${BOLD}IA ESTRATEGICA (opcional):${NC}"
    echo -e "  ${CYAN}export ANTHROPIC_API_KEY=\"sua_chave\"${NC}"
    echo -e "  ${DIM}Sem isso, o bot funciona normal — so sem a IA avancada${NC}"
    echo ""

    show_permissions_guide

    echo ""
    info "Pressione Enter para fechar."
    read -r </dev/tty 2>/dev/null || true
}

main "$@"
