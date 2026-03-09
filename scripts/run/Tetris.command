#!/usr/bin/env bash
#
# Quadrix macOS Launcher
# Bu dosyaya çift tıklayarak oyunu başlatabilirsiniz!
#
# NOT: Bu dosyayı çalıştırılabilir yapmak için:
#      chmod +x scripts/run/Tetris.command
#

# Repo köküne git
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT" || exit 1

# Terminal penceresini güzel ayarla
printf '\e]0;Quadrix - Full Edition\a'

# macOS crash önleme SDL ayarları
export SDL_VIDEO_HIGHDPI_DISABLED="1"
export SDL_VIDEO_MAC_FULLSCREEN_SPACES="0"
export SDL_AUDIODRIVER="coreaudio"
export SDL_VIDEODRIVER="cocoa"

# Ana başlatıcıyı çalıştır
if [[ -x "./scripts/run/start_game.sh" ]]; then
    ./scripts/run/start_game.sh "$@"
else
    # Fallback: direkt Python ile başlat
    if command -v python3.12 >/dev/null 2>&1; then
        python3.12 main.py "$@"
    elif command -v python3 >/dev/null 2>&1; then
        python3 main.py "$@"
    else
        echo "Python bulunamadı!"
        read -p "Devam etmek için Enter'a basın..."
        exit 1
    fi
fi

# Oyun kapandıktan sonra Terminal'i kapat
exit 0
