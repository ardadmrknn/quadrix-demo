# -*- coding: utf-8 -*-
"""online_pvp_game <-> platform_utils import sözleşmesi (demo).

Kök neden (2026-10-09, VDS): demo platform_utils'unda ``resource_path``
HİÇ tanımlı değildi (git -S ile doğrulandı; v2'de platform_utils.py:22'de
var). online_pvp_game.py:284'ün ``from platform_utils import
create_display, set_app_icon, resource_path`` ifadesi bu yüzden demo'da
HER import'ta ImportError'a düşüyor ve modül sessizce except dalındaki
fallback ailesine geçiyordu:

- ``create_display`` -> 5 satırlık çiğ ``pygame.display.set_mode`` (VRR
  filtreleme, GL pencere talebi / Steam overlay tek-context koordinasyonu,
  Linux fullscreen mod override, sanal tuval/letterbox ve work-area
  kelepçeleme yolları demo üretiminde ÖLÜ);
- ``get_mouse_pos`` -> guard'sız ``pygame.mouse.get_pos`` (gerçek
  platform_utils sürümü try/except ile (0, 0) döner — pygame.quit() sonrası
  "video system not initialized" hatasına düşmez);
- ``normalize_mouse_pos`` -> identity (letterbox düzeltmesi yok).

Test görünürliğündeki ikincil belirti: test_duz007_action_metadata_contract
finally bloklarında pygame.quit() çağırdığından, lobby dosyasının
koleksiyon-zamanı display init'i koşum fazına ölü ulaşıyor ve guard'sız
fallback get_mouse_pos 57 lobby testini düşürüyordu (duz007 x lobby
zehirlenmesi). Bu sözleşme testi import başarısını kilitlediğinde o
belirti de doğal olarak kapanır.
"""
from __future__ import annotations

import inspect
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_platform_utils_exposes_online_pvp_import_names():
    """online_pvp_game:284-285'in istediği isimlerin TAMAMI gerçek
    platform_utils'ta bulunmalı (fallback pişmemeli)."""
    import platform_utils

    for name in (
        'create_display',
        'set_app_icon',
        'resource_path',
        'normalize_mouse_pos',
        'get_mouse_pos',
        'resolve_frame_rate_cap',
    ):
        assert hasattr(platform_utils, name), (
            f"platform_utils '{name}' dışa açmıyor — online_pvp_game "
            f"import'u ImportError'a düşüp fallback ailesine geçer"
        )


def test_online_pvp_game_uses_real_platform_utils():
    """online_pvp_game modül-seviyesi isimleri platform_utils'tan
    bağlanmalı; yerel fallback tanımları DEĞİL."""
    import online_pvp_game
    import platform_utils

    assert online_pvp_game.create_display is platform_utils.create_display
    assert online_pvp_game.set_app_icon is platform_utils.set_app_icon
    assert online_pvp_game.resource_path is platform_utils.resource_path
    assert online_pvp_game.normalize_mouse_pos is platform_utils.normalize_mouse_pos
    assert online_pvp_game.get_mouse_pos is platform_utils.get_mouse_pos
    assert online_pvp_game.resolve_frame_rate_cap is platform_utils.resolve_frame_rate_cap


def test_resource_path_is_pyinstaller_aware():
    """v2 platform_utils.py:22 paritesi: frozen çalıştırmada sys._MEIPASS
    taban yolunu kullanmalı (demo Steam paketi PyInstaller ile donduruluyor)."""
    import platform_utils

    source = inspect.getsource(platform_utils.resource_path)
    assert '_MEIPASS' in source, (
        'resource_path PyInstaller _MEIPASS yolunu tanımıyor — frozen '
        'EXE paketinde asset yolları paket kökünü değil geliştirme ağacını gösterir'
    )
