"""Tutorial progress veri yardimcilari.

Bu modul saf veri donusumleri yapar. Disk yazma ve kullanici secimi gibi
yan etkiler user_manager tarafinda kalir.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict

try:
    from .tutorial_lessons import CHAPTERS, LEGACY_CHAPTER_MAP, LEGACY_LESSON_MAP, get_lesson, list_lessons_for_chapter  # type: ignore
except Exception:
    from tutorial_lessons import CHAPTERS, LEGACY_CHAPTER_MAP, LEGACY_LESSON_MAP, get_lesson, list_lessons_for_chapter


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp_stars(stars: Any) -> int:
    try:
        value = int(stars)
    except Exception:
        value = 0
    return max(0, min(3, value))


def build_default_tutorial_progress() -> Dict[str, Any]:
    chapters: Dict[str, Any] = {}
    for chapter in CHAPTERS:
        chapter_id = str(chapter.get("id") or "")
        lessons = {
            str(lesson.get("id")): {
                "completed": False,
                "stars": 0,
                "best_stats": {},
                "first_completed_at": None,
                "last_completed_at": None,
            }
            for lesson in list_lessons_for_chapter(chapter_id)
        }
        chapters[chapter_id] = {
            "unlocked": bool(chapter.get("unlocked_by_default", False)),
            "completed": False,
            "stars": 0,
            "lessons": lessons,
        }
    return {"chapters": chapters}


def _recalculate_chapter(progress: Dict[str, Any], chapter_id: str) -> None:
    chapter_entry = progress.get("chapters", {}).get(chapter_id)
    if not isinstance(chapter_entry, dict):
        return
    lessons = chapter_entry.get("lessons", {})
    if not isinstance(lessons, dict) or not lessons:
        chapter_entry["completed"] = False
        chapter_entry["stars"] = 0
        return
    total_stars = 0
    completed_count = 0
    for lesson_entry in lessons.values():
        if not isinstance(lesson_entry, dict):
            continue
        total_stars += _clamp_stars(lesson_entry.get("stars", 0))
        if bool(lesson_entry.get("completed", False)):
            completed_count += 1
    chapter_entry["stars"] = total_stars
    chapter_entry["completed"] = completed_count == len(lessons)


def ensure_progress_shape(progress: Any) -> Dict[str, Any]:
    default_progress = build_default_tutorial_progress()
    if not isinstance(progress, dict):
        return default_progress

    normalized = deepcopy(default_progress)
    existing_chapters = progress.get("chapters", {})
    if not isinstance(existing_chapters, dict):
        existing_chapters = {}

    for chapter_id, normalized_chapter in normalized["chapters"].items():
        existing_chapter = existing_chapters.get(chapter_id, {})
        if not isinstance(existing_chapter, dict):
            existing_chapter = {}
        normalized_chapter["unlocked"] = bool(existing_chapter.get("unlocked", normalized_chapter["unlocked"]))

        existing_lessons = existing_chapter.get("lessons", {})
        if not isinstance(existing_lessons, dict):
            existing_lessons = {}

        for lesson_id, normalized_lesson in normalized_chapter["lessons"].items():
            existing_lesson = existing_lessons.get(lesson_id, {})
            if not isinstance(existing_lesson, dict):
                existing_lesson = {}
            normalized_lesson["completed"] = bool(existing_lesson.get("completed", False))
            normalized_lesson["stars"] = _clamp_stars(existing_lesson.get("stars", 0))
            best_stats = existing_lesson.get("best_stats", {})
            normalized_lesson["best_stats"] = deepcopy(best_stats) if isinstance(best_stats, dict) else {}
            normalized_lesson["first_completed_at"] = existing_lesson.get("first_completed_at")
            normalized_lesson["last_completed_at"] = existing_lesson.get("last_completed_at")

        _recalculate_chapter(normalized, chapter_id)

    unlock_next_chapter_if_needed(normalized)
    return normalized


def mark_lesson_completed(progress: Any, lesson_id: str, stars: int, stats: Dict[str, Any] | None = None) -> Dict[str, Any]:
    normalized = ensure_progress_shape(progress)
    lesson = get_lesson(lesson_id)
    if not lesson:
        return normalized

    canonical_lesson_id = str(lesson.get("id") or "")
    chapter_id = str(lesson.get("chapter") or "")
    chapter_entry = normalized.get("chapters", {}).get(chapter_id)
    if not isinstance(chapter_entry, dict):
        return normalized

    lesson_entry = chapter_entry.get("lessons", {}).get(canonical_lesson_id)
    if not isinstance(lesson_entry, dict):
        return normalized

    lesson_entry["completed"] = True
    lesson_entry["stars"] = max(_clamp_stars(lesson_entry.get("stars", 0)), _clamp_stars(stars))
    if stats:
        best_stats = lesson_entry.get("best_stats", {})
        if not isinstance(best_stats, dict):
            best_stats = {}
        best_stats.update(deepcopy(stats))
        lesson_entry["best_stats"] = best_stats
    now_iso = _utc_now_iso()
    if not lesson_entry.get("first_completed_at"):
        lesson_entry["first_completed_at"] = now_iso
    lesson_entry["last_completed_at"] = now_iso

    _recalculate_chapter(normalized, chapter_id)
    unlock_next_chapter_if_needed(normalized)
    return normalized


def mark_chapter_completed(progress: Any, chapter_id: str, stars_per_lesson: int = 1) -> Dict[str, Any]:
    normalized = ensure_progress_shape(progress)
    for lesson in list_lessons_for_chapter(chapter_id):
        lesson_id = str(lesson.get("id") or "")
        if lesson_id:
            normalized = mark_lesson_completed(normalized, lesson_id, stars_per_lesson)
    return normalized


def get_chapter_completion(progress: Any, chapter_id: str) -> Dict[str, Any]:
    normalized = ensure_progress_shape(progress)
    resolved_chapter_id = LEGACY_CHAPTER_MAP.get(chapter_id, chapter_id)
    chapter_entry = normalized.get("chapters", {}).get(resolved_chapter_id, {})
    lessons = chapter_entry.get("lessons", {}) if isinstance(chapter_entry, dict) else {}
    lesson_values = list(lessons.values()) if isinstance(lessons, dict) else []
    completed_count = sum(1 for lesson in lesson_values if isinstance(lesson, dict) and lesson.get("completed"))
    total_lessons = len(lesson_values)
    return {
        "unlocked": bool(chapter_entry.get("unlocked", False)),
        "completed": bool(chapter_entry.get("completed", False)),
        "stars": int(chapter_entry.get("stars", 0) or 0),
        "completed_lessons": completed_count,
        "total_lessons": total_lessons,
    }


def get_total_stars(progress: Any) -> int:
    normalized = ensure_progress_shape(progress)
    total = 0
    for chapter_entry in normalized.get("chapters", {}).values():
        if isinstance(chapter_entry, dict):
            total += int(chapter_entry.get("stars", 0) or 0)
    return total


def unlock_next_chapter_if_needed(progress: Dict[str, Any]) -> Dict[str, Any]:
    chapters = progress.get("chapters", {})
    if not isinstance(chapters, dict):
        return progress
    for index, chapter in enumerate(CHAPTERS[:-1]):
        current_chapter_id = str(chapter.get("id") or "")
        next_chapter_id = str(CHAPTERS[index + 1].get("id") or "")
        current_entry = chapters.get(current_chapter_id)
        next_entry = chapters.get(next_chapter_id)
        if isinstance(current_entry, dict) and isinstance(next_entry, dict) and bool(current_entry.get("completed", False)):
            next_entry["unlocked"] = True
    return progress


def migrate_legacy_progress(progress: Any) -> Dict[str, Any]:
    """Eski chapter/lesson ID'lerini yeni V2 ID'lerine taşır.

    Eğer progress zaten yeni ID'leri içeriyorsa dokunmaz.
    """
    if not isinstance(progress, dict):
        return ensure_progress_shape(progress)

    old_chapters = progress.get("chapters", {})
    if not isinstance(old_chapters, dict):
        return ensure_progress_shape(progress)

    # Yeni ID'ler zaten varsa migration gerekmez
    has_new_ids = any(ch_id in old_chapters for ch_id in ("quick_start", "surface_control", "queue_hold"))
    has_old_ids = any(ch_id in old_chapters for ch_id in LEGACY_CHAPTER_MAP)

    if not has_old_ids or has_new_ids:
        return ensure_progress_shape(progress)

    migrated_chapters: Dict[str, Any] = {}

    for old_chapter_id, old_chapter_data in old_chapters.items():
        if not isinstance(old_chapter_data, dict):
            continue
        new_chapter_id = LEGACY_CHAPTER_MAP.get(old_chapter_id, old_chapter_id)
        old_lessons = old_chapter_data.get("lessons", {})
        if not isinstance(old_lessons, dict):
            old_lessons = {}

        migrated_lessons: Dict[str, Any] = {}
        for old_lesson_id, old_lesson_data in old_lessons.items():
            if not isinstance(old_lesson_data, dict):
                continue
            new_lesson_id = LEGACY_LESSON_MAP.get(old_lesson_id, old_lesson_id)
            migrated_lessons[new_lesson_id] = deepcopy(old_lesson_data)

        migrated_chapter = deepcopy(old_chapter_data)
        migrated_chapter["lessons"] = migrated_lessons
        migrated_chapters[new_chapter_id] = migrated_chapter

    progress_copy = deepcopy(progress)
    progress_copy["chapters"] = migrated_chapters
    return ensure_progress_shape(progress_copy)