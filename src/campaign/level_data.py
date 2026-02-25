"""100 Level Campaign Verisi

Her level progresif olarak zorlaşır:
- Düşme hızı artar
- Görev hedefleri artar
- Yeni mekanikler eklenir
- Blok çeşitliliği artar

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
        # Skor hedefi: ~100 puan/blok ortalama üzerinden
        estimated_blocks = target // 80
        base_blocks = int(estimated_blocks * multiplier)
    elif obj_type == 'tetris':
        # Quadrix yapmak zor - her Quadrix ~8-10 blok gerektirir
        base_blocks = int(target * 10 * multiplier)
    elif obj_type == 'combo':
        # Combo: Ardışık temizleme gerektirir
        base_blocks = int(target * 8 * multiplier)
    elif obj_type == 'clear_garbage':
        # Çöp temizleme: Hedef otomatik ayarlanır, bol blok ver
        base_blocks = int(max(target, 15) * multiplier)
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


def _calculate_speed(level: int) -> int:
    """Level'a göre düşme hızını hesapla (ms)"""
    # Level 1: 900ms, Level 100: 400ms (progresif azalma)
    base_speed = 900
    min_speed = 400
    speed_decrease_per_level = 5
    
    speed = base_speed - (level * speed_decrease_per_level)
    return max(min_speed, speed)


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
    """Level'a göre izin verilen blokları döndür"""
    all_pieces = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']
    
    if level <= 3:
        return ['I', 'O', 'T']  # Sadece basit bloklar
    elif level <= 6:
        return ['I', 'O', 'T', 'L']
    elif level <= 10:
        return ['I', 'O', 'T', 'L', 'J']
    elif level <= 15:
        return ['I', 'O', 'T', 'L', 'J', 'S']
    else:
        return all_pieces  # Tüm bloklar


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
        },
        2: {
            "tr": "Buz Diyarı",
            "en": "Ice Realm",
            "de": "Eisreich",
            "fr": "Royaume de Glace",
            "es": "Reino de Hielo",
            "it": "Regno di Ghiaccio",
            "pt": "Reino de Gelo",
        },
        3: {
            "tr": "Lav Mağarası",
            "en": "Lava Caves",
            "de": "Lavahöhlen",
            "fr": "Grottes de Lave",
            "es": "Cuevas de Lava",
            "it": "Grotte di Lava",
            "pt": "Cavernas de Lava",
        },
        4: {
            "tr": "Fırtına Kalesi",
            "en": "Storm Fortress",
            "de": "Sturmfestung",
            "fr": "Forteresse de la Tempête",
            "es": "Fortaleza de la Tormenta",
            "it": "Fortezza della Tempesta",
            "pt": "Fortaleza da Tempestade",
        },
        5: {
            "tr": "Yıldız Kulesi",
            "en": "Star Tower",
            "de": "Sternenturm",
            "fr": "Tour des Étoiles",
            "es": "Torre de las Estrellas",
            "it": "Torre delle Stelle",
            "pt": "Torre das Estrelas",
        },
    }


def _generate_level(level: int) -> LevelConfig:
    """Dinamik olarak level konfigürasyonu oluştur"""
    world = _get_world(level)
    speed = _calculate_speed(level)
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
    if level == 16:
        move_limit = 40
    elif level == 17:
        for obj in objectives:
            if obj.get('type') == 'tetris':
                obj['target'] = 1
    elif level == 22:
        if 3 in stars and stars[3]['type'] == 'time_limit':
            stars[3]['value'] = 80
            stars[3]['description'] = {"tr": "80s içinde tamamla", "en": "Complete in 80s"}
    elif level == 23:
        if 3 in stars and stars[3]['type'] == 'time_limit':
            stars[3]['value'] = 90
            stars[3]['description'] = {"tr": "90s içinde tamamla", "en": "Complete in 90s"}
    elif level == 24:
        move_limit = 40
    elif level == 25:
        objectives = [{"type": "score", "target": 6000}]
        if 3 in stars and stars[3]['type'] == 'time_limit':
            stars[3]['value'] = 80
            stars[3]['description'] = {"tr": "80s içinde tamamla", "en": "Complete in 80s"}
    elif level == 26:
        objectives = [{"type": "clear_lines", "target": 15}]
        move_limit = 60
    elif level == 27:
        objectives = [{"type": "score", "target": 7000}]
    elif level == 29:
        objectives = [{"type": "score", "target": 10000}]
    elif level == 30:
        for obj in objectives:
            if obj.get('type') == 'tetris':
                obj['target'] = 3
    
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
        10: {"tr": "İlk Sınav", "en": "First Trial", "de": "First Trial", "fr": "First Trial", "es": "First Trial", "it": "First Trial", "pt": "First Trial"},
        20: {"tr": "Buz Efendisi", "en": "Ice Lord", "de": "Ice Lord", "fr": "Ice Lord", "es": "Ice Lord", "it": "Ice Lord", "pt": "Ice Lord"},
        30: {"tr": "Kilit Ustası", "en": "Lock Master", "de": "Lock Master", "fr": "Lock Master", "es": "Lock Master", "it": "Lock Master", "pt": "Lock Master"},
        40: {"tr": "Patlama Kralı", "en": "Blast King", "de": "Blast King", "fr": "Blast King", "es": "Blast King", "it": "Blast King", "pt": "Blast King"},
        50: {"tr": "Zaman Bekçisi", "en": "Time Guardian", "de": "Time Guardian", "fr": "Time Guardian", "es": "Time Guardian", "it": "Time Guardian", "pt": "Time Guardian"},
        60: {"tr": "Lav Ejderhası", "en": "Lava Dragon", "de": "Lava Dragon", "fr": "Lava Dragon", "es": "Lava Dragon", "it": "Lava Dragon", "pt": "Lava Dragon"},
        70: {"tr": "Fırtına Lordu", "en": "Storm Lord", "de": "Storm Lord", "fr": "Storm Lord", "es": "Storm Lord", "it": "Storm Lord", "pt": "Storm Lord"},
        80: {"tr": "Gölge Şövalyesi", "en": "Shadow Knight", "de": "Shadow Knight", "fr": "Shadow Knight", "es": "Shadow Knight", "it": "Shadow Knight", "pt": "Shadow Knight"},
        90: {"tr": "Yıldız Prensi", "en": "Star Prince", "de": "Star Prince", "fr": "Star Prince", "es": "Star Prince", "it": "Star Prince", "pt": "Star Prince"},
        100: {"tr": "Son Mücadele", "en": "Final Showdown", "de": "Final Showdown", "fr": "Final Showdown", "es": "Final Showdown", "it": "Final Showdown", "pt": "Final Showdown"},
    }
    
    if is_boss and level in boss_names:
        return boss_names[level]
    
    # Normal level isimleri - World'e göre
    world = _get_world(level)
    world_level = ((level - 1) % 20) + 1  # Her dünyada 1-20
    
    world_prefixes = {
        1: {"tr": "Vadi", "en": "Valley", "de": "Tal", "fr": "Vallée", "es": "Valle", "it": "Valle", "pt": "Vale"},
        2: {"tr": "Buz", "en": "Ice", "de": "Eis", "fr": "Glace", "es": "Hielo", "it": "Ghiaccio", "pt": "Gelo"},
        3: {"tr": "Lav", "en": "Lava", "de": "Lava", "fr": "Lave", "es": "Lava", "it": "Lava", "pt": "Lava"},
        4: {"tr": "Fırtına", "en": "Storm", "de": "Sturm", "fr": "Tempête", "es": "Tormenta", "it": "Tempesta", "pt": "Tempestade"},
        5: {"tr": "Yıldız", "en": "Star", "de": "Stern", "fr": "Étoile", "es": "Estrella", "it": "Stella", "pt": "Estrela"},
    }
    
    prefix = world_prefixes.get(world, {"tr": "Level", "en": "Level", "de": "Level", "fr": "Niveau", "es": "Nivel", "it": "Livello", "pt": "Nível"})
    
    return {
        "tr": f"{prefix['tr']} {world_level}",
        "en": f"{prefix['en']} {world_level}",
        "de": f"{prefix['de']} {world_level}",
        "fr": f"{prefix['fr']} {world_level}",
        "es": f"{prefix['es']} {world_level}",
        "it": f"{prefix['it']} {world_level}",
        "pt": f"{prefix['pt']} {world_level}",
    }


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
            "description": {"tr": f"{survival_time} saniye hayatta kal", "en": f"Survive {survival_time} seconds"}
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
            "description": {"tr": "Süre içinde tamamla", "en": "Complete in time"}
        })
    
    elif objective_type == 'no_gaps':
        # Boşluk bırakmadan temizle
        lines_target = _calculate_lines_target(level) // 2
        objectives.append({
            "type": "perfect_clear",
            "target": lines_target,
            "description": {"tr": f"{lines_target} satırı sıfır boşlukla", "en": f"{lines_target} lines with no gaps"}
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
            "XXXXXXXXXX",
        ],
        # Level 10 (Boss): U formu
        [
            "XXX....XXX",
            "XXX....XXX",
            "XXXXXXXXXX",
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
        ],
        # Level 14: Ters U
        [
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
            "XX......XX",
            "XXXXXXXXXX",
        ],
        # Level 18: Köprü
        [
            "XXX....XXX",
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
            "...XXXX...",
            "XXXXXXXXXX",
            "...XXXX...",
        ],
        # Level 34: Kale mazgalları
        [
            "X.X.XX.X.X",
            "XXXXXXXXXX",
            "XX......XX",
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
            "XX.XXXX.XX",
            ".XXXXXXXX.",
            "..XXXXXX..",
        ],
        # Level 37: Yıldız
        [
            "....XX....",
            "..XXXXXX..",
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
            ".X.X.X.X.X",
            "XXXXXXXXXX",
        ],
        # Level 50 (Boss): Kartal
        [
            "X........X",
            "XXX....XXX",
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
            "X........X",
            "X.XXXXXX.X",
            "X........X",
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
            "X.XXXXXX.X",
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
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
            "XXXXXXXXXX",
        ],
        # Level 69: Ters üçgen tuzak
        [
            "XXXXXXXXXX",
            "XXXXX.XXXX",
            "XXXX...XXX",
            "XXX.....XX",
            "XX.......X",
        ],
        # Level 70 (Boss): Karmaşık kale
        [
            "X.X.XX.X.X",
            "XXXXXXXXXX",
            "X........X",
            "X.XXXXXX.X",
            "X........X",
            "XXXXXXXXXX",
        ],
        # Level 71: Dörtlü bölme
        [
            "XXXX..XXXX",
            "XXXX..XXXX",
            "...........",
            "XXXX..XXXX",
            "XXXX..XXXX",
        ],
        # Level 72: Spiral cehennem
        [
            "XXXXXXXXX.",
            "X..........",
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
            "XXXXXXXXXX",
            "X.X....X.X",
            "XXXXXXXXXX",
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
        # Level 89: Master koridor
        [
            "X.X.X.X.X.",
            "X.X.X.X.X.",
            ".X.X.X.X.X",
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
        # Level 100 (FINAL BOSS): Evrenin Kalbi - EN ZOR
        [
            "X.X.X.X.X.",
            ".X.X.X.X.X",
            "X.X.X.X.X.",
            ".X.X.X.X.X",
            "X.X.X.X.X.",
            ".X.X.X.X.X",
            "X.X.X.X.X.",
        ],
    ]
    
    # İndeks kontrolü
    if shape_index < 0:
        return ["XXXX..XXXX"]
    if shape_index >= len(SHAPES):
        return SHAPES[-1]  # Son şekli kullan
    
    return SHAPES[shape_index]


def shape_to_grid(shape: List[str], cols: int = 10, level: int = 1) -> List[List[int]]:
    """Şekil desenini grid formatına dönüştür
    
    ÖNEMLİ: Her satırda en az 1 boşluk olmalı yoksa satır temizlenemez!
    """
    grid = []
    
    # Level'a göre renk (her level için tutarlı)
    # Dünya bazlı renk teması
    world = (level - 1) // 20 + 1
    color_themes = {
        1: [1, 2],      # Dünya 1: Cyan, Yellow
        2: [1, 4],      # Dünya 2: Cyan, Green 
        3: [5, 7],      # Dünya 3: Red, Orange
        4: [3, 6],      # Dünya 4: Purple, Blue
        5: [2, 7],      # Dünya 5: Yellow (gold), Orange
    }
    colors = color_themes.get(world, [1, 2])
    
    for row_idx, row_str in enumerate(shape):
        row_data = []
        filled_count = 0
        
        for col_idx in range(cols):
            if col_idx < len(row_str):
                char = row_str[col_idx]
                if char == 'X':
                    # Alternatif renk (dama deseni)
                    color = colors[(row_idx + col_idx) % 2]
                    row_data.append(color)
                    filled_count += 1
                else:
                    row_data.append(0)
            else:
                row_data.append(0)
        
        # ÖNEMLİ: Eğer satır tamamen doluysa, rastgele 1-2 hücreyi boş yap
        # Bu olmadan satır temizlenemez!
        if filled_count >= cols:
            # Satırda en az 1 boşluk olmalı - ortaya yakın bir yere boşluk ekle
            gap_pos = cols // 2 + (row_idx % 3) - 1  # Her satırda farklı pozisyon
            if 0 <= gap_pos < cols:
                row_data[gap_pos] = 0
        
        grid.append(row_data)
    
    return grid


# === LEVEL VERİTABANI ===

def _build_levels_dict() -> Dict[int, LevelConfig]:
    """Tüm 100 level'ı oluştur"""
    levels = {}
    for i in range(1, 101):
        levels[i] = _generate_level(i)
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
