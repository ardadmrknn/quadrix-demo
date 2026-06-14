"""Ortak Focus/Navigation Yöneticisi — Gamepad Full-Support Faz 2.

Tüm ekranlar için yeniden kullanılabilir focus ring + directional navigation
+ confirm/back action contract sağlar. Mevcut sentetik klavye pipeline'ını
bozmaz; üstüne native focus modeli ekler.

Kullanım:
    fm = FocusManager()
    fm.register([
        FocusTarget(rect=pygame.Rect(100, 50, 200, 40), id='btn_play'),
        FocusTarget(rect=pygame.Rect(100, 100, 200, 40), id='btn_settings'),
    ])
    # Her frame:
    fm.handle_action(action)  # GamepadAction.NAV_DOWN, CONFIRM, BACK, vb.
    fm.draw_focus_ring(screen)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

import pygame


# ─── Gamepad Action Enum (F2.4) ─────────────────────────────────────────────

class GamepadAction(Enum):
    """Proje genelinde ortak gamepad action contract.

    Tüm ekranlar bu action'ları handle edebilir; mapping gamepad_manager'da
    kalır (ACTION_TO_KEY + sentetik event pipeline).
    """
    CONFIRM = auto()       # A / Enter / Space
    BACK = auto()          # B / ESC
    NAV_UP = auto()        # D-pad Up / K_UP
    NAV_DOWN = auto()      # D-pad Down / K_DOWN
    NAV_LEFT = auto()      # D-pad Left / K_LEFT
    NAV_RIGHT = auto()     # D-pad Right / K_RIGHT
    TAB_NEXT = auto()      # RB / K_RIGHTBRACKET
    TAB_PREV = auto()      # LB / K_LEFTBRACKET


# Key → GamepadAction mapping (sentetik KEYDOWN event'lerinden action çözümü)
_KEY_TO_ACTION: dict[int, GamepadAction] = {
    pygame.K_RETURN: GamepadAction.CONFIRM,
    pygame.K_KP_ENTER: GamepadAction.CONFIRM,
    pygame.K_SPACE: GamepadAction.CONFIRM,
    pygame.K_ESCAPE: GamepadAction.BACK,
    pygame.K_UP: GamepadAction.NAV_UP,
    pygame.K_DOWN: GamepadAction.NAV_DOWN,
    pygame.K_LEFT: GamepadAction.NAV_LEFT,
    pygame.K_RIGHT: GamepadAction.NAV_RIGHT,
    pygame.K_RIGHTBRACKET: GamepadAction.TAB_NEXT,
    pygame.K_LEFTBRACKET: GamepadAction.TAB_PREV,
}


def key_to_action(key: int) -> Optional[GamepadAction]:
    """pygame key code'dan GamepadAction'a çevir. Eşleşme yoksa None."""
    return _KEY_TO_ACTION.get(key)


# ─── Focus Target ───────────────────────────────────────────────────────────

@dataclass
class FocusTarget:
    """Tek bir odaklanabilir UI elemanı."""
    rect: pygame.Rect
    id: str = ''
    on_confirm: Optional[Callable[[], object]] = None
    on_back: Optional[Callable[[], object]] = None
    group: str = 'default'
    # Opsiyonel: bu target'ın navigasyon komşuları (None = otomatik hesapla)
    neighbor_up: Optional[str] = None
    neighbor_down: Optional[str] = None
    neighbor_left: Optional[str] = None
    neighbor_right: Optional[str] = None


# ─── Focus Manager ──────────────────────────────────────────────────────────

class FocusManager:
    """Ekranlar arası paylaşılabilir focus/navigation yöneticisi.

    Özellikler:
    - Directional navigation (nearest-neighbor veya explicit komşu)
    - Focus ring çizimi (highlight border)
    - Confirm/back action dispatch
    - Wrap-around opsiyonel
    """

    def __init__(self, *, wrap: bool = False):
        self._targets: list[FocusTarget] = []
        self._focused_index: int = 0
        self._wrap = wrap
        # Focus ring görsel ayarları
        self.ring_color: tuple[int, int, int] = (80, 180, 255)
        self.ring_width: int = 2
        self.ring_padding: int = 3
        self.ring_radius: int = 6

    @property
    def focused_index(self) -> int:
        return self._focused_index

    @focused_index.setter
    def focused_index(self, value: int) -> None:
        if self._targets:
            self._focused_index = max(0, min(len(self._targets) - 1, int(value)))
        else:
            self._focused_index = 0

    @property
    def focused_target(self) -> Optional[FocusTarget]:
        if not self._targets:
            return None
        idx = max(0, min(len(self._targets) - 1, self._focused_index))
        return self._targets[idx]

    @property
    def focused_id(self) -> str:
        target = self.focused_target
        return target.id if target else ''

    def register(self, targets: list[FocusTarget]) -> None:
        """Yeni target listesi kaydet. Focus index sıfırlanır."""
        self._targets = list(targets)
        self._focused_index = 0

    def update_rects(self, rects: dict[str, pygame.Rect]) -> None:
        """Mevcut target'ların rect'lerini güncelle (layout değiştiğinde).

        Args:
            rects: {target_id: new_rect} mapping'i.
        """
        for target in self._targets:
            if target.id in rects:
                target.rect = rects[target.id]

    def clear(self) -> None:
        """Tüm target'ları temizle."""
        self._targets.clear()
        self._focused_index = 0

    def handle_action(self, action: GamepadAction) -> object | None:
        """Bir GamepadAction'ı işle. Confirm/back callback sonucu döner."""
        if not self._targets:
            return None

        if action == GamepadAction.CONFIRM:
            target = self.focused_target
            if target and target.on_confirm:
                return target.on_confirm()
            return 'confirm'

        if action == GamepadAction.BACK:
            target = self.focused_target
            if target and target.on_back:
                return target.on_back()
            return 'back'

        if action in (GamepadAction.NAV_UP, GamepadAction.NAV_DOWN,
                      GamepadAction.NAV_LEFT, GamepadAction.NAV_RIGHT):
            self._navigate(action)
            return None

        return None

    def handle_key(self, key: int) -> object | None:
        """pygame key code'dan action çözüp handle et. Eşleşme yoksa None."""
        action = key_to_action(key)
        if action is None:
            return None
        return self.handle_action(action)

    def _navigate(self, action: GamepadAction) -> None:
        """Directional navigation: nearest-neighbor veya explicit komşu."""
        if not self._targets:
            return

        current = self.focused_target
        if current is None:
            return

        # Explicit komşu kontrolü
        direction_map = {
            GamepadAction.NAV_UP: 'neighbor_up',
            GamepadAction.NAV_DOWN: 'neighbor_down',
            GamepadAction.NAV_LEFT: 'neighbor_left',
            GamepadAction.NAV_RIGHT: 'neighbor_right',
        }
        neighbor_attr = direction_map.get(action)
        if neighbor_attr:
            neighbor_id = getattr(current, neighbor_attr, None)
            if neighbor_id:
                for i, t in enumerate(self._targets):
                    if t.id == neighbor_id:
                        self._focused_index = i
                        return

        # Nearest-neighbor hesaplama
        cx, cy = current.rect.centerx, current.rect.centery
        best_idx = None
        best_dist = float('inf')

        for i, target in enumerate(self._targets):
            if i == self._focused_index:
                continue
            tx, ty = target.rect.centerx, target.rect.centery
            dx, dy = tx - cx, ty - cy

            # Yön filtresi
            if action == GamepadAction.NAV_UP and dy >= 0:
                continue
            if action == GamepadAction.NAV_DOWN and dy <= 0:
                continue
            if action == GamepadAction.NAV_LEFT and dx >= 0:
                continue
            if action == GamepadAction.NAV_RIGHT and dx <= 0:
                continue

            # Mesafe (yön ağırlıklı)
            if action in (GamepadAction.NAV_UP, GamepadAction.NAV_DOWN):
                dist = abs(dy) + abs(dx) * 0.3
            else:
                dist = abs(dx) + abs(dy) * 0.3

            if dist < best_dist:
                best_dist = dist
                best_idx = i

        if best_idx is not None:
            self._focused_index = best_idx
        elif self._wrap:
            # Wrap: karşı uca git
            if action == GamepadAction.NAV_DOWN:
                self._focused_index = 0
            elif action == GamepadAction.NAV_UP:
                self._focused_index = len(self._targets) - 1
            elif action == GamepadAction.NAV_RIGHT:
                self._focused_index = 0
            elif action == GamepadAction.NAV_LEFT:
                self._focused_index = len(self._targets) - 1

    def draw_focus_ring(self, screen: pygame.Surface) -> None:
        """Aktif focus target'ın etrafına highlight ring çiz."""
        target = self.focused_target
        if target is None:
            return
        rect = target.rect
        if rect.width <= 0 or rect.height <= 0:
            return
        padded = rect.inflate(self.ring_padding * 2, self.ring_padding * 2)
        try:
            pygame.draw.rect(
                screen,
                self.ring_color,
                padded,
                self.ring_width,
                border_radius=self.ring_radius,
            )
        except Exception:
            pygame.draw.rect(screen, self.ring_color, padded, self.ring_width)

    def get_focused_rect(self) -> Optional[pygame.Rect]:
        """Aktif focus target'ın rect'ini döndür."""
        target = self.focused_target
        return target.rect if target else None
