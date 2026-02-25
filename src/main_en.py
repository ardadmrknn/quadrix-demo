"""Quadrix Oyunu - English default launcher"""

import os

# Varsayılan dili İngilizceye çek (kullanıcı ayarları yoksa uygulanır)
os.environ.setdefault('TETRIS_DEFAULT_LANGUAGE', 'en')

from main import main

if __name__ == "__main__":
    main()
