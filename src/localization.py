"""Dil ve lokalizasyon sistemi

Bu modül, oyundaki tüm metin çevirilerini merkezi olarak yönetir.
Yeni dil eklemek için:
1. SUPPORTED_LANGUAGES listesine dil kodunu ekleyin (örn: 'de', 'fr')
2. LANGUAGE_METADATA'ya dil bilgilerini ekleyin
3. TRANSLATIONS içindeki her anahtara yeni dil çevirisini ekleyin
4. get_language_name() fonksiyonuna yeni dili ekleyin
"""

import importlib.util
import os
import threading

# Desteklenen diller (ISO 639-1 kodları)
SUPPORTED_LANGUAGES = ['tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ja', 'zh', 'ko']
DEFAULT_LANGUAGE = 'tr'

# Dil metadata bilgileri - yeni diller için bu sözlüğe ekleme yapın
LANGUAGE_METADATA = {
    'tr': {
        'name': 'Turkish',
        'native_name': 'Türkçe',
        'flag_emoji': '🇹🇷',
        'rtl': False,
        'complete': True,
    },
    'en': {
        'name': 'English',
        'native_name': 'English',
        'flag_emoji': '🇬🇧',
        'rtl': False,
        'complete': True,
    },
    'de': {
        'name': 'German',
        'native_name': 'Deutsch',
        'flag_emoji': '🇩🇪',
        'rtl': False,
        'complete': False,
    },
    'fr': {
        'name': 'French',
        'native_name': 'Français',
        'flag_emoji': '🇫🇷',
        'rtl': False,
        'complete': False,
    },
    'es': {
        'name': 'Spanish',
        'native_name': 'Español',
        'flag_emoji': '🇪🇸',
        'rtl': False,
        'complete': False,
    },
    'it': {
        'name': 'Italian',
        'native_name': 'Italiano',
        'flag_emoji': '🇮🇹',
        'rtl': False,
        'complete': False,
    },
    'pt': {
        'name': 'Portuguese',
        'native_name': 'Português',
        'flag_emoji': '🇵🇹',
        'rtl': False,
        'complete': False,
    },
    'ja': {
        'name': 'Japanese',
        'native_name': '日本語',
        'flag_emoji': '🇯🇵',
        'rtl': False,
        'complete': False,
    },
    'zh': {
        'name': 'Chinese',
        'native_name': '中文',
        'flag_emoji': '🇨🇳',
        'rtl': False,
        'complete': False,
    },
    'ko': {
        'name': 'Korean',
        'native_name': '한국어',
        'flag_emoji': '🇰🇷',
        'rtl': False,
        'complete': False,
    },
}

# Tüm oyun metinleri
TRANSLATIONS = {
    # ======================= ANA MENÜ =======================
    'main_menu_title': {
        'tr': 'QUADRIX',
        'en': 'QUADRIX',
        'ja': 'テトリス',
        'zh': '俄罗斯方块',
        'ko': '테트리스',
    },
    'campaign_mode': {
        'tr': '100 Level Macera',
        'en': '100 Level Adventure',
        'ja': '100レベルの冒険',
        'zh': '100关冒险',
        'ko': '100레벨 모험',
    },
    'single_player': {
        'tr': 'Tek Oyunculu',
        'en': 'Single Player',
        'ja': 'シングルプレイ',
        'zh': '单人游戏',
        'ko': '싱글 플레이',
    },
    'new_gen_tetris': {
        'tr': 'Kart Ustalığı',
        'en': 'Card Mastery',
        'ja': 'カードマスタリー',
        'zh': '卡牌大师',
        'ko': '카드 마스터리',
    },
    'daily_challenge': {
        'tr': 'Günlük Görev',
        'en': 'Daily Challenge',
        'ja': 'デイリーチャレンジ',
        'zh': '每日挑战',
        'ko': '일일 도전',
    },
    'pvp_2_players': {
        'tr': 'PvP (2 Oyuncu)',
        'en': 'PvP (2 Players)',
        'ja': 'PvP (2人)',
        'zh': 'PvP（2人）',
        'ko': 'PvP (2인)',
    },
    'extras': {
        'tr': 'Oyun Modları',
        'en': 'Game Modes',
        'ja': 'ゲームモード',
        'zh': '游戏模式',
        'ko': '게임 모드',
    },
    'tutorial_mode': {
        'tr': 'Öğretici',
        'en': 'Tutorial',
        'ja': 'チュートリアル',
        'zh': '教程',
        'ko': '튜토리얼',
    },
    'high_scores': {
        'tr': 'Skorlar',
        'en': 'High Scores',
        'ja': 'ハイスコア',
        'zh': '高分榜',
        'ko': '하이스코어',
    },
    'achievements': {
        'tr': 'Başarımlar',
        'en': 'Achievements',
        'ja': '実績',
        'zh': '成就',
        'ko': '업적',
    },
    'switch_user': {
        'tr': 'Kullanıcı Değiştir',
        'en': 'Switch User',
        'ja': 'ユーザー切替',
        'zh': '切换用户',
        'ko': '사용자 전환',
    },
    'settings': {
        'tr': 'Ayarlar',
        'en': 'Settings',
        'ja': '設定',
        'zh': '设置',
        'ko': '설정',
    },
    'guide': {
        'tr': 'Kılavuz',
        'en': 'Guide',
        'ja': 'ガイド',
        'zh': '指南',
        'ko': '가이드',
    },
    'credits': {
        'tr': 'Krediler',
        'en': 'Credits',
        'ja': 'クレジット',
        'zh': '制作人员',
        'ko': '크레딧',
    },
    'exit': {
        'tr': 'Çık',
        'en': 'Exit',
        'ja': '終了',
        'zh': '退出',
        'ko': '종료',
    },
    'quit': {
        'tr': 'Çıkış',
        'en': 'Quit',
        'ja': '終了',
        'zh': '退出',
        'ko': '종료',
    },
    'button_switch': {
        'tr': 'Geç',
        'en': 'Select',
        'ja': '選択',
        'zh': '选择',
        'ko': '선택',
    },
    'tab_single_player': {
        'tr': 'Tek Oyuncu',
        'en': 'Single Player',
        'zh': '单人',
        'ko': '싱글',
    },
    'tab_pvp_player1': {
        'tr': 'PvP - Oyuncu 1',
        'en': 'PvP - Player 1',
        'zh': 'PvP - 玩家1',
        'ko': 'PvP - 플레이어 1',
    },
    'tab_pvp_player2': {
        'tr': 'PvP - Oyuncu 2',
        'en': 'PvP - Player 2',
        'zh': 'PvP - 玩家2',
        'ko': 'PvP - 플레이어 2',
    },
    'tab_gamepad': {
        'tr': 'Gamepad',
        'en': 'Gamepad',
        'zh': '手柄',
        'ko': '게임패드',
    },
    'gp_enabled': {
        'tr': 'Gamepad Aktif',
        'en': 'Gamepad Enabled',
        'zh': '启用手柄',
        'ko': '게임패드 활성화',
    },
    'gp_rumble': {
        'tr': 'Titreşim',
        'en': 'Vibration',
        'zh': '振动',
        'ko': '진동',
    },
    'gp_deadzone': {
        'tr': 'Hassasiyet (Deadzone)',
        'en': 'Deadzone',
        'zh': '死区',
        'ko': '데드존',
    },
    'gp_mouse_sensitivity': {
        'tr': 'Mouse Hassasiyeti',
        'en': 'Mouse Sensitivity',
        'zh': '鼠标灵敏度',
        'ko': '마우스 민감도',
    },
    'gp_hard_drop': {
        'tr': 'Anında Bırak',
        'en': 'Hard Drop',
        'zh': '硬降',
        'ko': '하드 드롭',
    },
    'gp_rotate': {
        'tr': 'Döndür',
        'en': 'Rotate',
        'zh': '旋转',
        'ko': '회전',
    },
    'gp_rotate_alt': {
        'tr': 'Döndür (Alt)',
        'en': 'Rotate (Alt)',
        'zh': '旋转(备选)',
        'ko': '회전 (보조)',
    },
    'gp_hold': {
        'tr': 'Hold / Değiştir',
        'en': 'Hold / Swap',
        'zh': '保留 / 交换',
        'ko': '홀드 / 교체',
    },
    'gp_hold2': {
        'tr': '2. Cep',
        'en': '2nd Pocket',
        'zh': '第二口袋',
        'ko': '2번 포켓',
    },
    'gp_pause': {
        'tr': 'Duraklat',
        'en': 'Pause',
        'zh': '暂停',
        'ko': '일시정지',
    },
    'gp_main_menu_prompt': {
        'tr': 'Ana Menü Onayı',
        'en': 'Main Menu Prompt',
        'zh': '返回主菜单确认',
        'ko': '메인 메뉴 확인',
    },
    'gp_status_connected': {
        'tr': '✅ Bağlı',
        'en': '✅ Connected',
        'zh': '✅ 已连接',
        'ko': '✅ 연결됨',
    },
    'gp_status_disconnected': {
        'tr': '❌ Bağlı Değil',
        'en': '❌ Not Connected',
        'zh': '❌ 未连接',
        'ko': '❌ 연결 안 됨',
    },
    'gp_press_button': {
        'tr': 'Gamepad butonuna bas...',
        'en': 'Press a gamepad button...',
        'zh': '按下手柄按键...',
        'ko': '게임패드 버튼을 누르세요...',
    },
    'gp_move_direction': {
        'tr': 'Hareket: D-Pad / Sol Stick',
        'en': 'Move: D-Pad / Left Stick',
        'zh': '移动: 十字键 / 左摇杆',
        'ko': '이동: D-Pad / 왼쪽 스틱',
    },
    'gp_on': {
        'tr': 'Açık',
        'en': 'On',
        'zh': '开',
        'ko': '켜짐',
    },
    'gp_off': {
        'tr': 'Kapalı',
        'en': 'Off',
        'zh': '关',
        'ko': '꺼짐',
    },
    'gp_section_ingame': {
        'tr': 'Oyun İçi',
        'en': 'In-Game',
        'zh': '游戏中',
        'ko': '게임 중',
    },
    'gp_section_card': {
        'tr': 'Kart Modu',
        'en': 'Card Mode',
        'zh': '卡牌模式',
        'ko': '카드 모드',
    },
    'gp_section_menu': {
        'tr': 'Ana Menü',
        'en': 'Main Menu',
        'zh': '主菜单',
        'ko': '메인 메뉴',
    },
    'gp_section_general': {
        'tr': 'Genel',
        'en': 'General',
        'zh': '常规',
        'ko': '일반',
    },
    'gp_menu_back': {
        'tr': 'Geri',
        'en': 'Back',
        'zh': '返回',
        'ko': '뒤로',
    },
    'gp_menu_confirm': {
        'tr': 'Onayla / Seç',
        'en': 'Confirm / Select',
        'zh': '确认 / 选择',
        'ko': '확인 / 선택',
    },
    'gp_lt': {
        'tr': 'LT (Sol Tetik)',
        'en': 'LT (Left Trigger)',
        'zh': 'LT (左扳机)',
        'ko': 'LT (왼쪽 트리거)',
    },
    'gp_rt': {
        'tr': 'RT (Sağ Tetik)',
        'en': 'RT (Right Trigger)',
        'zh': 'RT (右扳机)',
        'ko': 'RT (오른쪽 트리거)',
    },
    'gp_restart': {
        'tr': 'Yeniden Başlat',
        'en': 'Restart',
        'zh': '重新开始',
        'ko': '다시 시작',
    },
    'gp_discard_held': {
        'tr': 'Saklananı Sil',
        'en': 'Discard Held',
        'zh': '丢弃保留',
        'ko': '보류 삭제',
    },
    'gp_soft_drop_btn': {
        'tr': 'Hızlı Düşür (Buton)',
        'en': 'Soft Drop (Button)',
        'zh': '软降(按键)',
        'ko': '소프트 드롭 (버튼)',
    },
    'gp_unbound': {
        'tr': 'Atanmamış',
        'en': 'Unbound',
        'zh': '未绑定',
        'ko': '미지정',
    },
    'gp_card_rewind': {
        'tr': 'Geri Sarma',
        'en': 'Rewind',
        'zh': '回溯',
        'ko': '되감기',
    },
    'gp_card_sniper': {
        'tr': 'Keskin Nişancı',
        'en': 'Sniper Shot',
        'zh': '狙击',
        'ko': '저격',
    },
    'gp_card_time_capsule_save': {
        'tr': 'Zaman Kapsülü Kaydet',
        'en': 'Save Time Capsule',
        'zh': '保存时间胶囊',
        'ko': '타임 캡슐 저장',
    },
    'gp_card_time_capsule_restore': {
        'tr': 'Zaman Kapsülü Geri Yükle',
        'en': 'Restore Time Capsule',
        'zh': '恢复时间胶囊',
        'ko': '타임 캡슐 복원',
    },
    'gp_card_phase_shift': {
        'tr': 'Faz Kaydır',
        'en': 'Phase Shift',
        'zh': '相位转移',
        'ko': '페이즈 시프트',
    },
    'gp_card_ghost': {
        'tr': 'Hayalet Parça',
        'en': 'Ghost Piece',
        'zh': '幽灵方块',
        'ko': '고스트 피스',
    },
    'gp_card_hammer': {
        'tr': 'Çekiç',
        'en': 'Hammer',
        'zh': '锤子',
        'ko': '해머',
    },
    'gp_card_bomb': {
        'tr': 'Bomba Ustası',
        'en': 'Bomb Master',
        'zh': '炸弹大师',
        'ko': '폭탄 마스터',
    },
    'gp_menu_tab_next': {
        'tr': 'Sonraki Sekme',
        'en': 'Next Tab',
        'zh': '下一选项卡',
        'ko': '다음 탭',
    },
    'gp_menu_tab_prev': {
        'tr': 'Önceki Sekme',
        'en': 'Previous Tab',
        'zh': '上一选项卡',
        'ko': '이전 탭',
    },
    'gp_menu_navigate': {
        'tr': 'Gezinme: D-Pad / Sol Stick',
        'en': 'Navigate: D-Pad / Left Stick',
        'zh': '导航: 十字键 / 左摇杆',
        'ko': '탐색: D-Pad / 왼쪽 스틱',
    },
    'ctrl_move_left': {
        'tr': 'Sola kay',
        'en': 'Move Left',
        'zh': '向左移动',
        'ko': '왼쪽 이동',
    },
    'ctrl_move_right': {
        'tr': 'Sağa kay',
        'en': 'Move Right',
        'zh': '向右移动',
        'ko': '오른쪽 이동',
    },
    'ctrl_soft_drop': {
        'tr': 'Hızlı indir',
        'en': 'Soft Drop',
        'zh': '软降',
        'ko': '소프트 드롭',
    },
    'ctrl_hard_drop': {
        'tr': 'Anında bırak',
        'en': 'Hard Drop',
        'zh': '硬降',
        'ko': '하드 드롭',
    },
    'ctrl_rotate': {
        'tr': 'Döndür',
        'en': 'Rotate',
        'zh': '旋转',
        'ko': '회전',
    },
    'ctrl_hold': {
        'tr': 'Hold / değiştir',
        'en': 'Hold / Swap',
        'zh': '保留 / 交换',
        'ko': '홀드 / 교체',
    },
    'ctrl_pause': {
        'tr': 'Duraklat',
        'en': 'Pause',
        'zh': '暂停',
        'ko': '일시정지',
    },
    'ctrl_toggle_fps': {
        'tr': 'FPS göster',
        'en': 'Toggle FPS',
        'zh': '显示FPS',
        'ko': 'FPS 표시',
    },
    'ctrl_fullscreen_toggle': {
        'tr': 'Tam ekran',
        'en': 'Fullscreen',
        'zh': '全屏',
        'ko': '전체 화면',
    },
    'key_left_arrow': {
        'tr': 'Sol Ok',
        'en': 'Left Arrow',
        'zh': '左箭头',
        'ko': '왼쪽 화살표',
    },
    'key_right_arrow': {
        'tr': 'Sağ Ok',
        'en': 'Right Arrow',
        'zh': '右箭头',
        'ko': '오른쪽 화살표',
    },
    'key_up_arrow': {
        'tr': 'Yukarı Ok',
        'en': 'Up Arrow',
        'zh': '上箭头',
        'ko': '위쪽 화살표',
    },
    'key_down_arrow': {
        'tr': 'Aşağı Ok',
        'en': 'Down Arrow',
        'zh': '下箭头',
        'ko': '아래쪽 화살표',
    },
    'key_space': {
        'tr': 'Boşluk',
        'en': 'Space',
        'zh': '空格',
        'ko': '스페이스',
    },
    'key_enter': {
        'tr': 'Enter',
        'en': 'Enter',
        'zh': '回车',
        'ko': '엔터',
    },
    'key_escape': {
        'tr': 'ESC',
        'en': 'ESC',
        'zh': 'ESC',
        'ko': 'ESC',
    },
    'key_left_shift': {
        'tr': 'Sol Shift',
        'en': 'Left Shift',
        'zh': '左Shift',
        'ko': '왼쪽 Shift',
    },
    'key_right_shift': {
        'tr': 'Sağ Shift',
        'en': 'Right Shift',
        'zh': '右Shift',
        'ko': '오른쪽 Shift',
    },
    'key_caps_lock': {
        'tr': 'Caps Lock',
        'en': 'Caps Lock',
        'zh': '大写锁定',
        'ko': '캡스락',
    },
    'key_tab': {
        'tr': 'Tab',
        'en': 'Tab',
        'zh': 'Tab',
        'ko': '탭',
    },
    'key_left_ctrl': {
        'tr': 'Sol Ctrl',
        'en': 'Left Ctrl',
        'zh': '左Ctrl',
        'ko': '왼쪽 Ctrl',
    },
    'key_right_ctrl': {
        'tr': 'Sağ Ctrl',
        'en': 'Right Ctrl',
        'zh': '右Ctrl',
        'ko': '오른쪽 Ctrl',
    },
    'key_left_alt': {
        'tr': 'Sol Alt',
        'en': 'Left Alt',
        'zh': '左Alt',
        'ko': '왼쪽 Alt',
    },
    'key_right_alt': {
        'tr': 'Sağ Alt',
        'en': 'Right Alt',
        'zh': '右Alt',
        'ko': '오른쪽 Alt',
    },
    'guide_controls_header': {
        'tr': 'Kontroller',
        'en': 'Controls',
        'zh': '控制',
        'ko': '컨트롤',
    },
    'guide_controls_line': {
        'tr': '{action}: {keys}',
        'en': '{action}: {keys}',
        'zh': '{action}: {keys}',
        'ko': '{action}: {keys}',
    },
    'none': {
        'tr': 'Yok',
        'en': 'None',
        'zh': '无',
        'ko': '없음',
    },
    
    # ======================= AYARLAR MENÜSÜ =======================
    'settings_title': {
        'tr': 'AYARLAR',
        'en': 'SETTINGS',
        'de': 'EINSTELLUNGEN',
        'fr': 'PARAMÈTRES',
        'es': 'AJUSTES',
        'it': 'IMPOSTAZIONI',
        'pt': 'CONFIGURAÇÕES',
        'ja': '設定',
        'zh': '设置',
        'ko': '설정'
    },
    'graphics': {
        'tr': 'Grafikler',
        'en': 'Graphics',
        'de': 'Grafik',
        'fr': 'Graphiques',
        'es': 'Gráficos',
        'it': 'Grafica',
        'pt': 'Gráficos',
        'ja': 'グラフィック',
        'zh': '图形',
        'ko': '그래픽'
    },
    'block_styles': {
        'tr': 'Blok Görünümleri',
        'en': 'Block Styles',
        'de': 'Blockstile',
        'fr': 'Styles de blocs',
        'es': 'Estilos de bloques',
        'it': 'Stili blocchi',
        'pt': 'Estilos de blocos',
        'ja': 'ブロックスタイル',
        'zh': '方块样式',
        'ko': '블록 스타일'
    },
    'piece_workshop': {
        'tr': 'Parça Atölyesi',
        'en': 'Piece Workshop',
        'de': 'Teile-Werkstatt',
        'fr': 'Atelier de pièces',
        'es': 'Taller de piezas',
        'it': 'Officina pezzi',
        'pt': 'Oficina de peças',
        'ja': 'ピース工房',
        'zh': '方块工坊',
        'ko': '피스 공방'
    },
    'piece_workshop_showcase_desc': {
        'tr': 'Kendi parçalarını tasarla!',
        'en': 'Design your own pieces!',
        'de': 'Gestalte eigene Teile!',
        'fr': 'Crée tes propres pièces !',
        'es': '¡Diseña tus propias piezas!',
        'it': 'Progetta i tuoi pezzi!',
        'pt': 'Projete suas próprias peças!',
        'ja': '自分だけのピースを作ろう！',
        'zh': '设计你的专属方块！',
        'ko': '나만의 피스를 디자인하세요!'
    },
    'block_styles_showcase_desc': {
        'tr': 'Renkleri özelleştir!',
        'en': 'Customize block colors!',
        'de': 'Blockfarben anpassen!',
        'fr': 'Personnalise les couleurs !',
        'es': '¡Personaliza los colores!',
        'it': 'Personalizza i colori!',
        'pt': 'Personalize as cores!',
        'ja': 'ブロックの色をカスタマイズ！',
        'zh': '自定义方块颜色！',
        'ko': '블록 색상을 커스터마이즈!'
    },
    'debug_mode': {
        'tr': 'Debug Modu',
        'en': 'Debug Mode',
        'de': 'Debug-Modus',
        'fr': 'Mode débogage',
        'es': 'Modo depuración',
        'it': 'Modalità debug',
        'pt': 'Modo depuração',
        'ja': 'デバッグモード',
        'zh': '调试模式',
        'ko': '디버그 모드'
    },
    'card_debug': {
        'tr': 'Kart Modu Debug',
        'en': 'Card Debug',
        'de': 'Karten-Debug',
        'fr': 'Débogage cartes',
        'es': 'Depuración de cartas',
        'it': 'Debug carte',
        'pt': 'Depuração de cartas',
        'ja': 'カードデバッグ',
        'zh': '卡牌调试',
        'ko': '카드 디버그'
    },
    'gameplay': {
        'tr': 'Oynanış',
        'en': 'Gameplay',
        'de': 'Spielablauf',
        'fr': 'Jouabilité',
        'es': 'Jugabilidad',
        'it': 'Gameplay',
        'pt': 'Jogabilidade',
        'ja': 'ゲームプレイ',
        'zh': '游戏玩法',
        'ko': '게임플레이'
    },
    'tracks_label': {
        'tr': 'Müzikler',
        'en': 'Tracks',
        'de': 'Titel',
        'fr': 'Pistes',
        'es': 'Pistas',
        'it': 'Tracce',
        'pt': 'Faixas',
        'ja': 'トラック',
        'zh': '曲目',
        'ko': '트랙'
    },
    'language_setting': {
        'tr': 'Dil / Language',
        'en': 'Language',
        'de': 'Sprache',
        'fr': 'Langue',
        'es': 'Idioma',
        'it': 'Lingua',
        'pt': 'Idioma',
        'ja': '言語 / Language',
        'zh': '语言',
        'ko': '언어'
    },
    'language': {
        'tr': 'Dil',
        'en': 'Language',
        'de': 'Sprache',
        'fr': 'Langue',
        'es': 'Idioma',
        'it': 'Lingua',
        'pt': 'Idioma',
        'ja': '言語',
        'zh': '语言',
        'ko': '언어'
    },
    'turkish': {
        'tr': 'Türkçe',
        'en': 'Turkish',
        'de': 'Türkisch',
        'fr': 'Turc',
        'es': 'Turco',
        'it': 'Turco',
        'pt': 'Turco',
        'ja': 'トルコ語',
        'zh': '土耳其语',
        'ko': '터키어'
    },
    'english': {
        'tr': 'İngilizce',
        'en': 'English',
        'de': 'Englisch',
        'fr': 'Anglais',
        'es': 'Inglés',
        'it': 'Inglese',
        'pt': 'Inglês',
        'ja': '英語',
        'zh': '英语',
        'ko': '영어'
    },
    'german': {
        'tr': 'Almanca',
        'en': 'German',
        'de': 'Deutsch',
        'fr': 'Allemand',
        'es': 'Alemán',
        'it': 'Tedesco',
        'pt': 'Alemão',
        'ja': 'ドイツ語',
        'zh': '德语',
        'ko': '독일어'
    },
    'french': {
        'tr': 'Fransızca',
        'en': 'French',
        'de': 'Französisch',
        'fr': 'Français',
        'es': 'Francés',
        'it': 'Francese',
        'pt': 'Francês',
        'ja': 'フランス語',
        'zh': '法语',
        'ko': '프랑스어'
    },
    'spanish': {
        'tr': 'İspanyolca',
        'en': 'Spanish',
        'de': 'Spanisch',
        'fr': 'Espagnol',
        'es': 'Español',
        'it': 'Spagnolo',
        'pt': 'Espanhol',
        'ja': 'スペイン語',
        'zh': '西班牙语',
        'ko': '스페인어'
    },
    'italian': {
        'tr': 'İtalyanca',
        'en': 'Italian',
        'de': 'Italienisch',
        'fr': 'Italien',
        'es': 'Italiano',
        'it': 'Italiano',
        'pt': 'Italiano',
        'ja': 'イタリア語',
        'zh': '意大利语',
        'ko': '이탈리아어'
    },
    'portuguese': {
        'tr': 'Portekizce',
        'en': 'Portuguese',
        'de': 'Portugiesisch',
        'fr': 'Portugais',
        'es': 'Portugués',
        'it': 'Portoghese',
        'pt': 'Português',
        'ja': 'ポルトガル語',
        'zh': '葡萄牙语',
        'ko': '포르투갈어'
    },
    'theme': {
        'tr': 'Tema',
        'en': 'Theme',
        'de': 'Thema',
        'fr': 'Thème',
        'es': 'Tema',
        'it': 'Tema',
        'pt': 'Tema',
        'ja': 'テーマ',
        'zh': '主题',
        'ko': '테마'
    },
    'music': {
        'tr': 'Müzik',
        'en': 'Music',
        'de': 'Musik',
        'fr': 'Musique',
        'es': 'Música',
        'it': 'Musica',
        'pt': 'Música',
        'ja': '音楽',
        'zh': '音乐',
        'ko': '음악'
    },
    'sound_effects': {
        'tr': 'Ses Efektleri',
        'en': 'Sound Effects',
        'de': 'Soundeffekte',
        'fr': 'Effets Sonores',
        'es': 'Efectos de Sonido',
        'it': 'Effetti Sonori',
        'pt': 'Efeitos Sonoros',
        'ja': '効果音',
        'zh': '音效',
        'ko': '효과음'
    },
    'music_volume': {
        'tr': 'Müzik Seviyesi',
        'en': 'Music Volume',
        'de': 'Musiklautstärke',
        'fr': 'Volume Musique',
        'es': 'Volumen Música',
        'it': 'Volume Musica',
        'pt': 'Volume Música',
        'ja': '音楽音量',
        'zh': '音乐音量',
        'ko': '음악 볼륨'
    },
    'sfx_volume': {
        'tr': 'Efekt Seviyesi',
        'en': 'SFX Volume',
        'de': 'Effekt-Lautstärke',
        'fr': 'Volume Effets',
        'es': 'Volumen Efectos',
        'it': 'Volume Effetti',
        'pt': 'Volume Efeitos',
        'ja': '効果音量',
        'zh': '音效音量',
        'ko': '효과음 볼륨'
    },
    'mute_all': {
        'tr': 'Sessiz Mod',
        'en': 'Mute All',
        'de': 'Alles stumm',
        'fr': 'Tout couper',
        'es': 'Silenciar Todo',
        'it': 'Disattiva Tutto',
        'pt': 'Silenciar Tudo',
        'ja': 'ミュート',
        'zh': '全部静音',
        'ko': '전체 음소거'
    },
    'ghost_piece': {
        'tr': 'Gölge Parça',
        'en': 'Ghost Piece',
        'de': 'Geisterstück',
        'fr': 'Pièce Fantôme',
        'es': 'Pieza Fantasma',
        'it': 'Pezzo Fantasma',
        'pt': 'Peça Fantasma',
        'ja': 'ゴーストピース',
        'zh': '幽灵方块',
        'ko': '고스트 피스'
    },
    'effects': {
        'tr': 'Efektler',
        'en': 'Effects',
        'de': 'Effekte',
        'fr': 'Effets',
        'es': 'Efectos',
        'it': 'Effetti',
        'pt': 'Efeitos',
        'ja': 'エフェクト',
        'zh': '效果',
        'ko': '효과'
    },
    'game_music': {
        'tr': 'Oyun Müziği',
        'en': 'Game Music',
        'de': 'Spielmusik',
        'fr': 'Musique de Jeu',
        'es': 'Música del Juego',
        'it': 'Musica del Gioco',
        'pt': 'Música do Jogo',
        'ja': 'ゲーム音楽',
        'zh': '游戏音乐',
        'ko': '게임 음악'
    },
    'menu_music': {
        'tr': 'Menü Müziği',
        'en': 'Menu Music',
        'de': 'Menümusik',
        'fr': 'Musique du Menu',
        'es': 'Música del Menú',
        'it': 'Musica del Menu',
        'pt': 'Música do Menu',
        'ja': 'メニュー音楽',
        'zh': '菜单音乐',
        'ko': '메뉴 음악'
    },
    'music_campaign': {
        'tr': 'Görev Modu',
        'en': 'Campaign Mode',
        'de': 'Kampagnenmodus',
        'fr': 'Mode Campagne',
        'es': 'Modo Campaña',
        'it': 'Modalità Campagna',
        'pt': 'Modo Campanha',
        'ja': 'キャンペーンモード',
        'zh': '战役模式',
        'ko': '캠페인 모드'
    },
    'music_classic': {
        'tr': 'Klasik (Tek Oyuncu)',
        'en': 'Classic (Single Player)',
        'de': 'Klassisch (Einzelspieler)',
        'fr': 'Classique (Solo)',
        'es': 'Clásico (Un Jugador)',
        'it': 'Classico (Giocatore Singolo)',
        'pt': 'Clássico (Um Jogador)',
        'ja': 'クラシック（シングル）',
        'zh': '经典（单人）',
        'ko': '클래식(싱글)'
    },
    'music_daily': {
        'tr': 'Daily Challenge',
        'en': 'Daily Challenge',
        'de': 'Tägliche Herausforderung',
        'fr': 'Défi Quotidien',
        'es': 'Desafío Diario',
        'it': 'Sfida Giornaliera',
        'pt': 'Desafio Diário',
        'ja': 'デイリーチャレンジ',
        'zh': '每日挑战',
        'ko': '일일 도전'
    },
    'music_sprint': {
        'tr': 'Sprint Mode',
        'en': 'Sprint Mode',
        'de': 'Sprint-Modus',
        'fr': 'Mode Sprint',
        'es': 'Modo Sprint',
        'it': 'Modalità Sprint',
        'pt': 'Modo Sprint',
        'ja': 'スプリント',
        'zh': '冲刺模式',
        'ko': '스프린트 모드'
    },
    'music_ultra': {
        'tr': 'Ultra Mode',
        'en': 'Ultra Mode',
        'de': 'Ultra-Modus',
        'fr': 'Mode Ultra',
        'es': 'Modo Ultra',
        'it': 'Modalità Ultra',
        'pt': 'Modo Ultra',
        'ja': 'ウルトラ',
        'zh': '超强模式',
        'ko': '울트라 모드'
    },
    'music_zen': {
        'tr': 'Zen Mode',
        'en': 'Zen Mode',
        'de': 'Zen-Modus',
        'fr': 'Mode Zen',
        'es': 'Modo Zen',
        'it': 'Modalità Zen',
        'pt': 'Modo Zen',
        'ja': '禅',
        'zh': '禅模式',
        'ko': '젠 모드'
    },
    'music_tetris2': {
        'tr': 'Quadrix Extra',
        'en': 'Quadrix Extra',
        'de': 'Quadrix Extra',
        'fr': 'Quadrix Extra',
        'es': 'Quadrix Extra',
        'it': 'Quadrix Extra',
        'pt': 'Quadrix Extra',
        'ja': 'テトリス・エクストラ',
        'zh': '俄罗斯方块 额外',
        'ko': '테트리스 엑스트라'
    },
    'music_mystery': {
        'tr': 'Kart Ustalığı',
        'en': 'Card Mastery',
        'de': 'Karten-Meisterschaft',
        'fr': 'Maîtrise des Cartes',
        'es': 'Maestría de Cartas',
        'it': 'Maestria delle Carte',
        'pt': 'Maestria de Cartas',
        'ja': 'カードマスタリー',
        'zh': '卡牌大师',
        'ko': '카드 마스터리'
    },
    'music_wide': {
        'tr': 'Wide Mode',
        'en': 'Wide Mode',
        'de': 'Breitbild-Modus',
        'fr': 'Mode Large',
        'es': 'Modo Ancho',
        'it': 'Modalità Larga',
        'pt': 'Modo Amplo',
        'ja': 'ワイドモード',
        'zh': '宽屏模式',
        'ko': '와이드 모드'
    },
    'music_survival': {
        'tr': 'Survival Mode',
        'en': 'Survival Mode',
        'de': 'Überlebensmodus',
        'fr': 'Mode Survie',
        'es': 'Modo Supervivencia',
        'it': 'Modalità Sopravvivenza',
        'pt': 'Modo Sobrevivência',
        'ja': 'サバイバルモード',
        'zh': '生存模式',
        'ko': '서바이벌 모드'
    },
    'music_cascade': {
        'tr': 'Cascade Mode',
        'en': 'Cascade Mode',
        'de': 'Kaskaden-Modus',
        'fr': 'Mode Cascade',
        'es': 'Modo Cascada',
        'it': 'Modalità Cascata',
        'pt': 'Modo Cascata',
        'ja': 'カスケードモード',
        'zh': '级联模式',
        'ko': '캐스케이드 모드'
    },
    'music_hardcore': {
        'tr': 'Hardcore Mode',
        'en': 'Hardcore Mode',
        'de': 'Hardcore-Modus',
        'fr': 'Mode Hardcore',
        'es': 'Modo Hardcore',
        'it': 'Modalità Hardcore',
        'pt': 'Modo Hardcore',
        'ja': 'ハードコアモード',
        'zh': '硬核模式',
        'ko': '하드코어 모드'
    },
    'music_pvp': {
        'tr': 'PvP (2 Oyuncu)',
        'en': 'PvP (2 Players)',
        'de': 'PvP (2 Spieler)',
        'fr': 'PvP (2 Joueurs)',
        'es': 'PvP (2 Jugadores)',
        'zh': 'PvP（2人）',
        'ko': 'PvP (2인)',
        'it': 'PvP (2 Giocatori)',
        'pt': 'PvP (2 Jogadores)',
        'ja': 'PvP（2人）'
    },
    'back': {
        'tr': 'Geri',
        'en': 'Back',
        'de': 'Zurück',
        'fr': 'Retour',
        'es': 'Atrás',
        'it': 'Indietro',
        'pt': 'Voltar',
        'ja': '戻る'
    },
    'on': {
        'tr': 'AÇIK',
        'en': 'ON',
        'de': 'AN',
        'fr': 'OUI',
        'es': 'SÍ',
        'it': 'SÌ',
        'pt': 'SIM',
        'ja': 'オン'
    },
    'off': {
        'tr': 'KAPALI',
        'en': 'OFF',
        'de': 'AUS',
        'fr': 'NON',
        'es': 'NO',
        'it': 'NO',
        'pt': 'NÃO',
        'ja': 'オフ'
    },
    'dont_show_again': {
        'tr': 'Bunu bir daha gösterme',
        'en': 'Don\'t show this again',
        'de': 'Nicht mehr anzeigen',
        'fr': 'Ne plus afficher',
        'es': 'No mostrar de nuevo',
        'it': 'Non mostrare più',
        'pt': 'Não mostrar novamente',
        'ja': '次回から表示しない'
    },
    
    # ======================= OYUN İÇİ =======================
    'paused': {
        'tr': 'DURAKLATILDI',
        'en': 'PAUSED',
        'de': 'PAUSIERT',
        'fr': 'PAUSE',
        'es': 'PAUSADO',
        'it': 'IN PAUSA',
        'pt': 'PAUSADO',
        'ja': '一時停止'
    },
    'resume': {
        'tr': 'Devam Et',
        'en': 'Resume',
        'de': 'Fortsetzen',
        'fr': 'Reprendre',
        'es': 'Continuar',
        'it': 'Riprendi',
        'pt': 'Continuar',
        'ja': '再開'
    },
    'main_menu': {
        'tr': 'Ana Menü',
        'en': 'Main Menu',
        'de': 'Hauptmenü',
        'fr': 'Menu Principal',
        'es': 'Menú Principal',
        'it': 'Menu Principale',
        'pt': 'Menu Principal',
        'ja': 'メインメニュー'
    },
    'restart': {
        'tr': 'Yeniden Başla',
        'en': 'Restart',
        'de': 'Neustart',
        'fr': 'Recommencer',
        'es': 'Reiniciar',
        'it': 'Ricomincia',
        'pt': 'Reiniciar',
        'ja': 'リスタート',
        'zh': '重新开始',
        'ko': '다시 시작'
    },
    'game_over': {
        'tr': 'OYUN BİTTİ',
        'en': 'GAME OVER',
        'de': 'SPIEL VORBEI',
        'fr': 'FIN DE PARTIE',
        'es': 'FIN DEL JUEGO',
        'it': 'GAME OVER',
        'pt': 'FIM DE JOGO',
        'ja': 'ゲームオーバー',
        'zh': '游戏结束',
        'ko': '게임 오버'
    },
    'score': {
        'tr': 'Skor',
        'en': 'Score',
        'de': 'Punkte',
        'fr': 'Score',
        'es': 'Puntos',
        'it': 'Punteggio',
        'pt': 'Pontuação',
        'ja': 'スコア',
        'zh': '分数',
        'ko': '점수'
    },
    'level': {
        'tr': 'Seviye',
        'en': 'Level',
        'de': 'Level',
        'fr': 'Niveau',
        'es': 'Nivel',
        'it': 'Livello',
        'pt': 'Nível',
        'ja': 'レベル',
        'zh': '等级',
        'ko': '레벨'
    },
    'lines': {
        'tr': 'Satır',
        'en': 'Lines',
        'de': 'Zeilen',
        'fr': 'Lignes',
        'es': 'Líneas',
        'it': 'Righe',
        'pt': 'Linhas',
        'ja': 'ライン',
        'zh': '行数',
        'ko': '라인'
    },
    'time': {
        'tr': 'Süre',
        'en': 'Time',
        'de': 'Zeit',
        'fr': 'Temps',
        'es': 'Tiempo',
        'it': 'Tempo',
        'pt': 'Tempo',
        'ja': '時間',
        'zh': '时间',
        'ko': '시간'
    },
    'time_left': {
        'tr': 'Kalan',
        'en': 'Remaining',
        'de': 'Verbleibend',
        'fr': 'Restant',
        'es': 'Restante',
        'it': 'Rimanente',
        'pt': 'Restante',
        'ja': '残り',
        'zh': '剩余',
        'ko': '남은'
    },
    'combo': {
        'tr': 'Kombo',
        'en': 'Combo',
        'de': 'Kombo',
        'fr': 'Combo',
        'es': 'Combo',
        'it': 'Combo',
        'pt': 'Combo',
        'ja': 'コンボ',
        'zh': '连击',
        'ko': '콤보'
    },
    'next': {
        'tr': 'Sıradaki:',
        'en': 'Next:',
        'de': 'Nächstes:',
        'fr': 'Suivant:',
        'es': 'Siguiente:',
        'it': 'Prossimo:',
        'pt': 'Próximo:',
        'ja': '次:',
        'zh': '下一个:',
        'ko': '다음:'
    },
    'hold': {
        'tr': 'Saklanan (C):',
        'en': 'Hold (C):',
        'de': 'Halten (C):',
        'fr': 'Réserve (C):',
        'es': 'Guardar (C):',
        'it': 'Riserva (C):',
        'pt': 'Reserva (C):',
        'ja': 'ホールド (C):',
        'zh': '保留 (C):',
        'ko': '홀드 (C):'
    },
    'hud_key_uses': {
        'tr': '{label}: {count}',
        'en': '{label}: {count}',
        'de': '{label}: {count}',
        'fr': '{label}: {count}',
        'es': '{label}: {count}',
        'it': '{label}: {count}',
        'pt': '{label}: {count}',
        'ja': '{label}: {count}',
        'zh': '{label}: {count}',
        'ko': '{label}: {count}'
    },
    'hold_2': {
        'tr': 'Saklanan 2 (V):',
        'en': 'Hold 2 (V):',
        'de': 'Halten 2 (V):',
        'fr': 'Réserve 2 (V):',
        'es': 'Guardar 2 (V):',
        'it': 'Riserva 2 (V):',
        'pt': 'Reserva 2 (V):',
        'ja': 'ホールド2 (V):',
        'zh': '保留2 (V):',
        'ko': '홀드 2 (V):'
    },
    'controls': {
        'tr': 'Kontroller',
        'en': 'Controls',
        'de': 'Steuerung',
        'fr': 'Contrôles',
        'es': 'Controles',
        'it': 'Controlli',
        'pt': 'Controles',
        'ja': '操作',
        'zh': '操作',
        'ko': '조작'
    },
    'move': {
        'tr': 'Hareket',
        'en': 'Move',
        'de': 'Bewegen',
        'fr': 'Déplacer',
        'es': 'Mover',
        'it': 'Muovi',
        'pt': 'Mover',
        'ja': '移動',
        'zh': '移动',
        'ko': '이동'
    },
    'rotate': {
        'tr': 'Döndür',
        'en': 'Rotate',
        'de': 'Drehen',
        'fr': 'Tourner',
        'es': 'Rotar',
        'it': 'Ruota',
        'pt': 'Girar',
        'ja': '回転',
        'zh': '旋转',
        'ko': '회전'
    },
    'soft_drop': {
        'tr': 'Yavaş Düşür',
        'en': 'Soft Drop',
        'de': 'Langsam fallen',
        'fr': 'Descente lente',
        'es': 'Caída lenta',
        'it': 'Caduta lenta',
        'pt': 'Queda lenta',
        'ja': 'ソフトドロップ',
        'zh': '软降',
        'ko': '소프트 드롭'
    },
    'hard_drop': {
        'tr': 'Sert Düşür',
        'en': 'Hard Drop',
        'de': 'Schnell fallen',
        'fr': 'Descente rapide',
        'es': 'Caída rápida',
        'it': 'Caduta rapida',
        'pt': 'Queda rápida',
        'ja': 'ハードドロップ',
        'zh': '硬降',
        'ko': '하드 드롭'
    },
    'pause': {
        'tr': 'Duraklat',
        'en': 'Pause',
        'de': 'Pause',
        'fr': 'Pause',
        'es': 'Pausa',
        'it': 'Pausa',
        'pt': 'Pausar',
        'ja': '一時停止',
        'zh': '暂停',
        'ko': '일시정지'
    },
    
    # ======================= PAUSE MENÜ =======================
    'pause_hint': {
        'tr': 'Yukarı/Aşağı Seç   Sol/Sağ Ayarla   Enter Onayla   P Devam   Mouse: Tıkla/Wheel',
        'en': 'Up/Down Select   Left/Right Adjust   Enter Confirm   P Resume   Mouse: Click/Wheel',
        'de': 'Auf/Ab Auswählen   Links/Rechts Anpassen   Enter Bestätigen   P Fortsetzen   Maus: Klick/Rad',
        'fr': 'Haut/Bas Sélectionner   Gauche/Droite Ajuster   Entrée Confirmer   P Reprendre   Souris: Clic/Molette',
        'es': 'Arriba/Abajo Seleccionar   Izq/Der Ajustar   Enter Confirmar   P Continuar   Ratón: Clic/Rueda',
        'it': 'Su/Giù Seleziona   Sinistra/Destra Regola   Invio Conferma   P Riprendi   Mouse: Clic/Rotella',
        'pt': 'Cima/Baixo Selecionar   Esq/Dir Ajustar   Enter Confirmar   P Continuar   Mouse: Clique/Roda',
        'ja': '上下: 選択   左右: 調整   Enter: 決定   P: 再開   マウス: クリック/ホイール',
        'zh': '上下: 选择   左右: 调整   Enter: 确认   P: 继续   鼠标: 点击/滚轮',
        'ko': '위/아래: 선택   좌/우: 조절   Enter: 확인   P: 계속   마우스: 클릭/휠'
    },
    
    # ======================= ÇIKIŞ ONAYI =======================
    'quit_confirm_title': {
        'tr': 'Ana menüye dönmek istiyor musun?',
        'en': 'Return to main menu?',
        'de': 'Zurück zum Hauptmenü?',
        'fr': 'Retourner au menu principal?',
        'es': '¿Volver al menú principal?',
        'it': 'Tornare al menu principale?',
        'pt': 'Voltar ao menu principal?',
        'ja': 'メインメニューに戻りますか？',
        'zh': '返回主菜单吗？',
        'ko': '메인 메뉴로 돌아가시겠습니까?'
    },
    'quit_confirm_message': {
        'tr': 'Oyun sonlandırılacak ve ana menüye döneceksin. Kaydedilmemiş ilerleme kaybolabilir.',
        'en': 'This run will end and you will return to the main menu. Unsaved progress may be lost.',
        'de': 'Dieses Spiel wird beendet und du kehrst zum Hauptmenü zurück. Ungespeicherter Fortschritt kann verloren gehen.',
        'fr': 'Cette partie se terminera et vous retournerez au menu principal. La progression non sauvegardée peut être perdue.',
        'es': 'Esta partida terminará y volverás al menú principal. El progreso no guardado puede perderse.',
        'it': 'Questa partita terminerà e tornerai al menu principale. I progressi non salvati potrebbero andare persi.',
        'pt': 'Esta partida terminará e você voltará ao menu principal. O progresso não salvo pode ser perdido.',
        'ja': 'このプレイは終了し、メインメニューに戻ります。未保存の進行状況が失われる可能性があります。',
        'zh': '本次游戏将结束并返回主菜单。未保存的进度可能会丢失。',
        'ko': '이번 플레이가 종료되고 메인 메뉴로 돌아갑니다. 저장되지 않은 진행 상황이 사라질 수 있습니다.'
    },
    'quit_confirm_yes_label': {
        'tr': 'Evet',
        'en': 'Yes',
        'de': 'Ja',
        'fr': 'Oui',
        'es': 'Sí',
        'it': 'Sì',
        'pt': 'Sim',
        'ja': 'はい',
        'zh': '是',
        'ko': '예'
    },
    'quit_confirm_no_label': {
        'tr': 'Vazgeç',
        'en': 'Cancel',
        'de': 'Abbrechen',
        'fr': 'Annuler',
        'es': 'Cancelar',
        'it': 'Annulla',
        'pt': 'Cancelar',
        'ja': 'キャンセル',
        'zh': '取消',
        'ko': '취소'
    },
    'quit_confirm_select_hint': {
        'tr': 'Seç: Mouse ile tıkla veya klavyeyi kullan',
        'en': 'Select: Click with mouse or use keyboard',
        'de': 'Auswählen: Mit Maus klicken oder Tastatur verwenden',
        'fr': 'Sélectionner: Cliquez avec la souris ou utilisez le clavier',
        'es': 'Seleccionar: Haz clic con el ratón o usa el teclado',
        'it': 'Seleziona: Clicca con il mouse o usa la tastiera',
        'pt': 'Selecionar: Clique com o mouse ou use o teclado',
        'ja': '選択: マウスでクリック、またはキーボードを使用',
        'zh': '选择：用鼠标点击或使用键盘',
        'ko': '선택: 마우스로 클릭하거나 키보드를 사용하세요'
    },
    'exit_confirm_title': {
        'tr': 'OYUNDAN ÇIKILSIN MI?',
        'en': 'QUIT THE GAME?',
        'de': 'SPIEL BEENDEN?',
        'fr': 'QUITTER LE JEU ?',
        'es': '¿SALIR DEL JUEGO?',
        'it': 'USCIRE DAL GIOCO?',
        'pt': 'SAIR DO JOGO?',
        'ja': 'ゲームを終了しますか？',
        'zh': '退出游戏吗？',
        'ko': '게임을 종료하시겠습니까?'
    },
    'exit_confirm_message': {
        'tr': 'Oyun kapanacak. Kaydedilmemiş ilerlemen varsa kaybolabilir.',
        'en': 'The game will close. Unsaved progress may be lost.',
        'de': 'Das Spiel wird beendet. Ungespeicherter Fortschritt kann verloren gehen.',
        'fr': 'Le jeu va se fermer. La progression non sauvegardée peut être perdue.',
        'es': 'El juego se cerrará. El progreso no guardado puede perderse.',
        'it': 'Il gioco si chiuderà. I progressi non salvati potrebbero andare persi.',
        'pt': 'O jogo será encerrado. O progresso não salvo pode ser perdido.',
        'ja': 'ゲームを終了します。未保存の進行状況が失われる可能性があります。',
        'zh': '游戏将关闭。未保存的进度可能会丢失。',
        'ko': '게임이 종료됩니다. 저장되지 않은 진행 상황이 사라질 수 있습니다.'
    },
    'yes': {
        'tr': 'Evet (ENTER)',
        'en': 'Yes (ENTER)',
        'de': 'Ja (ENTER)',
        'fr': 'Oui (ENTRÉE)',
        'es': 'Sí (ENTER)',
        'it': 'Sì (INVIO)',
        'pt': 'Sim (ENTER)',
        'ja': 'はい (ENTER)',
        'zh': '是 (ENTER)',
        'ko': '예 (ENTER)'
    },
    'no': {
        'tr': 'Hayır (ESC)',
        'en': 'No (ESC)',
        'de': 'Nein (ESC)',
        'fr': 'Non (ÉCHAP)',
        'es': 'No (ESC)',
        'it': 'No (ESC)',
        'pt': 'Não (ESC)',
        'ja': 'いいえ (ESC)',
        'zh': '否 (ESC)',
        'ko': '아니오 (ESC)'
    },
    'quit_hint': {
        'tr': 'ENTER / Y : Çık   |   ESC / N : İptal',
        'en': 'ENTER / Y : Quit   |   ESC / N : Cancel',
        'de': 'ENTER / Y : Beenden   |   ESC / N : Abbrechen',
        'fr': 'ENTRÉE / O : Quitter   |   ÉCHAP / N : Annuler',
        'es': 'ENTER / S : Salir   |   ESC / N : Cancelar',
        'it': 'INVIO / S : Esci   |   ESC / N : Annulla',
        'pt': 'ENTER / S : Sair   |   ESC / N : Cancelar',
        'ja': 'ENTER / Y : 終了   |   ESC / N : キャンセル',
        'zh': 'ENTER / Y : 退出   |   ESC / N : 取消',
        'ko': 'ENTER / Y : 종료   |   ESC / N : 취소'
    },
    
    # ======================= GAME OVER =======================
    'new_high_score': {
        'tr': 'YENİ REKOR!',
        'en': 'NEW HIGH SCORE!',
        'de': 'NEUER HIGHSCORE!',
        'fr': 'NOUVEAU RECORD!',
        'es': '¡NUEVO RÉCORD!',
        'it': 'NUOVO RECORD!',
        'pt': 'NOVO RECORDE!',
        'ja': '新記録！',
        'zh': '新纪录！',
        'ko': '신기록!'
    },
    'final_score': {
        'tr': 'Final Skor',
        'en': 'Final Score',
        'de': 'Endpunktzahl',
        'fr': 'Score Final',
        'es': 'Puntuación Final',
        'it': 'Punteggio Finale',
        'pt': 'Pontuação Final',
        'ja': '最終スコア',
        'zh': '最终得分',
        'ko': '최종 점수'
    },
    'play_again': {
        'tr': 'Tekrar Oyna',
        'en': 'Play Again',
        'de': 'Nochmal spielen',
        'fr': 'Rejouer',
        'es': 'Jugar de Nuevo',
        'it': 'Gioca Ancora',
        'pt': 'Jogar Novamente',
        'ja': 'もう一度',
        'zh': '再玩一次',
        'ko': '다시 하기'
    },
    'press_enter_restart': {
        'tr': 'Yeniden başlamak için ENTER',
        'en': 'Press ENTER to restart',
        'de': 'ENTER zum Neustarten',
        'fr': 'Appuyez sur ENTRÉE pour recommencer',
        'es': 'Presiona ENTER para reiniciar',
        'it': 'Premi INVIO per ricominciare',
        'pt': 'Pressione ENTER para reiniciar',
        'ja': 'ENTERで再開',
        'zh': '按 ENTER 重新开始',
        'ko': 'ENTER를 눌러 재시작'
    },
    'press_esc_menu': {
        'tr': 'Menü için ESC',
        'en': 'Press ESC for menu',
        'de': 'ESC für Menü',
        'fr': 'ÉCHAP pour le menu',
        'es': 'ESC para el menú',
        'it': 'ESC per il menu',
        'pt': 'ESC para o menu',
        'ja': 'ESCでメニュー',
        'zh': '按 ESC 进入菜单',
        'ko': 'ESC를 눌러 메뉴'
    },
    
    # ======================= HİGH SCORES =======================
    'high_scores': {
        'tr': 'Yüksek Skorlar',
        'en': 'High Scores',
        'de': 'Bestenliste',
        'fr': 'Meilleurs Scores',
        'es': 'Mejores Puntuaciones',
        'it': 'Punteggi Migliori',
        'pt': 'Melhores Pontuações',
        'ja': 'ハイスコア',
        'zh': '高分榜',
        'ko': '하이스코어'
    },
    'high_scores_title': {
        'tr': 'EN YÜKSEK SKORLAR',
        'en': 'HIGH SCORES',
        'de': 'BESTENLISTE',
        'fr': 'MEILLEURS SCORES',
        'es': 'MEJORES PUNTUACIONES',
        'it': 'MIGLIORI PUNTEGGI',
        'pt': 'MELHORES PONTUAÇÕES',
        'ja': 'ハイスコア',
        'zh': '最高分',
        'ko': '최고 점수'
    },
    'high_scores_hint': {
        'tr': '↑ ↓ : Kaydır  |  ESC : Geri',
        'en': '↑ ↓ : Scroll  |  ESC : Back',
        'de': '↑ ↓ : Scrollen  |  ESC : Zurück',
        'fr': '↑ ↓ : Défiler  |  ÉCHAP : Retour',
        'es': '↑ ↓ : Desplazar  |  ESC : Atrás',
        'it': '↑ ↓ : Scorri  |  ESC : Indietro',
        'pt': '↑ ↓ : Rolar  |  ESC : Voltar',
        'ja': '↑ ↓ : スクロール  |  ESC : 戻る',
        'zh': '↑ ↓ : 滚动  |  ESC : 返回',
        'ko': '↑ ↓ : 스크롤  |  ESC : 뒤로'
    },
    'rank': {
        'tr': 'Sıra',
        'en': 'Rank',
        'de': 'Rang',
        'fr': 'Rang',
        'es': 'Rango',
        'it': 'Posizione',
        'pt': 'Posição',
        'ja': '順位',
        'zh': '排名',
        'ko': '순위'
    },
    'player': {
        'tr': 'Oyuncu',
        'en': 'Player',
        'de': 'Spieler',
        'fr': 'Joueur',
        'es': 'Jugador',
        'it': 'Giocatore',
        'pt': 'Jogador',
        'ja': 'プレイヤー',
        'zh': '玩家',
        'ko': '플레이어'
    },
    'date': {
        'tr': 'Tarih',
        'en': 'Date',
        'de': 'Datum',
        'fr': 'Date',
        'es': 'Fecha',
        'it': 'Data',
        'pt': 'Data',
        'ja': '日付',
        'zh': '日期',
        'ko': '날짜'
    },
    
    # ======================= BAŞARILAR =======================
    'achievements': {
        'tr': 'Başarılar',
        'en': 'Achievements',
        'de': 'Erfolge',
        'fr': 'Succès',
        'es': 'Logros',
        'it': 'Obiettivi',
        'pt': 'Conquistas',
        'ja': '実績',
        'zh': '成就',
        'ko': '업적'
    },
    'achievement_unlocked': {
        'tr': 'Başarım Açıldı!',
        'en': 'Achievement Unlocked!',
        'de': 'Erfolg freigeschaltet!',
        'fr': 'Succès débloqué!',
        'es': '¡Logro desbloqueado!',
        'it': 'Obiettivo sbloccato!',
        'pt': 'Conquista desbloqueada!',
        'ja': '実績解除！',
        'zh': '成就解锁！',
        'ko': '업적 달성!'
    },
    'locked': {
        'tr': 'Kilitli',
        'en': 'Locked',
        'de': 'Gesperrt',
        'fr': 'Verrouillé',
        'es': 'Bloqueado',
        'it': 'Bloccato',
        'pt': 'Bloqueado',
        'ja': 'ロック中',
        'zh': '未解锁',
        'ko': '잠김'
    },
    
    # ======================= TUTORIAL =======================
    'tutorial_welcome_title': {
        'tr': 'QUADRIX EĞİTİMİ',
        'en': 'QUADRIX TUTORIAL',
        'ja': 'テトリスチュートリアル',
        'zh': '俄罗斯方块教程',
        'ko': '테트리스 튜토리얼'
    },
    'tutorial_welcome_desc': {
        'tr': 'Quadrix\'e hoş geldin! Temel kontrolleri öğrenmek ister misin?',
        'en': 'Welcome to Quadrix! Would you like to learn the basic controls?',
        'ja': 'テトリスへようこそ！基本操作を学びますか？',
        'zh': '欢迎来到俄罗斯方块！想学习基础操作吗？',
        'ko': '테트리스에 오신 것을 환영합니다! 기본 조작을 배워볼까요?'
    },
    'tutorial_welcome_move': {
        'tr': 'Hareket kontrollerini öğrenelim!',
        'en': 'Let\'s learn movement controls!',
        'ja': '移動操作を学びましょう！',
        'zh': '让我们学习移动操作！',
        'ko': '이동 조작을 배워봅시다!'
    },
    'tutorial_welcome_rotate': {
        'tr': 'Şimdi parçaları döndürmeyi öğrenelim!',
        'en': 'Now let\'s learn to rotate pieces!',
        'ja': '次は回転を学びましょう！',
        'zh': '现在学习旋转方块！',
        'ko': '이제 회전을 배워봅시다!'
    },
    'tutorial_welcome_soft_drop': {
        'tr': 'Hızlı düşürme tekniğini deneyelim!',
        'en': 'Let\'s try soft drop!',
        'ja': 'ソフトドロップを試しましょう！',
        'zh': '试试软降吧！',
        'ko': '소프트 드롭을 해볼까요!'
    },
    'tutorial_welcome_hard_drop': {
        'tr': 'Anında düşürme özelliğini kullanalım!',
        'en': 'Let\'s use hard drop!',
        'ja': 'ハードドロップを使いましょう！',
        'zh': '使用硬降吧！',
        'ko': '하드 드롭을 사용해봅시다!'
    },
    'tutorial_welcome_line_clear': {
        'tr': 'Satır temizleme zamanı!',
        'en': 'Time to clear a line!',
        'ja': 'ライン消去の時間！',
        'zh': '该清行了！',
        'ko': '줄을 지울 시간!'
    },
    'tutorial_welcome_hold': {
        'tr': 'Parça saklama özelliğini keşfedelim!',
        'en': 'Let\'s explore hold!',
        'ja': 'ホールド機能を試しましょう！',
        'zh': '来试试保留功能！',
        'ko': '홀드 기능을 알아봅시다!'
    },
    'tutorial_welcome_complete': {
        'tr': 'Tebrikler! Eğitimi tamamladınız!',
        'en': 'Congratulations! You completed the tutorial!',
        'ja': 'おめでとう！チュートリアル完了！',
        'zh': '恭喜！你完成了教程！',
        'ko': '축하합니다! 튜토리얼을 완료했습니다!'
    },
    'tutorial_sub_move': {
        'tr': 'Sol: {left}/3  Sağ: {right}/3',
        'en': 'Left: {left}/3  Right: {right}/3',
        'ja': '左: {left}/3  右: {right}/3',
        'zh': '左: {left}/3  右: {right}/3',
        'ko': '왼쪽: {left}/3  오른쪽: {right}/3'
    },
    'tutorial_sub_rotate': {
        'tr': 'Döndürme: {count}/{target}',
        'en': 'Rotate: {count}/{target}',
        'ja': '回転: {count}/{target}',
        'zh': '旋转: {count}/{target}',
        'ko': '회전: {count}/{target}'
    },
    'tutorial_sub_soft_drop': {
        'tr': 'AŞAĞI tuşunu basılı tut ({progress}/{target})',
        'en': 'Hold DOWN ({progress}/{target})',
        'ja': '[下] を押し続ける ({progress}/{target})',
        'zh': '按住[下]（{progress}/{target}）',
        'ko': '[아래]를 누른 채 유지 ({progress}/{target})'
    },
    'tutorial_sub_hard_drop': {
        'tr': 'BOŞLUK tuşuna bas',
        'en': 'Press SPACE',
        'ja': '[スペース] を押す',
        'zh': '按下[空格]',
        'ko': '[스페이스]를 누르세요'
    },
    'tutorial_sub_line_clear': {
        'tr': 'Satırı temizle',
        'en': 'Clear a line',
        'ja': 'ラインを消す',
        'zh': '清除一行',
        'ko': '줄을 지우세요'
    },
    'tutorial_sub_hold': {
        'tr': 'C tuşuna bas',
        'en': 'Press C',
        'ja': '[C] を押す',
        'zh': '按下[C]',
        'ko': '[C]를 누르세요'
    },
    'tutorial_sub_finish': {
        'tr': 'ENTER tuşuna bas',
        'en': 'Press ENTER',
        'ja': '[ENTER] を押す',
        'zh': '按下[ENTER]',
        'ko': '[ENTER]를 누르세요'
    },
    'tutorial_tip_title': {
        'tr': 'TAVSİYE',
        'en': 'TIP',
        'ja': 'ヒント',
        'zh': '提示',
        'ko': '팁'
    },
    'tutorial_tip_step_1': {
        'tr': 'Önce sola, sonra sağa hareket et. Kenar kontrolü oyunun temeli.',
        'en': 'Move left first, then right. Edge control is the core skill.',
        'ja': 'まず左、次に右へ移動。端のコントロールが基本です。',
        'zh': '先向左，再向右移动。边缘控制是基础。',
        'ko': '먼저 왼쪽, 다음 오른쪽으로 이동하세요. 가장자리 컨트롤이 기본입니다.'
    },
    'tutorial_tip_step_2': {
        'tr': 'Döndürmeden önce boşluğu oku. Erken dönüş hatayı azaltır.',
        'en': 'Read the gap before rotating. Early rotation reduces mistakes.',
        'ja': '回転前に隙間を確認。早めの回転でミスを減らせます。',
        'zh': '旋转前先看空位。提前旋转可减少失误。',
        'ko': '회전 전에 빈칸을 확인하세요. 빠른 회전이 실수를 줄입니다.'
    },
    'tutorial_tip_step_3': {
        'tr': 'Yumuşak düşürmeyi kısa kontrollü basışlarla kullan; kilitlemeden yer ayarla.',
        'en': 'Use soft drop with short controlled presses to fine-tune placement.',
        'ja': 'ソフトドロップは短く調整しながら使い、配置を整えましょう。',
        'zh': '用短促可控的软降微调位置，再决定落点。',
        'ko': '소프트 드롭을 짧고 정확하게 써서 위치를 미세 조정하세요.'
    },
    'tutorial_tip_step_4': {
        'tr': 'Sert düşürme geri alınmaz. Hattı net gördüğünde kullan.',
        'en': 'Hard drop cannot be undone. Use it when the landing is clear.',
        'ja': 'ハードドロップは取り消せません。着地が確実な時に使いましょう。',
        'zh': '硬降不可撤销。确认落点后再使用。',
        'ko': '하드 드롭은 되돌릴 수 없습니다. 착지 위치가 확실할 때 사용하세요.'
    },
    'tutorial_tip_step_5': {
        'tr': 'Boşluğu tek hamlede kapatıp satır temizlemeye odaklan.',
        'en': 'Close the gap in one move and focus on clearing the line.',
        'ja': '1手で隙間を埋めてライン消去に集中しましょう。',
        'zh': '一手补齐空位，专注清行。',
        'ko': '한 번에 빈칸을 메우고 줄 지우기에 집중하세요.'
    },
    'tutorial_tip_step_6': {
        'tr': 'Hold, yanlış parçayı saklayıp doğru parçayı beklemek içindir.',
        'en': 'Use Hold to stash a bad piece and wait for a better one.',
        'ja': 'ホールドは不要なピースを保留し、良いピースを待つために使います。',
        'zh': 'Hold 用于暂存不合适的方块，等待更好的方块。',
        'ko': '홀드는 맞지 않는 블록을 보관하고 더 좋은 블록을 기다릴 때 씁니다.'
    },
    'tutorial_tip_step_7': {
        'tr': 'Temeller tamam. Şimdi ritim ve temiz yerleşimle devam et.',
        'en': 'Basics complete. Keep rhythm and place pieces cleanly.',
        'ja': '基礎は完了。リズム良く、丁寧に配置していきましょう。',
        'zh': '基础已完成。保持节奏并稳定摆放。',
        'ko': '기본 완료. 리듬을 유지하고 깔끔하게 배치하세요.'
    },
    'tutorial_success_1': {
        'tr': 'Mükemmel!',
        'en': 'Perfect!',
        'ja': 'パーフェクト！',
        'zh': '完美！',
        'ko': '완벽해요!'
    },
    'tutorial_success_2': {
        'tr': 'Harika!',
        'en': 'Great!',
        'ja': 'すばらしい！',
        'zh': '太棒了！',
        'ko': '훌륭해요!'
    },
    'tutorial_success_3': {
        'tr': 'Süper!',
        'en': 'Awesome!',
        'ja': '最高！',
        'zh': '厉害！',
        'ko': '최고예요!'
    },
    'tutorial_success_4': {
        'tr': 'Bravo!',
        'en': 'Bravo!',
        'ja': 'ブラボー！',
        'zh': '棒极了！',
        'ko': '브라보!'
    },
    'tutorial_success_5': {
        'tr': 'Tebrikler!',
        'en': 'Congrats!',
        'ja': 'おめでとう！',
        'zh': '恭喜！',
        'ko': '축하해요!'
    },
    'tutorial_success_6': {
        'tr': 'Başarılı!',
        'en': 'Success!',
        'ja': '成功！',
        'zh': '成功！',
        'ko': '성공!'
    },
    'tutorial_step_done_move': {
        'tr': 'Hareket Öğrenildi!',
        'en': 'Movement Learned!',
        'ja': '移動を習得！',
        'zh': '已学会移动！',
        'ko': '이동을 배웠어요!'
    },
    'tutorial_step_done_rotate': {
        'tr': 'Döndürme Öğrenildi!',
        'en': 'Rotation Learned!',
        'ja': '回転を習得！',
        'zh': '已学会旋转！',
        'ko': '회전을 배웠어요!'
    },
    'tutorial_step_done_soft_drop': {
        'tr': 'Yumuşak Düşürme Öğrenildi!',
        'en': 'Soft Drop Learned!',
        'ja': 'ソフトドロップを習得！',
        'zh': '已学会软降！',
        'ko': '소프트 드롭을 배웠어요!'
    },
    'tutorial_step_done_hard_drop': {
        'tr': 'Sert Düşürme Öğrenildi!',
        'en': 'Hard Drop Learned!',
        'ja': 'ハードドロップを習得！',
        'zh': '已学会硬降！',
        'ko': '하드 드롭을 배웠어요!'
    },
    'tutorial_step_done_line_clear': {
        'tr': 'Satır Temizleme Öğrenildi!',
        'en': 'Line Clear Learned!',
        'ja': 'ライン消去を習得！',
        'zh': '已学会清行！',
        'ko': '줄 지우기를 배웠어요!'
    },
    'tutorial_step_done_hold': {
        'tr': 'Parça Saklama Öğrenildi!',
        'en': 'Hold Learned!',
        'ja': 'ホールドを習得！',
        'zh': '已学会保留！',
        'ko': '홀드를 배웠어요!'
    },
    'tutorial_step_done_generic': {
        'tr': 'Adım Tamamlandı!',
        'en': 'Step Complete!',
        'ja': 'ステップ完了！',
        'zh': '步骤完成！',
        'ko': '단계 완료!'
    },
    'tutorial_success_move_right': {
        'tr': 'Sağ hareket!',
        'en': 'Move right!',
        'zh': '向右移动！',
        'ko': '오른쪽으로 이동!'
    },
    'tutorial_success_rotate': {
        'tr': 'Güzel döndürme!',
        'en': 'Nice rotation!',
        'zh': '漂亮的旋转！',
        'ko': '좋은 회전!'
    },
    'tutorial_success_hard_drop': {
        'tr': 'Sert düşürme başarılı!',
        'en': 'Hard drop success!',
        'zh': '硬降成功！',
        'ko': '하드 드롭 성공!'
    },
    'tutorial_success_hold': {
        'tr': 'Parça saklama başarılı!',
        'en': 'Hold success!',
        'zh': '保留成功！',
        'ko': '홀드 성공!'
    },
    'tutorial_success_line_clear': {
        'tr': 'Satır temizlendi!',
        'en': 'Line cleared!',
        'zh': '已清除一行！',
        'ko': '줄이 지워졌어요!'
    },
    'play_tutorial': {
        'tr': 'Eğitimi Oyna',
        'en': 'Play Tutorial',
        'zh': '开始教程',
        'ko': '튜토리얼 플레이'
    },
    'skip_tutorial': {
        'tr': 'Atla',
        'en': 'Skip',
        'ja': 'スキップ',
        'zh': '跳过',
        'ko': '건너뛰기'
    },
    'tutorial_step_1': {
        'tr': 'Hareket etmek için [SOL] ve [SAĞ] ok tuşlarını kullan.',
        'en': 'Use [LEFT] and [RIGHT] arrow keys to move.',
        'ja': '[左] と [右] 矢印キーで移動します。',
        'zh': '使用[左]和[右]方向键移动。',
        'ko': '[왼쪽]과 [오른쪽] 방향키로 이동하세요.'
    },
    'tutorial_step_2': {
        'tr': 'Parçayı döndürmek için [YUKARI] ok tuşuna bas.',
        'en': 'Press [UP] arrow key to rotate.',
        'ja': '[上] 矢印キーで回転します。',
        'zh': '按[上]方向键旋转。',
        'ko': '[위] 방향키로 회전하세요.'
    },
    'tutorial_step_3': {
        'tr': 'Daha hızlı düşmek için [AŞAĞI] tuşuna basılı tut.',
        'en': 'Hold [DOWN] to drop faster (Soft Drop).',
        'ja': '[下] を押し続けて速く落とします（ソフトドロップ）。',
        'zh': '按住[下]可更快下落（软降）。',
        'ko': '[아래]를 누르고 있으면 더 빨리 떨어집니다(소프트 드롭).'
    },
    'tutorial_step_4': {
        'tr': 'Parçayı anında kilitlemek için [BOŞLUK] tuşuna bas.',
        'en': 'Press [SPACE] to lock instantly (Hard Drop).',
        'ja': '[スペース] で即時に固定します（ハードドロップ）。',
        'zh': '按[空格]可立即锁定（硬降）。',
        'ko': '[스페이스]를 누르면 즉시 고정됩니다(하드 드롭).'
    },
    'tutorial_step_5': {
        'tr': 'Satırları doldurarak yok et! I parçasını boşluğa yerleştir.',
        'en': 'Clear lines by filling them! Place the I-piece in the gap.',
        'ja': 'ラインを埋めて消しましょう！Iピースを空きに入れてください。',
        'zh': '填满并消除行！把 I 形方块放到空隙里。',
        'ko': '줄을 채워 지워보세요! I 블록을 빈칸에 넣으세요.'
    },
    'tutorial_step_6': {
        'tr': 'Bu parçayı saklamak için [{hold_key}] tuşuna bas.',
        'en': 'Press [{hold_key}] to hold this piece.',
        'ja': 'このピースをホールドするには [{hold_key}] を押します。',
        'zh': '按[{hold_key}]保留这个方块。',
        'ko': '이 블록을 홀드하려면 [{hold_key}]를 누르세요.'
    },
    'tutorial_complete': {
        'tr': 'Harika! Artık oynamaya hazırsın. İyi eğlenceler!',
        'en': 'Great! You are ready to play. Have fun!',
        'ja': '素晴らしい！プレイの準備ができました。楽しんで！',
        'zh': '太棒了！你已经准备好开始游戏了。祝你玩得开心！',
        'ko': '좋아요! 이제 플레이할 준비가 되었어요. 즐거운 시간 보내세요!'
    },
    'tutorial_progress': {
        'tr': 'Hedef: {}/{}',
        'en': 'Goal: {}/{}',
        'ja': '目標: {}/{}',
        'zh': '目标: {}/{}',
        'ko': '목표: {}/{}'
    },
    'tutorial_mode': {
        'tr': 'Eğitim',
        'en': 'Tutorial',
        'ja': 'チュートリアル',
        'zh': '教程',
        'ko': '튜토리얼'
    },
    'unlocked': {
        'tr': 'Açıldı',
        'en': 'Unlocked',
        'de': 'Freigeschaltet',
        'fr': 'Débloqué',
        'es': 'Desbloqueado',
        'it': 'Sbloccato',
        'pt': 'Desbloqueado',
        'ja': '解放済み',
        'zh': '已解锁',
        'ko': '잠금 해제'
    },
    
    # ======================= PVP =======================
    'player_1': {
        'tr': 'Oyuncu 1',
        'en': 'Player 1',
        'de': 'Spieler 1',
        'fr': 'Joueur 1',
        'es': 'Jugador 1',
        'it': 'Giocatore 1',
        'pt': 'Jogador 1',
        'ja': 'プレイヤー1',
        'zh': '玩家1',
        'ko': '플레이어 1'
    },
    'player_2': {
        'tr': 'Oyuncu 2',
        'en': 'Player 2',
        'de': 'Spieler 2',
        'fr': 'Joueur 2',
        'es': 'Jugador 2',
        'it': 'Giocatore 2',
        'pt': 'Jogador 2',
        'ja': 'プレイヤー2',
        'zh': '玩家2',
        'ko': '플레이어 2'
    },
    'player_1_wins': {
        'tr': 'OYUNCU 1 KAZANDI!',
        'en': 'PLAYER 1 WINS!',
        'de': 'SPIELER 1 GEWINNT!',
        'fr': 'LE JOUEUR 1 GAGNE!',
        'es': '¡JUGADOR 1 GANA!',
        'it': 'GIOCATORE 1 VINCE!',
        'pt': 'JOGADOR 1 VENCE!',
        'ja': 'プレイヤー1の勝ち！',
        'zh': '玩家1获胜！',
        'ko': '플레이어 1 승리!'
    },
    'player_2_wins': {
        'tr': 'OYUNCU 2 KAZANDI!',
        'en': 'PLAYER 2 WINS!',
        'de': 'SPIELER 2 GEWINNT!',
        'fr': 'LE JOUEUR 2 GAGNE!',
        'es': '¡JUGADOR 2 GANA!',
        'it': 'GIOCATORE 2 VINCE!',
        'pt': 'JOGADOR 2 VENCE!',
        'ja': 'プレイヤー2の勝ち！',
        'zh': '玩家2获胜！',
        'ko': '플레이어 2 승리!'
    },
    'draw': {
        'tr': 'BERABERE!',
        'en': 'DRAW!',
        'de': 'UNENTSCHIEDEN!',
        'fr': 'ÉGALITÉ!',
        'es': '¡EMPATE!',
        'it': 'PAREGGIO!',
        'pt': 'EMPATE!',
        'ja': '引き分け！',
        'zh': '平局！',
        'ko': '무승부!'
    },
    'vs': {
        'tr': 'VS',
        'en': 'VS',
        'de': 'VS',
        'fr': 'VS',
        'es': 'VS',
        'it': 'VS',
        'pt': 'VS',
        'ja': 'VS',
        'zh': 'VS',
        'ko': 'VS'
    },
    
    # ======================= MODLAR =======================
    'classic_mode': {
        'tr': 'Klasik Mod',
        'en': 'Classic Mode',
        'de': 'Klassischer Modus',
        'fr': 'Mode Classique',
        'es': 'Modo Clásico',
        'it': 'Modalità Classica',
        'pt': 'Modo Clássico',
        'ja': 'クラシックモード',
        'zh': '经典模式',
        'ko': '클래식 모드'
    },
    'mystery_mode': {
        'tr': 'Kart Ustalığı',
        'en': 'Card Mastery',
        'de': 'Kartenmeister',
        'fr': 'Maîtrise des Cartes',
        'es': 'Maestría de Cartas',
        'it': 'Maestria delle Carte',
        'pt': 'Maestria de Cartas',
        'ja': 'カードマスタリー',
        'zh': '卡牌大师',
        'ko': '카드 마스터리'
    },
    'zen_mode': {
        'tr': 'Zen Modu',
        'en': 'Zen Mode',
        'de': 'Zen-Modus',
        'fr': 'Mode Zen',
        'es': 'Modo Zen',
        'it': 'Modalità Zen',
        'pt': 'Modo Zen',
        'ja': '禅モード',
        'zh': '禅模式',
        'ko': '젠 모드'
    },
    
    # ======================= CAMPAIGN MODE =======================
    'campaign_mode': {
        'tr': 'Görev Modu',
        'en': 'Campaign Mode',
        'de': 'Kampagnenmodus',
        'fr': 'Mode Campagne',
        'es': 'Modo Campaña',
        'it': 'Modalità Campagna',
        'pt': 'Modo Campanha',
        'ja': 'キャンペーンモード',
        'zh': '战役模式',
        'ko': '캠페인 모드'
    },
    'campaign_title': {
        'tr': 'GÖREV MODU',
        'en': 'CAMPAIGN MODE',
        'de': 'KAMPAGNENMODUS',
        'fr': 'MODE CAMPAGNE',
        'es': 'MODO CAMPAÑA',
        'it': 'MODALITÀ CAMPAGNA',
        'pt': 'MODO CAMPANHA',
        'ja': 'キャンペーンモード',
        'zh': '战役模式',
        'ko': '캠페인 모드'
    },
    'campaign_desc': {
        'tr': '100 level macera! Her level biraz daha zor.',
        'en': '100-level adventure! Each level gets tougher.',
        'de': '100-Level-Abenteuer! Jedes Level wird schwieriger.',
        'fr': 'Aventure de 100 niveaux ! Chaque niveau est plus difficile.',
        'es': '¡Aventura de 100 niveles! Cada nivel es más difícil.',
        'it': 'Avventura di 100 livelli! Ogni livello è più difficile.',
        'pt': 'Aventura de 100 níveis! Cada nível fica mais difícil.',
        'ja': '100レベルの冒険！レベルごとに難しくなります。',
        'zh': '100关冒险！每一关都会更难。',
        'ko': '100레벨 모험! 레벨이 올라갈수록 더 어려워집니다.'
    },
    'campaign_progress': {
        'tr': '{current}/{total} {level_label} | {stars} {stars_label}',
        'en': '{current}/{total} {level_label} | {stars} {stars_label}',
        'de': '{current}/{total} {level_label} | {stars} {stars_label}',
        'fr': '{current}/{total} {level_label} | {stars} {stars_label}',
        'es': '{current}/{total} {level_label} | {stars} {stars_label}',
        'it': '{current}/{total} {level_label} | {stars} {stars_label}',
        'pt': '{current}/{total} {level_label} | {stars} {stars_label}',
        'ja': '{current}/{total} {level_label} | {stars} {stars_label}',
        'zh': '{current}/{total} {level_label} | {stars} {stars_label}',
        'ko': '{current}/{total} {level_label} | {stars} {stars_label}'
    },
    'campaign_objectives_title': {
        'tr': 'GÖREVLER',
        'en': 'OBJECTIVES',
        'de': 'ZIELE',
        'fr': 'OBJECTIFS',
        'es': 'OBJETIVOS',
        'it': 'OBIETTIVI',
        'pt': 'OBJETIVOS',
        'ja': '目標',
        'zh': '目标',
        'ko': '목표'
    },
    'campaign_star_conditions_title': {
        'tr': 'YILDIZ KOŞULLARI',
        'en': 'STAR CONDITIONS',
        'de': 'STERNBEDINGUNGEN',
        'fr': 'CONDITIONS D\'ÉTOILES',
        'es': 'CONDICIONES DE ESTRELLAS',
        'it': 'CONDIZIONI DELLE STELLE',
        'pt': 'CONDIÇÕES DE ESTRELAS',
        'ja': '星条件',
        'zh': '星级条件',
        'ko': '별 조건'
    },
    'campaign_stats_title': {
        'tr': 'İSTATİSTİK',
        'en': 'STATS',
        'de': 'STATISTIKEN',
        'fr': 'STATISTIQUES',
        'es': 'ESTADÍSTICAS',
        'it': 'STATISTICHE',
        'pt': 'ESTATÍSTICAS',
        'ja': '統計',
        'zh': '统计',
        'ko': '통계'
    },
    'campaign_rewards_title': {
        'tr': 'ÖDÜLLER',
        'en': 'REWARDS',
        'de': 'BELOHNUNGEN',
        'fr': 'RÉCOMPENSES',
        'es': 'RECOMPENSAS',
        'it': 'RICOMPENSE',
        'pt': 'RECOMPENSAS',
        'ja': '報酬',
        'zh': '奖励',
        'ko': '보상'
    },
    'campaign_next_level_title': {
        'tr': 'SONRAKİ LEVEL',
        'en': 'NEXT LEVEL',
        'de': 'NÄCHSTES LEVEL',
        'fr': 'NIVEAU SUIVANT',
        'es': 'SIGUIENTE NIVEL',
        'it': 'PROSSIMO LIVELLO',
        'pt': 'PRÓXIMO NÍVEL',
        'ja': '次のレベル',
        'zh': '下一关',
        'ko': '다음 레벨'
    },
    'campaign_complete': {
        'tr': 'Kampanya tamamlandı',
        'en': 'Campaign complete',
        'de': 'Kampagne abgeschlossen',
        'fr': 'Campagne terminée',
        'es': 'Campaña completada',
        'it': 'Campagna completata',
        'pt': 'Campanha concluída',
        'ja': 'キャンペーン完了',
        'zh': '战役完成',
        'ko': '캠페인 완료'
    },
    'campaign_footer_controls': {
        'tr': 'ENTER: Devam   ESC: Menü',
        'en': 'ENTER: Continue   ESC: Menu',
        'de': 'ENTER: Fortfahren   ESC: Menü',
        'fr': 'ENTRÉE : Continuer   ÉCHAP : Menu',
        'es': 'ENTER: Continuar   ESC: Menú',
        'it': 'INVIO: Continua   ESC: Menu',
        'pt': 'ENTER: Continuar   ESC: Menu',
        'ja': 'ENTER: 続行   ESC: メニュー',
        'zh': 'ENTER：继续   ESC：菜单',
        'ko': 'ENTER: 계속   ESC: 메뉴'
    },
    'campaign_congrats_title': {
        'tr': 'TEBRİKLER!',
        'en': 'CONGRATS!',
        'de': 'GLÜCKWUNSCH!',
        'fr': 'BRAVO!',
        'es': '¡FELICIDADES!',
        'it': 'COMPLIMENTI!',
        'pt': 'PARABÉNS!',
        'ja': 'おめでとう！',
        'zh': '恭喜！',
        'ko': '축하합니다!'
    },
    'campaign_failed_title': {
        'tr': 'BAŞARISIZ!',
        'en': 'FAILED!',
        'de': 'FEHLGESCHLAGEN!',
        'fr': 'ÉCHOUÉ!',
        'es': '¡FALLIDO!',
        'it': 'FALLITO!',
        'pt': 'FALHOU!',
        'ja': '失敗！',
        'zh': '失败！',
        'ko': '실패!'
    },
    'campaign_failed_hint': {
        'tr': '[R] Tekrar Dene | [ESC] Menü',
        'en': '[R] Retry | [ESC] Menu',
        'de': '[R] Erneut | [ESC] Menü',
        'fr': '[R] Rejouer | [ÉCHAP] Menu',
        'es': '[R] Reintentar | [ESC] Menú',
        'it': '[R] Riprova | [ESC] Menu',
        'pt': '[R] Tentar de novo | [ESC] Menu',
        'ja': '[R] リトライ | [ESC] メニュー',
        'zh': '[R] 重试 | [ESC] 菜单',
        'ko': '[R] 다시 시도 | [ESC] 메뉴'
    },
    'campaign_fail_time': {
        'tr': 'Süre doldu!',
        'en': 'Time is up!',
        'de': 'Zeit abgelaufen!',
        'fr': 'Temps écoulé !',
        'es': '¡Se acabó el tiempo!',
        'it': 'Tempo scaduto!',
        'pt': 'Tempo esgotado!',
        'ja': '時間切れ！',
        'zh': '时间到！',
        'ko': '시간 초과!'
    },
    'campaign_fail_moves': {
        'tr': 'Hamle hakkı bitti!',
        'en': 'No moves left!',
        'de': 'Keine Züge mehr!',
        'fr': 'Plus de coups !',
        'es': '¡No quedan movimientos!',
        'it': 'Nessuna mossa rimasta!',
        'pt': 'Sem movimentos restantes!',
        'ja': '手数が尽きた！',
        'zh': '没有剩余步数！',
        'ko': '남은 횟수가 없습니다!'
    },
    'campaign_fail_blocks': {
        'tr': 'Blok hakkı bitti!',
        'en': 'No blocks left!',
        'de': 'Keine Blöcke mehr!',
        'fr': 'Plus de blocs !',
        'es': '¡No quedan bloques!',
        'it': 'Nessun blocco rimasto!',
        'pt': 'Sem blocos restantes!',
        'ja': 'ブロックが尽きた！',
        'zh': '没有剩余方块！',
        'ko': '남은 블록이 없습니다!'
    },
    'campaign_block_limit_title': {
        'tr': 'Kalan Blok',
        'en': 'Blocks Left',
        'de': 'Verbleibende Blöcke',
        'fr': 'Blocs restants',
        'es': 'Bloques restantes',
        'it': 'Blocchi rimasti',
        'pt': 'Blocos restantes',
        'ja': '残りブロック',
        'zh': '剩余方块',
        'ko': '남은 블록'
    },
    'campaign_boss': {
        'tr': 'BOSS',
        'en': 'BOSS',
        'de': 'BOSS',
        'fr': 'BOSS',
        'es': 'BOSS',
        'it': 'BOSS',
        'pt': 'BOSS',
        'ja': 'ボス',
        'zh': '首领',
        'ko': '보스'
    },
    'campaign_mini_boss': {
        'tr': 'Mini Boss',
        'en': 'Mini Boss',
        'de': 'Mini-Boss',
        'fr': 'Mini-boss',
        'es': 'Mini jefe',
        'it': 'Mini boss',
        'pt': 'Mini chefe',
        'ja': 'ミニボス',
        'zh': '迷你首领',
        'ko': '미니 보스'
    },
    'campaign_world_tab_format': {
        'tr': 'D{index} {name}',
        'en': 'W{index} {name}',
        'de': 'W{index} {name}',
        'fr': 'M{index} {name}',
        'es': 'M{index} {name}',
        'it': 'M{index} {name}',
        'pt': 'M{index} {name}',
        'ja': 'W{index} {name}',
        'zh': 'W{index} {name}',
        'ko': 'W{index} {name}'
    },
    'campaign_world_short_1': {
        'tr': 'Vadi',
        'en': 'Valley',
        'de': 'Tal',
        'fr': 'Vallée',
        'es': 'Valle',
        'it': 'Valle',
        'pt': 'Vale',
        'ja': '谷',
        'zh': '山谷',
        'ko': '계곡'
    },
    'campaign_world_short_2': {
        'tr': 'Buz',
        'en': 'Ice',
        'de': 'Eis',
        'fr': 'Glace',
        'es': 'Hielo',
        'it': 'Ghiaccio',
        'pt': 'Gelo',
        'ja': '氷',
        'zh': '冰',
        'ko': '얼음'
    },
    'campaign_world_short_3': {
        'tr': 'Lav',
        'en': 'Lava',
        'de': 'Lava',
        'fr': 'Lave',
        'es': 'Lava',
        'it': 'Lava',
        'pt': 'Lava',
        'ja': '溶岩',
        'zh': '熔岩',
        'ko': '용암'
    },
    'campaign_world_short_4': {
        'tr': 'Fırtına',
        'en': 'Storm',
        'de': 'Sturm',
        'fr': 'Tempête',
        'es': 'Tormenta',
        'it': 'Tempesta',
        'pt': 'Tempestade',
        'ja': '嵐',
        'zh': '风暴',
        'ko': '폭풍'
    },
    'campaign_world_short_5': {
        'tr': 'Yıldız',
        'en': 'Star',
        'de': 'Stern',
        'fr': 'Étoile',
        'es': 'Estrella',
        'it': 'Stella',
        'pt': 'Estrela',
        'ja': '星',
        'zh': '星',
        'ko': '별'
    },
    'campaign_status_locked': {
        'tr': 'KİLİTLİ',
        'en': 'LOCKED',
        'de': 'GESPERRT',
        'fr': 'VERROUILLÉ',
        'es': 'BLOQUEADO',
        'it': 'BLOCCATO',
        'pt': 'BLOQUEADO',
        'ja': 'ロック',
        'zh': '锁定',
        'ko': '잠김'
    },
    'campaign_status_ready': {
        'tr': 'HAZIR',
        'en': 'READY',
        'de': 'BEREIT',
        'fr': 'PRÊT',
        'es': 'LISTO',
        'it': 'PRONTO',
        'pt': 'PRONTO',
        'ja': '準備完了',
        'zh': '准备就绪',
        'ko': '준비 완료'
    },
    'campaign_status_perfect': {
        'tr': 'MÜKEMMEL!',
        'en': 'PERFECT!',
        'de': 'PERFEKT!',
        'fr': 'PARFAIT!',
        'es': '¡PERFECTO!',
        'it': 'PERFETTO!',
        'pt': 'PERFEITO!',
        'ja': 'パーフェクト！',
        'zh': '完美！',
        'ko': '완벽해요!'
    },
    'campaign_status_stars': {
        'tr': '{stars} YILDIZ',
        'en': '{stars} STARS',
        'de': '{stars} STERNE',
        'fr': '{stars} ÉTOILES',
        'es': '{stars} ESTRELLAS',
        'it': '{stars} STELLE',
        'pt': '{stars} ESTRELAS',
        'ja': '{stars} 星',
        'zh': '{stars} 星',
        'ko': '{stars} 별'
    },
    'campaign_play': {
        'tr': 'OYNA',
        'en': 'PLAY',
        'de': 'SPIELEN',
        'fr': 'JOUER',
        'es': 'JUGAR',
        'it': 'GIOCA',
        'pt': 'JOGAR',
        'ja': 'プレイ',
        'zh': '开始',
        'ko': '플레이'
    },
    'campaign_cond_complete': {
        'tr': 'Leveli tamamla',
        'en': 'Complete the level',
        'de': 'Level abschließen',
        'fr': 'Terminer le niveau',
        'es': 'Completa el nivel',
        'it': 'Completa il livello',
        'pt': 'Conclua o nível',
        'ja': 'レベルをクリア',
        'zh': '完成关卡',
        'ko': '레벨 완료'
    },
    'campaign_cond_score': {
        'tr': '{value} puan',
        'en': '{value} points',
        'de': '{value} Punkte',
        'fr': '{value} points',
        'es': '{value} puntos',
        'it': '{value} punti',
        'pt': '{value} pontos',
        'ja': '{value} ポイント',
        'zh': '{value} 分',
        'ko': '{value} 점'
    },
    'campaign_cond_combo': {
        'tr': '{value} adım zincir yap (üst üste satır temizle)',
        'en': 'Build a {value}-step chain (clear lines in a row)',
        'de': '{value}er-Kombo erzielen',
        'fr': 'Faire {value} combo',
        'es': 'Hacer {value} combo',
        'it': 'Esegui {value} combo',
        'pt': 'Fazer {value} combo',
        'ja': '{value} コンボ',
        'zh': '达成 {value} 连击',
        'ko': '{value} 콤보 달성'
    },
    'campaign_cond_multi_clear_2': {
        'tr': '2\'li satır temizle',
        'en': 'Make a Double (2-line)',
        'de': 'Double machen (2 Linien)',
        'fr': 'Faire un Double (2 lignes)',
        'es': 'Hacer Double (2 líneas)',
        'it': 'Fare un Double (2 linee)',
        'pt': 'Fazer Double (2 linhas)',
        'ja': 'ダブル（2ライン）',
        'zh': '完成双消（2行）',
        'ko': '더블 만들기(2줄)'
    },
    'campaign_cond_multi_clear_3': {
        'tr': '3\'lü satır temizle',
        'en': 'Make a Triple (3-line)',
        'de': 'Triple machen (3 Linien)',
        'fr': 'Faire un Triple (3 lignes)',
        'es': 'Hacer Triple (3 líneas)',
        'it': 'Fare un Triple (3 linee)',
        'pt': 'Fazer Triple (3 linhas)',
        'ja': 'トリプル（3ライン）',
        'zh': '完成三消（3行）',
        'ko': '트리플 만들기(3줄)'
    },
    'campaign_cond_multi_clear_n': {
        'tr': '{value}\'li temizle',
        'en': 'Clear {value} lines at once',
        'de': '{value} Linien auf einmal löschen',
        'fr': 'Effacer {value} lignes d\'un coup',
        'es': 'Limpia {value} líneas de una vez',
        'it': 'Elimina {value} linee in una volta',
        'pt': 'Limpe {value} linhas de uma vez',
        'ja': '{value}ライン同時消去',
        'zh': '一次清除 {value} 行',
        'ko': '한 번에 {value}줄 지우기'
    },
    'campaign_cond_tetris': {
        'tr': '{value} Quadrix yap',
        'en': 'Make {value} Quadrix',
        'de': '{value} Quadrix erzielen',
        'fr': 'Faire {value} Quadrix',
        'es': 'Hacer {value} Quadrix',
        'it': 'Fare {value} Quadrix',
        'pt': 'Fazer {value} Quadrix',
        'ja': '{value} テトリス',
        'zh': '完成 {value} 次四消',
        'ko': '{value} 테트리스 만들기'
    },
    'campaign_cond_combo_chain': {
        'tr': 'Üst üste {value} zincir (boş turda sıfırlanır)',
        'en': '{value} combo in a row',
        'de': '{value} Combos in Folge',
        'fr': '{value} combos d\'affilée',
        'es': '{value} combos seguidos',
        'it': '{value} combo di fila',
        'pt': '{value} combos seguidos',
        'ja': '{value}連続コンボ',
        'zh': '连续 {value} 连击',
        'ko': '{value} 연속 콤보'
    },
    'campaign_cond_time_limit': {
        'tr': '{value}s içinde tamamla',
        'en': 'Complete within {value}s',
        'de': 'In {value}s abschließen',
        'fr': 'Terminer en {value}s',
        'es': 'Completa en {value}s',
        'it': 'Completa entro {value}s',
        'pt': 'Conclua em {value}s',
        'ja': '{value}s以内にクリア',
        'zh': '在 {value}s 内完成',
        'ko': '{value}s 안에 완료'
    },
    'campaign_cond_extra_lines': {
        'tr': '+{value} ekstra satır',
        'en': '+{value} extra lines',
        'de': '+{value} zusätzliche Linien',
        'fr': '+{value} lignes en plus',
        'es': '+{value} líneas extra',
        'it': '+{value} linee extra',
        'pt': '+{value} linhas extras',
        'ja': '+{value} 追加ライン',
        'zh': '+{value} 额外行',
        'ko': '+{value} 추가 줄'
    },
    'campaign_cond_efficiency': {
        'tr': '+{value} ekstra ilerleme',
        'en': '+{value} extra progress',
        'de': '+{value} zusätzlicher Fortschritt',
        'fr': '+{value} progression extra',
        'es': '+{value} progreso extra',
        'it': '+{value} progresso extra',
        'pt': '+{value} progresso extra',
        'ja': '+{value} 追加進行',
        'zh': '+{value} 额外进度',
        'ko': '+{value} 추가 진행'
    },
    'campaign_cond_time': {
        'tr': '{value}s içinde',
        'en': 'within {value}s',
        'de': 'innerhalb {value}s',
        'fr': 'en {value}s',
        'es': 'en {value}s',
        'it': 'entro {value}s',
        'pt': 'em {value}s',
        'ja': '{value}s以内',
        'zh': '{value}s 内',
        'ko': '{value}s 이내'
    },
    'campaign_remaining_time': {
        'tr': 'Kalan: {seconds}s',
        'en': 'Remaining: {seconds}s',
        'de': 'Verbleibend: {seconds}s',
        'fr': 'Restant : {seconds}s',
        'es': 'Restante: {seconds}s',
        'it': 'Rimanente: {seconds}s',
        'pt': 'Restante: {seconds}s',
        'ja': '残り: {seconds}s',
        'zh': '剩余：{seconds}s',
        'ko': '남은 시간: {seconds}s'
    },
    'campaign_moves_remaining': {
        'tr': 'Hamle: {remaining}/{limit}',
        'en': 'Moves: {remaining}/{limit}',
        'de': 'Züge: {remaining}/{limit}',
        'fr': 'Coups : {remaining}/{limit}',
        'es': 'Movimientos: {remaining}/{limit}',
        'it': 'Mosse: {remaining}/{limit}',
        'pt': 'Movimentos: {remaining}/{limit}',
        'ja': '手数: {remaining}/{limit}',
        'zh': '步数：{remaining}/{limit}',
        'ko': '이동: {remaining}/{limit}'
    },
    'campaign_blocks_placed': {
        'tr': 'Blok: {count}',
        'en': 'Blocks: {count}',
        'de': 'Blöcke: {count}',
        'fr': 'Blocs : {count}',
        'es': 'Bloques: {count}',
        'it': 'Blocchi: {count}',
        'pt': 'Blocos: {count}',
        'ja': 'ブロック: {count}',
        'zh': '方块：{count}',
        'ko': '블록: {count}'
    },
    'campaign_max_combo': {
        'tr': 'En Uzun Combo',
        'en': 'Max Combo',
        'de': 'Max. Combo',
        'fr': 'Combo max',
        'es': 'Combo máx.',
        'it': 'Combo max',
        'pt': 'Combo máx.',
        'ja': '最大コンボ',
        'zh': '最大连击',
        'ko': '최대 콤보'
    },
    'moves': {
        'tr': 'Hamle',
        'en': 'Moves',
        'de': 'Züge',
        'fr': 'Coups',
        'es': 'Movimientos',
        'it': 'Mosse',
        'pt': 'Movimentos',
        'ja': '手数',
        'zh': '步数',
        'ko': '이동'
    },
    'campaign_reward_card_cosmetic': {
        'tr': 'Kart/Kozmetik',
        'en': 'Card/Cosmetic',
        'de': 'Karte/Kosmetik',
        'fr': 'Carte/Cosmétique',
        'es': 'Carta/Cosmético',
        'it': 'Carta/Cosmetico',
        'pt': 'Carta/Cosmético',
        'ja': 'カード/コスメ',
        'zh': '卡牌/外观',
        'ko': '카드/코스튬'
    },
    'none': {
        'tr': 'Yok',
        'en': 'None',
        'de': 'Keine',
        'fr': 'Aucun',
        'es': 'Ninguno',
        'it': 'Nessuno',
        'pt': 'Nenhum',
        'ja': 'なし',
        'zh': '无',
        'ko': '없음'
    },
    'campaign_new_world': {
        'tr': 'Yeni Dünya',
        'en': 'New World',
        'de': 'Neue Welt',
        'fr': 'Nouveau monde',
        'es': 'Nuevo mundo',
        'it': 'Nuovo mondo',
        'pt': 'Novo mundo',
        'ja': '新しい世界',
        'zh': '新世界',
        'ko': '새로운 세계'
    },
    'campaign_world_progress': {
        'tr': 'Dünya İlerlemesi',
        'en': 'World Progress',
        'de': 'Weltfortschritt',
        'fr': 'Progression du monde',
        'es': 'Progreso del mundo',
        'it': 'Progresso del mondo',
        'pt': 'Progresso do mundo',
        'ja': '世界の進行',
        'zh': '世界进度',
        'ko': '월드 진행'
    },
    'campaign_difficulty': {
        'tr': 'Zorluk',
        'en': 'Difficulty',
        'de': 'Schwierigkeit',
        'fr': 'Difficulté',
        'es': 'Dificultad',
        'it': 'Difficoltà',
        'pt': 'Dificuldade',
        'ja': '難易度',
        'zh': '难度',
        'ko': '난이도'
    },
    'campaign_rules': {
        'tr': 'Kurallar',
        'en': 'Rules',
        'de': 'Regeln',
        'fr': 'Règles',
        'es': 'Reglas',
        'it': 'Regole',
        'pt': 'Regras',
        'ja': 'ルール',
        'zh': '规则',
        'ko': '규칙'
    },
    'campaign_rules_standard': {
        'tr': 'Standart',
        'en': 'Standard',
        'de': 'Standard',
        'fr': 'Standard',
        'es': 'Estándar',
        'it': 'Standard',
        'pt': 'Padrão',
        'ja': '標準',
        'zh': '标准',
        'ko': '표준'
    },
    'campaign_rule_no_hold': {
        'tr': 'Hold yok',
        'en': 'No Hold',
        'de': 'Kein Hold',
        'fr': 'Pas de Hold',
        'es': 'Sin Hold',
        'it': 'Senza Hold',
        'pt': 'Sem Hold',
        'ja': 'ホールドなし',
        'zh': '无保留',
        'ko': '홀드 없음'
    },
    'campaign_rule_no_preview': {
        'tr': 'Önizleme yok',
        'en': 'No Preview',
        'de': 'Keine Vorschau',
        'fr': 'Pas d\'aperçu',
        'es': 'Sin vista previa',
        'it': 'Senza anteprima',
        'pt': 'Sem prévia',
        'ja': 'プレビューなし',
        'zh': '无预览',
        'ko': '미리보기 없음'
    },
    'campaign_rule_cascade': {
        'tr': 'Cascade',
        'en': 'Cascade',
        'de': 'Cascade',
        'fr': 'Cascade',
        'es': 'Cascade',
        'it': 'Cascade',
        'pt': 'Cascade',
        'ja': 'カスケード',
        'zh': '级联',
        'ko': '캐스케이드'
    },
    'campaign_rule_time_limit': {
        'tr': 'Süre limiti: {value}s',
        'en': 'Time limit: {value}s',
        'de': 'Zeitlimit: {value}s',
        'fr': 'Limite de temps : {value}s',
        'es': 'Límite de tiempo: {value}s',
        'it': 'Limite di tempo: {value}s',
        'pt': 'Limite de tempo: {value}s',
        'ja': '制限時間: {value}s',
        'zh': '时间限制：{value}s',
        'ko': '시간 제한: {value}s'
    },
    'campaign_rule_move_limit': {
        'tr': 'Hamle limiti: {value}',
        'en': 'Move limit: {value}',
        'de': 'Zuglimit: {value}',
        'fr': 'Limite de coups : {value}',
        'es': 'Límite de movimientos: {value}',
        'it': 'Limite mosse: {value}',
        'pt': 'Limite de movimentos: {value}',
        'ja': '手数制限: {value}',
        'zh': '步数限制：{value}',
        'ko': '이동 제한: {value}'
    },
    'campaign_rule_special_blocks': {
        'tr': 'Özel blok: {value}',
        'en': 'Special blocks: {value}',
        'de': 'Spezialblöcke: {value}',
        'fr': 'Blocs spéciaux : {value}',
        'es': 'Bloques especiales: {value}',
        'it': 'Blocchi speciali: {value}',
        'pt': 'Blocos especiais: {value}',
        'ja': '特殊ブロック: {value}',
        'zh': '特殊方块：{value}',
        'ko': '특수 블록: {value}'
    },
    'campaign_rule_block_limit': {
        'tr': 'Blok sınırı: {value}',
        'en': 'Block limit: {value}',
        'de': 'Blocklimit: {value}',
        'fr': 'Limite de blocs : {value}',
        'es': 'Límite de bloques: {value}',
        'it': 'Limite blocchi: {value}',
        'pt': 'Limite de blocos: {value}',
        'ja': 'ブロック制限: {value}',
        'zh': '方块限制：{value}',
        'ko': '블록 제한: {value}'
    },
    'difficulty_easy': {
        'tr': 'Kolay',
        'en': 'Easy',
        'de': 'Leicht',
        'fr': 'Facile',
        'es': 'Fácil',
        'it': 'Facile',
        'pt': 'Fácil',
        'ja': '簡単',
        'zh': '简单',
        'ko': '쉬움'
    },
    'difficulty_normal': {
        'tr': 'Orta',
        'en': 'Normal',
        'de': 'Normal',
        'fr': 'Normal',
        'es': 'Normal',
        'it': 'Normale',
        'pt': 'Normal',
        'ja': '普通',
        'zh': '普通',
        'ko': '보통'
    },
    'difficulty_hard': {
        'tr': 'Zor',
        'en': 'Hard',
        'de': 'Schwer',
        'fr': 'Difficile',
        'es': 'Difícil',
        'it': 'Difficile',
        'pt': 'Difícil',
        'ja': '難しい',
        'zh': '困难',
        'ko': '어려움'
    },
    'difficulty_expert': {
        'tr': 'Usta',
        'en': 'Expert',
        'de': 'Experte',
        'fr': 'Expert',
        'es': 'Experto',
        'it': 'Esperto',
        'pt': 'Especialista',
        'ja': '達人',
        'zh': '专家',
        'ko': '전문가'
    },
    'campaign_obj_clear_lines': {
        'tr': '{target} Satır Temizle',
        'en': 'Clear {target} Lines',
        'de': '{target} Linien löschen',
        'fr': 'Effacer {target} lignes',
        'es': 'Limpiar {target} líneas',
        'it': 'Cancella {target} righe',
        'pt': 'Limpar {target} linhas',
        'ja': '{target}ライン消去',
        'zh': '清除 {target} 行',
        'ko': '{target}줄 지우기'
    },
    'campaign_obj_clear_singles': {
        'tr': '{target} Tekli Temizle',
        'en': 'Clear {target} Singles',
        'de': '{target} Einzelne löschen',
        'fr': 'Effacer {target} simples',
        'es': 'Limpiar {target} simples',
        'it': 'Cancella {target} singoli',
        'pt': 'Limpar {target} simples',
        'ja': '{target}シングル消去',
        'zh': '清除 {target} 单消',
        'ko': '{target} 싱글 지우기'
    },
    'campaign_obj_clear_doubles': {
        'tr': '{target} İkili Temizle',
        'en': 'Clear {target} Doubles',
        'de': '{target} Doppelte löschen',
        'fr': 'Effacer {target} doubles',
        'es': 'Limpiar {target} dobles',
        'it': 'Cancella {target} doppi',
        'pt': 'Limpar {target} duplas',
        'ja': '{target}ダブル消去',
        'zh': '清除 {target} 双消',
        'ko': '{target} 더블 지우기'
    },
    'campaign_obj_clear_triples': {
        'tr': '{target} Üçlü Temizle',
        'en': 'Clear {target} Triples',
        'de': '{target} Dreifache löschen',
        'fr': 'Effacer {target} triples',
        'es': 'Limpiar {target} triples',
        'it': 'Cancella {target} tripli',
        'pt': 'Limpar {target} triplas',
        'ja': '{target}トリプル消去',
        'zh': '清除 {target} 三消',
        'ko': '{target} 트리플 지우기'
    },
    'campaign_obj_clear_garbage': {
        'tr': 'Tüm Çöp Bloklarını Temizle',
        'en': 'Clear all Garbage Blocks',
        'de': 'Alle Müllblöcke entfernen',
        'fr': 'Nettoyer tous les blocs déchets',
        'es': 'Eliminar todos los bloques de basura',
        'it': 'Elimina tutti i blocchi spazzatura',
        'pt': 'Limpe todos os blocos de lixo',
        'ja': 'ゴミブロックをすべて消去',
        'zh': '清除所有垃圾方块',
        'ko': '모든 쓰레기 블록 제거'
    },
    'campaign_obj_clear_garbage_count': {
        'tr': 'Tüm Çöp Bloklarını Temizle ({count} hücre)',
        'en': 'Clear all Garbage Blocks ({count} cells)',
        'de': 'Alle Müllblöcke entfernen ({count} Zellen)',
        'fr': 'Nettoyer tous les blocs déchets ({count} cellules)',
        'es': 'Eliminar todos los bloques de basura ({count} celdas)',
        'it': 'Elimina tutti i blocchi spazzatura ({count} celle)',
        'pt': 'Limpe todos os blocos de lixo ({count} células)',
        'ja': 'ゴミブロックをすべて消去（{count}セル）',
        'zh': '清除所有垃圾方块（{count}格）',
        'ko': '모든 쓰레기 블록 제거({count}칸)'
    },
    'campaign_obj_score': {
        'tr': '{target} Puan',
        'en': '{target} Points',
        'de': '{target} Punkte',
        'fr': '{target} points',
        'es': '{target} puntos',
        'it': '{target} punti',
        'pt': '{target} pontos',
        'ja': '{target} ポイント',
        'zh': '{target} 分',
        'ko': '{target} 점'
    },
    'campaign_obj_tetris': {
        'tr': '{target} Quadrix Yap',
        'en': 'Make {target} Quadrix',
        'de': '{target} Quadrix erzielen',
        'fr': 'Faire {target} Quadrix',
        'es': 'Hacer {target} Quadrix',
        'it': 'Fare {target} Quadrix',
        'pt': 'Fazer {target} Quadrix',
        'ja': '{target} テトリス',
        'zh': '完成 {target} 次四消',
        'ko': '{target} 테트리스 만들기'
    },
    'campaign_obj_combo': {
        'tr': '{target} adım zincir yap (üst üste satır temizle)',
        'en': 'Build a {target}-step chain (clear lines consecutively)',
        'de': '{target}x Combo erzielen',
        'fr': 'Faire {target}x combo',
        'es': 'Hacer {target}x combo',
        'it': 'Fare {target}x combo',
        'pt': 'Fazer {target}x combo',
        'ja': '{target}x コンボ',
        'zh': '达成 {target}x 连击',
        'ko': '{target}x 콤보 만들기'
    },
    'campaign_obj_survival': {
        'tr': '{target} saniye hayatta kal',
        'en': 'Survive {target} seconds',
        'de': '{target} Sekunden überleben',
        'fr': 'Survivre {target} secondes',
        'es': 'Sobrevive {target} segundos',
        'it': 'Sopravvivi {target} secondi',
        'pt': 'Sobreviva {target} segundos',
        'ja': '{target}秒生存',
        'zh': '生存 {target} 秒',
        'ko': '{target}초 생존'
    },
    'campaign_obj_time': {
        'tr': '{target} saniyede tamamla',
        'en': 'Complete in {target} seconds',
        'de': 'In {target} Sekunden abschließen',
        'fr': 'Terminer en {target} secondes',
        'es': 'Completa en {target} segundos',
        'it': 'Completa in {target} secondi',
        'pt': 'Conclua em {target} segundos',
        'ja': '{target}秒でクリア',
        'zh': '在 {target} 秒内完成',
        'ko': '{target}초 내 완료'
    },
    'campaign_obj_special_block': {
        'tr': '{target} Özel Blok Temizle',
        'en': 'Clear {target} Special Blocks',
        'de': '{target} Spezialblöcke entfernen',
        'fr': 'Nettoyer {target} blocs spéciaux',
        'es': 'Eliminar {target} bloques especiales',
        'it': 'Elimina {target} blocchi speciali',
        'pt': 'Limpe {target} blocos especiais',
        'ja': '特殊ブロック {target}個消去',
        'zh': '清除 {target} 个特殊方块',
        'ko': '특수 블록 {target}개 제거'
    },
    'campaign_obj_special_block_typed': {
        'tr': '{target} {block} Blok Temizle',
        'en': 'Clear {target} {block} Blocks',
        'de': '{target} {block}-Blöcke entfernen',
        'fr': 'Nettoyer {target} blocs {block}',
        'es': 'Eliminar {target} bloques {block}',
        'it': 'Elimina {target} blocchi {block}',
        'pt': 'Limpe {target} blocos {block}',
        'ja': '{block}ブロックを{target}個消去',
        'zh': '清除 {target} 个{block}方块',
        'ko': '{block} 블록 {target}개 제거'
    },
    'campaign_special_block_ice': {
        'tr': 'Buz',
        'en': 'Ice',
        'de': 'Eis',
        'fr': 'Glace',
        'es': 'Hielo',
        'it': 'Ghiaccio',
        'pt': 'Gelo',
        'ja': '氷',
        'zh': '冰',
        'ko': '얼음'
    },
    'campaign_special_block_locked': {
        'tr': 'Kilitli',
        'en': 'Locked',
        'de': 'Gesperrt',
        'fr': 'Verrouillé',
        'es': 'Bloqueado',
        'it': 'Bloccato',
        'pt': 'Bloqueado',
        'ja': 'ロック',
        'zh': '锁定',
        'ko': '잠김'
    },
    'campaign_special_block_bomb': {
        'tr': 'Bomba',
        'en': 'Bomb',
        'de': 'Bombe',
        'fr': 'Bombe',
        'es': 'Bomba',
        'it': 'Bomba',
        'pt': 'Bomba',
        'ja': '爆弾',
        'zh': '炸弹',
        'ko': '폭탄'
    },
    'campaign_special_block_star': {
        'tr': 'Yıldız',
        'en': 'Star',
        'de': 'Stern',
        'fr': 'Étoile',
        'es': 'Estrella',
        'it': 'Stella',
        'pt': 'Estrela',
        'ja': '星',
        'zh': '星',
        'ko': '별'
    },
    'campaign_special_block_timer': {
        'tr': 'Zamanlı',
        'en': 'Timer',
        'de': 'Timer',
        'fr': 'Minuteur',
        'es': 'Temporizador',
        'it': 'Timer',
        'pt': 'Temporizador',
        'ja': 'タイマー',
        'zh': '计时器',
        'ko': '타이머'
    },
    'campaign_special_block_special': {
        'tr': 'Özel',
        'en': 'Special',
        'de': 'Spezial',
        'fr': 'Spécial',
        'es': 'Especial',
        'it': 'Speciale',
        'pt': 'Especial',
        'ja': '特殊',
        'zh': '特殊',
        'ko': '특수'
    },
    'campaign_obj_perfect_clear': {
        'tr': '{target} mükemmel temizlik',
        'en': '{target} perfect clear',
        'de': '{target} perfekte Clears',
        'fr': '{target} perfect clears',
        'es': '{target} perfect clears',
        'it': '{target} perfect clear',
        'pt': '{target} perfect clears',
        'ja': '{target} パーフェクトクリア',
        'zh': '{target} 次完美消除',
        'ko': '{target} 퍼펙트 클리어'
    },
    'campaign_obj_move_efficiency': {
        'tr': '{target} Hamle ile Tamamla',
        'en': 'Finish in {target} Moves',
        'de': 'In {target} Zügen abschließen',
        'fr': 'Terminer en {target} coups',
        'es': 'Termina en {target} movimientos',
        'it': 'Completa in {target} mosse',
        'pt': 'Conclua em {target} movimentos',
        'ja': '{target}手以内でクリア',
        'zh': '在 {target} 步内完成',
        'ko': '{target}회 이내 완료'
    },
    'campaign_obj_move_efficiency_detail': {
        'tr': '{moves} hamlede {lines} satır',
        'en': '{lines} lines in {moves} moves',
        'de': '{lines} Linien in {moves} Zügen',
        'fr': '{lines} lignes en {moves} coups',
        'es': '{lines} líneas en {moves} movimientos',
        'it': '{lines} righe in {moves} mosse',
        'pt': '{lines} linhas em {moves} movimentos',
        'ja': '{moves}手で{lines}ライン',
        'zh': '{moves} 步完成 {lines} 行',
        'ko': '{moves}회에 {lines}줄'
    },
    'level_complete': {
        'tr': 'LEVEL TAMAMLANDI!',
        'en': 'LEVEL COMPLETE!',
        'de': 'LEVEL ABGESCHLOSSEN!',
        'fr': 'NIVEAU TERMINÉ!',
        'es': '¡NIVEL COMPLETADO!',
        'it': 'LIVELLO COMPLETATO!',
        'pt': 'NÍVEL CONCLUÍDO!',
        'ja': 'レベルクリア！',
        'zh': '关卡完成！',
        'ko': '레벨 완료!'
    },
    'level_failed': {
        'tr': 'BAŞARISIZ!',
        'en': 'FAILED!',
        'de': 'GESCHEITERT!',
        'fr': 'ÉCHOUÉ!',
        'es': '¡FALLIDO!',
        'it': 'FALLITO!',
        'pt': 'FALHOU!',
        'ja': '失敗！',
        'zh': '失败！',
        'ko': '실패!'
    },
    'next_level': {
        'tr': 'Sonraki Level',
        'en': 'Next Level',
        'de': 'Nächstes Level',
        'fr': 'Niveau Suivant',
        'es': 'Siguiente Nivel',
        'it': 'Prossimo Livello',
        'pt': 'Próximo Nível',
        'ja': '次のレベル',
        'zh': '下一关',
        'ko': '다음 레벨'
    },
    'try_again': {
        'tr': 'Tekrar Dene',
        'en': 'Try Again',
        'de': 'Erneut Versuchen',
        'fr': 'Réessayer',
        'es': 'Intentar de Nuevo',
        'it': 'Riprova',
        'pt': 'Tentar Novamente',
        'ja': '再挑戦',
        'zh': '再试一次',
        'ko': '다시 시도'
    },
    'level_select': {
        'tr': 'Level Seçimi',
        'en': 'Level Select',
        'de': 'Level-Auswahl',
        'fr': 'Sélection Niveau',
        'es': 'Selección Nivel',
        'it': 'Selezione Livello',
        'pt': 'Seleção de Nível',
        'ja': 'レベル選択',
        'zh': '关卡选择',
        'ko': '레벨 선택'
    },
    'world': {
        'tr': 'Dünya',
        'en': 'World',
        'de': 'Welt',
        'fr': 'Monde',
        'es': 'Mundo',
        'it': 'Mondo',
        'pt': 'Mundo',
        'ja': '世界',
        'zh': '世界',
        'ko': '월드'
    },
    'stars': {
        'tr': 'Yıldız',
        'en': 'Stars',
        'de': 'Sterne',
        'fr': 'Étoiles',
        'es': 'Estrellas',
        'it': 'Stelle',
        'pt': 'Estrelas',
        'ja': '星',
        'zh': '星',
        'ko': '별'
    },
    'objective': {
        'tr': 'Görev',
        'en': 'Objective',
        'de': 'Ziel',
        'fr': 'Objectif',
        'es': 'Objetivo',
        'it': 'Obiettivo',
        'pt': 'Objetivo',
        'ja': '目標',
        'zh': '目标',
        'ko': '목표'
    },
    'objectives': {
        'tr': 'Görevler',
        'en': 'Objectives',
        'de': 'Ziele',
        'fr': 'Objectifs',
        'es': 'Objetivos',
        'it': 'Obiettivi',
        'pt': 'Objetivos',
        'ja': '目標',
        'zh': '目标',
        'ko': '목표'
    },
    'clear_lines_obj': {
        'tr': 'Satır Temizle',
        'en': 'Clear Lines',
        'de': 'Zeilen löschen',
        'fr': 'Effacer Lignes',
        'es': 'Limpiar Líneas',
        'it': 'Cancella Righe',
        'pt': 'Limpar Linhas',
        'ja': 'ライン消去',
        'zh': '清除行',
        'ko': '줄 지우기'
    },
    'score_obj': {
        'tr': 'Puana Ulaş',
        'en': 'Reach Score',
        'de': 'Punkte erreichen',
        'fr': 'Atteindre Score',
        'es': 'Alcanzar Puntos',
        'it': 'Raggiungi Punteggio',
        'pt': 'Alcançar Pontuação',
        'ja': 'スコア到達',
        'zh': '达到分数',
        'ko': '점수 달성'
    },
    'tetris_obj': {
        'tr': 'Quadrix Yap',
        'en': 'Make Quadrix',
        'de': 'Quadrix machen',
        'fr': 'Faire Quadrix',
        'es': 'Hacer Quadrix',
        'it': 'Fai Quadrix',
        'pt': 'Fazer Quadrix',
        'ja': 'テトリス',
        'zh': '四消',
        'ko': '테트리스'
    },
    'combo_obj': {
        'tr': 'Combo Yap',
        'en': 'Make Combo',
        'de': 'Combo machen',
        'fr': 'Faire Combo',
        'es': 'Hacer Combo',
        'it': 'Fai Combo',
        'pt': 'Fazer Combo',
        'ja': 'コンボ',
        'zh': '连击',
        'ko': '콤보'
    },
    'time_limit': {
        'tr': 'Süre Limiti',
        'en': 'Time Limit',
        'de': 'Zeitlimit',
        'fr': 'Limite de Temps',
        'es': 'Límite de Tiempo',
        'it': 'Limite di Tempo',
        'pt': 'Limite de Tempo',
        'ja': '制限時間',
        'zh': '时间限制',
        'ko': '시간 제한'
    },
    'move_limit': {
        'tr': 'Hamle Limiti',
        'en': 'Move Limit',
        'de': 'Zuglimit',
        'fr': 'Limite de Mouvements',
        'es': 'Límite de Movimientos',
        'it': 'Limite di Mosse',
        'pt': 'Limite de Movimentos',
        'ja': '手数制限',
        'zh': '步数限制',
        'ko': '이동 제한'
    },
    'remaining': {
        'tr': 'Kalan',
        'en': 'Remaining',
        'de': 'Verbleibend',
        'fr': 'Restant',
        'es': 'Restante',
        'it': 'Rimanente',
        'pt': 'Restante',
        'ja': '残り',
        'zh': '剩余',
        'ko': '남은'
    },
    'progress': {
        'tr': 'İlerleme',
        'en': 'Progress',
        'de': 'Fortschritt',
        'fr': 'Progression',
        'es': 'Progreso',
        'it': 'Progresso',
        'pt': 'Progresso',
        'ja': '進行',
        'zh': '进度',
        'ko': '진행'
    },
    'locked': {
        'tr': 'Kilitli',
        'en': 'Locked',
        'de': 'Gesperrt',
        'fr': 'Verrouillé',
        'es': 'Bloqueado',
        'it': 'Bloccato',
        'pt': 'Bloqueado',
        'zh': '锁定',
        'ko': '잠김'
    },
    'boss_level': {
        'tr': 'Boss Level',
        'en': 'Boss Level',
        'de': 'Boss-Level',
        'fr': 'Niveau Boss',
        'es': 'Nivel Jefe',
        'pt': 'Nível Chefe',
        'ja': 'ボスレベル',
        'zh': '首领关',
        'ko': '보스 레벨',
    },
    'world_1': {
        'tr': 'Başlangıç Vadisi',
        'en': "Beginner's Valley",
        'de': 'Anfängertal',
        'fr': 'Vallée des Débutants',
        'es': 'Valle del Principiante',
        'pt': 'Vale do Iniciante',
        'ja': '初心者の谷',
        'zh': '新手山谷',
        'ko': '초보자 계곡',
    },
    'world_2': {
        'tr': 'Buz Diyarı',
        'en': 'Ice Realm',
        'de': 'Eisreich',
        'fr': 'Royaume de Glace',
        'es': 'Reino de Hielo',
        'pt': 'Reino do Gelo',
        'ja': '氷の王国',
        'zh': '冰之王国',
        'ko': '얼음 왕국',
    },
    'world_3': {
        'tr': 'Lav Mağarası',
        'en': 'Lava Caves',
        'de': 'Lavahöhlen',
        'fr': 'Grottes de Lave',
        'es': 'Cuevas de Lava',
        'pt': 'Cavernas de Lava',
        'ja': '溶岩洞窟',
        'zh': '熔岩洞穴',
        'ko': '용암 동굴',
    },
    'world_4': {
        'tr': 'Fırtına Kalesi',
        'en': 'Storm Fortress',
        'de': 'Sturmfestung',
        'fr': 'Forteresse des Tempêtes',
        'es': 'Fortaleza de la Tormenta',
        'pt': 'Fortaleza da Tempestade',
        'ja': '嵐の要塞',
        'zh': '风暴要塞',
        'ko': '폭풍 요새',
    },
    'world_5': {
        'tr': 'Yıldız Kulesi',
        'en': 'Star Tower',
        'de': 'Sternenturm',
        'fr': 'Tour des Étoiles',
        'es': 'Torre Estelar',
        'pt': 'Torre Estelar',
        'ja': '星の塔',
        'zh': '星之塔',
        'ko': '별의 탑',
    },
    'total_stars': {
        'tr': 'Toplam Yıldız',
        'en': 'Total Stars',
        'de': 'Gesamtsterne',
        'fr': 'Étoiles Totales',
        'es': 'Estrellas Totales',
        'pt': 'Estrelas Totais',
        'ja': '合計スター',
        'zh': '总星数',
        'ko': '총 별 수',
    },
    'continue_campaign': {
        'tr': 'Devam Et',
        'en': 'Continue',
        'de': 'Fortsetzen',
        'fr': 'Continuer',
        'es': 'Continuar',
        'pt': 'Continuar',
        'ja': '続ける',
        'zh': '继续',
        'ko': '계속하기',
    },
    'new_campaign': {
        'tr': 'Yeni Başla',
        'en': 'New Game',
        'de': 'Neues Spiel',
        'fr': 'Nouvelle Partie',
        'es': 'Nueva Partida',
        'pt': 'Nova Campanha',
        'ja': '新しく始める',
        'zh': '新游戏',
        'ko': '새 게임',
    },
    'campaign_progress_reset': {
        'tr': 'İlerleme sıfırlansın mı?',
        'en': 'Reset progress?',
        'de': 'Fortschritt zurücksetzen?',
        'fr': 'Réinitialiser progression?',
        'es': '¿Reiniciar progreso?',
        'it': 'Resettare progresso?',
        'pt': 'Resetar progresso?',
        'zh': '重置进度？',
        'ko': '진행 상황을 초기화할까요?'
    },
    
    'sprint_mode': {
        'tr': 'Sprint Modu',
        'en': 'Sprint Mode',
        'de': 'Sprint-Modus',
        'fr': 'Mode Sprint',
        'es': 'Modo Sprint',
        'it': 'Modalità Sprint',
        'pt': 'Modo Sprint',
        'ja': 'スプリントモード',
        'zh': '冲刺模式',
        'ko': '스프린트 모드'
    },
    'marathon_mode': {
        'tr': 'Maraton Modu',
        'en': 'Marathon Mode',
        'de': 'Marathon-Modus',
        'fr': 'Mode Marathon',
        'es': 'Modo Maratón',
        'it': 'Modalità Maratona',
        'pt': 'Modo Maratona',
        'ja': 'マラソンモード',
        'zh': '马拉松模式',
        'ko': '마라톤 모드'
    },
    'daily_challenge': {
        'tr': 'Günlük Görev',
        'en': 'Daily Challenge',
        'de': 'Tägliche Herausforderung',
        'fr': 'Défi Quotidien',
        'es': 'Desafío Diario',
        'it': 'Sfida Giornaliera',
        'pt': 'Desafio Diário',
        'ja': 'デイリーチャレンジ',
        'zh': '每日挑战',
        'ko': '일일 도전'
    },
    
    # ======================= EKSTRALAR =======================
    'leaderboard': {
        'tr': 'Skor Tablosu',
        'en': 'Leaderboard',
        'de': 'Rangliste',
        'fr': 'Classement',
        'es': 'Tabla de Clasificación',
        'it': 'Classifica',
        'pt': 'Ranking'
    },
    'statistics': {
        'tr': 'İstatistikler',
        'en': 'Statistics',
        'de': 'Statistiken',
        'fr': 'Statistiques',
        'es': 'Estadísticas',
        'it': 'Statistiche',
        'pt': 'Estatísticas'
    },
    'credits': {
        'tr': 'Emeği Geçenler',
        'en': 'Credits',
        'de': 'Credits',
        'fr': 'Crédits',
        'es': 'Créditos',
        'it': 'Crediti',
        'pt': 'Créditos',
        'ja': 'クレジット',
        'zh': '制作人员',
        'ko': '크레딧'
    },
    'credits_screen_title': {
        'tr': 'EMEĞİ GEÇENLER',
        'en': 'CREDITS',
        'de': 'CREDITS',
        'fr': 'CRÉDITS',
        'es': 'CRÉDITOS',
        'it': 'CREDITI',
        'pt': 'CRÉDITOS',
        'ja': 'クレジット',
        'zh': '制作人员',
        'ko': '크레딧'
    },
    'credits_screen_subtitle': {
        'tr': 'Oyunu mümkün kılan ekip ve topluluk',
        'en': 'The team and community who made it possible',
        'de': 'Das Team und die Community, die es möglich gemacht haben',
        'fr': 'L\'équipe et la communauté qui l\'ont rendu possible',
        'es': 'El equipo y la comunidad que lo hicieron posible',
        'it': 'Il team e la community che lo hanno reso possibile',
        'pt': 'A equipe e a comunidade que tornaram isso possível',
        'ja': '制作を支えたチームとコミュニティ',
        'zh': '让游戏成为可能的团队与社区',
        'ko': '게임을 가능하게 한 팀과 커뮤니티'
    },
    'credits_role_founder': {
        'tr': 'GELİŞTİRİCİLER',
        'en': 'DEVELOPERS',
        'de': 'ENTWICKLER',
        'fr': 'DÉVELOPPEURS',
        'es': 'DESARROLLADORES',
        'it': 'SVILUPPATORI',
        'pt': 'DESENVOLVEDORES',
        'ja': '開発者',
        'zh': '开发者',
        'ko': '개발자'
    },
    'credits_desc_arda': {
        'tr': 'Oyunda gördüğünüz her şey',
        'en': 'Everything you see in the game',
        'de': 'Alles was Sie im Spiel sehen',
        'fr': 'Tout ce que vous voyez dans le jeu',
        'es': 'Todo lo que ves en el juego',
        'it': 'Tutto ciò che vedi nel gioco',
        'pt': 'Tudo o que você vê no jogo',
        'ja': 'ゲーム内で見えるすべて',
        'zh': '你在游戏中看到的一切',
        'ko': '게임에서 보이는 모든 것'
    },
    'credits_role_aiux': {
        'tr': 'YAPAY ZEKA & UX',
        'en': 'AI & UX',
        'de': 'KI & UX',
        'fr': 'IA & UX',
        'es': 'IA & UX',
        'it': 'AI & UX',
        'pt': 'IA & UX',
        'ja': 'AI & UX',
        'zh': 'AI 与 UX',
        'ko': 'AI & UX'
    },
    'credits_desc_burak': {
        'tr': 'Oyun otomasyonu, menü etkileşimleri, testler',
        'en': 'Game automation, menu interactions, tests',
        'de': 'Spielautomatisierung, Menüinteraktionen, Tests',
        'fr': 'Automatisation du jeu, interactions de menu, tests',
        'es': 'Automatización del juego, interacciones de menú, pruebas',
        'it': 'Automazione del gioco, interazioni del menu, test',
        'pt': 'Automação do jogo, interações do menu, testes',
        'ja': 'ゲーム自動化、メニュー操作、テスト',
        'zh': '游戏自动化、菜单交互、测试',
        'ko': '게임 자동화, 메뉴 상호작용, 테스트'
    },
    'credits_supporters_title': {
        'tr': 'Destekçiler',
        'en': 'Supporters',
        'de': 'Unterstützer',
        'fr': 'Supporteurs',
        'es': 'Seguidores',
        'it': 'Sostenitori',
        'pt': 'Apoiadores',
        'ja': 'サポーター',
        'zh': '支持者',
        'ko': '서포터'
    },
    'credits_supporters_role': {
        'tr': 'OYUN TESTÇİLERİ',
        'en': 'GAME TESTERS',
        'de': 'SPIELTESTER',
        'fr': 'TESTEURS DE JEU',
        'es': 'PROBADORES DEL JUEGO',
        'it': 'TESTER DEL GIOCO',
        'pt': 'TESTADORES DO JOGO',
        'ja': 'ゲームテスター',
        'zh': '游戏测试者',
        'ko': '게임 테스터'
    },
    'credits_supporters_desc': {
        'tr': 'Tıkla: Test ekibini gör',
        'en': 'Click: See the testers',
        'de': 'Klicken: Tester sehen',
        'fr': 'Cliquez: Voir les testeurs',
        'es': 'Haz clic: Ver los probadores',
        'it': 'Clicca: Vedi i tester',
        'pt': 'Clique: Ver os testadores',
        'ja': 'クリック: テスターを見る',
        'zh': '点击：查看测试人员',
        'ko': '클릭: 테스터 보기'
    },
    'credits_role_music': {
        'tr': 'MÜZİK & SES',
        'en': 'MUSIC & SFX',
        'de': 'MUSIK & SFX',
        'fr': 'MUSIQUE & SFX',
        'es': 'MÚSICA & SFX',
        'it': 'MUSICA & SFX',
        'pt': 'MÚSICA & SFX',
        'ja': '音楽＆効果音',
        'zh': '音乐与音效',
        'ko': '음악 & 효과음'
    },
    'credits_desc_suno': {
        'tr': 'Atmosferik parçalar, ses efektleri',
        'en': 'Atmospheric tracks, sound effects',
        'de': 'Atmosphärische Tracks, Soundeffekte',
        'fr': 'Pistes atmosphériques, effets sonores',
        'es': 'Pistas atmosféricas, efectos de sonido',
        'it': 'Tracce atmosferiche, effetti sonori',
        'pt': 'Faixas atmosféricas, efeitos sonoros',
        'ja': '雰囲気系トラック、効果音',
        'zh': '氛围音乐与音效',
        'ko': '분위기 트랙, 효과음'
    },
    'credits_special_thanks_title': {
        'tr': 'Özel Teşekkürler',
        'en': 'Special Thanks',
        'de': 'Besonderer Dank',
        'fr': 'Remerciements Spéciaux',
        'es': 'Agradecimientos Especiales',
        'it': 'Ringraziamenti Speciali',
        'pt': 'Agradecimentos Especiais',
        'ja': '特別な感謝',
        'zh': '特别感谢',
        'ko': '특별 감사'
    },
    'credits_special_thanks_1': {
        'tr': 'Python & Pygame topluluğu',
        'en': 'The Python & Pygame community',
        'de': 'Die Python & Pygame Community',
        'fr': 'La communauté Python & Pygame',
        'es': 'La comunidad de Python y Pygame',
        'it': 'La community di Python e Pygame',
        'pt': 'A comunidade Python & Pygame',
        'ja': 'Python＆Pygameコミュニティ',
        'zh': 'Python 与 Pygame 社区',
        'ko': 'Python & Pygame 커뮤니티'
    },
    'credits_special_thanks_2': {
        'tr': 'Oynayıp geri bildirim veren herkes',
        'en': 'Everyone who played and gave feedback',
        'de': 'Alle, die gespielt und Feedback gegeben haben',
        'fr': 'Tous ceux qui ont joué et donné leur avis',
        'es': 'Todos los que jugaron y dieron su opinión',
        'it': 'Tutti quelli che hanno giocato e dato feedback',
        'pt': 'Todos que jogaram e deram feedback',
        'ja': '遊んでフィードバックをくれた皆さん',
        'zh': '所有游玩并提供反馈的人',
        'ko': '플레이하고 피드백을 준 모든 분들'
    },
    'credits_special_thanks_3': {
        'tr': 'Klasik tetris oyununu seven koca kitle',
        'en': 'The huge crowd who loves classic Quadrix',
        'de': 'Die große Menge, die klassisches Quadrix liebt',
        'fr': 'La grande foule qui aime le Quadrix classique',
        'es': 'La gran multitud que ama el Quadrix clásico',
        'it': 'La grande folla che ama il Quadrix classico',
        'pt': 'A grande multidão que ama o Quadrix clássico',
        'ja': 'クラシックテトリスを愛する大勢の人々',
        'zh': '热爱经典俄罗斯方块的大群玩家',
        'ko': '클래식 테트리스를 사랑하는 많은 분들'
    },
    'credits_social_info': {
        'tr': 'Instagram: @vibecode.production  |  Github: github.com/ardadmrknn  |  E-posta: {email}',
        'en': 'Instagram: @vibecode.production  |  Github: github.com/ardadmrknn  |  Email: {email}',
        'de': 'Instagram: @vibecode.production  |  Github: github.com/ardadmrknn  |  E-Mail: {email}',
        'fr': 'Instagram: @vibecode.production  |  Github: github.com/ardadmrknn  |  E-mail: {email}',
        'es': 'Instagram: @vibecode.production  |  Github: github.com/ardadmrknn  |  Correo: {email}',
        'it': 'Instagram: @vibecode.production  |  Github: github.com/ardadmrknn  |  E-mail: {email}',
        'pt': 'Instagram: @vibecode.production  |  Github: github.com/ardadmrknn  |  E-mail: {email}',
        'ja': 'Instagram: @vibecode.production  |  GitHub: github.com/ardadmrknn  |  メール: {email}',
        'zh': 'Instagram：@vibecode.production  |  GitHub：github.com/ardadmrknn  |  邮箱：{email}',
        'ko': 'Instagram: @vibecode.production  |  GitHub: github.com/ardadmrknn  |  이메일: {email}'
    },
    'credits_copyright': {
        'tr': '© 2025 - Tüm hakları saklıdır',
        'en': '© 2025 - All rights reserved',
        'de': '© 2025 - Alle Rechte vorbehalten',
        'fr': '© 2025 - Tous droits réservés',
        'es': '© 2025 - Todos los derechos reservados',
        'it': '© 2025 - Tutti i diritti riservati',
        'pt': '© 2025 - Todos os direitos reservados',
        'ja': '© 2025 - 無断転載を禁じます',
        'zh': '© 2025 - 保留所有权利',
        'ko': '© 2025 - 모든 권리 보유'
    },
    'credits_esc_hint': {
        'tr': 'ESC - Ana Menü',
        'en': 'ESC - Main Menu',
        'de': 'ESC - Hauptmenü',
        'fr': 'ÉCHAP - Menu Principal',
        'es': 'ESC - Menú Principal',
        'it': 'ESC - Menu Principale',
        'pt': 'ESC - Menu Principal',
        'ja': 'ESC - メインメニュー',
        'zh': 'ESC - 主菜单',
        'ko': 'ESC - 메인 메뉴'
    },
    'credits_testers_title': {
        'tr': 'Oyun Testçileri',
        'en': 'Game Testers',
        'de': 'Spieltester',
        'fr': 'Testeurs de Jeu',
        'es': 'Probadores del Juego',
        'it': 'Tester del Gioco',
        'pt': 'Testadores do Jogo',
        'ja': 'ゲームテスター',
        'zh': '游戏测试者',
        'ko': '게임 테스터'
    },
    'credits_testers_close_hint': {
        'tr': 'ESC veya dışarı tıkla: Kapat',
        'en': 'ESC or click outside: Close',
        'de': 'ESC oder außerhalb klicken: Schließen',
        'fr': 'ÉCHAP ou cliquez dehors: Fermer',
        'es': 'ESC o haz clic fuera: Cerrar',
        'it': 'ESC o clicca fuori: Chiudi',
        'pt': 'ESC ou clique fora: Fechar',
        'ja': 'ESCまたは外側クリック: 閉じる',
        'zh': 'ESC 或点击外部：关闭',
        'ko': 'ESC 또는 바깥 클릭: 닫기'
    },
    'sos_contact_header': {
        'tr': 'Bize ulaşmak isterseniz aşağıdaki yöntemlerle ulaşabilirsiniz.',
        'en': 'If you want to contact us, you can use the methods below.',
        'de': 'Wenn Sie uns kontaktieren möchten, können Sie die folgenden Methoden verwenden.',
        'fr': 'Si vous souhaitez nous contacter, vous pouvez utiliser les méthodes ci-dessous.',
        'es': 'Si desea contactarnos, puede usar los métodos a continuación.',
        'it': 'Se vuoi contattarci, puoi usare i metodi qui sotto.',
        'pt': 'Se você quiser nos contatar, pode usar os métodos abaixo.',
        'zh': '如需联系我们，可使用以下方式。',
        'ko': '문의가 필요하시면 아래 방법을 이용해주세요.'
    },
    'sos_mail': {
        'tr': 'Mail Gönder (Gmail)',
        'en': 'Send Email (Gmail)',
        'de': 'E-Mail senden (Gmail)',
        'fr': 'Envoyer un e-mail (Gmail)',
        'es': 'Enviar correo (Gmail)',
        'it': 'Invia e-mail (Gmail)',
        'pt': 'Enviar e-mail (Gmail)',
        'zh': '发送邮件（Gmail）',
        'ko': '메일 보내기(Gmail)'
    },
    'sos_instagram': {
        'tr': 'Instagram',
        'en': 'Instagram',
        'de': 'Instagram',
        'fr': 'Instagram',
        'es': 'Instagram',
        'it': 'Instagram',
        'pt': 'Instagram',
        'zh': 'Instagram',
        'ko': '인스타그램'
    },
    'sos_email_subject': {
        'tr': 'Quadrix - SOS / Geri Bildirim',
        'en': 'Quadrix - SOS / Feedback',
        'de': 'Quadrix - SOS / Feedback',
        'fr': 'Quadrix - SOS / Commentaires',
        'es': 'Quadrix - SOS / Comentarios',
        'it': 'Quadrix - SOS / Feedback',
        'pt': 'Quadrix - SOS / Feedback',
        'zh': 'Quadrix - SOS / 反馈',
        'ko': 'Quadrix - SOS / 피드백'
    },
    'opening_gmail': {
        'tr': 'Gmail açılıyor...',
        'en': 'Opening Gmail...',
        'de': 'Gmail wird geöffnet...',
        'fr': 'Ouverture de Gmail...',
        'es': 'Abriendo Gmail...',
        'it': 'Apertura di Gmail...',
        'pt': 'Abrindo Gmail...',
        'zh': '正在打开 Gmail...',
        'ko': 'Gmail 여는 중...'
    },
    'opening_instagram': {
        'tr': 'Instagram açılıyor...',
        'en': 'Opening Instagram...',
        'de': 'Instagram wird geöffnet...',
        'fr': 'Ouverture d\'Instagram...',
        'es': 'Abriendo Instagram...',
        'it': 'Apertura di Instagram...',
        'pt': 'Abrindo Instagram...',
        'zh': '正在打开 Instagram...',
        'ko': 'Instagram 여는 중...'
    },
    'browser_open_failed': {
        'tr': 'Tarayıcı açılamadı.',
        'en': 'Could not open browser.',
        'de': 'Browser konnte nicht geöffnet werden.',
        'fr': 'Impossible d\'ouvrir le navigateur.',
        'es': 'No se pudo abrir el navegador.',
        'it': 'Impossibile aprire il browser.',
        'pt': 'Não foi possível abrir o navegador.',
        'zh': '无法打开浏览器。',
        'ko': '브라우저를 열 수 없습니다.'
    },
    'daily_completed_hint': {
        'tr': 'Tamamlandı ✓',
        'en': 'Completed ✓',
        'de': 'Abgeschlossen ✓',
        'fr': 'Terminé ✓',
        'es': 'Completado ✓',
        'it': 'Completato ✓',
        'pt': 'Concluído ✓',
        'zh': '已完成 ✓',
        'ko': '완료됨 ✓'
    },
    'daily_lives_remaining_hint': {
        'tr': 'Kalan hak: {remaining}/{max}',
        'en': 'Lives left: {remaining}/{max}',
        'de': 'Leben übrig: {remaining}/{max}',
        'fr': 'Vies restantes: {remaining}/{max}',
        'es': 'Vidas restantes: {remaining}/{max}',
        'it': 'Vite rimanenti: {remaining}/{max}',
        'pt': 'Vidas restantes: {remaining}/{max}',
        'zh': '剩余生命：{remaining}/{max}',
        'ko': '남은 목숨: {remaining}/{max}'
    },
    'select_user_hint': {
        'tr': 'Kullanıcı seç!',
        'en': 'Select a user!',
        'de': 'Benutzer auswählen!',
        'fr': 'Sélectionnez un utilisateur!',
        'es': '¡Selecciona un usuario!',
        'it': 'Seleziona un utente!',
        'pt': 'Selecione um usuário!',
        'zh': '请选择用户！',
        'ko': '사용자를 선택하세요!'
    },
    'how_to_play': {
        'tr': 'Nasıl Oynanır',
        'en': 'How to Play',
        'de': 'Spielanleitung',
        'fr': 'Comment Jouer',
        'es': 'Cómo Jugar',
        'it': 'Come Giocare',
        'pt': 'Como Jogar',
        'zh': '玩法说明',
        'ko': '플레이 방법'
    },
    
    # ======================= GENEL =======================
    'loading': {
        'tr': 'Yükleniyor...',
        'en': 'Loading...',
        'de': 'Laden...',
        'fr': 'Chargement...',
        'es': 'Cargando...',
        'it': 'Caricamento...',
        'pt': 'Carregando...',
        'zh': '加载中...',
        'ko': '로딩 중...'
    },
    'please_wait': {
        'tr': 'Lütfen bekleyin...',
        'en': 'Please wait...',
        'de': 'Bitte warten...',
        'fr': 'Veuillez patienter...',
        'es': 'Por favor espere...',
        'it': 'Attendere prego...',
        'pt': 'Por favor, aguarde...',
        'zh': '请稍候...',
        'ko': '잠시만 기다려주세요...'
    },
    'error': {
        'tr': 'Hata',
        'en': 'Error',
        'de': 'Fehler',
        'fr': 'Erreur',
        'es': 'Error',
        'it': 'Errore',
        'pt': 'Erro',
        'zh': '错误',
        'ko': '오류'
    },
    'success': {
        'tr': 'Başarılı',
        'en': 'Success',
        'de': 'Erfolg',
        'fr': 'Succès',
        'es': 'Éxito',
        'it': 'Successo',
        'pt': 'Sucesso',
        'zh': '成功',
        'ko': '성공'
    },
    'warning': {
        'tr': 'Uyarı',
        'en': 'Warning',
        'de': 'Warnung',
        'fr': 'Avertissement',
        'es': 'Advertencia',
        'it': 'Avviso',
        'pt': 'Aviso',
        'zh': '警告',
        'ko': '경고'
    },
    'user_most_held_piece_title': {
        'tr': 'En çok saklanılan parça',
        'en': 'Most Held Piece',
        'de': 'Meist gehaltenes Teil',
        'fr': 'Pièce la plus gardée',
        'es': 'Pieza más guardada',
        'it': 'Pezzo più conservato',
        'pt': 'Peça mais guardada',
        'ja': '最も保持したピース',
        'zh': '保留次数最多的方块',
        'ko': '가장 많이 홀드한 블록'
    },
    'user_piece_label': {
        'tr': 'Parça: {piece}',
        'en': 'Piece: {piece}',
        'de': 'Teil: {piece}',
        'fr': 'Pièce : {piece}',
        'es': 'Pieza: {piece}',
        'it': 'Pezzo: {piece}',
        'pt': 'Peça: {piece}',
        'ja': 'ピース: {piece}',
        'zh': '方块：{piece}',
        'ko': '블록: {piece}'
    },
    'user_held_count_label': {
        'tr': 'Saklandı: {count} kez',
        'en': 'Held: {count} times',
        'de': 'Gehalten: {count} Mal',
        'fr': 'Gardée : {count} fois',
        'es': 'Guardada: {count} veces',
        'it': 'Conservata: {count} volte',
        'pt': 'Guardada: {count} vezes',
        'ja': '保持: {count}回',
        'zh': '保留：{count} 次',
        'ko': '홀드: {count}회'
    },
    'user_validation_trailing_space': {
        'tr': 'Sonda boşluk olamaz.',
        'en': 'Trailing spaces are not allowed.',
        'de': 'Nachgestellte Leerzeichen sind nicht erlaubt.',
        'fr': 'Les espaces en fin ne sont pas autorisés.',
        'es': 'No se permiten espacios al final.',
        'it': 'Gli spazi finali non sono consentiti.',
        'pt': 'Espaços no fim não são permitidos.',
        'ja': '末尾の空白は使えません。',
        'zh': '末尾不能有空格。',
        'ko': '끝에 공백은 사용할 수 없습니다.'
    },
    'user_validation_empty': {
        'tr': 'Kullanıcı adı boş olamaz.',
        'en': 'Username cannot be empty.',
        'de': 'Benutzername darf nicht leer sein.',
        'fr': 'Le nom d\'utilisateur ne peut pas être vide.',
        'es': 'El nombre de usuario no puede estar vacío.',
        'it': 'Il nome utente non può essere vuoto.',
        'pt': 'O nome de usuário não pode estar vazio.',
        'ja': 'ユーザー名は空にできません。',
        'zh': '用户名不能为空。',
        'ko': '사용자 이름은 비워둘 수 없습니다.'
    },
    'user_validation_too_short': {
        'tr': 'Kullanıcı adı çok kısa (min 2 karakter).',
        'en': 'Username is too short (min 2 characters).',
        'de': 'Benutzername ist zu kurz (mind. 2 Zeichen).',
        'fr': 'Le nom d\'utilisateur est trop court (min. 2 caractères).',
        'es': 'El nombre de usuario es demasiado corto (mín. 2 caracteres).',
        'it': 'Il nome utente è troppo corto (min 2 caratteri).',
        'pt': 'O nome de usuário é muito curto (mín. 2 caracteres).',
        'ja': 'ユーザー名が短すぎます（最小2文字）。',
        'zh': '用户名太短（至少 2 个字符）。',
        'ko': '사용자 이름이 너무 짧습니다(최소 2자).'
    },
    'user_validation_too_long': {
        'tr': 'Kullanıcı adı çok uzun (max 20 karakter).',
        'en': 'Username is too long (max 20 characters).',
        'de': 'Benutzername ist zu lang (max. 20 Zeichen).',
        'fr': 'Le nom d\'utilisateur est trop long (max. 20 caractères).',
        'es': 'El nombre de usuario es demasiado largo (máx. 20 caracteres).',
        'it': 'Il nome utente è troppo lungo (max 20 caratteri).',
        'pt': 'O nome de usuário é muito longo (máx. 20 caracteres).',
        'ja': 'ユーザー名が長すぎます（最大20文字）。',
        'zh': '用户名太长（最多 20 个字符）。',
        'ko': '사용자 이름이 너무 깁니다(최대 20자).'
    },
    'user_validation_invalid_chars': {
        'tr': 'Sadece harf, rakam, boşluk ve _ - kullan.',
        'en': 'Use only letters, numbers, spaces, and _ - .',
        'de': 'Nur Buchstaben, Zahlen, Leerzeichen und _ - verwenden.',
        'fr': 'Utilisez uniquement des lettres, chiffres, espaces et _ - .',
        'es': 'Usa solo letras, números, espacios y _ - .',
        'it': 'Usa solo lettere, numeri, spazi e _ - .',
        'pt': 'Use apenas letras, números, espaços e _ - .',
        'ja': '使用できるのは文字・数字・空白・_・- のみです。',
        'zh': '仅可使用字母、数字、空格以及 _ - 。',
        'ko': '문자, 숫자, 공백, _ - 만 사용할 수 있습니다.'
    },
    'user_validation_exists': {
        'tr': 'Bu kullanıcı adı zaten var.',
        'en': 'This username already exists.',
        'de': 'Dieser Benutzername existiert bereits.',
        'fr': 'Ce nom d\'utilisateur existe déjà.',
        'es': 'Este nombre de usuario ya existe.',
        'it': 'Questo nome utente esiste già.',
        'pt': 'Este nome de usuário já existe.',
        'ja': 'このユーザー名は既に存在します。',
        'zh': '该用户名已存在。',
        'ko': '이미 존재하는 사용자 이름입니다.'
    },
    'user_validation_suggestion': {
        'tr': 'Öneri: {suggestion}',
        'en': 'Suggestion: {suggestion}',
        'de': 'Vorschlag: {suggestion}',
        'fr': 'Suggestion : {suggestion}',
        'es': 'Sugerencia: {suggestion}',
        'it': 'Suggerimento: {suggestion}',
        'pt': 'Sugestão: {suggestion}',
        'ja': '提案: {suggestion}',
        'zh': '建议：{suggestion}',
        'ko': '제안: {suggestion}'
    },
    'confirm': {
        'tr': 'Onayla',
        'en': 'Confirm',
        'de': 'Bestätigen',
        'fr': 'Confirmer',
        'es': 'Confirmar',
        'it': 'Conferma',
        'pt': 'Confirmar',
        'zh': '确认',
        'ko': '확인'
    },
    'cancel': {
        'tr': 'İptal',
        'en': 'Cancel',
        'de': 'Abbrechen',
        'fr': 'Annuler',
        'es': 'Cancelar',
        'it': 'Annulla',
        'pt': 'Cancelar',
        'zh': '取消',
        'ko': '취소'
    },
    'save': {
        'tr': 'Kaydet',
        'en': 'Save',
        'de': 'Speichern',
        'fr': 'Sauvegarder',
        'es': 'Guardar',
        'it': 'Salva',
        'pt': 'Salvar',
        'zh': '保存',
        'ko': '저장'
    },
    'delete': {
        'tr': 'Sil',
        'en': 'Delete',
        'de': 'Löschen',
        'fr': 'Supprimer',
        'es': 'Eliminar',
        'it': 'Elimina',
        'pt': 'Excluir',
        'zh': '删除',
        'ko': '삭제'
    },
    'select': {
        'tr': 'Seç',
        'en': 'Select',
        'de': 'Auswählen',
        'fr': 'Sélectionner',
        'es': 'Seleccionar',
        'it': 'Seleziona',
        'pt': 'Selecionar',
        'zh': '选择',
        'ko': '선택'
    },
    'arrows': {
        'tr': 'Ok Tuşları',
        'en': 'Arrow Keys',
        'de': 'Pfeiltasten',
        'fr': 'Touches Fléchées',
        'es': 'Teclas de Flecha',
        'it': 'Tasti Freccia',
        'pt': 'Teclas de Seta',
        'zh': '方向键',
        'ko': '방향키'
    },
    'space': {
        'tr': 'Boşluk',
        'en': 'Space',
        'de': 'Leertaste',
        'fr': 'Espace',
        'es': 'Espacio',
        'it': 'Spazio',
        'pt': 'Espaço',
        'zh': '空格',
        'ko': '스페이스'
    },
    'enter': {
        'tr': 'Enter',
        'en': 'Enter',
        'de': 'Enter',
        'fr': 'Entrée',
        'es': 'Enter',
        'it': 'Invio',
        'pt': 'Enter',
        'zh': '回车',
        'ko': '엔터'
    },
    'esc': {
        'tr': 'ESC',
        'en': 'ESC',
        'de': 'ESC',
        'fr': 'ÉCHAP',
        'es': 'ESC',
        'it': 'ESC',
        'pt': 'ESC',
        'zh': 'ESC',
        'ko': 'ESC'
    },
    
    # ======================= QUADRIX SPESİFİK =======================
    'tetris': {
        'tr': 'QUADRIX!',
        'en': 'QUADRIX!',
        'de': 'QUADRIX!',
        'fr': 'QUADRIX!',
        'es': '¡QUADRIX!',
        'it': 'QUADRIX!',
        'pt': 'QUADRIX!',
        'zh': 'QUADRIX!',
        'ko': 'QUADRIX!'
    },
    'tetris_label': {
        'tr': 'Quadrix',
        'en': 'Quadrix',
        'de': 'Quadrix',
        'fr': 'Quadrix',
        'es': 'Quadrix',
        'it': 'Quadrix',
        'pt': 'Quadrix',
        'zh': '俄罗斯方块',
        'ko': '테트리스'
    },
    'single': {
        'tr': 'SINGLE',
        'en': 'SINGLE',
        'de': 'SINGLE',
        'fr': 'SIMPLE',
        'es': 'SIMPLE',
        'it': 'SINGOLA',
        'pt': 'SIMPLES',
        'zh': '单消',
        'ko': '싱글'
    },
    'double': {
        'tr': 'DOUBLE',
        'en': 'DOUBLE',
        'de': 'DOUBLE',
        'fr': 'DOUBLE',
        'es': 'DOBLE',
        'it': 'DOPPIA',
        'pt': 'DUPLA',
        'zh': '双消',
        'ko': '더블'
    },
    'triple': {
        'tr': 'TRIPLE',
        'en': 'TRIPLE',
        'de': 'TRIPLE',
        'fr': 'TRIPLE',
        'es': 'TRIPLE',
        'it': 'TRIPLA',
        'pt': 'TRIPLA',
        'zh': '三消',
        'ko': '트리플'
    },
    'perfect_clear': {
        'tr': 'MÜKEMMEL TEMİZLİK!',
        'en': 'PERFECT CLEAR!',
        'de': 'PERFEKTE RÄUMUNG!',
        'fr': 'NETTOYAGE PARFAIT!',
        'es': '¡LIMPIEZA PERFECTA!',
        'it': 'PULIZIA PERFETTA!',
        'pt': 'LIMPEZA PERFEITA!',
        'zh': '完美消除！',
        'ko': '퍼펙트 클리어!'
    },
    'back_to_back': {
        'tr': 'ART ARDA!',
        'en': 'BACK TO BACK!',
        'de': 'AUFEINANDERFOLGEND!',
        'fr': 'CONSÉCUTIF!',
        'es': '¡CONSECUTIVO!',
        'it': 'CONSECUTIVO!',
        'pt': 'CONSECUTIVO!',
        'zh': '连击！',
        'ko': '백투백!'
    },
    't_spin': {
        'tr': 'T-SPIN!',
        'en': 'T-SPIN!',
        'de': 'T-SPIN!',
        'fr': 'T-SPIN!',
        'es': '¡T-SPIN!',
        'it': 'T-SPIN!',
        'pt': 'T-SPIN!',
        'zh': 'T-旋！',
        'ko': 'T-스핀!'
    },
    
    # ======================= KULLANICI =======================
    'username': {
        'tr': 'Kullanıcı Adı',
        'en': 'Username',
        'de': 'Benutzername',
        'fr': 'Nom d\'utilisateur',
        'es': 'Nombre de Usuario',
        'it': 'Nome Utente',
        'pt': 'Nome de Usuário',
        'zh': '用户名',
        'ko': '사용자 이름'
    },
    'guest': {
        'tr': 'Misafir',
        'en': 'Guest',
        'de': 'Gast',
        'fr': 'Invité',
        'es': 'Invitado',
        'it': 'Ospite',
        'pt': 'Convidado',
        'zh': '游客',
        'ko': '게스트'
    },
    'login': {
        'tr': 'Giriş Yap',
        'en': 'Login',
        'de': 'Anmelden',
        'fr': 'Connexion',
        'es': 'Iniciar Sesión',
        'it': 'Accedi',
        'pt': 'Entrar',
        'zh': '登录',
        'ko': '로그인'
    },
    'logout': {
        'tr': 'Çıkış Yap',
        'en': 'Logout',
        'de': 'Abmelden',
        'fr': 'Déconnexion',
        'es': 'Cerrar Sesión',
        'it': 'Esci',
        'pt': 'Sair',
        'zh': '退出登录',
        'ko': '로그아웃'
    },
    'profile': {
        'tr': 'Profil',
        'en': 'Profile',
        'de': 'Profil',
        'fr': 'Profil',
        'es': 'Perfil',
        'it': 'Profilo',
        'pt': 'Perfil',
        'zh': '个人资料',
        'ko': '프로필'
    },
    'total_games': {
        'tr': 'Toplam Oyun',
        'en': 'Total Games',
        'de': 'Gesamt Spiele',
        'fr': 'Total de Parties',
        'es': 'Total de Partidas',
        'it': 'Partite Totali',
        'pt': 'Total de Jogos',
        'zh': '总局数',
        'ko': '총 게임 수'
    },
    'total_score': {
        'tr': 'Toplam Skor',
        'en': 'Total Score',
        'de': 'Gesamtpunktzahl',
        'fr': 'Score Total',
        'es': 'Puntuación Total',
        'it': 'Punteggio Totale',
        'pt': 'Pontuação Total',
        'zh': '总分',
        'ko': '총 점수'
    },
    'best_score': {
        'tr': 'En İyi Skor',
        'en': 'Best Score',
        'de': 'Bester Punktestand',
        'fr': 'Meilleur Score',
        'es': 'Mejor Puntuación',
        'it': 'Miglior Punteggio',
        'pt': 'Melhor Pontuação',
        'zh': '最高分',
        'ko': '최고 점수'
    },
    'total_lines': {
        'tr': 'Toplam Satır',
        'en': 'Total Lines',
        'de': 'Gesamte Zeilen',
        'fr': 'Lignes Totales',
        'es': 'Líneas Totales',
        'it': 'Righe Totali',
        'pt': 'Linhas Totais',
        'zh': '总行数',
        'ko': '총 라인'
    },
    'highest_level': {
        'tr': 'En Yüksek Seviye',
        'en': 'Highest Level',
        'de': 'Höchstes Level',
        'fr': 'Niveau Max',
        'es': 'Nivel Máximo',
        'it': 'Livello Massimo',
        'pt': 'Nível Máximo',
        'zh': '最高等级',
        'ko': '최고 레벨'
    },
    'favorite_mode': {
        'tr': 'Favori Mod',
        'en': 'Favorite Mode',
        'de': 'Lieblingsmodus',
        'fr': 'Mode Favori',
        'es': 'Modo Favorito',
        'it': 'Modalità Preferita',
        'pt': 'Modo Favorito',
        'zh': '最常玩的模式',
        'ko': '선호 모드'
    },
    'user_last_played': {
        'tr': 'Son Oynama',
        'en': 'Last Played',
        'de': 'Zuletzt gespielt',
        'fr': 'Dernière Partie',
        'es': 'Última Partida',
        'it': 'Ultima Partita',
        'pt': 'Última Partida',
        'ja': '最終プレイ',
        'zh': '上次游玩',
        'ko': '마지막 플레이'
    },
    'user_never_played': {
        'tr': 'Hiç oynanmadı',
        'en': 'Never played',
        'de': 'Nie gespielt',
        'fr': 'Jamais joué',
        'es': 'Nunca jugado',
        'it': 'Mai giocato',
        'pt': 'Nunca jogado',
        'ja': '未プレイ',
        'zh': '从未游玩',
        'ko': '플레이 기록 없음'
    },
    'user_profile_summary': {
        'tr': 'Profil Özeti',
        'en': 'Profile Summary',
        'de': 'Profilübersicht',
        'fr': 'Résumé du Profil',
        'es': 'Resumen del Perfil',
        'it': 'Riepilogo Profilo',
        'pt': 'Resumo do Perfil',
        'ja': 'プロフィール概要',
        'zh': '个人资料概要',
        'ko': '프로필 요약'
    },
    'daily_no_user': {
        'tr': 'Önce bir kullanıcı seçmelisin!',
        'en': 'Please select a user first!',
        'de': 'Bitte zuerst einen Benutzer auswählen!',
        'fr': 'Veuillez d\'abord sélectionner un utilisateur !',
        'es': '¡Primero selecciona un usuario!',
        'it': 'Seleziona prima un utente!',
        'pt': 'Selecione um usuário primeiro!',
        'zh': '请先选择一个用户！',
        'ko': '먼저 사용자를 선택하세요!'
    },
    'daily_completed': {
        'tr': 'Bugünün görevi çoktan tamamlandı.',
        'en': 'Today\'s challenge is already completed.',
        'de': 'Die heutige Herausforderung ist bereits abgeschlossen.',
        'fr': 'Le défi d\'aujourd\'hui est déjà terminé.',
        'es': 'El desafío de hoy ya está completado.',
        'it': 'La sfida di oggi è già completata.',
        'pt': 'O desafio de hoje já foi concluído.',
        'zh': '今天的挑战已经完成。',
        'ko': '오늘의 도전은 이미 완료되었습니다.'
    },
    'daily_no_attempts': {
        'tr': 'Bugün tüm haklarını kullandın. Yarın tekrar dene!',
        'en': 'You used all attempts today. Try again tomorrow!',
        'de': 'Heute alle Versuche verbraucht. Morgen erneut versuchen!',
        'fr': 'Vous avez utilisé toutes les tentatives aujourd\'hui. Réessayez demain !',
        'es': 'Usaste todos los intentos hoy. ¡Inténtalo mañana!',
        'it': 'Hai usato tutti i tentativi oggi. Riprova domani!',
        'pt': 'Você usou todas as tentativas hoje. Tente amanhã!',
        'zh': '你今天已用完所有次数。明天再试！',
        'ko': '오늘의 시도를 모두 사용했습니다. 내일 다시 시도하세요!'
    },
    'user_create_empty': {
        'tr': 'Kullanıcı adı boş olamaz!',
        'en': 'Username cannot be empty!',
        'de': 'Benutzername darf nicht leer sein!',
        'fr': 'Le nom d\'utilisateur ne peut pas être vide !',
        'es': '¡El nombre de usuario no puede estar vacío!',
        'it': 'Il nome utente non può essere vuoto!',
        'pt': 'O nome de usuário não pode estar vazio!',
        'ja': 'ユーザー名は空にできません！',
        'zh': '用户名不能为空！',
        'ko': '사용자 이름은 비워둘 수 없습니다!'
    },
    'user_create_exists': {
        'tr': 'Bu kullanıcı adı zaten mevcut!',
        'en': 'This username already exists!',
        'de': 'Dieser Benutzername existiert bereits!',
        'fr': 'Ce nom d\'utilisateur existe déjà !',
        'es': '¡Este nombre de usuario ya existe!',
        'it': 'Questo nome utente esiste già!',
        'pt': 'Este nome de usuário já existe!',
        'ja': 'このユーザー名は既に存在します！',
        'zh': '该用户名已存在！',
        'ko': '이미 존재하는 사용자 이름입니다!'
    },
    'user_create_too_long': {
        'tr': 'Kullanıcı adı çok uzun! (Max 20 karakter)',
        'en': 'Username is too long! (Max 20 characters)',
        'de': 'Benutzername ist zu lang! (Max. 20 Zeichen)',
        'fr': 'Le nom d\'utilisateur est trop long ! (Max 20 caractères)',
        'es': '¡El nombre de usuario es demasiado largo! (Máx 20 caracteres)',
        'it': 'Il nome utente è troppo lungo! (Max 20 caratteri)',
        'pt': 'O nome de usuário é muito longo! (Máx 20 caracteres)',
        'ja': 'ユーザー名が長すぎます！（最大20文字）',
        'zh': '用户名太长！（最多 20 个字符）',
        'ko': '사용자 이름이 너무 깁니다! (최대 20자)'
    },
    'user_create_success': {
        'tr': 'Kullanıcı başarıyla oluşturuldu!',
        'en': 'User created successfully!',
        'de': 'Benutzer erfolgreich erstellt!',
        'fr': 'Utilisateur créé avec succès !',
        'es': '¡Usuario creado con éxito!',
        'it': 'Utente creato con successo!',
        'pt': 'Usuário criado com sucesso!',
        'ja': 'ユーザーを作成しました！',
        'zh': '用户创建成功！',
        'ko': '사용자가 성공적으로 생성되었습니다!'
    },
    'user_delete_not_found': {
        'tr': 'Kullanıcı bulunamadı!',
        'en': 'User not found!',
        'de': 'Benutzer nicht gefunden!',
        'fr': 'Utilisateur introuvable !',
        'es': '¡Usuario no encontrado!',
        'it': 'Utente non trovato!',
        'pt': 'Usuário não encontrado!',
        'ja': 'ユーザーが見つかりません！',
        'zh': '找不到用户！',
        'ko': '사용자를 찾을 수 없습니다!'
    },
    'user_deleted': {
        'tr': 'Kullanıcı silindi!',
        'en': 'User deleted!',
        'de': 'Benutzer gelöscht!',
        'fr': 'Utilisateur supprimé !',
        'es': '¡Usuario eliminado!',
        'it': 'Utente eliminato!',
        'pt': 'Usuário excluído!',
        'ja': 'ユーザーを削除しました！',
        'zh': '用户已删除！',
        'ko': '사용자가 삭제되었습니다!'
    },
    'user_select_not_found': {
        'tr': 'Kullanıcı bulunamadı!',
        'en': 'User not found!',
        'de': 'Benutzer nicht gefunden!',
        'fr': 'Utilisateur introuvable !',
        'es': '¡Usuario no encontrado!',
        'it': 'Utente non trovato!',
        'pt': 'Usuário não encontrado!',
        'ja': 'ユーザーが見つかりません！',
        'zh': '找不到用户！',
        'ko': '사용자를 찾을 수 없습니다!'
    },
    'user_selected': {
        'tr': '{username} aktif kullanıcı olarak seçildi!',
        'en': '{username} selected as active user!',
        'de': '{username} als aktiver Benutzer ausgewählt!',
        'fr': '{username} sélectionné comme utilisateur actif !',
        'es': '¡{username} seleccionado como usuario activo!',
        'it': '{username} selezionato come utente attivo!',
        'pt': '{username} selecionado como usuário ativo!',
        'ja': '{username} をアクティブユーザーに設定しました！',
        'zh': '已将 {username} 设为当前用户！',
        'ko': '{username} 사용자가 활성 사용자로 선택되었습니다!'
    },
    'user_avatar_updated': {
        'tr': 'Avatar güncellendi!',
        'en': 'Avatar updated!',
        'de': 'Avatar aktualisiert!',
        'fr': 'Avatar mis à jour !',
        'es': '¡Avatar actualizado!',
        'it': 'Avatar aggiornato!',
        'pt': 'Avatar atualizado!',
        'ja': 'アバターを更新しました！',
        'zh': '头像已更新！',
        'ko': '아바타가 업데이트되었습니다!'
    },
    'user_action_delete_profile': {
        'tr': 'DEL : Profili Sil',
        'en': 'DEL : Delete Profile',
        'de': 'ENTF : Profil löschen',
        'fr': 'SUPPR : Supprimer profil',
        'es': 'SUPR : Eliminar perfil',
        'it': 'CANC : Elimina profilo',
        'pt': 'DEL : Excluir perfil',
        'ja': 'DEL : プロフィール削除',
        'zh': 'DEL：删除资料',
        'ko': 'DEL: 프로필 삭제'
    },
    'user_action_edit_profile': {
        'tr': 'ENTER : Profili Düzenle',
        'en': 'ENTER : Edit Profile',
        'de': 'ENTER : Profil bearbeiten',
        'fr': 'ENTRÉE : Modifier profil',
        'es': 'ENTER : Editar perfil',
        'it': 'INVIO : Modifica profilo',
        'pt': 'ENTER : Editar perfil',
        'ja': 'ENTER : プロフィール編集',
        'zh': 'ENTER：编辑资料',
        'ko': 'ENTER: 프로필 편집'
    },
    'user_avatar_select': {
        'tr': 'Avatar Seçimi',
        'en': 'Avatar Selection',
        'de': 'Avatar-Auswahl',
        'fr': 'Sélection d\'avatar',
        'es': 'Selección de Avatar',
        'it': 'Selezione Avatar',
        'pt': 'Seleção de Avatar',
        'ja': 'アバター選択',
        'zh': '选择头像',
        'ko': '아바타 선택'
    },
    'user_profile_info': {
        'tr': 'Profil Bilgileri',
        'en': 'Profile Info',
        'de': 'Profilinfos',
        'fr': 'Infos du Profil',
        'es': 'Info de Perfil',
        'it': 'Info Profilo',
        'pt': 'Info do Perfil',
        'ja': 'プロフィール情報',
        'zh': '资料信息',
        'ko': '프로필 정보'
    },
    'user_account_info': {
        'tr': 'Kullanıcı Bilgileri',
        'en': 'User Info',
        'de': 'Benutzerinfos',
        'fr': 'Infos Utilisateur',
        'es': 'Info de Usuario',
        'it': 'Info Utente',
        'pt': 'Info do Usuário',
        'ja': 'ユーザー情報',
        'zh': '用户信息',
        'ko': '사용자 정보'
    },
    'user_username_placeholder': {
        'tr': 'Kullanıcı adını yaz...',
        'en': 'Type a username...',
        'de': 'Benutzernamen eingeben...',
        'fr': 'Saisissez un nom d\'utilisateur...',
        'es': 'Escribe un nombre de usuario...',
        'it': 'Inserisci un nome utente...',
        'pt': 'Digite um nome de usuário...',
        'ja': 'ユーザー名を入力...',
        'zh': '输入用户名...',
        'ko': '사용자 이름 입력...'
    },
    'user_action_save': {
        'tr': 'Kaydet (Enter)',
        'en': 'Save (Enter)',
        'de': 'Speichern (Enter)',
        'fr': 'Enregistrer (Entrée)',
        'es': 'Guardar (Enter)',
        'it': 'Salva (Invio)',
        'pt': 'Salvar (Enter)',
        'ja': '保存 (Enter)',
        'zh': '保存 (Enter)',
        'ko': '저장 (Enter)'
    },
    'user_action_create': {
        'tr': 'Oluştur (Enter)',
        'en': 'Create (Enter)',
        'de': 'Erstellen (Enter)',
        'fr': 'Créer (Entrée)',
        'es': 'Crear (Enter)',
        'it': 'Crea (Invio)',
        'pt': 'Criar (Enter)',
        'ja': '作成 (Enter)',
        'zh': '创建 (Enter)',
        'ko': '생성 (Enter)'
    },
    'user_action_back_esc': {
        'tr': 'Geri (ESC)',
        'en': 'Back (ESC)',
        'de': 'Zurück (ESC)',
        'fr': 'Retour (Échap)',
        'es': 'Atrás (ESC)',
        'it': 'Indietro (ESC)',
        'pt': 'Voltar (ESC)',
        'ja': '戻る (ESC)',
        'zh': '返回 (ESC)',
        'ko': '뒤로 (ESC)'
    },
    'user_hint_save': {
        'tr': 'ENTER ile kaydet, ESC ile vazgeç.',
        'en': 'Press ENTER to save, ESC to cancel.',
        'de': 'ENTER zum Speichern, ESC zum Abbrechen.',
        'fr': 'ENTRÉE pour enregistrer, ÉCHAP pour annuler.',
        'es': 'ENTER para guardar, ESC para cancelar.',
        'it': 'INVIO per salvare, ESC per annullare.',
        'pt': 'ENTER para salvar, ESC para cancelar.',
        'ja': 'ENTERで保存、ESCでキャンセル。',
        'zh': '按 ENTER 保存，ESC 取消。',
        'ko': 'ENTER로 저장, ESC로 취소.'
    },
    'user_hint_create': {
        'tr': 'ENTER ile oluştur, ESC ile geri dön.',
        'en': 'Press ENTER to create, ESC to go back.',
        'de': 'ENTER zum Erstellen, ESC zum Zurückgehen.',
        'fr': 'ENTRÉE pour créer, ÉCHAP pour revenir.',
        'es': 'ENTER para crear, ESC para volver.',
        'it': 'INVIO per creare, ESC per tornare indietro.',
        'pt': 'ENTER para criar, ESC para voltar.',
        'ja': 'ENTERで作成、ESCで戻る。',
        'zh': '按 ENTER 创建，ESC 返回。',
        'ko': 'ENTER로 생성, ESC로 돌아가기.'
    },
    'user_select_title': {
        'tr': 'KULLANICI SEÇ',
        'en': 'SELECT USER',
        'de': 'BENUTZER WÄHLEN',
        'fr': 'SÉLECTIONNER UTILISATEUR',
        'es': 'SELECCIONAR USUARIO',
        'it': 'SELEZIONA UTENTE',
        'pt': 'SELECIONAR USUÁRIO',
        'ja': 'ユーザー選択',
        'zh': '选择用户',
        'ko': '사용자 선택'
    },
    'user_profiles': {
        'tr': 'Profiller',
        'en': 'Profiles',
        'de': 'Profile',
        'fr': 'Profils',
        'es': 'Perfiles',
        'it': 'Profili',
        'pt': 'Perfis',
        'ja': 'プロフィール',
        'zh': '资料',
        'ko': '프로필'
    },
    'user_edit_profile_title': {
        'tr': 'PROFİLİ DÜZENLE',
        'en': 'EDIT PROFILE',
        'de': 'PROFIL BEARBEITEN',
        'fr': 'MODIFIER LE PROFIL',
        'es': 'EDITAR PERFIL',
        'it': 'MODIFICA PROFILO',
        'pt': 'EDITAR PERFIL',
        'ja': 'プロフィール編集',
        'zh': '编辑资料',
        'ko': '프로필 편집'
    },
    'user_new_user_title': {
        'tr': 'YENİ KULLANICI',
        'en': 'NEW USER',
        'de': 'NEUER BENUTZER',
        'fr': 'NOUVEL UTILISATEUR',
        'es': 'NUEVO USUARIO',
        'it': 'NUOVO UTENTE',
        'pt': 'NOVO USUÁRIO',
        'ja': '新規ユーザー',
        'zh': '新用户',
        'ko': '새 사용자'
    },
    'user_helper_edit': {
        'tr': 'Avatarını güncelle ve kaydet.',
        'en': 'Update your avatar and save.',
        'de': 'Avatar aktualisieren und speichern.',
        'fr': 'Mettez à jour votre avatar et enregistrez.',
        'es': 'Actualiza tu avatar y guarda.',
        'it': 'Aggiorna il tuo avatar e salva.',
        'pt': 'Atualize seu avatar e salve.',
        'ja': 'アバターを更新して保存。',
        'zh': '更新头像并保存。',
        'ko': '아바타를 업데이트하고 저장하세요.'
    },
    'user_helper_create': {
        'tr': 'Avatarını seç, adını yaz ve hemen başla.',
        'en': 'Choose your avatar, enter a name, and start right away.',
        'de': 'Avatar wählen, Namen eingeben und sofort starten.',
        'fr': 'Choisissez un avatar, saisissez un nom et commencez.',
        'es': 'Elige un avatar, escribe un nombre y comienza.',
        'it': 'Scegli un avatar, inserisci un nome e inizia subito.',
        'pt': 'Escolha um avatar, digite um nome e comece.',
        'ja': 'アバターを選び、名前を入力してすぐ開始。',
        'zh': '选择头像，输入名字，立即开始。',
        'ko': '아바타를 선택하고 이름을 입력한 뒤 바로 시작하세요.'
    },
    'user_panel_edit': {
        'tr': 'Profil Düzenle',
        'en': 'Edit Profile',
        'de': 'Profil bearbeiten',
        'fr': 'Modifier le profil',
        'es': 'Editar perfil',
        'it': 'Modifica profilo',
        'pt': 'Editar perfil',
        'ja': 'プロフィール編集',
        'zh': '编辑资料',
        'ko': '프로필 편집'
    },
    'user_panel_create': {
        'tr': 'Profil Oluştur',
        'en': 'Create Profile',
        'de': 'Profil erstellen',
        'fr': 'Créer un profil',
        'es': 'Crear perfil',
        'it': 'Crea profilo',
        'pt': 'Criar perfil',
        'ja': 'プロフィール作成',
        'zh': '创建资料',
        'ko': '프로필 생성'
    },
    'user_set_active_message': {
        'tr': '{username} aktif kullanıcı',
        'en': '{username} is now active',
        'de': '{username} ist jetzt aktiv',
        'fr': '{username} est maintenant actif',
        'es': '{username} ahora está activo',
        'it': '{username} è ora attivo',
        'pt': '{username} agora está ativo',
        'ja': '{username} を有効化',
        'zh': '{username} 已设为当前用户',
        'ko': '{username} 활성 사용자로 설정됨'
    },
    'user_profile_saved': {
        'tr': 'Profil kaydedildi!',
        'en': 'Profile saved!',
        'de': 'Profil gespeichert!',
        'fr': 'Profil enregistré !',
        'es': '¡Perfil guardado!',
        'it': 'Profilo salvato!',
        'pt': 'Perfil salvo!',
        'ja': 'プロフィールを保存しました！',
        'zh': '资料已保存！',
        'ko': '프로필이 저장되었습니다!'
    },
    'user_stats_summary': {
        'tr': '{games} oyun  •  {score} puan  •  {lines} satır',
        'en': '{games} games  •  {score} points  •  {lines} lines',
        'de': '{games} Spiele  •  {score} Punkte  •  {lines} Zeilen',
        'fr': '{games} parties  •  {score} points  •  {lines} lignes',
        'es': '{games} partidas  •  {score} puntos  •  {lines} líneas',
        'it': '{games} partite  •  {score} punti  •  {lines} linee',
        'pt': '{games} jogos  •  {score} pontos  •  {lines} linhas',
        'ja': '{games}回  •  {score}点  •  {lines}ライン',
        'zh': '{games} 局  •  {score} 分  •  {lines} 行',
        'ko': '{games}판  •  {score}점  •  {lines}줄'
    },
    'user_set_active': {
        'tr': 'Aktif Yap',
        'en': 'Set Active',
        'de': 'Aktiv setzen',
        'fr': 'Rendre actif',
        'es': 'Hacer activo',
        'it': 'Imposta attivo',
        'pt': 'Definir ativo',
        'ja': '有効にする',
        'zh': '设为当前',
        'ko': '활성화'
    },
    'user_delete_confirm_line1': {
        'tr': '"{username}" kullanıcısını',
        'en': 'Delete user "{username}"',
        'de': 'Benutzer "{username}" löschen',
        'fr': 'Supprimer l\'utilisateur « {username} »',
        'es': 'Eliminar al usuario "{username}"',
        'it': 'Eliminare l\'utente "{username}"',
        'pt': 'Excluir o usuário "{username}"',
        'ja': 'ユーザー「{username}」を',
        'zh': '删除用户“{username}”',
        'ko': '사용자 "{username}"을'
    },
    'user_delete_confirm_line2': {
        'tr': 'kalıcı olarak silmek istediğinizden emin misiniz?',
        'en': 'Are you sure you want to delete permanently?',
        'de': 'Möchtest du endgültig löschen?',
        'fr': 'Voulez-vous vraiment supprimer définitivement ?',
        'es': '¿Seguro que quieres eliminar permanentemente?',
        'it': 'Sei sicuro di voler eliminare definitivamente?',
        'pt': 'Tem certeza de que deseja excluir permanentemente?',
        'ja': '完全に削除してもよろしいですか？',
        'zh': '确定要永久删除吗？',
        'ko': '영구 삭제하시겠습니까?'
    },
    'user_mode_games': {
        'tr': '{games} oyun',
        'en': '{games} games',
        'de': '{games} Spiele',
        'fr': '{games} parties',
        'es': '{games} partidas',
        'it': '{games} partite',
        'pt': '{games} jogos',
        'ja': '{games}回',
        'zh': '{games} 局',
        'ko': '{games}판'
    },
    'user_action_edit': {
        'tr': 'Düzenle',
        'en': 'Edit',
        'de': 'Bearbeiten',
        'fr': 'Modifier',
        'es': 'Editar',
        'it': 'Modifica',
        'pt': 'Editar',
        'ja': '編集',
        'zh': '编辑',
        'ko': '편집'
    },
    'user_field_avatar': {
        'tr': 'Avatar',
        'en': 'Avatar',
        'de': 'Avatar',
        'fr': 'Avatar',
        'es': 'Avatar',
        'it': 'Avatar',
        'pt': 'Avatar',
        'ja': 'アバター',
        'zh': '头像',
        'ko': '아바타'
    },
    'user_field_color': {
        'tr': 'Renk',
        'en': 'Color',
        'de': 'Farbe',
        'fr': 'Couleur',
        'es': 'Color',
        'it': 'Colore',
        'pt': 'Cor',
        'ja': '色',
        'zh': '颜色',
        'ko': '색상'
    },
    'user_field_bio': {
        'tr': 'Açıklama',
        'en': 'Bio',
        'de': 'Beschreibung',
        'fr': 'Description',
        'es': 'Descripción',
        'it': 'Descrizione',
        'pt': 'Descrição',
        'ja': '自己紹介',
        'zh': '简介',
        'ko': '소개'
    },
    'user_field_favorite_mode': {
        'tr': 'Favori Mod',
        'en': 'Favorite Mode',
        'de': 'Lieblingsmodus',
        'fr': 'Mode Favori',
        'es': 'Modo Favorito',
        'it': 'Modalità Preferita',
        'pt': 'Modo Favorito',
        'ja': 'お気に入りモード',
        'zh': '喜欢的模式',
        'ko': '선호 모드'
    },
    'user_field_empty': {
        'tr': '(Boş)',
        'en': '(Empty)',
        'de': '(Leer)',
        'fr': '(Vide)',
        'es': '(Vacío)',
        'it': '(Vuoto)',
        'pt': '(Vazio)',
        'ja': '(空)',
        'zh': '(空)',
        'ko': '(비어 있음)'
    },
    'color_blue': {
        'tr': 'Mavi',
        'en': 'Blue',
        'de': 'Blau',
        'fr': 'Bleu',
        'es': 'Azul',
        'it': 'Blu',
        'pt': 'Azul',
        'zh': '蓝色',
        'ko': '파랑'
    },
    'color_red': {
        'tr': 'Kırmızı',
        'en': 'Red',
        'de': 'Rot',
        'fr': 'Rouge',
        'es': 'Rojo',
        'it': 'Rosso',
        'pt': 'Vermelho',
        'zh': '红色',
        'ko': '빨강'
    },
    'color_green': {
        'tr': 'Yeşil',
        'en': 'Green',
        'de': 'Grün',
        'fr': 'Vert',
        'es': 'Verde',
        'it': 'Verde',
        'pt': 'Verde',
        'zh': '绿色',
        'ko': '초록'
    },
    'color_yellow': {
        'tr': 'Sarı',
        'en': 'Yellow',
        'de': 'Gelb',
        'fr': 'Jaune',
        'es': 'Amarillo',
        'it': 'Giallo',
        'pt': 'Amarelo',
        'zh': '黄色',
        'ko': '노랑'
    },
    'color_pink': {
        'tr': 'Pembe',
        'en': 'Pink',
        'de': 'Rosa',
        'fr': 'Rose',
        'es': 'Rosa',
        'it': 'Rosa',
        'pt': 'Rosa',
        'zh': '粉色',
        'ko': '분홍'
    },
    'color_cyan': {
        'tr': 'Cyan',
        'en': 'Cyan',
        'de': 'Cyan',
        'fr': 'Cyan',
        'es': 'Cian',
        'it': 'Ciano',
        'pt': 'Ciano',
        'zh': '青色',
        'ko': '시안'
    },
    'color_orange': {
        'tr': 'Turuncu',
        'en': 'Orange',
        'de': 'Orange',
        'fr': 'Orange',
        'es': 'Naranja',
        'it': 'Arancione',
        'pt': 'Laranja',
        'zh': '橙色',
        'ko': '주황'
    },
    'color_purple': {
        'tr': 'Mor',
        'en': 'Purple',
        'de': 'Lila',
        'fr': 'Violet',
        'es': 'Morado',
        'it': 'Viola',
        'pt': 'Roxo',
        'zh': '紫色',
        'ko': '보라'
    },
    'user_help_avatar_switch': {
        'tr': 'Sol/Sağ tuşları ile Avatar Değiştir',
        'en': 'Use Left/Right to change avatar',
        'de': 'Links/Rechts zum Avatarwechsel',
        'fr': 'Gauche/Droite pour changer d\'avatar',
        'es': 'Izquierda/Derecha para cambiar avatar',
        'it': 'Sinistra/Destra per cambiare avatar',
        'pt': 'Esquerda/Direita para trocar avatar',
        'ja': '左右キーでアバター変更',
        'zh': '用左右键切换头像',
        'ko': '좌/우 키로 아바타 변경'
    },
    'user_help_avatar_count': {
        'tr': '{count} farklı avatar mevcut',
        'en': '{count} avatars available',
        'de': '{count} Avatare verfügbar',
        'fr': '{count} avatars disponibles',
        'es': '{count} avatares disponibles',
        'it': '{count} avatar disponibili',
        'pt': '{count} avatares disponíveis',
        'ja': '{count}種類のアバター',
        'zh': '有 {count} 个头像可用',
        'ko': '사용 가능한 아바타 {count}개'
    },
    'user_help_avatar_custom': {
        'tr': 'C tuşu ile özel resim yükle',
        'en': 'Press C to upload a custom image',
        'de': 'Mit C ein eigenes Bild laden',
        'fr': 'Appuyez sur C pour charger une image',
        'es': 'Pulsa C para cargar una imagen',
        'it': 'Premi C per caricare un\'immagine',
        'pt': 'Pressione C para enviar uma imagem',
        'ja': 'Cでカスタム画像を読み込み',
        'zh': '按 C 上传自定义图片',
        'ko': 'C 키로 사용자 이미지 업로드'
    },
    'user_help_color_switch': {
        'tr': 'Sol/Sağ tuşları ile Renk Değiştir',
        'en': 'Use Left/Right to change color',
        'de': 'Links/Rechts zum Farbwechsel',
        'fr': 'Gauche/Droite pour changer de couleur',
        'es': 'Izquierda/Derecha para cambiar color',
        'it': 'Sinistra/Destra per cambiare colore',
        'pt': 'Esquerda/Direita para mudar a cor',
        'ja': '左右キーで色変更',
        'zh': '用左右键切换颜色',
        'ko': '좌/우 키로 색상 변경'
    },
    'user_help_color_count': {
        'tr': '{count} farklı renk mevcut',
        'en': '{count} colors available',
        'de': '{count} Farben verfügbar',
        'fr': '{count} couleurs disponibles',
        'es': '{count} colores disponibles',
        'it': '{count} colori disponibili',
        'pt': '{count} cores disponíveis',
        'ja': '{count}色',
        'zh': '有 {count} 种颜色',
        'ko': '사용 가능한 색상 {count}개'
    },
    'user_help_bio_input': {
        'tr': 'Karakter Gir veya BACKSPACE',
        'en': 'Type or use BACKSPACE',
        'de': 'Tippen oder BACKSPACE verwenden',
        'fr': 'Saisir ou utiliser RETOUR ARRIÈRE',
        'es': 'Escribe o usa BACKSPACE',
        'it': 'Digita o usa BACKSPACE',
        'pt': 'Digite ou use BACKSPACE',
        'ja': '入力／BACKSPACE',
        'zh': '输入或使用 BACKSPACE',
        'ko': '입력하거나 BACKSPACE 사용'
    },
    'user_help_bio_count': {
        'tr': '{count}/{max} karakter',
        'en': '{count}/{max} characters',
        'de': '{count}/{max} Zeichen',
        'fr': '{count}/{max} caractères',
        'es': '{count}/{max} caracteres',
        'it': '{count}/{max} caratteri',
        'pt': '{count}/{max} caracteres',
        'ja': '{count}/{max}文字',
        'zh': '{count}/{max} 字符',
        'ko': '{count}/{max}자'
    },
    'user_help_mode_switch': {
        'tr': 'Sol/Sağ tuşları ile Favori Mod Seç',
        'en': 'Use Left/Right to choose favorite mode',
        'de': 'Links/Rechts für Lieblingsmodus',
        'fr': 'Gauche/Droite pour mode favori',
        'es': 'Izquierda/Derecha para modo favorito',
        'it': 'Sinistra/Destra per modalità preferita',
        'pt': 'Esquerda/Direita para modo favorito',
        'ja': '左右キーでお気に入りモード選択',
        'zh': '用左右键选择喜欢的模式',
        'ko': '좌/우 키로 선호 모드 선택'
    },
    'user_help_mode_count': {
        'tr': '{count} farklı mod',
        'en': '{count} modes',
        'de': '{count} Modi',
        'fr': '{count} modes',
        'es': '{count} modos',
        'it': '{count} modalità',
        'pt': '{count} modos',
        'ja': '{count}種類のモード',
        'zh': '{count} 种模式',
        'ko': '{count}가지 모드'
    },
    'user_control_change_field': {
        'tr': 'Alan Değiştir',
        'en': 'Change Field',
        'de': 'Feld wechseln',
        'fr': 'Changer de champ',
        'es': 'Cambiar campo',
        'it': 'Cambia campo',
        'pt': 'Mudar campo',
        'ja': '項目変更',
        'zh': '切换字段',
        'ko': '항목 변경'
    },
    'user_control_change_value': {
        'tr': 'Değer Değiştir',
        'en': 'Change Value',
        'de': 'Wert ändern',
        'fr': 'Changer de valeur',
        'es': 'Cambiar valor',
        'it': 'Cambia valore',
        'pt': 'Mudar valor',
        'ja': '値変更',
        'zh': '更改数值',
        'ko': '값 변경'
    },
    'user_control_custom_avatar': {
        'tr': 'Özel Avatar',
        'en': 'Custom Avatar',
        'de': 'Benutzer-Avatar',
        'fr': 'Avatar personnalisé',
        'es': 'Avatar personalizado',
        'it': 'Avatar personalizzato',
        'pt': 'Avatar personalizado',
        'ja': 'カスタムアバター',
        'zh': '自定义头像',
        'ko': '커스텀 아바타'
    },
    'keys_tab_up_down': {
        'tr': 'Tab/Yukarı/Aşağı',
        'en': 'Tab/Up/Down',
        'de': 'Tab/Hoch/Runter',
        'fr': 'Tab/Haut/Bas',
        'es': 'Tab/Arriba/Abajo',
        'it': 'Tab/Su/Giù',
        'pt': 'Tab/Cima/Baixo',
        'zh': 'Tab/上/下',
        'ko': 'Tab/위/아래'
    },
    'keys_left_right': {
        'tr': 'Sol/Sağ',
        'en': 'Left/Right',
        'de': 'Links/Rechts',
        'fr': 'Gauche/Droite',
        'es': 'Izquierda/Derecha',
        'it': 'Sinistra/Destra',
        'pt': 'Esquerda/Direita',
        'zh': '左/右',
        'ko': '왼쪽/오른쪽'
    },
    'user_no_bio': {
        'tr': 'Henüz bir açıklama eklenmemiş',
        'en': 'No bio added yet',
        'de': 'Noch keine Beschreibung',
        'fr': 'Aucune description pour le moment',
        'es': 'Aún no hay descripción',
        'it': 'Nessuna descrizione ancora',
        'pt': 'Nenhuma descrição ainda',
        'ja': '自己紹介なし',
        'zh': '暂无简介',
        'ko': '소개가 아직 없습니다'
    },
    'highest_combo': {
        'tr': 'En Yüksek Combo',
        'en': 'Highest Combo',
        'de': 'Höchste Combo',
        'fr': 'Combo Max',
        'es': 'Combo Máximo',
        'it': 'Combo Massima',
        'pt': 'Combo Máximo',
        'zh': '最高连击',
        'ko': '최대 콤보'
    },
    'total_tetrises': {
        'tr': 'Quadrix Sayısı',
        'en': 'Quadrix Count',
        'de': 'Anzahl Quadrix',
        'fr': 'Nombre de Quadrix',
        'es': 'Cantidad de Quadrix',
        'it': 'Numero di Quadrix',
        'pt': 'Quantidade de Quadrix',
        'zh': '四消次数',
        'ko': '테트리스 횟수'
    },
    'play_time': {
        'tr': 'Oynama Süresi',
        'en': 'Play Time',
        'de': 'Spielzeit',
        'fr': 'Temps de Jeu',
        'es': 'Tiempo de Juego',
        'it': 'Tempo di Gioco',
        'pt': 'Tempo de Jogo',
        'zh': '游玩时间',
        'ko': '플레이 시간'
    },
    
    # ======================= YENİ NESİL QUADRIX =======================
    'energy': {
        'tr': 'Enerji',
        'en': 'Energy',
        'de': 'Energie',
        'fr': 'Énergie',
        'es': 'Energía',
        'it': 'Energia',
        'pt': 'Energia',
        'ja': 'エネルギー',
        'zh': '能量',
        'ko': '에너지'
    },
    'perks': {
        'tr': 'Yetenekler',
        'en': 'Perks',
        'de': 'Fähigkeiten',
        'fr': 'Avantages',
        'es': 'Ventajas',
        'it': 'Vantaggi',
        'pt': 'Vantagens',
        'ja': 'パーク',
        'zh': '能力',
        'ko': '특성'
    },
    'cards': {
        'tr': 'Kartlar',
        'en': 'Cards',
        'de': 'Karten',
        'fr': 'Cartes',
        'es': 'Cartas',
        'it': 'Carte',
        'pt': 'Cartas',
        'ja': 'カード',
        'zh': '卡牌',
        'ko': '카드'
    },
    'level_up': {
        'tr': 'SEVİYE ATLADIN!',
        'en': 'LEVEL UP!',
        'de': 'LEVEL UP!',
        'fr': 'NIVEAU SUPÉRIEUR!',
        'es': '¡SUBISTE DE NIVEL!',
        'it': 'LIVELLO AUMENTATO!',
        'pt': 'SUBIU DE NÍVEL!',
        'ja': 'レベルアップ！',
        'zh': '升级！',
        'ko': '레벨 업!'
    },
    'choose_perk': {
        'tr': 'Yetenek Seç',
        'en': 'Choose Perk',
        'de': 'Fähigkeit wählen',
        'fr': 'Choisir un Avantage',
        'es': 'Elegir Ventaja',
        'it': 'Scegli un Vantaggio',
        'pt': 'Escolher Vantagem',
        'ja': 'パークを選択',
        'zh': '选择能力',
        'ko': '특성 선택'
    },
    
    # ======================= İPUÇLARI =======================
    'tip_hold': {
        'tr': 'C tuşu ile parça saklayabilirsin',
        'en': 'Press C to hold a piece',
        'de': 'Drücke C um ein Teil zu halten',
        'fr': 'Appuyez sur C pour garder une pièce',
        'es': 'Presiona C para guardar una pieza',
        'it': 'Premi C per tenere un pezzo',
        'pt': 'Pressione C para guardar uma peça',
        'ja': 'Cでピースをホールドできます',
        'zh': '按 C 可以保留方块',
        'ko': 'C 키로 블록을 홀드할 수 있어요'
    },
    'tip_hard_drop': {
        'tr': 'SPACE ile hızlı düşür',
        'en': 'Press SPACE for hard drop',
        'de': 'Drücke LEERTASTE für schnelles Fallen',
        'fr': 'Appuyez sur ESPACE pour descente rapide',
        'es': 'Presiona ESPACIO para caída rápida',
        'it': 'Premi SPAZIO per caduta rapida',
        'pt': 'Pressione ESPAÇO para queda rápida',
        'ja': 'SPACEでハードドロップ',
        'zh': '按 SPACE 进行硬降',
        'ko': 'SPACE로 하드 드롭'
    },
    'tip_rotate': {
        'tr': 'Yukarı ok ile döndür',
        'en': 'Press UP to rotate',
        'de': 'Drücke HOCH um zu drehen',
        'fr': 'Appuyez sur HAUT pour tourner',
        'es': 'Presiona ARRIBA para rotar',
        'it': 'Premi SU per ruotare',
        'pt': 'Pressione CIMA para girar',
        'ja': '上矢印で回転',
        'zh': '按上方向键旋转',
        'ko': '위쪽 화살표로 회전'
    },
    
    # ======================= BAŞLIK ÇUBUĞU =======================
    'window_title': {
        'tr': 'Quadrix - Full Edition',
        'en': 'Quadrix - Full Edition',
        'de': 'Quadrix - Full Edition',
        'fr': 'Quadrix - Édition Complète',
        'es': 'Quadrix - Edición Completa',
        'it': 'Quadrix - Edizione Completa',
        'pt': 'Quadrix - Edição Completa',
        'ja': 'Quadrix - フルエディション',
        'zh': 'Quadrix - 完整版',
        'ko': 'Quadrix - 풀 에디션'
    },
    'window_title_pvp': {
        'tr': 'Quadrix - PvP Modu (2 Oyunculu)',
        'en': 'Quadrix - PvP Mode (2 Players)',
        'de': 'Quadrix - PvP Modus (2 Spieler)',
        'fr': 'Quadrix - Mode PvP (2 Joueurs)',
        'es': 'Quadrix - Modo PvP (2 Jugadores)',
        'it': 'Quadrix - Modalità PvP (2 Giocatori)',
        'pt': 'Quadrix - Modo PvP (2 Jogadores)',
        'ja': 'Quadrix - PvPモード（2人）',
        'zh': 'Quadrix - PvP 模式（2人）',
        'ko': 'Quadrix - PvP 모드(2인)'
    },
    
    # ======================= FOOTER =======================
    'copyright': {
        'tr': '© 2025 Arda & Burak',
        'en': '© 2025 Arda & Burak',
        'de': '© 2025 Arda & Burak',
        'fr': '© 2025 Arda & Burak',
        'es': '© 2025 Arda & Burak',
        'it': '© 2025 Arda & Burak',
        'pt': '© 2025 Arda & Burak',
        'ja': '© 2025 Arda & Burak',
        'zh': '© 2025 Arda & Burak',
        'ko': '© 2025 Arda & Burak'
    },
    'version': {
        'tr': 'Sürüm',
        'en': 'Version',
        'de': 'Version',
        'fr': 'Version',
        'es': 'Versión',
        'it': 'Versione',
        'pt': 'Versão',
        'ja': 'バージョン',
        'zh': '版本',
        'ko': '버전'
    },
    
    # ======================= EXIT DIALOG =======================
    'exit_title': {
        'tr': 'Çıkmak istiyor musun?',
        'en': 'Do you want to quit?',
        'de': 'Möchtest du beenden?',
        'fr': 'Voulez-vous quitter?',
        'es': '¿Quieres salir?',
        'it': 'Vuoi uscire?',
        'pt': 'Deseja sair?',
        'ja': '終了しますか？',
        'zh': '确定要退出吗？',
        'ko': '종료하시겠습니까?'
    },
    'exit_warning1': {
        'tr': 'Kaydedilmemiş ilerleme',
        'en': 'Unsaved progress',
        'de': 'Ungespeicherter Fortschritt',
        'fr': 'Progression non sauvegardée',
        'es': 'Progreso no guardado',
        'it': 'Progressi non salvati',
        'pt': 'Progresso não salvo',
        'ja': '未保存の進行状況',
        'zh': '未保存的进度',
        'ko': '저장되지 않은 진행 상황'
    },
    'exit_warning2': {
        'tr': 'kaybolabilir. Emin misin?',
        'en': 'may be lost. Are you sure?',
        'de': 'könnte verloren gehen. Bist du sicher?',
        'fr': 'peut être perdu. Êtes-vous sûr?',
        'es': 'puede perderse. ¿Estás seguro?',
        'it': 'potrebbe andare perso. Sei sicuro?',
        'pt': 'pode ser perdido. Tem certeza?',
        'ja': '失われる可能性があります。よろしいですか？',
        'zh': '可能会丢失。确定吗？',
        'ko': '사라질 수 있습니다. 정말로 종료할까요?'
    },
    'exit_yes': {
        'tr': 'Evet (ENTER)',
        'en': 'Yes (ENTER)',
        'de': 'Ja (ENTER)',
        'fr': 'Oui (ENTRÉE)',
        'es': 'Sí (ENTER)',
        'it': 'Sì (INVIO)',
        'pt': 'Sim (ENTER)',
        'ja': 'はい (ENTER)',
        'zh': '是 (ENTER)',
        'ko': '예 (ENTER)'
    },
    'exit_no': {
        'tr': 'Hayır (ESC)',
        'en': 'No (ESC)',
        'de': 'Nein (ESC)',
        'fr': 'Non (ÉCHAP)',
        'es': 'No (ESC)',
        'it': 'No (ESC)',
        'pt': 'Não (ESC)',
        'ja': 'いいえ (ESC)',
        'zh': '否 (ESC)',
        'ko': '아니오 (ESC)'
    },
    'exit_hint': {
        'tr': 'ENTER / Y : Çık   |   ESC / N : İptal',
        'en': 'ENTER / Y : Quit   |   ESC / N : Cancel',
        'de': 'ENTER / J : Beenden   |   ESC / N : Abbrechen',
        'fr': 'ENTRÉE / O : Quitter   |   ÉCHAP / N : Annuler',
        'es': 'ENTER / S : Salir   |   ESC / N : Cancelar',
        'it': 'INVIO / S : Esci   |   ESC / N : Annulla',
        'pt': 'ENTER / S : Sair   |   ESC / N : Cancelar',
        'ja': 'ENTER / Y : 終了   |   ESC / N : キャンセル',
        'zh': 'ENTER / Y：退出   |   ESC / N：取消',
        'ko': 'ENTER / Y: 종료   |   ESC / N: 취소'
    },
    
    # ======================= GAME OVER EXTRAS =======================
    'game_over_subtitle': {
        'tr': 'Skorların kaydedildi, tekrar dene!',
        'en': 'Scores saved, try again!',
        'de': 'Punkte gespeichert, versuche es nochmal!',
        'fr': 'Scores sauvegardés, réessayez!',
        'es': '¡Puntuaciones guardadas, inténtalo de nuevo!',
        'it': 'Punteggi salvati, riprova!',
        'pt': 'Pontuações salvas, tente novamente!',
        'ja': 'スコアは保存されました、もう一度！',
        'zh': '分数已保存，再试一次！',
        'ko': '점수가 저장되었습니다. 다시 도전하세요!'
    },
    'lines_cleared': {
        'tr': 'Temizlenen Satır',
        'en': 'Lines Cleared',
        'de': 'Geräumte Zeilen',
        'fr': 'Lignes Effacées',
        'es': 'Líneas Limpiadas',
        'it': 'Righe Eliminate',
        'pt': 'Linhas Limpas',
        'ja': '消去ライン',
        'zh': '已清除行数',
        'ko': '지운 줄'
    },
    'tetris_count': {
        'tr': 'Quadrix',
        'en': 'Quadrix',
        'de': 'Quadrix',
        'fr': 'Quadrix',
        'es': 'Quadrix',
        'it': 'Quadrix',
        'pt': 'Quadrix',
        'ja': 'テトリス',
        'zh': '四消',
        'ko': '테트리스'
    },
    'saved_profile': {
        'tr': 'Kaydedilen profil: {}',
        'en': 'Saved profile: {}',
        'de': 'Gespeichertes Profil: {}',
        'fr': 'Profil sauvegardé: {}',
        'es': 'Perfil guardado: {}',
        'it': 'Profilo salvato: {}',
        'pt': 'Perfil salvo: {}',
        'ja': '保存されたプロフィール: {}',
        'zh': '已保存的资料：{}',
        'ko': '저장된 프로필: {}'
    },
    'game_over_hint': {
        'tr': 'R ile yeniden başlat, ESC ile menüye dön.',
        'en': 'Press R to restart, ESC for menu.',
        'de': 'R zum Neustarten, ESC für Menü.',
        'fr': 'Appuyez sur R pour recommencer, ÉCHAP pour le menu.',
        'es': 'Presiona R para reiniciar, ESC para el menú.',
        'it': 'Premi R per ricominciare, ESC per il menu.',
        'pt': 'Pressione R para reiniciar, ESC para o menu.',
        'ja': 'Rで再開、ESCでメニュー。',
        'zh': '按 R 重开，ESC 返回菜单。',
        'ko': 'R로 재시작, ESC로 메뉴'
    },
    'daily_completed': {
        'tr': 'Bugünün görevi tamamlandı',
        'en': "Today's challenge completed",
        'de': 'Heutige Herausforderung abgeschlossen',
        'fr': 'Défi du jour terminé',
        'es': 'Desafío de hoy completado',
        'it': 'Sfida di oggi completata',
        'pt': 'Desafio de hoje concluído',
        'ja': '本日のチャレンジ完了',
        'zh': '今日挑战已完成',
        'ko': '오늘의 도전 완료'
    },
    'remaining_tries': {
        'tr': 'Kalan hak: {}/{}',
        'en': 'Remaining tries: {}/{}',
        'de': 'Verbleibende Versuche: {}/{}',
        'fr': 'Essais restants: {}/{}',
        'es': 'Intentos restantes: {}/{}',
        'it': 'Tentativi rimanenti: {}/{}',
        'pt': 'Tentativas restantes: {}/{}',
        'ja': '残り回数: {}/{}',
        'zh': '剩余次数：{}/{}',
        'ko': '남은 시도: {}/{}'
    },
    'back_to_menu': {
        'tr': 'Menüye Dön',
        'en': 'Back to Menu',
        'de': 'Zurück zum Menü',
        'fr': 'Retour au Menu',
        'es': 'Volver al Menú',
        'it': 'Torna al Menu',
        'pt': 'Voltar ao Menu',
        'ja': 'メニューへ戻る',
        'zh': '返回菜单',
        'ko': '메뉴로 돌아가기'
    },
    
    # ==================== KART SİSTEMİ ÇEVİRİLERİ ====================
    # Kart başlıkları
    'card_score_title': {
        'tr': 'Skor Patlaması', 'en': 'Score Burst', 'de': 'Punkteexplosion',
        'fr': 'Explosion de Score', 'es': 'Explosión de Puntos', 'it': 'Esplosione Punti', 'pt': 'Explosão de Pontos', 'ja': 'スコアバースト'
        , 'zh': '分数爆发', 'ko': '점수 폭발'
    },
    'card_score_desc': {
        'tr': 'Anında +{value} puan kazanırsın.',
        'en': 'Instantly gain +{value} points.',
        'de': 'Du erhältst sofort +{value} Punkte.',
        'fr': 'Gagnez instantanément +{value} points.',
        'es': 'Gana instantáneamente +{value} puntos.',
        'it': 'Ottieni istantaneamente +{value} punti.',
        'pt': 'Ganhe instantaneamente +{value} pontos.',
        'ja': '即座に+{value}ポイント獲得。',
        'zh': '立即获得 +{value} 分。',
        'ko': '즉시 +{value}점 획득.'
    },
    'card_speed_burst_title': {
        'tr': 'Hız Patlaması', 'en': 'Speed Burst', 'de': 'Geschwindigkeitsschub',
        'fr': 'Vitesse Éclair', 'es': 'Ráfaga de Velocidad', 'it': 'Scatto di Velocità', 'pt': 'Explosão de Velocidade', 'ja': 'スピードバースト'
        , 'zh': '速度爆发', 'ko': '속도 폭발'
    },
    'card_speed_burst_desc': {
        'tr': '{value} saniye boyunca %50 hızlı düşüş + temizlenen her satır için 2x puan!',
        'en': '50% faster drop for {value} seconds + 2x points for every cleared line!',
        'de': '50% schnellerer Fall für {value} Sekunden + 2x Punkte für jede gelöschte Zeile!',
        'fr': 'Chute 50% plus rapide pendant {value} secondes + 2x points pour chaque ligne effacée!',
        'es': '¡Caída un 50% más rápida durante {value} segundos + 2x puntos por cada línea borrada!',
        'it': 'Caduta più veloce del 50% per {value} secondi + 2x punti per ogni riga cancellata!',
        'pt': 'Queda 50% mais rápida por {value} segundos + 2x pontos para cada linha limpa!',
        'ja': '{value}秒間落下速度50%アップ + 消去1ラインごとに2倍ポイント！',
        'zh': '{value} 秒内下落速度提高 50% + 每清一行得分 x2！',
        'ko': '{value}초 동안 낙하 속도 50% 증가 + 줄 제거당 점수 2배!'
    },
    'card_time_capsule_title': {
        'tr': 'Zaman Kapsülü', 'en': 'Time Capsule', 'de': 'Zeitkapsel',
        'fr': 'Capsule Temporelle', 'es': 'Cápsula del Tiempo', 'it': 'Capsula del Tempo', 'pt': 'Cápsula do Tempo', 'ja': 'タイムカプセル'
        , 'zh': '时间胶囊', 'ko': '타임 캡슐'
    },
    'card_time_capsule_desc': {
        'tr': 'R ile zaman kapsülünü kullan: ilk basışta kaydet, ikinci basışta geri dön.',
        'en': 'Use time capsule with R: first press saves, second press restores.',
        'de': 'Speichere den Brettstatus mit T, kehre mit R zum gespeicherten Status zurück.',
        'fr': 'Sauvegardez l\'état du plateau avec T, revenez à l\'état sauvegardé avec R.',
        'es': 'Guarda el estado del tablero con T, vuelve al estado guardado con R.',
        'it': 'Salva lo stato della scheda con T, torna allo stato salvato con R.',
        'pt': 'Salve o estado do tabuleiro com T, retorne ao estado salvo com R.',
        'ja': 'Tで盤面を保存、Rで保存状態に戻る。',
        'zh': '按 T 保存棋盘，按 R 返回保存状态。',
        'ko': 'T로 보드를 저장하고 R로 저장 상태로 돌아갑니다.'
    },
    'card_clear_rows_title': {
        'tr': 'Alt Süpür', 'en': 'Bottom Sweep', 'de': 'Unterer Feger',
        'fr': 'Balayage Bas', 'es': 'Barrido Inferior', 'it': 'Spazzata Inferiore', 'pt': 'Varredura Inferior', 'ja': 'ボトムスイープ'
        , 'zh': '底部清扫', 'ko': '바닥 쓸기'
    },
    'card_clear_rows_desc': {
        'tr': 'En alttaki {value} satırı temizler. Bloklar aşağı oturur.',
        'en': 'Clears the bottom {value} rows. Blocks settle down.',
        'de': 'Löscht die untersten {value} Zeilen. Blöcke setzen sich.',
        'fr': 'Efface les {value} lignes du bas. Les blocs descendent.',
        'es': 'Limpia las {value} filas inferiores. Los bloques se asientan.',
        'it': 'Cancella le {value} righe inferiori. I blocchi si assestano.',
        'pt': 'Limpa as {value} linhas inferiores. Os blocos se acomodam.',
        'ja': '下から{value}行を消去。ブロックが落ちて詰まる。',
        'zh': '清除底部 {value} 行。方块会下落填充。',
        'ko': '아래 {value}줄을 제거합니다. 블록이 내려와 채워집니다.'
    },
    'card_block_magnet_title': {
        'tr': 'Blok Manyetigi', 'en': 'Block Magnet', 'de': 'Block Magnet',
        'fr': 'Aimant de Blocs', 'es': 'Imán de Bloques', 'it': 'Magnete dei Blocchi', 'pt': 'Ímã de Blocos', 'ja': 'ブロックマグネット', 'zh': '方块磁力', 'ko': '블록 마그넷'
    },
    'card_block_magnet_desc': {
        'tr': 'Tum bosluklar kapanir! Bloklar birbirine yapisir ve bosluklar yok olur.',
        'en': 'All gaps close! Blocks stick together and gaps disappear.',
        'de': 'Alle Lücken schließen sich! Blöcke kleben zusammen und Lücken verschwinden.',
        'fr': 'Tous les espaces se ferment! Les blocs se collent et les espaces disparaissent.',
        'es': 'Todos los espacios se cierran! Los bloques se pegan y los espacios desaparecen.',
        'it': 'Tutti gli spazi si chiudono! I blocchi si attaccano e gli spazi scompaiono.',
        'pt': 'Todos os espaços se fecham! Os blocos se grudam e os espaços desaparecem.',
        'ja': 'すべての隙間が閉じる！ブロックがくっつき、隙間が消える。',
        'zh': '所有空隙都会闭合！方块相互吸附，空隙消失。',
        'ko': '모든 빈틈이 닫힙니다! 블록이 붙어 빈틈이 사라집니다.'
    },
    'card_perk_flexible_border_title': {
        'tr': 'Esnek Sınır', 'en': 'Flexible Border', 'de': 'Flexible Grenze',
        'fr': 'Bordure Flexible', 'es': 'Borde Flexible', 'it': 'Bordo Flessibile', 'pt': 'Borda Flexível', 'ja': 'フレキシブルボーダー', 'zh': '弹性边界', 'ko': '유연한 경계'
    },
    'card_perk_flexible_border_desc': {
        'tr': 'PERK: Parçalar tahtanın kenarlarından 1 blok dışına çıkabilir.',
        'en': 'PERK: Pieces can extend 1 block beyond the board edges.',
        'de': 'PERK: Teile können 1 Block über die Spielfeldränder hinausragen.',
        'fr': 'PERK: Les pièces peuvent dépasser de 1 bloc au-delà des bords du plateau.',
        'es': 'PERK: Las piezas pueden extenderse 1 bloque más allá de los bordes del tablero.',
        'it': 'PERK: I pezzi possono estendersi di 1 blocco oltre i bordi del campo.',
        'pt': 'PERK: As peças podem se estender 1 bloco além das bordas do tabuleiro.',
        'ja': 'PERK: ピースは盤面の端から1ブロック外まで伸びられる。',
        'zh': 'PERK：方块可超出棋盘边缘 1 格。',
        'ko': 'PERK: 블록이 보드 가장자리 밖으로 1칸까지 나갈 수 있습니다.'
    },
    'card_column_cleanse_title': {
        'tr': 'Sütun Lazeri', 'en': 'Column Laser', 'de': 'Säulenlaser',
        'fr': 'Laser de Colonne', 'es': 'Láser de Columna', 'it': 'Laser Colonna', 'pt': 'Laser de Coluna', 'ja': 'カラムレーザー', 'zh': '列激光', 'ko': '컬럼 레이저'
    },
    'card_column_cleanse_desc': {
        'tr': 'Rastgele {value} sütunu tamamen temizler.',
        'en': 'Completely clears {value} random columns.',
        'de': 'Löscht {value} zufällige Spalten vollständig.',
        'fr': 'Efface complètement {value} colonnes aléatoires.',
        'es': 'Limpia completamente {value} columnas aleatorias.',
        'it': 'Cancella completamente {value} colonne casuali.',
        'pt': 'Limpa completamente {value} colunas aleatórias.',
        'ja': 'ランダムに{value}列を完全消去。',
        'zh': '随机完全清除 {value} 列。',
        'ko': '무작위 {value}열을 완전히 제거합니다.'
    },
    'card_force_piece_title': {
        'tr': 'Parça Seçici', 'en': 'Piece Selector', 'de': 'Teilwähler',
        'fr': 'Sélecteur de Pièce', 'es': 'Selector de Pieza', 'it': 'Selettore Pezzo', 'pt': 'Seletor de Peça', 'ja': 'ピースセレクター', 'zh': '方块选择器', 'ko': '피스 선택기'
    },
    'card_force_piece_desc': {
        'tr': 'Sonraki {value} parça I, T veya L şeklinde gelir.',
        'en': 'Next {value} pieces will be I, T, or L shaped.',
        'de': 'Die nächsten {value} Teile sind I-, T- oder L-förmig.',
        'fr': 'Les {value} prochaines pièces seront en forme de I, T ou L.',
        'es': 'Las siguientes {value} piezas serán en forma de I, T o L.',
        'it': 'I prossimi {value} pezzi saranno a forma di I, T o L.',
        'pt': 'As próximas {value} peças serão em forma de I, T ou L.',
        'ja': '次の{value}個のピースはI/T/L形。',
        'zh': '接下来 {value} 个方块将是 I/T/L 形。',
        'ko': '다음 {value}개는 I/T/L 모양입니다.'
    },
    'card_combo_boost_title': {
        'tr': 'Combo Kalkanı', 'en': 'Combo Shield', 'de': 'Komboschild',
        'fr': 'Bouclier Combo', 'es': 'Escudo Combo', 'it': 'Scudo Combo', 'pt': 'Escudo Combo', 'ja': 'コンボシールド', 'zh': '连击护盾', 'ko': '콤보 실드'
    },
    'card_combo_boost_desc': {
        'tr': '{value} saniye boyunca combo sıfırlanmaz.',
        'en': 'Combo will not reset for {value} seconds.',
        'de': 'Kombo wird für {value} Sekunden nicht zurückgesetzt.',
        'fr': 'Le combo ne se réinitialise pas pendant {value} secondes.',
        'es': 'El combo no se reinicia durante {value} segundos.',
        'it': 'Il combo non si azzera per {value} secondi.',
        'pt': 'O combo não será zerado por {value} segundos.',
        'ja': '{value}秒間コンボが途切れない。',
        'zh': '{value} 秒内连击不会重置。',
        'ko': '{value}초 동안 콤보가 리셋되지 않습니다.'
    },
    'card_time_slow_title': {
        'tr': 'Zaman Yavaşlatma', 'en': 'Time Slow', 'de': 'Zeitverlangsamung',
        'fr': 'Ralentissement du Temps', 'es': 'Ralentización del Tiempo', 'it': 'Rallentamento Tempo', 'pt': 'Desaceleração do Tempo', 'ja': 'タイムスロー', 'zh': '时间减速', 'ko': '시간 감속'
    },
    'card_time_slow_desc': {
        'tr': '{value} saniye boyunca parçalar %50 yavaş düşer.',
        'en': 'Pieces fall 50% slower for {value} seconds.',
        'de': 'Teile fallen {value} Sekunden lang 50% langsamer.',
        'fr': 'Les pièces tombent 50% plus lentement pendant {value} secondes.',
        'es': 'Las piezas caen 50% más lento durante {value} segundos.',
        'it': 'I pezzi cadono il 50% più lentamente per {value} secondi.',
        'pt': 'As peças caem 50% mais devagar por {value} segundos.',
        'ja': '{value}秒間ピース落下が50%遅くなる。',
        'zh': '{value} 秒内方块下落速度降低 50%。',
        'ko': '{value}초 동안 블록 낙하가 50% 느려집니다.'
    },
    'card_line_bonus_title': {
        'tr': 'Puan Çarpanı', 'en': 'Score Multiplier', 'de': 'Punktemultiplikator',
        'fr': 'Multiplicateur de Score', 'es': 'Multiplicador de Puntos', 'it': 'Moltiplicatore Punti', 'pt': 'Multiplicador de Pontos', 'ja': 'スコア倍率', 'zh': '得分倍率', 'ko': '점수 배수'
    },
    'card_line_bonus_desc': {
        'tr': 'Sonraki {value} satır temizlemede 2x puan.',
        'en': '2x points for the next {value} line clears.',
        'de': '2x Punkte für die nächsten {value} Zeilenräumungen.',
        'fr': '2x points pour les {value} prochaines lignes effacées.',
        'es': '2x puntos para las próximas {value} líneas eliminadas.',
        'it': '2x punti per le prossime {value} linee cancellate.',
        'pt': '2x pontos para as próximas {value} linhas limpas.',
        'ja': '次の{value}回のライン消去が2倍。',
        'zh': '接下来清除 {value} 行得分 x2。',
        'ko': '다음 {value}번 라인 제거는 2배 점수.'
    },
    'card_peak_sculpt_title': {
        'tr': 'Tepe Kesici', 'en': 'Peak Cutter', 'de': 'Spitzenschneider',
        'fr': 'Coupe-Sommet', 'es': 'Cortador de Picos', 'it': 'Taglia Picco', 'pt': 'Cortador de Pico', 'ja': 'ピークカッター', 'zh': '削峰者', 'ko': '봉우리 절단기'
    },
    'card_peak_sculpt_desc': {
        'tr': 'En yüksek {value} bloğu keser, tahtayı düzleştirir.',
        'en': 'Cuts the highest {value} blocks, flattening the board.',
        'de': 'Schneidet die höchsten {value} Blöcke ab und ebnet das Brett.',
        'fr': 'Coupe les {value} blocs les plus hauts, aplanissant le plateau.',
        'es': 'Corta los {value} bloques más altos, aplanando el tablero.',
        'it': 'Taglia i {value} blocchi più alti, appiattendo il tabellone.',
        'pt': 'Corta os {value} blocos mais altos, nivelando o tabuleiro.',
        'ja': '最も高い{value}ブロックを削り、盤面を平坦化。',
        'zh': '切除最高的 {value} 个方块，使棋盘变平。',
        'ko': '가장 높은 {value}블록을 제거해 판을 평탄화합니다.'
    },
    'card_nova_burst_title': {
        'tr': 'Nova Patlaması', 'en': 'Nova Burst', 'de': 'Nova-Explosion',
        'fr': 'Explosion Nova', 'es': 'Explosión Nova', 'it': 'Esplosione Nova', 'pt': 'Explosão Nova', 'ja': 'ノヴァバースト', 'zh': '新星爆发', 'ko': '노바 버스트'
    },
    'card_nova_burst_desc': {
        'tr': 'Sonraki {value} kilitte merkezde 3x3 alan patlar.',
        'en': 'Next {value} locks will explode a 3x3 area at center.',
        'de': 'Die nächsten {value} Platzierungen sprengen einen 3x3 Bereich in der Mitte.',
        'fr': 'Les {value} prochains verrouillages feront exploser une zone 3x3 au centre.',
        'es': 'Los próximos {value} bloqueos explotarán un área 3x3 en el centro.',
        'it': 'I prossimi {value} blocchi faranno esplodere un\'area 3x3 al centro.',
        'pt': 'Os próximos {value} travamentos explodirão uma área 3x3 no centro.',
        'ja': '次の{value}回のロックで中央の3x3が爆発。',
        'zh': '接下来 {value} 次锁定会在中心爆炸 3x3。',
        'ko': '다음 {value}번 잠금 시 중앙 3x3이 폭발합니다.'
    },
    'card_mini_bomb_title': {
        'tr': 'Mini Bomba', 'en': 'Mini Bomb', 'de': 'Mini-Bombe',
        'fr': 'Mini Bombe', 'es': 'Mini Bomba', 'it': 'Mini Bomba', 'pt': 'Mini Bomba', 'ja': 'ミニボム', 'zh': '迷你炸弹', 'ko': '미니 폭탄'
    },
    'card_mini_bomb_desc': {
        'tr': 'Mevcut parça kilitlenince kendi hücreleri + temas ettiği komşu blokları patlatır.',
        'en': 'When locked, explodes its own cells + touching neighbor blocks.',
        'de': 'Beim Platzieren sprengt es seine eigenen Zellen + berührende Nachbarblöcke.',
        'fr': 'Une fois verrouillée, explose ses propres cellules + les blocs voisins touchés.',
        'es': 'Al bloquearse, explota sus propias celdas + bloques vecinos tocados.',
        'it': 'Quando bloccato, esplode le proprie celle + blocchi vicini toccati.',
        'pt': 'Quando travado, explode suas próprias células + blocos vizinhos tocados.',
        'ja': 'ロック時、自身のセル＋接触する隣接ブロックを爆破。',
        'zh': '锁定时爆炸自身格子 + 接触的邻近方块。',
        'ko': '잠금 시 자신의 칸 + 접촉한 인접 블록을 폭발시킵니다.'
    },
    'card_quantum_tunneling_title': {
        'tr': 'Hayalet Parça', 'en': 'Ghost Piece', 'de': 'Geisterteil',
        'fr': 'Pièce Fantôme', 'es': 'Pieza Fantasma', 'it': 'Pezzo Fantasma', 'pt': 'Peça Fantasma', 'ja': 'ゴーストピース', 'zh': '幽灵方块', 'ko': '고스트 피스'
    },
    'card_quantum_tunneling_desc': {
        'tr': '3 hak: G ile istediğin parçayı hayalet yap; blokların içinden geçer.',
        'en': '3 uses: Press G to make a piece ghost; passes through blocks.',
        'de': '3 Verwendungen: Drücke G um ein Teil zum Geist zu machen; geht durch Blöcke.',
        'fr': '3 utilisations: Appuyez sur G pour rendre une pièce fantôme; traverse les blocs.',
        'es': '3 usos: Presiona G para hacer una pieza fantasma; atraviesa bloques.',
        'it': '3 usi: Premi G per rendere un pezzo fantasma; passa attraverso i blocchi.',
        'pt': '3 usos: Pressione G para tornar uma peça fantasma; atravessa blocos.',
        'ja': '3回: Gでピースをゴースト化。ブロックを通過。',
        'zh': '3 次：按 G 让方块幽灵化，可穿过方块。',
        'ko': '3회: G로 피스를 고스트화, 블록을 통과합니다.'
    },
    'card_hammer_title': {
        'tr': 'Zip Dosyası', 'en': 'Zip File', 'de': 'Zip-Datei',
        'fr': 'Fichier Zip', 'es': 'Archivo Zip', 'it': 'File Zip', 'pt': 'Arquivo Zip', 'ja': 'Zipファイル', 'zh': '压缩文件', 'ko': 'ZIP 파일'
    },
    'card_hammer_desc': {
        'tr': '3 hak: H ile mevcut düşen parçayı anlık 1x1 bloğa dönüştür.',
        'en': '3 uses: Press H to instantly turn the falling piece into a 1x1 block.',
        'de': '3 Verwendungen: Drücke H um das fallende Teil sofort in einen 1x1 Block zu verwandeln.',
        'fr': '3 utilisations: Appuyez sur H pour transformer instantanément la pièce en bloc 1x1.',
        'es': '3 usos: Presiona H para convertir instantáneamente la pieza en un bloque 1x1.',
        'it': '3 usi: Premi H per trasformare istantaneamente il pezzo in un blocco 1x1.',
        'pt': '3 usos: Pressione H para transformar instantaneamente a peça em um bloco 1x1.',
        'ja': '3回: Hで落下中のピースを即座に1x1ブロックに。',
        'zh': '3 次：按 H 立即将下落方块变为 1x1。',
        'ko': '3회: H로 떨어지는 피스를 즉시 1x1 블록으로 변경.'
    },
    'card_bomb_master_title': {
        'tr': 'Bomba Ustası', 'en': 'Bomb Master', 'de': 'Bombenmeister',
        'fr': 'Maître des Bombes', 'es': 'Maestro de Bombas', 'it': 'Maestro delle Bombe', 'pt': 'Mestre das Bombas', 'ja': 'ボムマスター', 'zh': '炸弹大师', 'ko': '폭탄 마스터'
    },
    'card_bomb_master_desc': {
        'tr': '3 hak: M tuşuyla mevcut parçayı mini bomba yap. Kilitlenince temas ettiği blokları patlatır.',
        'en': '3 uses: Press M to turn the current piece into a mini bomb. On lock, it explodes the blocks it touches.',
        'de': '3 Verwendungen: Drücke M, um das aktuelle Teil in eine Mini-Bombe zu verwandeln. Beim Platzieren sprengt es die berührten Blöcke.',
        'fr': '3 utilisations : appuyez sur M pour transformer la pièce actuelle en mini-bombe. À la pose, elle explose les blocs touchés.',
        'es': '3 usos: Presiona M para convertir la pieza actual en una mini bomba. Al bloquearse, explota los bloques que toca.',
        'it': '3 usi: Premi M per trasformare il pezzo attuale in una mini bomba. Al blocco, esplode i blocchi toccati.',
        'pt': '3 usos: Pressione M para transformar a peça atual em uma mini bomba. Ao travar, explode os blocos tocados.',
        'ja': '3回: Mで現在のピースをミニボム化。ロック時、接触ブロックを爆破。',
        'zh': '3 次：按 M 将当前方块变为迷你炸弹，锁定时爆炸接触方块。',
        'ko': '3회: M로 현재 피스를 미니 폭탄으로. 잠금 시 접촉 블록 폭발.'
    },
    'card_perk_explosive_title': {
        'tr': 'Bomba Ustası', 'en': 'Bomb Master', 'de': 'Bombenmeister',
        'fr': 'Maître des Bombes', 'es': 'Maestro de Bombas', 'it': 'Maestro delle Bombe', 'pt': 'Mestre das Bombas', 'ja': 'ボムマスター', 'zh': '炸弹大师', 'ko': '폭탄 마스터'
    },
    'card_perk_explosive_desc': {
        'tr': 'PERK: Oyuncu 2 satır temizleyince sonraki parça bomba olur; kilitte merkezde + (5 hücre) patlar.',
        'en': 'PERK: After clearing 2 lines, next piece becomes a bomb; explodes + shaped (5 cells) on lock.',
        'de': 'PERK: Nach 2 Zeilen wird das nächste Teil zur Bombe; explodiert + förmig (5 Zellen) beim Platzieren.',
        'fr': 'PERK: Après 2 lignes, la pièce suivante devient une bombe; explose en + (5 cellules) au verrouillage.',
        'es': 'PERK: Después de 2 líneas, la siguiente pieza se convierte en bomba; explota en + (5 celdas) al bloquear.',
        'it': 'PERK: Dopo 2 linee, il prossimo pezzo diventa una bomba; esplode a + (5 celle) al blocco.',
        'pt': 'PERK: Após 2 linhas, a próxima peça vira bomba; explode em + (5 células) ao travar.',
        'ja': 'PERK: 2ライン消去後、次のピースが爆弾化。ロック時に＋字(5セル)が爆発。',
        'zh': 'PERK：清除 2 行后下一块变炸弹；锁定时以 + 形（5格）爆炸。',
        'ko': 'PERK: 2줄 제거 후 다음 피스가 폭탄이 되며, 잠금 시 +형(5칸) 폭발.'
    },
    'card_rewind_power_title': {
        'tr': 'Geri Sarma', 'en': 'Rewind', 'de': 'Zurückspulen',
        'fr': 'Rembobinage', 'es': 'Rebobinar', 'it': 'Riavvolgi', 'pt': 'Rebobinar', 'ja': 'リワインド', 'zh': '回溯', 'ko': '되감기'
    },
    'card_rewind_power_desc': {
        'tr': 'PERK: U tuşuyla son parçayı geri sar (3 kullanım).',
        'en': 'PERK: Press U to undo the last piece (3 uses).',
        'de': 'PERK: Drücke U um das letzte Teil rückgängig zu machen (3 Verwendungen).',
        'fr': 'PERK: Appuyez sur U pour annuler la dernière pièce (3 utilisations).',
        'es': 'PERK: Presiona U para deshacer la última pieza (3 usos).',
        'it': 'PERK: Premi U per annullare l\'ultimo pezzo (3 usi).',
        'pt': 'PERK: Pressione U para desfazer a última peça (3 usos).',
        'ja': 'PERK: Uで直前のピースを巻き戻す(3回)。',
        'zh': 'PERK：按 U 撤销上一个方块（3 次）。',
        'ko': 'PERK: U로 마지막 피스를 되돌립니다(3회).'
    },
    'card_perk_chrono_title': {
        'tr': 'Zaman Durdurucu', 'en': 'Time Stopper', 'de': 'Zeitstopper',
        'fr': 'Arrêt du Temps', 'es': 'Detenedor del Tiempo', 'it': 'Ferma Tempo', 'pt': 'Parador do Tempo', 'ja': 'タイムストッパー', 'zh': '时间停止器', 'ko': '타임 스토퍼'
    },
    'card_perk_chrono_desc': {
        'tr': 'PERK: Her 10 satırda yerçekimi 3 saniye durur.',
        'en': 'PERK: Every 10 lines, gravity stops for 3 seconds.',
        'de': 'PERK: Alle 10 Zeilen stoppt die Schwerkraft für 3 Sekunden.',
        'fr': 'PERK: Toutes les 10 lignes, la gravité s\'arrête pendant 3 secondes.',
        'es': 'PERK: Cada 10 líneas, la gravedad se detiene por 3 segundos.',
        'it': 'PERK: Ogni 10 linee, la gravità si ferma per 3 secondi.',
        'pt': 'PERK: A cada 10 linhas, a gravidade para por 3 segundos.',
        'ja': 'PERK: 10ラインごとに重力が3秒停止。',
        'zh': 'PERK：每清 10 行，重力停止 3 秒。',
        'ko': 'PERK: 10줄마다 중력이 3초 멈춥니다.'
    },
    'card_perk_phase_title': {
        'tr': 'Şekil Değiştirici', 'en': 'Shape Shifter', 'de': 'Formwandler',
        'fr': 'Changeur de Forme', 'es': 'Cambiaformas', 'it': 'Cambiaforma', 'pt': 'Transformador', 'ja': 'シェイプシフター', 'zh': '形态变换者', 'ko': '셰이프 시프터'
    },
    'card_perk_phase_desc': {
        'tr': 'LSHIFT ile parçayı karşıtına dönüştür (L↔J, Z↔S). (3 kullanım)',
        'en': 'Press LSHIFT to transform piece to its mirror (L↔J, Z↔S). (3 uses)',
        'de': 'Drücke LSHIFT um das Teil zu spiegeln (L↔J, Z↔S). (3 Verwendungen)',
        'fr': 'Appuyez sur LSHIFT pour transformer la pièce en miroir (L↔J, Z↔S). (3 utilisations)',
        'es': 'Presiona LSHIFT para transformar la pieza en su espejo (L↔J, Z↔S). (3 usos)',
        'it': 'Premi LSHIFT per trasformare il pezzo nel suo specchio (L↔J, Z↔S). (3 usi)',
        'pt': 'Pressione LSHIFT para transformar a peça em seu espelho (L↔J, Z↔S). (3 usos)',
        'ja': 'LSHIFTでピースを左右反転(L↔J, Z↔S)。(3回)',
        'zh': '按 LSHIFT 将方块镜像 (L↔J, Z↔S)。（3 次）',
        'ko': 'LSHIFT로 피스를 좌우 반전(L↔J, Z↔S). (3회)'
    },
    'card_perk_synergy_title': {
        'tr': 'Sinerji Bonus', 'en': 'Synergy Bonus', 'de': 'Synergiebonus',
        'fr': 'Bonus de Synergie', 'es': 'Bono de Sinergia', 'it': 'Bonus Sinergia', 'pt': 'Bônus de Sinergia', 'ja': 'シナジーボーナス', 'zh': '协同奖励', 'ko': '시너지 보너스'
    },
    'card_perk_synergy_desc': {
        'tr': 'PERK: Her aktif perk için +%10 skor bonusu.',
        'en': 'PERK: +10% score bonus for each active perk.',
        'de': 'PERK: +10% Punktebonus für jeden aktiven Perk.',
        'fr': 'PERK: +10% de bonus de score pour chaque perk actif.',
        'es': 'PERK: +10% de bonificación de puntos por cada perk activo.',
        'it': 'PERK: +10% bonus punti per ogni perk attivo.',
        'pt': 'PERK: +10% de bônus de pontos para cada perk ativo.',
        'ja': 'PERK: 有効なパークごとにスコア+10%。',
        'zh': 'PERK：每个激活能力 +10% 得分。',
        'ko': 'PERK: 활성 특성당 점수 +10%.'
    },
    'card_perk_second_pocket_title': {
        'tr': 'Ekstra Cep', 'en': 'Extra Pocket', 'de': 'Extrafach',
        'fr': 'Poche Extra', 'es': 'Bolsillo Extra', 'it': 'Tasca Extra', 'pt': 'Bolso Extra', 'ja': 'エクストラポケット', 'zh': '额外口袋', 'ko': '추가 보관함'
    },
    'card_perk_second_pocket_desc': {
        'tr': 'PERK: V tuşuyla ikinci bir parça saklayabilirsin.',
        'en': 'PERK: Press V to store a second piece.',
        'de': 'PERK: Drücke V um ein zweites Teil zu speichern.',
        'fr': 'PERK: Appuyez sur V pour stocker une deuxième pièce.',
        'es': 'PERK: Presiona V para guardar una segunda pieza.',
        'it': 'PERK: Premi V per conservare un secondo pezzo.',
        'pt': 'PERK: Pressione V para guardar uma segunda peça.',
        'ja': 'PERK: Vで2つ目のピースを保持。',
        'zh': 'PERK：按 V 存第二个方块。',
        'ko': 'PERK: V로 두 번째 피스를 보관합니다.'
    },
    'card_perk_alchemist_title': {
        'tr': 'Altın Dokunuş', 'en': 'Golden Touch', 'de': 'Goldene Berührung',
        'fr': 'Toucher Doré', 'es': 'Toque Dorado', 'it': 'Tocco Dorato', 'pt': 'Toque Dourado', 'ja': 'ゴールデンタッチ', 'zh': '黄金之触', 'ko': '황금 손길'
    },
    'card_perk_alchemist_desc': {
        'tr': 'PERK: 4 satır (Quadrix) temizleyince rastgele bloklar altına döner.',
        'en': 'PERK: Clearing 4 lines (Quadrix) turns random blocks to gold.',
        'de': 'PERK: Bei 4 Zeilen (Quadrix) werden zufällige Blöcke zu Gold.',
        'fr': 'PERK: Effacer 4 lignes (Quadrix) transforme des blocs aléatoires en or.',
        'es': 'PERK: Limpiar 4 líneas (Quadrix) convierte bloques aleatorios en oro.',
        'it': 'PERK: Cancellare 4 linee (Quadrix) trasforma blocchi casuali in oro.',
        'pt': 'PERK: Limpar 4 linhas (Quadrix) transforma blocos aleatórios em ouro.',
        'ja': 'PERK: 4ライン(Quadrix)消去でランダムブロックが金に。',
        'zh': 'PERK：清除 4 行（四消）后随机方块变为金色。',
        'ko': 'PERK: 4줄(테트리스) 제거 시 랜덤 블록이 금으로 변합니다.'
    },
    'card_gravity_well_title': {
        'tr': 'Yerçekimi Dalgası', 'en': 'Gravity Wave', 'de': 'Gravitationswelle',
        'fr': 'Vague de Gravité', 'es': 'Onda de Gravedad', 'it': 'Onda Gravitazionale', 'pt': 'Onda Gravitacional', 'ja': 'グラビティウェーブ', 'zh': '引力波', 'ko': '중력 파동'
    },
    'card_gravity_well_desc': {
        'tr': 'Bloklar aşağı çöker, oluşan tüm dolu satırlar temizlenir.',
        'en': 'Blocks collapse down, all filled rows are cleared.',
        'de': 'Blöcke fallen nach unten, alle vollen Zeilen werden gelöscht.',
        'fr': 'Les blocs s\'effondrent, toutes les lignes pleines sont effacées.',
        'es': 'Los bloques colapsan hacia abajo, todas las filas llenas se limpian.',
        'it': 'I blocchi crollano, tutte le righe piene vengono cancellate.',
        'pt': 'Blocos desabam, todas as linhas cheias são limpas.',
        'ja': 'ブロックが落下して詰まり、すべての埋まった行が消える。',
        'zh': '方块下坠，所有满行都会被清除。',
        'ko': '블록이 내려와 모든 꽉 찬 줄이 제거됩니다.'
    },
    'card_ghost_echo_title': {
        'tr': 'İkinci Şans', 'en': 'Second Chance', 'de': 'Zweite Chance',
        'fr': 'Seconde Chance', 'es': 'Segunda Oportunidad', 'it': 'Seconda Possibilità', 'pt': 'Segunda Chance', 'ja': 'セカンドチャンス', 'zh': '第二次机会', 'ko': '두 번째 기회'
    },
    'card_ghost_echo_desc': {
        'tr': 'Ölümden Dönüş: Oyun bitecekken üst yarıyı temizler, devam edersin.',
        'en': 'Resurrection: When game would end, clears top half and you continue.',
        'de': 'Auferstehung: Wenn das Spiel enden würde, wird die obere Hälfte gelöscht und du spielst weiter.',
        'fr': 'Résurrection: Quand le jeu va finir, efface la moitié supérieure et vous continuez.',
        'es': 'Resurrección: Cuando el juego iba a terminar, limpia la mitad superior y continúas.',
        'it': 'Resurrezione: Quando il gioco sta per finire, cancella la metà superiore e continui.',
        'pt': 'Ressurreição: Quando o jogo ia acabar, limpa a metade superior e você continua.',
        'ja': '復活: ゲーム終了直前に上半分を消去して続行。',
        'zh': '复活：游戏将结束时清除上半部并继续。',
        'ko': '부활: 게임이 끝나기 직전 상단 절반을 지우고 계속합니다.'
    },
    'card_row_shuffle_title': {
        'tr': 'Blok Karıştırıcı', 'en': 'Block Shuffler', 'de': 'Blockmischer',
        'fr': 'Mélangeur de Blocs', 'es': 'Mezclador de Bloques', 'it': 'Mischia Blocchi', 'pt': 'Misturador de Blocos', 'ja': 'ブロックシャッフル', 'zh': '方块洗牌', 'ko': '블록 셔플러'
    },
    'card_row_shuffle_desc': {
        'tr': 'Alt {value} satırdaki blokları karıştırır, şansını dene!',
        'en': 'Shuffles blocks in the bottom {value} rows, try your luck!',
        'de': 'Mischt Blöcke in den unteren {value} Zeilen, versuche dein Glück!',
        'fr': 'Mélange les blocs dans les {value} lignes du bas, tente ta chance!',
        'es': '¡Mezcla los bloques en las {value} filas inferiores, prueba tu suerte!',
        'it': 'Mescola i blocchi nelle {value} righe inferiori, tenta la fortuna!',
        'pt': 'Embaralha blocos nas {value} linhas inferiores, tente a sorte!',
        'ja': '下{value}行のブロックをシャッフル。運試し！',
        'zh': '打乱底部 {value} 行方块，试试运气！',
        'ko': '아래 {value}줄의 블록을 섞습니다. 행운을 빌어요!'
    },
    'card_laser_drill_title': {
        'tr': 'Delici Parça', 'en': 'Drill Piece', 'de': 'Bohrteil',
        'fr': 'Pièce Foreuse', 'es': 'Pieza Perforadora', 'it': 'Pezzo Trapano', 'pt': 'Peça Perfuradora', 'ja': 'ドリルピース', 'zh': '钻孔方块', 'ko': '드릴 피스'
    },
    'card_laser_drill_desc': {
        'tr': 'Mevcut parça düşerken önündeki blokları eritir.',
        'en': 'Current piece melts blocks in its path while falling.',
        'de': 'Das aktuelle Teil schmilzt Blöcke auf seinem Weg beim Fallen.',
        'fr': 'La pièce actuelle fait fondre les blocs sur son chemin en tombant.',
        'es': 'La pieza actual derrite los bloques en su camino mientras cae.',
        'it': 'Il pezzo corrente scioglie i blocchi sul suo percorso mentre cade.',
        'pt': 'A peça atual derrete blocos em seu caminho ao cair.',
        'ja': '落下中、進路のブロックを溶かす。',
        'zh': '下落时融化路径上的方块。',
        'ko': '낙하 중 경로의 블록을 녹입니다.'
    },
    'card_sniper_shot_title': {
        'tr': 'Keskin Nişancı', 'en': 'Sniper Shot', 'de': 'Scharfschuss',
        'fr': 'Tir de Sniper', 'es': 'Disparo de Francotirador', 'it': 'Colpo da Cecchino', 'pt': 'Tiro de Atirador', 'ja': 'スナイパーショット', 'zh': '狙击射击', 'ko': '스나이퍼 샷'
    },
    'card_sniper_shot_desc': {
        'tr': '3 hak: Tahtada istediğin bir bloğu tıklayarak patlat.',
        'en': '3 uses: Click any block on the board to explode it.',
        'de': '3 Verwendungen: Klicke auf einen Block auf dem Brett, um ihn zu sprengen.',
        'fr': '3 utilisations : cliquez sur un bloc du plateau pour le faire exploser.',
        'es': '3 usos: Haz clic en un bloque del tablero para hacerlo explotar.',
        'it': '3 usi: Clicca su un blocco della griglia per farlo esplodere.',
        'pt': '3 usos: Clique em um bloco no tabuleiro para explodi-lo.',
        'ja': '3回: 盤面の任意のブロックをクリックして爆破。',
        'zh': '3 次：点击棋盘任意方块引爆。',
        'ko': '3회: 보드의 원하는 블록을 클릭해 폭발시킵니다.'
    },
    'card_future_changer_title': {
        'tr': 'Geleceği Değiştiren', 'en': 'Future Changer', 'de': 'Zukunftsänderer',
        'fr': 'Changeur de Futur', 'es': 'Cambiador del Futuro', 'it': 'Cambia Futuro', 'pt': 'Mudador do Futuro', 'ja': 'フューチャーチェンジャー', 'zh': '改变未来者', 'ko': '미래 변경자'
    },
    'card_future_changer_desc': {
        'tr': 'Sonraki 2 parçayı kendin seç! Bir popup açılır ve istediğin parçaları seçersin.',
        'en': 'Choose the next 2 pieces yourself! A popup opens and you select the pieces you want.',
        'de': 'Wähle die nächsten 2 Teile selbst! Ein Popup öffnet sich und du wählst die gewünschten Teile.',
        'fr': 'Choisissez les 2 prochaines pièces vous-même! Une fenêtre s\'ouvre et vous sélectionnez les pièces souhaitées.',
        'es': '¡Elige las próximas 2 piezas tú mismo! Se abre una ventana y seleccionas las piezas que quieras.',
        'it': 'Scegli tu stesso i prossimi 2 pezzi! Si apre un popup e selezioni i pezzi che vuoi.',
        'pt': 'Escolha as próximas 2 peças você mesmo! Um popup abre e você seleciona as peças que deseja.',
        'ja': '次の2個のピースを自分で選ぶ！ポップアップで選択。',
        'zh': '自己选择接下来 2 个方块！弹窗中选择。',
        'ko': '다음 2개 피스를 직접 선택! 팝업에서 선택합니다.'
    },
    
    # ==================== KART UI ÇEVİRİLERİ ====================
    'card_rarity_common': {
        'tr': 'Common', 'en': 'Common', 'de': 'Gewöhnlich', 'fr': 'Commun', 'es': 'Común', 'it': 'Comune', 'pt': 'Comum', 'ja': 'コモン', 'zh': '普通', 'ko': '일반'
    },
    'card_rarity_rare': {
        'tr': 'Rare', 'en': 'Rare', 'de': 'Selten', 'fr': 'Rare', 'es': 'Raro', 'it': 'Raro', 'pt': 'Raro', 'ja': 'レア', 'zh': '稀有', 'ko': '레어'
    },
    'card_rarity_epic': {
        'tr': 'Epic', 'en': 'Epic', 'de': 'Episch', 'fr': 'Épique', 'es': 'Épico', 'it': 'Epico', 'pt': 'Épico', 'ja': 'エピック', 'zh': '史诗', 'ko': '에픽'
    },
    'card_rarity_legendary': {
        'tr': 'Legendary', 'en': 'Legendary', 'de': 'Legendär', 'fr': 'Légendaire', 'es': 'Legendario', 'it': 'Leggendario', 'pt': 'Lendário', 'ja': 'レジェンダリー', 'zh': '传奇', 'ko': '레전더리'
    },
    'card_selection_title': {
        'tr': 'KART SEÇ', 'en': 'PICK A CARD', 'de': 'WÄHLE EINE KARTE', 'fr': 'CHOISISSEZ UNE CARTE', 'es': 'ELIGE UNA CARTA', 'it': 'SCEGLI UNA CARTA', 'pt': 'ESCOLHA UMA CARTA', 'ja': 'カードを選択', 'zh': '选择卡牌', 'ko': '카드 선택'
    },
    'card_skip': {
        'tr': 'Kartı Atla', 'en': 'Skip Card', 'de': 'Karte überspringen', 'fr': 'Passer la Carte', 'es': 'Saltar Carta', 'it': 'Salta Carta', 'pt': 'Pular Carta', 'ja': 'カードをスキップ', 'zh': '跳过卡牌', 'ko': '카드 건너뛰기'
    },
    'card_hint_equal': {
        'tr': 'Kartlar eşit şansta', 'en': 'Equal chance for all cards', 'de': 'Gleiche Chance für alle Karten', 'fr': 'Chance égale pour toutes les cartes', 'es': 'Igual oportunidad para todas las cartas', 'it': 'Uguale possibilità per tutte le carte', 'pt': 'Chance igual para todas as cartas', 'ja': 'すべてのカードが同じ確率', 'zh': '所有卡牌概率相同', 'ko': '모든 카드 동일 확률'
    },
    'card_hint_random': {
        'tr': 'Tamamen rastgele', 'en': 'Completely random', 'de': 'Völlig zufällig', 'fr': 'Complètement aléatoire', 'es': 'Completamente aleatorio', 'it': 'Completamente casuale', 'pt': 'Completamente aleatório', 'ja': '完全ランダム', 'zh': '完全随机', 'ko': '완전 랜덤'
    },
    'card_placeholder_empty': {
        'tr': 'Henüz kart yok', 'en': 'No cards yet', 'de': 'Noch keine Karten', 'fr': 'Pas encore de cartes', 'es': 'Aún no hay cartas', 'it': 'Nessuna carta ancora', 'pt': 'Nenhuma carta ainda', 'ja': 'まだカードがありません', 'zh': '还没有卡牌', 'ko': '아직 카드 없음'
    },
    'card_placeholder_no_perks': {
        'tr': 'Kalıcı perk yok', 'en': 'No persistent perks', 'de': 'Keine dauerhaften Perks', 'fr': 'Aucun perk permanent', 'es': 'Sin perks permanentes', 'it': 'Nessun perk permanente', 'pt': 'Nenhum perk permanente', 'ja': '永続パークなし', 'zh': '无永久能力', 'ko': '영구 특성 없음'
    },
    'card_placeholder_no_limited': {
        'tr': 'Sınırlı kart yok', 'en': 'No limited cards', 'de': 'Keine begrenzten Karten', 'fr': 'Aucune carte limitée', 'es': 'Sin cartas limitadas', 'it': 'Nessuna carta limitata', 'pt': 'Nenhuma carta limitada', 'ja': '限定カードなし', 'zh': '没有限定卡牌', 'ko': '제한 카드 없음'
    },
    'card_level_progress': {
        'tr': 'Seviye ilerleme: {current}/{needed}',
        'en': 'Level progress: {current}/{needed}',
        'de': 'Level-Fortschritt: {current}/{needed}',
        'fr': 'Progression du niveau : {current}/{needed}',
        'es': 'Progreso de nivel: {current}/{needed}',
        'it': 'Progresso livello: {current}/{needed}',
        'pt': 'Progresso de nível: {current}/{needed}',
        'ja': 'レベル進行: {current}/{needed}',
        'zh': '等级进度：{current}/{needed}',
        'ko': '레벨 진행: {current}/{needed}'
    },
    'card_pool_label': {
        'tr': 'Kart Havuzu: {hint}',
        'en': 'Card Pool: {hint}',
        'de': 'Kartenpool: {hint}',
        'fr': 'Pool de cartes : {hint}',
        'es': 'Reserva de cartas: {hint}',
        'it': 'Pool di carte: {hint}',
        'pt': 'Pool de cartas: {hint}',
        'ja': 'カードプール: {hint}',
        'zh': '卡池：{hint}',
        'ko': '카드 풀: {hint}'
    },
    
    # ==================== MOD İSİMLERİ ====================
    'mode_label_classic': {
        'tr': 'Klasik', 'en': 'Classic', 'de': 'Klassik', 'fr': 'Classique', 'es': 'Clásico', 'it': 'Classico', 'pt': 'Clássico', 'ja': 'クラシック', 'zh': '经典', 'ko': '클래식'
    },
    'mode_label_sprint': {
        'tr': 'Sprint', 'en': 'Sprint', 'de': 'Sprint', 'fr': 'Sprint', 'es': 'Sprint', 'it': 'Sprint', 'pt': 'Sprint', 'ja': 'スプリント', 'zh': '冲刺', 'ko': '스프린트'
    },
    'mode_label_ultra': {
        'tr': 'Ultra', 'en': 'Ultra', 'de': 'Ultra', 'fr': 'Ultra', 'es': 'Ultra', 'it': 'Ultra', 'pt': 'Ultra', 'ja': 'ウルトラ', 'zh': '超强', 'ko': '울트라'
    },
    'mode_label_zen': {
        'tr': 'Zen', 'en': 'Zen', 'de': 'Zen', 'fr': 'Zen', 'es': 'Zen', 'it': 'Zen', 'pt': 'Zen', 'ja': 'ゼン', 'zh': '禅', 'ko': '젠'
    },
    'mode_label_card_mastery': {
        'tr': 'Kart Ustalığı', 'en': 'Card Mastery', 'de': 'Kartenmeisterschaft', 'fr': 'Maîtrise des Cartes', 'es': 'Maestría de Cartas', 'it': 'Maestria delle Carte', 'pt': 'Maestria de Cartas', 'ja': 'カードマスタリー', 'zh': '卡牌大师', 'ko': '카드 마스터리'
    },
    'mode_label_survival': {
        'tr': 'Survival', 'en': 'Survival', 'de': 'Überleben', 'fr': 'Survie', 'es': 'Supervivencia', 'it': 'Sopravvivenza', 'pt': 'Sobrevivência', 'ja': 'サバイバル', 'zh': '生存', 'ko': '서바이벌'
    },
    'mode_label_cascade': {
        'tr': 'Cascade', 'en': 'Cascade', 'de': 'Cascade', 'fr': 'Cascade', 'es': 'Cascade', 'it': 'Cascade', 'pt': 'Cascade', 'ja': 'カスケード', 'zh': '级联', 'ko': '캐스케이드'
    },
    'mode_label_wide': {
        'tr': 'Wide', 'en': 'Wide', 'de': 'Wide', 'fr': 'Wide', 'es': 'Wide', 'it': 'Wide', 'pt': 'Wide', 'ja': 'ワイド', 'zh': '宽屏', 'ko': '와이드'
    },
    'mode_label_hardcore': {
        'tr': 'Hardcore', 'en': 'Hardcore', 'de': 'Hardcore', 'fr': 'Hardcore', 'es': 'Hardcore', 'it': 'Hardcore', 'pt': 'Hardcore', 'ja': 'ハードコア', 'zh': '硬核', 'ko': '하드코어'
    },
    'mode_tetris_extra': {
        'tr': 'QUADRIX EXTRA', 'en': 'QUADRIX EXTRA', 'de': 'QUADRIX EXTRA', 'fr': 'QUADRIX EXTRA', 'es': 'QUADRIX EXTRA', 'it': 'QUADRIX EXTRA', 'pt': 'QUADRIX EXTRA', 'ja': 'テトリスエクストラ', 'zh': 'QUADRIX EXTRA', 'ko': '테트리스 엑스트라'
    },
    'mode_card_mastery': {
        'tr': 'Kart Ustalığı', 'en': 'Card Mastery', 'de': 'Kartenmeisterschaft', 'fr': 'Maîtrise des Cartes', 'es': 'Maestría de Cartas', 'it': 'Maestria delle Carte', 'pt': 'Maestria de Cartas', 'ja': 'カードマスタリー', 'zh': '卡牌大师', 'ko': '카드 마스터리'
    },
    'mode_wide': {
        'tr': 'Geniş Mod', 'en': 'Wide Mode', 'de': 'Breiter Modus', 'fr': 'Mode Large', 'es': 'Modo Ancho', 'it': 'Modalità Larga', 'pt': 'Modo Largo', 'ja': 'ワイドモード', 'zh': '宽屏模式', 'ko': '와이드 모드'
    },
    'mode_classic': {
        'tr': 'KLASİK MOD', 'en': 'CLASSIC MODE', 'de': 'KLASSISCHER MODUS', 'fr': 'MODE CLASSIQUE', 'es': 'MODO CLÁSICO', 'it': 'MODALITÀ CLASSICA', 'pt': 'MODO CLÁSSICO', 'ja': 'クラシックモード', 'zh': '经典模式', 'ko': '클래식 모드'
    },
    'mode_sprint': {
        'tr': 'SPRINT MOD', 'en': 'SPRINT MODE', 'de': 'SPRINT-MODUS', 'fr': 'MODE SPRINT', 'es': 'MODO SPRINT', 'it': 'MODALITÀ SPRINT', 'pt': 'MODO SPRINT', 'ja': 'スプリントモード', 'zh': '冲刺模式', 'ko': '스프린트 모드'
    },
    'mode_ultra': {
        'tr': 'ULTRA MOD', 'en': 'ULTRA MODE', 'de': 'ULTRA-MODUS', 'fr': 'MODE ULTRA', 'es': 'MODO ULTRA', 'it': 'MODALITÀ ULTRA', 'pt': 'MODO ULTRA', 'ja': 'ウルトラモード', 'zh': '超强模式', 'ko': '울트라 모드'
    },
    'mode_zen': {
        'tr': 'ZEN MOD', 'en': 'ZEN MODE', 'de': 'ZEN-MODUS', 'fr': 'MODE ZEN', 'es': 'MODO ZEN', 'it': 'MODALITÀ ZEN', 'pt': 'MODO ZEN', 'ja': 'ゼンモード', 'zh': '禅模式', 'ko': '젠 모드'
    },
    'mode_survival': {
        'tr': 'HAYATTA KAL', 'en': 'SURVIVAL', 'de': 'ÜBERLEBEN', 'fr': 'SURVIE', 'es': 'SUPERVIVENCIA', 'it': 'SOPRAVVIVENZA', 'pt': 'SOBREVIVÊNCIA', 'ja': 'サバイバル', 'zh': '生存', 'ko': '서바이벌'
    },
    'mode_cascade': {
        'tr': 'CASCADE MOD', 'en': 'CASCADE MODE', 'de': 'CASCADE-MODUS', 'fr': 'MODE CASCADE', 'es': 'MODO CASCADE', 'it': 'MODALITÀ CASCADE', 'pt': 'MODO CASCADE', 'ja': 'カスケードモード', 'zh': '级联模式', 'ko': '캐스케이드 모드'
    },
    'mode_challenge': {
        'tr': 'MEYDAN OKUMA', 'en': 'CHALLENGE', 'de': 'HERAUSFORDERUNG', 'fr': 'DÉFI', 'es': 'DESAFÍO', 'it': 'SFIDA', 'pt': 'DESAFIO', 'ja': 'チャレンジ', 'zh': '挑战', 'ko': '도전'
    },
    'mode_mystery': {
        'tr': 'GİZEM MODU', 'en': 'MYSTERY MODE', 'de': 'MYSTERIÖSER MODUS', 'fr': 'MODE MYSTÈRE', 'es': 'MODO MISTERIO', 'it': 'MODALITÀ MISTERO', 'pt': 'MODO MISTÉRIO', 'ja': 'ミステリーモード', 'zh': '神秘模式', 'ko': '미스터리 모드'
    },
    'mode_pvp': {
        'tr': 'PvP MOD', 'en': 'PvP MODE', 'de': 'PvP-MODUS', 'fr': 'MODE PvP', 'es': 'MODO PvP', 'it': 'MODALITÀ PvP', 'pt': 'MODO PvP', 'ja': 'PvPモード', 'zh': 'PvP 模式', 'ko': 'PvP 모드'
    },
    'mode_hardcore': {
        'tr': 'HARDCORE MOD', 'en': 'HARDCORE MODE', 'de': 'HARDCORE-MODUS', 'fr': 'MODE HARDCORE', 'es': 'MODO HARDCORE', 'it': 'MODALITÀ HARDCORE', 'pt': 'MODO HARDCORE', 'ja': 'ハードコアモード', 'zh': '硬核模式', 'ko': '하드코어 모드'
    },
    'mode_daily': {
        'tr': 'GÜNLÜK GÖREV', 'en': 'DAILY CHALLENGE', 'de': 'TÄGLICHE HERAUSFORDERUNG', 'fr': 'DÉFI QUOTIDIEN', 'es': 'DESAFÍO DIARIO', 'it': 'SFIDA GIORNALIERA', 'pt': 'DESAFIO DIÁRIO', 'ja': 'デイリーチャレンジ', 'zh': '每日挑战', 'ko': '일일 도전'
    },
    
    # ==================== KART TİP ETİKETLERİ ====================
    'card_type_persistent': {
        'tr': 'Kalıcı', 'en': 'Persistent', 'de': 'Dauerhaft', 'fr': 'Permanent', 'es': 'Permanente', 'it': 'Permanente', 'pt': 'Permanente', 'ja': '永続', 'zh': '永久', 'ko': '영구'
    },
    'card_type_single_use': {
        'tr': 'Tek Kullanım', 'en': 'Single Use', 'de': 'Einmalig', 'fr': 'Usage Unique', 'es': 'Un Solo Uso', 'it': 'Uso Singolo', 'pt': 'Uso Único', 'ja': '使い切り', 'zh': '一次性', 'ko': '일회용'
    },
    'card_type_limited': {
        'tr': 'Sınırlı', 'en': 'Limited', 'de': 'Begrenzt', 'fr': 'Limité', 'es': 'Limitado', 'it': 'Limitato', 'pt': 'Limitado', 'ja': '限定', 'zh': '限定', 'ko': '제한'
    },
    'card_selected': {
        'tr': '{title} seçildi!', 'en': '{title} selected!', 'de': '{title} ausgewählt!', 'fr': '{title} sélectionné!', 'es': '¡{title} seleccionada!', 'it': '{title} selezionato!', 'pt': '{title} selecionado!', 'ja': '{title} を選択！', 'zh': '{title} 已选择！', 'ko': '{title} 선택됨!'
    },
    
    # ==================== KONTROL ETİKETLERİ ====================
    'tab_single_player': {
        'tr': 'Tek Oyuncu', 'en': 'Single Player', 'de': 'Einzelspieler', 'fr': 'Solo', 'es': 'Un Jugador', 'it': 'Giocatore Singolo', 'pt': 'Um Jogador', 'ja': 'シングル', 'zh': '单人', 'ko': '싱글'
    },
    'tab_pvp_player1': {
        'tr': 'PvP - Oyuncu 1', 'en': 'PvP - Player 1', 'de': 'PvP - Spieler 1', 'fr': 'PvP - Joueur 1', 'es': 'PvP - Jugador 1', 'it': 'PvP - Giocatore 1', 'pt': 'PvP - Jogador 1', 'ja': 'PvP - プレイヤー1', 'zh': 'PvP - 玩家1', 'ko': 'PvP - 플레이어 1'
    },
    'tab_pvp_player2': {
        'tr': 'PvP - Oyuncu 2', 'en': 'PvP - Player 2', 'de': 'PvP - Spieler 2', 'fr': 'PvP - Joueur 2', 'es': 'PvP - Jugador 2', 'it': 'PvP - Giocatore 2', 'pt': 'PvP - Jogador 2', 'ja': 'PvP - プレイヤー2', 'zh': 'PvP - 玩家2', 'ko': 'PvP - 플레이어 2'
    },
    'ctrl_move_left': {
        'tr': 'Sola kay', 'en': 'Move Left', 'de': 'Links bewegen', 'fr': 'Déplacer à gauche', 'es': 'Mover izquierda', 'it': 'Muovi sinistra', 'pt': 'Mover esquerda', 'ja': '左へ移動', 'zh': '向左移动', 'ko': '왼쪽 이동'
    },
    'ctrl_move_right': {
        'tr': 'Sağa kay', 'en': 'Move Right', 'de': 'Rechts bewegen', 'fr': 'Déplacer à droite', 'es': 'Mover derecha', 'it': 'Muovi destra', 'pt': 'Mover direita', 'ja': '右へ移動', 'zh': '向右移动', 'ko': '오른쪽 이동'
    },
    'ctrl_soft_drop': {
        'tr': 'Hızlı indir', 'en': 'Soft Drop', 'de': 'Sanft fallen', 'fr': 'Descente douce', 'es': 'Bajada suave', 'it': 'Discesa morbida', 'pt': 'Descida suave', 'ja': 'ソフトドロップ', 'zh': '软降', 'ko': '소프트 드롭'
    },
    'ctrl_hard_drop': {
        'tr': 'Anında bırak', 'en': 'Hard Drop', 'de': 'Hart fallen', 'fr': 'Descente rapide', 'es': 'Bajada rápida', 'it': 'Discesa rapida', 'pt': 'Queda rápida', 'ja': 'ハードドロップ', 'zh': '硬降', 'ko': '하드 드롭'
    },
    'ctrl_rotate': {
        'tr': 'Döndür', 'en': 'Rotate', 'de': 'Drehen', 'fr': 'Tourner', 'es': 'Rotar', 'it': 'Ruota', 'pt': 'Girar', 'ja': '回転', 'zh': '旋转', 'ko': '회전'
    },
    'ctrl_hold': {
        'tr': 'Hold / değiştir', 'en': 'Hold / swap', 'de': 'Halten / Tauschen', 'fr': 'Garder / Échanger', 'es': 'Guardar / Cambiar', 'it': 'Tieni / Scambia', 'pt': 'Guardar / Trocar', 'ja': 'ホールド/入れ替え', 'zh': '保留/交换', 'ko': '홀드/교체'
    },
    'ctrl_pause': {
        'tr': 'Duraklat', 'en': 'Pause', 'de': 'Pause', 'fr': 'Pause', 'es': 'Pausa', 'it': 'Pausa', 'pt': 'Pausar', 'ja': '一時停止', 'zh': '暂停', 'ko': '일시정지'
    },
    'ctrl_toggle_fps': {
        'tr': 'FPS göster', 'en': 'Toggle FPS', 'de': 'FPS anzeigen', 'fr': 'Afficher FPS', 'es': 'Mostrar FPS', 'it': 'Mostra FPS', 'pt': 'Mostrar FPS', 'ja': 'FPS表示切替', 'zh': '显示 FPS', 'ko': 'FPS 표시'
    },
    'ctrl_fullscreen_toggle': {
        'tr': 'Tam ekran', 'en': 'Fullscreen', 'de': 'Vollbild', 'fr': 'Plein écran', 'es': 'Pantalla completa', 'it': 'Schermo intero', 'pt': 'Tela cheia', 'ja': '全画面', 'zh': '全屏', 'ko': '전체 화면'
    },
    
    # ==================== MENÜ VE PANEL BAŞLIKLARI ====================
    'panel_scores': {
        'tr': 'SKOR TABLOSU', 'en': 'SCOREBOARD', 'de': 'PUNKTETAFEL', 'fr': 'TABLEAU DES SCORES', 'es': 'TABLA DE PUNTOS', 'it': 'CLASSIFICA', 'pt': 'PLACAR', 'ja': 'スコアボード'
    },
    'panel_block_styles': {
        'tr': 'BLOK GÖRÜNÜMLERİ', 'en': 'BLOCK STYLES', 'de': 'BLOCKSTILE', 'fr': 'STYLES DE BLOCS', 'es': 'ESTILOS DE BLOQUES', 'it': 'STILI BLOCCHI', 'pt': 'ESTILOS DE BLOCOS', 'ja': 'ブロックスタイル'
    },
    'block_style_mode_block': {
        'tr': 'Blok Görünümleri (Sadece Renk)',
        'en': 'Block Styles (Color Only)',
        'de': 'Blockstile (Nur Farbe)',
        'fr': 'Styles de Blocs (Couleur seulement)',
        'es': 'Estilos de Bloques (Solo color)',
        'it': 'Stili Blocchi (Solo colore)',
        'pt': 'Estilos de Blocos (Somente cor)',
        'ja': 'ブロックスタイル(色のみ)'
    },
    'block_style_mode_custom': {
        'tr': '{theme} Renkleri',
        'en': '{theme} Colors',
        'de': '{theme}-Farben',
        'fr': 'Couleurs {theme}',
        'es': 'Colores de {theme}',
        'it': 'Colori {theme}',
        'pt': 'Cores de {theme}',
        'ja': '{theme} カラー'
    },
    'block_style_btn_custom': {
        'tr': 'Özel', 'en': 'Custom', 'de': 'Benutzer', 'fr': 'Personnalisé', 'es': 'Personalizado', 'it': 'Personalizzato', 'pt': 'Personalizado', 'ja': 'カスタム'
    },
    'block_style_btn_default': {
        'tr': 'Varsayılan', 'en': 'Default', 'de': 'Standard', 'fr': 'Par défaut', 'es': 'Predeterminado', 'it': 'Predefinito', 'pt': 'Padrão', 'ja': 'デフォルト'
    },
    'block_style_footer_line1_block': {
        'tr': 'Çift Sol Tık: Renk seç | R: Renk sıfırla',
        'en': 'Double left click: Pick color | R: Reset color',
        'de': 'Doppelklick links: Farbe wählen | R: Farbe zurücksetzen',
        'fr': 'Double clic gauche : Choisir couleur | R : Réinitialiser couleur',
        'es': 'Doble clic izquierdo: Elegir color | R: Restablecer color',
        'it': 'Doppio clic sinistro: Scegli colore | R: Reimposta colore',
        'pt': 'Duplo clique esquerdo: Escolher cor | R: Restaurar cor',
        'ja': '左ダブルクリック: 色を選択 | R: 色をリセット'
    },
    'block_style_footer_line2_block': {
        'tr': 'TAB: Mod değiştir | Mouse: Kaydır | ESC: Geri | F12: Tam ekran',
        'en': 'TAB: Switch mode | Mouse: Scroll | ESC: Back | F12: Fullscreen',
        'de': 'TAB: Modus wechseln | Maus: Scrollen | ESC: Zurück | F12: Vollbild',
        'fr': 'TAB : Changer de mode | Souris : Défiler | ESC : Retour | F12 : Plein écran',
        'es': 'TAB: Cambiar modo | Ratón: Desplazar | ESC: Volver | F12: Pantalla completa',
        'it': 'TAB: Cambia modalità | Mouse: Scorri | ESC: Indietro | F12: Schermo intero',
        'pt': 'TAB: Mudar modo | Mouse: Rolar | ESC: Voltar | F12: Tela cheia',
        'ja': 'TAB: モード切替 | マウス: スクロール | ESC: 戻る | F12: 全画面',
        'zh': 'TAB：切换模式 | 鼠标：滚动 | ESC：返回 | F12：全屏',
        'ko': 'TAB: 모드 전환 | 마우스: 스크롤 | ESC: 뒤로 | F12: 전체 화면'
    },
    'block_style_footer_line1_custom': {
        'tr': 'Çift Sol Tık: Renk seç | R: Varsayılan | C: Mevcut temadan kopyala ({theme})',
        'en': 'Double left click: Pick color | R: Default | C: Copy from current theme ({theme})',
        'de': 'Doppelklick links: Farbe wählen | R: Standard | C: Aus aktuellem Thema kopieren ({theme})',
        'fr': 'Double clic gauche : Choisir couleur | R : Par défaut | C : Copier depuis le thème actuel ({theme})',
        'es': 'Doble clic izquierdo: Elegir color | R: Predeterminado | C: Copiar del tema actual ({theme})',
        'it': 'Doppio clic sinistro: Scegli colore | R: Predefinito | C: Copia dal tema attuale ({theme})',
        'pt': 'Duplo clique esquerdo: Escolher cor | R: Padrão | C: Copiar do tema atual ({theme})',
        'ja': '左ダブルクリック: 色を選択 | R: デフォルト | C: 現在のテーマからコピー ({theme})',
        'zh': '双击左键：选择颜色 | R：默认 | C：从当前主题复制（{theme}）',
        'ko': '왼쪽 더블클릭: 색 선택 | R: 기본 | C: 현재 테마에서 복사 ({theme})'
    },
    'block_style_footer_line2_custom': {
        'tr': 'TAB: Mod değiştir ({theme}) | Mouse: Kaydır | ESC: Geri | F12: Tam ekran',
        'en': 'TAB: Switch mode ({theme}) | Mouse: Scroll | ESC: Back | F12: Fullscreen',
        'de': 'TAB: Modus wechseln ({theme}) | Maus: Scrollen | ESC: Zurück | F12: Vollbild',
        'fr': 'TAB : Changer de mode ({theme}) | Souris : Défiler | ESC : Retour | F12 : Plein écran',
        'es': 'TAB: Cambiar modo ({theme}) | Ratón: Desplazar | ESC: Volver | F12: Pantalla completa',
        'it': 'TAB: Cambia modalità ({theme}) | Mouse: Scorri | ESC: Indietro | F12: Schermo intero',
        'pt': 'TAB: Mudar modo ({theme}) | Mouse: Rolar | ESC: Voltar | F12: Tela cheia',
        'ja': 'TAB: モード切替 ({theme}) | マウス: スクロール | ESC: 戻る | F12: 全画面',
        'zh': 'TAB：切换模式（{theme}） | 鼠标：滚动 | ESC：返回 | F12：全屏',
        'ko': 'TAB: 모드 전환 ({theme}) | 마우스: 스크롤 | ESC: 뒤로 | F12: 전체 화면'
    },
    'block_style_reset_all_log': {
        'tr': '↩️ Tüm özel blok temaları varsayılan tema renklerine döndürüldü',
        'en': '↩️ All custom block styles reset to theme defaults',
        'de': '↩️ Alle benutzerdefinierten Blockstile auf Standard zurückgesetzt',
        'fr': '↩️ Tous les styles de blocs personnalisés réinitialisés',
        'es': '↩️ Todos los estilos personalizados restablecidos a los valores predeterminados',
        'it': '↩️ Tutti gli stili personalizzati ripristinati ai predefiniti',
        'pt': '↩️ Todos os estilos personalizados restaurados ao padrão',
        'ja': '↩️ すべてのカスタムブロックスタイルをデフォルトに戻しました',
        'zh': '↩️ 所有自定义方块样式已重置为主题默认值',
        'ko': '↩️ 모든 사용자 지정 블록 스타일이 테마 기본값으로 초기화되었습니다'
    },
    'block_style_mode_changed_log': {
        'tr': '🔁 Mod değişti: {mode}',
        'en': '🔁 Mode changed: {mode}',
        'de': '🔁 Modus gewechselt: {mode}',
        'fr': '🔁 Mode changé : {mode}',
        'es': '🔁 Modo cambiado: {mode}',
        'it': '🔁 Modalità cambiata: {mode}',
        'pt': '🔁 Modo alterado: {mode}',
        'ja': '🔁 モード変更: {mode}',
        'zh': '🔁 模式已更改：{mode}',
        'ko': '🔁 모드 변경: {mode}'
    },
    'block_style_copy_log': {
        'tr': '🎨 {source} teması {target} içine kopyalandı',
        'en': '🎨 {source} theme copied into {target}',
        'de': '🎨 {source}-Thema in {target} kopiert',
        'fr': '🎨 Thème {source} copié dans {target}',
        'es': '🎨 Tema {source} copiado en {target}',
        'it': '🎨 Tema {source} copiato in {target}',
        'pt': '🎨 Tema {source} copiado para {target}',
        'ja': '🎨 {source} テーマを {target} にコピーしました',
        'zh': '🎨 已将 {source} 主题复制到 {target}',
        'ko': '🎨 {source} 테마가 {target}에 복사되었습니다'
    },
    'theme_label_fallback': {
        'tr': 'Tema', 'en': 'Theme', 'de': 'Thema', 'fr': 'Thème', 'es': 'Tema', 'it': 'Tema', 'pt': 'Tema', 'ja': 'テーマ', 'zh': '主题', 'ko': '테마'
    },
    'panel_theme': {
        'tr': 'TEMA SEÇ', 'en': 'SELECT THEME', 'de': 'THEMA WÄHLEN', 'fr': 'CHOISIR THÈME', 'es': 'ELEGIR TEMA', 'it': 'SCEGLI TEMA', 'pt': 'ESCOLHER TEMA', 'ja': 'テーマを選択', 'zh': '选择主题', 'ko': '테마 선택'
    },
    'panel_controls': {
        'tr': 'KONTROLLER', 'en': 'CONTROLS', 'de': 'STEUERUNG', 'fr': 'CONTRÔLES', 'es': 'CONTROLES', 'it': 'CONTROLLI', 'pt': 'CONTROLES', 'ja': 'コントロール', 'zh': '控制', 'ko': '컨트롤'
    },
    'panel_music': {
        'tr': 'MÜZİK AYARLARI', 'en': 'MUSIC SETTINGS', 'de': 'MUSIKEINSTELLUNGEN', 'fr': 'PARAMÈTRES MUSIQUE', 'es': 'AJUSTES DE MÚSICA', 'it': 'IMPOSTAZIONI MUSICA', 'pt': 'CONFIGURAÇÕES DE MÚSICA', 'ja': '音楽設定', 'zh': '音乐设置', 'ko': '음악 설정'
    },
    'panel_settings': {
        'tr': 'AYARLAR', 'en': 'SETTINGS', 'de': 'EINSTELLUNGEN', 'fr': 'PARAMÈTRES', 'es': 'AJUSTES', 'it': 'IMPOSTAZIONI', 'pt': 'CONFIGURAÇÕES', 'ja': '設定', 'zh': '设置', 'ko': '설정'
    },
    'settings_tab_game': {
        'tr': 'OYUN', 'en': 'GAME', 'ja': 'ゲーム', 'zh': '游戏', 'ko': '게임'
    },
    'settings_tab_display': {
        'tr': 'GÖRÜNTÜ', 'en': 'DISPLAY', 'ja': '表示', 'zh': '显示', 'ko': '디스플레이'
    },
    'settings_tab_audio': {
        'tr': 'SES', 'en': 'AUDIO', 'ja': '音声', 'zh': '音频', 'ko': '오디오'
    },
    'settings_tab_controls': {
        'tr': 'KONTROLLER', 'en': 'CONTROLS', 'ja': '操作', 'zh': '控制', 'ko': '컨트롤'
    },
    'settings_tab_customize': {
        'tr': 'ÖZELLEŞTİRME', 'en': 'CUSTOMIZE', 'ja': 'カスタマイズ', 'zh': '自定义', 'ko': '커스터마이즈'
    },
    'settings_tab_other': {
        'tr': 'DİĞER', 'en': 'OTHER', 'ja': 'その他', 'zh': '其他', 'ko': '기타'
    },
    'settings_section_gameplay': {
        'tr': 'OYNANIŞ', 'en': 'GAMEPLAY', 'ja': 'ゲームプレイ', 'zh': '游戏玩法', 'ko': '게임플레이'
    },
    'settings_section_screen': {
        'tr': 'EKRAN', 'en': 'SCREEN', 'ja': '画面', 'zh': '屏幕', 'ko': '화면'
    },
    'settings_section_visual': {
        'tr': 'GÖRSEL', 'en': 'VISUAL', 'ja': 'ビジュアル', 'zh': '视觉', 'ko': '비주얼'
    },
    'settings_section_music': {
        'tr': 'MÜZİK', 'en': 'MUSIC', 'ja': '音楽', 'zh': '音乐', 'ko': '음악'
    },
    'settings_section_sound_effects': {
        'tr': 'SES EFEKTLERİ', 'en': 'SOUND EFFECTS', 'ja': '効果音', 'zh': '音效', 'ko': '효과음'
    },
    'settings_section_general': {
        'tr': 'GENEL', 'en': 'GENERAL', 'ja': '一般', 'zh': '通用', 'ko': '일반'
    },
    'settings_section_mode_music': {
        'tr': 'MOD MÜZİKLERİ', 'en': 'MODE MUSIC', 'ja': 'モード音楽', 'zh': '模式音乐', 'ko': '모드 음악'
    },
    'settings_section_blocks': {
        'tr': 'BLOKLAR', 'en': 'BLOCKS', 'ja': 'ブロック', 'zh': '方块', 'ko': '블록'
    },
    'settings_section_system': {
        'tr': 'SİSTEM', 'en': 'SYSTEM', 'ja': 'システム', 'zh': '系统', 'ko': '시스템'
    },
    'settings_section_developer': {
        'tr': 'GELİŞTİRİCİ', 'en': 'DEVELOPER', 'ja': '開発者', 'zh': '开发者', 'ko': '개발자'
    },
    'settings_das_delay': {
        'tr': 'DAS Gecikmesi', 'en': 'DAS Delay', 'ja': 'DAS遅延', 'zh': 'DAS 延迟', 'ko': 'DAS 지연'
    },
    'settings_das_repeat': {
        'tr': 'DAS Tekrar', 'en': 'DAS Repeat', 'ja': 'DAS反復', 'zh': 'DAS 重复', 'ko': 'DAS 반복'
    },
    'settings_soft_drop_speed': {
        'tr': 'Yumuşak Düşme Hızı', 'en': 'Soft Drop Speed', 'ja': 'ソフトドロップ速度', 'zh': '软降速度', 'ko': '소프트 드롭 속도'
    },
    'panel_achievements': {
        'tr': 'BAŞARIMLAR', 'en': 'ACHIEVEMENTS', 'de': 'ERFOLGE', 'fr': 'SUCCÈS', 'es': 'LOGROS', 'it': 'TROFEI', 'pt': 'CONQUISTAS', 'ja': '実績', 'zh': '成就', 'ko': '업적'
    },
    
    # ==================== MÜZİK MOD GİRİŞLERİ ====================
    'music_campaign': {
        'tr': 'Görev Modu', 'en': 'Campaign Mode', 'de': 'Kampagnenmodus', 'fr': 'Mode Campagne', 'es': 'Modo Campaña', 'it': 'Modalità Campagna', 'pt': 'Modo Campanha', 'ja': 'キャンペーンモード', 'zh': '战役模式', 'ko': '캠페인 모드'
    },
    'music_classic': {
        'tr': 'Klasik (Tek Oyuncu)', 'en': 'Classic (Single Player)', 'de': 'Klassisch (Einzelspieler)', 'fr': 'Classique (Solo)', 'es': 'Clásico (Un Jugador)', 'it': 'Classico (Singolo)', 'pt': 'Clássico (Um Jogador)', 'ja': 'クラシック (シングル)', 'zh': '经典（单人）', 'ko': '클래식(싱글)'
    },
    'music_daily': {
        'tr': 'Daily Challenge', 'en': 'Daily Challenge', 'de': 'Tägliche Herausforderung', 'fr': 'Défi Quotidien', 'es': 'Desafío Diario', 'it': 'Sfida Giornaliera', 'pt': 'Desafio Diário', 'ja': 'デイリーチャレンジ', 'zh': '每日挑战', 'ko': '일일 도전'
    },
    'music_sprint': {
        'tr': 'Sprint Mode', 'en': 'Sprint Mode', 'de': 'Sprint-Modus', 'fr': 'Mode Sprint', 'es': 'Modo Sprint', 'it': 'Modalità Sprint', 'pt': 'Modo Sprint', 'ja': 'スプリントモード', 'zh': '冲刺模式', 'ko': '스프린트 모드'
    },
    'music_ultra': {
        'tr': 'Ultra Mode', 'en': 'Ultra Mode', 'de': 'Ultra-Modus', 'fr': 'Mode Ultra', 'es': 'Modo Ultra', 'it': 'Modalità Ultra', 'pt': 'Modo Ultra', 'ja': 'ウルトラモード', 'zh': '超强模式', 'ko': '울트라 모드'
    },
    'music_zen': {
        'tr': 'Zen Mode', 'en': 'Zen Mode', 'de': 'Zen-Modus', 'fr': 'Mode Zen', 'es': 'Modo Zen', 'it': 'Modalità Zen', 'pt': 'Modo Zen', 'ja': 'ゼンモード', 'zh': '禅模式', 'ko': '젠 모드'
    },
    'music_tetris2': {
        'tr': 'Quadrix Extra', 'en': 'Quadrix Extra', 'de': 'Quadrix Extra', 'fr': 'Quadrix Extra', 'es': 'Quadrix Extra', 'it': 'Quadrix Extra', 'pt': 'Quadrix Extra', 'ja': 'テトリスエクストラ', 'zh': '俄罗斯方块 额外', 'ko': '테트리스 엑스트라'
    },
    'music_mystery': {
        'tr': 'Kart Ustalığı', 'en': 'Card Mastery', 'de': 'Kartenmeisterschaft', 'fr': 'Maîtrise des Cartes', 'es': 'Maestría de Cartas', 'it': 'Maestria delle Carte', 'pt': 'Maestria de Cartas', 'ja': 'カードマスタリー', 'zh': '卡牌大师', 'ko': '카드 마스터리'
    },
    'music_wide': {
        'tr': 'Wide Mode', 'en': 'Wide Mode', 'de': 'Breiter Modus', 'fr': 'Mode Large', 'es': 'Modo Ancho', 'it': 'Modalità Larga', 'pt': 'Modo Largo', 'ja': 'ワイドモード', 'zh': '宽屏模式', 'ko': '와이드 모드'
    },
    'music_survival': {
        'tr': 'Survival Mode', 'en': 'Survival Mode', 'de': 'Überlebensmodus', 'fr': 'Mode Survie', 'es': 'Modo Supervivencia', 'it': 'Modalità Sopravvivenza', 'pt': 'Modo Sobrevivência', 'ja': 'サバイバルモード', 'zh': '生存模式', 'ko': '서바이벌 모드'
    },
    'music_cascade': {
        'tr': 'Cascade Mode', 'en': 'Cascade Mode', 'de': 'Kaskadenmodus', 'fr': 'Mode Cascade', 'es': 'Modo Cascada', 'it': 'Modalità Cascata', 'pt': 'Modo Cascata', 'ja': 'カスケードモード', 'zh': '级联模式', 'ko': '캐스케이드 모드'
    },
    'music_pvp': {
        'tr': 'LocalPvP (2 Oyuncu)', 'en': 'LocalPvP (2 Players)', 'de': 'LocalPvP (2 Spieler)', 'fr': 'PvP Local (2 Joueurs)', 'es': 'PvP Local (2 Jugadores)', 'it': 'PvP Locale (2 Giocatori)', 'pt': 'PvP Local (2 Jogadores)', 'ja': 'ローカルPvP (2人)', 'zh': '本地PvP（2人）', 'ko': '로컬 PvP(2인)'
    },
    
    # ==================== AYARLAR ETİKETLERİ ====================
    'setting_sound': {
        'tr': 'Ses', 'en': 'Sound', 'de': 'Ton', 'fr': 'Son', 'es': 'Sonido', 'it': 'Suono', 'pt': 'Som', 'ja': 'サウンド', 'zh': '声音', 'ko': '사운드'
    },
    'setting_effects': {
        'tr': 'Efektler', 'en': 'Effects', 'de': 'Effekte', 'fr': 'Effets', 'es': 'Efectos', 'it': 'Effetti', 'pt': 'Efeitos', 'ja': 'エフェクト', 'zh': '效果', 'ko': '효과'
    },
    'setting_difficulty': {
        'tr': 'Zorluk', 'en': 'Difficulty', 'de': 'Schwierigkeit', 'fr': 'Difficulté', 'es': 'Dificultad', 'it': 'Difficoltà', 'pt': 'Dificuldade', 'ja': '難易度', 'zh': '难度', 'ko': '난이도'
    },
    'setting_ghost': {
        'tr': 'Hayalet Parça', 'en': 'Ghost Piece', 'de': 'Geisterteil', 'fr': 'Pièce Fantôme', 'es': 'Pieza Fantasma', 'it': 'Pezzo Fantasma', 'pt': 'Peça Fantasma', 'ja': 'ゴーストピース', 'zh': '幽灵方块', 'ko': '고스트 피스'
    },
    'setting_music': {
        'tr': 'Müzik', 'en': 'Music', 'de': 'Musik', 'fr': 'Musique', 'es': 'Música', 'it': 'Musica', 'pt': 'Música', 'ja': '音楽', 'zh': '音乐', 'ko': '음악'
    },
    'setting_volume': {
        'tr': 'Ses Seviyesi', 'en': 'Volume', 'de': 'Lautstärke', 'fr': 'Volume', 'es': 'Volumen', 'it': 'Volume', 'pt': 'Volume', 'ja': '音量', 'zh': '音量', 'ko': '볼륨'
    },
    'setting_on': {
        'tr': 'Açık', 'en': 'On', 'de': 'An', 'fr': 'Activé', 'es': 'Activado', 'it': 'Attivo', 'pt': 'Ligado', 'ja': 'オン', 'zh': '开', 'ko': '켜짐'
    },
    'setting_off': {
        'tr': 'Kapalı', 'en': 'Off', 'de': 'Aus', 'fr': 'Désactivé', 'es': 'Desactivado', 'it': 'Disattivo', 'pt': 'Desligado', 'ja': 'オフ', 'zh': '关', 'ko': '꺼짐'
    },
    'diff_easy': {
        'tr': 'Kolay', 'en': 'Easy', 'de': 'Leicht', 'fr': 'Facile', 'es': 'Fácil', 'it': 'Facile', 'pt': 'Fácil', 'ja': 'イージー', 'zh': '简单', 'ko': '쉬움'
    },
    'diff_normal': {
        'tr': 'Normal', 'en': 'Normal', 'de': 'Normal', 'fr': 'Normal', 'es': 'Normal', 'it': 'Normale', 'pt': 'Normal', 'ja': 'ノーマル', 'zh': '普通', 'ko': '보통'
    },
    'diff_custom': {
        'tr': 'Özel', 'en': 'Custom', 'de': 'Benutzer', 'fr': 'Personnalisé', 'es': 'Personalizado', 'it': 'Personalizzato', 'pt': 'Personalizado', 'ja': 'カスタム', 'zh': '自定义', 'ko': '사용자 지정'
    },
    'diff_hard': {
        'tr': 'Zor', 'en': 'Hard', 'de': 'Schwer', 'fr': 'Difficile', 'es': 'Difícil', 'it': 'Difficile', 'pt': 'Difícil', 'ja': 'ハード', 'zh': '困难', 'ko': '어려움'
    },
    # ==================== PARÇA ETİKETLERİ ====================
    'piece_i': {
        'tr': 'I Parça', 'en': 'I Piece', 'de': 'I-Teil', 'fr': 'Pièce I', 'es': 'Pieza I', 'it': 'Pezzo I', 'pt': 'Peça I', 'ja': 'Iピース', 'zh': 'I 方块', 'ko': 'I 피스'
    },
    'piece_o': {
        'tr': 'O Parça', 'en': 'O Piece', 'de': 'O-Teil', 'fr': 'Pièce O', 'es': 'Pieza O', 'it': 'Pezzo O', 'pt': 'Peça O', 'ja': 'Oピース', 'zh': 'O 方块', 'ko': 'O 피스'
    },
    'piece_t': {
        'tr': 'T Parça', 'en': 'T Piece', 'de': 'T-Teil', 'fr': 'Pièce T', 'es': 'Pieza T', 'it': 'Pezzo T', 'pt': 'Peça T', 'ja': 'Tピース', 'zh': 'T 方块', 'ko': 'T 피스'
    },
    'piece_s': {
        'tr': 'S Parça', 'en': 'S Piece', 'de': 'S-Teil', 'fr': 'Pièce S', 'es': 'Pieza S', 'it': 'Pezzo S', 'pt': 'Peça S', 'ja': 'Sピース', 'zh': 'S 方块', 'ko': 'S 피스'
    },
    'piece_z': {
        'tr': 'Z Parça', 'en': 'Z Piece', 'de': 'Z-Teil', 'fr': 'Pièce Z', 'es': 'Pieza Z', 'it': 'Pezzo Z', 'pt': 'Peça Z', 'ja': 'Zピース', 'zh': 'Z 方块', 'ko': 'Z 피스'
    },
    'piece_j': {
        'tr': 'J Parça', 'en': 'J Piece', 'de': 'J-Teil', 'fr': 'Pièce J', 'es': 'Pieza J', 'it': 'Pezzo J', 'pt': 'Peça J', 'ja': 'Jピース', 'zh': 'J 方块', 'ko': 'J 피스'
    },
    'piece_l': {
        'tr': 'L Parça', 'en': 'L Piece', 'de': 'L-Teil', 'fr': 'Pièce L', 'es': 'Pieza L', 'it': 'Pezzo L', 'pt': 'Peça L', 'ja': 'Lピース', 'zh': 'L 方块', 'ko': 'L 피스'
    },
    
    # ==================== BUTON VE İŞLEM ETİKETLERİ ====================
    'btn_play': {
        'tr': 'OYNA', 'en': 'PLAY', 'de': 'SPIELEN', 'fr': 'JOUER', 'es': 'JUGAR', 'it': 'GIOCA', 'pt': 'JOGAR', 'ja': 'プレイ', 'zh': '开始', 'ko': '플레이'
    },
    'btn_back': {
        'tr': 'GERİ', 'en': 'BACK', 'de': 'ZURÜCK', 'fr': 'RETOUR', 'es': 'VOLVER', 'it': 'INDIETRO', 'pt': 'VOLTAR', 'ja': '戻る', 'zh': '返回', 'ko': '뒤로'
    },
    'btn_save': {
        'tr': 'KAYDET', 'en': 'SAVE', 'de': 'SPEICHERN', 'fr': 'SAUVER', 'es': 'GUARDAR', 'it': 'SALVA', 'pt': 'SALVAR', 'ja': '保存', 'zh': '保存', 'ko': '저장'
    },
    'btn_cancel': {
        'tr': 'İPTAL', 'en': 'CANCEL', 'de': 'ABBRECHEN', 'fr': 'ANNULER', 'es': 'CANCELAR', 'it': 'ANNULLA', 'pt': 'CANCELAR', 'ja': 'キャンセル', 'zh': '取消', 'ko': '취소'
    },
    'btn_reset': {
        'tr': 'SIFIRLA', 'en': 'RESET', 'de': 'ZURÜCKSETZEN', 'fr': 'RÉINITIALISER', 'es': 'REINICIAR', 'it': 'RIPRISTINA', 'pt': 'REDEFINIR', 'ja': 'リセット', 'zh': '重置', 'ko': '초기화'
    },
    'btn_apply': {
        'tr': 'UYGULA', 'en': 'APPLY', 'de': 'ANWENDEN', 'fr': 'APPLIQUER', 'es': 'APLICAR', 'it': 'APPLICA', 'pt': 'APLICAR', 'ja': '適用', 'zh': '应用', 'ko': '적용'
    },
    'btn_exit': {
        'tr': 'ÇIKIŞ', 'en': 'EXIT', 'de': 'BEENDEN', 'fr': 'QUITTER', 'es': 'SALIR', 'it': 'ESCI', 'pt': 'SAIR', 'ja': '終了', 'zh': '退出', 'ko': '나가기'
    },
    'btn_continue': {
        'tr': 'DEVAM', 'en': 'CONTINUE', 'de': 'WEITER', 'fr': 'CONTINUER', 'es': 'CONTINUAR', 'it': 'CONTINUA', 'pt': 'CONTINUAR', 'ja': '続ける', 'zh': '继续', 'ko': '계속'
    },
    'btn_restart': {
        'tr': 'YENİDEN BAŞLA', 'en': 'RESTART', 'de': 'NEU STARTEN', 'fr': 'RECOMMENCER', 'es': 'REINICIAR', 'it': 'RICOMINCIA', 'pt': 'RECOMEÇAR', 'ja': '再スタート', 'zh': '重新开始', 'ko': '재시작'
    },
    'press_key': {
        'tr': 'Bir tuşa basın...', 'en': 'Press a key...', 'de': 'Taste drücken...', 'fr': 'Appuyez sur une touche...', 'es': 'Presiona una tecla...', 'it': 'Premi un tasto...', 'pt': 'Pressione uma tecla...', 'ja': 'キーを押してください...', 'zh': '请按任意键...', 'ko': '아무 키나 누르세요...'
    },
    'no_scores': {
        'tr': 'Henüz skor yok', 'en': 'No scores yet', 'de': 'Noch keine Punkte', 'fr': 'Pas encore de scores', 'es': 'Sin puntuaciones aún', 'it': 'Nessun punteggio ancora', 'pt': 'Nenhuma pontuação ainda', 'ja': 'スコアはまだありません', 'zh': '暂无得分', 'ko': '점수 없음'
    },
    'active': {
        'tr': 'Aktif', 'en': 'Active', 'de': 'Aktiv', 'fr': 'Actif', 'es': 'Activo', 'it': 'Attivo', 'pt': 'Ativo', 'ja': '有効', 'zh': '激活', 'ko': '활성'
    },
    
    # ==================== MOD SKİN BAŞLIKLARI ====================
    'skin_classic_title': {
        'tr': 'KLASİK MOD', 'en': 'CLASSIC MODE', 'de': 'KLASSISCHER MODUS', 'fr': 'MODE CLASSIQUE', 'es': 'MODO CLÁSICO', 'it': 'MODALITÀ CLASSICA', 'pt': 'MODO CLÁSSICO', 'ja': 'クラシックモード', 'zh': '经典模式', 'ko': '클래식 모드'
    },
    'skin_classic_subtitle': {
        'tr': 'Tek oyunculu neon tahta', 'en': 'Neon board for single player', 'de': 'Neon-Brett für Einzelspieler', 'fr': 'Plateau néon pour un joueur', 'es': 'Tablero neón para un jugador', 'it': 'Tavola neon per giocatore singolo', 'pt': 'Tabuleiro neon para um jogador', 'ja': 'シングル用ネオンボード', 'zh': '单人霓虹棋盘', 'ko': '싱글용 네온 보드'
    },
    'skin_tutorial_title': {
        'tr': 'EĞİTİM', 'en': 'TUTORIAL', 'de': 'TUTORIAL', 'fr': 'TUTORIEL', 'es': 'TUTORIAL', 'it': 'TUTORIAL', 'pt': 'TUTORIAL', 'ja': 'チュートリアル', 'zh': '教程', 'ko': '튜토리얼'
    },
    'skin_tutorial_subtitle': {
        'tr': 'Adım adım öğrenme modu', 'en': 'Step-by-step learning mode', 'de': 'Schritt-für-Schritt-Lernmodus', 'fr': 'Mode d’apprentissage pas à pas', 'es': 'Modo de aprendizaje paso a paso', 'it': 'Modalità di apprendimento passo dopo passo', 'pt': 'Modo de aprendizado passo a passo', 'ja': 'ステップごとの学習モード', 'zh': '循序渐进学习模式', 'ko': '단계별 학습 모드'
    },
    'skin_sprint_title': {
        'tr': 'SPRINT RUSH', 'en': 'SPRINT RUSH', 'de': 'SPRINT RUSH', 'fr': 'SPRINT RUSH', 'es': 'SPRINT RUSH', 'it': 'SPRINT RUSH', 'pt': 'SPRINT RUSH', 'ja': 'スプリントラッシュ', 'zh': '冲刺疾速', 'ko': '스프린트 러시'
    },
    'skin_sprint_subtitle': {
        'tr': '40 satırı hızla bitir!', 'en': 'Clear 40 lines fast!', 'de': '40 Zeilen schnell räumen!', 'fr': 'Efface 40 lignes rapidement!', 'es': '¡Limpia 40 líneas rápido!', 'it': 'Cancella 40 righe velocemente!', 'pt': 'Limpe 40 linhas rápido!', 'ja': '40ラインを素早くクリア！', 'zh': '快速清除40行！', 'ko': '40줄을 빠르게 클리어!'
    },
    'skin_ultra_title': {
        'tr': 'ULTRA BLITZ', 'en': 'ULTRA BLITZ', 'de': 'ULTRA BLITZ', 'fr': 'ULTRA BLITZ', 'es': 'ULTRA BLITZ', 'it': 'ULTRA BLITZ', 'pt': 'ULTRA BLITZ', 'ja': 'ウルトラブリッツ', 'zh': '超强闪击', 'ko': '울트라 블리츠'
    },
    'skin_ultra_subtitle': {
        'tr': '2 dakika – maksimum skor', 'en': '2 minutes – max score', 'de': '2 Minuten – maximale Punkte', 'fr': '2 minutes – score max', 'es': '2 minutos – puntuación máxima', 'it': '2 minuti – punteggio massimo', 'pt': '2 minutos – pontuação máxima', 'ja': '2分で最大スコア', 'zh': '2分钟——最高分', 'ko': '2분 – 최고 점수'
    },
    'skin_zen_title': {
        'tr': 'ZEN GARDEN', 'en': 'ZEN GARDEN', 'de': 'ZEN GARTEN', 'fr': 'JARDIN ZEN', 'es': 'JARDÍN ZEN', 'it': 'GIARDINO ZEN', 'pt': 'JARDIM ZEN', 'ja': '禅の庭', 'zh': '禅之庭', 'ko': '젠 가든'
    },
    'skin_zen_subtitle': {
        'tr': 'Sonsuz rahatlama modu', 'en': 'Endless relaxation mode', 'de': 'Endloser Entspannungsmodus', 'fr': 'Mode détente infini', 'es': 'Modo relajación infinita', 'it': 'Modalità relax infinita', 'pt': 'Modo relaxamento infinito', 'ja': '無限リラックスモード', 'zh': '无限放松模式', 'ko': '무한 휴식 모드'
    },
    'skin_tetris2_title': {
        'tr': 'QUADRIX EXTRA', 'en': 'QUADRIX EXTRA', 'de': 'QUADRIX EXTRA', 'fr': 'QUADRIX EXTRA', 'es': 'QUADRIX EXTRA', 'it': 'QUADRIX EXTRA', 'pt': 'QUADRIX EXTRA', 'ja': 'テトリスエクストラ', 'zh': 'QUADRIX EXTRA', 'ko': '테트리스 엑스트라'
    },
    'skin_tetris2_subtitle': {
        'tr': 'Ekstra parçalar, ekstra kaos', 'en': 'Extra pieces, extra chaos', 'de': 'Extra Teile, extra Chaos', 'fr': 'Pièces en plus, chaos en plus', 'es': 'Piezas extra, caos extra', 'it': 'Pezzi extra, caos extra', 'pt': 'Peças extras, caos extra', 'ja': '追加ピース、追加カオス', 'zh': '额外方块，额外混乱', 'ko': '추가 피스, 추가 카오스'
    },
    'skin_mystery_title': {
        'tr': 'KART USTALIĞI', 'en': 'CARD MASTERY', 'de': 'KARTENMEISTERSCHAFT', 'fr': 'MAÎTRISE DES CARTES', 'es': 'MAESTRÍA DE CARTAS', 'it': 'MAESTRIA CARTE', 'pt': 'MAESTRIA DE CARTAS', 'ja': 'カードマスタリー', 'zh': '卡牌大师', 'ko': '카드 마스터리'
    },
    'skin_mystery_subtitle': {
        'tr': 'Her kart yeni sürpriz', 'en': 'Each card brings surprise', 'de': 'Jede Karte bringt Überraschung', 'fr': 'Chaque carte apporte surprise', 'es': 'Cada carta trae sorpresa', 'it': 'Ogni carta porta sorpresa', 'pt': 'Cada carta traz surpresa', 'ja': 'カードごとに新しい驚き', 'zh': '每张卡都有新惊喜', 'ko': '카드마다 새로운 놀라움'
    },
    'skin_wide_title': {
        'tr': 'WIDE ARENA', 'en': 'WIDE ARENA', 'de': 'BREITE ARENA', 'fr': 'ARÈNE LARGE', 'es': 'ARENA ANCHA', 'it': 'ARENA LARGA', 'pt': 'ARENA LARGA', 'ja': 'ワイドアリーナ', 'zh': '宽屏竞技场', 'ko': '와이드 아레나'
    },
    'skin_wide_subtitle': {
        'tr': '15 sütun geniş aksiyon', 'en': '15 columns wide action', 'de': '15 Spalten breite Aktion', 'fr': 'Action sur 15 colonnes', 'es': 'Acción en 15 columnas', 'it': 'Azione su 15 colonne', 'pt': 'Ação em 15 colunas', 'ja': '15列のワイドアクション', 'zh': '15列宽的动作', 'ko': '15열 와이드 액션'
    },
    'skin_survival_title': {
        'tr': 'SURVIVAL ALERT', 'en': 'SURVIVAL ALERT', 'de': 'ÜBERLEBENSALARM', 'fr': 'ALERTE SURVIE', 'es': 'ALERTA SUPERVIVENCIA', 'it': 'ALLERTA SOPRAVVIVENZA', 'pt': 'ALERTA SOBREVIVÊNCIA', 'ja': 'サバイバルアラート', 'zh': '生存警报', 'ko': '서바이벌 알림'
    },
    'skin_survival_subtitle': {
        'tr': 'Canını koru, hızlan!', 'en': 'Protect your lives, speed up!', 'de': 'Schütze dein Leben, beschleunige!', 'fr': 'Protège tes vies, accélère!', 'es': '¡Protege tus vidas, acelera!', 'it': 'Proteggi le tue vite, accelera!', 'pt': 'Proteja suas vidas, acelere!', 'ja': 'ライフを守り、加速せよ！', 'zh': '守住生命，提速！', 'ko': '목숨을 지켜라, 가속하라!'
    },
    'skin_cascade_title': {
        'tr': 'CASCADE WAVE', 'en': 'CASCADE WAVE', 'de': 'KASKADENWELLE', 'fr': 'VAGUE CASCADE', 'es': 'OLA EN CASCADA', 'it': 'ONDA A CASCATA', 'pt': 'ONDA EM CASCATA', 'ja': 'カスケードウェーブ', 'zh': '级联波浪', 'ko': '캐스케이드 웨이브'
    },
    'skin_cascade_subtitle': {
        'tr': 'Zincirleme satır patlamaları', 'en': 'Chain line explosions', 'de': 'Kettenlinien-Explosionen', 'fr': 'Explosions en chaîne', 'es': 'Explosiones en cadena', 'it': 'Esplosioni a catena', 'pt': 'Explosões em cadeia', 'ja': '連鎖ライン爆発', 'zh': '连锁行爆炸', 'ko': '연쇄 라인 폭발'
    },
    'skin_daily_title': {
        'tr': 'DAILY MISSION', 'en': 'DAILY MISSION', 'de': 'TÄGLICHE MISSION', 'fr': 'MISSION QUOTIDIENNE', 'es': 'MISIÓN DIARIA', 'it': 'MISSIONE GIORNALIERA', 'pt': 'MISSÃO DIÁRIA', 'ja': 'DAILY MISSION', 'zh': '每日任务', 'ko': '일일 미션'
    },
    'skin_daily_subtitle': {
        'tr': 'Günün meydan okuması', 'en': "Today's challenge", 'de': 'Heutige Herausforderung', 'fr': 'Défi du jour', 'es': 'Desafío del día', 'it': 'Sfida del giorno', 'pt': 'Desafio do dia', 'ja': '本日のチャレンジ', 'zh': '今日挑战', 'ko': '오늘의 도전'
    },
    'skin_pvp_title': {
        'tr': 'PVP ARENA', 'en': 'PVP ARENA', 'de': 'PVP ARENA', 'fr': 'ARÈNE PVP', 'es': 'ARENA PVP', 'it': 'ARENA PVP', 'pt': 'ARENA PVP', 'ja': 'PVP ARENA', 'zh': 'PVP 竞技场', 'ko': 'PVP 아레나'
    },
    'skin_pvp_subtitle': {
        'tr': 'Karşılıklı retro düello', 'en': 'Head-to-head retro duel', 'de': 'Retro-Duell gegeneinander', 'fr': 'Duel rétro face à face', 'es': 'Duelo retro cara a cara', 'it': 'Duello retro faccia a faccia', 'pt': 'Duelo retro cara a cara', 'ja': '対戦レトロデュエル', 'zh': '面对面的复古对决', 'ko': '정면 승부 레트로 듀얼'
    },
    
    # ==================== EXTRAS MENÜ MOD AÇIKLAMALARI ====================
    'extras_sprint_desc': {
        'tr': '40 satırı en hızlı sürede temizle.', 'en': 'Clear 40 lines as fast as possible.', 'de': 'Lösche 40 Zeilen so schnell wie möglich.', 'fr': 'Efface 40 lignes le plus vite possible.', 'es': 'Limpia 40 líneas lo más rápido posible.', 'it': 'Cancella 40 righe il più velocemente possibile.', 'pt': 'Limpe 40 linhas o mais rápido possível.', 'ja': '40ラインを最速で消そう。', 'zh': '以最快速度清除40行。', 'ko': '40줄을 최대한 빨리 지우세요.'
    },
    'mode_intro_classic_desc': {
        'tr': 'Herkesin bildiği Quadrix oyunu.\nSonsuz bir şekilde blokları yerleştirin ve satırları temizleyin.',
        'en': 'The classic Quadrix everyone knows.\nPlace blocks endlessly and clear lines.',
        'de': 'Der klassische Quadrix, den jeder kennt.\nPlatziere endlos Blöcke und lösche Linien.',
        'fr': 'Le Quadrix classique que tout le monde connaît.\nPlace des blocs sans fin et efface des lignes.',
        'es': 'El Quadrix clásico que todos conocen.\nColoca bloques sin fin y limpia líneas.',
        'it': 'Il classico Quadrix che tutti conoscono.\nPosiziona blocchi senza fine e cancella le linee.',
        'pt': 'O Quadrix clássico que todos conhecem.\nColoque blocos sem parar e limpe linhas.',
        'ja': '誰もが知るクラシックテトリス。\nブロックを置き続けてラインを消そう。',
        'zh': '人人皆知的经典俄罗斯方块。\n不断放置方块并清除行。',
        'ko': '모두가 아는 클래식 테트리스.\n블록을 끝없이 놓고 줄을 지우세요.'
    },
    'mode_intro_sprint_desc': {
        'tr': 'Zamana karşı bir yarış!\nHedefin en kısa sürede 40 satır temizlemek.',
        'en': 'A race against time!\nYour goal is to clear 40 lines as fast as possible.',
        'de': 'Ein Rennen gegen die Zeit!\nDein Ziel: 40 Linien so schnell wie möglich löschen.',
        'fr': 'Une course contre la montre !\nTon objectif : effacer 40 lignes le plus vite possible.',
        'es': '¡Una carrera contra el tiempo!\nTu objetivo es limpiar 40 líneas lo más rápido posible.',
        'it': 'Una gara contro il tempo!\nIl tuo obiettivo è cancellare 40 linee il più velocemente possibile.',
        'pt': 'Uma corrida contra o tempo!\nSeu objetivo é limpar 40 linhas o mais rápido possível.',
        'ja': '時間との勝負！\n40ラインを最速で消すのが目標。',
        'zh': '与时间赛跑！\n目标是在最短时间内清除40行。',
        'ko': '시간과의 경주!\n목표는 가장 빠르게 40줄을 지우는 것.'
    },
    'mode_intro_ultra_desc': {
        'tr': 'Kısıtlı zaman, maksimum puan!\nSadece 2 dakikan var; bu sürede en yüksek skoru hedefle.',
        'en': 'Limited time, maximum score!\nYou have only 2 minutes to reach the highest score.',
        'de': 'Begrenzte Zeit, maximale Punkte!\nDu hast nur 2 Minuten für die Höchstpunktzahl.',
        'fr': 'Temps limité, score maximal !\nTu n’as que 2 minutes pour viser le meilleur score.',
        'es': '¡Tiempo limitado, máxima puntuación!\nSolo tienes 2 minutos para lograr el mejor puntaje.',
        'it': 'Tempo limitato, punteggio massimo!\nHai solo 2 minuti per ottenere il punteggio migliore.',
        'pt': 'Tempo limitado, pontuação máxima!\nVocê tem apenas 2 minutos para alcançar a maior pontuação.',
        'ja': '制限時間で最高スコア！\n2分で最大スコアを目指そう。',
        'zh': '时间有限，最高得分！\n你只有2分钟，目标是最高分。',
        'ko': '제한된 시간, 최대 점수!\n2분 안에 최고 점수를 노리세요.'
    },
    'mode_intro_survival_desc': {
        'tr': 'Virüsler tahtayı işgal ediyor ve yayılıyor.\nSatır temizleyerek antivirüsü doldur ve hayatta kal.',
        'en': 'Viruses invade and spread on the board.\nClear lines to charge the antivirus and survive.',
        'de': 'Viren dringen ein und breiten sich aus.\nLösche Linien, lade den Antivirus auf und überlebe.',
        'fr': 'Des virus envahissent et se propagent.\nEfface des lignes pour charger l’antivirus et survivre.',
        'es': 'Los virus invaden y se expanden.\nLimpia líneas para cargar el antivirus y sobrevivir.',
        'it': 'I virus invadono e si diffondono.\nCancella linee per caricare l’antivirus e sopravvivere.',
        'pt': 'Vírus invadem e se espalham.\nLimpe linhas para carregar o antivírus e sobreviver.',
        'ja': 'ウイルスが侵入し広がる。\nラインを消して対ウイルスをチャージし、生き残れ。',
        'zh': '病毒入侵并在棋盘上蔓延。\n清除行来为抗病毒充能并生存。',
        'ko': '바이러스가 보드를 침입해 퍼집니다.\n줄을 지워 백신을 충전하고 살아남으세요.'
    },
    'mode_intro_cascade_desc': {
        'tr': 'Yerçekimi kuralları değişti!\nTemizlenen satırların üzerindeki bloklar aşağı düşer.',
        'en': 'Gravity rules have changed!\nBlocks above cleared lines fall down.',
        'de': 'Die Schwerkraftregeln haben sich geändert!\nBlöcke über gelöschten Linien fallen herunter.',
        'fr': 'Les règles de gravité ont changé !\nLes blocs au-dessus des lignes effacées tombent.',
        'es': '¡Las reglas de gravedad cambiaron!\nLos bloques sobre líneas limpiadas caen.',
        'it': 'Le regole della gravità sono cambiate!\nI blocchi sopra le linee cancellate cadono.',
        'pt': 'As regras de gravidade mudaram!\nBlocos acima de linhas limpas caem.',
        'ja': '重力ルールが変化！\n消したラインの上のブロックが落ちる。',
        'zh': '重力规则改变了！\n清除行上方的方块会下落。',
        'ko': '중력 규칙이 바뀌었습니다!\n지운 줄 위의 블록이 아래로 떨어집니다.'
    },
    'mode_intro_zen_desc': {
        'tr': 'Stres yok, süre yok.\nRahatla ve yerleştirmeye odaklan.',
        'en': 'No stress, no time limit.\nRelax and focus on placement.',
        'de': 'Kein Stress, keine Zeitbegrenzung.\nEntspann dich und fokussiere dich aufs Platzieren.',
        'fr': 'Pas de stress, pas de limite de temps.\nDétends-toi et concentre-toi sur le placement.',
        'es': 'Sin estrés, sin límite de tiempo.\nRelájate y concéntrate en colocar.',
        'it': 'Niente stress, niente limite di tempo.\nRilassati e concentrati sul posizionamento.',
        'pt': 'Sem estresse, sem limite de tempo.\nRelaxe e foque no posicionamento.',
        'ja': 'ストレスなし、制限時間なし。\nリラックスして配置に集中。',
        'zh': '没有压力，没有时间限制。\n放松并专注于摆放。',
        'ko': '스트레스 없이, 시간 제한 없이.\n편하게 놓기에 집중하세요.'
    },
    'mode_intro_mystery_desc': {
        'tr': 'Quadrix’e yeni bir boyut.\nÖzel kartlarla oyunu manipüle et.',
        'en': 'A new dimension for Quadrix.\nUse special cards to manipulate the game.',
        'de': 'Eine neue Dimension für Quadrix.\nNutze Spezialkarten, um das Spiel zu beeinflussen.',
        'fr': 'Une nouvelle dimension pour Quadrix.\nUtilise des cartes spéciales pour manipuler la partie.',
        'es': 'Una nueva dimensión para Quadrix.\nUsa cartas especiales para manipular el juego.',
        'it': 'Una nuova dimensione per Quadrix.\nUsa carte speciali per manipolare il gioco.',
        'pt': 'Uma nova dimensão para Quadrix.\nUse cartas especiais para manipular o jogo.',
        'ja': 'テトリスに新次元。\n特殊カードでゲームを操ろう。',
        'zh': '为俄罗斯方块带来新维度。\n用特殊卡牌操控游戏。',
        'ko': '테트리스에 새로운 차원.\n특수 카드로 게임을 조작하세요.'
    },
    'mode_intro_wide_desc': {
        'tr': 'Daha geniş bir oyun alanı.\nDaha fazla alan, daha büyük stratejiler.',
        'en': 'A wider playfield.\nMore space, bigger strategies.',
        'de': 'Ein breiteres Spielfeld.\nMehr Platz, größere Strategien.',
        'fr': 'Un plateau plus large.\nPlus d’espace, de plus grandes stratégies.',
        'es': 'Un campo más ancho.\nMás espacio, estrategias más grandes.',
        'it': 'Un campo più ampio.\nPiù spazio, strategie più grandi.',
        'pt': 'Um campo mais amplo.\nMais espaço, estratégias maiores.',
        'ja': 'より広いフィールド。\n広さで戦略も大きく。',
        'zh': '更宽的场地。\n更多空间，更大策略。',
        'ko': '더 넓은 플레이필드.\n더 많은 공간, 더 큰 전략.'
    },
    'mode_intro_tetris2_desc': {
        'tr': 'Yeni parçaları dene!\nEkstra bloklarla yeni kombinasyonlar keşfet.',
        'en': 'Try new pieces!\nDiscover new combos with extra blocks.',
        'de': 'Probiere neue Teile!\nEntdecke neue Kombos mit Extra-Blöcken.',
        'fr': 'Essaie de nouvelles pièces !\nDécouvre de nouvelles combos avec des blocs extras.',
        'es': '¡Prueba nuevas piezas!\nDescubre nuevos combos con bloques extra.',
        'it': 'Prova nuovi pezzi!\nScopri nuove combo con blocchi extra.',
        'pt': 'Experimente novas peças!\nDescubra novas combinações com blocos extras.',
        'ja': '新しいピースを試そう！\n追加ブロックで新しいコンボを発見。',
        'zh': '尝试新方块！\n用额外方块发现新连击。',
        'ko': '새로운 피스를 시험해 보세요!\n추가 블록으로 새로운 콤보를 발견하세요.'
    },
    'mode_intro_pvp_desc': {
        'tr': 'Arkadaşına meydan oku.\nAynı ekranda iki kişilik mücadele.',
        'en': 'Challenge a friend.\nTwo-player battle on the same screen.',
        'de': 'Fordere einen Freund heraus.\nZweispieler-Duell auf demselben Bildschirm.',
        'fr': 'Défie un ami.\nDuel à deux sur le même écran.',
        'es': 'Desafía a un amigo.\nDuelo de dos jugadores en la misma pantalla.',
        'it': 'Sfida un amico.\nDuello a due sullo stesso schermo.',
        'pt': 'Desafie um amigo.\nDuelo de dois jogadores na mesma tela.',
        'ja': '友達に挑戦。\n同じ画面で2人対戦。',
        'zh': '挑战朋友。\n同屏双人对战。',
        'ko': '친구에게 도전하세요.\n같은 화면에서 2인 대결.'
    },
    'mode_intro_hardcore_desc': {
        'tr': 'Sıradaki parçalar gizli, saklama yok, kontroller ters.\nSadece gerçek ustalar için!',
        'en': 'Next pieces hidden, no hold, inverted controls.\nOnly for true masters!',
        'de': 'Nächste Teile verborgen, kein Halten, umgekehrte Steuerung.\nNur für echte Meister!',
        'fr': 'Pièces suivantes cachées, pas de réserve, contrôles inversés.\nSeulement pour les vrais maîtres !',
        'es': 'Piezas siguientes ocultas, sin guardar, controles invertidos.\n¡Solo para verdaderos maestros!',
        'it': 'Pezzi successivi nascosti, niente hold, controlli invertiti.\nSolo per veri maestri!',
        'pt': 'Próximas peças ocultas, sem hold, controles invertidos.\nSó para verdadeiros mestres!',
        'ja': '次ピース非表示、ホールドなし、操作反転。\n真の達人向け！',
        'zh': '下一块隐藏、无保留、反向控制。\n仅献给真正大师！',
        'ko': '다음 피스 숨김, 홀드 없음, 조작 반전.\n진정한 고수만을 위한 모드!'
    },
    'extras_ultra_desc': {
        'tr': '2 dakikada maksimum skor.', 'en': 'Maximum score in 2 minutes.', 'de': 'Maximale Punkte in 2 Minuten.', 'fr': 'Score maximum en 2 minutes.', 'es': 'Puntuación máxima en 2 minutos.', 'it': 'Punteggio massimo in 2 minuti.', 'pt': 'Pontuação máxima em 2 minutos.', 'ja': '2分で最大スコア。', 'zh': '2分钟内最高得分。', 'ko': '2분 안에 최고 점수.'
    },
    'extras_zen_desc': {
        'tr': 'Stres yok, süre yok. Rahat oyna.', 'en': 'No stress, no time limit. Play relaxed.', 'de': 'Kein Stress, keine Zeitbegrenzung. Entspannt spielen.', 'fr': 'Pas de stress, pas de limite de temps. Joue détendu.', 'es': 'Sin estrés, sin límite de tiempo. Juega relajado.', 'it': 'Niente stress, niente limite di tempo. Gioca rilassato.', 'pt': 'Sem estresse, sem limite de tempo. Jogue relaxado.', 'ja': 'ストレスなし、時間制限なし。気楽にプレイ。', 'zh': '无压力，无时间限制。轻松玩。', 'ko': '스트레스 없이, 시간 제한 없이. 편하게 플레이하세요.'
    },
    'extras_tetris2_desc': {
        'tr': 'Ekstra parçalarla yeni kombinasyonlar.', 'en': 'New combinations with extra pieces.', 'de': 'Neue Kombinationen mit extra Teilen.', 'fr': 'Nouvelles combinaisons avec pièces extras.', 'es': 'Nuevas combinaciones con piezas extra.', 'it': 'Nuove combinazioni con pezzi extra.', 'pt': 'Novas combinações com peças extras.', 'ja': '追加ピースで新しいコンボ。', 'zh': '用额外方块的新组合。', 'ko': '추가 피스로 새로운 조합.'
    },
    'extras_mystery_desc': {
        'tr': 'Yeni nesil!!', 'en': 'Next generation!!', 'de': 'Nächste Generation!!', 'fr': 'Nouvelle génération!!', 'es': '¡¡Nueva generación!!', 'it': 'Nuova generazione!!', 'pt': 'Nova geração!!', 'ja': '次世代!!', 'zh': '新世代！！', 'ko': '차세대!!'
    },
    'extras_wide_desc': {
        'tr': '15x23 geniş tahta, tadını çıkar.', 'en': '15x23 wide board, enjoy it.', 'de': '15x23 breites Brett, genieße es.', 'fr': 'Plateau large 15x23, profite.', 'es': 'Tablero ancho 15x23, disfrútalo.', 'it': 'Tavola larga 15x23, divertiti.', 'pt': 'Tabuleiro largo 15x23, aproveite.', 'ja': '15x23の広いボードを楽しもう。', 'zh': '15x23 宽棋盘，尽情享受。', 'ko': '15x23 와이드 보드, 즐겨요.'
    },
    'extras_survival_desc': {
        'tr': 'Baskı artar, hatalar affetmez', 'en': 'Pressure rises, mistakes are costly', 'de': 'Druck steigt, Fehler kosten', 'fr': 'La pression monte, les erreurs coûtent', 'es': 'La presión aumenta, los errores cuestan', 'it': 'La pressione aumenta, gli errori costano', 'pt': 'A pressão aumenta, erros custam caro', 'ja': 'プレッシャー増大、ミスは致命的。', 'zh': '压力上升，失误代价高', 'ko': '압박이 올라가고 실수는 치명적'
    },
    'extras_cascade_desc': {
        'tr': 'Yerçekimiyle bloklar olduğu yere düşer.', 'en': 'Blocks fall with gravity.', 'de': 'Blöcke fallen mit Schwerkraft.', 'fr': 'Les blocs tombent avec la gravité.', 'es': 'Los bloques caen con la gravedad.', 'it': 'I blocchi cadono con la gravità.', 'pt': 'Blocos caem com a gravidade.', 'ja': '重力でブロックが落ちる。', 'zh': '方块会受重力下落。', 'ko': '블록이 중력에 의해 떨어집니다.'
    },
    'extras_hardcore_desc': {
        'tr': 'Sıradakiler gizli, saklama yok, kontroller ters!', 'en': 'Next pieces hidden, no hold, inverted controls!', 'de': 'Nächste Teile versteckt, kein Halten, umgekehrte Steuerung!', 'fr': 'Pièces suivantes cachées, pas de réserve, contrôles inversés!', 'es': '¡Piezas siguientes ocultas, sin guardar, controles invertidos!', 'it': 'Pezzi successivi nascosti, nessuna riserva, controlli invertiti!', 'pt': 'Próximas peças ocultas, sem guardar, controles invertidos!', 'ja': '次ピース非表示、ホールドなし、操作反転！', 'zh': '下一块隐藏、无保留、反向控制！', 'ko': '다음 피스 숨김, 홀드 없음, 조작 반전!'
    },
    
    # Zen Mode otomatik temizlik seçici
    'zen_auto_clear_title': {
        'tr': 'OTOMATİK TEMİZLİK AYARI', 'en': 'AUTO CLEAR SETTINGS', 'de': 'AUTO-LÖSCH EINSTELLUNGEN', 'fr': 'PARAMÈTRES DE NETTOYAGE AUTO', 'es': 'AJUSTES DE LIMPIEZA AUTO', 'it': 'IMPOSTAZIONI PULIZIA AUTO', 'pt': 'CONFIGURAÇÕES DE LIMPEZA AUTO', 'ja': '自動消去設定', 'zh': '自动清除设置', 'ko': '자동 클리어 설정'
    },
    'zen_auto_clear_desc': {
        'tr': 'Tahta dolduğunda kaç satır temizlensin?', 'en': 'How many rows to clear when board fills?', 'de': 'Wie viele Reihen löschen wenn Brett voll?', 'fr': 'Combien de lignes effacer quand le plateau est plein?', 'es': '¿Cuántas filas limpiar cuando el tablero se llena?', 'it': 'Quante righe cancellare quando il tavolo è pieno?', 'pt': 'Quantas linhas limpar quando o tabuleiro encher?', 'ja': '盤面が埋まったら何行消しますか？', 'zh': '棋盘满时清除多少行？', 'ko': '보드가 가득 찼을 때 몇 줄을 지울까요?'
    },
    'extras_title': {
        'tr': 'OYUN MODLARI', 'en': 'GAME MODES', 'de': 'SPIELMODI', 'fr': 'MODES DE JEU', 'es': 'MODOS DE JUEGO', 'it': 'MODALITÀ DI GIOCO', 'pt': 'MODOS DE JOGO', 'ja': 'ゲームモード', 'zh': '游戏模式', 'ko': '게임 모드'
    },
    'extras_subtitle': {
        'tr': 'Farklı kurallar, farklı heyecanlar!',
        'en': 'Different rules, different thrills!',
        'de': 'Andere Regeln, andere Spannung!',
        'fr': 'Règles différentes, émotions différentes !',
        'es': 'Reglas distintas, emociones distintas!',
        'it': 'Regole diverse, emozioni diverse!',
        'pt': 'Regras diferentes, emoções diferentes!',
        'ja': 'ルールが違えば、ドキドキも違う！',
        'zh': '不同规则，不同刺激！',
        'ko': '다른 규칙, 다른 스릴!'
    },
    'start': {
        'tr': 'BAŞLA', 'en': 'START', 'de': 'START', 'fr': 'DÉMARRER', 'es': 'INICIAR', 'it': 'INIZIA', 'pt': 'INICIAR', 'ja': 'スタート', 'zh': '开始', 'ko': '시작'
    },
    'dont_show_again': {
        'tr': 'Bunu bir daha gösterme', 'en': "Don't show this again", 'de': 'Nicht mehr anzeigen', 'fr': 'Ne plus afficher', 'es': 'No mostrar de nuevo', 'it': 'Non mostrare più', 'pt': 'Não mostrar novamente', 'ja': '次回から表示しない', 'zh': '下次不再显示', 'ko': '다시 표시하지 않음'
    },
    
    # PvP Çevirileri
    'pvp_player1': {
        'tr': 'Oyuncu 1', 'en': 'Player 1', 'de': 'Spieler 1', 'fr': 'Joueur 1', 'es': 'Jugador 1', 'it': 'Giocatore 1', 'pt': 'Jogador 1', 'ja': 'プレイヤー1', 'zh': '玩家1', 'ko': '플레이어 1'
    },
    'pvp_player2': {
        'tr': 'Oyuncu 2', 'en': 'Player 2', 'de': 'Spieler 2', 'fr': 'Joueur 2', 'es': 'Jugador 2', 'it': 'Giocatore 2', 'pt': 'Jogador 2', 'ja': 'プレイヤー2', 'zh': '玩家2', 'ko': '플레이어 2'
    },
    'pvp_wins': {
        'tr': 'KAZANDI!', 'en': 'WINS!', 'de': 'GEWINNT!', 'fr': 'GAGNE!', 'es': '¡GANA!', 'it': 'VINCE!', 'pt': 'VENCE!', 'ja': '勝利！', 'zh': '获胜！', 'ko': '승리!'
    },
    'pvp_draw': {
        'tr': 'BERABERE!', 'en': 'DRAW!', 'de': 'UNENTSCHIEDEN!', 'fr': 'ÉGALITÉ!', 'es': '¡EMPATE!', 'it': 'PAREGGIO!', 'pt': 'EMPATE!', 'ja': '引き分け！', 'zh': '平局！', 'ko': '무승부!'
    },
    'pvp_time_up': {
        'tr': 'SÜRE BİTTİ', 'en': 'TIME UP', 'de': 'ZEIT ABGELAUFEN', 'fr': 'TEMPS ÉCOULÉ', 'es': 'TIEMPO AGOTADO', 'it': 'TEMPO SCADUTO', 'pt': 'TEMPO ESGOTADO', 'ja': '時間切れ', 'zh': '时间到', 'ko': '시간 종료'
    },
    'pvp_top_out': {
        'tr': 'TOP-OUT', 'en': 'TOP-OUT', 'de': 'TOP-OUT', 'fr': 'TOP-OUT', 'es': 'TOP-OUT', 'it': 'TOP-OUT', 'pt': 'TOP-OUT', 'ja': 'トップアウト', 'zh': '顶出', 'ko': '탑아웃'
    },
    'pvp_title_names': {
        'tr': 'PVP - OYUNCU İSİMLERİ', 'en': 'PVP - PLAYER NAMES', 'de': 'PVP - SPIELERNAMEN', 'fr': 'PVP - NOMS DES JOUEURS', 'es': 'PVP - NOMBRES', 'it': 'PVP - NOMI GIOCATORI', 'pt': 'PVP - NOMES DOS JOGADORES', 'ja': 'PVP - プレイヤー名', 'zh': 'PVP - 玩家姓名', 'ko': 'PVP - 플레이어 이름'
    },
    'pvp_title_settings': {
        'tr': 'PVP - MAÇ AYARLARI', 'en': 'PVP - MATCH SETTINGS', 'de': 'PVP - SPIELEINSTELLUNGEN', 'fr': 'PVP - PARAMÈTRES', 'es': 'PVP - CONFIGURACIÓN', 'it': 'PVP - IMPOSTAZIONI', 'pt': 'PVP - CONFIGURAÇÕES', 'ja': 'PVP - 試合設定', 'zh': 'PVP - 比赛设置', 'ko': 'PVP - 경기 설정'
    },
    'pvp_subtitle_names': {
        'tr': 'Retro düelloya başlamadan önce takma adlarını yaz', 'en': 'Enter your nicknames before the retro duel', 'de': 'Spitznamen vor dem Retro-Duell eingeben', 'fr': 'Entrez vos pseudos avant le duel rétro', 'es': 'Ingresa tus apodos antes del duelo retro', 'it': 'Inserisci i soprannomi prima del duello retrò', 'pt': 'Digite seus apelidos antes do duelo retrô', 'ja': 'レトロデュエル前にニックネームを入力', 'zh': '复古对决前输入昵称', 'ko': '레트로 듀얼 전에 닉네임을 입력하세요'
    },
    'pvp_subtitle_mode': {
        'tr': 'Maç modunu seç: Süreli veya Süresiz', 'en': 'Choose match mode: Timed or Endless', 'de': 'Spielmodus wählen: Zeitlich oder Endlos', 'fr': 'Choisir le mode: Chronométré ou Sans limite', 'es': 'Elige el modo: Cronometrado o Sin límite', 'it': 'Scegli la modalità: A tempo o Infinita', 'pt': 'Escolha o modo: Cronometrado ou Sem limite', 'ja': '試合モードを選択: 時間制 or 無制限', 'zh': '选择比赛模式：计时或无限', 'ko': '경기 모드 선택: 타임드 또는 무한'
    },
    'pvp_subtitle_duration': {
        'tr': 'Maç süresini ayarla (1-10 dakika)', 'en': 'Set match duration (1-10 minutes)', 'de': 'Spieldauer einstellen (1-10 Minuten)', 'fr': 'Définir la durée (1-10 minutes)', 'es': 'Ajustar duración (1-10 minutos)', 'it': 'Imposta la durata (1-10 minuti)', 'pt': 'Definir duração (1-10 minutos)', 'ja': '試合時間を設定 (1〜10分)', 'zh': '设置比赛时长（1-10分钟）', 'ko': '경기 시간 설정(1-10분)'
    },
    'pvp_player_profiles': {
        'tr': 'OYUNCU PROFİLLERİ', 'en': 'PLAYER PROFILES', 'de': 'SPIELERPROFILE', 'fr': 'PROFILS DES JOUEURS', 'es': 'PERFILES DE JUGADORES', 'it': 'PROFILI GIOCATORI', 'pt': 'PERFIS DOS JOGADORES', 'ja': 'プレイヤープロフィール', 'zh': '玩家档案', 'ko': '플레이어 프로필'
    },
    'pvp_match_settings': {
        'tr': 'MAÇ AYARLARI', 'en': 'MATCH SETTINGS', 'de': 'SPIELEINSTELLUNGEN', 'fr': 'PARAMÈTRES DU MATCH', 'es': 'CONFIGURACIÓN DEL PARTIDO', 'it': 'IMPOSTAZIONI PARTITA', 'pt': 'CONFIGURAÇÕES DA PARTIDA', 'ja': '試合設定', 'zh': '比赛设置', 'ko': '경기 설정'
    },
    'pvp_player1_wasd': {
        'tr': 'Oyuncu 1 - WASD', 'en': 'Player 1 - WASD', 'de': 'Spieler 1 - WASD', 'fr': 'Joueur 1 - WASD', 'es': 'Jugador 1 - WASD', 'it': 'Giocatore 1 - WASD', 'pt': 'Jogador 1 - WASD', 'ja': 'プレイヤー1 - WASD', 'zh': '玩家1 - WASD', 'ko': '플레이어 1 - WASD'
    },
    'pvp_player2_arrows': {
        'tr': 'Oyuncu 2 - Ok Tuşları', 'en': 'Player 2 - Arrow Keys', 'de': 'Spieler 2 - Pfeiltasten', 'fr': 'Joueur 2 - Touches fléchées', 'es': 'Jugador 2 - Flechas', 'it': 'Giocatore 2 - Frecce', 'pt': 'Jogador 2 - Setas', 'ja': 'プレイヤー2 - 矢印キー', 'zh': '玩家2 - 方向键', 'ko': '플레이어 2 - 방향키'
    },
    'pvp_enter_name': {
        'tr': 'İsim yaz...', 'en': 'Enter name...', 'de': 'Name eingeben...', 'fr': 'Entrer le nom...', 'es': 'Escribe nombre...', 'it': 'Inserisci nome...', 'pt': 'Digite o nome...', 'ja': '名前を入力...', 'zh': '输入姓名...', 'ko': '이름 입력...'
    },
    'pvp_max_chars': {
        'tr': '12 karaktere kadar', 'en': 'Up to 12 characters', 'de': 'Bis zu 12 Zeichen', 'fr': 'Jusqu\'à 12 caractères', 'es': 'Hasta 12 caracteres', 'it': 'Fino a 12 caratteri', 'pt': 'Até 12 caracteres', 'ja': '最大12文字', 'zh': '最多12个字符', 'ko': '최대 12자'
    },
    'pvp_enter_confirm': {
        'tr': 'Enter ile onayla', 'en': 'Press Enter to confirm', 'de': 'Eingabe bestätigen', 'fr': 'Appuyer sur Entrée', 'es': 'Pulsa Enter', 'it': 'Premi Invio', 'pt': 'Pressione Enter', 'ja': 'Enterで確定', 'zh': '按回车确认', 'ko': 'Enter로 확인'
    },
    'pvp_match_mode': {
        'tr': 'Maç Modu:', 'en': 'Match Mode:', 'de': 'Spielmodus:', 'fr': 'Mode de jeu:', 'es': 'Modo de juego:', 'it': 'Modalità partita:', 'pt': 'Modo de jogo:', 'ja': '試合モード:', 'zh': '比赛模式：', 'ko': '경기 모드:'
    },
    'pvp_timed': {
        'tr': 'Süreli', 'en': 'Timed', 'de': 'Zeitlich', 'fr': 'Chronométré', 'es': 'Cronometrado', 'it': 'A tempo', 'pt': 'Cronometrado', 'ja': '時間制', 'zh': '计时', 'ko': '타임드'
    },
    'pvp_endless': {
        'tr': 'Süresiz', 'en': 'Endless', 'de': 'Endlos', 'fr': 'Sans limite', 'es': 'Sin límite', 'it': 'Infinita', 'pt': 'Sem limite', 'ja': '無制限', 'zh': '无限', 'ko': '무한'
    },
    'pvp_timed_desc': {
        'tr': 'Belirlenen süre sonunda en çok satırı silen kazanır', 'en': 'Most lines cleared when time runs out wins', 'de': 'Meiste Linien wenn Zeit abläuft gewinnt', 'fr': 'Le plus de lignes quand le temps expire gagne', 'es': 'El que más líneas limpie cuando acabe el tiempo gana', 'it': 'Chi elimina più linee allo scadere del tempo vince', 'pt': 'Quem limpar mais linhas quando o tempo acabar vence', 'ja': '時間切れ時に消したライン数が多い方が勝ち', 'zh': '时间结束时消除行数最多者获胜', 'ko': '시간 종료 시 더 많은 줄을 지운 사람이 승리'
    },
    'pvp_endless_desc': {
        'tr': 'Süre limiti yok - ilk eleyen kazanır', 'en': 'No time limit - first to eliminate wins', 'de': 'Keine Zeitbegrenzung - erster Ausscheidender gewinnt', 'fr': 'Pas de limite de temps - le premier éliminé perd', 'es': 'Sin límite de tiempo - el primero en eliminar gana', 'it': 'Nessun limite di tempo - chi elimina per primo vince', 'pt': 'Sem limite de tempo - primeiro a eliminar vence', 'ja': '時間制限なし - 先に脱落させた方が勝ち', 'zh': '无时间限制 - 先淘汰对方者获胜', 'ko': '시간 제한 없음 - 먼저 상대를 탈락시키는 사람이 승리'
    },
    'pvp_match_duration': {
        'tr': 'Maç Süresi:', 'en': 'Match Duration:', 'de': 'Spieldauer:', 'fr': 'Durée du match:', 'es': 'Duración del partido:', 'it': 'Durata partita:', 'pt': 'Duração da partida:', 'ja': '試合時間:', 'zh': '比赛时长：', 'ko': '경기 시간:'
    },
    'pvp_minutes': {
        'tr': 'dk', 'en': 'min', 'de': 'Min', 'fr': 'min', 'es': 'min', 'it': 'min', 'pt': 'min', 'ja': '分', 'zh': '分', 'ko': '분'
    },
    'pvp_duration_range': {
        'tr': '1 - 10 dakika arasında ayarlayabilirsiniz', 'en': 'You can set between 1 - 10 minutes', 'de': 'Sie können zwischen 1 - 10 Minuten einstellen', 'fr': 'Vous pouvez régler entre 1 - 10 minutes', 'es': 'Puedes ajustar entre 1 - 10 minutos', 'it': 'Puoi impostare tra 1 - 10 minuti', 'pt': 'Você pode definir entre 1 - 10 minutos', 'ja': '1〜10分の間で設定できます', 'zh': '可设置 1 - 10 分钟', 'ko': '1~10분 사이로 설정할 수 있습니다'
    },
    'pvp_start': {
        'tr': 'BAŞLA', 'en': 'START', 'de': 'START', 'fr': 'DÉMARRER', 'es': 'INICIAR', 'it': 'INIZIA', 'pt': 'INICIAR', 'ja': 'スタート', 'zh': '开始', 'ko': '시작'
    },
    'pvp_step': {
        'tr': 'Adım', 'en': 'Step', 'de': 'Schritt', 'fr': 'Étape', 'es': 'Paso', 'it': 'Passo', 'pt': 'Passo', 'ja': 'ステップ', 'zh': '步骤', 'ko': '단계'
    },
    'pvp_pause_hint': {
        'tr': 'Duraklat', 'en': 'Pause', 'de': 'Pause', 'fr': 'Pause', 'es': 'Pausa', 'it': 'Pausa', 'pt': 'Pausar', 'ja': '一時停止', 'zh': '暂停', 'ko': '일시정지'
    },
    'pvp_score': {
        'tr': 'Skor', 'en': 'Score', 'de': 'Punkte', 'fr': 'Score', 'es': 'Puntos', 'it': 'Punteggio', 'pt': 'Pontos', 'ja': 'スコア', 'zh': '得分', 'ko': '점수'
    },
    'pvp_lines': {
        'tr': 'Satır', 'en': 'Lines', 'de': 'Zeilen', 'fr': 'Lignes', 'es': 'Líneas', 'it': 'Linee', 'pt': 'Linhas', 'ja': 'ライン', 'zh': '行', 'ko': '줄'
    },
    'pvp_lines_suffix': {
        'tr': 'satır', 'en': 'lines', 'de': 'Zeilen', 'fr': 'lignes', 'es': 'líneas', 'it': 'linee', 'pt': 'linhas', 'ja': 'ライン', 'zh': '行', 'ko': '줄'
    },
    'pvp_points_diff': {
        'tr': 'puan', 'en': 'points', 'de': 'Punkte', 'fr': 'points', 'es': 'puntos', 'it': 'punti', 'pt': 'pontos', 'ja': 'ポイント', 'zh': '分', 'ko': '점수'
    },
    'pvp_lines_diff': {
        'tr': 'satır fark', 'en': 'lines diff', 'de': 'Zeilen Diff.', 'fr': 'lignes diff', 'es': 'líneas dif', 'it': 'linee diff', 'pt': 'linhas dif', 'ja': 'ライン差', 'zh': '行差', 'ko': '줄 차'
    },
    'pvp_restart': {
        'tr': 'Yeniden', 'en': 'Restart', 'de': 'Neustart', 'fr': 'Rejouer', 'es': 'Reiniciar', 'it': 'Ricomincia', 'pt': 'Reiniciar', 'ja': 'リスタート', 'zh': '重开', 'ko': '재시작'
    },
    
    # User Screens Çevirileri
    'user_no_storage_data': {
        'tr': 'Henüz saklama verisi yok.', 'en': 'No storage data yet.', 'de': 'Noch keine Speicherdaten.', 'fr': 'Pas encore de données.', 'es': 'Sin datos aún.', 'it': 'Nessun dato ancora.', 'pt': 'Sem dados ainda.', 'ja': 'まだ保存データがありません。', 'zh': '暂无存档数据。', 'ko': '저장 데이터가 아직 없습니다.'
    },
    'user_active': {
        'tr': 'Aktif', 'en': 'Active', 'de': 'Aktiv', 'fr': 'Actif', 'es': 'Activo', 'it': 'Attivo', 'pt': 'Ativo', 'ja': '有効', 'zh': '激活', 'ko': '활성'
    },
    'user_create_new': {
        'tr': 'Yeni kullanıcı oluştur', 'en': 'Create new user', 'de': 'Neuen Benutzer erstellen', 'fr': 'Créer un utilisateur', 'es': 'Crear nuevo usuario', 'it': 'Crea nuovo utente', 'pt': 'Criar novo usuário', 'ja': '新しいユーザーを作成', 'zh': '创建新用户', 'ko': '새 사용자 만들기'
    },
    'user_create_hint': {
        'tr': 'İlerlemeni kaydetmek için profil ekle', 'en': 'Add a profile to save your progress', 'de': 'Profil hinzufügen um Fortschritt zu speichern', 'fr': 'Ajouter un profil pour sauvegarder', 'es': 'Añade un perfil para guardar tu progreso', 'it': 'Aggiungi un profilo per salvare', 'pt': 'Adicione um perfil para salvar', 'ja': '進行を保存するためプロフィールを追加', 'zh': '添加档案以保存进度', 'ko': '진행 상황을 저장하려면 프로필을 추가하세요'
    },
    'user_no_users': {
        'tr': 'Henüz hiç kullanıcı yok.', 'en': 'No users yet.', 'de': 'Noch keine Benutzer.', 'fr': 'Aucun utilisateur.', 'es': 'Sin usuarios aún.', 'it': 'Nessun utente ancora.', 'pt': 'Sem usuários ainda.', 'ja': 'まだユーザーがいません。', 'zh': '暂无用户。', 'ko': '사용자가 아직 없습니다.'
    },
    'user_start_hint': {
        'tr': 'Başlamak için soldan yeni profil oluştur.', 'en': 'Create a new profile from the left to start.', 'de': 'Erstelle links ein neues Profil zum Starten.', 'fr': 'Créez un profil à gauche pour commencer.', 'es': 'Crea un perfil a la izquierda para empezar.', 'it': 'Crea un profilo a sinistra per iniziare.', 'pt': 'Crie um perfil à esquerda para começar.', 'ja': '開始するには左から新しいプロフィールを作成。', 'zh': '从左侧创建新档案以开始。', 'ko': '시작하려면 왼쪽에서 새 프로필을 만드세요.'
    },
    'user_new_profile': {
        'tr': 'Yeni bir kullanıcı oluştur.', 'en': 'Create a new user.', 'de': 'Neuen Benutzer erstellen.', 'fr': 'Créer un nouvel utilisateur.', 'es': 'Crear un nuevo usuario.', 'it': 'Crea un nuovo utente.', 'pt': 'Criar um novo usuário.', 'ja': '新しいユーザーを作成。', 'zh': '创建新用户。', 'ko': '새 사용자 만들기.'
    },
    'user_adventure_hint': {
        'tr': 'Avatar seç, isim yaz ve macerana başla!', 'en': 'Choose avatar, enter name and start!', 'de': 'Wähle Avatar, gib Namen ein und starte!', 'fr': 'Choisis un avatar, entre ton nom et commence!', 'es': '¡Elige avatar, escribe nombre y empieza!', 'it': 'Scegli avatar, scrivi nome e inizia!', 'pt': 'Escolha avatar, digite nome e comece!', 'ja': 'アバターを選び、名前を入力して開始！', 'zh': '选择头像，输入名字并开始冒险！', 'ko': '아바타를 선택하고 이름을 입력해 시작하세요!'
    },
    'user_bio': {
        'tr': 'Bio', 'en': 'Bio', 'de': 'Bio', 'fr': 'Bio', 'es': 'Bio', 'it': 'Bio', 'pt': 'Bio', 'ja': '自己紹介', 'zh': '简介', 'ko': '자기소개'
    },
    'user_confirm_delete': {
        'tr': 'Tekrar DEL ile onayla (2sn)', 'en': 'Confirm with DEL again (2s)', 'de': 'Mit DEL bestätigen (2s)', 'fr': 'Confirmer avec DEL (2s)', 'es': 'Confirma con DEL (2s)', 'it': 'Conferma con DEL (2s)', 'pt': 'Confirme com DEL (2s)', 'ja': 'DELで再確認(2秒)', 'zh': '再按 DEL 确认（2秒）', 'ko': 'DEL로 다시 확인 (2초)'
    },
    'user_custom_image': {
        'tr': 'Özel resim seçildi', 'en': 'Custom image selected', 'de': 'Eigenes Bild ausgewählt', 'fr': 'Image personnalisée', 'es': 'Imagen personalizada', 'it': 'Immagine personalizzata', 'pt': 'Imagem personalizada', 'ja': 'カスタム画像を選択しました', 'zh': '已选择自定义图片', 'ko': '사용자 지정 이미지를 선택했습니다'
    },
    'user_username': {
        'tr': 'Kullanıcı Adı', 'en': 'Username', 'de': 'Benutzername', 'fr': 'Nom d\'utilisateur', 'es': 'Nombre de usuario', 'it': 'Nome utente', 'pt': 'Nome de usuário', 'ja': 'ユーザー名', 'zh': '用户名', 'ko': '사용자 이름'
    },
    'user_name_locked': {
        'tr': 'Bu ad değiştirilemez', 'en': 'This name cannot be changed', 'de': 'Name kann nicht geändert werden', 'fr': 'Ce nom ne peut pas être changé', 'es': 'Este nombre no se puede cambiar', 'it': 'Questo nome non può essere cambiato', 'pt': 'Este nome não pode ser alterado', 'ja': 'この名前は変更できません', 'zh': '此名称不可更改', 'ko': '이 이름은 변경할 수 없습니다'
    },
    'user_locked': {
        'tr': 'Kilitli', 'en': 'Locked', 'de': 'Gesperrt', 'fr': 'Verrouillé', 'es': 'Bloqueado', 'it': 'Bloccato', 'pt': 'Bloqueado', 'ja': 'ロック中', 'zh': '已锁定', 'ko': '잠김'
    },
    'user_management': {
        'tr': 'Kullanıcı Yönetimi', 'en': 'User Management', 'de': 'Benutzerverwaltung', 'fr': 'Gestion des utilisateurs', 'es': 'Gestión de usuarios', 'it': 'Gestione utenti', 'pt': 'Gerenciamento de usuários', 'ja': 'ユーザー管理', 'zh': '用户管理', 'ko': '사용자 관리'
    },
    'user_no_active': {
        'tr': 'Aktif kullanıcı yok', 'en': 'No active user', 'de': 'Kein aktiver Benutzer', 'fr': 'Aucun utilisateur actif', 'es': 'Sin usuario activo', 'it': 'Nessun utente attivo', 'pt': 'Sem usuário ativo', 'ja': 'アクティブユーザーなし', 'zh': '无活跃用户', 'ko': '활성 사용자 없음'
    },
    'user_not_created': {
        'tr': 'Henüz kullanıcı oluşturulmamış', 'en': 'No users created yet', 'de': 'Noch keine Benutzer erstellt', 'fr': 'Aucun utilisateur créé', 'es': 'Sin usuarios creados', 'it': 'Nessun utente creato', 'pt': 'Nenhum usuário criado', 'ja': 'まだユーザーが作成されていません', 'zh': '尚未创建用户', 'ko': '아직 사용자가 생성되지 않음'
    },
    'user_will_delete': {
        'tr': 'Kullanıcı Silinecek!', 'en': 'User Will Be Deleted!', 'de': 'Benutzer wird gelöscht!', 'fr': 'L\'utilisateur sera supprimé!', 'es': '¡El usuario será eliminado!', 'it': 'L\'utente sarà eliminato!', 'pt': 'O usuário será excluído!', 'ja': 'ユーザーが削除されます！', 'zh': '用户将被删除！', 'ko': '사용자가 삭제됩니다!'
    },
    'user_delete_warning': {
        'tr': 'Tüm başarımlar ve skorlar silinecek!', 'en': 'All achievements and scores will be deleted!', 'de': 'Alle Erfolge und Punkte werden gelöscht!', 'fr': 'Tous les succès et scores seront supprimés!', 'es': '¡Todos los logros y puntuaciones serán eliminados!', 'it': 'Tutti i risultati e i punteggi saranno eliminati!', 'pt': 'Todas as conquistas e pontuações serão excluídas!', 'ja': 'すべての実績とスコアが削除されます！', 'zh': '所有成就和分数将被删除！', 'ko': '모든 업적과 점수가 삭제됩니다!'
    },
    'user_no': {
        'tr': 'N - Hayır', 'en': 'N - No', 'de': 'N - Nein', 'fr': 'N - Non', 'es': 'N - No', 'it': 'N - No', 'pt': 'N - Não', 'ja': 'N - いいえ', 'zh': 'N - 否', 'ko': 'N - 아니오'
    },
    'user_yes': {
        'tr': 'Y - Evet', 'en': 'Y - Yes', 'de': 'J - Ja', 'fr': 'O - Oui', 'es': 'S - Sí', 'it': 'S - Sì', 'pt': 'S - Sim', 'ja': 'Y - はい', 'zh': 'Y - 是', 'ko': 'Y - 예'
    },
    'user_favorite': {
        'tr': 'Favori', 'en': 'Favorite', 'de': 'Favorit', 'fr': 'Favori', 'es': 'Favorito', 'it': 'Preferito', 'pt': 'Favorito', 'ja': 'お気に入り', 'zh': '收藏', 'ko': '즐겨찾기'
    },
    'user_mode_stats': {
        'tr': 'Mod Bazlı İstatistikler', 'en': 'Mode Statistics', 'de': 'Modus-Statistiken', 'fr': 'Statistiques par mode', 'es': 'Estadísticas por modo', 'it': 'Statistiche per modalità', 'pt': 'Estatísticas por modo', 'ja': 'モード別統計', 'zh': '模式统计', 'ko': '모드 통계'
    },
    'user_no_games': {
        'tr': 'Henüz hiç oyun oynamamış', 'en': 'No games played yet', 'de': 'Noch keine Spiele gespielt', 'fr': 'Aucun jeu joué', 'es': 'Sin juegos jugados', 'it': 'Nessuna partita giocata', 'pt': 'Nenhum jogo jogado', 'ja': 'まだプレイしていません', 'zh': '尚未玩过游戏', 'ko': '아직 플레이한 게임이 없습니다'
    },
    'user_edit_profile': {
        'tr': 'Profil Düzenle', 'en': 'Edit Profile', 'de': 'Profil bearbeiten', 'fr': 'Modifier le profil', 'es': 'Editar perfil', 'it': 'Modifica profilo', 'pt': 'Editar perfil', 'ja': 'プロフィール編集', 'zh': '编辑档案', 'ko': '프로필 편집'
    },
    
    # ========== ACHIEVEMENT (BAŞARI) ÇEVİRİLERİ ==========
    # Başlangıç başarıları
    'ach_first_game_name': {
        'tr': 'İlk Adım', 'en': 'First Step', 'de': 'Erster Schritt', 'fr': 'Premier pas', 'es': 'Primer paso', 'it': 'Primo passo', 'pt': 'Primeiro passo', 'ja': '初めの一歩', 'zh': '第一步', 'ko': '첫걸음'
    },
    'ach_first_game_desc': {
        'tr': 'İlk oyununu tamamla', 'en': 'Complete your first game', 'de': 'Schließe dein erstes Spiel ab', 'fr': 'Termine ta première partie', 'es': 'Completa tu primer juego', 'it': 'Completa la tua prima partita', 'pt': 'Complete seu primeiro jogo', 'ja': '初めてのゲームを完了する', 'zh': '完成你的第一局游戏', 'ko': '첫 게임을 완료하세요'
    },
    'ach_first_line_name': {
        'tr': 'İlk Satır', 'en': 'First Line', 'de': 'Erste Reihe', 'fr': 'Première ligne', 'es': 'Primera línea', 'it': 'Prima riga', 'pt': 'Primeira linha', 'ja': '初ライン', 'zh': '第一行', 'ko': '첫 줄'
    },
    'ach_first_line_desc': {
        'tr': 'İlk satırını temizle', 'en': 'Clear your first line', 'de': 'Räume deine erste Reihe', 'fr': 'Efface ta première ligne', 'es': 'Limpia tu primera línea', 'it': 'Cancella la tua prima riga', 'pt': 'Limpe sua primeira linha', 'ja': '初めてラインを消す', 'zh': '清除你的第一行', 'ko': '첫 줄을 지우세요'
    },
    'ach_first_tetris_name': {
        'tr': 'İlk Quadrix', 'en': 'First Quadrix', 'de': 'Erster Quadrix', 'fr': 'Premier Quadrix', 'es': 'Primer Quadrix', 'it': 'Primo Quadrix', 'pt': 'Primeiro Quadrix', 'ja': '初テトリス', 'zh': '第一次俄罗斯方块', 'ko': '첫 테트리스'
    },
    'ach_first_tetris_desc': {
        'tr': 'İlk 4 satırlık Quadrix\'ini yap', 'en': 'Make your first 4-line Quadrix', 'de': 'Mache deinen ersten 4-Reihen-Quadrix', 'fr': 'Fais ton premier Quadrix de 4 lignes', 'es': 'Haz tu primer Quadrix de 4 líneas', 'it': 'Fai il tuo primo Quadrix da 4 righe', 'pt': 'Faça seu primeiro Quadrix de 4 linhas', 'ja': '初めて4ラインテトリスを達成', 'zh': '完成第一次4行俄罗斯方块', 'ko': '첫 4줄 테트리스를 달성하세요'
    },
    
    # Skor başarıları
    'ach_score_1k_name': {
        'tr': 'Başlangıç', 'en': 'Beginning', 'de': 'Anfang', 'fr': 'Début', 'es': 'Inicio', 'it': 'Inizio', 'pt': 'Início', 'ja': 'スタート', 'zh': '起步', 'ko': '시작'
    },
    'ach_score_1k_desc': {
        'tr': 'Bir oyunda 1,000 puana ulaş', 'en': 'Reach 1,000 points in one game', 'de': 'Erreiche 1.000 Punkte in einem Spiel', 'fr': 'Atteins 1 000 points en une partie', 'es': 'Alcanza 1.000 puntos en un juego', 'it': 'Raggiungi 1.000 punti in una partita', 'pt': 'Alcance 1.000 pontos em um jogo', 'ja': '1ゲームで1,000点到達', 'zh': '单局达到1,000分', 'ko': '한 게임에서 1,000점 달성'
    },
    'ach_score_10k_name': {
        'tr': 'Deneyimli', 'en': 'Experienced', 'de': 'Erfahren', 'fr': 'Expérimenté', 'es': 'Experimentado', 'it': 'Esperto', 'pt': 'Experiente', 'ja': '熟練者', 'zh': '熟练', 'ko': '숙련'
    },
    'ach_score_10k_desc': {
        'tr': 'Bir oyunda 10,000 puana ulaş', 'en': 'Reach 10,000 points in one game', 'de': 'Erreiche 10.000 Punkte in einem Spiel', 'fr': 'Atteins 10 000 points en une partie', 'es': 'Alcanza 10.000 puntos en un juego', 'it': 'Raggiungi 10.000 punti in una partita', 'pt': 'Alcance 10.000 pontos em um jogo', 'ja': '1ゲームで10,000点到達', 'zh': '单局达到10,000分', 'ko': '한 게임에서 10,000점 달성'
    },
    'ach_score_50k_name': {
        'tr': 'Usta', 'en': 'Master', 'de': 'Meister', 'fr': 'Maître', 'es': 'Maestro', 'it': 'Maestro', 'pt': 'Mestre', 'ja': '達人', 'zh': '大师', 'ko': '달인'
    },
    'ach_score_50k_desc': {
        'tr': 'Bir oyunda 50,000 puana ulaş', 'en': 'Reach 50,000 points in one game', 'de': 'Erreiche 50.000 Punkte in einem Spiel', 'fr': 'Atteins 50 000 points en une partie', 'es': 'Alcanza 50.000 puntos en un juego', 'it': 'Raggiungi 50.000 punti in una partita', 'pt': 'Alcance 50.000 pontos em um jogo', 'ja': '1ゲームで50,000点到達', 'zh': '单局达到50,000分', 'ko': '한 게임에서 50,000점 달성'
    },
    'ach_score_100k_name': {
        'tr': 'Efsane', 'en': 'Legend', 'de': 'Legende', 'fr': 'Légende', 'es': 'Leyenda', 'it': 'Leggenda', 'pt': 'Lenda', 'ja': 'レジェンド', 'zh': '传奇', 'ko': '전설'
    },
    'ach_score_100k_desc': {
        'tr': 'Bir oyunda 100,000 puana ulaş', 'en': 'Reach 100,000 points in one game', 'de': 'Erreiche 100.000 Punkte in einem Spiel', 'fr': 'Atteins 100 000 points en une partie', 'es': 'Alcanza 100.000 puntos en un juego', 'it': 'Raggiungi 100.000 punti in una partita', 'pt': 'Alcance 100.000 pontos em um jogo', 'ja': '1ゲームで100,000点到達', 'zh': '单局达到100,000分', 'ko': '한 게임에서 100,000점 달성'
    },
    
    # Satır başarıları
    'ach_lines_10_name': {
        'tr': 'Temizlikçi', 'en': 'Cleaner', 'de': 'Reiniger', 'fr': 'Nettoyeur', 'es': 'Limpiador', 'it': 'Pulitore', 'pt': 'Limpador', 'ja': 'クリーナー', 'zh': '清洁工', 'ko': '청소부'
    },
    'ach_lines_10_desc': {
        'tr': 'Bir oyunda 10 satır temizle', 'en': 'Clear 10 lines in one game', 'de': 'Räume 10 Reihen in einem Spiel', 'fr': 'Efface 10 lignes en une partie', 'es': 'Limpia 10 líneas en un juego', 'it': 'Cancella 10 righe in una partita', 'pt': 'Limpe 10 linhas em um jogo', 'ja': '1ゲームで10ライン消去', 'zh': '单局清除10行', 'ko': '한 게임에서 10줄 지우기'
    },
    'ach_lines_50_name': {
        'tr': 'Süpürge', 'en': 'Sweeper', 'de': 'Feger', 'fr': 'Balayeur', 'es': 'Barrendero', 'it': 'Spazzino', 'pt': 'Varredor', 'ja': 'スイーパー', 'zh': '扫地者', 'ko': '청소꾼'
    },
    'ach_lines_50_desc': {
        'tr': 'Bir oyunda 50 satır temizle', 'en': 'Clear 50 lines in one game', 'de': 'Räume 50 Reihen in einem Spiel', 'fr': 'Efface 50 lignes en une partie', 'es': 'Limpia 50 líneas en un juego', 'it': 'Cancella 50 righe in una partita', 'pt': 'Limpe 50 linhas em um jogo', 'ja': '1ゲームで50ライン消去', 'zh': '单局清除50行', 'ko': '한 게임에서 50줄 지우기'
    },
    'ach_lines_100_name': {
        'tr': 'Temizlik Robotu', 'en': 'Cleaning Bot', 'de': 'Reinigungsroboter', 'fr': 'Robot nettoyeur', 'es': 'Robot limpiador', 'it': 'Robot pulitore', 'pt': 'Robô limpador', 'ja': 'クリーニングボット', 'zh': '清洁机器人', 'ko': '청소 로봇'
    },
    'ach_lines_100_desc': {
        'tr': 'Bir oyunda 100 satır temizle', 'en': 'Clear 100 lines in one game', 'de': 'Räume 100 Reihen in einem Spiel', 'fr': 'Efface 100 lignes en une partie', 'es': 'Limpia 100 líneas en un juego', 'it': 'Cancella 100 righe in una partita', 'pt': 'Limpe 100 linhas em um jogo', 'ja': '1ゲームで100ライン消去', 'zh': '单局清除100行', 'ko': '한 게임에서 100줄 지우기'
    },
    'ach_lines_200_name': {
        'tr': 'Temizlik Makinesi', 'en': 'Cleaning Machine', 'de': 'Reinigungsmaschine', 'fr': 'Machine de nettoyage', 'es': 'Máquina limpiadora', 'it': 'Macchina per la pulizia', 'pt': 'Máquina de limpeza', 'ja': 'クリーニングマシン', 'zh': '清洁机器', 'ko': '청소 기계'
    },
    'ach_lines_200_desc': {
        'tr': 'Bir oyunda 200 satır temizle', 'en': 'Clear 200 lines in one game', 'de': 'Räume 200 Reihen in einem Spiel', 'fr': 'Efface 200 lignes en une partie', 'es': 'Limpia 200 líneas en un juego', 'it': 'Cancella 200 righe in una partita', 'pt': 'Limpe 200 linhas em um jogo', 'ja': '1ゲームで200ライン消去', 'zh': '单局清除200行', 'ko': '한 게임에서 200줄 지우기'
    },
    
    # Quadrix başarıları
    'ach_tetris_5_name': {
        'tr': 'Quadrix Ustası', 'en': 'Quadrix Master', 'de': 'Quadrix-Meister', 'fr': 'Maître Quadrix', 'es': 'Maestro Quadrix', 'it': 'Maestro Quadrix', 'pt': 'Mestre Quadrix', 'ja': 'テトリスマスター', 'zh': '俄罗斯方块大师', 'ko': '테트리스 마스터'
    },
    'ach_tetris_5_desc': {
        'tr': '5 Quadrix yap', 'en': 'Make 5 Tetrises', 'de': 'Mache 5 Tetrisse', 'fr': 'Fais 5 Quadrix', 'es': 'Haz 5 Tetrises', 'it': 'Fai 5 Quadrix', 'pt': 'Faça 5 Tetrises', 'ja': 'テトリスを5回達成', 'zh': '完成5次俄罗斯方块', 'ko': '테트리스 5회 달성'
    },
    'ach_tetris_10_name': {
        'tr': 'Quadrix Tanrısı', 'en': 'Quadrix God', 'de': 'Quadrix-Gott', 'fr': 'Dieu Quadrix', 'es': 'Dios Quadrix', 'it': 'Dio Quadrix', 'pt': 'Deus Quadrix', 'ja': 'テトリスゴッド', 'zh': '俄罗斯方块之神', 'ko': '테트리스 신'
    },
    'ach_tetris_10_desc': {
        'tr': '10 Quadrix yap', 'en': 'Make 10 Tetrises', 'de': 'Mache 10 Tetrisse', 'fr': 'Fais 10 Quadrix', 'es': 'Haz 10 Tetrises', 'it': 'Fai 10 Quadrix', 'pt': 'Faça 10 Tetrises', 'ja': 'テトリスを10回達成', 'zh': '完成10次俄罗斯方块', 'ko': '테트리스 10회 달성'
    },
    
    # Seviye başarıları
    'ach_level_5_name': {
        'tr': 'Hızlanıyor', 'en': 'Speeding Up', 'de': 'Beschleunigt', 'fr': 'En accélération', 'es': 'Acelerando', 'it': 'In accelerazione', 'pt': 'Acelerando', 'ja': '加速中', 'zh': '加速中', 'ko': '가속 중'
    },
    'ach_level_5_desc': {
        'tr': 'Bir oyunda seviye 5\'e ulaş', 'en': 'Reach level 5 in one game', 'de': 'Erreiche Level 5 in einem Spiel', 'fr': 'Atteins le niveau 5 en une partie', 'es': 'Alcanza el nivel 5 en un juego', 'it': 'Raggiungi il livello 5 in una partita', 'pt': 'Alcance o nível 5 em um jogo', 'ja': '1ゲームでレベル5到達', 'zh': '单局达到5级', 'ko': '한 게임에서 레벨 5 달성'
    },
    'ach_level_10_name': {
        'tr': 'Hız Canavarı', 'en': 'Speed Demon', 'de': 'Geschwindigkeitsdämon', 'fr': 'Démon de vitesse', 'es': 'Demonio de velocidad', 'it': 'Demone della velocità', 'pt': 'Demônio da velocidade', 'ja': 'スピードデーモン', 'zh': '速度恶魔', 'ko': '스피드 데몬'
    },
    'ach_level_10_desc': {
        'tr': 'Bir oyunda seviye 10\'a ulaş', 'en': 'Reach level 10 in one game', 'de': 'Erreiche Level 10 in einem Spiel', 'fr': 'Atteins le niveau 10 en une partie', 'es': 'Alcanza el nivel 10 en un juego', 'it': 'Raggiungi il livello 10 in una partita', 'pt': 'Alcance o nível 10 em um jogo', 'ja': '1ゲームでレベル10到達', 'zh': '单局达到10级', 'ko': '한 게임에서 레벨 10 달성'
    },
    'ach_level_15_name': {
        'tr': 'Süpersonik', 'en': 'Supersonic', 'de': 'Überschall', 'fr': 'Supersonique', 'es': 'Supersónico', 'it': 'Supersonico', 'pt': 'Supersônico', 'ja': '超音速', 'zh': '超音速', 'ko': '초음속'
    },
    'ach_level_15_desc': {
        'tr': 'Bir oyunda seviye 15\'e ulaş', 'en': 'Reach level 15 in one game', 'de': 'Erreiche Level 15 in einem Spiel', 'fr': 'Atteins le niveau 15 en une partie', 'es': 'Alcanza el nivel 15 en un juego', 'it': 'Raggiungi il livello 15 in una partita', 'pt': 'Alcance o nível 15 em um jogo', 'ja': '1ゲームでレベル15到達', 'zh': '单局达到15级', 'ko': '한 게임에서 레벨 15 달성'
    },
    'ach_level_20_name': {
        'tr': 'Işık Hızı', 'en': 'Light Speed', 'de': 'Lichtgeschwindigkeit', 'fr': 'Vitesse lumière', 'es': 'Velocidad luz', 'it': 'Velocità della luce', 'pt': 'Velocidade da luz', 'ja': '光速', 'zh': '光速', 'ko': '광속'
    },
    'ach_level_20_desc': {
        'tr': 'Bir oyunda seviye 20\'ye ulaş', 'en': 'Reach level 20 in one game', 'de': 'Erreiche Level 20 in einem Spiel', 'fr': 'Atteins le niveau 20 en une partie', 'es': 'Alcanza el nivel 20 en un juego', 'it': 'Raggiungi il livello 20 in una partita', 'pt': 'Alcance o nível 20 em um jogo', 'ja': '1ゲームでレベル20到達', 'zh': '单局达到20级', 'ko': '한 게임에서 레벨 20 달성'
    },
    
    # Oyun sayısı başarıları
    'ach_games_10_name': {
        'tr': 'Sadık Oyuncu', 'en': 'Loyal Player', 'de': 'Treuer Spieler', 'fr': 'Joueur fidèle', 'es': 'Jugador fiel', 'it': 'Giocatore fedele', 'pt': 'Jogador fiel', 'ja': '忠実なプレイヤー', 'zh': '忠实玩家', 'ko': '충실한 플레이어'
    },
    'ach_games_10_desc': {
        'tr': '10 oyun oyna', 'en': 'Play 10 games', 'de': 'Spiele 10 Spiele', 'fr': 'Joue 10 parties', 'es': 'Juega 10 juegos', 'it': 'Gioca 10 partite', 'pt': 'Jogue 10 jogos', 'ja': '10ゲームプレイ', 'zh': '玩10局游戏', 'ko': '10게임 플레이'
    },
    'ach_games_50_name': {
        'tr': 'Müdavim', 'en': 'Regular', 'de': 'Stammgast', 'fr': 'Habitué', 'es': 'Habitual', 'it': 'Assiduo', 'pt': 'Frequentador', 'ja': '常連', 'zh': '常客', 'ko': '단골'
    },
    'ach_games_50_desc': {
        'tr': '50 oyun oyna', 'en': 'Play 50 games', 'de': 'Spiele 50 Spiele', 'fr': 'Joue 50 parties', 'es': 'Juega 50 juegos', 'it': 'Gioca 50 partite', 'pt': 'Jogue 50 jogos', 'ja': '50ゲームプレイ', 'zh': '玩50局游戏', 'ko': '50게임 플레이'
    },
    'ach_games_100_name': {
        'tr': 'Profesyonel', 'en': 'Professional', 'de': 'Profi', 'fr': 'Professionnel', 'es': 'Profesional', 'it': 'Professionista', 'pt': 'Profissional', 'ja': 'プロフェッショナル', 'zh': '职业选手', 'ko': '프로'
    },
    'ach_games_100_desc': {
        'tr': '100 oyun oyna', 'en': 'Play 100 games', 'de': 'Spiele 100 Spiele', 'fr': 'Joue 100 parties', 'es': 'Juega 100 juegos', 'it': 'Gioca 100 partite', 'pt': 'Jogue 100 jogos', 'ja': '100ゲームプレイ', 'zh': '玩100局游戏', 'ko': '100게임 플레이'
    },
    
    # Özel başarılar
    'ach_combo_5_name': {
        'tr': 'Kombo Ustası', 'en': 'Combo Master', 'de': 'Kombo-Meister', 'fr': 'Maître combo', 'es': 'Maestro del combo', 'it': 'Maestro delle combo', 'pt': 'Mestre do combo', 'ja': 'コンボマスター', 'zh': '连击大师', 'ko': '콤보 마스터'
    },
    'ach_combo_5_desc': {
        'tr': 'Bir oyunda 5x kombo yap', 'en': 'Make a 5x combo in one game', 'de': 'Mache eine 5x Kombo in einem Spiel', 'fr': 'Fais un combo x5 en une partie', 'es': 'Haz un combo x5 en un juego', 'it': 'Fai una combo x5 in una partita', 'pt': 'Faça um combo x5 em um jogo', 'ja': '1ゲームで5xコンボ', 'zh': '单局达成5x连击', 'ko': '한 게임에서 5x 콤보'
    },
    'ach_perfect_clear_name': {
        'tr': 'Mükemmel Temizlik', 'en': 'Perfect Clear', 'de': 'Perfekte Räumung', 'fr': 'Nettoyage parfait', 'es': 'Limpieza perfecta', 'it': 'Pulizia perfetta', 'pt': 'Limpeza perfeita', 'ja': 'パーフェクトクリア', 'zh': '完美清除', 'ko': '퍼펙트 클리어'
    },
    'ach_perfect_clear_desc': {
        'tr': 'Tahtayı tamamen temizle', 'en': 'Clear the board completely', 'de': 'Räume das Brett vollständig', 'fr': 'Efface complètement le plateau', 'es': 'Limpia el tablero completamente', 'it': 'Cancella completamente la tavola', 'pt': 'Limpe o tabuleiro completamente', 'ja': '盤面を完全に消す', 'zh': '完全清空棋盘', 'ko': '보드를 완전히 비우기'
    },
    'ach_no_mistakes_name': {
        'tr': 'Kusursuz', 'en': 'Flawless', 'de': 'Makellos', 'fr': 'Parfait', 'es': 'Impecable', 'it': 'Impeccabile', 'pt': 'Perfeito', 'ja': 'ノーミス', 'zh': '无失误', 'ko': '노 미스'
    },
    'ach_no_mistakes_desc': {
        'tr': 'Daily Challenge: No Mistakes görevini tamamla', 'en': 'Complete Daily Challenge: No Mistakes', 'de': 'Tägliche Herausforderung: Keine Fehler abschließen', 'fr': 'Terminer le défi quotidien: Sans erreurs', 'es': 'Completa el desafío diario: Sin errores', 'it': 'Completa la sfida giornaliera: Senza errori', 'pt': 'Complete o desafio diário: Sem erros', 'ja': 'デイリーチャレンジ: ノーミスを達成', 'zh': '完成每日挑战：无失误', 'ko': '데일리 챌린지: 노 미스 완료'
    },
    
    # PvP başarıları
    'ach_pvp_first_win_name': {
        'tr': 'İlk Zafer', 'en': 'First Victory', 'de': 'Erster Sieg', 'fr': 'Première victoire', 'es': 'Primera victoria', 'it': 'Prima vittoria', 'pt': 'Primeira vitória', 'ja': '初勝利', 'zh': '首胜', 'ko': '첫 승리'
    },
    'ach_pvp_first_win_desc': {
        'tr': 'PvP\'de ilk galibiyetini al', 'en': 'Get your first PvP win', 'de': 'Hole deinen ersten PvP-Sieg', 'fr': 'Remporte ta première victoire PvP', 'es': 'Consigue tu primera victoria PvP', 'it': 'Ottieni la tua prima vittoria PvP', 'pt': 'Consiga sua primeira vitória PvP', 'ja': 'PvPで初勝利を得る', 'zh': '在 PvP 中获得首胜', 'ko': 'PvP 첫 승리'
    },
    'ach_pvp_10_wins_name': {
        'tr': 'Savaşçı', 'en': 'Warrior', 'de': 'Krieger', 'fr': 'Guerrier', 'es': 'Guerrero', 'it': 'Guerriero', 'pt': 'Guerreiro', 'ja': '戦士', 'zh': '战士', 'ko': '전사'
    },
    'ach_pvp_10_wins_desc': {
        'tr': 'PvP\'de 10 galibiyet', 'en': '10 PvP wins', 'de': '10 PvP-Siege', 'fr': '10 victoires PvP', 'es': '10 victorias PvP', 'it': '10 vittorie PvP', 'pt': '10 vitórias PvP', 'ja': 'PvPで10勝', 'zh': 'PvP 10 场胜利', 'ko': 'PvP 10승'
    },
    
    # Genel achievement UI çevirileri
    'ach_unlocked': {
        'tr': 'Başarı Açıldı!', 'en': 'Achievement Unlocked!', 'de': 'Erfolg freigeschaltet!', 'fr': 'Succès débloqué !', 'es': '¡Logro desbloqueado!', 'it': 'Obiettivo sbloccato!', 'pt': 'Conquista desbloqueada!', 'ja': '実績解除！', 'zh': '成就解锁！', 'ko': '업적 해제!'
    },
    'ach_progress': {
        'tr': 'İlerleme', 'en': 'Progress', 'de': 'Fortschritt', 'fr': 'Progression', 'es': 'Progreso', 'it': 'Progresso', 'pt': 'Progresso', 'ja': '進行', 'zh': '进度', 'ko': '진행'
    },
    'ach_progress_format': {
        'tr': 'İlerleme: {current}/{target} (%{percent})',
        'en': 'Progress: {current}/{target} ({percent}%)',
        'de': 'Fortschritt: {current}/{target} ({percent}%)',
        'fr': 'Progression : {current}/{target} ({percent}%)',
        'es': 'Progreso: {current}/{target} ({percent}%)',
        'zh': '进度：{current}/{target}（{percent}%）',
        'ko': '진행: {current}/{target} ({percent}%)',
        'it': 'Progresso: {current}/{target} ({percent}%)',
        'pt': 'Progresso: {current}/{target} ({percent}%)',
        'ja': '進行: {current}/{target} ({percent}%)'
    },
    'ach_progress_unknown': {
        'tr': 'İlerleme: -',
        'en': 'Progress: -',
        'de': 'Fortschritt: -',
        'fr': 'Progression : -',
        'es': 'Progreso: -',
        'it': 'Progresso: -',
        'pt': 'Progresso: -',
        'ja': '進行: -',
        'zh': '进度：-',
        'ko': '진행: -'
    },
    'ach_completed': {
        'tr': 'Tamamlandı', 'en': 'Completed', 'de': 'Abgeschlossen', 'fr': 'Terminé', 'es': 'Completado', 'it': 'Completato', 'pt': 'Concluído', 'ja': '完了', 'zh': '已完成', 'ko': '완료'
    },
    'ach_not_completed': {
        'tr': 'Tamamlanmadı', 'en': 'Not Completed', 'de': 'Nicht abgeschlossen', 'fr': 'Non terminé', 'es': 'No completado', 'it': 'Non completato', 'pt': 'Não concluído', 'ja': '未完了', 'zh': '未完成', 'ko': '미완료'
    },
    'ach_achievements': {
        'tr': 'Başarılar', 'en': 'Achievements', 'de': 'Erfolge', 'fr': 'Succès', 'es': 'Logros', 'it': 'Obiettivi', 'pt': 'Conquistas', 'ja': '実績', 'zh': '成就', 'ko': '업적'
    },
    
    # ========== SPLASH SCREEN & TIMER ÇEVİRİLERİ ==========
    'splash_press_enter': {
        'tr': 'Devam etmek için Enter basın', 'en': 'Press Enter to continue', 'de': 'Drücken Sie Enter zum Fortfahren', 'fr': 'Appuyez sur Entrée pour continuer', 'es': 'Presione Enter para continuar', 'it': 'Premi Invio per continuare', 'pt': 'Pressione Enter para continuar', 'ja': '続行するにはEnterを押してください', 'zh': '按 Enter 继续', 'ko': '계속하려면 Enter를 누르세요'
    },
    'timer_start': {
        'tr': 'Başlat (R)', 'en': 'Start (R)', 'de': 'Start (R)', 'fr': 'Démarrer (R)', 'es': 'Iniciar (R)', 'it': 'Avvia (R)', 'pt': 'Iniciar (R)', 'ja': '開始 (R)', 'zh': '开始 (R)', 'ko': '시작 (R)'
    },
    'timer_stop': {
        'tr': 'Durdur (R)', 'en': 'Stop (R)', 'de': 'Stopp (R)', 'fr': 'Arrêter (R)', 'es': 'Detener (R)', 'it': 'Ferma (R)', 'pt': 'Parar (R)', 'ja': '停止 (R)', 'zh': '停止 (R)', 'ko': '정지 (R)'
    },
    'timer_reset': {
        'tr': 'Sıfırla (Z)', 'en': 'Reset (Z)', 'de': 'Zurücksetzen (Z)', 'fr': 'Réinitialiser (Z)', 'es': 'Reiniciar (Z)', 'it': 'Reimposta (Z)', 'pt': 'Reiniciar (Z)', 'ja': 'リセット (Z)', 'zh': '重置 (Z)', 'ko': '초기화 (Z)'
    },
    'timer_close': {
        'tr': 'Kapat (Esc)', 'en': 'Close (Esc)', 'de': 'Schließen (Esc)', 'fr': 'Fermer (Esc)', 'es': 'Cerrar (Esc)', 'it': 'Chiudi (Esc)', 'pt': 'Fechar (Esc)', 'ja': '閉じる (Esc)', 'zh': '关闭 (Esc)', 'ko': '닫기 (Esc)'
    },
    'timer_pause': {
        'tr': 'Duraklat (Space)', 'en': 'Pause (Space)', 'de': 'Pause (Space)', 'fr': 'Pause (Espace)', 'es': 'Pausar (Espacio)', 'it': 'Pausa (Spazio)', 'pt': 'Pausar (Espaço)', 'ja': '一時停止 (Space)', 'zh': '暂停 (Space)', 'ko': '일시정지 (Space)'
    },
    'timer_resume': {
        'tr': 'Devam (Space)', 'en': 'Resume (Space)', 'de': 'Fortsetzen (Space)', 'fr': 'Reprendre (Espace)', 'es': 'Reanudar (Espacio)', 'it': 'Riprendi (Spazio)', 'pt': 'Continuar (Espaço)', 'ja': '再開 (Space)', 'zh': '继续 (Space)', 'ko': '재개 (Space)'
    },
    
    # ========== KART SEÇİMİ ÇEVİRİLERİ ==========
    'card_skip_selection': {
        'tr': 'Kart almadan devam et', 'en': 'Continue without card', 'de': 'Ohne Karte fortfahren', 'fr': 'Continuer sans carte', 'es': 'Continuar sin carta', 'it': 'Continua senza carta', 'pt': 'Continuar sem carta', 'ja': 'カードなしで続ける', 'zh': '不选卡继续', 'ko': '카드 없이 계속'
    },
    'card_choose': {
        'tr': 'Kart Seç', 'en': 'Choose Card', 'de': 'Karte wählen', 'fr': 'Choisir carte', 'es': 'Elegir carta', 'it': 'Scegli carta', 'pt': 'Escolher carta', 'ja': 'カードを選択', 'zh': '选择卡牌', 'ko': '카드 선택'
    },
    'card_level_up': {
        'tr': 'Seviye Atladın!', 'en': 'Level Up!', 'de': 'Level aufgestiegen!', 'fr': 'Niveau supérieur !', 'es': '¡Subiste de nivel!', 'it': 'Livello aumentato!', 'pt': 'Subiu de nível!', 'ja': 'レベルアップ！', 'zh': '升级了！', 'ko': '레벨 업!'
    },
    
    # ========== AVATAR EDITOR ÇEVİRİLERİ ==========
    'avatar_select_image': {
        'tr': 'Avatar Resmi Seç', 'en': 'Select Avatar Image', 'de': 'Avatar-Bild auswählen', 'fr': 'Sélectionner image avatar', 'es': 'Seleccionar imagen de avatar', 'it': 'Seleziona immagine avatar', 'pt': 'Selecionar imagem do avatar', 'ja': 'アバター画像を選択', 'zh': '选择头像图片', 'ko': '아바타 이미지 선택'
    },
    'avatar_image_files': {
        'tr': 'Resim Dosyaları', 'en': 'Image Files', 'de': 'Bilddateien', 'fr': 'Fichiers image', 'es': 'Archivos de imagen', 'it': 'File immagine', 'pt': 'Arquivos de imagem', 'ja': '画像ファイル', 'zh': '图片文件', 'ko': '이미지 파일'
    },
    'avatar_all_files': {
        'tr': 'Tüm Dosyalar', 'en': 'All Files', 'de': 'Alle Dateien', 'fr': 'Tous les fichiers', 'es': 'Todos los archivos', 'it': 'Tutti i file', 'pt': 'Todos os arquivos', 'ja': 'すべてのファイル', 'zh': '所有文件', 'ko': '모든 파일'
    },
    'avatar_edit_title': {
        'tr': 'Avatar Resmi Düzenle', 'en': 'Edit Avatar Image', 'de': 'Avatar-Bild bearbeiten', 'fr': 'Modifier image avatar', 'es': 'Editar imagen de avatar', 'it': 'Modifica immagine avatar', 'pt': 'Editar imagem do avatar', 'ja': 'アバター画像を編集', 'zh': '编辑头像图片', 'ko': '아바타 이미지 편집'
    },
    'avatar_preview': {
        'tr': 'Önizleme', 'en': 'Preview', 'de': 'Vorschau', 'fr': 'Aperçu', 'es': 'Vista previa', 'it': 'Anteprima', 'pt': 'Pré-visualização', 'ja': 'プレビュー', 'zh': '预览', 'ko': '미리보기'
    },
    'avatar_no_image_selected': {
        'tr': 'Henüz resim seçilmedi', 'en': 'No image selected yet', 'de': 'Noch kein Bild ausgewählt', 'fr': 'Aucune image sélectionnée', 'es': 'Ninguna imagen seleccionada', 'it': 'Nessuna immagine selezionata', 'pt': 'Nenhuma imagem selecionada', 'ja': 'まだ画像が選択されていません', 'zh': '尚未选择图片', 'ko': '아직 이미지가 선택되지 않았습니다'
    },
    'avatar_press_s': {
        'tr': 'S tuşuna basarak veya', 'en': 'Press S key or', 'de': 'Drücke S-Taste oder', 'fr': 'Appuyez sur S ou', 'es': 'Presione S o', 'it': 'Premi S oppure', 'pt': 'Pressione S ou', 'ja': 'Sキーを押すか', 'zh': '按 S 键或', 'ko': 'S 키를 누르거나'
    },
    'avatar_select_file': {
        'tr': 'bir resim dosyası seçin', 'en': 'select an image file', 'de': 'wähle eine Bilddatei', 'fr': 'sélectionnez un fichier image', 'es': 'seleccione un archivo de imagen', 'it': 'seleziona un file immagine', 'pt': 'selecione um arquivo de imagem', 'ja': '画像ファイルを選択', 'zh': '选择一张图片文件', 'ko': '이미지 파일을 선택하세요'
    },
    'avatar_key_select': {
        'tr': 'Seç', 'en': 'Select', 'de': 'Auswählen', 'fr': 'Sélectionner', 'es': 'Seleccionar', 'it': 'Seleziona', 'pt': 'Selecionar', 'ja': '選択', 'zh': '选择', 'ko': '선택'
    },
    'avatar_key_move': {
        'tr': 'Kare Taşı', 'en': 'Move Box', 'de': 'Rahmen verschieben', 'fr': 'Déplacer cadre', 'es': 'Mover marco', 'it': 'Sposta riquadro', 'pt': 'Mover caixa', 'ja': '枠を移動', 'zh': '移动框', 'ko': '박스 이동'
    },
    'avatar_key_size': {
        'tr': 'Boyut', 'en': 'Size', 'de': 'Größe', 'fr': 'Taille', 'es': 'Tamaño', 'it': 'Dimensione', 'pt': 'Tamanho', 'ja': 'サイズ', 'zh': '大小', 'ko': '크기'
    },
    'avatar_key_drag': {
        'tr': 'Taşı/Boyutlandır', 'en': 'Move/Resize', 'de': 'Verschieben/Größe', 'fr': 'Déplacer/Redimensionner', 'es': 'Mover/Redimensionar', 'it': 'Sposta/Ridimensiona', 'pt': 'Mover/Redimensionar', 'ja': '移動/サイズ変更', 'zh': '移动/缩放', 'ko': '이동/크기 조절'
    },
    'avatar_key_save': {
        'tr': 'Kaydet', 'en': 'Save', 'de': 'Speichern', 'fr': 'Enregistrer', 'es': 'Guardar', 'it': 'Salva', 'pt': 'Salvar', 'ja': '保存', 'zh': '保存', 'ko': '저장'
    },
    'avatar_key_cancel': {
        'tr': 'İptal', 'en': 'Cancel', 'de': 'Abbrechen', 'fr': 'Annuler', 'es': 'Cancelar', 'it': 'Annulla', 'pt': 'Cancelar', 'ja': 'キャンセル', 'zh': '取消', 'ko': '취소'
    },
    
    # ========== MENÜ ORTAK ÇEVİRİLERİ ==========
    'menu_yes_exit': {
        'tr': 'Evet, çık', 'en': 'Yes, exit', 'de': 'Ja, beenden', 'fr': 'Oui, quitter', 'es': 'Sí, salir', 'it': 'Sì, esci', 'pt': 'Sim, sair', 'ja': 'はい、終了', 'zh': '是，退出', 'ko': '예, 종료'
    },
    'menu_hint_select': {
        'tr': 'Seç: Mouse ile tıkla veya klavyeyi kullan', 'en': 'Select: Click with mouse or use keyboard', 'de': 'Auswahl: Mit Maus klicken oder Tastatur benutzen', 'fr': 'Sélection: Cliquez avec la souris ou utilisez le clavier', 'es': 'Seleccionar: Haz clic con el ratón o usa el teclado', 'it': 'Seleziona: Clicca col mouse o usa la tastiera', 'pt': 'Selecionar: Clique com o mouse ou use o teclado', 'ja': '選択: マウスでクリックまたはキーボード', 'zh': '选择：鼠标点击或使用键盘', 'ko': '선택: 마우스로 클릭하거나 키보드 사용'
    },
    'menu_back': {
        'tr': 'Geri', 'en': 'Back', 'de': 'Zurück', 'fr': 'Retour', 'es': 'Atrás', 'it': 'Indietro', 'pt': 'Voltar', 'ja': '戻る', 'zh': '返回', 'ko': '뒤로'
    },
    'menu_key_reset': {
        'tr': 'Seçili tuş varsayılana döndü', 'en': 'Selected key reset to default', 'de': 'Ausgewählte Taste auf Standard zurückgesetzt', 'fr': 'Touche sélectionnée remise par défaut', 'es': 'Tecla seleccionada restablecida', 'it': 'Tasto selezionato ripristinato', 'pt': 'Tecla selecionada redefinida', 'ja': '選択したキーをデフォルトに戻しました', 'zh': '已将选中按键重置为默认', 'ko': '선택한 키를 기본값으로 재설정했습니다'
    },
    'menu_achievements_progress': {
        'tr': '{count}/{total} başarı açıldı - %{percent}', 'en': '{count}/{total} achievements unlocked - {percent}%', 'de': '{count}/{total} Erfolge freigeschaltet - {percent}%', 'fr': '{count}/{total} succès débloqués - {percent}%', 'es': '{count}/{total} logros desbloqueados - {percent}%', 'it': '{count}/{total} obiettivi sbloccati - {percent}%', 'pt': '{count}/{total} conquistas desbloqueadas - {percent}%', 'ja': '{count}/{total} 実績解除 - {percent}%', 'zh': '{count}/{total} 成就已解锁 - {percent}%', 'ko': '{count}/{total} 업적 해제 - {percent}%'
    },
    'menu_dashboard_daily_fallback': {
        'tr': 'Bugünün görevini tamamla', 'en': "Complete today's challenge", 'de': 'Schließe die heutige Herausforderung ab', 'fr': "Termine le défi d'aujourd'hui", 'es': 'Completa el desafío de hoy', 'it': 'Completa la sfida di oggi', 'pt': 'Complete o desafio de hoje', 'ja': '今日のチャレンジをクリアしよう', 'zh': '完成今日挑战', 'ko': '오늘의 도전을 완료하세요'
    },
    'menu_dashboard_no_achievements': {
        'tr': 'Henüz başarım yok', 'en': 'No achievements yet', 'de': 'Noch keine Erfolge', 'fr': 'Aucun succès pour le moment', 'es': 'Aún no hay logros', 'it': 'Nessun obiettivo ancora', 'pt': 'Ainda não há conquistas', 'ja': 'まだ実績がありません', 'zh': '尚无成就', 'ko': '아직 업적이 없습니다'
    },
    'menu_dashboard_completion_percent': {
        'tr': 'Tamamlanma %{percent}', 'en': 'Completion {percent}%', 'de': 'Fortschritt {percent}%', 'fr': 'Progression {percent}%', 'es': 'Progreso {percent}%', 'it': 'Completamento {percent}%', 'pt': 'Conclusão {percent}%', 'ja': '達成率 {percent}%', 'zh': '完成度 {percent}%', 'ko': '완료율 {percent}%'
    },
    'menu_dashboard_campaign_levels': {
        'tr': 'Son: Lv {last}  ·  Sıradaki: Lv {next}', 'en': 'Last: Lv {last}  ·  Next: Lv {next}', 'de': 'Zuletzt: Lv {last}  ·  Nächste: Lv {next}', 'fr': 'Dernier : Nv {last}  ·  Suivant : Nv {next}', 'es': 'Último: Nv {last}  ·  Siguiente: Nv {next}', 'it': 'Ultimo: Lv {last}  ·  Prossimo: Lv {next}', 'pt': 'Último: Nv {last}  ·  Próximo: Nv {next}', 'ja': '前回: Lv {last}  ·  次: Lv {next}', 'zh': '上次：Lv {last}  ·  下一个：Lv {next}', 'ko': '최근: Lv {last}  ·  다음: Lv {next}'
    },
    'menu_dashboard_campaign_level_single': {
        'tr': 'Lv {level}', 'en': 'Lv {level}', 'de': 'Lv {level}', 'fr': 'Nv {level}', 'es': 'Nv {level}', 'it': 'Lv {level}', 'pt': 'Nv {level}', 'ja': 'Lv {level}', 'zh': 'Lv {level}', 'ko': 'Lv {level}'
    },
    'menu_header_subtitle': {
        'tr': 'Rahat olun ve eksiklikleri sağ üstten belirtin.', 'en': 'Relax and report any issues from the top-right.', 'de': 'Bleib entspannt und melde Probleme oben rechts.', 'fr': 'Restez zen et signalez les problèmes en haut à droite.', 'es': 'Relájate y reporta problemas desde la esquina superior derecha.', 'it': 'Rilassati e segnala eventuali problemi dall’angolo in alto a destra.', 'pt': 'Relaxe e informe problemas no canto superior direito.', 'ja': '落ち着いて、問題は右上から報告してください。', 'zh': '放轻松，如有问题请从右上角反馈。', 'ko': '편하게 즐기고, 문제는 오른쪽 상단에서 알려주세요.'
    },
    'menu_dashboard_quick_continue': {
        'tr': 'Hızlı Devam', 'en': 'Quick Continue', 'de': 'Schnell fortsetzen', 'fr': 'Reprise rapide', 'es': 'Continuar rápido', 'it': 'Continua rapido', 'pt': 'Continuar rápido', 'ja': 'クイック続行', 'zh': '快速继续', 'ko': '빠른 계속'
    },
    'menu_dashboard_campaign_title': {
        'tr': 'Görev Modu', 'en': 'Campaign Mode', 'de': 'Kampagnenmodus', 'fr': 'Mode Campagne', 'es': 'Modo Campaña', 'it': 'Modalità Campagna', 'pt': 'Modo Campanha', 'ja': 'キャンペーンモード', 'zh': '战役模式', 'ko': '캠페인 모드'
    },
    'menu_dashboard_pvp_title': {
        'tr': 'Online PvP\nCo-op', 'en': 'Online PvP\nCo-op', 'de': 'Online PvP\nCo-op', 'fr': 'PvP en ligne\nCo-op', 'es': 'PvP Online\nCo-op', 'it': 'PvP Online\nCo-op', 'pt': 'PvP Online\nCo-op', 'ja': 'オンラインPvP\n協力', 'zh': '在线 PvP\n合作', 'ko': '온라인 PvP\n협동'
    },
    'menu_dashboard_sub_new_gen_tetris': {
        'tr': 'Kart kombinleriyle puanını katla', 'en': 'Boost score with card combos', 'de': 'Steigere deine Punkte mit Kartenkombos', 'fr': 'Augmente ton score avec des combos de cartes', 'es': 'Aumenta tu puntaje con combos de cartas', 'it': 'Aumenta il punteggio con combo di carte', 'pt': 'Aumente a pontuação com combos de cartas', 'ja': 'カードコンボでスコアを伸ばそう', 'zh': '用卡牌连携提升分数', 'ko': '카드 콤보로 점수를 올리세요'
    },
    'menu_dashboard_sub_daily_challenge': {
        'tr': 'Bugünün görevini tamamla', 'en': "Complete today's challenge", 'de': 'Schließe die heutige Herausforderung ab', 'fr': "Termine le défi d'aujourd'hui", 'es': 'Completa el desafío de hoy', 'it': 'Completa la sfida di oggi', 'pt': 'Complete o desafio de hoje', 'ja': '今日のチャレンジをクリアしよう', 'zh': '完成今日挑战', 'ko': '오늘의 도전을 완료하세요'
    },
    'menu_dashboard_sub_piece_workshop': {
        'tr': 'Özel parçaları üret ve kaydet', 'en': 'Build and save custom pieces', 'de': 'Erstelle und speichere eigene Teile', 'fr': 'Crée et enregistre des pièces personnalisées', 'es': 'Crea y guarda piezas personalizadas', 'it': 'Crea e salva pezzi personalizzati', 'pt': 'Crie e salve peças personalizadas', 'ja': 'カスタムピースを作成して保存', 'zh': '创建并保存自定义方块', 'ko': '커스텀 조각을 만들고 저장하세요'
    },
    'menu_dashboard_sub_campaign_mode': {
        'tr': 'Görev zincirinde ilerle', 'en': 'Advance through missions', 'de': 'Schreite durch Missionen voran', 'fr': 'Progresse à travers les missions', 'es': 'Avanza a través de misiones', 'it': 'Avanza nelle missioni', 'pt': 'Avance pelas missões', 'ja': 'ミッションを進めよう', 'zh': '推进任务进度', 'ko': '미션을 진행하세요'
    },
    'menu_dashboard_sub_extras': {
        'tr': 'Ekstra oyun modlarını keşfet', 'en': 'Discover extra game modes', 'de': 'Entdecke zusätzliche Spielmodi', 'fr': 'Découvre des modes de jeu supplémentaires', 'es': 'Descubre modos de juego extra', 'it': 'Scopri modalità di gioco extra', 'pt': 'Descubra modos de jogo extras', 'ja': '追加ゲームモードを発見しよう', 'zh': '探索额外游戏模式', 'ko': '추가 게임 모드를 탐색하세요'
    },
    'menu_dashboard_sub_block_styles': {
        'tr': 'Bloklarını tema ve stille özelleştir', 'en': 'Customize block theme and style', 'de': 'Passe Block-Thema und Stil an', 'fr': 'Personnalise le thème et le style des blocs', 'es': 'Personaliza el tema y estilo de bloques', 'it': 'Personalizza tema e stile dei blocchi', 'pt': 'Personalize tema e estilo dos blocos', 'ja': 'ブロックのテーマとスタイルをカスタマイズ', 'zh': '自定义方块主题与风格', 'ko': '블록 테마와 스타일을 꾸미세요'
    },
    'menu_dashboard_sub_pvp': {
        'tr': 'Online & Co-op yakında', 'en': 'Online & Co-op coming soon', 'de': 'Online & Co-op bald verfügbar', 'fr': 'Online & Co-op bientôt', 'es': 'Online y Co-op próximamente', 'it': 'Online e Co-op in arrivo', 'pt': 'Online e Co-op em breve', 'ja': 'オンライン＆協力は近日公開', 'zh': '在线与合作即将推出', 'ko': '온라인 & 협동 모드 곧 출시'
    },
    'menu_dashboard_sub_tutorial': {
        'tr': 'Gir ve öğren!', 'en': 'Jump in and learn!', 'de': 'Starte und lerne!', 'fr': 'Lance-toi et apprends !', 'es': '¡Entra y aprende!', 'it': 'Entra e impara!', 'pt': 'Entre e aprenda!', 'ja': '始めて学ぼう！', 'zh': '马上上手并学习！', 'ko': '바로 시작하고 배워보세요!'
    },
    'menu_lb_error_config_missing': {
        'tr': 'LEADERBOARD_BACKEND_URL veya STEAM_APP_ID/STEAM_WEB_API_KEY tanımlı değil.', 'en': 'LEADERBOARD_BACKEND_URL or STEAM_APP_ID/STEAM_WEB_API_KEY is not configured.', 'de': 'LEADERBOARD_BACKEND_URL oder STEAM_APP_ID/STEAM_WEB_API_KEY ist nicht konfiguriert.', 'fr': 'LEADERBOARD_BACKEND_URL ou STEAM_APP_ID/STEAM_WEB_API_KEY n’est pas configuré.', 'es': 'LEADERBOARD_BACKEND_URL o STEAM_APP_ID/STEAM_WEB_API_KEY no está configurado.', 'it': 'LEADERBOARD_BACKEND_URL o STEAM_APP_ID/STEAM_WEB_API_KEY non configurato.', 'pt': 'LEADERBOARD_BACKEND_URL ou STEAM_APP_ID/STEAM_WEB_API_KEY não configurado.', 'ja': 'LEADERBOARD_BACKEND_URL または STEAM_APP_ID/STEAM_WEB_API_KEY が未設定です。', 'zh': '未配置 LEADERBOARD_BACKEND_URL 或 STEAM_APP_ID/STEAM_WEB_API_KEY。', 'ko': 'LEADERBOARD_BACKEND_URL 또는 STEAM_APP_ID/STEAM_WEB_API_KEY가 설정되지 않았습니다.'
    },
    'menu_lb_loading': {
        'tr': 'Steam skorları yükleniyor...', 'en': 'Loading Steam scores...', 'de': 'Steam-Punkte werden geladen...', 'fr': 'Chargement des scores Steam...', 'es': 'Cargando puntuaciones de Steam...', 'it': 'Caricamento punteggi Steam...', 'pt': 'Carregando pontuações da Steam...', 'ja': 'Steamスコアを読み込み中...', 'zh': '正在加载 Steam 分数...', 'ko': 'Steam 점수를 불러오는 중...'
    },
    'menu_lb_error_friends_auth': {
        'tr': 'Arkadaş skorları için oturum doğrulaması gerekli.', 'en': 'Session authentication is required for friends scores.', 'de': 'Für Freundeswerte ist eine Sitzungsanmeldung erforderlich.', 'fr': 'Une authentification de session est requise pour les scores amis.', 'es': 'Se requiere autenticación de sesión para las puntuaciones de amigos.', 'it': 'Autenticazione sessione necessaria per i punteggi amici.', 'pt': 'Autenticação de sessão necessária para pontuações de amigos.', 'ja': 'フレンドスコアにはセッション認証が必要です。', 'zh': '好友分数需要会话认证。', 'ko': '친구 점수에는 세션 인증이 필요합니다.'
    },
    'menu_lb_error_global_missing': {
        'tr': 'Global skor bulunamadı.', 'en': 'Global scores not found.', 'de': 'Globale Punkte nicht gefunden.', 'fr': 'Scores globaux introuvables.', 'es': 'No se encontraron puntuaciones globales.', 'it': 'Punteggi globali non trovati.', 'pt': 'Pontuações globais não encontradas.', 'ja': 'グローバルスコアが見つかりません。', 'zh': '未找到全球分数。', 'ko': '글로벌 점수를 찾을 수 없습니다.'
    },
    'menu_lb_error_fetch_failed': {
        'tr': 'Steam skorları alınamadı: {error}', 'en': 'Failed to fetch Steam scores: {error}', 'de': 'Steam-Punkte konnten nicht abgerufen werden: {error}', 'fr': 'Impossible de récupérer les scores Steam : {error}', 'es': 'No se pudieron obtener las puntuaciones de Steam: {error}', 'it': 'Impossibile recuperare i punteggi Steam: {error}', 'pt': 'Falha ao buscar pontuações Steam: {error}', 'ja': 'Steamスコアの取得に失敗しました: {error}', 'zh': '获取 Steam 分数失败：{error}', 'ko': 'Steam 점수를 가져오지 못했습니다: {error}'
    },
    'steam_lb_submit_no_license': {
        'tr': 'Skor kaydedilemedi: Steam hesabınızda bu oyunun lisansı yok. Oyunu Steam üzerinden edinin.',
        'en': 'Score not saved: Your Steam account does not own a license for this game. Please acquire the game on Steam.',
        'de': 'Punktzahl nicht gespeichert: Dein Steam-Konto hat keine Lizenz für dieses Spiel.',
        'fr': "Score non enregistré : Votre compte Steam n'a pas de licence pour ce jeu.",
        'es': 'Puntuación no guardada: Tu cuenta de Steam no tiene licencia para este juego.',
        'it': 'Punteggio non salvato: Il tuo account Steam non ha una licenza per questo gioco.',
        'pt': 'Pontuação não salva: Sua conta Steam não possui licença para este jogo.',
        'ja': 'スコアは保存されませんでした：Steamアカウントにこのゲームのライセンスがありません。',
        'zh': '分数未保存：您的 Steam 账户没有此游戏的许可证。',
        'ko': '점수가 저장되지 않았습니다: Steam 계정에 이 게임의 라이선스가 없습니다.',
    },
    'steam_lb_submit_steam_closed': {
        'tr': 'Skor kaydedilemedi: Steam çalışmıyor. Skoru görmek için Steam açık olmalı.',
        'en': 'Score not saved: Steam is not running. Open Steam to see your score on the leaderboard.',
        'de': 'Punktzahl nicht gespeichert: Steam läuft nicht.',
        'fr': "Score non enregistré : Steam n'est pas en cours d'exécution.",
        'es': 'Puntuación no guardada: Steam no está en ejecución.',
        'it': 'Punteggio non salvato: Steam non è in esecuzione.',
        'pt': 'Pontuação não salva: Steam não está em execução.',
        'ja': 'スコアは保存されませんでした：Steamが起動していません。',
        'zh': '分数未保存：Steam 未运行。',
        'ko': '점수가 저장되지 않았습니다: Steam이 실행중이지 않습니다.',
    },
    'steam_lb_submit_ok': {
        'tr': 'Skor Steam liderlik tablosuna kaydedildi! Sıralaman: #{rank}',
        'en': 'Score saved to Steam leaderboard! Your rank: #{rank}',
        'de': 'Punktzahl in Steam-Bestenliste gespeichert! Deine Platzierung: #{rank}',
        'fr': 'Score enregistré dans le classement Steam ! Ton classement : #{rank}',
        'es': '¡Puntuación guardada en la tabla de clasificación de Steam! Tu posición: #{rank}',
        'it': 'Punteggio salvato nella classifica Steam! Il tuo rango: #{rank}',
        'pt': 'Pontuação salva no placar Steam! Sua classificação: #{rank}',
        'ja': 'スコアがSteamランキングに保存されました！あなたのランク: #{rank}',
        'zh': '分数已保存到 Steam 排行榜！您的排名：#{rank}',
        'ko': 'Steam 리더보드에 점수가 저장되었습니다! 당신의 순위: #{rank}',
    },
    'menu_lb_title': {
        'tr': 'Skorlar', 'en': 'Scores', 'de': 'Punkte', 'fr': 'Scores', 'es': 'Puntuaciones', 'it': 'Punteggi', 'pt': 'Pontuações', 'ja': 'スコア', 'zh': '分数', 'ko': '점수'
    },
    'menu_lb_subtitle': {
        'tr': 'Kart Ustalığı (Steam)', 'en': 'Card Mastery (Steam)', 'de': 'Card Mastery (Steam)', 'fr': 'Maîtrise des cartes (Steam)', 'es': 'Dominio de cartas (Steam)', 'it': 'Maestria carte (Steam)', 'pt': 'Domínio de cartas (Steam)', 'ja': 'カードマスタリー（Steam）', 'zh': '卡牌大师（Steam）', 'ko': '카드 마스터리 (Steam)'
    },
    'menu_lb_tab_global': {
        'tr': 'Global', 'en': 'Global', 'de': 'Global', 'fr': 'Global', 'es': 'Global', 'it': 'Globale', 'pt': 'Global', 'ja': 'グローバル', 'zh': '全球', 'ko': '글로벌'
    },
    'menu_lb_tab_friends': {
        'tr': 'Arkadaşlar', 'en': 'Friends', 'de': 'Freunde', 'fr': 'Amis', 'es': 'Amigos', 'it': 'Amici', 'pt': 'Amigos', 'ja': 'フレンド', 'zh': '好友', 'ko': '친구'
    },
    'menu_lb_no_scores': {
        'tr': 'Skor bulunamadı.', 'en': 'No scores found.', 'de': 'Keine Punkte gefunden.', 'fr': 'Aucun score trouvé.', 'es': 'No se encontraron puntuaciones.', 'it': 'Nessun punteggio trovato.', 'pt': 'Nenhuma pontuação encontrada.', 'ja': 'スコアが見つかりません。', 'zh': '未找到分数。', 'ko': '점수를 찾을 수 없습니다.'
    },
    'menu_lb_unknown_user': {
        'tr': 'bilinmiyor', 'en': 'unknown', 'de': 'unbekannt', 'fr': 'inconnu', 'es': 'desconocido', 'it': 'sconosciuto', 'pt': 'desconhecido', 'ja': '不明', 'zh': '未知', 'ko': '알 수 없음'
    },
    'menu_gamepad_label': {
        'tr': 'Gamepad', 'en': 'Gamepad', 'de': 'Gamepad', 'fr': 'Manette', 'es': 'Gamepad', 'it': 'Gamepad', 'pt': 'Gamepad', 'ja': 'ゲームパッド', 'zh': '手柄', 'ko': '게임패드'
    },
    'menu_hint_enter_y': {
        'tr': 'ENTER / Y', 'en': 'ENTER / Y', 'de': 'ENTER / Y', 'fr': 'ENTRÉE / Y', 'es': 'ENTER / Y', 'it': 'INVIO / Y', 'pt': 'ENTER / Y', 'ja': 'ENTER / Y', 'zh': 'ENTER / Y', 'ko': 'ENTER / Y'
    },
    'menu_hint_esc_n': {
        'tr': 'ESC / N', 'en': 'ESC / N', 'de': 'ESC / N', 'fr': 'ESC / N', 'es': 'ESC / N', 'it': 'ESC / N', 'pt': 'ESC / N', 'ja': 'ESC / N', 'zh': 'ESC / N', 'ko': 'ESC / N'
    },
    'menu_theme_hint': {
        'tr': '↑ ↓: Seç  |  ENTER: Varsayılan  |  ← → / Tık: Liste  |  ESC: Geri', 'en': '↑ ↓: Select  |  ENTER: Default  |  ← → / Click: List  |  ESC: Back', 'de': '↑ ↓: Auswahl  |  ENTER: Standard  |  ← → / Klick: Liste  |  ESC: Zurück', 'fr': '↑ ↓: Sélection  |  ENTRÉE: Défaut  |  ← → / Clic: Liste  |  ESC: Retour', 'es': '↑ ↓: Seleccionar  |  ENTER: Predeterminado  |  ← → / Clic: Lista  |  ESC: Atrás', 'it': '↑ ↓: Seleziona  |  INVIO: Predefinito  |  ← → / Clic: Lista  |  ESC: Indietro', 'pt': '↑ ↓: Selecionar  |  ENTER: Padrão  |  ← → / Clique: Lista  |  ESC: Voltar'
        , 'ja': '↑ ↓: 選択  |  ENTER: デフォルト  |  ← → / クリック: リスト  |  ESC: 戻る', 'zh': '↑ ↓：选择  |  ENTER：默认  |  ← → / 点击：列表  |  ESC：返回', 'ko': '↑ ↓: 선택  |  ENTER: 기본  |  ← → / 클릭: 목록  |  ESC: 뒤로'
    },
    'menu_music_select': {
        'tr': 'MÜZİK SEÇ', 'en': 'SELECT MUSIC', 'de': 'MUSIK AUSWÄHLEN', 'fr': 'SÉLECTIONNER MUSIQUE', 'es': 'SELECCIONAR MÚSICA', 'it': 'SELEZIONA MUSICA', 'pt': 'SELECIONAR MÚSICA', 'ja': '音楽を選択', 'zh': '选择音乐', 'ko': '음악 선택'
    },
    'menu_music_hint': {
        'tr': '↑ ↓: Seç  |  ENTER: Uygula  |  ESC / Dışa tık: Kapat  |  R: Yenile', 'en': '↑ ↓: Select  |  ENTER: Apply  |  ESC / Click outside: Close  |  R: Refresh', 'de': '↑ ↓: Auswahl  |  ENTER: Anwenden  |  ESC / Außen klicken: Schließen  |  R: Aktualisieren', 'fr': '↑ ↓: Sélection  |  ENTRÉE: Appliquer  |  ESC / Clic extérieur: Fermer  |  R: Actualiser', 'es': '↑ ↓: Seleccionar  |  ENTER: Aplicar  |  ESC / Clic fuera: Cerrar  |  R: Actualizar', 'it': '↑ ↓: Seleziona  |  INVIO: Applica  |  ESC / Clic esterno: Chiudi  |  R: Aggiorna', 'pt': '↑ ↓: Selecionar  |  ENTER: Aplicar  |  ESC / Clique fora: Fechar  |  R: Atualizar'
        , 'ja': '↑ ↓: 選択  |  ENTER: 適用  |  ESC / 外側クリック: 閉じる  |  R: 更新', 'zh': '↑ ↓：选择  |  ENTER：应用  |  ESC / 点击外部：关闭  |  R：刷新', 'ko': '↑ ↓: 선택  |  ENTER: 적용  |  ESC / 바깥 클릭: 닫기  |  R: 새로고침'
    },
    'play': {
        'tr': 'Oyna', 'en': 'Play', 'de': 'Spielen', 'fr': 'Jouer', 'es': 'Jugar', 'it': 'Gioca', 'pt': 'Jogar', 'ja': 'プレイ', 'zh': '开始', 'ko': '플레이'
    },
    
    # ========== GRAFİK AYARLARI ÇEVİRİLERİ ==========
    'graphics_settings': {
        'tr': 'GRAFİK AYARLARI', 'en': 'GRAPHICS SETTINGS', 'de': 'GRAFIKEINSTELLUNGEN', 'fr': 'PARAMÈTRES GRAPHIQUES', 'es': 'AJUSTES GRÁFICOS', 'it': 'IMPOSTAZIONI GRAFICHE', 'pt': 'CONFIGURAÇÕES GRÁFICAS', 'ja': 'グラフィック設定', 'zh': '图形设置', 'ko': '그래픽 설정'
    },
    'window_mode': {
        'tr': 'Pencere Modu', 'en': 'Window Mode', 'de': 'Fenstermodus', 'fr': 'Mode fenêtre', 'es': 'Modo ventana', 'it': 'Modalità finestra', 'pt': 'Modo janela', 'ja': 'ウィンドウモード', 'zh': '窗口模式', 'ko': '창 모드'
    },
    'resolution': {
        'tr': 'Pencere Boyutu', 'en': 'Window Size', 'de': 'Fenstergröße', 'fr': 'Taille de fenêtre', 'es': 'Tamaño de ventana', 'it': 'Dimensione finestra', 'pt': 'Tamanho da janela', 'ja': 'ウィンドウサイズ', 'zh': '窗口大小', 'ko': '창 크기'
    },
    'vsync': {
        'tr': 'VSync', 'en': 'VSync', 'de': 'VSync', 'fr': 'VSync', 'es': 'VSync', 'it': 'VSync', 'pt': 'VSync', 'ja': 'VSync', 'zh': '垂直同步', 'ko': '수직 동기화'
    },
    'fps_limit': {
        'tr': 'FPS Limiti', 'en': 'FPS Limit', 'de': 'FPS-Limit', 'fr': 'Limite FPS', 'es': 'Límite FPS', 'it': 'Limite FPS', 'pt': 'Limite FPS', 'ja': 'FPS制限', 'zh': 'FPS 限制', 'ko': 'FPS 제한'
    },
    'show_fps': {
        'tr': 'FPS Göster', 'en': 'Show FPS', 'de': 'FPS anzeigen', 'fr': 'Afficher FPS', 'es': 'Mostrar FPS', 'it': 'Mostra FPS', 'pt': 'Mostrar FPS', 'ja': 'FPS表示', 'zh': '显示 FPS', 'ko': 'FPS 표시'
    },
    'show_ghost': {
        'tr': 'Gölge Göster', 'en': 'Show Ghost', 'de': 'Schatten anzeigen', 'fr': 'Afficher fantôme', 'es': 'Mostrar sombra', 'it': 'Mostra ombra', 'pt': 'Mostrar fantasma', 'ja': 'ゴースト表示', 'zh': '显示幽灵', 'ko': '고스트 표시'
    },
    'show_background': {
        'tr': 'Arka Plan Göster', 'en': 'Show Background', 'de': 'Hintergrund anzeigen', 'fr': 'Afficher arrière-plan', 'es': 'Mostrar fondo', 'it': 'Mostra sfondo', 'pt': 'Mostrar fundo', 'ja': '背景表示', 'zh': '显示背景', 'ko': '배경 표시'
    },
    'bg_transparency': {
        'tr': 'Arka Plan Şeffaflığı', 'en': 'Background Transparency', 'de': 'Hintergrund-Transparenz', 'fr': 'Transparence arrière-plan', 'es': 'Transparencia del fondo', 'it': 'Trasparenza sfondo', 'pt': 'Transparência do fundo', 'ja': '背景の透明度', 'zh': '背景透明度', 'ko': '배경 투명도'
    },
    'menu_transparency': {
        'tr': 'Menü Şeffaflığı', 'en': 'Menu Transparency', 'de': 'Menü-Transparenz', 'fr': 'Transparence menu', 'es': 'Transparencia del menú', 'it': 'Trasparenza menu', 'pt': 'Transparência do menu', 'ja': 'メニューの透明度', 'zh': '菜单透明度', 'ko': '메뉴 투명도'
    },
    'particle_effects': {
        'tr': 'Parçacık Efektleri', 'en': 'Particle Effects', 'de': 'Partikeleffekte', 'fr': 'Effets de particules', 'es': 'Efectos de partículas', 'it': 'Effetti particelle', 'pt': 'Efeitos de partículas', 'ja': 'パーティクル効果', 'zh': '粒子效果', 'ko': '파티클 효과'
    },
    'not_available_short': {
        'tr': 'N/A', 'en': 'N/A', 'de': 'N/V', 'fr': 'N/D', 'es': 'N/D', 'it': 'N/D', 'pt': 'N/D', 'ja': 'N/A', 'zh': 'N/A', 'ko': 'N/A'
    },
    'fullscreen': {
        'tr': 'Tam Ekran', 'en': 'Fullscreen', 'de': 'Vollbild', 'fr': 'Plein écran', 'es': 'Pantalla completa', 'it': 'Schermo intero', 'pt': 'Tela cheia', 'ja': '全画面', 'zh': '全屏', 'ko': '전체 화면'
    },
    'windowed': {
        'tr': 'Pencere', 'en': 'Windowed', 'de': 'Fenster', 'fr': 'Fenêtré', 'es': 'Ventana', 'it': 'Finestra', 'pt': 'Janela', 'ja': 'ウィンドウ', 'zh': '窗口', 'ko': '창 모드'
    },
    'automatic': {
        'tr': 'Otomatik', 'en': 'Automatic', 'de': 'Automatisch', 'fr': 'Automatique', 'es': 'Automático', 'it': 'Automatico', 'pt': 'Automático', 'ja': '自動', 'zh': '自动', 'ko': '자동'
    },
    'on': {
        'tr': 'Açık', 'en': 'On', 'de': 'An', 'fr': 'Activé', 'es': 'Activado', 'it': 'Attivo', 'pt': 'Ligado', 'ja': 'オン', 'zh': '开', 'ko': '켜짐'
    },
    'off': {
        'tr': 'Kapalı', 'en': 'Off', 'de': 'Aus', 'fr': 'Désactivé', 'es': 'Desactivado', 'it': 'Disattivo', 'pt': 'Desligado', 'ja': 'オフ', 'zh': '关', 'ko': '꺼짐'
    },
    'vsync_changed': {
        'tr': 'VSync Değişti', 'en': 'VSync Changed', 'de': 'VSync geändert', 'fr': 'VSync modifié', 'es': 'VSync cambiado', 'it': 'VSync modificato', 'pt': 'VSync alterado', 'ja': 'VSyncが変更されました', 'zh': 'VSync 已更改', 'ko': 'VSync 변경됨'
    },
    'vsync_restart_msg1': {
        'tr': 'VSync değişikliğinin uygulanması için', 'en': 'To apply the VSync change,', 'de': 'Um die VSync-Änderung anzuwenden,', 'fr': 'Pour appliquer le changement VSync,', 'es': 'Para aplicar el cambio de VSync,', 'it': 'Per applicare la modifica VSync,', 'pt': 'Para aplicar a alteração do VSync,'
        , 'ja': 'VSyncの変更を適用するには、', 'zh': '要应用 VSync 更改，', 'ko': 'VSync 변경을 적용하려면,'
    },
    'vsync_restart_msg2': {
        'tr': 'oyunu yeniden başlatman gerekiyor.', 'en': 'you need to restart the game.', 'de': 'musst du das Spiel neu starten.', 'fr': 'vous devez redémarrer le jeu.', 'es': 'necesitas reiniciar el juego.', 'it': 'devi riavviare il gioco.', 'pt': 'você precisa reiniciar o jogo.', 'ja': 'ゲームを再起動する必要があります。', 'zh': '需要重新启动游戏。', 'ko': '게임을 다시 시작해야 합니다.'
    },
    'vsync_restart_msg3': {
        'tr': 'Şimdi yeniden başlatılsın mı?', 'en': 'Restart now?', 'de': 'Jetzt neu starten?', 'fr': 'Redémarrer maintenant ?', 'es': '¿Reiniciar ahora?', 'it': 'Riavviare ora?', 'pt': 'Reiniciar agora?', 'ja': '今すぐ再起動しますか？', 'zh': '现在重启吗？', 'ko': '지금 다시 시작할까요?'
    },
    'restart_now': {
        'tr': 'Şimdi Yeniden Başlat', 'en': 'Restart Now', 'de': 'Jetzt neu starten', 'fr': 'Redémarrer maintenant', 'es': 'Reiniciar ahora', 'it': 'Riavvia ora', 'pt': 'Reiniciar agora', 'ja': '今すぐ再起動', 'zh': '立即重启', 'ko': '지금 재시작'
    },
    'later': {
        'tr': 'Sonra', 'en': 'Later', 'de': 'Später', 'fr': 'Plus tard', 'es': 'Más tarde', 'it': 'Più tardi', 'pt': 'Mais tarde', 'ja': '後で', 'zh': '稍后', 'ko': '나중에'
    },
    'back': {
        'tr': 'Geri', 'en': 'Back', 'de': 'Zurück', 'fr': 'Retour', 'es': 'Atrás', 'it': 'Indietro', 'pt': 'Voltar', 'ja': '戻る', 'zh': '返回', 'ko': '뒤로'
    },
    
    # ========== AYARLAR MENÜSÜ İPUÇLARI ==========
    'hint_controls': {
        'tr': 'Tek oyuncu ve PvP tuşlarını değiştir',
        'en': 'Change single player and PvP keys',
        'de': 'Einzelspieler- und PvP-Tasten ändern',
        'fr': 'Modifier les touches solo et PvP',
        'es': 'Cambiar teclas de un jugador y PvP',
        'it': 'Cambia tasti giocatore singolo e PvP',
        'pt': 'Alterar teclas de um jogador e PvP',
        'ja': 'シングルとPvPのキーを変更',
        'zh': '更改单人和 PvP 按键',
        'ko': '싱글 및 PvP 키 변경'
    },
    'hint_gameplay': {
        'tr': 'DAS, hareket ve düşme hızı ayarları',
        'en': 'DAS, movement speed, drop speed settings',
        'de': 'DAS, Bewegungs- und Fallgeschwindigkeit',
        'fr': 'DAS, vitesse de déplacement et de chute',
        'es': 'DAS, velocidad de movimiento y caída',
        'it': 'DAS, velocità di movimento e caduta',
        'pt': 'DAS, velocidade de movimento e queda',
        'ja': 'DAS、移動速度、落下速度の設定',
        'zh': 'DAS、移动速度、下落速度设置',
        'ko': 'DAS, 이동 속도, 드롭 속도 설정'
    },
    'hint_mute_all': {
        'tr': 'Tüm sesleri tek tuşla kapat/aç (M tuşu)',
        'en': 'Mute/unmute all sounds (M key)',
        'de': 'Alle Töne stumm/laut (M-Taste)',
        'fr': 'Couper/activer tous les sons (touche M)',
        'es': 'Silenciar/activar todos los sonidos (tecla M)',
        'it': 'Disattiva/attiva tutti i suoni (tasto M)',
        'pt': 'Silenciar/ativar todos os sons (tecla M)',
        'ja': 'すべての音をミュート/解除 (Mキー)',
        'zh': '一键静音/取消静音（M 键）',
        'ko': '모든 소리 음소거/해제 (M 키)'
    },
    'hint_music': {
        'tr': 'Müzikleri aç/kapat',
        'en': 'Toggle music on/off',
        'de': 'Musik ein-/ausschalten',
        'fr': 'Activer/désactiver la musique',
        'es': 'Activar/desactivar música',
        'it': 'Attiva/disattiva musica',
        'pt': 'Ativar/desativar música',
        'ja': '音楽のオン/オフ',
        'zh': '开/关音乐',
        'ko': '음악 켜기/끄기'
    },
    'hint_music_volume': {
        'tr': 'Müzik ses seviyesini ayarla (Sol/Sağ)',
        'en': 'Adjust music volume (Left/Right)',
        'de': 'Musiklautstärke anpassen (Links/Rechts)',
        'fr': 'Régler le volume de la musique (Gauche/Droite)',
        'es': 'Ajustar volumen de música (Izquierda/Derecha)',
        'it': 'Regola volume musica (Sinistra/Destra)',
        'pt': 'Ajustar volume da música (Esquerda/Direita)',
        'ja': '音楽音量を調整(左/右)',
        'zh': '调整音乐音量（左/右）',
        'ko': '음악 볼륨 조절(왼쪽/오른쪽)'
    },
    'hint_sound': {
        'tr': 'Ses efektlerini aç/kapat',
        'en': 'Toggle sound effects on/off',
        'de': 'Soundeffekte ein-/ausschalten',
        'fr': 'Activer/désactiver les effets sonores',
        'es': 'Activar/desactivar efectos de sonido',
        'it': 'Attiva/disattiva effetti sonori',
        'pt': 'Ativar/desativar efeitos sonoros',
        'ja': '効果音のオン/オフ',
        'zh': '开/关音效',
        'ko': '효과음 켜기/끄기'
    },
    'hint_sfx_volume': {
        'tr': 'Efekt ses seviyesini ayarla (Sol/Sağ)',
        'en': 'Adjust SFX volume (Left/Right)',
        'de': 'Effektlautstärke anpassen (Links/Rechts)',
        'fr': 'Régler le volume des effets (Gauche/Droite)',
        'es': 'Ajustar volumen de efectos (Izquierda/Derecha)',
        'it': 'Regola volume effetti (Sinistra/Destra)',
        'pt': 'Ajustar volume de efeitos (Esquerda/Direita)',
        'ja': '効果音音量を調整(左/右)',
        'zh': '调整音效音量（左/右）',
        'ko': '효과음 볼륨 조절(왼쪽/오른쪽)'
    },
    'hint_tracks': {
        'tr': 'Ana sayfa / oyun içi / bölüm müziklerini tek yerden yönet',
        'en': 'Manage menu/game/mode music in one place',
        'de': 'Menü-/Spiel-/Modus-Musik zentral verwalten',
        'fr': 'Gérer la musique du menu/jeu/mode en un seul endroit',
        'es': 'Gestionar música de menú/juego/modo en un solo lugar',
        'it': 'Gestisci musica menu/gioco/modalità in un unico posto',
        'pt': 'Gerenciar música do menu/jogo/modo em um só lugar',
        'ja': 'メニュー/ゲーム/モードの音楽を一括管理',
        'zh': '在一个地方管理菜单/游戏/模式音乐',
        'ko': '메뉴/게임/모드 음악을 한 곳에서 관리'
    },
    'hint_graphics': {
        'tr': 'Detaylı grafik ve pencere ayarları',
        'en': 'Detailed graphics and window settings',
        'de': 'Detaillierte Grafik- und Fenstereinstellungen',
        'fr': 'Paramètres graphiques et de fenêtre détaillés',
        'es': 'Ajustes detallados de gráficos y ventana',
        'it': 'Impostazioni grafiche e finestra dettagliate',
        'pt': 'Configurações detalhadas de gráficos e janela',
        'ja': '詳細なグラフィックとウィンドウ設定',
        'zh': '详细的图形和窗口设置',
        'ko': '상세 그래픽 및 창 설정'
    },
    'hint_theme': {
        'tr': 'Blok renkleri ve tema paleti',
        'en': 'Block colors and theme palette',
        'de': 'Blockfarben und Themenpalette',
        'fr': 'Couleurs des blocs et palette de thème',
        'es': 'Colores de bloques y paleta de tema',
        'it': 'Colori blocchi e palette tema',
        'pt': 'Cores dos blocos e paleta do tema',
        'ja': 'ブロック色とテーマパレット',
        'zh': '方块颜色与主题调色板',
        'ko': '블록 색상과 테마 팔레트'
    },
    'hint_block_styles': {
        'tr': 'Tetromino renk/doku düzenleyiciyi aç',
        'en': 'Open tetromino color/texture editor',
        'de': 'Tetromino-Farb-/Textur-Editor öffnen',
        'fr': 'Ouvrir l\'éditeur de couleur/texture des tétrominos',
        'es': 'Abrir editor de color/textura de tetrominós',
        'it': 'Apri editor colore/texture tetromino',
        'pt': 'Abrir editor de cor/textura dos tetrominós',
        'ja': 'テトリミノ色/テクスチャ編集を開く',
        'zh': '打开方块颜色/纹理编辑器',
        'ko': '테트로미노 색/텍스처 편집기 열기'
    },
    'hint_piece_workshop': {
        'tr': 'Özel parçalar oluştur (max 7 blok)',
        'en': 'Create custom pieces (max 7 blocks)',
        'de': 'Eigene Teile erstellen (max. 7 Blöcke)',
        'fr': 'Créer des pièces personnalisées (max 7 blocs)',
        'es': 'Crear piezas personalizadas (máx. 7 bloques)',
        'it': 'Crea pezzi personalizzati (max 7 blocchi)',
        'pt': 'Criar peças personalizadas (máx. 7 blocos)',
        'ja': 'カスタムピース作成(最大7ブロック)',
        'zh': '创建自定义方块（最多7块）',
        'ko': '커스텀 피스 생성(최대 7블록)'
    },
    'hint_language': {
        'tr': 'Oyun dilini degistir / Change language',
        'en': 'Change game language',
        'de': 'Spielsprache ändern',
        'fr': 'Changer la langue du jeu',
        'es': 'Cambiar idioma del juego',
        'it': 'Cambia lingua del gioco',
        'pt': 'Alterar idioma do jogo',
        'ja': 'ゲーム言語を変更',
        'zh': '更改游戏语言',
        'ko': '게임 언어 변경'
    },
    'hint_guide': {
        'tr': 'Oyun rehberi ve kart açıklamalarını görüntüle',
        'en': 'View game instructions and card guide',
        'de': 'Spielanleitung und Kartenführer anzeigen',
        'fr': 'Voir les instructions du jeu et le guide des cartes',
        'es': 'Ver instrucciones del juego y guía de cartas',
        'it': 'Visualizza istruzioni di gioco e guida alle carte',
        'pt': 'Ver instruções do jogo e guia de cartas',
        'ja': 'ゲーム説明とカードガイドを見る',
        'zh': '查看游戏说明和卡牌指南',
        'ko': '게임 안내와 카드 가이드 보기'
    },
    'hint_debug_mode': {
        'tr': 'Terminalde debug mesajlarını göster',
        'en': 'Show debug messages in terminal',
        'de': 'Debug-Nachrichten im Terminal anzeigen',
        'fr': 'Afficher les messages de débogage dans le terminal',
        'es': 'Mostrar mensajes de depuración en terminal',
        'it': 'Mostra messaggi debug nel terminale',
        'pt': 'Mostrar mensagens de depuração no terminal',
        'ja': '端末にデバッグメッセージを表示',
        'zh': '在终端显示调试信息',
        'ko': '터미널에 디버그 메시지 표시'
    },
    'hint_card_debug': {
        'tr': 'Kart seçim ekranında tüm kartları göster (debug mod)',
        'en': 'Show all cards in card selection (debug)',
        'de': 'Alle Karten in der Kartenauswahl anzeigen (Debug)',
        'fr': 'Afficher toutes les cartes dans la sélection (débogage)',
        'es': 'Mostrar todas las cartas en selección (depuración)',
        'it': 'Mostra tutte le carte nella selezione (debug)',
        'pt': 'Mostrar todas as cartas na seleção (depuração)',
        'ja': 'カード選択で全カード表示(デバッグ)',
        'zh': '卡牌选择中显示所有卡牌（调试）',
        'ko': '카드 선택에서 모든 카드 표시(디버그)'
    },
    'hint_back': {
        'tr': 'Ana menüye geri dön',
        'en': 'Back to main menu',
        'de': 'Zurück zum Hauptmenü',
        'fr': 'Retour au menu principal',
        'es': 'Volver al menú principal',
        'it': 'Torna al menu principale',
        'pt': 'Voltar ao menu principal',
        'ja': 'メインメニューに戻る',
        'zh': '返回主菜单',
        'ko': '메인 메뉴로 돌아가기'
    },
    
    # ========== OYNANIŞ AYARLARI ÇEVİRİLERİ ==========
    'gameplay_settings': {
        'tr': 'OYNANIŞ AYARLARI', 'en': 'GAMEPLAY SETTINGS', 'de': 'SPIELEINSTELLUNGEN', 'fr': 'PARAMÈTRES DE JEU', 'es': 'AJUSTES DE JUEGO', 'it': 'IMPOSTAZIONI DI GIOCO', 'pt': 'CONFIGURAÇÕES DE JOGO', 'ja': 'ゲームプレイ設定', 'zh': '游戏玩法设置', 'ko': '게임플레이 설정'
    },
    'das_delay': {
        'tr': 'Yana Kaydırma Gecikmesi (DAS)', 'en': 'Delayed Auto Shift (DAS)', 'de': 'Verzögerte Auto-Verschiebung (DAS)', 'fr': 'Décalage automatique différé (DAS)', 'es': 'Desplazamiento automático retardado (DAS)', 'it': 'Spostamento automatico ritardato (DAS)', 'pt': 'Deslocamento automático atrasado (DAS)', 'ja': '横移動遅延(DAS)', 'zh': '侧移延迟 (DAS)', 'ko': '측면 이동 지연(DAS)'
    },
    'das_delay_desc': {
        'tr': 'Parçayı sağ/sol basılı tutunca kayma ne kadar geç başlasın? (Daha düşük = daha hızlı)', 'en': 'How long before side movement starts when holding? (Lower = faster)', 'de': 'Wie lange dauert es, bis die Seitenbewegung beim Halten beginnt? (Niedriger = schneller)', 'fr': 'Combien de temps avant que le mouvement latéral commence en maintenant ? (Plus bas = plus rapide)', 'es': '¿Cuánto tiempo antes de que comience el movimiento lateral al mantener? (Más bajo = más rápido)', 'it': 'Quanto tempo prima che inizi il movimento laterale tenendo premuto? (Più basso = più veloce)', 'pt': 'Quanto tempo antes do movimento lateral começar ao segurar? (Menor = mais rápido)'
        , 'ja': '左右を押し続けた時に横移動が始まるまでの時間。(低いほど速い)',
        'zh': '按住左右时，侧向移动多久后开始？（越低越快）',
        'ko': '좌/우를 눌러 유지할 때 옆 이동이 시작되기까지의 시간(낮을수록 빠름)'
    },
    'das_repeat': {
        'tr': 'Yana Kaydırma Tekrar Hızı (ARR)', 'en': 'Auto Repeat Rate (ARR)', 'de': 'Auto-Wiederholungsrate (ARR)', 'fr': 'Taux de répétition automatique (ARR)', 'es': 'Tasa de repetición automática (ARR)', 'it': 'Tasso di ripetizione automatica (ARR)', 'pt': 'Taxa de repetição automática (ARR)', 'ja': '自動リピート速度(ARR)', 'zh': '自动重复速率 (ARR)', 'ko': '자동 반복 속도(ARR)'
    },
    'das_repeat_desc': {
        'tr': 'Basılı tutarken parçanın sağ/sol kayma hızı. (Daha düşük = daha hızlı)', 'en': 'Speed of side movement while holding. (Lower = faster)', 'de': 'Geschwindigkeit der Seitenbewegung beim Halten. (Niedriger = schneller)', 'fr': 'Vitesse du mouvement latéral en maintenant. (Plus bas = plus rapide)', 'es': 'Velocidad del movimiento lateral al mantener. (Más bajo = más rápido)', 'it': 'Velocità del movimento laterale tenendo premuto. (Più basso = più veloce)', 'pt': 'Velocidade do movimento lateral ao segurar. (Menor = mais rápido)'
        , 'ja': '押し続け中の横移動速度。(低いほど速い)',
        'zh': '按住时左右移动速度。（越低越快）',
        'ko': '눌러 유지할 때의 좌/우 이동 속도(낮을수록 빠름)'
    },
    'soft_drop_speed': {
        'tr': 'Yumuşak Düşme Hızı (Soft Drop)', 'en': 'Soft Drop Speed', 'de': 'Sanfte Fallgeschwindigkeit', 'fr': 'Vitesse de descente douce', 'es': 'Velocidad de caída suave', 'it': 'Velocità di caduta morbida', 'pt': 'Velocidade de queda suave', 'ja': 'ソフトドロップ速度', 'zh': '软降速度', 'ko': '소프트 드롭 속도'
    },
    'soft_drop_desc': {
        'tr': 'Aşağı tuşuna basınca düşme hızı. (Daha düşük = daha hızlı)', 'en': 'Drop speed when pressing down. (Lower = faster)', 'de': 'Fallgeschwindigkeit beim Drücken nach unten. (Niedriger = schneller)', 'fr': 'Vitesse de chute en appuyant vers le bas. (Plus bas = plus rapide)', 'es': 'Velocidad de caída al presionar abajo. (Más bajo = más rápido)', 'it': 'Velocità di caduta premendo giù. (Più basso = più veloce)', 'pt': 'Velocidade de queda ao pressionar para baixo. (Menor = mais rápido)'
        , 'ja': '下キーでの落下速度。(低いほど速い)',
        'zh': '按下时的下落速度。（越低越快）',
        'ko': '아래키를 누를 때의 낙하 속도(낮을수록 빠름)'
    },
    
    # ========== MOD MÜZİKLERİ ÇEVİRİLERİ ==========
    'mode_music': {
        'tr': 'BÖLÜM MÜZİKLERİ', 'en': 'MODE MUSIC', 'de': 'MODUS-MUSIK', 'fr': 'MUSIQUE DE MODE', 'es': 'MÚSICA DE MODO', 'it': 'MUSICA MODALITÀ', 'pt': 'MÚSICA DO MODO', 'ja': 'モード音楽', 'zh': '模式音乐', 'ko': '모드 음악'
    },
    'custom_count': {
        'tr': '{count} özel', 'en': '{count} custom', 'de': '{count} benutzerdefiniert', 'fr': '{count} personnalisé', 'es': '{count} personalizado', 'it': '{count} personalizzato', 'pt': '{count} personalizado', 'ja': '{count} カスタム', 'zh': '{count} 自定义', 'ko': '{count} 사용자 지정'
    },
    'modes_customized': {
        'tr': '{count} mod özelleştirildi', 'en': '{count} modes customized', 'de': '{count} Modi angepasst', 'fr': '{count} modes personnalisés', 'es': '{count} modos personalizados', 'it': '{count} modalità personalizzate', 'pt': '{count} modos personalizados', 'ja': '{count} モードをカスタム', 'zh': '已自定义 {count} 个模式', 'ko': '{count}개의 모드가 사용자 지정됨'
    },
    'default_ingame': {
        'tr': 'Varsayılan (Oyun İçi)', 'en': 'Default (In-Game)', 'de': 'Standard (Im Spiel)', 'fr': 'Par défaut (En jeu)', 'es': 'Predeterminado (En juego)', 'it': 'Predefinito (In gioco)', 'pt': 'Padrão (No jogo)', 'ja': 'デフォルト(ゲーム内)', 'zh': '默认（游戏内）', 'ko': '기본(게임 내)'
    },
    
    # ========== MÜZİK MENÜSÜ ÇEVİRİLERİ ==========
    'tracks': {
        'tr': 'MÜZİKLER', 'en': 'TRACKS', 'de': 'TITEL', 'fr': 'PISTES', 'es': 'PISTAS', 'it': 'TRACCE', 'pt': 'FAIXAS', 'ja': 'トラック', 'zh': '曲目', 'ko': '트랙'
    },
    'menu_music': {
        'tr': 'Ana Sayfa Müziği', 'en': 'Menu Music', 'de': 'Menümusik', 'fr': 'Musique du menu', 'es': 'Música del menú', 'it': 'Musica del menu', 'pt': 'Música do menu', 'ja': 'メニュー音楽', 'zh': '菜单音乐', 'ko': '메뉴 음악'
    },
    'game_music': {
        'tr': 'Oyun İçi Müzik', 'en': 'Game Music', 'de': 'Spielmusik', 'fr': 'Musique de jeu', 'es': 'Música del juego', 'it': 'Musica di gioco', 'pt': 'Música do jogo', 'ja': 'ゲーム内音楽', 'zh': '游戏内音乐', 'ko': '게임 음악'
    },
    'mode_music_label': {
        'tr': 'Bölüm Müzikleri', 'en': 'Mode Music', 'de': 'Modus-Musik', 'fr': 'Musique de mode', 'es': 'Música de modo', 'it': 'Musica modalità', 'pt': 'Música do modo', 'ja': 'モード音楽', 'zh': '模式音乐', 'ko': '모드 음악'
    },
    'default': {
        'tr': 'Varsayılan', 'en': 'Default', 'de': 'Standard', 'fr': 'Par défaut', 'es': 'Predeterminado', 'it': 'Predefinito', 'pt': 'Padrão', 'ja': 'デフォルト', 'zh': '默认', 'ko': '기본'
    },
    'active_label': {
        'tr': 'Aktif: {current}', 'en': 'Active: {current}', 'de': 'Aktiv: {current}', 'fr': 'Actif: {current}', 'es': 'Activo: {current}', 'it': 'Attivo: {current}', 'pt': 'Ativo: {current}', 'ja': '有効: {current}', 'zh': '当前：{current}', 'ko': '활성: {current}'
    },
    
    # ========== İPUCU METİNLERİ ==========
    'hint_select_apply_close': {
        'tr': '↑ ↓: Seç  |  ENTER: Uygula  |  ESC / Dışa tık: Kapat',
        'en': '↑ ↓: Select  |  ENTER: Apply  |  ESC / Click outside: Close',
        'de': '↑ ↓: Auswählen  |  ENTER: Anwenden  |  ESC / Außerhalb klicken: Schließen',
        'fr': '↑ ↓: Sélectionner  |  ENTRÉE: Appliquer  |  ÉCHAP / Clic extérieur: Fermer',
        'es': '↑ ↓: Seleccionar  |  ENTER: Aplicar  |  ESC / Clic afuera: Cerrar',
        'it': '↑ ↓: Seleziona  |  INVIO: Applica  |  ESC / Clic esterno: Chiudi',
        'pt': '↑ ↓: Selecionar  |  ENTER: Aplicar  |  ESC / Clique fora: Fechar',
        'ja': '↑ ↓: 選択  |  ENTER: 適用  |  ESC / 外側クリック: 閉じる',
        'zh': '↑ ↓：选择  |  ENTER：应用  |  ESC / 点击外部：关闭',
        'ko': '↑ ↓: 선택  |  ENTER: 적용  |  ESC / 바깥 클릭: 닫기'
    },
    'hint_select_open_close': {
        'tr': '↑ ↓: Seç  |  ENTER: Aç  |  ESC / Dışa tık: Kapat',
        'en': '↑ ↓: Select  |  ENTER: Open  |  ESC / Click outside: Close',
        'de': '↑ ↓: Auswählen  |  ENTER: Öffnen  |  ESC / Außerhalb klicken: Schließen',
        'fr': '↑ ↓: Sélectionner  |  ENTRÉE: Ouvrir  |  ÉCHAP / Clic extérieur: Fermer',
        'es': '↑ ↓: Seleccionar  |  ENTER: Abrir  |  ESC / Clic afuera: Cerrar',
        'it': '↑ ↓: Seleziona  |  INVIO: Apri  |  ESC / Clic esterno: Chiudi',
        'pt': '↑ ↓: Selecionar  |  ENTER: Abrir  |  ESC / Clique fora: Fechar',
        'ja': '↑ ↓: 選択  |  ENTER: 開く  |  ESC / 外側クリック: 閉じる',
        'zh': '↑ ↓：选择  |  ENTER：打开  |  ESC / 点击外部：关闭',
        'ko': '↑ ↓: 선택  |  ENTER: 열기  |  ESC / 바깥 클릭: 닫기'
    },
    
    # ========== BAŞARILAR EKRANI ==========
    'achievements_title': {
        'tr': 'BAŞARILAR', 'en': 'ACHIEVEMENTS', 'de': 'ERFOLGE', 'fr': 'SUCCÈS', 'es': 'LOGROS', 'it': 'TRAGUARDI', 'pt': 'CONQUISTAS', 'ja': '実績', 'zh': '成就', 'ko': '업적'
    },
    
    # ========== TAM EKRAN MODLARI ==========
    'fullscreen_mode': {
        'tr': 'Tam Ekran Modu', 'en': 'Fullscreen Mode', 'de': 'Vollbildmodus', 'fr': 'Mode plein écran', 'es': 'Modo pantalla completa', 'it': 'Modalità schermo intero', 'pt': 'Modo tela cheia', 'ja': '全画面モード', 'zh': '全屏模式', 'ko': '전체 화면 모드'
    },
    'borderless': {
        'tr': 'Kenarlıksız', 'en': 'Borderless', 'de': 'Randlos', 'fr': 'Sans bordure', 'es': 'Sin bordes', 'it': 'Senza bordi', 'pt': 'Sem bordas', 'ja': 'ボーダーレス', 'zh': '无边框', 'ko': '무테'
    },
    'exclusive': {
        'tr': 'Özel', 'en': 'Exclusive', 'de': 'Exklusiv', 'fr': 'Exclusif', 'es': 'Exclusivo', 'it': 'Esclusivo', 'pt': 'Exclusivo', 'ja': '排他', 'zh': '独占', 'ko': '독점'
    },
    'borderless_desc': {
        'tr': 'Alt+Tab ve ekran görüntüsüne izin verir', 'en': 'Allows Alt+Tab and screenshots', 'de': 'Erlaubt Alt+Tab und Screenshots', 'fr': 'Permet Alt+Tab et captures d\'écran', 'es': 'Permite Alt+Tab y capturas de pantalla', 'it': 'Permette Alt+Tab e screenshot', 'pt': 'Permite Alt+Tab e capturas de tela', 'ja': 'Alt+Tabとスクリーンショットを許可', 'zh': '允许 Alt+Tab 与截图', 'ko': 'Alt+Tab과 스크린샷 허용'
    },
    
    # ======================= KILAVUZ EKRANI =======================
    'guide_title': {
        'tr': 'KILAVUZ', 'en': 'GUIDE', 'de': 'ANLEITUNG', 'fr': 'GUIDE', 'es': 'GUÍA', 'it': 'GUIDA', 'pt': 'GUIA', 'ja': 'ガイド', 'zh': '指南', 'ko': '가이드'
    },
    'guide_menu_button': {
        'tr': 'Kılavuz', 'en': 'Guide', 'de': 'Anleitung', 'fr': 'Guide', 'es': 'Guía', 'it': 'Guida', 'pt': 'Guia', 'ja': 'ガイド', 'zh': '指南', 'ko': '가이드'
    },
    'previous': {
        'tr': 'Önceki', 'en': 'Previous', 'de': 'Zurück', 'fr': 'Précédent', 'es': 'Anterior', 'it': 'Precedente', 'pt': 'Anterior', 'ja': '前へ', 'zh': '上一页', 'ko': '이전'
    },
    'next_page': {
        'tr': 'Sonraki', 'en': 'Next', 'de': 'Weiter', 'fr': 'Suivant', 'es': 'Siguiente', 'it': 'Successivo', 'pt': 'Próximo', 'ja': '次へ', 'zh': '下一页', 'ko': '다음'
    },
    
    # --- Tab Başlıkları ---
    'guide_how_to_play_title': {
        'tr': 'Nasıl Oynanır', 'en': 'How to Play', 'de': 'So wird gespielt', 'fr': 'Comment jouer', 'es': 'Cómo jugar', 'it': 'Come giocare', 'pt': 'Como jogar', 'ja': '遊び方', 'zh': '如何游玩', 'ko': '플레이 방법'
    },
    'guide_game_modes_title': {
        'tr': 'Oyun Modları', 'en': 'Game Modes', 'de': 'Spielmodi', 'fr': 'Modes de jeu', 'es': 'Modos de juego', 'it': 'Modalità di gioco', 'pt': 'Modos de jogo', 'ja': 'ゲームモード', 'zh': '游戏模式', 'ko': '게임 모드'
    },
    'guide_cards_title': {
        'tr': 'Kartlar', 'en': 'Cards', 'de': 'Karten', 'fr': 'Cartes', 'es': 'Cartas', 'it': 'Carte', 'pt': 'Cartas', 'ja': 'カード', 'zh': '卡牌', 'ko': '카드'
    },
    'guide_tips_title': {
        'tr': 'İpuçları ve SSS', 'en': 'Tips & FAQ', 'de': 'Tipps & FAQ', 'fr': 'Conseils & FAQ', 'es': 'Consejos y FAQ', 'it': 'Suggerimenti & FAQ', 'pt': 'Dicas e FAQ', 'ja': 'ヒントとFAQ', 'zh': '提示与FAQ', 'ko': '팁 & FAQ'
    },
    'guide_main_objective_title': {
        'tr': 'ANA AMAÇ', 'en': 'MAIN OBJECTIVE', 'de': 'HAUPTZIEL', 'fr': 'OBJECTIF PRINCIPAL', 'es': 'OBJETIVO PRINCIPAL', 'it': 'OBIETTIVO PRINCIPALE', 'pt': 'OBJETIVO PRINCIPAL', 'ja': 'メイン目標', 'zh': '主要目标', 'ko': '주요 목표'
    },
    'guide_card_controls_title': {
        'tr': 'KONTROLLER', 'en': 'CONTROLS', 'de': 'STEUERUNG', 'fr': 'CONTRÔLES', 'es': 'CONTROLES', 'it': 'CONTROLLI', 'pt': 'CONTROLES', 'ja': '操作', 'zh': '控制', 'ko': '조작'
    },
    'guide_card_scoring_title': {
        'tr': 'PUANLAMA', 'en': 'SCORING', 'de': 'PUNKTE', 'fr': 'SCORE', 'es': 'PUNTUACIÓN', 'it': 'PUNTEGGIO', 'pt': 'PONTUAÇÃO', 'ja': 'スコア', 'zh': '计分', 'ko': '점수'
    },
    'guide_card_levels_title': {
        'tr': 'SEVİYE', 'en': 'LEVELS', 'de': 'LEVEL', 'fr': 'NIVEAUX', 'es': 'NIVELES', 'it': 'LIVELLI', 'pt': 'NÍVEIS', 'ja': 'レベル', 'zh': '等级', 'ko': '레벨'
    },
    'guide_card_tips_title': {
        'tr': 'İPUÇLARI', 'en': 'TIPS', 'de': 'TIPPS', 'fr': 'CONSEILS', 'es': 'CONSEJOS', 'it': 'SUGGERIMENTI', 'pt': 'DICAS', 'ja': 'ヒント', 'zh': '提示', 'ko': '팁'
    },
    'guide_controls_header': {
        'tr': '━━━ KONTROLLER ━━━', 'en': '━━━ CONTROLS ━━━', 'de': '━━━ STEUERUNG ━━━', 'fr': '━━━ CONTRÔLES ━━━', 'es': '━━━ CONTROLES ━━━', 'it': '━━━ CONTROLLI ━━━', 'pt': '━━━ CONTROLES ━━━', 'ja': '━━━ 操作 ━━━', 'zh': '━━━ 控制 ━━━', 'ko': '━━━ 조작 ━━━'
    },
    'guide_controls_line': {
        'tr': '• {keys}: {action}', 'en': '• {keys}: {action}', 'de': '• {keys}: {action}', 'fr': '• {keys}: {action}', 'es': '• {keys}: {action}', 'it': '• {keys}: {action}', 'pt': '• {keys}: {action}', 'ja': '• {keys}: {action}', 'zh': '• {keys}: {action}', 'ko': '• {keys}: {action}'
    },
    'guide_controls_left_right_arrows': {
        'tr': 'Sol/Sağ Ok', 'en': 'Left/Right Arrow', 'de': 'Links/Rechts Pfeil', 'fr': 'Flèches Gauche/Droite', 'es': 'Flechas Izq./Der.', 'it': 'Freccia Sinistra/Destra', 'pt': 'Setas Esquerda/Direita', 'ja': '左右矢印', 'zh': '左/右箭头', 'ko': '왼쪽/오른쪽 화살표'
    },
    'guide_action_move': {
        'tr': 'Hareket Ettir', 'en': 'Move', 'de': 'Bewegen', 'fr': 'Déplacer', 'es': 'Mover', 'it': 'Muovi', 'pt': 'Mover', 'ja': '移動', 'zh': '移动', 'ko': '이동'
    },
    'guide_action_rotate': {
        'tr': 'Döndür', 'en': 'Rotate', 'de': 'Drehen', 'fr': 'Tourner', 'es': 'Rotar', 'it': 'Ruota', 'pt': 'Girar', 'ja': '回転', 'zh': '旋转', 'ko': '회전'
    },
    'guide_action_soft_drop': {
        'tr': 'Yavaş Düşür (Soft)', 'en': 'Soft Drop', 'de': 'Langsam fallen', 'fr': 'Descente lente', 'es': 'Caída lenta', 'it': 'Caduta lenta', 'pt': 'Queda lenta', 'ja': 'ソフトドロップ', 'zh': '软降', 'ko': '소프트 드롭'
    },
    'guide_action_hard_drop': {
        'tr': 'Anında Düşür (Hard)', 'en': 'Hard Drop', 'de': 'Schnell fallen', 'fr': 'Descente rapide', 'es': 'Caída rápida', 'it': 'Caduta rapida', 'pt': 'Queda rápida', 'ja': 'ハードドロップ', 'zh': '硬降', 'ko': '하드 드롭'
    },
    'guide_action_hold': {
        'tr': 'Parçayı Sakla (Hold)', 'en': 'Hold Piece', 'de': 'Teil halten', 'fr': 'Mettre en réserve', 'es': 'Guardar pieza', 'it': 'Metti in riserva', 'pt': 'Guardar peça', 'ja': 'ホールド', 'zh': '保留方块', 'ko': '홀드'
    },
    'guide_action_pause': {
        'tr': 'Duraklat', 'en': 'Pause', 'de': 'Pause', 'fr': 'Pause', 'es': 'Pausa', 'it': 'Pausa', 'pt': 'Pausa', 'ja': '一時停止', 'zh': '暂停', 'ko': '일시정지'
    },
    'guide_action_restart': {
        'tr': 'Yeniden Başlat', 'en': 'Restart', 'de': 'Neustart', 'fr': 'Recommencer', 'es': 'Reiniciar', 'it': 'Ricomincia', 'pt': 'Reiniciar', 'ja': 'リスタート', 'zh': '重新开始', 'ko': '재시작'
    },
    'guide_rarity_common': {
        'tr': 'Yaygın', 'en': 'Common', 'de': 'Gewöhnlich', 'fr': 'Commun', 'es': 'Común', 'it': 'Comune', 'pt': 'Comum', 'ja': '一般', 'zh': '普通', 'ko': '일반'
    },
    'guide_rarity_uncommon': {
        'tr': 'Nadir Değil', 'en': 'Uncommon', 'de': 'Ungewöhnlich', 'fr': 'Peu commun', 'es': 'Poco común', 'it': 'Non comune', 'pt': 'Incomum', 'ja': 'ややレア', 'zh': '不常见', 'ko': '언커먼'
    },
    'guide_rarity_rare': {
        'tr': 'Nadir', 'en': 'Rare', 'de': 'Selten', 'fr': 'Rare', 'es': 'Raro', 'it': 'Raro', 'pt': 'Raro', 'ja': 'レア', 'zh': '稀有', 'ko': '레어'
    },
    'guide_rarity_epic': {
        'tr': 'Epik', 'en': 'Epic', 'de': 'Episch', 'fr': 'Épique', 'es': 'Épico', 'it': 'Epico', 'pt': 'Épico', 'ja': 'エピック', 'zh': '史诗', 'ko': '에픽'
    },
    'guide_rarity_legendary': {
        'tr': 'Efsanevi', 'en': 'Legendary', 'de': 'Legendär', 'fr': 'Légendaire', 'es': 'Legendario', 'it': 'Leggendario', 'pt': 'Lendário', 'ja': 'レジェンド', 'zh': '传说', 'ko': '레전더리'
    },
    'guide_rarity_perk': {
        'tr': 'Kalıcı Perk', 'en': 'Persistent Perk', 'de': 'Dauerhafter Perk', 'fr': 'Perk permanent', 'es': 'Perk permanente', 'it': 'Perk permanente', 'pt': 'Perk permanente', 'ja': '永続パーク', 'zh': '永久特性', 'ko': '영구 특전'
    },
    'key_left_arrow': {
        'tr': 'Sol Ok', 'en': 'Left Arrow', 'de': 'Links Pfeil', 'fr': 'Flèche gauche', 'es': 'Flecha izquierda', 'it': 'Freccia sinistra', 'pt': 'Seta esquerda', 'ja': '左矢印', 'zh': '左箭头', 'ko': '왼쪽 화살표'
    },
    'key_right_arrow': {
        'tr': 'Sağ Ok', 'en': 'Right Arrow', 'de': 'Rechts Pfeil', 'fr': 'Flèche droite', 'es': 'Flecha derecha', 'it': 'Freccia destra', 'pt': 'Seta direita', 'ja': '右矢印', 'zh': '右箭头', 'ko': '오른쪽 화살표'
    },
    'key_up_arrow': {
        'tr': 'Yukarı Ok', 'en': 'Up Arrow', 'de': 'Oben Pfeil', 'fr': 'Flèche haut', 'es': 'Flecha arriba', 'it': 'Freccia su', 'pt': 'Seta para cima', 'ja': '上矢印', 'zh': '上箭头', 'ko': '위쪽 화살표'
    },
    'key_down_arrow': {
        'tr': 'Aşağı Ok', 'en': 'Down Arrow', 'de': 'Unten Pfeil', 'fr': 'Flèche bas', 'es': 'Flecha abajo', 'it': 'Freccia giù', 'pt': 'Seta para baixo', 'ja': '下矢印', 'zh': '下箭头', 'ko': '아래쪽 화살표'
    },
    'key_space': {
        'tr': 'Boşluk', 'en': 'Space', 'de': 'Leertaste', 'fr': 'Espace', 'es': 'Espacio', 'it': 'Spazio', 'pt': 'Espaço', 'ja': 'スペース', 'zh': '空格', 'ko': '스페이스'
    },
    'key_enter': {
        'tr': 'Enter', 'en': 'Enter', 'de': 'Eingabe', 'fr': 'Entrée', 'es': 'Intro', 'it': 'Invio', 'pt': 'Enter', 'ja': 'Enter', 'zh': '回车', 'ko': '엔터'
    },
    'key_escape': {
        'tr': 'ESC', 'en': 'ESC', 'de': 'ESC', 'fr': 'ÉCHAP', 'es': 'ESC', 'it': 'ESC', 'pt': 'ESC', 'ja': 'ESC', 'zh': 'ESC', 'ko': 'ESC'
    },
    'key_left_shift': {
        'tr': 'Sol Shift', 'en': 'Left Shift', 'de': 'Linke Umschalt', 'fr': 'Maj gauche', 'es': 'Mayús izq.', 'it': 'Shift sinistro', 'pt': 'Shift esquerdo', 'ja': '左Shift', 'zh': '左Shift', 'ko': '왼쪽 Shift'
    },
    'key_right_shift': {
        'tr': 'Sağ Shift', 'en': 'Right Shift', 'de': 'Rechte Umschalt', 'fr': 'Maj droite', 'es': 'Mayús der.', 'it': 'Shift destro', 'pt': 'Shift direito', 'ja': '右Shift', 'zh': '右Shift', 'ko': '오른쪽 Shift'
    },
    'key_left_ctrl': {
        'tr': 'Sol Ctrl', 'en': 'Left Ctrl', 'de': 'Linke Strg', 'fr': 'Ctrl gauche', 'es': 'Ctrl izq.', 'it': 'Ctrl sinistro', 'pt': 'Ctrl esquerdo', 'ja': '左Ctrl', 'zh': '左Ctrl', 'ko': '왼쪽 Ctrl'
    },
    'key_right_ctrl': {
        'tr': 'Sağ Ctrl', 'en': 'Right Ctrl', 'de': 'Rechte Strg', 'fr': 'Ctrl droite', 'es': 'Ctrl der.', 'it': 'Ctrl destro', 'pt': 'Ctrl direito', 'ja': '右Ctrl', 'zh': '右Ctrl', 'ko': '오른쪽 Ctrl'
    },
    'key_left_alt': {
        'tr': 'Sol Alt', 'en': 'Left Alt', 'de': 'Linke Alt', 'fr': 'Alt gauche', 'es': 'Alt izq.', 'it': 'Alt sinistro', 'pt': 'Alt esquerdo', 'ja': '左Alt', 'zh': '左Alt', 'ko': '왼쪽 Alt'
    },
    'key_right_alt': {
        'tr': 'Sağ Alt', 'en': 'Right Alt', 'de': 'Rechte Alt', 'fr': 'Alt droite', 'es': 'Alt der.', 'it': 'Alt destro', 'pt': 'Alt direito', 'ja': '右Alt', 'zh': '右Alt', 'ko': '오른쪽 Alt'
    },
    'key_caps_lock': {
        'tr': 'Caps', 'en': 'Caps Lock', 'de': 'Feststelltaste', 'fr': 'Verr. maj.', 'es': 'Bloq Mayús', 'it': 'Bloc Maiusc', 'pt': 'Caps Lock', 'ja': 'Caps Lock', 'zh': '大写锁定', 'ko': 'Caps Lock'
    },
    'key_tab': {
        'tr': 'Tab', 'en': 'Tab', 'de': 'Tab', 'fr': 'Tab', 'es': 'Tab', 'it': 'Tab', 'pt': 'Tab', 'ja': 'Tab', 'zh': 'Tab', 'ko': 'Tab'
    },
    
    # --- Nasıl Oynanır Bölümü ---
    'guide_how_to_play_intro': {
        'tr': 'Quadrix, yukarıdan düşen parçaları (Tetromino) yatay satırlar oluşturacak şekilde dizme oyunudur.\n\nTam bir satır tamamlandığında o satır silinir ve puan kazanırsınız.\n\nTahtanın üstüne ulaşan parçalar oyunu bitirir.',
        'en': 'Quadrix is a game where you arrange falling pieces (Tetrominoes) to form complete horizontal lines.\n\nWhen a complete line is formed, it clears and you score points.\n\nPieces reaching the top of the board end the game.',
        'ja': 'テトリスは上から落ちてくるピース(テトリミノ)を横一列にそろえるゲームです。\n\n1列が完成すると消えて得点になります。\n\nブロックが天井に達するとゲーム終了です。',
        'zh': '俄罗斯方块是一款将从上方落下的方块（四格骨牌）排列成水平整行的游戏。\n\n当一行被填满时会被消除并获得分数。\n\n方块堆到顶部则游戏结束。',
        'ko': '테트리스는 위에서 떨어지는 피스(테트로미노)를 가로 한 줄로 맞추는 게임입니다.\n\n한 줄이 완성되면 사라지고 점수를 얻습니다.\n\n블록이 보드 상단에 닿으면 게임이 끝납니다.'
    },
    'guide_how_to_play_controls': {
        'tr': '━━━ KONTROLLER ━━━\n\n• Sol/Sağ Ok: Parçayı sola/sağa hareket ettir\n\n• Yukarı Ok / X: Saat yönünde döndür\n\n• Z: Saat yönünün tersine döndür\n\n• Aşağı Ok: Yavaş düşür (Soft Drop)\n\n• Boşluk: Anında düşür (Hard Drop)\n\n• C: Parçayı sakla (Hold)\n\n• P / ESC: Duraklat\n\n• R: Yeniden başlat',
        'en': '━━━ CONTROLS ━━━\n\n• Left/Right Arrow: Move piece left/right\n\n• Up Arrow / X: Rotate clockwise\n\n• Z: Rotate counter-clockwise\n\n• Down Arrow: Soft drop\n\n• Space: Hard drop (instant)\n\n• C: Hold piece\n\n• P / ESC: Pause\n\n• R: Restart',
        'ja': '━━━ 操作 ━━━\n\n• 左/右矢印: 左右移動\n\n• 上矢印 / X: 時計回りに回転\n\n• Z: 反時計回りに回転\n\n• 下矢印: ソフトドロップ\n\n• スペース: ハードドロップ(即時)\n\n• C: ホールド\n\n• P / ESC: 一時停止\n\n• R: リスタート',
        'zh': '━━━ 控制 ━━━\n\n• 左/右箭头：向左/右移动方块\n\n• 上箭头 / X：顺时针旋转\n\n• Z：逆时针旋转\n\n• 下箭头：软降\n\n• 空格：硬降（立即）\n\n• C：保留方块（Hold）\n\n• P / ESC：暂停\n\n• R：重新开始',
        'ko': '━━━ 조작 ━━━\n\n• 왼쪽/오른쪽 화살표: 피스를 좌/우로 이동\n\n• 위쪽 화살표 / X: 시계 방향 회전\n\n• Z: 반시계 방향 회전\n\n• 아래쪽 화살표: 소프트 드롭\n\n• 스페이스: 하드 드롭(즉시)\n\n• C: 홀드\n\n• P / ESC: 일시정지\n\n• R: 재시작'
    },
    'guide_how_to_play_scoring': {
        'tr': '━━━ PUANLAMA SİSTEMİ ━━━\n\n• 1 Satır: 100 × Seviye puan\n\n• 2 Satır (Double): 300 × Seviye puan\n\n• 3 Satır (Triple): 500 × Seviye puan\n\n• 4 Satır (Quadrix): 800 × Seviye puan\n\n• Combo Bonusu: Art arda satır silmede ek puan\n\n• Hard Drop: Parçanın düştüğü her satır için 2 puan\n\n━━━━━━━━━━━━━━━━━━━━━━\n\nÖrnek: Parça 5 satır düşerse = 10 puan\n\nİpucu: Hızlı oynamak için Space tuşunu kullan!',
        'en': '━━━ SCORING SYSTEM ━━━\n\n• 1 Line: 100 × Level points\n\n• 2 Lines (Double): 300 × Level points\n\n• 3 Lines (Triple): 500 × Level points\n\n• 4 Lines (Quadrix): 800 × Level points\n\n• Combo Bonus: Extra points for consecutive clears\n\n• Hard Drop: 2 points per row the piece falls\n\n━━━━━━━━━━━━━━━━━━━━━━\n\nExample: Piece falls 5 rows = 10 points\n\nTip: Use Space for fast play!',
        'ja': '━━━ スコアシステム ━━━\n\n• 1ライン: 100 × レベル\n\n• 2ライン(ダブル): 300 × レベル\n\n• 3ライン(トリプル): 500 × レベル\n\n• 4ライン(テトリス): 800 × レベル\n\n• コンボボーナス: 連続消去で加点\n\n• ハードドロップ: 落下1行ごとに2点\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n例: 5行落下 = 10点\n\nヒント: 速く遊ぶならSpaceキー！',
        'zh': '━━━ 计分系统 ━━━\n\n• 1 行：100 × 等级分\n\n• 2 行（Double）：300 × 等级分\n\n• 3 行（Triple）：500 × 等级分\n\n• 4 行（Quadrix）：800 × 等级分\n\n• 连击加成：连续消除额外加分\n\n• 硬降：方块每下落一行得 2 分\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n示例：方块下落 5 行 = 10 分\n\n提示：想快速游戏请用 Space！',
        'ko': '━━━ 점수 시스템 ━━━\n\n• 1줄: 100 × 레벨 점수\n\n• 2줄(더블): 300 × 레벨 점수\n\n• 3줄(트리플): 500 × 레벨 점수\n\n• 4줄(테트리스): 800 × 레벨 점수\n\n• 콤보 보너스: 연속 삭제 추가 점수\n\n• 하드 드롭: 피스가 떨어진 각 줄마다 2점\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n예: 5줄 낙하 = 10점\n\n팁: 빠르게 플레이하려면 Space 키!'
    },
    'guide_how_to_play_levels': {
        'tr': '━━━ SEVİYE SİSTEMİ ━━━\n\nHer 10 satır temizlediğinizde seviye artar.\n\nSeviye arttıkça:\n\n• Parçalar daha hızlı düşer\n\n• Kazanılan puanlar artar\n\n• Zorluk yükselir',
        'en': '━━━ LEVEL SYSTEM ━━━\n\nLevel increases every 10 lines cleared.\n\nAs level increases:\n\n• Pieces fall faster\n\n• Points earned multiply\n\n• Difficulty rises',
        'ja': '━━━ レベルシステム ━━━\n\n10ライン消すごとにレベルが上がる。\n\nレベルが上がると:\n\n• ピースの落下が速くなる\n\n• 得点倍率が上がる\n\n• 難易度が上がる',
        'zh': '━━━ 等级系统 ━━━\n\n每清除 10 行等级提升。\n\n随着等级提升：\n\n• 方块下落更快\n\n• 获得分数增加\n\n• 难度上升',
        'ko': '━━━ 레벨 시스템 ━━━\n\n10줄을 지울 때마다 레벨이 올라갑니다.\n\n레벨이 올라가면:\n\n• 피스가 더 빨리 떨어짐\n\n• 획득 점수 증가\n\n• 난이도 상승'
    },
    'guide_how_to_play_tips': {
        'tr': '━━━ ÖNEMLİ İPUÇLARI ━━━\n\n• Gölge parça (Ghost Piece), parçanın nereye düşeceğini gösterir\n\n• Hold sistemini stratejik olarak kullanın\n\n• Sıradaki parçaları sürekli kontrol edin\n\n• Quadrix (4 satır) yapmak için bir kenarı açık bırakın',
        'en': '━━━ IMPORTANT TIPS ━━━\n\n• Ghost piece shows where the piece will land\n\n• Use Hold system strategically\n\n• Keep checking the next pieces\n\n• Leave one edge open for Quadrix (4-line clear)',
        'ja': '━━━ 重要ヒント ━━━\n\n• ゴーストピースは着地点を示す\n\n• ホールドを戦略的に使う\n\n• 次のピースを常に確認\n\n• テトリス(4ライン)用に片側を空ける',
        'zh': '━━━ 重要提示 ━━━\n\n• 幽灵方块显示落点\n\n• 战略性使用 Hold 系统\n\n• 始终注意下一个方块\n\n• 为 Quadrix（4 行）留一侧空位',
        'ko': '━━━ 중요 팁 ━━━\n\n• 고스트 피스는 떨어질 위치를 보여줍니다\n\n• 홀드 시스템을 전략적으로 사용하세요\n\n• 다음 피스를 계속 확인하세요\n\n• 테트리스(4줄)를 위해 한쪽을 비워두세요'
    },
    
    # --- Oyun Modları Bölümü ---
    'guide_mode_campaign': {
        'tr': '• Görev Modu: 100 seviyelik macera. Seviye hedeflerini tamamlayıp yıldız toplayın.',
        'en': '• Campaign Mode: 100-level adventure. Complete objectives and earn stars.',
        'ja': '• キャンペーン: 100レベルの冒険。目標達成で星を獲得。',
        'zh': '• 任务模式：100关冒险。完成关卡目标并获得星星。',
        'ko': '• 캠페인 모드: 100레벨 모험. 목표를 완료하고 별을 획득하세요.'
    },
    'guide_mode_name_campaign': {
        'tr': 'Görev Modu', 'en': 'Campaign', 'de': 'Kampagne', 'fr': 'Campagne', 'es': 'Campaña', 'it': 'Campagna', 'pt': 'Campanha', 'ja': 'キャンペーン', 'zh': '任务模式', 'ko': '캠페인'
    },
    'guide_mode_classic': {
        'tr': '• Klasik Mod: Sonsuz modu. Elinizden geldiğince uzun oynayın ve yüksek skor yapın.',
        'en': '• Classic Mode: Endless mode. Play as long as you can and achieve high scores.',
        'ja': '• クラシック: エンドレス。できるだけ長くプレイして高スコア。',
        'zh': '• 经典模式：无尽模式。尽可能长时间游玩并取得高分。',
        'ko': '• 클래식 모드: 무한 모드. 가능한 오래 플레이해 고득점을 노리세요.'
    },
    'guide_mode_name_classic': {
        'tr': 'Klasik', 'en': 'Classic', 'de': 'Klassik', 'fr': 'Classique', 'es': 'Clásico', 'it': 'Classico', 'pt': 'Clássico', 'ja': 'クラシック', 'zh': '经典', 'ko': '클래식'
    },
    'guide_mode_sprint': {
        'tr': '• Sprint: 40 satırı mümkün olan en kısa sürede temizleyin. Hız yarışı!',
        'en': '• Sprint: Clear 40 lines as fast as possible. It\'s a race against time!',
        'ja': '• スプリント: 40ラインを最速で消す。タイムアタック！',
        'zh': '• 冲刺：尽可能快地清除40行。与时间赛跑！',
        'ko': '• 스프린트: 40줄을 최대한 빨리 지우세요. 시간과의 경주!'
    },
    'guide_mode_name_sprint': {
        'tr': 'Sprint', 'en': 'Sprint', 'de': 'Sprint', 'fr': 'Sprint', 'es': 'Sprint', 'it': 'Sprint', 'pt': 'Sprint', 'ja': 'スプリント', 'zh': '冲刺', 'ko': '스프린트'
    },
    'guide_mode_ultra': {
        'tr': '• Ultra: 3 dakikada mümkün olan en yüksek skoru yapın.',
        'en': '• Ultra: Score as high as possible within 3 minutes.',
        'ja': '• ウルトラ: 3分以内に最高スコアを狙う。',
        'zh': '• 超强：在3分钟内尽可能获得高分。',
        'ko': '• 울트라: 3분 안에 최대 점수를 노리세요.'
    },
    'guide_mode_name_ultra': {
        'tr': 'Ultra', 'en': 'Ultra', 'de': 'Ultra', 'fr': 'Ultra', 'es': 'Ultra', 'it': 'Ultra', 'pt': 'Ultra', 'ja': 'ウルトラ', 'zh': '超强', 'ko': '울트라'
    },
    'guide_mode_zen': {
        'tr': '• Zen: Stressiz, sonsuza kadar oynayın. Game over yok, sadece rahatlık.',
        'en': '• Zen: Stress-free endless play. No game over, just relaxation.',
        'ja': '• ゼン: ストレスなしの無限プレイ。ゲームオーバーなし。',
        'zh': '• 禅：无压力的无限游玩。没有游戏结束，只有放松。',
        'ko': '• 젠: 스트레스 없는 무한 플레이. 게임 오버 없이 편안하게.'
    },
    'guide_mode_name_zen': {
        'tr': 'Zen', 'en': 'Zen', 'de': 'Zen', 'fr': 'Zen', 'es': 'Zen', 'it': 'Zen', 'pt': 'Zen', 'ja': 'ゼン', 'zh': '禅', 'ko': '젠'
    },
    'guide_mode_survival': {
        'tr': '• Hayatta Kalma: Zorluk sürekli artar. Ne kadar dayanabilirsiniz?',
        'en': '• Survival: Difficulty constantly increases. How long can you last?',
        'ja': '• サバイバル: 難易度が上がり続ける。どこまで耐える？',
        'zh': '• 生存：难度不断上升。你能坚持多久？',
        'ko': '• 서바이벌: 난이도가 계속 상승합니다. 얼마나 버틸 수 있나요?'
    },
    'guide_mode_name_survival': {
        'tr': 'Survival', 'en': 'Survival', 'de': 'Überleben', 'fr': 'Survie', 'es': 'Supervivencia', 'it': 'Sopravvivenza', 'pt': 'Sobrevivência', 'ja': 'サバイバル', 'zh': '生存', 'ko': '서바이벌'
    },
    'guide_mode_cascade': {
        'tr': '• Kaskad: Parçalar yerleştikten sonra bloklar aşağı düşerek yeni birleşimler oluşturur.',
        'en': '• Cascade: After placement, blocks fall down creating chain reactions.',
        'ja': '• カスケード: 設置後にブロックが落下し連鎖が発生。',
        'zh': '• 级联：放置后方块下落，形成连锁反应。',
        'ko': '• 캐스케이드: 배치 후 블록이 떨어져 연쇄가 발생합니다.'
    },
    'guide_mode_name_cascade': {
        'tr': 'Cascade', 'en': 'Cascade', 'de': 'Cascade', 'fr': 'Cascade', 'es': 'Cascade', 'it': 'Cascade', 'pt': 'Cascade', 'ja': 'カスケード', 'zh': '级联', 'ko': '캐스케이드'
    },
    'guide_mode_tetris2': {
        'tr': '• Quadrix Extra: 7 klasik parçaya ek olarak 4 yeni parça türü (P, Q, U, Plus).',
        'en': '• Quadrix Extra: 4 new piece types (P, Q, U, Plus) in addition to 7 classic pieces.',
        'ja': '• テトリスエクストラ: 7種に加え新ピース(P, Q, U, Plus)。',
        'zh': '• 俄罗斯方块 Extra：在7种经典方块外新增4种方块（P、Q、U、Plus）。',
        'ko': '• 테트리스 엑스트라: 7가지 클래식 피스에 더해 4종(P, Q, U, Plus) 추가.'
    },
    'guide_mode_name_tetris2': {
        'tr': 'Quadrix Extra', 'en': 'Quadrix Extra', 'de': 'Quadrix Extra', 'fr': 'Quadrix Extra', 'es': 'Quadrix Extra', 'it': 'Quadrix Extra', 'pt': 'Quadrix Extra', 'ja': 'テトリスエクストラ', 'zh': 'Quadrix Extra', 'ko': '테트리스 엑스트라'
    },
    'guide_mode_wide': {
        'tr': '• Geniş Mod: Tahta genişliği 20 blok. Daha fazla alan, daha fazla strateji!',
        'en': '• Wide Mode: Board width is 20 blocks. More space, more strategy!',
        'ja': '• ワイド: 幅20ブロック。広い盤面で戦略拡大。',
        'zh': '• 宽屏模式：棋盘宽度 20 格。空间更大，策略更多！',
        'ko': '• 와이드 모드: 보드 폭 20블록. 더 큰 공간, 더 많은 전략!'
    },
    'guide_mode_name_wide': {
        'tr': 'Wide', 'en': 'Wide', 'de': 'Wide', 'fr': 'Wide', 'es': 'Wide', 'it': 'Wide', 'pt': 'Wide', 'ja': 'ワイド', 'zh': '宽屏', 'ko': '와이드'
    },
    'guide_mode_mystery': {
        'tr': '• Kart Ustalığı (Mystery): Özel kartlar kullanarak taktiksel avantajlar elde edin!',
        'en': '• Card Mastery (Mystery): Use special cards to gain tactical advantages!',
        'ja': '• カードマスタリー(Mystery): 特殊カードで戦術的優位を得る。',
        'zh': '• 卡牌大师（Mystery）：使用特殊卡牌获得战术优势！',
        'ko': '• 카드 마스터리(미스터리): 특수 카드로 전술적 우위를 얻으세요!'
    },
    'guide_mode_name_mystery': {
        'tr': 'Kart Ustalığı', 'en': 'Card Mastery', 'de': 'Kartenmeisterschaft', 'fr': 'Maîtrise des Cartes', 'es': 'Maestría de Cartas', 'it': 'Maestria delle Carte', 'pt': 'Maestria de Cartas', 'ja': 'カードマスタリー', 'zh': '卡牌大师', 'ko': '카드 마스터리'
    },
    'guide_mode_pvp': {
        'tr': '• PvP: 2 oyuncu yan yana yarışır. Sildiğiniz satırlar rakibe çöp satır olarak gider!',
        'en': '• PvP: 2 players compete side by side. Lines you clear send garbage to opponent!',
        'ja': '• PvP: 2人対戦。消したラインがお邪魔行として相手に送られる。',
        'zh': '• PvP：两名玩家并排对战。你消除的行会作为垃圾行送给对手！',
        'ko': '• PvP: 두 플레이어가 나란히 경쟁합니다. 지운 줄이 상대에게 가비지로 전송됩니다!'
    },
    'guide_mode_name_pvp': {
        'tr': 'PvP', 'en': 'PvP', 'de': 'PvP', 'fr': 'PvP', 'es': 'PvP', 'it': 'PvP', 'pt': 'PvP', 'ja': 'PvP', 'zh': 'PvP', 'ko': 'PvP'
    },
    'guide_mode_daily': {
        'tr': '• Günlük Meydan Okuma: Her gün yeni hedefler ve ödüller!',
        'en': '• Daily Challenge: New goals and rewards every day!',
        'ja': '• デイリーチャレンジ: 毎日新しい目標と報酬。',
        'zh': '• 每日挑战：每天都有新的目标和奖励！',
        'ko': '• 데일리 챌린지: 매일 새로운 목표와 보상!'
    },
    'guide_mode_name_daily': {
        'tr': 'Günlük', 'en': 'Daily', 'de': 'Täglich', 'fr': 'Quotidien', 'es': 'Diario', 'it': 'Giornaliero', 'pt': 'Diário', 'ja': 'デイリー', 'zh': '每日', 'ko': '데일리'
    },
    'guide_mode_hardcore': {
        'tr': '• Hardcore: Ters kontroller, gizli bilgiler ve yüksek risk. Sadece ustalar için!',
        'en': '• Hardcore: Inverted controls, hidden info, and high risk. Only for masters!',
        'ja': '• ハードコア: 反転操作・隠し情報・高リスク。達人向け！',
        'zh': '• 硬核：反向控制、隐藏信息、高风险。只适合高手！',
        'ko': '• 하드코어: 반전 조작, 숨겨진 정보, 높은 위험. 고수만을 위한 모드!'
    },
    'guide_mode_name_hardcore': {
        'tr': 'Hardcore', 'en': 'Hardcore', 'de': 'Hardcore', 'fr': 'Hardcore', 'es': 'Hardcore', 'it': 'Hardcore', 'pt': 'Hardcore', 'ja': 'ハードコア', 'zh': '硬核', 'ko': '하드코어'
    },
    
    # --- Kartlar Bölümü ---
    'guide_cards_intro_subtitle': {
        'tr': 'Kart Sistemine Giriş', 'en': 'Introduction to Card System', 'ja': 'カードシステム入門', 'zh': '卡牌系统入门', 'ko': '카드 시스템 소개'
    },
    'guide_cards_intro': {
        'tr': 'Kart Ustalığı modunda, oyun sırasında özel kartlar kazanırsınız. Bu kartlar çeşitli güçlendirmeler ve özel yetenekler sağlar. Kartlar 1-9 tuşları veya fare ile kullanılabilir. Her kart tek kullanımlıktır (bazı perkler hariç).',
        'en': 'In Card Mastery mode, you earn special cards during gameplay. These cards provide various enhancements and special abilities. Cards can be used with 1-9 keys or mouse. Each card is single-use (except some perks).',
        'ja': 'カードマスタリーでは、プレイ中に特別なカードを獲得します。カードは強化や特殊能力を付与します。1〜9キーまたはマウスで使用可能。カードは基本的に使い切り(一部パークを除く)。',
        'zh': '在卡牌大师模式中，游戏过程中会获得特殊卡牌。这些卡牌提供各种强化和特殊能力。卡牌可用 1-9 键或鼠标使用。每张卡为一次性（部分特性除外）。',
        'ko': '카드 마스터리 모드에서는 게임 중에 특별한 카드를 획득합니다. 이 카드들은 다양한 강화와 특수 능력을 제공합니다. 카드는 1-9 키 또는 마우스로 사용할 수 있습니다. 각 카드는 일회용입니다(일부 특성 제외).'
    },
    
    'guide_cards_score_subtitle': {
        'tr': 'Skor ve Temizleme Kartları', 'en': 'Score & Clearing Cards', 'ja': 'スコア&クリア系カード', 'zh': '得分与清除类卡牌', 'ko': '점수 및 클리어 카드'
    },
    'guide_card_score': {
        'tr': '• Puan Patlaması: Anında +1000 puan kazandırır.',
        'en': '• Score Burst: Instantly grants +1000 points.',
        'ja': '• スコアバースト: 即時+1000点。',
        'zh': '• 得分爆发：立即获得 +1000 分。',
        'ko': '• 스코어 버스트: 즉시 +1000점.'
    },
    'guide_card_clear_rows': {
        'tr': '• Satır Temizleyici: En alttaki dolu satırları anında siler.',
        'en': '• Row Clearer: Instantly clears bottom filled rows.',
        'ja': '• ラインクリア: 最下部の埋まった行を即時消去。',
        'zh': '• 行清除：立即清除最底部已填充的行。',
        'ko': '• 라인 클리어: 바닥의 채워진 줄을 즉시 삭제.'
    },
    'guide_card_column_cleanse': {
        'tr': '• Sütun Temizleme: Seçilen dikey sütunu tamamen temizler.',
        'en': '• Column Cleanse: Completely clears a selected vertical column.',
        'ja': '• カラムクレンジ: 選択列を完全消去。',
        'zh': '• 列净化：完全清除选定的垂直列。',
        'ko': '• 컬럼 클렌즈: 선택한 세로 열을 완전히 제거.'
    },
    'guide_card_peak_sculpt': {
        'tr': '• Zirve Yontma: Tahtadaki en yüksek blokları keser.',
        'en': '• Peak Sculpt: Trims the highest blocks on the board.',
        'ja': '• ピークカット: 最も高いブロックを削る。',
        'zh': '• 峰值削减：削去棋盘上最高的方块。',
        'ko': '• 피크 스컬프: 보드의 가장 높은 블록을 깎아냄.'
    },
    'guide_card_gravity_well': {
        'tr': '• Yerçekimi Kuyusu: Tüm boş alanları kapatarak blokları aşağı çeker.',
        'en': '• Gravity Well: Pulls all blocks down, closing gaps.',
        'ja': '• グラビティウェル: すべての隙間を埋めるように落下させる。',
        'zh': '• 重力井：填补空隙并将所有方块下拉。',
        'ko': '• 그래비티 웰: 모든 블록을 아래로 끌어내려 틈을 메움.'
    },
    
    'guide_cards_manipulation_subtitle': {
        'tr': 'Tahta Manipülasyon Kartları', 'en': 'Board Manipulation Cards', 'ja': '盤面操作カード', 'zh': '棋盘操控类卡牌', 'ko': '보드 조작 카드'
    },
    'guide_card_row_shuffle': {
        'tr': '• Satır Karıştırma: Tahtadaki satırların sırasını rastgele değiştirir.',
        'en': '• Row Shuffle: Randomly reorders the rows on the board.',
        'ja': '• ラインシャッフル: 盤面の行の順番をランダムに入れ替える。',
        'zh': '• 行洗牌：随机重新排列棋盘的行。',
        'ko': '• 라인 셔플: 보드의 줄 순서를 무작위로 섞음.'
    },
    'guide_card_block_magnet': {
        'tr': '• Blok Mıknatısı: Dağınık blokları merkeze doğru çeker.',
        'en': '• Block Magnet: Pulls scattered blocks towards center.',
        'ja': '• ブロックマグネット: 散らばったブロックを中心へ引き寄せる。',
        'zh': '• 方块磁铁：将散落的方块拉向中心。',
        'ko': '• 블록 마그넷: 흩어진 블록을 중앙으로 끌어당김.'
    },
    'guide_card_nova_burst': {
        'tr': '• Nova Patlaması: Merkezdeki 5x5 alanı temizler.',
        'en': '• Nova Burst: Clears a 5x5 area in the center.',
        'ja': '• ノヴァバースト: 中央の5x5を消去。',
        'zh': '• 新星爆发：清除中央 5x5 区域。',
        'ko': '• 노바 버스트: 중앙 5x5 영역을 제거.'
    },
    'guide_card_laser_drill': {
        'tr': '• Lazer Matkap: Seçilen sütunda dikey bir çizgiyi siler.',
        'en': '• Laser Drill: Drills down through a selected column.',
        'zh': '• 激光钻：清除选定列中的垂直一条线。',
        'ko': '• 레이저 드릴: 선택한 열을 세로로 관통해 제거.',
        'ja': '• レーザードリル: 選択列を縦に貫いて消去。'
    },
    'guide_card_force_piece': {
        'tr': '• Parça Zorlama: Sıradaki parçayı istediğiniz parça türüyle değiştirir.',
        'en': '• Force Piece: Replaces next piece with your desired type.',
        'ja': '• ピース強制: 次のピースを好きな形に変更。',
        'zh': '• 强制方块：将下一块替换为你想要的类型。',
        'ko': '• 피스 강제: 다음 피스를 원하는 형태로 변경.'
    },
    
    'guide_cards_buffs_subtitle': {
        'tr': 'Güçlendirme Kartları', 'en': 'Buff Cards', 'ja': '強化カード', 'zh': '增益卡', 'ko': '버프 카드'
    },
    'guide_card_combo_boost': {
        'tr': '• Kombo Arttırıcı: Bir sonraki temizleme için kombo çarpanını artırır.',
        'en': '• Combo Boost: Increases combo multiplier for next clear.',
        'ja': '• コンボブースト: 次の消去のコンボ倍率を上げる。',
        'zh': '• 连击提升：提高下一次消除的连击倍率。',
        'ko': '• 콤보 부스트: 다음 제거의 콤보 배수를 증가.'
    },
    'guide_card_time_slow': {
        'tr': '• Zaman Yavaşlatma: Kısa süreliğine parça düşüş hızını yavaşlatır.',
        'en': '• Time Slow: Temporarily slows down piece fall speed.',
        'ja': '• タイムスロー: 一時的に落下速度を遅くする。',
        'zh': '• 时间减缓：短时间降低方块下落速度。',
        'ko': '• 타임 슬로우: 잠시 낙하 속도를 늦춤.'
    },
    'guide_card_line_bonus': {
        'tr': '• Satır Bonusu: Bir sonraki satır temizleme 2x puan verir.',
        'en': '• Line Bonus: Next line clear gives 2x points.',
        'ja': '• ラインボーナス: 次のライン消去が2倍。',
        'zh': '• 行奖励：下一次消行获得 2 倍分数。',
        'ko': '• 라인 보너스: 다음 라인 클리어가 2배 점수.'
    },
    'guide_card_quantum_tunneling': {
        'tr': '• Kuantum Tünelleme: Parçanın blokların içinden geçmesine izin verir.',
        'en': '• Quantum Tunneling: Allows piece to pass through blocks.',
        'ja': '• クアンタムトンネル: ピースがブロックを通過できる。',
        'zh': '• 量子隧穿：允许方块穿过其他方块。',
        'ko': '• 퀀텀 터널링: 피스가 블록을 통과할 수 있음.'
    },
    'guide_card_ghost_echo': {
        'tr': '• Hayalet Yansıması: Gölge parçayı kalıcı olarak yerleştirir.',
        'en': '• Ghost Echo: Permanently places the ghost piece.',
        'ja': '• ゴーストエコー: ゴーストピースを恒久的に配置。',
        'zh': '• 幽灵回声：永久放置幽灵方块。',
        'ko': '• 고스트 에코: 고스트 피스를 영구 배치.'
    },
    
    'guide_cards_perks_subtitle': {
        'tr': 'Kalıcı Perkler', 'en': 'Permanent Perks', 'ja': '永続パーク', 'zh': '永久特性', 'ko': '영구 특전'
    },
    'guide_perk_explosive': {
        'tr': '• Patlayıcı Bloklar: Parçalar yerleştiğinde küçük bir patlama yapar.',
        'en': '• Explosive Blocks: Pieces cause small explosions when placed.',
        'ja': '• 爆発ブロック: 設置時に小さな爆発を起こす。',
        'zh': '• 爆炸方块：放置时产生小型爆炸。',
        'ko': '• 폭발 블록: 배치 시 작은 폭발 발생.'
    },
    'guide_perk_cushion': {
        'tr': '• Yastık: Hard drop sonrası 1 saniyelik hareket şansı.',
        'en': '• Cushion: 1 second movement window after hard drop.',
        'ja': '• クッション: ハードドロップ後に1秒の操作猶予。',
        'zh': '• 缓冲：硬降后有 1 秒移动时间。',
        'ko': '• 쿠션: 하드 드롭 후 1초 이동 여유.'
    },
    'guide_perk_chrono': {
        'tr': '• Kronometre: Her satır temizleme süreyi 5 saniye uzatır.',
        'en': '• Chrono: Each line clear extends time by 5 seconds.',
        'ja': '• クロノ: ライン消去ごとに5秒延長。',
        'zh': '• 计时器：每清除一行延长 5 秒。',
        'ko': '• 크로노: 라인 소거마다 5초 연장.'
    },
    'guide_perk_phase': {
        'tr': '• Faz Geçişi: Parça duvarlardan geçebilir (ekranın diğer tarafından çıkar).',
        'en': '• Phase Shift: Piece can pass through walls (wraps around).',
        'ja': '• フェーズシフト: 壁をすり抜けて反対側に出る。',
        'zh': '• 相位穿越：方块可穿过墙壁（从另一侧出现）。',
        'ko': '• 페이즈 시프트: 벽을 통과해 반대편에서 나타남.'
    },
    'guide_perk_synergy': {
        'tr': '• Sinerji: Aynı renk blokların yan yana gelmesi ek puan verir.',
        'en': '• Synergy: Same color blocks adjacent give bonus points.',
        'ja': '• シナジー: 同色ブロックが隣接するとボーナス。',
        'zh': '• 协同：相同颜色方块相邻可获得额外分数。',
        'ko': '• 시너지: 같은 색 블록이 인접하면 보너스 점수.'
    },
    'guide_perk_second_pocket': {
        'tr': '• İkinci Cep: İki ayrı parça saklama alanı (Hold).',
        'en': '• Second Pocket: Two separate hold slots for pieces.',
        'ja': '• セカンドポケット: ホールド枠が2つになる。',
        'zh': '• 第二口袋：两个独立的保留槽（Hold）。',
        'ko': '• 세컨드 포켓: 홀드 슬롯이 2개.'
    },
    'guide_perk_alchemist': {
        'tr': '• Simyacı: Her 5 parçada rastgele bir kart kazanırsınız.',
        'en': '• Alchemist: Earn a random card every 5 pieces.',
        'ja': '• アルケミスト: 5ピースごとにランダムカード獲得。',
        'zh': '• 炼金术士：每 5 个方块获得一张随机卡。',
        'ko': '• 알케미스트: 5피스마다 랜덤 카드 획득.'
    },
    
    # --- İpuçları ve SSS ---
    'guide_tips_intro': {
        'tr': '[UZMAN İPUÇLARI]', 'en': '[EXPERT TIPS]', 'ja': '[上級者のヒント]', 'zh': '[专家提示]', 'ko': '[전문가 팁]'
    },
    'guide_tip_1': {
        'tr': '• T-Spin tekniğini öğrenin: T parçasını döndürerek dar boşluklara yerleştirmek ekstra puan kazandırır.',
        'en': '• Learn T-Spin: Rotating T piece into tight spaces earns extra points.',
        'ja': '• Tスピンを覚える: Tピースを回転で狭い隙間に入れると追加得点。',
        'zh': '• 学习 T-Spin：将 T 方块旋转放入狭小空隙可获得额外分数。',
        'ko': '• T-스핀을 익히세요: T 피스를 회전해 좁은 공간에 넣으면 추가 점수.'
    },
    'guide_tip_2': {
        'tr': '• Düz parçayı (I) hep kenarda Quadrix için saklayın.',
        'en': '• Always save I-piece for Quadrix on the side.',
        'ja': '• Iピースはテトリス用に温存する。',
        'zh': '• 始终把 I 方块留在一侧用于 Quadrix。',
        'ko': '• I 피스를 테트리스를 위해 항상 아껴두세요.'
    },
    'guide_tip_3': {
        'tr': '• Orta alanı mümkün olduğunca düz tutun, boşluklar oluşmasını engelleyin.',
        'en': '• Keep the center flat, avoid creating holes.',
        'ja': '• 中央をできるだけ平らに保ち、穴を作らない。',
        'zh': '• 尽量保持中间平坦，避免形成空洞。',
        'ko': '• 중앙을 최대한 평평하게 유지해 구멍을 만들지 마세요.'
    },
    'guide_tip_4': {
        'tr': '• Kombo zincirleri kurmak için satırları art arda temizlemeye çalışın.',
        'en': '• Build combo chains by clearing lines consecutively.',
        'ja': '• 連続消去でコンボをつなぐ。',
        'zh': '• 尝试连续消行来建立连击链。',
        'ko': '• 연속으로 줄을 지워 콤보 체인을 만드세요.'
    },
    'guide_tip_5': {
        'tr': '• Kart modunda kartları doğru zamanda kullanmak kritik önem taşır.',
        'en': '• In card mode, using cards at the right time is crucial.',
        'ja': '• カードモードでは使うタイミングが重要。',
        'zh': '• 在卡牌模式中，正确时机使用卡牌至关重要。',
        'ko': '• 카드 모드에서는 적절한 타이밍에 카드를 사용하는 것이 중요합니다.'
    },
    'guide_faq_intro': {
        'tr': '\n[SIK SORULAN SORULAR]', 'en': '\n[FREQUENTLY ASKED QUESTIONS]', 'ja': '\n[よくある質問]', 'zh': '\n[常见问题]', 'ko': '\n[자주 묻는 질문]'
    },
    'guide_faq_1': {
        'tr': 'Q: Oyun neden çok hızlı?\nA: Seviye arttıkça hız artar. Ayarlardan başlangıç seviyesini düşürebilirsiniz.',
        'en': 'Q: Why is the game so fast?\nA: Speed increases with level. You can lower starting level in settings.',
        'ja': 'Q: ゲームが速すぎる？\nA: レベルが上がると速度が上がります。設定で開始レベルを下げられます。',
        'zh': 'Q：游戏为什么这么快？\nA：速度会随等级提升而增加。你可以在设置中降低起始等级。',
        'ko': 'Q: 게임이 왜 이렇게 빠르나요?\nA: 레벨이 올라갈수록 속도가 증가합니다. 설정에서 시작 레벨을 낮출 수 있습니다.'
    },
    'guide_faq_2': {
        'tr': 'Q: Kartlar nasıl kazanılır?\nA: Kart Ustalığı modunda satır temizleyerek ve belirli hedeflere ulaşarak kart kazanırsınız.',
        'en': 'Q: How to earn cards?\nA: In Card Mastery mode, clear lines and reach certain goals to earn cards.',
        'ja': 'Q: カードはどうやって入手？\nA: カードマスタリーでライン消去や目標達成で入手します。',
        'zh': 'Q：如何获得卡牌？\nA：在卡牌大师模式中，通过消行并达成特定目标获得卡牌。',
        'ko': 'Q: 카드는 어떻게 얻나요?\nA: 카드 마스터리 모드에서 줄을 지우고 특정 목표를 달성하면 얻습니다.'
    },
    'guide_faq_3': {
        'tr': 'Q: Ayarlar kaydediliyor mu?\nA: Evet, tüm ayarlar otomatik olarak kaydedilir.',
        'en': 'Q: Are settings saved?\nA: Yes, all settings are automatically saved.',
        'ja': 'Q: 設定は保存される？\nA: はい、すべて自動保存されます。',
        'zh': 'Q：设置会保存吗？\nA：是的，所有设置都会自动保存。',
        'ko': 'Q: 설정은 저장되나요?\nA: 네, 모든 설정은 자동으로 저장됩니다.'
    },
    # ============ KART GALERİSİ ÇEVİRİLERİ ============
    'guide_card_clear_rows_name': {
        'tr': 'Alt Süpür', 'en': 'Bottom Sweep', 'ja': 'ボトムスイープ', 'zh': '底部清扫', 'ko': '바닥 쓸기'
    },
    'guide_card_clear_rows_desc': {
        'tr': 'En alttaki 1-3 satırı anında temizler. Bloklar aşağı oturur ve skor kazanırsınız.',
        'en': 'Instantly clears the bottom 1-3 rows. Blocks settle down and you earn score.',
        'ja': '最下部の1〜3行を即時消去。ブロックが沈み、スコア獲得。',
        'zh': '立即清除底部 1-3 行。方块下沉并获得分数。',
        'ko': '바닥 1-3줄을 즉시 제거합니다. 블록이 내려가고 점수를 얻습니다.'
    },
    'guide_card_peak_sculpt_name': {
        'tr': 'Tepe Kesici', 'en': 'Peak Cutter', 'ja': 'ピークカッター', 'zh': '顶峰削减', 'ko': '피크 커터'
    },
    'guide_card_peak_sculpt_desc': {
        'tr': 'En yüksek 2-4 bloğu keser ve tahtayı düzleştirir. Tıkanıklıkları gidermek için idealdir.',
        'en': 'Cuts the top 2-4 blocks and flattens the board. Ideal for clearing congestion.',
        'ja': '最も高い2〜4ブロックを削り、盤面を平坦化。詰まり解消に最適。',
        'zh': '削去顶部 2-4 个方块并拉平棋盘。适合清除拥堵。',
        'ko': '상단 2-4블록을 잘라 보드를 평평하게 만듭니다. 막힘 해소에 적합.'
    },
    'guide_card_row_shuffle_name': {
        'tr': 'Blok Karıştırıcı', 'en': 'Block Shuffler', 'ja': 'ブロックシャッフル', 'zh': '方块洗牌', 'ko': '블록 셔플러'
    },
    'guide_card_row_shuffle_desc': {
        'tr': 'Alt 2-4 satırdaki blokları rastgele karıştırır. Şansınızı deneyin - bazen boşluklar kapanır!',
        'en': 'Randomly shuffles blocks in the bottom 2-4 rows. Try your luck - sometimes gaps close!',
        'ja': '下2〜4行のブロックをランダムにシャッフル。運試しで隙間が埋まることも。',
        'zh': '随机打乱底部 2-4 行的方块。试试运气——有时空隙会被填上！',
        'ko': '바닥 2-4줄의 블록을 무작위로 섞습니다. 운이 좋으면 빈틈이 메워질 수도!'
    },
    'guide_card_mini_bomb_name': {
        'tr': 'Mini Bomba', 'en': 'Mini Bomb', 'ja': 'ミニボム', 'zh': '迷你炸弹', 'ko': '미니 폭탄'
    },
    'guide_card_mini_bomb_desc': {
        'tr': 'Mevcut parça kilitlenince kendi hücreleri ve temas ettiği komşu blokları patlatır.',
        'en': 'When the current piece locks, it explodes its own cells and touching neighbor blocks.',
        'ja': 'ロック時、自身のセルと接触ブロックを爆破。',
        'zh': '当前方块锁定时，会爆炸自身格子及接触的邻近方块。',
        'ko': '현재 피스가 고정되면 자신의 칸과 접촉한 주변 블록을 폭발시킵니다.'
    },
    'guide_card_quantum_name': {
        'tr': 'Hayalet Parça', 'en': 'Ghost Piece', 'ja': 'ゴーストピース', 'zh': '幽灵方块', 'ko': '고스트 피스'
    },
    'guide_card_quantum_desc': {
        'tr': '3 kullanım hakkı: G tuşuyla parçayı hayalet yapın - blokların içinden geçebilir!',
        'en': '3 uses: Press G to make piece ghost - it can pass through blocks!',
        'ja': '3回: Gでピースをゴースト化。ブロックを通過できる！',
        'zh': '3 次使用：按 G 使方块变为幽灵——可穿过方块！',
        'ko': '3회 사용: G를 눌러 피스를 고스트화 — 블록을 통과할 수 있습니다!'
    },
    'guide_card_hammer_name': {
        'tr': 'Zip Dosyası', 'en': 'Zip File', 'ja': 'Zipファイル', 'zh': '压缩文件', 'ko': 'Zip 파일'
    },
    'guide_card_hammer_desc': {
        'tr': '3 kullanım hakkı: H tuşuyla mevcut parçayı anlık 1x1 bloğa dönüştürür.',
        'en': '3 uses: Press H to instantly transform current piece into a 1x1 block.',
        'ja': '3回: Hで現在のピースを即座に1x1ブロックへ。',
        'zh': '3 次使用：按 H 将当前方块瞬间变为 1x1 方块。',
        'ko': '3회 사용: H를 눌러 현재 피스를 즉시 1x1 블록으로 변환.'
    },
    'guide_card_laser_name': {
        'tr': 'Delici Parça', 'en': 'Drill Piece', 'ja': 'ドリルピース', 'zh': '钻头方块', 'ko': '드릴 피스'
    },
    'guide_card_laser_desc': {
        'tr': 'Mevcut parça düşerken önündeki blokları eritir. Tıkanmış alanları açmak için mükemmel!',
        'en': 'Current piece melts blocks in its path while falling. Perfect for opening clogged areas!',
        'ja': '落下中、進路のブロックを溶かす。詰まり解消に最適！',
        'zh': '当前方块下落时会熔化路径上的方块。非常适合打通堵塞区域！',
        'ko': '현재 피스가 떨어지는 동안 경로의 블록을 녹입니다. 막힌 구역을 여는 데 최적!'
    },
    'guide_card_sniper_name': {
        'tr': 'Keskin Nişancı', 'en': 'Sniper', 'ja': 'スナイパー', 'zh': '狙击手', 'ko': '스나이퍼'
    },
    'guide_card_sniper_desc': {
        'tr': '3 kullanım hakkı: Tahtada istediğiniz bir bloğu tıklayarak patlatın.',
        'en': '3 uses: Click on any block on the board to explode it.',
        'ja': '3回: 盤面の任意のブロックをクリックして爆破。',
        'zh': '3 次使用：点击棋盘任意方块即可爆破。',
        'ko': '3회 사용: 보드의 원하는 블록을 클릭해 폭발.'
    },
    'guide_card_nova_name': {
        'tr': 'Nova Patlaması', 'en': 'Nova Burst', 'ja': 'ノヴァバースト', 'zh': '新星爆发', 'ko': '노바 버스트'
    },
    'guide_card_nova_desc': {
        'tr': 'Sonraki 2-4 kilitlemede parçanın merkezinde 3x3 alan patlar. Güçlü temizlik!',
        'en': 'Next 2-4 locks explode a 3x3 area at piece center. Powerful cleaning!',
        'ja': '次の2〜4回のロックで中央3x3が爆発。強力な掃除！',
        'zh': '接下来 2-4 次锁定时，在方块中心爆炸 3x3 区域。强力清除！',
        'ko': '다음 2-4회 고정 시 피스 중심의 3x3이 폭발합니다. 강력한 청소!'
    },
    'guide_card_gravity_name': {
        'tr': 'Yerçekimi Dalgası', 'en': 'Gravity Wave', 'ja': 'グラビティウェーブ', 'zh': '重力波', 'ko': '그래비티 웨이브'
    },
    'guide_card_gravity_desc': {
        'tr': 'Tüm bloklar aşağı çöker, boşluklar kapanır. Oluşan dolu satırlar otomatik temizlenir.',
        'en': 'All blocks fall down, gaps close. Any complete rows are automatically cleared.',
        'ja': 'ブロックが落下して隙間が埋まり、完成行が自動消去される。',
        'zh': '所有方块下落，空隙被填补。形成的满行会自动清除。',
        'ko': '모든 블록이 내려가 빈틈이 메워집니다. 완성된 줄은 자동으로 제거됩니다.'
    },
    'guide_card_phase_name': {
        'tr': 'Şekil Değiştirici', 'en': 'Shape Shifter', 'ja': 'シェイプシフター', 'zh': '变形者', 'ko': '셰이프 시프터'
    },
    'guide_card_phase_desc': {
        'tr': '3 kullanım: LSHIFT ile parçayı karşıtına dönüştürün (L↔J, Z↔S). Stratejik esneklik!',
        'en': '3 uses: Press LSHIFT to swap piece to its mirror (L↔J, Z↔S). Strategic flexibility!',
        'ja': '3回: LSHIFTで左右反転(L↔J, Z↔S)。戦略的に柔軟！',
        'zh': '3 次使用：按 LSHIFT 将方块镜像（L↔J, Z↔S）。策略更灵活！',
        'ko': '3회 사용: LSHIFT로 피스를 좌우 반전(L↔J, Z↔S). 전략적 유연성!'
    },
    'guide_card_pocket_name': {
        'tr': 'Ekstra Cep', 'en': 'Extra Pocket', 'ja': 'エクストラポケット', 'zh': '额外口袋', 'ko': '엑스트라 포켓'
    },
    'guide_card_pocket_desc': {
        'tr': 'PERK: V tuşuyla ikinci bir parça saklayabilirsiniz. Daha fazla strateji seçeneği!',
        'en': 'PERK: Press V to hold a second piece. More strategic options!',
        'ja': 'PERK: Vで2つ目のピースを保持。戦略の幅が広がる！',
        'zh': '特性：按 V 可保留第二个方块。更多策略选择！',
        'ko': '특전: V를 눌러 두 번째 피스를 보관. 더 많은 전략 선택지!'
    },
    'guide_card_magnet_name': {
        'tr': 'Blok Manyetiği', 'en': 'Block Magnet', 'ja': 'ブロックマグネット', 'zh': '方块磁铁', 'ko': '블록 마그넷'
    },
    'guide_card_magnet_desc': {
        'tr': 'Efsanevi! Tüm boşluklar kapanır - bloklar birbirine yapışır. Tahta anında düzleşir.',
        'en': 'Legendary! All gaps close - blocks stick together. Board instantly flattens.',
        'ja': 'レジェンダリー！隙間が消え、盤面が一瞬で平坦になる。',
        'zh': '传说级！所有空隙关闭——方块彼此吸附。棋盘瞬间变平。',
        'ko': '전설급! 모든 빈틈이 사라지고 블록이 붙습니다. 보드가 즉시 평평해집니다.'
    },
    'guide_card_ghost_name': {
        'tr': 'İkinci Şans', 'en': 'Second Chance', 'ja': 'セカンドチャンス', 'zh': '第二次机会', 'ko': '세컨드 찬스'
    },
    'guide_card_ghost_desc': {
        'tr': 'Efsanevi! Ölümden dönüş: Oyun bitecekken üst yarıyı temizler, devam edersiniz.',
        'en': 'Legendary! Death save: When game would end, clears top half and you continue.',
        'ja': 'レジェンダリー！ゲーム終了直前に上半分を消去して続行。',
        'zh': '传说级！起死回生：游戏即将结束时清除上半部分并继续。',
        'ko': '전설급! 죽음 회피: 게임이 끝날 때 상단 절반을 지우고 계속합니다.'
    },
    'guide_perk_synergy_name': {
        'tr': 'Sinerji Bonus', 'en': 'Synergy Bonus', 'ja': 'シナジーボーナス', 'zh': '协同加成', 'ko': '시너지 보너스'
    },
    'guide_perk_synergy_desc': {
        'tr': 'Kalıcı PERK: Her aktif perk için +%10 skor bonusu. Perk toplayın, bonus artsın!',
        'en': 'Permanent PERK: +10% score bonus for each active perk. Collect perks, grow bonus!',
        'ja': '永続PERK: 有効なパークごとにスコア+10%。集めるほど強化！',
        'zh': '永久特性：每个激活特性 +10% 分数加成。收集特性，奖励更高！',
        'ko': '영구 특전: 활성 특성마다 점수 +10% 보너스. 특성을 모을수록 보너스 증가!'
    },
    'guide_perk_explosive_name': {
        'tr': 'Bomba Ustası', 'en': 'Bomb Master', 'ja': 'ボムマスター', 'zh': '炸弹大师', 'ko': '봄 마스터'
    },
    'guide_perk_explosive_desc': {
        'tr': '3 kullanım: M tuşuyla mevcut parçayı mini bomba yapın. Kilitlenince çevresini patlatır.',
        'en': '3 uses: Press M to make current piece a mini bomb. Explodes surroundings when locked.',
        'ja': '3回: Mで現在のピースをミニボム化。ロック時に周囲を爆破。',
        'zh': '3 次使用：按 M 将当前方块变为迷你炸弹。锁定时爆炸周围。',
        'ko': '3회 사용: M를 눌러 현재 피스를 미니 폭탄으로 만듭니다. 고정 시 주변 폭발.'
    },
    'guide_perk_chrono_name': {
        'tr': 'Zaman Kontrolü', 'en': 'Time Control', 'ja': 'タイムコントロール', 'zh': '时间控制', 'ko': '타임 컨트롤'
    },
    'guide_perk_chrono_desc': {
        'tr': 'Kalıcı PERK: Parça düşüş hızı %15 yavaşlar. Daha fazla düşünme zamanı!',
        'en': 'Permanent PERK: Piece fall speed slows by 15%. More time to think!',
        'ja': '永続PERK: 落下速度が15%低下。考える時間が増える！',
        'zh': '永久特性：方块下落速度降低 15%。有更多思考时间！',
        'ko': '영구 특전: 피스 낙하 속도가 15% 느려짐. 생각할 시간 증가!'
    },
    'guide_perk_cushion_name': {
        'tr': 'Yumuşak İniş', 'en': 'Soft Landing', 'ja': 'ソフトランディング', 'zh': '软着陆', 'ko': '소프트 랜딩'
    },
    'guide_perk_cushion_desc': {
        'tr': 'Kalıcı PERK: Parça kilitlenme gecikmesi 2× uzar. Daha fazla ayarlama şansı!',
        'en': 'Permanent PERK: Piece lock delay is 2× longer. More time to adjust placement!',
        'ja': '永続PERK: ロック遅延が2倍。調整の猶予が増える！',
        'zh': '永久特性：方块锁定延迟延长 2 倍。更有余地调整！',
        'ko': '영구 특전: 피스 고정 지연이 2배. 더 많은 조정 시간!'
    },
    'guide_perk_rewind_name': {
        'tr': 'Geri Sarma', 'en': 'Rewind', 'ja': 'リワインド', 'zh': '回溯', 'ko': '리와인드'
    },
    'guide_perk_rewind_desc': {
        'tr': '1 kullanım: R tuşuyla son hareketi geri alın. Hataları düzeltin!',
        'en': '1 use: Press R to undo last move. Fix mistakes!',
        'ja': '1回: Rで直前の操作を巻き戻す。ミスを修正！',
        'zh': '1 次使用：按 R 撤销上一步。修正失误！',
        'ko': '1회 사용: R을 눌러 마지막 이동을 되돌립니다. 실수 수정!'
    },
    'guide_card_future_name': {
        'tr': 'Geleceği Değiştiren', 'en': 'Future Changer', 'ja': 'フューチャーチェンジャー', 'zh': '未来改变者', 'ko': '퓨처 체인저'
    },
    'guide_card_future_desc': {
        'tr': 'Nadir! Sıradaki 2 parçayı seçmenize izin verir. Stratejik planlama için mükemmel!',
        'en': 'Rare! Lets you choose the next 2 pieces. Perfect for strategic planning!',
        'ja': 'レア！次の2ピースを選べる。戦略計画に最適！',
        'zh': '稀有！允许你选择接下来的 2 个方块。非常适合战略规划！',
        'ko': '희귀! 다음 2개 피스를 선택할 수 있습니다. 전략 계획에 최적!'
    },
    'guide_card_speed_burst_name': {
        'tr': 'Hız Patlaması', 'en': 'Speed Burst', 'ja': 'スピードバースト', 'zh': '速度爆发', 'ko': '스피드 버스트'
    },
    'guide_card_speed_burst_desc': {
        'tr': 'Süreli: %50 daha hızlı düşüş ve her satır için 2x puan!',
        'en': 'Timed: 50% faster drop and 2x points for every line!',
        'ja': '時間制: 落下50%高速化＋ラインごとに2倍得点！',
        'zh': '限时：下落速度快 50%，每行 2 倍得分！',
        'ko': '시간제: 낙하 50% 빨라지고 각 줄 2배 점수!'
    },
    'guide_card_flexible_border_name': {
        'tr': 'Esnek Sınır', 'en': 'Flexible Border', 'ja': 'フレキシブルボーダー', 'zh': '弹性边界', 'ko': '플렉서블 보더'
    },
    'guide_card_flexible_border_desc': {
        'tr': 'PERK: Parçalar tahtanın kenarlarından 1 blok dışına çıkabilir.',
        'en': 'PERK: Pieces can move 1 block outside the board borders.',
        'ja': 'PERK: ピースは盤面の端から1ブロック外まで移動できる。',
        'zh': '特性：方块可移出棋盘边界 1 格。',
        'ko': '특전: 피스가 보드 경계 밖으로 1칸 이동 가능.'
    },
    'guide_card_time_capsule_name': {
        'tr': 'Zaman Kapsülü', 'en': 'Time Capsule', 'ja': 'タイムカプセル', 'zh': '时间胶囊', 'ko': '타임 캡슐'
    },
    'guide_card_time_capsule_desc': {
        'tr': 'R ile kullan: ilk basış kaydeder, ikinci basış geri döndürür.',
        'en': 'Use with R: first press saves, second press restores.',
        'ja': 'Tで盤面を保存し、Rで戻る。',
        'zh': '按 T 保存棋盘状态，按 R 返回。',
        'ko': 'T로 보드 상태를 저장하고 R로 돌아갑니다.'
    },
    
    # ==================== YENİ KART LOKALİZASYONLARI ====================
    # --- Tuttuğunu Koparan (hold_destroyer varyantları) ---
    'card_hold_destroyer_title': {
        'tr': 'Tuttuğunu Koparan', 'en': 'Hold Breaker', 'ja': 'ホールドブレイカー', 'zh': '保留破坏者', 'ko': '홀드 브레이커'
    },
    'card_hold_destroyer_desc': {
        'tr': '{value} hak: Saklanan parçayı silme gücü! B tuşuyla kullan.',
        'en': '{value} use(s): Power to discard held piece! Press B to use.',
        'ja': '{value}回: 保持ピースを破棄する力！Bで使用。',
        'zh': '{value} 次使用：丢弃保留方块的能力！按 B 使用。',
        'ko': '{value}회 사용: 보관된 피스를 버리는 능력! B를 눌러 사용.'
    },
    'card_hold_destroyer_2_title': {
        'tr': 'Tuttuğunu Koparan', 'en': 'Hold Breaker', 'ja': 'ホールドブレイカー', 'zh': '保留破坏者', 'ko': '홀드 브레이커'
    },
    'card_hold_destroyer_2_desc': {
        'tr': '{value} hak: Saklanan parçayı silme gücü! B tuşuyla kullan.',
        'en': '{value} use(s): Power to discard held piece! Press B to use.',
        'ja': '{value}回: 保持ピースを破棄する力！Bで使用。',
        'zh': '{value} 次使用：丢弃保留方块的能力！按 B 使用。',
        'ko': '{value}회 사용: 보관된 피스를 버리는 능력! B를 눌러 사용.'
    },
    'card_hold_destroyer_3_title': {
        'tr': 'Tuttuğunu Koparan', 'en': 'Hold Breaker', 'ja': 'ホールドブレイカー', 'zh': '保留破坏者', 'ko': '홀드 브레이커'
    },
    'card_hold_destroyer_3_desc': {
        'tr': '{value} hak: Saklanan parçayı silme gücü! B tuşuyla kullan.',
        'en': '{value} use(s): Power to discard held piece! Press B to use.',
        'ja': '{value}回: 保持ピースを破棄する力！Bで使用。',
        'zh': '{value} 次使用：丢弃保留方块的能力！按 B 使用。',
        'ko': '{value}회 사용: 보관된 피스를 버리는 능력! B를 눌러 사용.'
    },
    'card_hold_destroyer_4_title': {
        'tr': 'Tuttuğunu Koparan', 'en': 'Hold Breaker', 'ja': 'ホールドブレイカー', 'zh': '保留破坏者', 'ko': '홀드 브레이커'
    },
    'card_hold_destroyer_4_desc': {
        'tr': '{value} hak: Saklanan parçayı silme gücü! B tuşuyla kullan.',
        'en': '{value} use(s): Power to discard held piece! Press B to use.',
        'ja': '{value}回: 保持ピースを破棄する力！Bで使用。',
        'zh': '{value} 次使用：丢弃保留方块的能力！按 B 使用。',
        'ko': '{value}회 사용: 보관된 피스를 버리는 능력! B를 눌러 사용.'
    },
    'card_hold_destroyer_5_title': {
        'tr': 'Tuttuğunu Koparan', 'en': 'Hold Breaker', 'ja': 'ホールドブレイカー', 'zh': '保留破坏者', 'ko': '홀드 브레이커'
    },
    'card_hold_destroyer_5_desc': {
        'tr': '{value} hak: Saklanan parçayı silme gücü! B tuşuyla kullan.',
        'en': '{value} use(s): Power to discard held piece! Press B to use.',
        'ja': '{value}回: 保持ピースを破棄する力！Bで使用。',
        'zh': '{value} 次使用：丢弃保留方块的能力！按 B 使用。',
        'ko': '{value}회 사용: 보관된 피스를 버리는 능력! B를 눌러 사용.'
    },
    # --- Renk Temizleme ---
    'card_color_cleanse_title': {
        'tr': 'Renk Temizleme', 'en': 'Color Cleanse', 'ja': 'カラークレンズ', 'zh': '颜色清除', 'ko': '컬러 클렌즈'
    },
    'card_color_cleanse_desc': {
        'tr': 'Rastgele bir renkteki tüm blokları temizler. Üstteki bloklar aşağıya düşer.',
        'en': 'Clears all blocks of a random color. Upper blocks fall down.',
        'ja': 'ランダムな色のブロックをすべて消去。上のブロックが落下する。',
        'zh': '清除随机一种颜色的所有方块。上方方块会下落。',
        'ko': '무작위 색상의 모든 블록을 제거합니다. 위의 블록이 내려갑니다.'
    },
    # --- Kumarbazın Zarı ---
    'card_gambler_dice_title': {
        'tr': 'Kumarbazın Zarı', 'en': "Gambler's Dice", 'ja': 'ギャンブラーのサイコロ', 'zh': '赌徒的骰子', 'ko': '도박사의 주사위'
    },
    'card_gambler_dice_desc': {
        'tr': 'Zar at! %50 şansla tüm tahta temizlenir ya da tahtanın yarısı rastgele blokla dolar.',
        'en': 'Roll the dice! 50% chance to clear the entire board or fill half with random blocks.',
        'ja': 'サイコロを振れ！50%の確率で全消去か、半分がランダムブロックで埋まる。',
        'zh': '掷骰子！50% 概率清除整个棋盘或一半被随机方块填满。',
        'ko': '주사위를 굴려라! 50% 확률로 보드 전체 제거 또는 절반이 랜덤 블록으로 채워짐.'
    },
    # --- Blok Atölyesi ---
    'card_block_workshop_card_title': {
        'tr': 'Blok Atölyesi', 'en': 'Block Workshop', 'ja': 'ブロック工房', 'zh': '方块工坊', 'ko': '블록 작업실'
    },
    'card_block_workshop_card_desc': {
        'tr': 'Popup bir atölye açılır ve tek seferlik maks 7 blokluk özel parça oluşturursun!',
        'en': 'Opens a workshop popup where you create a custom piece with up to 7 blocks!',
        'ja': 'ポップアップ工房が開き、最大7ブロックのカスタムピースを作成できる！',
        'zh': '弹出工坊窗口，一次性制作最多 7 个方块的自定义方块！',
        'ko': '작업실 팝업이 열리고 최대 7블록 커스텀 피스를 만들 수 있습니다!'
    },
    
    # ==================== PARÇA ATÖLYESİ ====================
    'piece_workshop_title': {
        'tr': 'PARÇA ATÖLYESİ',
        'en': 'PIECE WORKSHOP',
        'ja': 'ピース工房',
        'zh': '方块工坊',
        'ko': '피스 작업실'
    },
    'piece_workshop_tip': {
        'tr': 'Maks {max_blocks} blok | Bloklar bağlı olmalı | {modifier}+S: Kaydet',
        'en': 'Max {max_blocks} blocks | Blocks must be connected | {modifier}+S: Save',
        'ja': '最大{max_blocks}ブロック | ブロックは連結必須 | {modifier}+S: 保存'
    },
    'piece_workshop_counter': {
        'tr': '{count}/{max_blocks} blok',
        'en': '{count}/{max_blocks} blocks',
        'ja': '{count}/{max_blocks} ブロック'
    },
    'piece_workshop_save_button': {
        'tr': '{modifier}+S : Kaydet',
        'en': '{modifier}+S : Save',
        'ja': '{modifier}+S : 保存'
    },
    'piece_workshop_delete_button': {
        'tr': '{modifier}+D : Sil',
        'en': '{modifier}+D : Delete',
        'ja': '{modifier}+D : 削除'
    },
    'piece_workshop_custom_color': {
        'tr': 'ÖZEL RENK',
        'en': 'CUSTOM COLOR',
        'ja': 'カスタムカラー'
    },
    'piece_workshop_palette_title': {
        'tr': 'RENKLER',
        'en': 'COLORS',
        'ja': '色'
    },
    'piece_workshop_saved_pieces_title': {
        'tr': '📦 KAYITLI PARÇALAR',
        'en': '📦 SAVED PIECES',
        'ja': '📦 保存済みピース'
    },
    'piece_workshop_piece_count': {
        'tr': '{count} parça',
        'en': '{count} pieces',
        'ja': '{count} ピース'
    },
    'piece_workshop_no_pieces': {
        'tr': 'Henüz parça yok',
        'en': 'No pieces yet',
        'ja': 'まだピースがありません'
    },
    'piece_workshop_modes_title': {
        'tr': 'MODLAR',
        'en': 'MODES',
        'ja': 'モード'
    },
    'piece_workshop_modes_note_none': {
        'tr': 'Not: Hiç mod seçili değil — parça oyunda çıkmaz.',
        'en': 'Note: No modes selected — the piece will not appear in-game.',
        'ja': '注: モード未選択のため、ゲーム内に出現しません。'
    },
    'piece_workshop_modes_note_selected': {
        'tr': 'Not: Seçili modlarda bu parça oyunda çıkacak.',
        'en': 'Note: This piece will appear in selected modes.',
        'ja': '注: 選択したモードでこのピースが出現します。'
    },
    'piece_workshop_block_count': {
        'tr': '{count} blok',
        'en': '{count} blocks',
        'ja': '{count} ブロック'
    },
    'piece_workshop_all_modes': {
        'tr': 'Tüm modlar',
        'en': 'All modes',
        'ja': '全モード'
    },
    'piece_workshop_no_modes': {
        'tr': 'Mod yok',
        'en': 'No modes',
        'ja': 'モードなし'
    },
    'piece_workshop_mode_count': {
        'tr': '{count} mod',
        'en': '{count} modes',
        'ja': '{count} モード'
    },
    'piece_workshop_modes_updated': {
        'tr': 'Modlar güncellendi',
        'en': 'Modes updated',
        'ja': 'モードを更新しました'
    },
    'piece_workshop_color_changed': {
        'tr': 'Renk değiştirildi',
        'en': 'Color changed',
        'ja': '色を変更しました'
    },
    'piece_workshop_max_blocks': {
        'tr': 'Maksimum {max_blocks} blok ekleyebilirsin!',
        'en': 'You can add at most {max_blocks} blocks!',
        'ja': '追加できるのは最大{max_blocks}ブロック！'
    },
    'piece_workshop_blocks_connected_required': {
        'tr': 'Blok bağlı olmalı!',
        'en': 'Blocks must be connected!',
        'ja': 'ブロックは連結が必要！'
    },
    'piece_workshop_block_added': {
        'tr': 'Blok eklendi ({remaining} kaldı)',
        'en': 'Block added ({remaining} remaining)',
        'ja': 'ブロック追加 ({remaining} 残り)'
    },
    'piece_workshop_cannot_delete_breaks': {
        'tr': 'Bu bloğu silemezsin (bağlantı kopuyor)!',
        'en': 'You cannot delete this block (connection would break)!',
        'ja': 'このブロックは削除できません(連結が切れます)。'
    },
    'piece_workshop_block_deleted': {
        'tr': 'Blok silindi',
        'en': 'Block deleted',
        'ja': 'ブロックを削除しました'
    },
    'piece_workshop_grid_cleared': {
        'tr': 'Grid temizlendi',
        'en': 'Grid cleared',
        'ja': 'グリッドをクリアしました'
    },
    'piece_workshop_min_blocks': {
        'tr': 'En az 2 blok gerekli!',
        'en': 'At least 2 blocks are required!',
        'ja': '最低2ブロック必要！'
    },
    'piece_workshop_blocks_not_connected': {
        'tr': 'Bloklar bağlı değil!',
        'en': 'Blocks are not connected!',
        'ja': 'ブロックが連結されていません！'
    },
    'piece_workshop_piece_updated': {
        'tr': 'Parça güncellendi!',
        'en': 'Piece updated!',
        'ja': 'ピースを更新しました！'
    },
    'piece_workshop_load_failed': {
        'tr': '⚠️ Parça atölyesi yüklenemedi: {error}',
        'en': '⚠️ Piece workshop could not be loaded: {error}',
        'ja': '⚠️ ピース工房を読み込めませんでした: {error}'
    },
    'piece_workshop_custom_name': {
        'tr': 'Özel #{index}',
        'en': 'Custom #{index}',
        'ja': 'カスタム#{index}'
    },
    'piece_workshop_piece_saved': {
        'tr': 'Yeni parça kaydedildi!',
        'en': 'New piece saved!',
        'ja': '新しいピースを保存しました！'
    },
    'piece_workshop_editing': {
        'tr': '"{name}" düzenleniyor',
        'en': 'Editing "{name}"',
        'ja': '"{name}" を編集中'
    },
    'piece_workshop_piece_deleted': {
        'tr': 'Parça silindi',
        'en': 'Piece deleted',
        'ja': 'ピースを削除しました'
    },
    'piece_workshop_color_selected': {
        'tr': 'Renk seçildi',
        'en': 'Color selected',
        'ja': '色を選択しました'
    },
    'piece_workshop_custom_color_changed': {
        'tr': 'Özel renk değiştirildi',
        'en': 'Custom color changed',
        'ja': 'カスタム色を変更しました'
    },
    'piece_workshop_custom_color_cancelled': {
        'tr': 'Özel renk seçimi iptal',
        'en': 'Custom color selection cancelled',
        'ja': 'カスタム色の選択をキャンセルしました'
    },
    'color_picker_title': {
        'tr': 'Renk Seçici',
        'en': 'Color Picker',
        'ja': 'カラーピッカー'
    },
    'color_picker_cancel': {
        'tr': 'İptal',
        'en': 'Cancel',
        'ja': 'キャンセル'
    },
    'piece_workshop_custom_color_active': {
        'tr': 'Özel renk aktif',
        'en': 'Custom color active',
        'ja': 'カスタム色が有効'
    },
    'piece_workshop_edit_closed': {
        'tr': 'Düzenleme kapatıldı',
        'en': 'Editing closed',
        'ja': '編集を終了しました'
    },

    # ==================== MENÜ / MÜZİK / ARKA PLAN ====================
    'daily_prompt_title': {
        'tr': 'BUGÜNÜN GÜNLÜK GÖREVİ',
        'en': "TODAY'S DAILY CHALLENGE",
        'ja': '本日のデイリーチャレンジ'
    },
    'daily_prompt_missing': {
        'tr': 'Bugünün görev bilgisi bulunamadı.',
        'en': "Could not load today's challenge details.",
        'ja': '本日のチャレンジ情報を読み込めませんでした。'
    },
    'control_status_hint': {
        'tr': 'ENTER: Tuş ata  |  R: Sekmeyi varsayılan yap  |  TAB: Sekme değiştir  |  SOL/SAĞ: Birincil/İkincil',
        'en': 'ENTER: Bind key  |  R: Reset tab to default  |  TAB: Switch tab  |  LEFT/RIGHT: Primary/Secondary',
        'ja': 'ENTER: キー割り当て  |  R: タブをデフォルトに  |  TAB: タブ切替  |  左/右: 主/副'
    },
    'control_tab_reset': {
        'tr': 'Sekme varsayılana döndü',
        'en': 'Tab reset to default',
        'ja': 'タブをデフォルトに戻しました'
    },
    'track_default_label': {
        'tr': 'Varsayılan (Oyun İçi)',
        'en': 'Default (In-Game)',
        'ja': 'デフォルト(ゲーム内)'
    },
    'track_file_suffix': {
        'tr': '(dosya)',
        'en': '(file)',
        'ja': '(ファイル)'
    },
    'track_file_prefix': {
        'tr': 'Dosya: {path}',
        'en': 'File: {path}',
        'ja': 'ファイル: {path}'
    },
    'track_custom_fallback': {
        'tr': 'Ozel Parca',
        'en': 'Custom Track',
        'ja': 'カスタムトラック',
        'zh': '自定义曲目',
        'ko': '커스텀 트랙'
    },
    'track_title': {
        'tr': 'BÖLÜM MÜZİKLERİ',
        'en': 'LEVEL MUSIC',
        'ja': 'レベル音楽'
    },
    'track_summary': {
        'tr': '{count} mod özelleştirildi',
        'en': '{count} modes customized'
    },
    'bg_title': {
        'tr': 'ARKA PLAN SEÇİMİ',
        'en': 'BACKGROUND SELECTOR'
    },
    'bg_show': {
        'tr': 'Arka Plan Göster',
        'en': 'Show Background'
    },
    'bg_transparency': {
        'tr': 'Transparanlık',
        'en': 'Transparency'
    },
    'bg_main': {
        'tr': 'Ana Arka Plan',
        'en': 'Main Background'
    },
    'bg_single': {
        'tr': 'Tek Oyuncu Oyun Alanı',
        'en': 'Single Player Board'
    },
    'bg_outer': {
        'tr': 'Dış Alan Arka Planı',
        'en': 'Outer Area Background'
    },
    'bg_pvp_main': {
        'tr': 'PvP Ana Arka Plan',
        'en': 'PvP Main Background'
    },
    'bg_pvp_board': {
        'tr': 'PvP Oyun Alanları',
        'en': 'PvP Boards'
    },
    'bg_wide': {
        'tr': 'Geniş Mod Arka Planı',
        'en': 'Wide Mode Background'
    },
    'bg_back': {
        'tr': 'Geri',
        'en': 'Back'
    },
    'bg_default': {
        'tr': 'Varsayılan',
        'en': 'Default'
    },
    'theme_picker_hint': {
        'tr': '↑ ↓: Seç  |  ENTER: Uygula  |  ESC / Dışa tık: Kapat',
        'en': '↑ ↓: Select  |  ENTER: Apply  |  ESC / Click outside: Close'
    },
    'settings_tracks_custom': {
        'tr': '{count} liste',
        'en': '{count} custom'
    },
    'settings_tracks_default': {
        'tr': 'Varsayılan',
        'en': 'Default'
    },
    'settings_gameplay_hint': {
        'tr': 'ENTER : DAS & hız ayarları',
        'en': 'ENTER : DAS & speed settings'
    },
    'settings_controls_hint': {
        'tr': 'ENTER : Tuş atamalarını düzenle',
        'en': 'ENTER : Edit key bindings'
    },
    'settings_block_styles_hint': {
        'tr': 'ENTER : Renk ve PNG düzenle',
        'en': 'ENTER : Edit colors & PNG'
    },
    'settings_piece_workshop_hint': {
        'tr': 'ENTER : Atölyeyi aç',
        'en': 'ENTER : Open workshop'
    },

    # ==================== BLOK ATÖLYESİ ====================
    'block_workshop_title': {
        'tr': 'BLOK ATÖLYESİ',
        'en': 'BLOCK WORKSHOP'
    },
    'block_workshop_tip': {
        'tr': 'TAB: Parça seç  |  Q/E: Döndür  |  ENTER: Yerleştir  |  M: Blok yönetimi',
        'en': 'TAB: Select piece  |  Q/E: Rotate  |  ENTER: Place  |  M: Block manager'
    },
    'block_workshop_instructions_line1': {
        'tr': '🖱️ Sol tık: Boya  |  Sağ tık: Sil  |  K: Renk değiştir',
        'en': '🖱️ Left click: Paint  |  Right click: Erase  |  K: Change color'
    },
    'block_workshop_instructions_line2': {
        'tr': '⌨️ DEL: Temizle  |  {modifier}+S: Kaydet  |  [ ]: Paket değiştir',
        'en': '⌨️ DEL: Clear  |  {modifier}+S: Save  |  [ ]: Switch package'
    },
    'block_workshop_message_loaded': {
        'tr': 'Son kayıt yüklendi',
        'en': 'Last save loaded'
    },
    'block_workshop_clear_board': {
        'tr': 'Tahta temizlendi',
        'en': 'Board cleared'
    },
    'block_workshop_out_of_bounds': {
        'tr': 'Tahta dışına taşamazsın',
        'en': 'You cannot place outside the board'
    },
    'block_workshop_cell_empty': {
        'tr': 'Bu hücre boş',
        'en': 'This cell is empty'
    },
    'block_workshop_cell_color_reset': {
        'tr': 'Hücre rengi sıfırlandı',
        'en': 'Cell color reset'
    },
    'block_workshop_cell_color_updated': {
        'tr': 'Hücre rengi güncellendi',
        'en': 'Cell color updated'
    },
    'block_workshop_saved': {
        'tr': 'Atölye kaydedildi',
        'en': 'Workshop saved'
    },
    'block_workshop_new_set_created': {
        'tr': 'Yeni paket oluşturuldu',
        'en': 'New package created'
    },
    'block_workshop_min_one_set': {
        'tr': 'En az bir paket kalmalı',
        'en': 'At least one package must remain'
    },
    'block_workshop_set_deleted': {
        'tr': '"{name}" silindi',
        'en': '"{name}" deleted'
    },
    'block_workshop_set_loaded': {
        'tr': '"{name}" yüklendi',
        'en': '"{name}" loaded'
    },
    'block_workshop_set_name_title': {
        'tr': 'Paket Adı',
        'en': 'Package Name'
    },
    'block_workshop_set_name_prompt': {
        'tr': 'Yeni paket adını gir:',
        'en': 'Enter new package name:'
    },
    'block_workshop_set_name_updated': {
        'tr': 'Paket adı güncellendi',
        'en': 'Package name updated'
    },
    'block_workshop_set_mode_title': {
        'tr': 'Paket Mod Görünürlüğü',
        'en': 'Package Mode Visibility'
    },
    'block_workshop_set_mode_hint_line1': {
        'tr': '←/→ veya 1-0: Mod seç',
        'en': '←/→ or 1-0: Select mode'
    },
    'block_workshop_set_mode_hint_line2': {
        'tr': 'Boşluk/Enter: Aç/Kapat  ·  Esc: Kapat',
        'en': 'Space/Enter: Toggle  ·  Esc: Close'
    },
    'block_workshop_set_modes_updated': {
        'tr': 'Paket modları güncellendi',
        'en': 'Package modes updated'
    },
    'block_workshop_no_saved_blocks': {
        'tr': 'Henüz kayıtlı blok yok',
        'en': 'No saved blocks yet'
    },
    'block_workshop_manager_title': {
        'tr': 'Blok Yönetimi',
        'en': 'Block Manager'
    },
    'block_workshop_manager_empty': {
        'tr': 'Henüz kayıtlı blok yok.',
        'en': 'No saved blocks yet.'
    },
    'block_workshop_manager_row_label': {
        'tr': '{index}. {cells} hücre  alan: {width}x{height}',
        'en': '{index}. {cells} cells  area: {width}x{height}'
    },
    'block_workshop_manager_selected_info': {
        'tr': 'Seçili blok: {cells} hücre · Alan: {width}x{height}',
        'en': 'Selected block: {cells} cells · Area: {width}x{height}'
    },
    'block_workshop_manager_instructions_line1': {
        'tr': '↑/↓: Blok seç | ←/→: Mod imleci | SPACE veya 1-0: Mod değiştir',
        'en': '↑/↓: Select block | ←/→: Mode focus | SPACE or 1-0: Toggle mode'
    },
    'block_workshop_manager_instructions_line2': {
        'tr': 'DEL: Blok sil | K: Blok rengi | SHIFT+K: Renk sıfırla | ENTER: Tahtaya git | M/Esc: Kapat',
        'en': 'DEL: Delete block | K: Block color | SHIFT+K: Reset color | ENTER: Go to board | M/Esc: Close'
    },
    'block_workshop_manager_instructions_line3': {
        'tr': '{modifier}+N: Yeni paket | {modifier}+D: Kopyala | {modifier}+Del: Sil | F2: Adlandır | {modifier}+M: Modlar',
        'en': '{modifier}+N: New package | {modifier}+D: Duplicate | {modifier}+Del: Delete | F2: Rename | {modifier}+M: Modes'
    },
    'block_workshop_block_empty': {
        'tr': 'Bu blok boş',
        'en': 'This block is empty'
    },
    'block_workshop_block_colors_reset': {
        'tr': 'Blok renkleri sıfırlandı',
        'en': 'Block colors reset'
    },
    'block_workshop_block_color_updated': {
        'tr': 'Blok rengi güncellendi',
        'en': 'Block color updated'
    },
    'block_workshop_side_info_cells': {
        'tr': '🔢 Hücre: {count}',
        'en': '🔢 Cells: {count}'
    },
    'block_workshop_side_info_angle': {
        'tr': '🔄 Açı: {angle}°',
        'en': '🔄 Angle: {angle}°'
    },
    'block_workshop_saved_blocks_title': {
        'tr': '🧩 Kayıtlı Bloklar',
        'en': '🧩 Saved Blocks'
    },
    'block_workshop_saved_blocks_count': {
        'tr': '{count} blok',
        'en': '{count} blocks'
    },
    'block_workshop_saved_block_label': {
        'tr': '{index}. {cells} hücre  {width}x{height}',
        'en': '{index}. {cells} cells  {width}x{height}'
    },
    'block_workshop_packages_title': {
        'tr': 'Paketler',
        'en': 'Packages'
    },
    'block_workshop_no_packages': {
        'tr': 'Henüz paket yok ({modifier}+N ile oluştur).',
        'en': 'No packages yet (create with {modifier}+N).'
    },
    'block_workshop_action_new': {
        'tr': 'Yeni',
        'en': 'New'
    },
    'block_workshop_action_duplicate': {
        'tr': 'Kopyala',
        'en': 'Duplicate'
    },
    'block_workshop_action_rename': {
        'tr': 'Adlandır',
        'en': 'Rename'
    },
    'block_workshop_action_delete': {
        'tr': 'Sil',
        'en': 'Delete'
    },
    'block_workshop_action_modes': {
        'tr': 'Modlar',
        'en': 'Modes'
    },
    'block_workshop_default_set': {
        'tr': 'Varsayılan Paket',
        'en': 'Default Package'
    },
    'block_workshop_set_base': {
        'tr': 'Paket',
        'en': 'Package'
    },
    'block_workshop_set_number': {
        'tr': 'Paket {index}',
        'en': 'Package {index}'
    },
    'block_workshop_block_name': {
        'tr': '{label} #{index}',
        'en': '{label} #{index}'
    },
    'block_workshop_set_copy_suffix': {
        'tr': 'Kopya',
        'en': 'Copy'
    },
    # ======================= OYUN İÇİ PANEL METİNLERİ =======================
    'panel_best_times': {
        'tr': 'EN İYİ SÜRELER',
        'en': 'BEST TIMES',
        'ja': 'ベストタイム'
    },
    'panel_best_scores': {
        'tr': 'EN İYİ SKORLAR',
        'en': 'BEST SCORES',
        'ja': 'ベストスコア'
    },
    'panel_no_records': {
        'tr': 'Kayıt Yok',
        'en': 'No Records',
        'ja': '記録なし'
    },
    'sprint_target_hint': {
        'tr': '{lines} satırı hızla bitir!',
        'en': 'Clear {lines} lines fast!',
        'ja': '{lines}ラインを素早く消そう！'
    },
    'timer_label': {
        'tr': 'SÜRE',
        'en': 'TIME',
        'ja': '時間'
    },
    'sprint_congrats_title': {
        'tr': 'TEBRİKLER!',
        'en': 'CONGRATULATIONS!',
        'ja': 'おめでとう！'
    },
    'sprint_finish_message': {
        'tr': '{lines} satırı {time} saniyede tamamladınız!',
        'en': 'You cleared {lines} lines in {time} seconds!',
        'ja': '{time}秒で{lines}ラインを達成！'
    },
    'ultra_time_limit_hint': {
        'tr': '2 Dakika Sınırı!',
        'en': '2 Minute Limit!',
        'ja': '2分制限！'
    },
    'ultra_remaining_label': {
        'tr': '⏳ KALAN',
        'en': '⏳ REMAINING',
        'ja': '⏳ 残り'
    },
    'ultra_final_score': {
        'tr': 'Final Skorunuz: {score}',
        'en': 'Your Final Score: {score}',
        'ja': '最終スコア: {score}'
    },
    'ultra_played_time': {
        'tr': 'Oynanan Süre: {seconds} sn',
        'en': 'Play Time: {seconds} s',
        'ja': 'プレイ時間: {seconds}秒'
    },
    'zen_message_tetris': {
        'tr': 'MUHTEŞEM QUADRIX!',
        'en': 'AMAZING QUADRIX!',
        'ja': '最高のテトリス！'
    },
    'zen_message_lines': {
        'tr': '{lines} SATIR!',
        'en': '{lines} LINES!',
        'ja': '{lines}ライン！'
    },
    'zen_message_relax_bonus': {
        'tr': 'Rahatlatma Bonusu! +{bonus}',
        'en': 'Relax Bonus! +{bonus}',
        'ja': 'リラックスボーナス！+{bonus}'
    },
    'zen_message_full_clear': {
        'tr': 'TAM TEMİZLİK',
        'en': 'FULL CLEAR',
        'ja': '全消し'
    },
    'zen_message_rows_cleared': {
        'tr': '{rows} SATIR TEMİZLENDİ',
        'en': '{rows} LINES CLEARED',
        'ja': '{rows}ライン消去'
    },
    'zen_message_full_clear_fallback': {
        'tr': 'TAM TEMİZLİK (yetersiz alan)',
        'en': 'FULL CLEAR (not enough space)',
        'ja': '全消し（スペース不足）'
    },
    'zen_panel_auto_clear': {
        'tr': 'Otomatik Temizlik',
        'en': 'Auto Clear',
        'ja': '自動クリア'
    },
    'zen_panel_penalty': {
        'tr': 'Ceza',
        'en': 'Penalty',
        'ja': 'ペナルティ'
    },
    'zen_panel_bonus': {
        'tr': 'Bonus',
        'en': 'Bonus',
        'ja': 'ボーナス'
    },
    'zen_panel_time': {
        'tr': 'Süre',
        'en': 'Time',
        'ja': '時間'
    },
    'survival_panel_time_left': {
        'tr': 'KALAN SÜRE',
        'en': 'TIME LEFT',
        'ja': '残り時間'
    },
    'survival_panel_virus_level': {
        'tr': 'VİRÜS SEVİYESİ',
        'en': 'VIRUS LEVEL',
        'ja': 'ウイルスレベル'
    },
    'survival_panel_consumed': {
        'tr': 'YENİLEN BLOKLAR',
        'en': 'CONSUMED BLOCKS',
        'ja': '消費ブロック'
    },
    'survival_panel_active_infection': {
        'tr': 'AKTİF ENFEKSİYON',
        'en': 'ACTIVE INFECTION',
        'ja': '感染進行'
    },
    'survival_panel_antivirus': {
        'tr': 'ANTİVİRÜS',
        'en': 'ANTIVIRUS',
        'ja': 'アンチウイルス'
    },
    'survival_panel_points_remaining': {
        'tr': '{points} puan kaldı',
        'en': '{points} points left',
        'ja': '残り{points}ポイント'
    },
    'survival_panel_ready': {
        'tr': 'HAZIR!',
        'en': 'READY!',
        'ja': '準備完了！'
    },
    'cascade_tip_line1': {
        'tr': 'Satırlar düşer -',
        'en': 'Lines fall -',
        'ja': 'ラインが落ちる -'
    },
    'cascade_tip_line2': {
        'tr': 'Zincir bonus!',
        'en': 'Chain bonus!',
        'ja': '連鎖ボーナス！'
    },
    'cascade_level_message': {
        'tr': 'CASCADE x{level}!',
        'en': 'CASCADE x{level}!',
        'ja': 'カスケード x{level}！'
    },
    'cascade_mega_bonus': {
        'tr': 'Mega Bonus!',
        'en': 'Mega Bonus!',
        'ja': 'メガボーナス！'
    },
    'hardcore_warning_next': {
        'tr': 'Siradakiler',
        'en': 'Next',
        'ja': '次のピース'
    },
    'hardcore_warning_next_value_hidden': {
        'tr': 'GIZLI',
        'en': 'HIDDEN',
        'ja': '非表示'
    },
    'hardcore_warning_hold': {
        'tr': 'Saklama',
        'en': 'Hold',
        'ja': 'ホールド'
    },
    'hardcore_warning_hold_value_disabled': {
        'tr': 'DEVRE DISI',
        'en': 'DISABLED',
        'ja': '無効'
    },
    'hardcore_warning_controls': {
        'tr': 'Kontroller',
        'en': 'Controls',
        'ja': '操作'
    },
    'hardcore_warning_controls_value_inverted': {
        'tr': 'TERS',
        'en': 'INVERTED',
        'ja': '反転'
    },
    'survival_victory_title': {
        'tr': '🏆 KAZANDIN!',
        'en': '🏆 YOU WIN!',
        'ja': '🏆 勝利！'
    },
    'survival_victory_subtitle': {
        'tr': '{minutes} Dakika Hayatta Kaldın!',
        'en': 'You survived for {minutes} minutes!',
        'ja': '{minutes}分生き残った！'
    },
    'playlist_add': {
        'tr': '+ Ekle',
        'en': '+ Add'
    },
}

def _ensure_language_fallback(lang_code: str, fallback_order: tuple[str, ...] = ('en', 'tr')) -> None:
    """Eksik dil anahtarlarını fallback ile tamamla (runtime)."""
    for key, translations in TRANSLATIONS.items():
        if lang_code in translations and translations[lang_code]:
            continue
        for fb in fallback_order:
            if fb in translations:
                translations[lang_code] = translations[fb]
                break
        else:
            translations[lang_code] = key

# Japonca olan her yerde Çince/Korece de olsun (eksikse). Not: Placeholder olarak Japonca kopyalanır.
def _ensure_cjk_from_japanese():
    for key, translations in TRANSLATIONS.items():
        if 'ja' not in translations:
            continue
        if 'zh' not in translations:
            translations['zh'] = translations['ja']
        if 'ko' not in translations:
            translations['ko'] = translations['ja']

# CJK dilleri için tek adımda toplu doldurma.
_ensure_cjk_from_japanese()
_ensure_language_fallback('ja', ('en', 'tr'))
_ensure_language_fallback('zh', ('en', 'tr'))
_ensure_language_fallback('ko', ('en', 'tr'))

# Aktif dil (varsayılan Türkçe)
_current_language = DEFAULT_LANGUAGE

# localization.py dosyası değiştiğinde runtime'da otomatik yenileme
_HOT_RELOAD_ENABLED = os.getenv('TETRIS_LOCALIZATION_HOT_RELOAD', '1') != '0'
_HOT_RELOAD_LOCK = threading.Lock()
_LOCALIZATION_FILE = os.path.abspath(__file__)


def _safe_mtime(path: str) -> float | None:
    try:
        return os.path.getmtime(path)
    except Exception:
        return None


_last_known_mtime = _safe_mtime(_LOCALIZATION_FILE)


def _load_fresh_translations_from_file() -> dict[str, dict] | None:
    """localization.py dosyasını ayrı modül olarak okuyup TRANSLATIONS sözlüğünü al."""
    try:
        module_name = f"_quadrix_localization_hot_{os.getpid()}_{threading.get_ident()}"
        spec = importlib.util.spec_from_file_location(module_name, _LOCALIZATION_FILE)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        table = getattr(mod, 'TRANSLATIONS', None)
        if not isinstance(table, dict):
            return None
        normalized: dict[str, dict] = {}
        for key, value in table.items():
            if isinstance(value, dict):
                normalized[str(key)] = dict(value)
            else:
                normalized[str(key)] = {'en': str(value)}
        return normalized
    except Exception:
        return None


def refresh_localization_if_changed(force: bool = False) -> bool:
    """Dosya değiştiyse localization tablosunu anlık yenile.

    Returns:
        True: tablo yenilendi
        False: değişiklik yok veya yenileme başarısız
    """
    global TRANSLATIONS, _last_known_mtime

    if not _HOT_RELOAD_ENABLED:
        return False

    current_mtime = _safe_mtime(_LOCALIZATION_FILE)
    if current_mtime is None:
        return False

    if (not force) and (_last_known_mtime is not None) and (current_mtime <= _last_known_mtime):
        return False

    with _HOT_RELOAD_LOCK:
        current_mtime = _safe_mtime(_LOCALIZATION_FILE)
        if current_mtime is None:
            return False
        if (not force) and (_last_known_mtime is not None) and (current_mtime <= _last_known_mtime):
            return False

        fresh_table = _load_fresh_translations_from_file()
        if not fresh_table:
            return False

        TRANSLATIONS = fresh_table
        _ensure_cjk_from_japanese()
        _ensure_language_fallback('ja', ('en', 'tr'))
        _ensure_language_fallback('zh', ('en', 'tr'))
        _ensure_language_fallback('ko', ('en', 'tr'))
        _last_known_mtime = current_mtime
        return True

def set_language(lang_code: str) -> bool:
    """Dili değiştir. Başarılıysa True döner."""
    global _current_language
    refresh_localization_if_changed()
    if lang_code in SUPPORTED_LANGUAGES:
        _current_language = lang_code
        return True
    return False

def get_language() -> str:
    """Aktif dili döndür"""
    return _current_language

def get_text(key: str, default: str = None, **kwargs) -> str:
    """Verilen anahtar için çevrilmiş metni döndür.
    
    Args:
        key: Çeviri anahtarı
        default: Anahtar bulunamazsa dönecek değer
        **kwargs: Format parametreleri (örn: {name} için name='John')
    
    Returns:
        Çevrilmiş metin
    """
    refresh_localization_if_changed()
    if key in TRANSLATIONS:
        # Aktif dilde ara, yoksa EN'ye düş, yoksa TR'ye düş
        text = TRANSLATIONS[key].get(
            _current_language, 
            TRANSLATIONS[key].get('en', TRANSLATIONS[key].get('tr', default or key))
        )
        # Format parametreleri varsa uygula
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text
    return default or key

def t(key: str, default: str = None, **kwargs) -> str:
    """Kısa alias - get_text için"""
    return get_text(key, default, **kwargs)

def get_language_name(lang_code: str) -> str:
    """Dil kodundan yerel dil adını döndür"""
    if lang_code in LANGUAGE_METADATA:
        return LANGUAGE_METADATA[lang_code]['native_name']
    return lang_code

def get_language_display_name(lang_code: str) -> str:
    """Dil kodundan İngilizce dil adını döndür"""
    if lang_code in LANGUAGE_METADATA:
        return LANGUAGE_METADATA[lang_code]['name']
    return lang_code

def get_language_flag(lang_code: str) -> str:
    """Dil kodundan bayrak emoji döndür"""
    if lang_code in LANGUAGE_METADATA:
        return LANGUAGE_METADATA[lang_code]['flag_emoji']
    return '🏳️'

def is_language_complete(lang_code: str) -> bool:
    """Bir dilin çevirilerinin tamamlanıp tamamlanmadığını kontrol et"""
    if lang_code in LANGUAGE_METADATA:
        return LANGUAGE_METADATA[lang_code].get('complete', False)
    return False

def get_all_languages() -> list:
    """Tüm desteklenen dilleri döndür - [(kod, yerel_ad, bayrak, tamamlandı), ...]"""
    result = []
    for code in SUPPORTED_LANGUAGES:
        meta = LANGUAGE_METADATA.get(code, {})
        result.append((
            code,
            meta.get('native_name', code),
            meta.get('flag_emoji', '🏳️'),
            meta.get('complete', False)
        ))
    return result

def get_available_languages() -> list:
    """Sadece tamamlanmış dilleri döndür"""
    return [(code, name, flag, complete) 
            for code, name, flag, complete in get_all_languages() 
            if complete]

def get_missing_translations(lang_code: str) -> list:
    """Bir dil için eksik çeviri anahtarlarını bul"""
    missing = []
    for key, translations in TRANSLATIONS.items():
        if lang_code not in translations:
            missing.append(key)
    return missing

def get_translation_stats() -> dict:
    """Her dil için çeviri istatistikleri"""
    total_keys = len(TRANSLATIONS)
    stats = {}
    for lang in SUPPORTED_LANGUAGES:
        translated = sum(1 for key in TRANSLATIONS if lang in TRANSLATIONS[key])
        stats[lang] = {
            'translated': translated,
            'total': total_keys,
            'percentage': round(translated / total_keys * 100, 1) if total_keys > 0 else 0
        }
    return stats
