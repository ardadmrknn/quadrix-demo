"""100 Level Campaign Verisi

Her level progresif olarak zorlaşır:
- Düşme hızı artar
- Görev hedefleri artar
- Yeni mekanikler eklenir
- Temel tetromino havuzu sabit kalır

Zorluk Formülü:
- speed = 900 - (level * 5)  # 900ms'den 400ms'e düşer
- lines_target = base + (level * progression_rate)
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class LevelConfig:
    """Tek bir level'ın konfigürasyonu"""
    level: int
    world: int  # 1-5 arası dünya
    name: Dict[str, str]  # {"tr": "...", "en": "..."}
    
    # Görevler
    objectives: List[Dict[str, Any]]  # [{"type": "clear_lines", "target": 10}, ...]
    
    # Blok ayarları
    allowed_pieces: List[str] = field(default_factory=lambda: ['I', 'O', 'T', 'S', 'Z', 'J', 'L'])
    
    # Hız (ms) - düşük = hızlı
    speed: int = 800
    
    # Sınırlar
    time_limit: Optional[int] = None  # Saniye, None = süresiz
    move_limit: Optional[int] = None  # Blok sınırı (kaç blok kullanılabilir)
    
    # Özel bloklar ve engeller
    special_blocks: List[Dict[str, Any]] = field(default_factory=list)
    pre_placed_rows: int = 0  # Başlangıçta yerleşik satır sayısı (çöp bloklar)
    garbage_pattern: str = 'none'  # Çöp desen: none, random, checkered, pyramid, walls, valley, zigzag, holes
    
    # Özel kurallar
    no_hold: bool = False  # Hold kullanılamaz
    no_preview: bool = False  # Sonraki bloklar görünmez
    fast_start: bool = False  # Hızlı başlangıç
    cascade_mode: bool = False  # Cascade gravity aktif
    
    # Yıldız koşulları
    stars: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    
    # Ödüller
    xp_reward: int = 100
    
    # Boss level mi?
    is_boss: bool = False
    
    # Kilit açma koşulu
    unlock_requires: Optional[int] = None  # Önceki level numarası


def _calculate_block_limit(level: int, objectives: List[Dict[str, Any]], is_boss: bool) -> int:
    """Level'a göre blok sınırını hesapla.
    
    Formül: Görev hedefine dayalı akıllı blok limiti.
    - Satır temizleme: Hedefin ~2.0-3.0 katı blok (level'a göre azalır)
    - Skor hedefi: Tahmini blok gereksinimi * çarpan
    - Combo/Quadrix: Daha fazla blok (daha zor görevler)
    - Çöp temizleme: Çöp miktarına + ekstra blok
    - Hayatta kalma: Süre bazlı blok limiti
    
    Returns:
        Blok sınırı (minimum 15)
    """
    main_obj = objectives[0] if objectives else {}
    obj_type = main_obj.get('type', 'clear_lines')
    target = main_obj.get('target', 10)
    
    # Level'a göre çarpan (erken levellar daha cömert)
    if level <= 5:
        multiplier = 3.5  # Öğrenme aşaması - çok cömert
    elif level <= 15:
        multiplier = 3.0  # Hala rahat
    elif level <= 30:
        multiplier = 2.5  # Orta zorluk
    elif level <= 50:
        multiplier = 2.2  # Zorlaşıyor
    elif level <= 75:
        multiplier = 2.0  # Zor
    else:
        multiplier = 1.8  # Çok zor
    
    # Görev tipine göre temel blok sayısı
    if obj_type == 'clear_lines':
        # Satır temizleme: Her satır için ~2-3 blok gerekir ortalama
        base_blocks = int(target * multiplier)
    elif obj_type == 'score':
        # Skor hedefi: ~60 puan/blok ortalama (Faz 2: 80'den düşüldü)
        estimated_blocks = target // 60
        base_blocks = int(estimated_blocks * multiplier)
    elif obj_type == 'tetris':
        # Quadrix yapmak zor - her Quadrix ~7 blok (Faz 2: 10'dan düşüldü)
        base_blocks = int(target * 7 * multiplier)
    elif obj_type == 'combo':
        # Combo: Ardışık temizleme gerektirir
        base_blocks = int(target * 8 * multiplier)
    elif obj_type == 'clear_garbage':
        # Çöp temizleme: target=0 build-time'da bilinmediği için
        # gerçek çöp hücre sayısı tahmin edilir.
        # garbage_rows * board_width * 0.45 (~%45 doluluk varsayımı)
        garbage_rows = _calculate_garbage_rows(level, is_boss)
        # Override tablosunda explicit garbage_rows varsa onu kullan
        ov = _LEVEL_OVERRIDES.get(level, {}) if isinstance(_LEVEL_OVERRIDES.get(level), dict) else {}
        if 'garbage_rows' in ov:
            garbage_rows = ov['garbage_rows']
        # clear_garbage görevi varsa minimum 2 satır garanti (auto-gen kuralı)
        if garbage_rows == 0:
            garbage_rows = max(2, min(4, 2 + (level - 6) // 10))
        BOARD_WIDTH_ASSUMED = 10
        AVERAGE_FILL_RATIO = 0.45
        estimated_cells = max(15, int(garbage_rows * BOARD_WIDTH_ASSUMED * AVERAGE_FILL_RATIO))
        # Her bloğun ~3-4 hücre kaldıracağı varsayımıyla taban blok sayısı
        base_blocks = int((estimated_cells / 3.5) * multiplier)
    elif obj_type == 'survival':
        # Hayatta kalma: Süre bazlı (~1 blok/3 saniye ortalama)
        base_blocks = int((target // 3) * multiplier)
    elif obj_type == 'time_challenge':
        # Zamanlı: Orta seviye blok
        base_blocks = int(15 * multiplier)
    elif obj_type == 'perfect_clear':
        # Mükemmel temizleme: Daha fazla blok ver
        base_blocks = int(target * 3.0 * multiplier)
    else:
        # Varsayılan
        base_blocks = int(20 * multiplier)
    
    # Boss levellarda %30 ekstra blok
    if is_boss:
        base_blocks = int(base_blocks * 1.3)
    
    # Ek görevler varsa ekstra blok ekle
    if len(objectives) > 1:
        base_blocks += 5 * (len(objectives) - 1)
    
    # Minimum ve maksimum sınırlar
    return max(15, min(base_blocks, 120))


def _calculate_speed(level: int, objective_type: str = 'clear_lines') -> int:
    """Level'a göre düşme hızını hesapla (ms).

    Faz 2: Objective tipine duyarlı. Faz 3 dokümantasyon genişletmesi.

    Args:
        level: 1-100 arası level numarası
        objective_type: Ana objective tipi. Aşağıdaki tiplerde balans
            çarpanı uygulanır; diğer tipler base hızı kullanır:
              - 'survival': 0.92x (oyuncu meşgul olsun)
              - 'score':    1.05x (combo planlamak gerek)
              - 'tetris':   1.08x (I parçası beklemesi gerek)

    Returns:
        Düşme hızı (ms). Clamp aralığı: [400, 1100].
    """
    base_speed = 900 - (level * 5)

    if objective_type == 'survival':
        # Survival: %8 daha hızlı (oyuncu meşgul olsun)
        base_speed = int(base_speed * 0.92)
    elif objective_type == 'score':
        # Score: %5 daha yavaş (combo planlamak gerek)
        base_speed = int(base_speed * 1.05)
    elif objective_type == 'tetris':
        # Quadrix: %8 daha yavaş (I parçası beklemesi)
        base_speed = int(base_speed * 1.08)

    return max(400, min(1100, base_speed))


def _calculate_lines_target(level: int, base: int = 5) -> int:
    """Level'a göre satır hedefini hesapla"""
    # Level 1: 5, Level 10: 10, Level 50: 30, Level 100: 55
    if level <= 10:
        return base + (level - 1) // 2
    elif level <= 50:
        return 10 + (level - 10) // 2
    else:
        return 30 + (level - 50) // 2


def _get_allowed_pieces(level: int) -> List[str]:
    """Campaign için standart 7 parça havuzunu döndür."""
    return ['I', 'O', 'T', 'S', 'Z', 'J', 'L']


def _get_world(level: int) -> int:
    """Level'a göre dünya numarasını döndür"""
    if level <= 20:
        return 1  # Başlangıç Vadisi
    elif level <= 40:
        return 2  # Buz Diyarı
    elif level <= 60:
        return 3  # Lav Mağarası
    elif level <= 80:
        return 4  # Fırtına Kalesi
    else:
        return 5  # Yıldız Kulesi


def _get_world_names() -> Dict[int, Dict[str, str]]:
    """Dünya isimlerini döndür"""
    return {
        1: {
            "tr": "Başlangıç Vadisi",
            "en": "Beginner's Valley",
            "de": "Anfänger-Tal",
            "fr": "Vallée des Débutants",
            "es": "Valle del Principiante",
            "it": "Valle dei Principianti",
            "pt": "Vale do Iniciante",
            "ru": "Долина Новичков",
            "ja": "初心者の谷",
            "zh": "新手山谷",
            "ko": "초보자의 계곡",
        },
        2: {
            "tr": "Buz Diyarı",
            "en": "Ice Realm",
            "de": "Eisreich",
            "fr": "Royaume de Glace",
            "es": "Reino de Hielo",
            "it": "Regno di Ghiaccio",
            "pt": "Reino de Gelo",
            "ru": "Ледяное Царство",
            "ja": "氷の領域",
            "zh": "冰之领域",
            "ko": "얼음 왕국",
        },
        3: {
            "tr": "Lav Mağarası",
            "en": "Lava Caves",
            "de": "Lavahöhlen",
            "fr": "Grottes de Lave",
            "es": "Cuevas de Lava",
            "it": "Grotte di Lava",
            "pt": "Cavernas de Lava",
            "ru": "Лавовые Пещеры",
            "ja": "溶岩洞窟",
            "zh": "熔岩洞穴",
            "ko": "용암 동굴",
        },
        4: {
            "tr": "Fırtına Kalesi",
            "en": "Storm Fortress",
            "de": "Sturmfestung",
            "fr": "Forteresse de la Tempête",
            "es": "Fortaleza de la Tormenta",
            "it": "Fortezza della Tempesta",
            "pt": "Fortaleza da Tempestade",
            "ru": "Крепость Бури",
            "ja": "嵐の要塞",
            "zh": "风暴堡垒",
            "ko": "폭풍의 요새",
        },
        5: {
            "tr": "Yıldız Kulesi",
            "en": "Star Tower",
            "de": "Sternenturm",
            "fr": "Tour des Étoiles",
            "es": "Torre de las Estrellas",
            "it": "Torre delle Stelle",
            "pt": "Torre das Estrelas",
            "ru": "Звёздная Башня",
            "ja": "星の塔",
            "zh": "星之塔",
            "ko": "별의 탑",
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# LEVEL OVERRIDE YARDIMCI FONKSİYONLARI
# ──────────────────────────────────────────────────────────────────────────────

def _cs() -> Dict[str, Any]:
    """1. Yıldız: Leveli tamamla"""
    return {'type': 'complete', 'description': {'tr': "Level'ı tamamla", 'en': "Complete level"}}

def _ct(secs: int) -> Dict[str, Any]:
    """Zaman limiti yıldızı"""
    return {'type': 'time_limit', 'value': secs,
            'description': {'tr': f"{secs}s içinde tamamla", 'en': f"Complete in {secs}s"}}

def _cm(n: int) -> Dict[str, Any]:
    """Combo yıldızı"""
    return {'type': 'combo', 'value': n,
            'description': {'tr': f"{n} Combo yap", 'en': f"Get {n} Combo(s)"}}

def _mc(n: int) -> Dict[str, Any]:
    """Multi-clear yıldızı (2=Double, 3=Triple)"""
    suffix = "2'li" if n == 2 else "3'lü" if n == 3 else f"{n}'li"
    clear_name = "Double" if n == 2 else "Triple" if n == 3 else f"{n}-clear"
    return {'type': 'multi_clear', 'value': n,
            'description': {'tr': f"{suffix} satır temizle", 'en': f"Get a {clear_name}"}}

def _qx(n: int = 1) -> Dict[str, Any]:
    """Quadrix yıldızı"""
    desc_tr = "Quadrix yap (4'lü)" if n == 1 else f"{n} Quadrix yap"
    desc_en = "Make a Quadrix clear" if n == 1 else f"Make {n} Quadrix clears"
    return {
        'type': 'tetris',
        'value': n,
        'description_key': 'campaign_cond_tetris',
        'description_kwargs': {'value': n},
        'description': {'tr': desc_tr, 'en': desc_en},
    }

def _cc(n: int) -> Dict[str, Any]:
    """Combo zinciri yıldızı."""
    return {
        'type': 'combo_chain',
        'value': n,
        'description_key': 'campaign_cond_combo_chain',
        'description_kwargs': {'value': n},
        'description': {'tr': f"Üst üste {n} combo", 'en': f"Make {n} combos in a row"},
    }


def _translate_condition_key(key: str, lang: str, **kwargs: Any) -> str:
    try:
        from ..localization import TRANSLATIONS  # type: ignore
    except Exception:
        from localization import TRANSLATIONS

    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang) or entry.get('en') or entry.get('tr') or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            pass
    return str(text)


def _format_condition_value(value: Any, lang: str) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        formatted = f"{value:,}"
        if lang == 'tr':
            formatted = formatted.replace(',', '.')
        return formatted
    if isinstance(value, float):
        formatted = f"{value:g}"
        if lang == 'tr':
            formatted = formatted.replace('.', ',')
        return formatted
    return value


def resolve_star_condition_text(condition: Dict[str, Any], lang: str) -> str:
    """Yıldız koşulunu oyuncuya gösterilecek metne çevir."""
    cond_type = condition.get('type', 'complete')
    desc_key = condition.get('description_key')
    desc_kwargs = dict(condition.get('description_kwargs', {}) or {})

    if desc_key:
        if desc_key == 'campaign_cond_tetris' and int(condition.get('value', 0) or 0) == 1:
            desc_key = 'campaign_cond_tetris_single'
        formatted_kwargs = {
            key: _format_condition_value(value, lang)
            for key, value in desc_kwargs.items()
        }
        return _translate_condition_key(desc_key, lang, **formatted_kwargs)

    cond_value = int(condition.get('value', 0) or 0)
    formatted_value = _format_condition_value(cond_value, lang)
    if cond_type == 'complete':
        return _translate_condition_key('campaign_cond_complete', lang)
    if cond_type == 'score':
        return _translate_condition_key('campaign_cond_score', lang, value=formatted_value)
    if cond_type == 'combo':
        return _translate_condition_key('campaign_cond_combo', lang, value=formatted_value)
    if cond_type == 'multi_clear':
        if cond_value == 2:
            return _translate_condition_key('campaign_cond_multi_clear_2', lang)
        if cond_value == 3:
            return _translate_condition_key('campaign_cond_multi_clear_3', lang)
        return _translate_condition_key('campaign_cond_multi_clear_n', lang, value=formatted_value)
    if cond_type == 'tetris':
        key = 'campaign_cond_tetris_single' if cond_value == 1 else 'campaign_cond_tetris'
        return _translate_condition_key(key, lang, value=formatted_value)
    if cond_type == 'combo_chain':
        return _translate_condition_key('campaign_cond_combo_chain', lang, value=formatted_value)
    if cond_type == 'time_limit':
        return _translate_condition_key('campaign_cond_time_limit', lang, value=formatted_value)
    if cond_type == 'extra_lines':
        return _translate_condition_key('campaign_cond_extra_lines', lang, value=formatted_value)
    if cond_type == 'efficiency':
        return _translate_condition_key('campaign_cond_efficiency', lang, value=formatted_value)
    if cond_type == 'time':
        return _translate_condition_key('campaign_cond_time', lang, value=formatted_value)
    # Faz 2: Yeni tipler
    if cond_type == 'no_hold_run':
        return _translate_condition_key('campaign_cond_no_hold_run', lang)
    if cond_type == 'pristine':
        return _translate_condition_key('campaign_cond_pristine', lang)
    if cond_type == 'garbage_speed':
        return _translate_condition_key('campaign_cond_garbage_speed', lang, value=formatted_value)
    if cond_type == 'tetris_only':
        return _translate_condition_key('campaign_cond_tetris_only', lang)
    if cond_type == 'min_score':
        return _translate_condition_key('campaign_cond_min_score', lang, value=formatted_value)

    desc = condition.get('description', {})
    if isinstance(desc, dict):
        return str(desc.get(lang) or desc.get('en') or str(cond_type))
    return str(desc or cond_type)

def _mv(n: int) -> Dict[str, Any]:
    """Move (blok) limiti yıldızı"""
    return {'type': 'move_limit', 'value': n,
            'description': {'tr': f"{n} blokta tamamla", 'en': f"Complete in {n} moves"}}


# === FAZ 2: Yeni yıldız tipleri ===

def _no_hold_run() -> Dict[str, Any]:
    """Hold kullanmadan tamamla (mini-boss/boss zaten yasaklı; normal level'da gönüllü meydan okuma)."""
    return {
        'type': 'no_hold_run',
        'description_key': 'campaign_cond_no_hold_run',
        'description_kwargs': {},
    }


def _pristine() -> Dict[str, Any]:
    """Hard drop kullanmadan tamamla."""
    return {
        'type': 'pristine',
        'description_key': 'campaign_cond_pristine',
        'description_kwargs': {},
    }


def _garbage_speed(secs: int) -> Dict[str, Any]:
    """clear_garbage görevini X saniyede tamamla."""
    return {
        'type': 'garbage_speed',
        'value': secs,
        'description_key': 'campaign_cond_garbage_speed',
        'description_kwargs': {'value': secs},
    }


def _tetris_only() -> Dict[str, Any]:
    """Sadece Quadrix temizleme (single/double/triple sayılmaz)."""
    return {
        'type': 'tetris_only',
        'description_key': 'campaign_cond_tetris_only',
        'description_kwargs': {},
    }


def _min_score(n: int) -> Dict[str, Any]:
    """En az N puanla tamamla (ana görevden bağımsız)."""
    return {
        'type': 'min_score',
        'value': n,
        'description_key': 'campaign_cond_min_score',
        'description_kwargs': {'value': n},
    }


def _obj_lines(n: int) -> Dict[str, Any]:
    return {'type': 'clear_lines', 'target': n}

def _obj_score(n: int) -> Dict[str, Any]:
    return {'type': 'score', 'target': n}

def _obj_tetris(n: int = 1) -> Dict[str, Any]:
    return {'type': 'tetris', 'target': n}

def _obj_combo(n: int) -> Dict[str, Any]:
    return {'type': 'combo', 'target': n}

def _obj_garbage() -> Dict[str, Any]:
    return {'type': 'clear_garbage', 'target': 0}

def _obj_survival(n: int) -> Dict[str, Any]:
    return {
        'type': 'survival',
        'target': n,
    }

def _obj_multi_clear(n: int) -> Dict[str, Any]:
    if n == 2:
        desc_key = 'campaign_cond_multi_clear_2'
        desc_kwargs: Dict[str, Any] = {}
    elif n == 3:
        desc_key = 'campaign_cond_multi_clear_3'
        desc_kwargs = {}
    else:
        desc_key = 'campaign_cond_multi_clear_n'
        desc_kwargs = {'value': n}
    return {
        'type': 'multi_clear',
        'target': n,
        'description_key': desc_key,
        'description_kwargs': desc_kwargs,
    }

def _obj_special_block(n: int) -> Dict[str, Any]:
    return {'type': 'special_block', 'target': n}


# ──────────────────────────────────────────────────────────────────────────────
# LEVEL OVERRIDE TABLOSU
# Sadece auto-gen'den FARKLI olan alanlar belirtilmiştir.
# 'move_limit': None → limit yok | int → o limit | anahtar yoksa auto-calc
# 'time_limit': None → süresiz  | int → saniye   | anahtar yoksa auto-calc
# ──────────────────────────────────────────────────────────────────────────────
_LEVEL_OVERRIDES: Dict[int, Dict[str, Any]] = {
    # ─── DÜNYA 1: BAŞLANGIÇ VADİSİ ────────────────────
    1:   {'objectives': [_obj_lines(3)], 'move_limit': None, 'stars': {1: _cs(), 2: _mc(2), 3: _ct(110)}},
    2:   {'objectives': [_obj_lines(4)], 'move_limit': 19, 'stars': {1: _cs(), 2: _cm(1), 3: _ct(110)}},
    3:   {'objectives': [_obj_lines(5)], 'stars': {1: _cs(), 2: _mc(2), 3: _cm(1)}},
    4:   {'move_limit': None, 'time_limit': 100, 'stars': {1: _cs(), 2: _cm(1), 3: _mv(21)}},
    5:   {'stars': {1: _cs(), 2: _mc(2), 3: _ct(100)}},
    6:   {'move_limit': 24, 'stars': {1: _cs(), 2: _cm(1), 3: _cm(2)}},
    7:   {'objectives': [_obj_score(2100)], 'move_limit': 34, 'stars': {1: _cs(), 2: _mc(2), 3: _min_score(3000)}},
    8:   {'move_limit': 24, 'stars': {1: _cs(), 2: _cm(1), 3: _ct(80)}},
    9:   {'objectives': [_obj_lines(8)], 'move_limit': None, 'time_limit': 120, 'stars': {1: _cs(), 2: _mc(2), 3: _no_hold_run()}},
    10:  {'move_limit': 39, 'stars': {1: _cs(), 2: _cm(2), 3: _ct(75)}},            # BOSS
    11:  {'objectives': [_obj_score(2300)], 'move_limit': 42, 'stars': {1: _cs(), 2: _cm(2), 3: _ct(80)}},
    12:  {'objectives': [_obj_multi_clear(3)], 'move_limit': 35, 'stars': {1: _cs(), 2: _cm(1), 3: _ct(100)}},
    13:  {'move_limit': 42, 'garbage_rows': 2, 'stars': {1: _cs(), 2: _cm(2), 3: _pristine()}},
    14:  {'move_limit': 42, 'stars': {1: _cs(), 2: _mv(28), 3: _ct(80)}},
    15:  {'objectives': [_obj_lines(13)], 'move_limit': 39, 'stars': {1: _cs(), 2: _mc(3), 3: _cm(2)}},
    16:  {'objectives': [_obj_score(3000)], 'move_limit': 39, 'stars': {1: _cs(), 2: _cm(2), 3: _min_score(4500)}},
    17:  {'objectives': [_obj_tetris(1)], 'move_limit': None, 'stars': {1: _cs(), 2: _mv(28), 3: _ct(85)}},
    18:  {'move_limit': 34, 'stars': {1: _cs(), 2: _mc(3), 3: _cm(2)}},
    19:  {'move_limit': None, 'time_limit': 75, 'stars': {1: _cs(), 2: _mv(26), 3: _no_hold_run()}},
    20:  {'move_limit': 60, 'time_limit': 90, 'stars': {1: _cs(), 2: _cm(2), 3: _ct(75)}},  # BOSS
    # ─── DÜNYA 2: BUZ DİYARI ──────────────────────────
    21:  {'objectives': [_obj_lines(14)], 'move_limit': 36, 'stars': {1: _cs(), 2: _mc(3), 3: _cm(2)}},
    22:  {'objectives': [_obj_score(3500)], 'move_limit': 60, 'time_limit': 70, 'stars': {1: _cs(), 2: _cm(2), 3: _min_score(5000)}},
    23:  {'objectives': [_obj_tetris(1)], 'move_limit': 30, 'stars': {1: _cs(), 2: _ct(90), 3: _no_hold_run()}},
    24:  {'move_limit': 40, 'stars': {1: _cs(), 2: _mc(3), 3: _pristine()}},
    25:  {'stars': {1: _cs(), 2: _mv(50), 3: _ct(80)}},
    26:  {'objectives': [_obj_lines(15)], 'move_limit': 60, 'stars': {1: _cs(), 2: _cm(2), 3: _ct(85)}},
    27:  {'objectives': [_obj_score(7000)], 'stars': {1: _cs(), 2: _mc(3), 3: _min_score(9000)}},
    28:  {'objectives': [_obj_lines(6)], 'move_limit': None, 'time_limit': 30, 'garbage_rows': 0, 'stars': {1: _cs(), 2: _mc(2), 3: _ct(25)}},
    29:  {'objectives': [_obj_score(3000)], 'move_limit': None, 'time_limit': 50, 'stars': {1: _cs(), 2: _cm(1), 3: _no_hold_run()}},
    30:  {'objectives': [_obj_tetris(2)], 'move_limit': 80, 'time_limit': 150, 'stars': {1: _cs(), 2: _cm(1), 3: _ct(120)}},  # BOSS
    # ─── DÜNYA 2 (devam) ──────────────────────────────
    31:  {'garbage_rows': 4, 'stars': {1: _cs(), 2: _cm(2), 3: _pristine()}},
    32:  {'objectives': [_obj_combo(3), _obj_special_block(4)]},
    33:  {'stars': {1: _cs(), 2: _cm(3), 3: _cc(3)}},
    34:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(58)}},
    35:  {'stars': {1: _cs(), 2: _cm(3), 3: _no_hold_run()}},
    36:  {'objectives': [_obj_score(4600), _obj_special_block(5)], 'stars': {1: _cs(), 2: _qx(), 3: _min_score(6500)}},
    37:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(57)}},
    38:  {'stars': {1: _cs(), 2: _cm(3), 3: _pristine()}},
    39:  {'stars': {1: _cs(), 2: _cm(3), 3: _cc(3)}},
    40:  {'objectives': [_obj_lines(32), _obj_special_block(5)]},  # BOSS
    # ─── DÜNYA 3: LAV MAĞARASI ────────────────────────
    # Faz 2: 3. yıldız çeşitlendi: _ct, _cc, _garbage_speed, _min_score rotasyonu
    41:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(55)}},
    42:  {'stars': {1: _cs(), 2: _cm(3), 3: _cc(3)}},
    43:  {'stars': {1: _cs(), 2: _cm(3), 3: _min_score(7000)}},
    # L44: auto-gen ile aynı, override yok
    45:  {'objectives': [_obj_garbage(), _obj_special_block(2)], 'stars': {1: _cs(), 2: _cm(3), 3: _garbage_speed(75)}},
    46:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(52)}},
    47:  {'stars': {1: _cs(), 2: _cm(3), 3: _cc(3)}},
    48:  {'stars': {1: _cs(), 2: _qx(), 3: _min_score(8000)}},
    49:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(51)}},
    50:  {'objectives': [_obj_score(9000), _obj_special_block(3)], 'stars': {1: _cs(), 2: _cm(3), 3: _min_score(12000)}},  # BOSS
    51:  {'stars': {1: _cs(), 2: _cm(3), 3: _cc(3)}},
    # L52: auto-gen ile aynı, override yok
    53:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(49)}},
    54:  {'stars': {1: _cs(), 2: _cm(3), 3: _min_score(8500)}},
    55:  {'objectives': [_obj_survival(170), _obj_special_block(3)], 'stars': {1: _cs(), 2: _cm(3), 3: _ct(180)}},
    # L56: auto-gen ile aynı, override yok
    57:  {'stars': {1: _cs(), 2: _cm(3), 3: _cc(3)}},
    58:  {'stars': {1: _cs(), 2: _cm(3), 3: _ct(46)}},
    59:  {'stars': {1: _cs(), 2: _cm(3), 3: _garbage_speed(60)}},
    60:  {'objectives': [_obj_tetris(6), _obj_special_block(4)], 'stars': {1: _cs(), 2: _qx(), 3: _tetris_only()}},  # BOSS
    # ─── DÜNYA 4: FIRTINA KALESİ ──────────────────────
    # Faz 2: 3. yıldız çeşitlendi: _ct, _qx(2), _tetris_only, _pristine, _cc rotasyonu
    61:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(45)}},
    62:  {'stars': {1: _cs(), 2: _cm(4), 3: _pristine()}},
    63:  {'stars': {1: _cs(), 2: _cm(4), 3: _cc(3)}},
    64:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(44)}},
    65:  {'stars': {1: _cs(), 2: _qx(2), 3: _tetris_only()}},
    66:  {'stars': {1: _cs(), 2: _cm(4), 3: _cc(3)}},
    67:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(44)}},
    68:  {'stars': {1: _cs(), 2: _cm(4), 3: _pristine()}},
    69:  {'stars': {1: _cs(), 2: _cm(4), 3: _cc(3)}},
    70:  {'stars': {1: _cs(), 2: _qx(2), 3: _tetris_only()}},  # BOSS
    71:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(43)}},
    72:  {'stars': {1: _cs(), 2: _cm(4), 3: _pristine()}},
    73:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(42)}},
    74:  {'stars': {1: _cs(), 2: _cm(4), 3: _cc(3)}},
    75:  {'stars': {1: _cs(), 2: _qx(2), 3: _tetris_only()}},
    76:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(41)}},
    77:  {'stars': {1: _cs(), 2: _cm(4), 3: _pristine()}},
    78:  {'stars': {1: _cs(), 2: _cm(4), 3: _cc(3)}},
    79:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(41)}},
    80:  {'stars': {1: _cs(), 2: _qx(2), 3: _tetris_only()}},  # BOSS
    # ─── DÜNYA 5: YILDIZ KULESİ ───────────────────────
    # Faz 2: 3. yıldız tüm tipler karışık; boss'lar en zor (tetris_only veya min_score yüksek)
    81:  {'stars': {1: _cs(), 2: _cm(4), 3: _no_hold_run()}},
    82:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(40)}},
    83:  {'stars': {1: _cs(), 2: _cm(4), 3: _min_score(15000)}},
    84:  {'stars': {1: _cs(), 2: _cm(4), 3: _pristine()}},
    85:  {'stars': {1: _cs(), 2: _qx(2), 3: _tetris_only()}},
    86:  {'stars': {1: _cs(), 2: _cm(4), 3: _cc(3)}},
    87:  {'stars': {1: _cs(), 2: _cm(4), 3: _no_hold_run()}},
    88:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(38)}},
    89:  {'stars': {1: _cs(), 2: _cm(4), 3: _min_score(18000)}},
    90:  {'stars': {1: _cs(), 2: _qx(2), 3: _tetris_only()}},  # BOSS
    91:  {'stars': {1: _cs(), 2: _cm(4), 3: _pristine()}},
    92:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(37)}},
    93:  {'stars': {1: _cs(), 2: _cm(4), 3: _cc(3)}},
    94:  {'stars': {1: _cs(), 2: _cm(4), 3: _no_hold_run()}},
    95:  {'stars': {1: _cs(), 2: _qx(2), 3: _tetris_only()}},
    96:  {'stars': {1: _cs(), 2: _cm(4), 3: _min_score(20000)}},
    97:  {'stars': {1: _cs(), 2: _cm(4), 3: _ct(36)}},
    98:  {'stars': {1: _cs(), 2: _cm(4), 3: _pristine()}},
    99:  {'stars': {1: _cs(), 2: _cm(4), 3: _cc(3)}},
    100: {'stars': {1: _cs(), 2: _qx(2), 3: _tetris_only()}},  # FINAL BOSS

}


def _generate_level(level: int) -> LevelConfig:
    """Dinamik olarak level konfigürasyonu oluştur"""
    world = _get_world(level)
    allowed_pieces = _get_allowed_pieces(level)
    
    # Boss level mi? (Her 10. level)
    is_boss = level % 10 == 0
    
    # XP ödülü (boss levellar daha fazla verir)
    base_xp = 50 + (level * 5)
    xp_reward = base_xp * 3 if is_boss else base_xp
    
    # Level ismi
    level_names = _generate_level_names(level, is_boss)
    
    # Görevler - level'a göre değişir
    objectives = _generate_objectives(level, world, is_boss)

    # Faz 2: Hız objective tipine duyarlı
    main_obj_type = objectives[0].get('type', 'clear_lines') if objectives else 'clear_lines'
    speed = _calculate_speed(level, main_obj_type)
    
    # Yıldız koşulları
    stars = _generate_star_conditions(level, objectives)
    
    # Özel bloklar (World 2'den itibaren)
    special_blocks = _generate_special_blocks(level, world)
    
    # Özel kurallar
    no_hold = level >= 70 and (level % 7 == 0)  # Bazı geç levellarda hold yok
    cascade_mode = level >= 50 and (level % 5 == 0)  # Cascade modlu levellar
    
    # Zaman limiti (bazı levellarda)
    time_limit = None
    
    if level >= 30 and level % 6 == 0:
        # Her 6. level (30'dan sonra) zaman limiti var
        time_limit = max(60, 180 - (level - 30) * 2)  # 180s'den 60s'e düşer
    
    # Blok sınırı - TÜM LEVELLAR İÇİN
    move_limit = _calculate_block_limit(level, objectives, is_boss)
    
    # Çöp bloklar (garbage blocks) - level 6'dan itibaren
    garbage_rows = _calculate_garbage_rows(level, is_boss)
    garbage_pattern = _get_garbage_pattern(level)
    
    # clear_garbage görevi varsa mutlaka çöp satırı olmalı
    has_clear_garbage = any(obj.get('type') == 'clear_garbage' for obj in objectives)
    if has_clear_garbage and garbage_rows == 0:
        # Level'a göre 2-4 satır çöp ekle
        garbage_rows = max(2, min(4, 2 + (level - 6) // 10))
        
    # --- KULLANICI ÖZEL DEĞİŞİKLİKLERİ (OVERRIDES) ---
    ov = _LEVEL_OVERRIDES.get(level)
    if ov:
        if 'objectives' in ov:
            objectives = ov['objectives']
        if 'move_limit' in ov:
            move_limit = ov['move_limit']
        if 'time_limit' in ov:
            time_limit = ov['time_limit']
        if 'garbage_rows' in ov:
            garbage_rows = ov['garbage_rows']
        if 'garbage_pattern' in ov:
            garbage_pattern = ov['garbage_pattern']
        if 'no_hold' in ov:
            no_hold = ov['no_hold']
        if 'cascade_mode' in ov:
            cascade_mode = ov['cascade_mode']
        if 'speed' in ov:
            speed = ov['speed']
        if 'stars' in ov:
            stars = ov['stars']

    # === BUILD-TIME AUTO-FIX (Faz 1) ===
    # survival objective + time_limit çakışmasını otomatik gider:
    # time_limit, survival_target + 10s'den daha kısa olamaz.
    survival_target = None
    for obj in objectives:
        if obj.get('type') == 'survival':
            survival_target = int(obj.get('target', 0) or 0)
            break

    if survival_target is not None and time_limit is not None:
        min_time_limit = survival_target + 10
        if time_limit < min_time_limit:
            time_limit = min_time_limit

    return LevelConfig(
        level=level,
        world=world,
        name=level_names,
        objectives=objectives,
        allowed_pieces=allowed_pieces,
        speed=speed,
        time_limit=time_limit,
        move_limit=move_limit,
        special_blocks=special_blocks,
        pre_placed_rows=garbage_rows,  # Çöp satırları
        garbage_pattern=garbage_pattern,  # Yeni: çöp deseni
        no_hold=no_hold,
        cascade_mode=cascade_mode,
        stars=stars,
        xp_reward=xp_reward,
        is_boss=is_boss,
        unlock_requires=level - 1 if level > 1 else None,
    )
def _calculate_garbage_rows(level: int, is_boss: bool) -> int:
    """Çöp satırı sayısını hesapla"""
    if level < 6:
        return 0
    
    # Level 6-10: 2-3 satır (clear_garbage için yeterli)
    if level <= 10:
        base = 2 if level < 9 else 3
    # Level 11-20: 2-3 satır (bazı levellarda)
    elif level <= 20:
        if level % 3 == 0:  # Her 3. level
            base = 2 + (level - 10) // 5
        else:
            base = 0
    # Level 21-40: 2-4 satır
    elif level <= 40:
        if level % 2 == 0:  # Her 2. level
            base = 2 + (level - 20) // 10
        else:
            base = 0
    # Level 41-60: 3-5 satır
    elif level <= 60:
        base = 3 + (level - 40) // 10
    # Level 61-80: 4-6 satır
    elif level <= 80:
        base = 4 + (level - 60) // 10
    # Level 81-100: 5-8 satır
    else:
        base = 5 + (level - 80) // 7
    
    # Boss levellarda +2 satır
    if is_boss:
        base += 2
    
    return min(base, 10)  # Maximum 10 satır


def _get_garbage_pattern(level: int) -> str:
    """Çöp bloklarının desenini belirle"""
    if level < 6:
        return 'none'
    
    patterns = [
        'random',       # Rastgele boşluklu
        'checkered',    # Dama desenli
        'pyramid',      # Piramit şeklinde
        'walls',        # Duvarlı (ortada boşluk)
        'valley',       # Vadi (kenarlarda yüksek)
        'zigzag',       # Zikzak
        'holes',        # Rastgele delikli
    ]
    
    # Level'a göre desen seç
    if level <= 10:
        return 'random'
    elif level <= 20:
        return patterns[level % 3]  # random, checkered, pyramid
    elif level <= 40:
        return patterns[level % 5]  # İlk 5 desen
    else:
        return patterns[level % len(patterns)]  # Tüm desenler


def _generate_level_names(level: int, is_boss: bool) -> Dict[str, str]:
    """Level isimlerini oluştur"""
    
    # Boss level isimleri
    boss_names = {
        10: {
            "tr": "İlk Sınav", "en": "First Trial",
            "de": "Erste Prüfung", "fr": "Première Épreuve",
            "es": "Primera Prueba", "it": "Prima Prova", "pt": "Primeiro Teste",
            "ru": "Первое Испытание", "ja": "最初の試練", "zh": "首次试炼", "ko": "첫 시련",
        },
        20: {
            "tr": "Buz Efendisi", "en": "Ice Lord",
            "de": "Eisherr", "fr": "Seigneur des Glaces",
            "es": "Señor del Hielo", "it": "Signore del Ghiaccio", "pt": "Senhor do Gelo",
            "ru": "Ледяной Лорд", "ja": "氷の主", "zh": "冰之领主", "ko": "얼음의 군주",
        },
        30: {
            "tr": "Kilit Ustası", "en": "Lock Master",
            "de": "Schlossmeister", "fr": "Maître des Verrous",
            "es": "Maestro de Cerraduras", "it": "Maestro dei Lucchetti", "pt": "Mestre dos Cadeados",
            "ru": "Мастер Замков", "ja": "錠前の名手", "zh": "锁之大师", "ko": "자물쇠의 명인",
        },
        40: {
            "tr": "Patlama Kralı", "en": "Blast King",
            "de": "Sprengmeister", "fr": "Roi des Explosions",
            "es": "Rey de las Explosiones", "it": "Re delle Esplosioni", "pt": "Rei das Explosões",
            "ru": "Король Взрывов", "ja": "爆破王", "zh": "爆破之王", "ko": "폭발의 왕",
        },
        50: {
            "tr": "Zaman Bekçisi", "en": "Time Guardian",
            "de": "Zeitwächter", "fr": "Gardien du Temps",
            "es": "Guardián del Tiempo", "it": "Custode del Tempo", "pt": "Guardião do Tempo",
            "ru": "Страж Времени", "ja": "時の番人", "zh": "时之守护者", "ko": "시간의 수호자",
        },
        60: {
            "tr": "Lav Ejderhası", "en": "Lava Dragon",
            "de": "Lavadrache", "fr": "Dragon de Lave",
            "es": "Dragón de Lava", "it": "Drago di Lava", "pt": "Dragão de Lava",
            "ru": "Лавовый Дракон", "ja": "溶岩竜", "zh": "熔岩巨龙", "ko": "용암 드래곤",
        },
        70: {
            "tr": "Fırtına Lordu", "en": "Storm Lord",
            "de": "Sturmfürst", "fr": "Seigneur des Tempêtes",
            "es": "Señor de las Tormentas", "it": "Signore della Tempesta", "pt": "Senhor da Tempestade",
            "ru": "Лорд Бури", "ja": "嵐の主", "zh": "风暴领主", "ko": "폭풍의 군주",
        },
        80: {
            "tr": "Gölge Şövalyesi", "en": "Shadow Knight",
            "de": "Schattenritter", "fr": "Chevalier de l'Ombre",
            "es": "Caballero de las Sombras", "it": "Cavaliere dell'Ombra", "pt": "Cavaleiro das Sombras",
            "ru": "Рыцарь Тени", "ja": "影の騎士", "zh": "暗影骑士", "ko": "그림자 기사",
        },
        90: {
            "tr": "Yıldız Prensi", "en": "Star Prince",
            "de": "Sternenprinz", "fr": "Prince des Étoiles",
            "es": "Príncipe de las Estrellas", "it": "Principe delle Stelle", "pt": "Príncipe das Estrelas",
            "ru": "Звёздный Принц", "ja": "星の王子", "zh": "星之王子", "ko": "별의 왕자",
        },
        100: {
            "tr": "Son Mücadele", "en": "Final Showdown",
            "de": "Letztes Duell", "fr": "Confrontation Finale",
            "es": "Duelo Final", "it": "Resa dei Conti Finale", "pt": "Confronto Final",
            "ru": "Финальное Противостояние", "ja": "最終決戦", "zh": "最终对决", "ko": "최후의 결전",
        },
    }
    
    if is_boss and level in boss_names:
        return boss_names[level]
    
    # Normal level isimleri - World'e göre
    world = _get_world(level)
    world_level = ((level - 1) % 20) + 1  # Her dünyada 1-20
    
    world_prefixes = {
        1: {
            "tr": "Vadi", "en": "Valley",
            "de": "Tal", "fr": "Vallée", "es": "Valle", "it": "Valle", "pt": "Vale",
            "ru": "Долина", "ja": "渓谷", "zh": "山谷", "ko": "계곡",
        },
        2: {
            "tr": "Buz", "en": "Ice",
            "de": "Eis", "fr": "Glace", "es": "Hielo", "it": "Ghiaccio", "pt": "Gelo",
            "ru": "Лёд", "ja": "氷", "zh": "冰", "ko": "얼음",
        },
        3: {
            "tr": "Lav", "en": "Lava",
            "de": "Lava", "fr": "Lave", "es": "Lava", "it": "Lava", "pt": "Lava",
            "ru": "Лава", "ja": "溶岩", "zh": "熔岩", "ko": "용암",
        },
        4: {
            "tr": "Fırtına", "en": "Storm",
            "de": "Sturm", "fr": "Tempête", "es": "Tormenta", "it": "Tempesta", "pt": "Tempestade",
            "ru": "Буря", "ja": "嵐", "zh": "风暴", "ko": "폭풍",
        },
        5: {
            "tr": "Yıldız", "en": "Star",
            "de": "Stern", "fr": "Étoile", "es": "Estrella", "it": "Stella", "pt": "Estrela",
            "ru": "Звезда", "ja": "星", "zh": "星", "ko": "별",
        },
    }

    default_prefix = {
        "tr": "Level", "en": "Level",
        "de": "Level", "fr": "Niveau", "es": "Nivel", "it": "Livello", "pt": "Nível",
        "ru": "Уровень", "ja": "レベル", "zh": "关卡", "ko": "레벨",
    }
    prefix = world_prefixes.get(world, default_prefix)

    result: Dict[str, str] = {}
    for lang_code, prefix_text in prefix.items():
        result[lang_code] = f"{prefix_text} {world_level}"
    return result


def _generate_objectives(level: int, world: int, is_boss: bool) -> List[Dict[str, Any]]:
    """Level'a göre çeşitli görevler oluştur"""
    objectives = []
    
    # Level 1-5: Sadece basit satır temizleme
    if level <= 5:
        lines_target = _calculate_lines_target(level)
        objectives.append({
            "type": "clear_lines",
            "target": lines_target
        })
        return objectives
    
    # Level 6+: Çeşitli görevler
    
    # Görev tipi belirleme (level'a göre değişen)
    objective_type = _get_objective_type(level, world, is_boss)
    
    if objective_type == 'clear_lines':
        lines_target = _calculate_lines_target(level)
        if is_boss:
            lines_target = int(lines_target * 1.3)
        objectives.append({
            "type": "clear_lines",
            "target": lines_target
        })
    
    elif objective_type == 'clear_garbage':
        # Çöp temizleme görevi - TÜM gri çöp bloklarını temizle
        # Target: 0 = otomatik olarak board'daki çöp hücre sayısından hesaplanır
        objectives.append({
            "type": "clear_garbage",
            "target": 0  # Otomatik hesaplanacak
        })
    
    elif objective_type == 'score_target':
        # Puan hedefi
        score_target = 1000 + level * 100
        if is_boss:
            score_target = int(score_target * 1.5)
        objectives.append({
            "type": "score",
            "target": score_target
        })
    
    elif objective_type == 'tetris_count':
        # Quadrix yapma görevi
        tetris_target = 1 + level // 15
        if is_boss:
            tetris_target += 1
        objectives.append({
            "type": "tetris",
            "target": tetris_target
        })
    
    elif objective_type == 'survival':
        # Hayatta kalma görevi (süre)
        survival_time = 60 + (level // 5) * 10  # 60-260 saniye
        objectives.append({
            "type": "survival",
            "target": survival_time,
        })
    
    elif objective_type == 'combo':
        # Combo görevi
        combo_target = 2 + level // 20
        objectives.append({
            "type": "combo",
            "target": combo_target
        })
    
    elif objective_type == 'speed_clear':
        # Hızlı temizleme (az satır ama zamanlı)
        objectives.append({
            "type": "clear_lines",
            "target": 5 + level // 20
        })
        objectives.append({
            "type": "time_challenge",
            "target": max(30, 90 - level // 3),  # 30-90 saniye
        })
    
    # Ek görevler (world'e göre)
    _add_world_specific_objectives(objectives, level, world, is_boss)
    
    return objectives


def _get_objective_type(level: int, world: int, is_boss: bool) -> str:
    """Level için ana görev tipini belirle"""
    
    # Boss level: karışık zor görevler
    if is_boss:
        boss_types = ['clear_lines', 'score_target', 'tetris_count']
        return boss_types[(level // 10 - 1) % len(boss_types)]
    
    # Normal level: rotasyon sistemi
    objective_types = [
        'clear_lines',      # Klasik satır temizleme
        'score_target',     # Puan hedefi
        'tetris_count',     # Quadrix yapma
        'clear_garbage',    # Çöp temizleme
        'combo',            # Combo
        'speed_clear',      # Hızlı temizleme
        'survival',         # Hayatta kalma
    ]
    
    # Level 6-10: Basit çeşitlilik
    if level <= 10:
        simple_types = ['clear_lines', 'score_target', 'clear_garbage']
        return simple_types[(level - 6) % len(simple_types)]
    
    # Level 11-20: Daha fazla çeşit
    elif level <= 20:
        return objective_types[level % 5]
    
    # Level 21+: Tüm tipler
    else:
        return objective_types[level % len(objective_types)]


def _add_world_specific_objectives(objectives: List[Dict], level: int, world: int, is_boss: bool) -> None:
    """Dünyaya özel ek görevler ekle"""
    
    # Dünya 2: Buz temalı
    if world == 2:
        if level % 4 == 0 and level >= 25:
            objectives.append({
                "type": "special_block",
                "target": 3 + (level - 20) // 8,
                "block_type": "ice"
            })
    
    # Dünya 3: Bomba ve zamanlı bloklar
    elif world == 3:
        if level % 5 == 0 and level >= 45:
            objectives.append({
                "type": "special_block",
                "target": 2 + (level - 40) // 10,
                "block_type": "bomb"
            })
    
    # Dünya 4: Combo master
    elif world == 4:
        if level % 3 == 0:
            objectives.append({
                "type": "combo",
                "target": 3 + (level - 60) // 10
            })
    
    # Dünya 5: Her şey
    elif world == 5:
        if is_boss:
            objectives.append({
                "type": "tetris",
                "target": 2 + (level - 80) // 10
            })


def _generate_star_conditions(level: int, objectives: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """Yıldız kazanma koşullarını oluştur
    
    Yeni Sistem:
    - 1⭐: Ana görevi tamamla (satır/skor/çöp temizle)
    - 2⭐: Teknik beceri göster (combo, double/triple/tetris)
    - 3⭐: Ustalık (combo zinciri, süre limiti)
    """
    main_obj = objectives[0] if objectives else {}
    main_type = main_obj.get('type', 'clear_lines')
    
    # 1. YILDIZ - Her zaman ana görevi tamamla
    first_star = {
        "type": "complete",
        "description": {"tr": "Level'ı tamamla", "en": "Complete level"}
    }
    
    # 2. YILDIZ - Teknik beceri (level'a göre değişir)
    # Erken leveller: basit combo veya double
    # Orta leveller: triple veya 2 combo
    # Geç leveller: tetris veya 3+ combo
    
    if level <= 10:
        # Erken leveller: Basit combo veya double (2'li satır)
        if level % 2 == 0:
            second_star = {
                "type": "combo",
                "value": 1,
                "description": {"tr": "1 Combo yap", "en": "Get 1 Combo"}
            }
        else:
            second_star = {
                "type": "multi_clear",
                "value": 2,  # Double (2 satır aynı anda)
                "description": {"tr": "2'li satır temizle", "en": "Get a Double"}
            }
    elif level <= 30:
        # Orta leveller: Triple veya 2 combo
        if level % 3 == 0:
            second_star = {
                "type": "multi_clear",
                "value": 3,  # Triple (3 satır aynı anda)
                "description": {"tr": "3'lü satır temizle", "en": "Get a Triple"}
            }
        else:
            second_star = {
                "type": "combo",
                "value": 2,
                "description": {"tr": "2 Combo yap", "en": "Get 2 Combos"}
            }
    elif level <= 60:
        # İleri leveller: Quadrix veya 3 combo
        if level % 4 == 0:
            second_star = {
                "type": "tetris",
                "value": 1,
                "description": {"tr": "Quadrix yap (4'lü)", "en": "Get a Quadrix"}
            }
        else:
            second_star = {
                "type": "combo",
                "value": 3,
                "description": {"tr": "3 Combo yap", "en": "Get 3 Combos"}
            }
    else:
        # Uzman leveller: 2 Quadrix veya 4+ combo
        if level % 5 == 0:
            second_star = {
                "type": "tetris",
                "value": 2,
                "description": {"tr": "2 Quadrix yap", "en": "Get 2 Tetrises"}
            }
        else:
            second_star = {
                "type": "combo",
                "value": 4,
                "description": {"tr": "4 Combo yap", "en": "Get 4 Combos"}
            }
    
    # 3. YILDIZ - Ustalık (süre limiti veya combo zinciri)
    # Alternatif olarak süre veya combo zinciri
    
    if level % 3 == 0:
        # Her 3. level: Combo zinciri (üst üste combo)
        chain_target = min(3, 2 + level // 30)  # 2-3 arası
        third_star = {
            "type": "combo_chain",
            "value": chain_target,
            "description": {"tr": f"Üst üste {chain_target} combo", "en": f"{chain_target} combo chain"}
        }
    else:
        # Diğer leveller: Süre limiti
        # Level'a göre süre: erken leveller daha fazla süre
        if level <= 10:
            time_limit = 120 - (level * 5)  # 115s - 70s
        elif level <= 30:
            time_limit = 90 - ((level - 10) * 2)  # 88s - 50s
        elif level <= 60:
            time_limit = 60 - ((level - 30) // 2)  # 59s - 45s
        else:
            time_limit = 45 - ((level - 60) // 4)  # 44s - 35s
        
        time_limit = max(30, time_limit)  # Minimum 30 saniye
        
        third_star = {
            "type": "time_limit",
            "value": time_limit,
            "description": {"tr": f"{time_limit}s içinde tamamla", "en": f"Complete in {time_limit}s"}
        }
    
    return {
        1: first_star,
        2: second_star,
        3: third_star
    }


def _generate_special_blocks(level: int, world: int) -> List[Dict[str, Any]]:
    """Özel blokları oluştur"""
    special = []
    
    # Dünya 2: Buz blokları (Level 21+)
    if world >= 2 and level >= 21:
        ice_count = min(15, 3 + (level - 21) // 4)
        special.append({
            "type": "ice",
            "count": ice_count,
            "spawn_chance": 0.1 + (level - 21) * 0.005
        })
    
    # Dünya 2: Kilitli bloklar (Level 26+)
    if level >= 26:
        lock_count = min(10, 2 + (level - 26) // 5)
        special.append({
            "type": "locked",
            "count": lock_count,
            "spawn_chance": 0.05 + (level - 26) * 0.003
        })
    
    # Dünya 3: Bomba blokları (Level 41+)
    if world >= 3 and level >= 41:
        bomb_count = min(8, 1 + (level - 41) // 8)
        special.append({
            "type": "bomb",
            "count": bomb_count,
            "spawn_chance": 0.03 + (level - 41) * 0.002
        })
    
    # Dünya 3: Zamanlı bloklar (Level 51+)
    if level >= 51:
        timer_count = min(6, 1 + (level - 51) // 10)
        special.append({
            "type": "timer",
            "count": timer_count,
            "timer_seconds": max(8, 15 - (level - 51) // 10)  # 15s'den 8s'e düşer
        })
    
    # Dünya 4+: Yıldız blokları (bonus puanlar)
    if world >= 4 and level % 5 == 0:
        special.append({
            "type": "star",
            "count": 3,
            "bonus_points": 500
        })
    
    return special


def generate_garbage_grid(rows: int, cols: int = 10, pattern: str = 'random', level: int = 1) -> List[List[int]]:
    """Çöp blok grid'i oluştur - HER LEVEL İÇİN SABİT DESEN
    
    Level 1-5: Çöp yok
    Level 6-100: 95 farklı sabit şekil deseni
    
    Returns:
        2D liste - 0: boş, 1-7: farklı blok renkleri (garbage)
    """
    if level < 6 or rows <= 0 or pattern == 'none':
        return []
    
    # Level'a göre şekil deseni seç (6-100 arası -> 0-94 indeks)
    shape_index = level - 6
    
    # Önceden tanımlı şekil desenlerini al
    shape = get_level_shape(shape_index)
    
    # Şekli grid'e dönüştür
    return shape_to_grid(shape, cols, level)


def get_level_shape(shape_index: int) -> List[str]:
    """Level indeksine göre şekil desenini döndür (0-94)
    
    Daha büyük ve güzel şekiller - kalpler, yıldızlar, hayvanlar, semboller
    """
    
    # 95 farklı şekil deseni (basit -> zor)
    # Her satır: '.' = boş, 'X' = dolu (10 karakter genişlik)
    
    SHAPES = [
        # ═══════════════════════════════════════════════════════════════
        # DÜNYA 1: KOLAY (Level 6-20)
        # Basit şekiller - boşluklar kolay erişilebilir, yan yana
        # ═══════════════════════════════════════════════════════════════
        
        # Level 6: Sol merdiven - boşluk sağda, kolay
        [
            "XXX.......",
            "XXXXX.....",
            "XXXXXXX...",
        ],
        # Level 7: Sağ merdiven
        [
            ".......XXX",
            ".....XXXXX",
            "...XXXXXXX",
        ],
        # Level 8: Orta piramit
        [
            "...XXXX...",
            "..XXXXXX..",
            ".XXXXXXXX.",
        ],
        # Level 9: İki tepe
        [
            "XXX....XXX",
            "XXXX..XXXX",
            "XXXX..XXXX",
        ],
        # Level 10 (Boss): U formu
        [
            "XXX....XXX",
            "XXX....XXX",
            "XX.XXXXX.X",
            "XXXXX..XXX",
        ],
        # Level 11: Basamak sol
        [
            "XX........",
            "XXXX......",
            "XXXXXX....",
            "XXXXXXXX..",
        ],
        # Level 12: Basamak sağ
        [
            "........XX",
            "......XXXX",
            "....XXXXXX",
            "..XXXXXXXX",
        ],
        # Level 13: Çift tepe
        [
            "..XX..XX..",
            ".XXXX.XXXX",
            "XXXXX.XXXX",
        ],
        # Level 14: Ters U
        [
            "XXXX.XXXXX",
            "XX......XX",
            "XX......XX",
        ],
        # Level 15: V şekli
        [
            "XX......XX",
            ".XXX..XXX.",
            "..XXXXXX..",
        ],
        # Level 16: Elmas
        [
            "...XXXX...",
            ".XXXXXXXX.",
            "...XXXX...",
        ],
        # Level 17: Kare çerçeve
        [
            "XXXXX.XXXX",
            "XX......XX",
            "XXXX.XXXXX",
        ],
        # Level 18: Köprü
        [
            "XXX....XXX",
            "XXXXX.XXXX",
            "XXX....XXX",
        ],
        # Level 19: Kalp
        [
            ".XX....XX.",
            "XXXX..XXXX",
            ".XXXXXXXX.",
            "..XXXXXX..",
            "...XXXX...",
        ],
        # Level 20 (Boss): Taç - ilk karmaşık
        [
            "X..X..X..X",
            "XXXX.XXXXX",
            "XX.XXXXXXX",
            ".XXXXXXXX.",
        ],
        
        # ═══════════════════════════════════════════════════════════════
        # DÜNYA 2: ORTA (Level 21-40)
        # Boşluklar iki yönde - biraz strateji gerektirir
        # ═══════════════════════════════════════════════════════════════
        
        # Level 21: Zikzak basit
        [
            "XXXXX.....",
            "..XXXXX...",
            ".....XXXXX",
        ],
        # Level 22: Ters zikzak
        [
            ".....XXXXX",
            "..XXXXX...",
            "XXXXX.....",
        ],
        # Level 23: Dalga
        [
            "XXX...XXX.",
            ".XXX...XXX",
            "XXX...XXX.",
        ],
        # Level 24: Çift dalga
        [
            "XX..XX..XX",
            ".XX..XX..X",
            "XX..XX..XX",
        ],
        # Level 25: Mini boss - Kelebek
        [
            "XXX....XXX",
            ".XXXXXXXX.",
            "XXX....XXX",
            ".XXXXXXXX.",
        ],
        # Level 26: Yıldırım
        [
            "....XXXXXX",
            "..XXXX....",
            "XXXXXX....",
            "....XXXX..",
        ],
        # Level 27: Spiral başlangıç
        [
            "XXXXXXXXX.",
            "X.........",
            "X.XXXXXXXX",
            "X.........",
        ],
        # Level 28: İç içe U
        [
            "XX......XX",
            "XX.XXXX.XX",
            "XX......XX",
            "XX.XXXX.XX",
        ],
        # Level 29: Dama başlangıç
        [
            "XX.XX.XX.X",
            ".XX.XX.XX.",
            "XX.XX.XX.X",
        ],
        # Level 30 (Boss): Ejderha
        [
            "XX........",
            "XXXX..XX..",
            "XXXX.XXXXX",
            "XXXX..XX..",
            "XX........",
        ],
        # Level 31: Üçlü dalga
        [
            "XXX..XXX..",
            "..XXX..XXX",
            "XXX..XXX..",
            "..XXX..XXX",
        ],
        # Level 32: DNA sarmal
        [
            "XX......XX",
            ".XXX..XXX.",
            "..XXXXXX..",
            ".XXX..XXX.",
            "XX......XX",
        ],
        # Level 33: Artı karmaşık
        [
            "...XXXX...",
            "XXXXX.XXXX",
            "...XXXX...",
            "XXXX.XXXXX",
            "...XXXX...",
        ],
        # Level 34: Kale mazgalları
        [
            "X.X.XX.X.X",
            "XXXX.XXXXX",
            "XX......XX",
            "XXXXX.XXXX",
        ],
        # Level 35: Anahtar deliği
        [
            "..XXXXXX..",
            ".XX....XX.",
            "..XXXXXX..",
            "....XX....",
            "..XXXXXX..",
        ],
        # Level 36: Kalkan
        [
            ".XXXXXXXX.",
            "XXXX.XXXXX",
            "XX.XXXX.XX",
            ".XXXXXXXX.",
            "..XXXXXX..",
        ],
        # Level 37: Yıldız
        [
            "....XX....",
            "..XXXXXX..",
            "XXXXX.XXXX",
            "..XXXXXX..",
            ".XX....XX.",
        ],
        # Level 38: Çift spiral
        [
            "XXXXXXXX..",
            "........XX",
            "..XXXXXXXX",
            "XX........",
        ],
        # Level 39: Labirent giriş
        [
            "XXXXXXXXX.",
            "X........X",
            "X.XXXXXX.X",
            "X........X",
            ".XXXXXXXXX",
        ],
        # Level 40 (Boss): Phoenix
        [
            "....XX....",
            "..XXXXXX..",
            "XXXXX.XXXX",
            ".XX.XX.XX.",
            "XX......XX",
        ],
        
        # ═══════════════════════════════════════════════════════════════
        # DÜNYA 3: ZOR (Level 41-60)
        # Dağınık boşluklar - strateji şart
        # ═══════════════════════════════════════════════════════════════
        
        # Level 41: Dağınık delikler
        [
            "XX.XXX.XXX",
            "XXX.XXX.XX",
            "XX.XXX.XXX",
            "XXX.XXX.XX",
        ],
        # Level 42: Çapraz delik
        [
            "X.XXXXXXXX",
            "XXX.XXXXXX",
            "XXXXX.XXXX",
            "XXXXXXX.XX",
        ],
        # Level 43: Ters çapraz
        [
            "XXXXXXXX.X",
            "XXXXXX.XXX",
            "XXXX.XXXXX",
            "XX.XXXXXXX",
        ],
        # Level 44: Dama 2x2
        [
            "XX..XX..XX",
            "XX..XX..XX",
            "..XX..XX..",
            "..XX..XX..",
        ],
        # Level 45: Mini boss - Kare tuzak
        [
            "XXX..XXXXX",
            "XXX..XXXXX",
            "XXXXX..XXX",
            "XXXXX..XXX",
        ],
        # Level 46: Çoklu delik
        [
            "X.XX.XX.XX",
            "XX.XX.XX.X",
            "X.XX.XX.XX",
            "XX.XX.XX.X",
        ],
        # Level 47: Spiral zor
        [
            "XXXXXXXXX.",
            "X.XXXXXXXX",
            "X.X.......",
            "X.XXXXXXX.",
            ".........X",
        ],
        # Level 48: Köşe tuzakları
        [
            "XX......XX",
            "X.XXXXXX.X",
            "X.XXXXXX.X",
            "XX......XX",
        ],
        # Level 49: Alt üst dama
        [
            "X.X.X.X.X.",
            "XXXX.XXXXX",
            ".X.X.X.X.X",
            "XXXXX.XXXX",
        ],
        # Level 50 (Boss): Kartal
        [
            "X........X",
            "XXX....XXX",
            "XXXXX.XXXX",
            "XX.XXXX.XX",
            "X.X....X.X",
        ],
        # Level 51: Üçlü koridor
        [
            "XX..XX..XX",
            "XX..XX..XX",
            "XX..XX..XX",
            "XX..XX..XX",
        ],
        # Level 52: Kırık dama
        [
            ".XX.XX.XX.",
            "XX.XX.XX.X",
            ".XX.XX.XX.",
            "X.XX.XX.XX",
        ],
        # Level 53: Zigzag derin
        [
            "XXXX......",
            "..XXXX....",
            "....XXXX..",
            "......XXXX",
            "....XXXX..",
        ],
        # Level 54: Karmaşık dalga
        [
            "XXX..XXX..",
            "..XXX..XXX",
            ".XXX..XXX.",
            "XXX..XXX..",
        ],
        # Level 55: Dağınık tuzak - ZOR!
        [
            "X..XXX..XX",
            "XX..XXX..X",
            ".XX..XXX..",
            "X..XXX..XX",
            "XX..XXX..X",
        ],
        # Level 56: İç içe spiral
        [
            "XXXXXXXX..",
            "X......X.X",
            "X.XXXX.X.X",
            "X......X.X",
            "XXXXXXXX..",
        ],
        # Level 57: Kare içinde kare
        [
            "XXXXX.XXXX",
            "X........X",
            "X.XXXXXX.X",
            "X........X",
            "XXXX.XXXXX",
        ],
        # Level 58: Dikey kesik
        [
            "XX.XX.XX.X",
            "XX.XX.XX.X",
            "XX.XX.XX.X",
            "XX.XX.XX.X",
            "XX.XX.XX.X",
        ],
        # Level 59: Çoklu labirent
        [
            "X.XXXXXXX.",
            ".X.......X",
            "X.XXXXXXX.",
            ".X.......X",
            "X.XXXXXXX.",
        ],
        # Level 60 (Boss): Ejderha karmaşık
        [
            "X.X....X.X",
            "XXXX.XXXXX",
            "X.XXXXXX.X",
            "XXXXX.XXXX",
            ".XX.XX.XX.",
        ],
        
        # ═══════════════════════════════════════════════════════════════
        # DÜNYA 4: ÇOK ZOR (Level 61-80)
        # Stratejik boşluklar - dikkatli planlama gerekir
        # ═══════════════════════════════════════════════════════════════
        
        # Level 61: Karmaşık dama
        [
            "X.XX.X.XX.",
            ".XX.X.XX.X",
            "X.XX.X.XX.",
            ".XX.X.XX.X",
            "X.XX.X.XX.",
        ],
        # Level 62: Zikzak çoklu
        [
            "XXX...XXXX",
            "..XXX...XX",
            "XXXX...XXX",
            "...XXX...X",
        ],
        # Level 63: Çift spiral karmaşık
        [
            ".XXXXXXXX.",
            "X........X",
            "X.XXXXXX.X",
            ".X......X.",
            "XXXX.XXXXX",
        ],
        # Level 64: Alternatif koridor
        [
            "X..X..X..X",
            "X..X..X..X",
            ".XX.XX.XX.",
            "X..X..X..X",
            "X..X..X..X",
        ],
        # Level 65: Mini boss - Labirent
        [
            "XXXXXXX..X",
            "X.....X..X",
            "X.XXX.X..X",
            "X.X...X..X",
            "X.XXXXX..X",
            "X........X",
        ],
        # Level 66: Dalgalı delik
        [
            "XX..XXXXXX",
            "XXXX..XXXX",
            "XXXXXX..XX",
            "XXXX..XXXX",
            "XX..XXXXXX",
        ],
        # Level 67: Kırık çerçeve
        [
            "XXX.XX.XXX",
            "X........X",
            "X.XXXXXX.X",
            "X........X",
            "XXX.XX.XXX",
        ],
        # Level 68: Üçgen tuzak
        [
            "X.......XX",
            "XX.....XXX",
            "XXX...XXXX",
            "XXXX.XXXXX",
            "XXXXX.XXXX",
        ],
        # Level 69: Ters üçgen tuzak
        [
            "XXXXX.XXXX",
            "XXXXX.XXXX",
            "XXXX...XXX",
            "XXX.....XX",
            "XX.......X",
        ],
        # Level 70 (Boss): Karmaşık kale
        [
            "X.X.XX.X.X",
            "XXXX.XXXXX",
            "X........X",
            "X.XXXXXX.X",
            "X........X",
            "XXXXX.XXXX",
        ],
        # Level 71: Dörtlü bölme
        [
            "XXXX..XXXX",
            "XXXX..XXXX",
            "..........",
            "XXXX..XXXX",
            "XXXX..XXXX",
        ],
        # Level 72: Spiral cehennem
        [
            "XXXXXXXXX.",
            "X.........",
            "X.XXXXXXXX",
            "X.X.......",
            "X.X.XXXXXX",
            "X.X.......",
        ],
        # Level 73: Karmaşık boşluk - ZOR!
        [
            "X.XX..XX.X",
            "XX.X..X.XX",
            ".XX.XX.XX.",
            "XX.X..X.XX",
            "X.XX..XX.X",
        ],
        # Level 74: Çoklu koridor
        [
            "X..XX..XX.",
            "X..XX..XX.",
            ".XX..XX..X",
            ".XX..XX..X",
            "X..XX..XX.",
        ],
        # Level 75: Mega spiral
        [
            ".XXXXXXXXX",
            ".X.......X",
            ".X.XXXXX.X",
            ".X.X...X.X",
            ".X.XXX.X.X",
            ".X.....X.X",
        ],
        # Level 76: Kırık yıldız
        [
            "X...XX...X",
            ".X.XXXX.X.",
            "..XXXXXX..",
            ".X.XXXX.X.",
            "X...XX...X",
        ],
        # Level 77: Çift labirent
        [
            "XXXXX.XXXX",
            "X...X.X..X",
            "X.X.X.X.XX",
            "X.X...X..X",
            "X.XXXXX.XX",
        ],
        # Level 78: Kareler
        [
            "XX..XX..XX",
            "XX..XX..XX",
            "..XX..XX..",
            "..XX..XX..",
            "XX..XX..XX",
        ],
        # Level 79: Ultra zikzak
        [
            "XX....XXXX",
            ".XX....XXX",
            "..XX....XX",
            "...XX....X",
            "....XX....",
        ],
        # Level 80 (Boss): Ejderha son
        [
            "X..XXXX..X",
            "XXXX.XXXXX",
            "X.X....X.X",
            "XXXXX.XXXX",
            "X..X..X..X",
            ".XX.XX.XX.",
        ],
        
        # ═══════════════════════════════════════════════════════════════
        # DÜNYA 5: İMKANSIZ (Level 81-100)
        # En karmaşık boşluklar - master seviye strateji
        # ═══════════════════════════════════════════════════════════════
        
        # Level 81: Master dama
        [
            "X.X.X.X.X.",
            ".X.X.X.X.X",
            "X.X.X.X.X.",
            ".X.X.X.X.X",
            "X.X.X.X.X.",
        ],
        # Level 82: Ters spiral
        [
            "X.XXXXXXXX",
            "X.X......X",
            "X.X.XXXX.X",
            "X.X....X.X",
            "X.XXXXXX.X",
            "X........X",
        ],
        # Level 83: Üçlü alternatif
        [
            "X..X..X..X",
            ".X..X..X..",
            "..X..X..X.",
            "X..X..X..X",
            ".X..X..X..",
        ],
        # Level 84: Çoklu kare tuzak
        [
            "XX.XX.XX.X",
            "XX.XX.XX.X",
            ".XX.XX.XX.",
            "XX.XX.XX.X",
            "XX.XX.XX.X",
        ],
        # Level 85: Mini boss - Ultra labirent
        [
            "XXXXXXXXX.",
            "X.......X.",
            "X.XXXXX.X.",
            "X.X...X.X.",
            "X.X.X.X.X.",
            "X...X...X.",
        ],
        # Level 86: Karmaşık dalga
        [
            "XX...XX..X",
            ".XX...XX..",
            "..XX...XX.",
            "X..XX...XX",
            "XX..XX...X",
        ],
        # Level 87: Delik karnavalı
        [
            "X.X..X.X..",
            ".X.XX.X.XX",
            "X.X..X.X..",
            ".X.XX.X.XX",
            "X.X..X.X..",
        ],
        # Level 88: Üçlü spiral
        [
            ".XXXXXXXXX",
            ".X.......X",
            "XX.XXXXXX.",
            "...X....X.",
            "XXXX.XXXX.",
        ],
        # Level 89: Master koridor (yenilenmiş — daha az tekrar, denge zikzak)
        [
            "X.X.X.X.X.",
            ".X.X.X.X.X",
            "X.X.X.X.X.",
            ".X.X.X.X.X",
            "X.X.X.X.X.",
        ],
        # Level 90 (Boss): Titan
        [
            "X..XX..XX.",
            ".XX..XX..X",
            "X..XX..XX.",
            ".XX..XX..X",
            "X..XX..XX.",
            ".XX..XX..X",
        ],
        # Level 91: Mega dama
        [
            ".X.X.X.X.X",
            "X.X.X.X.X.",
            ".X.X.X.X.X",
            "X.X.X.X.X.",
            ".X.X.X.X.X",
            "X.X.X.X.X.",
        ],
        # Level 92: Ultimate spiral
        [
            "XXXXXXXX.X",
            "X......X.X",
            "X.XXXX.X.X",
            "X.X..X.X.X",
            "X.X..X.X.X",
            "X.XXXX...X",
        ],
        # Level 93: Çılgın zikzak
        [
            "X...X...X.",
            ".X...X...X",
            "X...X...X.",
            ".X...X...X",
            "X...X...X.",
            ".X...X...X",
        ],
        # Level 94: Karmaşık grid
        [
            "X.XX.XX.X.",
            ".X..X..X.X",
            "X.XX.XX.X.",
            ".X..X..X.X",
            "X.XX.XX.X.",
        ],
        # Level 95: Mini boss - Cehennem labirenti
        [
            ".X.XXXXXX.",
            ".X.X....X.",
            "XX.X.XX.X.",
            "...X.X..X.",
            "XXXX.XXXX.",
            ".........X",
        ],
        # Level 96: Final dalga
        [
            "X..X..X..X",
            ".XX.XX.XX.",
            "X..X..X..X",
            ".XX.XX.XX.",
            "X..X..X..X",
            ".XX.XX.XX.",
        ],
        # Level 97: Master tuzak
        [
            "X.X.XX.X.X",
            ".X.X..X.X.",
            "X.X.XX.X.X",
            ".X.X..X.X.",
            "X.X.XX.X.X",
            ".X.X..X.X.",
        ],
        # Level 98: Ultra karmaşık
        [
            ".XX.X.XX.X",
            "X..X.X..X.",
            ".XX.X.XX.X",
            "X..X.X..X.",
            ".XX.X.XX.X",
            "X..X.X..X.",
        ],
        # Level 99: Ölüm spirali
        [
            "X.XXXXXXX.",
            "X.X.....X.",
            "X.X.XXX.X.",
            "X.X.X.X.X.",
            "X.X...X.X.",
            "X.XXXXX.X.",
            "X.......X.",
        ],
        # Level 100 (FINAL BOSS): Evrenin Kalbi — simetrik mandala
        [
            "X.X.XX.X.X",
            ".X.X..X.X.",
            "X..X..X..X",
            ".XX.XX.XX.",
            "X..X..X..X",
            ".X.X..X.X.",
            "X.X.XX.X.X",
        ],
    ]
    
    # İndeks kontrolü
    if shape_index < 0:
        return ["XXXX..XXXX"]
    if shape_index >= len(SHAPES):
        return SHAPES[-1]  # Son şekli kullan
    
    return SHAPES[shape_index]


def shape_to_grid(shape: List[str], cols: int = 10, level: int = 1) -> List[List[int]]:
    """Şekil desenini grid formatına dönüştür.

    Faz 2: Tam dolu satır hack'i kaldırıldı. SHAPES verisi her satırda
    en az 1 boşluk içermeli (validator + test ile doğrulanır).
    Renk teması dünya başına 3-4 renge çıkarıldı.
    """
    grid = []

    # Level'a göre renk teması (her dünyada 3-4 farklı renk)
    world = (level - 1) // 20 + 1
    color_themes = {
        1: [1, 2, 4],       # Vadi: Cyan, Yellow, Green (organik)
        2: [1, 4, 6],       # Buz: Cyan, Green, Blue (soğuk)
        3: [5, 7, 2],       # Lav: Red, Orange, Yellow (sıcak)
        4: [3, 6, 1],       # Fırtına: Purple, Blue, Cyan (elektrik)
        5: [2, 7, 3, 1],    # Yıldız: Yellow, Orange, Purple, Cyan (mistik)
    }
    colors = color_themes.get(world, [1, 2])

    for row_idx, row_str in enumerate(shape):
        row_data = []

        for col_idx in range(cols):
            if col_idx < len(row_str):
                char = row_str[col_idx]
                if char == 'X':
                    # Çeşitliliği artırmak için (row*3 + col) % len(colors)
                    color = colors[(row_idx * 3 + col_idx) % len(colors)]
                    row_data.append(color)
                else:
                    row_data.append(0)
            else:
                row_data.append(0)

        grid.append(row_data)

    return grid


def get_boss_type_for_level(level_num: int) -> Optional[str]:
    """Boss/mini-boss tipini level numarasından belirle.

    Single source of truth (Faz 3): hem CampaignMode._boss_get_type, hem
    CampaignLevelSelect._draw_level_info bu fonksiyonu kullanır. Divergence
    riski tasarımsal olarak ortadan kalkar.

    Returns:
        'rain' | 'seal' | 'dark' (boss, level%10==0, level<100)
        'final' (level==100)
        'fast' | 'missing' (mini-boss, level%5==0 ama level%10!=0)
        None (normal level)
    """
    if level_num == 100:
        return 'final'
    if level_num % 10 == 0 and level_num > 0:
        # rain (10,40,70), seal (20,50,80), dark (30,60,90)
        return ('rain', 'seal', 'dark')[((level_num // 10) - 1) % 3]
    if level_num % 5 == 0 and level_num > 0:
        # fast (5,25,45,65,85), missing (15,35,55,75,95)
        return ('fast', 'missing')[(level_num // 10) % 2]
    return None


# === LEVEL VALIDATOR ===

def _validate_level_config(cfg: 'LevelConfig') -> List[str]:
    """LevelConfig için statik tutarlılık kontrolü.

    Faz 1: Çakışan kuralları rapor olarak listeler. Üretim akışını kırmaz;
    `__debug__` veya QUADRIX_DEV=1 ortamında uyarı basar.

    Returns:
        Hata mesajlarının listesi. Boş liste → konfig temiz.
    """
    errors: List[str] = []

    # 1. allowed_pieces boş olamaz
    if not cfg.allowed_pieces:
        errors.append(f"L{cfg.level}: allowed_pieces boş olamaz")

    # 2. stars dict 1, 2, 3 anahtarlarına sahip olmalı
    star_keys = set(cfg.stars.keys()) if isinstance(cfg.stars, dict) else set()
    missing_stars = {1, 2, 3} - star_keys
    if missing_stars:
        errors.append(f"L{cfg.level}: stars eksik anahtarlar={sorted(missing_stars)}")

    # 3. survival objective varsa time_limit yeterince geniş olmalı
    survival_target = None
    for obj in cfg.objectives:
        if obj.get('type') == 'survival':
            survival_target = int(obj.get('target', 0) or 0)
            break

    if survival_target is not None and cfg.time_limit is not None:
        # survival hedefi + 5s'den daha az time_limit fail garantisi yaratır
        if cfg.time_limit <= survival_target + 5:
            errors.append(
                f"L{cfg.level}: time_limit={cfg.time_limit}s survival hedefini ({survival_target}s) "
                f"karşılayamaz; en az survival_target+10s olmalı"
            )

    # 4. move_limit varsa minimum 10
    if cfg.move_limit is not None and cfg.move_limit < 10:
        errors.append(f"L{cfg.level}: move_limit={cfg.move_limit} çok küçük (minimum 10)")

    # 5. clear_garbage objective varsa garbage rows ve pattern olmalı
    has_clear_garbage = any(obj.get('type') == 'clear_garbage' for obj in cfg.objectives)
    if has_clear_garbage:
        if cfg.pre_placed_rows <= 0:
            errors.append(
                f"L{cfg.level}: clear_garbage görevi var ama pre_placed_rows={cfg.pre_placed_rows} (>0 olmalı)"
            )
        if cfg.garbage_pattern == 'none':
            errors.append(
                f"L{cfg.level}: clear_garbage görevi var ama garbage_pattern='none'"
            )

    # 6. time_limit makul (survival hariç çok kısa süreler)
    if cfg.time_limit is not None and cfg.time_limit < 20:
        errors.append(f"L{cfg.level}: time_limit={cfg.time_limit}s çok kısa (minimum 20s)")

    # 7. speed makul aralıkta (100ms - 1500ms)
    if not (100 <= cfg.speed <= 1500):
        errors.append(f"L{cfg.level}: speed={cfg.speed}ms makul aralık dışı (100-1500)")

    return errors


def validate_all_levels() -> Dict[int, List[str]]:
    """Tüm 100 level için validator çalıştır; sadece hata barındıran level'ları döndür."""
    issues: Dict[int, List[str]] = {}
    for i in range(1, 101):
        cfg = _generate_level(i)
        errs = _validate_level_config(cfg)
        if errs:
            issues[i] = errs
    return issues


# === LEVEL VERİTABANI ===

def _build_levels_dict() -> Dict[int, LevelConfig]:
    """Tüm 100 level'ı oluştur ve dev modda doğrula."""
    levels = {}
    for i in range(1, 101):
        levels[i] = _generate_level(i)

    # Dev mode validator: QUADRIX_DEV=1 veya pytest çalışıyorsa uyarı bas.
    import os, sys
    if os.environ.get('QUADRIX_DEV') == '1' or 'pytest' in sys.modules:
        problems: List[str] = []
        for i, cfg in levels.items():
            errs = _validate_level_config(cfg)
            problems.extend(errs)
        if problems:
            print('[CAMPAIGN VALIDATOR] Level config issues:')
            for p in problems:
                print(f'  - {p}')

    return levels


# Lazy loading için global değişken
_LEVELS_CACHE: Optional[Dict[int, LevelConfig]] = None


def get_levels() -> Dict[int, LevelConfig]:
    """Tüm level'ları döndür (lazy loading)"""
    global _LEVELS_CACHE
    if _LEVELS_CACHE is None:
        _LEVELS_CACHE = _build_levels_dict()
    return _LEVELS_CACHE


def get_level(level_num: int) -> Optional[LevelConfig]:
    """Belirli bir level'ı döndür"""
    levels = get_levels()
    return levels.get(level_num)


def get_total_levels() -> int:
    """Toplam level sayısını döndür"""
    return 100


def get_world_info(world_num: int) -> Dict[str, Any]:
    """Dünya bilgisini döndür"""
    world_names = _get_world_names()
    
    return {
        "number": world_num,
        "name": world_names.get(world_num, {"tr": f"Dünya {world_num}", "en": f"World {world_num}"}),
        "start_level": (world_num - 1) * 20 + 1,
        "end_level": world_num * 20,
        "total_levels": 20,
    }


# Backwards compatibility - LEVELS artık get_levels() ile alınmalı


# === DEBUG / TEST FONKSİYONLARI ===

def print_level_summary(level_num: int) -> None:
    """Level özetini yazdır (debug için)"""
    level = get_level(level_num)
    if not level:
        print(f"Level {level_num} bulunamadı!")
        return
    
    print(f"\n{'='*50}")
    print(f"LEVEL {level.level}: {level.name['tr']} ({level.name['en']})")
    print(f"{'='*50}")
    print(f"Dünya: {level.world}")
    print(f"Hız: {level.speed}ms")
    print(f"Bloklar: {', '.join(level.allowed_pieces)}")
    print(f"XP Ödülü: {level.xp_reward}")
    print(f"Boss: {'Evet' if level.is_boss else 'Hayır'}")
    
    print(f"\nGörevler:")
    for obj in level.objectives:
        print(f"  - {obj['type']}: {obj.get('target', 'N/A')}")
    
    if level.time_limit:
        print(f"\nSüre Limiti: {level.time_limit} saniye")
    if level.move_limit:
        print(f"Blok Sınırı: {level.move_limit}")
    
    if level.special_blocks:
        print(f"\nÖzel Bloklar:")
        for sb in level.special_blocks:
            print(f"  - {sb['type']}: {sb.get('count', 'N/A')}")
    
    print(f"\nYıldız Koşulları:")
    for star, cond in level.stars.items():
        print(f"  ⭐{star}: {cond['description']['tr']}")


if __name__ == "__main__":
    # Test: İlk 10 level'ı yazdır
    for i in [1, 5, 10, 25, 50, 75, 100]:
        print_level_summary(i)
