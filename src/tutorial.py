import pygame
import random
import os
import math

_compute_line_sweep_progress_speed = None

try:
    from .game import Game  # type: ignore
    from .localization import t  # type: ignore
    from .retro_style import retro_style  # type: ignore
    from .constants import *  # type: ignore
    from .pieces import create_piece_by_name  # type: ignore
    from .platform_utils import create_display, normalize_mouse_pos, get_mouse_pos  # type: ignore
    from .tutorial_lessons import (  # type: ignore
        get_chapters,
        get_chapter,
        get_first_lesson_id,
        get_lesson,
        get_lesson_for_legacy_step,
        get_lessons,
        list_lessons_for_chapter,
        get_next_lesson_id,
    )
    from .tutorial_progress import build_default_tutorial_progress, migrate_legacy_progress  # type: ignore
    from .tutorial_scenarios import (  # type: ignore
        build_occupancy_from_rows,
        capture_board_metrics,
        evaluate_scenario,
        enrich_scenario_outcome,
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
    from .ui_scaling import get_modal_scale, get_projected_effective_scale  # type: ignore
    from .sweep_effects import compute_line_sweep_progress_speed as _compute_line_sweep_progress_speed  # type: ignore
except Exception:
    from game import Game
    from localization import t
    from retro_style import retro_style
    from constants import *
    from pieces import create_piece_by_name
    from platform_utils import create_display, normalize_mouse_pos, get_mouse_pos
    from tutorial_lessons import (
        get_chapters,
        get_chapter,
        get_first_lesson_id,
        get_lesson,
        get_lesson_for_legacy_step,
        get_lessons,
        list_lessons_for_chapter,
        get_next_lesson_id,
    )
    from tutorial_progress import build_default_tutorial_progress, migrate_legacy_progress
    from tutorial_scenarios import (
        build_occupancy_from_rows,
        capture_board_metrics,
        evaluate_scenario,
        enrich_scenario_outcome,
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
    from ui_scaling import get_modal_scale, get_projected_effective_scale
    try:
        from sweep_effects import compute_line_sweep_progress_speed as _compute_line_sweep_progress_speed
    except Exception:
        _compute_line_sweep_progress_speed = None


if _compute_line_sweep_progress_speed is None:
    def _compute_line_sweep_progress_speed(base_block_speed: float, sweep_travel_px: float, level: int | float = 1) -> float:
        travel_px = max(1.0, float(sweep_travel_px))
        block_speed = max(0.001, float(base_block_speed))
        try:
            level_i = max(1, int(level))
        except Exception:
            level_i = 1
        base_duration = travel_px / (block_speed * 3600.0)
        duration_ratio = max(0.42, 0.965 ** max(0, level_i - 1))
        sweep_duration = max(0.0001, base_duration * duration_ratio)
        return 1.0 / sweep_duration


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


TUTORIAL_MODAL_REFERENCE_SIZE = (1366.0, 768.0)

class TutorialMode(Game):
    def __init__(self, difficulty='Normal', sound_enabled=True, effects_enabled=True, 
                 achievement_manager=None, theme_manager=None, screen=None, 
                 fullscreen=False, settings_manager=None, user_manager=None, 
                 game_mode='tutorial', sound_manager=None, score_manager=None, 
                 block_style_manager=None, launch_lesson_id=None, lesson_flow_scope='full',
                 entry_source=None, return_target=None):
        
        super().__init__(difficulty, sound_enabled, effects_enabled, achievement_manager, 
                         theme_manager, screen, fullscreen, settings_manager, user_manager, 
                         game_mode, sound_manager, 
                         block_style_manager=block_style_manager,
                         score_manager=score_manager)
        
        self.entry_source = entry_source or 'menu'
        self.return_target = return_target or 'menu'
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
        self._scenario_allow_hold = False
        
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
        # İlk derslerde board ortasında çıkan "hangi tuşa bas" rehber paneli.
        self.inline_howto_active = False
        self.inline_howto_text = ""
        self.inline_howto_pulse = 0.0
        
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
        self.lesson_result_primary_rect = None
        self.lesson_attempt_counts = {}
        self.card_choice_state = {}
        # FAZ C — Ders öncesi briefing mikro-ekranı state'i
        self.lesson_stage = "play"
        self.briefing_active = False
        self.briefing_data = None
        self._pending_briefing_lesson_id = None
        self.briefing_start_rect = None
        self.briefing_skip_rect = None
        self.briefing_seen_lessons = set()
        # FAZ 2 — Bölüm bitince çıkan ilerleme paneli (devam et / çıkıp oyna) state'i.
        self.progress_panel_active = False
        self.progress_panel_data = None
        self.progress_panel_continue_rect = None
        self.progress_panel_play_rect = None
        self.progress_panel_hub_rect = None
        self.progress_panel_selected_index = 0
        self._auto_continue_after_transition = False
        self.progress_panel_anim = 0.0
        # FAZ D — Canlı hedef chip'leri + board highlight state'i
        self.board_highlight_timer = 0.0
        self.board_highlight_duration_s = 3.0
        self.board_highlight_spec = None
        self._board_highlight_allowed = False
        self._board_highlight_last_index = -1
        self._objective_chip_states = {}
        # Hold kutucuğu vurgusu (hold dersleri; sınavlarda gösterilmez)
        self.hold_highlight_active = False
        self.hold_highlight_armed = False
        self.hold_highlight_index = 0
        self.hold_highlight_pulse = 0.0
        self._board_highlight_last_index = -1
        self.card_ui = MysteryCardUI() if MysteryCardUI else None
        self._pending_card_choice_index = None
        # FAZ 7 — Kart etkisi canlı gösterim (showcase) sahnesi state'i.
        self.card_effect_showcase_timer = 0.0
        self.card_effect_showcase_duration_s = 1.25
        # Ö3a — Bu oturumda showcase'i gösterilmiş animasyonlu kart efektleri.
        self._shown_card_effect_ids = set()
        self.card_effect_highlight_timer = 0.0
        self.card_effect_highlight_duration_s = 0.7
        self.card_effect_highlight_cells = set()
        self.card_effect_showcase_phase = 'highlight'
        self.lesson_flow_scope = 'chapter' if lesson_flow_scope == 'chapter' else 'full'
        self.hub_return_enabled = launch_lesson_id is None
        self.hub_active = False
        self.hub_selected_chapter_id = None
        self.hub_selected_lesson_id = None
        self.hub_chapter_rects = []
        self.hub_lesson_rects = []
        self.hub_start_rect = None
        self.hub_back_rect = None
        self.hub_arrow_left_rect = None
        self.hub_arrow_right_rect = None
        self._hub_carousel_anim_offset = 0.0
        self._hub_carousel_anim_target = 0.0
        self._hub_carousel_prev_chapter_id = None
        self.hub_progress_snapshot = build_default_tutorial_progress()
        self._tutorial_arrow_icon_left_base = None
        self._tutorial_arrow_icon_right_base = None
        self._tutorial_arrow_icon_cache = {}
        self._load_tutorial_arrow_icons()
        self._tutorial_star_icon_base = None
        self._tutorial_star_icon_cache = {}
        self._load_tutorial_star_icon()
        self._load_lesson_catalog()
        self._sync_tutorial_card_overlay_reference()
        
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
        if getattr(self, 'briefing_active', False):
            return True
        # İlerleme paneli açıkken imleç görünür kalsın (tıklanabilir butonlar var).
        if getattr(self, 'progress_panel_active', False):
            return True
        # Sonuç paneli açıkken imleç görünür kalsın (tıklanabilir Devam/Tekrar butonu var).
        if getattr(self, 'lesson_result_active', False):
            return True
        if self._is_card_choice_lesson_active() and not getattr(self, 'lesson_result_active', False):
            return True
        return super().wants_mouse_visible()

    def _sync_tutorial_card_overlay_reference(self) -> None:
        if self.card_ui:
            self.card_ui.set_overlay_reference_size(
                int(TUTORIAL_MODAL_REFERENCE_SIZE[0]),
                int(TUTORIAL_MODAL_REFERENCE_SIZE[1]),
            )

    def _load_tutorial_star_icon(self):
        self._tutorial_star_icon_base = None
        self._tutorial_star_icon_cache = {}

        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'ui', 'egitim_star.png'),
            os.path.join(os.path.dirname(__file__), 'assets', 'ui', 'egitim_star.png'),
            'assets/ui/egitim_star.png',
            '../assets/ui/egitim_star.png',
        ]

        for path in possible_paths:
            try:
                if os.path.exists(path):
                    self._tutorial_star_icon_base = pygame.image.load(path).convert_alpha()
                    break
            except Exception:
                continue

    def _load_tutorial_arrow_icons(self):
        self._tutorial_arrow_icon_left_base = None
        self._tutorial_arrow_icon_right_base = None
        self._tutorial_arrow_icon_cache = {}

        left_paths = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'ui', 'egitim_arrow_left.png'),
            os.path.join(os.path.dirname(__file__), 'assets', 'ui', 'egitim_arrow_left.png'),
            'assets/ui/egitim_arrow_left.png',
            '../assets/ui/egitim_arrow_left.png',
        ]
        right_paths = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'ui', 'egitim_arrow_right.png'),
            os.path.join(os.path.dirname(__file__), 'assets', 'ui', 'egitim_arrow_right.png'),
            'assets/ui/egitim_arrow_right.png',
            '../assets/ui/egitim_arrow_right.png',
        ]

        for path in left_paths:
            try:
                if os.path.exists(path):
                    self._tutorial_arrow_icon_left_base = pygame.image.load(path).convert_alpha()
                    break
            except Exception:
                continue

        for path in right_paths:
            try:
                if os.path.exists(path):
                    self._tutorial_arrow_icon_right_base = pygame.image.load(path).convert_alpha()
                    break
            except Exception:
                continue

    def _get_tutorial_arrow_icon(self, direction, width, height, hover=False):
        if direction == 'left':
            base_icon = self._tutorial_arrow_icon_left_base
        else:
            base_icon = self._tutorial_arrow_icon_right_base

        if base_icon is None:
            return None

        width = max(8, int(width))
        height = max(8, int(height))
        cache_key = (direction, width, height, bool(hover))
        cached = self._tutorial_arrow_icon_cache.get(cache_key)
        if cached is not None:
            return cached

        icon = pygame.transform.smoothscale(base_icon, (width, height))
        # İkonun dış köşelerini yumuşat; kutu/sert köşe hissini azalt.
        mask = pygame.Surface((width, height), pygame.SRCALPHA)
        mask_radius = max(3, int(min(width, height) * 0.22))
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=mask_radius)
        icon.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        if not hover:
            icon.fill((205, 215, 232, 215), special_flags=pygame.BLEND_RGBA_MULT)

        self._tutorial_arrow_icon_cache[cache_key] = icon
        return icon

    def _get_tutorial_star_icon(self, size, filled=True, locked=False):
        base_icon = self._tutorial_star_icon_base
        if base_icon is None:
            return None

        size = max(6, int(size))
        cache_key = (size, bool(filled), bool(locked))
        cached = self._tutorial_star_icon_cache.get(cache_key)
        if cached is not None:
            return cached

        if base_icon.get_width() == size and base_icon.get_height() == size:
            icon = base_icon.copy()
        else:
            icon = pygame.transform.smoothscale(base_icon, (size, size))

        if not filled:
            icon.fill((95, 105, 130, 255), special_flags=pygame.BLEND_RGBA_MULT)
            icon.fill((255, 255, 255, 170), special_flags=pygame.BLEND_RGBA_MULT)
        if locked:
            icon.fill((155, 165, 180, 225), special_flags=pygame.BLEND_RGBA_MULT)

        self._tutorial_star_icon_cache[cache_key] = icon
        return icon

    def _blit_tutorial_star_icon(self, x, y, size, filled=True, locked=False):
        icon = self._get_tutorial_star_icon(size, filled=filled, locked=locked)
        if icon is not None:
            self.screen.blit(icon, (int(x), int(y)))
            return

        center = (int(x) + int(size) // 2, int(y) + int(size) // 2)
        color = (255, 215, 0) if filled else (100, 110, 130)
        pygame.draw.circle(self.screen, color, center, max(2, int(size) // 3))

    def _draw_tutorial_star_row(self, x, y, filled_count, total_count, size, gap=2, locked=False):
        total_count = max(0, int(total_count))
        filled_count = max(0, min(total_count, int(filled_count)))
        size = max(6, int(size))
        gap = max(0, int(gap))

        cursor_x = int(x)
        for index in range(total_count):
            self._blit_tutorial_star_icon(
                cursor_x,
                int(y),
                size,
                filled=index < filled_count,
                locked=locked,
            )
            cursor_x += size + gap

        if total_count <= 0:
            return 0
        return (total_count * size) + ((total_count - 1) * gap)

    def _get_left_gameplay_reserve_width(self) -> int:
        ui_scale = self._tutorial_modal_scale(min_scale=0.70, max_scale=1.18)
        return self._sx(260, ui_scale) + self._sx(20, ui_scale, minimum=0)

    def _tutorial_modal_scale(self, min_scale: float = 0.72, max_scale: float = 1.18) -> float:
        try:
            return get_projected_effective_scale(
                self.screen,
                min_scale=min_scale,
                max_scale=max_scale,
                reference_size=TUTORIAL_MODAL_REFERENCE_SIZE,
            )
        except Exception:
            scale = get_modal_scale(
                self._active_ui_size(),
                reference_size=TUTORIAL_MODAL_REFERENCE_SIZE,
            )
            return max(min_scale, min(max_scale, scale))

    def _build_tutorial_support_layout(self, main_rect: pygame.Rect, ui_scale: float):
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        objectives = self._get_board_lesson_objectives()
        has_objectives = bool(objectives)
        tip_width = main_rect.width
        tip_gap = s(10)

        compact_measure_h = min(max(main_rect.height, s(96)), s(140))
        measure_rect = pygame.Rect(0, 0, tip_width, compact_measure_h)
        panel_pad_x, panel_pad_y = self._panel_content_padding(
            measure_rect,
            s,
            pad_x=14,
            pad_y=10,
            x_ratio=0.08,
            y_ratio=0.10,
        )
        title_gap = max(s(6), int(measure_rect.height * 0.05))
        body_max_width = max(s(60), tip_width - panel_pad_x * 2)

        tip_title_text = t('tutorial_tip_title', default='İPUCU')
        tip_title_font = self._get_fitting_font(
            tip_title_text,
            s(15, minimum=11),
            body_max_width,
            bold=True,
            min_size=max(10, s(11, minimum=10)),
        )
        text_font, lines, text_line_gap, tip_content_h = self._fit_wrapped_text_block(
            self.tip_message,
            base_size=s(15, minimum=11),
            max_width=body_max_width,
            max_height=max(s(46), int(main_rect.height * 0.42)),
            bold=False,
            min_size=max(10, s(11, minimum=10)),
            max_lines=4,
        )
        tip_height = panel_pad_y + tip_title_font.get_height() + title_gap + tip_content_h + panel_pad_y

        layout = {
            'objectives': objectives,
            'has_objectives': has_objectives,
            'tip_width': tip_width,
            'tip_gap': tip_gap,
            'panel_pad_x': panel_pad_x,
            'panel_pad_y': panel_pad_y,
            'title_gap': title_gap,
            'body_max_width': body_max_width,
            'tip_title_font': tip_title_font,
            'text_font': text_font,
            'lines': lines,
            'text_line_gap': text_line_gap,
            'tip_height': tip_height,
            'obj_height': 0,
            'objective_blocks': [],
            'obj_title_font': None,
            'objective_title_gap': 0,
            'objective_item_gap': 0,
            'objective_text_x': 0,
            'bullet_radius': 0,
        }

        if has_objectives:
            obj_title_text = t('tutorial_targets_title', default='HEDEFLER')
            obj_title_font = self._get_fitting_font(
                obj_title_text,
                s(15, minimum=11),
                body_max_width,
                bold=True,
                min_size=max(10, s(11, minimum=10)),
            )
            bullet_radius = max(2, min(s(4), obj_title_font.get_height() // 3))
            bullet_gap = max(s(8), int(tip_width * 0.03))
            objective_text_x = panel_pad_x + bullet_radius * 2 + bullet_gap
            objective_text_width = max(s(50), tip_width - objective_text_x - panel_pad_x)
            objective_item_gap = max(s(7), int(measure_rect.height * 0.06))
            objective_title_gap = max(s(6), int(measure_rect.height * 0.05))
            objective_blocks = []

            for objective in objectives[:3]:
                objective_font, objective_lines, objective_line_gap, objective_height = self._fit_wrapped_text_block(
                    str(objective.get('text') or ''),
                    base_size=s(15, minimum=11),
                    max_width=objective_text_width,
                    max_height=max(s(42), int(main_rect.height * 0.34)),
                    bold=False,
                    min_size=max(10, s(11, minimum=10)),
                    max_lines=3,
                )
                objective_blocks.append(
                    {
                        'font': objective_font,
                        'lines': objective_lines,
                        'line_gap': objective_line_gap,
                        'height': objective_height,
                    }
                )

            objectives_content_h = sum(block['height'] for block in objective_blocks)
            if objective_blocks:
                objectives_content_h += objective_item_gap * (len(objective_blocks) - 1)
            obj_height = panel_pad_y + obj_title_font.get_height() + objective_title_gap + objectives_content_h + panel_pad_y

            layout.update(
                {
                    'obj_height': obj_height,
                    'objective_blocks': objective_blocks,
                    'obj_title_font': obj_title_font,
                    'objective_title_gap': objective_title_gap,
                    'objective_item_gap': objective_item_gap,
                    'objective_text_x': objective_text_x,
                    'bullet_radius': bullet_radius,
                }
            )

        stack_height = tip_height + (layout['obj_height'] + tip_gap if has_objectives else 0)
        layout['stack_height'] = stack_height
        layout['bottom_reserve'] = tip_gap + stack_height
        return layout

    def _tutorial_overlay_rect(self) -> pygame.Rect:
        board_offset_x, board_offset_y = self.get_board_offset()
        cell_size = self.get_cell_size()
        ui_scale = self._tutorial_modal_scale(min_scale=0.70, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        panel_width = s(260)
        panel_height = s(320)
        panel_margin = s(20)
        panel_x = board_offset_x - panel_width - panel_margin
        base_panel_size = s(260)
        base_panel_y = board_offset_y + (self.board_height * cell_size - base_panel_size) // 2
        panel_y = base_panel_y - (panel_height - base_panel_size)

        if panel_x < s(10):
            panel_x = s(10)

        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        # İpucu/hedefler blokları kaldırıldığı için ek alt-rezervasyon yapılmıyor;
        # panel yalnız aktif canvas içinde kalacak şekilde sınırlandırılır.
        _, active_height = self._active_ui_size()
        allowed_bottom = active_height - s(10)
        if panel_rect.bottom > allowed_bottom:
            panel_rect.y = max(s(10), allowed_bottom - panel_rect.height)

        return panel_rect

    def _tutorial_hub_panel_rect(self) -> pygame.Rect:
        active_width, active_height = self._active_ui_size()
        ui_scale = self._tutorial_modal_scale(min_scale=0.72, max_scale=1.12)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        panel_width = min(active_width - s(48), s(1180))
        panel_height = min(active_height - s(48), s(720))
        return pygame.Rect(
            (active_width - panel_width) // 2,
            (active_height - panel_height) // 2,
            panel_width,
            panel_height,
        )

    def _tutorial_lesson_result_panel_rect(self, is_board_result: bool, is_card_result: bool = False) -> pygame.Rect:
        active_width, active_height = self._active_ui_size()
        ui_scale = self._tutorial_modal_scale(min_scale=0.72, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        # Ders sonuç panelleri başlat/çıkış (briefing) paneliyle aynı boyutta olsun.
        # (2026-06-20: font +2px sonrası içeriğin kırpılmaması için yükseklik artırıldı.)
        if is_board_result:
            panel_width, panel_height = s(640), s(540)
        elif is_card_result:
            panel_width, panel_height = s(640), s(540)
        else:
            panel_width, panel_height = s(560), s(410)
        # Aktif canvas'ı taşmasın.
        panel_width = min(panel_width, active_width - s(48))
        panel_height = min(panel_height, active_height - s(40))
        return pygame.Rect(
            (active_width - panel_width) // 2,
            (active_height - panel_height) // 2,
            panel_width,
            panel_height,
        )

    def _apply_tutorial_resize(self, width: int, height: int) -> None:
        requested_width = max(int(width), MIN_WINDOW_WIDTH)
        requested_height = max(int(height), MIN_WINDOW_HEIGHT)
        # Overlay backend (gl_compat/sdl2) aktif ve boyut sabitse create_display ÇAĞIRMA;
        # ikinci set_mode/swapchain rebuild Steam hook'unu kırar.
        try:
            import platform_utils as _pu
            if _pu.overlay_should_skip_rebuild(requested_width, requested_height):
                _gs = _pu.overlay_active_game_surface()
                if _gs is not None:
                    self.screen = _gs
                    self.window_width = self.screen.get_width()
                    self.window_height = self.screen.get_height()
                    self.update_fonts()
                    self._sync_tutorial_card_overlay_reference()
                    return
        except Exception:
            pass
        self.screen = create_display(
            requested_width,
            requested_height,
            fullscreen=False,
            resizable=True,
        )
        self.window_width = self.screen.get_width()
        self.window_height = self.screen.get_height()
        self.update_fonts()
        self._sync_tutorial_card_overlay_reference()

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
                    return migrate_legacy_progress(progress)
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
            skill_tags = lesson.get('skill_tags')
            entries.append(
                {
                    'lesson': lesson,
                    'completed': bool(lesson_progress.get('completed', False)),
                    'stars': int(lesson_progress.get('stars', 0) or 0),
                    'why_it_matters': self._lesson_why(lesson),
                    'duration_seconds': int(lesson.get('duration_seconds', 0) or 0),
                    'skill_tags': list(skill_tags) if isinstance(skill_tags, (list, tuple)) else [],
                    'difficulty': int(lesson.get('difficulty', 0) or 0),
                    'lesson_type': str(lesson.get('lesson_type') or ''),
                }
            )
        return entries

    def _lesson_type_label(self, lesson_type) -> str:
        """Ders tipi etiketini lokalize et (FAZ A)."""
        type_key = str(lesson_type or '').strip()
        if not type_key:
            return ''
        labels = {
            'drill': ('tutorial_lesson_type_drill', 'Alıştırma'),
            'board_puzzle': ('tutorial_lesson_type_board_puzzle', 'Tahta Bulmacası'),
            'card_lab': ('tutorial_lesson_type_card_lab', 'Kart Laboratuvarı'),
            'repair_challenge': ('tutorial_lesson_type_repair_challenge', 'Kurtarma'),
            'exam': ('tutorial_lesson_type_exam', 'Sınav'),
        }
        loc_key, fallback = labels.get(type_key, (None, type_key.replace('_', ' ').title()))
        if loc_key:
            return t(loc_key, default=fallback)
        return fallback

    def _skill_tag_label(self, skill_tag) -> str:
        """Beceri etiketini insan-okunur biçime çevir (FAZ A)."""
        tag = str(skill_tag or '').strip()
        if not tag:
            return ''
        loc_key = 'tutorial_skill_{0}'.format(tag)
        return t(loc_key, default=tag.replace('_', ' ').title())

    def _behavior_label(self, behavior_key) -> str:
        """FAZ E — Davranış anahtarını lokalize cümleye çevir."""
        key = str(behavior_key or '').strip()
        if not key:
            return ''
        defaults = {
            'no_new_holes': 'Delik açmadın.',
            'kept_height': 'Yüksekliği kontrol altında tuttun.',
            'cleared_lines': 'Hedef satırları temizledin.',
            'created_holes': 'Yeni delik açtın.',
            'stack_too_high': 'Kuleyi gereğinden çok yükselttin.',
            'need_more_lines': 'Yeterli satır temizleyemedin.',
        }
        loc_key = 'tutorial_behavior_{0}'.format(key)
        return t(loc_key, default=defaults.get(key, key.replace('_', ' ')))

    def _get_selected_hub_lesson_entry(self):
        """Hub'da o an seçili olan dersin zengin entry'sini döndür (FAZ A)."""
        if not self.hub_selected_chapter_id or not self.hub_selected_lesson_id:
            return None
        for entry in self._get_hub_lesson_entries(self.hub_selected_chapter_id):
            if str(entry['lesson'].get('id') or '') == str(self.hub_selected_lesson_id):
                return entry
        return None

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
        self._hub_carousel_prev_chapter_id = self.hub_selected_chapter_id
        self._hub_carousel_anim_offset = float(-delta)
        self._hub_carousel_anim_target = 0.0
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
            'hold_used': False,
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
                'hold_used': bool(self.lesson_runtime_state.get('hold_used', False)),
                'lines_cleared': int(getattr(self.board, 'lines_cleared', 0) or 0),
            }
        )

    def _is_scenario_lesson_active(self):
        return isinstance(self.active_lesson, dict) and self.active_lesson.get('kind') == 'scenario'

    def _is_card_choice_lesson_active(self):
        return isinstance(self.active_lesson, dict) and self.active_lesson.get('kind') == 'card_choice'

    def _card_choice_stage(self):
        """Kart dersi akış aşaması: 'board_preview' | 'choosing' | 'effect'."""
        if not isinstance(self.card_choice_state, dict):
            return 'choosing'
        return str(self.card_choice_state.get('stage') or 'choosing')

    def _is_card_choosing_stage(self):
        """Kart seçim arayüzünün (kartların) gösterildiği aşama mı?"""
        return self._is_card_choice_lesson_active() and self._card_choice_stage() == 'choosing'

    def _is_board_basics_lesson_active(self):
        return (
            isinstance(self.active_lesson, dict)
            and self.active_lesson.get('kind') == 'scenario'
            and bool(self.active_lesson.get('scenario_id'))
        )

    def _get_active_board_scenario(self):
        if not self._is_board_basics_lesson_active():
            return None
        return get_scenario(self.active_lesson.get('scenario_id'))

    def _get_board_lesson_objectives(self):
        scenario = self._get_active_board_scenario()
        if not isinstance(scenario, dict):
            return []
        objectives = []
        for objective in list(scenario.get('objectives') or []):
            if not isinstance(objective, dict):
                continue
            text = str(objective.get('text') or '').strip()
            if not text:
                continue
            objectives.append(
                {
                    'id': objective.get('id'),
                    'text': text,
                }
            )
        return objectives

    def _setup_board_highlight(self, scenario, lesson=None, attempt_count=1):
        """Senaryo highlight'ını ve hold vurgusunu derse göre hazırla.

        Kurallar:
        - Board iniş highlight'ı (parçanın oturacağı tam ayak izi) normal
          derslerde 1 başarısızlıktan SONRA (attempt >= 2), sınavlarda 2
          başarısızlıktan SONRA (attempt >= 3) gösterilir.
        - Hold gerektiren (expected_hold_usage) sınav-olmayan derslerde hold
          kutucuğu hemen vurgulanır; hold kullanılınca kapanır.
        - Sınav (lesson_type == 'exam') derslerinde hold vurgusu gösterilmez;
          yalnız 2 başarısızlıktan sonra board iniş bandı çıkar.
        - Ders 5 (line-clear) bu metottan geçmez; kendi setup'ında highlight
          hemen açılır.
        """
        lesson_type = ''
        if isinstance(lesson, dict):
            lesson_type = str(lesson.get('lesson_type') or '')
        else:
            active_lesson = getattr(self, 'active_lesson', None)
            if isinstance(active_lesson, dict):
                lesson_type = str(active_lesson.get('lesson_type') or '')
        is_exam = lesson_type == 'exam'
        attempt_count = int(attempt_count or 1)

        spec = None
        if isinstance(scenario, dict):
            placements = scenario.get('highlight_placements')
            columns = scenario.get('highlight_columns')
            cells = scenario.get('highlight_cells')
            if placements:
                spec = {
                    'placements': [
                        [str(p[0]), int(p[1]), int(p[2])]
                        for p in placements
                        if isinstance(p, (list, tuple)) and len(p) == 3
                    ],
                    'columns': [],
                    'cells': [],
                }
            elif columns or cells:
                spec = {
                    'placements': [],
                    'columns': [int(c) for c in (columns or []) if isinstance(c, (int, float))],
                    'cells': [tuple(cell) for cell in (cells or []) if isinstance(cell, (list, tuple)) and len(cell) == 2],
                }
        self.board_highlight_spec = spec

        # Hold vurgusu: hold gerektiren, sınav-olmayan dersler.
        # Bazı derslerde hold sırası ilk parçadan sonra gelir (hold_highlight_index).
        expects_hold = bool(isinstance(scenario, dict) and scenario.get('expected_hold_usage'))
        self.hold_highlight_armed = bool(expects_hold and not is_exam)
        self.hold_highlight_index = int(scenario.get('hold_highlight_index', 0) or 0) if isinstance(scenario, dict) else 0
        self.hold_highlight_pulse = 0.0
        # Anlık görünürlük placement index'e göre güncellenir.
        self.hold_highlight_active = bool(self.hold_highlight_armed and self.hold_highlight_index == 0)

        # Board iniş highlight'ı: zorlanan oyuncuyu kaybetmemek için normal
        # derslerde 1 başarısızlıktan sonra (attempt 2+) gösterilir. Sınavlarda
        # daha geç — 2 başarısızlıktan sonra (attempt 3+) — gelir.
        highlight_after = 3 if is_exam else 2
        self._board_highlight_allowed = bool(spec and attempt_count >= highlight_after)
        self._board_highlight_last_index = self._active_highlight_placement_index()
        if self._board_highlight_allowed:
            self.board_highlight_timer = self.board_highlight_duration_s
        else:
            self.board_highlight_timer = 0.0

    def _trigger_board_highlight(self, duration_s=None):
        """Stuck-hint tetiklendiğinde highlight'ı yeniden göster."""
        if not self.board_highlight_spec:
            return
        self.board_highlight_timer = float(duration_s if duration_s is not None else self.board_highlight_duration_s)

    def _compute_landing_footprint(self, name, rotation, x):
        """Belirtilen parçayı (name, rotation, x) CANLI board üzerinde sert düşür
        ve oturacağı tam hücreleri döndür. Geometri her zaman doğru olur
        (örn. dik I parçası dikey görünür)."""
        board = getattr(self, 'board', None)
        if board is None:
            return []
        try:
            piece = self._create_named_piece(str(name))
        except Exception:
            return []
        if piece is None:
            return []
        try:
            for _ in range(int(rotation) % 4):
                piece.rotate()
            piece.x = int(x)
            piece.y = -4
        except Exception:
            return []
        # Geçerli başlangıç değilse footprint yok.
        if not board.is_valid_position(piece):
            return []
        # Sert düşür.
        guard = 0
        while board.is_valid_position(piece, dy=1) and guard < 64:
            piece.y += 1
            guard += 1
        cells = []
        bw = int(getattr(self, 'board_width', 10) or 10)
        bh = int(getattr(self, 'board_height', 20) or 20)
        for cx, cy in piece.get_cells():
            if 0 <= cx < bw and 0 <= cy < bh:
                cells.append((int(cx), int(cy)))
        return cells

    def _active_highlight_placement_index(self):
        """O an aktif olan highlight yerleştirme indeksini döndür.

        Senaryoda kaç parça kilitlendiyse (scenario_lock_count) o kadar
        yerleştirme tamamlanmış sayılır; sıradaki gösterilir.
        """
        lock_count = 0
        runtime_state = getattr(self, 'lesson_runtime_state', None)
        if isinstance(runtime_state, dict):
            lock_count = int(runtime_state.get('scenario_lock_count', 0) or 0)
        return max(0, lock_count)

    def _get_active_highlight_cells(self):
        """Aktif highlight hücrelerini (parçanın iniş ayak izi) dinamik hesapla.

        placements varsa: o anki yerleştirme için CANLI board'da footprint çıkar.
        Aksi halde eski cells/columns yedeğini kullan.
        """
        spec = getattr(self, 'board_highlight_spec', None)
        if not isinstance(spec, dict):
            return []
        placements = spec.get('placements') or []
        if placements:
            idx = self._active_highlight_placement_index()
            if idx >= len(placements):
                return []
            name, rotation, x = placements[idx]
            return self._compute_landing_footprint(name, rotation, x)

        # Yedek: statik cells.
        cells = []
        bw = int(getattr(self, 'board_width', 10) or 10)
        bh = int(getattr(self, 'board_height', 20) or 20)
        for cell in spec.get('cells', []):
            try:
                cx, cy = int(cell[0]), int(cell[1])
            except Exception:
                continue
            if 0 <= cx < bw and 0 <= cy < bh:
                cells.append((cx, cy))
        if cells:
            return cells

        # Yedek: sütun bandı (yığın yüzeyinin hemen üstü).
        occupancy = getattr(self.board, 'occupancy', None) if getattr(self, 'board', None) else None

        def _surface_top_row(grid_x):
            if not occupancy:
                return bh
            for y in range(bh):
                try:
                    if 0 <= grid_x < len(occupancy[y]) and occupancy[y][grid_x]:
                        return y
                except (IndexError, TypeError):
                    continue
            return bh

        band_height = 3
        for column in spec.get('columns', []):
            gx = int(column)
            if not (0 <= gx < bw):
                continue
            surface_top = _surface_top_row(gx)
            band_bottom = surface_top - 1
            band_top = max(0, surface_top - band_height)
            for gy in range(band_top, band_bottom + 1):
                if 0 <= gy < bh:
                    cells.append((gx, gy))
        return cells

    def _get_live_objective_states(self):
        """Oyun sırasında hedeflerin anlık geçti/geçmedi durumunu hesapla (FAZ D)."""
        scenario = self._get_active_board_scenario()
        if not isinstance(scenario, dict):
            return []
        initial_metrics = self.lesson_runtime_state.get('initial_metrics', {}) if isinstance(self.lesson_runtime_state, dict) else {}
        current_metrics = capture_board_metrics(self.board)
        metric_values = {
            'line_delta': int(current_metrics.get('lines_cleared', 0) or 0) - int(initial_metrics.get('lines_cleared', 0) or 0),
            'hole_delta': int(current_metrics.get('holes', 0) or 0) - int(initial_metrics.get('holes', 0) or 0),
            'height_delta': int(current_metrics.get('max_height', 0) or 0) - int(initial_metrics.get('max_height', 0) or 0),
            'hold_used': 1 if (isinstance(self.lesson_runtime_state, dict) and self.lesson_runtime_state.get('hold_used')) else 0,
        }
        states = []
        for objective in list(scenario.get('objectives') or []):
            if not isinstance(objective, dict):
                continue
            text = str(objective.get('text') or '').strip()
            if not text:
                continue
            metric_name = str(objective.get('metric') or '')
            comparison = str(objective.get('comparison') or 'max')
            target_value = int(objective.get('value', 0) or 0)
            passed = False
            if metric_name in metric_values:
                actual = metric_values[metric_name]
                passed = actual >= target_value if comparison == 'min' else actual <= target_value
            states.append({'id': objective.get('id'), 'text': text, 'passed': bool(passed)})
        return states

    def _enrich_board_lesson_outcome(self, outcome):
        if not isinstance(outcome, dict):
            return dict(outcome or {})
        scenario = self._get_active_board_scenario()
        if not isinstance(scenario, dict):
            return dict(outcome)
        enriched = dict(outcome)
        hold_used = 1 if isinstance(self.lesson_runtime_state, dict) and self.lesson_runtime_state.get('hold_used', False) else 0
        enriched['hold_used'] = int(enriched.get('hold_used', hold_used) or 0)
        if bool(scenario.get('expected_hold_usage')) and enriched['hold_used'] < 1:
            enriched['success'] = False
            enriched['stars'] = 0
            enriched['feedback_key'] = 'need_hold'
        active_lesson = getattr(self, 'active_lesson', None) or {}
        scenario_id = active_lesson.get('scenario_id') or ''
        return enrich_scenario_outcome(enriched, scenario, scenario_id=scenario_id)

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

    def _lesson_why(self, lesson=None):
        """Dersin 'why_it_matters' metnini lokalize ederek döndür.

        Anahtar deseni: tutorial_why_<lesson_id>. Anahtar yoksa hardcoded TR
        metni fallback olarak kullanılır (geriye dönük güvenli).
        """
        lesson_data = lesson or self.active_lesson or {}
        if not isinstance(lesson_data, dict):
            return ''
        why_fallback = str(lesson_data.get('why_it_matters') or '').strip()
        lesson_id = str(lesson_data.get('id') or '').strip()
        if not lesson_id:
            return why_fallback
        return t(f'tutorial_why_{lesson_id}', default=why_fallback)

    def _compose_lesson_guidance(self, instruction='', explanation=''):
        parts = []
        for raw_part in (instruction, explanation):
            text = str(raw_part or '').strip()
            if text:
                parts.append(text)
        return ' '.join(parts)

    def _get_followup_lesson_id(self, lesson_id=None):
        return get_next_lesson_id(
            lesson_id or self.active_lesson_id,
            chapter_only=self.lesson_flow_scope == 'chapter',
        )

    def _get_next_chapter_target(self, lesson_id=None):
        source_lesson_id = str(lesson_id or self.active_lesson_id or '')
        if not source_lesson_id:
            return None, None
        current_lesson = self.lesson_lookup.get(source_lesson_id) or get_lesson(source_lesson_id)
        current_chapter_id = str(current_lesson.get('chapter') or '') if isinstance(current_lesson, dict) else ''
        next_lesson_id = get_next_lesson_id(source_lesson_id, chapter_only=False)
        if not next_lesson_id:
            return None, None
        next_lesson = self.lesson_lookup.get(str(next_lesson_id)) or get_lesson(next_lesson_id)
        if not isinstance(next_lesson, dict):
            return None, None
        next_chapter_id = str(next_lesson.get('chapter') or '')
        if not next_chapter_id or next_chapter_id == current_chapter_id:
            return None, None
        return next_chapter_id, str(next_lesson.get('id') or '')

    def _get_chapter_progression_panel(self, chapter_id):
        """Bölümün ilerleme paneli metadata'sını döndür; yoksa None."""
        chapter = get_chapter(chapter_id)
        if not isinstance(chapter, dict):
            return None
        panel_meta = chapter.get('progression_panel')
        return panel_meta if isinstance(panel_meta, dict) else None

    def _pending_chapter_boundary(self):
        """Tamamlanan ders bir bölümün sonundaysa ve sıradaki ders farklı bir
        bölüme geçiyorsa (chapter_id, panel_meta, next_lesson_id) döndür; yoksa None.

        Yalnız `progression_panel` metadata'sına sahip bölümler için panel önerilir.
        """
        current_lesson = self.active_lesson if isinstance(self.active_lesson, dict) else None
        current_chapter_id = str(current_lesson.get('chapter') or '') if current_lesson else ''
        if not current_chapter_id:
            return None
        panel_meta = self._get_chapter_progression_panel(current_chapter_id)
        if not panel_meta:
            return None
        next_lesson_id = get_next_lesson_id(self.active_lesson_id, chapter_only=False)
        if not next_lesson_id:
            return None
        next_lesson = self.lesson_lookup.get(str(next_lesson_id)) or get_lesson(next_lesson_id)
        next_chapter_id = str(next_lesson.get('chapter') or '') if isinstance(next_lesson, dict) else ''
        if not next_chapter_id or next_chapter_id == current_chapter_id:
            return None
        return current_chapter_id, panel_meta, str(next_lesson_id)

    def _continue_after_completion(self):
        # FAZ 2 — Bölüm sınırını geçmeden önce ilerleme paneli göster
        # (devam et / çıkıp oyna). Yalnız panel metadata'sı olan bölümlerde.
        if not getattr(self, 'progress_panel_active', False):
            boundary = self._pending_chapter_boundary()
            if boundary is not None:
                _chapter_id, panel_meta, next_lesson_id = boundary
                self._open_progression_panel(panel_meta, next_lesson_id)
                return True
        if self.next_lesson_id:
            self._start_lesson(self.next_lesson_id)
            return True
        next_chapter_id, next_lesson_id = self._get_next_chapter_target(self.active_lesson_id)
        if next_chapter_id and next_lesson_id and self.lesson_flow_scope != 'chapter':
            self._start_lesson(next_lesson_id)
            return True
        if self.hub_return_enabled:
            preferred_chapter_id = self.active_lesson.get('chapter') if isinstance(self.active_lesson, dict) else None
            self._open_tutorial_hub(preferred_chapter_id=preferred_chapter_id, preferred_lesson_id=self.active_lesson_id)
            return True
        return 'menu'

    # ── FAZ 2 — İlerleme paneli (bölüm sonu karar ekranı) ──────────────
    def _open_progression_panel(self, panel_meta, next_lesson_id):
        """Bölüm sonu ilerleme panelini aç (oyun mantığı durur)."""
        title = t(
            str(panel_meta.get('title_key') or ''),
            default=str(panel_meta.get('title_fallback') or ''),
        ) if panel_meta.get('title_key') else str(panel_meta.get('title_fallback') or '')
        body = t(
            str(panel_meta.get('body_key') or ''),
            default=str(panel_meta.get('body_fallback') or ''),
        ) if panel_meta.get('body_key') else str(panel_meta.get('body_fallback') or '')
        self.progress_panel_data = {
            'title': title,
            'body': body,
            'next_lesson_id': str(next_lesson_id or ''),
        }
        self.progress_panel_active = True
        self.progress_panel_selected_index = 0
        self.lesson_result_active = False
        self.lesson_result = None
        self.waiting_for_enter = False
        self.in_transition = False
        self.card_choice_state = {}
        # Panel açılış vurgusu (yumuşak giriş animasyonu).
        self.progress_panel_anim = 0.0
        try:
            self.sound.play('tutorial_complete')
        except Exception:
            pass

    def _progression_panel_continue(self):
        """İlerleme panelinde 'Öğrenmeye Devam Et' — sıradaki bölüme geç."""
        data = self.progress_panel_data if isinstance(self.progress_panel_data, dict) else {}
        next_lesson_id = str(data.get('next_lesson_id') or '')
        self.progress_panel_active = False
        self.progress_panel_data = None
        # first-run (chapter scope) ise akademinin kalanını da aç.
        if self.lesson_flow_scope == 'chapter':
            self.lesson_flow_scope = 'full'
        if next_lesson_id:
            self._start_lesson(next_lesson_id)
            return True
        if getattr(self, 'hub_return_enabled', False):
            self._open_tutorial_hub()
            return True
        return 'menu'

    def _progression_panel_play(self):
        """İlerleme panelinde 'Çıkıp Oyna' — ana menüye dön (kullanıcı kararı)."""
        self.progress_panel_active = False
        self.progress_panel_data = None
        return 'menu'

    def _wrap_text(self, text, font, max_width, max_lines=None):
        text = str(text or '')
        if not text:
            return []
        if max_width <= 0:
            return [text]

        import re as _re
        def _repl(m):
            return _re.sub(r'\s', '__SPC__', m.group(0))
        text_processed = _re.sub(r'\[[^\]]*\]', _repl, text)

        try:
            from .localization import get_language
        except Exception:
            from localization import get_language
        lang = str(get_language() or 'en').lower()
        is_cjk = lang in ('ja', 'jp', 'zh', 'ko')

        def is_cjk_char(char):
            ord_c = ord(char)
            return (
                (0x4e00 <= ord_c <= 0x9fff) or
                (0x3040 <= ord_c <= 0x309f) or
                (0x30a0 <= ord_c <= 0x30ff) or
                (0xac00 <= ord_c <= 0xd7af) or
                (0x1100 <= ord_c <= 0x11ff) or
                (0x3130 <= ord_c <= 0x318f)
            )

        def should_add_space(w1, w2):
            if not w1 or not w2:
                return False
            if is_cjk_char(w1[-1]) or is_cjk_char(w2[0]):
                return False
            return True

        lines = []
        for paragraph in text_processed.split('\n'):
            if is_cjk:
                words = []
                current_latin = []
                for char in paragraph:
                    if is_cjk_char(char):
                        if current_latin:
                            words.append("".join(current_latin))
                            current_latin = []
                        words.append(char)
                    else:
                        if char.isspace():
                            if current_latin:
                                words.append("".join(current_latin))
                                current_latin = []
                        else:
                            current_latin.append(char)
                if current_latin:
                    words.append("".join(current_latin))
            else:
                words = paragraph.split()

            if not words:
                if not max_lines or len(lines) < max_lines:
                    lines.append('')
                if max_lines and len(lines) >= max_lines:
                    return [line.replace('__SPC__', ' ') for line in lines[:max_lines]]
                continue

            current_line = words[0]
            for word in words[1:]:
                space = ' ' if should_add_space(current_line, word) else ''
                test_line = f'{current_line}{space}{word}'
                test_line_measure = test_line.replace('__SPC__', ' ')
                if font.size(test_line_measure)[0] <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    if max_lines and len(lines) >= max_lines:
                        return [line.replace('__SPC__', ' ') for line in lines[:max_lines]]
                    current_line = word

            lines.append(current_line)
            if max_lines and len(lines) >= max_lines:
                return [line.replace('__SPC__', ' ') for line in lines[:max_lines]]

        result_lines = lines[:max_lines] if max_lines else lines
        return [line.replace('__SPC__', ' ') for line in result_lines]

    def _measure_text_block_height(self, font, lines, line_gap):
        if not lines:
            return 0
        return (len(lines) * font.get_height()) + (max(0, len(lines) - 1) * line_gap)

    def _get_fitting_font(self, text, base_size, max_width, bold=False, min_size=10):
        fitting_font = getattr(retro_style, 'get_fitting_font', None)
        if callable(fitting_font):
            return fitting_font(text, base_size, max_width, bold=bold, min_size=min_size)

        size = max(int(base_size), int(min_size))
        min_size = max(8, int(min_size))
        font = retro_style.get_font(size, bold=bold)
        while max_width and font.size(str(text or ''))[0] > max_width and size > min_size:
            size -= 1 if size <= 16 else 2
            font = retro_style.get_font(size, bold=bold)
        return font

    def _fit_wrapped_text_block(
        self,
        text,
        *,
        base_size,
        max_width,
        max_height=None,
        bold=False,
        min_size=10,
        max_lines=None,
    ):
        text = str(text or '').strip()
        max_width = max(1, int(max_width or 1))
        base_size = max(8, int(base_size))
        min_size = max(8, int(min_size))
        if max_height is not None:
            max_height = max(1, int(max_height))

        if not text:
            font = retro_style.get_font(base_size, bold=bold)
            line_gap = max(2, int(font.get_height() * 0.28))
            return font, [], line_gap, 0

        size = max(base_size, min_size)
        fallback = None
        while size >= min_size:
            font = retro_style.get_font(size, bold=bold)
            lines = self._wrap_text(text, font, max_width)
            line_gap = max(2, int(font.get_height() * 0.28))

            if max_lines is not None and len(lines) > max_lines:
                fallback = (font, lines[:max_lines], line_gap)
                size -= 1 if size <= 16 else 2
                continue

            total_height = self._measure_text_block_height(font, lines, line_gap)
            fallback = (font, lines, line_gap)
            if max_height is None or total_height <= max_height:
                return font, lines, line_gap, total_height

            size -= 1 if size <= 16 else 2

        if fallback is None:
            font = retro_style.get_font(min_size, bold=bold)
            lines = self._wrap_text(text, font, max_width, max_lines=max_lines)
            line_gap = max(2, int(font.get_height() * 0.28))
        else:
            font, lines, line_gap = fallback

        if max_lines is not None:
            lines = lines[:max_lines]
        total_height = self._measure_text_block_height(font, lines, line_gap)
        return font, lines, line_gap, total_height

    def _panel_content_padding(self, rect, s, pad_x=16, pad_y=12, x_ratio=0.07, y_ratio=0.06):
        inner_x = min(rect.width // 4, max(s(pad_x), int(rect.width * x_ratio)))
        inner_y = min(rect.height // 4, max(s(pad_y), int(rect.height * y_ratio)))
        return inner_x, inner_y

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
        for name in list(names or []):
            queue.append(self._create_named_piece(str(name)))
        while len(queue) < 3:
            queue.append(self.spawn_new_piece())
        return queue

    def _get_scenario_lock_budget(self):
        if not isinstance(self.lesson_runtime_state, dict):
            return 1
        return max(1, int(self.lesson_runtime_state.get('scenario_max_piece_locks', 1) or 1))

    def _register_scenario_piece_lock(self):
        if not isinstance(self.lesson_runtime_state, dict):
            self.lesson_runtime_state = {}
        lock_count = int(self.lesson_runtime_state.get('scenario_lock_count', 0) or 0) + 1
        self.lesson_runtime_state['scenario_lock_count'] = lock_count
        return lock_count

    def _use_scenario_hold(self):
        if not getattr(self, '_scenario_allow_hold', False):
            return False
        if not getattr(self, 'can_hold', False):
            return False
        if not self.current_piece or self.in_transition:
            return False

        if self.held_piece is None:
            self.held_piece = self.current_piece
            if self.next_piece_queue:
                self.current_piece = self.next_piece_queue.pop(0)
                self._skip_hidden_rows(self.current_piece)
            else:
                self.current_piece = self.spawn_new_piece()
                self._position_piece_at_spawn(self.current_piece)
                self._skip_hidden_rows(self.current_piece)
            self.next_piece_queue.append(self.spawn_new_piece())
        else:
            self.current_piece, self.held_piece = self.held_piece, self.current_piece
            self._position_piece_at_spawn(self.current_piece)
            self._skip_hidden_rows(self.current_piece)

        self.can_hold = False
        self._register_step_activity()
        if isinstance(self.lesson_runtime_state, dict):
            self.lesson_runtime_state['hold_used'] = True
        self.apply_theme_to_pieces()
        if self.sound:
            self.sound.play('hold')
        self._sync_lesson_runtime_state()
        return True

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
        self._clear_tutorial_das()
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
        self._scenario_allow_hold = self.can_hold
        self.apply_theme_to_pieces()

        lesson_id = str(lesson.get('id') or '')
        attempt_count = int(self.lesson_attempt_counts.get(lesson_id, 0) or 0) + 1
        self.lesson_attempt_counts[lesson_id] = attempt_count

        self.lesson_runtime_state.update(
            {
                'scenario_id': scenario.get('id') or lesson.get('scenario_id'),
                'initial_metrics': capture_board_metrics(self.board),
                'attempt_count': attempt_count,
                'scenario_lock_count': 0,
                'scenario_max_piece_locks': max(1, int(scenario.get('max_piece_locks', 1) or 1)),
                'hold_used': False,
            }
        )
        # FAZ D — Board highlight, hold vurgusu ve hedef durumlarını hazırla.
        self._setup_board_highlight(scenario, lesson=lesson, attempt_count=attempt_count)
        self._objective_chip_states = {}
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
            # Akış aşaması: önce tahtayı incele, sonra kart seç.
            'stage': 'board_preview',
        }
        if self.card_ui:
            self.card_ui.reset()
            self._sync_tutorial_card_overlay_reference()
        self.base_fall_speed = 0
        self.fall_speed = 0
        self.soft_drop_counter = 0
        self.soft_drop_active = False
        self._clear_tutorial_das()
        self.sub_message = t('tutorial_card_choose_hint', default='Sol/Sağ ile seç, Enter ile onayla; istersen 1-3 kısayollarını kullan.')
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
        ui_scale = self._tutorial_modal_scale(min_scale=0.72, max_scale=1.12)

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

    # Tahtada görsel (animasyonlu) etkisi olan kart kimlikleri.
    _ANIMATED_CARD_EFFECTS = {
        'clear_rows', 'peak_sculpt', 'gravity_well', 'nova_burst', 'mini_bomb', 'row_shuffle',
    }

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
        # Kartın etkisini (ad + açıklama) sonuca göm; tek, cilalı sonuç ekranı.
        outcome['card_title'] = get_tutorial_card_title(selected_card)
        outcome['card_description'] = get_tutorial_card_description(selected_card)
        self.lesson_runtime_state['selected_card_id'] = selected_card.get('id')
        self.lesson_runtime_state['last_result'] = dict(outcome)

        card_id = str(selected_card.get('id') or '')
        has_animated_effect = card_id in self._ANIMATED_CARD_EFFECTS
        # Ö3a — Aynı animasyonlu kart efekti bu oturumda DAHA ÖNCE gösterildiyse
        # showcase'i atla (oyuncu aynı efekti 2. kez izlemek istemez). Etki yine
        # board'a uygulanır, tek bir sonuç paneli açılır. İlk gösterim bozulmaz.
        shown = getattr(self, '_shown_card_effect_ids', None)
        if not isinstance(shown, set):
            shown = set()
            self._shown_card_effect_ids = shown
        already_shown = card_id in shown
        if has_animated_effect and not already_shown:
            shown.add(card_id)
            # Kart ustalığı hissi: önce etkilenecek hücreleri VURGULA, sonra
            # temizle/uygula, en son sonuç panelini aç (iki fazlı animasyon).
            self._begin_card_effect_showcase(selected_card, outcome)
            return

        # Görsel etkisi olmayan kartlar (perk/zamanlı buff) VEYA tekrar gösterilen
        # animasyonlu kartlar: etkiyi uygula, doğrudan sonuç panelini aç.
        effect_summary = self._apply_tutorial_card_effect(selected_card)
        if effect_summary:
            outcome['effect_applied'] = True
            outcome['effect_summary'] = effect_summary
        self.sound.play('tutorial_progress')
        self._show_lesson_result(outcome)

    def _begin_card_effect_showcase(self, selected_card, outcome):
        """Seçilen kartın tahtaya etkisini iki fazlı CANLI göster.

        Faz 1 (vurgu): etkilenecek hücreler yanıp söner (henüz silinmez).
        Faz 2 (uygula): hücreler temizlenir/çökertilir, kısa bekleme.
        Süre dolunca _finish_card_effect_showcase sonuç panelini açar.
        """
        if not isinstance(self.card_choice_state, dict):
            self.card_choice_state = {}
        self.card_choice_state['stage'] = 'showcase'
        self.card_choice_state['showcase_outcome'] = dict(outcome or {})
        self.card_choice_state['showcase_card'] = dict(selected_card or {})
        self.card_choice_state['showcase_card_title'] = get_tutorial_card_title(selected_card)
        self.card_choice_state['showcase_success'] = bool(outcome.get('success'))
        self.card_choice_state['showcase_applied'] = False
        # Vurgulanacak hücreler (mutasyondan ÖNCE hesaplanır).
        self.card_effect_highlight_cells = self._compute_card_effect_cells(selected_card)
        self.card_effect_showcase_phase = 'highlight'
        self.card_effect_highlight_timer = float(getattr(self, 'card_effect_highlight_duration_s', 0.75))
        self.card_effect_showcase_timer = float(getattr(self, 'card_effect_showcase_duration_s', 0.9))
        try:
            self.sound.play('move')
        except Exception:
            pass

    def _apply_card_effect_showcase_mutation(self):
        """Showcase faz 2: kartın board mutasyonunu uygula + temizleme efekti."""
        state = self.card_choice_state if isinstance(self.card_choice_state, dict) else {}
        if state.get('showcase_applied'):
            return
        selected_card = state.get('showcase_card') if isinstance(state.get('showcase_card'), dict) else {}
        outcome = state.get('showcase_outcome') if isinstance(state.get('showcase_outcome'), dict) else {}
        effect_summary = self._apply_tutorial_card_effect(selected_card)
        if effect_summary:
            outcome['effect_applied'] = True
            outcome['effect_summary'] = effect_summary
            state['showcase_outcome'] = dict(outcome)
        state['showcase_applied'] = True
        self.card_effect_highlight_cells = set()
        self.card_effect_showcase_phase = 'settle'
        # Temizlik/uygulama anı: flash + sarsıntı.
        try:
            self.screen_shake = max(float(getattr(self, 'screen_shake', 0.0) or 0.0), 10.0)
        except Exception:
            pass
        try:
            self.sound.play('line_clear' if bool(state.get('showcase_success')) else 'tutorial_progress')
        except Exception:
            pass

    def _finish_card_effect_showcase(self):
        """Showcase bitti — (gerekirse mutasyonu uygula ve) sonuç panelini aç."""
        # Erken atlama: mutasyon henüz uygulanmadıysa uygula.
        if isinstance(self.card_choice_state, dict) and not self.card_choice_state.get('showcase_applied'):
            self._apply_card_effect_showcase_mutation()
        outcome = {}
        if isinstance(self.card_choice_state, dict):
            outcome = dict(self.card_choice_state.get('showcase_outcome') or {})
            self.card_choice_state['stage'] = 'result'
        self.card_effect_showcase_timer = 0.0
        self.card_effect_highlight_timer = 0.0
        self.card_effect_highlight_cells = set()
        self._show_lesson_result(outcome)

    def _animate_card_block_fall(self, pre_positions):
        """Kart etkisi sonrası blokların düşüşünü ana oyundaki gibi animasyonla.

        pre_positions: {x: [eski dolu y'ler]} (mutasyondan ÖNCE yakalanan).
        Mutasyon + apply_gravity sonrası yeni konumlara göre falling_block_animations
        kurar (her blok eski→yeni y farkı kadar yukarıdan düşer).
        """
        board = getattr(self, 'board', None)
        if board is None:
            return
        try:
            cell_size = max(1, int(self.get_cell_size()))
        except Exception:
            cell_size = 24
        anims = []
        try:
            for x in range(board.width):
                new_rows = [y for y in range(board.height) if board.occupancy[y][x]]
                old_rows = list(pre_positions.get(x, []))
                # Hayatta kalan blok sayısı kadar eşle (alttan üste).
                paired = min(len(new_rows), len(old_rows))
                new_sorted = sorted(new_rows, reverse=True)
                old_sorted = sorted(old_rows, reverse=True)
                for i in range(paired):
                    new_y = new_sorted[i]
                    old_y = old_sorted[i]
                    drop = int(new_y - old_y)
                    if drop > 0:
                        anims.append({
                            'row': int(new_y),
                            'col': int(x),
                            'current_offset': float(-drop * cell_size),
                            'target_offset': 0.0,
                            'sweep_trigger': 0.0,
                            'started': True,
                        })
        except Exception:
            anims = []
        if anims:
            self.falling_block_animations = anims

    def _trigger_card_line_clear_animation(self, source='card'):
        """Tahtadaki tüm dolu satırları ana oyun pipeline'ıyla temizle + animasyonla.

        board.clear_lines() last_cleared_lines'ı doldurur; _queue_line_clear_effects
        sweep + parçacık + flash + blok düşüşü efektlerini kurar (ana oyunla aynı).
        Döndürür: temizlenen satır sayısı.
        """
        board = getattr(self, 'board', None)
        if board is None:
            return 0
        try:
            cleared = int(board.clear_lines(source=source))
        except Exception:
            cleared = 0
        if cleared > 0:
            try:
                self._queue_line_clear_effects(cleared)
            except Exception:
                pass
        return cleared

    def _apply_tutorial_card_effect(self, card):
        """Seçilen kartın etkisini tutorial tahtasına uygula — ana oyundaki gerçek
        animasyon hattını kullanır (satır temizleme sweep'i, blok düşüşü, parçacık,
        ekran sarsıntısı). Perk/zamanlı buff kartlarında tahta değişmez.

        Tüm işlemler savunmacı (board None / eksik attr güvenli).
        Döndürür: gösterilecek kısa etki özeti metni veya ''.
        """
        board = getattr(self, 'board', None)
        if board is None or not isinstance(card, dict):
            return ''
        card_id = str(card.get('id') or '')
        try:
            value = int(card.get('value', 0) or 0)
        except Exception:
            value = 0

        def _snapshot_columns():
            snap = {}
            try:
                for x in range(board.width):
                    snap[x] = [y for y in range(board.height) if board.occupancy[y][x]]
            except Exception:
                pass
            return snap

        def _occupied_rows_bottom_up():
            rows = []
            for y in range(board.height - 1, -1, -1):
                if any(board.occupancy[y]):
                    rows.append(y)
            return rows

        def _clear_cell(x, y):
            board.occupancy[y][x] = False
            board.grid[y][x] = BLACK
            if hasattr(board, 'texture_grid'):
                board.texture_grid[y][x] = None
            if hasattr(board, 'gold'):
                board.gold[y][x] = False
            if hasattr(board, 'owners'):
                board.owners[y][x] = None

        def _cell_pixel_center(x, y):
            try:
                ox, oy = self.get_board_offset()
                cs = max(1, int(self.get_cell_size()))
                return ox + x * cs + cs // 2, oy + y * cs + cs // 2
            except Exception:
                return None

        try:
            if card_id == 'clear_rows':
                # Alt Süpür: en alttaki N satırı kaldır, blokları düşür (ana oyun gibi).
                pre = _snapshot_columns()
                n = max(1, value or 2)
                width = board.width
                for _ in range(n):
                    board.grid.pop(); board.grid.insert(0, [BLACK] * width)
                    if hasattr(board, 'texture_grid'):
                        board.texture_grid.pop(); board.texture_grid.insert(0, [None] * width)
                    board.occupancy.pop(); board.occupancy.insert(0, [False] * width)
                    if hasattr(board, 'gold'):
                        board.gold.pop(); board.gold.insert(0, [False] * width)
                    if hasattr(board, 'owners'):
                        board.owners.pop(); board.owners.insert(0, [None] * width)
                try:
                    board.apply_gravity()
                except Exception:
                    pass
                self._animate_card_block_fall(pre)
                self._trigger_card_line_clear_animation()
                try:
                    self.trigger_screen_shake(intensity=6, duration=10 / 60.0)
                except Exception:
                    pass
                return t('tutorial_card_effect_clear_rows', rows=n,
                         default=f'{n} alt satır temizlendi, bloklar aşağı oturdu.')

            if card_id == 'peak_sculpt':
                # Tepe Kesici: ana oyun algoritmasıyla aynı hücreleri kaldır
                # (vurgu fazıyla birebir eşleşir). ANA OYUNDA olduğu gibi yerçekimi
                # UYGULANMAZ — yalnız tepe blokları silinir, alttaki bloklar yerinde
                # kalır. (Önceki sürümde apply_gravity çağrılıp tüm bloklar düşüyordu;
                # bu Yerçekimi Dalgası etkisine benziyordu ve tutarsızdı.)
                cut = max(1, value or 3)
                target_cells = self._simulate_peak_sculpt_cells(cut)
                removed = 0
                for (x, y) in target_cells:
                    center = _cell_pixel_center(x, y)
                    _clear_cell(x, y)
                    removed += 1
                    if center:
                        try:
                            self.create_particles(count=8, x=center[0], y=center[1],
                                                  colors=[(120, 230, 255)], speed=5)
                        except Exception:
                            pass
                # Yerçekimi YOK — kesilen tepe boşlukları olduğu gibi kalır.
                self._trigger_card_line_clear_animation()
                try:
                    self.trigger_screen_shake(intensity=5, duration=9 / 60.0)
                except Exception:
                    pass
                return t('tutorial_card_effect_peak_sculpt', blocks=removed,
                         default=f'En yüksek {removed} blok kesildi, yüzey alçaldı.')

            if card_id in ('gravity_well', 'block_magnet'):
                # Yerçekimi Dalgası: tüm boşlukları kapat (düşür), satırları temizle.
                pre = _snapshot_columns()
                try:
                    board.apply_gravity()
                except Exception:
                    pass
                self._animate_card_block_fall(pre)
                self._trigger_card_line_clear_animation()
                try:
                    self.trigger_screen_shake(intensity=7, duration=12 / 60.0)
                except Exception:
                    pass
                return t('tutorial_card_effect_gravity_well',
                         default='Tüm bloklar aşağı çöktü, boşluklar kapandı.')

            if card_id in ('nova_burst', 'mini_bomb'):
                # Patlama: merkezdeki yoğun bölgede temizle + parçacık + sarsıntı.
                pre = _snapshot_columns()
                rows = _occupied_rows_bottom_up()
                if rows:
                    cy = rows[0]
                    cx = board.width // 2
                    rad = 1 if card_id == 'nova_burst' else 0
                    blast_center = _cell_pixel_center(cx, cy)
                    for yy in range(cy - rad, cy + rad + 1):
                        for xx in range(cx - rad, cx + rad + 1):
                            if 0 <= yy < board.height and 0 <= xx < board.width:
                                _clear_cell(xx, yy)
                    if blast_center:
                        try:
                            self.create_particles(
                                count=28 if card_id == 'nova_burst' else 16,
                                x=blast_center[0], y=blast_center[1],
                                colors=[(255, 180, 80), (255, 120, 60), (255, 230, 150)],
                                speed=8)
                        except Exception:
                            pass
                    try:
                        self.trigger_screen_shake(
                            intensity=10 if card_id == 'nova_burst' else 6,
                            duration=14 / 60.0)
                    except Exception:
                        pass
                try:
                    board.apply_gravity()
                except Exception:
                    pass
                self._animate_card_block_fall(pre)
                self._trigger_card_line_clear_animation()
                return t('tutorial_card_effect_burst',
                         default='Yoğun bölgede patlama — bloklar temizlendi.')

            if card_id == 'row_shuffle':
                # Karıştırıcı: ana oyundaki gibi alt N satırdaki TÜM hücreleri
                # (dolu/boş + renk) havuzla, karıştırıp geri dağıt, sonra yerçekimi
                # uygula. (Önceki sürüm yalnız renkleri değiştiriyor ve yerçekimi
                # uygulamıyordu; ana oyun blokları taşıyıp aşağı oturtuyor.)
                import random as _rnd
                pre = _snapshot_columns()
                rows = _occupied_rows_bottom_up()[:max(1, value or 2)]
                if rows:
                    pool = []
                    for y in rows:
                        for x in range(board.width):
                            pool.append((bool(board.occupancy[y][x]), board.grid[y][x]))
                    _rnd.shuffle(pool)
                    idx = 0
                    for y in rows:
                        for x in range(board.width):
                            occ, col = pool[idx]
                            idx += 1
                            board.occupancy[y][x] = occ
                            board.grid[y][x] = col if occ else BLACK
                            if hasattr(board, 'texture_grid') and not occ:
                                board.texture_grid[y][x] = None
                            if hasattr(board, 'gold') and not occ:
                                board.gold[y][x] = False
                            if hasattr(board, 'owners') and not occ:
                                board.owners[y][x] = None
                        center = _cell_pixel_center(board.width // 2, y)
                        if center:
                            try:
                                self.create_particles(count=6, x=center[0], y=center[1],
                                                      colors=[(200, 160, 255)], speed=4)
                            except Exception:
                                pass
                    try:
                        board.apply_gravity()
                    except Exception:
                        pass
                    self._animate_card_block_fall(pre)
                self._trigger_card_line_clear_animation()
                return t('tutorial_card_effect_row_shuffle',
                         default='Alt satırlardaki bloklar karıştırıldı.')
        except Exception:
            return ''

        # Perk / zamanlı buff kartları: tahta değişmez.
        if bool(card.get('persistent')):
            return t('tutorial_card_effect_perk',
                     default='Kalıcı perk etkin — tüm run boyunca çalışır.')
        if bool(card.get('timed_buff')):
            return t('tutorial_card_effect_timed',
                     default='Zamanlı güç etkin — kısa süre avantaj sağlar.')
        return ''

    def _simulate_peak_sculpt_cells(self, steps):
        """Tepe Kesici'nin kaldıracağı hücreleri ana oyun algoritmasıyla simüle et.

        Mutasyon YOK — yalnız bir kopya yükseklik/işgal matrisi üzerinde çalışır.
        Ana oyundaki _level_peaks ile aynı kural: her adımda en yüksek sütunun
        tepe bloğunu kaldır; max_h - min_h <= 1 olunca dur.
        Döndürür: kaldırılacak (x, y) hücrelerinin listesi.
        """
        board = getattr(self, 'board', None)
        if board is None:
            return []
        width = board.width
        height = board.height
        # İşgal matrisinin kopyası (mutasyon yok).
        occ = [[bool(board.occupancy[y][x]) for x in range(width)] for y in range(height)]
        steps = max(1, int(steps))

        def col_height(x):
            for y in range(height):
                if occ[y][x]:
                    return height - y
            return 0

        removed_cells = []
        for _ in range(steps):
            heights = [col_height(x) for x in range(width)]
            if not heights:
                break
            max_h = max(heights)
            min_h = min(heights)
            if max_h <= 0 or (max_h - min_h) <= 1:
                break
            x = heights.index(max_h)
            for y in range(height):
                if occ[y][x]:
                    occ[y][x] = False
                    removed_cells.append((x, y))
                    break
        return removed_cells

    def _compute_card_effect_cells(self, card):
        """Kartın etkileyeceği (silinecek/vurgulanacak) hücreleri hesapla — mutasyon YOK.

        Showcase'in 'vurgu' fazında yanıp sönecek hücreleri döndürür.
        Döndürür: {(x, y), ...} kümesi.
        """
        board = getattr(self, 'board', None)
        if board is None or not isinstance(card, dict):
            return set()
        card_id = str(card.get('id') or '')
        try:
            value = int(card.get('value', 0) or 0)
        except Exception:
            value = 0
        cells = set()
        try:
            occupied_rows = [y for y in range(board.height - 1, -1, -1) if any(board.occupancy[y])]
            if card_id in ('clear_rows', 'row_shuffle'):
                n = max(1, value or 2)
                for y in occupied_rows[:n]:
                    for x in range(board.width):
                        if board.occupancy[y][x]:
                            cells.add((x, y))
            elif card_id == 'peak_sculpt':
                # Ana oyundaki _level_peaks algoritmasını birebir simüle et:
                # her adımda en yüksek sütunun tepe bloğunu kaldır; max-min <= 1
                # olunca dur. Vurgu = gerçekten kaldırılacak hücreler.
                cells = set(self._simulate_peak_sculpt_cells(max(1, value or 3)))
            elif card_id in ('nova_burst', 'mini_bomb'):
                if occupied_rows:
                    cy = occupied_rows[0]
                    cx = board.width // 2
                    rad = 1 if card_id == 'nova_burst' else 0
                    for yy in range(cy - rad, cy + rad + 1):
                        for xx in range(cx - rad, cx + rad + 1):
                            if 0 <= yy < board.height and 0 <= xx < board.width:
                                cells.add((xx, yy))
            elif card_id == 'gravity_well':
                # Çökecek tüm dolu hücreler vurgulanır.
                for y in range(board.height):
                    for x in range(board.width):
                        if board.occupancy[y][x]:
                            cells.add((x, y))
        except Exception:
            return set()
        return cells

    def _advance_card_preview_to_choosing(self):
        """Tahta inceleme aşamasından kart seçim aşamasına geç."""
        if not isinstance(self.card_choice_state, dict):
            return
        if self.card_choice_state.get('stage') != 'board_preview':
            return
        self.card_choice_state['stage'] = 'choosing'
        if self.card_ui:
            self.card_ui.reset()
            self._sync_tutorial_card_overlay_reference()
        try:
            self.sound.play('move')
        except Exception:
            pass

    def _show_lesson_result(self, result):
        outcome = self._enrich_board_lesson_outcome(dict(result or {}))
        success = bool(outcome.get('success'))
        feedback_map = {
            'clean': t('tutorial_result_feedback_clean', default='Temiz hamle. Tahtayı kontrol ederek ilerledin.'),
            'need_more_lines': t('tutorial_result_feedback_need_more_lines', default='Hedef satır sayısına ulaşamadın. Tahtadaki ana boşluğu tekrar oku.'),
            'need_hold': t('tutorial_result_feedback_need_hold', default='Bu derste doğru çözüm hold kullanmayı gerektiriyor. Önce parçayı saklayıp sonra gelen fırsatı kullan.'),
            'created_holes': t('tutorial_result_feedback_created_holes', default='Bu hamle yeni delikler açıyor. Kart modunda bu tür hatalar sonraki seçimleri zayıflatır.'),
            'stack_too_high': t('tutorial_result_feedback_stack_too_high', default='Bu hamle kuleyi gereksiz büyüttü. Önce güvenli tarafı kullan.'),
        }
        followup_lesson_id = self._get_followup_lesson_id(self.active_lesson_id)
        next_chapter_id, next_chapter_lesson_id = self._get_next_chapter_target(self.active_lesson_id)
        action_text = t('tutorial_result_action_to_menu', default='ENTER / SPACE: Menüye dön')
        if success and followup_lesson_id:
            action_text = t('tutorial_result_action_next_lesson', default='ENTER / SPACE: Sonraki ders')
        elif success and next_chapter_id and next_chapter_lesson_id and self.lesson_flow_scope != 'chapter':
            action_text = t('tutorial_result_action_next_chapter', default='ENTER / SPACE: Sonraki bölüme geç')
        elif success and self.hub_return_enabled:
            action_text = t('tutorial_result_action_to_hub', default='ENTER / SPACE: Ders merkezine dön')
        if not success:
            action_text = t('tutorial_result_action_retry', default='ENTER / R: Tekrar dene')

        self.lesson_result_active = True
        self._pending_card_choice_index = None
        if self.card_ui:
            self.card_ui.clear_selection_feedback()
        # FAZ E — Pedagojik üçlü: iyi yaptın / geliştir / ipucu.
        did_well_texts = [self._behavior_label(k) for k in list(outcome.get('did_well_keys') or [])]
        did_well_texts = [txt for txt in did_well_texts if txt]
        improve_texts = [self._behavior_label(k) for k in list(outcome.get('improve_keys') or [])]
        improve_texts = [txt for txt in improve_texts if txt]
        progressive_hint = self._get_progressive_result_hint(outcome, success)
        self.lesson_result = {
            'success': success,
            'title': str(outcome.get('title') or (t('tutorial_result_completed', default='Ders tamamlandı') if success else t('tutorial_result_retry_title', default='Tekrar Dene'))),
            'feedback': str(outcome.get('feedback') or feedback_map.get(outcome.get('feedback_key'), feedback_map['clean'])),
            'stars': int(outcome.get('stars', 0) or 0),
            'line_delta': int(outcome.get('line_delta', 0) or 0),
            'hole_delta': int(outcome.get('hole_delta', 0) or 0),
            'height_delta': int(outcome.get('height_delta', 0) or 0),
            'action_text': str(outcome.get('action_text') or action_text),
            'selected_card_title': outcome.get('selected_card_title'),
            'recommended_card_title': outcome.get('recommended_card_title'),
            'recommended_reason': outcome.get('recommended_reason'),
            'card_title': outcome.get('card_title'),
            'card_description': outcome.get('card_description'),
            'effect_summary': outcome.get('effect_summary'),
            'objective_results': list(outcome.get('objective_results') or []),
            'coach_text': str(outcome.get('coach_text') or ''),
            'did_well_texts': did_well_texts,
            'improve_texts': improve_texts,
            'progressive_hint': progressive_hint,
        }
        self.waiting_for_enter = False
        if success:
            self._mark_active_lesson_completed(stars=self.lesson_result['stars'])
            self.next_lesson_id = followup_lesson_id
            self._create_success_effects()
            self.sound.play('tutorial_complete')
            # FAZ 9.7 — Görkemli ilk Quadrix anı: 4 satır temizlendiyse ekstra kutlama.
            try:
                if int(outcome.get('line_delta', 0) or 0) >= 4:
                    self._create_mini_success_effect(
                        t('tutorial_quadrix_celebrate', default='QUADRIX! 4 satır birden!'))
                    self.progress_celebration_text = t(
                        'tutorial_quadrix_celebrate', default='QUADRIX! 4 satır birden!')
                    self.progress_celebration_timer = 2.2
                    self.trigger_screen_shake(intensity=12, duration=16 / 60.0)
            except Exception:
                pass

    def _handle_lesson_result_advance(self):
        """Sonuç panelinden ilerleme/tekrar kararını uygula (klavye + fare ortak yolu).

        Başarılıysa bir sonraki adıma geçer (_continue_after_completion); başarısızsa
        dersi yeniden başlatır. Dönüş: handle_input'a iletilecek değer veya None.
        """
        lesson_success = bool(self.lesson_result and self.lesson_result.get('success'))
        if lesson_success:
            return self._continue_after_completion()
        # Başarısız: dersi tekrar dene.
        self._start_lesson(self.active_lesson_id)
        return True

    def _get_progressive_result_hint(self, outcome, success) -> str:
        """FAZ E — Tekrarlanan başarısızlıkta sertleşen ipucu üret.

        Deneme sayısı arttıkça genel ipuçtan spesifik çözüme doğru ilerler.
        Başarılı sonuçta ipucu döndürmez. Aynı string'i tekrar göstermemek için
        son gösterilen ipucu lesson_runtime_state'te tutulur.
        """
        if success:
            return ''
        attempt = 1
        if isinstance(self.lesson_runtime_state, dict):
            attempt = int(self.lesson_runtime_state.get('attempt_count', 1) or 1)

        scenario = self._get_active_board_scenario()
        coach_feedback = scenario.get('coach_feedback') if isinstance(scenario, dict) else None
        feedback_key = str(outcome.get('feedback_key') or '')

        # 1. deneme: genel yönlendirme (briefing tip'i).
        # 2. deneme: feedback_key'e özgü coach metni.
        # 3+. deneme: en spesifik — scenario tip_text (somut hamle).
        if attempt <= 1:
            hint = t('tutorial_hint_level_general', default='İpuçlarını oku ve acele etme; önce tahtayı incele.')
        elif attempt == 2 and isinstance(coach_feedback, dict) and coach_feedback.get(feedback_key):
            hint = str(coach_feedback.get(feedback_key))
        else:
            hint = str(
                (scenario.get('tip_text') if isinstance(scenario, dict) else '')
                or (isinstance(coach_feedback, dict) and coach_feedback.get(feedback_key))
                or t('tutorial_hint_level_specific', default='Adım adım: önce doğru lane\'i seç, sonra parçayı oraya yerleştir.')
            )

        # Aynı ipucu tekrar gösterilmesin — farklıysa kaydet.
        last_hint = ''
        if isinstance(self.lesson_runtime_state, dict):
            last_hint = str(self.lesson_runtime_state.get('last_progressive_hint', '') or '')
        if hint and hint == last_hint and isinstance(coach_feedback, dict) and coach_feedback.get(feedback_key):
            # Tekrar ediyorsa bir kademe spesifikleştir.
            alt = str(scenario.get('tip_text') if isinstance(scenario, dict) else '')
            if alt and alt != hint:
                hint = alt
        if isinstance(self.lesson_runtime_state, dict):
            self.lesson_runtime_state['last_progressive_hint'] = hint
        return hint

    def _evaluate_active_scenario(self):
        initial_metrics = self.lesson_runtime_state.get('initial_metrics', {}) if isinstance(self.lesson_runtime_state, dict) else {}
        scenario = get_scenario(self.active_lesson.get('scenario_id')) if isinstance(self.active_lesson, dict) else None
        if not scenario:
            return None
        current_metrics = capture_board_metrics(self.board)
        outcome = evaluate_scenario(initial_metrics, current_metrics, scenario.get('evaluation'))
        outcome = self._enrich_board_lesson_outcome(outcome)
        self.lesson_runtime_state['last_result'] = dict(outcome)
        return outcome

    def _start_lesson(self, lesson_id):
        lesson = self.lesson_lookup.get(str(lesson_id)) or get_lesson(lesson_id)
        if not lesson:
            self._setup_step(1)
            return
        # FAZ C — Gerçek kuruluma geçmeden önce briefing'i hazırla ve göster.
        # Aynı ders ikinci kez oynanıyorsa briefing'i otomatik atla (kısa oturum).
        if self._should_show_lesson_briefing(lesson):
            self._open_lesson_briefing(lesson)
            return
        self._commit_lesson_setup(lesson)

    def _commit_lesson_setup(self, lesson, keep_briefing=False):
        """Dersin asıl kurulumunu yap (tahta, parça, runtime state).

        keep_briefing=True iken briefing açıkken çağrılır (arka plan tahtasını
        kurmak için); briefing state'i bozulmaz, oyun mantığı briefing_active ile
        durdurulmaya devam eder.
        """
        if not keep_briefing:
            self.briefing_active = False
            self.briefing_data = None
            self._pending_briefing_lesson_id = None
            self.lesson_stage = "play"
        # Önceki dersten kalan "başardın" banner'larını / kutlama yazısını temizle.
        self.step_completion_effects = []
        self.progress_celebration_timer = 0
        self.progress_celebration_text = ''
        self.inline_howto_active = False
        self.inline_howto_text = ''
        self.card_choice_state = {}
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

    def _should_show_lesson_briefing(self, lesson) -> bool:
        """Briefing gösterilmeli mi? İlk oynanışta evet, tekrarda otomatik geç."""
        if not isinstance(lesson, dict):
            return False
        lesson_id = str(lesson.get('id') or '')
        if not lesson_id:
            return False
        # 2026-06-20: İlk 4 drill dersi (tek-tuş mekaniği: hareket / döndür / soft /
        # hard drop) için briefing MODALI hiç gösterilmez — oyuncu Enter'a uğramadan
        # doğrudan oynar; board üstündeki satır-içi HOW TO rehberi (aynı metin)
        # yönlendirir. 5. ders (ilk satır temizleme) bir puzzle'dır, briefing'i korur.
        legacy_step = lesson.get('legacy_step')
        if isinstance(legacy_step, int) and legacy_step in (1, 2, 3, 4):
            return False
        seen = getattr(self, 'briefing_seen_lessons', None)
        if seen is None:
            seen = set()
            self.briefing_seen_lessons = seen
        # Aynı ders daha önce briefing gördüyse tekrar gösterme.
        return lesson_id not in seen

    def _blit_line_with_key_highlights(self, line, font, x, y, base_color, key_color, key_bg=None):
        """Bir metin satırını çiz; '[...]' içindeki tuş etiketlerini farklı renkte
        (ve istenirse hafif arka plan rozetiyle) vurgula. Toplam çizilen genişliği döndür.

        Tuş etiketleri (örn. [LEFT / A]) yeşil rehber kutusunda göze daha net ve
        hoş gelsin diye sıcak amber renkte gösterilir.
        """
        import re as _re
        segments = _re.split(r'(\[[^\]]*\])', str(line))
        cursor_x = int(x)
        for seg in segments:
            if not seg:
                continue
            is_key = len(seg) >= 2 and seg[0] == '[' and seg[-1] == ']'
            color = key_color if is_key else base_color
            surf = font.render(seg, True, color)
            if is_key and key_bg is not None:
                pad = max(2, font.get_height() // 8)
                badge = pygame.Rect(cursor_x - pad + 1, y - pad // 2,
                                    surf.get_width() + pad * 2 - 2, surf.get_height() + pad)
                bg_surf = pygame.Surface(badge.size, pygame.SRCALPHA)
                bg_surf.fill(key_bg)
                self.screen.blit(bg_surf, badge.topleft)
            self.screen.blit(surf, (cursor_x, y))
            cursor_x += surf.get_width()
        return cursor_x - int(x)

    def _get_lesson_howto_text(self, lesson_data) -> str:
        """İlk derslerde 'ne yapılacak ve nasıl' rehber metnini üret.

        Legacy step dersleri için tuş-temelli yönergeyi (tutorial_step_N +
        tutorial_tip_step_N) birleştirir. İlk defa oynayan oyuncuya başlat/atla
        panelinde net rehber sağlar.
        """
        if not isinstance(lesson_data, dict):
            return ''
        legacy_step = lesson_data.get('legacy_step')
        if not isinstance(legacy_step, int):
            return ''
        left_key = self._action_key_label('move_left', pygame.K_LEFT)
        right_key = self._action_key_label('move_right', pygame.K_RIGHT)
        rotate_key = self._action_key_label('rotate', pygame.K_UP)
        soft_key = self._action_key_label('soft_drop', pygame.K_DOWN, include_down_for_soft=True)
        hard_drop_key = self._action_key_label('hard_drop', pygame.K_SPACE)
        hold_key = self._action_key_label('hold', pygame.K_c)
        step_keys = {
            1: ('tutorial_step_1', 'tutorial_tip_step_1'),
            2: ('tutorial_step_2', 'tutorial_tip_step_2'),
            3: ('tutorial_step_3', 'tutorial_tip_step_3'),
            4: ('tutorial_step_4', 'tutorial_tip_step_4'),
            5: ('tutorial_step_5', 'tutorial_tip_step_5'),
            6: ('tutorial_step_6', 'tutorial_tip_step_6'),
        }
        keys = step_keys.get(int(legacy_step))
        if not keys:
            return ''
        instr_key, tip_key = keys
        instruction = t(
            instr_key,
            left_key=left_key, right_key=right_key, rotate_key=rotate_key,
            soft_key=soft_key, hard_drop_key=hard_drop_key, hold_key=hold_key,
            default='',
        )
        tip = t(tip_key, default='')
        return self._compose_lesson_guidance(instruction, tip)

    def _prepare_lesson_briefing(self, lesson) -> dict:
        """Briefing payload'ını ders metadata'sından üret (FAZ C)."""
        lesson_data = lesson if isinstance(lesson, dict) else {}
        scenario = None
        try:
            if lesson_data.get('kind') == 'scenario':
                scenario = get_scenario(lesson_data.get('scenario_id'))
            elif lesson_data.get('kind') == 'card_choice':
                scenario = get_card_choice_scenario(lesson_data.get('scenario_id'))
        except Exception:
            scenario = None
        scenario = scenario if isinstance(scenario, dict) else {}

        goal_text = str(
            scenario.get('goal_text')
            or lesson_data.get('goal_fallback')
            or self._lesson_description(lesson_data)
            or ''
        ).strip()
        watch_text = str(
            scenario.get('tip_text')
            or lesson_data.get('tip_fallback')
            or ''
        ).strip()

        # Hedef listesi (board senaryolarındaki objectives).
        objectives = []
        for objective in list(scenario.get('objectives') or []):
            if not isinstance(objective, dict):
                continue
            text = str(objective.get('text') or '').strip()
            if text:
                objectives.append(text)

        # Ders sayacı (DERS X / toplam) — hub ile aynı toplam.
        lesson_total = max(1, len(self.lesson_catalog)) if isinstance(getattr(self, 'lesson_catalog', None), list) else 1
        try:
            lesson_index = self._lesson_index(lesson_data.get('id'))
        except Exception:
            lesson_index = 1

        # G1 — Bölüm ilerleme rozeti ("Bölüm 5/7 · Kart Temelleri").
        chapter_index, chapter_total, chapter_name = self._chapter_progress_info(lesson_data)

        return {
            'lesson_id': str(lesson_data.get('id') or ''),
            'title': self._lesson_title(lesson_data),
            'goal': goal_text,
            'how_to': self._get_lesson_howto_text(lesson_data),
            'why': self._lesson_why(lesson_data),
            'watch': watch_text,
            'objectives': objectives,
            'duration_seconds': int(lesson_data.get('duration_seconds', 0) or 0),
            'difficulty': int(lesson_data.get('difficulty', 0) or 0),
            'lesson_type': str(lesson_data.get('lesson_type') or ''),
            'lesson_index': int(lesson_index),
            'lesson_total': int(lesson_total),
            'chapter_index': int(chapter_index),
            'chapter_total': int(chapter_total),
            'chapter_name': str(chapter_name or ''),
        }

    def _chapter_progress_info(self, lesson_data):
        """(chapter_index, chapter_total, chapter_name) döndür — G1 bölüm rozeti için.

        chapter_index 1-tabanlı; bulunamazsa (0, toplam, '') döner.
        """
        try:
            chapters = get_chapters()
        except Exception:
            chapters = []
        chapter_total = len(chapters)
        chapter_id = str(lesson_data.get('chapter') or '') if isinstance(lesson_data, dict) else ''
        chapter_index = 0
        chapter_name = ''
        for i, chapter in enumerate(chapters, start=1):
            if str(chapter.get('id') or '') == chapter_id:
                chapter_index = i
                title_key = chapter.get('title_key')
                fallback = chapter.get('title_fallback') or chapter_id
                chapter_name = t(title_key, default=fallback) if title_key else str(fallback)
                break
        return chapter_index, chapter_total, chapter_name

    def _open_lesson_briefing(self, lesson):
        """Briefing mikro-ekranını aç (oyun mantığı durur).

        Briefing açılırken YENİ dersin tahtası da kurulur; böylece panel arka
        planında doğru (yeni) seviye görünür. Oyun mantığı briefing_active ile
        durdurulduğu için tahta oynanmaz, sadece arka plan olarak görünür.
        """
        self.briefing_data = self._prepare_lesson_briefing(lesson)
        # Yeni dersin tahtasını şimdi kur (arka plan doğru seviyeyi göstersin).
        self._commit_lesson_setup(lesson, keep_briefing=True)
        self.briefing_active = True
        self.lesson_stage = "briefing"
        self._pending_briefing_lesson_id = str(lesson.get('id') or '')
        # Oyun arka planını sakin tut.
        self.in_transition = False
        self.waiting_for_enter = False
        self.lesson_result_active = False
        self.lesson_result = None
        # Önceki dersten kalan "başardın" banner'larını ve kutlama yazısını temizle
        # (yeni derse geçişte eski paneller görünmesin).
        self.step_completion_effects = []
        self.progress_celebration_timer = 0
        self.progress_celebration_text = ''
        try:
            self.sound.play('move')
        except Exception:
            pass

    def _confirm_lesson_briefing(self):
        """Briefing'i onayla ve derse başla (ENTER/SPACE/click).

        Tahta zaten _open_lesson_briefing'de kurulduğu için burada yalnız
        briefing'i kapatıp oyun mantığını serbest bırakırız.
        """
        lesson_id = self._pending_briefing_lesson_id
        if lesson_id:
            seen = getattr(self, 'briefing_seen_lessons', None)
            if seen is None:
                seen = set()
                self.briefing_seen_lessons = seen
            seen.add(str(lesson_id))
        self.briefing_active = False
        self.briefing_data = None
        self.lesson_stage = "play"
        self._pending_briefing_lesson_id = None

    def _skip_lesson_briefing(self):
        """Briefing'de 'Çıkış' — dersi başlatmadan ana menüye dön (ESC).

        Eskiden 'Atla' dersi başlatıyordu; artık eğitimden tamamen çıkış yapar.
        """
        self.briefing_active = False
        self.briefing_data = None
        self._pending_briefing_lesson_id = None
        return 'menu'

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
                    'hold_used': bool(self.lesson_runtime_state.get('hold_used', False)),
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
        # İlk derslerde board ortasında çıkan "hangi tuşa bas" rehber paneli,
        # derste kullanılan herhangi bir tuşa basılınca otomatik kaybolur.
        self.inline_howto_active = False

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
        self._clear_tutorial_das()
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
        # NOT: step_completion_effects'i BURADA temizleme — önceki adımın "tamam"
        # banner'ı animasyonunu tamamlasın (hızlı geçişlerde yarıda kesilmesin).
        # Banner'lar kendiliğinden süre dolunca silinir; en fazla 2 ile sınırlı.
        self.progress_celebration_timer = 0
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

        # İlk derslerde (1-4) board ortasında "hangi tuşa basılmalı" rehber paneli aç.
        # Derste kullanılan herhangi bir tuşa basılınca _register_step_activity ile kapanır.
        if step_num in (1, 2, 3, 4):
            inline_lesson = get_lesson_for_legacy_step(step_num)
            self.inline_howto_text = self._get_lesson_howto_text(inline_lesson) if inline_lesson else ''
            self.inline_howto_active = bool(self.inline_howto_text)
            self.inline_howto_pulse = 0.0
        else:
            self.inline_howto_active = False
            self.inline_howto_text = ''

        left_key = self._action_key_label('move_left', pygame.K_LEFT)
        right_key = self._action_key_label('move_right', pygame.K_RIGHT)
        rotate_key = self._action_key_label('rotate', pygame.K_UP)
        soft_key = self._action_key_label('soft_drop', pygame.K_DOWN, include_down_for_soft=True)
        hard_drop_key = self._action_key_label('hard_drop', pygame.K_SPACE)
        hold_key = self._action_key_label('hold', pygame.K_c)
        lesson_title = self._lesson_title() or self.overlay_message

        if step_num == 1: # Move
            self.step_target = 3
            self.overlay_message = lesson_title
            self.tip_message = self._compose_lesson_guidance(
                t('tutorial_step_1', left_key=left_key, right_key=right_key),
                t('tutorial_tip_step_1'),
            )
            self.sub_message = t('tutorial_sub_move', left=0, right=0)
            
        elif step_num == 2: # Rotate
            self.step_target = 3 
            self.overlay_message = lesson_title
            self.tip_message = self._compose_lesson_guidance(
                t('tutorial_step_2', rotate_key=rotate_key),
                t('tutorial_tip_step_2'),
            )
            self.sub_message = t('tutorial_sub_rotate', count=0, target=3)
            # Ensure T piece for rotation demo, centered
            self.current_piece = self._create_named_piece('T')
            self.current_piece.x = 4
            self.current_piece.y = 2
            self.apply_theme_to_pieces()
            
        elif step_num == 3: # Soft Drop
            self.step_target = 40 # Frames held ~0.7s (at 60fps)
            self.overlay_message = lesson_title
            self.tip_message = self._compose_lesson_guidance(
                t('tutorial_step_3', soft_key=soft_key),
                t('tutorial_tip_step_3'),
            )
            self.sub_message = t('tutorial_sub_soft_drop', soft_key=soft_key, progress=0, target=40)
            
        elif step_num == 4: # Hard Drop
            self.step_target = 1
            self.overlay_message = lesson_title
            self.tip_message = self._compose_lesson_guidance(
                t('tutorial_step_4', hard_drop_key=hard_drop_key),
                t('tutorial_tip_step_4'),
            )
            self.sub_message = t('tutorial_sub_hard_drop', hard_drop_key=hard_drop_key)
            
        elif step_num == 5: # Line Clear
            self.step_target = 1
            self.overlay_message = lesson_title
            self.tip_message = self._compose_lesson_guidance(
                t('tutorial_step_5'),
                t('tutorial_tip_step_5'),
            )
            self.sub_message = t('tutorial_sub_line_clear')
            self._setup_line_clear_scenario()
            
        elif step_num == 6: # Hold
            self.step_target = 1
            self.overlay_message = lesson_title
            self.tip_message = self._compose_lesson_guidance(
                t('tutorial_step_6', hold_key=hold_key),
                t('tutorial_tip_step_6'),
            )
            self.sub_message = t('tutorial_sub_hold', hold_key=hold_key)
            self.can_hold = True
            self.held_piece = None
            
        elif step_num == 7: # Complete
            self.step_target = 1
            self.waiting_for_enter = True
            self.next_lesson_id = self._get_followup_lesson_id(self.active_lesson_id)
            next_chapter_id, next_chapter_lesson_id = self._get_next_chapter_target(self.active_lesson_id)
            self.overlay_message = self._lesson_title() or t('tutorial_complete')
            self.tip_message = t('tutorial_tip_step_7')
            if self.next_lesson_id:
                self.sub_message = t('tutorial_next_board_lessons_prompt', default='Enter ile tahta okuma derslerine geç.')
            elif next_chapter_id and next_chapter_lesson_id and self.lesson_flow_scope != 'chapter':
                self.sub_message = t('tutorial_next_chapter_prompt', default='Enter ile sonraki bölüme geç.')
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
        # Mavi "tamamlandı" paneli geldiği an, yeşil "tamam!" banner'ları DONMASIN —
        # anında yok olsun (kullanıcı isteği). Banner'lar transition sırasında
        # yarıda kalmış gibi görünmesin diye burada temizleniyor.
        self.step_completion_effects = []
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
        active_width, active_height = self._active_ui_size()
        center_x = active_width // 2
        center_y = active_height // 2
        
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
        """Küçük başarı efekti — göze hoş, kayıp gitmeyen bir 'başardın' banner'ı.

        Ekranın üst-orta kısmında kısa süre beliren, yukarı süzülerek solan,
        ✓ ikonlu yeşil bir bildirim. step_completion_effects listesine eklenir;
        _update_success_effects zamanlar, _draw_mini_success_effects çizer.
        """
        try:
            self.sound.play('tutorial_progress')
        except Exception:
            pass
        message = str(message or '').strip()
        if not message:
            return
        if not isinstance(getattr(self, 'step_completion_effects', None), list):
            self.step_completion_effects = []
        # Aynı mesaj zaten gösteriliyorsa tekrar ekleme (yarıda kesilme/çift gösterim önle).
        for existing in self.step_completion_effects:
            if str(existing.get('message', '')) == message and float(existing.get('timer', 0)) > 0.5:
                return
        # En fazla 2 banner aynı anda — üst üste binme/karmaşa önle (en eskiyi düşür).
        while len(self.step_completion_effects) >= 2:
            self.step_completion_effects.pop(0)
        self.step_completion_effects.append({
            'message': message,
            'timer': 1.4,
            'max_timer': 1.4,
            'alpha': 255,
            'y_offset': 0.0,
            'scale': 0.6,
        })

    def _ensure_normal_piece(self, force_new=False):
        if force_new or not self.current_piece or self.current_piece.name == 'O':
            self.current_piece = self._create_named_piece('T')
            self.current_piece.x = 4
            self.current_piece.y = self._compute_spawn_y(self.current_piece)
            self._skip_hidden_rows(self.current_piece)
            self.apply_theme_to_pieces()

    def _setup_line_clear_scenario(self):
        self._clear_tutorial_board()
        color = (100, 100, 100) # Gray
        bottom = self.board.height - 1
        above = self.board.height - 2

        # Boşluk sağ tarafta (sütun 7-8): oyuncu O parçasını sağa taşımalı.
        for x in range(self.board.width):
            if x not in (7, 8):
                self.board.grid[bottom][x] = color
                self.board.occupancy[bottom][x] = True

        for x in range(self.board.width):
            if x in (0, 1, 9):
                self.board.grid[above][x] = color
                self.board.occupancy[above][x] = True

        # O parçası merkezde doğar → sağa taşınması gerekir
        self.current_piece = self._create_named_piece('O')
        self.current_piece.x = 4
        self.current_piece.y = self._compute_spawn_y(self.current_piece)
        self._skip_hidden_rows(self.current_piece)
        # Bu derste sağ panel tek sonraki parçayı göstermeli.
        self.next_piece_queue = [self.spawn_new_piece()]
        self.apply_theme_to_pieces()

        # Ders 5: highlight HEMEN gösterilir (2 başarısızlık beklenmez).
        # O parçası 7-8 sütunlarındaki boşluğa oturur — dinamik footprint.
        self.board_highlight_spec = {
            'placements': [['O', 0, 7]],
            'columns': [],
            'cells': [(7, above), (8, above), (7, bottom), (8, bottom)],
        }
        self._board_highlight_allowed = True
        self.board_highlight_timer = float(getattr(self, 'board_highlight_duration_s', 3.0))
        self.hold_highlight_active = False
        self.hold_highlight_pulse = 0.0
    
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
            if getattr(self, 'hub_arrow_left_rect', None) and self.hub_arrow_left_rect.collidepoint(pos):
                self._move_hub_chapter_selection(-1)
                return True
            if getattr(self, 'hub_arrow_right_rect', None) and self.hub_arrow_right_rect.collidepoint(pos):
                self._move_hub_chapter_selection(1)
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

    def _tutorial_horizontal_movement_enabled(self):
        if getattr(self, 'game_over', False):
            return False
        if getattr(self, 'show_exit_prompt', False):
            return False
        if getattr(self, 'briefing_active', False):
            return False
        if getattr(self, 'progress_panel_active', False):
            return False
        if getattr(self, 'in_transition', False):
            return False
        if getattr(self, 'waiting_for_enter', False):
            return False
        if getattr(self, 'lesson_result_active', False):
            return False
        if getattr(self, 'hub_active', False):
            return False

        active_lesson = getattr(self, 'active_lesson', None)
        if isinstance(active_lesson, dict) and active_lesson.get('kind') == 'card_choice':
            return False
        if isinstance(active_lesson, dict) and active_lesson.get('kind') == 'scenario':
            return True
        return getattr(self, 'step', 0) in (1, 5, 6)

    def _clear_tutorial_das(self):
        self.das_direction = 0
        self.das_timer = 0
        self.das_repeat_timer = 0
        self.das_charged = False

    def _begin_tutorial_das(self, direction):
        self.das_direction = direction
        self.das_timer = 0
        self.das_repeat_timer = 0
        self.das_charged = False

    def _tutorial_action_pressed(self, action):
        try:
            pressed = pygame.key.get_pressed()
        except Exception:
            pressed = None
        for key in self._action_keys(self.control_bindings, action):
            if self._is_key_pressed(key, pressed):
                return True
        return False

    def _handle_tutorial_das_keyup(self, key):
        if key in self._action_keys(self.control_bindings, 'move_left'):
            if self.das_direction == -1:
                if self._tutorial_action_pressed('move_right'):
                    self._perform_tutorial_horizontal_move(1)
                    self._begin_tutorial_das(1)
                else:
                    self._clear_tutorial_das()
            return True

        if key in self._action_keys(self.control_bindings, 'move_right'):
            if self.das_direction == 1:
                if self._tutorial_action_pressed('move_left'):
                    self._perform_tutorial_horizontal_move(-1)
                    self._begin_tutorial_das(-1)
                else:
                    self._clear_tutorial_das()
            return True

        return False

    def _perform_tutorial_horizontal_move(self, direction):
        if not self._tutorial_horizontal_movement_enabled():
            self._clear_tutorial_das()
            return False

        if direction == -1:
            moved = self._try_move_left()
        elif direction == 1:
            moved = self._try_move_right()
        else:
            return False

        if not moved:
            return False

        self._register_step_activity()
        if getattr(self, 'sound', None):
            self.sound.play('move')

        active_lesson = getattr(self, 'active_lesson', None)
        if isinstance(active_lesson, dict) and active_lesson.get('kind') == 'scenario':
            if direction == -1:
                self.step_move_left_count += 1
            else:
                self.step_move_right_count += 1
            self._sync_lesson_runtime_state()
            return True

        if getattr(self, 'step', 0) == 1:
            if direction == -1:
                self.step_move_left_count = min(3, self.step_move_left_count + 1)
                self.sub_message = t('tutorial_sub_move', left=self.step_move_left_count, right=self.step_move_right_count)
                if self.step_move_left_count <= 3:
                    self._create_mini_success_effect(t('tutorial_success_move_left', default='Sola hareket tamam!'))
            else:
                self.step_move_right_count = min(3, self.step_move_right_count + 1)
                self.sub_message = t('tutorial_sub_move', left=self.step_move_left_count, right=self.step_move_right_count)
                if self.step_move_right_count <= 3:
                    self._create_mini_success_effect(t('tutorial_success_move_right'))
            self._sync_lesson_runtime_state()
            if self.step_move_left_count >= 3 and self.step_move_right_count >= 3:
                self._complete_step(2)
        elif getattr(self, 'step', 0) in (5, 6):
            self._sync_lesson_runtime_state()

        return True

    def _perform_das_move(self, direction):
        return self._perform_tutorial_horizontal_move(direction)

    def _handle_tutorial_horizontal_keydown(self, key, bindings):
        if key in self._action_keys(bindings, 'move_left'):
            if self._tutorial_horizontal_movement_enabled():
                self._perform_tutorial_horizontal_move(-1)
                self._begin_tutorial_das(-1)
            return True
        if key in self._action_keys(bindings, 'move_right'):
            if self._tutorial_horizontal_movement_enabled():
                self._perform_tutorial_horizontal_move(1)
                self._begin_tutorial_das(1)
            return True
        return False

    def handle_input(self):
        if self.game_over:
             return super().handle_input()
             
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            # --- EXIT PROMPT HANDLING (Mouse + Key) ---
            if self.show_exit_prompt:
                self._clear_tutorial_das()
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
                self._apply_tutorial_resize(event.w, event.h)
                continue

            # FAZ C — Briefing aktifken oyun mantığı çalışmaz; sadece başlat/çıkış.
            if getattr(self, 'briefing_active', False):
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        result = self._skip_lesson_briefing()
                        if result is not None:
                            return result
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        self._confirm_lesson_briefing()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                    skip_rect = getattr(self, 'briefing_skip_rect', None)
                    start_rect = getattr(self, 'briefing_start_rect', None)
                    if skip_rect and skip_rect.collidepoint(pos):
                        result = self._skip_lesson_briefing()
                        if result is not None:
                            return result
                    else:
                        # Başlat butonu veya panelin başka bir yeri → dersi başlat.
                        self._confirm_lesson_briefing()
                continue

            # FAZ 2 — İlerleme paneli aktifken: devam et / çıkıp oyna.
            if getattr(self, 'progress_panel_active', False):
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        result = self._progression_panel_continue()
                        if result is not None:
                            return result
                    elif event.key == pygame.K_ESCAPE:
                        result = self._progression_panel_play()
                        if result is not None:
                            return result
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                    continue_rect = getattr(self, 'progress_panel_continue_rect', None)
                    play_rect = getattr(self, 'progress_panel_play_rect', None)
                    if continue_rect and continue_rect.collidepoint(pos):
                        result = self._progression_panel_continue()
                        if result is not None:
                            return result
                    elif play_rect and play_rect.collidepoint(pos):
                        result = self._progression_panel_play()
                        if result is not None:
                            return result
                continue

            if self.hub_active:
                hub_action = self._handle_hub_input_event(event)
                if hub_action is not None:
                    return hub_action
                continue

            if self._is_card_choice_lesson_active() and not self.lesson_result_active:
                stage = self._card_choice_stage()
                # Kart etkisi gösterim sahnesi: animasyon oynarken girişi yut;
                # ENTER/SPACE/tık ile erken atlanabilir (sonuç paneline geç).
                if stage == 'showcase':
                    if event.type == pygame.KEYDOWN and event.key in (
                        pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
                    ):
                        self._finish_card_effect_showcase()
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self._finish_card_effect_showcase()
                    continue
                # Tahta inceleme aşaması: ENTER/SPACE/tık ile kart seçimine geç.
                if stage == 'board_preview':
                    if event.type == pygame.KEYDOWN and event.key in (
                        pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
                    ):
                        self._advance_card_preview_to_choosing()
                        continue
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                        cont_rect = getattr(self, 'card_preview_continue_rect', None)
                        if cont_rect and cont_rect.collidepoint(pos):
                            self._advance_card_preview_to_choosing()
                        continue
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        self.show_exit_prompt = True
                    continue
                if event.type == pygame.MOUSEMOTION and self.card_ui:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                    self.card_ui.handle_mouse_move(pos)
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.card_ui:
                    pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                    choice = self.card_ui.handle_mouse_click(pos)
                    if choice == 'PEEK':
                        continue
                    if isinstance(choice, int):
                        self._queue_card_choice_selection(choice)
                        continue

            # Sonuç paneli açıkken fare ile ilerleme/tekrar (tıklanabilir buton).
            if self.lesson_result_active and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = normalize_mouse_pos(getattr(event, 'pos', None)) or get_mouse_pos()
                primary_rect = getattr(self, 'lesson_result_primary_rect', None)
                if primary_rect and primary_rect.collidepoint(pos):
                    result_action = self._handle_lesson_result_advance()
                    if result_action is not None:
                        return result_action
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
                        return self._continue_after_completion()
                    continue

                if self.lesson_result_active:
                    lesson_success = bool(self.lesson_result and self.lesson_result.get('success'))
                    continue_keys = (pygame.K_RETURN, pygame.K_KP_ENTER)
                    if lesson_success:
                        continue_keys = continue_keys + (pygame.K_SPACE,)
                    if event.key in continue_keys:
                        result_action = self._handle_lesson_result_advance()
                        if result_action is not None:
                            return result_action
                        continue
                    if event.key == pygame.K_r:
                        # R her zaman dersi yeniden başlatır (tekrar dene).
                        self._start_lesson(self.active_lesson_id)
                        return True
                    continue
                
                bindings = self.control_bindings

                if self._is_card_choice_lesson_active():
                    # Yalnız kart seçim aşamasında klavye seçim girişlerini işle.
                    if self._card_choice_stage() != 'choosing':
                        continue
                    if self.card_ui and getattr(self.card_ui, 'peek_mode_active', False):
                        continue
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
                    if self._handle_tutorial_horizontal_keydown(event.key, bindings):
                        continue
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
                    elif event.key == bindings.get('hold') and getattr(self, '_scenario_allow_hold', False):
                        self._use_scenario_hold()
                    continue
                
                # --- Step Logic with Filtering ---
                
                # Step 1: Move Left/Right
                if self.step == 1:
                    self._handle_tutorial_horizontal_keydown(event.key, bindings)
                                
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
                    if self._handle_tutorial_horizontal_keydown(event.key, bindings):
                        continue
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
                    if self._handle_tutorial_horizontal_keydown(event.key, bindings):
                        continue
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
                                self._skip_hidden_rows(self.current_piece)
                                self.next_piece_queue.append(self.spawn_new_piece())
                            else:
                                self.current_piece, self.held_piece = self.held_piece, self.current_piece
                                self.current_piece.x = 3
                                self.current_piece.y = self._compute_spawn_y(self.current_piece)
                                self._skip_hidden_rows(self.current_piece)
                            self.can_hold = False
                            self.sound.play('move')
                            self._create_mini_success_effect(t('tutorial_success_hold'))
                            self._complete_step(7)

            # GLOBAL KEYUP HANDLING (Safety)
            if event.type == pygame.KEYUP:
                if event.key in self._soft_drop_keycodes():
                    self.fall_speed = self.base_fall_speed
                    self.soft_drop_active = False
                self._handle_tutorial_das_keyup(event.key)

        return True

    def _perform_hard_drop(self):
        start_y = self.current_piece.y
        while self.board.is_valid_position(self.current_piece):
            self.current_piece.y += 1
        self.current_piece.y -= 1
        if self.effects_enabled and self.current_piece.y > start_y:
            self.trigger_hard_drop_screen_shake()
        self.lock_and_new_piece()
        self.sound.play('drop')
        try:
            from gamepad_manager import get_gamepad_manager
            get_gamepad_manager().rumble(0.3, 0.6, 120)
        except Exception:
            pass

    def _update_overlay_safe_visual_effects(self, delta_time):
        dt = max(0.0, float(delta_time or 0.0))
        dt_seconds = dt / 1000.0
        dt_frames = dt / 16.666 if dt > 0 else 0.0

        if self.line_clear_animation > 0:
            self.line_clear_animation = float(self.line_clear_animation) - dt_frames
            frames_left = int(self.line_clear_animation)
            self.line_clear_flash = (frames_left % 10) < 5
            if self.line_clear_animation <= 0:
                self.line_clear_flash = False
                self.board.last_cleared_lines = []

        if self.line_clear_sweep_active:
            cell_size = self.get_cell_size()
            board_pixel_width = self.board_width * cell_size
            sweep_width = max(1, int(cell_size * 1.5))
            sweep_travel_px = max(1.0, float(board_pixel_width + sweep_width))
            level = max(1, int(getattr(self.board, 'level', 1)))
            sweep_speed = _compute_line_sweep_progress_speed(self.block_fall_speed, sweep_travel_px, level)
            self.line_clear_sweep_progress += dt_seconds * sweep_speed
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
            lock_count = self._register_scenario_piece_lock()
            outcome = self._evaluate_active_scenario()
            if outcome and (bool(outcome.get('success')) or lock_count >= self._get_scenario_lock_budget()):
                self._show_lesson_result(outcome)
            else:
                self._sync_lesson_runtime_state()
            return
        
        # Check line clear for Step 5
        if self.step == 5 and not self.in_transition:
            lines_after = self.board.lines_cleared
            if lines_after > lines_before:
                self._mark_active_lesson_completed(stars=1)
                self.hub_progress_snapshot = self._get_tutorial_progress_snapshot()
                self.in_transition = True
                self.transition_timer = 1.5
                # Mavi "tamamlandı" paneli açıldığı an yeşil banner'lar donmasın —
                # anında temizlenir (kullanıcı isteği).
                self.step_completion_effects = []
                self.transition_text = t('tutorial_step_done_line_clear', default='Satır temizleme tamam!')
                self.next_step_num = 0
                # Yalnız AYNI bölüm içindeki sonraki dersi otomatik başlat. Bölüm
                # sınırını (quick_start sonu) geçişte ise transition bitince ilerleme
                # paneli OTOMATİK açılır (Enter beklenmez).
                self.next_lesson_id = get_next_lesson_id(self.active_lesson_id, chapter_only=True)
                self.waiting_for_enter = False
                self._auto_continue_after_transition = not bool(self.next_lesson_id)
                self.overlay_message = t('tutorial_quick_start_done', default='Hızlı Başlangıç tamamlandı!')
                self.sub_message = ''
                # İlk 4 dersle AYNI: ortada sarı/altın kutlama paneli göster
                # (soldaki yeşil panel artık çizilmiyor).
                self._create_success_effects()
                self.progress_celebration_timer = 2.0
                self.progress_celebration_text = t('tutorial_step_done_line_clear', default='İlk satır temizlemeni yaptın.')
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
        if not self._tutorial_horizontal_movement_enabled():
            self._clear_tutorial_das()

        # FAZ C — Briefing aktifken oyun simülasyonu durur; yalnız efektler ilerler.
        if getattr(self, 'briefing_active', False):
            self._update_overlay_safe_visual_effects(delta_time)
            return

        # FAZ 2 — İlerleme paneli aktifken de oyun simülasyonu durur.
        if getattr(self, 'progress_panel_active', False):
            self._update_overlay_safe_visual_effects(delta_time)
            return

        # Handle transition delay
        if self.in_transition:
            self.transition_timer -= dt_seconds
            if self.transition_timer <= 0:
                self.in_transition = False
                if self.next_lesson_id:
                    self._start_lesson(self.next_lesson_id)
                elif getattr(self, '_auto_continue_after_transition', False):
                    # Bölüm sonu — ilerleme panelini OTOMATİK aç (Enter beklenmez).
                    self._auto_continue_after_transition = False
                    self._continue_after_completion()
                elif self.waiting_for_enter:
                    pass  # Enter bekleniyor (geri uyumluluk)
                else:
                    self._setup_step(self.next_step_num)
            # Transition sırasında da efektleri güncelle
            self._update_success_effects(dt_seconds)
            self._update_overlay_safe_visual_effects(delta_time)
            return
            
        # Başarı efektlerini güncelle
        self._update_success_effects(dt_seconds)

        if self.hub_active:
            # Carousel animasyonunu güncelle
            hub_anim_offset = float(getattr(self, '_hub_carousel_anim_offset', 0.0) or 0.0)
            hub_anim_target = float(getattr(self, '_hub_carousel_anim_target', 0.0) or 0.0)
            if abs(hub_anim_offset) > 0.005:
                speed = 8.0
                hub_anim_offset += (hub_anim_target - hub_anim_offset) * min(1.0, speed * dt_seconds)
                self._hub_carousel_anim_offset = hub_anim_offset
                if abs(self._hub_carousel_anim_offset) < 0.005:
                    self._hub_carousel_anim_offset = 0.0
                    self._hub_carousel_prev_chapter_id = None
            else:
                self._hub_carousel_anim_offset = 0.0
                self._hub_carousel_prev_chapter_id = None
            self._update_overlay_safe_visual_effects(delta_time)
            return

        if self.lesson_result_active:
            self._update_overlay_safe_visual_effects(delta_time)
            return

        if self._is_card_choice_lesson_active():
            stage = self._card_choice_stage()
            if stage == 'showcase':
                # İki fazlı kart etkisi gösterimi: vurgu → uygula/temizle → sonuç.
                phase = getattr(self, 'card_effect_showcase_phase', 'highlight')
                if phase == 'highlight':
                    self.card_effect_highlight_timer = max(
                        0.0, float(getattr(self, 'card_effect_highlight_timer', 0.0)) - dt_seconds)
                    if self.card_effect_highlight_timer <= 0.0:
                        self._apply_card_effect_showcase_mutation()
                else:
                    self.card_effect_showcase_timer = max(
                        0.0, float(getattr(self, 'card_effect_showcase_timer', 0.0)) - dt_seconds)
                    if self.card_effect_showcase_timer <= 0.0:
                        self._finish_card_effect_showcase()
                if self.card_ui:
                    self.card_ui.update(delta_time, False)
                self._update_overlay_safe_visual_effects(delta_time)
                return
            if self.card_ui and stage == 'choosing':
                self.card_ui.update(delta_time, True)
                if self._pending_card_choice_index is not None and not self.card_ui.is_selection_animating():
                    self._finalize_pending_card_choice_selection()
            self._update_overlay_safe_visual_effects(delta_time)
            return

        if self.card_ui:
            self.card_ui.update(delta_time, False)
        
        # Board highlight: yerleştirme indeksi değişince her yeni parça için
        # süreyi sıfırla (her highlight ekranda kendi süresini dolduruncaya kadar kalır).
        if self._is_scenario_lesson_active() and getattr(self, '_board_highlight_allowed', False):
            current_idx = self._active_highlight_placement_index()
            if current_idx != getattr(self, '_board_highlight_last_index', -1):
                self._board_highlight_last_index = current_idx
                # Yeni parça için highlight'ı yeniden göster (eğer hâlâ placement varsa).
                if self._get_active_highlight_cells():
                    self.board_highlight_timer = self.board_highlight_duration_s
                self.step_idle_timer = 0.0
        # FAZ D — Board highlight zamanlayıcısını ilerlet.
        if getattr(self, 'board_highlight_timer', 0.0) > 0.0:
            self.board_highlight_timer = max(0.0, float(self.board_highlight_timer) - dt_seconds)

        # Hold kutu vurgusu: doğru placement sırası gelince yan; hold kullanılınca kapat.
        if getattr(self, 'hold_highlight_armed', False):
            current_idx = self._active_highlight_placement_index()
            hold_used = bool(isinstance(self.lesson_runtime_state, dict) and self.lesson_runtime_state.get('hold_used'))
            should_show = (current_idx == int(getattr(self, 'hold_highlight_index', 0) or 0)) and not hold_used
            self.hold_highlight_active = should_show
            if should_show:
                self.hold_highlight_pulse = float(getattr(self, 'hold_highlight_pulse', 0.0)) + dt_seconds

        # Mini başarı efektlerini güncelle (pop-in → bekle → yukarı süzül & sol)
        for effect in self.step_completion_effects[:]:
            effect['timer'] -= dt_seconds
            max_t = float(effect.get('max_timer', 1.4)) or 1.4
            t_left = max(0.0, float(effect['timer']))
            elapsed = max_t - t_left
            # Pop-in: ilk 0.2 sn'de 0.6 → 1.08, sonra 1.0'a otur.
            if elapsed < 0.2:
                effect['scale'] = 0.6 + (1.08 - 0.6) * (elapsed / 0.2)
            elif elapsed < 0.32:
                effect['scale'] = 1.08 - 0.08 * ((elapsed - 0.2) / 0.12)
            else:
                effect['scale'] = 1.0
            # Son 0.5 sn'de yukarı süzülerek sol.
            if t_left < 0.5:
                effect['alpha'] = int(255 * (t_left / 0.5))
                effect['y_offset'] -= 36 * dt_seconds
            else:
                effect['alpha'] = 255
            if effect['timer'] <= 0:
                self.step_completion_effects.remove(effect)

        # 2026-06-20: İlk 4 derste, board üstündeki HOW TO'da istenen tuşa basılana
        # kadar parça AŞAĞI DÜŞMESİN. inline_howto_active yalnız step 1-4'te aktiftir ve
        # derste kullanılan tuşa basılınca otomatik False olur (istenen tetik). Aktifken
        # her karede fall_time sıfırlanır → ebeveyn gravity eşiği (fall_speed) hiç aşılmaz.
        if getattr(self, 'inline_howto_active', False):
            self.fall_time = 0

        super().update(delta_time)

        if not self.waiting_for_enter and not self._is_scenario_lesson_active() and self.step < 7:
            self.step_idle_timer += dt_seconds
            self.stuck_hint_pulse_timer += dt_seconds
            if self.step_idle_timer >= self.stuck_hint_delay_s and not self.stuck_hint_message:
                self.stuck_hint_message = self._get_stuck_hint_text()

        # FAZ D — Takılma algılanınca board highlight'ı tekrar göster.
        # Yalnız highlight'a izin verilen (2+ başarısızlık / ders 5) derslerde.
        if (not self.waiting_for_enter and not self.lesson_result_active
                and (self._is_scenario_lesson_active() or self.step == 5) and self.board_highlight_spec
                and getattr(self, '_board_highlight_allowed', False)):
            # Senaryo derslerinde timer yukarıdaki blokta artmaz; burada arttır.
            if self._is_scenario_lesson_active():
                self.step_idle_timer += dt_seconds
            if self.step_idle_timer >= self.stuck_hint_delay_s and self.board_highlight_timer <= 0.0:
                self._trigger_board_highlight()
                self.step_idle_timer = 0.0
        
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
                 
                 if self.soft_drop_counter >= self.step_target:
                     self._complete_step(4)

    def draw_mode_overlay(self):
        """Mod katmanına çizim (Game.draw içinde çağrılır)"""
        if self.hub_active:
            self._draw_tutorial_hub()
            return

        # FAZ C — Briefing aktifse, sadece briefing'i çiz (oyun arka planda durur).
        if getattr(self, 'briefing_active', False):
            self._draw_lesson_briefing()
            return

        # FAZ 2 — İlerleme paneli aktifse, board üzerine paneli çiz.
        if getattr(self, 'progress_panel_active', False):
            self._draw_progression_panel()
            return

        # Başarı efektlerini çiz
        self._draw_success_effects()
        
        # Mini başarı efektlerini çiz
        self._draw_mini_success_effects()

        if self._is_card_choice_lesson_active() and not self.lesson_result_active:
            stage = self._card_choice_stage()
            if stage == 'board_preview':
                # Önce tahtayı incele: üstte "devam et" panelli açıklama.
                self._draw_card_board_preview_overlay()
            elif stage == 'showcase':
                # Kart etkisi canlı gösteriliyor: board görünür + üstte etki banner'ı.
                self._draw_card_effect_showcase()
            else:
                self._draw_card_choice_overlay()
        else:
            # FAZ D — Board highlight (iniş ayak izi) + hold kutu vurgusu.
            if not self.lesson_result_active:
                if getattr(self, 'board_highlight_spec', None):
                    self._draw_board_highlight()
                if self._is_scenario_lesson_active():
                    self._draw_hold_box_highlight()
                    # Hedef tamamlanışı mikro kutlamasını tetikle (çizim sol panelde).
                    self._update_objective_completion_feedback()
            # Tutorial overlay'ini çiz
            self._draw_tutorial_overlay()
            # İlk derslerde board ortasında "hangi tuşa bas" rehber paneli.
            if not self.lesson_result_active and not self.in_transition:
                self._draw_inline_howto_hint()

        if self.lesson_result_active:
            self._draw_lesson_result_panel()
        
        # Progress celebration çiz
        self._draw_progress_celebration()

    def _draw_board_highlight(self):
        """Parçanın oturacağı tam ayak izini (footprint) kırmızı outline ile işaretle.

        Hücreler tam grid hizasında çizilir; ayak izinin etrafına birleşik bir
        kenar çizgisi (sadece dış kenarlar) çekilir — tek tek kutucuk yerine
        parçanın gerçek şekline tam oturan bir çerçeve. Kırmızı = dikkat çeker.
        """
        if getattr(self, 'board_highlight_timer', 0.0) <= 0.0:
            return
        spec = getattr(self, 'board_highlight_spec', None)
        if not isinstance(spec, dict):
            return
        try:
            board_offset_x, board_offset_y = self.get_board_offset()
            cell_size = int(self.get_cell_size())
        except Exception:
            return
        if cell_size <= 0:
            return

        board_width = int(getattr(self, 'board_width', 10) or 10)
        board_height = int(getattr(self, 'board_height', 20) or 20)

        # Yanıp sönme.
        pulse = abs(math.sin(self.board_highlight_timer * 4.0))
        alpha = int(120 + 120 * pulse)
        color = (255, 70, 70)
        border_w = max(2, cell_size // 9)
        active_width, active_height = self._active_ui_size()
        canvas_rect = pygame.Rect(0, 0, active_width, active_height)

        # İşaretlenecek hücreler: aktif parçanın CANLI board'daki iniş ayak izi
        # (placements) veya statik yedek (cells/columns) — hepsi tek noktadan.
        cells = set()
        for cell in self._get_active_highlight_cells():
            try:
                gx, gy = int(cell[0]), int(cell[1])
            except Exception:
                continue
            if 0 <= gx < board_width and 0 <= gy < board_height:
                cells.add((gx, gy))

        if not cells:
            return

        def _cell_rect(gx, gy):
            return pygame.Rect(
                board_offset_x + gx * cell_size,
                board_offset_y + gy * cell_size,
                cell_size,
                cell_size,
            )

        # 1) Hücreleri yarı saydam kırmızı ile doldur (birleşik görünüm).
        fill_alpha = max(0, min(160, alpha // 2))
        for (gx, gy) in cells:
            r = _cell_rect(gx, gy).clip(canvas_rect)
            if r.width <= 0 or r.height <= 0:
                continue
            fill = pygame.Surface(r.size, pygame.SRCALPHA)
            fill.fill((*color, fill_alpha))
            self.screen.blit(fill, r.topleft)

        # 2) Yalnız dış kenarlara birleşik çerçeve çiz (komşu hücreyle paylaşılan
        #    kenarları atla) → parçanın tam şekline oturan tek outline.
        line_color = (*color, max(0, min(255, alpha)))
        for (gx, gy) in cells:
            rect = _cell_rect(gx, gy)
            # Üst kenar
            if (gx, gy - 1) not in cells:
                self._draw_highlight_edge(rect.topleft, rect.topright, line_color, border_w, canvas_rect)
            # Alt kenar
            if (gx, gy + 1) not in cells:
                self._draw_highlight_edge(rect.bottomleft, rect.bottomright, line_color, border_w, canvas_rect)
            # Sol kenar
            if (gx - 1, gy) not in cells:
                self._draw_highlight_edge(rect.topleft, rect.bottomleft, line_color, border_w, canvas_rect)
            # Sağ kenar
            if (gx + 1, gy) not in cells:
                self._draw_highlight_edge(rect.topright, rect.bottomright, line_color, border_w, canvas_rect)

    def _draw_highlight_edge(self, start, end, color, width, canvas_rect):
        """Highlight outline'ı için tek kenar segmenti çiz (canvas içinde)."""
        x1, y1 = start
        x2, y2 = end
        # Basit canvas-içi kontrol (segment dikey ya da yatay).
        if not (canvas_rect.left - 2 <= x1 <= canvas_rect.right + 2 and
                canvas_rect.left - 2 <= x2 <= canvas_rect.right + 2):
            return
        if not (canvas_rect.top - 2 <= y1 <= canvas_rect.bottom + 2 and
                canvas_rect.top - 2 <= y2 <= canvas_rect.bottom + 2):
            return
        try:
            pygame.draw.line(self.screen, color, (x1, y1), (x2, y2), width)
        except Exception:
            pass

    def _update_objective_completion_feedback(self):
        """Hedef ilk kez tamamlandığında mikro kutlama tetikle (çizim sol panelde).

        Sağ üstteki ayrı chip listesi kaldırıldı; hedefler sol HEDEFLER panelinde
        canlı renklenir. Burada yalnızca geçiş anında küçük kutlama veriyoruz.
        """
        states = self._get_live_objective_states()
        if not states:
            return
        chip_states = self._objective_chip_states if isinstance(self._objective_chip_states, dict) else {}
        for index, state in enumerate(states):
            passed = bool(state.get('passed'))
            obj_id = state.get('id') or index
            was_passed = bool(chip_states.get(obj_id, False))
            if passed and not was_passed:
                try:
                    self._create_mini_success_effect(str(state.get('text') or ''))
                except Exception:
                    pass
            chip_states[obj_id] = passed
        self._objective_chip_states = chip_states

    def _draw_hold_box_highlight(self):
        """Hold dersinde sağ paneldeki hold kutucuğunu vurgula (iniş efekti gibi).

        Sınav (exam) derslerinde gösterilmez; sınav 2 denemede tamamlanamazsa
        bunun yerine board iniş bandı highlight'ı devreye girer.
        """
        if not getattr(self, 'hold_highlight_active', False):
            return
        hold_rect = getattr(self, '_hud_hold_box_rect', None)
        if hold_rect is None:
            return
        # Hold zaten kullanıldıysa vurguyu durdur.
        if not getattr(self, 'can_hold', True) or getattr(self, 'held_piece', None) is not None:
            return

        try:
            cell_size = int(self.get_cell_size())
        except Exception:
            cell_size = 24
        pulse = abs(math.sin(getattr(self, 'hold_highlight_pulse', 0.0) * 4.0))
        alpha = int(120 + 120 * pulse)
        color = (255, 70, 70)
        border_w = max(2, cell_size // 9)

        glow_rect = hold_rect.inflate(border_w * 3, border_w * 3)
        glow = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow, (*color, max(0, min(255, alpha // 4))), glow.get_rect(), border_radius=10)
        self.screen.blit(glow, glow_rect.topleft)
        pygame.draw.rect(self.screen, (*color, max(0, min(255, alpha))), hold_rect, border_w, border_radius=8)

        # Hold kutusunun üstüne doğru küçük bir ok (parça buraya saklanacak).
        try:
            arrow_cx = hold_rect.centerx
            arrow_top = hold_rect.top - border_w * 2
            half = max(5, cell_size // 3)
            pygame.draw.polygon(
                self.screen, (*color, max(0, min(255, alpha))),
                [(arrow_cx - half, arrow_top - half),
                 (arrow_cx + half, arrow_top - half),
                 (arrow_cx, arrow_top)],
            )
        except Exception:
            pass

    def _draw_transition_callout(self, panel_rect, step_rect, ui_scale):
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        title_font = retro_style.get_font(
            max(s(18, minimum=12), int(s(24, minimum=16) * self.success_text_scale)),
            bold=True,
        )
        subtitle_font = retro_style.get_font(s(14, minimum=10), bold=True)

        max_text_width = panel_rect.width - s(54)
        title_lines = self._wrap_text(self.transition_text, title_font, max_text_width, max_lines=2)
        subtitle_lines = []
        if self.progress_celebration_text:
            subtitle_lines = self._wrap_text(
                self.progress_celebration_text,
                subtitle_font,
                max_text_width,
                max_lines=2,
            )

        title_line_height = title_font.get_height() + s(6)
        subtitle_line_height = subtitle_font.get_height() + s(4)
        block_height = s(18) + len(title_lines) * title_line_height + s(16)
        if subtitle_lines:
            block_height += s(8) + len(subtitle_lines) * subtitle_line_height

        content_top = step_rect.bottom + s(14)
        content_bottom = panel_rect.bottom - s(18)
        available_height = max(block_height, content_bottom - content_top)
        callout_rect = pygame.Rect(
            panel_rect.x + s(14),
            content_top + max(0, (available_height - block_height) // 2),
            panel_rect.width - s(28),
            block_height,
        )

        pulse = max(0.0, min(1.0, self.success_glow_timer))
        bubble = pygame.Surface((callout_rect.width, callout_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(bubble, (10, 28, 20, 184 + int(24 * pulse)), bubble.get_rect(), border_radius=s(14))
        pygame.draw.rect(
            bubble,
            (76, 208, 146, 214 + int(20 * pulse)),
            bubble.get_rect(),
            width=1,
            border_radius=s(14),
        )
        accent_rect = pygame.Rect(s(14), s(12), bubble.get_width() - s(28), max(3, s(4)))
        pygame.draw.rect(
            bubble,
            (110, 240, 170, 190),
            accent_rect,
            border_radius=max(2, accent_rect.height // 2),
        )
        self.screen.blit(bubble, callout_rect.topleft)

        shadow_offset = s(2)
        cursor_y = callout_rect.y + s(18)
        for line in title_lines:
            center_y = cursor_y + title_font.get_height() // 2
            shadow_surf = title_font.render(line, True, (5, 16, 11))
            shadow_surf.set_alpha(210)
            shadow_rect = shadow_surf.get_rect(
                center=(callout_rect.centerx + shadow_offset, center_y + shadow_offset)
            )
            self.screen.blit(shadow_surf, shadow_rect)

            line_surf = title_font.render(line, True, (124, 255, 150))
            line_rect = line_surf.get_rect(center=(callout_rect.centerx, center_y))
            self.screen.blit(line_surf, line_rect)
            cursor_y += title_line_height

        if subtitle_lines:
            cursor_y += s(2)
            for line in subtitle_lines:
                center_y = cursor_y + subtitle_font.get_height() // 2
                shadow_surf = subtitle_font.render(line, True, (8, 18, 30))
                shadow_surf.set_alpha(190)
                shadow_rect = shadow_surf.get_rect(
                    center=(callout_rect.centerx + shadow_offset, center_y + shadow_offset)
                )
                self.screen.blit(shadow_surf, shadow_rect)

                line_surf = subtitle_font.render(line, True, (172, 228, 255))
                line_rect = line_surf.get_rect(center=(callout_rect.centerx, center_y))
                self.screen.blit(line_surf, line_rect)
                cursor_y += subtitle_line_height
        
    def _draw_progression_panel(self):
        """FAZ 2/8 — Bölüm sonu ilerleme paneli (devam et / çıkıp oyna).

        İçerik yüksekliğe göre dinamik; yumuşak giriş animasyonu (pop + fade) ile
        açılır. Tüm boyutlar _tutorial_modal_scale + _sx ile oyunun ölçeğine bağlıdır.
        """
        data = self.progress_panel_data if isinstance(self.progress_panel_data, dict) else {}
        active_width, active_height = self._active_ui_size()
        ui_scale = self._tutorial_modal_scale(min_scale=0.72, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        # Giriş animasyonu ilerlet (0 → 1).
        anim = float(getattr(self, 'progress_panel_anim', 1.0) or 0.0)
        anim = min(1.0, anim + 0.12)
        self.progress_panel_anim = anim
        ease = 1.0 - (1.0 - anim) * (1.0 - anim)  # ease-out quad

        # Karartma animasyonla koyulaşır — board görünür kalsın ama panel öne çıksın.
        overlay = pygame.Surface((active_width, active_height), pygame.SRCALPHA)
        overlay.fill((5, 8, 18, int(185 * ease)))
        self.screen.blit(overlay, (0, 0))

        title_font = retro_style.get_font(s(26, minimum=17), bold=True)
        body_font = retro_style.get_font(s(16, minimum=11))

        panel_width = min(active_width - s(48), s(600))
        pad_x_inset = s(28)
        content_w = panel_width - pad_x_inset * 2

        title_text = str(data.get('title') or '')
        body_text = str(data.get('body') or '')
        body_lines = self._wrap_text(body_text, body_font, content_w, max_lines=5)

        btn_h = s(50, minimum=36)
        btn_gap = s(14)
        button_count = 2  # Devam Et + Çıkıp Oyna

        title_h = title_font.get_height()
        body_line_h = body_font.get_height() + s(4)
        pad_top = s(28)
        pad_bottom = s(24)
        section_gap = s(18)
        icon_band = s(40)  # üstte küçük kutlama ikonu/şeridi

        content_h = (
            pad_top
            + icon_band
            + title_h + section_gap
            + len(body_lines) * body_line_h
            + section_gap
            + button_count * btn_h + (button_count - 1) * btn_gap
            + pad_bottom
        )
        panel_h = int(content_h)
        panel_top = max(s(40), (active_height - panel_h) // 2)
        max_top = max(s(40), active_height - panel_h - s(20))
        panel_top = min(panel_top, max_top)

        # Pop animasyonu: panel hafif küçükten tam boya büyür.
        scale_anim = 0.92 + 0.08 * ease
        anim_w = int(panel_width * scale_anim)
        anim_h = int(panel_h * scale_anim)
        panel_rect = pygame.Rect(
            (active_width - anim_w) // 2,
            panel_top + (panel_h - anim_h) // 2,
            anim_w,
            anim_h,
        )
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=int(244 * ease),
                                     border_color=retro_style.success, glow=True)

        # İçeriği yalnız animasyon yeterince ilerleyince çiz (titremesin).
        if ease < 0.35:
            return

        cursor_y = panel_rect.y + pad_top

        # Üst kutlama ikonu (parlayan yıldız) — dikkat çekici.
        star_size = s(30, minimum=20)
        star_pulse = 0.85 + 0.15 * abs(math.sin(getattr(self, 'progress_celebration_timer', 0.0) * 3.0 + anim * 3.0))
        self._blit_tutorial_star_icon(
            panel_rect.centerx - int(star_size * star_pulse) // 2,
            cursor_y,
            int(star_size * star_pulse),
            filled=True,
        )
        cursor_y += icon_band

        # Başlık (ortalı, parlak).
        title_surf = title_font.render(title_text, True, (150, 245, 190))
        self.screen.blit(title_surf, title_surf.get_rect(centerx=panel_rect.centerx, top=cursor_y))
        cursor_y += title_h + section_gap

        # Gövde metni (ortalı satırlar).
        for line in body_lines:
            line_surf = body_font.render(line, True, (224, 232, 242))
            self.screen.blit(line_surf, line_surf.get_rect(centerx=panel_rect.centerx, top=cursor_y))
            cursor_y += body_line_h
        cursor_y += section_gap

        mouse_pos = get_mouse_pos()
        btn_w = min(s(330), content_w)
        btn_x = panel_rect.centerx - btn_w // 2

        # Devam Et.
        continue_rect = pygame.Rect(btn_x, cursor_y, btn_w, btn_h)
        self.progress_panel_continue_rect = continue_rect
        self._draw_briefing_action_button(
            continue_rect,
            t('tutorial_progress_panel_continue', default='Öğrenmeye Devam Et'),
            'ENTER',
            retro_style.success,
            continue_rect.collidepoint(mouse_pos),
            s,
        )
        cursor_y += btn_h + btn_gap

        # Çıkıp Oyna.
        play_rect = pygame.Rect(btn_x, cursor_y, btn_w, btn_h)
        self.progress_panel_play_rect = play_rect
        self._draw_briefing_action_button(
            play_rect,
            t('tutorial_progress_panel_play', default='Çıkıp Oyna'),
            'ESC',
            retro_style.secondary,
            play_rect.collidepoint(mouse_pos),
            s,
        )
        self.progress_panel_hub_rect = None

    def _draw_lesson_briefing(self):
        """FAZ C/6 — Ders öncesi briefing mikro-ekranı (oyun temel paneli stilinde).

        Yerleşim: ortalı ve büyük "DERS X/Y — Başlık" rozeti + tip/süre/zorluk +
        NASIL YAPILIR rehberi (ilk derslerde tuş yönergesi) + HEDEFLER + Neden +
        Dikkat + Başlat/Çıkış. Tüm rect'ler aktif canvas'a göre ölçeklenir.
        """
        data = self.briefing_data if isinstance(self.briefing_data, dict) else {}
        active_width, active_height = self._active_ui_size()
        ui_scale = self._tutorial_modal_scale(min_scale=0.72, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        # Tam ekran karartma
        overlay = pygame.Surface((active_width, active_height), pygame.SRCALPHA)
        overlay.fill((5, 8, 18, 210))
        self.screen.blit(overlay, (0, 0))

        panel_width = min(active_width - s(48), s(640))
        panel_height = min(active_height - s(40), s(520))
        panel_rect = pygame.Rect(
            (active_width - panel_width) // 2,
            (active_height - panel_height) // 2,
            panel_width,
            panel_height,
        )
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=238,
                                     border_color=retro_style.primary, glow=True)

        h1_font = retro_style.get_font(s(24, minimum=17), bold=True)
        counter_font = retro_style.get_font(s(22, minimum=15), bold=True)
        label_font = retro_style.get_font(s(24, minimum=18), bold=True)
        body_font = retro_style.get_font(s(17, minimum=13))
        tiny_font = retro_style.get_font(s(14, minimum=11))

        pad_x = panel_rect.x + s(24)
        content_w = panel_rect.width - s(48)

        # ── Ortalı, büyük "DERS X/Y — Başlık" rozeti ──
        lesson_index = int(data.get('lesson_index', 0) or 0)
        lesson_total = int(data.get('lesson_total', 0) or 0)
        title_text = str(data.get('title') or t('tutorial_briefing_goal', default='Hedef'))
        if lesson_index and lesson_total:
            counter_prefix = t('tutorial_lesson_counter', current=lesson_index, total=lesson_total,
                               default=f'DERS {lesson_index}/{lesson_total}')
            header_text = f'{counter_prefix} — {title_text}'
        else:
            header_text = title_text

        header_top = panel_rect.y + s(16)
        header_surf = retro_style.render_fit_text(
            header_text, (255, 255, 255), content_w - s(20), s(22, minimum=15), bold=True)
        header_bg = pygame.Rect(
            panel_rect.centerx - (header_surf.get_width() + s(28)) // 2,
            header_top,
            header_surf.get_width() + s(28),
            header_surf.get_height() + s(12),
        )
        hb = pygame.Surface(header_bg.size, pygame.SRCALPHA)
        hb.fill((18, 28, 48, 220))
        self.screen.blit(hb, header_bg.topleft)
        pygame.draw.rect(self.screen, (90, 160, 220), header_bg, 1, border_radius=8)
        self.screen.blit(header_surf, header_surf.get_rect(center=header_bg.center))
        # Başlık altı ayraç çizgisi.
        sep_y = header_bg.bottom + s(8)
        pygame.draw.line(self.screen, (*retro_style.primary[:3], 90),
                         (pad_x, sep_y), (panel_rect.right - s(24), sep_y))
        cursor_y = sep_y + s(14)

        bottom_limit = panel_rect.bottom - s(72)

        def _draw_block(label_key, label_default, label_color, text_value, cy, *, body_color=(224, 232, 242), max_lines=3):
            text_value = str(text_value or '').strip()
            if not text_value or cy >= bottom_limit:
                return cy
            label_surf = label_font.render(t(label_key, default=label_default), True, label_color)
            self.screen.blit(label_surf, label_surf.get_rect(centerx=panel_rect.centerx, top=cy))
            cy += label_surf.get_height() + s(4)
            for line in self._wrap_text(text_value, body_font, content_w, max_lines=max_lines):
                if cy + body_font.get_height() > bottom_limit:
                    break
                line_surf = body_font.render(line, True, body_color)
                self.screen.blit(line_surf, line_surf.get_rect(centerx=panel_rect.centerx, top=cy))
                cy += body_font.get_height() + s(3)
            return cy + s(10)

        # ── NASIL YAPILIR rehberi (ilk derslerde tuş yönergesi — vurgulu kutu) ──
        howto_text = str(data.get('how_to') or '').strip()
        if howto_text and cursor_y < bottom_limit:
            howto_font = retro_style.get_font(s(18, minimum=13), bold=False)
            howto_label_font = retro_style.get_font(s(17, minimum=13), bold=True)
            howto_lines = self._wrap_text(howto_text, howto_font, content_w - s(24), max_lines=3)
            label_h = howto_label_font.get_height()
            box_inner_pad = s(12)
            box_h = box_inner_pad * 2 + label_h + s(6) + len(howto_lines) * (howto_font.get_height() + s(3))
            box_rect = pygame.Rect(pad_x - s(6), cursor_y, content_w + s(12), int(box_h))
            # Dikkat çekici accent kutu (yeşil cam + sol kenar şeridi + hafif nabız).
            pulse = 0.5 + 0.5 * abs(math.sin(getattr(self, 'stuck_hint_pulse_timer', 0.0) * 2.2))
            box_bg = pygame.Surface(box_rect.size, pygame.SRCALPHA)
            box_bg.fill((24, 60, 44, 215))
            self.screen.blit(box_bg, box_rect.topleft)
            border_col = (int(90 + 70 * pulse), int(220 + 30 * pulse), int(150 + 50 * pulse))
            pygame.draw.rect(self.screen, border_col, box_rect, max(1, s(2)), border_radius=s(8))
            # Sol accent şeridi.
            pygame.draw.rect(self.screen, (120, 245, 175),
                             pygame.Rect(box_rect.x, box_rect.y, s(4), box_rect.height),
                             border_radius=s(2))
            inner_x = box_rect.x + box_inner_pad + s(4)
            iy = box_rect.y + box_inner_pad
            # Başlık + küçük ok ikonu hissi.
            label_surf = howto_label_font.render(
                '▶ ' + t('tutorial_briefing_howto', default='NASIL YAPILIR'), True, (150, 255, 195))
            self.screen.blit(label_surf, (inner_x, iy))
            iy += label_h + s(6)
            for line in howto_lines:
                self._blit_line_with_key_highlights(
                    line, howto_font, inner_x, iy,
                    base_color=(236, 248, 240),
                    key_color=(255, 214, 130),
                    key_bg=(70, 55, 20, 180),
                )
                iy += howto_font.get_height() + s(3)
            cursor_y = box_rect.bottom + s(12)

        # ── HEDEFLER paneli ──
        objectives = list(data.get('objectives') or [])
        if objectives and cursor_y < bottom_limit:
            obj_label = label_font.render(t('tutorial_targets_title', default='HEDEFLER'), True, (110, 240, 170))
            self.screen.blit(obj_label, obj_label.get_rect(centerx=panel_rect.centerx, top=cursor_y))
            cursor_y += obj_label.get_height() + s(6)
            for objective in objectives[:4]:
                lines = self._wrap_text(objective, body_font, content_w, max_lines=2)
                for line in lines:
                    if cursor_y + body_font.get_height() > bottom_limit:
                        break
                    line_surf = body_font.render(line, True, (224, 232, 240))
                    self.screen.blit(line_surf, line_surf.get_rect(centerx=panel_rect.centerx, top=cursor_y))
                    cursor_y += body_font.get_height() + s(2)
                cursor_y += s(4)
            cursor_y += s(8)

        # Not (2026-06-20): Pedagojik "Neden" bloğu briefing'den kaldırıldı — oyuncunun
        # ders başına okuma yükünü azaltmak için (geri bildirim: "3 parçaya bölünmüş yapı
        # uyku getiriyor"). Bağlam kaybolmaz: "why_it_matters" hub ders kartında korunur.
        # Briefing artık yalnız eyleme dönük blokları gösterir: HEDEFLER + Dikkat.
        cursor_y = _draw_block('tutorial_briefing_watch', 'Dikkat et', (160, 190, 250), data.get('watch'), cursor_y, max_lines=2)

        # ── Başlat / Çıkış butonları ──
        button_h = s(44)
        button_y = panel_rect.bottom - button_h - s(18)
        spacing = s(14)
        btn_w = min(s(210), (content_w - spacing) // 2)
        total_w = btn_w * 2 + spacing
        start_x = panel_rect.centerx - total_w // 2
        start_rect = pygame.Rect(start_x, button_y, btn_w, button_h)
        skip_rect = pygame.Rect(start_x + btn_w + spacing, button_y, btn_w, button_h)
        self.briefing_start_rect = start_rect
        self.briefing_skip_rect = skip_rect

        mouse_pos = get_mouse_pos()
        self._draw_briefing_action_button(
            start_rect,
            t('tutorial_briefing_start', default='Başlat'),
            'ENTER',
            retro_style.success,
            start_rect.collidepoint(mouse_pos),
            s,
        )
        # 'Atla' yerine artık 'Çıkış' — eğitimden ana menüye döner.
        self._draw_briefing_action_button(
            skip_rect,
            t('tutorial_briefing_exit', default='Çıkış'),
            'ESC',
            retro_style.secondary,
            skip_rect.collidepoint(mouse_pos),
            s,
        )

    def _draw_briefing_action_button(self, rect, label, sub_label, color, hover, s):
        """Briefing Başlat/Atla butonu — çıkış onay panelindeki buton stilinde.

        Ortalanmış başlık + hemen altında küçük ENTER/ESC alt-etiketi.
        """
        draw_rect = rect.inflate(s(6), s(4)) if hover else rect

        btn_bg = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
        if hover:
            pygame.draw.rect(btn_bg, (*color[:3], 35), btn_bg.get_rect(), border_radius=12)
            hl_rect = pygame.Rect(s(4), s(2), draw_rect.width - s(8), max(1, s(1)))
            pygame.draw.rect(btn_bg, (*color[:3], 60), hl_rect)
        else:
            pygame.draw.rect(btn_bg, (20, 26, 42, 200), btn_bg.get_rect(), border_radius=12)
        self.screen.blit(btn_bg, draw_rect.topleft)

        border_w = 3 if hover else 1
        border_a = 220 if hover else 100
        pygame.draw.rect(self.screen, (*color[:3], border_a), draw_rect, border_w, border_radius=12)

        txt_color = (255, 255, 255) if hover else (220, 230, 245)
        label_font = self._get_fitting_font(label, s(20, minimum=14), draw_rect.width - s(28), bold=True)
        label_surf = label_font.render(label, True, txt_color)
        sub_font = retro_style.get_font(s(13, minimum=10), bold=False)
        sub_color = color[:3] if hover else (140, 155, 180)
        sub_surf = sub_font.render(sub_label, True, sub_color)

        gap = s(3)
        total_h = label_surf.get_height() + gap + sub_surf.get_height()
        ty = draw_rect.centery - total_h // 2
        self.screen.blit(label_surf, label_surf.get_rect(midtop=(draw_rect.centerx, ty)))
        self.screen.blit(sub_surf, sub_surf.get_rect(midtop=(draw_rect.centerx, ty + label_surf.get_height() + gap)))

    def _draw_tutorial_overlay(self):
        ui_scale = self._tutorial_modal_scale(min_scale=0.70, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        rect = self._tutorial_overlay_rect()
        retro_style.draw_glass_panel(self.screen, rect, alpha=220, border_color=(0, 200, 255))
        content_pad_x, content_pad_y = self._panel_content_padding(rect, s, pad_x=16, pad_y=12, x_ratio=0.08, y_ratio=0.05)
        content_width = max(s(60), rect.width - content_pad_x * 2)
        section_gap = max(s(8), int(rect.height * 0.03))
        
        # Step Counter (üst kısım) - daha büyük font
        lesson_total = max(1, len(self.lesson_catalog))
        lesson_index = self._lesson_index()
        step_text = t('tutorial_lesson_counter', current=lesson_index, total=lesson_total, default=f'DERS {lesson_index}/{lesson_total}')
        if self.lesson_result_active and not self.next_lesson_id:
            step_text = t('tutorial_last_lesson', default='SON DERS')
        badge_pad_x = max(s(8), int(rect.width * 0.03))
        badge_pad_y = max(s(4), int(rect.height * 0.02))
        badge_radius = max(4, s(6))
        step_font = self._get_fitting_font(
            step_text,
            s(18, minimum=12),
            content_width - badge_pad_x * 2,
            bold=True,
            min_size=max(10, s(11, minimum=10)),
        )
        step_surf = step_font.render(step_text, True, (150, 220, 255))
        
        step_bg_rect = pygame.Rect(
            rect.right - content_pad_x - (step_surf.get_width() + badge_pad_x * 2),
            rect.top + content_pad_y,
            step_surf.get_width() + badge_pad_x * 2,
            step_surf.get_height() + badge_pad_y * 2,
        )
        pygame.draw.rect(self.screen, (20, 30, 50, 180), step_bg_rect, border_radius=badge_radius)
        pygame.draw.rect(self.screen, (100, 150, 200), step_bg_rect, 1, border_radius=badge_radius)
        step_rect_pos = step_surf.get_rect(center=step_bg_rect.center)
        self.screen.blit(step_surf, step_rect_pos)

        footer_bottom = rect.bottom - content_pad_y
        show_progress_bar = not self.in_transition and self.sub_message and self.step in [1, 2, 3]
        bar_h = max(s(6), int(rect.height * 0.025))
        progress_gap = section_gap if show_progress_bar else 0
        progress_rect = None

        if show_progress_bar:
            progress_rect = pygame.Rect(
                rect.centerx - content_width // 2,
                footer_bottom - bar_h,
                content_width,
                bar_h,
            )
            footer_bottom = progress_rect.top - progress_gap

        sub_font = None
        sub_lines = []
        sub_line_gap = 0
        sub_total_height = 0
        sub_top = footer_bottom

        if not self.in_transition and self.sub_message:
            sub_font, sub_lines, sub_line_gap, sub_total_height = self._fit_wrapped_text_block(
                self.sub_message,
                base_size=s(16, minimum=11),
                max_width=content_width,
                max_height=max(s(28), int(rect.height * 0.28)),
                bold=False,
                min_size=max(10, s(11, minimum=10)),
                max_lines=3,
            )
            sub_top = footer_bottom - sub_total_height

        body_top = step_bg_rect.bottom + section_gap
        body_bottom = sub_top - section_gap if sub_lines else footer_bottom - (section_gap if progress_rect else 0)
        body_height = max(step_font.get_height(), body_bottom - body_top)
        
        # Mesaj (orta kısım) - daha büyük fontlar
        # NOT: Geçiş (transition) sırasında soldaki yeşil "tamamlandı" kutusu
        # ARTIK ÇİZİLMİYOR — başarı geri bildirimi board ortasındaki sarı/altın
        # kutlama paneliyle (_draw_progress_celebration) veriliyor (tüm derslerde
        # tutarlı). Geçişte sol panelde yalnız ders başlığı sabit kalır.
        if True:
            text = self.overlay_message
            color = (140, 230, 255)

            font, visible_lines, line_gap, total_h = self._fit_wrapped_text_block(
                text,
                base_size=s(26, minimum=15),
                max_width=content_width,
                max_height=body_height,
                bold=True,
                min_size=max(12, s(14, minimum=12)),
                max_lines=4,
            )
            line_height = font.get_height() + line_gap
            start_y = body_top + max(0, (body_height - total_h) // 2)
            for i, line in enumerate(visible_lines):
                # Hafif gölge + parlak ana metin: ders başlığı belirgin görünsün.
                shadow_surf = font.render(line, True, (8, 16, 28))
                main_surf = font.render(line, True, color)
                cx = rect.centerx
                cy = start_y + i * line_height + font.get_height() // 2
                shadow_rect = shadow_surf.get_rect(center=(cx + max(1, s(1, minimum=1)), cy + max(1, s(1, minimum=1))))
                self.screen.blit(shadow_surf, shadow_rect)
                self.screen.blit(main_surf, main_surf.get_rect(center=(cx, cy)))
        
        # Sub-message ve ilerleme çubuğu (alt kısım) - daha büyük font
        if not self.in_transition and sub_lines:
            draw_y = sub_top
            for i, line in enumerate(sub_lines):
                sub_surf = sub_font.render(line, True, (180, 180, 180))
                sub_rect = sub_surf.get_rect(center=(rect.centerx, draw_y + sub_font.get_height() // 2))
                self.screen.blit(sub_surf, sub_rect)
                draw_y += sub_font.get_height() + sub_line_gap
            
            # İlerleme çubuğu (adım 1, 2, 3 için)
            if progress_rect is not None:
                progress = 0
                if self.step == 1:
                    progress = (self.step_move_left_count + self.step_move_right_count) / 6.0
                elif self.step == 2:
                    progress = self.step_rotate_count / 3.0
                elif self.step == 3:
                    progress = min(self.soft_drop_counter / self.step_target, 1.0)

                # Arka plan
                pygame.draw.rect(self.screen, (50, 50, 50), progress_rect, border_radius=max(3, bar_h // 2))
                
                # İlerleme
                if progress > 0:
                    progress_w = int(progress_rect.width * progress)
                    progress_color = (50, 255, 50) if progress >= 1.0 else (100, 200, 255)
                    pygame.draw.rect(
                        self.screen,
                        progress_color,
                        (progress_rect.x, progress_rect.y, progress_w, progress_rect.height),
                        border_radius=max(3, bar_h // 2),
                    )

        if not self.in_transition and self.tip_message:
            # İstek üzerine: oyun alanındaki sol ipucu/hedefler blokları kaldırıldı.
            # Tuş rehberi artık yalnız başlat/çıkış (briefing) panelinde gösteriliyor.
            pass

    def _draw_tutorial_tip_panel(self, main_rect: pygame.Rect):
        """Ana eğitim panelinin altında kısa tavsiye panelini çizer.

        TODO(Tutorial Companion):
        - Bu panelin soluna mentor karakter portresi ekle.
        - Tavsiyeyi karakterin konuşma balonunda göster.
        - Karakter ifadesini adıma göre değiştir (örn. Move, Rotate, Hold).
        """
        _, active_height = self._active_ui_size()
        ui_scale = self._tutorial_modal_scale(min_scale=0.70, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        support_layout = self._build_tutorial_support_layout(main_rect, ui_scale)
        objectives = support_layout['objectives']
        has_objectives = support_layout['has_objectives']
        tip_width = support_layout['tip_width']
        tip_gap = support_layout['tip_gap']
        panel_pad_x = support_layout['panel_pad_x']
        panel_pad_y = support_layout['panel_pad_y']
        title_gap = support_layout['title_gap']
        tip_title_font = support_layout['tip_title_font']
        text_font = support_layout['text_font']
        lines = support_layout['lines']
        text_line_gap = support_layout['text_line_gap']
        tip_height = support_layout['tip_height']
        obj_height = support_layout['obj_height']
        objective_blocks = support_layout['objective_blocks']
        obj_title_font = support_layout['obj_title_font']
        objective_title_gap = support_layout['objective_title_gap']
        objective_item_gap = support_layout['objective_item_gap']
        objective_text_x = support_layout['objective_text_x']
        bullet_radius = support_layout['bullet_radius']
        stack_height = support_layout['stack_height']
        place_below = main_rect.bottom + tip_gap + stack_height <= active_height - s(10)

        # ── Hedef paneli (varsa) ──
        if has_objectives:
            if place_below:
                obj_y = main_rect.bottom + tip_gap
                tip_y = obj_y + obj_height + tip_gap
            else:
                group_top = max(s(10), main_rect.y - tip_gap - stack_height)
                tip_y = group_top
                obj_y = tip_y + tip_height + tip_gap

            obj_rect = pygame.Rect(main_rect.x, obj_y, tip_width, obj_height)
            retro_style.draw_glass_panel(self.screen, obj_rect, alpha=220, border_color=(80, 220, 140))

            obj_title_surf = obj_title_font.render(t('tutorial_targets_title', default='HEDEFLER'), True, (110, 240, 170))
            self.screen.blit(obj_title_surf, obj_title_surf.get_rect(midtop=(obj_rect.centerx, obj_rect.y + panel_pad_y)))

            # Canlı hedef durumları (tamamlanan hedef yeşil + onay işareti).
            try:
                live_states = self._get_live_objective_states()
            except Exception:
                live_states = []
            passed_flags = [bool(st.get('passed')) for st in live_states]

            objective_y = obj_rect.y + panel_pad_y + obj_title_font.get_height() + objective_title_gap
            bullet_x = obj_rect.x + panel_pad_x + bullet_radius
            text_x = obj_rect.x + objective_text_x
            for block_index, block in enumerate(objective_blocks):
                if not block['lines']:
                    continue
                is_passed = passed_flags[block_index] if block_index < len(passed_flags) else False
                bullet_color = (110, 240, 170) if is_passed else (120, 140, 165)
                text_color = (150, 240, 190) if is_passed else (225, 232, 240)
                center_y = objective_y + block['font'].get_height() // 2
                pygame.draw.circle(self.screen, bullet_color, (bullet_x, center_y), bullet_radius)
                if is_passed:
                    # Onay işareti (tamamlandı).
                    chk = max(2, bullet_radius)
                    pygame.draw.lines(
                        self.screen, (12, 26, 18), False,
                        [(bullet_x - chk, center_y),
                         (bullet_x - chk // 2, center_y + chk),
                         (bullet_x + chk, center_y - chk)],
                        max(1, bullet_radius // 2),
                    )
                line_y = objective_y
                for line in block['lines']:
                    objective_surf = block['font'].render(line, True, text_color)
                    self.screen.blit(objective_surf, (text_x, line_y))
                    line_y += block['font'].get_height() + block['line_gap']
                objective_y += block['height'] + objective_item_gap
        else:
            tip_y = main_rect.bottom + tip_gap if place_below else max(s(10), main_rect.y - tip_gap - tip_height)

        # ── İpucu paneli (her zaman) ──
        tip_rect = pygame.Rect(main_rect.x, tip_y, tip_width, tip_height)
        retro_style.draw_glass_panel(self.screen, tip_rect, alpha=200, border_color=(100, 160, 220))

        tip_label_surf = tip_title_font.render(t('tutorial_tip_title', default='İPUCU'), True, (140, 190, 240))
        self.screen.blit(tip_label_surf, tip_label_surf.get_rect(midtop=(tip_rect.centerx, tip_rect.y + panel_pad_y)))

        text_color = (215, 225, 238)
        content_start_y = tip_rect.y + panel_pad_y + tip_title_font.get_height() + title_gap
        for i, line in enumerate(lines):
            line_surf = text_font.render(line, True, text_color)
            line_rect = line_surf.get_rect(center=(tip_rect.centerx, content_start_y + i * (text_font.get_height() + text_line_gap) + text_font.get_height() // 2))
            self.screen.blit(line_surf, line_rect)
            
    def _draw_mini_success_effects(self):
        """Mini başarı 'başardın' banner'larını çiz — ✓ ikonlu, glow'lu, ölçekli.

        Banner'lar dörtgen oyun alanı (board) içinde kalır, yatayda board'a göre
        ortalanır ve dikeyde üst üste binmeyecek şekilde istiflenir. Metin board
        genişliğine sığacak şekilde küçültülür.
        """
        if not self.step_completion_effects:
            return
        ui_scale = self._tutorial_modal_scale(min_scale=0.70, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        active_width, active_height = self._active_ui_size()

        # Board sınırlarını al — banner board içinde kalsın, taşmasın.
        try:
            board_x, board_y = self.get_board_offset()
            cell_size = max(1, int(self.get_cell_size()))
            board_w = int(self.board_width) * cell_size
            board_h = int(self.board_height) * cell_size
        except Exception:
            board_x, board_y = 0, 0
            board_w, board_h = active_width, active_height
        board_center_x = board_x + board_w // 2
        max_banner_w = max(s(120), board_w - s(24))

        pad_x = s(18)
        pad_y = s(9)
        gap = s(9)
        # En yeni banner en üstte; her biri altına istiflenir (üst üste binmez).
        base_top = board_y + max(s(12), int(board_h * 0.16))
        stack_step = 0
        for i, effect in enumerate(self.step_completion_effects):
            alpha = max(0, min(255, int(effect.get('alpha', 255))))
            if alpha <= 0:
                continue
            message = str(effect.get('message', ''))
            if not message:
                continue
            y_offset = float(effect.get('y_offset', 0))
            scale = max(0.5, float(effect.get('scale', 1.0)))

            # Metni board'a sığacak şekilde küçült.
            font_size = s(19, minimum=12)
            base_font = retro_style.get_font(font_size, bold=True)
            check_w = base_font.size('✓ ')[0]
            while font_size > s(11, minimum=9) and base_font.size(message)[0] + check_w + pad_x * 2 + gap > max_banner_w:
                font_size -= 1
                base_font = retro_style.get_font(font_size, bold=True)

            text_surf = base_font.render(message, True, (235, 255, 240))
            check_surf = base_font.render('✓', True, (120, 255, 160))
            content_w = check_surf.get_width() + gap + text_surf.get_width()
            banner_w = min(max_banner_w, content_w + pad_x * 2)
            banner_h = max(text_surf.get_height(), check_surf.get_height()) + pad_y * 2

            banner = pygame.Surface((int(banner_w), int(banner_h)), pygame.SRCALPHA)
            # Glow + cam zemin + yeşil kenar + sol accent şeridi.
            pygame.draw.rect(banner, (14, 38, 26, 235), banner.get_rect(), border_radius=s(10))
            pygame.draw.rect(banner, (90, 235, 150, 235), banner.get_rect(), max(2, s(2)), border_radius=s(10))
            pygame.draw.rect(banner, (120, 255, 170), pygame.Rect(0, 0, max(2, s(3)), int(banner_h)),
                             border_radius=s(2))
            inner_x = pad_x
            banner.blit(check_surf, (inner_x, (banner_h - check_surf.get_height()) // 2))
            banner.blit(text_surf, (inner_x + check_surf.get_width() + gap,
                                    (banner_h - text_surf.get_height()) // 2))

            if abs(scale - 1.0) > 0.01:
                sw = max(1, int(banner_w * scale))
                sh = max(1, int(banner_h * scale))
                banner = pygame.transform.smoothscale(banner, (sw, sh))
            banner.set_alpha(alpha)
            pos_x = board_center_x - banner.get_width() // 2
            pos_y = int(base_top + stack_step + y_offset)
            # Board alt sınırını taşma.
            pos_y = min(pos_y, board_y + board_h - banner.get_height() - s(6))
            self.screen.blit(banner, (pos_x, pos_y))
            stack_step += banner_h + gap

    def _draw_inline_howto_hint(self):
        """İlk derslerde (1-4) board'un üst-orta kısmında 'hangi tuşa bas' rehber paneli.

        İçerik briefing'deki "NASIL YAPILIR" kutusuyla aynı (tuş etiketleri renkli).
        Derste kullanılan herhangi bir tuşa basılınca (_register_step_activity)
        otomatik kaybolur.
        """
        if not getattr(self, 'inline_howto_active', False):
            return
        text = str(getattr(self, 'inline_howto_text', '') or '').strip()
        if not text:
            return
        ui_scale = self._tutorial_modal_scale(min_scale=0.70, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        active_width, active_height = self._active_ui_size()

        try:
            board_x, board_y = self.get_board_offset()
            cell_size = max(1, int(self.get_cell_size()))
            board_w = int(self.board_width) * cell_size
            board_h = int(self.board_height) * cell_size
        except Exception:
            board_x, board_y = 0, 0
            board_w, board_h = active_width, active_height

        # 2026-06-20: Kutu %10 büyütüldü (gs = s × 1.10) ve üstteki "sıradaki ders" yeşil
        # banner'ı (board_h*0.16 + yükseklik) ile çakışmaması için biraz aşağı alındı.
        # gs ölçek-uyumlu: değer önce ×1.10, sonra oyunun _sx() UI ölçeğinden geçer
        # (sabit piksel kaçağı yok; tüm diğer panellerle aynı ölçekleme sistemi).
        GROW = 1.10
        gs = lambda v, minimum=1: self._sx(v * GROW, ui_scale, max(1, int(round(minimum * GROW))))

        panel_w = min(board_w - s(20), gs(360))
        inner_pad = gs(14)
        content_w = panel_w - inner_pad * 2

        label_font = retro_style.get_font(gs(15, minimum=11), bold=True)
        body_font = retro_style.get_font(gs(15, minimum=11), bold=False)
        lines = self._wrap_text(text, body_font, content_w - gs(8), max_lines=3)
        label_h = label_font.get_height()
        body_line_h = body_font.get_height() + gs(3)
        panel_h = inner_pad * 2 + label_h + gs(6) + len(lines) * body_line_h

        # Board üst-orta; banner ile çakışmasın diye 0.20 → 0.28 board yüksekliğine indirildi.
        panel_x = board_x + (board_w - panel_w) // 2
        panel_y = board_y + max(s(56), int(board_h * 0.28))
        # Büyütülen kutu board alt sınırını taşmasın.
        panel_y = min(panel_y, board_y + board_h - panel_h - s(10))
        panel_rect = pygame.Rect(int(panel_x), int(panel_y), int(panel_w), int(panel_h))

        # Nabız atan yeşil accent kutu (briefing how-to kutusuyla aynı dil).
        self.inline_howto_pulse = float(getattr(self, 'inline_howto_pulse', 0.0)) + 0.05
        pulse = 0.5 + 0.5 * abs(math.sin(self.inline_howto_pulse * 2.2))
        box_bg = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        box_bg.fill((20, 54, 40, 232))
        self.screen.blit(box_bg, panel_rect.topleft)
        border_col = (int(90 + 70 * pulse), int(220 + 30 * pulse), int(150 + 50 * pulse))
        pygame.draw.rect(self.screen, border_col, panel_rect, max(1, gs(2)), border_radius=gs(8))
        pygame.draw.rect(self.screen, (120, 245, 175),
                         pygame.Rect(panel_rect.x, panel_rect.y, gs(4), panel_rect.height),
                         border_radius=gs(2))

        inner_x = panel_rect.x + inner_pad + gs(4)
        iy = panel_rect.y + inner_pad
        label_surf = label_font.render(
            '▶ ' + t('tutorial_briefing_howto', default='NASIL YAPILIR'), True, (150, 255, 195))
        self.screen.blit(label_surf, (inner_x, iy))
        iy += label_h + gs(6)
        for line in lines:
            self._blit_line_with_key_highlights(
                line, body_font, inner_x, iy,
                base_color=(236, 248, 240),
                key_color=(255, 214, 130),
                key_bg=(70, 55, 20, 180),
            )
            iy += body_line_h

    def _draw_progress_celebration(self):
        """İlerleme kutlamasını çiz — belirgin, parlak, board içinde ortalı banner."""
        if self.progress_celebration_timer <= 0 or not self.progress_celebration_text:
            return
        ui_scale = self._tutorial_modal_scale(min_scale=0.70, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        active_width, active_height = self._active_ui_size()

        # Board sınırları — banner board içinde kalsın.
        try:
            board_x, board_y = self.get_board_offset()
            cell_size = max(1, int(self.get_cell_size()))
            board_w = int(self.board_width) * cell_size
            board_h = int(self.board_height) * cell_size
        except Exception:
            board_x, board_y = 0, 0
            board_w, board_h = active_width, active_height
        center_x = board_x + board_w // 2

        # Zaman bazlı alpha + pop ölçeği (son 0.5 sn'de solar).
        t_left = float(self.progress_celebration_timer)
        alpha = max(0, min(255, int(255 * min(1.0, t_left / 0.5))))
        appear = min(1.0, (2.0 - t_left) / 0.25) if t_left > 0 else 1.0
        ease = max(0.0, min(1.0, appear))
        scale = 0.6 + 0.4 * ease
        pulse = 0.5 + 0.5 * abs(math.sin(t_left * 5.0))

        max_w = max(s(180), board_w - s(28))
        font_size = s(30, minimum=18)
        font = retro_style.get_font(font_size, bold=True)
        while font_size > s(15, minimum=12) and font.size(self.progress_celebration_text)[0] + s(72) > max_w:
            font_size -= 1
            font = retro_style.get_font(font_size, bold=True)
        # Sıcak altın/sarı tonları — kutlama/başarı hissi.
        text_surf = font.render(self.progress_celebration_text, True, (255, 244, 200))

        # Üstte parlayan yıldız ikonu — dikkat çekici kutlama.
        star_size = max(s(18, minimum=12), int(font.get_height() * 0.9))
        star_gap = s(8)

        pad_x = s(26)
        pad_y = s(16)
        content_w = text_surf.get_width()
        banner_w = min(max_w, content_w + pad_x * 2)
        banner_h = text_surf.get_height() + star_size + star_gap + pad_y * 2
        banner = pygame.Surface((int(banner_w), int(banner_h)), pygame.SRCALPHA)

        # Dış glow (altın hale).
        glow_alpha = int(70 + 60 * pulse)
        pygame.draw.rect(banner, (255, 200, 70, glow_alpha), banner.get_rect(), border_radius=s(16))
        # İç koyu zemin (kontrast için sıcak koyu kahve/lacivert karışımı).
        inner = banner.get_rect().inflate(-s(5), -s(5))
        pygame.draw.rect(banner, (40, 30, 12, 240), inner, border_radius=s(13))
        # Altın kenarlık (nabız atan).
        border_col = (int(255), int(210 + 30 * pulse), int(90 + 60 * pulse))
        pygame.draw.rect(banner, border_col, banner.get_rect(), max(2, s(3)), border_radius=s(16))

        # Yıldız ikonu (üstte, ortalı).
        star_x = (banner_w - star_size) // 2
        star_y = pad_y - s(2)
        prev_screen = self.screen
        try:
            # _blit_tutorial_star_icon doğrudan self.screen'e çizer; geçici olarak
            # banner yüzeyine yönlendir.
            self.screen = banner
            self._blit_tutorial_star_icon(int(star_x), int(star_y), int(star_size), filled=True)
        except Exception:
            pass
        finally:
            self.screen = prev_screen

        # Metni yıldızın altına ortala.
        banner.blit(text_surf, text_surf.get_rect(center=(banner_w // 2, star_y + star_size + star_gap + text_surf.get_height() // 2)))

        if abs(scale - 1.0) > 0.01:
            banner = pygame.transform.smoothscale(
                banner, (max(1, int(banner_w * scale)), max(1, int(banner_h * scale))))
        banner.set_alpha(alpha)
        # Oyun alanının ORTASINA yerleştir (kullanıcı isteği).
        pos_x = center_x - banner.get_width() // 2
        pos_y = board_y + (board_h - banner.get_height()) // 2
        self.screen.blit(banner, (pos_x, pos_y))

    def _draw_tutorial_hub(self):
        active_width, active_height = self._active_ui_size()
        ui_scale = self._tutorial_modal_scale(min_scale=0.72, max_scale=1.12)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        # ── Tam ekran koyu overlay ──
        overlay = pygame.Surface((active_width, active_height), pygame.SRCALPHA)
        overlay.fill((5, 5, 15, 200))
        self.screen.blit(overlay, (0, 0))

        panel_rect = self._tutorial_hub_panel_rect()
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=210, border_color=retro_style.primary, glow=True)

        # ── Fontlar ──
        h1_font = retro_style.get_font(s(30, minimum=20), bold=True)
        h2_font = retro_style.get_font(s(22, minimum=15), bold=True)
        h3_font = retro_style.get_font(s(19, minimum=14), bold=True)
        body_font = retro_style.get_font(s(17, minimum=13))
        small_font = retro_style.get_font(s(15, minimum=11))
        tiny_font = retro_style.get_font(s(13, minimum=10))

        mouse_pos = get_mouse_pos()

        # ── Başlık bandı ──
        header_h = s(72)
        header_rect = pygame.Rect(panel_rect.x, panel_rect.y, panel_rect.width, header_h)
        header_bg = pygame.Surface(header_rect.size, pygame.SRCALPHA)
        header_bg.fill((8, 12, 30, 210))
        self.screen.blit(header_bg, header_rect.topleft)
        pygame.draw.line(self.screen, (*retro_style.primary[:3], 110),
                         (header_rect.x + s(20), header_rect.bottom - 1),
                         (header_rect.right - s(20), header_rect.bottom - 1))

        title_text = t('tutorial_hub_title', default='Eğitim Merkezi')
        title_surf = h1_font.render(title_text, True, retro_style.primary)
        self.screen.blit(title_surf, (header_rect.x + s(28), header_rect.y + (header_rect.height - title_surf.get_height()) // 2))

        total_stars = self._get_total_tutorial_stars()
        star_badge_font = retro_style.get_font(s(16, minimum=12), bold=True)
        star_value_surf = star_badge_font.render(str(total_stars), True, (255, 215, 0))
        badge_star_size = max(
            s(16, minimum=11),
            min(s(24), star_value_surf.get_height() + s(2, minimum=1)),
        )
        badge_star_gap = s(6, minimum=3)
        star_badge_w = star_value_surf.get_width() + badge_star_size + badge_star_gap + s(20)
        star_badge_h = max(star_value_surf.get_height(), badge_star_size) + s(8)
        star_badge_rect = pygame.Rect(header_rect.right - star_badge_w - s(28),
                                      header_rect.y + s(14), star_badge_w, star_badge_h)
        star_bg = pygame.Surface(star_badge_rect.size, pygame.SRCALPHA)
        star_bg.fill((12, 20, 45, 210))
        self.screen.blit(star_bg, star_badge_rect.topleft)
        pygame.draw.rect(self.screen, (255, 215, 0, 130), star_badge_rect, 1, border_radius=8)
        badge_star_x = star_badge_rect.x + s(10)
        badge_star_y = star_badge_rect.centery - badge_star_size // 2
        self._blit_tutorial_star_icon(badge_star_x, badge_star_y, badge_star_size, filled=True)
        self.screen.blit(
            star_value_surf,
            (
                badge_star_x + badge_star_size + badge_star_gap,
                star_badge_rect.centery - star_value_surf.get_height() // 2,
            ),
        )

        content_top = header_rect.bottom + s(14)
        content_bottom = panel_rect.bottom - s(90)
        content_height = content_bottom - content_top

        # ══════════════════════════════════════════════════════
        # SOL PANEL — Bölüm carousel
        # ══════════════════════════════════════════════════════
        chapter_area_w = s(350)
        chapter_area_rect = pygame.Rect(panel_rect.x + s(20), content_top,
                                        chapter_area_w, content_height)

        chapter_entries = self._get_hub_chapter_entries()
        chapter_count = len(chapter_entries)
        current_chapter_index = 0
        for ci, entry in enumerate(chapter_entries):
            if entry['chapter'].get('id') == self.hub_selected_chapter_id:
                current_chapter_index = ci
                break

        # ── Ok butonları (glass button stili) ──
        arrow_w = s(40, minimum=30)
        arrow_h = s(56, minimum=42)
        arrow_y = chapter_area_rect.y + (chapter_area_rect.height - arrow_h) // 2
        arrow_left_rect = pygame.Rect(chapter_area_rect.x - s(10), arrow_y, arrow_w, arrow_h)
        arrow_right_rect = pygame.Rect(chapter_area_rect.right - arrow_w + s(10), arrow_y, arrow_w, arrow_h)
        self.hub_arrow_left_rect = arrow_left_rect
        self.hub_arrow_right_rect = arrow_right_rect

        for arrow_rect, direction in [(arrow_left_rect, 'left'), (arrow_right_rect, 'right')]:
            hover = arrow_rect.collidepoint(mouse_pos)
            outer_radius = max(10, min(arrow_rect.width, arrow_rect.height) // 2)
            # Glow
            if hover:
                glow_r = arrow_rect.inflate(s(10, minimum=6), s(10, minimum=6))
                glow_s = pygame.Surface(glow_r.size, pygame.SRCALPHA)
                pygame.draw.rect(glow_s, (*retro_style.primary[:3], 44), glow_s.get_rect(), border_radius=outer_radius + 4)
                self.screen.blit(glow_s, glow_r.topleft)

            # Outer capsule
            btn_alpha = 208 if hover else 170
            fill_c = (24, 32, 52) if hover else (14, 22, 38)
            btn_s = pygame.Surface(arrow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(btn_s, (*fill_c, btn_alpha), btn_s.get_rect(), border_radius=outer_radius)

            # Inner inset panel (daha pürüzsüz görünüm)
            inner_rect = btn_s.get_rect().inflate(-s(6, minimum=4), -s(6, minimum=4))
            inner_radius = max(8, outer_radius - s(4, minimum=2))
            inner_c = (28, 38, 62, 226 if hover else 188)
            pygame.draw.rect(btn_s, inner_c, inner_rect, border_radius=inner_radius)
            self.screen.blit(btn_s, arrow_rect.topleft)

            # Border
            b_color = retro_style.primary if hover else (60, 75, 100)
            pygame.draw.rect(self.screen, b_color, arrow_rect, 2, border_radius=outer_radius)

            # Arrow icon (fallback: glyph)
            icon_w = max(10, arrow_rect.width - s(14, minimum=8))
            icon_h = max(10, arrow_rect.height - s(18, minimum=10))
            icon = self._get_tutorial_arrow_icon(direction, icon_w, icon_h, hover=hover)
            if icon is not None:
                icon_rect = icon.get_rect(center=arrow_rect.center)
                self.screen.blit(icon, icon_rect)
            else:
                arrow_char = '\u25C0' if direction == 'left' else '\u25B6'
                a_font = retro_style.get_font(s(16, minimum=12), bold=True)
                a_color = (255, 255, 255) if hover else (200, 210, 225)
                a_surf = a_font.render(arrow_char, True, a_color)
                self.screen.blit(a_surf, (
                    arrow_rect.x + (arrow_rect.width - a_surf.get_width()) // 2,
                    arrow_rect.y + (arrow_rect.height - a_surf.get_height()) // 2,
                ))

        # ── Kart alanı ──
        card_pad_x = arrow_w + s(15)
        card_area_x = chapter_area_rect.x + card_pad_x
        card_area_w = chapter_area_rect.width - card_pad_x * 2
        card_area_y = chapter_area_rect.y
        card_area_h = chapter_area_rect.height - s(28)

        clip_rect = pygame.Rect(card_area_x, card_area_y, card_area_w, card_area_h)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)

        anim_offset = float(getattr(self, '_hub_carousel_anim_offset', 0.0) or 0.0)
        self.hub_chapter_rects = []

        def _draw_chapter_card(entry, offset_x):
            chapter = entry['chapter']
            chapter_id = str(chapter.get('id') or '')
            is_locked = not entry.get('unlocked', False)
            is_completed = entry.get('completed', False)

            cx = card_area_x + int(offset_x * (card_area_w + s(16)))
            card_rect = pygame.Rect(cx, card_area_y, card_area_w, card_area_h)

            # Animasyon alpha
            alpha_factor = max(0.0, 1.0 - abs(offset_x) * 1.8)
            if alpha_factor < 0.02:
                return

            # Accent renk: kilitli=muted, tamamlandı=yeşil, aktif=cyan
            if is_locked:
                card_accent = (80, 85, 100)
            elif is_completed:
                card_accent = (0, 255, 150)
            else:
                card_accent = retro_style.primary

            card_alpha = int(190 * alpha_factor)

            # Glow (sadece aktif kart — offset~0)
            if abs(offset_x) < 0.15 and not is_locked:
                glow_r = card_rect.inflate(14, 14)
                glow_s = pygame.Surface(glow_r.size, pygame.SRCALPHA)
                pygame.draw.rect(glow_s, (*card_accent[:3], 30), glow_s.get_rect(), border_radius=14)
                self.screen.blit(glow_s, glow_r.topleft)

            # Panel
            retro_style.draw_glass_panel(self.screen, card_rect, alpha=card_alpha,
                                         border_color=card_accent, top_highlight=False)
            self.hub_chapter_rects.append((card_rect, chapter_id))

            # ── Başlık bandı ──
            band_h = s(50)
            band_rect = pygame.Rect(card_rect.x + 2, card_rect.y + 2, card_rect.width - 4, band_h)
            band_bg = pygame.Surface(band_rect.size, pygame.SRCALPHA)
            band_bg.fill((8, 12, 30, 180))
            self.screen.blit(band_bg, band_rect.topleft)
            pygame.draw.line(self.screen, (*card_accent[:3], 80),
                             (band_rect.x + s(8), band_rect.bottom),
                             (band_rect.right - s(8), band_rect.bottom))

            # Bölüm numarası badge
            ch_index = next((i for i, e in enumerate(chapter_entries)
                             if e['chapter'].get('id') == chapter_id), 0)
            num_text = f"{ch_index + 1}"
            num_font = retro_style.get_font(s(14, minimum=10), bold=True)
            num_surf = num_font.render(num_text, True, card_accent)
            num_bg_size = max(num_surf.get_width(), num_surf.get_height()) + s(10)
            num_bg_rect = pygame.Rect(band_rect.x + s(10), band_rect.y + (band_h - num_bg_size) // 2,
                                      num_bg_size, num_bg_size)
            num_bg_s = pygame.Surface(num_bg_rect.size, pygame.SRCALPHA)
            num_bg_s.fill((15, 20, 45, 200))
            self.screen.blit(num_bg_s, num_bg_rect.topleft)
            pygame.draw.rect(self.screen, (*card_accent[:3], 160), num_bg_rect, 1, border_radius=6)
            self.screen.blit(num_surf, (
                num_bg_rect.x + (num_bg_rect.width - num_surf.get_width()) // 2,
                num_bg_rect.y + (num_bg_rect.height - num_surf.get_height()) // 2,
            ))

            # Bölüm başlığı
            title_x = num_bg_rect.right + s(10)
            chapter_title = self._lesson_title(chapter)
            title_max_w = band_rect.right - title_x - s(10)
            title_surf = retro_style.render_fit_text(chapter_title, (255, 255, 255) if not is_locked else (150, 155, 168),
                                                     title_max_w, s(18, minimum=14), bold=True)
            self.screen.blit(title_surf, (title_x, band_rect.y + (band_h - title_surf.get_height()) // 2))

            # ── Kart gövdesi ──
            body_y = band_rect.bottom + s(16)
            pad_x = card_rect.x + s(18)
            text_w = card_rect.width - s(36)

            # İlerleme çubuğu
            completed_n = entry.get('completed_lessons', 0)
            total_n = entry.get('total_lessons', 0)
            bar_w = text_w
            bar_h = s(6, minimum=4)
            bar_rect = pygame.Rect(pad_x, body_y, bar_w, bar_h)
            pygame.draw.rect(self.screen, (30, 35, 55), bar_rect, border_radius=3)
            if total_n > 0:
                fill_w = max(0, int(bar_w * completed_n / total_n))
                if fill_w > 0:
                    fill_rect = pygame.Rect(pad_x, body_y, fill_w, bar_h)
                    pygame.draw.rect(self.screen, card_accent[:3], fill_rect, border_radius=3)
            pygame.draw.rect(self.screen, (*card_accent[:3], 60), bar_rect, 1, border_radius=3)

            # İlerleme metni
            status_y = body_y + bar_h + s(8)
            status_text = t(
                'tutorial_hub_chapter_status',
                completed=completed_n, total=total_n, stars=entry.get('stars', 0),
                default=f"{completed_n}/{total_n} ders  |  {entry.get('stars', 0)} yıldız",
            )
            status_color = retro_style.text_secondary if not is_locked else retro_style.text_muted
            status_surf = body_font.render(status_text, True, status_color)
            self.screen.blit(status_surf, (pad_x, status_y))

            # Zorluk yıldızları
            diff_y = status_y + s(18)
            difficulty = max(0, min(5, int(chapter.get('difficulty', 1) or 1)))
            diff_label = body_font.render(t('tutorial_difficulty', default='Zorluk:'), True,
                                           retro_style.text_muted if is_locked else retro_style.text_secondary)
            self.screen.blit(diff_label, (pad_x, diff_y))
            star_x = pad_x + diff_label.get_width() + s(8)
            star_size = max(s(13, minimum=9), min(s(18, minimum=12), body_font.get_height() + s(2, minimum=1)))
            star_y = diff_y + max(0, (diff_label.get_height() - star_size) // 2)
            self._draw_tutorial_star_row(
                star_x,
                star_y,
                difficulty,
                5,
                star_size,
                gap=max(1, s(2, minimum=1)),
                locked=is_locked,
            )

            # Açıklama
            desc_y = diff_y + s(22)
            chapter_desc = (t(chapter.get('description_key'), default=chapter.get('description_fallback', ''))
                            if chapter.get('description_key')
                            else str(chapter.get('description_fallback', '')))
            desc_lines = self._wrap_text(chapter_desc, body_font, text_w, max_lines=4)
            for line in desc_lines:
                desc_c = (235, 240, 250) if not is_locked else retro_style.text_muted
                line_surf = body_font.render(line, True, desc_c)
                self.screen.blit(line_surf, (pad_x, desc_y))
                desc_y += s(17)

            # ── Alt durum badge'i ──
            badge_y = card_rect.bottom - s(40)
            if is_locked:
                badge_text = t('tutorial_hub_locked', default='Kilitli')
                badge_color = retro_style.accent  # turuncu
                badge_icon = '\U0001F512 '
            elif is_completed:
                badge_text = t('tutorial_hub_completed', default='Tamamlandı')
                badge_color = (0, 255, 150)
                badge_icon = '\u2714 '
            else:
                badge_text = t('tutorial_hub_in_progress', default='Devam ediyor')
                badge_color = retro_style.primary
                badge_icon = '\u25B6 '

            badge_font = retro_style.get_font(s(13, minimum=10), bold=True)
            badge_surf = badge_font.render(badge_text, True, badge_color)
            badge_w = badge_surf.get_width() + s(22)
            badge_h_px = badge_surf.get_height() + s(10)
            badge_rect = pygame.Rect(card_rect.centerx - badge_w // 2, badge_y, badge_w, badge_h_px)
            badge_bg = pygame.Surface(badge_rect.size, pygame.SRCALPHA)
            badge_bg.fill((12, 20, 45, 190))
            self.screen.blit(badge_bg, badge_rect.topleft)
            pygame.draw.rect(self.screen, (*badge_color[:3], 120), badge_rect, 1, border_radius=8)
            self.screen.blit(badge_surf, (badge_rect.x + s(11), badge_rect.y + s(5)))

        # Aktif kartı çiz
        current_entry = chapter_entries[current_chapter_index] if current_chapter_index < len(chapter_entries) else None
        if current_entry:
            _draw_chapter_card(current_entry, anim_offset)

        # Animasyon: kayarak gelen/giden kartlar
        if abs(anim_offset) > 0.005:
            if anim_offset > 0:
                prev_idx = (current_chapter_index - 1) % len(chapter_entries)
                _draw_chapter_card(chapter_entries[prev_idx], anim_offset - 1.0)
            if anim_offset < 0:
                next_idx = (current_chapter_index + 1) % len(chapter_entries)
                _draw_chapter_card(chapter_entries[next_idx], anim_offset + 1.0)

        self.screen.set_clip(old_clip)

        # ── Sayfa göstergeleri ──
        dot_r = s(5, minimum=3)
        dot_gap = s(16, minimum=12)
        dots_total_w = chapter_count * dot_gap
        dots_cx = chapter_area_rect.x + chapter_area_rect.width // 2
        dots_y = chapter_area_rect.bottom - s(12)
        for di in range(chapter_count):
            cx = dots_cx - dots_total_w // 2 + di * dot_gap + dot_gap // 2
            if di == current_chapter_index:
                pygame.draw.circle(self.screen, retro_style.primary, (cx, dots_y), dot_r)
                # Aktif dot glow
                glow_s = pygame.Surface((dot_r * 6, dot_r * 6), pygame.SRCALPHA)
                pygame.draw.circle(glow_s, (*retro_style.primary[:3], 40),
                                   (dot_r * 3, dot_r * 3), dot_r * 3)
                self.screen.blit(glow_s, (cx - dot_r * 3, dots_y - dot_r * 3))
            else:
                pygame.draw.circle(self.screen, retro_style.text_muted, (cx, dots_y), dot_r - 1)

        # ══════════════════════════════════════════════════════
        # SAĞ PANEL — Ders listesi + seçili ders detayı (FAZ A)
        # ══════════════════════════════════════════════════════
        right_region_x = chapter_area_rect.right + s(16)
        right_region_w = panel_rect.right - right_region_x - s(20)
        # Sağ bölge ikiye ayrılır: solda ders listesi, sağda detay paneli.
        detail_w = max(s(220), int(right_region_w * 0.46))
        lesson_list_w = max(s(180), right_region_w - detail_w - s(14))
        lesson_rect = pygame.Rect(right_region_x, content_top, lesson_list_w, content_height)
        detail_rect = pygame.Rect(lesson_rect.right + s(14), content_top, detail_w, content_height)
        retro_style.draw_glass_panel(self.screen, lesson_rect, alpha=160,
                                     border_color=(60, 120, 80), top_highlight=False)

        # Ders paneli başlık bandı
        lesson_header_h = s(42)
        lh_rect = pygame.Rect(lesson_rect.x + 2, lesson_rect.y + 2, lesson_rect.width - 4, lesson_header_h)
        lh_bg = pygame.Surface(lh_rect.size, pygame.SRCALPHA)
        lh_bg.fill((8, 12, 30, 180))
        self.screen.blit(lh_bg, lh_rect.topleft)
        pygame.draw.line(self.screen, (60, 180, 120, 80),
                         (lh_rect.x + s(12), lh_rect.bottom),
                         (lh_rect.right - s(12), lh_rect.bottom))
        # Sol strip
        strip_rect = pygame.Rect(lh_rect.x + 2, lh_rect.y + 4, 4, lh_rect.height - 8)
        pygame.draw.rect(self.screen, (0, 255, 150), strip_rect, border_radius=2)

        lesson_header_surf = h3_font.render(t('tutorial_hub_lessons', default='Dersler'), True, (0, 255, 150))
        self.screen.blit(lesson_header_surf, (lh_rect.x + s(14), lh_rect.y + (lesson_header_h - lesson_header_surf.get_height()) // 2))

        lesson_entries = self._get_hub_lesson_entries(self.hub_selected_chapter_id) if self.hub_selected_chapter_id else []
        selected_chapter_entry = current_entry
        chapter_locked = bool(selected_chapter_entry) and not selected_chapter_entry.get('unlocked', False)

        self.hub_lesson_rects = []
        lesson_list_top = lesson_rect.y + lesson_header_h + s(14)
        lesson_gap = s(6)
        if chapter_locked:
            locked_lines = self._wrap_text(
                t('tutorial_hub_locked_hint', default='Bu bölüm, önceki eğitimler tamamlanınca açılır.'),
                body_font, lesson_rect.width - s(40), max_lines=3)
            hint_y = lesson_list_top + s(30)
            lock_icon = h2_font.render('\U0001F512', True, retro_style.accent)
            self.screen.blit(lock_icon, (lesson_rect.centerx - lock_icon.get_width() // 2, hint_y))
            hint_y += lock_icon.get_height() + s(12)
            for line in locked_lines:
                line_surf = body_font.render(line, True, retro_style.text_muted)
                self.screen.blit(line_surf, (lesson_rect.x + s(20), hint_y))
                hint_y += s(20)
        else:
            lesson_avail_h = max(s(160), lesson_rect.bottom - lesson_list_top - s(10))
            n_lessons = max(1, len(lesson_entries))
            lesson_card_h = min(s(72), max(s(50), (lesson_avail_h - lesson_gap * (n_lessons - 1)) // n_lessons))
            compact = lesson_card_h <= s(58)
            for li, entry in enumerate(lesson_entries, start=1):
                lesson = entry['lesson']
                lesson_id = str(lesson.get('id') or '')
                is_selected = lesson_id == self.hub_selected_lesson_id
                lesson_completed = entry.get('completed', False)

                row_rect = pygame.Rect(lesson_rect.x + s(10), lesson_list_top,
                                       lesson_rect.width - s(20), lesson_card_h)

                # Seçili ders glow
                if is_selected:
                    sel_glow = row_rect.inflate(8, 8)
                    sel_gs = pygame.Surface(sel_glow.size, pygame.SRCALPHA)
                    pygame.draw.rect(sel_gs, (*retro_style.primary[:3], 35), sel_gs.get_rect(), border_radius=12)
                    self.screen.blit(sel_gs, sel_glow.topleft)

                # Ders kartı
                row_alpha = 200 if is_selected else 150
                row_fill = (28, 35, 55) if is_selected else (18, 24, 40)
                row_s = pygame.Surface(row_rect.size, pygame.SRCALPHA)
                row_s.fill((*row_fill, row_alpha))
                self.screen.blit(row_s, row_rect.topleft)

                # Border
                r_border = retro_style.primary if is_selected else (60, 75, 100)
                pygame.draw.rect(self.screen, r_border, row_rect, 2 if is_selected else 1, border_radius=10)

                # Sol strip
                ls_color = retro_style.primary if is_selected else ((0, 255, 150) if lesson_completed else (100, 110, 130))
                ls_w = 4 if is_selected else 3
                ls_rect = pygame.Rect(row_rect.x + 3, row_rect.y + 4, ls_w, row_rect.height - 8)
                pygame.draw.rect(self.screen, ls_color, ls_rect, border_radius=2)

                self.hub_lesson_rects.append((row_rect, lesson_id))

                # Numara + başlık
                text_x = row_rect.x + s(16)
                title_color = (255, 255, 255) if is_selected else (200, 210, 225)
                # Global ders numarası (Bölüm1 Seviye1 = 1 ... Bölüm7 Seviye28 = 28).
                try:
                    global_no = self._lesson_index(lesson_id)
                except Exception:
                    global_no = li
                title_text_l = f"{global_no}. {self._lesson_title(lesson)}"
                title_max_w = row_rect.width - s(100)
                title_surf = retro_style.render_fit_text(title_text_l, title_color, title_max_w,
                                                         s(14, minimum=11), bold=is_selected)
                self.screen.blit(title_surf, (text_x, row_rect.y + s(8)))

                # Süre rozeti (kısa oturum algısı — FAZ A)
                duration_seconds = int(entry.get('duration_seconds', 0) or 0)
                if duration_seconds > 0:
                    dur_text = t('tutorial_meta_duration', seconds=duration_seconds,
                                 default=f'~{duration_seconds} sn')
                    dur_surf = tiny_font.render(dur_text, True, retro_style.text_muted)
                    self.screen.blit(dur_surf, (row_rect.right - dur_surf.get_width() - s(12), row_rect.y + s(8)))

                # Açıklama (kompakt değilse) — tek satıra sığacak şekilde,
                # taşarsa "…" ile kısaltılır (yarıda kesik görünmez).
                if not compact:
                    lesson_desc = self._lesson_description(lesson)
                    desc_max_w = row_rect.width - s(32)
                    desc_lines = self._wrap_text(lesson_desc, tiny_font, desc_max_w, max_lines=1)
                    if desc_lines:
                        desc_text = desc_lines[0]
                        # Tek satıra sığmayan açıklama varsa "…" ekle.
                        full_first = self._wrap_text(lesson_desc, tiny_font, desc_max_w, max_lines=2)
                        if len(full_first) > 1 and desc_text == full_first[0]:
                            while desc_text and tiny_font.size(desc_text + '…')[0] > desc_max_w:
                                desc_text = desc_text[:-1].rstrip()
                            desc_text = (desc_text + '…') if desc_text else desc_lines[0]
                        desc_surf = tiny_font.render(desc_text, True, retro_style.text_muted)
                        self.screen.blit(desc_surf, (text_x, row_rect.y + s(28)))

                # Yıldız + durum
                stars_n = max(0, min(3, int(entry.get('stars', 0) or 0)))
                star_size = max(s(12, minimum=9), min(s(16, minimum=11), tiny_font.get_height() + s(2, minimum=1)))
                star_gap = max(1, s(2, minimum=1))
                star_row_w = (star_size * 3) + (star_gap * 2)
                star_y = row_rect.y + (s(8) if compact else row_rect.height - s(18))
                star_y = max(row_rect.y + s(6), min(star_y, row_rect.bottom - star_size - s(4)))
                star_x = row_rect.right - star_row_w - s(12)
                self._draw_tutorial_star_row(star_x, star_y, stars_n, 3, star_size, gap=star_gap)

                if lesson_completed and not compact:
                    done_surf = tiny_font.render(t('tutorial_hub_completed', default='Tamamlandı'),
                                                 True, (0, 255, 150))
                    done_x = max(text_x, row_rect.right - done_surf.get_width() - star_row_w - s(20))
                    self.screen.blit(done_surf, (done_x, star_y))

                lesson_list_top += lesson_card_h + lesson_gap

        # ── Seçili ders detay paneli (FAZ A) ──
        self._draw_hub_lesson_detail_panel(detail_rect, chapter_locked, h3_font, body_font, small_font, tiny_font, s)

        # ══════════════════════════════════════════════════════
        # ALT PANEL — butonlar (kontrol ipucu satırı kaldırıldı; butonlar
        # zaten ESC/ENTER alt-etiketini gösteriyor)
        # ══════════════════════════════════════════════════════
        button_y = panel_rect.bottom - s(58)
        button_h = s(42)
        back_rect = pygame.Rect(panel_rect.x + s(22), button_y, s(160), button_h)
        start_rect = pygame.Rect(panel_rect.right - s(222), button_y, s(200), button_h)
        self.hub_back_rect = back_rect
        self.hub_start_rect = start_rect

        back_hover = back_rect.collidepoint(mouse_pos)
        start_hover = start_rect.collidepoint(mouse_pos)
        retro_style.draw_uniform_button(
            self.screen, back_rect,
            t('tutorial_hub_back', default='Menüye Dön'),
            sub_text='ESC',
            color_code=retro_style.secondary,
            selected=back_hover,
            state='hover' if back_hover else 'normal',
        )
        can_start = (bool(selected_chapter_entry) and
                     selected_chapter_entry.get('unlocked') and
                     bool(self.hub_selected_lesson_id))
        start_label = (t('tutorial_hub_start', default='Dersi Başlat')
                       if can_start
                       else t('tutorial_hub_locked', default='Kilitli'))
        retro_style.draw_uniform_button(
            self.screen, start_rect,
            start_label,
            sub_text='ENTER',
            color_code=retro_style.success if can_start else retro_style.primary,
            selected=start_hover,
            state='hover' if start_hover else 'normal',
        )

    def _draw_hub_lesson_detail_panel(self, detail_rect, chapter_locked, h3_font, body_font, small_font, tiny_font, s):
        """Seçili ders için zengin detay panelini çiz (FAZ A).

        Gösterilenler: başlık + tip rozeti, süre, zorluk, neden önemli,
        beceri chip'leri ve yıldız durumu. Tüm metinler t(...) fallback'li.
        """
        retro_style.draw_glass_panel(self.screen, detail_rect, alpha=170,
                                     border_color=(70, 130, 170), top_highlight=False)

        # Başlık bandı
        header_h = s(42)
        dh_rect = pygame.Rect(detail_rect.x + 2, detail_rect.y + 2, detail_rect.width - 4, header_h)
        dh_bg = pygame.Surface(dh_rect.size, pygame.SRCALPHA)
        dh_bg.fill((8, 12, 30, 180))
        self.screen.blit(dh_bg, dh_rect.topleft)
        pygame.draw.line(self.screen, (90, 170, 220, 90),
                         (dh_rect.x + s(12), dh_rect.bottom),
                         (dh_rect.right - s(12), dh_rect.bottom))
        strip_rect = pygame.Rect(dh_rect.x + 2, dh_rect.y + 4, 4, dh_rect.height - 8)
        pygame.draw.rect(self.screen, (110, 190, 255), strip_rect, border_radius=2)
        detail_header_surf = h3_font.render(t('tutorial_meta_what', default='Ne öğreneceksin'), True, (150, 210, 255))
        self.screen.blit(detail_header_surf, (dh_rect.x + s(14), dh_rect.y + (header_h - detail_header_surf.get_height()) // 2))

        pad_x = detail_rect.x + s(16)
        content_w = detail_rect.width - s(32)
        cursor_y = dh_rect.bottom + s(12)
        bottom_limit = detail_rect.bottom - s(12)

        entry = self._get_selected_hub_lesson_entry()
        if not entry or chapter_locked:
            hint_text = (t('tutorial_hub_locked_hint', default='Bu bölüm, önceki eğitimler tamamlanınca açılır.')
                         if chapter_locked
                         else t('tutorial_hub_select_lesson_hint', default='Detayları görmek için bir ders seç.'))
            for line in self._wrap_text(hint_text, body_font, content_w, max_lines=4):
                line_surf = body_font.render(line, True, retro_style.text_muted)
                self.screen.blit(line_surf, (pad_x, cursor_y))
                cursor_y += s(20)
            return

        lesson = entry['lesson']

        # Ders başlığı
        title_surf = retro_style.render_fit_text(self._lesson_title(lesson), (255, 255, 255),
                                                 content_w, s(17, minimum=13), bold=True)
        self.screen.blit(title_surf, (pad_x, cursor_y))
        cursor_y += title_surf.get_height() + s(8)

        # Tip rozeti + süre rozeti (yan yana)
        badge_y = cursor_y
        badge_h = s(20, minimum=15)
        type_label = self._lesson_type_label(entry.get('lesson_type'))
        if type_label:
            type_surf = tiny_font.render(type_label, True, (150, 210, 255))
            type_bg = pygame.Rect(pad_x, badge_y, type_surf.get_width() + s(14), badge_h)
            tb = pygame.Surface(type_bg.size, pygame.SRCALPHA)
            tb.fill((30, 60, 95, 200))
            self.screen.blit(tb, type_bg.topleft)
            pygame.draw.rect(self.screen, (90, 160, 220, 150), type_bg, 1, border_radius=6)
            self.screen.blit(type_surf, (type_bg.x + s(7), type_bg.centery - type_surf.get_height() // 2))
            next_badge_x = type_bg.right + s(8)
        else:
            next_badge_x = pad_x

        duration_seconds = int(entry.get('duration_seconds', 0) or 0)
        if duration_seconds > 0:
            dur_text = t('tutorial_meta_duration', seconds=duration_seconds, default=f'~{duration_seconds} sn')
            dur_surf = tiny_font.render(dur_text, True, (255, 220, 140))
            dur_bg = pygame.Rect(next_badge_x, badge_y, dur_surf.get_width() + s(14), badge_h)
            db = pygame.Surface(dur_bg.size, pygame.SRCALPHA)
            db.fill((60, 50, 25, 200))
            self.screen.blit(db, dur_bg.topleft)
            pygame.draw.rect(self.screen, (220, 180, 90, 150), dur_bg, 1, border_radius=6)
            self.screen.blit(dur_surf, (dur_bg.x + s(7), dur_bg.centery - dur_surf.get_height() // 2))
        cursor_y = badge_y + badge_h + s(12)

        # Zorluk göstergesi
        difficulty = max(0, min(5, int(entry.get('difficulty', 0) or 0)))
        if difficulty > 0:
            diff_label = small_font.render(t('tutorial_meta_difficulty', default='Zorluk'), True, retro_style.text_secondary)
            self.screen.blit(diff_label, (pad_x, cursor_y))
            star_x = pad_x + diff_label.get_width() + s(8)
            star_size = max(s(12, minimum=9), min(s(16, minimum=11), small_font.get_height() + s(2, minimum=1)))
            star_y = cursor_y + max(0, (diff_label.get_height() - star_size) // 2)
            self._draw_tutorial_star_row(star_x, star_y, difficulty, 5, star_size, gap=max(1, s(2, minimum=1)))
            cursor_y += diff_label.get_height() + s(12)

        # Neden önemli
        why_text = str(entry.get('why_it_matters') or '')
        if why_text and cursor_y < bottom_limit:
            why_label = small_font.render(t('tutorial_meta_why', default='Neden önemli'), True, (130, 220, 170))
            self.screen.blit(why_label, (pad_x, cursor_y))
            cursor_y += why_label.get_height() + s(4)
            for line in self._wrap_text(why_text, body_font, content_w, max_lines=4):
                if cursor_y + body_font.get_height() > bottom_limit:
                    break
                line_surf = body_font.render(line, True, (220, 230, 240))
                self.screen.blit(line_surf, (pad_x, cursor_y))
                cursor_y += body_font.get_height() + s(3)
            cursor_y += s(8)

        # Beceri chip'leri
        skill_tags = list(entry.get('skill_tags') or [])
        if skill_tags and cursor_y < bottom_limit:
            skills_label = small_font.render(t('tutorial_meta_skills', default='Kazanımlar'), True, (200, 170, 255))
            self.screen.blit(skills_label, (pad_x, cursor_y))
            cursor_y += skills_label.get_height() + s(6)
            chip_x = pad_x
            chip_y = cursor_y
            chip_h = s(19, minimum=14)
            chip_gap = s(6)
            for tag in skill_tags:
                label = self._skill_tag_label(tag)
                if not label:
                    continue
                chip_surf = tiny_font.render(label, True, (210, 195, 255))
                chip_w = chip_surf.get_width() + s(12)
                if chip_x + chip_w > detail_rect.right - s(12):
                    chip_x = pad_x
                    chip_y += chip_h + chip_gap
                if chip_y + chip_h > bottom_limit:
                    break
                chip_bg = pygame.Rect(chip_x, chip_y, chip_w, chip_h)
                cb = pygame.Surface(chip_bg.size, pygame.SRCALPHA)
                cb.fill((45, 35, 70, 200))
                self.screen.blit(cb, chip_bg.topleft)
                pygame.draw.rect(self.screen, (150, 120, 210, 150), chip_bg, 1, border_radius=8)
                self.screen.blit(chip_surf, (chip_bg.x + s(6), chip_bg.centery - chip_surf.get_height() // 2))
                chip_x += chip_w + chip_gap
            cursor_y = chip_y + chip_h + s(10)

        # Yıldız durumu (alt)
        stars_n = max(0, min(3, int(entry.get('stars', 0) or 0)))
        star_size = max(s(14, minimum=10), min(s(20, minimum=13), small_font.get_height() + s(4, minimum=2)))
        star_row_y = min(bottom_limit - star_size, detail_rect.bottom - star_size - s(12))
        if star_row_y > cursor_y - s(4):
            star_label = small_font.render(
                t('tutorial_result_stars', stars=stars_n, default=f'Yıldız: {stars_n}/3'),
                True, (255, 215, 120),
            )
            self.screen.blit(star_label, (pad_x, star_row_y + max(0, (star_size - star_label.get_height()) // 2)))
            self._draw_tutorial_star_row(pad_x + star_label.get_width() + s(8), star_row_y, stars_n, 3, star_size, gap=max(1, s(3, minimum=2)))

    def _tutorial_card_overlay_header_title(self) -> str:
        raw_title = self._lesson_title() or t('tutorial_card_context_title', default='Ders bağlamı')
        return str(raw_title or t('tutorial_card_context_title', default='Ders bağlamı')).strip()

    def _draw_card_effect_showcase(self):
        """Kart etkisi canlı gösterim sahnesi: board görünür, üstte etki banner'ı.

        Board zaten _apply_tutorial_card_effect ile değiştirildi (base Game.draw
        bunu çizer). Burada yalnız üstte kısa bir bilgilendirme banner'ı çizilir.
        """
        active_width, active_height = self._active_ui_size()
        ui_scale = self._tutorial_modal_scale(min_scale=0.72, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        state = self.card_choice_state if isinstance(self.card_choice_state, dict) else {}
        card_title = str(state.get('showcase_card_title') or '')
        success = bool(state.get('showcase_success'))
        outcome = state.get('showcase_outcome') if isinstance(state.get('showcase_outcome'), dict) else {}
        effect_summary = str(outcome.get('effect_summary') or '')

        # ── Faz 1 (vurgu): etkilenecek hücreleri board üzerinde güçlü vurgula ──
        phase = getattr(self, 'card_effect_showcase_phase', 'highlight')
        highlight_cells = getattr(self, 'card_effect_highlight_cells', None) or set()
        showcase_card = state.get('showcase_card') if isinstance(state.get('showcase_card'), dict) else {}
        card_id = str(showcase_card.get('id') or '')
        # Karta uygun vurgu rengi.
        if card_id in ('nova_burst', 'mini_bomb'):
            hl_core = (255, 150, 70)
            hl_edge = (255, 210, 150)
        elif card_id == 'peak_sculpt':
            hl_core = (120, 220, 255)
            hl_edge = (200, 240, 255)
        elif card_id == 'row_shuffle':
            hl_core = (200, 150, 255)
            hl_edge = (230, 200, 255)
        else:  # clear_rows / gravity_well
            hl_core = (255, 225, 90)
            hl_edge = (255, 250, 200)
        if phase == 'highlight' and highlight_cells:
            try:
                board_offset_x, board_offset_y = self.get_board_offset()
                cell_size = int(self.get_cell_size())
            except Exception:
                cell_size = 0
            if cell_size > 0:
                dur = max(0.001, float(getattr(self, 'card_effect_highlight_duration_s', 0.7)))
                remaining = float(getattr(self, 'card_effect_highlight_timer', 0.0))
                progress = max(0.0, min(1.0, (dur - remaining) / dur))
                pulse = 0.5 + 0.5 * abs(math.sin((dur - remaining) * 14.0))
                core_alpha = int(70 + 150 * pulse)
                bw = max(2, cell_size // 6)
                # Genişleyen dış glow (hafif, çevreyi sarar).
                glow_pad = int(cell_size * 0.35 * progress)
                fill_surf = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                fill_surf.fill((*hl_core, max(0, min(255, core_alpha))))
                for (cx, cy) in highlight_cells:
                    rx = board_offset_x + cx * cell_size
                    ry = board_offset_y + cy * cell_size
                    if glow_pad > 0:
                        glow_rect = pygame.Rect(rx - glow_pad, ry - glow_pad,
                                                cell_size + glow_pad * 2, cell_size + glow_pad * 2)
                        glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                        glow_surf.fill((*hl_core, int(40 * pulse)))
                        self.screen.blit(glow_surf, glow_rect.topleft)
                    self.screen.blit(fill_surf, (rx, ry))
                    pygame.draw.rect(self.screen, hl_edge,
                                     pygame.Rect(rx, ry, cell_size, cell_size), bw)

        title_font = retro_style.get_font(s(22, minimum=15), bold=True)
        body_font = retro_style.get_font(s(15, minimum=11))

        # Üst banner — board'u kapatmayacak şekilde ekranın üstünde.
        banner_w = min(active_width - s(40), s(560))
        line1 = t('tutorial_card_showcase_playing', card=card_title,
                  default=f'{card_title} kullanıldı')
        line1_lines = self._wrap_text(line1, title_font, banner_w - s(36), max_lines=1)
        eff_lines = self._wrap_text(effect_summary, body_font, banner_w - s(36), max_lines=2) if effect_summary else []

        pad = s(14)
        line_h_title = title_font.get_height()
        line_h_body = body_font.get_height() + s(3)
        banner_h = pad * 2 + line_h_title + (s(6) + len(eff_lines) * line_h_body if eff_lines else 0)
        banner_rect = pygame.Rect(
            (active_width - banner_w) // 2,
            s(24),
            banner_w,
            int(banner_h),
        )
        accent = retro_style.success if success else (220, 150, 90)
        retro_style.draw_glass_panel(self.screen, banner_rect, alpha=235, border_color=accent, glow=True)

        cy = banner_rect.y + pad
        for line in line1_lines:
            surf = title_font.render(line, True, (255, 255, 255))
            self.screen.blit(surf, surf.get_rect(centerx=banner_rect.centerx, top=cy))
            cy += line_h_title
        if eff_lines:
            cy += s(6)
            for line in eff_lines:
                surf = body_font.render(line, True, (190, 235, 205) if success else (240, 210, 180))
                self.screen.blit(surf, surf.get_rect(centerx=banner_rect.centerx, top=cy))
                cy += line_h_body

    def _draw_card_board_preview_overlay(self):
        """Kart dersinde önce tahtayı göster; ortada ilgi çekici açıklama + Devam Et.

        Tahta arka planda görünür kalır; panel board üzerinde göz hizasına konur,
        tüm tahtayı kapatmaz. Boyutlar _tutorial_modal_scale / _sx ile ölçeklenir.
        """
        active_width, active_height = self._active_ui_size()
        ui_scale = self._tutorial_modal_scale(min_scale=0.72, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        # Board sınırları (paneli board'a göre konumlamak için).
        try:
            board_x, board_y = self.get_board_offset()
            cell_size = max(1, int(self.get_cell_size()))
            board_w = int(self.board_width) * cell_size
            board_h = int(self.board_height) * cell_size
        except Exception:
            board_x, board_y = 0, 0
            board_w, board_h = active_width, active_height

        # Çok hafif karartma (tahta görünür kalır).
        overlay = pygame.Surface((active_width, active_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 60))
        self.screen.blit(overlay, (0, 0))

        scenario = self.card_choice_state.get('scenario', {}) if isinstance(self.card_choice_state, dict) else {}
        context_lines = [str(l).strip() for l in list(scenario.get('context_lines', []) or [])[:2] if str(l).strip()]

        panel_w = min(active_width - s(40), s(580))
        pad_x_inset = s(22)
        content_w = panel_w - pad_x_inset * 2

        title_font = retro_style.get_font(s(23, minimum=16), bold=True)
        # Durum/Öncelik yazıları büyük ve belirgin.
        info_font = retro_style.get_font(s(19, minimum=14), bold=True)
        info_line_h = info_font.get_height() + s(6)

        # Her bağlam satırını sarmala (kutu yüksekliği için).
        wrapped_blocks = []
        for line in context_lines:
            lines = self._wrap_text(line, info_font, content_w - s(28), max_lines=2)
            wrapped_blocks.append(lines)

        header_band = s(48)
        pad_top = s(16)
        box_pad_y = s(10)
        box_gap = s(12)
        btn_h = s(48)
        btn_gap = s(18)
        pad_bottom = s(18)

        boxes_h = 0
        for lines in wrapped_blocks:
            boxes_h += box_pad_y * 2 + len(lines) * info_line_h + box_gap
        content_h = header_band + pad_top + boxes_h + btn_gap + btn_h + pad_bottom
        panel_h = int(content_h)

        # Paneli board üzerinde göz hizasına konumla; tahtayı kapatmaz.
        panel_top = board_y + max(s(16), int(board_h * 0.14))
        max_top = max(s(20), active_height - panel_h - s(20))
        panel_top = min(panel_top, max_top)
        panel_x = board_x + (board_w - panel_w) // 2
        panel_x = max(s(10), min(panel_x, active_width - panel_w - s(10)))
        panel_rect = pygame.Rect(panel_x, panel_top, panel_w, panel_h)
        # Diğer panellerle aynı sade stil (glow YOK).
        retro_style.draw_glass_panel(self.screen, panel_rect, alpha=240, border_color=(255, 200, 90), glow=False)

        # ── Üst başlık (soluk arka plan, parlaklık dörtgeni/çizgisi YOK) ──
        header_rect = pygame.Rect(panel_rect.x + s(2), panel_rect.y + s(2),
                                  panel_rect.width - s(4), header_band)
        hb = pygame.Surface(header_rect.size, pygame.SRCALPHA)
        hb.fill((40, 32, 14, 120))  # soluk
        self.screen.blit(hb, header_rect.topleft)
        title_surf = title_font.render(
            t('tutorial_card_preview_title', default='Tahtanın durumu bu'), True, (255, 224, 150))
        self.screen.blit(title_surf, title_surf.get_rect(center=(header_rect.centerx, header_rect.centery)))

        cursor_y = header_rect.bottom + pad_top

        # ── Durum / Öncelik kutuları (ders 1-4 başla panelindeki yeşil vurgu stili) ──
        for lines in wrapped_blocks:
            box_h = box_pad_y * 2 + len(lines) * info_line_h
            box_rect = pygame.Rect(panel_rect.x + pad_x_inset - s(4), cursor_y,
                                   content_w + s(8), int(box_h))
            box_bg = pygame.Surface(box_rect.size, pygame.SRCALPHA)
            box_bg.fill((24, 60, 44, 215))
            self.screen.blit(box_bg, box_rect.topleft)
            pygame.draw.rect(self.screen, (110, 235, 165), box_rect, max(2, s(2)), border_radius=s(8))
            pygame.draw.rect(self.screen, (120, 255, 175),
                             pygame.Rect(box_rect.x, box_rect.y, max(2, s(3)), box_rect.height),
                             border_radius=s(2))
            ly = box_rect.y + box_pad_y
            for ln in lines:
                ln_surf = info_font.render(ln, True, (236, 248, 240))
                self.screen.blit(ln_surf, (box_rect.x + s(14), ly))
                ly += info_line_h
            cursor_y = box_rect.bottom + box_gap

        # Devam Et butonu.
        btn_w = min(s(280), content_w)
        btn_rect = pygame.Rect(panel_rect.centerx - btn_w // 2, panel_rect.bottom - btn_h - pad_bottom, btn_w, btn_h)
        self.card_preview_continue_rect = btn_rect
        mouse_pos = get_mouse_pos()
        self._draw_briefing_action_button(
            btn_rect,
            t('tutorial_card_preview_continue', default='Devam Et'),
            'ENTER',
            retro_style.success,
            btn_rect.collidepoint(mouse_pos),
            s,
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

        active_width, active_height = self._active_ui_size()

        if self.card_ui:
            fonts = self._build_tutorial_card_ui_font_pack()
            header_lines = []
            wrap_font = fonts.get('small') or fonts.get('desc')
            wrap_width = max(240, active_width - 280)
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
                active_width,
                active_height,
                fonts,
                choices,
                '',
                False,
                forced_hover_index=forced_hover_index,
                show_secondary_actions=False,
                show_peek_button=True,
                header_title=self._tutorial_card_overlay_header_title(),
                header_lines=header_lines,
                center_header=True,
            )
            return

        ui_scale = self._tutorial_modal_scale(min_scale=0.70, max_scale=1.10)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)

        context_width = min(active_width - s(40), s(980))
        context_height = s(92)
        context_rect = pygame.Rect(
            (active_width - context_width) // 2,
            s(24),
            context_width,
            context_height,
        )
        retro_style.draw_glass_panel(self.screen, context_rect, alpha=220, border_color=(255, 190, 80))

        title_font = retro_style.get_font(s(16, minimum=11), bold=True)
        body_font = retro_style.get_font(s(14, minimum=10))
        title_text = self._tutorial_card_overlay_header_title()
        title_surface = title_font.render(title_text, True, (255, 220, 150))
        self.screen.blit(title_surface, title_surface.get_rect(centerx=context_rect.centerx, top=context_rect.y + s(12)))

        context_lines = list(scenario.get('context_lines', []) or [])[:2]
        line_y = context_rect.y + s(40)
        for line in context_lines:
            line_surface = body_font.render(str(line), True, (230, 235, 242))
            self.screen.blit(line_surface, line_surface.get_rect(centerx=context_rect.centerx, top=line_y))
            line_y += s(20)

        card_gap = s(18)
        card_width = min(s(290), max(s(180), (context_width - (card_gap * (len(choices) - 1))) // len(choices)))
        card_height = s(280)
        total_width = card_width * len(choices) + card_gap * (len(choices) - 1)
        start_x = (active_width - total_width) // 2
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

            hint_text = t('tutorial_card_hint_selected', default='ENTER ile seç') if index == selected_index else t('tutorial_card_hint_controls', default='Seçmek için numara tuşları veya ok tuşları')
            hint_surface = meta_font.render(hint_text, True, border_color)
            self.screen.blit(hint_surface, (rect.x + s(12), rect.bottom - s(22)))

    def _draw_lesson_result_panel(self):
        if not isinstance(self.lesson_result, dict):
            return

        active_width, active_height = self._active_ui_size()
        ui_scale = self._tutorial_modal_scale(min_scale=0.72, max_scale=1.18)
        s = lambda v, minimum=1: self._sx(v, ui_scale, minimum)
        objective_results = list(self.lesson_result.get('objective_results') or [])
        coach_text = str(self.lesson_result.get('coach_text') or '')
        did_well_texts = list(self.lesson_result.get('did_well_texts') or [])
        improve_texts = list(self.lesson_result.get('improve_texts') or [])
        progressive_hint = str(self.lesson_result.get('progressive_hint') or '')
        success = bool(self.lesson_result.get('success'))
        is_board_result = bool(objective_results)
        is_card_result = (not is_board_result) and bool(self.lesson_result.get('card_title'))
        overlay = pygame.Surface((active_width, active_height), pygame.SRCALPHA)
        # Kart sonucunda tahtaya uygulanan etki görünsün diye daha hafif karartma.
        overlay.fill((0, 0, 0, 90) if is_card_result else (0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))
        rect = self._tutorial_lesson_result_panel_rect(is_board_result, is_card_result=is_card_result)
        retro_style.draw_glass_panel(self.screen, rect, alpha=235, border_color=(40, 220, 140) if success else (220, 120, 80))

        title_font = retro_style.get_font(s(30, minimum=20), bold=True)
        body_font = retro_style.get_font(s(19, minimum=14))
        small_font = retro_style.get_font(s(18, minimum=13))
        label_font = retro_style.get_font(s(24, minimum=18), bold=True)

        title_surf = title_font.render(str(self.lesson_result.get('title', t('tutorial_result_title', default='Sonuç'))), True, (255, 255, 255))
        self.screen.blit(title_surf, title_surf.get_rect(center=(rect.centerx, rect.y + s(30))))

        stars_text = t(
            'tutorial_result_stars',
            stars=int(self.lesson_result.get('stars', 0) or 0),
            default=f"Yıldız: {int(self.lesson_result.get('stars', 0) or 0)}/3",
        )
        stars_surf = body_font.render(stars_text, True, (255, 220, 120))
        self.screen.blit(stars_surf, stars_surf.get_rect(center=(rect.centerx, rect.y + s(62))))

        content_cursor_y = rect.y + s(86)
        detail_font = retro_style.get_font(s(17, minimum=13))
        pad_x = rect.x + s(28)
        text_x = rect.x + s(40)
        max_text_width = rect.width - s(56)
        # Alt kısımda tıklanabilir Devam/Tekrar butonu için yer ayır.
        action_btn_h = s(48, minimum=34)
        action_reserve = action_btn_h + s(22)
        bottom_limit = rect.bottom - action_reserve

        if is_board_result:
            # Hedef noktaları (ortalanmış, uzun/CJK metinler için sarmalı)
            for objective in objective_results[:3]:
                obj_text = str(objective.get('text') or '')
                if not obj_text:
                    continue
                for line in self._wrap_text(obj_text, detail_font, max_text_width, max_lines=2):
                    if content_cursor_y + detail_font.get_height() > bottom_limit:
                        break
                    objective_surf = detail_font.render(line, True, (225, 232, 240))
                    self.screen.blit(objective_surf, objective_surf.get_rect(centerx=rect.centerx, top=content_cursor_y))
                    content_cursor_y += detail_font.get_height() + s(2)
                content_cursor_y += s(2)

            # FAZ E — Pedagojik üçlü: İyi yaptın / Geliştir / İpucu.
            def _draw_feedback_block(label_key, label_default, label_color, texts, cy, bullet_color):
                texts = [str(tx).strip() for tx in texts if str(tx).strip()]
                if not texts or cy + label_font.get_height() > bottom_limit:
                    return cy
                label_surf = label_font.render(t(label_key, default=label_default), True, label_color)
                self.screen.blit(label_surf, label_surf.get_rect(centerx=rect.centerx, top=cy))
                cy += label_surf.get_height() + s(3)
                for tx in texts:
                    for line in self._wrap_text(tx, detail_font, max_text_width, max_lines=2):
                        if cy + detail_font.get_height() > bottom_limit:
                            return cy
                        line_surf = detail_font.render(line, True, (220, 230, 240))
                        self.screen.blit(line_surf, line_surf.get_rect(centerx=rect.centerx, top=cy))
                        cy += detail_font.get_height() + s(2)
                return cy + s(5)

            content_cursor_y += s(4)
            content_cursor_y = _draw_feedback_block(
                'tutorial_result_did_well', 'İyi yaptın', (110, 230, 160),
                did_well_texts, content_cursor_y, (90, 220, 140))
            content_cursor_y = _draw_feedback_block(
                'tutorial_result_improve', 'Geliştir', (255, 190, 120),
                improve_texts, content_cursor_y, (255, 160, 90))

            # İpucu (başarısızlıkta kademeli; başarıda coach_text)
            hint_text = progressive_hint if (progressive_hint and not success) else coach_text
            if hint_text and content_cursor_y + label_font.get_height() <= bottom_limit:
                hint_label = label_font.render(t('tutorial_result_ideal_hint', default='İpucu'), True, (150, 200, 245))
                self.screen.blit(hint_label, hint_label.get_rect(centerx=rect.centerx, top=content_cursor_y))
                content_cursor_y += hint_label.get_height() + s(3)
                for line in self._wrap_text(hint_text, detail_font, max_text_width, max_lines=3):
                    if content_cursor_y + detail_font.get_height() > bottom_limit:
                        break
                    line_surf = detail_font.render(line, True, (210, 222, 236))
                    self.screen.blit(line_surf, line_surf.get_rect(centerx=rect.centerx, top=content_cursor_y))
                    content_cursor_y += detail_font.get_height() + s(2)
        else:
            # ── Kart dersi sonucu: seçilen kartın etkisi + öneri + ipucu ──
            card_title = str(self.lesson_result.get('card_title') or '')
            card_desc = str(self.lesson_result.get('card_description') or '')
            recommended = str(self.lesson_result.get('recommended_card_title') or '')

            # Seçilen kart adı (vurgulu).
            if card_title:
                card_label = label_font.render(
                    t('tutorial_result_your_card', default='Seçtiğin kart'),
                    True, (150, 200, 245))
                self.screen.blit(card_label, card_label.get_rect(centerx=rect.centerx, top=content_cursor_y))
                content_cursor_y += card_label.get_height() + s(2)
                ct_font = retro_style.get_font(s(23, minimum=17), bold=True)
                ct_surf = ct_font.render(card_title, True, (255, 255, 255))
                self.screen.blit(ct_surf, ct_surf.get_rect(centerx=rect.centerx, top=content_cursor_y))
                content_cursor_y += ct_surf.get_height() + s(8)

            # Kartın tahtaya UYGULANAN etkisi (öncelikli "ne oldu" mesajı).
            effect_summary = str(self.lesson_result.get('effect_summary') or '')
            if effect_summary:
                eff_label = label_font.render(
                    t('tutorial_result_effect_label', default='Tahtadaki etki'), True, (130, 220, 170))
                self.screen.blit(eff_label, eff_label.get_rect(centerx=rect.centerx, top=content_cursor_y))
                content_cursor_y += eff_label.get_height() + s(3)
                for line in self._wrap_text(effect_summary, body_font, max_text_width, max_lines=2):
                    if content_cursor_y + body_font.get_height() > bottom_limit:
                        break
                    line_surf = body_font.render(line, True, (180, 235, 200))
                    self.screen.blit(line_surf, line_surf.get_rect(center=(rect.centerx, content_cursor_y + body_font.get_height() // 2)))
                    content_cursor_y += body_font.get_height() + s(3)
            else:
                # Etki özeti yoksa (perk/buff) kartın açıklamasını göster.
                effect_text = card_desc or str(self.lesson_result.get('feedback', ''))
                for line in self._wrap_text(effect_text, body_font, max_text_width, max_lines=2):
                    if content_cursor_y + body_font.get_height() > bottom_limit:
                        break
                    line_surf = body_font.render(line, True, (220, 230, 240))
                    self.screen.blit(line_surf, line_surf.get_rect(center=(rect.centerx, content_cursor_y + body_font.get_height() // 2)))
                    content_cursor_y += body_font.get_height() + s(3)

            # Tek kısa geri bildirim (coach) cümlesi.
            feedback = str(self.lesson_result.get('feedback', ''))
            if feedback and content_cursor_y + small_font.get_height() <= bottom_limit:
                content_cursor_y += s(6)
                for line in self._wrap_text(feedback, small_font, max_text_width, max_lines=2):
                    if content_cursor_y + small_font.get_height() > bottom_limit:
                        break
                    line_surf = small_font.render(line, True, (205, 218, 236))
                    self.screen.blit(line_surf, line_surf.get_rect(center=(rect.centerx, content_cursor_y + small_font.get_height() // 2)))
                    content_cursor_y += small_font.get_height() + s(2)

            # Yanlış seçimde önerilen kartı belirt.
            if not success and recommended and content_cursor_y + small_font.get_height() <= bottom_limit:
                content_cursor_y += s(6)
                rec_text = t('tutorial_result_recommended', card=recommended, default=f'Önerilen: {recommended}')
                for line in self._wrap_text(rec_text, small_font, max_text_width, max_lines=2):
                    if content_cursor_y + small_font.get_height() > bottom_limit:
                        break
                    line_surf = small_font.render(line, True, (255, 210, 130))
                    self.screen.blit(line_surf, line_surf.get_rect(center=(rect.centerx, content_cursor_y + small_font.get_height() // 2)))
                    content_cursor_y += small_font.get_height() + s(2)
                    content_cursor_y += small_font.get_height() + s(2)

                # FAZ 5 — Önerilen kartın NEDEN doğru olduğunu da göster (kontrast).
                rec_reason = str(self.lesson_result.get('recommended_reason') or '')
                if rec_reason and content_cursor_y + detail_font.get_height() <= bottom_limit:
                    for line in self._wrap_text(rec_reason, detail_font, max_text_width, max_lines=2):
                        if content_cursor_y + detail_font.get_height() > bottom_limit:
                            break
                        line_surf = detail_font.render(line, True, (210, 222, 236))
                        self.screen.blit(line_surf, line_surf.get_rect(center=(rect.centerx, content_cursor_y + detail_font.get_height() // 2)))
                        content_cursor_y += detail_font.get_height() + s(2)

        # Tıklanabilir ilerleme/tekrar butonu (klavye etiketi alt-satırda).
        success_btn = bool(self.lesson_result.get('success'))
        if success_btn:
            btn_label = t('tutorial_result_btn_continue', default='Devam Et')
            btn_sub = 'ENTER'
            btn_color = retro_style.success
        else:
            btn_label = t('tutorial_result_btn_retry', default='Tekrar Dene')
            btn_sub = 'ENTER / R'
            btn_color = (220, 150, 90)
        btn_w = min(s(320), rect.width - s(56))
        btn_rect = pygame.Rect(
            rect.centerx - btn_w // 2,
            rect.bottom - action_btn_h - s(16),
            btn_w,
            action_btn_h,
        )
        self.lesson_result_primary_rect = btn_rect
        mouse_pos = get_mouse_pos()
        self._draw_briefing_action_button(
            btn_rect,
            btn_label,
            btn_sub,
            btn_color,
            btn_rect.collidepoint(mouse_pos),
            s,
        )
