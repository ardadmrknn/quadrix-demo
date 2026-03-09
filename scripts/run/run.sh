#!/usr/bin/env bash
#
# Quadrix Hızlı Başlatıcı
# (venv kullanılmaz; paketler sistem Python'una kurulu olmalı)
#
cd "$(dirname "$0")" || exit 1
cd ../.. || exit 1

# VENV KESİNLİKLE YASAK: yanlışlıkla oluştuysa otomatik sil.
if [[ -d ".venv" ]]; then
    echo "[NO-VENV] .venv tespit edildi -> siliyorum (repo kuralı: venv ASLA)"
    rm -rf .venv
fi

# macOS için SDL ayarları (crash önleme)
if [[ "${OSTYPE:-}" == darwin* ]]; then
    export SDL_VIDEO_WINDOW_POS="center"
    # HiDPI KAPALI - Retina crash'lerini önler
    export SDL_VIDEO_HIGHDPI_DISABLED="1"
    # Fullscreen Spaces KAPALI - crash önleme
    export SDL_VIDEO_MAC_FULLSCREEN_SPACES="0"
    # Ses sürücüsü
    export SDL_AUDIODRIVER="coreaudio"
    # Video sürücüsü
    export SDL_VIDEODRIVER="cocoa"
fi

# Linux için SDL ayarları
if [[ "${OSTYPE:-}" == linux* ]]; then
    # PulseAudio tercih et
    export SDL_AUDIODRIVER="pulseaudio"
fi

# Oyunu başlat - main.py root'ta
if command -v python3.12 >/dev/null 2>&1; then
    exec python3.12 main.py "$@"
elif command -v python3 >/dev/null 2>&1; then
    exec python3 main.py "$@"
else
    exec python main.py "$@"
fi
