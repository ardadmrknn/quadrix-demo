#!/usr/bin/env bash
#
# Quadrix macOS/Linux Başlatıcı
# Bu script oyunu direkt sistem Python'u ile başlatır ve gerekli paketleri yükler
#
set -euo pipefail

# Repo köküne git
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REQ_FILE="$REPO_ROOT/packaging/requirements/requirements-macos.txt"
FALLBACK_REQ="$REPO_ROOT/packaging/requirements/requirements.txt"

cd "$REPO_ROOT"

# Renk kodları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# VENV KESİNLİKLE YASAK: yanlışlıkla oluştuysa otomatik sil.
if [[ -d ".venv" ]]; then
    echo -e "${YELLOW}!${NC} [NO-VENV] .venv tespit edildi -> siliyorum (repo kuralı: venv ASLA)"
    rm -rf .venv
fi

echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}     🎮 ${GREEN}QUADRIX - Full Edition${NC}        ${BLUE}║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
echo ""

# Platform kontrolü
if [[ "${OSTYPE:-}" == darwin* ]]; then
    PLATFORM="macOS"
    echo -e "${GREEN}✓${NC} Platform: macOS tespit edildi"
elif [[ "${OSTYPE:-}" == linux* ]]; then
    PLATFORM="Linux"
    echo -e "${GREEN}✓${NC} Platform: Linux tespit edildi"
else
    PLATFORM="Unknown"
    echo -e "${YELLOW}!${NC} Bilinmeyen platform: ${OSTYPE:-unknown}"
    echo -e "${YELLOW}!${NC} Windows için scripts/run/start_game.bat kullanın."
fi

# Başlatıcıya özel flag'leri oyuna göndermemek için ayır
FORCE_INSTALL=0
FORCE_UPDATE=0
if [[ "${1:-}" == "--install" ]]; then
    FORCE_INSTALL=1
    shift
elif [[ "${1:-}" == "--update" ]]; then
    FORCE_UPDATE=1
    shift
fi

# Python kontrolü
# Not: Bu script bash ile çalışır; zsh alias'ları (ör. python3 -> python3.12) burada geçerli değildir.
# O yüzden mevcutsa python3.12'yi önceliklendir.
PYTHON_BIN=""
if command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="python3.12"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo -e "${RED}✗${NC} Python 3 bulunamadı!"
    echo ""
    if [[ "$PLATFORM" == "macOS" ]]; then
        echo "  macOS için yükleme yöntemleri:"
        echo "    1. Homebrew: brew install python@3.12"
        echo "    2. python.org'dan indirin"
    else
        echo "  Linux için yükleme:"
        echo "    sudo apt install python3 python3-pip"
    fi
    exit 1
fi

# Python versiyonu kontrol et
PYTHON_VERSION=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$("$PYTHON_BIN" -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$("$PYTHON_BIN" -c "import sys; print(sys.version_info.minor)")

# Minimum Python 3.10 gerekli (type union syntax ve dataclass slots için)
if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 10 ]]; then
    echo -e "${RED}✗${NC} Python $PYTHON_VERSION tespit edildi"
    echo -e "${RED}✗${NC} Bu oyun Python 3.10 veya üzeri gerektirir!"
    echo ""
    if [[ "$PLATFORM" == "macOS" ]]; then
        echo "  macOS için güncelleme:"
        echo "    brew install python@3.12"
        echo "    veya python.org'dan Python 3.12 indirin"
    else
        echo "  Linux için güncelleme:"
        echo "    sudo apt install python3.12"
    fi
    exit 1
fi
echo -e "${GREEN}✓${NC} Python sürümü: $PYTHON_VERSION (✓ 3.10+ gereksinimi karşılandı)"

# macOS'ta SDL/pygame için gerekli konfigürasyon (CRASH ÖNLEME)
if [[ "$PLATFORM" == "macOS" ]]; then
    # SDL video sürücüsü ayarı (pencere focus için)
    export SDL_VIDEO_WINDOW_POS="center"
    
    # HiDPI KAPALI - Retina ekranlarda crash önleme
    export SDL_VIDEO_HIGHDPI_DISABLED="1"
    
    # Fullscreen Spaces KAPALI - macOS fullscreen crash önleme
    export SDL_VIDEO_MAC_FULLSCREEN_SPACES="0"
    
    # macOS native sürücüler
    export SDL_AUDIODRIVER="coreaudio"
    export SDL_VIDEODRIVER="cocoa"
    
    # Focus kaybında minimize etme
    export SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS="0"
    
    echo -e "${GREEN}✓${NC} macOS SDL ayarları yapılandırıldı (crash önleme aktif)"
fi

# Linux için SDL ayarları
if [[ "$PLATFORM" == "Linux" ]]; then
    # PulseAudio tercih et (varsa)
    if command -v pulseaudio >/dev/null 2>&1 || command -v pipewire-pulse >/dev/null 2>&1; then
        export SDL_AUDIODRIVER="pulseaudio"
    fi
fi

# Paket yükleme
install_packages() {
    echo -e "${YELLOW}→${NC} Paketler kontrol ediliyor..."

    # Venv kullanılmıyor: paketleri kullanıcı alanına kur (admin gerekmesin).
    # Not: Homebrew Python ile bu en sorunsuz yol.
    local pip_args=(--user)
    if [[ "$FORCE_UPDATE" -eq 1 ]]; then
        pip_args+=(--upgrade)
    fi
    
    if [ -f "$REQ_FILE" ]; then
        echo -e "${YELLOW}→${NC} macOS paketleri yükleniyor (packaging/requirements/requirements-macos.txt)..."
        "$PYTHON_BIN" -m pip install "${pip_args[@]}" --requirement "$REQ_FILE" --quiet
    elif [ -f "$FALLBACK_REQ" ]; then
        echo -e "${YELLOW}→${NC} Paketler yükleniyor (packaging/requirements/requirements.txt)..."
        "$PYTHON_BIN" -m pip install "${pip_args[@]}" --requirement "$FALLBACK_REQ" --quiet
    else
        echo -e "${YELLOW}→${NC} Minimum paketler yükleniyor..."
        "$PYTHON_BIN" -m pip install "${pip_args[@]}" pygame numpy --quiet
    fi
    
    echo -e "${GREEN}✓${NC} Paketler hazır"
}

# Paketler yüklü mü kontrol et; eksikse (veya --install/--update verildiyse) yükle
DEPS_OK=0
if "$PYTHON_BIN" -c "import pygame, numpy" >/dev/null 2>&1; then
    DEPS_OK=1
fi

if [[ "$FORCE_UPDATE" -eq 1 ]]; then
    echo -e "${YELLOW}→${NC} Paketler güncelleniyor..."
    install_packages
elif [[ "$FORCE_INSTALL" -eq 1 ]] || [[ "$DEPS_OK" -eq 0 ]]; then
    install_packages
fi

echo ""
echo -e "${GREEN}🎮 Oyun başlatılıyor...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Oyunu başlat
# macOS'ta pencereyi öne getirmek için osascript kullan (opsiyonel)
if [[ "$PLATFORM" == "macOS" ]]; then
    # Oyunu başlat ve Terminal'i geri planda bırak
    exec "$PYTHON_BIN" main.py "$@"
else
    exec "$PYTHON_BIN" main.py "$@"
fi
