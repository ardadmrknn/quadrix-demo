"""Cloud/local save layout helpers and migration utilities."""

from __future__ import annotations

import copy
import hashlib
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Any

try:
    from .atomic_io import atomic_write_json  # type: ignore
    from .data_paths import (  # type: ignore
        get_local_data_dir,
        iter_legacy_paths,
        migrate_legacy_file,
        resolve_cloud_path,
        resolve_local_path,
        resolve_profile_path,
    )
except Exception:
    from atomic_io import atomic_write_json
    from data_paths import (
        get_local_data_dir,
        iter_legacy_paths,
        migrate_legacy_file,
        resolve_cloud_path,
        resolve_local_path,
        resolve_profile_path,
    )


USERS_SCHEMA_VERSION = 2
SETTINGS_CLOUD_FILENAME = "settings_cloud.json"
SETTINGS_LOCAL_FILENAME = "settings_local.json"
CURRENT_USER_STATE_FILENAME = "current_user.json"
CAMPAIGN_PROGRESS_FILENAME = "campaign_progress.json"
TEMP_AVATAR_DIRNAME = "avatar_temp"

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")

LOCAL_SETTINGS_KEYS = {
    "fullscreen",
    "borderless_fullscreen",
    "resolution",
    "vsync",
    "fps_limit",
    "ui_scale_preset",
    "last_texture_dir",
    "custom_background",
    "bg_main",
    "bg_single",
    "bg_outer",
    "bg_pvp_main",
    "bg_pvp_board",
    "bg_wide",
}


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def read_json_file(path: str, default: Any = None) -> Any:
    try:
        if os.path.exists(path):
            import json

            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
    except Exception:
        pass
    return copy.deepcopy(default)


def write_json_file(path: str, payload: Any, *, indent: int = 2) -> None:
    atomic_write_json(path, payload, indent=indent, ensure_ascii=False)


def slugify_profile_name(value: str, default: str = "player") -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_\-]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw[:32] or default


def make_profile_id(username: str, steam_id: str | None = None, created_at: str | None = None) -> str:
    slug = slugify_profile_name(username)
    seed = "|".join(
        [
            str(username or ""),
            str(steam_id or ""),
            str(created_at or ""),
        ]
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]
    return f"{slug}_{digest}"


def get_users_cloud_path() -> str:
    return resolve_cloud_path("users.json")


def get_settings_cloud_path() -> str:
    return resolve_cloud_path(SETTINGS_CLOUD_FILENAME)


def get_settings_local_path() -> str:
    return resolve_local_path(SETTINGS_LOCAL_FILENAME)


def get_campaign_progress_path() -> str:
    return resolve_cloud_path(CAMPAIGN_PROGRESS_FILENAME)


def get_current_user_state_path() -> str:
    return resolve_local_path(CURRENT_USER_STATE_FILENAME)


def get_profile_achievements_path(profile_id: str) -> str:
    return resolve_profile_path(profile_id, "achievements.json")


def get_profile_highscores_path(profile_id: str) -> str:
    return resolve_profile_path(profile_id, "highscores.json")


def get_profile_avatar_path(profile_id: str) -> str:
    return resolve_profile_path(profile_id, "avatar.png")


def get_temp_avatar_dir() -> str:
    path = os.path.join(get_local_data_dir(), TEMP_AVATAR_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def build_temp_avatar_path(label: str = "avatar") -> str:
    slug = slugify_profile_name(label or "avatar", default="avatar")
    filename = f"{slug}_{int(datetime.now().timestamp() * 1000)}.png"
    return os.path.join(get_temp_avatar_dir(), filename)


def split_controls(controls: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(controls, dict):
        return {}, {}

    cloud_controls: dict[str, Any] = {}
    local_controls: dict[str, Any] = {}

    for section in ("single_player", "pvp"):
        value = controls.get(section)
        if isinstance(value, dict):
            cloud_controls[section] = copy.deepcopy(value)

    gamepad = controls.get("gamepad")
    if isinstance(gamepad, dict):
        local_controls["gamepad"] = copy.deepcopy(gamepad)

    return cloud_controls, local_controls


def merge_controls(default_controls: Any, cloud_controls: Any, local_controls: Any) -> dict[str, Any]:
    merged = copy.deepcopy(default_controls if isinstance(default_controls, dict) else {})

    if isinstance(cloud_controls, dict):
        for section, value in cloud_controls.items():
            if isinstance(value, dict):
                merged[section] = copy.deepcopy(value)

    if isinstance(local_controls, dict):
        gamepad = local_controls.get("gamepad")
        if isinstance(gamepad, dict):
            merged["gamepad"] = copy.deepcopy(gamepad)

    return merged


def split_settings_payload(settings: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(settings, dict):
        return {}, {}, {}

    cloud_settings: dict[str, Any] = {}
    local_settings: dict[str, Any] = {}
    campaign_progress: dict[str, Any] = {}

    for key, value in settings.items():
        if key == "campaign_progress":
            if isinstance(value, dict):
                campaign_progress = copy.deepcopy(value)
            continue

        if key == "controls":
            cloud_controls, local_controls = split_controls(value)
            if cloud_controls:
                cloud_settings["controls"] = cloud_controls
            if local_controls:
                local_settings["controls"] = local_controls
            continue

        if key in LOCAL_SETTINGS_KEYS:
            local_settings[key] = copy.deepcopy(value)
        else:
            cloud_settings[key] = copy.deepcopy(value)

    return cloud_settings, local_settings, campaign_progress


def merge_settings_payload(
    default_settings: dict[str, Any],
    cloud_settings: Any,
    local_settings: Any,
    campaign_progress: Any,
) -> dict[str, Any]:
    merged = copy.deepcopy(default_settings)

    if isinstance(cloud_settings, dict):
        for key, value in cloud_settings.items():
            if key == "controls":
                continue
            merged[key] = copy.deepcopy(value)

    if isinstance(local_settings, dict):
        for key, value in local_settings.items():
            if key == "controls":
                continue
            merged[key] = copy.deepcopy(value)

    merged["controls"] = merge_controls(
        default_settings.get("controls", {}),
        cloud_settings.get("controls", {}) if isinstance(cloud_settings, dict) else {},
        local_settings.get("controls", {}) if isinstance(local_settings, dict) else {},
    )

    merged["campaign_progress"] = (
        copy.deepcopy(campaign_progress) if isinstance(campaign_progress, dict) else {}
    )
    return merged


def is_avatar_reference(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    trimmed = value.strip()
    if not trimmed:
        return False
    lowered = trimmed.lower()
    return any(lowered.endswith(ext) for ext in IMAGE_EXTENSIONS) or os.path.exists(trimmed)


def move_file_into_place(source_path: str, target_path: str) -> str | None:
    try:
        if not source_path or not os.path.exists(source_path):
            return None
    except Exception:
        return None

    source_abs = os.path.abspath(source_path)
    target_abs = os.path.abspath(target_path)
    os.makedirs(os.path.dirname(target_abs), exist_ok=True)

    if source_abs == target_abs:
        return target_abs

    try:
        os.replace(source_abs, target_abs)
        return target_abs
    except OSError:
        try:
            shutil.copy2(source_abs, target_abs)
            try:
                os.remove(source_abs)
            except OSError:
                pass
            return target_abs
        except OSError:
            return None


def dedupe_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for path in paths:
        if not path:
            continue
        key = os.path.abspath(path)
        if key in seen:
            continue
        seen.add(key)
        output.append(path)
    return output


def collect_avatar_candidate_paths(username: str, avatar_value: str | None = None) -> list[str]:
    candidates: list[str] = []

    if isinstance(avatar_value, str) and avatar_value.strip():
        raw = avatar_value.strip()
        if os.path.isabs(raw) or os.path.dirname(raw):
            candidates.append(raw)
        else:
            candidates.extend(iter_legacy_paths(raw))

    legacy_name = f"{username}_avatar.png"
    candidates.extend(iter_legacy_paths(os.path.join("avatars", legacy_name)))
    return dedupe_paths(candidates)


def normalize_avatar_asset(profile_id: str, username: str, avatar_value: Any) -> Any:
    if not is_avatar_reference(avatar_value):
        return avatar_value

    target_path = get_profile_avatar_path(profile_id)
    for candidate in collect_avatar_candidate_paths(username, str(avatar_value)):
        moved = move_file_into_place(candidate, target_path)
        if moved:
            return moved

    if os.path.exists(target_path):
        return target_path

    return avatar_value


def migrate_legacy_settings_file(target_path: str, legacy_filename: str = "settings.json") -> bool:
    return migrate_legacy_file(target_path, iter_legacy_paths(legacy_filename))