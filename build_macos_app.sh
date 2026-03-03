#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  Quadrix - macOS All-in-One .app Build Script
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Quadrix"
SPEC_FILE="tetris_macos_allinone.spec"
DIST_DIR="dist"
BUILD_DIR="build"

CLEAN_BUILD=false
for arg in "$@"; do
    case "$arg" in
        --clean) CLEAN_BUILD=true ;;
    esac
done

echo -e "${CYAN}${BOLD}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}${BOLD}  Quadrix macOS All-in-One App Builder${NC}"
echo -e "${CYAN}${BOLD}══════════════════════════════════════════════${NC}"
echo ""

# Python 3.12 tercih et (PyInstaller + pygame kurulu)
PYTHON_CMD=""
if command -v python3.12 &>/dev/null; then
    PYTHON_CMD="python3.12"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    echo -e "${RED}HATA: Python bulunamadı!${NC}"; exit 1
fi

PYTHON_VER=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}✓${NC} Python: $PYTHON_VER"

# PyInstaller & Pygame kontrolü
if ! $PYTHON_CMD -c "import PyInstaller" 2>/dev/null; then
    echo -e "${RED}HATA: PyInstaller bulunamadı!${NC}"; exit 1
fi
if ! $PYTHON_CMD -c "import pygame" 2>/dev/null; then
    echo -e "${RED}HATA: pygame bulunamadı!${NC}"; exit 1
fi
echo -e "${GREEN}✓${NC} PyInstaller: $($PYTHON_CMD -c 'import PyInstaller; print(PyInstaller.__version__)')"
echo -e "${GREEN}✓${NC} Spec: $SPEC_FILE"
echo ""

if $CLEAN_BUILD; then
    echo -e "${YELLOW}🧹 Temizleniyor...${NC}"
    rm -rf "$BUILD_DIR/$APP_NAME" "$DIST_DIR/$APP_NAME" "$DIST_DIR/$APP_NAME.app"
fi

# Steam Net Bridge (Online PvP için zorunlu)
echo -e "${CYAN}🔧 Steam Net Bridge kontrolü...${NC}"
BRIDGE_SO=$(ls steam_net_bridge*.so 2>/dev/null | head -1 || true)
if [[ -z "$BRIDGE_SO" ]]; then
    echo -e "${YELLOW}  Bridge bulunamadı, derleniyor...${NC}"
    if [[ ! -f "steamworks/steam_net_bridge/build.sh" ]]; then
        echo -e "${RED}HATA: steamworks/steam_net_bridge/build.sh bulunamadı!${NC}"; exit 1
    fi
    chmod +x steamworks/steam_net_bridge/build.sh
    (cd steamworks/steam_net_bridge && ./build.sh)
    BRIDGE_SO=$(ls steam_net_bridge*.so 2>/dev/null | head -1 || true)
    if [[ -z "$BRIDGE_SO" ]]; then
        echo -e "${RED}HATA: Bridge derlemesi başarısız!${NC}"; exit 1
    fi
fi
echo -e "${GREEN}✓${NC} Bridge: $BRIDGE_SO"

# Menü layout embed
echo -e "${CYAN}📦 Menü layout embedleniyor...${NC}"
$PYTHON_CMD -c "
import sys; sys.path.insert(0, '.')
from tools.embed_menu_layout import write_embedded_layout_module
write_embedded_layout_module('.')
"

echo -e "${CYAN}${BOLD}🔨 PyInstaller ile .app oluşturuluyor...${NC}"
BUILD_START=$(date +%s)

$PYTHON_CMD -m PyInstaller "$SPEC_FILE" --noconfirm --clean --log-level WARN 2>&1 | \
    grep -E "Building|ERROR|WARNING|INFO.*Platform" || true

BUILD_END=$(date +%s)
APP_PATH="$DIST_DIR/$APP_NAME.app"

if [[ ! -d "$APP_PATH" ]]; then
    echo -e "${RED}✗ Build başarısız!${NC}"; exit 1
fi

APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
echo ""
echo -e "${GREEN}${BOLD}✅ Build tamamlandı!${NC} ($((BUILD_END - BUILD_START))s)"
echo -e "  📱 $APP_PATH ($APP_SIZE)"
echo ""
