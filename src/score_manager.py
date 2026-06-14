"""High score ve istatistik yöneticisi"""
import json
import os
import sys
from datetime import datetime

from atomic_io import atomic_write_json
import constants
from data_paths import iter_legacy_paths, migrate_legacy_file, resolve_data_path

class ScoreManager:
    """Skorları ve istatistikleri yönetir"""
    
    def __init__(self, filename='highscores.json'):
        """Score manager başlat"""
        if isinstance(filename, str) and filename:
            self.filename = resolve_data_path(filename)
            if not os.path.isabs(filename) and os.path.dirname(filename) == '':
                migrate_legacy_file(self.filename, iter_legacy_paths(filename))
        else:
            self.filename = filename
            
        self.highscores = []
        self.stats = {
            'total_games': 0,
            'total_score': 0,
            'total_lines': 0,
            'max_level': 1,
            'total_tetrises': 0,
            'total_playtime': 0
        }
        self.load()
    
    def load(self):
        """Skorları yükle"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.highscores = data.get('highscores', [])
                    self.stats = data.get('stats', self.stats)
        except Exception as e:
            if getattr(constants, 'DEBUG_MODE', False):
                print(f"[UYARI] Highscores yüklenemedi: {e}")
    
    def save(self):
        """Skorları kaydet"""
        try:
            data = {
                'highscores': self.highscores,
                'stats': self.stats
            }
            atomic_write_json(self.filename, data, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[UYARI] Highscores kaydedilemedi: {e}")
    
    def add_score(self, score, lines, level, tetrises=0, playtime=0):
        """Yeni skor ekle"""
        entry = {
            'score': score,
            'lines': lines,
            'level': level,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'tetrises': tetrises
        }
        
        self.highscores.append(entry)
        self.highscores.sort(key=lambda x: x['score'], reverse=True)
        self.highscores = self.highscores[:10]  # Top 10
        
        # İstatistikleri güncelle
        self.stats['total_games'] += 1
        self.stats['total_score'] += score
        self.stats['total_lines'] += lines
        self.stats['max_level'] = max(self.stats['max_level'], level)
        self.stats['total_tetrises'] += tetrises
        self.stats['total_playtime'] += playtime
        
        self.save()
        
        # Kaçıncı sırada?
        for i, entry_check in enumerate(self.highscores):
            if entry_check['score'] == score and entry_check['date'] == entry['date']:
                return i + 1
        return None
    
    def get_top_scores(self, count=10):
        """En yüksek skorları getir"""
        return self.highscores[:count]
    
    def is_high_score(self, score):
        """Bu skor yeni rekor mu?

        Not: UI'de "YENİ REKOR" göstergesi için kullanılır.
        0 gibi anlamsız skorlar rekor sayılmamalı.
        """
        try:
            score_val = int(max(0, score or 0))
        except Exception:
            score_val = 0

        if score_val <= 0:
            return False

        try:
            entries = self.highscores or []
            best = max((int(e.get('score', 0)) for e in entries if isinstance(e, dict)), default=0)
        except Exception:
            best = 0

        # İlk skor (best=0) için >0 olanlar rekor kabul edilir.
        return score_val > int(best)
    
    def get_rank(self, score):
        """Skorun kaçıncı sırada olduğunu bul"""
        for i, entry in enumerate(self.highscores):
            if score > entry['score']:
                return i + 1
        if len(self.highscores) < 10:
            return len(self.highscores) + 1
        return None
