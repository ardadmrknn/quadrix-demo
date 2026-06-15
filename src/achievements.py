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
import localization

def t(key: str, default: str = None, **kwargs) -> str:
    import sys
    loc = sys.modules.get('localization', localization)
    return loc.t(key, default, **kwargs)

# ---------------------------------------------------------------------------
# Oyun içi achievement ID → Steamworks API Name eşlemesi
# Steamworks konsolunda bu API Name'ler tanımlanmalıdır.
# ---------------------------------------------------------------------------
STEAM_ACHIEVEMENT_MAP: dict[str, str] = {
    # Başlangıç
    'first_game':       'ACH_FIRST_GAME',
    'first_line':       'ACH_FIRST_LINE',
    'first_tetris':     'ACH_FIRST_TETRIS',
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
    
    # PvP başarıları
    'pvp_first_win': {
        'name': 'İlk Zafer',
        'description': 'Online PvP\'de ilk galibiyetini al',
        'icon': '⚔️',
        'check': lambda stats: stats.get('pvp_wins', 0) >= 1
    },
    'pvp_10_wins': {
        'name': 'Savaşçı',
        'description': 'Online PvP\'de 10 galibiyet',
        'icon': '🛡️',
        'check': lambda stats: stats.get('pvp_wins', 0) >= 10
    },

    # Kampanya yıldız başarıları
    'campaign_stars_10': {
        'name': 'Yıldız Toplayıcı',
        'description': 'Görev modunda toplam 10 yıldız kazan',
        'icon': '⭐',
        'check': lambda stats: stats.get('campaign_total_stars', 0) >= 10
    },
    'campaign_stars_30': {
        'name': 'Yıldız Avcısı',
        'description': 'Görev modunda toplam 30 yıldız kazan',
        'icon': '🌟',
        'check': lambda stats: stats.get('campaign_total_stars', 0) >= 30
    },
    'campaign_stars_50': {
        'name': 'Yıldız Ustası',
        'description': 'Görev modunda toplam 50 yıldız kazan',
        'icon': '💫',
        'check': lambda stats: stats.get('campaign_total_stars', 0) >= 50
    },
    'campaign_stars_100': {
        'name': 'Yıldız Tanrısı',
        'description': 'Görev modunda toplam 100 yıldız kazan',
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
        'description': 'Sprint modunda 40 satırı 240 saniyeden kısa sürede bitir',
        'icon': '⏱️',
        'check': lambda stats: stats.get('sprint_best_time', 999) <= 240
    },
    'sprint_sub45': {
        'name': 'Sprint Uzmanı',
        'description': 'Sprint modunda 40 satırı 200 saniyeden kısa sürede bitir',
        'icon': '⚡',
        'check': lambda stats: stats.get('sprint_best_time', 999) <= 200
    },

    # Ultra
    'ultra_50k': {
        'name': 'Ultra Usta',
        'description': 'Ultra modunda 10.000+ puan yap',
        'icon': '💪',
        'check': lambda stats: stats.get('ultra_max_score', 0) >= 10000
    },
    'ultra_100k': {
        'name': 'Ultra Efsane',
        'description': 'Ultra modunda 15.000+ puan yap',
        'icon': '👑',
        'check': lambda stats: stats.get('ultra_max_score', 0) >= 15000
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


# Başarımların tamamlanması durumunda verilecek Lunar (Nöral Parça) ödül miktarları
ACHIEVEMENT_REWARDS = {
    # Starter (100 Lunar)
    'first_game': 100,
    'first_line': 100,
    'first_tetris': 100,
    
    # Common (150 Lunar)
    'score_1k': 150,
    'lines_10': 150,
    'level_5': 150,
    'games_10': 150,
    
    # Rare (300 Lunar)
    'score_10k': 300,
    'lines_50': 300,
    'tetris_5': 300,
    'level_10': 300,
    'games_50': 300,
    'combo_5': 300,
    
    # Epic (500 Lunar)
    'score_50k': 500,
    'lines_100': 500,
    'level_15': 500,
    'games_100': 500,
    'pvp_first_win': 500,
    'campaign_stars_10': 500,
    'campaign_stars_30': 500,
    'sprint_sub60': 500,
    'ultra_50k': 500,
    'survival_5min': 500,
    
    # Legendary (1000 Lunar)
    'score_100k': 1000,
    'lines_200': 1000,
    'tetris_10': 1000,
    'level_20': 1000,
    'pvp_10_wins': 1000,
    'campaign_stars_50': 1000,
    'campaign_stars_100': 1000,
    'campaign_level50_3star': 1000,
    'campaign_level100_3star': 1000,
    'sprint_sub45': 1000,
    'ultra_100k': 1000,
    'survival_10min': 1000,
    'cascade_chain_10': 1000,
    'hardcore_level10': 1000,
    'daily_7_streak': 1000,
    'daily_30_streak': 1000,
    'wide_200_lines': 1000,
}


class AchievementManager:
    """Başarı yöneticisi"""
    
    def __init__(self, filename='achievements.json', user_manager=None):
        """Achievement manager başlat"""
        if isinstance(filename, str) and filename:
            self.filename = resolve_data_path(filename)
            if not os.path.isabs(filename) and os.path.dirname(filename) == '':
                migrate_legacy_file(self.filename, iter_legacy_paths(filename))
        else:
            self.filename = filename
            
        self.unlocked = {}  # {achievement_id: unlock_date}
        self.claimed_rewards = set()  # Kazanılan ödülleri takip eden küme
        self.user_manager = user_manager
        self.stats = {
            'total_games': 0,
            'total_lines': 0,
            'total_tetrises': 0,
            'max_score': 0,
            'max_lines': 0,
            'max_level': 1,
            'max_combo': 0,
            'pvp_wins': 0,
            'campaign_total_stars': 0,
            'campaign_level_50_stars': 0,
            'campaign_level_100_stars': 0,
        }
        self.new_achievements = []  # Yeni açılan başarılar (gösterim için)
        self.load()
        if self.user_manager:
            self.grant_unclaimed_rewards()
            
    def grant_unclaimed_rewards(self):
        """Geriye dönük veya kazanılan ancak henüz verilmeyen Lunar ödüllerini topluca profile yazar."""
        if not self.user_manager or not hasattr(self.user_manager, 'add_fragments'):
            return
        updated = False
        for ach_id in list(self.unlocked.keys()):
            if ach_id in ACHIEVEMENT_REWARDS and ach_id not in self.claimed_rewards:
                reward = ACHIEVEMENT_REWARDS[ach_id]
                if reward > 0:
                    try:
                        self.user_manager.add_fragments(reward)
                        self.claimed_rewards.add(ach_id)
                        updated = True
                    except Exception as e:
                        if constants.DEBUG_MODE:
                            print(f"[UYARI] Geriye dönük başarım ödülü verilemedi ({ach_id}): {e}")
        if updated:
            self.save()
    
    def load(self):
        """Başarıları yükle"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    loaded_unlocked = data.get('unlocked', {})
                    if isinstance(loaded_unlocked, dict):
                        self.unlocked = {
                            achievement_id: unlock_date
                            for achievement_id, unlock_date in loaded_unlocked.items()
                            if achievement_id in ACHIEVEMENTS
                        }
                    else:
                        self.unlocked = {}
                    
                    loaded_claimed = data.get('claimed_rewards', [])
                    if isinstance(loaded_claimed, list):
                        self.claimed_rewards = set(loaded_claimed)
                    else:
                        self.claimed_rewards = set()
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
                'pvp_wins': self.stats.get('pvp_wins', 0),
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
                'unlocked': {
                    achievement_id: unlock_date
                    for achievement_id, unlock_date in self.unlocked.items()
                    if achievement_id in ACHIEVEMENTS
                },
                'claimed_rewards': list(getattr(self, 'claimed_rewards', set())),
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
            # Diğer değerler
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

        # İstatistikleri Steam'e senkronla
        self.sync_stats_to_steam()
        
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
                else:
                    # Açılmadıysa ilerleme bildirimi gönder (kademeli başarımlar)
                    self.indicate_steam_progress(ach_id)
            except Exception as e:
                if constants.DEBUG_MODE:
                    print(f"[UYARI] Başarı kontrolü hata ({ach_id}): {e}")
    
    def unlock(self, achievement_id):
        """Başarıyı aç, Lunar ödülü ver ve Steam'e senkronla"""
        if achievement_id not in self.unlocked:
            self.unlocked[achievement_id] = datetime.now().strftime('%Y-%m-%d %H:%M')
            self.new_achievements.append(achievement_id)
            if constants.DEBUG_MODE:
                name = ACHIEVEMENTS.get(achievement_id, {}).get('name', achievement_id)
                print(f"[ACH] Yeni başarı: {name}")
            
            # Lunar ödülü ver
            um = getattr(self, 'user_manager', None)
            claimed = getattr(self, 'claimed_rewards', None)
            if um and hasattr(um, 'add_fragments'):
                if achievement_id in ACHIEVEMENT_REWARDS and (claimed is None or achievement_id not in claimed):
                    reward = ACHIEVEMENT_REWARDS[achievement_id]
                    if reward > 0:
                        try:
                            um.add_fragments(reward)
                            if claimed is not None:
                                claimed.add(achievement_id)
                        except Exception as e:
                            if constants.DEBUG_MODE:
                                print(f"[UYARI] Başarım ödülü verilemedi ({achievement_id}): {e}")
            
            # Değişiklikleri hemen kaydet
            self.save()

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
        """Oyundaki tüm açılmış başarımları ve istatistikleri Steam'e toplu senkronla.

        Oyun açılışında veya profil yüklendiğinde çağrılmalı.
        """
        try:
            import steam_integration
            ach_count = steam_integration.sync_all_achievements(self.unlocked, STEAM_ACHIEVEMENT_MAP)
            stat_count = steam_integration.sync_stats_to_steam(self.stats)
            return ach_count + stat_count
        except Exception:
            return 0

    def sync_stats_to_steam(self):
        """Sadece istatistikleri Steam'e senkronla.

        Oyun sonu gibi stat güncellemelerinden sonra çağrılmalı.
        """
        try:
            import steam_integration
            return steam_integration.sync_stats_to_steam(self.stats)
        except Exception:
            return 0

    def indicate_steam_progress(self, achievement_id: str):
        """Belirli kilometre taşlarında Steam Overlay'de ilerleme bildirimi göster.

        Yıldız toplama, satır temizleme gibi kademeli başarımlarda
        %25, %50, %75 noktalarında kullanıcıya toast gösterir.
        """
        if achievement_id in self.unlocked:
            return  # Zaten açıkmış, bildirme

        steam_name = STEAM_ACHIEVEMENT_MAP.get(achievement_id)
        if not steam_name:
            return

        spec = self._progress_spec_for(achievement_id)
        if not spec:
            return

        stat_key, target, is_boolean = spec
        if is_boolean:
            return  # Boolean başarımlarda ilerleme gösterme

        current_raw = self.stats.get(stat_key, 0)
        try:
            current = int(current_raw or 0)
        except Exception:
            return

        # Sprint gibi ters istatistiklerde ilerleme bildirimi gösterme
        _inverse_stats = ('sprint_best_time',)
        if stat_key in _inverse_stats:
            return

        # Sadece belirli yüzdelerde bildir (%25, %50, %75)
        if target <= 0:
            return
        pct = (current / target) * 100
        _MILESTONES = (25, 50, 75)
        # Tam milestone'a denk geliyorsa veya çok yakınsa bildir
        for ms in _MILESTONES:
            if abs(pct - ms) < 2:  # %2 tolerans
                try:
                    import steam_integration
                    steam_integration.indicate_achievement_progress(
                        steam_name, current, target
                    )
                except Exception:
                    pass
                break
    
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
            return ("sprint_best_time", 240, False)
        if achievement_id == "sprint_sub45":
            return ("sprint_best_time", 200, False)
        if achievement_id == "ultra_50k":
            return ("ultra_max_score", 10000, False)
        if achievement_id == "ultra_100k":
            return ("ultra_max_score", 15000, False)
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
        unlocked = sum(1 for achievement_id in self.unlocked if achievement_id in ACHIEVEMENTS)
        return (unlocked / total * 100) if total > 0 else 0
    
    def get_new_achievements(self):
        """Yeni açılan başarıları al ve temizle"""
        new = self.new_achievements.copy()
        self.new_achievements = []
        return new
