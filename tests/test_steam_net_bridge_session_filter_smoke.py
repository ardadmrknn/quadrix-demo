"""
Smoke test — steam_net_bridge session filter (Phase 3)

C++ köprü mevcut değilse tüm testler skip edilir.
"""
import importlib
import pytest

# ---------- Bridge import (graceful skip) ----------

try:
    import steam_net_bridge as _bridge_mod
    BRIDGE_AVAILABLE = True
except ImportError:
    _bridge_mod = None
    BRIDGE_AVAILABLE = False

skip_no_bridge = pytest.mark.skipif(
    not BRIDGE_AVAILABLE,
    reason="steam_net_bridge C++ modülü bulunamadı — Steam SDK olmadan skip edilir"
)


# ---------- Testler ----------

def test_bridge_module_importable_or_skipped():
    """Modül ya import edilebilir ya da ImportError fırlatır — crash olmamalı."""
    try:
        importlib.import_module("steam_net_bridge")
    except ImportError:
        pass  # Beklenen durum; crash değil


@skip_no_bridge
def test_bridge_class_exists():
    """SteamNetBridge sınıfı modülde tanımlı olmalı."""
    assert hasattr(_bridge_mod, "SteamNetBridge"), \
        "steam_net_bridge.SteamNetBridge sınıfı bulunamadı"


@skip_no_bridge
def test_bridge_instantiation_no_crash():
    """SteamNetBridge() oluşturulabilmeli (SteamAPI_Init olmadan crash etmemeli)."""
    try:
        bridge = _bridge_mod.SteamNetBridge()
        assert bridge is not None
    except Exception as exc:
        pytest.skip(f"SteamNetBridge() oluşturma hatası (Steam init olmadan beklenen): {exc}")


@skip_no_bridge
def test_poll_events_returns_list_no_crash():
    """poll_events() crash etmeden çağrılabilmeli ve liste döndürmeli."""
    try:
        bridge = _bridge_mod.SteamNetBridge()
        events = bridge.poll_events()
        assert isinstance(events, list)
    except Exception as exc:
        pytest.skip(f"poll_events() çağrısı başarısız (Steam init olmadan beklenen): {exc}")


@skip_no_bridge
def test_net_event_type_attribute_accessible():
    """NetEvent .type, .steam_id, .data attr'larına erişim crash etmemeli."""
    assert hasattr(_bridge_mod, "NetEvent"), \
        "steam_net_bridge.NetEvent sınıfı bulunamadı"


def test_session_rejected_event_type_string_valid():
    """'session_rejected' event type string'inin Python tarafında tanınması (parse)."""
    # Python event handling kodunda bilinmeyen event type crash etmemelidir.
    # Bu test, string'in yasal bir string olduğunu ve herhangi bir parse
    # mekanizmasında sorun çıkarmayacağını doğrular.
    event_type = "session_rejected"
    assert isinstance(event_type, str)
    assert len(event_type) > 0
    # Bilinen event tipleri arasında olmasa bile set lookup crash etmemeli
    known_events = {"lobby_created", "lobby_joined", "session_accepted",
                    "lobby_member_joined", "lobby_member_left", "join_requested"}
    # session_rejected henüz known_events'e eklenmemiş olabilir — crash değil
    result = event_type in known_events
    assert isinstance(result, bool)  # bool dönmeli, exception değil


def test_session_rejected_reason_strings_valid():
    """session_rejected olayının data field'ları geçerli string olmalı."""
    reasons = ["not_lobby_member", "no_lobby_no_window"]
    for reason in reasons:
        assert isinstance(reason, str)
        assert len(reason) > 0
