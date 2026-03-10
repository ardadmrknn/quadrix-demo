import pygame
import random

try:
    from .game import Game  # type: ignore
    from .localization import t  # type: ignore
    from .retro_style import retro_style  # type: ignore
    from .constants import *  # type: ignore
    from .pieces import create_piece_by_name  # type: ignore
    from .platform_utils import create_display, normalize_mouse_pos, get_mouse_pos  # type: ignore
    from .tutorial_lessons import (  # type: ignore
        get_chapters,
        get_first_lesson_id,
        get_lesson,
        get_lesson_for_legacy_step,
        get_lessons,
        list_lessons_for_chapter,
        get_next_lesson_id,
    )
    from .tutorial_progress import build_default_tutorial_progress  # type: ignore
    from .tutorial_scenarios import (  # type: ignore
        build_occupancy_from_rows,
        capture_board_metrics,
        evaluate_scenario,
        get_scenario,
    )
    from .tutorial_cards import (  # type: ignore
        evaluate_card_choice,
        get_card_choice_scenario,
        get_tutorial_card_description,
        get_tutorial_card_rarity_label,
        get_tutorial_card_title,
        get_tutorial_card_type_label,
    )
    from .game_modes_extra import MysteryCardUI  # type: ignore
except Exception:
    from game import Game
    from localization import t
    from retro_style import retro_style
    from constants import *
    from pieces import create_piece_by_name
    from platform_utils import create_display, normalize_mouse_pos, get_mouse_pos
    from tutorial_lessons import (
        get_chapters,
        get_first_lesson_id,
        get_lesson,
        get_lesson_for_legacy_step,
        get_lessons,
        list_lessons_for_chapter,
        get_next_lesson_id,
    )
    from tutorial_progress import build_default_tutorial_progress
    from tutorial_scenarios import (
        build_occupancy_from_rows,
        capture_board_metrics,
        evaluate_scenario,
        get_scenario,
    )
    from tutorial_cards import (
        evaluate_card_choice,
        get_card_choice_scenario,
        get_tutorial_card_description,
        get_tutorial_card_rarity_label,
        get_tutorial_card_title,
        get_tutorial_card_type_label,
    )
    try:
        from game_modes_extra import MysteryCardUI
    except Exception:
        MysteryCardUI = None


def _tutorial_make_card_ui_font(size, bold=False):
    try:
        try:
            from .localization import get_language  # type: ignore
        except Exception:
            from localization import get_language
        lang = get_language()
    except Exception:
        lang = None

    effective_lang = 'ja' if lang == 'jp' else lang
    try:
        try:
            from .ui_language_profile import get_font_for_language  # type: ignore
        except Exception:
            from ui_language_profile import get_font_for_language
        font = get_font_for_language(effective_lang, size, bold=bold)
        if font is not None:
            return font
    except Exception:
        pass
    return retro_style.get_font(size, bold=bold)

class TutorialMode(Game):
    def __init__(self, difficulty='Normal', sound_enabled=True, effects_enabled=True, 
                 achievement_manager=None, theme_manager=None, screen=None, 
                 fullscreen=False, settings_manager=None, user_manager=None, 
                 game_mode='tutorial', sound_manager=None, score_manager=None, 
                 block_style_manager=None, launch_lesson_id=None, lesson_flow_scope='full'):
        
        super().__init__(difficulty, sound_enabled, effects_enabled, achievement_manager, 
                         theme_manager, screen, fullscreen, settings_manager, user_manager, 
                         game_mode, sound_manager, 
                         block_style_manager=block_style_manager,
                         score_manager=score_manager)
        
        self.step = 1
        self.step_target = 0
        self.waiting_for_enter = False
        self.overlay_message = ""
        self.sub_message = ""
        self.tip_message = ""
        self.stuck_hint_message = ""
        self.step_idle_timer = 0.0
        self.stuck_hint_delay_s = 8.0
        self.stuck_hint_pulse_timer = 0.0
        self.soft_drop_counter = 0 
        self.soft_drop_active = False
        self.base_fall_speed = 2000
        
        # Transition state
        self.in_transition = False
        self.transition_timer = 0
        self.next_step_num = 0
        self.transition_text = ""
        
        # Success effects
        self.success_particles = []
        self.success_glow_timer = 0
        self.success_text_scale = 1.0
        self.step_completion_effects = []
        
        # Progress celebration
        self.progress_celebration_timer = 0
        self.progress_celebration_text = ""
        
        self.fall_speed = 2000
        self.control_bindings = self._resolve_single_player_controls()
        
        # Step specific counters
        self.step_move_left_count = 0
        self.step_move_right_count = 0
        self.step_rotate_count = 0
        self.step_lines = 0
        self.lesson_catalog = []
        self.lesson_lookup = {}
        self.active_lesson_id = None
        self.active_lesson = None
        self.lesson_runtime_state = {}
        self.next_lesson_id = None
        self.lesson_result_active = False
        self.lesson_result = None
        self.lesson_attempt_counts = {}
        self.card_choice_state = {}
        self.card_ui = MysteryCardUI() if MysteryCardUI else None
        self._pending_card_choice_index = None
        self.lesson_flow_scope = 'chapter' if lesson_flow_scope == 'chapter' else 'full'
        self.hub_return_enabled = launch_lesson_id is None
        self.hub_active = False
        self.hub_selected_chapter_id = None
        self.hub_selected_lesson_id = None
        self.hub_chapter_rects = []
        self.hub_lesson_rects = []
        self.hub_start_rect = None
        self.hub_back_rect = None
        self.hub_progress_snapshot = build_default_tutorial_progress()
        self._load_lesson_catalog()
        if self.card_ui:
            self.card_ui.set_overlay_reference_size(self.window_width, self.window_height)
        
        initial_lesson_id = launch_lesson_id or get_first_lesson_id()
        if launch_lesson_id:
            self._start_lesson(initial_lesson_id)
        elif initial_lesson_id:
            self._open_tutorial_hub(preferred_lesson_id=initial_lesson_id)
        else:
            self._setup_step(1)

    def wants_mouse_visible(self) -> bool:
        if getattr(self, 'hub_active', False):
            return True
        if self._is_card_choice_lesson_active() and not getattr(self, 'lesson_result_active', False):
            return True
        return super().wants_mouse_visible()

    def _load_lesson_catalog(self):
        self.lesson_catalog = list(get_lessons())
        self.lesson_lookup = {
            str(lesson.get('id')): dict(lesson)
            for lesson in self.lesson_catalog
            if lesson.get('id')
        }

    def _get_tutorial_progress_snapshot(self):
        if self.user_manager and hasattr(self.user_manager, 'get_tutorial_progress'):
            try:
                progress = self.user_manager.get_tutorial_progress()
                if isinstance(progress, dict):
                    return progress
            except Exception:
                pass
        return build_default_tutorial_progress()

    def _get_chapter_progress(self, chapter_id):
        progress = self.hub_progress_snapshot.get('chapters', {}) if isinstance(self.hub_progress_snapshot, dict) else {}
        if not isinstance(progress, dict):
            return {}
        entry = progress.get(str(chapter_id), {})
        return entry if isinstance(entry, dict) else {}

    def _get_lesson_progress(self, chapter_id, lesson_id):
        chapter_progress = self._get_chapter_progress(chapter_id)
        lessons = chapter_progress.get('lessons', {}) if isinstance(chapter_progress, dict) else {}
        if not isinstance(lessons, dict):
            return {}
        entry = lessons.get(str(lesson_id), {})
        return entry if isinstance(entry, dict) else {}

    def _get_hub_chapter_entries(self):
        entries = []
        for chapter in get_chapters():
            chapter_id = str(chapter.get('id') or '')
            chapter_progress = self._get_chapter_progress(chapter_id)
            lessons = list_lessons_for_chapter(chapter_id)
            completed_lessons = 0
            for lesson in lessons:
                lesson_progress = self._get_lesson_progress(chapter_id, lesson.get('id'))
                if bool(lesson_progress.get('completed', False)):
                    completed_lessons += 1
            entries.append(
                {
                    'chapter': chapter,
                    'unlocked': bool(chapter_progress.get('unlocked', chapter.get('unlocked_by_default', False))),
                    'completed': bool(chapter_progress.get('completed', False)),
                    'stars': int(chapter_progress.get('stars', 0) or 0),
                    'completed_lessons': completed_lessons,
                    'total_lessons': len(lessons),
                }
            )
        return entries

    def _get_hub_lesson_entries(self, chapter_id):
        entries = []
        for lesson in list_lessons_for_chapter(chapter_id):
            lesson_id = str(lesson.get('id') or '')
            lesson_progress = self._get_lesson_progress(chapter_id, lesson_id)
            entries.append(
                {
                    'lesson': lesson,
                    'completed': bool(lesson_progress.get('completed', False)),
                    'stars': int(lesson_progress.get('stars', 0) or 0),
                }
            )
        return entries

    def _get_total_tutorial_stars(self):
        total = 0
        for chapter_entry in self._get_hub_chapter_entries():
            total += int(chapter_entry.get('stars', 0) or 0)
        return total

    def _pick_hub_lesson_id(self, chapter_id, preferred_lesson_id=None):
        lesson_entries = self._get_hub_lesson_entries(chapter_id)
        if not lesson_entries:
            return None
        if preferred_lesson_id:
            for entry in lesson_entries:
                if entry['lesson'].get('id') == preferred_lesson_id:
                    return str(preferred_lesson_id)
        for entry in lesson_entries:
            if not entry.get('completed', False):
                return str(entry['lesson'].get('id'))
        return str(lesson_entries[0]['lesson'].get('id'))

    def _select_hub_chapter(self, chapter_id, preferred_lesson_id=None):
        self.hub_selected_chapter_id = str(chapter_id) if chapter_id else None
        self.hub_selected_lesson_id = self._pick_hub_lesson_id(self.hub_selected_chapter_id, preferred_lesson_id=preferred_lesson_id)

    def _move_hub_chapter_selection(self, delta):
        chapters = self._get_hub_chapter_entries()
        if not chapters:
            return
        current_index = 0
        for index, entry in enumerate(chapters):
            if entry['chapter'].get('id') == self.hub_selected_chapter_id:
                current_index = index
                break
        new_index = (current_index + int(delta)) % len(chapters)
        chapter_id = chapters[new_index]['chapter'].get('id')
        self._select_hub_chapter(chapter_id)
        self.sound.play('move')

    def _move_hub_lesson_selection(self, delta):
        if not self.hub_selected_chapter_id:
            return
        lesson_entries = self._get_hub_lesson_entries(self.hub_selected_chapter_id)
        if not lesson_entries:
            return
        current_index = 0
        for index, entry in enumerate(lesson_entries):
            if entry['lesson'].get('id') == self.hub_selected_lesson_id:
                current_index = index
                break
        new_index = (current_index + int(delta)) % len(lesson_entries)
        self.hub_selected_lesson_id = str(lesson_entries[new_index]['lesson'].get('id'))
        self.sound.play('move')

    def _open_tutorial_hub(self, preferred_chapter_id=None, preferred_lesson_id=None):
        self.hub_progress_snapshot = self._get_tutorial_progress_snapshot()
        self.hub_active = True
        self.in_transition = False
        self.waiting_for_enter = False
        self.lesson_result_active = False
        self.lesson_result = None
        self.next_lesson_id = None
        self.card_choice_state = {}
        self.show_exit_prompt = False
        self.paused = False
        self._clear_tutorial_board()
        self._ensure_normal_piece(force_new=True)

        chapter_entries = self._get_hub_chapter_entries()
        preferred = str(preferred_chapter_id) if preferred_chapter_id else None
        if preferred and any(entry['chapter'].get('id') == preferred for entry in chapter_entries):
            self._select_hub_chapter(preferred, preferred_lesson_id=preferred_lesson_id)
            return

        unlocked_entry = next((entry for entry in chapter_entries if entry.get('unlocked')), None)
        target_chapter_id = unlocked_entry['chapter'].get('id') if unlocked_entry else (chapter_entries[0]['chapter'].get('id') if chapter_entries else None)
        self._select_hub_chapter(target_chapter_id, preferred_lesson_id=preferred_lesson_id)

    def _start_selected_hub_lesson(self):
        chapter_entries = self._get_hub_chapter_entries()
        current_chapter = next((entry for entry in chapter_entries if entry['chapter'].get('id') == self.hub_selected_chapter_id), None)
        if not current_chapter or not current_chapter.get('unlocked') or not self.hub_selected_lesson_id:
            try:
                self.sound.play('deny')
            except Exception:
                pass
            return
        self.hub_active = False
        self._start_lesson(self.hub_selected_lesson_id)

    def _reset_runtime_state_for_lesson(self, lesson):
        self.lesson_runtime_state = {
            'lesson_id': lesson.get('id') if isinstance(lesson, dict) else None,
            'legacy_step': lesson.get('legacy_step') if isinstance(lesson, dict) else None,
            'started_at': pygame.time.get_ticks(),
            'move_left_count': 0,
            'move_right_count': 0,
            'rotate_count': 0,
            'soft_drop_frames': 0,
            'feedback_key': None,
            'failed_reason': None,
        }

    def _sync_lesson_runtime_state(self):
        if not isinstance(self.lesson_runtime_state, dict):
            self.lesson_runtime_state = {}
        self.lesson_runtime_state.update(
            {
                'lesson_id': self.active_lesson_id,
                'legacy_step': self.step,
                'move_left_count': int(self.step_move_left_count),
                'move_right_count': int(self.step_move_right_count),
                'rotate_count': int(self.step_rotate_count),
                'soft_drop_frames': int(self.soft_drop_counter),
                'lines_cleared': int(getattr(self.board, 'lines_cleared', 0) or 0),
            }
        )

    def _is_scenario_lesson_active(self):
        return isinstance(self.active_lesson, dict) and self.active_lesson.get('kind') == 'scenario'

    def _is_card_choice_lesson_active(self):
        return isinstance(self.active_lesson, dict) and self.active_lesson.get('kind') == 'card_choice'

    def _lesson_index(self, lesson_id=None):
        target_id = lesson_id or self.active_lesson_id
        for index, lesson in enumerate(self.lesson_catalog, start=1):
            if lesson.get('id') == target_id:
                return index
        return 1

    def _lesson_title(self, lesson=None):
        lesson_data = lesson or self.active_lesson or {}
        if not isinstance(lesson_data, dict):
            return ''
        title_key = lesson_data.get('title_key')
        title_fallback = lesson_data.get('title_fallback') or lesson_data.get('id') or ''
        return t(title_key, default=title_fallback) if title_key else str(title_fallback)

    def _lesson_description(self, lesson=None):
        lesson_data = lesson or self.active_lesson or {}
        if not isinstance(lesson_data, dict):
            return ''
        description_key = lesson_data.get('description_key')
        description_fallback = lesson_data.get('description_fallback') or ''
        return t(description_key, default=description_fallback) if description_key else str(description_fallback)

    def _get_followup_lesson_id(self, lesson_id=None):
        return get_next_lesson_id(
            lesson_id or self.active_lesson_id,
            chapter_only=self.lesson_flow_scope == 'chapter',
        )

    def _wrap_text(self, text, font, max_width, max_lines=None):
        words = str(text or '').split(' ')
        lines = []
        current_line = ''
        for word in words:
            test_line = current_line + (' ' if current_line else '') + word
            if font.render(test_line, True, (255, 255, 255)).get_width() <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
                if max_lines and len(lines) >= max_lines:
                    break
        if current_line and (not max_lines or len(lines) < max_lines):
            lines.append(current_line)
        return lines

    def _clear_tutorial_board(self):
        self.board.reset()
        self.board.level = 1
        self.board.level_lines_cleared = 0
        self.board.combo = 0
        self.board.tetrises = 0
        self.game_over = False

    def _apply_board_rows(self, board_rows):
        occupancy = build_occupancy_from_rows(
            board_rows,
            width=self.board.width,
            height=self.board.height,
        )
        fill_color = (100, 100, 100)
        for y, row in enumerate(occupancy):
            for x, filled in enumerate(row):
                self.board.occupancy[y][x] = bool(filled)
                self.board.grid[y][x] = fill_color if filled else BLACK
                self.board.texture_grid[y][x] = None
                self.board.gold[y][x] = False
                self.board.owners[y][x] = None

    def _configure_piece_from_spec(self, piece_spec, default_name='T'):
        spec = dict(piece_spec or {})
        piece = self._create_named_piece(spec.get('name') or default_name)
        piece.x = int(spec.get('x', piece.x) or 0)
        piece.y = int(spec.get('y', piece.y) or 0)
        rotation_count = int(spec.get('rotation', 0) or 0) % 4
        for _ in range(rotation_count):
            piece.rotate()
        return piece

    def _build_piece_queue(self, names):
        queue = []
        for name in list(names or [])[:3]:
            queue.append(self._create_named_piece(str(name)))
        while len(queue) < 3:
            queue.append(self.spawn_new_piece())
        return queue

    def _setup_scenario_lesson(self, lesson):
        scenario = get_scenario(lesson.get('scenario_id')) if isinstance(lesson, dict) else None
        if not scenario:
            self._setup_step(1)
            return

        self.step = self._lesson_index(lesson.get('id'))
        self.in_transition = False
        self.waiting_for_enter = False
        self.lesson_result_active = False
        self.lesson_result = None
        self.card_choice_state = {}
        self.base_fall_speed = 1200
        self.fall_speed = self.base_fall_speed
        self.soft_drop_counter = 0
        self.soft_drop_active = False
        self.sub_message = str(scenario.get('goal_text') or lesson.get('goal_fallback') or '')
        self.tip_message = str(scenario.get('tip_text') or lesson.get('tip_fallback') or self._lesson_description(lesson))
        self.overlay_message = self._lesson_title(lesson)
        self._reset_stuck_hint_state()

        self.step_move_left_count = 0
        self.step_move_right_count = 0
        self.step_rotate_count = 0
        self.step_lines = 0
        self.success_particles = []
        self.success_glow_timer = 0
        self.success_text_scale = 1.0
        self.step_completion_effects = []
        self.progress_celebration_timer = 0
        self.progress_celebration_text = ''

        self._clear_tutorial_board()
        self._apply_board_rows(scenario.get('board_rows'))
        self.current_piece = self._configure_piece_from_spec(scenario.get('current_piece'), default_name='T')
        self.next_piece_queue = self._build_piece_queue(scenario.get('next_queue'))
        self.held_piece = None
        self.can_hold = bool(scenario.get('allow_hold', False))
        self.apply_theme_to_pieces()

        lesson_id = str(lesson.get('id') or '')
        attempt_count = int(self.lesson_attempt_counts.get(lesson_id, 0) or 0) + 1
        self.lesson_attempt_counts[lesson_id] = attempt_count

        self.lesson_runtime_state.update(
            {
                'scenario_id': scenario.get('id') or lesson.get('scenario_id'),
                'initial_metrics': capture_board_metrics(self.board),
                'attempt_count': attempt_count,
            }
        )
        self._sync_lesson_runtime_state()

    def _setup_card_choice_lesson(self, lesson):
        scenario = get_card_choice_scenario(lesson.get('scenario_id')) if isinstance(lesson, dict) else None
        if not scenario:
            self._setup_step(1)
            return

        self.step = self._lesson_index(lesson.get('id'))
        self.in_transition = False
        self.waiting_for_enter = False
        self.lesson_result_active = False
        self.lesson_result = None
        self._pending_card_choice_index = None
        self.card_choice_state = {
            'scenario': scenario,
            'selected_index': 0,
        }
        if self.card_ui:
            self.card_ui.reset()
            self.card_ui.set_overlay_reference_size(self.window_width, self.window_height)
        self.base_fall_speed = 0
        self.fall_speed = 0
        self.soft_drop_counter = 0
        self.soft_drop_active = False
        self.sub_message = t('tutorial_card_choose_hint', default='Sol/Sag ile sec, Enter ile onayla, 1-3 kisayollarini kullan.')
        self.tip_message = str(scenario.get('tip_text') or self._lesson_description(lesson))
        self.overlay_message = self._lesson_title(lesson)
        self._reset_stuck_hint_state()

        self.step_move_left_count = 0
        self.step_move_right_count = 0
        self.step_rotate_count = 0
        self.step_lines = 0
        self.success_particles = []
        self.success_glow_timer = 0
        self.success_text_scale = 1.0
        self.step_completion_effects = []
        self.progress_celebration_timer = 0
        self.progress_celebration_text = ''

        self._clear_tutorial_board()
        self._apply_board_rows(scenario.get('board_rows'))
        self.current_piece = self._configure_piece_from_spec(scenario.get('current_piece'), default_name='T')
        self.next_piece_queue = self._build_piece_queue(scenario.get('next_queue'))
        self.held_piece = None
        self.can_hold = False
        self.apply_theme_to_pieces()

        lesson_id = str(lesson.get('id') or '')
        attempt_count = int(self.lesson_attempt_counts.get(lesson_id, 0) or 0) + 1
        self.lesson_attempt_counts[lesson_id] = attempt_count
        self.lesson_runtime_state.update(
            {
                'scenario_id': scenario.get('scenario_id') or lesson.get('scenario_id'),
                'attempt_count': attempt_count,
                'selected_card_id': None,
                'context_lines': list(scenario.get('context_lines', []) or []),
            }
        )
        self._sync_lesson_runtime_state()

    def _build_tutorial_card_ui_font_pack(self):
        ui_scale = max(0.72, min(1.0, min(self.window_width / 1366.0, self.window_height / 768.0)))

        def font(base_size, min_size, bold=False):
            size = max(min_size, int(round(base_size * ui_scale)))
            return _tutorial_make_card_ui_font(size, bold=bold)

        return {
            'heading': font(44, 26),
            'panel_header': font(28, 17),
            'large': font(44, 24),
            'medium': font(32, 18),
            'small': font(18, 11),
            'card_title': font(26, 14),
            'value': font(52, 24),
            'icon': font(80, 32),
            'tag': font(20, 11),
            'desc': font(22, 11),
        }

    def _queue_card_choice_selection(self, index):
        if not self._is_card_choice_lesson_active():
            return
        scenario = self.card_choice_state.get('scenario', {}) if isinstance(self.card_choice_state, dict) else {}
        choices = scenario.get('choices', []) if isinstance(scenario, dict) else []
        if not (0 <= int(index) < len(choices)):
            return
        self.card_choice_state['selected_index'] = int(index)
        if self.card_ui:
            if self._pending_card_choice_index is not None or self.card_ui.is_selection_animating():
                return
            if self.card_ui.is_flip_animating():
                return
            self._pending_card_choice_index = int(index)
            self.card_ui.trigger_selection_feedback(int(index))
            return
        self._confirm_card_choice_selection(int(index))

    def _finalize_pending_card_choice_selection(self):
        if self._pending_card_choice_index is None:
            return
        pending_index = int(self._pending_card_choice_index)
        self._pending_card_choice_index = None
        self._confirm_card_choice_selection(pending_index)

    def _move_card_choice_selection(self, direction):
        if not self._is_card_choice_lesson_active():
            return
        scenario = self.card_choice_state.get('scenario', {}) if isinstance(self.card_choice_state, dict) else {}
        choices = scenario.get('choices', []) if isinstance(scenario, dict) else []
        if not choices:
            return
        current_index = int(self.card_choice_state.get('selected_index', 0) or 0)
        new_index = (current_index + int(direction)) % len(choices)
        self.card_choice_state['selected_index'] = new_index
        self.sound.play('move')

    def _confirm_card_choice_selection(self, forced_index=None):
        if not self._is_card_choice_lesson_active():
            return
        scenario = self.card_choice_state.get('scenario', {}) if isinstance(self.card_choice_state, dict) else {}
        choices = scenario.get('choices', []) if isinstance(scenario, dict) else []
        if not choices:
            return
        index = int(self.card_choice_state.get('selected_index', 0) or 0)
        if forced_index is not None and 0 <= int(forced_index) < len(choices):
            index = int(forced_index)
            self.card_choice_state['selected_index'] = index
        self._pending_card_choice_index = None
        if self.card_ui:
            self.card_ui.clear_selection_feedback()
        selected_card = choices[index]
        outcome = evaluate_card_choice(scenario, selected_card.get('id'))
        self.lesson_runtime_state['selected_card_id'] = selected_card.get('id')
        self.lesson_runtime_state['last_result'] = dict(outcome)
        self.sound.play('tutorial_progress')
        self._show_lesson_result(outcome)

    def _show_lesson_result(self, result):
        outcome = dict(result or {})
        success = bool(outcome.get('success'))
        feedback_map = {
            'clean': t('tutorial_result_feedback_clean', default='Temiz hamle. Tahtayi kontrol ederek ilerledin.'),
            'need_more_lines': t('tutorial_result_feedback_need_more_lines', default='Hedef satir sayisina ulasamadın. Tahtadaki ana boslugu tekrar oku.'),
            'created_holes': t('tutorial_result_feedback_created_holes', default='Hamle yeni delikler aciyor. Kart modunda bu tur hatalar sonraki secimleri zayiflatir.'),
            'stack_too_high': t('tutorial_result_feedback_stack_too_high', default='Hamle kuleyi gereksiz buyuttu. Once guvenli tarafı kullan.'),
        }
        followup_lesson_id = self._get_followup_lesson_id(self.active_lesson_id)
        action_text = t('tutorial_result_action_next_lesson', default='ENTER: Sonraki ders') if success and followup_lesson_id else t('tutorial_result_action_to_menu', default='ENTER: Menuye don')
        if success and not followup_lesson_id and self.hub_return_enabled:
            action_text = t('tutorial_result_action_to_hub', default='ENTER: Ders merkezine don')
        if not success:
            action_text = t('tutorial_result_action_retry', default='ENTER / R: Tekrar dene')

        self.lesson_result_active = True
        self._pending_card_choice_index = None
        if self.card_ui:
            self.card_ui.clear_selection_feedback()
        self.lesson_result = {
            'success': success,
            'title': str(outcome.get('title') or (t('tutorial_result_completed', default='Ders Tamamlandi') if success else t('tutorial_result_retry_title', default='Tekrar Dene'))),
            'feedback': str(outcome.get('feedback') or feedback_map.get(outcome.get('feedback_key'), feedback_map['clean'])),
            'stars': int(outcome.get('stars', 0) or 0),
            'line_delta': int(outcome.get('line_delta', 0) or 0),
            'hole_delta': int(outcome.get('hole_delta', 0) or 0),
            'height_delta': int(outcome.get('height_delta', 0) or 0),
            'action_text': str(outcome.get('action_text') or action_text),
            'selected_card_title': outcome.get('selected_card_title'),
            'recommended_card_title': outcome.get('recommended_card_title'),
        }
        self.waiting_for_enter = False
        if success:
            self._mark_active_lesson_completed(stars=self.lesson_result['stars'])
            self.next_lesson_id = followup_lesson_id
            self._create_success_effects()
            self.sound.play('tutorial_complete')

    def _evaluate_active_scenario(self):
        initial_metrics = self.lesson_runtime_state.get('initial_metrics', {}) if isinstance(self.lesson_runtime_state, dict) else {}
        scenario = get_scenario(self.active_lesson.get('scenario_id')) if isinstance(self.active_lesson, dict) else None
        if not scenario:
            return None
        current_metrics = capture_board_metrics(self.board)
        outcome = evaluate_scenario(initial_metrics, current_metrics, scenario.get('evaluation'))
        self.lesson_runtime_state['last_result'] = dict(outcome)
        return outcome

    def _start_lesson(self, lesson_id):
        lesson = self.lesson_lookup.get(str(lesson_id)) or get_lesson(lesson_id)
        if not lesson:
            self._setup_step(1)
            return
        self.active_lesson_id = str(lesson.get('id'))
        self.active_lesson = dict(lesson)
        self.next_lesson_id = None
        self._reset_runtime_state_for_lesson(lesson)
        legacy_step = lesson.get('legacy_step')
        if isinstance(legacy_step, int):
            self._setup_step(int(legacy_step))
        elif lesson.get('kind') == 'scenario':
            self._setup_scenario_lesson(lesson)
        elif lesson.get('kind') == 'card_choice':
            self._setup_card_choice_lesson(lesson)

    def _mark_active_lesson_completed(self, stars=1):
        if not (self.user_manager and self.active_lesson_id):
            return
        stats = {
            'step': int(self.step),
            'move_left_count': int(self.step_move_left_count),
            'move_right_count': int(self.step_move_right_count),
            'rotate_count': int(self.step_rotate_count),
            'soft_drop_frames': int(self.soft_drop_counter),
            'board_lines_cleared': int(getattr(self.board, 'lines_cleared', 0) or 0),
        }
        if isinstance(self.lesson_runtime_state, dict):
            stats.update(
                {
                    'attempt_count': int(self.lesson_runtime_state.get('attempt_count', 0) or 0),
                    'initial_metrics': dict(self.lesson_runtime_state.get('initial_metrics', {})) if isinstance(self.lesson_runtime_state.get('initial_metrics'), dict) else {},
                    'last_result': dict(self.lesson_runtime_state.get('last_result', {})) if isinstance(self.lesson_runtime_state.get('last_result'), dict) else {},
                    'selected_card_id': self.lesson_runtime_state.get('selected_card_id'),
                }
            )
        self.user_manager.mark_tutorial_lesson_completed(self.active_lesson_id, stars, stats=stats)

    def _advance_to_next_lesson(self):
        next_lesson_id = self._get_followup_lesson_id(self.active_lesson_id)
        if next_lesson_id:
            self._start_lesson(next_lesson_id)

    def _soft_drop_keycodes(self):
        """Tutorial için soft drop tuşlarını döndür (binding + aşağı ok)."""
        keys = set(self._action_keys(self.control_bindings, 'soft_drop'))
        keys.add(pygame.K_DOWN)
        return tuple(k for k in keys if isinstance(k, int))

    def _is_key_pressed(self, keycode: int, pressed_state=None) -> bool:
        """Tuş basılı mı? (arrow keys için scancode destekli)."""
        if pressed_state is None:
            pressed_state = pygame.key.get_pressed()
        try:
            scancode = pygame.key.get_scancode_from_key(keycode)
            if 0 <= scancode < len(pressed_state) and pressed_state[scancode]:
                return True
        except Exception:
            pass
        if 0 <= keycode < len(pressed_state):
            return bool(pressed_state[keycode])
        return False

    def _key_label(self, keycode: int) -> str:
        """Keycode için kullanıcıya gösterilecek kısa etiket üret."""
        try:
            name = pygame.key.name(int(keycode))
        except Exception:
            return 'KEY'
        if not name:
            return 'KEY'

        label = str(name).strip().upper()
        if label in ('RETURN', 'KP ENTER'):
            return 'ENTER'
        if label in ('LEFT SHIFT', 'RIGHT SHIFT'):
            return 'SHIFT'
        return label

    def _action_key_label(self, action: str, fallback: int | None = None, include_down_for_soft: bool = False) -> str:
        """Aksiyon için birincil/ikincil tuş etiketlerini birleştir."""
        keys = list(self._action_keys(self.control_bindings, action))
        if include_down_for_soft and pygame.K_DOWN not in keys:
            keys.append(pygame.K_DOWN)
        if fallback is not None and not keys:
            keys.append(fallback)

        labels = []
        for keycode in keys:
            if not isinstance(keycode, int):
                continue
            key_label = self._key_label(keycode)
            if key_label not in labels:
                labels.append(key_label)

        return ' / '.join(labels) if labels else 'KEY'

    def _reset_stuck_hint_state(self):
        self.step_idle_timer = 0.0
        self.stuck_hint_message = ""
        self.stuck_hint_pulse_timer = 0.0

    def _register_step_activity(self):
        self.step_idle_timer = 0.0
        self.stuck_hint_message = ""

    def _get_stuck_hint_text(self) -> str:
        left_key = self._action_key_label('move_left', pygame.K_LEFT)
        right_key = self._action_key_label('move_right', pygame.K_RIGHT)
        rotate_key = self._action_key_label('rotate', pygame.K_UP)
        soft_key = self._action_key_label('soft_drop', pygame.K_DOWN, include_down_for_soft=True)
        hard_drop_key = self._action_key_label('hard_drop', pygame.K_SPACE)
        hold_key = self._action_key_label('hold', pygame.K_c)

        key_map = {
            1: 'tutorial_stuck_step_1',
            2: 'tutorial_stuck_step_2',
            3: 'tutorial_stuck_step_3',
            4: 'tutorial_stuck_step_4',
            5: 'tutorial_stuck_step_5',
            6: 'tutorial_stuck_step_6',
            7: 'tutorial_stuck_step_7',
        }
        key = key_map.get(self.step)
        if not key:
            return ""
        return t(
            key,
            left_key=left_key,
            right_key=right_key,
            rotate_key=rotate_key,
            soft_key=soft_key,
            hard_drop_key=hard_drop_key,
            hold_key=hold_key,
        )
        
    def spawn_new_piece(self):
        # Tutorial'da da ana oyundaki torba (bag) mantığı kullanılsın.
        return super().spawn_new_piece()

    def _setup_step(self, step_num):
        lesson = get_lesson_for_legacy_step(step_num)
        if lesson:
            self.active_lesson_id = str(lesson.get('id'))
            self.active_lesson = lesson
        self.step = step_num
        self.in_transition = False
        self.waiting_for_enter = False
        self.lesson_result_active = False
        self.lesson_result = None
        self.card_choice_state = {}
        self.base_fall_speed = 2000
        self.fall_speed = self.base_fall_speed # Reset fall speed
        self.soft_drop_counter = 0 
        self.soft_drop_active = False
        self.sub_message = ""
        self.tip_message = ""
        self._reset_stuck_hint_state()
        
        # Reset counters
        self.step_move_left_count = 0
        self.step_move_right_count = 0
        self.step_rotate_count = 0
        self.step_lines = 0
        
        # Clear all effects for clean transition
        self.success_particles = []
        self.success_glow_timer = 0
        self.success_text_scale = 1.0
        self.step_completion_effects = []
        self.progress_celebration_timer = 0
        
        # CLEAR BOARD AND SPAWN NEW PIECE FOR EVERY STEP (Cleaner UX)
        # Exception: Step 5 needs a specific board setup
        if step_num != 5:
            self._clear_tutorial_board()
            self._ensure_normal_piece(force_new=True)

        # Step-specific welcome messages
        welcome_messages = {
            1: t('tutorial_welcome_move'),
            2: t('tutorial_welcome_rotate'),
            3: t('tutorial_welcome_soft_drop'),
            4: t('tutorial_welcome_hard_drop'),
            5: t('tutorial_welcome_line_clear'),
            6: t('tutorial_welcome_hold'),
            7: t('tutorial_welcome_complete')
        }
        
        if step_num in welcome_messages:
            self._create_mini_success_effect(welcome_messages[step_num])

        left_key = self._action_key_label('move_left', pygame.K_LEFT)
        right_key = self._action_key_label('move_right', pygame.K_RIGHT)
        rotate_key = self._action_key_label('rotate', pygame.K_UP)
        soft_key = self._action_key_label('soft_drop', pygame.K_DOWN, include_down_for_soft=True)
        hard_drop_key = self._action_key_label('hard_drop', pygame.K_SPACE)
        hold_key = self._action_key_label('hold', pygame.K_c)

        if step_num == 1: # Move
            self.step_target = 3
            self.overlay_message = t('tutorial_step_1', left_key=left_key, right_key=right_key)
            self.tip_message = t('tutorial_tip_step_1')
            self.sub_message = t('tutorial_sub_move', left=0, right=0)
            
        elif step_num == 2: # Rotate
            self.step_target = 3 
            self.overlay_message = t('tutorial_step_2', rotate_key=rotate_key)
            self.tip_message = t('tutorial_tip_step_2')
            self.sub_message = t('tutorial_sub_rotate', count=0, target=3)
            # Ensure T piece for rotation demo, centered
            self.current_piece = self._create_named_piece('T')
            self.current_piece.x = 4
            self.current_piece.y = 2
            self.apply_theme_to_pieces()
            
        elif step_num == 3: # Soft Drop
            self.step_target = 40 # Frames held ~0.7s (at 60fps)
            self.overlay_message = t('tutorial_step_3', soft_key=soft_key)
            self.tip_message = t('tutorial_tip_step_3')
            self.sub_message = t('tutorial_sub_soft_drop', soft_key=soft_key, progress=0, target=40)
            
        elif step_num == 4: # Hard Drop
            self.step_target = 1
            self.overlay_message = t('tutorial_step_4', hard_drop_key=hard_drop_key)
            self.tip_message = t('tutorial_tip_step_4')
            self.sub_message = t('tutorial_sub_hard_drop', hard_drop_key=hard_drop_key)
            
        elif step_num == 5: # Line Clear
            self.step_target = 1
            self.overlay_message = t('tutorial_step_5')
            self.tip_message = t('tutorial_tip_step_5')
            self.sub_message = t('tutorial_sub_line_clear')
            self._setup_line_clear_scenario()
            
        elif step_num == 6: # Hold
            self.step_target = 1
            self.overlay_message = t('tutorial_step_6', hold_key=hold_key)
            self.tip_message = t('tutorial_tip_step_6')
            self.sub_message = t('tutorial_sub_hold', hold_key=hold_key)
            self.can_hold = True
            self.held_piece = None
            
        elif step_num == 7: # Complete
            self.step_target = 1
            self.waiting_for_enter = True
            self.next_lesson_id = self._get_followup_lesson_id(self.active_lesson_id)
            self.overlay_message = self._lesson_title() or t('tutorial_complete')
            self.tip_message = t('tutorial_tip_step_7')
            if self.next_lesson_id:
                self.sub_message = t('tutorial_next_board_lessons_prompt', default='ENTER ile tahta derslerine gec.')
            else:
                self.sub_message = t('tutorial_sub_finish')

        self._sync_lesson_runtime_state()

    def _complete_step(self, next_step):
        if self.in_transition:
            return

        self._mark_active_lesson_completed(stars=1)
            
        self.in_transition = True
        self.transition_timer = 1.5 # 1.5 saniye daha uzun gösterim
        self.next_step_num = next_step
        next_lesson = get_lesson_for_legacy_step(next_step)
        self.next_lesson_id = next_lesson.get('id') if next_lesson else self._get_followup_lesson_id(self.active_lesson_id)
        
        # Başarı efektleri
        self._create_success_effects()
        self.sound.play('tutorial_complete')  # Daha özel ses
        
        # Reset speed immediately to prevent chaos during transition
        self.fall_speed = self.base_fall_speed 
        
        # Success messages
        msgs = [
            t('tutorial_success_1'),
            t('tutorial_success_2'),
            t('tutorial_success_3'),
            t('tutorial_success_4'),
            t('tutorial_success_5'),
            t('tutorial_success_6'),
        ]
        self.transition_text = random.choice(msgs)
        
        # Progress celebration
        self.progress_celebration_timer = 2.0
        step_names = {
            2: t('tutorial_step_done_move'),
            3: t('tutorial_step_done_rotate'),
            4: t('tutorial_step_done_soft_drop'),
            5: t('tutorial_step_done_hard_drop'),
            6: t('tutorial_step_done_line_clear'),
            7: t('tutorial_step_done_hold')
        }
        self.progress_celebration_text = step_names.get(next_step, t('tutorial_step_done_generic'))

    def _create_success_effects(self):
        """Başarı için parçacık efektleri oluştur"""
        self.success_particles = []
        self.success_glow_timer = 1.0
        self.success_text_scale = 1.5
        
        # Parçacık efektleri
        center_x = self.window_width // 2
        center_y = self.window_height // 2
        
        for _ in range(20):
            particle = {
                'x': center_x + random.randint(-50, 50),
                'y': center_y + random.randint(-50, 50),
                'vx': random.uniform(-100, 100),
                'vy': random.uniform(-150, -50),
                'life': 1.0,
                'color': random.choice([
                    (255, 215, 0),   # Altın
                    (0, 255, 255),   # Cyan
                    (255, 105, 180), # Pembe
                    (50, 255, 50),   # Yeşil
                    (255, 165, 0)    # Turuncu
                ]),
                'size': random.randint(3, 8)
            }
            self.success_particles.append(particle)
    
    def _update_success_effects(self, delta_seconds):
        """Başarı efektlerini güncelle"""
        # Parçacık güncellemesi
        for particle in self.success_particles[:]:
            particle['x'] += particle['vx'] * delta_seconds
            particle['y'] += particle['vy'] * delta_seconds
            particle['vy'] += 200 * delta_seconds  # Yerçekimi
            particle['life'] -= delta_seconds * 2
            
            if particle['life'] <= 0:
                self.success_particles.remove(particle)
        
        # Glow timer
        if self.success_glow_timer > 0:
            self.success_glow_timer -= delta_seconds
        
        # Text scale animation
        if self.success_text_scale > 1.0:
            self.success_text_scale -= delta_seconds * 2
            self.success_text_scale = max(1.0, self.success_text_scale)
        
        # Progress celebration
        if self.progress_celebration_timer > 0:
            self.progress_celebration_timer -= delta_seconds
    
    def _draw_success_effects(self):
        """Başarı efektlerini çiz"""
        # Parçacıkları çiz
        for particle in self.success_particles:
            alpha = int(particle['life'] * 255)
            if alpha > 0:
                color = (*particle['color'], alpha)
                pos = (int(particle['x']), int(particle['y']))
                
                # Parçacık çiz (daire)
                try:
                    surf = pygame.Surface((particle['size'] * 2, particle['size'] * 2), pygame.SRCALPHA)
                    pygame.draw.circle(surf, color, (particle['size'], particle['size']), particle['size'])
                    self.screen.blit(surf, (pos[0] - particle['size'], pos[1] - particle['size']))
                except:
                    # Fallback: basit nokta
                    pygame.draw.circle(self.screen, particle['color'][:3], pos, particle['size'])

    def _create_mini_success_effect(self, message):
        """Küçük başarı efekti oluştur"""
        self.step_completion_effects.append({
            'message': message,
            'timer': 1.0,
            'y_offset': 0,
            'alpha': 255,
            'scale': 1.2
        })
        # Mini başarı sesi
        self.sound.play('tutorial_progress')

    def _ensure_normal_piece(self, force_new=False):
        if force_new or not self.current_piece or self.current_piece.name == 'O':
            self.current_piece = self._create_named_piece('T')
            self.current_piece.x = 4
            self.current_piece.y = 0
            self.apply_theme_to_pieces()

    def _setup_line_clear_scenario(self):
        self._clear_tutorial_board()
        color = (100, 100, 100) # Gray
        bottom = self.board.height - 1
        above = self.board.height - 2

        # Kolay satır temizleme pratiği: kesin bir parça dayatmadan
        # oyuncuya bag'den gelen parça ile çözüm fırsatı verir.
        for x in range(self.board.width):
            if x not in (4, 5):
                self.board.grid[bottom][x] = color
                self.board.occupancy[bottom][x] = True

        for x in range(self.board.width):
            if x in (0, 1, 8, 9):
                self.board.grid[above][x] = color
                self.board.occupancy[above][x] = True

        if not self.current_piece:
            self.current_piece = self.spawn_new_piece()
        self.current_piece.x = 3
        self.current_piece.y = 0
        self.apply_theme_to_pieces()
    
    # --------------------------------------------------------------------------
    # INPUT FILTERING AND HANDLING
    # --------------------------------------------------------------------------
    def _handle_hub_input_event(self, event):
        chapter_left_keys = set(self._action_keys(self.control_bindings, 'move_left')) | {pygame.K_LEFT, pygame.K_a}
        chapter_right_keys = set(self._action_keys(self.control_bindings, 'move_right')) | {pygame.K_RIGHT, pygame.K_d}
        lesson_up_keys = {pygame.K_UP, pygame.K_w}
        lesson_down_keys = {pygame.K_DOWN, pygame.K_s}

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return 'menu'
            if event.key in chapter_left_keys:
                self._move_hub_chapter_selection(-1)
                return True
            if event.key in chapter_right_keys:
                self._move_hub_chapter_selection(1)
                return True
            if event.key in lesson_up_keys:
                self._move_hub_lesson_selection(-1)
                return True
            if event.key in lesson_down_keys:
                self._move_hub_lesson_selection(1)
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._start_selected_hub_lesson()
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
            if self.hub_back_rect and self.hub_back_rect.collidepoint(pos):
                return 'menu'
            if self.hub_start_rect and self.hub_start_rect.collidepoint(pos):
                self._start_selected_hub_lesson()
                return True
            for rect, chapter_id in self.hub_chapter_rects:
                if rect.collidepoint(pos):
                    self._select_hub_chapter(chapter_id)
                    self.sound.play('move')
                    return True
            for rect, lesson_id in self.hub_lesson_rects:
                if rect.collidepoint(pos):
                    self.hub_selected_lesson_id = str(lesson_id)
                    self.sound.play('move')
                    return True

        if event.type == pygame.MOUSEWHEEL:
            self._move_hub_lesson_selection(-1 if event.y > 0 else 1)
            return True

        return None

    def _is_action_allowed(self, action):
        """Step-specific input filtering."""
        if self.step == 1: # Move
            return action in ['move_left', 'move_right']
        elif self.step == 2: # Rotate
            return action == 'rotate'
        elif self.step == 3: # Soft Drop
            return action == 'soft_drop'
        elif self.step == 4: # Hard Drop
            return action == 'hard_drop'
        elif self.step == 5: # Line Clear
            return True # All allowed
        elif self.step == 6: # Hold
            return action in ['hold', 'move_left', 'move_right', 'soft_drop', 'rotate'] # Allow basics to survive
        elif self.step == 7: # Complete
            return False
        return False

    def handle_input(self):
        if self.game_over:
             return super().handle_input()
             
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            # --- EXIT PROMPT HANDLING (Mouse + Key) ---
            if self.show_exit_prompt:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_n):
                        self.show_exit_prompt = False
                        continue
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_y):
                        return 'menu'
                
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                    # Check rects provided by Game._draw_exit_prompt_overlay
                    if getattr(self, 'exit_yes_rect', None) and self.exit_yes_rect.collidepoint(pos):
                        return 'menu'
                    if getattr(self, 'exit_no_rect', None) and self.exit_no_rect.collidepoint(pos):
                        self.show_exit_prompt = False
                
                # Consume all events while prompt is active
                continue

            # --- STANDARD EVENTS ---
            if event.type == pygame.VIDEORESIZE:
                self.window_width = max(event.w, MIN_WINDOW_WIDTH)
                self.window_height = max(event.h, MIN_WINDOW_HEIGHT)
                self.screen = create_display(
                    self.window_width,
                    self.window_height,
                    fullscreen=False,
                    resizable=True,
                )
                self.update_fonts()
                if self.card_ui:
                    self.card_ui.set_overlay_reference_size(self.window_width, self.window_height)
                continue

            if self.hub_active:
                hub_action = self._handle_hub_input_event(event)
                if hub_action is not None:
                    return hub_action
                continue

            if self._is_card_choice_lesson_active() and not self.lesson_result_active:
                if event.type == pygame.MOUSEMOTION and self.card_ui:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                    self.card_ui.handle_mouse_move(pos)
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.card_ui:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                    choice = self.card_ui.handle_mouse_click(pos)
                    if isinstance(choice, int):
                        self._queue_card_choice_selection(choice)
                        continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.show_exit_prompt = True
                    continue
                
                # Block inputs during transition
                if self.in_transition:
                    continue
                
                if self.waiting_for_enter:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if self.user_manager:
                            self._mark_active_lesson_completed(stars=1)
                            self.user_manager.set_tutorial_completed(True)
                        if self.next_lesson_id:
                            self._start_lesson(self.next_lesson_id)
                            return True
                        if self.hub_return_enabled:
                            preferred_chapter_id = self.active_lesson.get('chapter') if isinstance(self.active_lesson, dict) else None
                            self._open_tutorial_hub(preferred_chapter_id=preferred_chapter_id, preferred_lesson_id=self.active_lesson_id)
                            return True
                        return 'menu'
                    continue

                if self.lesson_result_active:
                    if event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
                        if self.lesson_result and self.lesson_result.get('success') and event.key != pygame.K_r:
                            if self.next_lesson_id:
                                self._start_lesson(self.next_lesson_id)
                                return True
                            if self.hub_return_enabled:
                                preferred_chapter_id = self.active_lesson.get('chapter') if isinstance(self.active_lesson, dict) else None
                                self._open_tutorial_hub(preferred_chapter_id=preferred_chapter_id, preferred_lesson_id=self.active_lesson_id)
                                return True
                            return 'menu'
                        self._start_lesson(self.active_lesson_id)
                        return True
                    continue
                
                bindings = self.control_bindings

                if self._is_card_choice_lesson_active():
                    digit_map = {
                        pygame.K_1: 0,
                        pygame.K_2: 1,
                        pygame.K_3: 2,
                        pygame.K_KP1: 0,
                        pygame.K_KP2: 1,
                        pygame.K_KP3: 2,
                    }
                    if event.key in self._action_keys(bindings, 'move_left'):
                        self._move_card_choice_selection(-1)
                    elif event.key in self._action_keys(bindings, 'move_right'):
                        self._move_card_choice_selection(1)
                    elif event.key in digit_map:
                        self._queue_card_choice_selection(digit_map[event.key])
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._queue_card_choice_selection(self.card_choice_state.get('selected_index', 0))
                    continue

                if self._is_scenario_lesson_active():
                    if event.key in self._action_keys(bindings, 'move_left'):
                        if self._try_move_left():
                            self._register_step_activity()
                            self.sound.play('move')
                            self.step_move_left_count += 1
                            self._sync_lesson_runtime_state()
                    elif event.key in self._action_keys(bindings, 'move_right'):
                        if self._try_move_right():
                            self._register_step_activity()
                            self.sound.play('move')
                            self.step_move_right_count += 1
                            self._sync_lesson_runtime_state()
                    elif event.key in self._action_keys(bindings, 'rotate'):
                        original_x = self.current_piece.x
                        self.current_piece.rotate()
                        kicked = False
                        if not self.board.is_valid_position(self.current_piece):
                            for dx in [1, -1, 2, -2]:
                                self.current_piece.x = original_x + dx
                                if self.board.is_valid_position(self.current_piece):
                                    kicked = True
                                    break
                            if not kicked:
                                self.current_piece.x = original_x
                                for _ in range(3):
                                    self.current_piece.rotate()
                        if self.board.is_valid_position(self.current_piece):
                            self._register_step_activity()
                            self.sound.play('rotate')
                            self.step_rotate_count += 1
                            self._sync_lesson_runtime_state()
                    elif event.key in self._soft_drop_keycodes():
                        self._register_step_activity()
                        self.fall_speed = FAST_FALL_SPEED
                        self.soft_drop_active = True
                        self._sync_lesson_runtime_state()
                    elif event.key in self._action_keys(bindings, 'hard_drop'):
                        self._register_step_activity()
                        self._sync_lesson_runtime_state()
                        self._perform_hard_drop()
                    continue
                
                # --- Step Logic with Filtering ---
                
                # Step 1: Move Left/Right
                if self.step == 1:
                    if event.key in self._action_keys(bindings, 'move_left'):
                        if self._try_move_left():
                            self._register_step_activity()
                            self.sound.play('move')
                            self.step_move_left_count = min(3, self.step_move_left_count + 1)
                            self._sync_lesson_runtime_state()
                            self.sub_message = t('tutorial_sub_move', left=self.step_move_left_count, right=self.step_move_right_count)
                            
                            # Mini başarı efekti
                            if self.step_move_left_count <= 3:
                                self._create_mini_success_effect("Sol hareket!")
                            
                            if self.step_move_left_count >= 3 and self.step_move_right_count >= 3:
                                self._complete_step(2)
                    elif event.key in self._action_keys(bindings, 'move_right'):
                        if self._try_move_right():
                            self._register_step_activity()
                            self.sound.play('move')
                            self.step_move_right_count = min(3, self.step_move_right_count + 1)
                            self._sync_lesson_runtime_state()
                            self.sub_message = t('tutorial_sub_move', left=self.step_move_left_count, right=self.step_move_right_count)
                            
                            # Mini başarı efekti
                            if self.step_move_right_count <= 3:
                                self._create_mini_success_effect(t('tutorial_success_move_right'))
                            
                            if self.step_move_left_count >= 3 and self.step_move_right_count >= 3:
                                self._complete_step(2)
                                
                # Step 2: Rotate
                elif self.step == 2:
                    if event.key in self._action_keys(bindings, 'rotate'):
                        original_x = self.current_piece.x
                        self.current_piece.rotate()
                        # Simple wallkick
                        kicked = False
                        if not self.board.is_valid_position(self.current_piece):
                            for dx in [1, -1, 2, -2]:
                                self.current_piece.x = original_x + dx
                                if self.board.is_valid_position(self.current_piece):
                                    kicked = True
                                    break
                            if not kicked:
                                self.current_piece.x = original_x
                                for _ in range(3): self.current_piece.rotate()
                        
                        # Count rotation regardless of wallkick result for cleaner UX
                        # (If it rotates successfully or kicks successfully)
                        if self.board.is_valid_position(self.current_piece):
                            self._register_step_activity()
                            self.sound.play('rotate')
                            self.step_rotate_count += 1
                            self._sync_lesson_runtime_state()
                            self.sub_message = t('tutorial_sub_rotate', count=self.step_rotate_count, target=3)
                            
                            # Mini başarı efekti
                            self._create_mini_success_effect(t('tutorial_success_rotate'))
                            
                            if self.step_rotate_count >= self.step_target:
                                self._complete_step(3)

                # Step 3: Soft Drop
                elif self.step == 3:
                    if event.key in self._soft_drop_keycodes():
                        self._register_step_activity()
                        self.fall_speed = FAST_FALL_SPEED
                        self.soft_drop_active = True
                        self._sync_lesson_runtime_state()

                # Step 4: Hard Drop
                elif self.step == 4:
                    if event.key == bindings['hard_drop']:
                        self._register_step_activity()
                        self._perform_hard_drop()
                        self._create_mini_success_effect(t('tutorial_success_hard_drop'))
                        self._complete_step(5)

                # Step 5: Line Clear (Allow ALL moves to play naturally)
                elif self.step == 5:
                    if event.key in self._action_keys(bindings, 'move_left'):
                        if self._try_move_left():
                            self._register_step_activity()
                            self.sound.play('move')
                    elif event.key in self._action_keys(bindings, 'move_right'):
                        if self._try_move_right():
                            self._register_step_activity()
                            self.sound.play('move')
                    elif event.key in self._action_keys(bindings, 'rotate'):
                         self.current_piece.rotate()
                         if not self.board.is_valid_position(self.current_piece):
                             # simple kick try
                             orig_x = self.current_piece.x
                             kicked = False
                             for dx in [1, -1]: 
                                 self.current_piece.x = orig_x + dx
                                 if self.board.is_valid_position(self.current_piece): kicked=True; break
                             if not kicked:
                                 self.current_piece.x = orig_x
                                 for _ in range(3): self.current_piece.rotate()
                         else:
                             self._register_step_activity()
                             self.sound.play('rotate')
                    elif event.key in self._soft_drop_keycodes():
                        self._register_step_activity()
                        self.fall_speed = FAST_FALL_SPEED
                    elif event.key == bindings['hard_drop']:
                        self._register_step_activity()
                        self._perform_hard_drop()
                        
                # Step 6: Hold
                elif self.step == 6:
                    # Allow basic survival moves too
                    if event.key in self._action_keys(bindings, 'move_left'):
                        if self._try_move_left():
                            self._register_step_activity()
                            self.sound.play('move')
                    elif event.key in self._action_keys(bindings, 'move_right'):
                        if self._try_move_right():
                            self._register_step_activity()
                            self.sound.play('move')
                    elif event.key in self._action_keys(bindings, 'rotate'):
                        self.current_piece.rotate()
                        if not self.board.is_valid_position(self.current_piece):
                            for _ in range(3):
                                self.current_piece.rotate()
                        else:
                            self._register_step_activity()
                            self.sound.play('rotate')
                        
                    if event.key == bindings['hold']:
                        if self.can_hold:
                            self._register_step_activity()
                            if self.held_piece is None:
                                self.held_piece = self.current_piece
                                self.current_piece = self.next_piece_queue.pop(0)
                                self.next_piece_queue.append(self.spawn_new_piece())
                            else:
                                self.current_piece, self.held_piece = self.held_piece, self.current_piece
                                self.current_piece.x = 3
                                self.current_piece.y = 0
                            self.can_hold = False
                            self.sound.play('move')
                            self._create_mini_success_effect(t('tutorial_success_hold'))
                            self._complete_step(7)

            # GLOBAL KEYUP HANDLING (Safety)
            if event.type == pygame.KEYUP:
                if event.key in self._soft_drop_keycodes():
                    self.fall_speed = self.base_fall_speed
                    self.soft_drop_active = False

        return True

    def _perform_hard_drop(self):
        while self.board.is_valid_position(self.current_piece):
            self.current_piece.y += 1
        self.current_piece.y -= 1
        self.lock_and_new_piece()
        self.sound.play('drop')

    def _update_overlay_safe_visual_effects(self, delta_time):
        dt = max(0.0, float(delta_time or 0.0))
        dt_frames = dt / 16.666 if dt > 0 else 0.0

        if self.line_clear_animation > 0:
            self.line_clear_animation = float(self.line_clear_animation) - dt_frames
            frames_left = int(self.line_clear_animation)
            self.line_clear_flash = (frames_left % 10) < 5
            if self.line_clear_animation <= 0:
                self.line_clear_flash = False
                self.board.last_cleared_lines = []

        if self.line_clear_sweep_active:
            self.line_clear_sweep_progress += dt_frames * 0.06
            if self.line_clear_sweep_progress >= 1.0:
                self.line_clear_sweep_progress = 1.0
                self.line_clear_sweep_active = False
                self.line_clear_sweep_rows = []

        for wave in self.line_clear_wave_effects[:]:
            wave['radius'] += wave['speed'] * dt_frames
            wave['alpha'] = int(200 * (1 - wave['radius'] / wave['max_radius']))
            if wave['radius'] >= wave['max_radius'] or wave['alpha'] <= 0:
                self.line_clear_wave_effects.remove(wave)

        if self.falling_block_animations:
            fall_speed = self.block_fall_speed * dt_frames * 60
            sweep_progress = self.line_clear_sweep_progress
            for anim in self.falling_block_animations:
                if not anim.get('started', False) and sweep_progress >= anim.get('sweep_trigger', 0):
                    anim['started'] = True
                if anim.get('started', False):
                    anim['current_offset'] += fall_speed
                    if anim['current_offset'] >= 0:
                        anim['current_offset'] = 0
            self.falling_block_animations = [
                anim for anim in self.falling_block_animations
                if not (anim['current_offset'] >= 0 and anim.get('started', False))
            ]

        if self.combo_message_time > 0:
            self.combo_message_time = float(self.combo_message_time) - dt_frames
            if self.combo_message_time <= 0:
                self.combo_message_time = 0

        if self.drop_trails:
            self._update_drop_trails(dt_frames)

        self.update_particles(dt_ms=dt)
        self.update_ambient_particles(dt_ms=dt)
        self.update_screen_shake(dt_ms=dt)

    def lock_and_new_piece(self):
        # TUTORIAL OVERRIDE:
        # For Steps 1, 2, 3 (Move, Rotate, Soft Drop) -> DO NOT LOCK.
        # Just respawn piece at top to keep board clean and let user practice endlessly
        if self.step in [1, 2, 3] and not self._is_scenario_lesson_active():
            # Reset piece to top
            self._ensure_normal_piece(force_new=True)
            return

        lines_before = self.board.lines_cleared
        super().lock_and_new_piece()

        if self._is_scenario_lesson_active() and not self.in_transition and not self.lesson_result_active:
            outcome = self._evaluate_active_scenario()
            if outcome:
                self._show_lesson_result(outcome)
            return
        
        # Check line clear for Step 5
        if self.step == 5 and not self.in_transition:
            lines_after = self.board.lines_cleared
            if lines_after > lines_before:
                self._create_mini_success_effect(t('tutorial_success_line_clear'))
                self._complete_step(6)
            else:
                # Failed, reset
                self._setup_line_clear_scenario()
    
    def check_game_over(self):
        # Tutorial can't really lose, but if it happens, reset step
        if self._is_scenario_lesson_active() and self.board.is_game_over() and not self.lesson_result_active:
             current_metrics = capture_board_metrics(self.board)
             initial_metrics = self.lesson_runtime_state.get('initial_metrics', {}) if isinstance(self.lesson_runtime_state, dict) else {}
             self.game_over = False
             self._show_lesson_result(
                 {
                     'success': False,
                     'stars': 0,
                     'feedback_key': 'stack_too_high',
                     'line_delta': int(current_metrics.get('lines_cleared', 0) or 0) - int(initial_metrics.get('lines_cleared', 0) or 0),
                     'hole_delta': int(current_metrics.get('holes', 0) or 0) - int(initial_metrics.get('holes', 0) or 0),
                     'height_delta': int(current_metrics.get('max_height', 0) or 0) - int(initial_metrics.get('max_height', 0) or 0),
                 }
             )
             return
        if self.board.is_game_over():
             self._clear_tutorial_board()
             if self.step == 5:
                 self._setup_line_clear_scenario()

    def update(self, delta_time):
        dt_seconds = max(0.0, float(delta_time or 0.0)) / 1000.0

        # Handle transition delay
        if self.in_transition:
            self.transition_timer -= dt_seconds
            if self.transition_timer <= 0:
                if self.next_lesson_id:
                    self._start_lesson(self.next_lesson_id)
                else:
                    self._setup_step(self.next_step_num)
            # Transition sırasında da efektleri güncelle
            self._update_success_effects(dt_seconds)
            self._update_overlay_safe_visual_effects(delta_time)
            return
            
        # Başarı efektlerini güncelle
        self._update_success_effects(dt_seconds)

        if self.hub_active:
            self._update_overlay_safe_visual_effects(delta_time)
            return

        if self.lesson_result_active:
            self._update_overlay_safe_visual_effects(delta_time)
            return

        if self._is_card_choice_lesson_active():
            if self.card_ui:
                self.card_ui.update(delta_time, True)
                if self._pending_card_choice_index is not None and not self.card_ui.is_selection_animating():
                    self._finalize_pending_card_choice_selection()
            self._update_overlay_safe_visual_effects(delta_time)
            return

        if self.card_ui:
            self.card_ui.update(delta_time, False)
        
        # Mini başarı efektlerini güncelle
        for effect in self.step_completion_effects[:]:
            effect['timer'] -= dt_seconds
            effect['y_offset'] -= 30 * dt_seconds  # Yukarı hareket
            effect['alpha'] = int(255 * (effect['timer'] / 1.0))
            effect['scale'] = 1.2 - (0.2 * (1.0 - effect['timer']))
            
            if effect['timer'] <= 0:
                self.step_completion_effects.remove(effect)
            
        super().update(delta_time)

        if not self.waiting_for_enter and not self._is_scenario_lesson_active() and self.step < 7:
            self.step_idle_timer += dt_seconds
            self.stuck_hint_pulse_timer += dt_seconds
            if self.step_idle_timer >= self.stuck_hint_delay_s and not self.stuck_hint_message:
                self.stuck_hint_message = self._get_stuck_hint_text()
        
        # Step 3 progress tracking: check key hold
        if self.step == 3:
             if self.soft_drop_active:
                 self._register_step_activity()
                 self.soft_drop_counter += 1
                 # İlerleme göstergesi güncelle
                 progress = min(self.soft_drop_counter, self.step_target)
                 self._sync_lesson_runtime_state()
                 soft_key = self._action_key_label('soft_drop', pygame.K_DOWN, include_down_for_soft=True)
                 self.sub_message = t('tutorial_sub_soft_drop', soft_key=soft_key, progress=progress, target=self.step_target)
                 
                 if self.soft_drop_counter > self.step_target:
                     self._complete_step(4)

    def draw_mode_overlay(self):
        """Mod katmanına çizim (Game.draw içinde çağrılır)"""
        if self.hub_active:
            self._draw_tutorial_hub()
            return

        # Başarı efektlerini çiz
        self._draw_success_effects()
        
        # Mini başarı efektlerini çiz
        self._draw_mini_success_effects()

        if self._is_card_choice_lesson_active() and not self.lesson_result_active:
            self._draw_card_choice_overlay()
        else:
            # Tutorial overlay'ini çiz
            self._draw_tutorial_overlay()

        if self.lesson_result_active:
            self._draw_lesson_result_panel()
        
        # Progress celebration çiz
        self._draw_progress_celebration()
        
    def _draw_tutorial_overlay(self):
        # Oyun alanının sol tarafına konumlandırılmış kare panel
        # Board offset'ini al
        board_offset_x, board_offset_y = self.get_board_offset()
        cell_size = self.get_cell_size()
        ui_scale = self._ui_scale(min_scale=0.70, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        
        # Panel boyutları - yukarı doğru uzatılmış
        panel_width = s(260)
        panel_height = s(320)
        panel_margin = s(20)
        
        # Panel sol tarafta, board'un solunda
        panel_x = board_offset_x - panel_width - panel_margin
        # Dikey konum: eski alt kenarı koru, paneli yukarı doğru uzat
        base_panel_size = s(260)
        base_panel_y = board_offset_y + (self.board_height * cell_size - base_panel_size) // 2
        panel_y = base_panel_y - (panel_height - base_panel_size)
        
        # Ekran sınırlarını kontrol et
        if panel_x < s(10):
            panel_x = s(10)
        
        rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        retro_style.draw_glass_panel(self.screen, rect, alpha=220, border_color=(0, 200, 255))
        
        # Step Counter (üst kısım) - daha büyük font
        lesson_total = max(1, len(self.lesson_catalog))
        lesson_index = self._lesson_index()
        step_text = t('tutorial_lesson_counter', current=lesson_index, total=lesson_total, default=f'DERS {lesson_index}/{lesson_total}')
        if self.lesson_result_active and not self.next_lesson_id:
            step_text = t('tutorial_last_lesson', default='SON DERS')
        step_font = retro_style.get_font(s(18, minimum=12), bold=True)
        step_surf = step_font.render(step_text, True, (150, 220, 255))
        
        step_bg_rect = pygame.Rect(rect.right - step_surf.get_width() - s(18), rect.top + s(10), 
                      step_surf.get_width() + s(14), step_surf.get_height() + s(6))
        pygame.draw.rect(self.screen, (20, 30, 50, 180), step_bg_rect, border_radius=6)
        pygame.draw.rect(self.screen, (100, 150, 200), step_bg_rect, 1, border_radius=6)
        step_rect_pos = step_surf.get_rect(center=step_bg_rect.center)
        self.screen.blit(step_surf, step_rect_pos)
        
        # Mesaj (orta kısım) - daha büyük fontlar
        if self.in_transition:
            font = retro_style.get_font(max(s(16, minimum=12), int(s(26, minimum=16) * self.success_text_scale)), bold=True)
            text = self.transition_text
            color = (100, 255, 100)
            
            if self.success_glow_timer > 0:
                try:
                    glow_alpha = int(self.success_glow_timer * 150)
                    glow_surf = font.render(text, True, (255, 255, 255, glow_alpha))
                    for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2)]:
                        glow_rect = glow_surf.get_rect(center=(rect.centerx + dx, rect.centery - s(20) + dy))
                        self.screen.blit(glow_surf, glow_rect)
                except:
                    pass
        else:
            font = retro_style.get_font(s(20, minimum=12), bold=True)
            text = self.overlay_message
            color = (255, 255, 255)
        
        # Mesajı panele sığdır (kelime kaydırma)
        max_text_width = rect.width - s(30)
        lines = self._wrap_text(text, font, max_text_width)
        
        # Mesaj satırlarını çiz (üstteki ADIM etiketi ve alttaki sub/progress alanıyla çakışma olmasın)
        line_height = font.get_height() + s(6)
        content_top = step_bg_rect.bottom + s(12)
        content_bottom = rect.bottom - (s(74) if (not self.in_transition and self.sub_message) else s(20))
        content_height = max(0, content_bottom - content_top)
        max_lines = max(1, content_height // line_height)
        visible_lines = lines[:max_lines]
        total_h = len(visible_lines) * line_height
        start_y = content_top + max(0, (content_height - total_h) // 2)
        for i, line in enumerate(visible_lines):
            line_surf = font.render(line, True, color)
            line_rect = line_surf.get_rect(center=(rect.centerx, start_y + i * line_height))
            self.screen.blit(line_surf, line_rect)
        
        # Sub-message ve ilerleme çubuğu (alt kısım) - daha büyük font
        if not self.in_transition and self.sub_message:
            sub_font = retro_style.get_font(s(16, minimum=11))
            sub_surf = sub_font.render(self.sub_message, True, (180, 180, 180))
            sub_rect = sub_surf.get_rect(center=(rect.centerx, rect.bottom - s(55)))
            self.screen.blit(sub_surf, sub_rect)
            
            # İlerleme çubuğu (adım 1, 2, 3 için)
            if self.step in [1, 2, 3]:
                progress = 0
                if self.step == 1:
                    progress = (self.step_move_left_count + self.step_move_right_count) / 6.0
                elif self.step == 2:
                    progress = self.step_rotate_count / 3.0
                elif self.step == 3:
                    progress = min(self.soft_drop_counter / self.step_target, 1.0)
                
                # Progress bar - daha geniş
                bar_w = rect.width - s(40)
                bar_h = s(8)
                bar_x = rect.centerx - bar_w // 2
                bar_y = rect.bottom - s(25)
                
                # Arka plan
                pygame.draw.rect(self.screen, (50, 50, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
                
                # İlerleme
                if progress > 0:
                    progress_w = int(bar_w * progress)
                    progress_color = (50, 255, 50) if progress >= 1.0 else (100, 200, 255)
                    pygame.draw.rect(self.screen, progress_color, (bar_x, bar_y, progress_w, bar_h), border_radius=3)

        if not self.in_transition and self.tip_message:
            self._draw_tutorial_tip_panel(rect)

    def _draw_tutorial_tip_panel(self, main_rect: pygame.Rect):
        """Ana eğitim panelinin altında kısa tavsiye panelini çizer.

        TODO(Tutorial Companion):
        - Bu panelin soluna mentor karakter portresi ekle.
        - Tavsiyeyi karakterin konuşma balonunda göster.
        - Karakter ifadesini adıma göre değiştir (örn. Move, Rotate, Hold).
        """
        ui_scale = self._ui_scale(min_scale=0.70, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        tip_width = main_rect.width
        tip_height = s(132)
        tip_gap = s(14)

        tip_rect = pygame.Rect(main_rect.x, main_rect.bottom + tip_gap, tip_width, tip_height)
        if tip_rect.bottom > self.window_height - s(10):
            tip_rect.y = max(s(10), main_rect.y - tip_height - tip_gap)

        retro_style.draw_glass_panel(self.screen, tip_rect, alpha=210, border_color=(0, 200, 255))

        title_font = retro_style.get_font(s(15, minimum=11), bold=True)
        title_surf = title_font.render(t('tutorial_tip_title'), True, (140, 210, 255))
        title_rect = title_surf.get_rect(midtop=(tip_rect.centerx, tip_rect.y + s(10)))
        self.screen.blit(title_surf, title_rect)

        text_font = retro_style.get_font(s(16, minimum=11))
        text_color = (215, 225, 238)
        max_text_width = tip_rect.width - s(24)
        lines = self._wrap_text(self.tip_message, text_font, max_text_width)

        content_top = title_rect.bottom + s(8)
        content_bottom = tip_rect.bottom - s(10)
        content_height = max(0, content_bottom - content_top)
        line_height = text_font.get_height() + s(5)
        max_lines = max(1, content_height // line_height)
        visible_lines = lines[:max_lines]
        total_h = len(visible_lines) * line_height
        content_start_y = content_top + max(0, (content_height - total_h) // 2)

        for i, line in enumerate(visible_lines):
            line_surf = text_font.render(line, True, text_color)
            line_rect = line_surf.get_rect(center=(tip_rect.centerx, content_start_y + i * line_height))
            self.screen.blit(line_surf, line_rect)
            
    def _draw_mini_success_effects(self):
        """Mini başarı efektlerini çiz"""
        return

    def _draw_progress_celebration(self):
        """İlerleme kutlamasını çiz"""
        return

    def _draw_tutorial_hub(self):
        ui_scale = self._ui_scale(min_scale=0.72, max_scale=1.12)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        overlay = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        overlay.fill((4, 8, 18, 228))
        self.screen.blit(overlay, (0, 0))

        panel_width = min(self.window_width - s(48), s(1180))
        panel_height = min(self.window_height - s(48), s(720))
        panel_rect = pygame.Rect(
            (self.window_width - panel_width) // 2,
            (self.window_height - panel_height) // 2,
            panel_width,
            panel_height,
        )
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=230, border_color=(70, 190, 255))

        title_font = retro_style.get_font(s(28, minimum=18), bold=True)
        body_font = retro_style.get_font(s(16, minimum=11))
        small_font = retro_style.get_font(s(14, minimum=10))
        tiny_font = retro_style.get_font(s(12, minimum=9))

        title_text = t('tutorial_hub_title', default='Egitim Merkezi')
        subtitle_text = t(
            'tutorial_hub_subtitle',
            total_stars=self._get_total_tutorial_stars(),
            default=f"Tamamlanan dersleri tekrar oyna veya yeni bolumleri ac. Yildiz: {self._get_total_tutorial_stars()}",
        )
        title_surf = title_font.render(title_text, True, (255, 255, 255))
        self.screen.blit(title_surf, (panel_rect.x + s(26), panel_rect.y + s(22)))
        subtitle_lines = self._wrap_text(subtitle_text, body_font, panel_rect.width - s(52), max_lines=2)
        subtitle_y = panel_rect.y + s(58)
        for line in subtitle_lines:
            line_surf = body_font.render(line, True, (170, 210, 230))
            self.screen.blit(line_surf, (panel_rect.x + s(26), subtitle_y))
            subtitle_y += s(20)

        content_top = subtitle_y + s(16)
        content_height = panel_rect.height - (content_top - panel_rect.y) - s(98)
        chapter_rect = pygame.Rect(panel_rect.x + s(22), content_top, s(320), content_height)
        lesson_rect = pygame.Rect(chapter_rect.right + s(18), content_top, panel_rect.right - chapter_rect.right - s(40), content_height)

        retro_style.draw_glass_panel(self.screen, chapter_rect, alpha=170, border_color=(70, 150, 210))
        retro_style.draw_glass_panel(self.screen, lesson_rect, alpha=170, border_color=(80, 170, 120))

        chapter_header = title_font.render(t('tutorial_hub_chapters', default='Bolumler'), True, (150, 220, 255))
        lesson_header = title_font.render(t('tutorial_hub_lessons', default='Dersler'), True, (150, 255, 190))
        self.screen.blit(chapter_header, (chapter_rect.x + s(16), chapter_rect.y + s(14)))
        self.screen.blit(lesson_header, (lesson_rect.x + s(16), lesson_rect.y + s(14)))

        chapter_entries = self._get_hub_chapter_entries()
        self.hub_chapter_rects = []
        chapter_card_y = chapter_rect.y + s(60)
        chapter_gap = s(12)
        chapter_available_height = max(s(120), chapter_rect.height - s(76))
        chapter_count = max(1, len(chapter_entries))
        chapter_card_h = min(s(116), max(s(84), (chapter_available_height - chapter_gap * (chapter_count - 1)) // chapter_count))
        for entry in chapter_entries:
            chapter = entry['chapter']
            chapter_id = str(chapter.get('id') or '')
            is_selected = chapter_id == self.hub_selected_chapter_id
            is_locked = not entry.get('unlocked', False)
            compact_chapter_card = chapter_card_h <= s(92)
            card_rect = pygame.Rect(chapter_rect.x + s(12), chapter_card_y, chapter_rect.width - s(24), chapter_card_h)
            border_color = (255, 205, 90) if is_selected else ((100, 105, 120) if is_locked else (90, 180, 240))
            retro_style.draw_glass_panel(self.screen, card_rect, alpha=205, border_color=border_color)
            self.hub_chapter_rects.append((card_rect, chapter_id))

            chapter_title = self._lesson_title(chapter)
            title_color = (255, 255, 255) if not is_locked else (150, 155, 168)
            title_line = title_font.render(chapter_title, True, title_color)
            self.screen.blit(title_line, (card_rect.x + s(14), card_rect.y + s(10)))

            status_text = t(
                'tutorial_hub_chapter_status',
                completed=entry.get('completed_lessons', 0),
                total=entry.get('total_lessons', 0),
                stars=entry.get('stars', 0),
                default=f"{entry.get('completed_lessons', 0)}/{entry.get('total_lessons', 0)} ders  |  {entry.get('stars', 0)} yildiz",
            )
            status_surf = small_font.render(status_text, True, (170, 205, 225) if not is_locked else (130, 135, 145))
            status_y = card_rect.y + (s(38) if compact_chapter_card else s(42))
            self.screen.blit(status_surf, (card_rect.x + s(14), status_y))

            if not compact_chapter_card:
                chapter_desc = t(chapter.get('description_key'), default=chapter.get('description_fallback', '')) if chapter.get('description_key') else str(chapter.get('description_fallback', ''))
                desc_lines = self._wrap_text(chapter_desc, small_font, card_rect.width - s(28), max_lines=2)
                desc_y = card_rect.y + s(64)
                for line in desc_lines:
                    line_surf = small_font.render(line, True, (208, 216, 225) if not is_locked else (120, 124, 132))
                    self.screen.blit(line_surf, (card_rect.x + s(14), desc_y))
                    desc_y += s(16)

            footer_text = t('tutorial_hub_locked', default='Kilitli') if is_locked else (t('tutorial_hub_completed', default='Tamamlandi') if entry.get('completed') else t('tutorial_hub_in_progress', default='Devam ediyor'))
            footer_surf = tiny_font.render(footer_text, True, (255, 210, 120) if is_locked else (150, 255, 180))
            self.screen.blit(footer_surf, (card_rect.right - footer_surf.get_width() - s(12), card_rect.bottom - s(20)))

            chapter_card_y += chapter_card_h + chapter_gap

        lesson_entries = self._get_hub_lesson_entries(self.hub_selected_chapter_id) if self.hub_selected_chapter_id else []
        selected_chapter_entry = next((entry for entry in chapter_entries if entry['chapter'].get('id') == self.hub_selected_chapter_id), None)
        chapter_locked = bool(selected_chapter_entry) and not selected_chapter_entry.get('unlocked', False)

        self.hub_lesson_rects = []
        lesson_card_y = lesson_rect.y + s(60)
        lesson_gap = s(8)
        if chapter_locked:
            locked_lines = self._wrap_text(t('tutorial_hub_locked_hint', default='Bu bolum onceki egitimler tamamlaninca acilir.'), body_font, lesson_rect.width - s(32), max_lines=3)
            hint_y = lesson_card_y + s(24)
            for line in locked_lines:
                line_surf = body_font.render(line, True, (210, 190, 150))
                self.screen.blit(line_surf, (lesson_rect.x + s(16), hint_y))
                hint_y += s(22)
        else:
            lesson_available_height = max(s(180), lesson_rect.height - s(76))
            lesson_count = max(1, len(lesson_entries))
            lesson_card_h = min(s(78), max(s(56), (lesson_available_height - lesson_gap * (lesson_count - 1)) // lesson_count))
            description_line_limit = 2 if lesson_card_h >= s(72) else 1
            for entry in lesson_entries:
                lesson = entry['lesson']
                lesson_id = str(lesson.get('id') or '')
                is_selected = lesson_id == self.hub_selected_lesson_id
                compact_lesson_card = lesson_card_h <= s(62)
                row_rect = pygame.Rect(lesson_rect.x + s(12), lesson_card_y, lesson_rect.width - s(24), lesson_card_h)
                border_color = (255, 205, 90) if is_selected else (100, 190, 130)
                retro_style.draw_glass_panel(self.screen, row_rect, alpha=205, border_color=border_color)
                self.hub_lesson_rects.append((row_rect, lesson_id))

                title_line = body_font.render(self._lesson_title(lesson), True, (255, 255, 255))
                self.screen.blit(title_line, (row_rect.x + s(14), row_rect.y + s(10)))

                if not compact_lesson_card:
                    lesson_desc = self._lesson_description(lesson)
                    desc_lines = self._wrap_text(lesson_desc, small_font, row_rect.width - s(28), max_lines=description_line_limit)
                    desc_y = row_rect.y + s(34)
                    for line in desc_lines:
                        line_surf = small_font.render(line, True, (205, 215, 223))
                        self.screen.blit(line_surf, (row_rect.x + s(14), desc_y))
                        desc_y += s(16)

                status_text = t(
                    'tutorial_hub_lesson_status',
                    stars=entry.get('stars', 0),
                    default=f"Yildiz: {entry.get('stars', 0)}/3",
                )
                if entry.get('completed'):
                    status_text = f"{status_text}  |  {t('tutorial_hub_completed', default='Tamamlandi')}"
                status_surf = tiny_font.render(status_text, True, (150, 230, 180))
                status_y = row_rect.y + (s(32) if compact_lesson_card else lesson_card_h - s(20))
                self.screen.blit(status_surf, (row_rect.right - status_surf.get_width() - s(12), status_y))

                lesson_card_y += lesson_card_h + lesson_gap

        controls_text = t(
            'tutorial_hub_controls',
            default='Sol/Sag: bolum  Yukari/Asagi: ders  Enter: baslat  ESC: menu',
        )
        controls_surf = small_font.render(controls_text, True, (170, 200, 220))
        self.screen.blit(controls_surf, (panel_rect.x + s(24), panel_rect.bottom - s(72)))

        button_y = panel_rect.bottom - s(58)
        button_h = s(42)
        back_rect = pygame.Rect(panel_rect.x + s(22), button_y, s(160), button_h)
        start_rect = pygame.Rect(panel_rect.right - s(222), button_y, s(200), button_h)
        self.hub_back_rect = back_rect
        self.hub_start_rect = start_rect

        back_hover = back_rect.collidepoint(get_mouse_pos())
        start_hover = start_rect.collidepoint(get_mouse_pos())
        retro_style.draw_uniform_button(
            self.screen,
            back_rect,
            t('tutorial_hub_back', default='Menuye Don'),
            sub_text='ESC',
            color_code=retro_style.secondary,
            selected=back_hover,
            state='hover' if back_hover else 'normal',
        )
        can_start = bool(selected_chapter_entry) and selected_chapter_entry.get('unlocked') and bool(self.hub_selected_lesson_id)
        start_label = t('tutorial_hub_start', default='Dersi Baslat') if can_start else t('tutorial_hub_locked', default='Kilitli')
        retro_style.draw_uniform_button(
            self.screen,
            start_rect,
            start_label,
            sub_text='ENTER',
            color_code=retro_style.success if can_start else retro_style.primary,
            selected=start_hover,
            state='hover' if start_hover else 'normal',
        )

    def _draw_card_choice_overlay(self):
        if not isinstance(self.card_choice_state, dict):
            return
        scenario = self.card_choice_state.get('scenario', {})
        if not isinstance(scenario, dict):
            return
        choices = scenario.get('choices', [])
        if not choices:
            return

        if self.card_ui:
            fonts = self._build_tutorial_card_ui_font_pack()
            header_lines = []
            wrap_font = fonts.get('small') or fonts.get('desc')
            wrap_width = max(240, self.window_width - 280)
            for raw_line in list(scenario.get('context_lines', []) or [])[:2]:
                header_lines.extend(self._wrap_text(str(raw_line), wrap_font, wrap_width, max_lines=2))
            header_lines = header_lines[:4]
            mouse_pos = get_mouse_pos() if pygame.mouse.get_focused() else None
            mouse_over_card = False
            if mouse_pos:
                for rect in list(getattr(self.card_ui, 'card_rects', []) or []):
                    if rect and rect.collidepoint(mouse_pos):
                        mouse_over_card = True
                        break
            forced_hover_index = None
            if not mouse_over_card:
                forced_hover_index = int(self.card_choice_state.get('selected_index', 0) or 0)
            self.card_ui.draw_selection_overlay(
                self.screen,
                self.window_width,
                self.window_height,
                fonts,
                choices,
                '',
                False,
                forced_hover_index=forced_hover_index,
                show_secondary_actions=False,
                show_peek_button=False,
                header_title=self._lesson_title() or t('tutorial_card_context_title', default='Ders Baglami'),
                header_lines=header_lines,
            )
            return

        ui_scale = self._ui_scale(min_scale=0.70, max_scale=1.10)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        context_width = min(self.window_width - s(40), s(980))
        context_height = s(92)
        context_rect = pygame.Rect(
            (self.window_width - context_width) // 2,
            s(24),
            context_width,
            context_height,
        )
        retro_style.draw_glass_panel(self.screen, context_rect, alpha=220, border_color=(255, 190, 80))

        title_font = retro_style.get_font(s(16, minimum=11), bold=True)
        body_font = retro_style.get_font(s(14, minimum=10))
        title_surface = title_font.render(t('tutorial_card_context_title', default='Ders Baglami'), True, (255, 220, 150))
        self.screen.blit(title_surface, (context_rect.x + s(18), context_rect.y + s(12)))

        context_lines = list(scenario.get('context_lines', []) or [])[:2]
        line_y = context_rect.y + s(40)
        for line in context_lines:
            line_surface = body_font.render(str(line), True, (230, 235, 242))
            self.screen.blit(line_surface, (context_rect.x + s(18), line_y))
            line_y += s(20)

        card_gap = s(18)
        card_width = min(s(290), max(s(180), (context_width - (card_gap * (len(choices) - 1))) // len(choices)))
        card_height = s(280)
        total_width = card_width * len(choices) + card_gap * (len(choices) - 1)
        start_x = (self.window_width - total_width) // 2
        y = context_rect.bottom + s(18)
        selected_index = int(self.card_choice_state.get('selected_index', 0) or 0)

        title_card_font = retro_style.get_font(s(18, minimum=12), bold=True)
        meta_font = retro_style.get_font(s(13, minimum=9))
        desc_font = retro_style.get_font(s(14, minimum=10))

        for index, card in enumerate(choices):
            rect = pygame.Rect(start_x + index * (card_width + card_gap), y, card_width, card_height)
            border_color = (255, 210, 100) if index == selected_index else (120, 150, 180)
            retro_style.draw_glass_panel(self.screen, rect, alpha=225, border_color=border_color)

            number_text = f"{index + 1}"
            number_surface = meta_font.render(number_text, True, border_color)
            self.screen.blit(number_surface, (rect.x + s(12), rect.y + s(10)))

            title_text = get_tutorial_card_title(card)
            title_surface = title_card_font.render(title_text, True, (255, 255, 255))
            self.screen.blit(title_surface, (rect.x + s(12), rect.y + s(34)))

            rarity_text = get_tutorial_card_rarity_label(card)
            type_text = get_tutorial_card_type_label(card)
            rarity_surface = meta_font.render(rarity_text, True, (255, 220, 140))
            type_surface = meta_font.render(type_text, True, (180, 220, 255))
            self.screen.blit(rarity_surface, (rect.x + s(12), rect.y + s(66)))
            self.screen.blit(type_surface, (rect.x + s(12), rect.y + s(86)))

            description = get_tutorial_card_description(card)
            max_width = rect.width - s(24)
            lines = self._wrap_text(description, desc_font, max_width)

            cursor_y = rect.y + s(118)
            for line in lines[:6]:
                line_surface = desc_font.render(line, True, (220, 230, 240))
                self.screen.blit(line_surface, (rect.x + s(12), cursor_y))
                cursor_y += s(18)

            hint_text = t('tutorial_card_hint_selected', default='ENTER ile sec') if index == selected_index else t('tutorial_card_hint_controls', default='Secmek icin numara veya ok tuslari')
            hint_surface = meta_font.render(hint_text, True, border_color)
            self.screen.blit(hint_surface, (rect.x + s(12), rect.bottom - s(22)))

    def _draw_lesson_result_panel(self):
        if not isinstance(self.lesson_result, dict):
            return

        ui_scale = self._ui_scale(min_scale=0.72, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        overlay = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))
        panel_width = s(380)
        panel_height = s(210)
        rect = pygame.Rect(
            (self.window_width - panel_width) // 2,
            (self.window_height - panel_height) // 2,
            panel_width,
            panel_height,
        )
        retro_style.draw_glass_panel(self.screen, rect, alpha=235, border_color=(40, 220, 140) if self.lesson_result.get('success') else (220, 120, 80))

        title_font = retro_style.get_font(s(24, minimum=16), bold=True)
        body_font = retro_style.get_font(s(16, minimum=11))
        small_font = retro_style.get_font(s(14, minimum=10))

        title_surf = title_font.render(str(self.lesson_result.get('title', t('tutorial_result_title', default='Sonuc'))), True, (255, 255, 255))
        self.screen.blit(title_surf, title_surf.get_rect(center=(rect.centerx, rect.y + s(28))))

        stars_text = t(
            'tutorial_result_stars',
            stars=int(self.lesson_result.get('stars', 0) or 0),
            default=f"Yildiz: {int(self.lesson_result.get('stars', 0) or 0)}/3",
        )
        stars_surf = body_font.render(stars_text, True, (255, 220, 120))
        self.screen.blit(stars_surf, stars_surf.get_rect(center=(rect.centerx, rect.y + s(64))))

        max_text_width = rect.width - s(32)
        feedback = str(self.lesson_result.get('feedback', ''))
        lines = self._wrap_text(feedback, body_font, max_text_width, max_lines=3)

        start_y = rect.y + s(92)
        for index, line in enumerate(lines[:3]):
            line_surf = body_font.render(line, True, (220, 230, 240))
            self.screen.blit(line_surf, line_surf.get_rect(center=(rect.centerx, start_y + index * s(22))))

        stats_text = t(
            'tutorial_result_metrics',
            lines=int(self.lesson_result.get('line_delta', 0) or 0),
            holes=f"{int(self.lesson_result.get('hole_delta', 0) or 0):+d}",
            height=f"{int(self.lesson_result.get('height_delta', 0) or 0):+d}",
            default=(
                f"Satir {int(self.lesson_result.get('line_delta', 0) or 0)}  "
                f"Delik {int(self.lesson_result.get('hole_delta', 0) or 0):+d}  "
                f"Yukseklik {int(self.lesson_result.get('height_delta', 0) or 0):+d}"
            ),
        )
        if self.lesson_result.get('selected_card_title'):
            stats_text = (
                f"{t('tutorial_result_selected_label', default='Secilen')}: {self.lesson_result.get('selected_card_title', '')}  "
                f"{t('tutorial_result_ideal_label', default='Ideal')}: {self.lesson_result.get('recommended_card_title', '')}"
            )
        stats_lines = self._wrap_text(stats_text, small_font, rect.width - s(28), max_lines=2)
        stats_start_y = rect.bottom - (s(58) if len(stats_lines) > 1 else s(44))
        for index, line in enumerate(stats_lines):
            stats_surf = small_font.render(line, True, (150, 205, 230))
            self.screen.blit(stats_surf, stats_surf.get_rect(center=(rect.centerx, stats_start_y + index * s(16))))

        action_surf = small_font.render(str(self.lesson_result.get('action_text', 'ENTER')), True, (255, 255, 255))
        self.screen.blit(action_surf, action_surf.get_rect(center=(rect.centerx, rect.bottom - s(18))))
