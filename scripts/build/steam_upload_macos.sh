#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  Quadrix - macOS Steam Upload Script
# ═══════════════════════════════════════════════════════════════════
#
#  Kullanım:
#    ./scripts/build/steam_upload_macos.sh                          # Varsayılan (playtest)
#    ./scripts/build/steam_upload_macos.sh --full                   # Tam sürüm (tüm depotlar)
#    ./scripts/build/steam_upload_macos.sh --build-first            # Önce .app derle, sonra yükle
#    ./scripts/build/steam_upload_macos.sh --build-first --full     # Derle + tam sürüm yükle
#    ./scripts/build/steam_upload_macos.sh --desc "Beta 2"          # Özel build açıklaması
#
#  Gereksinimler:
#    - SteamCMD kurulu olmalı
#    - Steamworks partner hesabı ile giriş yapılmış olmalı
#    - dist/Quadrix.app build'i hazır olmalı
#
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Renk kodları ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Proje dizini ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# ── Python (NFC normalizasyon için) ──
if command -v python3.12 &>/dev/null; then
    PYTHON_CMD="python3.12"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    echo -e "${RED}HATA: Python bulunamadı (NFC normalizasyon için gerekli)${NC}"; exit 1
fi

# ── Varsayılanlar ──
STEAM_USER="${STEAM_BUILD_USER:-}"
STEAMCMD_PATH="${STEAMCMD_PATH:-/Users/burakyasayan/Steam/steamcmd}"
FULL_BUILD=false
BUILD_FIRST=false
BUILD_DESC="macOS build $(date +%Y-%m-%d)"
APP_ID="4428040"
MACOS_DEPOT_ID="4428043"

# ── Komut satırı argümanları ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --full)         FULL_BUILD=true; shift ;;
        --build-first)  BUILD_FIRST=true; shift ;;
        --user)         STEAM_USER="$2"; shift 2 ;;
        --steamcmd)     STEAMCMD_PATH="$2"; shift 2 ;;
        --desc)         BUILD_DESC="$2"; shift 2 ;;
        --help|-h)
            echo "Kullanım: $0 [seçenekler]"
            echo ""
            echo "  --full           Tam sürüm build (Windows + macOS)"
            echo "  --build-first    Önce .app derle, sonra Steam'e yükle"
            echo "  --user USER      Steam build hesabı kullanıcı adı"
            echo "  --steamcmd PATH  SteamCMD yolu (varsayılan: $STEAMCMD_PATH)"
            echo "  --desc TEXT      Build açıklaması"
            echo ""
            echo "Ortam değişkenleri:"
            echo "  STEAM_BUILD_USER  Steam build hesabı (--user ile aynı)"
            echo "  STEAMCMD_PATH     SteamCMD yolu"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}Bilinmeyen argüman: $1${NC}"
            exit 1
            ;;
    esac
done

# ═══════════════════════════════════════════════════════════════════
echo -e "${CYAN}${BOLD}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}${BOLD}  Quadrix - macOS Steam Upload${NC}"
echo -e "${CYAN}${BOLD}══════════════════════════════════════════════${NC}"
echo ""

# ── 1. SteamCMD kontrolü ──
if [[ ! -x "$STEAMCMD_PATH" ]]; then
    echo -e "${RED}HATA: SteamCMD bulunamadı: $STEAMCMD_PATH${NC}"
    echo "  STEAMCMD_PATH ortam değişkenini ayarlayın veya --steamcmd kullanın"
    exit 1
fi
echo -e "${GREEN}✓${NC} SteamCMD: $STEAMCMD_PATH"

# ── 2. Steam kullanıcı adı ──
if [[ -z "$STEAM_USER" ]]; then
    echo -ne "${YELLOW}Steam build hesabı kullanıcı adı: ${NC}"
    read -r STEAM_USER
fi
if [[ -z "$STEAM_USER" ]]; then
    echo -e "${RED}HATA: Steam kullanıcı adı boş olamaz.${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Steam kullanıcı: $STEAM_USER"
echo ""

# ── 3. Opsiyonel: Önce build al ──
if $BUILD_FIRST; then
    echo -e "${CYAN}🔨 Önce macOS .app build alınıyor...${NC}"
    if [[ -x "./scripts/build/build_macos_app.sh" ]]; then
        ./scripts/build/build_macos_app.sh --clean
    else
        echo -e "${RED}HATA: scripts/build/build_macos_app.sh bulunamadı veya çalıştırılabilir değil.${NC}"
        exit 1
    fi
    echo ""
fi

# ── 4. dist/Quadrix.app kontrolü ──
APP_PATH="dist/Quadrix.app"
if [[ ! -d "$APP_PATH" ]]; then
    echo -e "${RED}HATA: $APP_PATH bulunamadı!${NC}"
    echo "  Önce build alın: ./scripts/build/build_macos_app.sh"
    echo "  Veya: $0 --build-first"
    exit 1
fi

APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
echo -e "${GREEN}✓${NC} App: $APP_PATH ($APP_SIZE)"

# ── 4b. NFC normalizasyon (macOS NFD → NFC) ──
# macOS dosya adlarını decomposed (NFD) formda saklar (ü = u+combining).
# SteamCMD bu encoding'i manifest'te kabul etmiyor (HTTP 400).
# Çözüm: upload öncesi tüm dosya adlarını NFC'ye normalize et.
NFC_DIR="/tmp/quadrix_nfc_upload_$$"
echo -e "${CYAN}🔧 Dosya adları NFC normalize ediliyor (macOS NFD fix)...${NC}"
$PYTHON_CMD -c "
import unicodedata, os, shutil, sys

src = '$APP_PATH'
dst = '$NFC_DIR/Quadrix.app'

if os.path.exists('$NFC_DIR'):
    shutil.rmtree('$NFC_DIR')

count = 0
symlinks = 0
for root, dirs, files in os.walk(src, followlinks=False):
    rel = os.path.relpath(root, src)
    dst_root = os.path.join(dst, rel) if rel != '.' else dst
    nfc_dst_root = unicodedata.normalize('NFC', dst_root)
    os.makedirs(nfc_dst_root, exist_ok=True)

    # Symlink dizinleri koru
    for d in dirs:
        src_d = os.path.join(root, d)
        if os.path.islink(src_d):
            nfc_d = unicodedata.normalize('NFC', d)
            link_target = os.readlink(src_d)
            nfc_link = unicodedata.normalize('NFC', link_target)
            os.symlink(nfc_link, os.path.join(nfc_dst_root, nfc_d))
            symlinks += 1

    for f in files:
        nfc_f = unicodedata.normalize('NFC', f)
        src_path = os.path.join(root, f)
        dst_path = os.path.join(nfc_dst_root, nfc_f)
        if os.path.islink(src_path):
            # Symlink'i koru (hedefi de NFC normalize et)
            link_target = os.readlink(src_path)
            nfc_link = unicodedata.normalize('NFC', link_target)
            os.symlink(nfc_link, dst_path)
            symlinks += 1
        else:
            shutil.copy2(src_path, dst_path)
        count += 1

print(f'{count} dosya, {symlinks} symlink NFC normalize edildi.')
"
echo -e "${GREEN}✓${NC} NFC normalizasyon tamamlandı"

# ── 5. VDF dosyalarını hazırla ──
SCRIPTS_DIR="steamworks/scripts"
OUTPUT_DIR="steamworks/output"
mkdir -p "$OUTPUT_DIR"

CONTENT_ROOT="$NFC_DIR"

if $FULL_BUILD; then
    VDF_FILE="$SCRIPTS_DIR/app_build_full.vdf"
    echo -e "${GREEN}✓${NC} Mod: Tam sürüm (Windows + macOS)"
else
    VDF_FILE="$SCRIPTS_DIR/app_build_playtest_macos.vdf"
    echo -e "${GREEN}✓${NC} Mod: Playtest (sadece macOS)"
fi

# VDF dosyasını geçici olarak ContentRoot ve BuildOutput ile güncelle
TEMP_VDF="/tmp/quadrix_steam_build_$$.vdf"
sed \
    -e "s|\"ContentRoot\" \".*\"|\"ContentRoot\" \"$CONTENT_ROOT\"|" \
    -e "s|\"BuildOutput\" \".*\"|\"BuildOutput\" \"$(cd "$OUTPUT_DIR" && pwd)\"|" \
    -e "s|\"Desc\" \".*\"|\"Desc\" \"$BUILD_DESC\"|" \
    "$VDF_FILE" > "$TEMP_VDF"

echo -e "${GREEN}✓${NC} Build açıklaması: $BUILD_DESC"
echo ""

# VDF içeriğini göster
echo -e "${CYAN}📋 SteamPipe yapılandırması:${NC}"
echo "─────────────────────────────────"
cat "$TEMP_VDF"
echo "─────────────────────────────────"
echo ""

# ── 6. Depot VDF'i de ContentRoot'un yanında olmalı ──
# SteamCMD, depot VDF'leri app VDF ile aynı dizinde arar
cp "$SCRIPTS_DIR/depot_build_macos.vdf" "/tmp/depot_build_macos.vdf"
if $FULL_BUILD && [[ -f "$SCRIPTS_DIR/depot_build_playtest_windows.vdf" ]]; then
    cp "$SCRIPTS_DIR/depot_build_playtest_windows.vdf" "/tmp/depot_build_playtest_windows.vdf"
fi

# ── 7. Steam'e yükle ──
echo -e "${CYAN}${BOLD}🚀 Steam'e yükleniyor...${NC}"
echo -e "   (Steam Guard doğrulaması istenebilir)"
echo ""

# SteamCMD x86_64 binary → Apple Silicon'da arch -x86_64 gerekli
if [[ "$(uname -m)" == "arm64" ]]; then
    arch -x86_64 "$STEAMCMD_PATH" \
        +login "$STEAM_USER" \
        +run_app_build "$TEMP_VDF" \
        +quit
else
    "$STEAMCMD_PATH" \
        +login "$STEAM_USER" \
        +run_app_build "$TEMP_VDF" \
        +quit
fi

UPLOAD_EXIT=$?

# Temp dosyaları temizle
rm -f "$TEMP_VDF" "/tmp/depot_build_macos.vdf" "/tmp/depot_build_playtest_windows.vdf"
rm -rf "$NFC_DIR"

echo ""
if [[ $UPLOAD_EXIT -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✅ Steam Upload Başarılı!${NC}"
    echo -e "${GREEN}${BOLD}══════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Sonraki adımlar:"
    echo -e "  1. ${BOLD}Steamworks Partner Panel${NC} → AppID $APP_ID → Builds"
    echo -e "  2. Yüklenen build'i kontrol et ve branch'e ata"
    echo -e "  3. macOS launch option'ı doğrula:"
    echo -e "     ${BOLD}Quadrix.app/Contents/MacOS/Quadrix${NC}"
    echo ""
else
    echo -e "${RED}${BOLD}══════════════════════════════════════════════${NC}"
    echo -e "${RED}${BOLD}  ✗ Steam Upload Başarısız (exit: $UPLOAD_EXIT)${NC}"
    echo -e "${RED}${BOLD}══════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Loglar: $OUTPUT_DIR/"
    echo -e "  Sık sorunlar:"
    echo -e "  - Steam Guard doğrulaması gerekiyor"
    echo -e "  - Build hesabının AppID $APP_ID için yetkisi yok"
    echo -e "  - Depot $MACOS_DEPOT_ID Steamworks panelinde oluşturulmamış"
    echo ""
    exit 1
fi
