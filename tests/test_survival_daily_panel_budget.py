# -*- coding: utf-8 -*-
"""P1-4/P1-5 (Quadrix_Tum_Ekranlar_Olcekleme_Denetim_Raporu):
Survival + Daily Challenge panel dikey içerik bütçesi.

Rapor kök nedenleri:
- P1-4: Survival paneli içerik ritmini sabit s() ile (~s(340)) çiziyor, panel
  zeminini ise active_height tabanlı formül kısıtlıyordu → %175/%200 preset
  + kısa pencere yüksekliğinde son bloklar çerçevenin altına taşıyordu.
  Düzeltme: measure-first blok planı (gerçek font yükseklikleri), kuantalı
  flow ladder (1.0→0.52), opsiyonel blok düşürme (antivirus → enfeksiyon →
  virüs seviyesi), safe rect boyut kısıtı clamp'ten ÖNCE.
- P1-5: Daily panel yüksekliği sabit %50 ekran oranıydı; açıklama satır limiti
  sabit 3'tü. Düzeltme: içerik bütçesinden panel yüksekliği, kalan bütçeden
  dinamik açıklama satır limiti, hedef/progress + tüm blok rect'leri
  ``_daily_panel_rects`` altına kaydedilir, alt bloklar yükseklik farkındalı
  guard'larla panel tabanını aşamaz.

Ölçüm sınırı (dürüst rapor): gerçek 4K görsel doğrulama kılavuz §7'deki
manuel Windows smoke'a aittir — dummy driver altında koşulmaz. Bu dosya
plan sözleşmesini (değişmezler) ve kaynak sözleşmesini kilitler.

Kalıp: test_wide_arena_hud_scale_containment (SRC yol hazırlığı + dummy
sürücüler + gerçek modül importu; __new__ bare-instance idyomu; set_mode
YOK — düz Surface blit hedefi, SDL dummy vsync AV riski yoktur).
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

import game_modes_advanced as advanced_module
from ui_scaling import set_ui_scale_preset

if not pygame.font.get_init():
    pygame.font.init()


# Raporun istediği senaryo matrisi: 5 çözünürlük x 4 preset.
RESOLUTIONS = [
    (800, 480),
    (1024, 600),
    (1280, 720),
    (1920, 1080),
    (3840, 2160),
]
PRESETS = ["normal", "large", "massive", "double"]

SURVIVAL_MANDATORY_BLOCKS = (
    'title', 'separator', 'time_label', 'time_value',
    'consumed_label', 'consumed_bar',
)
SURVIVAL_OPTIONAL_GROUPS = {'antivirus', 'infection', 'virus_level'}


def _make_survival_mode(screen: pygame.Surface) -> advanced_module.SurvivalMode:
    """Bare SurvivalMode: _draw_survival_panel yalnız statik/ölçülebilir
    yardımcıları ve bu attr'ları kullanır (phase8 bare-instance idyomu)."""
    mode = advanced_module.SurvivalMode.__new__(advanced_module.SurvivalMode)
    mode.screen = screen
    mode.window_width, mode.window_height = screen.get_size()
    mode.board = SimpleNamespace(score=4000)
    mode.survival_time = 120000  # time_left >= 60000 → flash yolu yok
    mode.consumed_count = 5
    mode.virus_level = 3
    mode.infected_blocks = {(1, 1): 0, (2, 2): 1000}
    mode.max_infected = 15
    mode.last_antivirus_score = 0
    mode.get_board_offset = lambda: (screen.get_width() // 2, 40)
    return mode


def _default_challenge() -> dict:
    return {
        'id': 'test-daily',
        'name': 'Günlük Görev',
        'description': 'Kısa bir günlük açıklaması.',
        'briefing': 'Kısa brifing.',
        'target_score': 5000,
        'objective_line': '5000 puana ulaş',
        'rule_line': 'Kural satırı',
        'fail_line': 'Başarısızlık koşulu',
        'reward_line': 'Ödül satırı',
        'bonus': 1.5,
        'adaptive_scale': 1.2,
    }


def _fake_user_manager() -> SimpleNamespace:
    return SimpleNamespace(
        get_daily_status=lambda: {'completed': False, 'fails': 1, 'streak': 4},
    )


def _make_daily_mode(screen: pygame.Surface, challenge: dict, **overrides):
    mode = advanced_module.DailyChallengeMode.__new__(advanced_module.DailyChallengeMode)
    mode.screen = screen
    mode.window_width, mode.window_height = screen.get_size()
    mode.challenge = dict(challenge)
    mode.board = SimpleNamespace(score=1500, lines_cleared=7, combo=2)
    mode.get_board_offset = lambda: (screen.get_width() // 2, 24)
    mode.challenge_completed = overrides.pop('challenge_completed', False)
    mode.side_effects = overrides.pop('side_effects', [])
    mode.user_manager = overrides.pop('user_manager', None)
    mode.max_mistakes = overrides.pop('max_mistakes', 0)
    mode.mistakes_made = overrides.pop('mistakes_made', 0)
    for key, value in overrides.items():
        setattr(mode, key, value)
    return mode


def _assert_survival_containment(mode, width: int, height: int) -> dict:
    rects = mode._survival_hud_rects
    panel = rects['panel']
    assert pygame.Rect(0, 0, width, height).contains(panel), (
        f"panel ekrana taşıyor: {panel} ekran {(width, height)} "
        f"flow={rects['flow']} dropped={rects['dropped']}"
    )
    # Çekirdek değişmezi: içerik panel tabanını aşamaz (P1-4).
    assert rects['content_bottom'] <= panel.bottom + 1, (
        f"içerik panel tabanını aştı: bottom={rects['content_bottom']} "
        f"panel.bottom={panel.bottom} flow={rects['flow']} dropped={rects['dropped']}"
    )
    for name, block_rect in rects['blocks'].items():
        assert panel.contains(block_rect), (
            f"blok '{name}' panel dışında: {block_rect} panel {panel}"
        )
    for name in SURVIVAL_MANDATORY_BLOCKS:
        assert name in rects['blocks'], f"zorunlu blok '{name}' düştü"
    assert set(rects['dropped']) <= SURVIVAL_OPTIONAL_GROUPS
    assert 0.52 <= rects['flow'] <= 1.0
    return rects


# ── P1-4: Survival paneli — çözünürlük x preset matrisi ─────────────────────


@pytest.mark.parametrize("width,height", RESOLUTIONS)
@pytest.mark.parametrize("preset", PRESETS)
def test_survival_panel_content_fits_vertical_budget(width, height, preset):
    """Rapor matrisi: her (çözünürlük, preset) ikilisinde içerik bütçede kalır.

    Eski kodda 800x480/1024x600/1280x720 double ve 800x480 massive
    senaryolarında içerik (≈s(358)) panel zeminini (≤active_height payı)
    aşıyordu; yeni ölçüm tabanlı ladder bu senaryolarda flow küçültür veya
    opsiyonel blok düşürür — asla taşmaz.
    """
    screen = pygame.Surface((width, height), pygame.SRCALPHA)
    mode = _make_survival_mode(screen)
    set_ui_scale_preset(preset)
    try:
        mode._draw_survival_panel()
    finally:
        set_ui_scale_preset("normal")

    _assert_survival_containment(mode, width, height)


def test_survival_panel_baseline_1366x768_keeps_full_content():
    """Referans senaryo (scale=1.0): hiçbir blok düşmez, ladder en fazla tek
    adım iner — baseline'da içerik kaybı bir regresyondur."""
    screen = pygame.Surface((1366, 768), pygame.SRCALPHA)
    mode = _make_survival_mode(screen)
    mode._draw_survival_panel()

    rects = _assert_survival_containment(mode, 1366, 768)
    assert rects['dropped'] == ()
    assert rects['flow'] >= 0.88
    for name in ('level_label', 'level_boxes', 'infect_label', 'infect_bar',
                 'av_label', 'av_bar'):
        assert name in rects['blocks']


def test_survival_av_info_does_not_overlap_label():
    """Wide Arena C1 dersi: sağdan hizalanan antivirus bilgisi soldaki
    etiketle aritmetik olarak çakışmamalı."""
    screen = pygame.Surface((1366, 768), pygame.SRCALPHA)
    mode = _make_survival_mode(screen)
    mode._draw_survival_panel()

    blocks = mode._survival_hud_rects['blocks']
    if 'av_label' in blocks and 'av_info' in blocks:
        assert not blocks['av_label'].colliderect(blocks['av_info']), (
            f"av_label {blocks['av_label']} av_info {blocks['av_info']} çakışıyor"
        )


def test_survival_panel_respects_render_safe_rect(monkeypatch):
    """Safe rect varsa panel tamamen onun içinde kalır (boyut kısıtı +
    konum clamp'i birlikte)."""
    screen = pygame.Surface((1920, 1080), pygame.SRCALPHA)
    mode = _make_survival_mode(screen)
    safe = pygame.Rect(200, 100, 1000, 500)
    monkeypatch.setattr(
        advanced_module, 'get_render_safe_rect', lambda surf: pygame.Rect(safe))
    mode._draw_survival_panel()

    rects = mode._survival_hud_rects
    assert safe.contains(rects['panel']), f"panel safe rect dışında: {rects['panel']}"
    assert rects['content_bottom'] <= rects['panel'].bottom + 1


def test_survival_panel_small_safe_rect_engages_size_cap(monkeypatch):
    """Rect.clamp küçültmez: dar safe rect'te BOYUT kısıtı clamp'ten önce
    devreye girmeli; zorunlu bloklar yine çizilmeli."""
    screen = pygame.Surface((1920, 1080), pygame.SRCALPHA)
    mode = _make_survival_mode(screen)
    safe = pygame.Rect(0, 0, 300, 260)
    monkeypatch.setattr(
        advanced_module, 'get_render_safe_rect', lambda surf: pygame.Rect(safe))
    mode._draw_survival_panel()

    rects = mode._survival_hud_rects
    assert safe.contains(rects['panel']), f"panel safe rect dışında: {rects['panel']}"
    assert rects['panel'].width <= safe.width
    assert rects['panel'].height <= safe.height
    for name in SURVIVAL_MANDATORY_BLOCKS:
        assert name in rects['blocks']
    assert rects['content_bottom'] <= rects['panel'].bottom + 1


def test_survival_panel_plan_is_repeatable_and_stable():
    """Aynı girdi iki kare üst üste aynı rect kümesini üretir (önbellek
    kararlılığı; kare-başı Surface tahsisi yasağının gözlemlenebilir hâli)."""
    screen = pygame.Surface((1366, 768), pygame.SRCALPHA)
    mode = _make_survival_mode(screen)
    mode._draw_survival_panel()
    first = {name: rect.copy() for name, rect in mode._survival_hud_rects['blocks'].items()}
    mode._draw_survival_panel()
    second = mode._survival_hud_rects['blocks']

    assert set(first) == set(second)
    for name, rect in first.items():
        assert rect == second[name], f"blok '{name}' kareler arası kararsız"


# ── P1-5: Daily paneli — içerik bütçesi + dinamik açıklama limiti ───────────


@pytest.mark.parametrize("width,height", RESOLUTIONS)
@pytest.mark.parametrize("preset", PRESETS)
def test_daily_panel_content_fits_vertical_budget(width, height, preset):
    """Panel ekranda kalır, içerik panel tabanını aşmaz, çekirdek bloklar
    (başlık/isim/hedef/progress) her senaryoda çizilir."""
    screen = pygame.Surface((width, height), pygame.SRCALPHA)
    mode = _make_daily_mode(screen, _default_challenge())
    set_ui_scale_preset(preset)
    try:
        mode.draw_mode_info(0, 0)
    finally:
        set_ui_scale_preset("normal")

    recorded = mode._daily_panel_rects
    panel = recorded['panel']
    assert pygame.Rect(0, 0, width, height).contains(panel), (
        f"panel ekrana taşıyor: {panel} ekran {(width, height)}"
    )
    assert recorded['content_bottom'] <= panel.bottom + 1, (
        f"içerik panel tabanını aştı: {recorded['content_bottom']} > {panel.bottom}"
    )
    for key in ('title', 'name', 'progress'):
        assert panel.contains(recorded[key]), f"'{key}' panel dışında: {recorded[key]}"
    for line_rect in recorded['desc_lines']:
        assert panel.contains(line_rect), f"açıklama satırı panel dışında: {line_rect}"


def test_daily_panel_height_is_content_driven():
    """Kısa içerik → taban 320; uzun içerik → bütçe 420'ye kadar büyür
    (eski sabit %50 ekran oranı davranışının yerini içerik bütçesi alır)."""
    screen = pygame.Surface((1920, 1080), pygame.SRCALPHA)
    lean = _default_challenge()
    lean['description'] = 'Kısa.'
    lean['briefing'] = ''
    mode = _make_daily_mode(screen, lean)
    mode.draw_mode_info(0, 0)
    assert mode._daily_panel_rects['panel'].height == 320

    rich = _default_challenge()
    rich['description'] = 'Bu cümleler panelin içerik bütçesini doldurmak için ' * 6
    rich['briefing'] = 'Brifing satırı bir. Brifing satırı iki.'
    mode = _make_daily_mode(screen, rich)
    mode.draw_mode_info(0, 0)
    assert mode._daily_panel_rects['panel'].height > 320
    assert mode._daily_panel_rects['panel'].height <= 420


def test_daily_long_description_line_limit_follows_remaining_budget():
    """Uzun açıklama: satır limiti kalan dikey bütçeden türetilir — tam
    sarmadan belirgin şekilde az ve taşma yok (eski sabit max_lines=3 değil)."""
    screen = pygame.Surface((1920, 1080), pygame.SRCALPHA)
    challenge = _default_challenge()
    challenge['description'] = 'Bu çok uzun bir günlük açıklamasıdır. ' * 30
    mode = _make_daily_mode(screen, challenge)
    mode.draw_mode_info(0, 0)

    recorded = mode._daily_panel_rects
    panel = recorded['panel']
    desc_font = advanced_module.ui_style.get_font(15, bold=False)
    inner_w = panel.width - 18 * 2
    full_lines = advanced_module.wrap_text_limited(
        challenge['description'], desc_font, inner_w)

    assert len(full_lines.lines) > 4, "kurulum: açıklama gerçekten uzun olmalı"
    assert 1 <= recorded['desc_max_lines'] < len(full_lines.lines), (
        f"satır limiti bütçeden türetilmedi: {recorded['desc_max_lines']} "
        f"vs tam sarma {len(full_lines.lines)}"
    )
    assert len(recorded['desc_lines']) == recorded['desc_max_lines']
    for line_rect in recorded['desc_lines']:
        assert panel.contains(line_rect)
    assert recorded['content_bottom'] <= panel.bottom + 1


def test_daily_completed_bonus_and_tail_blocks_render():
    """P1-5 + gizli NameError regresyonu: get_language artık fonksiyon-içi
    import. Eski kodda completed göstergesinden SONRAKİ her şey (bonus,
    kural/ödül satırları, durum/streak/adaptive) NameError ile kayboluyordu —
    çağrı yerindeki try/except sessizce yutuyordu. Doğrudan çağrı eski kodda
    patlamalıydı; yeni kod tüm kuyruk bloklarını çizer."""
    screen = pygame.Surface((1920, 1080), pygame.SRCALPHA)
    challenge = _default_challenge()
    challenge['description'] = ''
    challenge['briefing'] = 'Brif.'
    challenge['fail_line'] = ''
    challenge['reward_line'] = ''
    mode = _make_daily_mode(
        screen, challenge,
        challenge_completed=True,
        side_effects=['Efekt bir'],
        user_manager=_fake_user_manager(),
    )
    mode.draw_mode_info(0, 0)

    recorded = mode._daily_panel_rects
    panel = recorded['panel']
    assert recorded.get('completed') is not None, "completed göstergesi çizilmedi"
    assert recorded.get('bonus') is not None, "bonus çarpanı çizilmedi"
    assert recorded['details'], "kural satırı çizilmedi"
    assert recorded['status'], "günlük durum satırı çizilmedi"
    assert recorded['streak'] is not None, "streak çizilmedi"
    assert recorded['adaptive'] is not None, "adaptive göstergesi çizilmedi"
    assert recorded['content_bottom'] <= panel.bottom + 1


def test_daily_mistakes_counter_renders_when_tracked():
    """Hata sayacı bloğu (challenge_completed=False iken) çizilir —
    _blit_lines font argümanı hatasını kapsayan regresyon."""
    screen = pygame.Surface((1920, 1080), pygame.SRCALPHA)
    challenge = _default_challenge()
    challenge['description'] = ''
    challenge['briefing'] = 'Brif.'
    mode = _make_daily_mode(
        screen, challenge,
        max_mistakes=3,
        mistakes_made=1,
        user_manager=_fake_user_manager(),
    )
    mode.draw_mode_info(0, 0)

    recorded = mode._daily_panel_rects
    assert recorded['mistakes'], "hata sayacı çizilmedi"
    assert recorded['status'], "günlük durum satırı çizilmedi"
    assert recorded['content_bottom'] <= recorded['panel'].bottom + 1


def test_daily_panel_never_exceeds_screen_bottom():
    """Kısa pencere: ekran bütçesi panel alt kenarını ekranda tutar
    (taban 240 duyarlılığıyla)."""
    screen = pygame.Surface((800, 400), pygame.SRCALPHA)
    mode = _make_daily_mode(screen, _default_challenge())
    mode.draw_mode_info(0, 0)

    recorded = mode._daily_panel_rects
    panel = recorded['panel']
    assert panel.bottom <= screen.get_height() + 1, (
        f"panel alt kenarı ekranı aştı: {panel}"
    )
    assert panel.height >= 240
    assert recorded['content_bottom'] <= panel.bottom + 1


# ── Kaynak sözleşmeleri (AST-pin idyomu) ─────────────────────────────────────


def _advanced_source() -> str:
    return pathlib.Path(advanced_module.__file__).read_text(encoding='utf-8')


def test_survival_panel_uses_quantized_ladder_with_ordered_drops():
    source = _advanced_source()
    # Ölç-önce ladder: 5 basamak, üniform küçültme (game.py/Hardcore deseni).
    assert re.search(r"for flow_candidate in \(1\.0, 0\.88, 0\.76, 0\.64, 0\.52\):", source)
    assert "optional_groups = ('antivirus', 'infection', 'virus_level')" in source
    # Zorunlu bloklar asla düşmez: fallback yalnız opsiyonel grubu düşürür.
    assert "_build_content_plan(0.52, frozenset(optional_groups))" in source


def test_survival_panel_clamps_size_before_rect_clamp():
    """Rect.clamp küçültmez: boyut kısıtı kaynak sırasında clamp'ten önce."""
    source = _advanced_source()
    size_cap = source.index("panel_w = min(panel_w, max(s(120), bounds.width - 2 * s(8)))")
    rect_clamp = source.index("panel_rect = panel_rect.clamp(safe_rect)")
    assert size_cap < rect_clamp


def test_survival_title_glow_is_cached_not_per_frame_copy():
    """Kare-başı 4x copy() yasağı (CLAUDE.md): glow tek önbellekli yüzeyden
    4 sabit ofsetle blit'lenir."""
    source = _advanced_source()
    survival_body = source[source.index("def _draw_survival_panel"):source.index("def draw_mode_info", source.index("def _draw_survival_panel"))]
    assert "glow_copy" not in survival_body
    assert "_survival_title_key" in survival_body
    assert "for offset in [(2, 0), (-2, 0), (0, 2), (0, -2)]:" in survival_body


def test_daily_desc_line_limit_is_dynamic_not_constant():
    source = _advanced_source()
    daily_body = source[source.index("def draw_mode_info", source.index("class DailyChallengeMode")):]
    # Eski sabit açıklama limiti kalktı; dinamik limit + kayıt var.
    assert "max_lines=3" not in daily_body
    assert "desc_max_lines" in daily_body
    assert "self._daily_panel_rects = recorded" in daily_body


def test_daily_bonus_language_is_imported_locally():
    """Gizli NameError düzeltmesinin kaynağı: get_language fonksiyon-içe."""
    source = _advanced_source()
    assert "from localization import t, get_language" in source


def test_survival_hud_rects_are_recorded():
    source = _advanced_source()
    assert "self._survival_hud_rects = {" in source


def test_module_imports_layout_and_safe_rect_helpers():
    source = _advanced_source()
    assert "from .ui_text_layout import wrap_text_limited" in source
    assert "from .game_over_surfaces import get_render_safe_rect" in source
