"""Phase 4: Online PvP mesaj doğrulama testleri.

Bozuk/eksik payload'ların oyun state'ini bozmaması ve exception
doğurmaması testte doğrulanır.
"""
from __future__ import annotations

import sys
import os
import json
import types
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# --- sys.path düzeltmesi ---
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
for p in (ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

# pygame import'u headless testte init edilmemeli. macOS'ta SDL display/audio
# init'i collection aşamasında native abort üretebiliyor; testler zaten
# online_pvp_game import'u için pygame'i stub'lıyor.
try:
    import pygame
except Exception:
    pygame = MagicMock()
    sys.modules['pygame'] = pygame

# steam_networking stub — gerçek bridge olmadan import edilebilsin
import importlib
import steam_networking as _sn


# ─── Yardımcı: minimal NetMessage ───────────────────────────────

def make_msg(payload_dict: dict, sender: int = 99):
    """Test için gerçek NetMessage nesnesi oluştur."""
    msg = _sn.NetMessage(sender=sender, payload=json.dumps(payload_dict))
    return msg


# ─── Minimal OnlinePvPGame mock kurulumu ────────────────────────

#: Stub'lanacak modüllerin listesi
_STUB_MODULES = [
    'pygame', 'board', 'pieces', 'sound', 'background',
    'background_effects', 'themes', 'retro_style', 'ui_theme',
    'localization', 'platform_utils', 'gamepad_manager',
    'achievements', 'score_manager', 'user_manager', 'steam_integration',
]


def _make_stubs() -> dict:
    """online_pvp_game'in ihtiyaç duyduğu tüm stub'ları oluştur."""
    stubs: dict = {}
    for name in _STUB_MODULES:
        stubs[name] = MagicMock()

    # from X import Y kalıpları için stub niteliklerini açıkça tanımla
    stubs['board'].Board = MagicMock()
    stubs['pieces'].Piece = MagicMock()
    stubs['pieces'].SHAPES = []
    stubs['sound'].SoundManager = MagicMock()
    stubs['background'].BackgroundManager = MagicMock()
    stubs['background_effects'].get_shared_falling_blocks_layer = MagicMock()
    stubs['themes'].ThemeManager = MagicMock()
    stubs['retro_style'].retro_style = MagicMock()
    stubs['retro_style'].retro_style.get_font = MagicMock()
    stubs['retro_style'].retro_style.draw_glass_panel = MagicMock()
    stubs['retro_style'].retro_style.get_fitting_font = MagicMock()
    stubs['ui_theme'].UIFonts = MagicMock()
    stubs['ui_theme'].UIColors = MagicMock()
    stubs['ui_theme'].UIStyle = MagicMock()
    stubs['localization'].t = lambda key, default='': default
    stubs['steam_integration'].pause_pump = MagicMock()
    stubs['steam_integration'].resume_pump = MagicMock()

    # constants: önceki testler boş stub bırakabilir — gerçek modülü yükle
    # sys.modules'ı geçici olarak temizleyip gerçek constants'ı import et
    _old_constants = sys.modules.pop('constants', None)
    try:
        import constants as _real_constants
        stubs['constants'] = _real_constants
    except ImportError:
        # Gerçek constants import edilemiyorsa minimal stub oluştur
        import types as _types
        _c = _types.ModuleType('constants')
        _c.BOARD_WIDTH = 10
        _c.BOARD_HEIGHT = 20
        _c.BLACK = (0, 0, 0)
        _c.COLORS = {}
        _c.INITIAL_FALL_SPEED = 500
        _c.FAST_FALL_SPEED = 50
        _c.SPEED_INCREASE_PER_LEVEL = 30
        _c.DEFAULT_LOCK_DELAY = 500
        _c.DAS_DELAY = 170
        _c.DAS_REPEAT = 50
        stubs['constants'] = _c
    finally:
        if _old_constants is not None:
            sys.modules['constants'] = _old_constants
        else:
            sys.modules.pop('constants', None)

    return stubs


def _build_game(opponent_id: int = 99):
    """Minimal bir OnlinePvPGame instance'ı döndürür (Pygame gerektirmez)."""
    stubs = _make_stubs()
    # Stubs'ı sys.modules'a yaz (mevcut olanlarla birlikte)
    added: list[str] = []
    for name, stub in stubs.items():
        added.append(name)
        sys.modules[name] = stub

    # Şimdi online_pvp_game'i import et (zaten yüklüyse kaldır, temizden import et)
    sys.modules.pop('online_pvp_game', None)
    mod = importlib.import_module('online_pvp_game')

    # Mock net nesnesi
    mock_net = MagicMock()
    mock_net.opponent_steam_id = opponent_id
    mock_net.get_messages = MagicMock(return_value=[])

    # OnlinePvPGame'i doğrudan __new__ ile oluştur (Pygame surface gerektirmez)
    game = object.__new__(mod.OnlinePvPGame)

    # Gerekli state'leri elle başlat
    game.net = mock_net
    game._net_initialized = True
    game.opponent_ready = False
    game.my_ready = False
    game.game_seed = 0
    game.piece_sequence = []
    game.game_over = False
    game.winner = ''
    game.opponent_score = 0
    game.opponent_lines = 0
    game.opponent_level = 1
    game.opponent_paused = False
    game.opponent_grid_snapshot = None
    game._status_msg = ''
    game._status_timer = 0.0
    game.online_state = 'playing'
    game.pending_garbage = 0
    game._garbage_gap = 0
    game.sound = MagicMock()
    game.my_board = MagicMock()

    return game, added


class _BasePvPTest(unittest.TestCase):
    """Ortak setUp/tearDown: sys.modules'ı tamamen restore eder."""

    _OPPONENT_ID: int = 99  # alt sınıflar override eder

    def setUp(self):
        # sys.modules'ın TAM anlık görüntüsünü al — restore için kullanılacak
        self._modules_snapshot = dict(sys.modules)
        self._added_mods = []
        try:
            self.game, self._added_mods = _build_game(opponent_id=self._OPPONENT_ID)
        except Exception:
            # setUp başarısız olsa bile sys.modules'ı hemen geri al
            # (Python setUp() exception fırlatırsa tearDown() ÇALIŞMAZ)
            self._restore_modules()
            raise

    def _restore_modules(self):
        """sys.modules'ı setUp öncesi haline TAM olarak döndür."""
        # 1. Snapshot'ta olmayan tüm modülleri sil (setUp sonrası eklenenler)
        for key in list(sys.modules.keys()):
            if key not in self._modules_snapshot:
                del sys.modules[key]
        # 2. Snapshot'taki TÜM modülleri geri yaz (eksik olanları ekle, değişenleri düzelt)
        for key, mod in self._modules_snapshot.items():
            sys.modules[key] = mod

    def tearDown(self):
        self._restore_modules()


class TestInvalidSenderIgnored(_BasePvPTest):
    """Bilinmeyen sender'dan gelen mesaj ignore edilmeli."""
    _OPPONENT_ID = 1001

    def test_garbage_from_unknown_sender_ignored(self):
        """Bilinmeyen sender'dan gelen GARBAGE_ATTACK işlenmemeli."""
        unknown_sender = 9999
        msgs = [make_msg({'type': 'garbage', 'lines': 4, 'gap': 3}, sender=unknown_sender)]
        self.game.net.get_messages.return_value = msgs

        before = self.game.pending_garbage
        self.game._process_messages()
        # pending_garbage değişmemiş olmalı (ignore)
        self.assertEqual(self.game.pending_garbage, before)

    def test_score_update_from_unknown_sender_ignored(self):
        """Bilinmeyen sender'dan gelen SCORE_UPDATE işlenmemeli."""
        msgs = [make_msg({'type': 'score_update', 'score': 9999, 'lines': 99, 'level': 10},
                         sender=5555)]
        self.game.net.get_messages.return_value = msgs

        self.game.opponent_score = 0
        self.game._process_messages()
        self.assertEqual(self.game.opponent_score, 0)

    def test_valid_sender_processed(self):
        """Doğru sender'dan gelen mesaj işlenmeli."""
        msgs = [make_msg({'type': 'score_update', 'score': 100, 'lines': 5, 'level': 2},
                         sender=1001)]
        self.game.net.get_messages.return_value = msgs

        self.game._process_messages()
        self.assertEqual(self.game.opponent_score, 100)


class TestLinesClamped(_BasePvPTest):
    """lines ve gap değerleri clamp edilmeli."""
    _OPPONENT_ID = 42

    def setUp(self):
        super().setUp()
        self._receive_calls = []

        def fake_receive(lines, gap):
            self._receive_calls.append((lines, gap))

        self.game._receive_garbage = fake_receive

    def test_negative_lines_clamped_to_zero(self):
        msgs = [make_msg({'type': 'garbage', 'lines': -5, 'gap': 3}, sender=42)]
        self.game.net.get_messages.return_value = msgs
        self.game._process_messages()
        self.assertTrue(len(self._receive_calls) >= 1, "Mesaj işlenmemiş")
        received_lines = self._receive_calls[0][0]
        self.assertGreaterEqual(received_lines, 0, f"lines {received_lines} < 0 — clamp edilmemiş")

    def test_huge_lines_clamped(self):
        msgs = [make_msg({'type': 'garbage', 'lines': 9999, 'gap': 3}, sender=42)]
        self.game.net.get_messages.return_value = msgs
        self.game._process_messages()
        self.assertTrue(len(self._receive_calls) >= 1, "Mesaj işlenmemiş")
        received_lines = self._receive_calls[0][0]
        self.assertLessEqual(received_lines, 20, f"lines {received_lines} > 20 — clamp edilmemiş")

    def test_negative_gap_allowed_sentinel(self):
        """gap=-1 sentinel olarak geçerlidir."""
        msgs = [make_msg({'type': 'garbage', 'lines': 2, 'gap': -1}, sender=42)]
        self.game.net.get_messages.return_value = msgs
        self.game._process_messages()
        self.assertEqual(len(self._receive_calls), 1)
        received_gap = self._receive_calls[0][1]
        # -1 sentinel geçerli (rastgele gap anlamı), korunmalı
        self.assertEqual(received_gap, -1)

    def test_huge_gap_clamped(self):
        """gap=9999 board genişliğiyle clamp edilmeli."""
        from constants import BOARD_WIDTH
        msgs = [make_msg({'type': 'garbage', 'lines': 2, 'gap': 9999}, sender=42)]
        self.game.net.get_messages.return_value = msgs
        self.game._process_messages()
        self.assertTrue(len(self._receive_calls) >= 1)
        received_gap = self._receive_calls[0][1]
        self.assertLessEqual(received_gap, BOARD_WIDTH - 1,
                             f"gap {received_gap} >= BOARD_WIDTH — clamp edilmemiş")


class TestMalformedGridIgnored(_BasePvPTest):
    """Yanlış boyutlu grid içeren BOARD_STATE mesajı ignore edilmeli."""
    _OPPONENT_ID = 77

    def test_too_few_rows(self):
        """5 satırlı grid (beklenen 20) ignore edilmeli."""
        bad_grid = [[None] * 10 for _ in range(5)]
        msgs = [make_msg({'type': 'board_state', 'grid': bad_grid,
                          'score': 0, 'lines': 0, 'level': 1}, sender=77)]
        self.game.net.get_messages.return_value = msgs
        self.game.opponent_grid_snapshot = None

        self.game._process_messages()
        self.assertIsNone(self.game.opponent_grid_snapshot,
                          "Bozuk grid snapshot'a yazılmamalıydı")

    def test_wrong_column_count(self):
        """10 satır ama her biri 5 sütun — ignore edilmeli."""
        bad_grid = [[None] * 5 for _ in range(20)]
        msgs = [make_msg({'type': 'board_state', 'grid': bad_grid,
                          'score': 0, 'lines': 0, 'level': 1}, sender=77)]
        self.game.net.get_messages.return_value = msgs
        self.game.opponent_grid_snapshot = None

        self.game._process_messages()
        self.assertIsNone(self.game.opponent_grid_snapshot,
                          "Yanlış sütun sayılı grid snapshot'a yazılmamalıydı")

    def test_grid_not_list_ignored(self):
        """grid=42 (sayı) — ignore edilmeli."""
        msgs = [make_msg({'type': 'board_state', 'grid': 42,
                          'score': 0, 'lines': 0, 'level': 1}, sender=77)]
        self.game.net.get_messages.return_value = msgs
        self.game.opponent_grid_snapshot = None

        self.game._process_messages()
        self.assertIsNone(self.game.opponent_grid_snapshot)

    def test_valid_grid_accepted(self):
        """Geçerli boyutlu grid kabul edilmeli."""
        from constants import BOARD_WIDTH, BOARD_HEIGHT
        good_grid = [[None] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
        msgs = [make_msg({'type': 'board_state', 'grid': good_grid,
                          'score': 50, 'lines': 2, 'level': 1}, sender=77)]
        self.game.net.get_messages.return_value = msgs
        self.game.opponent_grid_snapshot = None

        self.game._process_messages()
        self.assertIsNotNone(self.game.opponent_grid_snapshot,
                             "Geçerli grid snapshot'a yazılmalıydı")


class TestGameStartPiecesTooLong(_BasePvPTest):
    """1000 uzunluklu pieces listesi trimmed veya ignored olmalı."""
    _OPPONENT_ID = 55

    def setUp(self):
        super().setUp()
        self.game._start_countdown = MagicMock()

    def test_pieces_trimmed_or_ignored(self):
        huge_pieces = list(range(1000))
        msgs = [make_msg({'type': 'game_start', 'seed': 12345, 'pieces': huge_pieces},
                         sender=55)]
        self.game.net.get_messages.return_value = msgs

        self.game._process_messages()

        stored = self.game.piece_sequence
        self.assertLessEqual(len(stored), 500,
                             f"piece_sequence {len(stored)} eleman — trim/ignore bekleniyor")

    def test_valid_pieces_accepted(self):
        valid_pieces = list(range(10))
        msgs = [make_msg({'type': 'game_start', 'seed': 42, 'pieces': valid_pieces},
                         sender=55)]
        self.game.net.get_messages.return_value = msgs
        self.game._process_messages()
        # En az 1 parça kabul edilmeli
        self.assertGreater(len(self.game.piece_sequence), 0)


class TestValidMessageProcessed(_BasePvPTest):
    """Geçerli mesaj normal işlenmeli."""
    _OPPONENT_ID = 10

    def test_score_update_applied(self):
        msgs = [make_msg({'type': 'score_update', 'score': 500, 'lines': 10, 'level': 3},
                         sender=10)]
        self.game.net.get_messages.return_value = msgs
        self.game._process_messages()
        self.assertEqual(self.game.opponent_score, 500)
        self.assertEqual(self.game.opponent_lines, 10)
        self.assertEqual(self.game.opponent_level, 3)

    def test_score_clamped_within_reasonable_range(self):
        """Score aşırı büyükse clamp edilmeli ya da kabul edilmeli ama negatif olmamalı."""
        msgs = [make_msg({'type': 'score_update', 'score': -100, 'lines': 0, 'level': 1},
                         sender=10)]
        self.game.net.get_messages.return_value = msgs
        self.game._process_messages()
        self.assertGreaterEqual(self.game.opponent_score, 0,
                                "Negatif score kabul edilmemeli")


if __name__ == '__main__':
    unittest.main()
