# -*- coding: utf-8 -*-
"""Eğitim modu iyileştirmeleri (FAZ A-E) için hedefli testler.

Kapsam:
- FAZ A: Hub ders metadata entry'leri + ders detay paneli yardımcıları
- FAZ B: 3 seçenekli davet popup'ı dönüş değerleri
- FAZ C: Briefing state varsayılanları ve akışı
- FAZ E: Zengin sonuç paneli pedagojik alanları
"""

from __future__ import annotations

import importlib
import os
import sys
import types
import unittest
from unittest import mock


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def _ensure_real_module(module_name: str):
    existing = sys.modules.get(module_name)
    module_path = getattr(existing, '__file__', '') if existing is not None else ''
    if existing is not None and (not module_path or os.path.abspath(module_path).startswith(os.path.abspath(SRC_DIR)) is False):
        sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


tutorial_module = _ensure_real_module('tutorial')
tutorial_lessons = _ensure_real_module('tutorial_lessons')
TutorialMode = tutorial_module.TutorialMode


class TestHubLessonMetadata(unittest.TestCase):
    """FAZ A: Ölü metadata'nın hub entry'lerine taşınması."""

    def _build_progress_tutorial(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.user_manager = None
        tutorial.hub_progress_snapshot = tutorial_module.build_default_tutorial_progress()
        return tutorial

    def test_hub_lesson_entries_carry_metadata(self):
        tutorial = self._build_progress_tutorial()
        entries = TutorialMode._get_hub_lesson_entries(tutorial, 'quick_start')
        self.assertTrue(entries)
        first = entries[0]
        for key in ('why_it_matters', 'duration_seconds', 'skill_tags', 'difficulty', 'lesson_type'):
            self.assertIn(key, first)
        # qs_move_lane referans değerleri
        move_entry = next(e for e in entries if e['lesson'].get('id') == 'qs_move_lane')
        self.assertEqual(move_entry['duration_seconds'], 15)
        self.assertEqual(move_entry['difficulty'], 1)
        self.assertEqual(move_entry['lesson_type'], 'drill')
        self.assertIn('movement', move_entry['skill_tags'])
        self.assertTrue(move_entry['why_it_matters'])

    def test_lesson_type_label_is_localized_with_fallback(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            self.assertEqual(tutorial._lesson_type_label('drill'), 'Alıştırma')
            self.assertEqual(tutorial._lesson_type_label('exam'), 'Sınav')
            # Bilinmeyen tip → başlık biçimine düşer, patlamaz
            self.assertEqual(tutorial._lesson_type_label('weird_kind'), 'Weird Kind')
            self.assertEqual(tutorial._lesson_type_label(''), '')

    def test_skill_tag_label_handles_unknown_tags(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        # Bilinen etiket gerçek lokalizasyon üzerinden gelir (varsayılan dil tr).
        self.assertEqual(tutorial._skill_tag_label('movement'), 'Hareket')
        # Bilinmeyen etiket fallback başlık biçimine düşer, patlamaz.
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            self.assertEqual(tutorial._skill_tag_label('unknown_skill'), 'Unknown Skill')
            self.assertEqual(tutorial._skill_tag_label(''), '')

    def test_get_selected_hub_lesson_entry_resolves_active_selection(self):
        tutorial = self._build_progress_tutorial()
        tutorial.hub_selected_chapter_id = 'quick_start'
        tutorial.hub_selected_lesson_id = 'qs_rotate_fit'
        entry = TutorialMode._get_selected_hub_lesson_entry(tutorial)
        self.assertIsNotNone(entry)
        self.assertEqual(entry['lesson'].get('id'), 'qs_rotate_fit')

    def test_get_selected_hub_lesson_entry_returns_none_without_selection(self):
        tutorial = self._build_progress_tutorial()
        tutorial.hub_selected_chapter_id = None
        tutorial.hub_selected_lesson_id = None
        self.assertIsNone(TutorialMode._get_selected_hub_lesson_entry(tutorial))


class TestBriefingState(unittest.TestCase):
    """FAZ C: Briefing state varsayılanları ve akışı."""

    def test_briefing_state_attributes_have_safe_defaults(self):
        # __new__ ile kurulan nesnede getattr savunması AttributeError üretmemeli.
        tutorial = TutorialMode.__new__(TutorialMode)
        self.assertFalse(getattr(tutorial, 'briefing_active', False))
        self.assertIsNone(getattr(tutorial, 'briefing_data', None))
        self.assertEqual(getattr(tutorial, 'lesson_stage', 'play'), 'play')

    def test_prepare_lesson_briefing_builds_payload(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.lesson_attempt_counts = {}
        tutorial.lesson_catalog = tutorial_lessons.get_lessons()
        lesson = tutorial_lessons.get_lesson('surface_gap_fill')
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            data = TutorialMode._prepare_lesson_briefing(tutorial, lesson)
        self.assertIsInstance(data, dict)
        self.assertTrue(data.get('title'))
        self.assertTrue(data.get('why'))
        self.assertEqual(data.get('difficulty'), lesson.get('difficulty'))
        self.assertEqual(data.get('duration_seconds'), lesson.get('duration_seconds'))
        # FAZ C+: briefing artık hedef listesi ve ders sayacı içerir.
        self.assertTrue(data.get('objectives'))
        self.assertGreaterEqual(data.get('lesson_index', 0), 1)
        self.assertEqual(data.get('lesson_total'), len(tutorial.lesson_catalog))

    def test_legacy_step_briefing_includes_howto_guide(self):
        # FAZ 6 — İlk derslerde başlat panelinde 'nasıl yapılır' tuş rehberi olmalı.
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.lesson_attempt_counts = {}
        tutorial.lesson_catalog = tutorial_lessons.get_lessons()
        tutorial._action_key_label = lambda action, fallback=None, include_down_for_soft=False: {
            'move_left': 'SOL', 'move_right': 'SAĞ', 'rotate': 'YUKARI',
            'soft_drop': 'AŞAĞI', 'hard_drop': 'SPACE', 'hold': 'C',
        }.get(action, 'TUŞ')
        lesson = tutorial_lessons.get_lesson('qs_move_lane')
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key) or key):
            data = TutorialMode._prepare_lesson_briefing(tutorial, lesson)
        self.assertTrue(data.get('how_to'))

    def test_scenario_lesson_briefing_has_no_howto(self):
        # Senaryo derslerinde tuş rehberi yoktur (yalnız legacy step'lerde).
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.lesson_attempt_counts = {}
        tutorial.lesson_catalog = tutorial_lessons.get_lessons()
        tutorial._action_key_label = lambda *a, **k: 'TUŞ'
        lesson = tutorial_lessons.get_lesson('surface_gap_fill')
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            data = TutorialMode._prepare_lesson_briefing(tutorial, lesson)
        self.assertFalse(data.get('how_to'))

    def _build_lesson_flow_tutorial(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.lesson_lookup = {}
        tutorial.briefing_active = False
        tutorial.briefing_data = None
        tutorial._pending_briefing_lesson_id = None
        tutorial.briefing_seen_lessons = set()
        tutorial.lesson_stage = 'play'
        tutorial.lesson_attempt_counts = {}
        tutorial.in_transition = False
        tutorial.waiting_for_enter = False
        tutorial.lesson_result_active = False
        tutorial.lesson_result = None
        tutorial.card_choice_state = {}
        tutorial.sound = types.SimpleNamespace(play=lambda *_a, **_k: None)
        return tutorial

    def test_start_lesson_opens_briefing_and_sets_up_board(self):
        # Yeni akış: briefing açılırken tahta KURULUR (arka plan doğru seviye),
        # ama briefing_active=True ile oyun durur.
        tutorial = self._build_lesson_flow_tutorial()
        committed = {}
        tutorial._commit_lesson_setup = lambda lesson, keep_briefing=False: committed.update(
            {'lesson': lesson, 'keep_briefing': keep_briefing})
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            TutorialMode._start_lesson(tutorial, 'surface_gap_fill')
        self.assertTrue(tutorial.briefing_active)
        self.assertEqual(tutorial.lesson_stage, 'briefing')
        self.assertEqual(tutorial._pending_briefing_lesson_id, 'surface_gap_fill')
        # Tahta briefing açılırken kuruldu (keep_briefing=True).
        self.assertEqual(committed.get('lesson', {}).get('id'), 'surface_gap_fill')
        self.assertTrue(committed.get('keep_briefing'))

    def test_confirm_briefing_dismisses_and_marks_seen(self):
        tutorial = self._build_lesson_flow_tutorial()
        committed = {'count': 0}
        def _commit(lesson, keep_briefing=False):
            committed['count'] += 1
            committed['lesson'] = lesson
        tutorial._commit_lesson_setup = _commit
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            TutorialMode._start_lesson(tutorial, 'surface_gap_fill')
            TutorialMode._confirm_lesson_briefing(tutorial)
        self.assertFalse(tutorial.briefing_active)
        self.assertEqual(tutorial.lesson_stage, 'play')
        # Kurulum yalnız 1 kez (briefing açılışında); confirm tekrar kurmaz.
        self.assertEqual(committed['count'], 1)
        self.assertIn('surface_gap_fill', tutorial.briefing_seen_lessons)

    def test_second_play_auto_skips_briefing(self):
        tutorial = self._build_lesson_flow_tutorial()
        committed = []
        tutorial._commit_lesson_setup = lambda lesson, keep_briefing=False: committed.append(
            (lesson, keep_briefing))
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            # İlk oynanış: briefing açılır (tahta keep_briefing ile kurulur), onaylanır.
            TutorialMode._start_lesson(tutorial, 'surface_gap_fill')
            TutorialMode._confirm_lesson_briefing(tutorial)
            # İkinci oynanış: briefing otomatik atlanır, doğrudan kurulum (keep_briefing=False).
            TutorialMode._start_lesson(tutorial, 'surface_gap_fill')
        self.assertFalse(tutorial.briefing_active)
        self.assertEqual(len(committed), 2)
        self.assertTrue(committed[0][1])   # ilk: keep_briefing=True
        self.assertFalse(committed[1][1])  # ikinci: keep_briefing=False (doğrudan)

    def test_skip_briefing_exits_to_menu(self):
        # FAZ 6 — Briefing 'Çıkış' dersi başlatmaz, ana menüye döner.
        tutorial = self._build_lesson_flow_tutorial()
        committed = {}
        tutorial._commit_lesson_setup = lambda lesson, keep_briefing=False: committed.update(
            {'lesson': lesson, 'keep_briefing': keep_briefing})
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            TutorialMode._start_lesson(tutorial, 'surface_gap_fill')
            result = TutorialMode._skip_lesson_briefing(tutorial)
        self.assertFalse(tutorial.briefing_active)
        self.assertEqual(result, 'menu')


class TestBoardHighlightAndObjectives(unittest.TestCase):
    """FAZ D: Board highlight setup ve canlı hedef durumları."""

    def _make_board_like(self, occupancy, lines_cleared=0):
        return types.SimpleNamespace(occupancy=occupancy, lines_cleared=lines_cleared)

    def test_setup_board_highlight_reads_placements(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board_highlight_duration_s = 3.0
        scenario = {'highlight_placements': [['T', 2, 3]]}
        # 1. denemede highlight gösterilmez (2 başarısızlık beklenir).
        TutorialMode._setup_board_highlight(tutorial, scenario, attempt_count=1)
        self.assertIsNotNone(tutorial.board_highlight_spec)
        self.assertEqual(tutorial.board_highlight_spec['placements'], [['T', 2, 3]])
        self.assertEqual(tutorial.board_highlight_timer, 0.0)
        self.assertFalse(tutorial._board_highlight_allowed)

    def test_setup_board_highlight_shows_after_two_fails(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board_highlight_duration_s = 3.0
        scenario = {'highlight_placements': [['T', 2, 3]]}
        TutorialMode._setup_board_highlight(tutorial, scenario, attempt_count=3)
        self.assertGreater(tutorial.board_highlight_timer, 0.0)
        self.assertTrue(tutorial._board_highlight_allowed)

    def test_setup_board_highlight_shows_for_normal_lesson_on_attempt_two(self):
        # FAZ 4 — Normal (sınav olmayan) derste 1 başarısızlıktan sonra highlight gelir.
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board_highlight_duration_s = 3.0
        scenario = {'highlight_placements': [['T', 2, 3]]}
        lesson = {'lesson_type': 'board_puzzle', 'id': 'surface_gap_fill'}
        TutorialMode._setup_board_highlight(tutorial, scenario, lesson=lesson, attempt_count=2)
        self.assertTrue(tutorial._board_highlight_allowed)
        self.assertGreater(tutorial.board_highlight_timer, 0.0)

    def test_setup_board_highlight_exam_hidden_on_attempt_two(self):
        # FAZ 4 — Sınavda attempt 2'de hâlâ gizli; yalnız attempt 3+ gösterilir.
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board_highlight_duration_s = 3.0
        scenario = {'highlight_placements': [['T', 2, 3]]}
        lesson = {'lesson_type': 'exam', 'id': 'exam_board_midterm'}
        TutorialMode._setup_board_highlight(tutorial, scenario, lesson=lesson, attempt_count=2)
        self.assertFalse(tutorial._board_highlight_allowed)
        self.assertEqual(tutorial.board_highlight_timer, 0.0)

    def test_setup_board_highlight_none_when_no_spec(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board_highlight_duration_s = 3.0
        TutorialMode._setup_board_highlight(tutorial, {'board_rows': []})
        self.assertIsNone(tutorial.board_highlight_spec)
        self.assertEqual(tutorial.board_highlight_timer, 0.0)

    def test_hold_lesson_enables_hold_highlight_immediately(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board_highlight_duration_s = 3.0
        scenario = {'highlight_placements': [['I', 1, 3]], 'expected_hold_usage': True}
        lesson = {'lesson_type': 'drill', 'id': 'plan_hold_save'}
        TutorialMode._setup_board_highlight(tutorial, scenario, lesson=lesson, attempt_count=1)
        self.assertTrue(tutorial.hold_highlight_active)
        # Hold dersinde board iniş highlight'ı ilk denemede gösterilmez.
        self.assertEqual(tutorial.board_highlight_timer, 0.0)

    def test_exam_lesson_hides_hold_highlight_and_board_first_two_attempts(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board_highlight_duration_s = 3.0
        scenario = {'highlight_placements': [['I', 1, 3]], 'expected_hold_usage': True}
        lesson = {'lesson_type': 'exam', 'id': 'exam_board_midterm'}
        for attempt in (1, 2):
            TutorialMode._setup_board_highlight(tutorial, scenario, lesson=lesson, attempt_count=attempt)
            self.assertFalse(tutorial.hold_highlight_active, f'attempt {attempt}')
            self.assertEqual(tutorial.board_highlight_timer, 0.0, f'attempt {attempt}')

    def test_exam_lesson_shows_board_band_after_two_fails(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board_highlight_duration_s = 3.0
        scenario = {'highlight_placements': [['T', 2, 2]]}
        lesson = {'lesson_type': 'exam', 'id': 'exam_board_midterm'}
        TutorialMode._setup_board_highlight(tutorial, scenario, lesson=lesson, attempt_count=3)
        self.assertFalse(tutorial.hold_highlight_active)
        self.assertGreater(tutorial.board_highlight_timer, 0.0)

    def test_target_scenarios_carry_highlight_placements(self):
        scenario_ids = [
            'gap_fill_double', 'keep_stack_low', 'avoid_holes_trap', 'vertical_well_quadrix',
            'queue_read_setup', 'hold_vs_place_decision', 'two_step_combo',
            'recovery_breathing_room', 'recovery_hole_vs_height', 'recovery_reduce_ceiling',
            'recovery_wrong_side', 'exam_board_combined', 'exam_plan_combined', 'exam_hybrid_final',
            'hold_save_practice',
        ]
        valid_names = {'I', 'O', 'T', 'S', 'Z', 'J', 'L'}
        for sid in scenario_ids:
            scenario = tutorial_module.get_scenario(sid)
            placements = scenario.get('highlight_placements')
            self.assertTrue(placements, sid)
            budget = max(1, int(scenario.get('max_piece_locks', 1) or 1))
            # Yerleştirme sayısı kilit bütçesini aşmamalı.
            self.assertLessEqual(len(placements), budget, sid)
            for p in placements:
                self.assertEqual(len(p), 3, sid)
                self.assertIn(p[0], valid_names, sid)
                self.assertTrue(0 <= int(p[1]) <= 3, f'{sid} rotation={p[1]}')

    def test_compute_landing_footprint_uses_live_board_geometry(self):
        """Dinamik footprint: dik I parçası (rotation=1) gerçekten dikey 4 hücre
        olmalı; geometri parçanın şekline tam uymalı."""
        pieces_module = _ensure_real_module('pieces')
        Piece = pieces_module.Piece
        SHAPE_NAMES = pieces_module.SHAPE_NAMES

        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board_width = 10
        tutorial.board_height = 20
        # vertical_well_quadrix: sağda 9. sütun açık kuyu, I dik inmeli.
        scenario = tutorial_module.get_scenario('vertical_well_quadrix')
        occ = tutorial_module.build_occupancy_from_rows(scenario['board_rows'], width=10, height=20)

        class _BoardLike:
            def __init__(self, occupancy):
                self.occupancy = occupancy
                self.width = 10
                self.height = 20
                self.flexible_border_active = False

            def is_valid_position(self, piece, dx=0, dy=0):
                for px, py in piece.get_cells():
                    px += dx
                    py += dy
                    if px < 0 or px >= self.width or py >= self.height:
                        return False
                    if py < 0:
                        continue
                    if self.occupancy[py][px]:
                        return False
                return True

        tutorial.board = _BoardLike(occ)
        tutorial._create_named_piece = lambda name: Piece(x=0, y=0, shape_index=SHAPE_NAMES.index(name))

        cells = tutorial._compute_landing_footprint('I', 1, 7)
        self.assertTrue(cells)
        # Dik I → tek sütunda 4 hücre.
        xs = {c[0] for c in cells}
        ys = sorted(c[1] for c in cells)
        self.assertEqual(len(xs), 1, f'dik I tek sütun olmalı: {cells}')
        self.assertEqual(len(cells), 4, cells)
        # Ardışık 4 satır (dikey süreklilik).
        self.assertEqual(ys, list(range(ys[0], ys[0] + 4)), cells)
        # Tüm hücreler başlangıçta boş olmalı.
        for (cx, cy) in cells:
            self.assertFalse(occ[cy][cx], (cx, cy))

    def test_get_active_highlight_cells_follows_lock_count(self):
        """İkinci parça (lock_count=1) highlight'ı, placements[1]'i yansıtmalı."""
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board_width = 10
        tutorial.board_height = 20
        tutorial.board = None  # footprint hesaplanamaz ama indeks mantığı test edilir
        tutorial.board_highlight_spec = {
            'placements': [['L', 3, 3], ['I', 1, 3]],
            'columns': [],
            'cells': [],
        }
        calls = []
        tutorial._compute_landing_footprint = lambda name, rot, x: calls.append((name, rot, x)) or [(x, 0)]
        tutorial.lesson_runtime_state = {'scenario_lock_count': 0}
        tutorial._get_active_highlight_cells()
        self.assertEqual(calls[-1], ('L', 3, 3))
        tutorial.lesson_runtime_state = {'scenario_lock_count': 1}
        tutorial._get_active_highlight_cells()
        self.assertEqual(calls[-1], ('I', 1, 3))
        # Tüm parçalar kilitlendiyse highlight yok.
        tutorial.lesson_runtime_state = {'scenario_lock_count': 2}
        self.assertEqual(tutorial._get_active_highlight_cells(), [])

    def test_all_scenario_placements_produce_valid_footprints(self):
        """Her senaryonun TÜM placement adımları, sırayla CANLI board üzerinde
        4 hücrelik geçerli (boş) bir iniş ayak izi üretmeli. Bu, 2. ve sonraki
        parçaların highlight'ının da doğru çalıştığını garanti eder."""
        pieces_module = _ensure_real_module('pieces')
        Piece = pieces_module.Piece
        SHAPE_NAMES = pieces_module.SHAPE_NAMES

        class _BoardLike:
            def __init__(self, occupancy):
                self.occupancy = occupancy
                self.width = 10
                self.height = 20
                self.flexible_border_active = False

            def is_valid_position(self, piece, dx=0, dy=0):
                for px, py in piece.get_cells():
                    px += dx
                    py += dy
                    if px < 0 or px >= self.width or py >= self.height:
                        return False
                    if py < 0:
                        continue
                    if self.occupancy[py][px]:
                        return False
                return True

        def clear_full_rows(occ):
            rows = [row for row in occ if not all(row)]
            while len(rows) < 20:
                rows.insert(0, [False] * 10)
            return rows

        scenario_ids = [
            'gap_fill_double', 'keep_stack_low', 'avoid_holes_trap', 'vertical_well_quadrix',
            'queue_read_setup', 'hold_vs_place_decision', 'two_step_combo',
            'recovery_breathing_room', 'recovery_hole_vs_height', 'recovery_reduce_ceiling',
            'recovery_wrong_side', 'exam_board_combined', 'exam_plan_combined', 'exam_hybrid_final',
            'hold_save_practice',
        ]
        for sid in scenario_ids:
            scenario = tutorial_module.get_scenario(sid)
            placements = scenario.get('highlight_placements')
            occ = tutorial_module.build_occupancy_from_rows(scenario['board_rows'], width=10, height=20)

            tutorial = TutorialMode.__new__(TutorialMode)
            tutorial.board_width = 10
            tutorial.board_height = 20
            tutorial._create_named_piece = lambda name: Piece(x=0, y=0, shape_index=SHAPE_NAMES.index(name))

            # Her placement'ı sırayla uygula; footprint'i hesapla, sonra kilitle.
            for step_idx, (name, rot, x) in enumerate(placements):
                tutorial.board = _BoardLike(occ)
                cells = tutorial._compute_landing_footprint(name, rot, x)
                self.assertTrue(cells, f'{sid} adım {step_idx} footprint boş: {(name, rot, x)}')
                # I/O/T/S/Z/J/L hepsi 4 hücre.
                self.assertEqual(len(cells), 4, f'{sid} adım {step_idx}: {cells}')
                # Hücreler başlangıçta boş olmalı.
                for (cx, cy) in cells:
                    self.assertFalse(occ[cy][cx], f'{sid} adım {step_idx} dolu hücre: {(cx, cy)}')
                # Kilitle ve satırları temizle (sonraki parça için board ilerlet).
                for (cx, cy) in cells:
                    occ[cy][cx] = True
                occ = clear_full_rows(occ)

    def test_live_objective_states_track_line_clear(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        scenario = {
            'objectives': [
                {'id': 'clear_lines', 'text': '2 satır temizle', 'metric': 'line_delta', 'comparison': 'min', 'value': 2},
                {'id': 'avoid_holes', 'text': 'Delik açma', 'metric': 'hole_delta', 'comparison': 'max', 'value': 0},
            ],
        }
        tutorial.active_lesson = {'kind': 'scenario', 'scenario_id': 'live_test'}
        tutorial._get_active_board_scenario = lambda: scenario
        tutorial.lesson_runtime_state = {
            'initial_metrics': {'lines_cleared': 0, 'holes': 0, 'max_height': 4},
            'hold_used': False,
        }
        # 2 satır temizlenmiş, delik yok
        tutorial.board = self._make_board_like(
            tutorial_module.build_occupancy_from_rows([], width=10, height=20),
            lines_cleared=2,
        )
        states = TutorialMode._get_live_objective_states(tutorial)
        passed = {st['id']: st['passed'] for st in states}
        self.assertTrue(passed['clear_lines'])
        self.assertTrue(passed['avoid_holes'])

    def test_live_objective_states_empty_without_scenario(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial._get_active_board_scenario = lambda: None
        self.assertEqual(TutorialMode._get_live_objective_states(tutorial), [])


class TestRichResultFeedback(unittest.TestCase):
    """FAZ E: Pedagojik geri bildirim alanları + kademeli ipucu."""

    def test_evaluate_scenario_exposes_did_well_and_improve_keys(self):
        scenario = tutorial_module.get_scenario('gap_fill_double')
        clean = tutorial_module.evaluate_scenario(
            {'holes': 0, 'max_height': 2, 'lines_cleared': 0},
            {'holes': 0, 'max_height': 0, 'lines_cleared': 2},
            scenario['evaluation'],
        )
        self.assertIn('did_well_keys', clean)
        self.assertIn('improve_keys', clean)
        self.assertIn('no_new_holes', clean['did_well_keys'])
        self.assertIn('cleared_lines', clean['did_well_keys'])
        self.assertEqual(clean['improve_keys'], [])

    def test_evaluate_scenario_flags_created_holes_in_improve(self):
        scenario = tutorial_module.get_scenario('gap_fill_double')
        messy = tutorial_module.evaluate_scenario(
            {'holes': 0, 'max_height': 2, 'lines_cleared': 0},
            {'holes': 2, 'max_height': 5, 'lines_cleared': 0},
            scenario['evaluation'],
        )
        self.assertFalse(messy['success'])
        self.assertIn('created_holes', messy['improve_keys'])
        self.assertIn('need_more_lines', messy['improve_keys'])

    def test_progressive_hint_escalates_with_attempts(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        scenario = {
            'tip_text': 'Spesifik: T parçasını sağa kaydır.',
            'coach_feedback': {'need_more_lines': 'Ana boşluğu doğrudan kapat.'},
        }
        tutorial._get_active_board_scenario = lambda: scenario
        outcome = {'feedback_key': 'need_more_lines'}

        # 1. deneme → genel
        tutorial.lesson_runtime_state = {'attempt_count': 1}
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            h1 = TutorialMode._get_progressive_result_hint(tutorial, outcome, False)
        # 2. deneme → coach metni
        tutorial.lesson_runtime_state = {'attempt_count': 2}
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            h2 = TutorialMode._get_progressive_result_hint(tutorial, outcome, False)
        # 3. deneme → spesifik tip
        tutorial.lesson_runtime_state = {'attempt_count': 3}
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            h3 = TutorialMode._get_progressive_result_hint(tutorial, outcome, False)

        self.assertTrue(h1)
        self.assertEqual(h2, 'Ana boşluğu doğrudan kapat.')
        self.assertEqual(h3, 'Spesifik: T parçasını sağa kaydır.')
        self.assertNotEqual(h1, h2)
        self.assertNotEqual(h2, h3)

    def test_progressive_hint_empty_on_success(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial._get_active_board_scenario = lambda: {'tip_text': 'x'}
        tutorial.lesson_runtime_state = {'attempt_count': 3}
        self.assertEqual(TutorialMode._get_progressive_result_hint(tutorial, {}, True), '')

    def test_behavior_label_localizes_with_fallback(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        self.assertEqual(tutorial._behavior_label('no_new_holes'), 'Delik açmadın.')
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            self.assertEqual(tutorial._behavior_label('created_holes'), 'Yeni delik açtın.')
            self.assertEqual(tutorial._behavior_label(''), '')


class TestCardLessonFlow(unittest.TestCase):
    """Kart dersi 2 aşamalı akış: board_preview → choosing → (zengin sonuç paneli)."""

    def _make_card_tutorial(self, scenario):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.active_lesson = {'kind': 'card_choice'}
        tutorial.card_ui = None
        tutorial.card_choice_state = {
            'scenario': scenario,
            'selected_index': 0,
            'stage': 'board_preview',
        }
        tutorial.lesson_runtime_state = {}
        tutorial.sound = types.SimpleNamespace(play=lambda *_a, **_k: None)
        tutorial._pending_card_choice_index = None
        tutorial._sync_tutorial_card_overlay_reference = lambda: None
        return tutorial

    def test_card_stage_helpers(self):
        scenario = {'choices': [{'id': 'a'}, {'id': 'b'}], 'recommended_card_id': 'a'}
        tutorial = self._make_card_tutorial(scenario)
        self.assertEqual(tutorial._card_choice_stage(), 'board_preview')
        self.assertFalse(tutorial._is_card_choosing_stage())

    def test_advance_preview_moves_to_choosing(self):
        scenario = {'choices': [{'id': 'a'}, {'id': 'b'}], 'recommended_card_id': 'a'}
        tutorial = self._make_card_tutorial(scenario)
        TutorialMode._advance_card_preview_to_choosing(tutorial)
        self.assertEqual(tutorial._card_choice_stage(), 'choosing')
        self.assertTrue(tutorial._is_card_choosing_stage())

    def test_confirm_selection_goes_straight_to_result_with_card_info(self):
        scenario = {
            'choices': [
                {'id': 'good', 'title': 'İyi Kart', 'description': 'Delikleri kapatır.'},
                {'id': 'bad', 'title': 'Kötü Kart', 'description': 'Hız verir.'},
            ],
            'recommended_card_id': 'good',
            'acceptable_card_ids': [],
        }
        tutorial = self._make_card_tutorial(scenario)
        tutorial.card_choice_state['stage'] = 'choosing'
        tutorial.card_choice_state['selected_index'] = 0
        shown = {}
        tutorial._show_lesson_result = lambda outcome: shown.setdefault('outcome', dict(outcome))
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            TutorialMode._confirm_card_choice_selection(tutorial)
        # Ara "Sonucu gör" ekranı YOK — doğrudan sonuç gösterilir.
        self.assertIn('outcome', shown)
        self.assertTrue(shown['outcome'].get('success'))
        # Kart etkisi (ad + açıklama) sonuca gömülmeli.
        self.assertEqual(shown['outcome'].get('card_title'), 'İyi Kart')
        self.assertEqual(shown['outcome'].get('card_description'), 'Delikleri kapatır.')

    def test_wrong_card_result_marks_failure_with_card_info(self):
        scenario = {
            'choices': [
                {'id': 'good', 'title': 'İyi', 'description': 'X'},
                {'id': 'bad', 'title': 'Kötü', 'description': 'Y'},
            ],
            'recommended_card_id': 'good',
            'acceptable_card_ids': [],
        }
        tutorial = self._make_card_tutorial(scenario)
        tutorial.card_choice_state['stage'] = 'choosing'
        tutorial.card_choice_state['selected_index'] = 1  # yanlış
        shown = {}
        tutorial._show_lesson_result = lambda outcome: shown.setdefault('outcome', dict(outcome))
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            TutorialMode._confirm_card_choice_selection(tutorial)
        self.assertIn('outcome', shown)
        self.assertFalse(shown['outcome'].get('success'))

    def _make_card_tutorial_with_board(self, scenario):
        import types as _types
        tutorial = self._make_card_tutorial(scenario)
        width, height = 10, 6
        occupancy = [[False] * width for _ in range(height)]
        for x in range(width):
            occupancy[height - 1][x] = True
        tutorial.board = _types.SimpleNamespace(
            width=width, height=height, occupancy=occupancy,
            grid=[[(0, 0, 0)] * width for _ in range(height)],
            texture_grid=[[None] * width for _ in range(height)],
            gold=[[False] * width for _ in range(height)],
            owners=[[None] * width for _ in range(height)],
        )
        tutorial.screen_shake = 0.0
        tutorial.card_effect_showcase_timer = 0.0
        tutorial.card_effect_showcase_duration_s = 0.9
        tutorial.card_effect_highlight_timer = 0.0
        tutorial.card_effect_highlight_duration_s = 0.75
        tutorial.card_effect_highlight_cells = set()
        tutorial.card_effect_showcase_phase = 'highlight'
        return tutorial

    def test_animated_card_enters_showcase_before_result(self):
        # FAZ 7 — Animasyonlu etkili kart önce showcase sahnesine geçer, sonuç hemen gelmez.
        scenario = {
            'choices': [{'id': 'clear_rows', 'title': 'Alt Süpür', 'description': 'X', 'value': 1}],
            'recommended_card_id': 'clear_rows',
            'acceptable_card_ids': [],
        }
        tutorial = self._make_card_tutorial_with_board(scenario)
        tutorial.card_choice_state['stage'] = 'choosing'
        tutorial.card_choice_state['selected_index'] = 0
        shown = {}
        tutorial._show_lesson_result = lambda outcome: shown.setdefault('outcome', dict(outcome))
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            TutorialMode._confirm_card_choice_selection(tutorial)
        # Faz 1 (vurgu): showcase'e geçildi, hücreler hesaplandı, board HENÜZ değişmedi.
        self.assertEqual(tutorial.card_choice_state.get('stage'), 'showcase')
        self.assertEqual(tutorial.card_effect_showcase_phase, 'highlight')
        self.assertTrue(tutorial.card_effect_highlight_cells)  # alt satır vurgulandı
        self.assertNotIn('outcome', shown)
        # Alt satır hâlâ dolu (mutasyon faz 2'de).
        self.assertTrue(any(tutorial.board.occupancy[tutorial.board.height - 1]))
        # Faz 2 (uygula): mutasyon + temizlik.
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            TutorialMode._apply_card_effect_showcase_mutation(tutorial)
        self.assertEqual(tutorial.card_effect_showcase_phase, 'settle')
        self.assertTrue(tutorial.card_choice_state.get('showcase_applied'))
        # Showcase bitince sonuç açılır.
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            TutorialMode._finish_card_effect_showcase(tutorial)
        self.assertIn('outcome', shown)
        self.assertTrue(shown['outcome'].get('success'))

    def test_finish_showcase_applies_mutation_if_skipped_early(self):
        # Erken atlama: faz 2'ye varmadan _finish çağrılırsa mutasyon yine uygulanır.
        scenario = {
            'choices': [{'id': 'clear_rows', 'title': 'Alt Süpür', 'description': 'X', 'value': 2}],
            'recommended_card_id': 'clear_rows',
            'acceptable_card_ids': [],
        }
        tutorial = self._make_card_tutorial_with_board(scenario)
        tutorial.card_choice_state['stage'] = 'choosing'
        tutorial.card_choice_state['selected_index'] = 0
        shown = {}
        tutorial._show_lesson_result = lambda outcome: shown.setdefault('outcome', dict(outcome))
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            TutorialMode._confirm_card_choice_selection(tutorial)
            # Vurgu fazındayken doğrudan finish (erken atlama).
            TutorialMode._finish_card_effect_showcase(tutorial)
        self.assertTrue(tutorial.card_choice_state.get('showcase_applied'))
        self.assertIn('outcome', shown)

    def test_non_animated_card_skips_showcase(self):
        # Animasyonsuz kart (perk) showcase'e girmeden doğrudan sonuca gider.
        scenario = {
            'choices': [{'id': 'perk_second_pocket', 'title': 'Ekstra Cep', 'description': 'X', 'persistent': True}],
            'recommended_card_id': 'perk_second_pocket',
            'acceptable_card_ids': [],
        }
        tutorial = self._make_card_tutorial_with_board(scenario)
        tutorial.card_choice_state['stage'] = 'choosing'
        tutorial.card_choice_state['selected_index'] = 0
        shown = {}
        tutorial._show_lesson_result = lambda outcome: shown.setdefault('outcome', dict(outcome))
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            TutorialMode._confirm_card_choice_selection(tutorial)
        self.assertNotEqual(tutorial.card_choice_state.get('stage'), 'showcase')
        self.assertIn('outcome', shown)

    def test_apply_tutorial_card_effect_clear_rows_mutates_board(self):
        # FAZ 6 — Kart ustalığı hissi: clear_rows alt satırları temizler.
        tutorial = TutorialMode.__new__(TutorialMode)
        width, height = 10, 6
        occupancy = [[False] * width for _ in range(height)]
        grid = [[(0, 0, 0)] * width for _ in range(height)]
        # En alt iki satır dolu.
        for x in range(width):
            occupancy[height - 1][x] = True
            occupancy[height - 2][x] = True
            grid[height - 1][x] = (100, 100, 100)
            grid[height - 2][x] = (100, 100, 100)
        tutorial.board = types.SimpleNamespace(
            width=width, height=height, occupancy=occupancy, grid=grid,
            texture_grid=[[None] * width for _ in range(height)],
            gold=[[False] * width for _ in range(height)],
            owners=[[None] * width for _ in range(height)],
        )
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            summary = TutorialMode._apply_tutorial_card_effect(
                tutorial, {'id': 'clear_rows', 'value': 2})
        self.assertTrue(summary)
        # Etki sonrası tahtada dolu hücre kalmamalı (2 dolu satır temizlendi).
        filled = sum(1 for row in occupancy for cell in row if cell)
        self.assertEqual(filled, 0)

    def test_apply_tutorial_card_effect_perk_no_board_change(self):
        # Perk kartı tahtayı değiştirmez ama özet döndürür.
        tutorial = TutorialMode.__new__(TutorialMode)
        width, height = 10, 4
        occupancy = [[False] * width for _ in range(height)]
        occupancy[height - 1][0] = True
        tutorial.board = types.SimpleNamespace(
            width=width, height=height, occupancy=occupancy,
            grid=[[(0, 0, 0)] * width for _ in range(height)],
            texture_grid=[[None] * width for _ in range(height)],
            gold=[[False] * width for _ in range(height)],
            owners=[[None] * width for _ in range(height)],
        )
        with mock.patch.object(tutorial_module, 't', lambda key, *a, **k: k.get('default', key)):
            summary = TutorialMode._apply_tutorial_card_effect(
                tutorial, {'id': 'perk_second_pocket', 'persistent': True})
        self.assertTrue(summary)
        self.assertTrue(occupancy[height - 1][0])  # değişmedi

    def test_apply_tutorial_card_effect_safe_without_board(self):
        # board None ise güvenli boş döner.
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board = None
        self.assertEqual(
            TutorialMode._apply_tutorial_card_effect(tutorial, {'id': 'clear_rows'}), '')


class TestPerPlacementHighlightTiming(unittest.TestCase):
    """Her highlight kendi süresince ekranda kalmalı; yeni parçada süre sıfırlanır."""

    def test_hold_highlight_index_controls_visibility(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board_highlight_duration_s = 3.0
        scenario = {
            'highlight_placements': [['J', 1, 3], ['I', 1, 0]],
            'expected_hold_usage': True,
            'hold_highlight_index': 1,
        }
        lesson = {'lesson_type': 'repair_challenge', 'id': 'recover_wrong_side_escape'}
        TutorialMode._setup_board_highlight(tutorial, scenario, lesson=lesson, attempt_count=1)
        # hold_highlight_index=1 → ilk parçada hold vurgusu kapalı.
        self.assertTrue(tutorial.hold_highlight_armed)
        self.assertEqual(tutorial.hold_highlight_index, 1)
        self.assertFalse(tutorial.hold_highlight_active)

    def test_hold_highlight_index_zero_shows_immediately(self):
        tutorial = TutorialMode.__new__(TutorialMode)
        tutorial.board_highlight_duration_s = 3.0
        scenario = {
            'highlight_placements': [['I', 1, 3]],
            'expected_hold_usage': True,
        }
        lesson = {'lesson_type': 'drill', 'id': 'plan_hold_save'}
        TutorialMode._setup_board_highlight(tutorial, scenario, lesson=lesson, attempt_count=1)
        self.assertTrue(tutorial.hold_highlight_armed)
        self.assertEqual(tutorial.hold_highlight_index, 0)
        self.assertTrue(tutorial.hold_highlight_active)

    def test_recovery_reduce_ceiling_has_hold_highlight_index(self):
        scenario = tutorial_module.get_scenario('recovery_reduce_ceiling')
        self.assertEqual(scenario.get('hold_highlight_index'), 1)


if __name__ == '__main__':
    unittest.main()