#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  Quadrix Steam Net Bridge — macOS / Linux Build Script
#
#  Gereksinimler:
#    1. Xcode Command Line Tools (macOS): xcode-select --install
#       veya GCC/Clang (Linux): sudo apt install build-essential
#    2. Python 3.12 + pybind11:  pip3 install pybind11
#    3. CMake 3.18+:  brew install cmake  (macOS)
#    4. Steamworks SDK:  steamworks/sdk/ altına çıkarılmış olmalı
#
#  Kullanım:
#    cd steamworks/steam_net_bridge
#    chmod +x build.sh
#    ./build.sh
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Quadrix Steam Net Bridge — Derleniyor    ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════╝${NC}"
echo ""

# CMake kontrolü
if ! command -v cmake &>/dev/null; then
    echo -e "${RED}[HATA] cmake bulunamadı.${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  Kurulum: brew install cmake"
    else
        echo "  Kurulum: sudo apt install cmake"
    fi
    exit 1
fi

# Python kontrolü (varsayilan: 3.12)
if [[ -n "${QUADRIX_PYTHON:-}" ]]; then
    PYTHON="$QUADRIX_PYTHON"
elif command -v python3.12 &>/dev/null; then
    PYTHON="python3.12"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo -e "${RED}[HATA] Python bulunamadı.${NC}"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PYTHON_EXE="$($PYTHON -c 'import sys; print(sys.executable)')"
PY_TAG="$($PYTHON -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")')"
EXT_SUFFIX="$($PYTHON -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX") or ".so")')"
BUILD_DIR="$SCRIPT_DIR/build_py${PY_TAG}"

echo "[BILGI] Kullanılan Python: $PYTHON_EXE"
echo "[BILGI] Build dizini: $BUILD_DIR"

# Pybind11 kontrolü
if ! "$PYTHON_EXE" -c "import pybind11" 2>/dev/null; then
    echo "[BILGI] pybind11 kuruluyor..."
    "$PYTHON_EXE" -m pip install pybind11 --break-system-packages
fi

# SDK kontrolü
SDK_DIR="$SCRIPT_DIR/../sdk"

if [[ ! -f "$SDK_DIR/public/steam/steam_api.h" ]]; then
    echo -e "${RED}[HATA] Steamworks SDK bulunamadı!${NC}"
    echo "        steamworks/sdk/ dizinine SDK'yı çıkarın."
    echo "        İndirme: https://partner.steamgames.com"
    exit 1
fi

# Build dizini
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Pybind11 CMake dizinini bul
PYBIND11_CMAKE_DIR=$("$PYTHON_EXE" -c "import pybind11; print(pybind11.get_cmake_dir())" 2>/dev/null || echo "")
CMAKE_EXTRA_ARGS=""
if [[ -n "$PYBIND11_CMAKE_DIR" ]]; then
    CMAKE_EXTRA_ARGS="-Dpybind11_DIR=$PYBIND11_CMAKE_DIR"
fi

CMAKE_EXTRA_ARGS="$CMAKE_EXTRA_ARGS -DPYBIND11_FINDPYTHON=ON -DPython_EXECUTABLE=$PYTHON_EXE -DPYTHON_EXECUTABLE=$PYTHON_EXE"

# Platform ayarları
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${CYAN}Platform: macOS${NC}"
    # Universal binary (arm64 + x86_64) desteği
    MACOS_ARCHS="${QUADRIX_MACOS_ARCHS:-arm64;x86_64}"
    CMAKE_EXTRA_ARGS="$CMAKE_EXTRA_ARGS -DCMAKE_OSX_ARCHITECTURES=$MACOS_ARCHS"
else
    echo -e "${CYAN}Platform: Linux${NC}"
fi

# CMake configure + build
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    $CMAKE_EXTRA_ARGS

cmake --build . --config Release -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

if [[ $? -ne 0 ]]; then
    echo -e "${RED}[HATA] Derleme başarısız!${NC}"
    cd ..
    exit 1
fi

# Çıktı dosyasını local_artifacts/bridge altına kopyala
PROJECT_ROOT="$SCRIPT_DIR/../.."
TARGET_DIR="$PROJECT_ROOT/local_artifacts/bridge"
mkdir -p "$TARGET_DIR"
echo ""
echo "[KOPYALAMA] Modül dosyası local_artifacts/bridge klasörüne kopyalanıyor..."

ARTIFACT=""
if [[ -n "$EXT_SUFFIX" ]]; then
    ARTIFACT=$(find . -name "steam_net_bridge*${EXT_SUFFIX}" | head -1 || true)
fi
if [[ -z "$ARTIFACT" ]]; then
    ARTIFACT=$(find . -name "steam_net_bridge*.so" | head -1 || true)
fi

if [[ -z "$ARTIFACT" ]]; then
    echo -e "${RED}[HATA] Derleme çıktı dosyası bulunamadı.${NC}"
    exit 1
fi

cp "$ARTIFACT" "$TARGET_DIR/"
echo "  → $(basename "$ARTIFACT") kopyalandı"

if [[ "$OSTYPE" == "darwin"* ]]; then
    STEAM_DYLIB_SRC="$SDK_DIR/redistributable_bin/osx/libsteam_api.dylib"
    if [[ -f "$STEAM_DYLIB_SRC" ]]; then
        cp "$STEAM_DYLIB_SRC" "$TARGET_DIR/"
        echo "  → libsteam_api.dylib kopyalandı"
    else
        echo -e "${RED}[HATA] libsteam_api.dylib bulunamadı: $STEAM_DYLIB_SRC${NC}"
        exit 1
    fi
fi

cd ..
echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Derleme başarılı!${NC}"
echo -e "${GREEN}  $(basename "$ARTIFACT") local_artifacts/bridge altında hazır.${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
