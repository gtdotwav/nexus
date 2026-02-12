#!/bin/bash
# ═══════════════════════════════════════════════════════
#  NEXUS — macOS Installer v0.5.0
#
#  Installs NEXUS on macOS (Intel + Apple Silicon).
#  Handles: Python, Homebrew, dependencies, config,
#           permissions guidance, desktop shortcut.
#
#  Usage:
#    bash scripts/install_macos.sh
#    -- or double-click INSTALAR_MAC.command --
#
#  One-liner (bypasses Gatekeeper):
#    bash <(curl -fsSL https://raw.githubusercontent.com/gtdotwav/nexus/main/scripts/install_macos.sh)
# ═══════════════════════════════════════════════════════

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

NEXUS_VERSION="0.5.0"
NEXUS_DIR="$HOME/NEXUS"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10

# Global: set by find_python()
PYTHON_CMD=""

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

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

die() {
    fail "$1"
    echo ""
    echo "  Pressione Enter para fechar."
    read -r </dev/tty 2>/dev/null || true
    exit 1
}

# ─── STEP 1: Check macOS ─────────────────────────────

check_macos() {
    if [[ "$(uname)" != "Darwin" ]]; then
        die "Este instalador e para macOS. Para Windows, use: INSTALAR.bat"
    fi

    local arch
    arch=$(uname -m)
    if [[ "$arch" == "arm64" ]]; then
        ok "macOS Apple Silicon (M1/M2/M3) detectado"
    else
        ok "macOS Intel (x86_64) detectado"
    fi
}

# ─── STEP 2: Install Homebrew if needed ──────────────
# Homebrew is the standard macOS package manager.
# On Apple Silicon it installs to /opt/homebrew, on Intel to /usr/local.

install_homebrew() {
    if command -v brew &> /dev/null; then
        return 0  # already installed
    fi

    warn "Homebrew nao encontrado — instalando automaticamente..."
    info "Homebrew e o gerenciador de pacotes padrao do macOS"
    info "Ele vai pedir tua senha de administrador do Mac"
    echo ""

    # Install Homebrew (non-interactive via NONINTERACTIVE env)
    if NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" 2>&1; then
        # After install, Homebrew may not be in PATH yet (especially Apple Silicon)
        # Apple Silicon: /opt/homebrew/bin
        # Intel: /usr/local/bin (usually already in PATH)
        if [[ -f "/opt/homebrew/bin/brew" ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
            # Also add to shell profile so it persists
            local shell_profile=""
            if [[ -f "$HOME/.zshrc" ]]; then
                shell_profile="$HOME/.zshrc"
            elif [[ -f "$HOME/.bash_profile" ]]; then
                shell_profile="$HOME/.bash_profile"
            elif [[ -f "$HOME/.profile" ]]; then
                shell_profile="$HOME/.profile"
            fi
            if [[ -n "$shell_profile" ]]; then
                if ! grep -q "homebrew" "$shell_profile" 2>/dev/null; then
                    echo '' >> "$shell_profile"
                    echo '# Homebrew (added by NEXUS installer)' >> "$shell_profile"
                    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$shell_profile"
                    info "Homebrew adicionado ao $shell_profile"
                fi
            fi
        elif [[ -f "/usr/local/bin/brew" ]]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi

        if command -v brew &> /dev/null; then
            ok "Homebrew instalado com sucesso"
            return 0
        else
            fail "Homebrew instalou mas nao esta no PATH"
            info "Fecha o terminal, abre de novo, e roda o instalador outra vez"
            return 1
        fi
    else
        fail "Erro ao instalar Homebrew"
        info "Tenta instalar manualmente:"
        echo '    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        return 1
    fi
}

# ─── STEP 3: Find or install Python ──────────────────
# Sets global PYTHON_CMD (avoids stdout capture bug)

find_python() {
    PYTHON_CMD=""

    # 1) Check if a suitable Python already exists
    for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$cmd" &> /dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
            local major minor
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [[ "$major" -ge "$MIN_PYTHON_MAJOR" && "$minor" -ge "$MIN_PYTHON_MINOR" ]]; then
                PYTHON_CMD="$cmd"
                break
            fi
        fi
    done

    if [[ -n "$PYTHON_CMD" ]]; then
        local full_ver
        full_ver=$("$PYTHON_CMD" --version 2>&1)
        ok "Python encontrado: $full_ver"
        return 0
    fi

    # 2) Python not found — install via Homebrew (installing Homebrew first if needed)
    warn "Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ nao encontrado"
    echo ""

    # Ensure Homebrew is available
    if ! install_homebrew; then
        die "Nao foi possivel instalar o Homebrew. Instala Python manualmente: https://python.org/downloads/"
    fi

    # Install Python via Homebrew
    info "Instalando Python 3.12 via Homebrew (pode demorar 1-2 min)..."
    if brew install python@3.12 2>&1; then
        # Homebrew may install python3.12 or just update python3
        for cmd in python3.12 python3; do
            if command -v "$cmd" &> /dev/null; then
                local ver
                ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
                local major minor
                major=$(echo "$ver" | cut -d. -f1)
                minor=$(echo "$ver" | cut -d. -f2)
                if [[ "$major" -ge "$MIN_PYTHON_MAJOR" && "$minor" -ge "$MIN_PYTHON_MINOR" ]]; then
                    PYTHON_CMD="$cmd"
                    break
                fi
            fi
        done

        if [[ -n "$PYTHON_CMD" ]]; then
            ok "Python instalado: $("$PYTHON_CMD" --version 2>&1)"
            return 0
        else
            die "Python instalou mas nao foi encontrado no PATH. Fecha o terminal, abre de novo, e roda o instalador."
        fi
    else
        die "Erro ao instalar Python via Homebrew. Instala manualmente: https://python.org/downloads/"
    fi
}

# ─── STEP 4: Check Git ───────────────────────────────

check_git() {
    if command -v git &> /dev/null; then
        ok "Git encontrado"
        return 0
    fi

    warn "Git nao encontrado"

    # Try Homebrew first (faster, no GUI popup)
    if command -v brew &> /dev/null; then
        info "Instalando Git via Homebrew..."
        if brew install git 2>&1; then
            ok "Git instalado via Homebrew"
            return 0
        fi
    fi

    # Fallback: Xcode Command Line Tools (includes git)
    info "Instalando Xcode Command Line Tools (inclui Git)..."
    info "Uma janela pode aparecer pedindo pra instalar — aceita e espera."
    xcode-select --install 2>/dev/null || true

    # Wait for installation to complete (polls every 5s, max 10 min)
    info "Esperando instalacao terminar..."
    local waited=0
    while [[ $waited -lt 600 ]]; do
        if command -v git &> /dev/null; then
            ok "Git instalado via Xcode Command Line Tools"
            return 0
        fi
        sleep 5
        waited=$((waited + 5))
        # Show progress every 30s
        if [[ $((waited % 30)) -eq 0 ]]; then
            info "Ainda instalando... ($waited s)"
        fi
    done

    # Last chance check
    if command -v git &> /dev/null; then
        ok "Git instalado"
        return 0
    fi

    die "Git nao foi instalado apos 10 min. Instala manualmente: xcode-select --install"
}

# ─── STEP 5: Clone or update repo ────────────────────

clone_or_update() {
    if [[ -d "$NEXUS_DIR/.git" ]]; then
        info "Atualizando NEXUS existente..."
        cd "$NEXUS_DIR"
        git pull --quiet 2>/dev/null || warn "Pull falhou (sem internet?), continuando..."
        ok "NEXUS atualizado"
    else
        if [[ -d "$NEXUS_DIR" ]]; then
            info "Pasta NEXUS existe sem git, removendo..."
            rm -rf "$NEXUS_DIR"
        fi
        info "Clonando repositorio..."
        if ! git clone https://github.com/gtdotwav/nexus.git "$NEXUS_DIR" --quiet 2>&1; then
            die "Erro ao clonar. Verifica tua internet."
        fi
        ok "NEXUS baixado em $NEXUS_DIR"
    fi

    cd "$NEXUS_DIR"
}

# ─── STEP 6: Install dependencies ────────────────────

install_deps() {
    info "Instalando dependencias (pode demorar 1-2 min)..."

    # Upgrade pip
    "$PYTHON_CMD" -m pip install --upgrade pip --quiet 2>/dev/null || true

    # Install from pyproject.toml (editable mode)
    if ! "$PYTHON_CMD" -m pip install -e . --quiet 2>/dev/null; then
        warn "Modo editavel falhou, tentando normal..."
        "$PYTHON_CMD" -m pip install . --quiet 2>/dev/null || warn "pip install falhou"
    fi

    # macOS-specific: mss for screen capture (cross-platform)
    "$PYTHON_CMD" -m pip install mss --quiet 2>/dev/null || true

    # macOS-specific: pyobjc for native window management (optional)
    if "$PYTHON_CMD" -m pip install pyobjc-framework-Quartz --quiet 2>/dev/null; then
        ok "Dependencias instaladas (com captura nativa macOS)"
    else
        ok "Dependencias instaladas (captura via mss)"
    fi
}

# ─── STEP 7a: Create config and directories ──────────

setup_config() {
    # Create data directory
    mkdir -p "$NEXUS_DIR/data"
    mkdir -p "$NEXUS_DIR/skills"

    # Create config if doesn't exist
    if [[ ! -f "$NEXUS_DIR/config/settings.yaml" ]]; then
        if [[ -f "$NEXUS_DIR/config/settings.yaml.example" ]]; then
            cp "$NEXUS_DIR/config/settings.yaml.example" "$NEXUS_DIR/config/settings.yaml"

            # Patch config for macOS: change backend from dxcam to mss
            sed -i '' 's/backend: "dxcam"/backend: "mss"/' "$NEXUS_DIR/config/settings.yaml" 2>/dev/null || true

            ok "Config criado (edite config/settings.yaml com seus hotkeys)"
        fi
    else
        ok "Config ja existe"
    fi
}

# ─── STEP 7b: Create launcher shortcut ───────────────

create_shortcuts() {
    # Create INICIAR_MAC.command in NEXUS directory
    cat > "$NEXUS_DIR/INICIAR_MAC.command" << 'SCRIPT'
#!/bin/bash
cd "$(dirname "$0")"
echo ""
echo "  Iniciando NEXUS..."
echo "  Abre o Tibia e loga no seu personagem antes!"
echo ""

# Try nexus CLI first, fallback to module
if command -v nexus &> /dev/null; then
    nexus start
else
    python3 -m nexus_cli start 2>/dev/null || python3 launcher.py
fi

echo ""
echo "  NEXUS encerrado. Pressione Enter para fechar."
read -r
SCRIPT
    chmod +x "$NEXUS_DIR/INICIAR_MAC.command"
    xattr -d com.apple.quarantine "$NEXUS_DIR/INICIAR_MAC.command" 2>/dev/null || true

    # Create Desktop shortcut
    local desktop="$HOME/Desktop"
    if [[ -d "$desktop" ]]; then
        cat > "$desktop/NEXUS Agent.command" << SCRIPT
#!/bin/bash
cd "$NEXUS_DIR"
bash "$NEXUS_DIR/INICIAR_MAC.command"
SCRIPT
        chmod +x "$desktop/NEXUS Agent.command"
        xattr -d com.apple.quarantine "$desktop/NEXUS Agent.command" 2>/dev/null || true
        ok "Atalho criado na Area de Trabalho"
    fi
}

# ─── STEP 7: macOS Permissions Guide ─────────────────

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
    echo -e "     Vai em: Ajustes do Sistema → Privacidade e Seguranca"
    echo -e "             → Gravacao de Tela → Adiciona o Terminal"
    echo ""
    echo -e "  ${CYAN}2. Acessibilidade (Accessibility)${NC}"
    echo -e "     ${DIM}Para controlar teclado e mouse${NC}"
    echo -e "     Vai em: Ajustes do Sistema → Privacidade e Seguranca"
    echo -e "             → Acessibilidade → Adiciona o Terminal"
    echo ""
    echo -e "  ${DIM}Se usar iTerm2, Warp, ou outro terminal, adiciona ele ao inves${NC}"
    echo -e "  ${DIM}do Terminal padrao do macOS.${NC}"
    echo ""

    # Try to open System Preferences (read from /dev/tty for curl compatibility)
    info "Quer abrir as Configuracoes de Privacidade agora? (s/n)"
    if read -r -n 1 response </dev/tty 2>/dev/null; then
        echo ""
        if [[ "$response" == "s" || "$response" == "S" ]]; then
            open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture" 2>/dev/null || \
            open "x-apple.systempreferences:com.apple.preference.security" 2>/dev/null || true
            info "Janela de Configuracoes aberta"
        fi
    else
        echo ""
    fi
}

# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════

main() {
    banner

    echo -e "  ${BOLD}[1/7] Verificando macOS...${NC}"
    check_macos
    echo ""

    echo -e "  ${BOLD}[2/7] Verificando Homebrew...${NC}"
    if command -v brew &> /dev/null; then
        ok "Homebrew encontrado"
    else
        install_homebrew || die "Homebrew necessario. Instala manualmente e roda de novo."
    fi
    echo ""

    echo -e "  ${BOLD}[3/7] Verificando Python...${NC}"
    find_python
    echo ""

    echo -e "  ${BOLD}[4/7] Verificando Git...${NC}"
    check_git
    echo ""

    echo -e "  ${BOLD}[5/7] Baixando NEXUS...${NC}"
    clone_or_update
    echo ""

    echo -e "  ${BOLD}[6/7] Instalando dependencias...${NC}"
    install_deps
    echo ""

    echo -e "  ${BOLD}[7/7] Configurando...${NC}"
    setup_config
    create_shortcuts
    echo ""

    echo -e "  ${GREEN}═══════════════════════════════════════════${NC}"
    echo -e "  ${GREEN}✓ INSTALACAO COMPLETA!${NC}"
    echo -e "  ${GREEN}═══════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Arquivos em: ${CYAN}$NEXUS_DIR${NC}"
    echo ""
    echo -e "  ${BOLD}COMO USAR:${NC}"
    echo -e "  ──────────"
    echo -e "  1. Edita ${CYAN}config/settings.yaml${NC} com seu personagem e hotkeys"
    echo -e "  2. Abre o Tibia e loga"
    echo -e "  3. Double-click em ${CYAN}\"NEXUS Agent\"${NC} na Area de Trabalho"
    echo -e "     (ou roda ${CYAN}nexus start${NC} no terminal)"
    echo ""
    echo -e "  ${BOLD}OPCIONAL (IA estrategica):${NC}"
    echo -e "  ──────────────────────────"
    echo -e "  Se quiser o cerebro estrategico (Claude pensando junto):"
    echo -e "  ${CYAN}export ANTHROPIC_API_KEY=\"sua_chave_aqui\"${NC}"
    echo -e "  Sem isso, o bot funciona normal (so sem a parte de IA avancada)"
    echo ""

    show_permissions_guide

    echo ""
    info "Pressione Enter para fechar."
    read -r </dev/tty 2>/dev/null || true
}

main "$@"
