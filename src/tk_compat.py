"""tkinter compatibility helpers.

This project primarily uses pygame/SDL. On macOS, initializing tkinter after SDL has
already created its NSApplication subclass can crash with:

    NSInvalidArgumentException: -[SDLApplication macOSVersion]

A practical workaround is to initialize tkinter once early (before pygame.init()),
then reuse a single hidden root window for subsequent dialogs.
"""

from __future__ import annotations

from typing import Any, Optional

_tk_root: Optional[Any] = None
_tk_available: Optional[bool] = None


def get_tk_root() -> Optional[Any]:
    """Return a shared hidden Tk root, or None if tkinter is unavailable."""

    global _tk_root, _tk_available

    if _tk_available is False:
        return None

    try:
        import tkinter as tk
    except Exception:
        _tk_available = False
        return None

    _tk_available = True

    if _tk_root is None:
        root = tk.Tk()
        root.withdraw()
        try:
            # Bring dialogs to the front, but do not keep the hidden root always-on-top.
            root.attributes('-topmost', True)
            root.update_idletasks()
            root.attributes('-topmost', False)
        except Exception:
            pass
        _tk_root = root

    return _tk_root


def prewarm_tkinter() -> None:
    """Best-effort initialization used to avoid macOS SDL/Tk crashes."""

    root = get_tk_root()
    if root is None:
        return
    try:
        root.update_idletasks()
    except Exception:
        pass
