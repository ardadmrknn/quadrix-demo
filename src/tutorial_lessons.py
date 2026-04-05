"""Tutorial ders kataloğu.

Faz 1'de mevcut step tabanlı tutorial akışını veri odaklı bir ders listesine
taşımak için kullanılır. Davranış korunur; lesson metadata ayrı dosyada tutulur.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


CHAPTERS: List[Dict[str, Any]] = [
    {
        "id": "basics",
        "title_key": "tutorial_basics_title",
        "title_fallback": "Temel Kontroller",
        "description_key": "tutorial_basics_desc",
        "description_fallback": "Hareket, döndürme, düşürme ve saklama temellerini sırayla öğren.",
        "unlocked_by_default": True,
    },
    {
        "id": "board_basics",
        "title_key": "tutorial_board_basics_title",
        "title_fallback": "Tahta Okuma",
        "description_key": "tutorial_board_basics_desc",
        "description_fallback": "Tahtayı okuyup temiz, güvenli ve verimli yerleşim yapmayı öğren.",
        "unlocked_by_default": False,
    },
    {
        "id": "card_academy",
        "title_key": "tutorial_card_academy_title",
        "title_fallback": "Kart Akademisi",
        "description_key": "tutorial_card_academy_desc",
        "description_fallback": "Kart seçimlerini tahta durumuna göre değerlendirmeyi öğren.",
        "unlocked_by_default": False,
    },
]


LESSONS: List[Dict[str, Any]] = [
    {
        "id": "move_intro",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 1,
        "title_key": "tutorial_lesson_move_title",
        "title_fallback": "Hareket ve konum alma",
        "description_key": "tutorial_lesson_move_desc",
        "description_fallback": "Parçayı sağa ve sola taşıyarak yatay kontrolü öğren.",
        "allowed_actions": ["move_left", "move_right"],
        "success_condition": "move_left_right_counts",
    },
    {
        "id": "rotate_intro",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 2,
        "title_key": "tutorial_lesson_rotate_title",
        "title_fallback": "Döndürme kontrolü",
        "description_key": "tutorial_lesson_rotate_desc",
        "description_fallback": "Boşluğu okuyup parçayı doğru anda döndür.",
        "allowed_actions": ["rotate"],
        "success_condition": "rotate_three_times",
    },
    {
        "id": "soft_drop_intro",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 3,
        "title_key": "tutorial_lesson_soft_drop_title",
        "title_fallback": "Yumuşak düşürme",
        "description_key": "tutorial_lesson_soft_drop_desc",
        "description_fallback": "Parçayı kilitlemeden kontrollü biçimde aşağı indir.",
        "allowed_actions": ["soft_drop"],
        "success_condition": "soft_drop_frames",
    },
    {
        "id": "hard_drop_intro",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 4,
        "title_key": "tutorial_lesson_hard_drop_title",
        "title_fallback": "Sert düşürme",
        "description_key": "tutorial_lesson_hard_drop_desc",
        "description_fallback": "Net gördüğün anda parçayı tek tuşla anında yerleştir.",
        "allowed_actions": ["hard_drop"],
        "success_condition": "hard_drop_once",
    },
    {
        "id": "line_clear_intro",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 5,
        "title_key": "tutorial_lesson_line_clear_title",
        "title_fallback": "Satır tamamlama",
        "description_key": "tutorial_lesson_line_clear_desc",
        "description_fallback": "Boşluğu kapatıp ilk satır temizlemeni yap.",
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop", "hold"],
        "success_condition": "line_clear_once",
    },
    {
        "id": "hold_intro",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 6,
        "title_key": "tutorial_lesson_hold_title",
        "title_fallback": "Parça saklama",
        "description_key": "tutorial_lesson_hold_desc",
        "description_fallback": "Uygun olmayan parçayı saklayıp sıradaki parçayla devam et.",
        "allowed_actions": ["hold", "move_left", "move_right", "rotate", "soft_drop"],
        "success_condition": "hold_once",
    },
    {
        "id": "tutorial_complete",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 7,
        "title_key": "tutorial_lesson_complete_title",
        "title_fallback": "Temel eğitim özeti",
        "description_key": "tutorial_lesson_complete_desc",
        "description_fallback": "Temel kontrolleri toparla ve sonraki bölümlere geç.",
        "allowed_actions": [],
        "success_condition": "confirm_exit",
    },
    {
        "id": "board_gap_fill",
        "chapter": "board_basics",
        "kind": "scenario",
        "scenario_id": "gap_fill_double",
        "title_key": "tutorial_board_gap_fill_title",
        "title_fallback": "Geniş boşluğu kapat",
        "description_key": "tutorial_board_gap_fill_desc",
        "description_fallback": "İki hücrelik boşluğu doğru parçayla kapat ve iki satırı aynı anda temizle.",
        "goal_fallback": "Hedef: İki satırı temizle ve yeni delik açma.",
        "tip_fallback": "Kart seçimlerinde de önce tahtadaki geniş boşlukları fark etmek gerekir.",
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "board_keep_low",
        "chapter": "board_basics",
        "kind": "scenario",
        "scenario_id": "keep_stack_low",
        "title_key": "tutorial_board_keep_low_title",
        "title_fallback": "Kuleyi alçak tut",
        "description_key": "tutorial_board_keep_low_desc",
        "description_fallback": "Her hamlede satır temizlemek gerekmez; bazen en iyi oyun yüksekliği artırmamaktır.",
        "goal_fallback": "Hedef: Yeni delik açmadan yüksekliği artırma.",
        "tip_fallback": "Açık tarafı kullanmak, kötü bir boşluğu zorla kapatmaktan daha güçlüdür.",
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "board_vertical_well",
        "chapter": "board_basics",
        "kind": "scenario",
        "scenario_id": "vertical_well_quadrix",
        "title_key": "tutorial_board_vertical_well_title",
        "title_fallback": "Kuyuyu değerlendir",
        "description_key": "tutorial_board_vertical_well_desc",
        "description_fallback": "Hazır kuyuyu fark et ve I parçasıyla tek hamlede Quadrix yap.",
        "goal_fallback": "Hedef: Kuyuda I parçasıyla 4 satır temizle.",
        "tip_fallback": "Kart modunda güçlü karar, sadece iyi kartı seçmek değil; onu bekleyecek tahtayı hazırlamaktır.",
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "card_rescue_pick",
        "chapter": "card_academy",
        "kind": "card_choice",
        "scenario_id": "rescue_pick",
        "title_key": "tutorial_card_rescue_title",
        "title_fallback": "Acil kurtarma seçimi",
        "description_key": "tutorial_card_rescue_desc",
        "description_fallback": "Tehlikeli bir tahtada önce hangi kartın gerçekten nefes aldırdığını öğren.",
        "allowed_actions": ["move_left", "move_right", "confirm"],
    },
    {
        "id": "card_long_term_pick",
        "chapter": "card_academy",
        "kind": "card_choice",
        "scenario_id": "long_term_pick",
        "title_key": "tutorial_card_long_term_title",
        "title_fallback": "Uzun vadeli değer",
        "description_key": "tutorial_card_long_term_desc",
        "description_fallback": "Tahta güvenliyken anlık kazanç yerine kalıcı değer üreten kartı seç.",
        "allowed_actions": ["move_left", "move_right", "confirm"],
    },
    {
        "id": "card_synergy_pick",
        "chapter": "card_academy",
        "kind": "card_choice",
        "scenario_id": "synergy_pick",
        "title_key": "tutorial_card_synergy_title",
        "title_fallback": "Sinerji seçimi",
        "description_key": "tutorial_card_synergy_desc",
        "description_fallback": "Mevcut build ile en iyi çalışan kartı okumayı öğren.",
        "allowed_actions": ["move_left", "move_right", "confirm"],
    },
]


CHAPTER_BY_ID: Dict[str, Dict[str, Any]] = {chapter["id"]: chapter for chapter in CHAPTERS}
LESSON_BY_ID: Dict[str, Dict[str, Any]] = {lesson["id"]: lesson for lesson in LESSONS}
LESSON_BY_LEGACY_STEP: Dict[int, Dict[str, Any]] = {
    int(lesson["legacy_step"]): lesson
    for lesson in LESSONS
    if isinstance(lesson.get("legacy_step"), int)
}


def get_chapters() -> List[Dict[str, Any]]:
    return [dict(chapter) for chapter in CHAPTERS]


def get_lessons() -> List[Dict[str, Any]]:
    return [dict(lesson) for lesson in LESSONS]


def list_lessons_for_chapter(chapter_id: str) -> List[Dict[str, Any]]:
    return [dict(lesson) for lesson in LESSONS if lesson.get("chapter") == chapter_id]


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
    lesson = get_lesson(lesson_id)
    chapter_id = str(lesson.get("chapter") or "") if lesson else ""
    for index, lesson in enumerate(LESSONS):
        if lesson.get("id") == lesson_id:
            if index + 1 < len(LESSONS):
                next_lesson = LESSONS[index + 1]
                if chapter_only and str(next_lesson.get("chapter") or "") != chapter_id:
                    return None
                return str(next_lesson["id"])
            return None
    return None