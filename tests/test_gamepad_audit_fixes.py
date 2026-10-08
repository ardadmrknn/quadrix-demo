# -*- coding: utf-8 -*-
"""2026-10-04 gamepad denetim dalgası düzeltmelerinin regresyon testleri (demo).

Denetim (53 ajanlı ultracode turu) bulgularının düzeltmelerini kilitler:
- F2/F7: coop gameplay dispatch DUZ-007 tamamlama — gamepad event'leri
  canonical action metadata + oyuncu çözümlemesiyle eşleşir (gamepad hold
  K_c, coop P1 K_e / P2 K_RSHIFT tuşlarına tesadüfen eşleşemediği için
  hiç çalışmıyordu); klavye remap'i gamepad girdisini düşürmez.
- F4: online_coop ana döngü pompa istisnası (çifte pompa, menu-context
  baseline'ı oyun bağlamı edge'lerini yutuyordu).
- F5: coop_campaign state'i 'game' bağlamına giriyor (RB/LB menü
  aksiyonu üretiyor, hard_drop/hold ölüydü).
- F6: ghost-klavye koruması — tests/test_game_ghost_keyboard_guard.py.
- F8: hotplug SDL renumbering — _scan_gamepads instance_id dedup (aynı
  fiziksel cihaz iki kez kaydedilmiyor; kalan cihaz indeks kaymasıyla
  taşınıyor) + kare-başı Joystick tahsisi engelleme.
- G6: _swallow_next_keydown süre limiti (binding sonrası ilk GERÇEK
  klavye tuşu yutulmuyordu) + game-over legend dict/int güvenliği.

Modül importları gövde içinde (koleksiyon-runtime sys.modules kimlik
bölünmesi dersi — bkz. conftest koleksiyon-sınırı purgeleri).
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest


def _gp_event(action, key, player=None, device=None, etype=pygame.KEYDOWN):
    return types.SimpleNamespace(
        type=etype, key=key, mod=0, from_gamepad=True, action=action,
        device_index=device, gamepad_player=player,
    )


def _kbd_event(key, etype=pygame.KEYDOWN):
    return types.SimpleNamespace(type=etype, key=key, mod=0, unicode='', from_gamepad=False)


# ── F2/F7: dispatch yardımcıları (coop + pvp) ───────────────────────────────

@pytest.mark.parametrize('module_name', ['coop_game', 'pvp_game'])
def test_player_action_matching_contract(module_name):
    """Gamepad event'i action metadata + oyuncudan; klavye tuştan eşleşir."""
    mod = __import__(module_name)
    cls = mod.CoopGame if module_name == 'coop_game' else mod.PvPGame
    game = cls.__new__(cls)
    game.p1_gamepad_idx = None
    game.p2_gamepad_idx = None

    controls = {'hold': pygame.K_e, 'move_left': pygame.K_a, 'rotate': pygame.K_w}
    match = cls._event_matches_player_action

    # Gamepad hold: K_c sentetik tuşu klavye hold tuşuna (K_e) eşleşmez —
    # yalnız action metadata eşleşir. Eski davranışta gamepad hold ölüydü.
    ev_hold_p1 = _gp_event('hold', pygame.K_c, player=1, device=4)
    assert match(ev_hold_p1, controls, 'hold', 1, 1) is True
    assert match(ev_hold_p1, controls, 'hold', 2, 1) is False

    # rotate alias: gamepad 'rotate_alt' → 'rotate' dalı.
    ev_rot = _gp_event('rotate_alt', pygame.K_UP, player=1, device=4)
    assert match(ev_rot, controls, 'rotate', 1, 1, gamepad_aliases=('rotate_alt',)) is True
    assert match(ev_rot, controls, 'rotate_ccw', 1, 1) is False, 'alias yalnız verildiği aksiyon için geçerli'

    # Klavye: yalnız fiziksel tuş; gamepad'in sentetik tuşu klavye gibi
    # eşleşmez (K_c != K_e) — klavye remap'i gamepad'i düşürmez.
    assert match(_kbd_event(pygame.K_e), controls, 'hold', 1, None) is True
    assert match(_kbd_event(pygame.K_c), controls, 'hold', 1, None) is False

    # KEYUP da aynı sözleşmeyle eşleşir (DAS/soft-drop kilitleri temizlenir).
    ev_up = _gp_event('move_left', pygame.K_LEFT, player=1, device=4, etype=pygame.KEYUP)
    assert match(ev_up, controls, 'move_left', 1, 1) is True


@pytest.mark.parametrize('module_name', ['coop_game', 'pvp_game'])
def test_resolve_gamepad_player_defaults_to_legacy_p2(module_name):
    mod = __import__(module_name)
    cls = mod.CoopGame if module_name == 'coop_game' else mod.PvPGame
    game = cls.__new__(cls)
    game.p1_gamepad_idx = None
    game.p2_gamepad_idx = None

    # Atama yok → legacy tek-gamepad davranışı (ok tuşları P2'yi sürer).
    assert game._resolve_gamepad_player(_gp_event('hold', pygame.K_c, device=7)) == 2
    # gamepad_player metadata'sı öncelikli.
    assert game._resolve_gamepad_player(_gp_event('hold', pygame.K_c, player=1, device=7)) == 1
    # device_index atama eşleşmesi.
    game.p1_gamepad_idx = 7
    assert game._resolve_gamepad_player(_gp_event('hold', pygame.K_c, device=7)) == 1
    game.p2_gamepad_idx = 9
    assert game._resolve_gamepad_player(_gp_event('hold', pygame.K_c, device=9)) == 2


def test_ensure_gamepad_player_assignments_two_pads(monkeypatch):
    """İki+ pad bağlıysa bağlanma sırasına göre P1/P2; tek pad atanmaz."""
    import coop_game as cg
    import gamepad_manager as gm

    game = cg.CoopGame.__new__(cg.CoopGame)
    game.p1_gamepad_idx = None
    game.p2_gamepad_idx = None
    fake_gpm = types.SimpleNamespace(gamepads={0: types.SimpleNamespace(instance_id=101), 3: types.SimpleNamespace(instance_id=102)})
    # v2 coop modül-düzeyi import'la bağlar; iç import da aynı kaynağa düşer.
    monkeypatch.setattr(cg, 'get_gamepad_manager', lambda: fake_gpm)
    monkeypatch.setattr(gm, 'get_gamepad_manager', lambda: fake_gpm)

    game._ensure_gamepad_player_assignments()
    assert game.p1_gamepad_idx == 0
    assert game.p2_gamepad_idx == 3
    # İdempotent: ikinci çağrı değiştirmez; tek pad senaryosunda atama yok.
    game._ensure_gamepad_player_assignments()
    assert (game.p1_gamepad_idx, game.p2_gamepad_idx) == (0, 3)
    single = cg.CoopGame.__new__(cg.CoopGame)
    single.p1_gamepad_idx = None
    single.p2_gamepad_idx = None
    single_gpm = types.SimpleNamespace(gamepads={2: types.SimpleNamespace(instance_id=103)})
    monkeypatch.setattr(cg, 'get_gamepad_manager', lambda: single_gpm)
    monkeypatch.setattr(gm, 'get_gamepad_manager', lambda: single_gpm)
    single._ensure_gamepad_player_assignments()
    assert single.p1_gamepad_idx is None and single.p2_gamepad_idx is None


# ── F4/F5: main.py bağlam + pompa sözleşmeleri ──────────────────────────────

def test_main_gamepad_context_and_pump_contracts():
    """coop_campaign 'game' bağlamına girer; online_pvp/online_coop kendi
    pompasını yönetir (ana döngü çifte pompa yapmaz)."""
    src = (ROOT_DIR / 'src' / 'main.py').read_text(encoding='utf-8')
    norm = re.sub(r'\s+', ' ', src)
    assert "elif state in ('game', 'pvp', 'coop', 'coop_campaign'):" in norm
    # Pompa istisnası online_pvp + online_coop: ikisi de KENDİ pompasını
    # yönetir (online_coop self-pump'ı v2 paritesidir — handle_input
    # başında set_context+update). İstisna yapılmasa çifte pompa olurdu.
    assert "if state not in ('online_pvp', 'online_coop'):" in norm
    assert "if state in ('online_pvp', 'online_coop'):" in norm
    # coop_campaign runtime'ı bağlam dalında çözülür.
    assert 'active_runtime = coop_campaign_game' in norm
    # SDL öncesi Steam init (Steam Input geç hazırlanma dayanıklılığı —
    # demo Steam dağıtımında daha da kritik; denetim bulgusu: port edilmemişti).
    assert 'SDL öncesi SDK init' in src


# ── F8: hotplug renumbering dedup + kare-başı Joystick tahsisi ──────────────

class _FakeJoystick:
    def __init__(self, instance):
        self._instance = instance
        self._init = False
        self.opened_count = 0

    def init(self):
        self._init = True

    def get_init(self):
        return self._init

    def get_name(self):
        return 'Fake Pad'

    def get_guid(self):
        return 'fake-guid'

    def quit(self):
        self._init = False

    def get_instance_id(self):
        return self._instance


def test_scan_renumber_moves_entry_without_duplicate(monkeypatch):
    """SDL renumbering: kalan cihaz yeni indekse TAŞINIR — ikinci kayıt
    açılmaz (çift girdi) ve eski anahtar yeni cihaza açık kalır."""
    import gamepad_manager as gm

    manager = gm.GamepadManager.__new__(gm.GamepadManager)
    manager.gamepads = {}
    state_b = gm.GamepadState(instance_id=20, device_index=1)
    state_b.joystick = types.SimpleNamespace(
        get_init=lambda: True, get_name=lambda: 'Pad B', quit=lambda: None,
    )
    manager.gamepads[1] = state_b

    fake_js = _FakeJoystick(20)
    open_calls = []
    monkeypatch.setattr(gm.pygame.joystick, 'get_count', lambda: 1)
    monkeypatch.setattr(
        gm.pygame.joystick, 'Joystick',
        lambda i: (open_calls.append(i), fake_js)[1],
    )

    manager._scan_gamepads()

    assert set(manager.gamepads.keys()) == {0}, 'kayıt yeni anahtara taşınmalı, ikinci kayıt açılmamalı'
    assert manager.gamepads[0] is state_b
    assert manager.gamepads[0].device_index == 0
    assert open_calls == [0]

    # İkinci tarama: canlı slot için yeni Joystick AÇILMAZ (kare-başı
    # tahsis yasağı — CLAUDE.md).
    manager._scan_gamepads()
    assert open_calls == [0], 'canlı slot için Joystick yeniden açılmamalı'


def test_scan_registers_new_device_in_freed_slot(monkeypatch):
    """Renumber sonrası boşalan eski anahtara yeni cihaz kaydedilebilir."""
    import gamepad_manager as gm

    manager = gm.GamepadManager.__new__(gm.GamepadManager)
    manager.gamepads = {0: gm.GamepadState(instance_id=20, device_index=0)}
    manager.gamepads[0].joystick = types.SimpleNamespace(
        get_init=lambda: True, get_name=lambda: 'Pad B', quit=lambda: None,
    )
    registered = []
    monkeypatch.setattr(manager, '_register_gamepad', lambda idx: registered.append(idx) or True)

    fake_new = _FakeJoystick(99)
    monkeypatch.setattr(gm.pygame.joystick, 'get_count', lambda: 2)
    monkeypatch.setattr(
        gm.pygame.joystick, 'Joystick',
        lambda i: manager.gamepads[0].joystick if i == 0 else fake_new,
    )

    manager._scan_gamepads()
    assert registered == [1], 'yeni cihaz boşalan 1 anahtarına kaydedilmeli'


# ── G6: swallow deadline + game-over legend ─────────────────────────────────

def test_swallow_keydown_has_deadline():
    src = (ROOT_DIR / 'src' / 'settings_screen_tabbed.py').read_text(encoding='utf-8')
    assert '_swallow_next_keydown_deadline_ms' in src
    assert src.count('_swallow_next_keydown_deadline_ms = pygame.time.get_ticks() + 600') == 4, (
        'dört set noktasının hepsi süre limiti atamalı'
    )
    # Bayrak atamaları da deadline atamalarıyla eş sayıda olmalı — gelecekte
    # deadlinesız yeni bir bayrak seti eklense test yakalamalı (inceleme bulgusu).
    assert src.count('_swallow_next_keydown = True') == src.count(
        '_swallow_next_keydown_deadline_ms = pygame.time.get_ticks() + 600'
    )
    assert 'pygame.time.get_ticks() > self._swallow_next_keydown_deadline_ms' in src, (
        'süresi dolan bayrak gerçek tuşu yutmamalı'
    )


def test_game_over_legend_survives_dict_binding_format():
    """Game-over legend'ı {'primary': N} dict binding'iyle çökmez — eski
    kod int(dict) TypeError'u sessizce yutup klavye etiketine düşüyordu."""
    src = (ROOT_DIR / 'src' / 'game.py').read_text(encoding='utf-8')
    start = src.index("restart_key = 'R'")
    end = src.index('buttons = [', start)
    block = src[start:end]
    # Modül seviyesindeki güvenli çözümleyici (kare-başı closure yasağı).
    assert '_gp_binding_button_value' in block
    helper = src[src.index('def _gp_binding_button_value'):]
    helper = helper[:helper.index('\ndef ')]
    assert 'isinstance(raw, dict)' in helper
    assert "raw.get('primary', raw.get('button'" in helper


# ── dispatch kullanım sözleşmeleri ───────────────────────────────────────────

def test_handle_input_uses_metadata_dispatch():
    """handle_input gameplay dalları ham event.key yerine metadata
    eşleşmesi kullanır (hold/hard_drop/soft_drop/move dahil; KEYUP'lar da).
    Demo'da hem coop hem pvp helper tabanlıdır (v2 pvp atama-lobisi
    mekanizmasını kullanır; demo'ya lobi bilinçli taşınmadı)."""
    for module_name in ('coop_game', 'pvp_game'):
        src = (ROOT_DIR / 'src' / (module_name + '.py')).read_text(encoding='utf-8')
        assert src.count('_event_matches_player_action(event,') >= 18, (
            module_name + ': P1+P2 KEYDOWN ve KEYUP dallarının tamamı metadata eşleşmesi kullanmalı'
        )
        assert '_resolve_gamepad_player(event) if is_gamepad' in src


# ── demo uyarlamaları: layout v3 (Y-retry) + kayıt device_index ──────────────

def test_layout_v3_restart_and_level_select_defaults():
    """Demo layout v3: restart=Y(3) — game-over'da Y ile yeniden deneme artık
    varsayılanlarda ölü değil (denetim bulgusu: kod yolu hazır bekliyordu,
    ayar default'u -1 onu öldürüyordu); level_select=X(2) level-failed'da."""
    import settings_manager as sm
    gp = sm.DEFAULT_CONTROLS['gamepad']
    assert gp['restart']['primary'] == 3
    assert gp['level_select']['primary'] == 2
    assert sm.CURRENT_GAMEPAD_LAYOUT_VERSION >= 3


def test_layout_v3_migration_moves_unmodified_restart():
    """v2 layout'undaki özelleştirilmemiş restart=-1 → v3 Y(3) taşınır;
    özelleştirilmiş değer ezilmez; level_select yeni eklenir."""
    import settings_manager as sm
    inst = sm.SettingsManager.__new__(sm.SettingsManager)
    gp_existing = {
        'gamepad_layout_version': 2,
        'restart': {'primary': -1, 'secondary': -1},
        'hold': {'primary': 9, 'secondary': -1},
    }
    migrated = inst._migrate_gamepad_block(gp_existing)
    assert migrated['restart'] == {'primary': 3, 'secondary': -1}
    assert migrated['level_select'] == {'primary': 2, 'secondary': -1}
    assert migrated['gamepad_layout_version'] == sm.CURRENT_GAMEPAD_LAYOUT_VERSION
    # Özelleştirilmiş restart ezilmez.
    custom = dict(gp_existing)
    custom['restart'] = {'primary': 7, 'secondary': -1}
    migrated2 = inst._migrate_gamepad_block(custom)
    assert migrated2['restart'] == {'primary': 7, 'secondary': -1}


def test_register_gamepad_state_carries_device_index():
    """Üretim kaydı GamepadState'e device_index atar — routing bunu okur
    (denetim bulgusu: demo kaydı -1 bırakıyordu, event'ler cihazsız kalıyordu).
    PlayStation D-pad debounce (v2 paritesi) de kayıtta atanır."""
    src = (ROOT_DIR / 'src' / 'gamepad_manager.py').read_text(encoding='utf-8')
    start = src.index('def _register_gamepad')
    end = src.index('\ndef ', start + 10)
    block = src[start:end]
    assert 'device_index=device_index,' in block
    assert 'dpad_debounce_time_ms = 60.0' in block


# ── instance-id atama takibi (inceleme düzeltmesi) ───────────────────────────

def test_gamepad_player_assignment_survives_renumber():
    """Bir pad kopunca SDL kalan pad'in indeksini kaydırır; instance_id
    ataması hayatta kalan pad'in OYUNCUSUNU korur (indeks karışması yok)."""
    import coop_game as cg
    import gamepad_manager as gm

    game = cg.CoopGame.__new__(cg.CoopGame)
    game.p1_gamepad_idx = 0
    game.p2_gamepad_idx = 1
    game.p1_gamepad_instance_id = 201
    game.p2_gamepad_instance_id = 202

    # P1'in pedi (instance 201, indeks 0) koptu; kalan ped (202) artık
    # indeks 0'da (SDL renumbering).
    gpm_after = types.SimpleNamespace(gamepads={0: types.SimpleNamespace(instance_id=202)})
    # _resolve: kalan pad'in event'i (device 0) → instance 202 → P2 kalmalı.
    orig_cg = cg.get_gamepad_manager
    orig_gm = gm.get_gamepad_manager
    try:
        cg.get_gamepad_manager = lambda: gpm_after
        gm.get_gamepad_manager = lambda: gpm_after
        ev = types.SimpleNamespace(
            type=pygame.KEYDOWN, key=pygame.K_c, mod=0, from_gamepad=True,
            action='hold', device_index=0, gamepad_player=None,
        )
        assert game._resolve_gamepad_player(ev) == 2, (
            'renumber sonrası hayatta kalan pad oyuncusunu korumalı (P2)'
        )
        # _ensure: kopan instance temizlenmeli (P1 ataması boşalmalı).
        game._ensure_gamepad_player_assignments()
        assert game.p1_gamepad_instance_id is None
        assert game.p1_gamepad_idx is None
        # Kalan pad tek başına → P2 ataması da temizlenmez (instance bağlı):
        assert game.p2_gamepad_instance_id == 202
    finally:
        # HER İKİ modül bağlaması geri konmalı — yalnız cg'yi geri koymak
        # gm.get_gamepad_manager lambdasını sızdırır (sonraki dosyaların
        # get_gamepad_manager() çağrıları SimpleNamespace alırdı).
        cg.get_gamepad_manager = orig_cg
        gm.get_gamepad_manager = orig_gm


def test_poll_only_binding_on_dpad_dir_suppresses_natural_direction():
    """Slot/restart gibi poll-only aksiyon D-pad yön butonuna bağlıysa doğal
    yön bastırılır — aynı buton doğal yönü VE slot poll'unu birlikte
    tetiklememeli (inceleme bulgusu; v2 paritesi)."""
    import gamepad_manager as gm

    manager = gm.GamepadManager.__new__(gm.GamepadManager)
    manager.gamepads = {}
    manager._context = gm.GamepadManager.CONTEXT_GAME
    manager._bindings = {
        'slot_1': {'button': 12},  # D-pad Down'a slot bağlandı
    }
    assert 'down' in manager._get_overridden_dpad_dirs()

    # restart da poll-only: D-pad Up'a bağlanınca 'up' bastırılır.
    # OP-031: _get_overridden_dpad_dirs artık _bindings_rev sözleşmesiyle
    # memoize — doğrudan _bindings ataması sonrası rev bump şart (üretim
    # yolları 644/748 bump'lar; burada test harness'i aynı sözleşmeye uyar).
    manager._bindings = {'restart': {'button': 11}}
    manager._bindings_rev = getattr(manager, '_bindings_rev', 0) + 1
    assert 'up' in manager._get_overridden_dpad_dirs()


def test_resolve_game_button_actions_is_memoized():
    """Çözüm haritası bindings değişmedikçe ÖNBELLEK'Ten döner (kare başına
    3-4 kez yeniden inşanın kapanması; v2 paritesi)."""
    import gamepad_manager as gm

    manager = gm.GamepadManager.__new__(gm.GamepadManager)
    manager.gamepads = {}
    manager._context = gm.GamepadManager.CONTEXT_GAME
    manager._bindings = {'rotate': {'button': 11}, 'hard_drop': {'button': 5}}

    first = manager._resolve_game_button_actions()
    second = manager._resolve_game_button_actions()
    assert first is second, 'aynı bindings → aynı (önbellek) nesne'

    manager._bindings_rev = getattr(manager, '_bindings_rev', 0) + 1
    third = manager._resolve_game_button_actions()
    assert third is not first, 'rev değişince önbellek düşmeli'


def test_is_direction_held_scopes_to_device():
    """is_direction_held(device_index=...) O cihazın durumunu okur (v2
    paritesi) — iki padli oyunda DAS bırakış kontrolü bırakan oyuncunun
    pad'ine bakar."""
    import gamepad_manager as gm

    manager = gm.GamepadManager.__new__(gm.GamepadManager)
    manager.gamepads = {}
    manager._context = gm.GamepadManager.CONTEXT_GAME
    manager._bindings = {}
    fake_js = lambda: types.SimpleNamespace(get_init=lambda: True, get_name=lambda: 'Pad', quit=lambda: None)
    pad_p1 = gm.GamepadState(device_index=0, joystick=fake_js())
    pad_p1.dpad = (1, 0)   # P1 pad'i SAĞI basılı tutuyor
    pad_p1.dpad_debounced_dx = 1  # debounced değerlerden okuma (v2 paritesi)
    pad_p2 = gm.GamepadState(device_index=1, joystick=fake_js())
    pad_p2.dpad = (0, 0)   # P2 pad'i boş
    manager.gamepads = {0: pad_p1, 1: pad_p2}

    assert manager.is_direction_held('right') is True
    assert manager.is_direction_held('right', device_index=1) is False
    assert manager.is_direction_held('right', device_index=0) is True


def test_migration_v1_loop_guarded_for_version2_files():
    """version=2 dosyada v1→v2 döngüsü YENİDEN ÇALIŞMAZ — v1 eski
    default'una denk kullanıcı özelleştirmeleri ezilmez (inceleme bulgusu)."""
    import settings_manager as sm
    inst = sm.SettingsManager.__new__(sm.SettingsManager)
    # hard_drop=3, v1'in eski default'u (kullanıcı bilerek böyle bıraktı).
    gp_existing = {
        'gamepad_layout_version': 2,
        'hard_drop': {'primary': 3, 'secondary': -1},
        'restart': {'primary': -1, 'secondary': -1},
    }
    migrated = inst._migrate_gamepad_block(gp_existing)
    assert migrated['hard_drop'] == {'primary': 3, 'secondary': -1}, (
        'version=2 dosyada v1→v2 döngüsü custom değeri ezmemeli'
    )
    # v2→v3 adımı yine çalışır.
    assert migrated['restart'] == {'primary': 3, 'secondary': -1}


def test_load_settings_bumps_bindings_rev():
    """R2 inceleme bulgusu (v2): _load_settings bindings'i yeniden atarken
    rev bump YAPMALI — yoksa ayar ekranından rebind uygulandığında memoize
    çözüm haritası bayat kalır (yeni atama yeniden başlatana kadar etkin
    olmaz). Kaynak sözleşmesi: deepcopy atamasını rev bump izlemeli."""
    src = (ROOT_DIR / 'src' / 'gamepad_manager.py').read_text(encoding='utf-8')
    start = src.index('def _load_settings')
    end = src.index('\n    def ', start + 10)
    body = src[start:end]
    assign_pos = body.index('self._bindings = copy.deepcopy(DEFAULT_GAMEPAD_BINDINGS)')
    after = body[assign_pos:assign_pos + 800]
    assert '_bindings_rev' in after.split('def ')[0], (
        '_load_settings deepcopy atamasını rev bump izlemeli'
    )


def test_renumber_refreshes_gamepad_idx_for_rumble():
    """idx senkronu: instance hayatta kalıp yeni indekse taşındıysa
    p*_gamepad_idx tazelenir — rumble hedefleri idx üzerinden okunur."""
    import coop_game as cg
    import gamepad_manager as gm
    import types as _t

    game = cg.CoopGame.__new__(cg.CoopGame)
    game.p1_gamepad_idx = 0
    game.p2_gamepad_idx = 1
    game.p1_gamepad_instance_id = 201
    game.p2_gamepad_instance_id = 202
    # P1 koptu; P2'nin pedi (202) 1'den 0'a taşındı.
    gpm_after = _t.SimpleNamespace(gamepads={0: _t.SimpleNamespace(instance_id=202)})
    orig_cg, orig_gm = cg.get_gamepad_manager, gm.get_gamepad_manager
    try:
        cg.get_gamepad_manager = lambda: gpm_after
        gm.get_gamepad_manager = lambda: gpm_after
        game._ensure_gamepad_player_assignments()
        assert game.p2_gamepad_idx == 0, 'hayatta kalan pad yeni indekse senkron olmali'
        assert game.p2_gamepad_instance_id == 202
    finally:
        cg.get_gamepad_manager = orig_cg
        gm.get_gamepad_manager = orig_gm


def test_v1_layout_file_still_migrates_to_v2():
    """version=1 dosyada v1→v2 döngüsü ÇALIŞMALI (version<2 koruması yalnız
    version=2+ dosyaları korur — v1 yolu kapanmamalı)."""
    import settings_manager as sm
    inst = sm.SettingsManager.__new__(sm.SettingsManager)
    gp_existing = {
        'gamepad_layout_version': 1,
        # v1 default'ları (özelleştirilmemiş):
        'slot_1': {'primary': 9, 'secondary': -1},
        'hard_drop': {'primary': 3, 'secondary': -1},
        'hold2': {'primary': 2, 'secondary': -1},
        'restart': {'primary': -1, 'secondary': -1},
    }
    migrated = inst._migrate_gamepad_block(gp_existing)
    assert migrated['slot_1']['primary'] == 0, 'v1 LB(9) → v2 A(0)'
    assert migrated['hard_drop']['primary'] == 10, 'v1 Y(3) → v2 RB(10)'
    assert migrated['hold2']['primary'] == 8, 'v1 X(2) → v2 R3(8)'
    # v2→v3 adımı da çalışır.
    assert migrated['restart']['primary'] == 3
    assert migrated['gamepad_layout_version'] == sm.CURRENT_GAMEPAD_LAYOUT_VERSION


def test_online_coop_self_pump_contract():
    """online_coop handle_input kendi gamepad pompasını yönetir (v2 paritesi):
    PLAYING'de 'game', aksi halde 'menu' bağlamı + update(delta) + dönen
    sentetik eventlerin ana döngüye karışması. Blok silinirse ana döngü
    pompa istisnası yüzünden gamepad girdisi tamamen ölürdü (R2 inceleme
    bulgusunun kapanışı)."""
    src = (ROOT_DIR / 'src' / 'online_coop_game.py').read_text(encoding='utf-8')
    assert "self.gamepad = _get_gpm()" in src or "self.gamepad = _get_gamepad_manager()" in src, (
        '__init__ gamepad bağlantısı olmalı'
    )
    assert "online_state == OnlineCoopState.PLAYING" in src
    assert "_gamepad.set_context('game')" in src
    assert "_gamepad.set_context('menu')" in src
    assert "gamepad_events = _gamepad.update(delta)" in src
    assert "list(pygame.event.get()) + gamepad_events" in src


# ── game-over / level-fail gamepad tüketim sözleşmeleri ─────────────────────

def test_campaign_level_fail_polls_restart_and_level_select():
    """Solo campaign level-fail/complete ekranı Y(restart)/X(level_select)
    poll-only aksiyonlarını okur — blok silinirse gamepad tamamen ölür ve
    paket yeşil kalırdı (kapsam eleştirmeni boşluğu)."""
    src = (ROOT_DIR / 'src' / 'campaign' / 'campaign_mode.py').read_text(encoding='utf-8')
    hi = src.index('def handle_input')
    body = src[hi:src.index('\n    def ', hi + 10)]
    assert "was_action_just_pressed('level_select')" in body
    assert "was_action_just_pressed('restart')" in body
    # Poll tetiklendiğinde sentetik sızıntı tüketilir.
    assert 'pygame.event.clear' in body


def test_coop_campaign_level_fail_gamepad_paths():
    """Coop campaign level-fail: Y/X poll bloğu + A/ENTER ileri-aksiyon dalı
    (demo'da ENTER dalı 2026-10-04 port edildi; v2 doğuştan sahip)."""
    src = (ROOT_DIR / 'src' / 'campaign' / 'coop_campaign_mode.py').read_text(encoding='utf-8')
    hi = src.index('def handle_input')
    body = src[hi:src.index('\n    def ', hi + 10)]
    assert "was_action_just_pressed('restart')" in body
    # A/ENTER ileri aksiyon: failed'da retry, complete'te sonraki level.
    enter_branch = src[src.index("if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)"):]
    enter_branch = enter_branch[:enter_branch.index('\n                    #')]
    assert 'self._restart_level()' in enter_branch
    assert "'next_level'" in enter_branch
