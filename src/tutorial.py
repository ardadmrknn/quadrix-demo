import pygame
import random

try:
    from .game import Game  # type: ignore
    from .localization import t  # type: ignore
    from .retro_style import retro_style  # type: ignore
    from .constants import *  # type: ignore
    from .pieces import create_piece_by_name  # type: ignore
    from .platform_utils import create_display, normalize_mouse_pos, get_mouse_pos  # type: ignore
except Exception:
    from game import Game
    from localization import t
    from retro_style import retro_style
    from constants import *
    from pieces import create_piece_by_name
    from platform_utils import create_display, normalize_mouse_pos, get_mouse_pos

class TutorialMode(Game):
    def __init__(self, difficulty='Normal', sound_enabled=True, effects_enabled=True, 
                 achievement_manager=None, theme_manager=None, screen=None, 
                 fullscreen=False, settings_manager=None, user_manager=None, 
                 game_mode='tutorial', sound_manager=None, score_manager=None, 
                 block_style_manager=None):
        
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
        
        self._setup_step(1)

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
        self.step = step_num
        self.in_transition = False
        self.fall_speed = 2000 # Reset fall speed
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
            self.board.grid = [[None for _ in range(self.board.width)] for _ in range(self.board.height)]
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
            self.overlay_message = t('tutorial_complete')
            self.tip_message = t('tutorial_tip_step_7')
            self.sub_message = t('tutorial_sub_finish')

    def _complete_step(self, next_step):
        if self.in_transition:
            return
            
        self.in_transition = True
        self.transition_timer = 1.5 # 1.5 saniye daha uzun gösterim
        self.next_step_num = next_step
        
        # Başarı efektleri
        self._create_success_effects()
        self.sound.play('tutorial_complete')  # Daha özel ses
        
        # Reset speed immediately to prevent chaos during transition
        self.fall_speed = 2000 
        
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
        self.board.grid = [[None for _ in range(self.board.width)] for _ in range(self.board.height)]
        color = (100, 100, 100) # Gray
        bottom = self.board.height - 1
        above = self.board.height - 2

        # Kolay satır temizleme pratiği: kesin bir parça dayatmadan
        # oyuncuya bag'den gelen parça ile çözüm fırsatı verir.
        for x in range(self.board.width):
            if x not in (4, 5):
                self.board.grid[bottom][x] = color

        for x in range(self.board.width):
            if x in (0, 1, 8, 9):
                self.board.grid[above][x] = color

        if not self.current_piece:
            self.current_piece = self.spawn_new_piece()
        self.current_piece.x = 3
        self.current_piece.y = 0
        self.apply_theme_to_pieces()
    
    # --------------------------------------------------------------------------
    # INPUT FILTERING AND HANDLING
    # --------------------------------------------------------------------------
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
                            self.user_manager.set_tutorial_completed(True)
                        return 'menu'
                    continue
                
                bindings = self.control_bindings
                
                # --- Step Logic with Filtering ---
                
                # Step 1: Move Left/Right
                if self.step == 1:
                    if event.key in self._action_keys(bindings, 'move_left'):
                        if self._try_move_left():
                            self._register_step_activity()
                            self.sound.play('move')
                            self.step_move_left_count = min(3, self.step_move_left_count + 1)
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
                    self.fall_speed = 2000
                    self.soft_drop_active = False

        return True

    def _perform_hard_drop(self):
        while self.board.is_valid_position(self.current_piece):
            self.current_piece.y += 1
        self.current_piece.y -= 1
        self.lock_and_new_piece()
        self.sound.play('drop')

    def lock_and_new_piece(self):
        # TUTORIAL OVERRIDE:
        # For Steps 1, 2, 3 (Move, Rotate, Soft Drop) -> DO NOT LOCK.
        # Just respawn piece at top to keep board clean and let user practice endlessly
        if self.step in [1, 2, 3]:
            # Reset piece to top
            self._ensure_normal_piece(force_new=True)
            return

        lines_before = self.board.lines_cleared
        super().lock_and_new_piece()
        
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
        if self.board.is_game_over():
             self.board.grid = [[None for _ in range(self.board.width)] for _ in range(self.board.height)]
             if self.step == 5:
                 self._setup_line_clear_scenario()

    def update(self, delta_time):
        dt_seconds = max(0.0, float(delta_time or 0.0)) / 1000.0

        # Handle transition delay
        if self.in_transition:
            self.transition_timer -= dt_seconds
            if self.transition_timer <= 0:
                self._setup_step(self.next_step_num)
            # Transition sırasında da efektleri güncelle
            self._update_success_effects(dt_seconds)
            return
            
        # Başarı efektlerini güncelle
        self._update_success_effects(dt_seconds)
        
        # Mini başarı efektlerini güncelle
        for effect in self.step_completion_effects[:]:
            effect['timer'] -= dt_seconds
            effect['y_offset'] -= 30 * dt_seconds  # Yukarı hareket
            effect['alpha'] = int(255 * (effect['timer'] / 1.0))
            effect['scale'] = 1.2 - (0.2 * (1.0 - effect['timer']))
            
            if effect['timer'] <= 0:
                self.step_completion_effects.remove(effect)
            
        super().update(delta_time)

        if not self.waiting_for_enter and self.step < 7:
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
                 soft_key = self._action_key_label('soft_drop', pygame.K_DOWN, include_down_for_soft=True)
                 self.sub_message = t('tutorial_sub_soft_drop', soft_key=soft_key, progress=progress, target=self.step_target)
                 
                 if self.soft_drop_counter > self.step_target:
                     self._complete_step(4)

    def draw_mode_overlay(self):
        """Mod katmanına çizim (Game.draw içinde çağrılır)"""
        # Başarı efektlerini çiz
        self._draw_success_effects()
        
        # Mini başarı efektlerini çiz
        self._draw_mini_success_effects()
        
        # Tutorial overlay'ini çiz
        self._draw_tutorial_overlay()
        
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
        step_text = f"ADIM {self.step}/7"
        if self.step == 7: step_text = "SON ADIM"
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
        words = text.split(' ')
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            test_surf = font.render(test_line, True, color)
            if test_surf.get_width() <= max_text_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
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
        words = self.tip_message.split(' ')
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            test_surf = text_font.render(test_line, True, text_color)
            if test_surf.get_width() <= max_text_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

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
