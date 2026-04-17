"""Quadrix Oyunu - English default launcher"""

import os
import sys

# Varsayılan dili İngilizceye çek (kullanıcı ayarları yoksa uygulanır)
os.environ.setdefault('TETRIS_DEFAULT_LANGUAGE', 'en')

# Windows cp1254 gibi kısıtlı kodlamalarda emoji print koruması
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass

from main import main

if __name__ == "__main__":
    main()
