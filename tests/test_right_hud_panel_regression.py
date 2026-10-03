"""DUZ-001 — Sağ HUD paneli NameError regresyon testleri.

Kapsam (Iade_Duzeltme_Plani.md DUZ-001, demo hedef):
- `game.py::Game._draw_right_hud_panel` gerçek metot çağrısı headless
  Surface üzerinde NameError üretmeden tamamlanmalı. Geçmiş hata:
  `panel_width` yerel değişkeni tanımsızken gövdede kullanılıyordu;
  `compileall` bunu yakalayamaz — yalnızca gerçek çağrı yakalar
  (fix: game.py `panel_width = panel_rect.width`, v2 core paritesi).
- Classic yolu Game'in kendisidir; Zen/Sprint/Ultra/Tetris2/Wide/
  Mystery/Survival/Cascade/DailyChallenge/Campaign/Tutorial modları
  `_draw_right_hud_panel`'i override ETMEZ → temel Game metodunu miras
  alır (sınıf sözlüğü kanıtıyla doğrulanır).
- HardcoreMode (game_modes.py) kendi override'ını kullanır; o da gerçek
  çağrıyla NameError üretmemeli.

Desen referansı: tests/test_phase7_campaign_hud_ui_scaling.py
(`__new__` ile instance + stub'lanmış yardımcılar + gerçek metot çağrısı).
"""

from __future__ import annotations

import pathlib
import sys
import types
from types import SimpleNamespace

import pygame


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class _FakeFont:
    def __init__(self, size: int):
        self._size = max(1, int(size))

    def render(self, text, antialias, color):
        width, height = self.size(text)
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        rgb = tuple(color[:3]) if isinstance(color, tuple) else (255, 255, 255)
        surface.fill((*rgb, 255))
        return surface

    def size(self, text):
        return max(1, int(len(str(text or '')) * self._size * 0.55)), self.get_height()

    def get_height(self):
        return self._size

    def get_linesize(self):
        return self._size


def _make_fake_font(size: int, bold: bool = False):
    return _FakeFont(size)


def _install_right_hud_test_stubs(monkeypatch) -> None:
    def _get_fitting_font(text, size, max_width, bold=False, min_size=None):
        base_size = max(1, int(size))
        minimum = max(1, int(min_size or 1))
        candidate = base_size
        while candidate > minimum:
            font = _make_fake_font(candidate, bold=bold)
            if font.size(text)[0] <= max_width:
                return font
            candidate -= 1
        return _make_fake_font(minimum, bold=bold)

    retro_style_stub = types.ModuleType('retro_style')
    retro_style_stub.retro_style = SimpleNamespace(
        draw_glass_panel=lambda surface, rect, alpha=90, border_color=(255, 255, 255), glow=False: pygame.draw.rect(surface, border_color, rect, 1),
        get_font=lambda size, bold=False: _make_fake_font(size, bold=bold),
        get_fitting_font=_get_fitting_font,
    )
    localization_stub = types.ModuleType('localization')
    localization_stub.t = lambda key, *args, **kwargs: key

    monkeypatch.setitem(sys.modules, 'retro_style', retro_style_stub)
    monkeypatch.setitem(sys.modules, 'localization', localization_stub)


def _prepare_base_game(cls, size=(1366, 768)) -> object:
    """Game (veya alt sınıf) instance'ını __new__ ile kur; yalnızca
    _draw_right_hud_panel'ın gerektirdiği alanları sağla."""
    game = cls.__new__(cls)
    game.screen = pygame.Surface(size, pygame.SRCALPHA)
    game.window_width, game.window_height = size
    game.board = SimpleNamespace(score=12345, lines_cleared=9, level=7, combo=1, tetrises=0)
    game.next_piece_queue = []
    game.held_piece = None
    game.can_hold = True
    game._hide_next_pieces = False
    game._show_hold_x = False
    # Çizim yardımcıları — test odağı panel geometrisi/NameError; doku ve
    # cam panel katmanları stub'lanır (test_phase7 deseniyle aynı).
    game._draw_hud_glass_panel = lambda rect: None
    game._draw_custom_frame = lambda rect, asset_name, padding=0, hole_punch=False: False
    game.draw_textured_block = lambda *args, **kwargs: None
    game._make_texture_slice = lambda *args, **kwargs: None
    return game


def test_base_game_right_hud_panel_completes_without_name_error(monkeypatch):
    """DUZ-001 ana regresyon: temel Game._draw_right_hud_panel gerçek
    çağrıyla tamamlanmalı (panel_width tanımı game.py'de sabit)."""
    from game import Game
    from mode_skins import get_mode_skin

    _install_right_hud_test_stubs(monkeypatch)
    game = _prepare_base_game(Game)
    skin = get_mode_skin('classic')

    # NameError yükselirse pytest bu satırda patlar — testin kendisi
    # kabul kriterinin kanıtıdır.
    game._draw_right_hud_panel(
        430, 70, 300, 620,
        skin, None,
        (255, 255, 255), (0, 255, 255), (180, 180, 180),
    )

    # Metot kendi geometri alanlarını yazmalı (CampaignMode testleriyle
    # aynı sözleşme) — panel gerçekten çizilmiş olmalı.
    assert game._hud_panel_rect is not None
    assert game._hud_panel_rect.width > 0


def test_base_game_right_hud_panel_restores_previous_clip(monkeypatch):
    """DUZ-001 clip-guard: çizim öncesi clip panel rect'ine sınırlandırılır
    ve finally bloğu önceki clip'i geri yükler (v2 paritesi)."""
    from game import Game
    from mode_skins import get_mode_skin

    _install_right_hud_test_stubs(monkeypatch)
    game = _prepare_base_game(Game)
    skin = get_mode_skin('classic')

    # Önceki clip: tam ekran (varsayılan) yerine bilinen bir bölge seç —
    # geri yükleme iddiası yanlışlıkla 'her şey None' geçmesin.
    previous_clip = pygame.Rect(10, 10, 100, 100)
    game.screen.set_clip(previous_clip)

    game._draw_right_hud_panel(
        430, 70, 300, 620,
        skin, None,
        (255, 255, 255), (0, 255, 255), (180, 180, 180),
    )

    restored = game.screen.get_clip()
    assert restored == previous_clip, (
        f"Çizim sonrası clip geri yüklenmeli: {restored!r} != {previous_clip!r}"
    )


def test_game_modes_inherit_base_right_hud_panel():
    """Kartın mod yolları: override etmeyen modlar Game metodunu miras
    alır → birinci test bu yolların hepsini kapsar. Override edenler
    yalnızca HardcoreMode (game_modes.py) ve CampaignMode
    (campaign/campaign_mode.py) — kendi testleri aşağıdadır."""
    from game import Game
    from game_modes import SprintMode, UltraMode, ZenMode
    from game_modes_advanced import SurvivalMode, CascadeMode, DailyChallengeMode
    from game_modes_extra import Tetris2Mode, MysteryMode, WideMode
    from tutorial import TutorialMode

    base_method = Game.__dict__['_draw_right_hud_panel']
    for cls in (
        SprintMode, UltraMode, ZenMode,
        SurvivalMode, CascadeMode, DailyChallengeMode,
        Tetris2Mode, MysteryMode, WideMode,
        TutorialMode,
    ):
        own = cls.__dict__.get('_draw_right_hud_panel')
        assert own is None, (
            f"{cls.__name__} beklenmedik şekilde _draw_right_hud_panel'i "
            f"override ediyor — bu test güncellenmeli (DUZ-001 kapsamı)."
        )
        resolved = cls._draw_right_hud_panel
        assert resolved is base_method, (
            f"{cls.__name__}._draw_right_hud_panel Game temel metodunu "
            f"çözümlemeli; farklı bir metoda işaret ediyor."
        )


def test_hardcore_mode_right_hud_panel_completes_without_name_error(monkeypatch):
    """HardcoreMode kendi override'ını kullanır (game_modes.py); gerçek
    çağrıyla NameError üretmemeli."""
    from game_modes import HardcoreMode

    _install_right_hud_test_stubs(monkeypatch)
    hardcore = _prepare_base_game(HardcoreMode)
    hardcore.current_level_num = 7
    hardcore.is_boss = False
    hardcore.is_mini_boss = False

    hardcore._draw_right_hud_panel(
        430, 70, 300, 620,
        None, None,
        (255, 255, 255), (0, 255, 255), (180, 180, 180),
    )

    # Hardcore override'ı kendi geometrisini üretir — gövde hatasız
    # tamamlanma bu testin kabul ölçütüdür (DUZ-001 NameError regresyonu).
    assert hardcore is not None


def test_campaign_mode_right_hud_panel_completes_without_name_error(monkeypatch):
    """CampaignMode kendi override'ını kullanır (campaign_mode.py); gerçek
    çağrıyla NameError üretmemeli. Ayrıntılı geometri iddiaları
    tests/test_phase7_campaign_hud_ui_scaling.py'de zaten mevcut — bu
    test DUZ-001 NameError regresyonu olarak yalnızca tamamlanmayı
    doğrular."""
    from campaign.campaign_mode import CampaignMode

    _install_right_hud_test_stubs(monkeypatch)
    campaign = _prepare_base_game(CampaignMode)
    campaign.current_level_num = 7
    campaign.is_boss = False
    campaign.is_mini_boss = False

    campaign._draw_right_hud_panel(
        430, 70, 300, 620,
        None, None,
        (255, 255, 255), (0, 255, 255), (180, 180, 180),
    )

    assert campaign._hud_panel_rect is not None
    assert campaign._hud_panel_rect.width > 0
