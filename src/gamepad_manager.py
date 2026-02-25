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

import pygame
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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
    'move_left':    {'dpad': 'left',   'axis': ('left_x', -1)},
    'move_right':   {'dpad': 'right',  'axis': ('left_x', +1)},
    'soft_drop':    {'dpad': 'down',   'axis': ('left_y', +1)},
    'hard_drop':    {'button': 0},   # A (Xbox) / Cross (PS)
    'rotate':       {'button': None}, # Devre dışı (sol stick yukarı döndürüyor)
    'rotate_alt':   {'button': None}, # Devre dışı
    'hold':         {'button': 9},   # LB / L1
    'hold2':        {'button': 2},   # X (Xbox) / Square (PS)
    'pause':        {'button': 6},   # Start / Options / +
    'main_menu_prompt': {'button': None},  # Ana menü onayi (ESC)
    'lt':           {'trigger': 'left'},  # LT / L2 (analog trigger)
    'rt':           {'trigger': 'right'}, # RT / R2 (analog trigger)
    'restart':      {'button': None}, # Devre dışı
    'discard_held': {'button': 7},   # L3 (Left Stick Click)
    # Kart modu aksiyonlari (varsayilan: atanmis degil)
    'card_rewind': {'button': None},
    'card_sniper': {'button': None},
    'card_time_capsule_save': {'button': None},
    'card_time_capsule_restore': {'button': None},
    'card_phase_shift': {'button': None},
    'card_ghost': {'button': None},
    'card_hammer': {'button': None},
    'card_bomb': {'button': None},

    # Menü navigasyonu
    'menu_up':      {'dpad': 'up',    'axis': ('left_y', -1)},
    'menu_down':    {'dpad': 'down',  'axis': ('left_y', +1)},
    'menu_left':    {'dpad': 'left',  'axis': ('left_x', -1)},
    'menu_right':   {'dpad': 'right', 'axis': ('left_x', +1)},
    'menu_confirm': {'button': 0},   # A / Cross / B(Nintendo)
    'menu_back':    {'button': 1},   # B / Circle / A(Nintendo)
    'menu_tab_next': {'button': 10}, # RB / R1
    'menu_tab_prev': {'button': 9},  # LB / L1
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
    'hard_drop': pygame.K_SPACE,
    'rotate': pygame.K_UP,
    'rotate_alt': pygame.K_UP,
    'hold': pygame.K_c,
    'hold2': pygame.K_v,
    'pause': pygame.K_p,
    'main_menu_prompt': pygame.K_ESCAPE,
    'lt': pygame.K_q,        # LT → varsayılan olarak Q (kullanıcı değiştirebilir)
    'rt': pygame.K_e,        # RT → varsayılan olarak E
    'restart': pygame.K_r,
    'discard_held': pygame.K_b,
    'card_rewind': pygame.K_u,
    'card_sniper': pygame.K_n,
    'card_time_capsule_save': pygame.K_t,
    'card_time_capsule_restore': pygame.K_r,
    'card_phase_shift': pygame.K_LSHIFT,
    'card_ghost': pygame.K_g,
    'card_hammer': pygame.K_h,
    'card_bomb': pygame.K_m,
    'menu_confirm': pygame.K_RETURN,
    'menu_back': pygame.K_ESCAPE,
    'menu_tab_next': pygame.K_RIGHTBRACKET,  # RB → sonraki sekme
    'menu_tab_prev': pygame.K_LEFTBRACKET,  # LB → önceki sekme
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
    gamepad_type: str = GamepadType.UNKNOWN
    name: str = ''
    guid: str = ''
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
    # Stick tekrar (DAS benzeri) sayaçları
    stick_repeat_x: float = 0.0
    stick_repeat_y: float = 0.0
    stick_initial_delay_x: bool = False
    stick_initial_delay_y: bool = False


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

    # Bağlam: 'game' = oyun içi, 'menu' = menü/UI
    # B butonu oyun içinde rotate, menüde back olarak çalışır
    CONTEXT_GAME = 'game'
    CONTEXT_MENU = 'menu'

    def __init__(self):
        """Gamepad sistemini başlat"""
        # pygame.joystick modülünü başlat
        if not pygame.joystick.get_init():
            pygame.joystick.init()

        self.gamepads: Dict[int, GamepadState] = {}
        self.enabled = True

        # Vibration/rumble desteği
        self.rumble_enabled = True

        # Aktif bağlam (oyun içi veya menü)
        self._context = self.CONTEXT_MENU

        # Ayarlardan oku (varsa)
        self._load_settings()

        # İlk tarama
        self._scan_gamepads()

    def _load_settings(self):
        """Settings'den gamepad ayarlarını yükle."""
        try:
            from settings_manager import SettingsManager
            sm = SettingsManager()
            controls = sm.get_controls()
            gp_cfg = controls.get('gamepad', {})
            self.enabled = gp_cfg.get('enabled', True)
            self.rumble_enabled = gp_cfg.get('rumble', True)
            dz = gp_cfg.get('deadzone', 0.35)
            if isinstance(dz, (int, float)):
                self.DEADZONE = max(0.1, min(0.9, float(dz)))
            ms = gp_cfg.get('mouse_sensitivity', 1.0)
            if isinstance(ms, (int, float)):
                self.MOUSE_SENSITIVITY = max(0.1, min(3.0, float(ms)))
            # Eski çakışan ayarları temizle (rotate/restart UI'dan kaldırıldı)
            _deprecated = {'rotate', 'rotate_alt', 'restart'}
            for dep_action in _deprecated:
                if dep_action in DEFAULT_GAMEPAD_BINDINGS:
                    DEFAULT_GAMEPAD_BINDINGS[dep_action] = {'button': None, 'button_secondary': None}

            # Buton eşlemelerini güncelle
            button_actions = [
                'hard_drop', 'hold', 'hold2', 'pause',
                'main_menu_prompt', 'menu_back', 'menu_confirm', 'menu_tab_next', 'menu_tab_prev',
                'discard_held', 'lt', 'rt',
                'card_rewind', 'card_sniper', 'card_time_capsule_save',
                'card_time_capsule_restore', 'card_phase_shift',
                'card_ghost', 'card_hammer', 'card_bomb',
            ]
            for action in button_actions:
                raw = gp_cfg.get(action)
                if action not in DEFAULT_GAMEPAD_BINDINGS:
                    continue

                binding = DEFAULT_GAMEPAD_BINDINGS[action]
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

    def _scan_gamepads(self):
        """Bağlı gamepad'leri tara ve kaydet"""
        count = pygame.joystick.get_count()
        for i in range(count):
            if i not in self.gamepads:
                self._register_gamepad(i)

    def _register_gamepad(self, device_index: int):
        """Yeni bir gamepad'i kaydet"""
        try:
            js = pygame.joystick.Joystick(device_index)
            js.init()

            gp_type = self._detect_type(js)
            name = js.get_name()
            guid = ''
            try:
                guid = js.get_guid()
            except Exception:
                pass

            state = GamepadState(
                joystick=js,
                gamepad_type=gp_type,
                name=name,
                guid=guid,
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

        # Sol stick kontrolü (dijital eşik geçildi mi?)
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
        binding = DEFAULT_GAMEPAD_BINDINGS.get(action)
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
        binding = DEFAULT_GAMEPAD_BINDINGS.get(action)
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

    def get_button_label(self, action: str, gp_type: str = None) -> str:
        """Bir aksiyon için kontrolcüye özgü buton etiketini döndür.

        Örn: get_button_label('hard_drop', 'xbox') → 'A'
             get_button_label('hard_drop', 'playstation') → '✕'
             get_button_label('hard_drop', 'nintendo') → 'B'
        """
        if gp_type is None:
            gp = self.get_active_gamepad()
            gp_type = gp.gamepad_type if gp else GamepadType.UNKNOWN

        binding = DEFAULT_GAMEPAD_BINDINGS.get(action, {})

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

                # Butonları oku
                num_buttons = gp.joystick.get_numbuttons()
                for b in range(num_buttons):
                    gp.buttons[b] = gp.joystick.get_button(b)

                # Analog eksenleri oku
                num_axes = gp.joystick.get_numaxes()
                if num_axes >= 2:
                    raw_x = gp.joystick.get_axis(0)
                    raw_y = gp.joystick.get_axis(1)
                    gp.left_stick.x = self._apply_deadzone(raw_x)
                    gp.left_stick.y = self._apply_deadzone(raw_y)
                if num_axes >= 4:
                    gp.right_stick.x = self._apply_deadzone(gp.joystick.get_axis(2))
                    gp.right_stick.y = self._apply_deadzone(gp.joystick.get_axis(3))
                if num_axes >= 6:
                    gp.left_trigger = max(0.0, (gp.joystick.get_axis(4) + 1.0) / 2.0)
                    gp.right_trigger = max(0.0, (gp.joystick.get_axis(5) + 1.0) / 2.0)

                # D-pad (hat) oku
                num_hats = gp.joystick.get_numhats()
                if num_hats > 0:
                    gp.dpad = gp.joystick.get_hat(0)

                # Dijital yön hesapla (analog stick → dijital)
                gp.left_stick.digital_x = self._to_digital(gp.left_stick.x)
                gp.left_stick.digital_y = self._to_digital(gp.left_stick.y)

                # Olayları üret
                synthetic.extend(self._generate_button_events(gp))
                synthetic.extend(self._generate_trigger_events(gp))
                synthetic.extend(self._generate_dpad_events(gp))
                synthetic.extend(self._generate_stick_events(gp, delta_ms))
                synthetic.extend(self._generate_mouse_events(gp, delta_ms))
                synthetic.extend(self._generate_mouse_click_events(gp))

            except Exception as e:
                # Gamepad kopmuş olabilir
                print(f"⚠️ Gamepad {gp_id} okuma hatası: {e}")

        return synthetic

    def _check_connections(self):
        """Yeni bağlanan/kopan gamepad'leri kontrol et"""
        try:
            current_count = pygame.joystick.get_count()
            known_ids = set(self.gamepads.keys())

            # Yeni bağlananlar
            for i in range(current_count):
                if i not in known_ids:
                    self._register_gamepad(i)

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
        except Exception:
            pass

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
        cfg_bindings = DEFAULT_GAMEPAD_BINDINGS

        # Ayarlardan okunan buton eşlemelerini dinamik olarak oluştur
        if in_game:
            # Oyun içi: buton → aksiyon eşlemesi
            game_actions_list = [
                'hard_drop', 'hold', 'hold2',
                'pause', 'main_menu_prompt', 'discard_held',
                'lt', 'rt',
                'card_rewind', 'card_sniper', 'card_time_capsule_save',
                'card_time_capsule_restore', 'card_phase_shift',
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
            ]
            button_actions = {}
            for action in menu_actions_list:
                binding = cfg_bindings.get(action, {})
                for btn in self._iter_button_indices(binding):
                    button_actions[btn] = action

        for btn_idx, action in button_actions.items():
            if action is None:
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
            for action, binding in DEFAULT_GAMEPAD_BINDINGS.items():
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

        # Prev state'i her zaman güncelle (context ne olursa olsun)
        gp.prev_left_trigger_pressed = lt_pressed
        gp.prev_right_trigger_pressed = rt_pressed

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
                return events

            js = gp.joystick
            if not js or not js.get_init():
                return events

            num_axes = js.get_numaxes()
            if num_axes < 4:
                return events

            # --- Ham değerleri oku (sınıf deadzone'ünü ATLA) ---
            raw_rx = js.get_axis(2)
            raw_ry = js.get_axis(3)

            dz = self.MOUSE_DEADZONE

            # Deadzone filtresi
            if abs(raw_rx) < dz:
                raw_rx = 0.0
            if abs(raw_ry) < dz:
                raw_ry = 0.0

            if raw_rx == 0.0 and raw_ry == 0.0:
                return events

            # Deadzone sonrası normalize (0–1 aralığına)
            def _norm(val: float) -> float:
                sign = 1.0 if val > 0 else -1.0
                n = (abs(val) - dz) / (1.0 - dz)
                return sign * max(0.0, min(1.0, n))

            rx = _norm(raw_rx)
            ry = _norm(raw_ry)

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
            if not hasattr(gp, '_mouse_accum_x'):
                gp._mouse_accum_x = 0.0
                gp._mouse_accum_y = 0.0

            gp._mouse_accum_x += fdx
            gp._mouse_accum_y += fdy

            dx = int(gp._mouse_accum_x)
            dy = int(gp._mouse_accum_y)

            if dx == 0 and dy == 0:
                return events

            # Harcanan tam pikselleri düş
            gp._mouse_accum_x -= dx
            gp._mouse_accum_y -= dy

            width, height = surface.get_size()
            cur_x, cur_y = pygame.mouse.get_pos()
            new_x = max(0, min(width - 1, cur_x + dx))
            new_y = max(0, min(height - 1, cur_y + dy))

            pygame.mouse.set_pos(new_x, new_y)
            events.append(
                pygame.event.Event(
                    pygame.MOUSEMOTION,
                    pos=(new_x, new_y),
                    rel=(dx, dy),
                    buttons=(0, 0, 0),
                )
            )
        except Exception:
            pass
        return events

    def _generate_mouse_click_events(self, gp: GamepadState) -> List[pygame.event.Event]:
        """A butonu ve R3 ile sol tık üretimi.

        Menüde: R3 (sağ stick bas) = sol tık.
        Oyun içinde: A butonu (menu_confirm) popup/overlay aktifken
        sol tık olarak da çalışır (normal gameplay'de çalışmaz).
        """
        events: List[pygame.event.Event] = []

        # --- A butonu → sol tık (oyun içi popup/overlay'lerde) ---
        if self._context == self.CONTEXT_GAME:
            try:
                confirm_binding = DEFAULT_GAMEPAD_BINDINGS.get('menu_confirm', {})
                a_btn = confirm_binding.get('button', 0)
                if a_btn is not None:
                    a_now = gp.buttons.get(a_btn, False)
                    a_prev = gp.prev_buttons.get(a_btn, False)
                    if a_now and not a_prev:
                        events.append(
                            pygame.event.Event(
                                pygame.MOUSEBUTTONDOWN,
                                button=1,
                                pos=pygame.mouse.get_pos(),
                            )
                        )
                    elif not a_now and a_prev:
                        events.append(
                            pygame.event.Event(
                                pygame.MOUSEBUTTONUP,
                                button=1,
                                pos=pygame.mouse.get_pos(),
                            )
                        )
            except Exception:
                pass
            return events

        # --- Menü bağlamı: R3 = sol tık ---
        try:
            # R3 = buton 8 (Right Stick Click)
            btn_idx = 8
            pressed_now = gp.buttons.get(btn_idx, False)
            pressed_prev = gp.prev_buttons.get(btn_idx, False)
            if pressed_now and not pressed_prev:
                events.append(
                    pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN,
                        button=1,
                        pos=pygame.mouse.get_pos(),
                    )
                )
            elif not pressed_now and pressed_prev:
                events.append(
                    pygame.event.Event(
                        pygame.MOUSEBUTTONUP,
                        button=1,
                        pos=pygame.mouse.get_pos(),
                    )
                )
        except Exception:
            pass
        return events

    # ─── D-Pad Olayları ─────────────────────────────────────────────────────

    def _get_overridden_dpad_dirs(self) -> set:
        """D-Pad butonları (11-14) bir kart/aksiyon aksiyonuna atanmışsa
        o yönün ok-tuşu eventini bastırmak için yön setini döndür."""
        overridden = set()
        dpad_btn_to_dir = {11: 'up', 12: 'down', 13: 'left', 14: 'right'}
        # Hareket dışı aksiyonlar (D-Pad yönünü override eden)
        movement_actions = {'move_left', 'move_right', 'soft_drop',
                           'menu_up', 'menu_down', 'menu_left', 'menu_right'}
        for action, binding in DEFAULT_GAMEPAD_BINDINGS.items():
            if action in movement_actions:
                continue
            btn = binding.get('button')
            if btn in dpad_btn_to_dir:
                overridden.add(dpad_btn_to_dir[btn])
        return overridden

    def _generate_dpad_events(self, gp: GamepadState) -> List[pygame.event.Event]:
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

        return events

    # ─── Analog Stick Olayları ──────────────────────────────────────────────

    def _generate_stick_events(self, gp: GamepadState, delta_ms: float) -> List[pygame.event.Event]:
        """Analog stick'i dijital yöne çevirip DAS benzeri tekrar ile olay üret"""
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
            # Aşağı yön tutulduğunda tekrar göndermeye gerek yok
            # (soft drop game.py'de is_direction_held ile sürekli kontrol ediliyor)
            # Sadece yukarı yön için DAS tekrar gerekebilir
            if stick.digital_y == -1:
                gp.stick_repeat_y += delta_ms
                if not gp.stick_initial_delay_y:
                    if gp.stick_repeat_y >= self.STICK_INITIAL_DELAY:
                        gp.stick_initial_delay_y = True
                        gp.stick_repeat_y = 0
                        events.append(self._make_key_event(pygame.K_UP, pygame.KEYDOWN))
                        events.append(self._make_key_event(pygame.K_UP, pygame.KEYUP))
                else:
                    if gp.stick_repeat_y >= self.STICK_REPEAT_INTERVAL:
                        gp.stick_repeat_y -= self.STICK_REPEAT_INTERVAL
                        events.append(self._make_key_event(pygame.K_UP, pygame.KEYDOWN))
                        events.append(self._make_key_event(pygame.K_UP, pygame.KEYUP))

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
        if not self.rumble_enabled:
            return
        gp = self.get_active_gamepad()
        if not gp or not gp.joystick:
            return
        try:
            gp.joystick.rumble(low_frequency, high_frequency, duration_ms)
        except Exception:
            pass  # Tüm kontrolcüler rumble desteklemez

    def stop_rumble(self):
        """Titreşimi durdur"""
        gp = self.get_active_gamepad()
        if not gp or not gp.joystick:
            return
        try:
            gp.joystick.stop_rumble()
        except Exception:
            pass

    # ─── Temizlik ───────────────────────────────────────────────────────────

    def cleanup(self):
        """Tüm gamepad'leri temizle"""
        for gp in self.gamepads.values():
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


def reload_gamepad_settings():
    """Ayarlar değiştiğinde gamepad konfigürasyonunu yeniden yükle."""
    global _instance
    if _instance is not None:
        _instance._load_settings()
