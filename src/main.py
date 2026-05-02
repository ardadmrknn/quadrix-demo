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

# ==================== DUAL-MODULE SINGLETON FIX (retro_style + others) ===========
# Aynı sorun retro_style ve diğer singleton modüller için de geçerli:
# bare import (from retro_style import retro_style) → sys.modules['retro_style']
# ama Python paket çözümlemesi → sys.modules['src.retro_style'] olarak AYRI yüklenebilir.
# İki farklı modül = iki farklı RetroStyle singleton = set_background_transparency()
# yalnız bir kopyayı günceller, diğeri default (0.3) kalır.
for _mod_name in ('retro_style', 'background_effects', 'background', 'ui_theme'):
    try:
        _bare_mod = __import__(_mod_name)
        sys.modules.setdefault(f'src.{_mod_name}', _bare_mod)
    except Exception:
        pass
try:
    del _mod_name, _bare_mod
except NameError:
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
def _persist_active_game_run(game) -> None:
    """Aktif oyunun skor/istatistik kaydını tek noktadan tamamla."""
    if game is None:
        return

    finalize_run = getattr(game, 'finalize_run', None)
    if not callable(finalize_run):
        return

    try:
        raw_playtime = getattr(game, 'game_time', 0)
        playtime = max(0, int(raw_playtime or 0)) // 1000
    except Exception:
        playtime = None

    try:
        finalize_run(playtime)
    except TypeError:
        try:
            finalize_run()
        except Exception as exc:
            print(f"[Save] Oyun cikis kaydi tamamlanamadi: {exc}")
    except Exception as exc:
        print(f"[Save] Oyun cikis kaydi tamamlanamadi: {exc}")

try:
    from .game import Game, prewarm_common_mode_entry_backgrounds  # type: ignore
    from .block_styles import BlockStyleManager  # type: ignore
    from .tutorial import TutorialMode  # type: ignore
    from .splash_screen import SplashScreen  # type: ignore
    from .pvp_game import PvPGame  # type: ignore
    from .coop_game import CoopGame  # type: ignore
    from .online_pvp_game import OnlinePvPGame  # type: ignore
    from .online_coop_game import OnlineCoopGame  # type: ignore
    from .game_modes import SprintMode, UltraMode, ZenMode, HardcoreMode  # type: ignore
    from .game_modes_extra import Tetris2Mode, MysteryMode, WideMode  # type: ignore
    from .game_modes_advanced import SurvivalMode, CascadeMode, DailyChallengeMode  # type: ignore
    from .campaign import CampaignMode, CampaignLevelSelect  # type: ignore
    from .campaign.coop_campaign_mode import CoopCampaignMode  # type: ignore
    from .campaign.coop_level_select import CoopLevelSelect  # type: ignore
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
    from .platform_utils import request_window_focus, init_platform_display, get_display_flags, create_display, get_native_resolution, normalize_mouse_pos, get_mouse_pos, set_app_icon, resolve_frame_rate_cap  # type: ignore
    from .retro_style import retro_style  # type: ignore
    from .background_effects import (  # type: ignore
        start_screen_transition, update_screen_transition,
        draw_screen_transition, is_screen_transition_active,
        ScreenTransition
    )
    from .gamepad_manager import get_gamepad_manager, is_gamepad_connected  # type: ignore
    from .ui_scaling import get_projected_effective_scale  # type: ignore
    from .leaderboard_trailer_screen import LeaderboardTrailerScreen  # type: ignore
except Exception:
    from game import Game, prewarm_common_mode_entry_backgrounds
    from block_styles import BlockStyleManager
    from tutorial import TutorialMode
    from splash_screen import SplashScreen
    from pvp_game import PvPGame
    from coop_game import CoopGame
    from online_pvp_game import OnlinePvPGame
    from online_coop_game import OnlineCoopGame
    from game_modes import SprintMode, UltraMode, ZenMode, HardcoreMode
    from game_modes_extra import Tetris2Mode, MysteryMode, WideMode
    from game_modes_advanced import SurvivalMode, CascadeMode, DailyChallengeMode
    from campaign import CampaignMode, CampaignLevelSelect
    from campaign.coop_campaign_mode import CoopCampaignMode
    from campaign.coop_level_select import CoopLevelSelect
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
    from platform_utils import request_window_focus, init_platform_display, get_display_flags, create_display, get_native_resolution, normalize_mouse_pos, get_mouse_pos, set_app_icon, resolve_frame_rate_cap
    from retro_style import retro_style
    from background_effects import (
        start_screen_transition, update_screen_transition,
        draw_screen_transition, is_screen_transition_active,
        ScreenTransition
    )
    from gamepad_manager import get_gamepad_manager, is_gamepad_connected
    from ui_scaling import get_projected_effective_scale
    from leaderboard_trailer_screen import LeaderboardTrailerScreen
import pygame
from pathlib import Path


def _has_active_profile_session(user_manager, steam_user_set):
    if steam_user_set:
        return True

    try:
        current_user = user_manager.get_current_user()
    except Exception:
        current_user = getattr(user_manager, 'current_user', None)

    if not current_user:
        return False

    try:
        users = user_manager.get_all_users() or {}
    except Exception:
        users = getattr(user_manager, 'users', {}) or {}
    return current_user in users


def _build_user_bound_views(
    screen,
    user_manager,
    steam_mode_scores_loader,
):
    achievements_file = user_manager.get_achievements_file()
    highscores_file = user_manager.get_highscores_file()

    score_manager = ScoreManager(highscores_file)
    achievement_manager = AchievementManager(achievements_file)
    highscore_screen = HighScoreScreen(
        screen,
        score_manager,
        user_manager,
        steam_mode_scores=steam_mode_scores_loader(limit=3),
    )
    achievement_screen = AchievementScreen(screen, achievement_manager)
    return score_manager, achievement_manager, highscore_screen, achievement_screen


def resource_path(relative_path: str) -> str:
    """PyInstaller ile derlenen exe için doğru path'i al"""
    try:
        import sys
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).resolve().parents[1]
    return str(base_path / relative_path)


_CUSTOM_CURSOR_SURFACE: pygame.Surface | None = None
_CUSTOM_CURSOR_HOTSPOT = (4, 4)


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
        global _CUSTOM_CURSOR_SURFACE
        _CUSTOM_CURSOR_SURFACE = cursor_surface
        hotspot = _CUSTOM_CURSOR_HOTSPOT
        cursor = pygame.cursors.Cursor(hotspot, cursor_surface)
        pygame.mouse.set_cursor(cursor)
        print("[Cursor] Ozel fare imleci yuklendi")
        return True
    except Exception as e:
        try:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
        except Exception:
            pass
        print(f"[Cursor] Ozel cursor yuklenemedi, varsayilan kullaniliyor: {e}")
        return False


def _steam_gl_software_cursor_active() -> bool:
    """Windows Steam/OpenGL path can lose SDL's hardware cursor; draw our own."""
    if sys.platform != 'win32':
        return False
    try:
        from gl_compat import is_gl_active
        return bool(is_gl_active())
    except Exception:
        return False


def draw_software_cursor_if_needed(target_surface, *, force: bool = False) -> bool:
    if not force and not _steam_gl_software_cursor_active():
        return False
    if _CUSTOM_CURSOR_SURFACE is None or target_surface is None:
        return False
    try:
        if not pygame.mouse.get_visible():
            return False
    except Exception:
        return False
    try:
        mx, my = pygame.mouse.get_pos()
        hx, hy = _CUSTOM_CURSOR_HOTSPOT
        target_surface.blit(_CUSTOM_CURSOR_SURFACE, (int(mx) - hx, int(my) - hy))
        return True
    except Exception:
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
    'online_pvp': {
        'title_key': 'mode_online_pvp',
        'desc_key': 'mode_intro_online_pvp_desc'
    },
    'hardcore': {
        'title_key': 'mode_hardcore',
        'desc_key': 'mode_intro_hardcore_desc'
    }
}


def _maybe_recover_windows_display(screen, *, settings_manager=None):
    """Windows'ta PrintScreen/focus-loss sonrası display'i debounce ile toparla.

    Dönüş:
        Aynı surface (değişmediyse) veya yeniden oluşturulmuş yeni display surface.
    """
    if current_platform != 'Windows' or screen is None:
        return screen

    gl_active = False
    try:
        if _get_steam_overlay_gl_mode(settings_manager) != 'off':
            from gl_compat import is_gl_active
            gl_active = bool(is_gl_active())
    except Exception:
        gl_active = False

    state = getattr(
        _maybe_recover_windows_display,
        '_state',
        {
            'display_was_inactive': False,
            'pending_focus_recover_ms': -1,
            'prtsc_was_down': False,
            'pending_prtsc_recover_ms': -1,
            'last_display_recover_ms': -10_000,
        },
    )
    # Eski state ile uyumluluk: yeni alan yoksa ekle.
    state.setdefault('pending_focus_recover_ms', -1)

    now_ms = pygame.time.get_ticks()
    try:
        is_active = bool(pygame.display.get_active())
    except Exception:
        is_active = True

    should_recover = False
    recover_reason = None
    if not is_active:
        state['display_was_inactive'] = True
        state['pending_focus_recover_ms'] = -1
    else:
        if state['display_was_inactive']:
            state['display_was_inactive'] = False
            # Alt+Tab/focus dönüşünde hemen set_mode çağırma:
            # kısa gecikme sonrası yalnızca bir kez toparla.
            state['pending_focus_recover_ms'] = now_ms + 220

    if state['pending_focus_recover_ms'] > 0 and now_ms >= state['pending_focus_recover_ms']:
        state['pending_focus_recover_ms'] = -1
        should_recover = True
        recover_reason = 'focus'

    prtsc_down = False
    k_prtsc = getattr(pygame, 'K_PRINTSCREEN', None)
    if k_prtsc is not None:
        try:
            keys = pygame.key.get_pressed()
            if 0 <= int(k_prtsc) < len(keys):
                prtsc_down = bool(keys[int(k_prtsc)])
        except Exception:
            prtsc_down = False

    if prtsc_down and not state['prtsc_was_down']:
        state['pending_prtsc_recover_ms'] = now_ms + 220
    state['prtsc_was_down'] = prtsc_down

    if (
        state['pending_prtsc_recover_ms'] > 0
        and now_ms >= state['pending_prtsc_recover_ms']
        and not state['prtsc_was_down']
    ):
        state['pending_prtsc_recover_ms'] = -1
        should_recover = True
        recover_reason = 'prtsc'

    # GL overlay aktifken focus/PrintScreen kaynaklı set_mode zinciri
    # (rebuild + reapply) siyah ekran ve stale-frame sorunlarını büyütebilir.
    if should_recover and gl_active and recover_reason in ('focus', 'prtsc'):
        should_recover = False

    if should_recover and (now_ms - state['last_display_recover_ms'] >= 900):
        state['last_display_recover_ms'] = now_ms

        try:
            width = max(800, int(screen.get_width() or 0))
            height = max(600, int(screen.get_height() or 0))
        except Exception:
            width, height = 1024, 768

        fullscreen = False
        borderless = False
        try:
            if settings_manager is not None:
                fullscreen = bool(settings_manager.get('fullscreen', False))
                borderless = bool(settings_manager.get('borderless_fullscreen', True))
            else:
                fullscreen = bool(screen.get_flags() & pygame.FULLSCREEN)
                borderless = fullscreen
        except Exception:
            fullscreen = False
            borderless = False

        try:
            new_screen = create_display(
                width,
                height,
                fullscreen=fullscreen,
                resizable=True,
                borderless=(borderless if fullscreen else False),
            )
            if recover_reason == 'focus':
                request_window_focus()
            _maybe_recover_windows_display._state = state
            return new_screen
        except Exception:
            pass

    _maybe_recover_windows_display._state = state
    return screen


def _get_actual_display_surface():
    """Gorunen display surface'ini dondur; GL varsa offscreen yerine gerçek display'i kullan."""
    try:
        from gl_compat import get_display_surface, is_gl_active
        if is_gl_active():
            actual = get_display_surface()
            if actual is not None:
                return actual
    except Exception:
        pass

    try:
        return pygame.display.get_surface()
    except Exception:
        return None


def _refresh_screen_from_display(current_screen):
    """Popup/recover sonrasinda varsa en guncel display surface'i dondur."""
    actual = _get_actual_display_surface()
    if actual is not None:
        return actual
    return current_screen


def _apply_screen_to_targets(new_screen, *targets):
    """Yeni display surface'ini screen sahibi uzun omurlu nesnelere yay."""
    def _sync_target_screen(target):
        if target is None:
            return
        if hasattr(target, 'screen'):
            try:
                target.screen = new_screen
            except Exception:
                pass
        try:
            width = int(new_screen.get_width())
            height = int(new_screen.get_height())
        except Exception:
            width = height = 0
        for attr_name, attr_value in (
            ('window_width', width),
            ('window_height', height),
            ('screen_w', width),
            ('screen_h', height),
        ):
            if hasattr(target, attr_name):
                try:
                    setattr(target, attr_name, attr_value)
                except Exception:
                    pass

    for target in targets:
        _sync_target_screen(target)
        nested_avatar_editor = getattr(target, 'avatar_editor', None) if target is not None else None
        _sync_target_screen(nested_avatar_editor)


def _get_steam_overlay_gl_mode(settings_manager=None) -> str:
    """Return normalized Steam overlay GL mode: auto|off|force."""
    raw_value = os.environ.get('QUADRIX_STEAM_OVERLAY_GL')
    if raw_value is None and settings_manager is not None:
        try:
            raw_value = settings_manager.get('steam_overlay_gl', 'auto')
        except Exception:
            raw_value = 'auto'

    mode = str(raw_value or 'auto').strip().lower()
    if mode in ('0', 'false', 'off', 'disable', 'disabled', 'none'):
        return 'off'
    if mode in ('1', 'true', 'on', 'force', 'forced', 'enable', 'enabled'):
        return 'force'
    return 'auto'

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
    bg_capture = _capture_popup_backdrop(screen, dim_alpha=160)
    
    start_time = pygame.time.get_ticks()
    
    while running_popup:
        clock.tick(60)
        screen = _maybe_recover_windows_display(screen, settings_manager=settings_manager)
        bg_capture = _ensure_popup_backdrop(bg_capture, screen, dim_alpha=160)
        
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
    """Popup/panel olcegi: logical UI size ile karar ver, raw surface'e projekte et."""
    return get_projected_effective_scale(
        screen,
        min_scale=0.65,
        max_scale=1.35,
        reference_size=(1920.0, 1080.0),
        apply_preset=False,
    )


def _capture_popup_backdrop(screen, *, dim_alpha: int) -> pygame.Surface:
    """Popup arka planini aktif surface boyutunda yakalayip karartir."""
    backdrop = screen.copy()
    dim_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    dim_surface.fill((0, 0, 0, max(0, min(255, int(dim_alpha)))))
    backdrop.blit(dim_surface, (0, 0))
    return backdrop


def _ensure_popup_backdrop(
    backdrop: pygame.Surface | None,
    screen,
    *,
    dim_alpha: int,
) -> pygame.Surface:
    """Display recover/resize sonrasi popup backdrop'unu aktif surface ile senkron tut."""
    if backdrop is None or backdrop.get_size() != screen.get_size():
        return _capture_popup_backdrop(screen, dim_alpha=dim_alpha)
    return backdrop


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
    bg_capture = _capture_popup_backdrop(screen, dim_alpha=160)
    
    result = False
    
    while running_popup:
        clock.tick(60)
        screen = _maybe_recover_windows_display(screen, settings_manager=settings_manager)
        bg_capture = _ensure_popup_backdrop(bg_capture, screen, dim_alpha=160)
        
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
            lbl = retro_style.get_font(max(10, int(14 * popup_scale))).render(t('lines', 'Satır'), True, (150, 150, 150))
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
    bg_capture = _capture_popup_backdrop(screen, dim_alpha=220)
    
    while running_popup:
        clock.tick(60)
        screen = _maybe_recover_windows_display(screen)
        bg_capture = _ensure_popup_backdrop(bg_capture, screen, dim_alpha=220)
        
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
    steam_overlay_gl_mode = _get_steam_overlay_gl_mode(settings_manager)
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

    # ── Steam SDK erken başlat (Overlay hook için) ─────────────────────────
    # Steam overlay, pencere oluşturulmadan ÖNCE SteamAPI_Init() gerektirir.
    # create_display()'den önce başlatarak overlay'in D3D hook'unu
    # yakalamasını sağlıyoruz.  init() idempotent olduğundan ilerideki
    # ikinci çağrı güvenle mevcut durumu döndürür.
    try:
        import steam_integration as _steam_early
        if _steam_early.init():
            print("[Steam] Erken SDK init OK - overlay hook aktif")
    except Exception:
        pass

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

    settings_manager.set('fullscreen', True)

    try:
        screen = create_display(
            native_width,
            native_height,
            fullscreen=True,
            resizable=False,
            borderless=True,
        )
        
        # macOS: Surface validation
        if current_platform == 'Darwin':
            try:
                screen.fill((0, 0, 0))
                pygame.display.flip()
            except Exception:
                pygame.display.quit()
                pygame.display.init()
                screen = create_display(native_width, native_height, fullscreen=True, resizable=False, borderless=True)
                
    except Exception:
        screen = create_display(native_width, native_height, fullscreen=True, resizable=False, borderless=True)

    # ── Steam overlay OpenGL uyumluluk katmanı (Windows) ───────────────────
    # Steam overlay yalnızca D3D/OpenGL rendering context'e hook olabilir.
    # Pygame varsayılan olarak software renderer (GDI) kullandığından overlay
    # görünmez.  gl_compat modülü pencereyi OpenGL moduna alır ve pygame
    # surface'i her frame GL texture olarak ekrana çizer.
    try:
        if steam_overlay_gl_mode != 'off':
            from gl_compat import gl_overlay_setup
            screen = gl_overlay_setup(screen)
        else:
            print("[GL Compat] Konfigürasyonla devre dışı bırakıldı")
    except Exception as _gl_e:
        print(f"[GL Compat] Atlandı: {_gl_e}")

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
    fullscreen = True  # Oyun her zaman tam ekran çalışır
    last_fullscreen_toggle_ms = -10_000
    
    # Yöneticiler
    user_manager = UserManager()  # Kullanıcı yöneticisi

    steam_leaderboard_service = SteamLeaderboardService(
        backend_base_url=os.getenv('LEADERBOARD_BACKEND_URL', ''),
        publisher_key=os.getenv('STEAM_WEB_API_KEY', ''),
        app_id=int(os.getenv('STEAM_APP_ID', '0') or '0'),
    )
    steam_mode_scores_cache: dict[str, list[dict]] = {}
    steam_mode_scores_loading = False
    steam_mode_scores_last_attempt = -120.0
    steam_mode_scores_refresh_s = 45.0

    def _load_steam_mode_scores(limit=3, force=False):
        nonlocal steam_mode_scores_loading, steam_mode_scores_last_attempt

        # SDK erişilebilir mi kontrol et
        _sdk_available = False
        try:
            import steam_integration as _si_check
            _sdk_available = _si_check.is_available()
        except Exception:
            pass

        service_configured = steam_leaderboard_service.is_configured()

        if not service_configured and not _sdk_available:
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
                data: dict[str, list[dict]] = {}

                # Yol 1+2: Backend proxy veya Direct Web API
                if service_configured:
                    data = steam_leaderboard_service.fetch_all_mode_highscores(modes, limit=limit)

                # Yol 3: SDK fallback
                if _sdk_available:
                    try:
                        import steam_integration as _si
                        for mode in modes:
                            if not data.get(mode):
                                sdk_entries = _si.fetch_global_scores(mode, limit=limit)
                                if sdk_entries:
                                    data[mode] = sdk_entries
                    except Exception:
                        pass

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
    elif not _has_active_profile_session(user_manager, _steam_user_set):
        state = 'user_selection'
    
    theme_manager = ThemeManager(settings_manager)
    score_manager = None
    achievement_manager = None
    highscore_screen = None
    achievement_screen = None

    if _has_active_profile_session(user_manager, _steam_user_set):
        score_manager, achievement_manager, highscore_screen, achievement_screen = _build_user_bound_views(
            screen,
            user_manager,
            _load_steam_mode_scores,
        )

    # Steam'e daha önce açılmış başarımları geriye dönük senkronla
    if _steam_init_ok and achievement_manager is not None:
        try:
            achievement_manager.sync_to_steam()
        except Exception:
            pass
    
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
    
    # Menü arka plan görselini ayarlardan uygula.
    try:
        retro_style.set_background_transparency(settings_manager.get('bg_transparency', 0.3))
    except Exception:
        pass

    # Falling blocks katmanını effects_opacity ile senkronize et.
    try:
        from background_effects import get_shared_falling_blocks_layer as _get_fb_init
        _eff_init = float(settings_manager.get('effects_opacity', 1.0))
        for _layer_name, _layer_kwargs in (
            ('default', {}),
        ):
            _fb_init = _get_fb_init(_layer_name, **_layer_kwargs)
            if _fb_init is not None:
                _fb_init.set_opacity_multiplier(_eff_init)
    except Exception:
        pass

    # Menü/UI panel şeffaflığını uygula (arka plan görselinden bağımsız).
    try:
        retro_style.set_menu_transparency(settings_manager.get('menu_transparency', 1.0))
    except Exception:
        pass

    # Müzik için SoundManager
    from sound import SoundManager
    menu_sound = SoundManager()
    initial_mute_all = bool(settings_manager.get('mute_all', False))
    try:
        menu_sound.set_muted(initial_mute_all)
    except Exception:
        pass

    # Enter sonrası siyah bekleme oluşmaması için ağır ekran kurulumlarını
    # splash öncesinde hazırla.
    menu = Menu(screen, user_manager, settings_manager=settings_manager)
    try:
        prewarm_common_mode_entry_backgrounds(settings_manager=settings_manager)
    except Exception:
        pass
    # Köşe butonundaki ses durumunu başlangıçta senkronize et
    try:
        menu.set_muted(initial_mute_all)
    except Exception:
        pass
    settings_screen = TabbedSettingsScreen(screen, theme_manager, settings_manager, menu_sound)
    mode_music_screen = MusicSettingsScreen(screen, settings_manager, menu_sound)
    control_settings_screen = ControlSettingsScreen(screen, settings_manager)
    block_style_screen = BlockStyleSettingsScreen(screen, theme_manager, settings_manager)
    block_workshop_screen = BlockWorkshopScreen(screen, settings_manager, theme_manager)
    piece_workshop_screen = PieceWorkshopScreen(screen, settings_manager, theme_manager)  # Yeni parça atölyesi
    credits_screen = CreditsScreen(screen)
    extras_screen = ExtrasScreen(screen, user_manager)  # Ekstralar menüsü
    user_selection_screen = UserSelectionScreen(screen, user_manager)
    user_management_screen = UserManagementScreen(screen, user_manager)
    graphics_menu = None  # Grafikler menüsü
    gameplay_settings_menu = None  # Oynanış ayarları menüsü
    guide_screen = None  # Kılavuz ekranı
    leaderboard_trailer_screen = LeaderboardTrailerScreen(screen, settings_manager=settings_manager, user_manager=user_manager)

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
    
    # Menüler
    # First show splash screen (press Enter to continue)
    splash = SplashScreen(screen, settings_manager=settings_manager)
    # If splash returns False (user closed window), exit
    if not splash.run():
        pygame.quit()
        return

    # Splash sırasında display yeniden kurulmuş olabilir; ana referansı senkronize et.
    try:
        _display_surface = pygame.display.get_surface()
        if _display_surface is not None:
            screen = _display_surface
        elif getattr(splash, 'screen', None) is not None:
            screen = splash.screen
    except Exception:
        pass

    _apply_screen_to_targets(
        screen,
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
        campaign_level_select,
        leaderboard_trailer_screen,
    )

    # Splash -> menü geçişini yumuşat: son splash karesini kısa bir süre
    # menü üstünde eritir (crossfade), böylece ani cut hissi ve siyah boşluk azalır.
    splash_handoff_frame = getattr(splash, 'last_frame', None)
    if splash_handoff_frame is not None:
        try:
            target_size = screen.get_size()
            if splash_handoff_frame.get_size() != target_size:
                if current_platform == 'Darwin':
                    splash_handoff_frame = pygame.transform.scale(splash_handoff_frame, target_size)
                else:
                    splash_handoff_frame = pygame.transform.smoothscale(splash_handoff_frame, target_size)
        except Exception:
            try:
                splash_handoff_frame = pygame.transform.scale(splash_handoff_frame, screen.get_size())
            except Exception:
                splash_handoff_frame = None

    if splash_handoff_frame is not None:
        blend_duration_ms = 260
        blend_start_ms = pygame.time.get_ticks()
        blend_clock = pygame.time.Clock()

        while True:
            now_ms = pygame.time.get_ticks()
            blend_progress = min(1.0, float(now_ms - blend_start_ms) / max(1, blend_duration_ms))
            eased = 1.0 - (1.0 - blend_progress) * (1.0 - blend_progress)

            should_abort = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    should_abort = True
                    pygame.event.post(event)
            if should_abort:
                break

            menu.draw()

            overlay_alpha = max(0, int(255 * (1.0 - eased)))
            if overlay_alpha > 0:
                overlay = splash_handoff_frame.copy()
                overlay.set_alpha(overlay_alpha)
                screen.blit(overlay, (0, 0))

            pygame.display.flip()

            if blend_progress >= 1.0:
                break
            blend_clock.tick(60)

    # Splash screen'den sonra event kuyruğunu temizle
    pygame.event.clear()
    pygame.event.clear()

    # Kaydedilmiş müzik ayarını kontrol et - ANA SAYFA MÜZİĞİNİ çal
    print("=" * 60)
    print("🎵 ANA MENÜ MÜZİĞİ BAŞLATILIYOR")
    print("=" * 60)
    music_enabled = settings_manager.get('music_enabled', True)
    try:
        menu_sound.set_muted(initial_mute_all)
    except Exception:
        pass
    print(f"   music_enabled ayarı: {music_enabled}")
    
    if music_enabled and not initial_mute_all:
        menu_music = settings_manager.get('menu_music', 'main_1')
        print(f"   menu_music ayarı: {menu_music}")
        print(f"   Çalınacak track: {menu_music.lower()}")
        
        # Ses seviyelerini ayarla ve uygula (Varsayılan: %30 Müzik, %50 Efekt)
        saved_music_vol = settings_manager.get('music_volume', 0.3)
        saved_menu_music_vol = settings_manager.get('menu_music_volume', 0.3)
        saved_sfx_vol = settings_manager.get('sfx_volume', 0.5)
        
        # Ana menüdeyken menu_music_volume kullan
        menu_sound.unduck_music()
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
        if not music_enabled:
            print("   Müzik KAPALI (music_enabled=False)")
        elif initial_mute_all:
            print("   Müzik KAPALI (mute_all=True)")
    print("=" * 60)

    # Durum — Steam profili veya aktif kullanıcı varsa menüye, yoksa kullanıcı seçimine.
    state = 'menu' if _has_active_profile_session(user_manager, _steam_user_set) else 'user_selection'
    confirm_exit = False
    game = None
    pvp_game = None
    coop_game = None
    coop_campaign_game = None
    coop_level_select = None
    _coop_campaign_needs_refresh = False
    game_return_state = 'menu'
    block_styles_return_state = 'menu'
    _campaign_needs_refresh = False  # Campaign progress yenileme flag'i

    def _sync_user_bound_state() -> bool:
        nonlocal score_manager, achievement_manager, highscore_screen, achievement_screen
        nonlocal _campaign_needs_refresh, _coop_campaign_needs_refresh

        if not _has_active_profile_session(user_manager, _steam_user_set):
            score_manager = None
            achievement_manager = None
            highscore_screen = None
            achievement_screen = None
            return False

        score_manager, achievement_manager, highscore_screen, achievement_screen = _build_user_bound_views(
            screen,
            user_manager,
            _load_steam_mode_scores,
        )
        _campaign_needs_refresh = True
        _coop_campaign_needs_refresh = True
        return True

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
        print("  ✅ Tam Ekran Oynanış")
        print("  ✅ Sessiz Mod (M tuşu)")
        print("\n🎯 Oyun başlatılıyor...\n")

    def _ensure_menu_music_playing(force: bool = False):
        """Menü sesi açıldığında parçanın gerçekten aktif olmasını garanti et."""
        if not settings_screen.music_enabled or settings_screen.mute_all:
            return

        try:
            music_busy = bool(pygame.mixer.music.get_busy())
        except Exception:
            music_busy = False

        channel_busy = False
        current_channel = getattr(menu_sound, 'current_music_channel', None)
        if current_channel is not None:
            try:
                channel_busy = bool(current_channel.get_busy())
            except Exception:
                pass

        if not force and (music_busy or channel_busy):
            return

        try:
            menu_sound.unduck_music()
        except Exception:
            pass
        try:
            menu_sound.set_music_volume(settings_manager.get('menu_music_volume', 0.3))
        except Exception:
            pass

        menu_music = settings_manager.get('menu_music', 'main_1')
        try:
            playlist = settings_manager.get_menu_music_playlist()
            playlist_keys = [menu_sound.ensure_track_available(p) for p in playlist]
            playlist_keys = [p for p in playlist_keys if p]
            if playlist_keys:
                do_shuffle = bool(settings_manager.get('music_shuffle', False))
                menu_sound.set_music_playlist(
                    playlist_keys,
                    loop=True,
                    autoplay=True,
                    force=force,
                    shuffle=do_shuffle,
                )
            else:
                menu_sound.play_music(menu_music.lower(), loop=True, force=force)
        except Exception:
            menu_sound.play_music(menu_music.lower(), loop=True, force=force)
    
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
        if not settings_screen.mute_all:
            _ensure_menu_music_playing()
        if constants.DEBUG_MODE:
            print("🔇 Sessiz mod: AÇIK (M tuşu)" if settings_screen.mute_all else "🔊 Sessiz mod: KAPALI (M tuşu)")

    def _apply_screen(new_screen):
        """Ekran yeniden oluşturulduğunda tüm ekran referanslarını güncelle."""
        nonlocal screen
        # GL wrapper aktifse display rebuild sonrası tekrar kur
        try:
            from gl_compat import _reapply_gl, is_gl_active
            if is_gl_active():
                new_screen = _reapply_gl(new_screen)
        except Exception:
            pass
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
        try:
            setup_custom_cursor()
        except Exception:
            pass

        _apply_screen_to_targets(
            new_screen,
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
            campaign_level_select,
            guide_screen,
            leaderboard_trailer_screen,
            graphics_menu,
            gameplay_settings_menu,
            getattr(_handle_online_pvp, '_game', None),
            game,
            pvp_game,
            coop_game,
            coop_campaign_game,
            coop_level_select,
        )

    def _rebuild_display(width, height, *, fullscreen_value=None, resizable=True, borderless_value=None):
        """create_display çağır ve yeni screen'i her yere uygula."""
        nonlocal fullscreen
        fullscreen = True
        settings_manager.set('fullscreen', True)
        new_screen = create_display(
            width,
            height,
            fullscreen=True,
            resizable=False,
            borderless=True,
        )
        _apply_screen(new_screen)

    def _run_popup_and_sync_screen(popup_callable, *args, **kwargs):
        """Popup loop'u display recover yapsa bile ana screen referansini senkron tut."""
        nonlocal screen
        result = popup_callable(screen, *args, **kwargs)
        refreshed_screen = _refresh_screen_from_display(screen)
        if refreshed_screen is not screen:
            _apply_screen(refreshed_screen)
        return result
        # Mod değişimi sonrası birikmiş resize/video event'lerini temizle
        # (bunlar sonraki frame'de ikinci bir geçiş tetikleyebilir)
        try:
            pygame.event.pump()
            pygame.event.clear([pygame.VIDEORESIZE])
        except Exception:
            pass
        return new_screen

    def _toggle_fullscreen(width=500, height=700):
        """Eski toggle çağrılarını tam ekranı yeniden uygulayarak uyumlu tut."""
        nonlocal fullscreen, last_fullscreen_toggle_ms, screen, running
        now_ms = pygame.time.get_ticks()
        if now_ms - last_fullscreen_toggle_ms < 600:
            return False
        last_fullscreen_toggle_ms = now_ms

        fullscreen = True
        settings_manager.set('fullscreen', True)

        try:
            _rebuild_display(width, height, fullscreen_value=True, resizable=False, borderless_value=True)
            return True
        except Exception:
            pass

        if current_platform == 'Darwin':
            if _restart_application():
                running = False
                return True

        return False

    def _get_fullscreen_key():
        """Ayarlardan fullscreen toggle tuşunu al."""
        return None

    def _check_fullscreen_toggle(event):
        """Event'in fullscreen toggle olup olmadığını kontrol et."""
        return False

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
        nonlocal running, state, confirm_exit, confirm_daily, daily_prompt_selected, daily_prompt_challenge, game, pvp_game, coop_game, guide_screen
        nonlocal cheat_buffer, cheat_last_key_ms
        nonlocal coop_level_select, _coop_campaign_needs_refresh, leaderboard_trailer_screen

        for event in pygame.event.get():
            # Global M tuşu - Sessiz mod
            if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                toggle_global_mute()
                continue
            if event.type == pygame.QUIT:
                if sys.platform == 'darwin':
                    try:
                        import steam_integration as _si_quit
                        _si_quit.request_shutdown()
                    except Exception:
                        pass
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
                                sound_manager=menu_sound,
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
                            sound_manager=menu_sound,
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
                        if sys.platform == 'darwin':
                            try:
                                import steam_integration as _si_exit
                                _si_exit.request_shutdown()
                            except Exception:
                                pass
                        running = False
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or event.pos
                    if menu.exit_yes_rect and menu.exit_yes_rect.collidepoint(pos):
                        if sys.platform == 'darwin':
                            try:
                                import steam_integration as _si_exit2
                                _si_exit2.request_shutdown()
                            except Exception:
                                pass
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
                    sound_manager=menu_sound,
                    score_manager=score_manager,
                )
                state = 'game'
            
            elif action in ('single_player', 'Tek Oyunculu', 'Single Player'):
                # Tutorial Check
                if not user_manager.is_tutorial_completed() and not user_manager.is_tutorial_prompt_dismissed():
                    if _run_popup_and_sync_screen(_show_tutorial_prompt):
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
                            launch_lesson_id='move_intro',
                            sound_manager=menu_sound,
                            score_manager=score_manager,
                            block_style_manager=block_style_manager
                        )
                        state = 'game'
                        continue
                    else:
                        # Skip Tutorial — progress üretmeden sadece popup'ı kapat
                        user_manager.dismiss_tutorial_prompt()

                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'classic', settings_manager=settings_manager):
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
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'mystery', settings_manager=settings_manager):
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
                    sound_manager=menu_sound,
                    score_manager=score_manager,
                )
                state = 'game'
            elif action in ('pvp_2_players', 'PvP (2 Oyuncu)', 'PvP (2 Players)'):
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'pvp', settings_manager=settings_manager):
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
            elif action in ('online_pvp', 'Online PvP'):
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'online_pvp', settings_manager=settings_manager):
                    continue
                confirm_exit = False
                # Menü müziğini durdur; online PvP kendi müziğini başlatacak.
                menu_sound.stop_music()
                online_pvp_game = OnlinePvPGame(
                    screen=screen,
                    fullscreen=fullscreen,
                    user_manager=user_manager,
                    achievement_manager=achievement_manager,
                    settings_manager=settings_manager,
                    sound_manager=menu_sound,
                )
                _handle_online_pvp._game = online_pvp_game
                state = 'online_pvp'
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
            elif action in ('achievements', 'Başarılar', 'Başarımlar', 'Achievements'):
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
            elif action == 'leaderboard_trailer':
                confirm_exit = False
                if leaderboard_trailer_screen is None:
                    leaderboard_trailer_screen = LeaderboardTrailerScreen(screen, settings_manager=settings_manager, user_manager=user_manager)
                leaderboard_trailer_screen.restart_animation()
                state = 'leaderboard_trailer'
            elif action in ('credits', 'Emeği Geçenler', 'Credits'):
                confirm_exit = False
                state = 'credits'
            elif action == 'main_menu':
                confirm_exit = False
                state = 'menu'
            elif action == 'coop_mode':
                confirm_exit = False
                menu_sound.stop_music()
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                coop_game = CoopGame(
                    sound,
                    effects,
                    screen,
                    fullscreen,
                    user_manager,
                    settings_manager,
                    sound_manager=menu_sound,
                )
                state = 'coop'
            elif action == 'online_coop':
                confirm_exit = False
                menu.show_info(t('menu_dashboard_sub_store'))
            elif action == 'coop_campaign':
                confirm_exit = False
                if coop_level_select is None:
                    coop_level_select = CoopLevelSelect(
                        screen=screen,
                        settings_manager=settings_manager,
                        user_manager=user_manager,
                    )
                _coop_campaign_needs_refresh = True
                state = 'coop_campaign_select'
            elif action == 'store':
                confirm_exit = False
                menu.show_info(t('menu_dashboard_sub_store'))
            elif action == 'piece_workshop':
                confirm_exit = False
                state = 'piece_workshop'
            elif action == 'block_styles':
                confirm_exit = False
                block_styles_return_state = 'menu'
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
        if state != 'menu':
            return True
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
            elif action and action.startswith('reset_tab_defaults:'):
                reset_tab = action.split(':', 1)[1].strip().lower()
                try:
                    settings_screen.sync_from_settings_manager()
                except Exception:
                    pass

                if reset_tab in ('audio', 'display'):
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

                    if settings_screen.mute_all:
                        menu_sound.sfx_enabled = False
                    else:
                        menu_sound.sfx_enabled = settings_screen.sound_enabled

                    try:
                        menu_sound.set_muted(settings_screen.mute_all)
                    except Exception:
                        pass
                    try:
                        menu_sound.set_music_volume(settings_screen.menu_music_volume)
                    except Exception:
                        pass
                    try:
                        menu_sound.set_volume(settings_screen.sfx_volume)
                    except Exception:
                        pass

                if reset_tab == 'display':
                    if game:
                        try:
                            game.background_manager.enabled = True
                            game.single_background.enabled = True
                            game.outer_background.enabled = True
                        except Exception:
                            pass
                    if pvp_game:
                        try:
                            pvp_game.board_background.enabled = True
                            pvp_game.outer_background.enabled = True
                        except Exception:
                            pass

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
                    if coop_game:
                        for _bg_attr in ('background', 'board_background', 'outer_background'):
                            _bg_obj = getattr(coop_game, _bg_attr, None)
                            if _bg_obj is not None and hasattr(_bg_obj, 'set_transparency'):
                                try:
                                    _bg_obj.set_transparency(trans_value)
                                except Exception:
                                    pass
                        try:
                            coop_game._outer_bg_composite_cache = {'key': None, 'surface': None}
                        except Exception:
                            pass

                    try:
                        eff_value = float(settings_manager.get('effects_opacity', 1.0))
                    except Exception:
                        eff_value = 1.0
                    try:
                        from background_effects import get_shared_falling_blocks_layer as _get_fb
                        for _layer_name, _layer_kwargs in (
                            ('default', {}),
                        ):
                            _fb = _get_fb(_layer_name, **_layer_kwargs)
                            if _fb is not None:
                                _fb.set_opacity_multiplier(eff_value)
                    except Exception:
                        pass
                    for _gobj in (game, coop_game, pvp_game):
                        if _gobj is not None:
                            _gobj.effects_opacity = eff_value

                    try:
                        menu_value = float(settings_manager.get('menu_transparency', 1.0))
                    except Exception:
                        menu_value = 1.0
                    try:
                        retro_style.set_menu_transparency(menu_value)
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
                if not settings_screen.mute_all:
                    _ensure_menu_music_playing()
                print("🔇 Sessiz mod: AÇIK" if settings_screen.mute_all else "🔊 Sessiz mod: KAPALI")
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
                fullscreen = True
                settings_manager.set('fullscreen', True)
                _rebuild_display(screen.get_width(), screen.get_height(), fullscreen_value=True, resizable=False, borderless_value=True)
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
                if coop_game:
                    for _bg_attr in ('background', 'board_background', 'outer_background'):
                        _bg_obj = getattr(coop_game, _bg_attr, None)
                        if _bg_obj is not None and hasattr(_bg_obj, 'set_transparency'):
                            try:
                                _bg_obj.set_transparency(trans_value)
                            except Exception:
                                pass
                    # Composite cache'i invalidate et
                    try:
                        coop_game._outer_bg_composite_cache = {'key': None, 'surface': None}
                    except Exception:
                        pass
            elif action == 'change_effects_opacity':
                # Efekt şeffaflığı değişti — falling blocks + ambient particles
                try:
                    eff_value = float(settings_manager.get('effects_opacity', 1.0))
                except Exception:
                    eff_value = 1.0
                try:
                    from background_effects import get_shared_falling_blocks_layer as _get_fb
                    for _layer_name, _layer_kwargs in (
                        ('default', {}),
                    ):
                        _fb = _get_fb(_layer_name, **_layer_kwargs)
                        if _fb is not None:
                            _fb.set_opacity_multiplier(eff_value)
                except Exception:
                    pass
                # Aktif oyun nesnelerine de yansıt
                for _gobj in (game, coop_game, pvp_game):
                    if _gobj is not None:
                        _gobj.effects_opacity = eff_value
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
                block_styles_return_state = 'settings'
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
        nonlocal game, running, state, guide_screen

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
            elif action == 'tutorial_hub':
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
            elif action and action.startswith('tutorial_lesson:'):
                lesson_id = action.split(':', 1)[1]
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
                    launch_lesson_id=lesson_id,
                    lesson_flow_scope='chapter',
                    sound_manager=menu_sound,
                    score_manager=score_manager,
                    block_style_manager=block_style_manager
                )
                state = 'game'
        guide_screen.draw()
        return True

    def _handle_leaderboard_trailer(delta_ms):
        nonlocal running, state, leaderboard_trailer_screen

        if leaderboard_trailer_screen is None:
            leaderboard_trailer_screen = LeaderboardTrailerScreen(screen, settings_manager=settings_manager, user_manager=user_manager)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            action = leaderboard_trailer_screen.handle_input(event)
            if action == 'back':
                state = 'menu'
            elif action == 'toggle_fullscreen':
                _toggle_fullscreen(500, 700)

        leaderboard_trailer_screen.draw()
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
        nonlocal running, state, block_styles_return_state

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            action = block_style_screen.handle_input(event)
            if action == 'back':
                state = block_styles_return_state
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
        nonlocal running, state, block_styles_return_state

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            action = piece_workshop_screen.handle_input(event)
            if action == 'back':
                state = 'menu'
            elif action == 'block_styles':
                block_styles_return_state = 'piece_workshop'
                state = 'block_styles'
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
        nonlocal running, state, game, game_return_state, pvp_game, coop_level_select, _coop_campaign_needs_refresh

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
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'sprint', settings_manager=settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = SprintMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'sprint', score_manager=score_manager, sound_manager=menu_sound)
                state = 'game'
            elif action == 'Ultra Mode':
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'ultra', settings_manager=settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = UltraMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'ultra', score_manager=score_manager, sound_manager=menu_sound)
                state = 'game'
            elif action == 'Zen Mode':
                # Zen Mode için optimize edilmiş başlangıç penceresi (Intro + Ayar)
                auto_clear_rows = _run_popup_and_sync_screen(
                    _show_zen_start_popup,
                    board_height=20,
                    settings_manager=settings_manager,
                )
                if auto_clear_rows is False:
                    continue  # İptal edildi
                menu_sound.stop_music()
                game_return_state = 'extras'
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = ZenMode('Kolay', sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'zen', score_manager=score_manager, auto_clear_rows=auto_clear_rows, sound_manager=menu_sound)
                state = 'game'
            elif action == 'Hardcore Mode':
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'hardcore', settings_manager=settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = HardcoreMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'hardcore', score_manager=score_manager, sound_manager=menu_sound)
                state = 'game'
            elif action in ('pvp_2_players', 'PvP (2 Oyuncu)', 'PvP (2 Players)'):
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'pvp', settings_manager=settings_manager):
                    continue
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
            elif action in ('Quadrix 2', 'Quadrix Extra'):
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'tetris2', settings_manager=settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = Tetris2Mode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'tetris2', score_manager=score_manager, sound_manager=menu_sound)
                state = 'game'
            elif action in ('Mystery Mode', 'Kart Ustalığı', 'Yeni Nesil Quadrix', 'New Gen Quadrix', 'Card Mastery'):
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'mystery', settings_manager=settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = MysteryMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'mystery', score_manager=score_manager, sound_manager=menu_sound)
                state = 'game'
            elif action == 'Wide Mode':
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'wide', settings_manager=settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = WideMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'wide', score_manager=score_manager, sound_manager=menu_sound)
                state = 'game'
            elif action == 'Survival Mode':
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'survival', settings_manager=settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = SurvivalMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'survival', score_manager=score_manager, sound_manager=menu_sound)
                state = 'game'
            elif action == 'Cascade Mode':
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'cascade', settings_manager=settings_manager):
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
                difficulty = settings_screen.difficulty
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                game = CascadeMode(difficulty, sound, effects, achievement_manager, theme_manager, screen, fullscreen, settings_manager, user_manager, 'cascade', score_manager=score_manager, sound_manager=menu_sound)
                state = 'game'
            elif action == 'Online PvP':
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'online_pvp', settings_manager=settings_manager):
                    continue
                # Menü müziğini durdur; online PvP kendi müziğini başlatacak.
                menu_sound.stop_music()
                online_pvp_game = OnlinePvPGame(
                    screen=screen,
                    fullscreen=fullscreen,
                    user_manager=user_manager,
                    achievement_manager=achievement_manager,
                    settings_manager=settings_manager,
                    sound_manager=menu_sound,
                )
                _handle_online_pvp._game = online_pvp_game
                state = 'online_pvp'
            elif action in ('daily_challenge', t('daily_challenge')):
                allowed, reason = user_manager.can_play_daily() if user_manager else (False, 'Kullanıcı bulunamadı!')
                if not allowed:
                    state = 'menu'
                    menu.show_info(reason or 'Daily Challenge kilitli!')
                    continue
                menu_sound.stop_music()
                game_return_state = 'extras'
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
                    sound_manager=menu_sound,
                    score_manager=score_manager,
                )
                state = 'game'
            elif action == 'Classic Mode':
                if not _run_popup_and_sync_screen(_show_mode_intro_popup, 'classic', settings_manager=settings_manager):
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
            elif action == 'coop_campaign':
                if coop_level_select is None:
                    coop_level_select = CoopLevelSelect(
                        screen=screen,
                        settings_manager=settings_manager,
                        user_manager=user_manager,
                    )
                _coop_campaign_needs_refresh = True
                state = 'coop_campaign_select'

        if state != 'extras':
            return True
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
            _persist_active_game_run(game)
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
            _persist_active_game_run(game)

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
                menu_sound.unduck_music()
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
                    sound_manager=menu_sound,
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
                menu_sound.unduck_music()
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
            return False

        pvp_game.update(delta_ms)
        pvp_game.draw()
        try:
            if getattr(pvp_game, 'sound', None):
                pvp_game.sound.update_music_playlist()
        except Exception:
            pass
        return True

    def _handle_coop(delta_ms):
        nonlocal running, state, coop_game

        if not coop_game:
            state = 'menu'
            return False

        result = coop_game.handle_input()

        if result is False:
            running = False
            return False

        if result == 'menu':
            state = 'menu'
            coop_game = None
            if settings_screen.music_enabled and not getattr(settings_screen, 'mute_all', False):
                _menu_vol = settings_manager.get('menu_music_volume', 0.3)
                menu_sound.unduck_music()
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
            return False

        coop_game.update(delta_ms)
        coop_game.draw()
        try:
            if getattr(coop_game, 'sound', None):
                coop_game.sound.update_music_playlist()
        except Exception:
            pass
        return True

    def _handle_online_pvp(delta_ms):
        nonlocal running, state
        online_pvp = getattr(_handle_online_pvp, '_game', None)

        if not online_pvp:
            state = 'menu'
            return False

        try:
            result = online_pvp.handle_input()
        except Exception as e:
            print(f"[OnlinePvP] handle_input hatası: {e}")
            import traceback; traceback.print_exc()
            try:
                online_pvp._cleanup()
            except Exception:
                pass
            _handle_online_pvp._game = None
            state = 'menu'
            return False

        if result is False:
            try:
                online_pvp._cleanup()
            except Exception:
                pass
            _handle_online_pvp._game = None
            running = False
            return False

        if result == 'toggle_fullscreen':
            _toggle_fullscreen(500, 700)
            if not running:  # macOS restart tetiklendi
                return False
            online_pvp.screen = screen
            online_pvp.window_width = screen.get_width()
            online_pvp.window_height = screen.get_height()
            online_pvp.fullscreen = fullscreen
        elif result == 'menu':
            state = 'menu'
            # Online PvP temizliği — pump thread'i sürdür
            try:
                online_pvp._cleanup()
            except Exception:
                pass
            _handle_online_pvp._game = None
            if settings_screen.music_enabled and not getattr(settings_screen, 'mute_all', False):
                _menu_vol = settings_manager.get('menu_music_volume', 0.3)
                menu_sound.unduck_music()
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
            return False

        try:
            online_pvp.update(delta_ms)
            online_pvp.draw()
        except Exception as e:
            print(f"[OnlinePvP] update/draw hatası: {e}")
            import traceback; traceback.print_exc()
            try:
                online_pvp._cleanup()
            except Exception:
                pass
            _handle_online_pvp._game = None
            state = 'menu'
            return False
        try:
            if getattr(online_pvp, 'sound', None):
                online_pvp.sound.update_music_playlist()
        except Exception:
            pass
        return True

    _handle_online_pvp._game = None

    def _handle_online_coop(delta_ms):
        nonlocal running, state
        online_coop = getattr(_handle_online_coop, '_game', None)

        if not online_coop:
            state = 'menu'
            return False

        try:
            result = online_coop.handle_input()
        except Exception as e:
            print(f"[OnlineCoop] handle_input hatası: {e}")
            import traceback; traceback.print_exc()
            try:
                online_coop._cleanup()
            except Exception:
                pass
            _handle_online_coop._game = None
            state = 'menu'
            return False

        if result is False:
            try:
                online_coop._cleanup()
            except Exception:
                pass
            _handle_online_coop._game = None
            running = False
            return False

        if result == 'toggle_fullscreen':
            _toggle_fullscreen(500, 700)
            if not running:
                return False
            online_coop.screen = screen
            online_coop.window_width = screen.get_width()
            online_coop.window_height = screen.get_height()
            online_coop.fullscreen = fullscreen
        elif result == 'menu':
            state = 'menu'
            try:
                online_coop._cleanup()
            except Exception:
                pass
            _handle_online_coop._game = None
            if settings_screen.music_enabled and not getattr(settings_screen, 'mute_all', False):
                _menu_vol = settings_manager.get('menu_music_volume', 0.3)
                menu_sound.unduck_music()
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
            return False

        try:
            online_coop.update(delta_ms)
            online_coop.draw()
        except Exception as e:
            print(f"[OnlineCoop] update/draw hatası: {e}")
            import traceback; traceback.print_exc()
            try:
                online_coop._cleanup()
            except Exception:
                pass
            _handle_online_coop._game = None
            state = 'menu'
            return False
        try:
            if getattr(online_coop, 'sound', None):
                online_coop.sound.update_music_playlist()
        except Exception:
            pass
        return True

    _handle_online_coop._game = None

    def _handle_user_selection(delta_ms):
        nonlocal running, state, game

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            action = user_selection_screen.handle_input(event)
            if action in ('user_selected', 'new_user_created'):
                if not _sync_user_bound_state():
                    state = 'user_selection'
                    continue
                user_selection_screen.users_list = list(user_manager.get_all_users().keys())
                state = 'menu'
                # Yeni kullanıcı oluşturulduğunda tutorial pop-up göster
                if action == 'new_user_created':
                    user_manager.set_tutorial_completed(False)
                    if _run_popup_and_sync_screen(_show_tutorial_prompt):
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
                            launch_lesson_id='move_intro',
                            sound_manager=menu_sound,
                            score_manager=score_manager,
                            block_style_manager=block_style_manager
                        )
                        state = 'game'
                    else:
                        # Skip — sahte progress üretme, sadece popup'ı kapat
                        user_manager.dismiss_tutorial_prompt()
            elif action == 'edit_user':
                target_user = user_selection_screen.get_selected_username()
                if target_user:
                    user_management_screen.open_edit_for(target_user)
                    state = 'user_management'
            elif action == 'back_to_menu':
                user_selection_screen.users_list = list(user_manager.get_all_users().keys())
                state = 'menu' if _sync_user_bound_state() else 'user_selection'

        user_selection_screen.update()
        user_selection_screen.draw()
        return True

    def _handle_user_management(delta_ms):
        nonlocal running, state

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            action = user_management_screen.handle_input(event)
            if action == 'back':
                _sync_user_bound_state()
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
                        sound_manager=menu_sound,
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

    # --- Co-op Campaign Level Select ---
    def _handle_coop_campaign_select(delta_ms):
        nonlocal running, state, coop_campaign_game, coop_level_select, _coop_campaign_needs_refresh

        if coop_level_select is None:
            coop_level_select = CoopLevelSelect(
                screen=screen,
                settings_manager=settings_manager,
                user_manager=user_manager,
            )

        if _coop_campaign_needs_refresh:
            coop_level_select.progress = coop_level_select._load_progress()
            _coop_campaign_needs_refresh = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                return True

            action = coop_level_select.handle_input(event)

            if action == 'back':
                state = 'menu'
                return True

            if action and action.startswith('play_'):
                try:
                    level_num = int(action.split('_')[1])
                    menu_sound.stop_music()
                    sound = settings_screen.sound_enabled
                    effects = settings_screen.effects_enabled

                    coop_campaign_game = CoopCampaignMode(
                        current_level=level_num,
                        sound_enabled=sound,
                        effects_enabled=effects,
                        screen=screen,
                        fullscreen=fullscreen,
                        user_manager=user_manager,
                        settings_manager=settings_manager,
                        sound_manager=menu_sound,
                    )
                    state = 'coop_campaign'
                    return True
                except (ValueError, IndexError):
                    pass

        coop_level_select.update(delta_ms / 1000.0)
        coop_level_select.draw()
        return True

    # --- Co-op Campaign Game ---
    def _handle_coop_campaign(delta_ms):
        nonlocal running, state, coop_campaign_game, _coop_campaign_needs_refresh

        if not coop_campaign_game:
            state = 'menu'
            return False

        result = coop_campaign_game.handle_input()

        if result is False:
            running = False
            return False

        if result == 'menu':
            state = 'coop_campaign_select'
            _coop_campaign_needs_refresh = True
            coop_campaign_game = None
            # Menü müziğini geri getir
            if settings_screen.music_enabled and not getattr(settings_screen, 'mute_all', False):
                _menu_vol = settings_manager.get('menu_music_volume', 0.3)
                menu_sound.unduck_music()
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
            return False

        if result == 'next_level':
            nxt = coop_campaign_game.get_next_level_num()
            if nxt:
                sound = settings_screen.sound_enabled
                effects = settings_screen.effects_enabled
                coop_campaign_game = CoopCampaignMode(
                    current_level=nxt,
                    sound_enabled=sound,
                    effects_enabled=effects,
                    screen=screen,
                    fullscreen=fullscreen,
                    user_manager=user_manager,
                    settings_manager=settings_manager,
                    sound_manager=menu_sound,
                )
                return True
            else:
                # Son level — level select'e dön
                _coop_campaign_needs_refresh = True
                state = 'coop_campaign_select'
                coop_campaign_game = None
                return False

        coop_campaign_game.update(delta_ms)
        coop_campaign_game.draw()
        try:
            if getattr(coop_campaign_game, 'sound', None):
                coop_campaign_game.sound.update_music_playlist()
        except Exception:
            pass
        return True

    STATE_HANDLERS = {
        'menu': _handle_menu,
        'credits': _handle_credits,
        'highscores': _handle_highscores,
        'settings': _handle_settings,
        'mode_music': _handle_mode_music,
        'controls': _handle_controls,
        'guide': _handle_guide,
        'leaderboard_trailer': _handle_leaderboard_trailer,
        'graphics': _handle_graphics,
        'gameplay_settings': _handle_gameplay_settings,
        'block_styles': _handle_block_styles,
        'block_workshop': _handle_block_workshop,
        'piece_workshop': _handle_piece_workshop,
        'achievements': _handle_achievements,
        'extras': _handle_extras,
        'game': _handle_game,
        'pvp': _handle_pvp,
        'coop': _handle_coop,
        'online_pvp': _handle_online_pvp,
        'online_coop': _handle_online_coop,
        'user_selection': _handle_user_selection,
        'user_management': _handle_user_management,
        'campaign_select': _handle_campaign_select,
        'coop_campaign_select': _handle_coop_campaign_select,
        'coop_campaign': _handle_coop_campaign,
    }
    
    running = True
    confirm_daily = False
    daily_prompt_selected = 0
    daily_prompt_challenge = None
    
    # Ekran geçiş efekti için state takibi
    _previous_state = state
    # Menü state'inden başlandığında basılı tutma tekrarı aktif
    if state not in ('game', 'pvp', 'coop', 'coop_campaign', 'online_pvp', 'online_coop'):
        pygame.key.set_repeat(350, 80)

    # Geçiş tipleri (state çiftlerine göre)
    def _get_transition_type(from_state: str, to_state: str) -> str:
        """State geçişi için uygun efekt tipini belirle."""
        # Oyuna giriş için perde efekti (campaign'den de oyuna girerken)
        if to_state in ('game', 'pvp', 'coop', 'coop_campaign', 'online_pvp', 'online_coop'):
            return 'wipe'
        # Oyundan çıkış için fade
        if from_state in ('game', 'pvp', 'coop', 'coop_campaign', 'online_pvp', 'online_coop'):
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
        forward_states = ['extras', 'highscores', 'achievements', 'credits', 'guide', 'leaderboard_trailer', 'campaign_select']
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
        try:
            fps_limit = int(settings_manager.get('fps_limit', 0) or 0)
        except Exception:
            fps_limit = 0
        frame_cap = resolve_frame_rate_cap(fps_limit)
        if (
            sys.platform == 'darwin'
            and state in ('game', 'pvp', 'coop', 'coop_campaign', 'online_pvp', 'online_coop')
            and hasattr(clock, 'tick_busy_loop')
        ):
            delta_ms = clock.tick_busy_loop(frame_cap)
        else:
            delta_ms = clock.tick(frame_cap)

        # ── Gamepad Bağlam Güncelleme ──────────────────────────────────
        # Oyun/PvP sırasında gamepad bağlamını 'game' olarak ayarla.
        # Böylece B=rotate, A=hard_drop vb. oyun aksiyonları çalışır.
        # Menü/ayar ekranlarında bağlam 'menu' kalır (B=back, A=confirm).
        # Not: online_pvp kendi bağlam yönetimini yapar (lobi=menu, playing=game).
        try:
            if state == 'online_pvp':
                pass  # online_pvp kendi set_context + update çağrısını yapar
            elif state in ('game', 'pvp', 'coop'):
                active_runtime = None
                if state == 'game':
                    active_runtime = game
                elif state == 'pvp':
                    active_runtime = pvp_game
                elif state == 'coop':
                    active_runtime = coop_game

                wants_pointer_ui = False
                if active_runtime is not None:
                    wants_pointer_ui = bool(getattr(active_runtime, 'wants_mouse_visible', lambda: False)())

                gamepad_mgr.set_context('menu' if wants_pointer_ui else 'game')
            else:
                gamepad_mgr.set_context('menu')
        except Exception:
            pass

        # ── Gamepad Güncelleme ──────────────────────────────────────────
        # Gamepad durumunu oku ve sentetik klavye olaylarını pygame
        # event kuyruğuna post et.  Böylece tüm handler'lar (menü, oyun,
        # ayarlar vb.) otomatik olarak gamepad girişini klavye olayı
        # gibi işler — ek kod değişikliği gerekmez.
        # online_pvp kendi handle_input() içinde update() çağırır (çift güncelleme önlenir).
        try:
            if state != 'online_pvp':
                gp_events = gamepad_mgr.update(delta_ms)
                for gp_ev in gp_events:
                    pygame.event.post(gp_ev)
        except Exception:
            pass
        # ────────────────────────────────────────────────────────────────

        # Windows: PrintScreen / focus-loss sonrası bozulma ve pencere kaybına
        # karşı display'i otomatik iyileştir (tüm pencere akışlarında ortak guard).
        try:
            maybe_screen = _maybe_recover_windows_display(screen, settings_manager=settings_manager)
            if maybe_screen is not None and maybe_screen is not screen:
                _apply_screen(maybe_screen)
        except Exception:
            pass

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
            # Coop kendi açılış perdesini çiziyor; aynı anda global transition başlatma.
            if state != 'coop':
                transition_type = _get_transition_type(_previous_state, state)
                # Campaign select için daha uzun süre (daha belirgin efekt)
                if 'campaign_select' in (_previous_state, state):
                    duration = 450
                else:
                    duration = 350
                start_screen_transition(screen, None, duration_ms=duration, transition_type=transition_type)
            _previous_state = state
            # Menü ekranlarında basılı tutma tekrarı aktif, oyunda devre dışı
            if state in ('game', 'pvp', 'coop', 'online_pvp'):
                pygame.key.set_repeat(0)
            else:
                pygame.key.set_repeat(350, 80)

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
            elif state == 'coop' and coop_game is not None:
                pygame.mouse.set_visible(bool(getattr(coop_game, 'wants_mouse_visible', lambda: False)()))
            else:
                pygame.mouse.set_visible(True)
        except Exception:
            # Güvenli varsayılan
            pygame.mouse.set_visible(state not in ('game', 'pvp', 'coop'))

        did_draw = bool(handler(delta_ms))

        # Handler içinde (popup/modal) display yeniden oluşturulmuş olabilir.
        # Ana screen referansını ve bağlı ekranları tek noktadan senkronize et.
        try:
            surface_now = pygame.display.get_surface()
            if surface_now is not None and surface_now is not screen:
                _apply_screen(surface_now)
        except Exception:
            pass

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
            transition_overlay_active = is_screen_transition_active()
            handler_flips_display = state in ('coop', 'coop_campaign', 'online_coop')
            if transition_overlay_active or not handler_flips_display:
                draw_screen_transition(screen)
                draw_software_cursor_if_needed(screen)
                pygame.display.flip()

        # Sık değişen ayarları (slider vb.) toplu kaydet.
        try:
            settings_manager.flush_if_due()
        except Exception:
            pass

        # FPS limitleme frame başında uygulanıyor.

    # ── macOS: erken shutdown sinyali (merkezi) ────────────────────────
    # Hangi handler running=False yaparsa yapsın, worker thread'lere
    # "kapanıyoruz" sinyali burada gönderilir. Bu sayede leaderboard/avatar
    # worker'ları Steam SDK çağrılarını bırakır ve cleanup hızlanır.
    if sys.platform == 'darwin':
        try:
            import steam_integration as _si_early
            _si_early.request_shutdown()
        except Exception:
            pass

    # ── macOS: SIGALRM güvenlik ağı (kernel seviyesi) ──────────────────
    # pygame.display.quit() / pygame.quit() macOS'ta GIL'i bırakmadan
    # Cocoa/SDL C kodunda BLOKE olabiliyor. Bu durumda:
    #   - Python signal handler çalışamaz (yalnızca bytecode aralarında çalışır)
    #   - Watchdog thread os._exit() çağıramaz (GIL'e ihtiyacı var)
    # SIG_DFL + alarm: SIGALRM kernel tarafından işlenir, GIL bağımsız.
    # C kodu takılsa bile kernel process'i anında sonlandırır.
    if sys.platform == 'darwin':
        try:
            import signal as _sig
            _sig.signal(_sig.SIGALRM, _sig.SIG_DFL)
            _sig.alarm(3)
        except Exception:
            pass

    # ── macOS: pump thread'i durdur ────────────────────────────────────
    # Pump thread SteamAPI_RunCallbacks() çağırıyorken bridge/SDL temizliği
    # yapılırsa deadlock oluşur. Önce pump'u durdur.
    if sys.platform == 'darwin':
        try:
            import steam_integration as _si_pre
            _si_pre._pump_running = False
            _si_pre._shutdown_requested = True
            _si_pre._pump_paused = True
            _si_pre._pump_paused_event.set()
            # Mevcut RunCallbacks() çağrısının bitmesini bekle
            if _si_pre._pump_lock.acquire(timeout=0.5):
                _si_pre._pump_lock.release()
            # Pump thread'inin döngüden çıkmasını da bekle
            _pt = _si_pre._pump_thread
            if _pt is not None and _pt.is_alive():
                _pt.join(timeout=0.15)
        except Exception:
            pass

    # ── macOS: minimal cleanup — pygame çağrısı YOK ───────────────────
    # pygame.display.quit() ve pygame.quit() macOS'ta Cocoa/SDL deadlock
    # oluşturup process'i DONDURUYOR. Bu çağrılar macOS'ta atlanır.
    # os._exit(0) tüm kaynakları (SDL penceresi, thread'ler, bellek) temizler.
    # Steam de process çıkışını graceful handle eder (SteamAPI_Shutdown opsiyonel).
    if sys.platform == 'darwin':
        # C++ bridge temizliği (lobi çıkışı — hızlı, bloke etmez)
        try:
            from steam_networking import shutdown_all_instances as _shutdown_net
            _shutdown_net()
        except Exception:
            pass
        # Ayarları kaydet (dosya I/O — bloke etmez)
        try:
            settings_manager.save_settings()
        except Exception:
            pass

        print("\n" + "=" * 60)
        print("Oyun kapandı. Skorunuz kaydedildi!")
        print("Ayarlarınız kaydedildi! ⚙️")
        print("Oynadığınız için teşekkürler! 🎮")
        print("=" * 60)

        # SIGALRM iptal — normal çıkışa ulaştık
        try:
            _sig.alarm(0)
        except Exception:
            pass
        os._exit(0)

    # ── Windows/Linux: tam cleanup ─────────────────────────────────────
    try:
        from steam_networking import shutdown_all_instances as _shutdown_net
        _shutdown_net()
    except Exception:
        pass

    try:
        import steam_integration as _steam_shutdown
        _steam_shutdown.shutdown()
    except Exception:
        pass

    pygame.quit()

    settings_manager.save_settings()

    print("\n" + "=" * 60)
    print("Oyun kapandı. Skorunuz kaydedildi!")
    print("Ayarlarınız kaydedildi! ⚙️")
    print("Oynadığınız için teşekkürler! 🎮")
    print("=" * 60)


if __name__ == "__main__":
    main()
