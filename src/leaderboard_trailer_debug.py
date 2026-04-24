from __future__ import annotations

TRAILER_DEBUG_DURATION_MS = 4200
TRAILER_DEBUG_TRIGGER_KEY = 'L'
TRAILER_DEBUG_LUNA_ID = 'debug_luna'
TRAILER_DEBUG_LUNA_ASSET = 'assets/test_icon/luna_leaderboard_icon.png'

_PLAYER_SCORES = [118000, 113000, 108000, 103000, 98000, 93000, 88000, 83000, 78000]
_LUNA_START_SCORE = 64000
_LUNA_TARGET_SCORE = 123500


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _smoothstep(value: float) -> float:
    value = _clamp01(value)
    return value * value * (3.0 - 2.0 * value)


def build_trailer_debug_seed_entries() -> list[dict]:
    entries: list[dict] = []
    for idx, score in enumerate(_PLAYER_SCORES, start=1):
        entries.append({
            'debug_id': f'debug_player_{idx}',
            'debug_persona': f'Player {idx}',
            'rank': idx,
            'score': score,
        })

    entries.append({
        'debug_id': TRAILER_DEBUG_LUNA_ID,
        'debug_persona': 'Luna',
        'debug_avatar_asset': TRAILER_DEBUG_LUNA_ASSET,
        'rank': 10,
        'score': _LUNA_START_SCORE,
    })
    return entries


def build_trailer_debug_entries(
    now_ms: int,
    start_ms: int | None,
    duration_ms: int = TRAILER_DEBUG_DURATION_MS,
) -> tuple[list[dict], float, bool]:
    entries = build_trailer_debug_seed_entries()
    progress = 0.0 if start_ms is None else _clamp01((int(now_ms) - int(start_ms)) / float(max(1, duration_ms)))
    eased_progress = _smoothstep(progress)
    luna_score = int(round(_LUNA_START_SCORE + (_LUNA_TARGET_SCORE - _LUNA_START_SCORE) * eased_progress))

    for entry in entries:
        if entry.get('debug_id') == TRAILER_DEBUG_LUNA_ID:
            entry['score'] = luna_score
            break

    sorted_entries = sorted(
        entries,
        key=lambda item: (
            -int(item.get('score', 0) or 0),
            int(item.get('rank', 999) or 999),
            str(item.get('debug_id', '')),
        ),
    )
    for rank, entry in enumerate(sorted_entries, start=1):
        entry['rank'] = rank

    is_running = start_ms is not None and progress < 1.0
    return sorted_entries, progress, is_running