"""Build-time generated demo/full configuration.

This file is rewritten by scripts/build/write_demo_config.py.
"""

from __future__ import annotations

import os
from typing import MutableMapping


IS_DEMO = True

DEMO_STEAM_APP_ID = "4635310"
DEMO_STEAM_STORE_URL = "https://store.steampowered.com/app/4414520/Quadrix/"
DEMO_APP_NAME = "quadrix_demo"
FULL_APP_NAME = "quadrix_full"

DEMO_LOCKED_EXTRAS_MODE_IDS = {
    "Cascade Mode",
    "Hardcore Mode",
    "Quadrix Extra",
    "Survival Mode",
    "daily_challenge",
}

DEMO_PARTIAL_EXTRAS_MODE_IDS = {"Challenge Mode"}
DEMO_TRANSITION_EXTRAS_MODE_IDS = {"Online PvP"}
DEMO_LOCKED_MAIN_ACTIONS = {"online_coop", "online_pvp"}

DEMO_CHALLENGE_UNLOCKED_STAGES = 20
DEMO_SOLO_WORLD_LIMIT = 1
DEMO_SOLO_LEVEL_LIMIT = 20
DEMO_COOP_WORLD_LIMIT = 1
DEMO_COOP_LEVEL_LIMIT = 10

DEMO_CARD_SELECTION_LEVEL_INTERVAL = 10
FULL_CARD_SELECTION_LEVEL_INTERVAL = 5



def _normalize_id(value: str | None) -> str:
    return str(value or "").strip()

def get_runtime_app_name() -> str:
    return DEMO_APP_NAME if IS_DEMO else FULL_APP_NAME


def get_card_selection_level_interval() -> int:
    if IS_DEMO:
        return DEMO_CARD_SELECTION_LEVEL_INTERVAL
    return FULL_CARD_SELECTION_LEVEL_INTERVAL



def get_card_selection_bucket(level_num: int) -> int:
    interval = max(1, get_card_selection_level_interval())
    try:
        normalized_level = max(0, int(level_num or 0))
    except Exception:
        normalized_level = 0
    return normalized_level // interval


def get_extras_lock_kind(mode_id: str | None) -> str | None:
    if not IS_DEMO:
        return None
    normalized = _normalize_id(mode_id)
    if normalized in DEMO_LOCKED_EXTRAS_MODE_IDS:
        return "full"
    if normalized in DEMO_TRANSITION_EXTRAS_MODE_IDS:
        return "transition"
    if normalized in DEMO_PARTIAL_EXTRAS_MODE_IDS:
        return "partial"
    return None


def is_locked_main_action(action_id: str | None) -> bool:
    return bool(IS_DEMO and _normalize_id(action_id) in DEMO_LOCKED_MAIN_ACTIONS)


def is_solo_campaign_world_available(world_num: int) -> bool:
    if not IS_DEMO:
        return True
    try:
        return int(world_num or 0) <= DEMO_SOLO_WORLD_LIMIT
    except Exception:
        return False


def is_solo_campaign_level_available(level_num: int) -> bool:
    if not IS_DEMO:
        return True
    try:
        return int(level_num or 0) <= DEMO_SOLO_LEVEL_LIMIT
    except Exception:
        return False


def is_coop_campaign_world_available(world_num: int) -> bool:
    if not IS_DEMO:
        return True
    try:
        return int(world_num or 0) <= DEMO_COOP_WORLD_LIMIT
    except Exception:
        return False


def is_coop_campaign_level_available(level_num: int) -> bool:
    if not IS_DEMO:
        return True
    try:
        return int(level_num or 0) <= DEMO_COOP_LEVEL_LIMIT
    except Exception:
        return False

def apply_runtime_environment(env: MutableMapping[str, str] | None = None) -> str | None:
    target_env = os.environ if env is None else env
    target_env.setdefault("QUADRIX_APP_NAME", get_runtime_app_name())
    return target_env.get("QUADRIX_APP_NAME")
