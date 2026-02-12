#!/bin/bash
# ═══════════════════════════════════════════════════════
#  NEXUS — Instalador One-Click para macOS
#
#  COMO USAR:
#    Opcao 1: Clique DIREITO neste arquivo → "Abrir"
#             (necessario na primeira vez por causa do Gatekeeper)
#
#    Opcao 2: Abra o Terminal e cole:
#             bash -c "$(curl -fsSL https://raw.githubusercontent.com/gtdotwav/nexus/main/scripts/install_macos.sh)"
#
#  Se o macOS bloquear com "nao pode verificar o desenvolvedor":
#    → Clique direito → Abrir (ou Control+Click → Abrir)
#    → Vai em Ajustes do Sistema → Privacidade e Seguranca → "Abrir Mesmo Assim"
# ═══════════════════════════════════════════════════════

# Remove quarantine flag from self (prevents Gatekeeper on next run)
xattr -d com.apple.quarantine "$0" 2>/dev/null || true

# Move to the script's directory (or home if from Downloads)
cd "$HOME"

clear

echo ""
echo "    ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗"
echo "    ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝"
echo "    ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗"
echo "    ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║"
echo "    ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║"
echo "    ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝╚══════╝"
echo ""
echo "    Instalador Automatico v0.5.0 — macOS"
echo "    ─────────────────────────────────────────────"
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

NEXUS_DIR="$HOME/NEXUS"

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

# ─── Check if already installed ──────────────────────

if [[ -d "$NEXUS_DIR/.git" && -f "$NEXUS_DIR/scripts/install_macos.sh" ]]; then
    ok "NEXUS ja esta instalado em $NEXUS_DIR"
    info "Rodando o instalador pra atualizar..."
    echo ""
    bash "$NEXUS_DIR/scripts/install_macos.sh"
    exit $?
fi

# ─── Step 1: Check for Git ───────────────────────────

echo "  [1/3] Verificando Git..."

if ! command -v git &> /dev/null; then
    warn "Git nao encontrado"
    if command -v brew &> /dev/null; then
        info "Instalando Git via Homebrew..."
        brew install git
    else
        info "Instalando Xcode Command Line Tools..."
        xcode-select --install 2>/dev/null || true
        echo ""
        warn "Uma janela vai aparecer. Aceita a instalacao."
        warn "Depois, roda este arquivo de novo."
        echo ""
        echo "  Pressione Enter para fechar."
        read -r
        exit 1
    fi
fi

ok "Git encontrado"

# ─── Step 2: Clone NEXUS ─────────────────────────────

echo "  [2/3] Baixando NEXUS..."

if [[ -d "$NEXUS_DIR" ]]; then
    warn "Pasta $NEXUS_DIR existe, removendo..."
    rm -rf "$NEXUS_DIR"
fi

git clone https://github.com/gtdotwav/nexus.git "$NEXUS_DIR" --quiet
if [[ $? -ne 0 ]]; then
    fail "Erro ao baixar. Verifica tua internet."
    echo ""
    echo "  Pressione Enter para fechar."
    read -r
    exit 1
fi

ok "NEXUS baixado em $NEXUS_DIR"

# ─── Step 3: Run full installer ──────────────────────

echo "  [3/3] Executando instalador completo..."
echo ""

bash "$NEXUS_DIR/scripts/install_macos.sh"
