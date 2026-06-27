"""Gamepad / Kontrolcü Desteği - Xbox, PlayStation, Nintendo Switch Pro Controller

Bu modül, bağlanan gamepad'leri otomatik algılar ve joystick/buton
olaylarını sentetik pygame klavye olaylarına çevirerek mevcut input
sistemine şeffaf entegrasyon sağlar.

Desteklenen kontrolcüler:
  - Xbox Controller (Xbox One, Series X|S, 360)
  - PlayStation DualShock 4 / DualSense (PS4 / PS5)
  - Nintendo Switch Pro Controller / Joy-Con
  - Genel SDL2 uyumlu gamepad'ler
"""

import copy
import math
import sys

import pygame
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from platform_utils import IS_WINDOWS, get_mouse_pos as _gmp

try:
    from pygame._sdl2 import controller as _sdl2_controller
except Exception:
    _sdl2_controller = None

# src.main kismi import basarisiz olup absolute fallback'e dustugunde ayni dosya
# hem `src.gamepad_manager` hem `gamepad_manager` olarak yuklenebiliyordu.
# Bu da iki ayri singleton olusturup ayarlar ekraninin guncelledigi binding'lerin
# oyun tarafina yansimamasi sonucunu doguruyordu.
_current_module = sys.modules.get(__name__)
if _current_module is not None:
    if __name__ == 'src.gamepad_manager':
        sys.modules['gamepad_manager'] = _current_module
    elif __name__ == 'gamepad_manager':
        sys.modules['src.gamepad_manager'] = _current_module


CONTROLLER_BUTTON_A = getattr(pygame, 'CONTROLLER_BUTTON_A', 0)
CONTROLLER_BUTTON_B = getattr(pygame, 'CONTROLLER_BUTTON_B', 1)
CONTROLLER_BUTTON_X = getattr(pygame, 'CONTROLLER_BUTTON_X', 2)
CONTROLLER_BUTTON_Y = getattr(pygame, 'CONTROLLER_BUTTON_Y', 3)
CONTROLLER_BUTTON_BACK = getattr(pygame, 'CONTROLLER_BUTTON_BACK', 4)
CONTROLLER_BUTTON_GUIDE = getattr(pygame, 'CONTROLLER_BUTTON_GUIDE', 5)
CONTROLLER_BUTTON_START = getattr(pygame, 'CONTROLLER_BUTTON_START', 6)
CONTROLLER_BUTTON_LEFTSTICK = getattr(pygame, 'CONTROLLER_BUTTON_LEFTSTICK', 7)
CONTROLLER_BUTTON_RIGHTSTICK = getattr(pygame, 'CONTROLLER_BUTTON_RIGHTSTICK', 8)
CONTROLLER_BUTTON_LEFTSHOULDER = getattr(pygame, 'CONTROLLER_BUTTON_LEFTSHOULDER', 9)
CONTROLLER_BUTTON_RIGHTSHOULDER = getattr(pygame, 'CONTROLLER_BUTTON_RIGHTSHOULDER', 10)
CONTROLLER_BUTTON_DPAD_UP = getattr(pygame, 'CONTROLLER_BUTTON_DPAD_UP', 11)
CONTROLLER_BUTTON_DPAD_DOWN = getattr(pygame, 'CONTROLLER_BUTTON_DPAD_DOWN', 12)
CONTROLLER_BUTTON_DPAD_LEFT = getattr(pygame, 'CONTROLLER_BUTTON_DPAD_LEFT', 13)
CONTROLLER_BUTTON_DPAD_RIGHT = getattr(pygame, 'CONTROLLER_BUTTON_DPAD_RIGHT', 14)

CONTROLLER_AXIS_LEFTX = getattr(pygame, 'CONTROLLER_AXIS_LEFTX', 0)
CONTROLLER_AXIS_LEFTY = getattr(pygame, 'CONTROLLER_AXIS_LEFTY', 1)
CONTROLLER_AXIS_RIGHTX = getattr(pygame, 'CONTROLLER_AXIS_RIGHTX', 2)
CONTROLLER_AXIS_RIGHTY = getattr(pygame, 'CONTROLLER_AXIS_RIGHTY', 3)
CONTROLLER_AXIS_TRIGGERLEFT = getattr(pygame, 'CONTROLLER_AXIS_TRIGGERLEFT', 4)
CONTROLLER_AXIS_TRIGGERRIGHT = getattr(pygame, 'CONTROLLER_AXIS_TRIGGERRIGHT', 5)

CANONICAL_CONTROLLER_BUTTONS = (
    CONTROLLER_BUTTON_A,
    CONTROLLER_BUTTON_B,
    CONTROLLER_BUTTON_X,
    CONTROLLER_BUTTON_Y,
    CONTROLLER_BUTTON_BACK,
    CONTROLLER_BUTTON_GUIDE,
    CONTROLLER_BUTTON_START,
    CONTROLLER_BUTTON_LEFTSTICK,
    CONTROLLER_BUTTON_RIGHTSTICK,
    CONTROLLER_BUTTON_LEFTSHOULDER,
    CONTROLLER_BUTTON_RIGHTSHOULDER,
    CONTROLLER_BUTTON_DPAD_UP,
    CONTROLLER_BUTTON_DPAD_DOWN,
    CONTROLLER_BUTTON_DPAD_LEFT,
    CONTROLLER_BUTTON_DPAD_RIGHT,
)

WINDOWS_XINPUT_RAW_BUTTON_TO_CANONICAL = {
    0: CONTROLLER_BUTTON_A,
    1: CONTROLLER_BUTTON_B,
    2: CONTROLLER_BUTTON_X,
    3: CONTROLLER_BUTTON_Y,
    4: CONTROLLER_BUTTON_LEFTSHOULDER,
    5: CONTROLLER_BUTTON_RIGHTSHOULDER,
    6: CONTROLLER_BUTTON_BACK,
    7: CONTROLLER_BUTTON_START,
    8: CONTROLLER_BUTTON_LEFTSTICK,
    9: CONTROLLER_BUTTON_RIGHTSTICK,
    10: CONTROLLER_BUTTON_GUIDE,
}

# Xbox / PlayStation / Nintendo buton indeksleri (SDL GameController layout)
# SDL GameController standardında butonlar:
#   0 = A (Xbox) / Cross (PS) / B (Nintendo)
#   1 = B (Xbox) / Circle (PS) / A (Nintendo)
#   2 = X (Xbox) / Square (PS) / Y (Nintendo)
#   3 = Y (Xbox) / Triangle (PS) / X (Nintendo)
#   4 = Back/Select/Share
#   5 = Guide/Home/PS
#   6 = Start/Options/+
#   7 = Left Stick Click (L3)
#   8 = Right Stick Click (R3)
#   9 = Left Bumper (LB/L1)
#  10 = Right Bumper (RB/R1)
#  11 = D-pad Up
#  12 = D-pad Down
#  13 = D-pad Left
#  14 = D-pad Right

# Axis indeksleri (SDL standard):
#   0 = Left Stick X  (-1 sol, +1 sağ)
#   1 = Left Stick Y  (-1 yukarı, +1 aşağı)
#   2 = Right Stick X
#   3 = Right Stick Y
#   4 = Left Trigger  (0 to 1)
#   5 = Right Trigger  (0 to 1)


class GamepadType:
    """Kontrolcü tipi sabitleri"""
    UNKNOWN = 'unknown'
    XBOX = 'xbox'
    PLAYSTATION = 'playstation'
    NINTENDO = 'nintendo'


# ─── Varsayılan buton eşlemeleri ────────────────────────────────────────────
# Her aksiyon için gamepad butonu.  Varsayılanlar SDL GameController layout.

DEFAULT_GAMEPAD_BINDINGS = {
    # Oyun içi aksiyonlar
    #
    # YENI OYUN-ICI LAYOUT (Kart Ustaligi cift-tetik fix'i):
    #   Eski layout LB/RB/LT/RT'yi hem temel aksiyon (hold/discard/lt/rt) hem de
    #   slot tetigi olarak paylasiyordu. Kart Ustaligi'nda tek butona basinca hem
    #   temel aksiyon hem slot tetikleniyordu (cift-tetik). Yeni layout slotlari
    #   A/X/B/Y + LT/RT'ye, temel aksiyonlari ise LB(hold)/RB(hard_drop)'a tasiyarak
    #   bu cakismayi tamamen ortadan kaldirir. Donme yalnizca D-pad ^ ile yapilir.
    'move_left':    {'dpad': 'left',   'axis': ('left_x', -1)},
    'move_right':   {'dpad': 'right',  'axis': ('left_x', +1)},
    'soft_drop':    {'dpad': 'down',   'axis': ('left_y', +1)},
    'hard_drop':    {'button': 10},  # RB / R1 (yeni; eski Y=3'ten tasindi)
    'rotate':       {'button': 11}, # varsayilan D-pad Up
    'rotate_alt':   {'button': None}, # bos (eski B=1 kaldirildi)
    'hold':         {'button': 9},   # LB / L1 (degismedi)
    'hold2':        {'button': 8},   # R3 / RS Click (Ekstra Cep / perk_second_pocket)
    'pause':        {'button': 6, 'button_secondary': 5},   # Start / Options / + or Guide (Home)
    'lt':           {'button': None}, # bos (eski LT trigger kaldirildi)
    'rt':           {'button': None}, # bos (eski RT trigger kaldirildi)
    # POLL-ONLY game-over / level-failed aksiyonlari.
    # restart = Y(3), level_select = X(2). Bu iki aksiyon game_actions_list /
    # menu_actions_list / sentetik emisyon listelerine GIRMEZ; yalnizca
    # game-over/level-failed handler'lari icinde was_action_just_pressed ile
    # okunur. Boylece oyun ortasinda Y/X'in slot poll'u ile cakismaz.
    'restart':      {'button': 3},  # Y / Triangle — game-over'da yeniden dene (poll-only)
    'level_select': {'button': 2},  # X / Square — campaign'de level sec (poll-only)
    'discard_held': {'button': None}, # bos (eski RB=10 kaldirildi; kart slota konarak kullanilir)
    # Kart modu aksiyonlari (varsayilan: atanmis degil)
    'card_rewind': {'button': None},
    'card_sniper': {'button': None},
    'card_time_capsule_save': {'button': None},
    'card_time_capsule_restore': {'button': None},
    'card_freeze': {'button': None}, # bos (eski B=1 kaldirildi; zaten etkisizdi)
    'card_phase_shift': {'button': None},
    'card_ghost': {'button': None},
    'card_hammer': {'button': None},
    'card_bomb': {'button': None},

    # NOT: Enerji yetenekleri (Ground Sweep / Time Warp) tamamen kaldirildi.
    # Bu yetenekler artik oyunda yok; gamepad aksiyonu (card_ground_sweep /
    # card_time_warp) da yoktur.

    # Kart Ustaligi sol panel yuvalari (slot_1..slot_6).
    # Bu aksiyonlar SADECE poll edilir (was_action_just_pressed / is_action_pressed);
    # sentetik klavye event'i URETMEZLER (game_actions_list / menu_actions_list'te
    # yer almazlar). Varsayilan layout settings_manager 'gamepad' blogu ile birebir
    # ayni olmalidir; aksi halde settings dosyasi yokken (ilk acilis) yuvalar olu kalir.
    'slot_1': {'button': 0},                 # A (Xbox) / Cross (PS)
    'slot_2': {'button': 2},                 # X (Xbox) / Square (PS)
    'slot_3': {'button': 1},                 # B (Xbox) / Circle (PS)
    'slot_4': {'button': 3},                 # Y (Xbox) / Triangle (PS)
    'slot_5': {'trigger': 'left'},           # LT / L2 (trigger pseudo-index 100)
    'slot_6': {'trigger': 'right'},          # RT / R2 (trigger pseudo-index 101)

    # Menü navigasyonu
    'menu_up':      {'dpad': 'up',    'axis': ('left_y', -1)},
    'menu_down':    {'dpad': 'down',  'axis': ('left_y', +1)},
    'menu_left':    {'dpad': 'left',  'axis': ('left_x', -1)},
    'menu_right':   {'dpad': 'right', 'axis': ('left_x', +1)},
    'menu_confirm': {'button': 0},   # A / Cross / B(Nintendo)
    'menu_back':    {'button': 1},   # B / Circle / A(Nintendo)
    'menu_tab_next': {'button': 10}, # RB / R1
    'menu_tab_prev': {'button': 9},  # LB / L1
    # Outgame editor aksiyonları (workshop, user screens, popup'lar)
    'editor_secondary': {'button': 2},  # X (Xbox) / Square (PS) — silme, alternatif aksiyon
    'editor_delete': {'button': 3},     # Y (Xbox) / Triangle (PS) — delete/clear
}

# D-pad → Klavye eşlemesi (menüler ve oyun için)
DPAD_TO_KEY = {
    'up': pygame.K_UP,
    'down': pygame.K_DOWN,
    'left': pygame.K_LEFT,
    'right': pygame.K_RIGHT,
}

# Oyun aksiyonu → Klavye tuşu eşlemesi
ACTION_TO_KEY = {
    # Hareket aksiyonlari: varsayilan olarak D-pad/sol stick uretir (asagidaki
    # DEFAULT_GAMEPAD_BINDINGS 'dpad'/'axis' alanlari). Kullanici ek olarak bir
    # butona da atayabilir → o buton basildiginda ok-tusu sentetik event uretir.
    'move_left': pygame.K_LEFT,
    'move_right': pygame.K_RIGHT,
    'soft_drop': pygame.K_DOWN,
    'hard_drop': pygame.K_SPACE,
    'rotate': pygame.K_UP,
    'rotate_alt': pygame.K_UP,
    'hold': pygame.K_c,
    'hold2': pygame.K_v,
    'pause': pygame.K_p,
    'lt': pygame.K_q,        # LT → varsayılan olarak Q (kullanıcı değiştirebilir)
    'rt': pygame.K_e,        # RT → varsayılan olarak E
    'restart': pygame.K_r,
    'discard_held': pygame.K_b,
    'card_rewind': pygame.K_u,
    'card_sniper': pygame.K_n,
    'card_time_capsule_save': pygame.K_t,
    'card_time_capsule_restore': pygame.K_r,
    'card_freeze': pygame.K_f,
    'card_phase_shift': pygame.K_LSHIFT,
    'card_ghost': pygame.K_g,
    'card_hammer': pygame.K_h,
    'card_bomb': pygame.K_m,
    'menu_confirm': pygame.K_RETURN,
    'menu_back': pygame.K_ESCAPE,
    'menu_tab_next': pygame.K_RIGHTBRACKET,  # RB → sonraki sekme
    'menu_tab_prev': pygame.K_LEFTBRACKET,  # LB → önceki sekme
    'editor_secondary': pygame.K_x,   # X butonu → silme/alternatif
    'editor_delete': pygame.K_DELETE,  # Y butonu → delete/clear
}


@dataclass
class StickState:
    """Analog stick'in mevcut durumunu takip eder"""
    x: float = 0.0
    y: float = 0.0
    # Dijital yön (dead zone sonrası): -1, 0, +1
    digital_x: int = 0
    digital_y: int = 0
    # Önceki dijital yön (kenar algılama için)
    prev_digital_x: int = 0
    prev_digital_y: int = 0


@dataclass
class GamepadState:
    """Tek bir gamepad'in tam durumu"""
    joystick: pygame.joystick.JoystickType = None
    controller: Optional[object] = None
    gamepad_type: str = GamepadType.UNKNOWN
    name: str = ''
    guid: str = ''
    instance_id: Optional[int] = None
    # Buton basılı durumları (buton_index → bool)
    buttons: Dict[int, bool] = field(default_factory=dict)
    prev_buttons: Dict[int, bool] = field(default_factory=dict)
    # Analog stickler
    left_stick: StickState = field(default_factory=StickState)
    right_stick: StickState = field(default_factory=StickState)
    # Triggerlar (0.0 – 1.0)
    left_trigger: float = 0.0
    right_trigger: float = 0.0
    prev_left_trigger_pressed: bool = False
    prev_right_trigger_pressed: bool = False
    # D-pad (hat)
    dpad: Tuple[int, int] = (0, 0)  # (x, y) : -1/0/+1
    prev_dpad: Tuple[int, int] = (0, 0)
    dpad_repeat_x: float = 0.0
    dpad_repeat_y: float = 0.0
    dpad_initial_delay_x: bool = False
    dpad_initial_delay_y: bool = False
    # Stick tekrar (DAS benzeri) sayaçları
    stick_repeat_x: float = 0.0
    stick_repeat_y: float = 0.0
    stick_initial_delay_x: bool = False
    stick_initial_delay_y: bool = False
    # Sağ stick fare emülasyonu için ham eksenler ve drift filtresi durumu
    raw_right_x: float = 0.0
    raw_right_y: float = 0.0
    mouse_neutral_x: float = 0.0
    mouse_neutral_y: float = 0.0
    mouse_neutral_ready: bool = False
    mouse_control_active: bool = False
    mouse_accum_x: float = 0.0
    mouse_accum_y: float = 0.0


class GamepadManager:
    """Tüm bağlı gamepad'leri yönetir ve olayları klavye olaylarına çevirir.

    Kullanım:
        gpm = GamepadManager()
        # Her frame:
        synthetic_events = gpm.update(delta_ms)
        for event in synthetic_events:
            # Bunlar normal pygame.event gibi işlenebilir
            handle_input(event)
    """

    # Analog stick dead-zone eşiği (0.0 – 1.0)
    DEADZONE = 0.35
    # Stick'ten dijital yön tetikleme eşiği
    DIGITAL_THRESHOLD = 0.6
    # DAS benzeri tekrar: ilk bekleme ve tekrar aralığı (ms)
    STICK_INITIAL_DELAY = 300   # İlk hareket sonrası bekleme
    STICK_REPEAT_INTERVAL = 120  # Tekrar hızı
    # Trigger basılma eşiği (0.0 – 1.0)
    TRIGGER_THRESHOLD = 0.5
    # Sağ stick → fare imleci hızı ve hassasiyeti
    MOUSE_SPEED = 20.0
    MOUSE_SENSITIVITY = 1.0
    MOUSE_DEADZONE = 0.12       # Fare için ayrı (düşük) deadzone
    MOUSE_ACCEL_EXPONENT = 2.0  # Kuadratik ivme (hassas + hızlı)
    MOUSE_ACTIVATE_THRESHOLD = 0.18
    MOUSE_RELEASE_THRESHOLD = 0.08
    MOUSE_NEUTRAL_TRACK_THRESHOLD = 0.12
    MOUSE_NEUTRAL_FOLLOW_RATE = 0.03

    # Bağlam: 'game' = oyun içi, 'menu' = menü/UI
    # B butonu oyun içinde rotate, menüde back olarak çalışır
    CONTEXT_GAME = 'game'
    CONTEXT_MENU = 'menu'

    def __init__(self):
        """Gamepad sistemini başlat"""
        # pygame.joystick modülünü başlat
        if not pygame.joystick.get_init():
            pygame.joystick.init()
        try:
            if _sdl2_controller is not None and not _sdl2_controller.get_init():
                _sdl2_controller.init()
        except Exception:
            pass

        self.gamepads: Dict[int, GamepadState] = {}
        self.enabled = True

        # Vibration/rumble desteği
        self.rumble_enabled = True
        self.rumble_level = 'high'
        self.rumble_multiplier = 1.0

        # Aktif bağlam (oyun içi veya menü)
        self._context = self.CONTEXT_MENU

        # Menü pointer modu: sağ stick (fare) son kullanıldıysa True,
        # d-pad / sol stick son kullanıldıysa False.
        # True iken A butonu K_RETURN yerine MOUSEBUTTONDOWN üretir.
        self._menu_pointer_active = False

        # Focus-nav olan ekranlar bu flag'i True yaparak pointer mode'un
        # otomatik aktifleşmesini engeller. Sağ stick hareketi yine fare
        # imlecini taşır ama A butonu K_RETURN üretmeye devam eder.
        self._suppress_pointer_mode = False

        # Instance-level binding kopyası (global DEFAULT_GAMEPAD_BINDINGS mutasyona uğramaz)
        self._bindings = copy.deepcopy(DEFAULT_GAMEPAD_BINDINGS)

        # Menü navigasyonunda çift tetiklenmeyi önlemek için debouncing veri yapısı
        self._last_menu_key_times: Dict[int, int] = {}

        # Ayarlardan oku (varsa)
        self._load_settings()

        # Son aktif girdi zamanı
        self._last_gamepad_input_time: int = 0
        self._internal_time: float = 0.0

        # İlk tarama
        self._scan_gamepads()

    def get_last_input_time(self) -> int:
        """Son aktif gamepad girdisi zamanını milisaniye cinsinden döndürür."""
        return getattr(self, '_last_gamepad_input_time', 0)

    def _load_settings(self):
        """Settings'den gamepad ayarlarını yükle."""
        try:
            from settings_manager import SettingsManager
            sm = SettingsManager()
            controls = sm.get_controls()
            gp_cfg = controls.get('gamepad', {})
            self.enabled = gp_cfg.get('enabled', True)
            normalize_rumble = getattr(SettingsManager, 'normalize_gamepad_rumble_value', None)
            rumble_multiplier_for_value = getattr(SettingsManager, 'gamepad_rumble_multiplier_for_value', None)
            rumble_enabled_for_value = getattr(SettingsManager, 'gamepad_rumble_enabled_for_value', None)
            rumble_value = gp_cfg.get('rumble', 'high')
            if callable(normalize_rumble):
                self.rumble_level = str(normalize_rumble(rumble_value))
            else:
                if isinstance(rumble_value, bool):
                    self.rumble_level = 'high' if rumble_value else 'off'
                elif isinstance(rumble_value, (int, float)) and not isinstance(rumble_value, bool):
                    slider_value = max(0, min(3, int(round(rumble_value))))
                    self.rumble_level = {0: 'off', 1: 'low', 2: 'medium', 3: 'high'}.get(slider_value, 'high')
                else:
                    rumble_text = str(rumble_value or '').strip().lower()
                    rumble_aliases = {
                        'false': 'off',
                        '0': 'off',
                        'off': 'off',
                        'yok': 'off',
                        'none': 'off',
                        'kapali': 'off',
                        'kapalı': 'off',
                        '1': 'low',
                        'low': 'low',
                        'az': 'low',
                        '2': 'medium',
                        'medium': 'medium',
                        'orta': 'medium',
                        'true': 'high',
                        'on': 'high',
                        'acik': 'high',
                        'açık': 'high',
                        '3': 'high',
                        'high': 'high',
                        'cok': 'high',
                        'çok': 'high',
                    }
                    self.rumble_level = rumble_aliases.get(rumble_text, 'high')
            if callable(rumble_multiplier_for_value):
                self.rumble_multiplier = float(rumble_multiplier_for_value(self.rumble_level))
            else:
                self.rumble_multiplier = 0.0 if self.rumble_level == 'off' else 1.0
            if callable(rumble_enabled_for_value):
                self.rumble_enabled = bool(rumble_enabled_for_value(self.rumble_level))
            else:
                self.rumble_enabled = self.rumble_level != 'off'
            if not self.rumble_enabled or self.rumble_multiplier <= 0.0:
                self.stop_rumble()
            dz = gp_cfg.get('deadzone', 0.35)
            if isinstance(dz, (int, float)):
                self.DEADZONE = max(0.1, min(0.9, float(dz)))
            ms = gp_cfg.get('mouse_sensitivity', 1.0)
            if isinstance(ms, (int, float)):
                self.MOUSE_SENSITIVITY = max(0.1, min(3.0, float(ms)))
            # Her reload'da temiz bir kopya ile başla (önceki mutasyonlar sıfırlanır)
            self._bindings = copy.deepcopy(DEFAULT_GAMEPAD_BINDINGS)

            # Eski çakışan ayarları temizle.
            # NOT: 'restart' artik kullaniliyor (game-over Y butonu) — deprecated
            # listesinden cikarildi. Su an temizlenecek deprecated aksiyon yok.
            _deprecated = set()
            for dep_action in _deprecated:
                if dep_action in self._bindings:
                    self._bindings[dep_action] = {'button': None, 'button_secondary': None}

            # Buton eşlemelerini güncelle.
            # NOT: Hareket aksiyonlari (move_left/right, soft_drop) varsayilan
            # olarak D-pad + sol stick'e baglidir. Asagidaki dongu yalnizca
            # 'button'/'trigger' anahtarlarini pop'lar (dpad/axis KORUNUR), bu
            # yuzden kullanici ek bir buton atarsa D-pad varsayilani aynen kalir,
            # buton da paralel calisir. Config'de deger -1 ise hicbir buton
            # eklenmez (saf D-pad varsayilani).
            button_actions = [
                'move_left', 'move_right', 'soft_drop',
                'hard_drop', 'rotate', 'rotate_alt', 'hold', 'hold2', 'pause',
                'menu_back', 'menu_confirm', 'menu_tab_next', 'menu_tab_prev',
                'discard_held', 'lt', 'rt',
                'restart', 'level_select',
                'slot_1', 'slot_2', 'slot_3', 'slot_4', 'slot_5', 'slot_6',
                'card_rewind', 'card_sniper', 'card_time_capsule_save',
                'card_time_capsule_restore', 'card_freeze', 'card_phase_shift',
                'card_ghost', 'card_hammer', 'card_bomb',
                'editor_secondary', 'editor_delete',
            ]
            for action in button_actions:
                raw = gp_cfg.get(action)
                if action not in self._bindings:
                    continue
                # Config'de bu aksiyon yok → default'a dokunma
                if raw is None:
                    continue

                binding = self._bindings[action]
                binding.pop('button', None)
                binding.pop('button_secondary', None)
                binding.pop('trigger', None)
                binding.pop('trigger_secondary', None)

                primary = None
                secondary = None
                if isinstance(raw, dict):
                    pval = raw.get('primary')
                    sval = raw.get('secondary')
                    if isinstance(pval, int):
                        primary = pval
                    if isinstance(sval, int):
                        secondary = sval
                elif isinstance(raw, int):
                    primary = raw

                def _assign(slot_value: Optional[int], secondary_slot: bool = False) -> None:
                    if slot_value is None or slot_value < 0:
                        return
                    if slot_value in (100, 101):
                        key = 'trigger_secondary' if secondary_slot else 'trigger'
                        binding[key] = 'left' if slot_value == 100 else 'right'
                    else:
                        key = 'button_secondary' if secondary_slot else 'button'
                        binding[key] = int(slot_value)

                _assign(primary, secondary_slot=False)
                _assign(secondary, secondary_slot=True)
        except Exception:
            pass  # İlk çalıştırmada settings dosyası olmayabilir

    def _iter_button_indices(self, binding: dict) -> List[int]:
        indices: List[int] = []
        for key in ('button', 'button_secondary'):
            btn = binding.get(key)
            if isinstance(btn, int) and btn >= 0 and btn not in indices:
                indices.append(btn)
        return indices

    def _iter_trigger_dirs(self, binding: dict) -> List[str]:
        dirs: List[str] = []
        for key in ('trigger', 'trigger_secondary'):
            trig = binding.get(key)
            if trig in ('left', 'right') and trig not in dirs:
                dirs.append(trig)
        return dirs

    def _scan_gamepads(self) -> None:
        """Bağlı gamepad'leri de-duplication mantığıyla tara ve kaydet"""
        count = pygame.joystick.get_count()
        temp_gamepads = []
        for i in range(count):
            try:
                js = pygame.joystick.Joystick(i)
                js.init()
                name = js.get_name().lower()
                gp_type = self._detect_type(js)
                temp_gamepads.append((i, js, name, gp_type))
            except Exception:
                pass

        has_xbox = any(t[3] == GamepadType.XBOX for t in temp_gamepads)

        for device_index, js, name, gp_type in temp_gamepads:
            # De-duplication: Sanal Xbox kontrolcüsü varken fiziksel PlayStation DirectInput bağlantısını yoksay
            if has_xbox and gp_type == GamepadType.PLAYSTATION and 'wireless' in name:
                try:
                    js.quit()
                except Exception:
                    pass
                continue

            if device_index not in self.gamepads:
                self._register_gamepad(device_index)

    def _register_gamepad(self, device_index: int):
        """Yeni bir gamepad'i kaydet"""
        try:
            js = pygame.joystick.Joystick(device_index)
            js.init()

            controller = self._create_controller(js, device_index)

            gp_type = self._detect_type(js)
            name = js.get_name()
            guid = ''
            try:
                guid = js.get_guid()
            except Exception:
                pass

            if controller is not None:
                try:
                    controller_name = getattr(controller, 'name', '') or ''
                    if controller_name:
                        name = controller_name
                except Exception:
                    pass

            state = GamepadState(
                joystick=js,
                controller=controller,
                gamepad_type=gp_type,
                name=name,
                guid=guid,
                instance_id=self._get_joystick_instance_id(js),
            )
            self.gamepads[device_index] = state
            print(f"🎮 Gamepad bağlandı: {name} [{gp_type}] (ID: {device_index})")
            return True
        except Exception as e:
            print(f"⚠️ Gamepad {device_index} başlatılamadı: {e}")
            return False

    def _detect_type(self, js: pygame.joystick.JoystickType) -> str:
        """Kontrolcü tipini ismine göre algıla"""
        name = js.get_name().lower()

        # Xbox ailesi
        if any(k in name for k in ('xbox', 'xinput', 'x-box', 'microsoft')):
            return GamepadType.XBOX

        # PlayStation ailesi
        if any(k in name for k in (
            'dualsense', 'dualshock', 'ps5', 'ps4', 'ps3',
            'playstation', 'sony', 'wireless controller'
        )):
            return GamepadType.PLAYSTATION

        # Nintendo ailesi
        if any(k in name for k in (
            'pro controller', 'joy-con', 'switch', 'nintendo',
            'joycon', 'joy con'
        )):
            return GamepadType.NINTENDO

        return GamepadType.UNKNOWN

    def _get_joystick_instance_id(self, js: pygame.joystick.JoystickType) -> Optional[int]:
        if js is None:
            return None
        for attr_name in ('get_instance_id', 'get_id'):
            getter = getattr(js, attr_name, None)
            if not callable(getter):
                continue
            try:
                value = getter()
            except Exception:
                continue
            if isinstance(value, int):
                return value
        return None

    def _create_controller(self, js: pygame.joystick.JoystickType, device_index: int):
        if js is None or _sdl2_controller is None:
            return None

        try:
            if not _sdl2_controller.get_init():
                _sdl2_controller.init()
        except Exception:
            return None

        factories = []
        from_joystick = getattr(_sdl2_controller.Controller, 'from_joystick', None)
        if callable(from_joystick):
            factories.append(lambda: from_joystick(js))

        is_controller = getattr(_sdl2_controller, 'is_controller', None)
        if callable(is_controller):
            try:
                if is_controller(device_index):
                    factories.append(lambda: _sdl2_controller.Controller(device_index))
            except Exception:
                pass
        else:
            factories.append(lambda: _sdl2_controller.Controller(device_index))

        for factory in factories:
            try:
                controller = factory()
            except Exception:
                continue
            if controller is None:
                continue
            try:
                if hasattr(controller, 'get_init') and not controller.get_init() and hasattr(controller, 'init'):
                    controller.init()
            except Exception:
                pass
            return controller

        return None

    def _normalize_playstation_raw_button(self, raw_index: int, name: str) -> int:
        """Ham PlayStation joystick buton indekslerini standart SDL layout'una eşler."""
        # Windows DirectInput veya macOS ham Bluetooth modlarında buton indeksleri farklılık gösterir.
        # Standart SDL GameController düzeni: A=0 (Cross), B=1 (Circle), X=2 (Square), Y=3 (Triangle), 
        # Back=4 (Share), Guide=5 (PS), Start=6 (Options), L3=7, R3=8, L1=9, R1=10
        
        # Yaygın kablosuz / kablolu ham PlayStation eşleme tabloları
        # 1. Standart Windows DirectInput / DS4 / DualSense Bluetooth ham eşlemesi:
        # Square=0, Cross=1, Circle=2, Triangle=3, L1=4, R1=5, L2=6, R2=7, Share=8, Options=9, L3=10, R3=11, PS=12
        dinput_map = {
            1: 0,   # Cross -> A (0)
            2: 1,   # Circle -> B (1)
            0: 2,   # Square -> X (2)
            3: 3,   # Triangle -> Y (3)
            4: 9,   # L1 -> LShoulder (9)
            5: 10,  # R1 -> RShoulder (10)
            8: 4,   # Share/Select -> Back (4)
            9: 6,   # Options/Start -> Start (6)
            10: 7,  # L3 -> LStickClick (7)
            11: 8,  # R3 -> RStickClick (8)
            12: 5,  # PS Button -> Guide (5)
        }
        
        # Eğer isim veya cihaz PlayStation olarak tanımlanmışsa ve dinput_map içinde indeks varsa eşle
        return dinput_map.get(raw_index, raw_index)

    def _normalize_raw_button_index(self, gp: Optional[GamepadState], raw_button_index: int) -> int:
        try:
            raw_index = int(raw_button_index)
        except Exception:
            return raw_button_index

        if gp is None:
            return raw_index
            
        gp_type = getattr(gp, 'gamepad_type', GamepadType.UNKNOWN)
        gp_name = getattr(gp, 'name', '').lower()
        
        if gp_type == GamepadType.XBOX or gp_type == GamepadType.UNKNOWN:
            return WINDOWS_XINPUT_RAW_BUTTON_TO_CANONICAL.get(raw_index, raw_index)
            
        if gp_type == GamepadType.PLAYSTATION:
            # Sadece ham joystick modundaysak (Controller nesnesi yoksa) normalizasyon uygula
            if getattr(gp, 'controller', None) is None:
                return self._normalize_playstation_raw_button(raw_index, gp_name)
                
        return raw_index

    def _read_button_states(self, gp: GamepadState) -> Dict[int, bool]:
        controller = getattr(gp, 'controller', None)
        if controller is not None:
            buttons: Dict[int, bool] = {}
            for btn_idx in CANONICAL_CONTROLLER_BUTTONS:
                try:
                    buttons[btn_idx] = bool(controller.get_button(btn_idx))
                except Exception:
                    buttons.setdefault(btn_idx, False)
            return buttons

        buttons: Dict[int, bool] = {}
        js = gp.joystick
        if js is None:
            return buttons

        try:
            num_buttons = js.get_numbuttons()
        except Exception:
            return buttons

        for raw_idx in range(num_buttons):
            try:
                pressed = bool(js.get_button(raw_idx))
            except Exception:
                pressed = False
            canonical_idx = self._normalize_raw_button_index(gp, raw_idx)
            buttons[canonical_idx] = buttons.get(canonical_idx, False) or pressed
        return buttons

    def _normalize_controller_axis_value(self, value, *, trigger: bool = False) -> float:
        try:
            axis = float(value)
        except Exception:
            return 0.0
        if not math.isfinite(axis):
            return 0.0

        if trigger:
            if axis > 1.5:
                axis = axis / 32767.0
            elif axis < -0.001:
                axis = (axis + 1.0) / 2.0
            return max(0.0, min(1.0, axis))

        if abs(axis) > 1.5:
            scale = 32768.0 if axis < 0.0 else 32767.0
            axis = axis / scale
        return max(-1.0, min(1.0, axis))

    def _read_controller_axis(self, gp: GamepadState, axis_index: int, *, trigger: bool = False) -> float:
        controller = getattr(gp, 'controller', None)
        if controller is None:
            return 0.0
        try:
            raw_value = controller.get_axis(axis_index)
        except Exception:
            return 0.0
        return self._normalize_controller_axis_value(raw_value, trigger=trigger)

    def _find_gamepad_for_event(self, joy_id=None, instance_id=None) -> Optional[GamepadState]:
        target_instance = None
        if isinstance(instance_id, (int, float)) and not isinstance(instance_id, bool):
            target_instance = int(instance_id)
        target_joy = None
        if isinstance(joy_id, (int, float)) and not isinstance(joy_id, bool):
            target_joy = int(joy_id)

        if target_instance is not None:
            for gp in self.gamepads.values():
                if getattr(gp, 'instance_id', None) == target_instance:
                    return gp
                if self._get_joystick_instance_id(getattr(gp, 'joystick', None)) == target_instance:
                    return gp

        if target_joy is not None:
            direct_match = self.gamepads.get(target_joy)
            if direct_match is not None:
                return direct_match
            for device_index, gp in self.gamepads.items():
                if device_index == target_joy:
                    return gp
                js = getattr(gp, 'joystick', None)
                getter = getattr(js, 'get_id', None)
                if callable(getter):
                    try:
                        if int(getter()) == target_joy:
                            return gp
                    except Exception:
                        pass

        return self.get_active_gamepad()

    def resolve_capture_button_index(self, raw_button_index: int, *, joy_id=None, instance_id=None) -> int:
        gp = self._find_gamepad_for_event(joy_id=joy_id, instance_id=instance_id)
        if gp is not None and getattr(gp, 'controller', None) is not None:
            controller = gp.controller
            current_pressed = {}
            for btn_idx in CANONICAL_CONTROLLER_BUTTONS:
                try:
                    current_pressed[btn_idx] = bool(controller.get_button(btn_idx))
                except Exception:
                    current_pressed[btn_idx] = bool(gp.buttons.get(btn_idx, False))

            newly_pressed = [
                btn_idx
                for btn_idx, is_pressed in current_pressed.items()
                if is_pressed and not gp.prev_buttons.get(btn_idx, False)
            ]
            if len(newly_pressed) == 1:
                return newly_pressed[0]
            if newly_pressed:
                return newly_pressed[-1]

            pressed = [btn_idx for btn_idx, is_pressed in current_pressed.items() if is_pressed]
            if len(pressed) == 1:
                return pressed[0]

        return self._normalize_raw_button_index(gp, raw_button_index)

    def resolve_capture_trigger_index(self, raw_axis, raw_value, *, joy_id=None, instance_id=None) -> Optional[int]:
        gp = self._find_gamepad_for_event(joy_id=joy_id, instance_id=instance_id)
        if gp is not None and getattr(gp, 'controller', None) is not None:
            left = float(getattr(gp, 'left_trigger', 0.0) or 0.0)
            right = float(getattr(gp, 'right_trigger', 0.0) or 0.0)
            if left >= self.TRIGGER_THRESHOLD or right >= self.TRIGGER_THRESHOLD:
                return 100 if left >= right else 101

        try:
            axis_index = int(raw_axis)
        except Exception:
            return None
        if axis_index not in (4, 5):
            return None

        try:
            trigger_value = float(raw_value)
        except Exception:
            trigger_value = 0.0
        if trigger_value < 0.0:
            trigger_value = (trigger_value + 1.0) / 2.0
        if trigger_value >= self.TRIGGER_THRESHOLD:
            return 100 if axis_index == 4 else 101
        return None

    def get_active_gamepad(self) -> Optional[GamepadState]:
        """İlk aktif gamepad'i döndür"""
        for gp in self.gamepads.values():
            if gp.joystick and gp.joystick.get_init():
                return gp
        return None

    def get_gamepad_type_label(self) -> str:
        """Aktif gamepad'in kullanıcı dostu adını döndür"""
        gp = self.get_active_gamepad()
        if not gp:
            return ''
        labels = {
            GamepadType.XBOX: 'Xbox Controller',
            GamepadType.PLAYSTATION: 'PlayStation Controller',
            GamepadType.NINTENDO: 'Nintendo Controller',
            GamepadType.UNKNOWN: 'Gamepad',
        }
        return labels.get(gp.gamepad_type, 'Gamepad')

    def set_context(self, context: str):
        """Aktif bağlamı ayarla: 'game' veya 'menu'.
        B butonu oyun içinde rotate, menüde back olarak çalışır.
        Bağlam değişiminde prev_buttons sıfırlanır (hayalet event önleme)."""
        if context != self._context:
            self._context = context
            # Bağlam geçişinde önceki buton durumlarını sıfırla.
            # Böylece eski bağlamdaki basılı butonlar yeni bağlamda
            # yanlış edge-transition event'i üretmez.
            for gp in self.gamepads.values():
                gp.prev_buttons = dict(gp.buttons)
                gp.prev_left_trigger_pressed = gp.left_trigger >= self.TRIGGER_THRESHOLD
                gp.prev_right_trigger_pressed = gp.right_trigger >= self.TRIGGER_THRESHOLD

    def get_context(self) -> str:
        """Aktif bağlamı döndür."""
        return self._context

    def set_suppress_pointer_mode(self, suppress: bool) -> None:
        """Focus-nav olan ekranlar pointer mode'u bastırmak için kullanır.

        True iken sağ stick fare imlecini taşımaya devam eder ama
        `_menu_pointer_active` otomatik aktifleşmez; A butonu K_RETURN
        üretmeye devam eder (mouse click yerine).
        """
        self._suppress_pointer_mode = bool(suppress)
        if suppress:
            self._menu_pointer_active = False

    def is_connected(self) -> bool:
        """Herhangi bir gamepad bağlı mı?"""
        return any(
            gp.joystick and gp.joystick.get_init()
            for gp in self.gamepads.values()
        )

    def is_direction_held(self, direction: str) -> bool:
        """Belirtilen yönün (up/down/left/right) gamepad'de basılı tutulup
        tutulmadığını döndür. D-pad VEYA sol analog stick kontrol edilir.

        Bu metod pygame.key.get_pressed() ile birlikte kullanılarak
        gamepad'den gelen sürekli yön girdisini algılamak için tasarlanmıştır.
        """
        gp = self.get_active_gamepad()
        if not gp:
            return False

        # Yön -> Karşılık gelen aksiyon eşleşmesi
        dir_to_action = {
            'up': 'rotate',
            'down': 'soft_drop',
            'left': 'move_left',
            'right': 'move_right'
        }
        
        # Eğer bu yöne atanmış aksiyon (rebind edilmiş buton) şu an basılıysa doğrudan True dön
        action = dir_to_action.get(direction)
        if action and self.is_action_pressed(action):
            return True

        # Eğer bu yön bir aksiyon tarafından override edildiyse yön girdisini algılama
        suppressed = self._get_overridden_dpad_dirs() if self._context == self.CONTEXT_GAME else set()
        if direction in suppressed:
            return False

        # D-pad kontrolü
        dx, dy = gp.dpad
        if direction == 'down' and dy == -1:    # SDL hat: aşağı = -1
            return True
        if direction == 'up' and dy == 1:       # SDL hat: yukarı = +1
            return True
        if direction == 'left' and dx == -1:
            return True
        if direction == 'right' and dx == 1:
            return True

        # Sol stick kontrolü: sadece menü/UI'da; oyun içinde D-pad yeterli
        if self._context != self.CONTEXT_GAME:
            if direction == 'down' and gp.left_stick.digital_y == 1:
                return True
            if direction == 'up' and gp.left_stick.digital_y == -1:
                return True
            if direction == 'left' and gp.left_stick.digital_x == -1:
                return True
            if direction == 'right' and gp.left_stick.digital_x == 1:
                return True

        return False

    def is_action_pressed(self, action: str) -> bool:
        """Belirtilen gamepad aksiyonunun şu an basılı olup olmadığını döndür.

        pygame.key.get_pressed() sentetik olayları algılamadığından,
        kart yetenekleri (G, H, B vb.) için doğrudan gamepad buton
        durumunu kontrol etmek gerekir.
        """
        binding = self._bindings.get(action)
        if not binding:
            return False
        gp = self.get_active_gamepad()
        if not gp:
            return False
        for trigger_dir in self._iter_trigger_dirs(binding):
            if trigger_dir == 'left' and gp.left_trigger >= self.TRIGGER_THRESHOLD:
                return True
            if trigger_dir == 'right' and gp.right_trigger >= self.TRIGGER_THRESHOLD:
                return True

        for btn in self._iter_button_indices(binding):
            if gp.buttons.get(btn, False):
                return True

        return False

    def was_action_just_pressed(self, action: str) -> bool:
        """Belirtilen aksiyon bu frame'de yeni basıldı mı? (edge detection)

        Önceki frame'de basılı değilken şimdi basılıysa True döner.
        """
        binding = self._bindings.get(action)
        if not binding:
            return False
        gp = self.get_active_gamepad()
        if not gp:
            return False
        for trigger_dir in self._iter_trigger_dirs(binding):
            if trigger_dir == 'left':
                now = gp.left_trigger >= self.TRIGGER_THRESHOLD
                prev = gp.prev_left_trigger_pressed
                if now and not prev:
                    return True
            elif trigger_dir == 'right':
                now = gp.right_trigger >= self.TRIGGER_THRESHOLD
                prev = gp.prev_right_trigger_pressed
                if now and not prev:
                    return True

        for btn in self._iter_button_indices(binding):
            now = gp.buttons.get(btn, False)
            prev = gp.prev_buttons.get(btn, False)
            if now and not prev:
                return True

        return False

    def get_action_button_indices(self, action: str) -> List[int]:
        """Bir aksiyonun primary/secondary buton indekslerini döndür.

        Trigger binding'leri pseudo index olarak döner:
        - 100: left trigger
        - 101: right trigger
        """
        binding = self._bindings.get(action, {})
        if not binding:
            return []

        indices: List[int] = []
        for trigger_dir in self._iter_trigger_dirs(binding):
            pseudo_idx = 100 if trigger_dir == 'left' else 101
            if pseudo_idx not in indices:
                indices.append(pseudo_idx)

        for btn in self._iter_button_indices(binding):
            if btn not in indices:
                indices.append(btn)

        return indices

    def get_button_label(self, action: str, gp_type: str = None) -> str:
        """Bir aksiyon için kontrolcüye özgü buton etiketini döndür.

        Örn: get_button_label('hard_drop', 'xbox') → 'A'
             get_button_label('hard_drop', 'playstation') → '✕'
             get_button_label('hard_drop', 'nintendo') → 'B'
        """
        if gp_type is None:
            gp = self.get_active_gamepad()
            gp_type = gp.gamepad_type if gp else GamepadType.UNKNOWN

        binding = self._bindings.get(action, {})

        # D-pad aksiyonları
        dpad_dir = binding.get('dpad')
        if dpad_dir and 'button' not in binding and 'trigger' not in binding:
            dpad_labels = {
                'up': '🔼 D-pad ↑',
                'down': '🔽 D-pad ↓',
                'left': '◀ D-pad ←',
                'right': '▶ D-pad →',
            }
            return dpad_labels.get(dpad_dir, f'D-pad {dpad_dir}')

        labels: List[str] = []
        for trigger_dir in self._iter_trigger_dirs(binding):
            pseudo_idx = 100 if trigger_dir == 'left' else 101
            labels.append(self.get_button_index_label(pseudo_idx, gp_type))

        for btn in self._iter_button_indices(binding):
            labels.append(self.get_button_index_label(btn, gp_type))

        uniq: List[str] = []
        for lbl in labels:
            if lbl not in uniq:
                uniq.append(lbl)
        if not uniq:
            return '?'
        if len(uniq) == 1:
            return uniq[0]
        return f"{uniq[0]} / {uniq[1]}"

    def get_button_index_label(self, btn_index: int, gp_type: str = None) -> str:
        """Buton indeksinden kontrolcüye özgü etiket döndür.

        Örn: get_button_index_label(0, 'xbox') → 'A'
             get_button_index_label(0, 'playstation') → '✕'
             get_button_index_label(100) → 'LT' (trigger)
        """
        # Özel trigger indeksleri
        if btn_index == 100:
            trigger_labels = {
                GamepadType.XBOX: 'LT',
                GamepadType.PLAYSTATION: 'L2',
                GamepadType.NINTENDO: 'ZL',
            }
            return trigger_labels.get(gp_type or GamepadType.UNKNOWN, 'LT')
        if btn_index == 101:
            trigger_labels = {
                GamepadType.XBOX: 'RT',
                GamepadType.PLAYSTATION: 'R2',
                GamepadType.NINTENDO: 'ZR',
            }
            return trigger_labels.get(gp_type or GamepadType.UNKNOWN, 'RT')

        # D-pad butonlari (SDL GameController hat buttons map)
        dpad_labels = {
            11: 'D-Pad Up',
            12: 'D-Pad Down',
            13: 'D-Pad Left',
            14: 'D-Pad Right',
        }
        if btn_index in dpad_labels:
            return dpad_labels[btn_index]

        if gp_type is None:
            gp = self.get_active_gamepad()
            gp_type = gp.gamepad_type if gp else GamepadType.UNKNOWN

        # Xbox buton isimleri
        xbox_labels = {0: 'A', 1: 'B', 2: 'X', 3: 'Y', 4: '-', 5: 'Guide',
                   6: '+', 7: 'LS', 8: 'RS', 9: 'LB', 10: 'RB'}
        # PlayStation buton isimleri
        ps_labels = {0: '✕', 1: '○', 2: '□', 3: '△', 4: '-', 5: 'PS',
                 6: '+', 7: 'L3', 8: 'R3', 9: 'L1', 10: 'R1'}
        # Nintendo buton isimleri (ters A/B)
        nintendo_labels = {0: 'B', 1: 'A', 2: 'Y', 3: 'X', 4: '-', 5: 'Home',
                   6: '+', 7: 'LS', 8: 'RS', 9: 'L', 10: 'R'}

        label_map = {
            GamepadType.XBOX: xbox_labels,
            GamepadType.PLAYSTATION: ps_labels,
            GamepadType.NINTENDO: nintendo_labels,
        }

        labels = label_map.get(gp_type, xbox_labels)
        return labels.get(btn_index, f'Btn{btn_index}')

    # ─── Ana Güncelleme Döngüsü ────────────────────────────────────────────

    def update(self, delta_ms: float) -> List[pygame.event.Event]:
        """Her frame çağrılır. Gamepad durumunu günceller ve
        sentetik pygame olayları listesi döndürür.

        Args:
            delta_ms: Son frame'den bu yana geçen süre (milisaniye)

        Returns:
            Sentetik pygame event'leri listesi (KEYDOWN/KEYUP)
        """
        if not self.enabled:
            return []

        if not hasattr(self, '_internal_time'):
            self._internal_time = 0.0
        self._internal_time += delta_ms

        synthetic: List[pygame.event.Event] = []

        # Bağlantı/kopma kontrolü
        self._check_connections()

        for gp_id, gp in list(self.gamepads.items()):
            if not gp.joystick or not gp.joystick.get_init():
                continue

            try:
                # Önceki durumu kaydet
                gp.prev_buttons = dict(gp.buttons)
                gp.prev_dpad = gp.dpad
                gp.left_stick.prev_digital_x = gp.left_stick.digital_x
                gp.left_stick.prev_digital_y = gp.left_stick.digital_y
                # Trigger prev durumunu da BURADA (yeni degerler okunmadan once)
                # kaydet ki was_action_just_pressed('slot_5'/'slot_6') edge
                # algilamasi butonlarla simetrik calissin. Aksi halde prev,
                # _generate_trigger_events sonunda guncel degere set ediliyor ve
                # poll sirasinda now==prev olup LT/RT slotlari hic tetiklenmiyordu.
                gp.prev_left_trigger_pressed = gp.left_trigger >= self.TRIGGER_THRESHOLD
                gp.prev_right_trigger_pressed = gp.right_trigger >= self.TRIGGER_THRESHOLD

                gp.buttons = self._read_button_states(gp)

                controller = getattr(gp, 'controller', None)
                num_axes = 0
                try:
                    num_axes = gp.joystick.get_numaxes()
                except Exception:
                    num_axes = 0

                if num_axes >= 2:
                    raw_x = self._sanitize_axis(gp.joystick.get_axis(0))
                    raw_y = self._sanitize_axis(gp.joystick.get_axis(1))
                    gp.left_stick.x = self._apply_deadzone(raw_x)
                    gp.left_stick.y = self._apply_deadzone(raw_y)
                elif controller is not None:
                    raw_x = self._read_controller_axis(gp, CONTROLLER_AXIS_LEFTX)
                    raw_y = self._read_controller_axis(gp, CONTROLLER_AXIS_LEFTY)
                    gp.left_stick.x = self._apply_deadzone(raw_x)
                    gp.left_stick.y = self._apply_deadzone(raw_y)

                if num_axes >= 4:
                    raw_right_x = self._sanitize_axis(gp.joystick.get_axis(2))
                    raw_right_y = self._sanitize_axis(gp.joystick.get_axis(3))
                    gp.raw_right_x = raw_right_x
                    gp.raw_right_y = raw_right_y
                    gp.right_stick.x = self._apply_deadzone(raw_right_x)
                    gp.right_stick.y = self._apply_deadzone(raw_right_y)
                    self._update_mouse_neutral(gp)
                elif controller is not None:
                    # Button canonicalization icin SDL controller kullansak da
                    # sag stick mouse emulasyonu joystick axis yolunda daha stabil.
                    raw_right_x = self._read_controller_axis(gp, CONTROLLER_AXIS_RIGHTX)
                    raw_right_y = self._read_controller_axis(gp, CONTROLLER_AXIS_RIGHTY)
                    gp.raw_right_x = raw_right_x
                    gp.raw_right_y = raw_right_y
                    gp.right_stick.x = self._apply_deadzone(raw_right_x)
                    gp.right_stick.y = self._apply_deadzone(raw_right_y)
                    self._update_mouse_neutral(gp)
                else:
                    gp.raw_right_x = 0.0
                    gp.raw_right_y = 0.0
                    self._reset_mouse_emulation(gp)

                if num_axes >= 6:
                    raw_lt = gp.joystick.get_axis(4)
                    raw_rt = gp.joystick.get_axis(5)
                    
                    # İlk frame'lerde eksenlerin kararsız başlangıç değerlerini (-1.0 veya 0.0) süzmek için guard
                    if not getattr(gp, '_trigger_calibrated', False):
                        gp._trigger_calibrated = True
                        # Tetikler bırakılmış durumdayken genellikle -1.0 veya tam 0.0 döner.
                        # Eğer her iki tetik de belirgin şekilde negatifse aralık -1..1'dir, aksi halde 0..1'dir.
                        gp._trigger_range_full = (raw_lt < -0.5 and raw_rt < -0.5)
                        gp._trigger_initial_raw_lt = raw_lt
                        gp._trigger_initial_raw_rt = raw_rt
                    
                    # Sürücü kararsızlığını önlemek için başlangıçtaki sıfır noktasını koru
                    if getattr(gp, '_trigger_range_full', True):
                        gp.left_trigger = max(0.0, (raw_lt + 1.0) / 2.0)
                        gp.right_trigger = max(0.0, (raw_rt + 1.0) / 2.0)
                    else:
                        # Eğer aralık 0..1 ise ve henüz tetiklere basılmadıysa başlangıçtaki gürültüyü süz
                        if raw_lt == getattr(gp, '_trigger_initial_raw_lt', 0.0) and raw_lt < 0.1:
                            gp.left_trigger = 0.0
                        else:
                            gp.left_trigger = max(0.0, min(1.0, raw_lt))
                            
                        if raw_rt == getattr(gp, '_trigger_initial_raw_rt', 0.0) and raw_rt < 0.1:
                            gp.right_trigger = 0.0
                        else:
                            gp.right_trigger = max(0.0, min(1.0, raw_rt))
                elif controller is not None:
                    gp.left_trigger = self._read_controller_axis(gp, CONTROLLER_AXIS_TRIGGERLEFT, trigger=True)
                    gp.right_trigger = self._read_controller_axis(gp, CONTROLLER_AXIS_TRIGGERRIGHT, trigger=True)
                    gp._trigger_calibrated = True
                    gp._trigger_range_full = False
                else:
                    gp.left_trigger = 0.0
                    gp.right_trigger = 0.0
                    gp._trigger_calibrated = False
                    gp._trigger_range_full = True

                # D-pad: önce hat, gerekirse button 11-14 fallback
                gp.dpad = self._read_dpad_state(gp)

                # Dijital yön hesapla (analog stick → dijital)
                gp.left_stick.digital_x = self._to_digital(gp.left_stick.x)
                gp.left_stick.digital_y = self._to_digital(gp.left_stick.y)

                # Olayları üret
                synthetic.extend(self._generate_button_events(gp))
                synthetic.extend(self._generate_trigger_events(gp))
                synthetic.extend(self._generate_dpad_events(gp, delta_ms))
                synthetic.extend(self._generate_stick_events(gp, delta_ms))
                synthetic.extend(self._generate_mouse_events(gp, delta_ms))
                synthetic.extend(self._generate_mouse_click_events(gp))

            except Exception as e:
                # Gamepad kopmuş olabilir
                print(f"⚠️ Gamepad {gp_id} okuma hatası: {e}")

        # Son aktif gamepad girdisi zamanını güncelle (basılı tutma durumları dahil)
        has_active_input = False
        for gp in self.gamepads.values():
            if not gp.joystick or not gp.joystick.get_init():
                continue
            if any(gp.buttons.values()):
                has_active_input = True
                break
            if gp.left_stick.x != 0.0 or gp.left_stick.y != 0.0:
                has_active_input = True
                break
            if gp.right_stick.x != 0.0 or gp.right_stick.y != 0.0:
                has_active_input = True
                break
            if gp.dpad != (0, 0):
                has_active_input = True
                break
            if gp.left_trigger >= self.TRIGGER_THRESHOLD or gp.right_trigger >= self.TRIGGER_THRESHOLD:
                has_active_input = True
                break

        if synthetic or has_active_input:
            self._last_gamepad_input_time = int(self._internal_time)

        # Menü bağlamındayken mükerrer/çift sinyal gönderme sorununu çözmek için
        # synthetic KEYDOWN olaylarını debouncing filtresinden geçir.
        if self._context == self.CONTEXT_MENU:
            now = int(self._internal_time)
            filtered_synthetic = []
            if not hasattr(self, '_last_menu_key_times'):
                self._last_menu_key_times = {}
            for ev in synthetic:
                if ev.type == pygame.KEYDOWN:
                    if ev.key in self._last_menu_key_times:
                        last_time = self._last_menu_key_times[ev.key]
                        if now - last_time < 80:  # 80ms debounce
                            continue
                    self._last_menu_key_times[ev.key] = now
                filtered_synthetic.append(ev)
            return filtered_synthetic

        return synthetic

    def _check_connections(self) -> None:
        """Yeni bağlanan/kopan gamepad'leri kontrol et"""
        try:
            known_ids = set(self.gamepads.keys())

            # Kopanlar (pygame erişilemez hale gelmiş)
            for gp_id in list(known_ids):
                gp = self.gamepads[gp_id]
                try:
                    if gp.joystick and not gp.joystick.get_init():
                        raise RuntimeError("not init")
                    # Basit bir get ile kontrol
                    if gp.joystick:
                        gp.joystick.get_name()
                except Exception:
                    print(f"🎮 Gamepad koptu: {gp.name} (ID: {gp_id})")
                    del self.gamepads[gp_id]

            # Yeni bağlananları de-duplication mantığıyla tara ve kaydet
            self._scan_gamepads()
        except Exception:
            pass

    def handle_hotplug_event(self, event) -> str | None:
        """Pygame `JOYDEVICEADDED` / `JOYDEVICEREMOVED` event'ini işle.

        Bu yöntem oyun döngüsünden çağrılmalıdır; `update()` içindeki
        polling döngüsü her tick koşmayabilir veya pygame bazı platformlarda
        `joystick.get_count()`'u reconnect sonrası geç günceller. Event
        tabanlı yol, hem prompt connected-state'ini hem de auto-pause
        akışlarını gerçek-zamanda doğru tutar.

        Geri dönüş:
        - 'connected'    : Yeni bir gamepad eklendi (veya yeniden algılandı).
        - 'disconnected' : Bilinen bir gamepad kopuldu.
        - None           : Event tipi konu dışı veya state değişmedi.
        """
        event_type = getattr(event, 'type', None)
        if event_type is None:
            return None

        added_type = getattr(pygame, 'JOYDEVICEADDED', None)
        removed_type = getattr(pygame, 'JOYDEVICEREMOVED', None)

        if (added_type is not None and event_type == added_type):
            # Yeni cihaz eklendi → eğer event device_index sağlıyorsa sadece o indeksi işle
            device_index = getattr(event, 'device_index', None)
            if device_index is not None:
                # Aynı slotta zaten CANLI bir kayıt olabilir: ana döngü
                # update() → _check_connections() polling'i handle_input'tan
                # ÖNCE koşar ve replug edilen cihazı bu frame'de zaten
                # kaydetmiş olabilir. Canlı bir joystick'i quit() edip yeniden
                # kaydetmek girişi anlık olarak bozar (reconnect kaçar). Bu
                # yüzden yalnızca gerçekten bayat (init olmayan/erişilemez) bir
                # slotu temizleyip yeniden kaydet.
                existing = self.gamepads.get(device_index)
                if existing is not None:
                    still_live = False
                    try:
                        js = getattr(existing, 'joystick', None)
                        if js is not None and js.get_init():
                            js.get_name()  # erişilebilir mi?
                            still_live = True
                    except Exception:
                        still_live = False
                    if still_live:
                        # Polling zaten kaydetmiş; churn yok, bağlı kabul et.
                        self._menu_pointer_active = False
                        return 'connected'
                    # Bayat slot → temizle ve yeniden kaydet.
                    try:
                        js = getattr(existing, 'joystick', None)
                        if js is not None:
                            js.quit()
                    except Exception:
                        pass
                    try:
                        del self.gamepads[device_index]
                    except Exception:
                        pass

                try:
                    registered = self._register_gamepad(device_index)
                except Exception:
                    registered = False
                if registered:
                    self._menu_pointer_active = False
                    try:
                        print(f"[Gamepad] Yeni kontrolcü bağlandı (Index: {device_index})")
                    except Exception:
                        pass
                    return 'connected'
                # device_index ile kayıt başarısız olduysa (indeks kayması
                # olabilir) genel taramaya düş; böylece reconnect kaçmaz.
                try:
                    self._check_connections()
                except Exception:
                    pass
                self._menu_pointer_active = False
                return 'connected' if len(self.gamepads) > 0 else None

            # Cihaz indeksi yoksa, genel tarama/fallback yap
            try:
                self._check_connections()
            except Exception:
                try:
                    # Fallback: tam tarama
                    self._scan_gamepads()
                except Exception:
                    pass
            # pointer state sıfırla
            self._menu_pointer_active = False
            return 'connected' if len(self.gamepads) > 0 else None

        if (removed_type is not None and event_type == removed_type):
            instance_id = getattr(event, 'instance_id', None)
            if instance_id is None:
                return None
            # Eşleşen instance_id'yi bul ve sil
            matched_idx = None
            for idx, gp in list(self.gamepads.items()):
                try:
                    if getattr(gp, 'instance_id', None) == instance_id:
                        matched_idx = idx
                        break
                except Exception:
                    continue
            if matched_idx is not None:
                try:
                    stale = self.gamepads[matched_idx]
                    if stale and getattr(stale, 'joystick', None) is not None:
                        stale.joystick.quit()
                except Exception:
                    pass
                try:
                    del self.gamepads[matched_idx]
                except Exception:
                    pass
                self._menu_pointer_active = False
                try:
                    print(f"[Gamepad] Kontrolcü bağlantısı kesildi (Instance: {instance_id})")
                except Exception:
                    pass
                return 'disconnected'

            # matched_idx None: muhtemelen update()/_check_connections() bu
            # frame'de polling ile cihazı zaten kaldırmış olabilir (ana döngü
            # update'i handle_input'tan önce çağırır). Bu durumda da disconnect
            # bilgisini kaybetme — auto-pause tetiklensin. Yalnızca artık hiç
            # bağlı kontrolcü kalmadıysa 'disconnected' bildir.
            if not self.is_connected():
                self._menu_pointer_active = False
                return 'disconnected'

        return None

    def _apply_deadzone(self, value: float) -> float:
        """Dead-zone uygula"""
        if abs(value) < self.DEADZONE:
            return 0.0
        # Dead-zone sonrası değeri 0-1 aralığına normalize et
        sign = 1.0 if value > 0 else -1.0
        normalized = (abs(value) - self.DEADZONE) / (1.0 - self.DEADZONE)
        return sign * min(1.0, normalized)

    def _to_digital(self, value: float) -> int:
        """Analog değeri dijital yöne çevir (-1, 0, +1)"""
        if value < -self.DIGITAL_THRESHOLD:
            return -1
        if value > self.DIGITAL_THRESHOLD:
            return +1
        return 0

    def _buttons_to_dpad(self, gp: GamepadState) -> tuple[int, int]:
        """Buton 11-14 üzerinden D-pad durumunu çöz.

        Bazı cihazlar D-pad'i hat yerine SDL button 11-14 olarak raporlar.
        """
        x = 0
        y = 0
        if gp.buttons.get(13, False):
            x -= 1
        if gp.buttons.get(14, False):
            x += 1
        if gp.buttons.get(11, False):
            y += 1
        if gp.buttons.get(12, False):
            y -= 1
        return (max(-1, min(1, x)), max(-1, min(1, y)))

    def _read_dpad_state(self, gp: GamepadState) -> tuple[int, int]:
        """D-pad durumunu hat + button fallback ile oku.

        Hat raporu olan kontrolcülerde hat yetkilidir; buton 11-14
        farklı fonksiyonlara ait olabilir (touchpad, share vb.).
        Buton fallback yalnızca hat olmayan kontrolcülerde kullanılır.
        """
        controller = getattr(gp, 'controller', None)
        if controller is not None:
            try:
                left = bool(controller.get_button(CONTROLLER_BUTTON_DPAD_LEFT))
                right = bool(controller.get_button(CONTROLLER_BUTTON_DPAD_RIGHT))
                up = bool(controller.get_button(CONTROLLER_BUTTON_DPAD_UP))
                down = bool(controller.get_button(CONTROLLER_BUTTON_DPAD_DOWN))
                return (
                    max(-1, min(1, (-1 if left else 0) + (1 if right else 0))),
                    max(-1, min(1, (1 if up else 0) + (-1 if down else 0))),
                )
            except Exception:
                pass

        hat_x = 0
        hat_y = 0
        has_hat = False
        try:
            js = gp.joystick
            if js and js.get_numhats() > 0:
                has_hat = True
                hat_x, hat_y = js.get_hat(0)
        except Exception:
            hat_x, hat_y = 0, 0

        if not has_hat:
            btn_x, btn_y = self._buttons_to_dpad(gp)
            if hat_x == 0 and btn_x != 0:
                hat_x = btn_x
            if hat_y == 0 and btn_y != 0:
                hat_y = btn_y
        return (hat_x, hat_y)

    def _reset_mouse_emulation(self, gp: GamepadState) -> None:
        gp.mouse_control_active = False
        gp.mouse_accum_x = 0.0
        gp.mouse_accum_y = 0.0

    def _sanitize_axis(self, value: float | int | None) -> float:
        try:
            axis = float(value)
        except Exception:
            return 0.0
        if not math.isfinite(axis):
            return 0.0
        return max(-1.0, min(1.0, axis))

    def _update_mouse_neutral(self, gp: GamepadState) -> None:
        raw_x = self._sanitize_axis(getattr(gp, 'raw_right_x', 0.0))
        raw_y = self._sanitize_axis(getattr(gp, 'raw_right_y', 0.0))

        if not gp.mouse_neutral_ready:
            gp.mouse_neutral_x = raw_x
            gp.mouse_neutral_y = raw_y
            gp.mouse_neutral_ready = True
            return

        if gp.mouse_control_active:
            return

        drift_x = raw_x - gp.mouse_neutral_x
        drift_y = raw_y - gp.mouse_neutral_y
        if math.hypot(drift_x, drift_y) > self.MOUSE_NEUTRAL_TRACK_THRESHOLD:
            return

        follow = float(self.MOUSE_NEUTRAL_FOLLOW_RATE)
        gp.mouse_neutral_x += drift_x * follow
        gp.mouse_neutral_y += drift_y * follow

    def _get_mouse_axes(self, gp: GamepadState) -> tuple[float, float]:
        neutral_x = gp.mouse_neutral_x if gp.mouse_neutral_ready else 0.0
        neutral_y = gp.mouse_neutral_y if gp.mouse_neutral_ready else 0.0
        raw_x = self._sanitize_axis(getattr(gp, 'raw_right_x', 0.0)) - neutral_x
        raw_y = self._sanitize_axis(getattr(gp, 'raw_right_y', 0.0)) - neutral_y
        return (
            max(-1.0, min(1.0, raw_x)),
            max(-1.0, min(1.0, raw_y)),
        )

    def _apply_mouse_radial_deadzone(self, raw_x: float, raw_y: float, deadzone: float) -> tuple[float, float]:
        magnitude = math.hypot(raw_x, raw_y)
        if magnitude <= deadzone:
            return (0.0, 0.0)

        scaled_mag = (magnitude - deadzone) / max(1e-6, 1.0 - deadzone)
        scaled_mag = max(0.0, min(1.0, scaled_mag))
        scale = scaled_mag / magnitude
        return (raw_x * scale, raw_y * scale)

    def _make_key_event(self, key: int, event_type: int) -> pygame.event.Event:
        """Sentetik KEYDOWN veya KEYUP eventi oluştur"""
        return pygame.event.Event(
            event_type,
            key=key,
            mod=0,
            unicode='',
            scancode=0,
            from_gamepad=True,
        )

    # ─── Buton Olayları ─────────────────────────────────────────────────────

    def _generate_button_events(self, gp: GamepadState) -> List[pygame.event.Event]:
        """Buton basılma/bırakılma olaylarını üret.
        Bağlama göre (game/menu) B butonu farklı davranır.
        Ayarlardan okunan buton eşlemelerini kullanır."""
        events = []
        in_game = (self._context == self.CONTEXT_GAME)
        cfg_bindings = self._bindings

        # Ayarlardan okunan buton eşlemelerini dinamik olarak oluştur
        if in_game:
            # Oyun içi: buton → aksiyon eşlemesi
            game_actions_list = [
                'move_left', 'move_right', 'soft_drop',
                'hard_drop', 'rotate', 'rotate_alt', 'hold', 'hold2',
                'pause', 'discard_held',
                'lt', 'rt',
                'card_rewind', 'card_sniper', 'card_time_capsule_save',
                'card_time_capsule_restore', 'card_freeze', 'card_phase_shift',
                'card_ghost', 'card_hammer', 'card_bomb',
            ]
            button_actions = {}
            for action in game_actions_list:
                binding = cfg_bindings.get(action, {})
                for btn in self._iter_button_indices(binding):
                    button_actions[btn] = action
        else:
            # Menü: buton → aksiyon eşlemesi
            menu_actions_list = [
                'menu_confirm', 'menu_back', 'pause',
                'menu_tab_next', 'menu_tab_prev',
                'editor_secondary', 'editor_delete',
            ]
            button_actions = {}
            for action in menu_actions_list:
                binding = cfg_bindings.get(action, {})
                for btn in self._iter_button_indices(binding):
                    button_actions[btn] = action

        dpad_btn_to_dir = {11: 'up', 12: 'down', 13: 'left', 14: 'right'}
        dir_to_action = {
            'up': 'rotate',
            'down': 'soft_drop',
            'left': 'move_left',
            'right': 'move_right'
        }

        for btn_idx, action in button_actions.items():
            if action is None:
                continue

            # Eğer basılan buton bir D-pad yönü ise ve o yönün kendi doğal eylemi ise,
            # bunun event'ini buton eventi olarak üretme. Çünkü bu yön için event
            # zaten _generate_dpad_events fonksiyonunda üretilecek (çift tetiklemeyi önleme).
            if btn_idx in dpad_btn_to_dir:
                btn_dir = dpad_btn_to_dir[btn_idx]
                if dir_to_action.get(btn_dir) == action:
                    continue

            # Menü pointer modunda menu_confirm → K_RETURN üretme;
            # A butonu _generate_mouse_click_events'te tıklama olarak işlenir.
            if not in_game and action == 'menu_confirm' and self._menu_pointer_active:
                continue

            pressed_now = gp.buttons.get(btn_idx, False)
            pressed_prev = gp.prev_buttons.get(btn_idx, False)

            key = ACTION_TO_KEY.get(action)
            if key is None:
                continue

            if pressed_now and not pressed_prev:
                events.append(self._make_key_event(key, pygame.KEYDOWN))
            elif not pressed_now and pressed_prev:
                events.append(self._make_key_event(key, pygame.KEYUP))

        return events

    def _generate_trigger_events(self, gp: GamepadState) -> List[pygame.event.Event]:
        """LT/RT trigger olaylarını üret.
        Trigger'lar analog eksendedir; eşik geçildiğinde buton gibi davranır.
        Tüm aksiyonları tarar: herhangi bir aksiyon trigger'a bağlıysa event üretir.
        Menüde trigger kullanılmaz."""
        events = []

        lt_pressed = gp.left_trigger >= self.TRIGGER_THRESHOLD
        rt_pressed = gp.right_trigger >= self.TRIGGER_THRESHOLD

        # Trigger eventleri sadece oyun bağlamında üret
        if self._context == self.CONTEXT_GAME:
            # Tüm aksiyonları tara, trigger binding olanları bul
            for action, binding in self._bindings.items():
                trigger_dirs = self._iter_trigger_dirs(binding)
                if not trigger_dirs:
                    continue
                key = ACTION_TO_KEY.get(action)
                if key is None:
                    continue
                down = False
                up = False
                for trigger_dir in trigger_dirs:
                    if trigger_dir == 'left':
                        if lt_pressed and not gp.prev_left_trigger_pressed:
                            down = True
                        elif not lt_pressed and gp.prev_left_trigger_pressed:
                            up = True
                    elif trigger_dir == 'right':
                        if rt_pressed and not gp.prev_right_trigger_pressed:
                            down = True
                        elif not rt_pressed and gp.prev_right_trigger_pressed:
                            up = True
                if down:
                    events.append(self._make_key_event(key, pygame.KEYDOWN))
                elif up:
                    events.append(self._make_key_event(key, pygame.KEYUP))

        # NOT: prev_left/right_trigger_pressed ARTIK update() basinda (yeni
        # trigger degerleri okunmadan once) kaydediliyor. Burada tekrar
        # guncellemiyoruz; aksi halde poll sirasinda now==prev olur ve
        # was_action_just_pressed trigger slotlari (slot_5/slot_6) icin hic
        # edge algilamaz.

        return events

    def _generate_mouse_events(self, gp: GamepadState, delta_ms: float) -> List[pygame.event.Event]:
        """Sağ stick ile fare imleci hareketi üret.

        Sol stick deadzone'u (0.35) fare için çok yüksek olduğundan
        ham joystick değerlerini okuyup kendi düşük deadzone'ümüzü uyguluyoruz.
        Kuadratik ivme eğrisi: stick az ıtıldığında hassas, tam yana
        yatırıldığında hızlı hareket.
        """
        events: List[pygame.event.Event] = []
        try:
            surface = pygame.display.get_surface()
            if not surface:
                self._reset_mouse_emulation(gp)
                return events

            js = gp.joystick
            if not js or not js.get_init():
                self._reset_mouse_emulation(gp)
                return events

            if getattr(gp, 'controller', None) is None and js.get_numaxes() < 4:
                self._reset_mouse_emulation(gp)
                return events

            raw_rx, raw_ry = self._get_mouse_axes(gp)
            magnitude = math.hypot(raw_rx, raw_ry)
            activation_threshold = max(float(self.MOUSE_ACTIVATE_THRESHOLD), float(self.MOUSE_DEADZONE))
            release_threshold = max(float(self.MOUSE_RELEASE_THRESHOLD), float(self.MOUSE_DEADZONE))

            if not gp.mouse_control_active:
                if magnitude < activation_threshold:
                    gp.mouse_accum_x = 0.0
                    gp.mouse_accum_y = 0.0
                    return events
                gp.mouse_control_active = True
            elif magnitude <= release_threshold:
                self._reset_mouse_emulation(gp)
                return events

            rx, ry = self._apply_mouse_radial_deadzone(raw_rx, raw_ry, release_threshold)
            if rx == 0.0 and ry == 0.0:
                return events

            # Kuadratik ivme eğrisi: küçük stick = hassas, büyük stick = hızlı
            exp = self.MOUSE_ACCEL_EXPONENT
            ax = (abs(rx) ** exp) * (1.0 if rx >= 0 else -1.0)
            ay = (abs(ry) ** exp) * (1.0 if ry >= 0 else -1.0)

            # Frame-rate bağımsız hız (16ms = 60fps referans)
            scale = max(0.1, float(delta_ms) / 16.0)
            speed = self.MOUSE_SPEED * self.MOUSE_SENSITIVITY

            fdx = ax * speed * scale
            fdy = ay * speed * scale

            # Biriken alt-piksel hareketini takip et
            gp.mouse_accum_x += fdx
            gp.mouse_accum_y += fdy

            dx = int(gp.mouse_accum_x)
            dy = int(gp.mouse_accum_y)

            if dx == 0 and dy == 0:
                return events

            # Harcanan tam pikselleri düş
            gp.mouse_accum_x -= dx
            gp.mouse_accum_y -= dy

            # Mouse API'leri logical (window) space'te çalışır
            if hasattr(pygame.display, 'get_window_size'):
                width, height = pygame.display.get_window_size()
            else:
                width, height = surface.get_size()
            cur_x, cur_y = pygame.mouse.get_pos()
            new_x = max(0, min(width - 1, cur_x + dx))
            new_y = max(0, min(height - 1, cur_y + dy))

            pygame.mouse.set_pos(new_x, new_y)
            events.append(
                pygame.event.Event(
                    pygame.MOUSEMOTION,
                    pos=_gmp(),
                    rel=(dx, dy),
                    buttons=(0, 0, 0),
                )
            )
            # Sağ stick fare hareketi → pointer modunu aktifle
            # Yalnızca belirgin stick itişinde aktifle; küçük drift/artık
            # hareket D-pad/sol stick navigasyonunu geçersiz kılmasın.
            if self._context == self.CONTEXT_MENU:
                if magnitude >= activation_threshold:
                    if not getattr(self, '_suppress_pointer_mode', False):
                        self._menu_pointer_active = True
        except Exception:
            self._reset_mouse_emulation(gp)
        return events

    def _generate_mouse_click_events(self, gp: GamepadState) -> List[pygame.event.Event]:
        """A butonu ve R3 ile sol tık üretimi.

        Menüde:
          - R3 (sağ stick bas) = her zaman sol tık.
          - Pointer modu aktifken A butonu = sol tık (imlecin altına tıkla).
        Oyun içinde:
          - A butonu popup/overlay aktifken sol tık.
        """
        events: List[pygame.event.Event] = []

        # --- A butonu → sol tık (oyun içi popup/overlay ve genel tıklama) ---
        if self._context == self.CONTEXT_GAME:
            try:
                confirm_binding = self._bindings.get('menu_confirm', {})
                for a_btn in self._iter_button_indices(confirm_binding):
                    a_now = gp.buttons.get(a_btn, False)
                    a_prev = gp.prev_buttons.get(a_btn, False)
                    if a_now and not a_prev:
                        events.append(
                            pygame.event.Event(
                                pygame.MOUSEBUTTONDOWN,
                                button=1,
                                pos=_gmp(),
                                from_gamepad=True,
                                gamepad_context=self._context,
                            )
                        )
                    elif not a_now and a_prev:
                        events.append(
                            pygame.event.Event(
                                pygame.MOUSEBUTTONUP,
                                button=1,
                                pos=_gmp(),
                                from_gamepad=True,
                                gamepad_context=self._context,
                            )
                        )
            except Exception:
                pass
            return events

        # --- Menü bağlamı ---

        # Pointer modu aktifken A butonu → sol tık (imlecin altını tıklar)
        if self._menu_pointer_active:
            try:
                confirm_binding = self._bindings.get('menu_confirm', {})
                for a_btn in self._iter_button_indices(confirm_binding):
                    a_now = gp.buttons.get(a_btn, False)
                    a_prev = gp.prev_buttons.get(a_btn, False)
                    if a_now and not a_prev:
                        events.append(
                            pygame.event.Event(
                                pygame.MOUSEBUTTONDOWN,
                                button=1,
                                pos=_gmp(),
                                from_gamepad=True,
                                gamepad_context=self._context,
                            )
                        )
                    elif not a_now and a_prev:
                        events.append(
                            pygame.event.Event(
                                pygame.MOUSEBUTTONUP,
                                button=1,
                                pos=_gmp(),
                                from_gamepad=True,
                                gamepad_context=self._context,
                            )
                        )
            except Exception:
                pass

        # R3 = her zaman sol tık (sağ stick basma)
        try:
            btn_idx = 8
            pressed_now = gp.buttons.get(btn_idx, False)
            pressed_prev = gp.prev_buttons.get(btn_idx, False)
            if pressed_now and not pressed_prev:
                events.append(
                    pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN,
                        button=1,
                        pos=_gmp(),
                        from_gamepad=True,
                        gamepad_context=self._context,
                    )
                )
            elif not pressed_now and pressed_prev:
                events.append(
                    pygame.event.Event(
                        pygame.MOUSEBUTTONUP,
                        button=1,
                        pos=_gmp(),
                        from_gamepad=True,
                        gamepad_context=self._context,
                    )
                )
        except Exception:
            pass
        return events

    # ─── D-Pad Olayları ─────────────────────────────────────────────────────

    def _get_overridden_dpad_dirs(self) -> set:
        """D-Pad butonları (11-14) başka bir eyleme atanmışsa veya
        ilgili hareket eylemine başka bir buton atanmışsa o yönün ok-tuşu eventini bastır."""
        overridden = set()
        dpad_btn_to_dir = {11: 'up', 12: 'down', 13: 'left', 14: 'right'}
        
        # Her bir yönün karşılık geldiği oyun içi hareket/döndürme eylemi
        dir_to_action = {
            'up': 'rotate',
            'down': 'soft_drop',
            'left': 'move_left',
            'right': 'move_right'
        }

        # 1) Eğer bir D-pad yön butonu (11-14), kendi eylemi dışındaki herhangi bir eyleme atanmışsa bastır.
        for action, binding in self._bindings.items():
            for btn in self._iter_button_indices(binding):
                if btn in dpad_btn_to_dir:
                    btn_dir = dpad_btn_to_dir[btn]
                    # Eğer buton bu yönün kendi doğal eylemine atanmadıysa override et
                    if dir_to_action.get(btn_dir) != action:
                        overridden.add(btn_dir)

        # 2) Eğer bir hareket eylemine (move_left, move_right, soft_drop, rotate) başka bir tuş atanmışsa,
        # o eylemin doğal D-pad yönünün yerleşik emülasyonunu bastır.
        for btn_dir, action in dir_to_action.items():
            btn_code = 11 if btn_dir == 'up' else 12 if btn_dir == 'down' else 13 if btn_dir == 'left' else 14
            binding = self._bindings.get(action, {})
            buttons = self._iter_button_indices(binding)
            # Eğer eyleme en az bir buton atanmışsa ve bunlardan hiçbiri bu yönün kendi D-pad butonu değilse
            if buttons and not any(btn == btn_code for btn in buttons):
                overridden.add(btn_dir)

        return overridden

    def _generate_repeat_pulses(
        self,
        direction: int,
        delta_ms: float,
        repeat_timer: float,
        initial_delay_done: bool,
        negative_key: int,
        positive_key: int,
    ) -> Tuple[List[pygame.event.Event], float, bool]:
        """Basılı tutulan yön için klavye benzeri tekrar pulse'ları üret."""
        if direction == 0:
            return [], 0.0, False

        repeat_timer += delta_ms
        events: List[pygame.event.Event] = []
        key = negative_key if direction == -1 else positive_key

        if not initial_delay_done:
            if repeat_timer >= self.STICK_INITIAL_DELAY:
                initial_delay_done = True
                repeat_timer = 0.0
                events.append(self._make_key_event(key, pygame.KEYDOWN))
                events.append(self._make_key_event(key, pygame.KEYUP))
        else:
            while repeat_timer >= self.STICK_REPEAT_INTERVAL:
                repeat_timer -= self.STICK_REPEAT_INTERVAL
                events.append(self._make_key_event(key, pygame.KEYDOWN))
                events.append(self._make_key_event(key, pygame.KEYUP))

        return events, repeat_timer, initial_delay_done

    def _generate_dpad_events(self, gp: GamepadState, delta_ms: float) -> List[pygame.event.Event]:
        """D-pad yönlendirme olaylarını üret.
        D-Pad butonları (11-14) bir kart aksiyonuna atandıysa
        o yön için ok-tuşu üretilmez (çakışma engellenir)."""
        events = []
        dx, dy = gp.dpad
        pdx, pdy = gp.prev_dpad

        # Oyun içinde kart aksiyonlarına atanmış D-Pad yönlerini bul
        suppressed = self._get_overridden_dpad_dirs() if self._context == self.CONTEXT_GAME else set()

        # D-pad X ekseni (sol/sağ)
        if dx != pdx:
            # Önceki yönün KEYUP'ını gönder
            if pdx == -1 and 'left' not in suppressed:
                events.append(self._make_key_event(pygame.K_LEFT, pygame.KEYUP))
            elif pdx == 1 and 'right' not in suppressed:
                events.append(self._make_key_event(pygame.K_RIGHT, pygame.KEYUP))

            # Yeni yönün KEYDOWN'ını gönder
            if dx == -1 and 'left' not in suppressed:
                events.append(self._make_key_event(pygame.K_LEFT, pygame.KEYDOWN))
            elif dx == 1 and 'right' not in suppressed:
                events.append(self._make_key_event(pygame.K_RIGHT, pygame.KEYDOWN))
            gp.dpad_repeat_x = 0.0
            gp.dpad_initial_delay_x = False
        elif dx != 0 and self._context == self.CONTEXT_MENU:
            repeat_events, gp.dpad_repeat_x, gp.dpad_initial_delay_x = self._generate_repeat_pulses(
                dx,
                delta_ms,
                gp.dpad_repeat_x,
                gp.dpad_initial_delay_x,
                pygame.K_LEFT,
                pygame.K_RIGHT,
            )
            if dx == -1 and 'left' in suppressed:
                repeat_events = []
            elif dx == 1 and 'right' in suppressed:
                repeat_events = []
            events.extend(repeat_events)
        else:
            gp.dpad_repeat_x = 0.0
            gp.dpad_initial_delay_x = False

        # D-pad Y ekseni (yukarı/aşağı)
        # Not: SDL hat'ında Y ekseni ters: yukarı = +1, aşağı = -1
        if dy != pdy:
            if pdy == -1 and 'down' not in suppressed:  # aşağı bırakıldı
                events.append(self._make_key_event(pygame.K_DOWN, pygame.KEYUP))
            elif pdy == 1 and 'up' not in suppressed:  # yukarı bırakıldı
                events.append(self._make_key_event(pygame.K_UP, pygame.KEYUP))

            if dy == -1 and 'down' not in suppressed:  # aşağı basıldı
                events.append(self._make_key_event(pygame.K_DOWN, pygame.KEYDOWN))
            elif dy == 1 and 'up' not in suppressed:  # yukarı basıldı
                events.append(self._make_key_event(pygame.K_UP, pygame.KEYDOWN))
            gp.dpad_repeat_y = 0.0
            gp.dpad_initial_delay_y = False
        elif dy != 0 and self._context == self.CONTEXT_MENU:
            repeat_events, gp.dpad_repeat_y, gp.dpad_initial_delay_y = self._generate_repeat_pulses(
                -dy,
                delta_ms,
                gp.dpad_repeat_y,
                gp.dpad_initial_delay_y,
                pygame.K_UP,
                pygame.K_DOWN,
            )
            if dy == -1 and 'down' in suppressed:
                repeat_events = []
            elif dy == 1 and 'up' in suppressed:
                repeat_events = []
            events.extend(repeat_events)
        else:
            gp.dpad_repeat_y = 0.0
            gp.dpad_initial_delay_y = False

        # D-pad navigasyonu yapıldıysa pointer modundan çık
        if events and self._context == self.CONTEXT_MENU:
            self._menu_pointer_active = False
        return events

    # ─── Analog Stick Olayları ──────────────────────────────────────────────

    def _generate_stick_events(self, gp: GamepadState, delta_ms: float) -> List[pygame.event.Event]:
        """Analog stick'i dijital yöne çevirip DAS benzeri tekrar ile olay üret.

        Oyun içinde sol stick devre dışıdır — blok hareketi yalnızca D-pad ile.
        Menü/UI ekranlarında sol stick navigasyon için kullanılır.
        """
        # Oyun bağlamında sol stick ile blok hareket etmesin
        if self._context == self.CONTEXT_GAME:
            return []

        events = []
        stick = gp.left_stick

        # ── X Ekseni ──
        if stick.digital_x != stick.prev_digital_x:
            # Yön değişti - öncekinin KEYUP'ı
            if stick.prev_digital_x == -1:
                events.append(self._make_key_event(pygame.K_LEFT, pygame.KEYUP))
            elif stick.prev_digital_x == 1:
                events.append(self._make_key_event(pygame.K_RIGHT, pygame.KEYUP))

            # Yeni yönün KEYDOWN'ı
            if stick.digital_x == -1:
                events.append(self._make_key_event(pygame.K_LEFT, pygame.KEYDOWN))
                gp.stick_repeat_x = 0
                gp.stick_initial_delay_x = False
            elif stick.digital_x == 1:
                events.append(self._make_key_event(pygame.K_RIGHT, pygame.KEYDOWN))
                gp.stick_repeat_x = 0
                gp.stick_initial_delay_x = False
        elif stick.digital_x != 0:
            # Aynı yönde tutulmaya devam ediliyor → DAS tekrar
            gp.stick_repeat_x += delta_ms
            if not gp.stick_initial_delay_x:
                if gp.stick_repeat_x >= self.STICK_INITIAL_DELAY:
                    gp.stick_initial_delay_x = True
                    gp.stick_repeat_x = 0
                    key = pygame.K_LEFT if stick.digital_x == -1 else pygame.K_RIGHT
                    events.append(self._make_key_event(key, pygame.KEYDOWN))
                    events.append(self._make_key_event(key, pygame.KEYUP))
            else:
                if gp.stick_repeat_x >= self.STICK_REPEAT_INTERVAL:
                    gp.stick_repeat_x -= self.STICK_REPEAT_INTERVAL
                    key = pygame.K_LEFT if stick.digital_x == -1 else pygame.K_RIGHT
                    events.append(self._make_key_event(key, pygame.KEYDOWN))
                    events.append(self._make_key_event(key, pygame.KEYUP))

        # ── Y Ekseni ──
        if stick.digital_y != stick.prev_digital_y:
            if stick.prev_digital_y == -1:
                events.append(self._make_key_event(pygame.K_UP, pygame.KEYUP))
            elif stick.prev_digital_y == 1:
                events.append(self._make_key_event(pygame.K_DOWN, pygame.KEYUP))

            if stick.digital_y == -1:
                events.append(self._make_key_event(pygame.K_UP, pygame.KEYDOWN))
                gp.stick_repeat_y = 0
                gp.stick_initial_delay_y = False
            elif stick.digital_y == 1:
                # Aşağı yön → soft drop: hemen KEYDOWN gönder (tekrar gerekmez,
                # game.py sürekli is_direction_held('down') kontrol eder)
                events.append(self._make_key_event(pygame.K_DOWN, pygame.KEYDOWN))
                gp.stick_repeat_y = 0
                gp.stick_initial_delay_y = False
        elif stick.digital_y != 0:
            repeat_events, gp.stick_repeat_y, gp.stick_initial_delay_y = self._generate_repeat_pulses(
                stick.digital_y,
                delta_ms,
                gp.stick_repeat_y,
                gp.stick_initial_delay_y,
                pygame.K_UP,
                pygame.K_DOWN,
            )
            events.extend(repeat_events)

        # Sol stick navigasyonu yapıldıysa pointer modundan çık
        if events and self._context == self.CONTEXT_MENU:
            self._menu_pointer_active = False
        return events

    # ─── Titreşim (Rumble) ──────────────────────────────────────────────────

    def rumble(self, low_frequency: float = 0.5, high_frequency: float = 0.5,
               duration_ms: int = 200):
        """Aktif gamepad'i titret (destekleniyorsa).

        Args:
            low_frequency: Düşük frekans motor gücü (0.0 – 1.0)
            high_frequency: Yüksek frekans motor gücü (0.0 – 1.0)
            duration_ms: Titreşim süresi (ms)
        """
        if not getattr(self, 'rumble_enabled', True):
            return
        multiplier = float(getattr(self, 'rumble_multiplier', 1.0) or 0.0)
        if multiplier <= 0.0:
            return
        gp = self.get_active_gamepad()
        if not gp or not gp.joystick:
            return
        try:
            scaled_low = max(0.0, min(1.0, float(low_frequency) * multiplier))
        except Exception:
            scaled_low = 0.0
        try:
            scaled_high = max(0.0, min(1.0, float(high_frequency) * multiplier))
        except Exception:
            scaled_high = 0.0
        try:
            scaled_duration = max(0, int(duration_ms))
        except Exception:
            scaled_duration = 0
        if scaled_low <= 0.0 and scaled_high <= 0.0:
            return
        try:
            controller = getattr(gp, 'controller', None)
            if controller is not None:
                controller.rumble(scaled_low, scaled_high, scaled_duration)
            else:
                gp.joystick.rumble(scaled_low, scaled_high, scaled_duration)
        except Exception:
            pass  # Tüm kontrolcüler rumble desteklemez

    def stop_rumble(self):
        """Titreşimi durdur"""
        gp = self.get_active_gamepad()
        if not gp or not gp.joystick:
            return
        try:
            controller = getattr(gp, 'controller', None)
            if controller is not None and hasattr(controller, 'stop_rumble'):
                controller.stop_rumble()
            else:
                gp.joystick.stop_rumble()
        except Exception:
            pass

    # ─── Temizlik ───────────────────────────────────────────────────────────

    def cleanup(self):
        """Tüm gamepad'leri temizle"""
        for gp in self.gamepads.values():
            try:
                if getattr(gp, 'controller', None):
                    gp.controller.quit()
            except Exception:
                pass
            try:
                if gp.joystick:
                    gp.joystick.quit()
            except Exception:
                pass
        self.gamepads.clear()


# ─── Global Singleton ──────────────────────────────────────────────────────
# Tek bir instance üzerinden kullanılır (menü ve oyun arasında paylaşılır)

_instance: Optional[GamepadManager] = None


def get_gamepad_manager() -> GamepadManager:
    """Global GamepadManager instance'ını döndür (lazy init)"""
    global _instance
    if _instance is None:
        _instance = GamepadManager()
    return _instance


def is_gamepad_connected() -> bool:
    """Herhangi bir gamepad bağlı mı? (hızlı kontrol)"""
    global _instance
    if _instance is None:
        return False
    return _instance.is_connected()


def handle_gamepad_hotplug_event(event) -> str | None:
    """Modül-level adapter. Oyun döngüleri global GamepadManager singleton'ına
    `JOYDEVICEADDED` / `JOYDEVICEREMOVED` event'lerini bu yardımcı üzerinden
    iletir. Geri dönüş GamepadManager.handle_hotplug_event ile aynıdır:
    'connected', 'disconnected' veya None.
    """
    global _instance
    if _instance is None:
        return None
    try:
        return _instance.handle_hotplug_event(event)
    except Exception:
        return None


def is_gamepad_disconnect_event(event) -> bool:
    """`JOYDEVICEREMOVED` event'i mi? (auto-pause kararları için)."""
    event_type = getattr(event, 'type', None)
    if event_type is None:
        return False
    removed_type = getattr(pygame, 'JOYDEVICEREMOVED', None)
    return removed_type is not None and event_type == removed_type


def pump_gamepad_into_event_queue(delta_ms: float = 16.0, context: Optional[str] = 'menu') -> int:
    """Blocking popup/modal döngüleri için gamepad girişini canlı tutar.

    Ana oyun döngüsü her frame `GamepadManager.update()` çağırıp sentetik
    klavye/fare olaylarını kuyruğa post eder. Ancak `_show_mode_intro_popup`,
    renk seçici gibi kendi `while` + `pygame.event.get()` döngüsüne sahip
    bloklayıcı ekranlar bu pump'ı atlar ve gamepad ölü kalır. Bu yardımcı,
    o döngülerin başında çağrılarak:
      1. (opsiyonel) bağlamı ayarlar (popup'lar için 'menu'),
      2. gamepad durumunu okur,
      3. üretilen sentetik olayları pygame kuyruğuna post eder.

    Returns:
        Kuyruğa eklenen sentetik olay sayısı (test/teşhis için).
    """
    manager = None
    try:
        manager = get_gamepad_manager()
    except Exception:
        manager = _instance
    if manager is None:
        return 0
    try:
        if context is not None:
            manager.set_context(context)
        events = manager.update(delta_ms)
        posted = 0
        for ev in events:
            try:
                pygame.event.post(ev)
                posted += 1
            except Exception:
                pass
        return posted
    except Exception:
        return 0


def reload_gamepad_settings():
    """Ayarlar değiştiğinde gamepad konfigürasyonunu yeniden yükle."""
    global _instance
    if _instance is not None:
        _instance._load_settings()


def normalize_gamepad_event_button(event) -> Optional[int]:
    event_type = getattr(event, 'type', None)
    controller_down = getattr(pygame, 'CONTROLLERBUTTONDOWN', None)
    controller_up = getattr(pygame, 'CONTROLLERBUTTONUP', None)
    if event_type in (controller_down, controller_up):
        raw_button = getattr(event, 'button', None)
        if isinstance(raw_button, (int, float)) and not isinstance(raw_button, bool):
            return int(raw_button)
        return None

    valid_types = (getattr(pygame, 'JOYBUTTONDOWN', None), getattr(pygame, 'JOYBUTTONUP', None))
    if event_type not in valid_types:
        return None

    raw_button = getattr(event, 'button', None)
    if not isinstance(raw_button, (int, float)) or isinstance(raw_button, bool):
        return None

    manager = get_gamepad_manager()
    return manager.resolve_capture_button_index(
        int(raw_button),
        joy_id=getattr(event, 'joy', None),
        instance_id=getattr(event, 'instance_id', None),
    )


def normalize_gamepad_trigger_event(event) -> Optional[int]:
    event_type = getattr(event, 'type', None)
    controller_axis_motion = getattr(pygame, 'CONTROLLERAXISMOTION', None)
    if event_type == controller_axis_motion:
        axis = getattr(event, 'axis', None)
        try:
            axis_index = int(axis)
        except Exception:
            return None
        if axis_index not in (CONTROLLER_AXIS_TRIGGERLEFT, CONTROLLER_AXIS_TRIGGERRIGHT):
            return None
        try:
            trigger_value = float(getattr(event, 'value', 0.0))
        except Exception:
            trigger_value = 0.0
        if trigger_value < 0.0:
            trigger_value = (trigger_value + 1.0) / 2.0
        if trigger_value >= get_gamepad_manager().TRIGGER_THRESHOLD:
            return 100 if axis_index == CONTROLLER_AXIS_TRIGGERLEFT else 101
        return None

    if event_type != getattr(pygame, 'JOYAXISMOTION', None):
        return None

    manager = get_gamepad_manager()
    return manager.resolve_capture_trigger_index(
        getattr(event, 'axis', None),
        getattr(event, 'value', 0.0),
        joy_id=getattr(event, 'joy', None),
        instance_id=getattr(event, 'instance_id', None),
    )



# ─── Re-export: GamepadAction enum (focus_manager'dan) ───────────────────────
# Ekranlar `from gamepad_manager import GamepadAction` ile erişebilsin.
try:
    from focus_manager import GamepadAction, key_to_action  # noqa: F401
except ImportError:
    pass
