"""Quadrix Oyunu - English default launcher"""

import os
import sys

# Varsayılan dili İngilizceye çek (kullanıcı ayarları yoksa uygulanır)
os.environ.setdefault('TETRIS_DEFAULT_LANGUAGE', 'en')

# Windows terminallerinde Türkçe karakter ve emoji bozulmalarını önle.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from main import main

if __name__ == "__main__":
    main()
