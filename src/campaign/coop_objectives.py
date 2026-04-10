"""Co-op Kampanya Görev (Objective) Sınıfları

CoopGame event sistemine bağlanan, co-op'a özel görev türleri.
Mevcut Objective base class'ını kullanır.
"""
from __future__ import annotations
from typing import Dict, Any, Optional

from .objectives import (
    Objective,
    ClearLinesObjective,
    ScoreObjective,
    TetrisObjective,
    ComboObjective,
    TimeObjective,
)


# -----------------------------------------------------------------------
# Mevcut objective'lerin co-op uyumlu sarmalayıcıları
# (event formatı aynı olduğu için doğrudan kullanılabilir)
# -----------------------------------------------------------------------

CoopClearLinesObjective = ClearLinesObjective
CoopScoreObjective = ScoreObjective
CoopTetrisObjective = TetrisObjective
CoopSurvivalObjective = TimeObjective


# -----------------------------------------------------------------------
# Co-op'a özel yeni objective türleri
# -----------------------------------------------------------------------

class SharedHoldObjective(Objective):
    """Hold'u N kez kullan görevi.

    Sınıf adı geriye dönük config anahtarı uyumu için korunur; güncel co-op
    davranışı oyuncu bazlı ayrı hold slotları kullanır.
    """

    def __init__(self, target: int = 3):
        super().__init__(
            target,
            f"Hold'u {target} Kez Kullan",
            f"Use Hold {target} Times",
            description_key='coop_obj_shared_hold',
            description_params={
                'target': lambda lang, v=target: Objective._format_number(v, lang)
            },
        )

    def update(self, game, event_type: str, event_data: Dict[str, Any]) -> None:
        if event_type == 'hold_used':
            self.progress += 1
            self.check_completion()


class BalancedContributionObjective(Objective):
    """Dengeli Katkı Görevi — İki oyuncu da en az %X katkı sağlamalı."""

    def __init__(self, min_pct: int = 30):
        self.min_pct = min_pct
        super().__init__(
            100,  # hedef: kontrol göstergesi
            f"Her Oyuncu En Az %{min_pct} Katkı",
            f"Each Player at Least {min_pct}% Contribution",
            description_key='coop_obj_balanced',
            description_params={
                'pct': lambda lang, v=min_pct: str(v),
            },
        )
        # Bu görev lines_cleared bazlı kontrolle tamamlanır
        self._total_lines_needed = 10  # Minimum satır eşiği

    def update(self, game, event_type: str, event_data: Dict[str, Any]) -> None:
        if event_type != 'lines_cleared':
            return
        total_cells = getattr(game, 'p1_total_cells', 0) + getattr(game, 'p2_total_cells', 0)
        if total_cells < 20:
            # Yeterli veri yok
            return
        p1_pct = getattr(game, 'p1_contribution_pct', 50)
        p2_pct = getattr(game, 'p2_contribution_pct', 50)
        total_lines = getattr(game, 'total_lines_cleared', 0)
        if total_lines >= self._total_lines_needed and p1_pct >= self.min_pct and p2_pct >= self.min_pct:
            self.progress = 100
            self.check_completion()
        else:
            self.progress = min(p1_pct, p2_pct)

    def get_progress_text(self) -> str:
        return f"Min %{self.progress}"


class FreezeRecoveryObjective(Objective):
    """Freeze'den Kurtulma Görevi — N kez freeze'den kurtul."""

    def __init__(self, target: int = 2):
        super().__init__(
            target,
            f"Freeze'den {target} Kez Kurtul",
            f"Recover from Freeze {target} Times",
            description_key='coop_obj_freeze_recovery',
            description_params={
                'target': lambda lang, v=target: Objective._format_number(v, lang),
            },
        )
        self._frozen_players: set = set()

    def update(self, game, event_type: str, event_data: Dict[str, Any]) -> None:
        if event_type == 'player_frozen':
            self._frozen_players.add(event_data.get('player'))
        elif event_type == 'lines_cleared':
            # Satır temizlendikten sonra unfreeze olmuş olabilir
            p1_frozen = getattr(game, 'p1_frozen', False)
            p2_frozen = getattr(game, 'p2_frozen', False)
            for p in list(self._frozen_players):
                still_frozen = (p == 'P1' and p1_frozen) or (p == 'P2' and p2_frozen)
                pending = (p == 'P1' and getattr(game, '_p1_pending_unfreeze', False)) or \
                          (p == 'P2' and getattr(game, '_p2_pending_unfreeze', False))
                if not still_frozen or pending:
                    self._frozen_players.discard(p)
                    self.progress += 1
            self.check_completion()


class CoopComboObjective(Objective):
    """Co-op Combo Görevi — Ardışık satır temizleme."""

    def __init__(self, target: int = 3):
        super().__init__(
            target,
            f"{target} Ardışık Temizleme Yap",
            f"Make {target} Consecutive Clears",
            description_key='coop_obj_combo',
            description_params={
                'target': lambda lang, v=target: Objective._format_number(v, lang),
            },
        )
        self._consecutive = 0
        self._last_cleared = False

    def update(self, game, event_type: str, event_data: Dict[str, Any]) -> None:
        if event_type == 'lines_cleared':
            self._last_cleared = True
            self._consecutive += 1
            if self._consecutive > self.progress:
                self.progress = self._consecutive
            self.check_completion()
        elif event_type == 'piece_placed':
            # Önceki parçada satır temizlenmediyse combo kırılır
            if not self._last_cleared:
                self._consecutive = 0
            self._last_cleared = False


# -----------------------------------------------------------------------
# Factory
# -----------------------------------------------------------------------

def create_coop_objective(obj_config: Dict[str, Any]) -> Objective:
    """Görev konfigürasyonundan co-op objective instance'ı oluştur."""
    obj_type = obj_config.get('type', 'clear_lines')
    target = obj_config.get('target', 10)
    kwargs = {k: v for k, v in obj_config.items() if k not in ('type', 'target')}

    factories = {
        'clear_lines': lambda: CoopClearLinesObjective(
            target=target,
            line_type=kwargs.get('line_type'),
        ),
        'score': lambda: CoopScoreObjective(target=target),
        'tetris': lambda: CoopTetrisObjective(target=target),
        'survival': lambda: CoopSurvivalObjective(
            target_seconds=target,
            objective_type='survive',
        ),
        'shared_hold': lambda: SharedHoldObjective(target=target),
        'balanced': lambda: BalancedContributionObjective(
            min_pct=kwargs.get('min_pct', 30),
        ),
        'freeze_recovery': lambda: FreezeRecoveryObjective(target=target),
        'combo': lambda: CoopComboObjective(target=target),
    }

    factory = factories.get(obj_type)
    if factory:
        return factory()
    return CoopClearLinesObjective(target=target)
