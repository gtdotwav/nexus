#!/bin/bash
# ═══════════════════════════════════════════════════════
#  NEXUS — macOS Installer
#
#  Installs NEXUS on macOS (Intel + Apple Silicon).
#  Handles: Python, dependencies, config, shortcuts.
#
#  Usage:
#    curl -fsSL https://nexus-agent.github.io/install.sh | bash
#    -- or --
#    bash scripts/install_macos.sh
# ═══════════════════════════════════════════════════════

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

NEXUS_HOME="$HOME/.nexus"
NEXUS_VERSION="0.1.0"
MIN_PYTHON_VERSION="3.11"

banner() {
    echo -e "${CYAN}"
    echo "    ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗"
    echo "    ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝"
    echo "    ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗"
    echo "    ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║"
    echo "    ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║"
    echo "    ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝╚══════╝"
    echo -e "${NC}"
    echo -e "    ${DIM}Autonomous Gaming Agent v${NEXUS_VERSION}${NC}"
    echo -e "    ${DIM}macOS Installer${NC}"
    echo ""
}

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

# ─── Check macOS ──────────────────────────────────────

check_macos() {
    if [[ "$(uname)" != "Darwin" ]]; then
        fail "This installer is for macOS only."
        echo "  For Windows, use: scripts/install_windows.ps1"
        exit 1
    fi

    local arch
    arch=$(uname -m)
    if [[ "$arch" == "arm64" ]]; then
        ok "macOS Apple Silicon (arm64) detected"
    else
        ok "macOS Intel (x86_64) detected"
    fi
}

# ─── Check/Install Python ────────────────────────────

check_python() {
    local python_cmd=""

    # Check python3.11+ specifically
    for cmd in python3.13 python3.12 python3.11 python3; do
        if command -v "$cmd" &> /dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
            local major minor
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [[ "$major" -ge 3 && "$minor" -ge 11 ]]; then
                python_cmd="$cmd"
                break
            fi
        fi
    done

    if [[ -n "$python_cmd" ]]; then
        local full_ver
        full_ver=$("$python_cmd" --version 2>&1)
        ok "Python found: $full_ver ($python_cmd)"
        echo "$python_cmd"
        return 0
    fi

    # Python not found — offer to install
    warn "Python $MIN_PYTHON_VERSION+ not found"

    if command -v brew &> /dev/null; then
        info "Installing Python via Homebrew..."
        brew install python@3.12
        python_cmd="python3.12"
        ok "Python installed: $("$python_cmd" --version)"
        echo "$python_cmd"
        return 0
    else
        fail "Homebrew not found. Please install Python $MIN_PYTHON_VERSION+ manually:"
        echo "    https://python.org/downloads/"
        echo "  Or install Homebrew first:"
        echo "    /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
}

# ─── Create Virtual Environment ──────────────────────

setup_venv() {
    local python_cmd="$1"

    mkdir -p "$NEXUS_HOME"

    if [[ ! -d "$NEXUS_HOME/venv" ]]; then
        info "Creating virtual environment..."
        "$python_cmd" -m venv "$NEXUS_HOME/venv"
        ok "Virtual environment created"
    else
        ok "Virtual environment exists"
    fi

    # Activate
    source "$NEXUS_HOME/venv/bin/activate"
    ok "Virtual environment activated"
}

# ─── Install Dependencies ────────────────────────────

install_deps() {
    info "Installing dependencies..."

    # Upgrade pip
    pip install --upgrade pip --quiet 2>/dev/null

    # Determine if we're in the repo or installing from scratch
    local repo_dir
    repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

    if [[ -f "$repo_dir/pyproject.toml" ]]; then
        # Install from local repo
        pip install -e "$repo_dir" --quiet 2>/dev/null
        ok "NEXUS installed from local source"
    else
        # Install core dependencies manually
        pip install \
            opencv-python numpy Pillow pynput \
            anthropic pyyaml structlog rich \
            aiohttp click \
            --quiet 2>/dev/null
        ok "Core dependencies installed"
    fi

    # macOS-specific: screenshot library
    pip install pyobjc-framework-Quartz --quiet 2>/dev/null || true
    ok "macOS screen capture support installed"
}

# ─── Create Config ───────────────────────────────────

create_config() {
    local config_file="$NEXUS_HOME/config.yaml"

    if [[ -f "$config_file" ]]; then
        ok "Config already exists: $config_file"
        return
    fi

    info "Creating default config..."

    cat > "$config_file" << 'YAML'
# NEXUS Configuration — macOS
# Edit this file to customize your agent.

agent:
  game: tibia
  character_name: YourCharacter
  server: YourServer

perception:
  capture:
    method: screenshot  # macOS uses screenshot method
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
YAML

    ok "Config created: $config_file"
}

# ─── Create Shell Command ────────────────────────────

create_command() {
    local bin_dir="$NEXUS_HOME/venv/bin"
    local nexus_cmd="$bin_dir/nexus"

    # The nexus command should already exist from pip install
    if [[ -f "$nexus_cmd" ]]; then
        ok "nexus command available in venv"
    fi

    # Create a convenience symlink in /usr/local/bin
    local global_cmd="/usr/local/bin/nexus"
    if [[ ! -f "$global_cmd" ]] && [[ -w "/usr/local/bin" ]]; then
        cat > "$global_cmd" << SCRIPT
#!/bin/bash
source "$NEXUS_HOME/venv/bin/activate"
exec python -m nexus_cli "\$@"
SCRIPT
        chmod +x "$global_cmd"
        ok "Global command created: nexus"
    elif [[ -f "$global_cmd" ]]; then
        ok "Global nexus command exists"
    else
        warn "Could not create global command (no write access to /usr/local/bin)"
        info "You can use: source ~/.nexus/venv/bin/activate && nexus"
    fi
}

# ─── Create Desktop Shortcut ────────────────────────

create_shortcut() {
    local app_dir="$HOME/Desktop/NEXUS.command"

    cat > "$app_dir" << SCRIPT
#!/bin/bash
cd "$NEXUS_HOME"
source "$NEXUS_HOME/venv/bin/activate"
python -m nexus_cli start --dashboard
SCRIPT
    chmod +x "$app_dir"
    ok "Desktop shortcut created: NEXUS.command"
}

# ─── macOS Permissions ───────────────────────────────

check_permissions() {
    info "Checking macOS permissions..."

    # Screen recording permission (needed for screen capture)
    echo ""
    warn "NEXUS needs Screen Recording permission to capture the game."
    info "Go to: System Settings → Privacy & Security → Screen Recording"
    info "Add your Terminal app (or iTerm2, etc.) to the list."
    echo ""

    # Accessibility permission (needed for keyboard/mouse control)
    warn "NEXUS needs Accessibility permission for keyboard/mouse control."
    info "Go to: System Settings → Privacy & Security → Accessibility"
    info "Add your Terminal app to the list."
    echo ""
}

# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════

main() {
    banner

    echo -e "${BOLD}Checking system...${NC}\n"
    check_macos

    echo ""
    echo -e "${BOLD}Setting up Python...${NC}\n"
    local python_cmd
    python_cmd=$(check_python)

    echo ""
    echo -e "${BOLD}Creating environment...${NC}\n"
    setup_venv "$python_cmd"

    echo ""
    echo -e "${BOLD}Installing dependencies...${NC}\n"
    install_deps

    echo ""
    echo -e "${BOLD}Configuring NEXUS...${NC}\n"
    create_config

    echo ""
    echo -e "${BOLD}Setting up commands...${NC}\n"
    create_command
    create_shortcut

    echo ""
    check_permissions

    echo -e "${BOLD}${GREEN}Installation complete!${NC}\n"
    echo -e "  ${CYAN}Quick start:${NC}"
    echo -e "    1. Set your API key: ${CYAN}export ANTHROPIC_API_KEY=your_key${NC}"
    echo -e "    2. Edit config: ${CYAN}$NEXUS_HOME/config.yaml${NC}"
    echo -e "    3. Start NEXUS: ${CYAN}nexus start${NC}"
    echo -e "    4. Open dashboard: ${CYAN}http://127.0.0.1:8420${NC}"
    echo ""
    echo -e "  ${DIM}Or double-click NEXUS.command on your Desktop.${NC}"
    echo ""
}

main "$@"
