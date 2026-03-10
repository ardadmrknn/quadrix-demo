"""Tutorial ders kataloğu.

Faz 1'de mevcut step tabanlı tutorial akışını veri odaklı bir ders listesine
taşımak için kullanılır. Davranış korunur; lesson metadata ayrı dosyada tutulur.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


CHAPTERS: List[Dict[str, Any]] = [
    {
        "id": "basics",
        "title_key": "tutorial_mode",
        "title_fallback": "Egitim",
        "description_key": "tutorial_welcome_desc",
        "description_fallback": "Temel Quadrix hareketlerini ogreten baslangic bolumu.",
        "unlocked_by_default": True,
    },
    {
        "id": "board_basics",
        "title_key": "tutorial_board_basics_title",
        "title_fallback": "Tahta Okuma",
        "description_key": "tutorial_board_basics_desc",
        "description_fallback": "Kuleyi okuyup temiz ve verimli yerlestirme yapmayi ogreten bolum.",
        "unlocked_by_default": False,
    },
    {
        "id": "card_academy",
        "title_key": "tutorial_card_academy_title",
        "title_fallback": "Kart Akademisi",
        "description_key": "tutorial_card_academy_desc",
        "description_fallback": "Kart secimini board durumuna gore okumayi ogreten bolum.",
        "unlocked_by_default": False,
    },
]


LESSONS: List[Dict[str, Any]] = [
    {
        "id": "move_intro",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 1,
        "title_key": "tutorial_welcome_move",
        "title_fallback": "Hareket",
        "description_key": "tutorial_tip_step_1",
        "description_fallback": "Saga ve sola hareket etmeyi ogren.",
        "allowed_actions": ["move_left", "move_right"],
        "success_condition": "move_left_right_counts",
    },
    {
        "id": "rotate_intro",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 2,
        "title_key": "tutorial_welcome_rotate",
        "title_fallback": "Dondurme",
        "description_key": "tutorial_tip_step_2",
        "description_fallback": "Parcalari dondurmeyi ogren.",
        "allowed_actions": ["rotate"],
        "success_condition": "rotate_three_times",
    },
    {
        "id": "soft_drop_intro",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 3,
        "title_key": "tutorial_welcome_soft_drop",
        "title_fallback": "Yavas Dusus",
        "description_key": "tutorial_tip_step_3",
        "description_fallback": "Soft drop ile parcayi kontrollu indir.",
        "allowed_actions": ["soft_drop"],
        "success_condition": "soft_drop_frames",
    },
    {
        "id": "hard_drop_intro",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 4,
        "title_key": "tutorial_welcome_hard_drop",
        "title_fallback": "Sert Dusus",
        "description_key": "tutorial_tip_step_4",
        "description_fallback": "Hard drop ile parcayi aninda yerlestir.",
        "allowed_actions": ["hard_drop"],
        "success_condition": "hard_drop_once",
    },
    {
        "id": "line_clear_intro",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 5,
        "title_key": "tutorial_welcome_line_clear",
        "title_fallback": "Satir Temizleme",
        "description_key": "tutorial_tip_step_5",
        "description_fallback": "Bir satiri tamamlayip temizle.",
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop", "hold"],
        "success_condition": "line_clear_once",
    },
    {
        "id": "hold_intro",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 6,
        "title_key": "tutorial_welcome_hold",
        "title_fallback": "Hold",
        "description_key": "tutorial_tip_step_6",
        "description_fallback": "Bir parcayi hold alaninda sakla.",
        "allowed_actions": ["hold", "move_left", "move_right", "rotate", "soft_drop"],
        "success_condition": "hold_once",
    },
    {
        "id": "tutorial_complete",
        "chapter": "basics",
        "kind": "legacy_step",
        "legacy_step": 7,
        "title_key": "tutorial_complete",
        "title_fallback": "Tamamlandi",
        "description_key": "tutorial_tip_step_7",
        "description_fallback": "Tutorial tamamlandi; cikmak icin Enter bas.",
        "allowed_actions": [],
        "success_condition": "confirm_exit",
    },
    {
        "id": "board_gap_fill",
        "chapter": "board_basics",
        "kind": "scenario",
        "scenario_id": "gap_fill_double",
        "title_key": "tutorial_board_gap_fill_title",
        "title_fallback": "Genis Boslugu Oku",
        "description_key": "tutorial_board_gap_fill_desc",
        "description_fallback": "Iki hucrelik boslugu dogru parca ile kapat ve iki satiri ayni anda sil.",
        "goal_fallback": "Hedef: Iki satir temizle ve yeni delik acma.",
        "tip_fallback": "Kart seciminde de once tahtadaki genis bosluklari fark etmek gerekir.",
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "board_keep_low",
        "chapter": "board_basics",
        "kind": "scenario",
        "scenario_id": "keep_stack_low",
        "title_key": "tutorial_board_keep_low_title",
        "title_fallback": "Kuleyi Alçak Tut",
        "description_key": "tutorial_board_keep_low_desc",
        "description_fallback": "Her hamlede temizleme gerekmez; bazen en iyi oyun yuksekligi artirmamaktir.",
        "goal_fallback": "Hedef: Yeni delik acmadan yuksekligi artirma.",
        "tip_fallback": "Acik tarafi kullanmak, kotu bir boslugu zorla doldurmaktan daha gucludur.",
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "board_vertical_well",
        "chapter": "board_basics",
        "kind": "scenario",
        "scenario_id": "vertical_well_quadrix",
        "title_key": "tutorial_board_vertical_well_title",
        "title_fallback": "Kuyuyu Oku",
        "description_key": "tutorial_board_vertical_well_desc",
        "description_fallback": "Hazir kuyuyu gor ve I parcasi ile tek hamlede Quadrix yap.",
        "goal_fallback": "Hedef: Kuyuda I parcasi ile 4 satir temizle.",
        "tip_fallback": "Kart modunda guclu karar, sadece iyi karti secmek degil onu bekleyecek tahta hazirlamaktir.",
        "allowed_actions": ["move_left", "move_right", "rotate", "soft_drop", "hard_drop"],
    },
    {
        "id": "card_rescue_pick",
        "chapter": "card_academy",
        "kind": "card_choice",
        "scenario_id": "rescue_pick",
        "title_key": "tutorial_card_rescue_title",
        "title_fallback": "Kurtarma Karti Sec",
        "description_key": "tutorial_card_rescue_desc",
        "description_fallback": "Tehlikeli tahtada once hangi kartin seni kurtardigini ogren.",
        "allowed_actions": ["move_left", "move_right", "confirm"],
    },
    {
        "id": "card_long_term_pick",
        "chapter": "card_academy",
        "kind": "card_choice",
        "scenario_id": "long_term_pick",
        "title_key": "tutorial_card_long_term_title",
        "title_fallback": "Uzun Vadeli Yatirim",
        "description_key": "tutorial_card_long_term_desc",
        "description_fallback": "Guvenli oyunda anlik kart yerine kalici deger ureten secimi bul.",
        "allowed_actions": ["move_left", "move_right", "confirm"],
    },
    {
        "id": "card_synergy_pick",
        "chapter": "card_academy",
        "kind": "card_choice",
        "scenario_id": "synergy_pick",
        "title_key": "tutorial_card_synergy_title",
        "title_fallback": "Sinerjiyi Oku",
        "description_key": "tutorial_card_synergy_desc",
        "description_fallback": "Mevcut build ile hangi kartin buyudugunu okumayi ogren.",
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