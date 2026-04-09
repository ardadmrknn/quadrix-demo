"""Co-op Kampanya Level Verileri

20 co-op level, 2 dünya halinde:
  Dünya 1 (1-10): Başlangıç — Temel co-op mekanikleri
  Dünya 2 (11-20): Koordinasyon — Daha zorlu hedefler

Her level progresif olarak zorlaşır.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class CoopLevelConfig:
    """Tek bir co-op level'ın konfigürasyonu."""
    level: int
    world: int  # 1-2
    name: Dict[str, str]
    objectives: List[Dict[str, Any]]
    speed: int = 900  # ms (düşme hızı)
    time_limit: Optional[int] = None
    no_hold: bool = False
    no_preview: bool = False
    stars: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    xp_reward: int = 100
    is_boss: bool = False


# -----------------------------------------------------------------------
# Yıldız koşulu yardımcıları
# -----------------------------------------------------------------------

def _cs() -> Dict[str, Any]:
    """1. yıldız: Level'ı tamamla."""
    return {'type': 'complete'}

def _ct(secs: int) -> Dict[str, Any]:
    """Zaman limiti yıldızı."""
    return {'type': 'time_limit', 'value': secs}

def _sc(score: int) -> Dict[str, Any]:
    """Skor yıldızı."""
    return {'type': 'score', 'value': score}

def _qx(n: int = 1) -> Dict[str, Any]:
    """Quadrix yıldızı."""
    return {'type': 'tetris', 'value': n}

def _cm(n: int = 2) -> Dict[str, Any]:
    """Combo yıldızı."""
    return {'type': 'combo', 'value': n}

def _bl(pct: int = 35) -> Dict[str, Any]:
    """Dengeli katkı yıldızı."""
    return {'type': 'balanced', 'value': pct}


# -----------------------------------------------------------------------
# Görev yardımcıları
# -----------------------------------------------------------------------

def _obj_lines(n: int) -> Dict[str, Any]:
    return {'type': 'clear_lines', 'target': n}

def _obj_score(n: int) -> Dict[str, Any]:
    return {'type': 'score', 'target': n}

def _obj_tetris(n: int) -> Dict[str, Any]:
    return {'type': 'tetris', 'target': n}

def _obj_survival(secs: int) -> Dict[str, Any]:
    return {'type': 'survival', 'target': secs}

def _obj_hold(n: int) -> Dict[str, Any]:
    return {'type': 'shared_hold', 'target': n}

def _obj_balanced(min_pct: int = 30) -> Dict[str, Any]:
    return {'type': 'balanced', 'target': 100, 'min_pct': min_pct}

def _obj_freeze_recovery(n: int) -> Dict[str, Any]:
    return {'type': 'freeze_recovery', 'target': n}


# -----------------------------------------------------------------------
# Level tanımları
# -----------------------------------------------------------------------

_COOP_LEVELS: Dict[int, Dict[str, Any]] = {
    # ========================
    # DÜNYA 1: Başlangıç Vadisi (1-10)
    # ========================
    1: {
        'world': 1,
        'name': {'tr': 'İlk Adım', 'en': 'First Step'},
        'objectives': [_obj_lines(3)],
        'speed': 900,
        'stars': {1: _cs(), 2: _ct(90), 3: _ct(60)},
        'xp_reward': 80,
    },
    2: {
        'world': 1,
        'name': {'tr': 'Birlikte Temizle', 'en': 'Clear Together'},
        'objectives': [_obj_lines(5)],
        'speed': 880,
        'stars': {1: _cs(), 2: _ct(100), 3: _ct(70)},
        'xp_reward': 90,
    },
    3: {
        'world': 1,
        'name': {'tr': 'Takım Skoru', 'en': 'Team Score'},
        'objectives': [_obj_score(500)],
        'speed': 860,
        'stars': {1: _cs(), 2: _sc(800), 3: _ct(80)},
        'xp_reward': 100,
    },
    4: {
        'world': 1,
        'name': {'tr': 'On Satır', 'en': 'Ten Lines'},
        'objectives': [_obj_lines(10)],
        'speed': 840,
        'stars': {1: _cs(), 2: _ct(120), 3: _qx(1)},
        'xp_reward': 110,
    },
    5: {
        'world': 1,
        'name': {'tr': 'Hold Yok!', 'en': 'No Hold!'},
        'objectives': [_obj_lines(10)],
        'speed': 820,
        'no_hold': True,
        'is_boss': False,
        'stars': {1: _cs(), 2: _ct(100), 3: _ct(75)},
        'xp_reward': 130,
    },
    6: {
        'world': 1,
        'name': {'tr': 'Paylaşım Zamanı', 'en': 'Sharing Time'},
        'objectives': [_obj_lines(8), _obj_hold(3)],
        'speed': 800,
        'stars': {1: _cs(), 2: _ct(120), 3: _sc(1200)},
        'xp_reward': 140,
    },
    7: {
        'world': 1,
        'name': {'tr': 'Hızlanan Tempo', 'en': 'Rising Tempo'},
        'objectives': [_obj_lines(15)],
        'speed': 780,
        'stars': {1: _cs(), 2: _ct(150), 3: _qx(2)},
        'xp_reward': 150,
    },
    8: {
        'world': 1,
        'name': {'tr': 'Bin Beş Yüz', 'en': 'Fifteen Hundred'},
        'objectives': [_obj_score(1500)],
        'speed': 760,
        'stars': {1: _cs(), 2: _sc(2000), 3: _ct(100)},
        'xp_reward': 160,
    },
    9: {
        'world': 1,
        'name': {'tr': 'Senkronize', 'en': 'Synchronized'},
        'objectives': [_obj_lines(18)],
        'speed': 740,
        'stars': {1: _cs(), 2: _bl(35), 3: _ct(140)},
        'xp_reward': 170,
    },
    10: {
        'world': 1,
        'name': {'tr': 'Kör Ayna', 'en': 'Blind Mirror'},
        'objectives': [_obj_lines(20)],
        'speed': 720,
        'no_preview': True,
        'is_boss': True,
        'stars': {1: _cs(), 2: _ct(180), 3: _sc(3000)},
        'xp_reward': 200,
    },

    # ========================
    # DÜNYA 2: Koordinasyon Kalesi (11-20)
    # ========================
    11: {
        'world': 2,
        'name': {'tr': 'Denge Ustası', 'en': 'Balance Master'},
        'objectives': [_obj_lines(15), _obj_balanced(30)],
        'speed': 700,
        'stars': {1: _cs(), 2: _bl(40), 3: _ct(120)},
        'xp_reward': 200,
    },
    12: {
        'world': 2,
        'name': {'tr': 'Dayanıklılık', 'en': 'Endurance'},
        'objectives': [_obj_survival(120)],
        'speed': 680,
        'stars': {1: _cs(), 2: _sc(2000), 3: _qx(2)},
        'xp_reward': 210,
    },
    13: {
        'world': 2,
        'name': {'tr': 'Yirmi Beş', 'en': 'Twenty Five'},
        'objectives': [_obj_lines(25)],
        'speed': 660,
        'stars': {1: _cs(), 2: _ct(180), 3: _bl(40)},
        'xp_reward': 220,
    },
    14: {
        'world': 2,
        'name': {'tr': 'Quadrix İkilisi', 'en': 'Quadrix Duo'},
        'objectives': [_obj_tetris(2)],
        'speed': 640,
        'stars': {1: _cs(), 2: _qx(3), 3: _ct(120)},
        'xp_reward': 230,
    },
    15: {
        'world': 2,
        'name': {'tr': 'Kısıtlı Hold', 'en': 'Limited Hold'},
        'objectives': [_obj_lines(25)],
        'speed': 620,
        'no_hold': True,
        'is_boss': False,
        'stars': {1: _cs(), 2: _ct(160), 3: _sc(4000)},
        'xp_reward': 250,
    },
    16: {
        'world': 2,
        'name': {'tr': 'Üç Bin', 'en': 'Three Thousand'},
        'objectives': [_obj_score(3000)],
        'speed': 600,
        'stars': {1: _cs(), 2: _sc(4500), 3: _ct(140)},
        'xp_reward': 260,
    },
    17: {
        'world': 2,
        'name': {'tr': 'Otuz Satır', 'en': 'Thirty Lines'},
        'objectives': [_obj_lines(30)],
        'speed': 580,
        'stars': {1: _cs(), 2: _qx(3), 3: _bl(40)},
        'xp_reward': 280,
    },
    18: {
        'world': 2,
        'name': {'tr': 'Aktarma Ustası', 'en': 'Transfer Master'},
        'objectives': [_obj_lines(20), _obj_hold(5)],
        'speed': 560,
        'stars': {1: _cs(), 2: _ct(150), 3: _sc(5000)},
        'xp_reward': 290,
    },
    19: {
        'world': 2,
        'name': {'tr': 'Uzun Oyun', 'en': 'Long Game'},
        'objectives': [_obj_survival(180)],
        'speed': 540,
        'stars': {1: _cs(), 2: _sc(5000), 3: _qx(4)},
        'xp_reward': 300,
    },
    20: {
        'world': 2,
        'name': {'tr': 'Son Sınav', 'en': 'Final Exam'},
        'objectives': [_obj_lines(35)],
        'speed': 500,
        'no_preview': True,
        'is_boss': True,
        'stars': {1: _cs(), 2: _ct(240), 3: _sc(7000)},
        'xp_reward': 400,
    },
}


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------

TOTAL_COOP_LEVELS = len(_COOP_LEVELS)
COOP_WORLDS = 2


def get_coop_level(level_num: int) -> Optional[CoopLevelConfig]:
    """Level numarasına göre config döndür. Geçersizse None."""
    data = _COOP_LEVELS.get(level_num)
    if data is None:
        return None
    return CoopLevelConfig(
        level=level_num,
        world=data.get('world', 1),
        name=data.get('name', {'tr': f'Level {level_num}', 'en': f'Level {level_num}'}),
        objectives=data.get('objectives', [_obj_lines(10)]),
        speed=data.get('speed', 900),
        time_limit=data.get('time_limit'),
        no_hold=data.get('no_hold', False),
        no_preview=data.get('no_preview', False),
        stars=data.get('stars', {1: _cs()}),
        xp_reward=data.get('xp_reward', 100),
        is_boss=data.get('is_boss', False),
    )


def get_coop_world_levels(world: int) -> List[CoopLevelConfig]:
    """Bir dünyaya ait tüm level'ları döndür."""
    result = []
    for num, data in sorted(_COOP_LEVELS.items()):
        if data.get('world') == world:
            cfg = get_coop_level(num)
            if cfg:
                result.append(cfg)
    return result
