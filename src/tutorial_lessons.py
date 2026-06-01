"""Tutorial ders kataloğu — Kanonik V2.

7 bölüm, 26 ders.  Plan referansı:
plans/2026-04-18-egitim-modu-yeniden-tasarim-ve-icerik-stratejisi.md §7
plans/2026-06-01-egitim-akis-yogunlugu-ve-yeni-oyuncu-deneyimi-plani.md §Ö5a
(kart bölümü 8→6 sıkıştırıldı: cards_tempo_trap + cards_long_term_value kaldırıldı)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Eski → yeni ID eşleme tablosu (progress migration için)
# ---------------------------------------------------------------------------
LEGACY_CHAPTER_MAP: Dict[str, str] = {
    "basics": "quick_start",
    "board_basics": "surface_control",
    "card_academy": "card_foundations",
}

LEGACY_LESSON_MAP: Dict[str, str] = {
    "move_intro": "qs_move_lane",
    "rotate_intro": "qs_rotate_fit",
    "soft_drop_intro": "qs_soft_drop_control",
    "hard_drop_intro": "qs_safe_hard_drop",
    "line_clear_intro": "qs_first_clear",
    "hold_intro": "plan_hold_save",
    "tutorial_complete": "qs_first_clear",
    "board_gap_fill": "surface_gap_fill",
    "board_keep_low": "surface_keep_low",
    "board_vertical_well": "surface_protect_well",
    "card_rescue_pick": "cards_rescue_now",
    # Ö5a — kaldırılan kart dersleri korunan derslere eşlenir (eski ilerleme
    # orphan kalmasın; tamamlanmışlık benzer kavramı öğreten derse taşınır).
    "card_long_term_pick": "cards_perk_vs_instant",
    "cards_long_term_value": "cards_perk_vs_instant",
    "cards_tempo_trap": "cards_rescue_now",
    "card_synergy_pick": "cards_synergy_scale",
}


CHAPTERS: List[Dict[str, Any]] = [
    {
        "id": "quick_start",
        "title_key": "tutorial_quick_start_title",
        "title_fallback": "Hızlı Başlangıç",
        "description_key": "tutorial_quick_start_desc",
        "description_fallback": "90 saniyede oynanabilir minimum yetkinliği al.",
        "unlocked_by_default": True,
        "difficulty": 1,
        # Bölüm bitince çıkan ilerleme paneli (devam et / çıkıp oyna kararı).
        # Yalnız bu alana sahip bölümler panel gösterir; diğerlerinde sessiz akış korunur.
        "progression_panel": {
            "title_key": "tutorial_progress_panel_basics_title",
            "title_fallback": "Temel hareketleri öğrendin!",
            "body_key": "tutorial_progress_panel_basics_body",
            "body_fallback": "Artık oynamak için yeterince biliyorsun. Daha fazlasını "
                             "öğrenmek istersen Devam Et'e bas, ya da çıkıp oynayarak "
                             "kendin keşfet.",
        },
    },
    {
        "id": "surface_control",
        "title_key": "tutorial_surface_control_title",
        "title_fallback": "Yüzey Kontrolü",
        "description_key": "tutorial_surface_control_desc",
        "description_fallback": "Temiz yüzey, delik önleme ve kuyu koruma mantığını otur.",
        "unlocked_by_default": False,
        "difficulty": 2,
        "progression_panel": {
            "title_key": "tutorial_progress_panel_surface_title",
            "title_fallback": "Yüzey kontrolünü öğrendin!",
            "body_key": "tutorial_progress_panel_surface_body",
            "body_fallback": "Yüzeyi temiz ve alçak tutmayı çözdün. Şimdi sıradaki "
                             "parçaları ve hold'u planlamayı öğrenmeye ne dersin?",
        },
    },
    {
        "id": "queue_hold",
        "title_key": "tutorial_queue_hold_title",
        "title_fallback": "Queue ve Hold",
        "description_key": "tutorial_queue_hold_desc",
        "description_fallback": "Gelecek planlama ve hold karar mantığını öğren.",
        "unlocked_by_default": False,
        "difficulty": 2,
        "progression_panel": {
            "title_key": "tutorial_progress_panel_queue_title",
            "title_fallback": "Planlamayı öğrendin!",
            "body_key": "tutorial_progress_panel_queue_body",
            "body_fallback": "Sırayı ve hold'u kullanmayı çözdün. Şimdi kötü bir tahtadan "
                             "sakin kalarak kurtulmayı öğrenelim mi?",
        },
    },
    {
        "id": "recovery",
        "title_key": "tutorial_recovery_title",
        "title_fallback": "Kurtarma ve Hayatta Kalma",
        "description_key": "tutorial_recovery_desc",
        "description_fallback": "Kötü board altında sakin ve doğru önceliklerle oyna.",
        "unlocked_by_default": False,
        "difficulty": 3,
        "progression_panel": {
            "title_key": "tutorial_progress_panel_recovery_title",
            "title_fallback": "Kurtarmayı öğrendin!",
            "body_key": "tutorial_progress_panel_recovery_body",
            "body_fallback": "Board becerilerini tamamladın. Şimdi konu değişiyor: artık "
                             "parça değil, doğru KARTI doğru anda seçmeyi öğreneceksin.",
        },
    },
    {
        "id": "card_foundations",
        "title_key": "tutorial_card_foundations_title",
        "title_fallback": "Kart Temelleri",
        "description_key": "tutorial_card_foundations_desc",
        "description_fallback": "Kart ailelerini, risk etiketlerini ve board bağlamını tanı.",
        "unlocked_by_default": False,
        "difficulty": 2,
        "progression_panel": {
            "title_key": "tutorial_progress_panel_cards_title",
            "title_fallback": "Kart temellerini öğrendin!",
            "body_key": "tutorial_progress_panel_cards_body",
            "body_fallback": "Hangi kartın ne zaman doğru olduğunu okumaya başladın. "
                             "Şimdi sinerji ve uzun vadeli build mantığına geçelim mi?",
        },
    },
    {
        "id": "card_strategy",
        "title_key": "tutorial_card_strategy_title",
        "title_fallback": "Kart Stratejisi ve Sinerji",
        "description_key": "tutorial_card_strategy_desc",
        "description_fallback": "Uzun vadeli build mantığı ve risk-getiri dengesini öğren.",
        "unlocked_by_default": False,
        "difficulty": 3,
        "progression_panel": {
            "title_key": "tutorial_progress_panel_strategy_title",
            "title_fallback": "Kart stratejisini öğrendin!",
            "body_key": "tutorial_progress_panel_strategy_body",
            "body_fallback": "Artık sınavlara hazırsın. Az ipucuyla, öğrendiğin her şeyi "
                             "birleştireceksin. Hazır olduğunda Devam Et'e bas.",
        },
    },
    {
        "id": "mastery_exams",
        "title_key": "tutorial_mastery_exams_title",
        "title_fallback": "Sınavlar ve Ustalık Görevleri",
        "description_key": "tutorial_mastery_exams_desc",
        "description_fallback": "Öğrenilen ilkeleri daha az ipucuyla birleştir.",
        "unlocked_by_default": False,
        "difficulty": 4,
    },
]


LESSONS: List[Dict[str, Any]] = [
    # ══════════════════════════════════════════════════════════════
    # Chapter A — quick_start  (5 ders, legacy steps 1-5)
    # ══════════════════════════════════════════════════════════════
    {
        "id": "qs_move_lane",
        "chapter": "quick_start",
        "kind": "legacy_step",
        "legacy_step": 1,
        "lesson_type": "drill",
        "title_key": "tutorial_lesson_move_title",
        "title_fallback": "Hareket ve konum alma",
        "description_key": "tutorial_lesson_move_desc",
        "description_fallback": "Parçayı sağa ve sola taşıyarak yatay kontrolü öğren.",
        "why_it_matters": "Doğru lane'e girmek her yerleştirmenin ilk adımıdır.",
        "difficulty": 1,
        "duration_seconds": 15,
        "skill_tags": ["movement"],
        "allowed_actions": ["move_left", "move_right"],
        "success_condition": "move_left_right_counts",
    },
    {
        "id": "qs_rotate_fit",
        "chapter": "quick_start",
        "kind": "legacy_step",
        "legacy_step": 2,
        "lesson_type": "drill",
        "title_key": "tutorial_lesson_rotate_title",
        "title_fallback": "Döndürme kontrolü",
        "description_key": "tutorial_lesson_rotate_desc",
        "description_fallback": "Boşluğu okuyup parçayı doğru anda döndür.",
        "why_it_matters": "Dar boşlukları görmek ve doğru dönüşü seçmek yüzey temizliğinin temelidir.",
        "difficulty": 1,
        "duration_seconds": 15,
        "skill_tags": ["rotation"],
        "allowed_actions": ["rotate"],
        "success_condition": "rotate_three_times",
    },
    {
        "id": "qs_soft_drop_control",
        "chapter": "quick_start",
        "kind": "legacy_step",
        "legacy_step": 3,
        "lesson_type": "drill",
        "title_key": "tutorial_lesson_soft_drop_title",
        "title_fallback": "Yumuşak düşürme",
        "description_key": "tutorial_lesson_soft_drop_desc",
        "description_fallback": "Parçayı kilitlemeden kontrollü biçimde aşağı indir.",
        "why_it_matters": "Soft drop, parçanın nereye oturacağını görmeni sağlar.",
        "difficulty": 1,
        "duration_seconds": 15,
        "skill_tags": ["soft_drop"],
        "allowed_actions": ["soft_drop"],
        "success_condition": "soft_drop_frames",
    },
    {
        "id": "qs_safe_hard_drop",
        "chapter": "quick_start",
        "kind": "legacy_step",
        "legacy_step": 4,
        "lesson_type": "drill",
        "title_key": "tutorial_lesson_hard_drop_title",
        "title_fallback": "Sert düşürme",
        "description_key": "tutorial_lesson_hard_drop_desc",
        "description_fallback": "Net gördüğün anda parçayı tek tuşla anında yerleştir.",
        "why_it_matters": "Board'u okumuşken hızlı kilitleme güvenli karar demektir.",
        "difficulty": 1,
        "duration_seconds": 10,
        "skill_tags": ["hard_drop"],
        "allowed_actions": ["hard_drop"],
        "success_condition": "hard_drop_once",
    },
    {
        "id": "qs_first_clear",
        "chapter": "quick_start",
        "kind": "legacy_step",
        "legacy_step": 5,
        "lesson_type": "board_puzzle",
        "title_key": "tutorial_lesson_line_clear_title",
        "title_fallback": "Satır tamamlama",
        "description_key": "tutorial_lesson_line_clear_desc",
        "description_fallback": "Boşluğu kapatıp ilk satır temizlemeni yap.",
        "why_it_matters": "İlk temiz yerleşim dersi — acele değil, doğru yerleştirme önceliği.",
        "difficulty": 1,
        "duration_seconds": 30,
        "skill_tags": ["line_clear"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
        "success_condition": "line_clear_once",
    },

    # ══════════════════════════════════════════════════════════════
    # Chapter B — surface_control  (4 ders, scenario)
    # ══════════════════════════════════════════════════════════════
    {
        "id": "surface_gap_fill",
        "chapter": "surface_control",
        "kind": "scenario",
        "scenario_id": "gap_fill_double",
        "lesson_type": "board_puzzle",
        "title_key": "tutorial_board_gap_fill_title",
        "title_fallback": "Geniş boşluğu kapat",
        "description_key": "tutorial_board_gap_fill_desc",
        "description_fallback": "İki hücrelik boşluğu doğru parçayla kapat ve iki satırı aynı anda temizle.",
        "why_it_matters": "Geniş boşlukları okumak, kart kararlarının da temelidir.",
        "goal_fallback": "Hedef: İki satırı temizle ve yeni delik açma.",
        "tip_fallback": "Kart seçimlerinde de önce tahtadaki geniş boşlukları fark etmek gerekir.",
        "difficulty": 2,
        "duration_seconds": 30,
        "skill_tags": ["gap_fill", "surface"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "surface_keep_low",
        "chapter": "surface_control",
        "kind": "scenario",
        "scenario_id": "keep_stack_low",
        "lesson_type": "board_puzzle",
        "title_key": "tutorial_board_keep_low_title",
        "title_fallback": "Kuleyi alçak tut",
        "description_key": "tutorial_board_keep_low_desc",
        "description_fallback": "Her hamlede satır temizlemek gerekmez; bazen en iyi oyun yüksekliği artırmamaktır.",
        "why_it_matters": "Düşük yüzey = daha çok karar zamanı, daha az panik.",
        "goal_fallback": "Hedef: Yeni delik açmadan yüksekliği artırma.",
        "tip_fallback": "Açık tarafı kullanmak, kötü bir boşluğu zorla kapatmaktan daha güçlüdür.",
        "difficulty": 2,
        "duration_seconds": 30,
        "skill_tags": ["height", "surface"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "surface_avoid_holes",
        "chapter": "surface_control",
        "kind": "scenario",
        "scenario_id": "avoid_holes_trap",
        "lesson_type": "board_puzzle",
        "title_key": "tutorial_surface_avoid_holes_title",
        "title_fallback": "Delik açmadan yerleştir",
        "description_key": "tutorial_surface_avoid_holes_desc",
        "description_fallback": "Kısa vadeli rahatlamak için delik açmanın neden kötü olduğunu gör.",
        "why_it_matters": "Delikler gelecek hamleleri zorlaştırır; önleme, tamir etmekten ucuzdur.",
        "goal_fallback": "Hedef: Delik açmadan parçayı yerleştir.",
        "tip_fallback": "Bir delik açmamak, iki satır temizlemekten daha değerli olabilir.",
        "difficulty": 2,
        "duration_seconds": 30,
        "skill_tags": ["holes", "surface"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "surface_protect_well",
        "chapter": "surface_control",
        "kind": "scenario",
        "scenario_id": "vertical_well_quadrix",
        "lesson_type": "board_puzzle",
        "title_key": "tutorial_board_vertical_well_title",
        "title_fallback": "Kuyuyu değerlendir",
        "description_key": "tutorial_board_vertical_well_desc",
        "description_fallback": "Hazır kuyuyu fark et ve I parçasıyla tek hamlede Quadrix yap.",
        "why_it_matters": "Kuyuyu sabırla korumak en büyük ödülü verir.",
        "goal_fallback": "Hedef: Kuyuda I parçasıyla 4 satır temizle.",
        "tip_fallback": "Kart modunda güçlü karar, sadece iyi kartı seçmek değil; onu bekleyecek tahtayı hazırlamaktır.",
        "difficulty": 2,
        "duration_seconds": 20,
        "skill_tags": ["well", "tetris"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },

    # ══════════════════════════════════════════════════════════════
    # Chapter C — queue_hold  (4 ders, scenario)
    # ══════════════════════════════════════════════════════════════
    {
        "id": "plan_hold_save",
        "chapter": "queue_hold",
        "kind": "scenario",
        "scenario_id": "hold_save_practice",
        "lesson_type": "board_puzzle",
        "title_key": "tutorial_plan_hold_save_title",
        "title_fallback": "Hold ile parça sakla",
        "description_key": "tutorial_plan_hold_save_desc",
        "description_fallback": "Uygun olmayan parçayı saklayıp daha uygun parçayla devam et.",
        "why_it_matters": "Hold, panik butonu değil; doğru parçayı doğru ana saklama aracıdır.",
        "goal_fallback": "Hedef: Hold kullanarak daha iyi bir yerleştirme yap.",
        "tip_fallback": "Hold'u kullanarak kötü parçayı kenara koy, sıradakiyle devam et.",
        "difficulty": 2,
        "duration_seconds": 30,
        "skill_tags": ["hold"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop", "hold"],
    },
    {
        "id": "plan_queue_read",
        "chapter": "queue_hold",
        "kind": "scenario",
        "scenario_id": "queue_read_setup",
        "lesson_type": "board_puzzle",
        "title_key": "tutorial_plan_queue_read_title",
        "title_fallback": "Sırayı oku",
        "description_key": "tutorial_plan_queue_read_desc",
        "description_fallback": "Bir sonraki parçaya göre bugünkü lane kararını ver.",
        "why_it_matters": "Sonraki parçayı bilmek, bugünkü hamleyi daha akıllı yapar.",
        "goal_fallback": "Hedef: Sıradaki parçayı düşünerek yerleştir.",
        "tip_fallback": "Sıradaki parçayı gözden kaçırma — o da kararının bir parçası.",
        "difficulty": 2,
        "duration_seconds": 30,
        "skill_tags": ["queue", "planning"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "plan_hold_vs_place",
        "chapter": "queue_hold",
        "kind": "scenario",
        "scenario_id": "hold_vs_place_decision",
        "lesson_type": "board_puzzle",
        "title_key": "tutorial_plan_hold_vs_place_title",
        "title_fallback": "Koy mu, sakla mı?",
        "description_key": "tutorial_plan_hold_vs_place_desc",
        "description_fallback": "Bu parçayı şimdi koymak mı yoksa hold'a atmak mı daha değerli?",
        "why_it_matters": "Hold kararı, her hamlenin gizli seçeneğidir.",
        "goal_fallback": "Hedef: Doğru hold kararını ver.",
        "tip_fallback": "Parçayı koyabiliyorsan koy — ama daha iyi bir yer gelecekse sakla.",
        "difficulty": 2,
        "duration_seconds": 30,
        "skill_tags": ["hold", "decision"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop", "hold"],
    },
    {
        "id": "plan_two_step_setup",
        "chapter": "queue_hold",
        "kind": "scenario",
        "scenario_id": "two_step_combo",
        "lesson_type": "board_puzzle",
        "title_key": "tutorial_plan_two_step_title",
        "title_fallback": "İki adımlık kurulum",
        "description_key": "tutorial_plan_two_step_desc",
        "description_fallback": "Tek hamle değil iki hamlelik kurulum yaparak büyük temizlik al.",
        "why_it_matters": "Planlı iki hamle, rastgele beş hamleden güçlüdür.",
        "goal_fallback": "Hedef: İki parçayı sırayla yerleştirip çoklu satır temizle.",
        "tip_fallback": "İlk parçayı yerleştirirken ikincisinin nereye gideceğini düşün.",
        "difficulty": 3,
        "duration_seconds": 45,
        "skill_tags": ["planning", "combo"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },

    # ══════════════════════════════════════════════════════════════
    # Chapter D — recovery  (4 ders, scenario)
    # ══════════════════════════════════════════════════════════════
    {
        "id": "recover_make_breathing_room",
        "chapter": "recovery",
        "kind": "scenario",
        "scenario_id": "recovery_breathing_room",
        "lesson_type": "repair_challenge",
        "title_key": "tutorial_recover_breathing_title",
        "title_fallback": "Nefes alanı aç",
        "description_key": "tutorial_recover_breathing_desc",
        "description_fallback": "Yüksek ve karışık tahtada önce alan açarak hayatta kal.",
        "why_it_matters": "Panik yerine önce nefes almak, doğru kararların ön koşuludur.",
        "goal_fallback": "Hedef: En az 1 satır temizle ve tahtayı daha kötü yapma.",
        "tip_fallback": "Skor düşünme — önce nefes al, sonra plan yap.",
        "difficulty": 3,
        "duration_seconds": 45,
        "skill_tags": ["recovery", "survival"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "recover_hole_or_height",
        "chapter": "recovery",
        "kind": "scenario",
        "scenario_id": "recovery_hole_vs_height",
        "lesson_type": "board_puzzle",
        "title_key": "tutorial_recover_hole_height_title",
        "title_fallback": "Delik mi, yükseklik mi?",
        "description_key": "tutorial_recover_hole_height_desc",
        "description_fallback": "Delik kapatma ile tepe düşürme arasında doğru önceliği belirle.",
        "why_it_matters": "Yanlış öncelik seçmek, sorunu çözmek yerine büyütür.",
        "goal_fallback": "Hedef: Doğru önceliğe odaklan.",
        "tip_fallback": "Genellikle delik kapatmak, tepe düşürmekten daha acildir.",
        "difficulty": 3,
        "duration_seconds": 45,
        "skill_tags": ["recovery", "priority"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "recover_reduce_ceiling",
        "chapter": "recovery",
        "kind": "scenario",
        "scenario_id": "recovery_reduce_ceiling",
        "lesson_type": "repair_challenge",
        "title_key": "tutorial_recover_ceiling_title",
        "title_fallback": "Tavanı düşür",
        "description_key": "tutorial_recover_ceiling_desc",
        "description_fallback": "Tavan baskısında güvenli taraf ve hız kontrolüyle yüksekliği azalt.",
        "why_it_matters": "Yüksek tavan = az alan = her hata ölümcül.",
        "goal_fallback": "Hedef: Yüksekliği en az 2 birim düşür.",
        "tip_fallback": "Güvenli tarafı kullan, satır temizlemeye odaklan.",
        "difficulty": 3,
        "duration_seconds": 45,
        "skill_tags": ["recovery", "height"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "recover_wrong_side_escape",
        "chapter": "recovery",
        "kind": "scenario",
        "scenario_id": "recovery_wrong_side",
        "lesson_type": "repair_challenge",
        "title_key": "tutorial_recover_wrong_side_title",
        "title_fallback": "Yanlış taraf kurtarma",
        "description_key": "tutorial_recover_wrong_side_desc",
        "description_fallback": "Yanlış tarafa yığılmış board'dan kontrollü çıkış yap.",
        "why_it_matters": "Tek tarafa yığılmak en yaygın ölüm sebebidir.",
        "goal_fallback": "Hedef: Dengesiz tahtayı düzelt.",
        "tip_fallback": "Boş tarafı doldurma — yüksek tarafı indir.",
        "difficulty": 3,
        "duration_seconds": 45,
        "skill_tags": ["recovery", "balance"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },

    # ══════════════════════════════════════════════════════════════
    # Chapter E — card_foundations  (4 ders, card_choice)
    # ══════════════════════════════════════════════════════════════
    {
        "id": "cards_rescue_now",
        "chapter": "card_foundations",
        "kind": "card_choice",
        "scenario_id": "rescue_pick",
        "lesson_type": "card_lab",
        "title_key": "tutorial_card_rescue_title",
        "title_fallback": "Acil kurtarma seçimi",
        "description_key": "tutorial_card_rescue_desc",
        "description_fallback": "Tehlikeli bir tahtada önce hangi kartın gerçekten nefes aldırdığını öğren.",
        "why_it_matters": "Riskli board'da öncelik: hayatta kalmak, skor değil.",
        "difficulty": 2,
        "duration_seconds": 30,
        "skill_tags": ["cards", "rescue"],
        "allowed_actions": ["move_left", "move_right", "confirm"],
    },
    {
        "id": "cards_perk_vs_instant",
        "chapter": "card_foundations",
        "kind": "card_choice",
        "scenario_id": "perk_vs_instant",
        "lesson_type": "card_lab",
        "title_key": "tutorial_cards_perk_vs_instant_title",
        "title_fallback": "Perk mi, anlık mı?",
        "description_key": "tutorial_cards_perk_vs_instant_desc",
        "description_fallback": "Kalıcı perk ile anlık spell arasındaki zaman ufku farkını anla.",
        "why_it_matters": "Anlık efekt bir satır çözer; perk tüm run boyunca değer üretir.",
        "difficulty": 2,
        "duration_seconds": 30,
        "skill_tags": ["cards", "perk", "instant"],
        "allowed_actions": ["move_left", "move_right", "confirm"],
    },

    # ══════════════════════════════════════════════════════════════
    # Chapter F — card_strategy  (4 ders, card_choice)
    # ══════════════════════════════════════════════════════════════
    {
        "id": "cards_synergy_scale",
        "chapter": "card_strategy",
        "kind": "card_choice",
        "scenario_id": "synergy_pick",
        "lesson_type": "card_lab",
        "title_key": "tutorial_card_synergy_title",
        "title_fallback": "Sinerji seçimi",
        "description_key": "tutorial_card_synergy_desc",
        "description_fallback": "Mevcut build ile en iyi çalışan kartı okumayı öğren.",
        "why_it_matters": "Tek kart gücü değil, mevcut perk zinciriyle uyum önemlidir.",
        "difficulty": 3,
        "duration_seconds": 30,
        "skill_tags": ["cards", "synergy"],
        "allowed_actions": ["move_left", "move_right", "confirm"],
    },
    {
        "id": "cards_rare_not_auto_pick",
        "chapter": "card_strategy",
        "kind": "card_choice",
        "scenario_id": "rare_not_auto",
        "lesson_type": "card_lab",
        "title_key": "tutorial_cards_rare_not_auto_title",
        "title_fallback": "Nadir ≠ doğru",
        "description_key": "tutorial_cards_rare_not_auto_desc",
        "description_fallback": "Nadir kartın her zaman doğru kart olmadığını gör.",
        "why_it_matters": "Rarity, board ihtiyacını değil; kartın genel gücünü gösterir.",
        "difficulty": 3,
        "duration_seconds": 30,
        "skill_tags": ["cards", "rarity", "decision"],
        "allowed_actions": ["move_left", "move_right", "confirm"],
    },
    {
        "id": "cards_build_direction",
        "chapter": "card_strategy",
        "kind": "card_choice",
        "scenario_id": "build_direction",
        "lesson_type": "card_lab",
        "title_key": "tutorial_cards_build_direction_title",
        "title_fallback": "Hedefli çözüm",
        "description_key": "tutorial_cards_build_direction_desc",
        "description_fallback": "Tek bir kule veya lokal problem varsa, geniş etki yerine nokta atışı kartı seç.",
        "why_it_matters": "Doğru kart bazen en büyük efekt değil, en az israfla çözen karttır.",
        "difficulty": 3,
        "duration_seconds": 30,
        "skill_tags": ["cards", "precision", "efficiency"],
        "allowed_actions": ["move_left", "move_right", "confirm"],
    },
    {
        "id": "cards_risk_reward_timing",
        "chapter": "card_strategy",
        "kind": "card_choice",
        "scenario_id": "risk_reward_timing",
        "lesson_type": "card_lab",
        "title_key": "tutorial_cards_risk_reward_title",
        "title_fallback": "Risk-getiri zamanlaması",
        "description_key": "tutorial_cards_risk_reward_desc",
        "description_fallback": "Tempo açma penceresini ne zaman zorlamanın doğru olduğunu öğren.",
        "why_it_matters": "Güvenli board'da risk almak büyütür; tehlikeli board'da öldürür.",
        "difficulty": 3,
        "duration_seconds": 30,
        "skill_tags": ["cards", "risk", "timing"],
        "allowed_actions": ["move_left", "move_right", "confirm"],
    },

    # ══════════════════════════════════════════════════════════════
    # Chapter G — mastery_exams  (3 ders, scenario)
    # ══════════════════════════════════════════════════════════════
    {
        "id": "exam_board_midterm",
        "chapter": "mastery_exams",
        "kind": "scenario",
        "scenario_id": "exam_board_combined",
        "lesson_type": "exam",
        "title_key": "tutorial_exam_board_title",
        "title_fallback": "Board Ara Sınavı",
        "description_key": "tutorial_exam_board_desc",
        "description_fallback": "Yüzey, delik ve kuyu kararlarını tek senaryoda birleştir.",
        "why_it_matters": "Tekil ilkeleri birlikte uygulayabilmek gerçek ustalıktır.",
        "goal_fallback": "Hedef: Birden fazla hedefi aynı anda tamamla.",
        "tip_fallback": "İpuçları az — öğrendiklerini birleştir.",
        "difficulty": 4,
        "duration_seconds": 60,
        "skill_tags": ["exam", "surface", "well", "holes"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "exam_plan_midterm",
        "chapter": "mastery_exams",
        "kind": "scenario",
        "scenario_id": "exam_plan_combined",
        "lesson_type": "exam",
        "title_key": "tutorial_exam_plan_title",
        "title_fallback": "Planlama Ara Sınavı",
        "description_key": "tutorial_exam_plan_desc",
        "description_fallback": "Queue, hold ve risk azaltma kararlarını aynı senaryoda kullan.",
        "why_it_matters": "Planlama ilkelerini bilinçsiz reflekse çevirmek hedef.",
        "goal_fallback": "Hedef: Hold ve queue'yu kullanarak temiz sonuç al.",
        "tip_fallback": "Az ipucu — sırayı ve hold'u birlikte düşün.",
        "difficulty": 4,
        "duration_seconds": 60,
        "skill_tags": ["exam", "queue", "hold", "planning"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop", "hold"],
    },
    {
        "id": "exam_hybrid_final",
        "chapter": "mastery_exams",
        "kind": "scenario",
        "scenario_id": "exam_hybrid_final",
        "lesson_type": "exam",
        "title_key": "tutorial_exam_hybrid_title",
        "title_fallback": "Final Sınavı",
        "description_key": "tutorial_exam_hybrid_desc",
        "description_fallback": "Board + kart + zamanlama + geri bildirim öğrenişinin final sentezi.",
        "why_it_matters": "Her şeyi birleştiren son test.",
        "goal_fallback": "Hedef: Tüm becerileri tek bir senaryoda göster.",
        "tip_fallback": "Artık ipucu yok — sen biliyorsun.",
        "difficulty": 5,
        "duration_seconds": 90,
        "skill_tags": ["exam", "mastery"],
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop", "hold"],
    },
]


# ---------------------------------------------------------------------------
# Lookup tablolar
# ---------------------------------------------------------------------------
CHAPTER_BY_ID: Dict[str, Dict[str, Any]] = {chapter["id"]: chapter for chapter in CHAPTERS}
LESSON_BY_ID: Dict[str, Dict[str, Any]] = {lesson["id"]: lesson for lesson in LESSONS}
LESSON_BY_LEGACY_STEP: Dict[int, Dict[str, Any]] = {
    int(lesson["legacy_step"]): lesson
    for lesson in LESSONS
    if isinstance(lesson.get("legacy_step"), int)
}

# Eski ID'lerden yeni ID'lere ek lookup
for _old_id, _new_id in LEGACY_LESSON_MAP.items():
    if _old_id not in LESSON_BY_ID and _new_id in LESSON_BY_ID:
        LESSON_BY_ID[_old_id] = LESSON_BY_ID[_new_id]


def _resolve_chapter_id(chapter_id: str | None) -> str:
    if not chapter_id:
        return ""
    return str(LEGACY_CHAPTER_MAP.get(str(chapter_id), chapter_id))


def _resolve_lesson_id(lesson_id: str | None) -> str:
    lesson = get_lesson(lesson_id)
    if not lesson:
        return ""
    return str(lesson.get("id") or "")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_chapters() -> List[Dict[str, Any]]:
    return [dict(chapter) for chapter in CHAPTERS]


def get_chapter(chapter_id: str | None) -> Optional[Dict[str, Any]]:
    """Tek bir bölüm metadata'sını döndür (legacy ID'ler çözülür)."""
    resolved = _resolve_chapter_id(chapter_id)
    if not resolved:
        return None
    chapter = CHAPTER_BY_ID.get(resolved)
    return dict(chapter) if chapter else None


def get_lessons() -> List[Dict[str, Any]]:
    return [dict(lesson) for lesson in LESSONS]


def list_lessons_for_chapter(chapter_id: str) -> List[Dict[str, Any]]:
    resolved = _resolve_chapter_id(chapter_id)
    return [dict(lesson) for lesson in LESSONS if lesson.get("chapter") == resolved]


def get_lesson(lesson_id: str | None) -> Optional[Dict[str, Any]]:
    if not lesson_id:
        return None
    lesson = LESSON_BY_ID.get(str(lesson_id))
    return dict(lesson) if lesson else None


def get_lesson_for_legacy_step(step_num: int | None) -> Optional[Dict[str, Any]]:
    if step_num is None:
        return None
    lesson = LESSON_BY_LEGACY_STEP.get(int(step_num))
    return dict(lesson) if lesson else None


def get_legacy_step_for_lesson(lesson_id: str | None) -> Optional[int]:
    lesson = get_lesson(lesson_id)
    if not lesson:
        return None
    legacy_step = lesson.get("legacy_step")
    return int(legacy_step) if isinstance(legacy_step, int) else None


def get_first_lesson_id(chapter_id: str | None = None) -> Optional[str]:
    if chapter_id:
        chapter_lessons = list_lessons_for_chapter(chapter_id)
        return chapter_lessons[0]["id"] if chapter_lessons else None
    return LESSONS[0]["id"] if LESSONS else None


def get_next_lesson_id(lesson_id: str | None, chapter_only: bool = False) -> Optional[str]:
    if not lesson_id:
        return get_first_lesson_id()
    resolved_lesson_id = _resolve_lesson_id(lesson_id)
    if not resolved_lesson_id:
        return None
    lesson = get_lesson(resolved_lesson_id)
    chapter_id = str(lesson.get("chapter") or "") if lesson else ""
    for index, l in enumerate(LESSONS):
        if l.get("id") == resolved_lesson_id:
            if index + 1 < len(LESSONS):
                next_lesson = LESSONS[index + 1]
                if chapter_only and str(next_lesson.get("chapter") or "") != chapter_id:
                    return None
                return str(next_lesson["id"])
            return None
    return None