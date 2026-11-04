from __future__ import annotations

import pathlib
import sys

import pytest

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import steam_integration


pytestmark = [pytest.mark.quadrix_feedback, pytest.mark.quadrix_phase6]


class _FriendsDll:
    def __init__(self, value: bytes):
        self.value = value

    def SteamAPI_ISteamFriends_GetPersonaName(self, _friends):
        return self.value


def test_persona_refresh_invalidates_cache_and_all_accessors_share_value(monkeypatch):
    monkeypatch.setattr(steam_integration, "_persona_name_cache", "EskiAd")
    monkeypatch.setattr(steam_integration, "_dll", _FriendsDll(b"YeniAd"))
    monkeypatch.setattr(steam_integration, "_isteam_friends", object())
    monkeypatch.setattr(steam_integration, "_init_ok", True)
    monkeypatch.setattr(steam_integration, "is_available", lambda: True)
    monkeypatch.setattr(steam_integration, "get_steam_id", lambda: 76561198000000001)

    assert steam_integration.get_persona_name() == "EskiAd"
    assert steam_integration.refresh_persona_name_cache() == "YeniAd"
    assert steam_integration.get_persona_name() == "YeniAd"
    assert steam_integration.get_user_display_name() == "YeniAd"
    assert steam_integration.get_user_identity()["persona_name"] == "YeniAd"


def test_persona_cache_clear_is_safe_without_steam(monkeypatch):
    monkeypatch.setattr(steam_integration, "_persona_name_cache", "EskiAd")
    steam_integration.clear_persona_name_cache()
    assert steam_integration._persona_name_cache is None

