"""PlayStation / Gamepad D-pad Debouncing Birim Testleri.

Bu testler gamepad D-pad yön tuşlarının dalgalanmalarını (chatter) engelleyen
debouncing mekanizmasını doğrular.
"""
import os
import sys
import pathlib
import pygame

ROOT_DIR = pathlib.Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gamepad_manager import GamepadManager, GamepadState  # noqa: E402


class MockJoystick:
    def get_init(self) -> bool:
        return True
        
    def get_name(self) -> str:
        return "Mock PlayStation Controller"
        
    def get_numaxes(self) -> int:
        return 6
        
    def get_axis(self, idx: int) -> float:
        return 0.0
        
    def get_numhats(self) -> int:
        return 1
        
    def get_hat(self, idx: int) -> tuple[int, int]:
        return (0, 0)


def test_gamepad_dpad_debouncing():
    # Pygame'i ve video sistemini sessizce init et (test ortamında pencere açılmasın)
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    pygame.init()
    pygame.joystick.init()
    
    gpm = GamepadManager()
    # Otomatik algılama taramasını devreden çıkarıyoruz ki mock state'imiz uçmasın
    gpm._check_connections = lambda: None
    
    mock_joy = MockJoystick()
    gp = GamepadState(
        joystick=mock_joy,
        controller=None,
        device_index=0,
        instance_id=1
    )
    gp.dpad_debounce_time_ms = 60.0
    gpm.gamepads[0] = gp
    
    # Bir sonraki frame donanımdan okunacak D-pad değerini simüle eden değişken
    next_dpad = (0, 0)
    
    # Mock okuma metotları
    gpm._read_dpad_state = lambda g: next_dpad
    gpm._read_button_states = lambda g: {}
    gpm.enabled = True
    
    # 1. Başlangıç: Basış yok
    next_dpad = (0, 0)
    events = gpm.update(16.0)
    assert len(events) == 0
    assert gp.dpad_debounced_dx == 0
    
    # 2. Sola basış: Anında KEYDOWN üretilmeli
    next_dpad = (-1, 0)
    events = gpm.update(16.0)
    assert len(events) == 1
    assert events[0].type == pygame.KEYDOWN
    assert events[0].key == pygame.K_LEFT
    assert gp.dpad_debounced_dx == -1
    
    # 3. Yönü bırakış (gürültü): Debounce süresi (60ms) dolana kadar debounced_dx -1 kalmalı
    next_dpad = (0, 0)
    events = gpm.update(10.0)  # 10ms geçti
    assert len(events) == 0
    assert gp.dpad_debounced_dx == -1
    assert gp.dpad_is_debouncing_x is True
    
    # 4. Debounce bitmeden sola tekrar basış (chatter): Debounce iptal edilmeli, hiç KEYUP/KEYDOWN üretilmemeli
    next_dpad = (-1, 0)
    events = gpm.update(10.0)  # 10ms daha geçti (toplam 20ms)
    assert len(events) == 0
    assert gp.dpad_debounced_dx == -1
    assert gp.dpad_is_debouncing_x is False
    
    # 5. Tekrar bırakış: Debounce süreci yeniden başlamalı
    next_dpad = (0, 0)
    events = gpm.update(10.0)  # 10ms geçti
    assert len(events) == 0
    assert gp.dpad_debounced_dx == -1
    assert gp.dpad_is_debouncing_x is True
    
    # 6. Debounce süresinin dolması: 65ms daha bekleyelim (toplam 10+65=75ms > 60ms)
    events = gpm.update(65.0)
    assert len(events) == 1
    assert events[0].type == pygame.KEYUP
    assert events[0].key == pygame.K_LEFT
    assert gp.dpad_debounced_dx == 0
    assert gp.dpad_is_debouncing_x is False
