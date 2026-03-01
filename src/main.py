"""Quadrix Oyunu - Python & Pygame
Ana giriş noktası
"""

import os
import platform
import subprocess
import sys
import threading
import time


src_dir_for_imports = os.path.dirname(os.path.abspath(__file__))
if src_dir_for_imports not in sys.path:
    sys.path.insert(0, src_dir_for_imports)

# ==================== DUAL-MODULE LOCALIZATION FIX ====================
# src/main.py "from src.main import main" ile paket olarak yüklendiğinde,
# relative import (from .localization) → sys.modules['src.localization'] oluşturur;
# ancak game.py, menu.py gibi alt modüller bare import (from localization import t)
# kullanır → sys.modules['localization'] olarak AYRI bir modül yükler.
# İki farklı modül nesnesi = iki farklı _current_language → set_language() diğerine yansımaz.
# Çözüm: localization'ı tek seferlik yükleyip her iki ad altında da kaydet.
try:
    import localization as _loc_singleton
    sys.modules.setdefault('src.localization', _loc_singleton)
except Exception:
    pass

# ==================== WORKING DIRECTORY FIX (macOS .app için kritik) ====================
# Finder'dan açıldığında CWD yanlış olabiliyor, bu yüzden doğru dizine geçiyoruz
def _fix_working_directory():
    """PyInstaller .app bundle için working directory'yi düzelt"""
    if getattr(sys, 'frozen', False):
        # PyInstaller ile paketlenmiş
        if hasattr(sys, '_MEIPASS'):
            # _MEIPASS: PyInstaller'ın geçici extract dizini (assets burada)
            bundle_dir = sys._MEIPASS
        else:
            bundle_dir = os.path.dirname(sys.executable)
        os.chdir(bundle_dir)
    else:
        # Normal Python - src klasöründen bir üst dizine git
        src_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(src_dir)
        os.chdir(project_root)

_fix_working_directory()
# ========================================================================================

# Pygame için environment variables - titreme önleme / uyumluluk
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ['SDL_VIDEO_CENTERED'] = '1'  # Pencereyi merkezle

# Platform-spesifik video sürücüsü (renderer'ı zorlamıyoruz: bazı sistemlerde
# 'failed to create renderer' hatasına sebep olabiliyor.)
current_platform = platform.system()
if current_platform == 'Windows':
    os.environ.setdefault('SDL_VIDEODRIVER', 'windows')
elif current_platform == 'Darwin':  # macOS
    # macOS SDL ayarları - pygame.init() öncesi set edilmeli
    current_audio = os.environ.get('SDL_AUDIODRIVER', '')
    if current_audio != 'dummy':
        os.environ['SDL_AUDIODRIVER'] = 'coreaudio'
    # Retina HiDPI: aktif — SDL surface fiziksel piksel boyutunda oluşturulur,
    # pencere logical point boyutunda kalır.  Tüm mouse koordinatları
    # normalize_mouse_pos() / get_mouse_pos() üzerinden fiziksel piksele çevrilir.
    os.environ.setdefault('SDL_VIDEO_HIGHDPI_DISABLED', '0')
    os.environ.setdefault('SDL_VIDEO_MAC_FULLSCREEN_SPACES', '0')
    os.environ.setdefault('SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS', '0')
    os.environ.setdefault('SDL_VIDEODRIVER', 'cocoa')

# VSYNC (SDL tarafında). FPS unlocked olsa bile tearing'i azaltır.
os.environ.setdefault('SDL_RENDER_VSYNC', '1')
os.environ.setdefault('SDL_HINT_RENDER_SCALE_QUALITY', '1')


def _apply_leaderboard_cli_overrides(argv: list[str]) -> None:
    """Steam Launch Options ile gelen leaderboard parametrelerini env'e uygula."""

    def _clean_value(value: str) -> str:
        raw = str(value or '').strip()
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            raw = raw[1:-1].strip()
        return raw

    def _next_value(index: int) -> tuple[str, int]:
        if index + 1 < len(argv):
            return argv[index + 1], 2
        return '', 1

    i = 0
    while i < len(argv):
        raw = str(argv[i] or '').strip()
        if raw.startswith('--leaderboard-backend-url='):
            value = _clean_value(raw.split('=', 1)[1])
            if value and not value.startswith('--'):
                os.environ['LEADERBOARD_BACKEND_URL'] = value
        elif raw == '--leaderboard-backend-url':
            value, consumed = _next_value(i)
            value = _clean_value(value)
            if value and not value.startswith('--'):
                os.environ['LEADERBOARD_BACKEND_URL'] = value
            i += consumed - 1
        elif raw.startswith('--leaderboard-client-token='):
            value = _clean_value(raw.split('=', 1)[1])
            if value and not value.startswith('--'):
                os.environ['LEADERBOARD_CLIENT_TOKEN'] = value
        elif raw == '--leaderboard-client-token':
            value, consumed = _next_value(i)
            value = _clean_value(value)
            if value and not value.startswith('--'):
                os.environ['LEADERBOARD_CLIENT_TOKEN'] = value
            i += consumed - 1
        i += 1

try:
    from .game import Game  # type: ignore
    from .block_styles import BlockStyleManager  # type: ignore
    from .tutorial import TutorialMode  # type: ignore
    from .splash_screen import SplashScreen  # type: ignore
    from .pvp_game import PvPGame  # type: ignore
    from .game_modes import SprintMode, UltraMode, ZenMode, HardcoreMode  # type: ignore
    from .game_modes_extra import Tetris2Mode, MysteryMode, WideMode  # type: ignore
    from .game_modes_advanced import SurvivalMode, CascadeMode, DailyChallengeMode  # type: ignore
    from .campaign import CampaignMode, CampaignLevelSelect  # type: ignore
    from .menu import Menu, HighScoreScreen, SettingsScreen, BlockStyleSettingsScreen, BlockWorkshopScreen, AchievementScreen, CreditsScreen, ControlSettingsScreen, MusicSettingsScreen  # type: ignore
    from .settings_screen_tabbed import TabbedSettingsScreen  # type: ignore
    from .extras_menu import ExtrasScreen  # type: ignore
    from .graphics_menu import GraphicsMenu  # type: ignore
    from .gameplay_settings import GameplaySettingsMenu  # type: ignore
    from .piece_workshop import PieceWorkshopScreen  # type: ignore
    from .guide_screen import GuideScreen  # type: ignore
    from .score_manager import ScoreManager  # type: ignore
    from .achievements import AchievementManager  # type: ignore
    from .themes import ThemeManager  # type: ignore
    from .settings_manager import SettingsManager  # type: ignore
    from .user_manager import UserManager, DAILY_MAX_FAILURES  # type: ignore
    from .steam_leaderboards import SteamLeaderboardService  # type: ignore
    from .user_screens import UserSelectionScreen, UserManagementScreen  # type: ignore
    from .localization import set_language, t  # type: ignore
    from .platform_utils import request_window_focus, init_platform_display, get_display_flags, create_display, get_native_resolution, is_fullscreen_toggle, normalize_mouse_pos, get_mouse_pos, set_app_icon  # type: ignore
    from .retro_style import retro_style  # type: ignore
    from .background_effects import (  # type: ignore
        start_screen_transition, update_screen_transition,
        draw_screen_transition, is_screen_transition_active,
        ScreenTransition
    )
    from .gamepad_manager import get_gamepad_manager, is_gamepad_connected  # type: ignore
except Exception:
    from game import Game
    from block_styles import BlockStyleManager
    from tutorial import TutorialMode
    from splash_screen import SplashScreen
    from pvp_game import PvPGame
    from game_modes import SprintMode, UltraMode, ZenMode, HardcoreMode
    from game_modes_extra import Tetris2Mode, MysteryMode, WideMode
    from game_modes_advanced import SurvivalMode, CascadeMode, DailyChallengeMode
    from campaign import CampaignMode, CampaignLevelSelect
    from menu import Menu, HighScoreScreen, SettingsScreen, BlockStyleSettingsScreen, BlockWorkshopScreen, AchievementScreen, CreditsScreen, ControlSettingsScreen, MusicSettingsScreen
    from settings_screen_tabbed import TabbedSettingsScreen
    from extras_menu import ExtrasScreen
    from graphics_menu import GraphicsMenu
    from gameplay_settings import GameplaySettingsMenu
    from piece_workshop import PieceWorkshopScreen
    from guide_screen import GuideScreen
    from score_manager import ScoreManager
    from achievements import AchievementManager
    from themes import ThemeManager
    from settings_manager import SettingsManager
    from user_manager import UserManager, DAILY_MAX_FAILURES
    from steam_leaderboards import SteamLeaderboardService
    from user_screens import UserSelectionScreen, UserManagementScreen
    from localization import set_language, t
    from platform_utils import request_window_focus, init_platform_display, get_display_flags, create_display, get_native_resolution, is_fullscreen_toggle, normalize_mouse_pos, get_mouse_pos, set_app_icon
    from retro_style import retro_style
    from background_effects import (
        start_screen_transition, update_screen_transition,
        draw_screen_transition, is_screen_transition_active,
        ScreenTransition
    )
    from gamepad_manager import get_gamepad_manager, is_gamepad_connected
import pygame
from pathlib import Path


def resource_path(relative_path: str) -> str:
    """PyInstaller ile derlenen exe için doğru path'i al"""
    try:
        import sys
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).resolve().parents[1]
    return str(base_path / relative_path)


def setup_custom_cursor() -> bool:
    """Özel fare imlecini yükle ve ayarla
    
    Returns:
        True: Başarıyla ayarlandı
        False: Varsayılan cursor kullanılıyor
    """
    try:
        cursor_path = resource_path('assets/ui/cursor.png')
        cursor_surface = pygame.image.load(cursor_path).convert_alpha()
        # Cursor boyutunu 32x32'ye ölçekle (standart cursor boyutu)
        cursor_surface = pygame.transform.smoothscale(cursor_surface, (32, 32))
        # Hotspot: tıklama noktası (sol üst köşeye yakın)
        hotspot = (4, 4)
        cursor = pygame.cursors.Cursor(hotspot, cursor_surface)
        pygame.mouse.set_cursor(cursor)
        print("🖱️ Özel fare imleci yüklendi")
        return True
    except Exception as e:
        print(f"⚠️ Özel cursor yüklenemedi, varsayılan kullanılıyor: {e}")
        return False



# Oyun Modu Bilgilendirmeleri (Başlık, Açıklama)
GAME_MODE_INFOS = {
    'classic': {
        'title_key': 'mode_classic',
        'desc_key': 'mode_intro_classic_desc'
    },
    'sprint': {
        'title_key': 'mode_sprint',
        'desc_key': 'mode_intro_sprint_desc'
    },
    'ultra': {
        'title_key': 'mode_ultra',
        'desc_key': 'mode_intro_ultra_desc'
    },
    'survival': {
        'title_key': 'mode_survival',
        'desc_key': 'mode_intro_survival_desc'
    },
    'cascade': {
        'title_key': 'mode_cascade',
        'desc_key': 'mode_intro_cascade_desc'
    },
    'zen': {
        'title_key': 'mode_zen',
        'desc_key': 'mode_intro_zen_desc'
    },
    'mystery': { # Kart Ustalığı / Mystery
        'title_key': 'skin_mystery_title',
        'desc_key': 'mode_intro_mystery_desc'
    },
    'wide': {
        'title_key': 'mode_wide',
        'desc_key': 'mode_intro_wide_desc'
    },
    'tetris2': {
        'title_key': 'mode_tetris_extra',
        'desc_key': 'mode_intro_tetris2_desc'
    },
    'pvp': {
        'title_key': 'mode_pvp',
        'desc_key': 'mode_intro_pvp_desc'
    },
    'hardcore': {
        'title_key': 'mode_hardcore',
        'desc_key': 'mode_intro_hardcore_desc'
    }
}

def _show_mode_intro_popup(screen, mode_key, settings_manager=None):
    """
    Oyun moduna girmeden önce bilgi penceresi gösterir (Blocking Loop).
    Eğer 'mode_key' sözlükte yoksa direkt True döner (popup göstermez).
    True -> BAŞLA
    False -> İPTAL
    """
    # Eğer kullanıcı "bir daha gösterme" dediyse direkt geç
    if settings_manager and settings_manager.get(f'hide_intro_{mode_key}', False):
        return True

    info = GAME_MODE_INFOS.get(mode_key)
    if not info:
        return True

    title = t(info.get('title_key', ''), default=info.get('title', ''))
    text = t(info.get('desc_key', ''), default=info.get('desc', ''))

    clock = pygame.time.Clock()
    running_popup = True
    result = False
    
    # Checkbox durumu
    dont_show_checked = False
    
    # Arka planı bir kez yakala (screenshot)
    bg_capture = screen.copy()
    dim_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    dim_surface.fill((0, 0, 0, 160))
    bg_capture.blit(dim_surface, (0, 0))
    
    start_time = pygame.time.get_ticks()
    
    while running_popup:
        clock.tick(60)
        
        # Dinamik layout hesapla (resize durumuna karşı)
        width, height = screen.get_size()
        popup_scale = _fullscreen_popup_scale(screen)
        side_margin = max(34, int(44 * popup_scale))
        panel_width = min(int(600 * popup_scale), width - side_margin * 2)
        panel_height = min(int(360 * popup_scale), height - max(80, int(100 * popup_scale)))
        panel_width = max(380, panel_width)
        panel_height = max(250, panel_height)
        panel_rect = pygame.Rect((width - panel_width) // 2, (height - panel_height) // 2, panel_width, panel_height)
        
        spacing = max(10, int(16 * popup_scale))
        btn_w = min(int(220 * popup_scale), (panel_rect.width - max(34, int(60 * popup_scale)))//2)
        btn_h = max(40, int(54 * popup_scale))
        total_btn_w = btn_w * 2 + spacing
        btn_start_x = panel_rect.centerx - total_btn_w // 2
        btn_y = panel_rect.bottom - btn_h - max(16, int(24 * popup_scale))
        
        play_rect = pygame.Rect(btn_start_x, btn_y, btn_w, btn_h)
        cancel_rect = pygame.Rect(btn_start_x + btn_w + spacing, btn_y, btn_w, btn_h)
        
        # Checkbox hesapla (butonların üstünde)
        cb_size = max(14, int(20 * popup_scale))
        cb_area_height = max(20, int(30 * popup_scale))
        cb_y = btn_y - cb_area_height - max(8, int(12 * popup_scale))
        
        # Metni ölç
        cb_font = retro_style.get_font(max(12, int(18 * popup_scale)), bold=False)
        cb_label = t('dont_show_again')
        cb_text_surf = cb_font.render(cb_label, True, (200, 200, 200))
        
        total_cb_width = cb_size + 10 + cb_text_surf.get_width()
        cb_start_x = panel_rect.centerx - total_cb_width // 2
        
        checkbox_rect = pygame.Rect(cb_start_x, cb_y, cb_size, cb_size)
        # Tıklama alanı (metni de kapsasın)
        checkbox_click_rect = pygame.Rect(cb_start_x, cb_y - 5, total_cb_width, cb_size + 10)

        # Olaylar
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running_popup = False
                result = False 
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running_popup = False
                    result = False
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    running_popup = False
                    result = True
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Mouse pos güncelle
                mpos = normalize_mouse_pos(event.pos) if 'normalize_mouse_pos' in globals() else event.pos

                if play_rect.collidepoint(mpos):
                    running_popup = False
                    result = True
                elif cancel_rect.collidepoint(mpos):
                    running_popup = False
                    result = False
                elif checkbox_click_rect.collidepoint(mpos):
                    dont_show_checked = not dont_show_checked

        # Çizim
        screen.blit(bg_capture, (0, 0))
        
        # Glass Panel
        retro_style.draw_glass_panel(screen, panel_rect, alpha=220, border_color=(*retro_style.accent, 200), glow=True)
        
        # Title
        title_font = retro_style.get_font(max(18, int(28 * popup_scale)), bold=True)
        title_surf = title_font.render(title, True, retro_style.accent)
        screen.blit(title_surf, title_surf.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + max(14, int(24 * popup_scale))))
        
        # Body
        body_font = retro_style.get_font(max(13, int(20 * popup_scale)), bold=False)
        body_color = (220, 230, 250)
        # Metin alanı checkbox'ın üstünde bitsin
        body_pad_x = max(16, int(30 * popup_scale))
        body_top = panel_rect.y + max(42, int(80 * popup_scale))
        body_rect = pygame.Rect(
            panel_rect.x + body_pad_x,
            body_top,
            panel_rect.width - body_pad_x * 2,
            max(80, panel_rect.height - max(120, int(180 * popup_scale))),
        )
        
        retro_style.draw_wrapped_text(
            screen,
            text,
            body_font,
            body_color,
            body_rect,
            align='center',
            line_spacing=max(4, int(8 * popup_scale))
        )
        
        # Checkbox Çizimi
        # Kutu
        pygame.draw.rect(screen, (20, 30, 50), checkbox_rect, border_radius=4)
        pygame.draw.rect(screen, (150, 160, 180), checkbox_rect, 2, border_radius=4)
        
        if dont_show_checked:
            # Tik işareti (veya içini doldur)
            inner_rect = checkbox_rect.inflate(-8, -8)
            pygame.draw.rect(screen, retro_style.success, inner_rect, border_radius=2)
            
        # Metin
        screen.blit(cb_text_surf, (checkbox_rect.right + 10, checkbox_rect.y + (cb_size - cb_text_surf.get_height()) // 2))
        
        # Buttons
        mouse_active = get_mouse_pos()
        
        play_hover = play_rect.collidepoint(mouse_active)
        cancel_hover = cancel_rect.collidepoint(mouse_active)
        cb_hover = checkbox_click_rect.collidepoint(mouse_active)

        retro_style.draw_uniform_button(screen, play_rect, t('start'), sub_text='ENTER', color_code=retro_style.success, selected=play_hover)
        retro_style.draw_uniform_button(screen, cancel_rect, t('cancel'), sub_text='ESC', color_code=retro_style.secondary, selected=cancel_hover)
        
        if cb_hover:
            hover_surf = pygame.Surface(checkbox_click_rect.size, pygame.SRCALPHA)
            hover_surf.fill((255, 255, 255, 25))
            screen.blit(hover_surf, checkbox_click_rect.topleft)
        
        pygame.display.flip()
        
    # Çıkarken kaydet
    if result and dont_show_checked and settings_manager:
        settings_manager.set(f'hide_intro_{mode_key}', True)

    return result


def _fullscreen_popup_scale(screen) -> float:
    """Popup/panel ölçeği (fullscreen referans: 1920x1080)."""
    width, height = screen.get_size()
    scale = min(width / 1920.0, height / 1080.0)
    return max(0.65, min(1.35, scale))


def _show_zen_start_popup(screen, board_height=20, settings_manager=None):
    """
    Zen Mode başlangıç penceresi.
    Hem mod tanıtımını hem de otomatik temizlik ayarını içerir, optimize edilmiş versiyon.
    """
    # Kayıtlı "bir daha gösterme" ayarını kontrol et
    if settings_manager and settings_manager.get('hide_zen_popup', False):
        return settings_manager.get('zen_auto_clear_rows', board_height)

    # Mod bilgisini al (Başlık ve Açıklama)
    info = GAME_MODE_INFOS.get('zen')
    mode_title = t(info.get('title_key', ''), default=info.get('title', 'ZEN MODU')) if info else t('mode_zen', default='ZEN MODU')
    mode_desc = t(info.get('desc_key', ''), default=info.get('desc', '')) if info else ''

    from background_effects import get_shared_falling_blocks_layer
    
    clock = pygame.time.Clock()
    running_popup = True
    
    # Minimum ve maksimum değerler
    MIN_ROWS = 4
    MAX_ROWS = board_height  # board_height = tüm tahta
    
    # Son seçimi ayarlardan yükle (varsayılan: tüm tahta)
    last_selection = MAX_ROWS
    if settings_manager:
        saved = settings_manager.get('zen_auto_clear_rows', MAX_ROWS)
        if saved is not None and MIN_ROWS <= saved <= MAX_ROWS:
            last_selection = saved
        elif saved is not None and saved < MIN_ROWS:
            last_selection = MIN_ROWS  # Minimum değere çek
        else:
            last_selection = MAX_ROWS  # None veya > MAX_ROWS ise tüm tahta
    
    selected_rows = max(MIN_ROWS, min(MAX_ROWS, last_selection))
    
    # Arka planı yakala (Intro popup stili)
    bg_capture = screen.copy()
    dim_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    dim_surface.fill((0, 0, 0, 160))
    bg_capture.blit(dim_surface, (0, 0))
    
    result = False
    
    while running_popup:
        clock.tick(60)
        
        width, height = screen.get_size()
        popup_scale = _fullscreen_popup_scale(screen)
        
        # Panel Boyutları - İçeriğe göre biraz uzun
        side_margin = max(30, int(40 * popup_scale))
        panel_width = min(int(600 * popup_scale), width - side_margin * 2)
        panel_height = min(int(450 * popup_scale), height - max(70, int(90 * popup_scale)))
        panel_width = max(400, panel_width)
        panel_height = max(300, panel_height)
        panel_rect = pygame.Rect((width - panel_width) // 2, (height - panel_height) // 2, panel_width, panel_height)
        
        # Butonlar
        btn_spacing = max(10, int(16 * popup_scale))
        btn_w = min(int(200 * popup_scale), (panel_rect.width - max(30, int(60 * popup_scale))) // 2)
        btn_h = max(38, int(50 * popup_scale))
        spacing = btn_spacing
        total_btn_w = btn_w * 2 + spacing
        btn_start_x = panel_rect.centerx - total_btn_w // 2
        btn_y = panel_rect.bottom - btn_h - max(16, int(24 * popup_scale))
        
        play_rect = pygame.Rect(btn_start_x, btn_y, btn_w, btn_h)
        cancel_rect = pygame.Rect(btn_start_x + btn_w + spacing, btn_y, btn_w, btn_h)
        
        # Seçici Alanı (Alt kısımda)
        selector_center_y = panel_rect.y + int(280 * popup_scale)
        arrow_size = max(28, int(40 * popup_scale))
        arrow_offset = int(100 * popup_scale)
        left_arrow_rect = pygame.Rect(panel_rect.centerx - arrow_offset - arrow_size, selector_center_y - arrow_size//2, arrow_size, arrow_size)
        right_arrow_rect = pygame.Rect(panel_rect.centerx + arrow_offset, selector_center_y - arrow_size//2, arrow_size, arrow_size)

        # Olaylar
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running_popup = False
                result = False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running_popup = False
                    result = False
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    running_popup = False
                    result = selected_rows if selected_rows < MAX_ROWS else None
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    selected_rows = max(MIN_ROWS, selected_rows - 1)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    selected_rows = min(MAX_ROWS, selected_rows + 1)
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mpos = normalize_mouse_pos(event.pos) if 'normalize_mouse_pos' in globals() else event.pos
                
                if play_rect.collidepoint(mpos):
                    running_popup = False
                    result = selected_rows if selected_rows < MAX_ROWS else None
                elif cancel_rect.collidepoint(mpos):
                    running_popup = False
                    result = False
                elif left_arrow_rect.collidepoint(mpos):
                    selected_rows = max(MIN_ROWS, selected_rows - 1)
                elif right_arrow_rect.collidepoint(mpos):
                    selected_rows = min(MAX_ROWS, selected_rows + 1)
        
        # Çizim
        screen.blit(bg_capture, (0, 0))
        # Panel arka planını daha opak yap (alpha 230 -> 245)
        retro_style.draw_glass_panel(screen, panel_rect, alpha=245, border_color=(100, 255, 200), glow=True)
        
        # 1. Mod Başlığı
        title_font = retro_style.get_font(max(18, int(28 * popup_scale)), bold=True)
        title_surf = title_font.render(mode_title, True, (100, 255, 200))
        screen.blit(title_surf, title_surf.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + max(14, int(24 * popup_scale))))
        
        # 2. Mod Açıklaması
        desc_font = retro_style.get_font(max(13, int(18 * popup_scale)), bold=False)
        y_text = panel_rect.y + max(40, int(64 * popup_scale))
        # Satırları doğru böl (hem \n hem de \\n desteği)
        lines = mode_desc.replace('\\n', '\n').split('\n')
        for line in lines:
            if not line.strip(): continue
            line_surf = desc_font.render(line.strip(), True, (220, 230, 240))
            screen.blit(line_surf, line_surf.get_rect(centerx=panel_rect.centerx, top=y_text))
            y_text += max(16, int(24 * popup_scale))
            
        # Ayırıcı Çizgi
        line_margin = max(20, int(40 * popup_scale))
        line_y = y_text + max(8, int(15 * popup_scale))
        pygame.draw.line(screen, (100, 255, 200, 100), (panel_rect.x + line_margin, line_y), (panel_rect.right - line_margin, line_y), 1)
        
        # 3. Ayar Başlığı ve Açıklaması
        y_text += max(18, int(35 * popup_scale))
        sett_font = retro_style.get_font(max(14, int(20 * popup_scale)), bold=True)
        sett_surf = sett_font.render(t('zen_auto_clear_title'), True, (255, 255, 255))
        screen.blit(sett_surf, sett_surf.get_rect(centerx=panel_rect.centerx, top=y_text))
        
        y_text += max(14, int(25 * popup_scale))
        sub_font = retro_style.get_font(max(12, int(16 * popup_scale)), bold=False)
        sub_surf = sub_font.render(t('zen_auto_clear_desc'), True, (180, 190, 200))
        screen.blit(sub_surf, sub_surf.get_rect(centerx=panel_rect.centerx, top=y_text))

        # 4. Seçici (Selector)
        mpos = get_mouse_pos()
        
        # Sol Ok
        left_hover = left_arrow_rect.collidepoint(mpos)
        left_color = (100, 255, 200) if left_hover else (150, 160, 180)
        if selected_rows <= MIN_ROWS: left_color = (60, 60, 70)
        pygame.draw.rect(screen, (30, 40, 50), left_arrow_rect, border_radius=8)
        pygame.draw.rect(screen, left_color, left_arrow_rect, 2, border_radius=8)
        arrow_txt_font = retro_style.get_font(max(20, int(30 * popup_scale)), bold=True)
        l_arr = arrow_txt_font.render("<", True, left_color)
        screen.blit(l_arr, l_arr.get_rect(center=left_arrow_rect.center))

        # Değer
        val_font = retro_style.get_font(max(28, int(48 * popup_scale)), bold=True)
        if selected_rows >= MAX_ROWS:
            v_txt = "TÜMÜ"
            v_col = (255, 215, 0)
        else:
            v_txt = str(selected_rows)
            v_col = (100, 255, 200)
        v_surf = val_font.render(v_txt, True, v_col)
        screen.blit(v_surf, v_surf.get_rect(center=(panel_rect.centerx, selector_center_y)))
        
        # Etiket
        if selected_rows < MAX_ROWS:
               lbl = retro_style.get_font(max(10, int(14 * popup_scale))).render("satır", True, (150, 150, 150))
               screen.blit(lbl, lbl.get_rect(center=(panel_rect.centerx, selector_center_y + max(20, int(35 * popup_scale)))))

        # Sağ Ok
        right_hover = right_arrow_rect.collidepoint(mpos)
        right_color = (100, 255, 200) if right_hover else (150, 160, 180)
        if selected_rows >= MAX_ROWS: right_color = (60, 60, 70)
        pygame.draw.rect(screen, (30, 40, 50), right_arrow_rect, border_radius=8)
        pygame.draw.rect(screen, right_color, right_arrow_rect, 2, border_radius=8)
        r_arr = arrow_txt_font.render(">", True, right_color)
        screen.blit(r_arr, r_arr.get_rect(center=right_arrow_rect.center))
        
        # 6. Butonlar
        play_hover = play_rect.collidepoint(mpos)
        cancel_hover = cancel_rect.collidepoint(mpos)
        
        retro_style.draw_uniform_button(screen, play_rect, t('start'), sub_text='ENTER', color_code=retro_style.success, selected=play_hover)
        retro_style.draw_uniform_button(screen, cancel_rect, t('cancel'), sub_text='ESC', color_code=retro_style.secondary, selected=cancel_hover)
        
        pygame.display.flip()
    
    # Seçimi kaydet
    if result is not False and settings_manager:
        settings_manager.set('zen_auto_clear_rows', selected_rows if selected_rows < MAX_ROWS else MAX_ROWS)
    
    return result


def _show_tutorial_prompt(screen):
    """
    Yeni oyunculara tutorial oynamak isteyip istemediklerini sor.
    Returns: True (Oyna), False (Atla)
    """
    title = t('tutorial_welcome_title')
    text = t('tutorial_welcome_desc')

    clock = pygame.time.Clock()
    running_popup = True
    result = False
    
    # Arka planı yakala
    bg_capture = screen.copy()
    dim_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    dim_surface.fill((0, 0, 0, 220))
    bg_capture.blit(dim_surface, (0, 0))
    
    while running_popup:
        clock.tick(60)
        
        width, height = screen.get_size()
        popup_scale = _fullscreen_popup_scale(screen)
        side_margin = max(30, int(40 * popup_scale))
        panel_width = min(int(820 * popup_scale), width - side_margin * 2)
        panel_height = min(int(420 * popup_scale), height - max(70, int(90 * popup_scale)))
        panel_width = max(560, panel_width)
        panel_height = max(320, panel_height)
        panel_rect = pygame.Rect((width - panel_width) // 2, (height - panel_height) // 2, panel_width, panel_height)
        
        btn_w = min(int(210 * popup_scale), (panel_rect.width - max(36, int(72 * popup_scale))) // 2)
        btn_h = max(46, int(62 * popup_scale))
        spacing = max(14, int(24 * popup_scale))
        total_btn_w = btn_w * 2 + spacing
        btn_start_x = panel_rect.centerx - total_btn_w // 2
        btn_y = panel_rect.bottom - btn_h - max(22, int(36 * popup_scale))
        
        # Atla solda, Eğitimi Oyna sağda
        skip_rect = pygame.Rect(btn_start_x, btn_y, btn_w, btn_h)
        play_rect = pygame.Rect(btn_start_x + btn_w + spacing, btn_y, btn_w, btn_h)
        
        # Olaylar
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running_popup = False
                result = False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: # Escape = Skip
                    running_popup = False
                    result = False
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running_popup = False
                    result = True
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mpos = normalize_mouse_pos(event.pos) if 'normalize_mouse_pos' in globals() else event.pos
                if play_rect.collidepoint(mpos):
                    running_popup = False
                    result = True
                elif skip_rect.collidepoint(mpos):
                    running_popup = False
                    result = False

        # Çizim
        screen.blit(bg_capture, (0, 0))
        retro_style.draw_glass_panel(screen, panel_rect, alpha=230, border_color=(100, 255, 100), glow=True)
        
        # Başlık ve Metin
        title_font = retro_style.get_font(max(22, int(32 * popup_scale)), bold=True)
        title_surf = title_font.render(title, True, (100, 255, 100))
        screen.blit(title_surf, title_surf.get_rect(centerx=panel_rect.centerx, top=panel_rect.y + max(22, int(36 * popup_scale))))
        
        body_font = retro_style.get_font(max(16, int(22 * popup_scale)))
        body_rect = pygame.Rect(
            panel_rect.x + max(20, int(36 * popup_scale)),
            panel_rect.y + max(60, int(96 * popup_scale)),
            panel_rect.width - max(40, int(72 * popup_scale)),
            max(80, int(130 * popup_scale)),
        )
        retro_style.draw_wrapped_text(screen, text, body_font, (240, 240, 240), body_rect, align='center')
        
        # Butonlar
        mpos = get_mouse_pos()
        
        retro_style.draw_uniform_button(screen, skip_rect, t('skip_tutorial'), sub_text='ESC', color_code=retro_style.secondary, selected=skip_rect.collidepoint(mpos))
        retro_style.draw_uniform_button(screen, play_rect, t('play_tutorial'), sub_text='ENTER', color_code=retro_style.success, selected=play_rect.collidepoint(mpos))
        
        pygame.display.flip()
        
    return result

def main():
    """Ana menü ve oyunu başlat"""
    try:
        _apply_leaderboard_cli_overrides(sys.argv[1:])
    except Exception:
        pass

    # Windows 10/11 DPI Awareness - pygame.init() öncesi ayarlanmalı
    from platform_utils import _init_windows_dpi_awareness
    _init_windows_dpi_awareness()
    
    # Ayarları pygame.init() öncesi yükle ki SDL hint/env (VSync gibi) doğru uygulansın.
    settings_manager = SettingsManager()  # Ayar yöneticisi
    try:
        vsync_enabled = bool(settings_manager.get('vsync', True))
    except Exception:
        vsync_enabled = True
    # SDL_RENDER_VSYNC renderer oluşturulurken okunur; pygame.init() ÖNCESİ set edilmeli.
    # Ayrıca ekran koruyucu engelleme
    os.environ['SDL_RENDER_VSYNC'] = '1' if vsync_enabled else '0'
    os.environ['SDL_VIDEO_ALLOW_SCREENSAVER'] = '0'

    # macOS: tkinter'ı SDL'den önce initialize et.
    # Aksi halde bazı sistemlerde tkinter dialog'u açarken
    # NSInvalidArgumentException: -[SDLApplication macOSVersion] crash'i görülebiliyor.
    if current_platform == 'Darwin':
        try:
            from tk_compat import prewarm_tkinter
            prewarm_tkinter()
        except ImportError:
            pass  # tk_compat mevcut değil, normal
        except Exception as exc:
            # Detaylı log - kullanıcı sorun yaşarsa yardımcı olur
            print(f"⚠️ Tk ön yükleme başarısız (dosya dialog'ı etkilenebilir): {exc}")

    # ==================== MIXER PRE-INIT (KRITIK) ====================
    # mixer pre_init, ses/müzik stabilitesini artırır (pygame.init'ten önce çağrılmalı!).
    # Mixer init
    mixer_initialized = False
    
    if current_platform == 'Darwin':
        pass  # macOS: pygame.init() sonrası lazy init
    else:
        try:
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
            mixer_initialized = True
        except Exception:
            pass

    pygame.init()
    
    
    
    # macOS için pygame.init() sonrası güvenli mixer init
    if current_platform == 'Darwin' and not mixer_initialized:
        macos_configs = [
            (44100, -16, 2, 4096),
            (44100, -16, 2, 2048),
            (48000, -16, 2, 4096),
            (22050, -16, 2, 2048),
            (44100, -16, 1, 2048),
        ]
        for freq, size, ch, buf in macos_configs:
            try:
                pygame.mixer.quit()
            except:
                pass
            try:
                pygame.mixer.init(frequency=freq, size=size, channels=ch, buffer=buf)
                if pygame.mixer.get_init():
                    mixer_initialized = True
                    break
            except Exception:
                continue
    
    # Fallback mixer init
    if not mixer_initialized:
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            if pygame.mixer.get_init():
                mixer_initialized = True
        except Exception:
            pass
    
    init_platform_display()
    
    # Sistem ekran çözünürlüğünü al
    native_width, native_height = get_native_resolution()
    
    # Platform uyumlu pencere modu - pencere modunda başla
    start_fullscreen = settings_manager.get('fullscreen', True)
    start_borderless = settings_manager.get('borderless_fullscreen', True)
    
    # Pencere boyutları (pencere modunda kullanılır)
    # Ayarlardan oku, yoksa mantıklı varsayılan kullan
    saved_resolution = settings_manager.get('resolution', 'auto')
    if saved_resolution == 'auto':
        if current_platform == 'Darwin':
            # macOS: Ekranın büyük bir kısmını kapla (%90)
            # Menu bar ve dock için biraz alan bırak
            window_width = max(1024, int(native_width * 0.90))
            window_height = max(700, int(native_height * 0.85))
        else:
            # Windows/Linux: Ekranın %80'i kadar, minimum 800x600
            window_width = max(800, min(1280, int(native_width * 0.8)))
            window_height = max(600, min(900, int(native_height * 0.8)))
    else:
        try:
            window_width, window_height = map(int, saved_resolution.split('x'))
        except Exception:
            window_width, window_height = 1024, 768
    
    try:
        screen = create_display(
            window_width,
            window_height,
            fullscreen=start_fullscreen,
            resizable=True,
            borderless=start_borderless,
        )
        
        # macOS: Surface validation
        if current_platform == 'Darwin':
            try:
                screen.fill((0, 0, 0))
                pygame.display.flip()
            except Exception:
                pygame.display.quit()
                pygame.display.init()
                screen = pygame.display.set_mode((800, 600), pygame.RESIZABLE)
                
    except Exception:
        screen = create_display(800, 600, fullscreen=False, resizable=True, borderless=False)
    
    pygame.display.set_caption('Quadrix')
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        _assets_dir = str(Path(sys._MEIPASS) / 'assets')
    else:
        _assets_dir = str(Path(__file__).resolve().parent.parent / 'assets')
    set_app_icon(_assets_dir)
    # macOS: Dock/process adını 'Quadrix' olarak ayarla (PyObjC varsa)
    if current_platform == 'Darwin':
        try:
            from AppKit import NSProcessInfo
            NSProcessInfo.processInfo().setProcessName_('Quadrix')
        except Exception:
            pass
    request_window_focus()
    
    # Özel fare imlecini yükle (display oluşturulduktan sonra)
    setup_custom_cursor()
    
    clock = pygame.time.Clock()
    fullscreen = start_fullscreen  # Tam ekran durumu
    last_fullscreen_toggle_ms = -10_000
    
    # Yöneticiler
    user_manager = UserManager()  # Kullanıcı yöneticisi

    steam_leaderboard_service = SteamLeaderboardService(
        backend_base_url=os.getenv('LEADERBOARD_BACKEND_URL', 'http://127.0.0.1:8787')
    )
    steam_mode_scores_cache: dict[str, list[dict]] = {}
    steam_mode_scores_loading = False
    steam_mode_scores_last_attempt = -120.0
    steam_mode_scores_refresh_s = 45.0

    def _load_steam_mode_scores(limit=3, force=False):
        nonlocal steam_mode_scores_loading, steam_mode_scores_last_attempt

        if not steam_leaderboard_service.is_configured():
            return steam_mode_scores_cache

        now_s = time.monotonic()
        if steam_mode_scores_loading:
            return steam_mode_scores_cache
        if (not force) and (now_s - steam_mode_scores_last_attempt) < steam_mode_scores_refresh_s:
            return steam_mode_scores_cache

        steam_mode_scores_last_attempt = now_s
        steam_mode_scores_loading = True

        modes = ['mystery']

        def _load_worker():
            nonlocal steam_mode_scores_loading
            try:
                data = steam_leaderboard_service.fetch_all_mode_highscores(modes, limit=limit)
                if data:
                    steam_mode_scores_cache.clear()
                    steam_mode_scores_cache.update(data)
            except Exception as exc:
                print(f"[Steam Leaderboards] Skorlar alınamadı: {exc}")
            finally:
                steam_mode_scores_loading = False

        threading.Thread(target=_load_worker, daemon=True).start()
        return steam_mode_scores_cache
    
    # ── Steam SDK başlat (Steam üzerinden çalışıyorsa) ──────────────────────
    _steam_init_ok = False
    _steam_user_set = False  # Steam profili başarıyla seçildiyse True
    try:
        import steam_integration as _steam
        _steam_init_ok = _steam.init()
        if _steam_init_ok:
            _steam_id_str = _steam.get_steam_id_str()      # Kalıcı kimlik
            _steam_persona = _steam.get_persona_name()     # Görünen ad

            if _steam_id_str or _steam_persona:
                # 1. Önce Steam ID ile eşleştir (persona adı değişmiş olabilir)
                _target_user = user_manager.get_user_by_steam_id(_steam_id_str) if _steam_id_str else None

                # 2. Steam ID eşleşmesi yoksa persona adına bak
                if not _target_user and _steam_persona:
                    _existing = user_manager.users.get(_steam_persona)
                    if _existing is not None:
                        # Profil var; mevcut steam_id aynı veya boşsa bağla
                        _existing_sid = str(_existing.get('steam_id') or '').strip()
                        if not _existing_sid or _existing_sid == _steam_id_str:
                            _target_user = _steam_persona
                            if _steam_id_str and not _existing_sid:
                                user_manager.set_steam_id(_target_user, _steam_id_str)
                        # else: aynı isimde farklı Steam hesabı → adım 3'te yeni kullanıcı oluştur

                # 3. Hiç profil yoksa veya persona çakıştıysa yeni oluştur
                if not _target_user and _steam_persona:
                    _base = _steam_persona[:16]
                    # Çakışma yoksa direkt kullan; varsa SteamID son 4 hanesiyle unique yap
                    _username = _base[:20]
                    if _username in user_manager.users:
                        _suffix = (_steam_id_str or '0000')[-4:]
                        _username = f"{_base[:15]}_{_suffix}"[:20]
                    ok_c, _ = user_manager.create_user(_username, avatar='🎮', steam_id=_steam_id_str)
                    if ok_c:
                        _target_user = _username
                        print(f"[Steam] Yeni profil oluşturuldu: {_target_user}")

                # 4. Her Steam başlatmada Steam profilini güçlü seç
                if _target_user:
                    if user_manager.current_user != _target_user:
                        user_manager.select_user(_target_user)
                    print(f"[Steam] Aktif profil: {_target_user} (SteamID: {_steam_id_str})")
                    _steam_user_set = True

            # 5. Auth ticket'ı leaderboard servisine aktar (arkadaş listesi için)
            try:
                _ticket = _steam.get_auth_session_ticket()
                if _ticket:
                    steam_leaderboard_service.steam_ticket = _ticket
                    steam_leaderboard_service.current_steam_id = _steam_id_str
                    print("[Steam] Auth ticket leaderboard servisine aktarıldı.")
            except Exception as _te:
                print(f"[Steam] Auth ticket alınamadı: {_te}")
    except Exception as _se:
        print(f"[Steam] Steam başlatma hatası: {_se}")

    # Steam profili seçildiyse menüye direkt git, yoksa kullanıcı yoksa seçim ekranı
    if _steam_user_set:
        state = 'menu'  # Steam otomatik profil — kullanıcı seçimini atla
    elif not user_manager.has_users():
        state = 'user_selection'
    
    # Kullanıcıya özel dosyalar
    achievements_file = user_manager.get_achievements_file()
    highscores_file = user_manager.get_highscores_file()
    
    score_manager = ScoreManager(highscores_file)
    achievement_manager = AchievementManager(achievements_file)
    theme_manager = ThemeManager(settings_manager)
    
    # Dil ayarını yükle ve uygula
    saved_language = settings_manager.get('language', 'tr')
    set_language(saved_language)
    try:
        from ui_language_profile import apply_language_ui_profile
        apply_language_ui_profile(saved_language)
    except Exception:
        pass
    import constants
    if constants.DEBUG_MODE:
        print(f"🌐 Dil ayarlandı: {saved_language}")
    
    # DEBUG MODE'u ayarlardan yükle ve global değişkene ata
    constants.DEBUG_MODE = settings_manager.get('debug_mode', False)
    
    # Kaydedilmiş temayı yükle
    saved_theme = settings_manager.get('theme', 'Classic')
    theme_manager.set_theme(saved_theme)

    # Menü arka plan görselini ayarlardan uygula.
    try:
        retro_style.set_background_transparency(settings_manager.get('bg_transparency', 0.3))
    except Exception:
        pass

    # Menü/UI panel şeffaflığını uygula (arka plan görselinden bağımsız).
    try:
        retro_style.set_menu_transparency(settings_manager.get('menu_transparency', 1.0))
    except Exception:
        pass

    try:
        retro_style.set_background_enabled(settings_manager.get('background_enabled', True))
    except Exception:
        pass
    
    # Müzik için SoundManager
    from sound import SoundManager
    menu_sound = SoundManager()
    
    # Menüler
    # First show splash screen (press Enter to continue)
    splash = SplashScreen(screen, settings_manager=settings_manager)
    # If splash returns False (user closed window), exit
    if not splash.run():
        pygame.quit()
        return

    # Splash screen'den sonra event kuyruğunu temizle
    pygame.event.clear()
    pygame.time.wait(50)
    pygame.event.clear()

    # Kaydedilmiş müzik ayarını kontrol et - ANA SAYFA MÜZİĞİNİ çal
    print("=" * 60)
    print("🎵 ANA MENÜ MÜZİĞİ BAŞLATILIYOR")
    print("=" * 60)
    music_enabled = settings_manager.get('music_enabled', True)
    print(f"   music_enabled ayarı: {music_enabled}")
    
    if music_enabled:
        menu_music = settings_manager.get('menu_music', 'main_1')
        print(f"   menu_music ayarı: {menu_music}")
        print(f"   Çalınacak track: {menu_music.lower()}")
        
        # Ses seviyelerini ayarla ve uygula (Varsayılan: %30 Müzik, %50 Efekt)
        saved_music_vol = settings_manager.get('music_volume', 0.3)
        saved_menu_music_vol = settings_manager.get('menu_music_volume', 0.3)
        saved_sfx_vol = settings_manager.get('sfx_volume', 0.5)
        
        # Ana menüdeyken menu_music_volume kullan
        menu_sound.set_music_volume(saved_menu_music_vol)
        menu_sound.set_volume(saved_sfx_vol)
        
        # Menü playlist'i başlat
        try:
            playlist = settings_manager.get_menu_music_playlist()
            playlist_keys = [menu_sound.ensure_track_available(p) for p in playlist]
            playlist_keys = [p for p in playlist_keys if p]
            if playlist_keys:
                do_shuffle = bool(settings_manager.get('music_shuffle', False))
                menu_sound.set_music_playlist(playlist_keys, loop=True, autoplay=True, force=True, shuffle=do_shuffle)
            else:
                menu_sound.play_music(menu_music.lower(), loop=True)
        except Exception:
            menu_sound.play_music(menu_music.lower(), loop=True)
    else:
        print("   Müzik KAPALI (music_enabled=False)")
    print("=" * 60)

    menu = Menu(screen, user_manager, settings_manager=settings_manager)
    # Köşe butonundaki ses durumunu başlangıçta senkronize et
    try:
        menu.set_muted(settings_manager.get('mute_all', False))
    except Exception:
        pass
    highscore_screen = HighScoreScreen(
        screen,
        score_manager,
        user_manager,
        steam_mode_scores=_load_steam_mode_scores(limit=3),
    )
    settings_screen = TabbedSettingsScreen(screen, theme_manager, settings_manager, menu_sound)
    mode_music_screen = MusicSettingsScreen(screen, settings_manager, menu_sound)
    control_settings_screen = ControlSettingsScreen(screen, settings_manager)
    block_style_screen = BlockStyleSettingsScreen(screen, theme_manager, settings_manager)
    block_workshop_screen = BlockWorkshopScreen(screen, settings_manager, theme_manager)
    piece_workshop_screen = PieceWorkshopScreen(screen, settings_manager, theme_manager)  # Yeni parça atölyesi
    achievement_screen = AchievementScreen(screen, achievement_manager)
    credits_screen = CreditsScreen(screen)
    extras_screen = ExtrasScreen(screen, user_manager)  # Ekstralar menüsü
    user_selection_screen = UserSelectionScreen(screen, user_manager)
    user_management_screen = UserManagementScreen(screen, user_manager)
    graphics_menu = None  # Grafikler menüsü
    gameplay_settings_menu = None  # Oynanış ayarları menüsü
    guide_screen = None  # Kılavuz ekranı
    
    # Campaign level seçim ekranı - önceden oluştur (lag önleme)
    campaign_level_select = CampaignLevelSelect(
        screen=screen,
        settings_manager=settings_manager,
        user_manager=user_manager,
    )

    # Kaydedilmiş sessiz mod ayarını SoundManager'a uygula.
    try:
        menu_sound.set_muted(getattr(settings_screen, 'mute_all', False))
    except Exception:
        pass
    
    # Durum — Steam profili varsa menüye, değilse kullanıcı durumuna göre
    state = 'menu' if (_steam_user_set or user_manager.has_users()) else 'user_selection'
    confirm_exit = False
    game = None
    pvp_game = None
    game_return_state = 'menu'
    _campaign_needs_refresh = False  # Campaign progress yenileme flag'i

    # Ana menü gizli kısayolları (GTA hileleri gibi).
    cheat_buffer = ''
    cheat_last_key_ms = 0
    cheat_sequences = {'arda': 'show_debug_settings', 'burak': 'campaign_unlock_all'}
    cheat_timeout_ms = 1500
    
    if constants.DEBUG_MODE:
        print("=" * 60)
        print("🎮 QUADRIX OYUNU - FULL EDITION V2.7 🎮")
        print("=" * 60)
        print("\n✨ ÖZELLİKLER:")
        print("  ✅ Tek Oyunculu Mod")
        print("  ✅ PvP (2 Oyunculu) Mod")
        print("  ✅ Başarı Sistemi (25+ Başarı) - YENİ! 🏆")
        print("  ✅ 5 Tema (Classic, Cyberpunk, Neon, Retro, Dark) - YENİ! 🎨")
        print("  ✅ Ayar Kaydetme Sistemi - YENİ! ⚙️")
        print("  ✅ Mouse Desteği - YENİ! 🖱️")
        print("  ✅ Ghost Piece (Gölge parça)")
        print("  ✅ Next Piece (Sonraki parça önizlemesi)")
        print("  ✅ Hold System (Parça saklama - C tuşu)")
        print("  ✅ High Score Sistemi (JSON'a kaydediliyor)")
        print("  ✅ Ses Efektleri")
        print("  ✅ Combo ve Quadrix Puanlama)")
        
    # Block Style Manager for main menu use (passing to TutorialMode)
    block_style_manager = BlockStyleManager(settings_manager)

    if constants.DEBUG_MODE:
        print("  ✅ Partiküller ve Animasyonlar")
        print("  ✅ Zorluk Seviyeleri")
        print("  ✅ Ana Menü ve Ayarlar")
        print("  ✅ İstatistikler ve Liderlik Tablosu")
        print("  ✅ Yeniden Boyutlandırılabilir Pencere")
        print("  ✅ Tam Ekran Modu (F12)")
        print("  ✅ Sessiz Mod (M tuşu)")
        print("\n🎯 Oyun başlatılıyor...\n")
    
    # Global M tuşu ile sessiz mod toggle fonksiyonu
    def toggle_global_mute():
        """M tuşuna basıldığında sessiz modu değiştir"""
        settings_screen.mute_all = not settings_screen.mute_all
        settings_manager.set('mute_all', settings_screen.mute_all)
        try:
            menu_sound.set_muted(settings_screen.mute_all)
        except Exception:
            pass
        # Köşe butonunu güncelle
        try:
            menu.set_muted(settings_screen.mute_all)
        except Exception:
            pass
        if constants.DEBUG_MODE:
            print("🔇 Sessiz mod: AÇIK (M tuşu)" if settings_screen.mute_all else "🔊 Sessiz mod: KAPALI (M tuşu)")

    def _apply_screen(new_screen):
        """Ekran yeniden oluşturulduğunda tüm ekran referanslarını güncelle."""
        nonlocal screen
        screen = new_screen
        # Display yeniden oluşturulunca pygame caption ve icon sıfırlanır — her seferinde geri yükle
        try:
            pygame.display.set_caption('Quadrix')
        except Exception:
            pass
        try:
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                _icon_assets_dir = str(Path(sys._MEIPASS) / 'assets')
            else:
                _icon_assets_dir = str(Path(__file__).resolve().parent.parent / 'assets')
            set_app_icon(_icon_assets_dir)
        except Exception:
            pass

        for obj in (
            menu,
            highscore_screen,
            settings_screen,
            mode_music_screen,
            control_settings_screen,
            block_style_screen,
            block_workshop_screen,
            piece_workshop_screen,
            achievement_screen,
            credits_screen,
            extras_screen,
            user_selection_screen,
            user_management_screen,
            graphics_menu,
            gameplay_settings_menu,
        ):
            if obj is not None and hasattr(obj, 'screen'):
                obj.screen = new_screen

        if game is not None and hasattr(game, 'screen'):
            game.screen = new_screen
        if pvp_game is not None and hasattr(pvp_game, 'screen'):
            pvp_game.screen = new_screen

    def _rebuild_display(width, height, *, fullscreen_value=None, resizable=True, borderless_value=None):
        """create_display çağır ve yeni screen'i her yere uygula."""
        nonlocal fullscreen
        if fullscreen_value is None:
            fullscreen_value = fullscreen
        if borderless_value is None:
            try:
                borderless_value = settings_manager.get('borderless_fullscreen', True)
            except Exception:
                borderless_value = False
        if not fullscreen_value:
            borderless_value = False
        new_screen = create_display(
            width,
            height,
            fullscreen=fullscreen_value,
            resizable=resizable,
            borderless=borderless_value,
        )
        _apply_screen(new_screen)
        # Mod değişimi sonrası birikmiş resize/video event'lerini temizle
        # (bunlar sonraki frame'de ikinci bir geçiş tetikleyebilir)
        try:
            pygame.event.pump()
            pygame.event.clear([pygame.VIDEORESIZE])
        except Exception:
            pass
        return new_screen

    def _toggle_fullscreen(width=500, height=700):
        """Tam ekranı toggle et ve display'i yeniden kur."""
        nonlocal fullscreen, last_fullscreen_toggle_ms, screen, running
        now_ms = pygame.time.get_ticks()
        if now_ms - last_fullscreen_toggle_ms < 600:
            return False
        last_fullscreen_toggle_ms = now_ms
        
        fullscreen = not fullscreen
        settings_manager.set('fullscreen', fullscreen)
        
        # --- Deneme 1: SDL2 native toggle (en güvenilir) ---
        try:
            if hasattr(pygame.display, 'toggle_fullscreen'):
                result = pygame.display.toggle_fullscreen()
                if result:
                    pygame.event.pump()
                    new_surface = pygame.display.get_surface()
                    if new_surface is not None:
                        _apply_screen(new_surface)
                        try:
                            pygame.event.clear([pygame.VIDEORESIZE])
                        except Exception:
                            pass
                        return True
        except Exception:
            pass
        
        # --- Deneme 2: Display rebuild (create_display + SDL env düzeltmeleri) ---
        try:
            _rebuild_display(width, height, fullscreen_value=fullscreen, resizable=True)
            return True
        except Exception:
            pass
        
        # --- Deneme 3: macOS için son çare restart ---
        if current_platform == 'Darwin':
            if _restart_application():
                running = False
                return True
        
        # Tümü başarısız, geri al
        fullscreen = not fullscreen
        settings_manager.set('fullscreen', fullscreen)
        return False

    def _get_fullscreen_key():
        """Ayarlardan fullscreen toggle tuşunu al."""
        try:
            controls = settings_manager.get_controls()
            fs_binding = controls.get('single_player', {}).get('fullscreen_toggle', {})
            key_name = fs_binding.get('primary', 'f12') if isinstance(fs_binding, dict) else fs_binding
            if key_name and isinstance(key_name, str):
                return pygame.key.key_code(key_name)
        except Exception:
            pass
        return pygame.K_F12  # Varsayılan

    def _check_fullscreen_toggle(event):
        """Event'in fullscreen toggle olup olmadığını kontrol et."""
        if event.type != pygame.KEYDOWN:
            return False
        custom_key = _get_fullscreen_key()
        return is_fullscreen_toggle(event.key, getattr(event, 'mod', 0), custom_key)

    def _restart_application() -> bool:
        """Uygulamayı yeniden başlat (PyInstaller onefile uyumlu)."""
        # Ayarları diske yazmaya çalış.
        try:
            settings_manager.flush_if_due()
        except Exception:
            pass
        try:
            settings_manager.save_settings()
        except Exception:
            pass

        # Yeni süreç başlat.
        try:
            exe = sys.executable
            # Frozen exe'de sys.argv[0] genelde exe yoludur; tekrar eklemeyelim.
            if getattr(sys, 'frozen', False):
                args = [exe] + (sys.argv[1:] if len(sys.argv) > 1 else [])
            else:
                args = [exe] + sys.argv
            # CWD'yi EXE'nin bulunduğu dizine ayarla (double-click davranışı)
            if getattr(sys, 'frozen', False):
                restart_cwd = os.path.dirname(sys.executable)
            else:
                restart_cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            subprocess.Popen(args, close_fds=True, cwd=restart_cwd)
        except Exception as e:
            print(f"[HATA] Yeniden başlatılamadı: {e}")
            return False

        # Bu süreçten temiz çık.
        try:
            pygame.quit()
        except Exception:
            pass
        # Eski process'in devam edip hata almasını önle
        # (display Surface quit vb.)
        os._exit(0)

    def _handle_menu(delta_ms):
        nonlocal running, state, confirm_exit, confirm_daily, daily_prompt_selected, daily_prompt_challenge, game, pvp_game, guide_screen
        nonlocal cheat_buffer, cheat_last_key_ms

        for event in pygame.event.get():
            # Global M tuşu - Sessiz mod
            if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                toggle_global_mute()
                continue
            if event.type == pygame.QUIT:
                running = False
                continue

            if confirm_daily:
                # Günlük görev bilgi paneli açıkken input burada yakalanır.
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE,):
                        confirm_daily = False
                        continue
                    if event.key in (pygame.K_LEFT, pygame.K_UP):
                        daily_prompt_selected = 0
                        continue
                    if event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                        daily_prompt_selected = 1
                        continue
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if daily_prompt_selected == 0:
                            # Oyna
                            confirm_daily = False
                            menu_sound.stop_music()
                            difficulty = settings_screen.difficulty
                            sound = settings_screen.sound_enabled
                            effects = settings_screen.effects_enabled
                            game = DailyChallengeMode(
                                difficulty,
                                sound,
                                effects,
                                achievement_manager,
                                theme_manager,
                                screen,
                                fullscreen,
                                settings_manager,
                                user_manager,
                                'daily',
                                score_manager=score_manager,
                            )
                            state = 'game'
                        else:
                            confirm_daily = False
                        continue
                if event.type == pygame.MOUSEMOTION:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                    if menu.daily_play_rect and menu.daily_play_rect.collidepoint(pos):
                        daily_prompt_selected = 0
                    elif menu.daily_cancel_rect and menu.daily_cancel_rect.collidepoint(pos):
                        daily_prompt_selected = 1
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                    if menu.daily_play_rect and menu.daily_play_rect.collidepoint(pos):
                        daily_prompt_selected = 0
                        confirm_daily = False
                        menu_sound.stop_music()
                        difficulty = settings_screen.difficulty
                        sound = settings_screen.sound_enabled
                        effects = settings_screen.effects_enabled
                        game = DailyChallengeMode(
                            difficulty,
                            sound,
                            effects,
                            achievement_manager,
                            theme_manager,
                            screen,
                            fullscreen,
                            settings_manager,
                            user_manager,
                            'daily',
                            score_manager=score_manager,
                        )
                        state = 'game'
                    elif menu.daily_cancel_rect and menu.daily_cancel_rect.collidepoint(pos):
                        daily_prompt_selected = 1
                        confirm_daily = False
                    continue
                continue

            if confirm_exit:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_n):
                        confirm_exit = False
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_y):
                        running = False
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                    if menu.exit_yes_rect and menu.exit_yes_rect.collidepoint(pos):
                        running = False
                    elif menu.exit_no_rect and menu.exit_no_rect.collidepoint(pos):
                        confirm_exit = False
                    continue
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and not menu._is_modal_open():
                confirm_exit = True
                continue

            # Gizli debug ayarlarını aç: ana menüde "arda" yaz.
            if event.type == pygame.KEYDOWN:
                ch = getattr(event, 'unicode', '') or ''
                if ch:
                    now_ms = pygame.time.get_ticks()
                    if now_ms - cheat_last_key_ms > cheat_timeout_ms:
                        cheat_buffer = ''
                    cheat_last_key_ms = now_ms

                    ch = ch.lower()
                    if ch.isalpha():
                        _max_cheat_len = max(len(s) for s in cheat_sequences)
                        cheat_buffer = (cheat_buffer + ch)[-_max_cheat_len:]
                        for seq, cheat_action in cheat_sequences.items():
                            if cheat_buffer.endswith(seq):
                                if cheat_action == 'show_debug_settings':
                                    # Runtime-only: diske yazma (oyun kapanınca tekrar gizli).
                                    try:
                                        if not settings_manager.get('show_debug_settings', False):
                                            settings_manager.settings['show_debug_settings'] = True
                                    except Exception:
                                        pass
                                    try:
                                        settings_screen.sync_from_settings_manager()
                                    except Exception:
                                        pass
                                elif cheat_action == 'campaign_unlock_all':
                                    try:
                                        currently_on = getattr(campaign_level_select, 'debug_unlock_all', False)
                                        if currently_on:
                                            campaign_level_select.debug_unlock_all = False
                                            # Taze progress yükle (kampanya oynanmış ama henüz refresh edilmemiş olabilir)
                                            try:
                                                campaign_level_select.progress = campaign_level_select._load_progress()
                                            except Exception:
                                                pass
                                            highest = campaign_level_select.progress.get('highest_level', 0)
                                            campaign_level_select.current_world = max(1, (highest - 1) // 20 + 1) if highest > 0 else 1
                                            campaign_level_select._update_selection_for_world()
                                            campaign_level_select.scroll_offset = 0
                                            campaign_level_select.hovered_level = None
                                        else:
                                            campaign_level_select.debug_unlock_all = True
                                    except Exception:
                                        pass
                                cheat_buffer = ''
                                break

            action = menu.handle_input(event)
            
            # === CAMPAIGN MODE ===
            if action == 'campaign_mode':
                confirm_exit = False
                state = 'campaign_select'
            elif isinstance(action, str) and action.startswith('campaign_quick_start_'):
                confirm_exit = False
                try:
                    level_num = int(action.split('_')[-1])
                except Exception:
                    level_num = 1
                level_num = max(1, min(100, level_num))

                menu_sound.stop_music()
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled

                game = CampaignMode(
                    current_level=level_num,
                    difficulty=difficulty,
                    sound_enabled=sound,
                    effects_enabled=effects,
                    achievement_manager=achievement_manager,
                    theme_manager=theme_manager,
                    screen=screen,
                    fullscreen=fullscreen,
                    settings_manager=settings_manager,
                    user_manager=user_manager,
                    score_manager=score_manager,
                )
                state = 'game'
            
            elif action in ('single_player', 'Tek Oyunculu', 'Single Player'):
                # Tutorial Check
                if not user_manager.is_tutorial_completed():
                    if _show_tutorial_prompt(screen):
                        # Start Tutorial
                        menu_sound.stop_music()
                        game = TutorialMode(
                            'Normal',
                            settings_screen.sound_enabled,
                            settings_screen.effects_enabled,
                            achievement_manager,
                            theme_manager,
                            screen,
                            fullscreen,
                            settings_manager,
                            user_manager,
                            sound_manager=menu_sound,
                            score_manager=score_manager,
                            block_style_manager=block_style_manager
                        )
                        state = 'game'
                        continue
                    else:
                        # Skip Tutorial
                        user_manager.set_tutorial_completed(True)

                if not _show_mode_intro_popup(screen, 'classic', settings_manager):
                    continue
                confirm_exit = False
                target_game_music = settings_screen.game_music.lower()
                same_track_playing = (
                    settings_screen.music_enabled
                    and menu_sound.current_track_name == target_game_music
                    and pygame.mixer.music.get_busy()
                )
                if not same_track_playing:
                    menu_sound.stop_music()
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = Game(
                    difficulty,
                    sound,
                    effects,
                    achievement_manager,
                    theme_manager,
                    screen,
                    fullscreen,
                    settings_manager,
                    user_manager,
                    'classic',
                    sound_manager=menu_sound,
                    score_manager=score_manager,
                )
                state = 'game'
            elif action == 'tutorial_mode':
                menu_sound.stop_music()
                game = TutorialMode(
                    'Normal',
                    settings_screen.sound_enabled,
                    settings_screen.effects_enabled,
                    achievement_manager,
                    theme_manager,
                    screen,
                    fullscreen,
                    settings_manager,
                    user_manager,
                    sound_manager=menu_sound,
                    score_manager=score_manager,
                    block_style_manager=block_style_manager
                )
                state = 'game'
            elif action in ('new_gen_tetris', 'Yeni Nesil Quadrix', 'Kart Ustalığı', 'New Gen Quadrix', 'Card Mastery'):
                if not _show_mode_intro_popup(screen, 'mystery', settings_manager):
                    continue
                confirm_exit = False
                menu_sound.stop_music()
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = MysteryMode(
                    difficulty,
                    sound,
                    effects,
                    achievement_manager,
                    theme_manager,
                    screen,
                    fullscreen,
                    settings_manager,
                    user_manager,
                    'mystery',
                    score_manager=score_manager,
                )
                state = 'game'
            elif action in ('pvp_2_players', 'PvP (2 Oyuncu)', 'PvP (2 Players)'):
                if not _show_mode_intro_popup(screen, 'pvp', settings_manager):
                     continue
                confirm_exit = False
                # Menü müziğini durdur; PvP kendi müziğini başlatacak.
                menu_sound.stop_music()
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                pvp_game = PvPGame(
                    sound,
                    effects,
                    screen,
                    fullscreen,
                    user_manager,
                    settings_manager,
                    sound_manager=menu_sound,
                )
                state = 'pvp'
            elif action in ('daily_challenge', t('daily_challenge')):
                confirm_exit = False
                allowed, reason = user_manager.can_play_daily() if user_manager else (False, 'Kullanıcı bulunamadı!')
                if not allowed:
                    menu.show_info(reason or 'Daily Challenge kilitli!')
                    continue
                confirm_daily = True
                daily_prompt_selected = 0
                try:
                    daily_prompt_challenge = DailyChallengeMode.get_today_challenge(user_manager=user_manager)
                except Exception:
                    daily_prompt_challenge = None
            elif action in ('extras', 'Ekstralar', 'Oyun Modları', 'Extras', 'Game Modes', t('extras')):
                confirm_exit = False
                state = 'extras'
            elif action in ('achievements', 'Başarılar', 'Achievements'):
                confirm_exit = False
                state = 'achievements'
            elif action in ('high_scores', 'High Scores', t('high_scores'), 'Yüksek Skorlar', 'En Yuksek Skorlar'):
                confirm_exit = False
                state = 'highscores'
            elif action in ('switch_user', 'Kullanıcı Değiştir', 'Switch User'):
                confirm_exit = False
                state = 'user_selection'
            elif action in ('settings', 'Ayarlar', 'Settings'):
                confirm_exit = False
                state = 'settings'
            elif action == 'toggle_mute_quick':
                # Köşe butonundan hızlı sessize alma
                toggle_global_mute()
                menu.set_muted(settings_screen.mute_all)
            elif action in ('guide', 'Kılavuz', 'Guide'):
                confirm_exit = False
                state = 'guide'
                guide_screen = GuideScreen(screen, settings_manager)
            elif action in ('credits', 'Emeği Geçenler', 'Credits'):
                confirm_exit = False
                state = 'credits'
            elif action == 'main_menu':
                confirm_exit = False
                state = 'menu'
            elif action == 'piece_workshop':
                confirm_exit = False
                state = 'piece_workshop'
            elif action == 'block_styles':
                confirm_exit = False
                state = 'block_styles'
            elif action == 'language_changed':
                # Ana menüden dil değiştirildiğinde tüm ekranları senkronize et
                try:
                    settings_screen.sync_from_settings_manager()
                except Exception:
                    pass
                try:
                    extras_screen._refresh_fonts()
                except Exception:
                    pass
                try:
                    if hasattr(achievement_screen, '_refresh_fonts_for_language'):
                        achievement_screen._refresh_fonts_for_language(force=True)
                except Exception:
                    pass
            elif action in ('exit', 'Çıkış', 'Exit'):
                confirm_exit = True
            elif action == 'toggle_fullscreen':
                confirm_exit = False
                _toggle_fullscreen(500, 700)

        if user_manager:
            status = user_manager.get_daily_status()
        else:
            status = None

        today_challenge = None
        try:
            today_challenge = DailyChallengeMode.get_today_challenge(user_manager=user_manager)
        except Exception:
            today_challenge = None
        challenge_title = (today_challenge or {}).get('name') or ''
        if status:
            if status.get('completed'):
                menu.set_daily_hint(t('daily_completed_hint'), (130, 255, 190), challenge_title=challenge_title)
            else:
                remaining = max(0, DAILY_MAX_FAILURES - status.get('fails', 0))
                color = (150, 255, 190) if remaining > 0 else (255, 120, 120)
                menu.set_daily_hint(
                    t('daily_lives_remaining_hint').format(remaining=remaining, max=DAILY_MAX_FAILURES),
                    color,
                    challenge_title=challenge_title,
                )
        else:
            menu.set_daily_hint(t('select_user_hint'), (255, 200, 140), challenge_title=challenge_title)

        menu.show_exit_prompt = confirm_exit
        menu.show_daily_prompt = confirm_daily
        menu.daily_prompt_selected = daily_prompt_selected
        menu.daily_prompt_challenge = daily_prompt_challenge
        menu.draw()
        return True

    def _handle_credits(delta_ms):
        nonlocal running, state

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if _check_fullscreen_toggle(event):
                _toggle_fullscreen(500, 700)
            action = credits_screen.handle_input(event)
            if action == 'back':
                state = 'menu'
        credits_screen.draw()
        return True

    def _handle_highscores(delta_ms):
        nonlocal running, state

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if _check_fullscreen_toggle(event):
                _toggle_fullscreen(500, 700)
            action = highscore_screen.handle_input(event)
            if action == 'back':
                state = 'menu'
        highscore_screen.draw()
        return True

    def _handle_settings(delta_ms):
        nonlocal running, state, graphics_menu, gameplay_settings_menu, game, guide_screen, fullscreen, pvp_game

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            action = settings_screen.handle_input(event)
            if action == 'back':
                state = 'menu'
            elif action == 'language_changed':
                # Ayarlardan dil değiştirildiğinde tüm ekranları senkronize et
                try:
                    menu.font_menu = retro_style.get_font(32, bold=True)
                    menu.font_small = retro_style.get_font(24)
                    menu._update_options()
                except Exception:
                    pass
                try:
                    extras_screen._refresh_fonts()
                except Exception:
                    pass
                try:
                    if hasattr(achievement_screen, '_refresh_fonts_for_language'):
                        achievement_screen._refresh_fonts_for_language(force=True)
                except Exception:
                    pass
            elif action == 'toggle_music':
                # Müzik ayarı değişti
                if settings_screen.music_enabled and not settings_screen.mute_all:
                    menu_music = settings_manager.get('menu_music', 'main_1')
                    try:
                        playlist = settings_manager.get_menu_music_playlist()
                        playlist_keys = [menu_sound.ensure_track_available(p) for p in playlist]
                        playlist_keys = [p for p in playlist_keys if p]
                        if playlist_keys:
                            do_shuffle = bool(settings_manager.get('music_shuffle', False))
                            menu_sound.set_music_playlist(playlist_keys, loop=True, autoplay=True, force=True, shuffle=do_shuffle)
                        else:
                            menu_sound.play_music(menu_music.lower(), loop=True)
                    except Exception:
                        menu_sound.play_music(menu_music.lower(), loop=True)
                else:
                    menu_sound.stop_music()
            elif action == 'toggle_sound':
                # Ses ayarı değişti
                if settings_screen.mute_all:
                    menu_sound.sfx_enabled = False
                else:
                    menu_sound.sfx_enabled = settings_screen.sound_enabled
            elif action == 'change_music_volume':
                # Müzik seviyesi değişti
                menu_sound.set_music_volume(settings_screen.music_volume)
                print(f"🔊 Müzik seviyesi: {int(settings_screen.music_volume * 100)}%")
            elif action == 'change_menu_music_volume':
                # Ana menü müzik seviyesi değişti
                menu_sound.set_music_volume(settings_screen.menu_music_volume)
                settings_manager.set('menu_music_volume', settings_screen.menu_music_volume)
                print(f"🔊 Ana menü müzik seviyesi: {int(settings_screen.menu_music_volume * 100)}%")
            elif action == 'change_sfx_volume':
                # Efekt seviyesi değişti
                menu_sound.set_volume(settings_screen.sfx_volume)
                print(f"🔊 Efekt seviyesi: {int(settings_screen.sfx_volume * 100)}%")
            elif action == 'toggle_mute':
                # Sessiz mod değişti
                try:
                    menu_sound.set_muted(settings_screen.mute_all)
                except Exception:
                    pass
                print("🔇 Sessiz mod: AÇIK" if settings_screen.mute_all else "🔊 Sessiz mod: KAPALI")
            elif action == 'toggle_background' or action == 'toggle_background_enabled':
                # Arka plan ayarı değişti
                enabled = True
                try:
                    enabled = bool(settings_manager.get('background_enabled', True))
                except Exception:
                    enabled = True
                try:
                    retro_style.set_background_enabled(enabled)
                except Exception:
                    pass
                if game:
                    try:
                        game.background_manager.enabled = enabled
                        game.single_background.enabled = enabled
                        game.outer_background.enabled = enabled
                    except Exception:
                        pass
                if pvp_game:
                    try:
                        pvp_game.board_background.enabled = enabled
                        pvp_game.outer_background.enabled = enabled
                    except Exception:
                        pass
            elif action == 'change_menu_music':
                # Ana Sayfa Müziği değişti
                if settings_screen.music_enabled and not settings_screen.mute_all and state == 'settings':
                    music_name = settings_screen.menu_music.lower()
                    menu_sound.play_music(music_name, loop=True)
                    print(f"🎵 Ana sayfa müziği değişti: {settings_screen.menu_music}")
            elif action == 'change_game_music':
                # Oyun İçi Müzik değişti
                print(f"🎮 Oyun içi müzik ayarlandı: {settings_screen.game_music}")
            elif action == 'mode_playlist_changed':
                pass
            elif action == 'toggle_debug':
                # Debug modu değişti
                constants.DEBUG_MODE = settings_screen.debug_mode
                status = "AÇIK" if constants.DEBUG_MODE else "KAPALI"
                print(f"🐛 Debug Modu: {status}")
            elif action == 'toggle_card_mode_debug':
                pass  # Kart debug değişti, sadece settings'e kaydediliyor
            elif action == 'apply_display_mode':
                # Pencere/Tam ekran modu veya çözünürlük değişti (sekmeli ekrandan)
                prev_fullscreen = fullscreen
                fullscreen = settings_manager.get('fullscreen', True)
                borderless = settings_manager.get('borderless_fullscreen', True)
                resolution = settings_manager.get('resolution', 'auto')
                if resolution == 'auto':
                    native_w, native_h = get_native_resolution()
                    width = max(800, min(1280, int(native_w * 0.8)))
                    height = max(600, min(900, int(native_h * 0.8)))
                else:
                    try:
                        width, height = map(int, resolution.split('x'))
                    except Exception:
                        width, height = 1024, 768

                fullscreen_changed = bool(prev_fullscreen) != bool(fullscreen)

                if fullscreen_changed:
                    # --- Deneme 1: SDL2 native toggle ---
                    toggled = False
                    try:
                        if hasattr(pygame.display, 'toggle_fullscreen'):
                            result = pygame.display.toggle_fullscreen()
                            if result:
                                pygame.event.pump()
                                new_surface = pygame.display.get_surface()
                                if new_surface is not None:
                                    _apply_screen(new_surface)
                                    toggled = True
                    except Exception:
                        pass

                    # --- Deneme 2: Display rebuild ---
                    if not toggled:
                        try:
                            new_screen = create_display(
                                width, height,
                                fullscreen=fullscreen,
                                resizable=True,
                                borderless=(borderless if fullscreen else False),
                            )
                            _apply_screen(new_screen)
                            toggled = True
                        except Exception:
                            pass

                    # --- Deneme 3: Restart (son çare) ---
                    if not toggled:
                        if _restart_application():
                            running = False
                            return False
                        # Restart da başarısız, geri al
                        fullscreen = prev_fullscreen
                        settings_manager.set('fullscreen', fullscreen)
                else:
                    # Sadece çözünürlük değişti; restart gerekmez
                    resolution = settings_manager.get('resolution', 'auto')
                    if resolution == 'auto':
                        native_w, native_h = get_native_resolution()
                        width = max(800, min(1280, int(native_w * 0.8)))
                        height = max(600, min(900, int(native_h * 0.8)))
                    else:
                        try:
                            width, height = map(int, resolution.split('x'))
                        except Exception:
                            width, height = 1024, 768
                    new_screen = create_display(
                        width, height,
                        fullscreen=fullscreen,
                        resizable=True,
                        borderless=(borderless if fullscreen else False),
                    )
                    _apply_screen(new_screen)
            elif action == 'change_bg_transparency':
                # Arka plan şeffaflığı değişti (sekmeli ekrandan)
                try:
                    trans_value = float(settings_manager.get('bg_transparency', 0.3))
                except Exception:
                    trans_value = 0.3
                try:
                    retro_style.set_background_transparency(trans_value)
                except Exception:
                    pass
                if game:
                    try:
                        game.background_manager.set_transparency(trans_value)
                        game.single_background.set_transparency(trans_value)
                        game.outer_background.set_transparency(trans_value)
                    except Exception:
                        pass
                if pvp_game:
                    try:
                        pvp_game.update_transparency(trans_value)
                    except Exception:
                        pass
            elif action == 'change_menu_transparency':
                # Menü şeffaflığı değişti (sekmeli ekrandan)
                try:
                    menu_value = float(settings_manager.get('menu_transparency', 1.0))
                except Exception:
                    menu_value = 1.0
                try:
                    retro_style.set_menu_transparency(menu_value)
                except Exception:
                    pass
            elif action == 'restart_now' or action == 'vsync_changed':
                # VSync değişikliği veya yeniden başlatma gerekiyor
                if _restart_application():
                    running = False
                    return False
            elif action == 'select_background':
                # Arka plan resmi seç
                from file_dialog import open_file_dialog
                filepath = open_file_dialog(
                    title="Arka Plan Resmi Seç",
                    filetypes=[
                        ("Resim Dosyaları", "*.png *.jpg *.jpeg *.bmp"),
                        ("PNG", "*.png"),
                        ("JPEG", "*.jpg *.jpeg"),
                        ("Tüm Dosyalar", "*.*")
                    ],
                )
                if filepath:
                    settings_screen.custom_background = filepath
                    settings_manager.set('custom_background', filepath)
                    print(f"🖼️ Arka plan resmi seçildi: {filepath}")
            elif action == 'mode_music':
                settings_screen.focus_tab('audio')
            elif action and action.startswith('edit_mode_playlist:'):
                mode_key = action.split(':', 1)[1]
                try:
                    settings_screen.open_mode_playlist_editor(mode_key)
                except Exception:
                    pass
            elif action == 'block_styles':
                state = 'block_styles'
            elif action == 'block_workshop':
                block_workshop_screen.refresh_styles()
                block_workshop_screen.reload_from_settings()
                state = 'block_workshop'
            elif action == 'piece_workshop':
                state = 'piece_workshop'
            elif action == 'controls':
                settings_screen.focus_tab('controls')
            elif action == 'graphics':
                settings_screen.focus_tab('display')
            elif action == 'gameplay':
                settings_screen.focus_tab('game')
            elif action == 'theme':
                settings_screen.focus_tab('customize', 'theme')
            elif action == 'toggle_fullscreen':
                _toggle_fullscreen(500, 700)
            elif action == 'quit_game':
                # Kullanıcı onay kutusunda 'Evet' seçti; oyunu kapat (oto yeniden açılma yok)
                running = False

        settings_screen.draw()
        return True

    def _handle_mode_music(delta_ms):
        nonlocal state, running

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                return True

            if _check_fullscreen_toggle(event):
                _toggle_fullscreen(500, 700)
                continue

            action = mode_music_screen.handle_input(event)
            if action == 'back':
                state = 'settings'
                return True
            elif action == 'toggle_fullscreen':
                _toggle_fullscreen(500, 700)

        try:
            mode_music_screen.draw()
        except Exception:
            state = 'settings'
        return True

    def _handle_controls(delta_ms):
        nonlocal state
        settings_screen.focus_tab('controls')
        state = 'settings'
        return _handle_settings(delta_ms)

    def _handle_guide(delta_ms):
        nonlocal running, state, guide_screen

        if guide_screen is None:
            state = 'menu'
            return True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            action = guide_screen.handle_input(event)
            if action == 'back':
                state = 'menu'
            elif action == 'toggle_fullscreen':
                _toggle_fullscreen(500, 700)
        guide_screen.draw()
        return True

    def _handle_graphics(delta_ms):
        nonlocal state
        settings_screen.focus_tab('display')
        state = 'settings'
        return _handle_settings(delta_ms)

    def _handle_gameplay_settings(delta_ms):
        nonlocal state
        settings_screen.focus_tab('game')
        state = 'settings'
        return _handle_settings(delta_ms)

    def _handle_block_styles(delta_ms):
        nonlocal running, state

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            action = block_style_screen.handle_input(event)
            if action == 'back':
                state = 'menu'
            elif action == 'toggle_fullscreen':
                _toggle_fullscreen(500, 700)
        block_style_screen.draw()
        return True

    def _handle_block_workshop(delta_ms):
        nonlocal running, state

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                try:
                    block_workshop_screen.save_on_exit()
                except Exception:
                    pass
                running = False
            action = block_workshop_screen.handle_input(event)
            if action == 'back':
                state = 'menu'
            elif action == 'toggle_fullscreen':
                _toggle_fullscreen(500, 700)
        block_workshop_screen.draw()
        return True

    def _handle_piece_workshop(delta_ms):
        nonlocal running, state

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            action = piece_workshop_screen.handle_input(event)
            if action == 'back':
                state = 'menu'
            elif action == 'toggle_fullscreen':
                _toggle_fullscreen(500, 700)
        piece_workshop_screen.draw()
        return True

    def _handle_achievements(delta_ms):
        nonlocal running, state

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if _check_fullscreen_toggle(event):
                _toggle_fullscreen(500, 700)
            action = achievement_screen.handle_input(event)
            if action == 'back':
                state = 'menu'
        achievement_screen.draw()
        return True

    def _handle_extras(delta_ms):
        nonlocal running, state, game, game_return_state

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if _check_fullscreen_toggle(event):
                _toggle_fullscreen(500, 700)

            action = extras_screen.handle_input(event)
            if action == 'Geri':
                state = 'menu'
            elif action == 'Campaign Mode':
                state = 'campaign_select'
            elif action == 'Sprint Mode':
                if not _show_mode_intro_popup(screen, 'sprint', settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = SprintMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'sprint', score_manager=score_manager)
                state = 'game'
            elif action == 'Ultra Mode':
                if not _show_mode_intro_popup(screen, 'ultra', settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = UltraMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'ultra', score_manager=score_manager)
                state = 'game'
            elif action == 'Zen Mode':
                # Zen Mode için optimize edilmiş başlangıç penceresi (Intro + Ayar)
                auto_clear_rows = _show_zen_start_popup(screen, board_height=20, settings_manager=settings_manager)
                if auto_clear_rows is False:
                    continue  # İptal edildi
                menu_sound.stop_music()
                game_return_state = 'extras'
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = ZenMode('Kolay', sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'zen', score_manager=score_manager, auto_clear_rows=auto_clear_rows)
                state = 'game'
            elif action == 'Hardcore Mode':
                if not _show_mode_intro_popup(screen, 'hardcore', settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = HardcoreMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'hardcore', score_manager=score_manager)
                state = 'game'
            elif action in ('Quadrix 2', 'Quadrix Extra'):
                if not _show_mode_intro_popup(screen, 'tetris2', settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = Tetris2Mode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'tetris2', score_manager=score_manager)
                state = 'game'
            elif action in ('Mystery Mode', 'Kart Ustalığı', 'Yeni Nesil Quadrix', 'New Gen Quadrix', 'Card Mastery'):
                if not _show_mode_intro_popup(screen, 'mystery', settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = MysteryMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'mystery', score_manager=score_manager)
                state = 'game'
            elif action == 'Wide Mode':
                if not _show_mode_intro_popup(screen, 'wide', settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = WideMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'wide', score_manager=score_manager)
                state = 'game'
            elif action == 'Survival Mode':
                if not _show_mode_intro_popup(screen, 'survival', settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = SurvivalMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'survival', score_manager=score_manager)
                state = 'game'
            elif action == 'Cascade Mode':
                if not _show_mode_intro_popup(screen, 'cascade', settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = CascadeMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'cascade', score_manager=score_manager)
                state = 'game'
            elif action == 'Classic Mode':
                if not _show_mode_intro_popup(screen, 'classic', settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = Game(
                    difficulty,
                    sound,
                    effects,
                    achievement_manager,
                    theme_manager,
                    screen,
                    fullscreen,
                    settings_manager,
                    user_manager,
                    'classic',
                    sound_manager=menu_sound,
                    score_manager=score_manager,
                )
                state = 'game'

        extras_screen.draw()
        return True

    def _handle_game(delta_ms):
        nonlocal running, state, game, game_return_state, _campaign_needs_refresh, highscore_screen

        if not game:
            state = 'menu'
            return False

        result = game.handle_input()
        
        # QUIT olayı kontrolü - önce kontrol et
        if result is False:
            running = False
            return False
        
        if result == 'toggle_fullscreen':
            _toggle_fullscreen(500, 700)
            if not running:  # macOS restart tetiklendi
                return False
            # Oyuna yeni screen'i ver
            game.screen = screen
            game.window_width = screen.get_width()
            game.window_height = screen.get_height()
            game.fullscreen = fullscreen
            game._cached_offset_key = None  # Cache'i temizle
            game._cached_cell_size_key = None
        elif result in ('menu', 'campaign_select', 'main_menu'):
            if not game.game_over:
                playtime = game.game_time // 1000
                if user_manager:
                    user_manager.update_user_stats(
                        games=1,
                        score=game.board.score,
                        lines=game.board.lines_cleared,
                        tetrises=game.board.tetrises,
                        combos=game.board.combo,
                        highest_combo=game.board.combo,
                        level=game.board.level,
                        playtime=playtime,
                        mode=game.game_mode,
                    )
                    print(f"Kullanıcı istatistikleri güncellendi (ESC): {game.game_mode.upper()} - {game.board.score} puan")

                if achievement_manager:
                    achievement_manager.stats['total_games'] = achievement_manager.stats.get('total_games', 0) + 1
                    achievement_manager.stats['total_lines'] = achievement_manager.stats.get('total_lines', 0) + game.board.lines_cleared

                    new_achievements = achievement_manager.update_stats(
                        score=game.board.score,
                        lines=game.board.lines_cleared,
                        level=game.board.level,
                        tetrises=game.board.tetrises,
                        combo=game.board.combo,
                    )

                    for ach_id in new_achievements:
                        achievement = achievement_manager.get_achievement(ach_id)
                        if achievement:
                            print(f"Başarı Açıldı: {achievement['name']} - {achievement['description']}")

                score_manager.add_score(
                    game.board.score,
                    game.board.lines_cleared,
                    game.board.level,
                    game.board.tetrises,
                    playtime,
                )

            if isinstance(game, DailyChallengeMode):
                game.record_daily_outcome(game.challenge_completed)

            # Campaign modundan çıkış - level select'e dön
            if isinstance(game, CampaignMode):
                _campaign_needs_refresh = True  # Progress'i yenile
                if result == 'main_menu':
                    state = 'menu'
                else:
                    state = 'campaign_select'
            else:
                if result == 'main_menu':
                    state = 'menu'
                else:
                    state = 'extras' if game_return_state == 'extras' else 'menu'
            
            target_menu_music = settings_manager.get('menu_music', settings_screen.menu_music).lower()
            menu_track_playing = (
                settings_screen.music_enabled
                and menu_sound.current_track_name == target_menu_music
                and pygame.mixer.music.get_busy()
            )
            if getattr(game, 'sound', None) and not menu_track_playing:
                game.sound.stop_music()
            game = None
            if settings_screen.music_enabled:
                # Ana menüye dönünce menu_music_volume uygula
                _menu_vol = settings_manager.get('menu_music_volume', 0.3)
                menu_sound.set_music_volume(_menu_vol)
                menu_music = settings_manager.get('menu_music', 'main_1')
                try:
                    playlist = settings_manager.get_menu_music_playlist()
                    playlist_keys = [menu_sound.ensure_track_available(p) for p in playlist]
                    playlist_keys = [p for p in playlist_keys if p]
                    if playlist_keys:
                        do_shuffle = bool(settings_manager.get('music_shuffle', False))
                        menu_sound.set_music_playlist(playlist_keys, loop=True, autoplay=True, force=True, shuffle=do_shuffle)
                    else:
                        menu_sound.play_music(menu_music.lower(), loop=True)
                except Exception:
                    menu_sound.play_music(menu_music.lower(), loop=True)
                print(f"🎵 Ana sayfa müziği başlatıldı: {menu_music}")
            # Oyun bitti — Steam skor tablosunu güncelle ve HighScoreScreen'e yansıt
            try:
                fresh_scores = _load_steam_mode_scores(force=True, limit=3)
                highscore_screen.steam_mode_scores = fresh_scores
            except Exception:
                pass
            return False
        
        # Campaign: Sonraki level'a geç
        elif result == 'next_level' and isinstance(game, CampaignMode):
            next_level = game.get_next_level_num()
            if next_level:
                # Yeni level için CampaignMode oluştur
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                
                game = CampaignMode(
                    current_level=next_level,
                    difficulty=difficulty,
                    sound_enabled=sound,
                    effects_enabled=effects,
                    achievement_manager=achievement_manager,
                    theme_manager=theme_manager,
                    screen=screen,
                    fullscreen=fullscreen,
                    settings_manager=settings_manager,
                    user_manager=user_manager,
                    score_manager=score_manager,
                )
                return True
            else:
                # Son level - tebrikler ve menüye dön
                _campaign_needs_refresh = True  # Progress'i yenile
                state = 'campaign_select'
                game = None
                return False

        game.update(delta_ms)
        game.draw()
        try:
            if getattr(game, 'sound', None):
                game.sound.update_music_playlist()
        except Exception:
            pass
        return True

    def _handle_pvp(delta_ms):
        nonlocal running, state, pvp_game

        if not pvp_game:
            state = 'menu'
            return False

        result = pvp_game.handle_input()
        
        # QUIT olayı kontrolü - önce kontrol et
        if result is False:
            running = False
            return False
        
        if result == 'toggle_fullscreen':
            _toggle_fullscreen(500, 700)
            if not running:  # macOS restart tetiklendi
                return False
            pvp_game.screen = screen
            pvp_game.window_width = screen.get_width()
            pvp_game.window_height = screen.get_height()
            pvp_game.fullscreen = fullscreen
            pvp_game._cached_offset_key = None
            pvp_game._cached_cell_size_key = None
        elif result == 'menu':
            state = 'menu'
            pvp_game = None
            if settings_screen.music_enabled and not getattr(settings_screen, 'mute_all', False):
                _menu_vol = settings_manager.get('menu_music_volume', 0.3)
                menu_sound.set_music_volume(_menu_vol)
                menu_music = settings_manager.get('menu_music', 'main_1')
                menu_sound.play_music(menu_music.lower(), loop=True)
                print(f"🎵 Ana sayfa müziği başlatıldı: {menu_music}")
            return False

        pvp_game.update(delta_ms)
        pvp_game.draw()
        try:
            if getattr(pvp_game, 'sound', None):
                pvp_game.sound.update_music_playlist()
        except Exception:
            pass
        return True

    def _handle_user_selection(delta_ms):
        nonlocal running, state, score_manager, achievement_manager, highscore_screen, achievement_screen, game

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            action = user_selection_screen.handle_input(event)
            if action in ('user_selected', 'new_user_created'):
                achievements_file = user_manager.get_achievements_file()
                highscores_file = user_manager.get_highscores_file()
                score_manager = ScoreManager(highscores_file)
                achievement_manager = AchievementManager(achievements_file)
                highscore_screen = HighScoreScreen(
                    screen,
                    score_manager,
                    user_manager,
                    steam_mode_scores=_load_steam_mode_scores(limit=3),
                )
                achievement_screen = AchievementScreen(screen, achievement_manager)
                user_selection_screen.users_list = list(user_manager.get_all_users().keys())
                state = 'menu'
                # Yeni kullanıcı oluşturulduğunda tutorial pop-up göster
                if action == 'new_user_created':
                    user_manager.set_tutorial_completed(False)
                    if _show_tutorial_prompt(screen):
                        menu_sound.stop_music()
                        game = TutorialMode(
                            'Normal',
                            settings_screen.sound_enabled,
                            settings_screen.effects_enabled,
                            achievement_manager,
                            theme_manager,
                            screen,
                            fullscreen,
                            settings_manager,
                            user_manager,
                            sound_manager=menu_sound,
                            score_manager=score_manager,
                            block_style_manager=block_style_manager
                        )
                        state = 'game'
                    else:
                        user_manager.set_tutorial_completed(True)
            elif action == 'edit_user':
                target_user = user_selection_screen.get_selected_username()
                if target_user:
                    user_management_screen.open_edit_for(target_user)
                    state = 'user_management'
            elif action == 'back_to_menu':
                state = 'menu'

        user_selection_screen.update()
        user_selection_screen.draw()
        return True

    def _handle_user_management(delta_ms):
        nonlocal running, state, score_manager, achievement_manager, highscore_screen, achievement_screen

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            action = user_management_screen.handle_input(event)
            if action == 'back':
                achievements_file = user_manager.get_achievements_file()
                highscores_file = user_manager.get_highscores_file()
                score_manager = ScoreManager(highscores_file)
                achievement_manager = AchievementManager(achievements_file)
                highscore_screen = HighScoreScreen(
                    screen,
                    score_manager,
                    user_manager,
                    steam_mode_scores=_load_steam_mode_scores(limit=3),
                )
                achievement_screen = AchievementScreen(screen, achievement_manager)
                user_management_screen.users_list = list(user_manager.get_all_users().keys())
                user_selection_screen.users_list = list(user_manager.get_all_users().keys())
                state = 'user_selection'

        user_management_screen.update()
        user_management_screen.draw()
        return True


    def _handle_campaign_select(delta_ms):
        nonlocal running, state, game, campaign_level_select, _campaign_needs_refresh
        
        # İlerleme bilgisini yenile (sadece gerektiğinde)
        if _campaign_needs_refresh:
            campaign_level_select.progress = campaign_level_select._load_progress()
            _campaign_needs_refresh = False
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                return True
            
            action = campaign_level_select.handle_input(event)
            
            if action == 'back':
                state = 'menu'
                return True
            
            # Level seçildi: play_X formatında
            if action and action.startswith('play_'):
                try:
                    level_num = int(action.split('_')[1])
                    
                    # Müziği durdur
                    menu_sound.stop_music()
                    
                    # Oyun ayarları
                    difficulty = settings_screen.difficulty
                    sound = settings_screen.sound_enabled
                    effects = settings_screen.effects_enabled
                    
                    # CampaignMode başlat
                    game = CampaignMode(
                        current_level=level_num,
                        difficulty=difficulty,
                        sound_enabled=sound,
                        effects_enabled=effects,
                        achievement_manager=achievement_manager,
                        theme_manager=theme_manager,
                        screen=screen,
                        fullscreen=fullscreen,
                        settings_manager=settings_manager,
                        user_manager=user_manager,
                        score_manager=score_manager,
                    )
                    
                    state = 'game'
                    return True
                except (ValueError, IndexError):
                    pass
        
        # Animasyonları güncelle
        campaign_level_select.update(delta_ms / 1000.0)  # ms -> saniye
        
        # Ekranı çiz
        campaign_level_select.draw()
        return True

    STATE_HANDLERS = {
        'menu': _handle_menu,
        'credits': _handle_credits,
        'highscores': _handle_highscores,
        'settings': _handle_settings,
        'mode_music': _handle_mode_music,
        'controls': _handle_controls,
        'guide': _handle_guide,
        'graphics': _handle_graphics,
        'gameplay_settings': _handle_gameplay_settings,
        'block_styles': _handle_block_styles,
        'block_workshop': _handle_block_workshop,
        'piece_workshop': _handle_piece_workshop,
        'achievements': _handle_achievements,
        'extras': _handle_extras,
        'game': _handle_game,
        'pvp': _handle_pvp,
        'user_selection': _handle_user_selection,
        'user_management': _handle_user_management,
        'campaign_select': _handle_campaign_select,
    }
    
    running = True
    confirm_daily = False
    daily_prompt_selected = 0
    daily_prompt_challenge = None
    
    # Ekran geçiş efekti için state takibi
    _previous_state = state
    
    # Geçiş tipleri (state çiftlerine göre)
    def _get_transition_type(from_state: str, to_state: str) -> str:
        """State geçişi için uygun efekt tipini belirle."""
        # Oyuna giriş için perde efekti (campaign'den de oyuna girerken)
        if to_state == 'game' or to_state == 'pvp':
            return 'wipe'
        # Oyundan çıkış için fade
        if from_state == 'game' or from_state == 'pvp':
            return 'fade'
        # Campaign select özel geçişleri
        if from_state == 'menu' and to_state == 'campaign_select':
            return 'slide_left'
        if from_state == 'campaign_select' and to_state == 'menu':
            return 'slide_right'
        # Showcase ekranları (ana menüden açılan): ileri sola, geri sağa
        showcase_states = ['piece_workshop', 'block_styles', 'block_workshop']
        if from_state == 'menu' and to_state in showcase_states:
            return 'slide_left'
        if from_state in showcase_states and to_state == 'menu':
            return 'slide_right'
        # Menü geçişleri için sayfa kaydırma efekti
        # İleri gidiş (derinleşme) - sola kayma
        forward_states = ['extras', 'highscores', 'achievements', 'credits', 'guide', 'campaign_select']
        if to_state in forward_states:
            return 'slide_left'
        # Geri dönüş - sağa kayma
        if from_state in forward_states and to_state == 'menu':
            return 'slide_right'
        # Ayarlar alt menüleri - ileri/geri
        settings_substates = ['controls', 'graphics', 'gameplay_settings', 'block_styles', 'block_workshop', 'piece_workshop', 'mode_music']
        if from_state == 'settings' and to_state in settings_substates:
            return 'slide_left'
        if from_state in settings_substates and to_state == 'settings':
            return 'slide_right'
        # Ana menü <-> Ayarlar
        if from_state == 'menu' and to_state == 'settings':
            return 'slide_left'
        if from_state == 'settings' and to_state == 'menu':
            return 'slide_right'
        # Kullanıcı ekranları
        if to_state in ['user_selection', 'user_management']:
            return 'slide_up'
        if from_state in ['user_selection', 'user_management']:
            return 'slide_down'
        # Varsayılan: sola kayma (ileri gidiş hissi)
        return 'slide_left'
    
    # Gamepad yöneticisini başlat (tüm state'lerde paylaşılır)
    gamepad_mgr = get_gamepad_manager()

    while running:
        # FPS limiti: 0 = MAX (sınırsız). VSync açıksa pratikte monitör Hz ile sınırlanır.
        try:
            fps_limit = int(settings_manager.get('fps_limit', 0) or 0)
        except Exception:
            fps_limit = 0
        delta_ms = clock.tick(fps_limit if fps_limit > 0 else 0)

        # ── Gamepad Bağlam Güncelleme ──────────────────────────────────
        # Oyun/PvP sırasında gamepad bağlamını 'game' olarak ayarla.
        # Böylece B=rotate, A=hard_drop vb. oyun aksiyonları çalışır.
        # Menü/ayar ekranlarında bağlam 'menu' kalır (B=back, A=confirm).
        try:
            if state in ('game', 'pvp'):
                gamepad_mgr.set_context('game')
            else:
                gamepad_mgr.set_context('menu')
        except Exception:
            pass

        # ── Gamepad Güncelleme ──────────────────────────────────────────
        # Gamepad durumunu oku ve sentetik klavye olaylarını pygame
        # event kuyruğuna post et.  Böylece tüm handler'lar (menü, oyun,
        # ayarlar vb.) otomatik olarak gamepad girişini klavye olayı
        # gibi işler — ek kod değişikliği gerekmez.
        try:
            gp_events = gamepad_mgr.update(delta_ms)
            for gp_ev in gp_events:
                pygame.event.post(gp_ev)
        except Exception:
            pass
        # ────────────────────────────────────────────────────────────────

        # Pause menüsü gibi başka yerlerden ayarlar değişebiliyor.
        # Bu yüzden SettingsScreen cache'ini SettingsManager ile senkron tut.
        if settings_screen:
            settings_screen.sync_from_settings_manager()
        
        # Ekran geçiş efektini güncelle
        transition_active = update_screen_transition()
        
        # State değişikliği algılama ve geçiş efekti başlatma
        if state != _previous_state and not transition_active:
            # Ana menüye her dönüşte/girişte leaderboard'u zorla yenile
            if state == 'menu':
                try:
                    menu.notify_menu_activated()
                except Exception:
                    pass
            # Geçiş efekti başlat (state zaten değişti, sadece görsel efekt)
            transition_type = _get_transition_type(_previous_state, state)
            # Campaign select için daha uzun süre (daha belirgin efekt)
            if 'campaign_select' in (_previous_state, state):
                duration = 450
            else:
                duration = 350
            start_screen_transition(screen, None, duration_ms=duration, transition_type=transition_type)
            _previous_state = state

        handler = STATE_HANDLERS.get(state)
        if handler is None:
            # Bilinmeyen state -> güvenli dönüş
            state = 'menu'
            _previous_state = state
            continue

        # Mouse görünürlüğü:
        # - Menü/UI ekranlarında görünür
        # - Oyun sırasında gizli
        # - Ancak pause/ESC overlay, kart seçimi vb. açılınca görünür
        try:
            if state == 'game' and game is not None:
                pygame.mouse.set_visible(bool(getattr(game, 'wants_mouse_visible', lambda: False)()))
            elif state == 'pvp' and pvp_game is not None:
                pygame.mouse.set_visible(bool(getattr(pvp_game, 'wants_mouse_visible', lambda: False)()))
            else:
                pygame.mouse.set_visible(True)
        except Exception:
            # Güvenli varsayılan
            pygame.mouse.set_visible(state not in ('game', 'pvp'))

        did_draw = bool(handler(delta_ms))

        # ── Menü Müzik Playlist Global Tick ────────────────────────────
        # update_music_playlist() daha önce yalnızca 'menu' ve 'settings'
        # handler'larında çağrılıyordu; bu yüzden credits, başarımlar,
        # kılavuz, yeni kullanıcı gibi ekranlarda parça bitince müzik
        # devam etmiyordu. Oyun sırasında stop_music() playlist'i
        # inactive yaptığından bu çağrı oyun müziğini etkilemez.
        try:
            menu_sound.update_music_playlist()
        except Exception:
            pass
        # ────────────────────────────────────────────────────────────────

        # Geçiş efektini çiz (her şeyin üstüne)
        if did_draw:
            draw_screen_transition(screen)
            pygame.display.flip()

        # Sık değişen ayarları (slider vb.) toplu kaydet.
        try:
            settings_manager.flush_if_due()
        except Exception:
            pass

        # FPS limitleme frame başında uygulanıyor.
    
    pygame.quit()
    
    # Ayarları son kez kaydet
    settings_manager.save_settings()
    
    print("\n" + "=" * 60)
    print("Oyun kapandı. Skorunuz kaydedildi!")
    print("Ayarlarınız kaydedildi! ⚙️")
    print("Oynadığınız için teşekkürler! 🎮")
    print("=" * 60)


if __name__ == "__main__":
    main()

