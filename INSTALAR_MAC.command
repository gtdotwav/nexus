#!/bin/bash
# ═══════════════════════════════════════════════════════
#  NEXUS — Instalador One-Click para macOS v0.5.1
#
#  COMO USAR:
#    Opcao 1 (recomendado):
#      Abra o Terminal e cole:
#      bash <(curl -fsSL https://raw.githubusercontent.com/gtdotwav/nexus/main/scripts/install_macos.sh)
#
#    Opcao 2:
#      Clique DIREITO neste arquivo → "Abrir"
#      (necessario na primeira vez por causa do Gatekeeper)
#
#  Se o macOS bloquear:
#    → Ajustes do Sistema → Privacidade e Seguranca → "Abrir Mesmo Assim"
# ═══════════════════════════════════════════════════════

# Remove quarantine flag from self (prevents Gatekeeper on next run)
xattr -d com.apple.quarantine "$0" 2>/dev/null || true

cd "$HOME" || exit 1
clear

NEXUS_DIR="$HOME/NEXUS"

echo ""
echo "    ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗"
echo "    ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝"
echo "    ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗"
echo "    ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║"
echo "    ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║"
echo "    ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝╚══════╝"
echo ""
echo "    Iniciando instalador..."
echo ""

# If NEXUS is already installed, just run the updater
if [[ -d "$NEXUS_DIR/.git" && -f "$NEXUS_DIR/scripts/install_macos.sh" ]]; then
    echo "  NEXUS ja esta instalado — atualizando..."
    echo ""
    exec bash "$NEXUS_DIR/scripts/install_macos.sh"
fi

# Otherwise, download and run the full installer directly
# This avoids duplicating logic — install_macos.sh handles everything
echo "  Baixando instalador completo..."
echo ""

# Use process substitution to keep stdin free for user interaction
exec bash <(curl -fsSL https://raw.githubusercontent.com/gtdotwav/nexus/main/scripts/install_macos.sh)
