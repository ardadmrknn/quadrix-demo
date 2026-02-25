"""
Tkinter'a bağımlı olmayan platform dosya diyalogu.

Derlenen .app paketlerinde tkinter hariç tutulduğunda,
macOS'un native NSOpenPanel'ini AppleScript üzerinden çağırır.
"""

from __future__ import annotations

import os
import platform
import subprocess
from typing import List, Optional, Tuple


def open_file_dialog(
    title: str = "Dosya Seç",
    filetypes: Optional[List[Tuple[str, str]]] = None,
) -> Optional[str]:
    """
    Dosya seçme diyalogu aç.

    Önce tkinter dener, bastırırsa macOS AppleScript'e düşer.

    Parametreler:
        title: Diyalog başlığı
        filetypes: [(açıklama, "*.png *.jpg"), ...] formatında filtre listesi

    Dönüş:
        Seçilen dosya yolu veya iptal edilirse None
    """
    # 1) tkinter dene
    path = _try_tkinter(title, filetypes)
    if path is not None:
        return path if path else None

    # 2) macOS native diyalog (AppleScript)
    if platform.system() == "Darwin":
        return _macos_file_dialog(title, filetypes)

    return None


def _try_tkinter(title: str, filetypes) -> Optional[str]:
    """Tkinter ile dosya diyalogu aç. None dönerse kullanılamıyor."""
    try:
        from tk_compat import get_tk_root
        from tkinter import filedialog
    except Exception:
        return None

    root = get_tk_root()
    if root is None:
        return None

    tk_filetypes = []
    if filetypes:
        for desc, exts in filetypes:
            tk_filetypes.append((desc, exts))

    filepath = filedialog.askopenfilename(
        title=title,
        filetypes=tk_filetypes or [("Tüm Dosyalar", "*.*")],
        parent=root,
    )

    try:
        import pygame
        pygame.event.clear()
    except Exception:
        pass
    try:
        from platform_utils import request_window_focus
        request_window_focus()
    except Exception:
        pass

    return filepath if filepath else ""


def _macos_file_dialog(title: str, filetypes) -> Optional[str]:
    """macOS AppleScript ile native dosya diyalogu aç."""
    # Uzantıları çıkar
    allowed_exts = []
    if filetypes:
        for _, exts_str in filetypes:
            for token in exts_str.replace(",", " ").split():
                token = token.strip().lstrip("*.")
                if token and token != "*":
                    allowed_exts.append(token)

    # AppleScript oluştur
    of_type_clause = ""
    if allowed_exts:
        ext_list = ", ".join(f'"{e}"' for e in allowed_exts)
        of_type_clause = f" of type {{{ext_list}}}"

    script = (
        'tell application "System Events"\n'
        f'  set theFile to choose file with prompt "{title}"{of_type_clause}\n'
        '  return POSIX path of theFile\n'
        'end tell'
    )

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        filepath = result.stdout.strip()
        if filepath and os.path.exists(filepath):
            return filepath
    except Exception as exc:
        print(f"[file_dialog] macOS dialog hatası: {exc}")

    # Focus'u pygame penceresine geri al
    try:
        from platform_utils import request_window_focus
        request_window_focus()
    except Exception:
        pass

    return None
