#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FAZ A9 — UI capture matrisi koşucusu (dummy driver altında).

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A9 madde 2'nin capture ayağı:
her (çözünürlük × preset × dil × ekran) hücresi için bir kez kur-çiz-sun,
pencere-seviyesi PNG + geometri/rect telemetry JSON'u üret.

  - PNG'ler GÖRSEL DESTEKTİR: asıl fail-fast doğrulama rect/telemetry
    (JSON) + compare_ui_captures.py ölçümleridir (A0 aracı).
  - Ayarlar ekranı üçlemesi (initial → 100→125 → 125→100) S2/S3'ün canlı
    preset geçişini gerçek instance üzerinde `_cycle_selector` ile üretir
    (FAZ A4 transaction'ının birebir yolu); her adım KENDİ kaydını
    (draw + flip + PNG + geometri anlık görüntüsü) alır.
  - Her ekran ailesinden ÖNCE combo geometrisi taze kurulur ve SONRA
    sökülür: settings üçlemesi canvas'ı değiştirdiğinden, bayat canvas
    referansına çizmek + flip'te eski canvas'i yeniden blit etmek
    (duman testinde tüm PNG'lerin birebir aynı çıkması) engellenir.
  - Kurulamayan ekran (mayın/kirli ortam) rapora dürüstçe yazılır —
    sessiz atlama YOKTUR.
  - Software backend altında koşar. SDL2/GL backend gerçek donanım ister
    (kılavuz D.6 9.2 manuel matrisi — kullanıcı koşusu).

Kullanım:
    py -3 tools/capture_ui_matrix.py                          # temsilci dilim
    py -3 tools/capture_ui_matrix.py --res all --preset all --lang tr,en
    py -3 tools/capture_ui_matrix.py --screens game_over_pvp,card_select --res 3840x2160

Çıktı:
    <out>/<family>[_<variant>]_<res>_<preset>_<lang>.png
    <out>/report.json   (geometri + rect + süre + hata kayıtları)
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import os

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame  # noqa: E402

import platform_utils  # noqa: E402
from localization import set_language  # noqa: E402

# D.5 A9 matrisi: çözünürlükler + presetler + diller.
ALL_RESOLUTIONS = (
    (1280, 720), (1280, 800), (1366, 768), (1600, 900), (1920, 1080),
    (2560, 1440), (2560, 1600), (3440, 1440), (3840, 2160),
)
ALL_PRESETS = ('compact', 'normal', 'large', 'huge', 'massive', 'double')
ALL_LANGS = ('tr', 'en', 'ru')

# Temsilci varsayılan dilim (tam süpürme: --res all --preset all).
DEFAULT_RESOLUTIONS = ('1920x1080', '3840x2160', '3440x1440', '1280x800')
DEFAULT_PRESETS = ('normal', 'large', 'double')
DEFAULT_LANGS = ('tr', 'en', 'ru')

SCREEN_FAMILIES = (
    'settings',          # üçleme: initial / cycle_up_* / cycle_back_* (S2/S3)
    'game_over_pvp',     # S4 (pvp/coop varyantları)
    'game_over_coop',    # S4
    'game_over_campaign',  # S4 — asıl FAILED overlay (orijinal görüntünün ekranı)
    'level_select',      # S7
    'main_menu',         # S8-S10
    'card_select',       # S5
    'gameplay',          # S6
)


# ---------------------------------------------------------------------------
# Kurulum/söküm yardımcıları. DERS (duman testinden): her yeni kurulumdan
# ÖNCE eski canvas sökülür ve canvas referansı her seferinde TAZE alınır —
# patch'li get_surface/kalıcı referans stale canvas döndürür.
# ---------------------------------------------------------------------------
def _teardown_canvas() -> None:
    try:
        platform_utils._teardown_virtual_canvas()
    except Exception:
        pass
    try:
        platform_utils._canvas_state = platform_utils.CANVAS_STATE_INACTIVE
        platform_utils._canvas_state_backend = None
    except Exception:
        pass


def _setup_canvas(res: tuple[int, int], preset: str):
    """Pencereyi kur, preset'i uygula, GÜNCEL canvas'ı döndür."""
    from ui_scaling import set_ui_scale_preset, get_ui_scale_multiplier

    pygame.display.set_mode(res)
    _teardown_canvas()
    set_ui_scale_preset(preset)
    real = pygame.display.get_surface()
    canvas = platform_utils.setup_virtual_canvas(real, get_ui_scale_multiplier())
    return real, canvas


def _geometry_snapshot() -> dict:
    g = platform_utils.get_render_geometry(None)
    return {
        'backend': g.backend,
        'canvas_size': list(g.canvas_size),
        'window_size': list(g.window_size),
        'presentation_rect': list(g.presentation_rect),
        'safe_rect': list(g.safe_rect),
        'scale': round(g.scale, 6),
        'ui_preset': g.ui_preset,
        'generation': g.generation,
    }


def _rect_to_list(rect):
    if rect is None:
        return None
    try:
        return [int(rect.x), int(rect.y), int(rect.w), int(rect.h)]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Ekran ailesi yakalayıcıları. Sözleşme: fn(canvas, lang, record) — aile
# çizer ve HER görsel adımda record(variant, extra) çağırır; record
# flip + pencere yüzeyi PNG kaydı + geometri anlık görüntüsü üretir.
# Kalıplar: test_p0 (game-over), test_p1 (level select),
# settings üçlemesi (demo uygulama zinciri — bkz. capture_settings),
# test_mystery_* (kart).
# ---------------------------------------------------------------------------
def capture_settings(canvas, lang: str, record) -> None:
    """Ayarlar ekranı ÜÇLEMESİ: S2/S3 canlı preset geçişi (demo yolu).

    DEMO UYARLAMASI (v2'den bilinçli fark): demo ayarlar ekranında preset
    seçicisi YOKTUR — satır tab içerikten kaldırıldı ve
    _cycle_selector('ui_scale_preset') no-op'tur (settings_screen_tabbed.py
    içindeki 'ui_scale_preset' dalı). v2'nin FAZ A4 UI döngü yolu demo'ya
    taşınmadı: demo kısıtıdır, ürün kodu değiştirilmez. Ölçüm bu yüzden
    demo'nun gerçek uygulama zincirini sürer — SettingsManager
    _sync_ui_scale_preset'ın preset'i kurduğu çekirdek adımların birebir
    aynısı: set_ui_scale_preset (font/text/layout cache'leri TEK çağrıda
    düşer) → rebuild_virtual_canvas (yeni tuval + geometri kuşağı) →
    ekran yeni ölçekte yeniden düzen (font imza sıfır + responsive
    metrikler + sekme içeriği). Tek gerçek instance üzerinde
    taban→+1→taban; her adımda draw + record (flip + kayıt).

    inst._set_value yamalıdır: demo ekranının preset'i UI üzerinden
    YAZMADIĞI da kanıtlanır (set_value_calls [] kalır — kısıt kanıtı).
    Ölçüm diske yazmaz: preset değişimi ui_scaling global'i üzerinden
    uygulanır, SettingsManager'a yazılmaz.

    DETERMİNİZM: Matris koşusu CLI'dan istenen taban preset'ten başlamalı:
    ui_scaling'in güncel preset'i (run_matrix'in _setup_canvas ile
    ayarladığı) tabana sabitlenir; varyant adları döngülenen preset'lerden
    üretilir (taban 'normal' için up_large/back_normal).
    """
    from settings_manager import SettingsManager
    import settings_screen_tabbed
    from ui_scaling import (
        UI_SCALE_PRESETS, get_ui_scale_preset, set_ui_scale_preset,
        get_ui_scale_multiplier,
    )

    sm = SettingsManager()
    inst = settings_screen_tabbed.TabbedSettingsScreen(canvas, None, sm)
    base = get_ui_scale_preset()
    if base in UI_SCALE_PRESETS:
        inst.ui_scale_preset = base
    idx = UI_SCALE_PRESETS.index(base) if base in UI_SCALE_PRESETS else 0
    up_preset = UI_SCALE_PRESETS[(idx + 1) % len(UI_SCALE_PRESETS)]
    calls: list = []
    inst._set_value = lambda key, value: calls.append((key, value))

    def _apply_preset(preset: str) -> None:
        """Demo uygulama zinciri: preset → tuval → düzen, tek transaction."""
        set_ui_scale_preset(preset)
        inst.ui_scale_preset = preset
        try:
            new_canvas = platform_utils.rebuild_virtual_canvas(
                get_ui_scale_multiplier())
        except Exception as exc:
            # v2 paritesi: sessiz yutma teşhis kusuru — rebuild başarısızsa
            # kayda geçer, transaction'ın kalanı yine işletilir.
            print(f"[A9-demo] Virtual canvas rebuild basarisiz: {exc!r}")
            new_canvas = None
        if new_canvas is not None and new_canvas is not inst.screen:
            inst.screen = new_canvas
        # FAZ A4 (S2/S3) v2 paritesi: preset geçişi tek transaction —
        # invalidate → rebuild → clamp. Font ölçek imzası sıfırlanır;
        # responsive metrikler ve sekme içeriği yeni ölçekte anında
        # yeniden üretilir; scroll/seçim yeni içerik yüksekliğine
        # clamp'lanır (swap'ten sonraki İLK karede karışık
        # font/rect/scroll görülmez).
        inst._font_scale_signature = None
        inst._apply_responsive_metrics()
        inst._rebuild_tab_content()
        inst._ensure_visible()

    inst.draw()
    record('initial', {'set_value_calls': [list(c) for c in calls],
                       'selector_base': base})

    calls.clear()
    _apply_preset(up_preset)
    inst.draw()
    record(f'cycle_up_{up_preset}', {'set_value_calls': [list(c) for c in calls]})

    calls.clear()
    _apply_preset(base)
    inst.draw()
    record(f'cycle_back_{base}', {'set_value_calls': [list(c) for c in calls]})


def capture_game_over_pvp(canvas, lang: str, record) -> None:
    from pvp_game import PvPGame
    from board import Board
    import pvp_game as pvp_module

    game = PvPGame.__new__(PvPGame)
    game.screen = canvas
    game.window_width, game.window_height = canvas.get_size()
    game.player1_name = "Ada"
    game.player2_name = "Bora"
    game.board1 = Board()
    game.board2 = Board()
    game.board1.score = 48000
    game.board2.score = 35000
    game.board1.lines_cleared = 42
    game.board2.lines_cleared = 31
    game.winner = 1
    game.match_end_reason = "elimination"
    game.p1_eliminated = False
    game.p2_eliminated = True
    game._game_over_restart_rect = None
    game._game_over_menu_rect = None
    pvp_module.get_mouse_pos = lambda: (-9999, -9999)

    game._draw_game_over_screen()
    record('default', {
        'rects': {
            'restart': _rect_to_list(game._game_over_restart_rect),
            'menu': _rect_to_list(game._game_over_menu_rect),
        },
    })


def capture_game_over_coop(canvas, lang: str, record) -> None:
    from coop_game import CoopGame
    import coop_game as coop_module

    game = CoopGame.__new__(CoopGame)
    game.screen = canvas
    game.window_width, game.window_height = canvas.get_size()
    game._game_over_snapshot = {
        "team_score": 1234, "total_lines": 40, "level": 3,
        "elapsed_ms": 65000, "p1_pct": 55, "p2_pct": 45,
        "p1_text": "P1", "p2_text": "P2",
    }
    # Fade animasyonu tamamlanmış kabul (steady görüntü).
    game._game_over_start_time = pygame.time.get_ticks() - 10_000
    game._game_over_peek_active = False
    game.user_manager = None
    game._game_over_restart_rect = None
    game._game_over_exit_rect = None
    coop_module.get_mouse_pos = lambda: (9999, 9999)

    game._draw_game_over_screen()
    record('default', {
        'rects': {
            'restart': _rect_to_list(game._game_over_restart_rect),
            'exit': _rect_to_list(game._game_over_exit_rect),
        },
    })


def capture_level_select(canvas, lang: str, record) -> None:
    from campaign.level_select import CampaignLevelSelect

    selector = CampaignLevelSelect(canvas)
    selector.draw()
    # S7 rect-düzeyi kanıtı: PLAY footer (safe içi + 24px marj sözleşmesi)
    # ve ortak Geri butonu (bilinçli 16/16 canvas marjı — paylaşımlı
    # chrome, level_select.py:22-24 muafiyet yorumu; coop kardeş ekranla
    # aynı marj). Rect'ler canvas uzayındadır; report geometry.safe_rect
    # de canvas uzayındır — karşılaştırma aynı uzayda yapılır.
    record('default', {
        'rects': {
            'play': _rect_to_list(selector.play_button),
            'back': _rect_to_list(selector.back_button),
        },
    })


def capture_main_menu(canvas, lang: str, record) -> None:
    from menu import Menu

    menu = Menu(canvas, user_manager=None, settings_manager=None)
    menu.draw()
    record('default', {})


def capture_card_select(canvas, lang: str, record) -> None:
    from game_modes_extra import MysteryCardUI
    from ui_theme import UIFonts

    ui = MysteryCardUI()
    ui.fade_alpha = 255  # overlay görünür (animasyon bitmiş)
    fonts = {
        'panel_header': UIFonts.get(28, bold=True),
        'medium': UIFonts.get(22),
        'small': UIFonts.get(18),
        'desc': UIFonts.get(18),
    }
    cards = [
        {
            'id': 'sample_common', '_group_id': 'g1', 'rarity': 'common',
            'tier': 1, 'title': 'Kart Baslik', 'description': 'Kart aciklamasi',
            'base': 1, 'value_range': (1, 1), 'tag': 'Common',
            'icon': '?', 'color': (120, 120, 130),
        },
        {
            'id': 'sample_rare', '_group_id': 'g2', 'rarity': 'rare',
            'tier': 2, 'title': 'Nadir Kart', 'description': 'Nadir aciklama',
            'base': 2, 'value_range': (1, 2), 'tag': 'Rare',
            'icon': '!', 'color': (80, 180, 255),
        },
        {
            'id': 'sample_epic', '_group_id': 'g3', 'rarity': 'epic',
            'tier': 1, 'title': 'Epik Kart', 'description': 'Epik aciklama',
            'base': 3, 'value_range': (2, 3), 'tag': 'Epic',
            'icon': '*', 'color': (180, 80, 255),
        },
        {
            'id': 'sample_legend', '_group_id': 'g4', 'rarity': 'legendary',
            'tier': 1, 'title': 'Efsane Kart', 'description': 'Efsane aciklama',
            'base': 5, 'value_range': (4, 5), 'tag': 'Legendary',
            'icon': '#', 'color': (255, 180, 0),
        },
    ]
    w, h = canvas.get_size()
    ui.draw_selection_overlay(
        canvas, w, h, fonts, cards, 'Kart secimi yapin',
    )
    record('default', {})


def capture_gameplay(canvas, lang: str, record) -> None:
    from game import Game
    from settings_manager import SettingsManager

    game = Game(
        'Normal', sound_enabled=False, effects_enabled=False,
        screen=canvas, fullscreen=False, settings_manager=SettingsManager(),
    )
    game.draw()
    record('default', {})


def capture_game_over_campaign(canvas, lang: str, record) -> None:
    """S4'ün asıl ekranı: kampanya level-FAILED overlay (gerçek font yolu).

    Orijinal "Quadrix_game over scaling problem.jpg" FAILED başlıklı bu
    overlay'dir — kapanış ölçümü pvp/coop vekiliyle değil birebir ekranla
    yapılır. Kurulum kalıbı test_phase6_campaign_modal_ui_scaling.py'den
    (animation dict + _failed_buttons rect'leri); font/retro_style GERÇEK
    (stub yok). Hover belirsizliğini önlemek için fare patch'i pvp/coop
    aileleriyle aynı.
    """
    from campaign import campaign_ui

    campaign_ui.get_mouse_pos = lambda: (-9999, -9999)
    effects = campaign_ui.CampaignUIEffects()
    effects.level_failed_animation = {'time': 1.0}
    effects.draw_level_failed_overlay(canvas, reason='board overflow')
    retry = effects._failed_buttons.get('retry')
    menu = effects._failed_buttons.get('menu')
    record('default', {'rects': {
        'retry': list(retry) if retry is not None else None,
        'menu': list(menu) if menu is not None else None,
    }})


CAPTURES = {
    'settings': capture_settings,
    'game_over_pvp': capture_game_over_pvp,
    'game_over_coop': capture_game_over_coop,
    'game_over_campaign': capture_game_over_campaign,
    'level_select': capture_level_select,
    'main_menu': capture_main_menu,
    'card_select': capture_card_select,
    'gameplay': capture_gameplay,
}


# ---------------------------------------------------------------------------
# Ana döngü
# ---------------------------------------------------------------------------
def _parse_res_list(spec: str) -> tuple[tuple[int, int], ...]:
    if spec == 'all':
        return ALL_RESOLUTIONS
    result = []
    for part in spec.split(','):
        part = part.strip().lower().replace('×', 'x')
        if not part:
            continue
        w, h = part.split('x')
        result.append((int(w), int(h)))
    return tuple(result)


def _parse_str_list(spec: str, all_values: tuple[str, ...]) -> tuple[str, ...]:
    if spec == 'all':
        return all_values
    return tuple(p.strip() for p in spec.split(',') if p.strip()) or all_values


def run_matrix(
    resolutions, presets, langs, families, out_dir: pathlib.Path,
) -> dict:
    pygame.init()
    pygame.font.init()
    if not pygame.display.get_init():
        pygame.display.init()

    # DETERMİNİZM (yalnız araç çalışma süresi — ürün kodu değişmez):
    # SettingsManager kurulumu kayıtlı kullanıcı profilindeki preset'i
    # ui_scaling'e senkronlar (_sync_ui_scale_preset). Draw yolları
    # GamepadManager tekil örneği üzerinden tembel SettingsManager kurar
    # (pvp game-over duman testinde preset 'normal' → 'large' ezildi).
    # Matrisin --preset boyutu kullanıcı makinesindeki kayıtlı profile
    # değil CLI'a bağlı olmalı; senkron nötrleştirilir. settings üçlemesi
    # kendi canlı geçişini (_cycle_selector → ui_scaling) yine üretir.
    from settings_manager import SettingsManager
    SettingsManager._sync_ui_scale_preset = lambda self: None

    # DETERMİNİZM (yalnız araç çalışma süresi — ürün kodu değişmez):
    # Ayarlar ekranı draw() içinde falling-blocks arka plan katmanını
    # gerçek zamanla ilerletir (background_effects.FallingBlocksLayer:
    # random şekil/renk, pygame.time.get_ticks tabanlı düşüş, düşen blok
    # üstte yeniden doğar). Milisaniyeler arayla alınan iki yakalama bu
    # yüzden piksel bazında farkılır; içerik bbox kenar ölçümlerine
    # animasyon gürültüsü bindirir (S3 görsel incelemesinde S/T
    # parçalarının yer değiştirdiği piksel-diff ile doğrulandı).
    # Ölçüm aleti düzen sinyalini izole etmek için katmanı dondurur.
    import background_effects
    background_effects.FallingBlocksLayer.update = lambda self, screen: None
    background_effects.FallingBlocksLayer.draw = lambda self, screen: None

    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        'tool': 'capture_ui_matrix.py',
        'backend_note': (
            'Software canvas (SDL dummy). SDL2/GL backendler gercek '
            'donanim ister — kilavuz D.6 9.2 manuel matrisi.'
        ),
        'combos': [],
    }

    total = 0
    failed = 0
    for res in resolutions:
        for preset in presets:
            for lang in langs:
                if not set_language(lang):
                    print(f"[UYARI] dil kurulamadi: {lang}")
                for family in families:
                    fn = CAPTURES[family]
                    entry = {
                        'res': list(res), 'preset': preset, 'lang': lang,
                        'family': family,
                        'captures': [],
                    }
                    t0 = time.perf_counter()
                    try:
                        # Her aileden önce combo geometrisini TAZE kur:
                        # settings üçlemesi önceki ailenin canvas'ını
                        # değiştirmiş olabilir.
                        real, canvas = _setup_canvas(res, preset)
                    except Exception as exc:
                        entry['setup_error'] = f"{type(exc).__name__}: {exc}"
                        report['combos'].append(entry)
                        failed += 1
                        continue

                    entries: list = []

                    def record(variant: str, extra: dict | None = None) -> None:
                        """draw sonrası: sun (flip) + pencere PNG + geometri."""
                        pygame.display.flip()
                        window_surf = (
                            platform_utils._real_display_surface or real
                        )
                        name = (
                            f"{family}_{variant}_{res[0]}x{res[1]}"
                            f"_{preset}_{lang}"
                        )
                        png_path = out_dir / f"{name}.png"
                        try:
                            pygame.image.save(window_surf, str(png_path))
                            png_name = png_path.name
                        except Exception as exc:
                            png_name = None
                            entries.append({
                                'variant': variant, 'png': None,
                                'error': f"kayit basarisiz: {exc}",
                                'geometry': _geometry_snapshot(),
                            })
                            return
                        entries.append({
                            'variant': variant,
                            'png': png_name,
                            'geometry': _geometry_snapshot(),
                            'extra': extra or {},
                        })

                    try:
                        fn(canvas, lang, record)
                    except Exception as exc:
                        traceback.print_exc()
                        entries.append({
                            'variant': 'none', 'png': None,
                            'error': f"{type(exc).__name__}: {exc}",
                            'geometry': _geometry_snapshot(),
                        })

                    entry['draw_ms'] = round((time.perf_counter() - t0) * 1000.0, 2)
                    entry['captures'] = entries
                    ok = sum(1 for e in entries if e.get('png'))
                    total += ok
                    if not entries or ok == 0:
                        failed += 1
                    report['combos'].append(entry)

                    # Sonraki aile temiz geometriyle başlasın.
                    _teardown_canvas()

    report['summary'] = {
        'total_captures': total,
        'failed': failed,
    }
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='FAZ A9 UI capture matrisi (dummy driver).',
    )
    parser.add_argument(
        '--res', default=','.join(DEFAULT_RESOLUTIONS),
        help="Virgulle ayrilmis cozunurlukler (1920x1080) veya 'all'.",
    )
    parser.add_argument(
        '--preset', default=','.join(DEFAULT_PRESETS),
        help="Virgulle ayrilmis presetler veya 'all'.",
    )
    parser.add_argument(
        '--lang', default=','.join(DEFAULT_LANGS),
        help="Virgulle ayrilmis diller veya 'all'.",
    )
    parser.add_argument(
        '--screens', default='all',
        help="Virgulle ayrilmis ekran aileleri veya 'all'.",
    )
    parser.add_argument('--out', default='captures_a9', help='Cikti dizini.')
    parser.add_argument(
        '--json', default=None, help='Rapor JSON yolu (varsayilan <out>/report.json).',
    )
    args = parser.parse_args(argv)

    resolutions = _parse_res_list(args.res)
    presets = _parse_str_list(args.preset, ALL_PRESETS)
    langs = _parse_str_list(args.lang, ALL_LANGS)
    if args.screens == 'all':
        families = SCREEN_FAMILIES
    else:
        families = _parse_str_list(args.screens, SCREEN_FAMILIES)
        unknown = [f for f in families if f not in CAPTURES]
        if unknown:
            parser.error(f"bilinmeyen ekran ailesi: {unknown}")

    out_dir = pathlib.Path(args.out)
    report = run_matrix(resolutions, presets, langs, families, out_dir)

    json_path = pathlib.Path(args.json) if args.json else out_dir / 'report.json'
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8',
    )

    summary = report['summary']
    print(
        f"[capture_ui_matrix] {summary['total_captures']} kayit, "
        f"{summary['failed']} basarisiz -> {json_path}"
    )
    return 1 if summary['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
