"""
Regression testi: Menü müzik playlist'inin tüm UI state'lerinde devam etmesi.

Bug: credits/başarımlar/kılavuz/yeni kullanıcı ekranlarında parça bitince
     müzik devam etmiyordu çünkü update_music_playlist() yalnızca bazı
     handler'larda çağrılıyordu.

Çözüm: main.py ana döngüsünde (while running:), her handler çağrısından
        sonra global olarak menu_sound.update_music_playlist() çağrılıyor.
"""

import ast
import textwrap
from pathlib import Path


MAIN_PY = Path(__file__).parent / "src" / "main.py"


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Kaynak kodu analizi (AST ile)
# ─────────────────────────────────────────────────────────────────────────────


def _find_while_running_body(tree: ast.AST):
    """AST'de `while running:` döngüsünün gövdesini döndürür."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.While)
            and isinstance(node.test, ast.Name)
            and node.test.id == "running"
        ):
            return node.body
    return None


def _stmt_calls_update_playlist(stmt: ast.stmt) -> bool:
    """
    Bir ast.stmt içinde  menu_sound.update_music_playlist()  çağrısı var mı?
    try/except bloklarına da bakar.
    """
    for node in ast.walk(stmt):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "update_music_playlist"
                and isinstance(func.value, ast.Name)
                and func.value.id == "menu_sound"
            ):
                return True
    return False


def test_global_playlist_tick_exists_in_main_loop():
    """
    `while running:` gövdesinde, doğrudan (ekrandan bağımsız olarak)
    menu_sound.update_music_playlist() çağrısının bulunduğunu doğrular.

    Çağrı bir `if state == '...'` dalının içinde olMAMALI —
    state-agnostic (global) olmalı.
    """
    src = MAIN_PY.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(MAIN_PY))

    body = _find_while_running_body(tree)
    assert body is not None, "`while running:` döngüsü main.py'de bulunamadı"

    # Döngü gövdesinin doğrudan ifadelerine (if/try/..) bak.
    # Önemli: İç if dallarına değil, gövdenin birinci seviyesine bakıyoruz.
    found = False
    for stmt in body:
        # try bloğu: handler(delta_ms) çağrısından *sonra* mı?
        # State'e bağlı if bloğunun içinde DEĞİL mi?
        if isinstance(stmt, ast.If):
            # Eğer if testi `state == ...` gibi bir şeyse, içindeki çağrı
            # state-spesifik demektir — global değil.
            test_src = ast.unparse(stmt.test) if hasattr(ast, "unparse") else ""
            if "state" in test_src:
                continue  # state-specific → sayma
        if _stmt_calls_update_playlist(stmt):
            found = True
            break

    assert found, (
        "main.py `while running:` döngüsünde state'ten bağımsız global "
        "menu_sound.update_music_playlist() çağrısı bulunamadı.\n"
        "Bu çağrı credits/başarımlar/kılavuz/yeni kullanıcı ekranlarında "
        "playlist'in ilerlemesini sağlar."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: SoundManager.update_music_playlist() birimi
#          (pygame monkeypatch — mixer init gerektirmez)
# ─────────────────────────────────────────────────────────────────────────────


class _FakeChannel:
    def __init__(self, busy: bool):
        self._busy = busy

    def get_busy(self):
        return self._busy

    def stop(self):
        self._busy = False


class _FakeMixerMusic:
    def __init__(self, busy: bool):
        self._busy = busy
        self._volume = 1.0
        self._loaded = None
        self._playing = False

    def get_busy(self):
        return self._busy

    def load(self, path):
        self._loaded = path

    def play(self, loops=0):
        self._playing = True
        self._busy = True

    def stop(self):
        self._busy = False
        self._playing = False

    def set_volume(self, v):
        self._volume = v

    def pause(self):
        pass

    def unpause(self):
        pass

    def get_pos(self):
        return 0


def _make_sound_manager(monkeypatch, music_busy: bool):
    """
    pygame.mixer.music'i sahte nesnelerle değiştirip
    SoundManager başlatır.  pygame.init() gerektirmez.
    """
    import sys
    import types

    # Minimal pygame stub
    if "pygame" not in sys.modules:
        pygame_stub = types.ModuleType("pygame")
        pygame_stub.USEREVENT = 32868  # tipik değer
        mixer_stub = types.ModuleType("pygame.mixer")
        mixer_stub.music = _FakeMixerMusic(music_busy)

        def get_init():
            return (44100, -16, 2)

        mixer_stub.get_init = get_init
        mixer_stub.pre_init = lambda *a, **kw: None
        mixer_stub.init = lambda *a, **kw: None
        mixer_stub.Sound = type("Sound", (), {"play": lambda s: None, "set_volume": lambda s, v: None})

        pygame_stub.mixer = mixer_stub
        pygame_stub.init = lambda: None
        pygame_stub.quit = lambda: None

        class _Event:
            def __init__(self, t): self.type = t
        pygame_stub.event = types.SimpleNamespace(get=lambda: [], post=lambda e: None)
        pygame_stub.QUIT = 256
        pygame_stub.KEYDOWN = 768
        pygame_stub.K_ESCAPE = 27

        sys.modules["pygame"] = pygame_stub
        sys.modules["pygame.mixer"] = mixer_stub
    else:
        # Sadece music'i override et
        import pygame
        monkeypatch.setattr(pygame.mixer, "music", _FakeMixerMusic(music_busy))

    # constants stub (DEBUG_MODE)
    if "src.constants" not in sys.modules and "constants" not in sys.modules:
        c_stub = types.ModuleType("constants")
        c_stub.DEBUG_MODE = False
        sys.modules["constants"] = c_stub
        sys.modules["src.constants"] = c_stub

    # SoundManager'ı import et
    import importlib, sys as _sys
    # src/ dizinini path'e ekle
    src_dir = str(Path(__file__).parent / "src")
    if src_dir not in _sys.path:
        _sys.path.insert(0, src_dir)

    sound_mod = importlib.import_module("sound")
    sm = sound_mod.SoundManager.__new__(sound_mod.SoundManager)
    # Manuel init — gerçek __init__ pygame.mixer.init vs. çağırabilir
    sm.enabled = True
    sm.music_enabled = True
    sm.muted = False
    sm.music_paused = False
    sm.music_playlist_active = True
    sm.music_playlist = ["track_a", "track_b", "track_c"]
    sm.music_playlist_index = 0
    sm.music_playlist_loop = True
    sm.current_track_name = "track_a"
    sm.current_music_channel = None
    sm.music_volume = 1.0
    sm.sounds = {}
    sm.music_tracks = {}
    sm.sfx_volume = 1.0
    return sm, sound_mod


def test_update_music_playlist_advances_when_not_busy(monkeypatch):
    """
    Parça bitmişse (get_busy → False),
    update_music_playlist() sıradaki parçayı başlatmalı.
    """
    sm, sound_mod = _make_sound_manager(monkeypatch, music_busy=False)

    played = []

    def fake_play(track_name, loop=True, force=False):
        played.append(track_name)
        sm.current_track_name = track_name

    import pygame
    monkeypatch.setattr(sm, "play_music", fake_play, raising=False)
    # Aynı zamanda pygame.mixer.music'i busy=False olarak ayarla
    pygame.mixer.music._busy = False

    sm.update_music_playlist()

    assert len(played) == 1, "Parça bitince sıradaki çalınmalıydı"
    assert played[0] == "track_b", f"Sıradaki parça 'track_b' olmalıydı, ama '{played[0]}' çalındı"


def test_update_music_playlist_does_not_advance_when_busy(monkeypatch):
    """
    Parça hâlâ çalıyorsa (get_busy → True),
    update_music_playlist() yeni parça başlatmamalı.
    """
    sm, sound_mod = _make_sound_manager(monkeypatch, music_busy=True)

    played = []

    def fake_play(track_name, loop=True, force=False):
        played.append(track_name)

    import pygame
    monkeypatch.setattr(sm, "play_music", fake_play, raising=False)
    pygame.mixer.music._busy = True

    sm.update_music_playlist()

    assert len(played) == 0, "Parça hâlâ çalırken yeni parça başlatılmamalıydı"


def test_update_music_playlist_inactive_is_noop(monkeypatch):
    """
    Playlist inactive ise (oyuna geçişte stop_music() sonrası),
    update_music_playlist() hiçbir şey yapmamalı.
    """
    sm, sound_mod = _make_sound_manager(monkeypatch, music_busy=False)
    sm.music_playlist_active = False

    played = []

    def fake_play(track_name, loop=True, force=False):  # noqa
        played.append(track_name)

    import pytest as _pytest
    monkeypatch.setattr(sm, "play_music", fake_play, raising=False)

    sm.update_music_playlist()

    assert len(played) == 0, "Playlist inactive iken parça başlatılmamalıydı"
