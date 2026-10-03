# -*- coding: utf-8 -*-
"""P1-12b: Online lobi/bekleme metin bütçeleri — containment regresyonları.

Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu.md (P1-12b): online PvP ve
Co-op lobi/bekleme ekranlarındaki metinler (lobi adı, detay, zaman, durum,
Steam ID) bütçelenmeden çiziliyordu; dar/kısa çözünürlüklerde panel dışına
taşıyor veya komşu elemanlarla çakışıyordu.

Bu dosya draw() yollarının GEOMETRİK sözleşmesini kilitler:
- bekleme paneli render güvenli alanı içinde (fallback: tam ekran);
- aksiyon/geri butonları panel içinde ve birbirini kapatmaz (Co-op'ta eski
  kodda card.bottom+20 butonları panel.bottom-70 geri butonuyla kısa
  ekranlarda ÖRTÜŞÜYORDU — alt-sınır regresyon testi);
- lobi listesi item metinleri (ad/detay/zaman) sağ kenar elemanlarıyla
  (rozet / Katıl butonu / doluluk barı) yatayda çakışmaz;
- durum mesajı 2 satıra dek sarılır ve güvenli alan içinde kalır;
- 1366x768 @ scale=1.0 taban yerleşimi piksel bazında korunur (PvP ph=440,
  Co-op ph=510; geri butonları eski sabit ofsetlerde).

Demo notu: quadrix-demo'da lobi/bekleme gamepad navigasyonu yok (v2'deki
focus/legend yolları taşınmadı — demo ayrımı korunur); bu testler yalnız
geometri sözleşmesini ölçer, gamepad atribütleri v2 test kalıbıyla aynı
fazla miktarda set edilir (kullanılmayanları ayarlamak zararsızdır).

Ölçüm sınırı (dürüst rapor): gerçek render geometry (A1 safe_rect) ve
görsel doğrulama kılavuz §7'deki manuel Windows smoke'a aittir — dummy
driver altında get_render_safe_rect None döner ve tam-ekran fallback
ölçülür. Bu dosya sözleşmeyi (değişmezler) kilitler.

Kalıp: test_online_coop_lobby_gamepad_nav (dummy sürücüler + __new__ bare
instance) ve test_online_pvp_launch_guard draw idyomu (v2'deki
test_online_lobby_containment.py'nin demo portu).
"""
from __future__ import annotations

import os
import pathlib
import sys
import time
import types

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

if not pygame.get_init():
    pygame.init()
if not pygame.display.get_init():
    pygame.display.init()
pygame.display.set_mode((320, 240))
if not pygame.font.get_init():
    pygame.font.init()

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

import online_pvp_game as pvp_module
import online_coop_game as coop_module

OnlinePvPGame = pvp_module.OnlinePvPGame
OnlineCoopGame = coop_module.OnlineCoopGame

# Rapor matrisi: küçük taşınabilir çözünürlüklerden 4K'ya; _ui_scale de
# varye edilir (dar pencerede motor 0.72'ye kadar küçültür, HiDPI'da büyütür).
SIZES = [
    (800, 480),
    (1024, 600),
    (1280, 720),
    (1366, 768),
    (1920, 1080),
    (3840, 2160),
]
SCALES = [1.0, 0.72, 1.5]

LONG_STATUS_TR = (
    'Sunucu bağlantısı zaman aşımına uğradı ve lobi listesi yenilenemiyor; '
    'lütfen bağlantınızı kontrol edip tekrar deneyin'
)
LONG_NAME_TR = 'Çok Uzun Türkçe Oyuncu Adı ' + 'X' * 40


def _pvp_entries():
    now = time.time()
    return [
        {'id': 1, 'name': LONG_NAME_TR, 'members': 1, 'max_members': 2,
         'visibility': 'public', 'requires_code': False, 'code': '',
         'found_time': now},
        {'id': 2, 'name': 'Kısa', 'members': 2, 'max_members': 4,
         'visibility': 'private', 'requires_code': True, 'code': '123456',
         'found_time': now},
    ]


def _coop_entries():
    now = time.time()
    return [
        {'id': 11, 'host_name': LONG_NAME_TR, 'members': 1,
         'max_members': 2, 'visibility': 'public', 'requires_code': False,
         'code': '', 'found_time': now},
        {'id': 12, 'host_name': 'Kısa', 'members': 2, 'max_members': 4,
         'visibility': 'private', 'requires_code': True, 'code': '654321',
         'found_time': now},
    ]


def _make_pvp(size, scale=1.0, lobby_code='482917', status=LONG_STATUS_TR):
    game = OnlinePvPGame.__new__(OnlinePvPGame)
    game.screen = pygame.Surface(size)
    game.window_width, game.window_height = size
    game._ui_scale = lambda sc=scale: sc
    game.gamepad = None
    game.settings_manager = None
    game.net = types.SimpleNamespace(my_steam_id=76561198000000000)
    game._net_initialized = True
    game._status_msg = status
    game._lobby_buttons = []
    game._lobby_code = lobby_code
    game._lobby_nav_active = False
    game._lobby_menu_selected = 0
    game._lobby_focus_zone = 'left'
    game._lobby_list_filter = 'all'
    game._lobby_list_scroll = 0
    game._lobby_list_selected = 0
    game._lobby_list_visible_count = 5
    game._lobby_list_fetching = False
    game._auto_lobby_refresh_requested = False
    game._lobby_list = _pvp_entries()
    game._join_code_active = False
    game._join_code_input = ''
    game._join_code_error = ''
    return game


def _make_coop(size, scale=1.0, lobby_code='482917', status=LONG_STATUS_TR):
    game = OnlineCoopGame.__new__(OnlineCoopGame)
    game.screen = pygame.Surface(size)
    game.window_width, game.window_height = size
    game._ui_scale = lambda sc=scale: sc
    game.gamepad = None
    game.settings_manager = None
    game.net = types.SimpleNamespace(my_steam_id=76561198000000000)
    game._status_msg = status
    game._lobby_buttons = []
    game._lobby_code = lobby_code
    game._lobby_nav_active = False
    game._lobby_menu_selected = 0
    game._lobby_focus_zone = 'left'
    game._lobby_list_filter = 'all'
    game._lobby_list_scroll = 0
    game._lobby_list_selected = 0
    game._lobby_list_visible_count = 5
    game._lobby_list_fetching = False
    game._auto_lobby_refresh_requested = False
    game._lobby_list = _coop_entries()
    game._join_code_active = False
    game._join_code_input = ''
    game._join_code_error = ''
    return game


def _screen_rect(size):
    return pygame.Rect(0, 0, size[0], size[1])


# ── PvP bekleme ekranı ──────────────────────────────────────────────────────


@pytest.mark.parametrize('scale', SCALES)
@pytest.mark.parametrize('size', SIZES)
@pytest.mark.parametrize('lobby_code', ['482917', ''])
def test_pvp_waiting_screen_containment(size, scale, lobby_code):
    game = _make_pvp(size, scale=scale, lobby_code=lobby_code)
    game._draw_waiting_screen()
    rects = game._online_waiting_rects
    assert rects is not None

    bounds = rects['bounds']
    assert bounds.width <= size[0] and bounds.height <= size[1]
    assert bounds.contains(rects['panel']), (size, scale, lobby_code)

    for key in ('title', 'code', 'copy', 'invite', 'back'):
        r = rects[key]
        if r is not None:
            assert rects['panel'].contains(r), (key, size, scale)

    # Durum mesajı: 2 satıra dek; güvenli alan içinde; panel içine
    # alındıysa gerçekten panel içinde.
    assert len(rects['status_line_rects']) <= 2
    for r in rects['status_line_rects']:
        assert bounds.contains(r), (size, scale)
        if rects['status_inside_panel']:
            assert rects['panel'].contains(r), (size, scale)


def test_pvp_waiting_screen_1366x768_baseline():
    """Taban yerleşim piksel bazında korunur: ph=440, flow=1.0, geri
    butonu eski sabit ofsette (panel.y + 100 + 122 + 16 + 54 = +292)."""
    game = _make_pvp((1366, 768))
    game._draw_waiting_screen()
    rects = game._online_waiting_rects

    assert rects['flow'] == 1.0
    assert rects['panel'].height == 440
    assert rects['back'].y == rects['panel'].y + 292
    assert rects['back'].height == 38
    assert rects['invite'].height == 44


# ── Co-op bekleme ekranı ─────────────────────────────────────────────────────


@pytest.mark.parametrize('scale', SCALES)
@pytest.mark.parametrize('size', SIZES)
@pytest.mark.parametrize('lobby_code', ['482917', ''])
def test_coop_waiting_screen_containment(size, scale, lobby_code):
    game = _make_coop(size, scale=scale, lobby_code=lobby_code)
    game._draw_waiting_screen()
    rects = game._coop_waiting_rects
    assert rects is not None

    panel = rects['panel']
    assert rects['bounds'].width <= size[0] and rects['bounds'].height <= size[1]
    assert rects['bounds'].contains(panel), (size, scale, lobby_code)
    assert panel.contains(rects['card'])

    # Alt-sınır regresyonu: aksiyon butonları ↔ geri butonu asla örtüşmez
    # (eski kodda kısa ekranlarda örtüşüyordu) ve hepsi panel içindedir.
    back = rects['back']
    assert panel.contains(back)
    for br in rects['button_rects']:
        assert panel.contains(br), (size, scale)
        assert not back.colliderect(br), (size, scale, br, back)

    assert len(rects['status_line_rects']) <= 2
    for r in rects['status_line_rects']:
        assert panel.contains(r), (size, scale)


def test_coop_waiting_screen_1366x768_baseline():
    """Taban yerleşim piksel bazında korunur: ph=510, flow=1.0, yatay
    butonlar, geri butonu panel.bottom-s(70) ofsetinde."""
    game = _make_coop((1366, 768))
    game._draw_waiting_screen()
    rects = game._coop_waiting_rects

    assert rects['flow'] == 1.0
    assert rects['stack_buttons'] is False
    assert rects['panel'].height == 510
    assert rects['back'].y == rects['panel'].bottom - 70
    assert rects['back'].height == 44


# ── Lobi menüsü (liste item metin bütçeleri + alt bant) ─────────────────────


@pytest.mark.parametrize('scale', SCALES)
@pytest.mark.parametrize('size', SIZES)
def test_pvp_lobby_menu_text_budgets(size, scale):
    game = _make_pvp(size, scale=scale)
    game._lobby_buttons.clear()
    game._draw_lobby_menu()
    rects = game._online_lobby_rects
    assert rects is not None

    assert rects['items'], 'lobi listesi boş olmamalı (fixture 2 kayıt verir)'
    for rec in rects['items']:
        # Ad: sağdaki rozete binişmez (bütçe: badge.x - 10).
        assert rec['name_rect'].right <= rec['badge_rect'].x - 6, (
            size, scale, rec['name_rect'], rec['badge_rect'])
        # Detay: sağdaki Katıl butonuna binişmez.
        assert rec['detail_rect'].right <= rec['join_rect'].x - 6, (
            size, scale, rec['detail_rect'], rec['join_rect'])
        # Zaman: doluluk barının KAYDEDİLMİŞ sol kenarına binişmez (üretim
        # sözleşmesi ölçekli s(102)'dir; ham 102 sabiti scale>1.0'da üretim
        # bütçesinden daha dar yapay bir sınır üretir — ambient dil
        # değişince t('just_now') birkaç piksel genişleyip o sınırı
        # ihlal edebiliyordu. Kayıtlı bar rect'i sözleşmenin ta kendisidir).
        if rec['time_rect'] is not None:
            assert rec['time_rect'].right <= rec['bar_rect'].x, (
                size, scale, rec['time_rect'], rec['bar_rect'])
        assert rec['join_rect'].right <= rec['item_rect'].right

    # Alt bant: durum satırları + Steam ID ekran içinde kalır.
    for r in rects['status_line_rects']:
        assert _screen_rect(size).contains(r), (size, scale)
    assert _screen_rect(size).contains(rects['steam_id_rect']), (size, scale)


@pytest.mark.parametrize('scale', SCALES)
@pytest.mark.parametrize('size', SIZES)
def test_coop_lobby_menu_text_budgets(size, scale):
    game = _make_coop(size, scale=scale)
    game._lobby_buttons.clear()
    game._draw_lobby_menu()
    rects = game._coop_lobby_rects
    assert rects is not None

    assert rects['items'], 'lobi listesi boş olmamalı (fixture 2 kayıt verir)'
    for rec in rects['items']:
        assert rec['name_rect'].right <= rec['badge_rect'].x - 6, (
            size, scale, rec['name_rect'], rec['badge_rect'])
        assert rec['detail_rect'].right <= rec['join_rect'].x - 6, (
            size, scale, rec['detail_rect'], rec['join_rect'])
        # Zaman: PvP ile aynı sözleşme — doluluk barının kaydedilmiş sol
        # kenarına binişmez (ölçekli bütçe; bkz. pvp varyantındaki not).
        if rec['time_rect'] is not None:
            assert rec['time_rect'].right <= rec['bar_rect'].x, (
                size, scale, rec['time_rect'], rec['bar_rect'])
        assert rec['join_rect'].right <= rec['item_rect'].right

    for r in rects['status_line_rects']:
        assert _screen_rect(size).contains(r), (size, scale)
    assert _screen_rect(size).contains(rects['steam_id_rect']), (size, scale)


def test_long_lobby_names_get_ellipsized_not_overflowing():
    """Uzun TR ad (host adı) bütçeyi aşarsa '...' ile kısalır; taşmaz.

    ASCII '...' — emoji yasak (CLAUDE.md); test_p0/p1_screen_containment
    idyomunu izler.
    """
    game = _make_pvp((800, 480))
    game._lobby_buttons.clear()
    game._draw_lobby_menu()
    first = game._online_lobby_rects['items'][0]
    assert first['name_rect'].width < 600  # 40+ karakterlik ad artık sığar
    assert first['name_rect'].right <= first['badge_rect'].x - 6

    game = _make_coop((800, 480))
    game._lobby_buttons.clear()
    game._draw_lobby_menu()
    first = game._coop_lobby_rects['items'][0]
    assert first['name_rect'].width < 600
    assert first['name_rect'].right <= first['badge_rect'].x - 6


def test_waiting_screen_status_wraps_to_at_most_two_lines():
    """Uzun TR durum mesajı 2 satıra sarılır (tek satıra sıkışıp taşmaz)."""
    game = _make_pvp((1280, 720))
    game._draw_waiting_screen()
    rects = game._online_waiting_rects
    assert 1 <= len(rects['status_line_rects']) <= 2

    game = _make_coop((1280, 720))
    game._draw_waiting_screen()
    rects = game._coop_waiting_rects
    assert 1 <= len(rects['status_line_rects']) <= 2


# ── Kaynak sözleşmeleri (sözleşme pin'leri) ──────────────────────────────────


def _source(module):
    return pathlib.Path(module.__file__).read_text(encoding='utf-8')


def test_pvp_source_contract_pins():
    src = _source(pvp_module)
    # Akış merdiveni (kuantalı küçültme) bekleme ekranında mevcut.
    assert 'for flow in (1.0, 0.88, 0.76, 0.64, 0.52):' in src
    # Güvenli alan + bütçe yardımcıları kullanımda.
    assert 'get_render_safe_rect' in src
    assert 'wrap_text_limited' in src
    assert 'ellipsize_text' in src


def test_coop_source_contract_pins():
    src = _source(coop_module)
    assert 'for flow in (1.0, 0.88, 0.76, 0.64, 0.52):' in src
    assert 'get_render_safe_rect' in src
    assert 'wrap_text_limited' in src
    assert 'ellipsize_text' in src
    # Dar panelde 3 yatay buton sığmazsa dikey istif devreye girer.
    assert 'stack_buttons = pw < s(448)' in src
    # Geri butonu bottom-up planlanır (panel dibinden yukarı) — örtüşme
    # yasağının yapısal garantisi.
    assert 'panel.bottom - back_bottom_margin - back_h' in src
