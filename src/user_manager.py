"""Kullanıcı profil yönetim sistemi"""
import json
import os
from datetime import datetime, date

from atomic_io import atomic_write_json
from data_paths import iter_legacy_paths, migrate_legacy_file, resolve_data_path
from localization import t

DAILY_MAX_FAILURES = 3
DAILY_HISTORY_LIMIT = 40

class UserManager:
    """Kullanıcı profilleri yöneticisi"""
    
    def __init__(self, users_file='users.json'):
        """Kullanıcı yöneticisini başlat"""
        if isinstance(users_file, str) and users_file:
            self.users_file = resolve_data_path(users_file)
            if not os.path.isabs(users_file) and os.path.dirname(users_file) == '':
                migrate_legacy_file(self.users_file, iter_legacy_paths(users_file))
        else:
            self.users_file = users_file
        self.users = {}
        self.current_user = None
        self.load_users()

    def _resolve_profile_file(self, username: str, key: str, fallback: str) -> str:
        profile = self.users.get(username)
        if not isinstance(profile, dict):
            return resolve_data_path(fallback)
        raw = profile.get(key) or fallback
        resolved = resolve_data_path(str(raw))
        if resolved != raw:
            profile[key] = resolved
        return resolved
    
    def load_users(self):
        """Kullanıcıları yükle"""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.users = data.get('users', {})
                    self.current_user = data.get('current_user', None)
                # Schema migrate: yeni alanları eski profillere ekle
                updated = False
                # Tüm desteklenen modlar
                all_modes = ['classic', 'sprint', 'ultra', 'zen', 'tetris2', 'mystery', 'wide', 'survival', 'cascade', 'hardcore', 'daily']
                for _name, profile in (self.users or {}).items():
                    if isinstance(profile, dict) and 'hold_piece_counts' not in profile:
                        profile['hold_piece_counts'] = {}
                        updated = True
                    if isinstance(profile, dict) and 'tutorial_completed' not in profile:
                        profile['tutorial_completed'] = False
                        updated = True
                    # Steam ID alanı (yeni alan — eski profiller için None)
                    if isinstance(profile, dict) and 'steam_id' not in profile:
                        profile['steam_id'] = None
                        updated = True
                    # Eksik modları game_stats'a ekle
                    if isinstance(profile, dict):
                        game_stats = profile.get('game_stats', {})
                        for mode in all_modes:
                            if mode not in game_stats:
                                game_stats[mode] = {'games': 0, 'score': 0, 'lines': 0}
                                updated = True
                        # pvp modu için ayrı kontrol
                        if 'pvp' not in game_stats:
                            game_stats['pvp'] = {'games': 0, 'wins': 0, 'losses': 0}
                            updated = True
                        profile['game_stats'] = game_stats
                if updated:
                    self.save_users()
            else:
                self.users = {}
                self.current_user = None
        except Exception as e:
            print(f"Kullanıcılar yüklenirken hata: {e}")
            self.users = {}
            self.current_user = None
    
    def save_users(self):
        """Kullanıcıları kaydet"""
        try:
            data = {
                'users': self.users,
                'current_user': self.current_user
            }
            atomic_write_json(self.users_file, data, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Kullanıcılar kaydedilirken hata: {e}")

    def _ensure_daily_status(self, username=None):
        """Aktif kullanıcı için günlük durumunu hazırla"""
        user = username or self.current_user
        if not user or user not in self.users:
            return None
        profile = self.users[user]
        updated = False
        if 'daily_status' not in profile:
            profile['daily_status'] = {
                'date': None,
                'fails': 0,
                'completed': False,
                # Günlük seri (streak): artar, gün kaçırılırsa sıfırlanır.
                'streak': 0,
                'last_completed': None,
                # Son günlük sonuçlar (en fazla DAILY_HISTORY_LIMIT kayıt)
                # {'date': 'YYYY-MM-DD', 'success': bool, 'challenge_id': str}
                'history': [],
            }
            updated = True
        status = profile['daily_status']

        # Backward-compat: eski profillere alan ekle
        if 'streak' not in status:
            status['streak'] = 0
            updated = True
        if 'last_completed' not in status:
            status['last_completed'] = None
            updated = True
        if 'history' not in status or not isinstance(status.get('history'), list):
            status['history'] = []
            updated = True

        today = date.today().isoformat()
        prev_date = status.get('date')
        if prev_date != today:
            # Gün değiştiyse: önce streak kırılmasını değerlendir
            try:
                if prev_date:
                    prev_d = date.fromisoformat(str(prev_date))
                    today_d = date.fromisoformat(str(today))
                    gap = (today_d - prev_d).days
                    if gap >= 1 and not status.get('completed'):
                        status['streak'] = 0
                    elif gap > 1:
                        # Gün atlandıysa streak sıfırlansın
                        status['streak'] = 0
            except Exception:
                pass

            status['date'] = today
            status['fails'] = 0
            status['completed'] = False
            updated = True
        if updated:
            self.save_users()
        return status

    def can_play_daily(self, username=None):
        """Daily Challenge erişimi var mı?"""
        status = self._ensure_daily_status(username)
        if status is None:
            return False, t('daily_no_user')
        if status.get('completed'):
            return False, t('daily_completed')
        if status.get('fails', 0) >= DAILY_MAX_FAILURES:
            return False, t('daily_no_attempts')
        return True, None

    def _upsert_daily_history(self, status, success, challenge_id=None):
        """Bugün için tekil günlük sonucu history'ye yaz/yenile."""
        history = status.get('history')
        if not isinstance(history, list):
            history = []
            status['history'] = history

        today = date.today().isoformat()
        existing_idx = None
        for idx in range(len(history) - 1, -1, -1):
            item = history[idx]
            if isinstance(item, dict) and str(item.get('date') or '') == today:
                existing_idx = idx
                break

        entry = {
            'date': today,
            'success': bool(success),
        }
        if challenge_id:
            entry['challenge_id'] = str(challenge_id)

        if existing_idx is None:
            history.append(entry)
        else:
            prev = history[existing_idx] if isinstance(history[existing_idx], dict) else {}
            prev_success = bool(prev.get('success'))
            # Aynı gün başarı geldiyse başarısız kaydı başarıya yükselt.
            entry['success'] = bool(success) or prev_success
            if not entry.get('challenge_id') and prev.get('challenge_id'):
                entry['challenge_id'] = str(prev.get('challenge_id'))
            history[existing_idx] = entry

        if len(history) > DAILY_HISTORY_LIMIT:
            status['history'] = history[-DAILY_HISTORY_LIMIT:]

    def register_daily_result(self, success, username=None, challenge_id=None):
        """Daily Challenge sonucu kaydet"""
        status = self._ensure_daily_status(username)
        if status is None:
            return
        if success:
            # Aynı günde tekrar çağrılırsa streak'i tekrar artırma
            if not status.get('completed'):
                today = date.today()
                last_completed = status.get('last_completed')
                try:
                    last_d = date.fromisoformat(str(last_completed)) if last_completed else None
                except Exception:
                    last_d = None

                if last_d and (today - last_d).days == 1:
                    status['streak'] = int(status.get('streak', 0) or 0) + 1
                else:
                    status['streak'] = 1
                status['last_completed'] = today.isoformat()
            status['completed'] = True
            self._upsert_daily_history(status, True, challenge_id=challenge_id)
        else:
            status['fails'] = status.get('fails', 0) + 1
            if status['fails'] >= DAILY_MAX_FAILURES:
                self._upsert_daily_history(status, False, challenge_id=challenge_id)
        self.save_users()

    def get_daily_status(self, username=None):
        """Daily Challenge durumunu oku"""
        status = self._ensure_daily_status(username)
        if status is None:
            return None
        return dict(status)
    
    def create_user(self, username, avatar=None):
        """Yeni kullanıcı oluştur"""
        if not username or username.strip() == '':
            return False, t('user_create_empty')
        
        if username in self.users:
            return False, t('user_create_exists')
        
        if len(username) > 20:
            return False, t('user_create_too_long')
        
        # Yeni kullanıcı oluştur
        self.users[username] = {
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'avatar': avatar or '👤',
            'avatar_color': (100, 150, 255),  # Varsayılan renk
            'bio': '',  # Kısa açıklama
            'favorite_mode': 'Classic',
            'total_games': 0,
            'total_score': 0,
            'total_lines': 0,
            'total_tetrises': 0,
            'total_combos': 0,
            'highest_combo': 0,
            'highest_level': 1,
            'total_playtime': 0,  # Saniye cinsinden
            'last_played': None,
            'neural_fragments': 0,
            # Hold (C) ile saklanan parça sayaçları
            # Örn: {'I': 12, 'T': 7}
            'hold_piece_counts': {},
            'achievements_file': resolve_data_path(f'achievements_{username}.json'),
            'highscores_file': resolve_data_path(f'highscores_{username}.json'),
            'game_stats': {
                'classic': {'games': 0, 'score': 0, 'lines': 0},
                'sprint': {'games': 0, 'score': 0, 'lines': 0},
                'ultra': {'games': 0, 'score': 0, 'lines': 0},
                'zen': {'games': 0, 'score': 0, 'lines': 0},
                'tetris2': {'games': 0, 'score': 0, 'lines': 0},
                'mystery': {'games': 0, 'score': 0, 'lines': 0},
                'wide': {'games': 0, 'score': 0, 'lines': 0},
                'survival': {'games': 0, 'score': 0, 'lines': 0},
                'cascade': {'games': 0, 'score': 0, 'lines': 0},
                'hardcore': {'games': 0, 'score': 0, 'lines': 0},
                'daily': {'games': 0, 'score': 0, 'lines': 0},
                'pvp': {'games': 0, 'wins': 0, 'losses': 0}
            },
            'tutorial_completed': False
        }
        
        # İlk kullanıcı ise otomatik seç
        if len(self.users) == 1:
            self.current_user = username
        
        self.save_users()
        return True, t('user_create_success')

    def record_hold_piece(self, piece_name: str, username=None):
        """C ile yapılan hold işlemlerinde saklanan parça istatistiğini kaydet."""
        user = username or self.current_user
        if not user or user not in self.users:
            return
        if not piece_name:
            return
        profile = self.users[user]
        counts = profile.get('hold_piece_counts')
        if not isinstance(counts, dict):
            counts = {}
            profile['hold_piece_counts'] = counts
        counts[piece_name] = int(counts.get(piece_name, 0) or 0) + 1
        self.save_users()

    def get_user_by_steam_id(self, steam_id: str) -> str | None:
        """Steam ID ile kullanıcı adını bul (persona adı değişse bile çalışır)."""
        if not steam_id:
            return None
        sid = str(steam_id)
        for username, profile in self.users.items():
            if isinstance(profile, dict) and str(profile.get('steam_id', '')) == sid:
                return username
        return None

    def set_steam_id(self, username: str, steam_id: str) -> None:
        """Mevcut profile Steam ID bağla (birleştirme veya geç-bağlama için)."""
        if username in self.users and isinstance(self.users[username], dict):
            self.users[username]['steam_id'] = str(steam_id) if steam_id else None
            self.save_users()

    def delete_user(self, username):
        """Kullanıcıyı sil"""
        if username not in self.users:
            return False, t('user_delete_not_found')
        
        # Başarım ve skor dosyalarını sil
        try:
            achievements_file = self._resolve_profile_file(username, 'achievements_file', f'achievements_{username}.json')
            if os.path.exists(achievements_file):
                os.remove(achievements_file)
            
            highscores_file = self._resolve_profile_file(username, 'highscores_file', f'highscores_{username}.json')
            if os.path.exists(highscores_file):
                os.remove(highscores_file)
        except Exception as e:
            print(f"Dosyalar silinirken hata: {e}")
        
        # Kullanıcıyı sil
        del self.users[username]
        
        # Eğer silinense aktif kullanıcıysa, başka biri seç
        if self.current_user == username:
            if self.users:
                self.current_user = list(self.users.keys())[0]
            else:
                self.current_user = None
        
        self.save_users()
        return True, t('user_deleted')
    
    def select_user(self, username):
        """Aktif kullanıcıyı değiştir"""
        if username not in self.users:
            return False, t('user_select_not_found')
        
        self.current_user = username
        self.save_users()
        return True, t('user_selected', username=username)
    
    def get_current_user(self):
        """Aktif kullanıcıyı al"""
        return self.current_user
    
    def get_user_data(self, username=None):
        """Kullanıcı verilerini al"""
        user = username or self.current_user
        if user and user in self.users:
            return self.users[user]
        return None
    
    def get_all_users(self):
        """Tüm kullanıcıları al"""
        return self.users
    
    def get_mode_highscore(self, mode: str, username=None) -> int:
        """Belirli bir oyun modunun en yüksek skorunu döndür"""
        user = username or self.current_user
        if user and user in self.users:
            game_stats = self.users[user].get('game_stats', {})
            mode_stats = game_stats.get(mode, {})
            # Önce highscores listesinden bak
            highscores = mode_stats.get('highscores', [])
            if highscores:
                return max(entry.get('score', 0) for entry in highscores)
            # Fallback: eski best_score alanı
            return mode_stats.get('best_score', 0)
        return 0
    
    def get_mode_highscores(self, mode: str, username=None, limit: int = 5) -> list:
        """Belirli bir oyun modunun en yüksek skor listesini döndür (max 5 skor)"""
        user = username or self.current_user
        if user and user in self.users:
            game_stats = self.users[user].get('game_stats', {})
            mode_stats = game_stats.get(mode, {})
            highscores = mode_stats.get('highscores', [])
            # Skora göre sırala ve limit'e kırp
            sorted_scores = sorted(highscores, key=lambda x: x.get('score', 0), reverse=True)
            return sorted_scores[:limit]
        return []
    
    def add_mode_highscore(self, mode: str, score: int, lines: int = 0, level: int = 1, username=None) -> int:
        """Bir oyun moduna yeni skor ekle. En yüksek 5 skoru tutar. Sıralama döndürür (1-5) veya None."""
        if score <= 0:
            return None
        user = username or self.current_user
        if not user or user not in self.users:
            return None
        
        game_stats = self.users[user].get('game_stats', {})
        if mode not in game_stats:
            game_stats[mode] = {'games': 0, 'score': 0, 'lines': 0}
        
        mode_stats = game_stats[mode]
        
        # Highscores listesini al veya oluştur
        if 'highscores' not in mode_stats:
            mode_stats['highscores'] = []
        
        highscores = mode_stats['highscores']
        
        # Yeni skoru ekle
        new_entry = {
            'score': score,
            'lines': lines,
            'level': level,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M')
        }
        highscores.append(new_entry)
        
        # Skora göre sırala
        highscores.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # En yüksek 5'i tut
        mode_stats['highscores'] = highscores[:5]
        
        # best_score alanını da güncelle (geriye uyumluluk)
        if highscores:
            mode_stats['best_score'] = highscores[0].get('score', 0)
        
        self.save_users()
        
        # Sıralama döndür (1-5 arası, veya None eğer listede değilse)
        for i, entry in enumerate(mode_stats['highscores']):
            if entry['score'] == score and entry['date'] == new_entry['date']:
                return i + 1
        return None
    
    def update_user_stats(self, username=None, games=0, score=0, lines=0, tetrises=0, combos=0, highest_combo=0, level=1, playtime=0, mode='classic'):
        """Kullanıcı istatistiklerini güncelle"""
        user = username or self.current_user
        if user and user in self.users:
            self.users[user]['total_games'] += games
            self.users[user]['total_score'] += score
            self.users[user]['total_lines'] += lines
            self.users[user]['total_tetrises'] += tetrises
            self.users[user]['total_combos'] += combos
            if highest_combo > self.users[user]['highest_combo']:
                self.users[user]['highest_combo'] = highest_combo
            if level > self.users[user]['highest_level']:
                self.users[user]['highest_level'] = level
            self.users[user]['total_playtime'] += playtime
            self.users[user]['last_played'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Mod bazlı istatistikler
            if mode in self.users[user]['game_stats']:
                if mode == 'pvp':
                    self.users[user]['game_stats'][mode]['games'] += games
                else:
                    self.users[user]['game_stats'][mode]['games'] += games
                    self.users[user]['game_stats'][mode]['score'] += score
                    self.users[user]['game_stats'][mode]['lines'] += lines
                    
                    # Highscores listesine ekle (en yüksek 5 skor)
                    if score > 0:
                        self.add_mode_highscore(mode, score, lines, level, user)
                        # add_mode_highscore zaten save_users çağırıyor, burada tekrar çağırmaya gerek yok
                        return
            
            self.save_users()

    def add_fragments(self, amount: int, username=None):
        """Add neural fragments to user's wallet."""
        user = username or self.current_user
        if user and user in self.users:
            current = self.users[user].get('neural_fragments', 0) or 0
            self.users[user]['neural_fragments'] = int(current + amount)
            self.save_users()

    def add_xp(self, mode: str, amount: int, username=None):
        """Add XP for a per-mode progression (simple key)."""
        user = username or self.current_user
        if user and user in self.users:
            stats = self.users[user].get('game_stats', {})
            mode_stats = stats.get(mode)
            if mode_stats is None:
                current_xp = self.users[user].get('xp', 0) or 0
                self.users[user]['xp'] = int(current_xp + amount)
            else:
                current_xp = int(mode_stats.get('xp', 0) or 0)
                current_level = int(mode_stats.get('level', 1) or 1)
                current_xp += int(amount)
                # Level-up logic using required XP formula
                def req_xp(lvl):
                    return int(100 * (1.15 ** (lvl - 1)))
                leveled = False
                while current_xp >= req_xp(current_level):
                    current_xp -= req_xp(current_level)
                    current_level += 1
                    leveled = True
                mode_stats['xp'] = int(current_xp)
                mode_stats['level'] = int(current_level)
                if leveled:
                    # update highest level if global
                    if current_level > self.users[user].get('highest_level', 1):
                        self.users[user]['highest_level'] = current_level
            self.save_users()
    
    def update_pvp_stats(self, username=None, win=False):
        """PvP istatistiklerini güncelle"""
        user = username or self.current_user
        if user and user in self.users:
            self.users[user]['game_stats']['pvp']['games'] += 1
            if win:
                self.users[user]['game_stats']['pvp']['wins'] += 1
            else:
                self.users[user]['game_stats']['pvp']['losses'] += 1
            self.save_users()
    
    def update_user_avatar(self, username, new_avatar, color=None):
        """Kullanıcı avatarını güncelle"""
        if username not in self.users:
            return False, t('user_select_not_found')
        
        self.users[username]['avatar'] = new_avatar
        if color:
            self.users[username]['avatar_color'] = color
        self.save_users()
        return True, t('user_avatar_updated')
    
    def update_user_profile(self, username, **kwargs):
        """Kullanıcı profilini güncelle"""
        if username not in self.users:
            return False, t('user_select_not_found')
        
        # Güncellenebilir alanlar
        allowed_fields = ['avatar', 'avatar_color', 'bio', 'favorite_mode']
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                self.users[username][key] = value
        
        self.save_users()
        return True, t('user_profile_updated')
    
    def has_users(self):
        """Hiç kullanıcı var mı?"""
        return len(self.users) > 0
    
    def get_achievements_file(self, username=None):
        """Kullanıcının başarım dosyasını al"""
        user = username or self.current_user
        if user and user in self.users:
            return self._resolve_profile_file(user, 'achievements_file', f'achievements_{user}.json')

        fallback = resolve_data_path('achievements.json')
        migrate_legacy_file(fallback, iter_legacy_paths('achievements.json'))
        return fallback
    
    def get_highscores_file(self, username=None):
        """Kullanıcının skor dosyasını al"""
        user = username or self.current_user
        if user and user in self.users:
            return self._resolve_profile_file(user, 'highscores_file', f'highscores_{user}.json')

        fallback = resolve_data_path('highscores.json')
        migrate_legacy_file(fallback, iter_legacy_paths('highscores.json'))
        return fallback
    
    def is_tutorial_completed(self, username=None):
        """Kullanıcının tutorial'ı tamamlayıp tamamlamadığını kontrol et"""
        user = username or self.current_user
        if user and user in self.users:
            return self.users[user].get('tutorial_completed', False)
        return False

    def set_tutorial_completed(self, completed=True, username=None):
        """Kullanıcının tutorial durumunu güncelle"""
        user = username or self.current_user
        if user and user in self.users:
            self.users[user]['tutorial_completed'] = completed
            self.save_users()

    # ── Kart kullanım istatistikleri ──────────────────────────────

    def record_card_usage(self, card_id: str, card_title: str = '', username=None):
        """Mystery modunda seçilen kartın kullanım sayısını artır."""
        user = username or self.current_user
        if not user or user not in self.users:
            return
        card_usage = self.users[user].get('card_usage', {})
        if not isinstance(card_usage, dict):
            card_usage = {}
        entry = card_usage.get(card_id, {'count': 0, 'title': card_title})
        entry['count'] = int(entry.get('count', 0) or 0) + 1
        if card_title:
            entry['title'] = card_title
        card_usage[card_id] = entry
        self.users[user]['card_usage'] = card_usage
        self.save_users()

    def get_favorite_card(self, username=None) -> dict | None:
        """En çok seçilen kartın bilgilerini döndür: {'id': str, 'title': str, 'count': int} veya None."""
        user = username or self.current_user
        if not user or user not in self.users:
            return None
        card_usage = self.users[user].get('card_usage', {})
        if not isinstance(card_usage, dict) or not card_usage:
            return None
        best_id, best_entry = max(card_usage.items(), key=lambda x: int(x[1].get('count', 0) or 0))
        count = int(best_entry.get('count', 0) or 0)
        if count <= 0:
            return None
        return {'id': best_id, 'title': best_entry.get('title', best_id), 'count': count}
