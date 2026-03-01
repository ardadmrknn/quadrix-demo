"""Achievement (Başarı) Sistemi"""
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime

import constants
from atomic_io import atomic_write_json
from data_paths import iter_legacy_paths, migrate_legacy_file, resolve_data_path
from localization import t

# ---------------------------------------------------------------------------
# Oyun içi achievement ID → Steamworks API Name eşlemesi
# Steamworks konsolunda bu API Name'ler tanımlanmalıdır.
# ---------------------------------------------------------------------------
STEAM_ACHIEVEMENT_MAP: dict[str, str] = {
    # Başlangıç
    'first_game':       'ACH_FIRST_GAME',
    'first_line':       'ACH_FIRST_LINE',
    'first_tetris':     'ACH_FIRST_TETRIS',
    'perfect_clear':    'ACH_PERFECT_CLEAR',
    'no_mistakes':      'ACH_NO_MISTAKES',
    # Skor
    'score_1k':         'ACH_SCORE_1K',
    'score_10k':        'ACH_SCORE_10K',
    'score_50k':        'ACH_SCORE_50K',
    'score_100k':       'ACH_SCORE_100K',
    # Satırlar
    'lines_10':         'ACH_LINES_10',
    'lines_50':         'ACH_LINES_50',
    'lines_100':        'ACH_LINES_100',
    'lines_200':        'ACH_LINES_200',
    # Tetris
    'tetris_5':         'ACH_TETRIS_5',
    'tetris_10':        'ACH_TETRIS_10',
    # Level
    'level_5':          'ACH_LEVEL_5',
    'level_10':         'ACH_LEVEL_10',
    'level_15':         'ACH_LEVEL_15',
    'level_20':         'ACH_LEVEL_20',
    # Oyun sayısı
    'games_10':         'ACH_GAMES_10',
    'games_50':         'ACH_GAMES_50',
    'games_100':        'ACH_GAMES_100',
    # Combo
    'combo_5':          'ACH_COMBO_5',
    # PvP
    'pvp_first_win':    'ACH_PVP_FIRST_WIN',
    'pvp_10_wins':      'ACH_PVP_10_WINS',
    # Kampanya
    'campaign_stars_10':       'ACH_CAMPAIGN_STARS_10',
    'campaign_stars_30':       'ACH_CAMPAIGN_STARS_30',
    'campaign_stars_50':       'ACH_CAMPAIGN_STARS_50',
    'campaign_stars_100':      'ACH_CAMPAIGN_STARS_100',
    'campaign_level50_3star':  'ACH_CAMPAIGN_LVL50_3STAR',
    'campaign_level100_3star': 'ACH_CAMPAIGN_LVL100_3STAR',
    # Mod bazlı
    'sprint_sub60':        'ACH_SPRINT_SUB60',
    'sprint_sub45':        'ACH_SPRINT_SUB45',
    'ultra_50k':           'ACH_ULTRA_50K',
    'ultra_100k':          'ACH_ULTRA_100K',
    'survival_5min':       'ACH_SURVIVAL_5MIN',
    'survival_10min':      'ACH_SURVIVAL_10MIN',
    'cascade_chain_10':    'ACH_CASCADE_CHAIN_10',
    'hardcore_level10':    'ACH_HARDCORE_LEVEL10',
    'daily_7_streak':      'ACH_DAILY_7_STREAK',
    'daily_30_streak':     'ACH_DAILY_30_STREAK',
    'wide_200_lines':      'ACH_WIDE_200_LINES',
}


def resource_path(relative_path):
    """PyInstaller ile derlenen exe için doğru path'i al"""
    try:
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).resolve().parents[1]
    return os.path.normpath(str(base_path / relative_path))

# Tüm başarılar
ACHIEVEMENTS = {
    # Başlangıç başarıları
    'first_game': {
        'name': 'İlk Adım',
        'description': 'İlk oyununu tamamla',
        'icon': '🎮',
        'check': lambda stats: stats['total_games'] >= 1
    },
    'first_line': {
        'name': 'İlk Satır',
        'description': 'İlk satırını temizle',
        'icon': '📏',
        # total_lines run sonunda güncelleniyor; oyun içinde anında bildirim için max_lines da desteklenir.
        'check': lambda stats: (stats.get('max_lines', 0) >= 1) or (stats.get('total_lines', 0) >= 1)
    },
    'first_tetris': {
        'name': 'İlk Quadrix',
        'description': 'İlk 4 satırlık Quadrix\'ini yap',
        'icon': '💎',
        'check': lambda stats: stats.get('total_tetrises', 0) >= 1
    },
    
    # Skor başarıları
    'score_1k': {
        'name': 'Başlangıç',
        'description': 'Bir oyunda 1,000 puana ulaş',
        'icon': '🌟',
        'check': lambda stats: stats.get('max_score', 0) >= 1000
    },
    'score_10k': {
        'name': 'Deneyimli',
        'description': 'Bir oyunda 10,000 puana ulaş',
        'icon': '⭐',
        'check': lambda stats: stats.get('max_score', 0) >= 10000
    },
    'score_50k': {
        'name': 'Usta',
        'description': 'Bir oyunda 50,000 puana ulaş',
        'icon': '🌠',
        'check': lambda stats: stats.get('max_score', 0) >= 50000
    },
    'score_100k': {
        'name': 'Efsane',
        'description': 'Bir oyunda 100,000 puana ulaş',
        'icon': '💫',
        'check': lambda stats: stats.get('max_score', 0) >= 100000
    },
    
    # Satır başarıları
    'lines_10': {
        'name': 'Temizlikçi',
        'description': 'Bir oyunda 10 satır temizle',
        'icon': '🧹',
        'check': lambda stats: stats.get('max_lines', 0) >= 10
    },
    'lines_50': {
        'name': 'Süpürge',
        'description': 'Bir oyunda 50 satır temizle',
        'icon': '🌪️',
        'check': lambda stats: stats.get('max_lines', 0) >= 50
    },
    'lines_100': {
        'name': 'Temizlik Robotu',
        'description': 'Bir oyunda 100 satır temizle',
        'icon': '🤖',
        'check': lambda stats: stats.get('max_lines', 0) >= 100
    },
    'lines_200': {
        'name': 'Temizlik Makinesi',
        'description': 'Bir oyunda 200 satır temizle',
        'icon': '⚡',
        'check': lambda stats: stats.get('max_lines', 0) >= 200
    },
    
    # Quadrix başarıları
    'tetris_5': {
        'name': 'Quadrix Ustası',
        'description': '5 Quadrix yap',
        'icon': '🎯',
        'check': lambda stats: stats.get('total_tetrises', 0) >= 5
    },
    'tetris_10': {
        'name': 'Quadrix Tanrısı',
        'description': '10 Quadrix yap',
        'icon': '👑',
        'check': lambda stats: stats.get('total_tetrises', 0) >= 10
    },
    
    # Seviye başarıları
    'level_5': {
        'name': 'Hızlanıyor',
        'description': 'Bir oyunda seviye 5\'e ulaş',
        'icon': '🚀',
        'check': lambda stats: stats.get('max_level', 1) >= 5
    },
    'level_10': {
        'name': 'Hız Canavarı',
        'description': 'Bir oyunda seviye 10\'a ulaş',
        'icon': '⚡',
        'check': lambda stats: stats.get('max_level', 1) >= 10
    },
    'level_15': {
        'name': 'Süpersonik',
        'description': 'Bir oyunda seviye 15\'e ulaş',
        'icon': '💨',
        'check': lambda stats: stats.get('max_level', 1) >= 15
    },
    'level_20': {
        'name': 'Işık Hızı',
        'description': 'Bir oyunda seviye 20\'ye ulaş',
        'icon': '✨',
        'check': lambda stats: stats.get('max_level', 1) >= 20
    },
    
    # Oyun sayısı başarıları
    'games_10': {
        'name': 'Sadık Oyuncu',
        'description': '10 oyun oyna',
        'icon': '🎮',
        'check': lambda stats: stats.get('total_games', 0) >= 10
    },
    'games_50': {
        'name': 'Müdavim',
        'description': '50 oyun oyna',
        'icon': '🎯',
        'check': lambda stats: stats.get('total_games', 0) >= 50
    },
    'games_100': {
        'name': 'Profesyonel',
        'description': '100 oyun oyna',
        'icon': '🏆',
        'check': lambda stats: stats.get('total_games', 0) >= 100
    },
    
    # Özel başarılar
    'combo_5': {
        'name': 'Kombo Ustası',
        'description': 'Bir oyunda 5x kombo yap',
        'icon': '🔥',
        'check': lambda stats: stats.get('max_combo', 0) >= 5
    },
    'perfect_clear': {
        'name': 'Mükemmel Temizlik',
        'description': 'Tahtayı tamamen temizle',
        'icon': '💯',
        'check': lambda stats: stats.get('perfect_clears', 0) >= 1
    },
    'no_mistakes': {
        'name': 'Kusursuz',
        'description': 'Daily Challenge: No Mistakes görevini tamamla',
        'icon': '👌',
        'check': lambda stats: stats.get('perfect_game', False)
    },
    
    # PvP başarıları
    'pvp_first_win': {
        'name': 'İlk Zafer',
        'description': 'PvP\'de ilk galibiyetini al',
        'icon': '⚔️',
        'check': lambda stats: stats.get('pvp_wins', 0) >= 1
    },
    'pvp_10_wins': {
        'name': 'Savaşçı',
        'description': 'PvP\'de 10 galibiyet',
        'icon': '🛡️',
        'check': lambda stats: stats.get('pvp_wins', 0) >= 10
    },

    # Kampanya yıldız başarıları
    'campaign_stars_10': {
        'name': 'Yıldız Toplayıcı',
        'description': 'Kampanyada toplam 10 yıldız kazan',
        'icon': '⭐',
        'check': lambda stats: stats.get('campaign_total_stars', 0) >= 10
    },
    'campaign_stars_30': {
        'name': 'Yıldız Avcısı',
        'description': 'Kampanyada toplam 30 yıldız kazan',
        'icon': '🌟',
        'check': lambda stats: stats.get('campaign_total_stars', 0) >= 30
    },
    'campaign_stars_50': {
        'name': 'Yıldız Ustası',
        'description': 'Kampanyada toplam 50 yıldız kazan',
        'icon': '💫',
        'check': lambda stats: stats.get('campaign_total_stars', 0) >= 50
    },
    'campaign_stars_100': {
        'name': 'Yıldız Tanrısı',
        'description': 'Kampanyada toplam 100 yıldız kazan',
        'icon': '✨',
        'check': lambda stats: stats.get('campaign_total_stars', 0) >= 100
    },
    'campaign_level50_3star': {
        'name': 'Yarı Mükemmel',
        'description': '50. bölümü 3 yıldızla tamamla',
        'icon': '🏅',
        'check': lambda stats: stats.get('campaign_level_50_stars', 0) >= 3
    },
    'campaign_level100_3star': {
        'name': 'Efsane Kahraman',
        'description': '100. bölümü 3 yıldızla tamamla',
        'icon': '🏆',
        'check': lambda stats: stats.get('campaign_level_100_stars', 0) >= 3
    },

    # ── Mod Bazlı Başarımlar ─────────────────────────────────────────────

    # Sprint
    'sprint_sub60': {
        'name': 'Hızlı Parmaklar',
        'description': 'Sprint modunda 40 satırı 60 saniyeden kısa sürede bitir',
        'icon': '⏱️',
        'check': lambda stats: stats.get('sprint_best_time', 999) <= 60
    },
    'sprint_sub45': {
        'name': 'Işık Hızı',
        'description': 'Sprint modunda 40 satırı 45 saniyeden kısa sürede bitir',
        'icon': '⚡',
        'check': lambda stats: stats.get('sprint_best_time', 999) <= 45
    },

    # Ultra
    'ultra_50k': {
        'name': 'Ultra Usta',
        'description': 'Ultra modunda 50.000+ puan yap',
        'icon': '💪',
        'check': lambda stats: stats.get('ultra_max_score', 0) >= 50000
    },
    'ultra_100k': {
        'name': 'Ultra Efsane',
        'description': 'Ultra modunda 100.000+ puan yap',
        'icon': '👑',
        'check': lambda stats: stats.get('ultra_max_score', 0) >= 100000
    },

    # Survival
    'survival_5min': {
        'name': 'Hayatta Kalan',
        'description': 'Survival modunda 5 dakika hayatta kal',
        'icon': '🛡️',
        'check': lambda stats: stats.get('survival_max_time', 0) >= 300
    },
    'survival_10min': {
        'name': 'Sağ Kalan',
        'description': 'Survival modunda 10 dakika hayatta kal',
        'icon': '🌟',
        'check': lambda stats: stats.get('survival_max_time', 0) >= 600
    },

    # Cascade
    'cascade_chain_10': {
        'name': 'Zincir Reaksiyonu',
        'description': 'Cascade modunda 10x+ zincir combo yap',
        'icon': '🔗',
        'check': lambda stats: stats.get('cascade_max_chain', 0) >= 10
    },

    # Hardcore
    'hardcore_level10': {
        'name': 'Hardcore Savaşçı',
        'description': 'Hardcore modunda seviye 10\'a ulaş',
        'icon': '💀',
        'check': lambda stats: stats.get('hardcore_max_level', 0) >= 10
    },

    # Daily Challenge
    'daily_7_streak': {
        'name': 'Haftalık Rutin',
        'description': 'Günlük Challenge\'da 7 gün üst üste oyna',
        'icon': '📅',
        'check': lambda stats: stats.get('daily_max_streak', 0) >= 7
    },
    'daily_30_streak': {
        'name': 'Disiplin Ustası',
        'description': 'Günlük Challenge\'da 30 gün üst üste oyna',
        'icon': '🔥',
        'check': lambda stats: stats.get('daily_max_streak', 0) >= 30
    },

    # Wide
    'wide_200_lines': {
        'name': 'Geniş Açı',
        'description': 'Wide modunda tek oyunda 200 satır temizle',
        'icon': '🌐',
        'check': lambda stats: stats.get('wide_max_lines', 0) >= 200
    },
}


def get_achievement_name(achievement_id: str) -> str:
    """Başarı ismini yerelleştirilmiş olarak döndür"""
    key = f'ach_{achievement_id}_name'
    # Önce localization'da ara, yoksa ACHIEVEMENTS'taki varsayılanı kullan
    localized = t(key)
    if localized != key:  # Çeviri bulundu
        return localized
    # Fallback: ACHIEVEMENTS'taki name
    if achievement_id in ACHIEVEMENTS:
        return ACHIEVEMENTS[achievement_id].get('name', achievement_id)
    return achievement_id


def get_achievement_desc(achievement_id: str) -> str:
    """Başarı açıklamasını yerelleştirilmiş olarak döndür"""
    key = f'ach_{achievement_id}_desc'
    # Önce localization'da ara, yoksa ACHIEVEMENTS'taki varsayılanı kullan
    localized = t(key)
    if localized != key:  # Çeviri bulundu
        return localized
    # Fallback: ACHIEVEMENTS'taki description
    if achievement_id in ACHIEVEMENTS:
        return ACHIEVEMENTS[achievement_id].get('description', '')
    return ''


class AchievementManager:
    """Başarı yöneticisi"""
    
    def __init__(self, filename='achievements.json'):
        """Achievement manager başlat"""
        if isinstance(filename, str) and filename:
            self.filename = resolve_data_path(filename)
            if not os.path.isabs(filename) and os.path.dirname(filename) == '':
                migrate_legacy_file(self.filename, iter_legacy_paths(filename))
        else:
            self.filename = filename
            
        self.unlocked = {}  # {achievement_id: unlock_date}
        self.stats = {
            'total_games': 0,
            'total_lines': 0,
            'total_tetrises': 0,
            'max_score': 0,
            'max_lines': 0,
            'max_level': 1,
            'max_combo': 0,
            'perfect_clears': 0,
            'pvp_wins': 0,
            'perfect_game': False,
            'campaign_total_stars': 0,
            'campaign_level_50_stars': 0,
            'campaign_level_100_stars': 0,
        }
        self.new_achievements = []  # Yeni açılan başarılar (gösterim için)
        self.load()
    
    def load(self):
        """Başarıları yükle"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.unlocked = data.get('unlocked', {})
                    loaded_stats = data.get('stats', {})
                    
                    # Stats'ı güncelle (varsayılanlarla birleştir)
                    for key in self.stats.keys():
                        if key in loaded_stats:
                            self.stats[key] = loaded_stats[key]

                    # Mod-bazlı istatistikleri de yükle (init'te olmayabilirler)
                    _MOD_STAT_KEYS = (
                        'sprint_best_time', 'ultra_max_score', 'survival_max_time',
                        'cascade_max_chain', 'hardcore_max_level', 'wide_max_lines',
                        'daily_max_streak',
                    )
                    for mk in _MOD_STAT_KEYS:
                        if mk in loaded_stats:
                            self.stats[mk] = loaded_stats[mk]

                if constants.DEBUG_MODE:
                    print(
                        f"[OK] Başarılar yuklendi: {len(self.unlocked)} başarı acilmis"
                    )
        except Exception as e:
            print(f"[HATA] Başarılar yuklenemedi: {e}")
    
    def save(self):
        """Başarıları kaydet"""
        try:
            # Sadece gerekli istatistikleri kaydet
            clean_stats = {
                'total_games': self.stats.get('total_games', 0),
                'total_lines': self.stats.get('total_lines', 0),
                'total_tetrises': self.stats.get('total_tetrises', 0),
                'max_score': self.stats.get('max_score', 0),
                'max_lines': self.stats.get('max_lines', 0),
                'max_level': self.stats.get('max_level', 1),
                'max_combo': self.stats.get('max_combo', 0),
                'perfect_clears': self.stats.get('perfect_clears', 0),
                'pvp_wins': self.stats.get('pvp_wins', 0),
                'perfect_game': self.stats.get('perfect_game', False),
                'campaign_total_stars': self.stats.get('campaign_total_stars', 0),
                'campaign_level_50_stars': self.stats.get('campaign_level_50_stars', 0),
                'campaign_level_100_stars': self.stats.get('campaign_level_100_stars', 0),
            }

            # Mod-bazlı istatistikler (varsa kaydet)
            _MOD_STAT_KEYS = (
                'sprint_best_time', 'ultra_max_score', 'survival_max_time',
                'cascade_max_chain', 'hardcore_max_level', 'wide_max_lines',
                'daily_max_streak',
            )
            for mk in _MOD_STAT_KEYS:
                val = self.stats.get(mk)
                if val is not None and val != 0:
                    clean_stats[mk] = val
            
            data = {
                'unlocked': self.unlocked,
                'stats': clean_stats
            }
            atomic_write_json(self.filename, data, indent=2, ensure_ascii=False)
            if constants.DEBUG_MODE:
                print(
                    f"[KAYIT] Başarılar kaydedildi: {len(self.unlocked)} başarı açıldı"
                )
        except Exception as e:
            print(f"[HATA] Başarılar kaydedilemedi: {e}")
    
    def update_stats(self, **kwargs):
        """İstatistikleri güncelle ve yeni başarıları kontrol et"""
        self.new_achievements = []

        # game_mode'u ayıkla (string olduğu için generic max() ile işlenemez)
        game_mode = kwargs.pop('game_mode', None)

        # Stats güncelle
        for key, value in kwargs.items():
            # max_ ile başlayanlar için maksimum değeri sakla
            if key in ['score', 'lines', 'level', 'combo']:
                max_key = f'max_{key}'
                self.stats[max_key] = max(self.stats.get(max_key, 0), value)
            # tetrises gibi toplam değerler
            elif key in ['tetrises']:
                self.stats[f'total_{key}'] = max(self.stats.get(f'total_{key}', 0), value)
            # perfect_game gibi boolean değerler
            elif key in ['perfect_game']:
                if value:
                    self.stats[key] = True
            # Diğer değerler (pvp_wins, perfect_clears vb.)
            else:
                if isinstance(value, bool):
                    self.stats[key] = value
                else:
                    self.stats[key] = max(self.stats.get(key, 0), value)

        # ── Mod-bazlı istatistikleri game_mode'a göre hesapla ─────────────
        if game_mode:
            score = kwargs.get('score', 0)
            lines = kwargs.get('lines', 0)
            level = kwargs.get('level', 0)
            combo = kwargs.get('combo', 0)
            elapsed_seconds = kwargs.get('elapsed_seconds', 0)

            if game_mode == 'sprint' and elapsed_seconds > 0 and lines >= 40:
                # Sprint: daha düşük süre daha iyi
                cur = self.stats.get('sprint_best_time', 999)
                self.stats['sprint_best_time'] = min(cur, elapsed_seconds)

            elif game_mode == 'ultra':
                self.stats['ultra_max_score'] = max(
                    self.stats.get('ultra_max_score', 0), score)

            elif game_mode == 'survival':
                self.stats['survival_max_time'] = max(
                    self.stats.get('survival_max_time', 0), elapsed_seconds)

            elif game_mode == 'cascade':
                self.stats['cascade_max_chain'] = max(
                    self.stats.get('cascade_max_chain', 0), combo)

            elif game_mode == 'hardcore':
                self.stats['hardcore_max_level'] = max(
                    self.stats.get('hardcore_max_level', 0), level)

            elif game_mode == 'wide':
                self.stats['wide_max_lines'] = max(
                    self.stats.get('wide_max_lines', 0), lines)

        # Başarıları kontrol et
        self.check_achievements()
        self.save()
        
        return self.new_achievements
    
    def check_achievements(self):
        """Tüm başarıları kontrol et"""
        for ach_id, achievement in ACHIEVEMENTS.items():
            # Zaten açılmışsa geç
            if ach_id in self.unlocked:
                continue
            
            # Koşulu kontrol et
            try:
                if achievement['check'](self.stats):
                    self.unlock(ach_id)
            except Exception as e:
                if constants.DEBUG_MODE:
                    print(f"[UYARI] Başarı kontrolü hata ({ach_id}): {e}")
    
    def unlock(self, achievement_id):
        """Başarıyı aç ve Steam'e senkronla"""
        if achievement_id not in self.unlocked:
            self.unlocked[achievement_id] = datetime.now().strftime('%Y-%m-%d %H:%M')
            self.new_achievements.append(achievement_id)
            if constants.DEBUG_MODE:
                name = ACHIEVEMENTS.get(achievement_id, {}).get('name', achievement_id)
                print(f"[ACH] Yeni başarı: {name}")
            # Steam'e bildir
            steam_name = STEAM_ACHIEVEMENT_MAP.get(achievement_id)
            if steam_name:
                try:
                    import steam_integration
                    steam_integration.unlock_steam_achievement(steam_name)
                except Exception:
                    pass
            return True
        return False

    def sync_to_steam(self):
        """Oyundaki tüm açılmış başarımları Steam'e toplu senkronla.

        Oyun açılışında veya profil yüklendiğinde çağrılmalı.
        """
        try:
            import steam_integration
            return steam_integration.sync_all_achievements(self.unlocked, STEAM_ACHIEVEMENT_MAP)
        except Exception:
            return 0
    
    def get_achievement(self, achievement_id):
        """Başarı bilgisini al"""
        if achievement_id in ACHIEVEMENTS:
            ach = ACHIEVEMENTS[achievement_id].copy()
            ach['name'] = get_achievement_name(achievement_id)
            ach['description'] = get_achievement_desc(achievement_id)
            ach['id'] = achievement_id
            ach['unlocked'] = achievement_id in self.unlocked
            ach['unlock_date'] = self.unlocked.get(achievement_id, None)
            ach.update(self.get_achievement_progress(achievement_id))
            return ach
        return None

    def _progress_spec_for(self, achievement_id):
        """Return (stat_key, target, is_boolean) for achievements we can quantify."""
        if achievement_id == "first_game":
            return ("total_games", 1, False)
        if achievement_id == "first_line":
            return ("total_lines", 1, False)
        if achievement_id == "first_tetris":
            return ("total_tetrises", 1, False)
        if achievement_id == "perfect_clear":
            return ("perfect_clears", 1, False)
        if achievement_id == "no_mistakes":
            return ("perfect_game", 1, True)
        if achievement_id == "pvp_first_win":
            return ("pvp_wins", 1, False)

        match = re.match(r"^score_(\d+)(k)?$", achievement_id)
        if match:
            base = int(match.group(1))
            target = base * 1000 if match.group(2) else base
            return ("max_score", target, False)

        match = re.match(r"^lines_(\d+)$", achievement_id)
        if match:
            return ("max_lines", int(match.group(1)), False)

        match = re.match(r"^tetris_(\d+)$", achievement_id)
        if match:
            return ("total_tetrises", int(match.group(1)), False)

        match = re.match(r"^level_(\d+)$", achievement_id)
        if match:
            return ("max_level", int(match.group(1)), False)

        match = re.match(r"^games_(\d+)$", achievement_id)
        if match:
            return ("total_games", int(match.group(1)), False)

        match = re.match(r"^combo_(\d+)$", achievement_id)
        if match:
            return ("max_combo", int(match.group(1)), False)

        match = re.match(r"^pvp_(\d+)_wins$", achievement_id)
        if match:
            return ("pvp_wins", int(match.group(1)), False)

        match = re.match(r"^campaign_stars_(\d+)$", achievement_id)
        if match:
            return ("campaign_total_stars", int(match.group(1)), False)

        if achievement_id == "campaign_level50_3star":
            return ("campaign_level_50_stars", 3, False)

        if achievement_id == "campaign_level100_3star":
            return ("campaign_level_100_stars", 3, False)

        # ── Mod-bazlı başarımlar ──────────────────────────────────────────
        if achievement_id == "sprint_sub60":
            return ("sprint_best_time", 60, False)
        if achievement_id == "sprint_sub45":
            return ("sprint_best_time", 45, False)
        if achievement_id == "ultra_50k":
            return ("ultra_max_score", 50000, False)
        if achievement_id == "ultra_100k":
            return ("ultra_max_score", 100000, False)
        if achievement_id == "survival_5min":
            return ("survival_max_time", 300, False)
        if achievement_id == "survival_10min":
            return ("survival_max_time", 600, False)
        if achievement_id == "cascade_chain_10":
            return ("cascade_max_chain", 10, False)
        if achievement_id == "hardcore_level10":
            return ("hardcore_max_level", 10, False)
        if achievement_id == "daily_7_streak":
            return ("daily_max_streak", 7, False)
        if achievement_id == "daily_30_streak":
            return ("daily_max_streak", 30, False)
        if achievement_id == "wide_200_lines":
            return ("wide_max_lines", 200, False)

        return None

    def get_achievement_progress(self, achievement_id):
        """Return progress fields for UI.

        Always returns:
        - progress_percent (0..100)
        - progress_text (string)

        When quantifiable also returns:
        - progress_current
        - progress_target
        """
        unlocked = achievement_id in self.unlocked
        if unlocked:
            return {
                "progress_percent": 100,
                "progress_text": t('ach_progress_format', current=1, target=1, percent=100),
                "progress_current": 1,
                "progress_target": 1,
            }

        spec = self._progress_spec_for(achievement_id)
        if not spec:
            return {
                "progress_percent": 0,
                "progress_text": t('ach_progress_unknown'),
            }

        stat_key, target, is_boolean = spec
        current_raw = self.stats.get(stat_key)

        if is_boolean:
            current = 1 if bool(current_raw) else 0
        else:
            try:
                current = int(current_raw or 0)
            except Exception:
                current = 0

        safe_target = max(1, int(target))

        # Sprint gibi "düşük = iyi" başarımlarda ters progress hesapla
        _inverse_stats = ('sprint_best_time',)
        if stat_key in _inverse_stats:
            if current <= 0 or current >= 999:
                percent = 0
                shown_current = 0
            else:
                # target=60, current=80 → %75;  current=60 → %100
                percent = int(max(0, min(100, (safe_target / current) * 100)))
                shown_current = current
        else:
            percent = int(max(0, min(100, (current / safe_target) * 100)))
            shown_current = min(current, safe_target)

        return {
            "progress_current": shown_current,
            "progress_target": safe_target,
            "progress_percent": percent,
            "progress_text": t('ach_progress_format', current=shown_current, target=safe_target, percent=percent),
        }
    
    def get_all_achievements(self):
        """Tüm başarıları al"""
        achievements = []
        for ach_id in ACHIEVEMENTS.keys():
            achievements.append(self.get_achievement(ach_id))
        return achievements
    
    def get_progress(self):
        """İlerleme yüzdesini al"""
        total = len(ACHIEVEMENTS)
        unlocked = len(self.unlocked)
        return (unlocked / total * 100) if total > 0 else 0
    
    def get_new_achievements(self):
        """Yeni açılan başarıları al ve temizle"""
        new = self.new_achievements.copy()
        self.new_achievements = []
        return new
