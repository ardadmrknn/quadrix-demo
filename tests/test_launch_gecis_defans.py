# -*- coding: utf-8 -*-
"""Geçiş desenkronu A+C2 sözleşmesi — demo portu (v2 621aabd ile aynı mekanizma).

Kullanıcı raporu: menü/extras'tan oyuna geçişte wipe perdesi "geç geliyor",
oyun perde arkasında zaten akıyormuş gibi açılıp kapanıyor. Kök neden
(telemetri kanıtı: slow_handler 933.4 ms extras→game, 935.0 ms
menu→online_pvp): kurulum tıklama karesinde, perde BAŞLAMADAN koşuyor →
~935 ms donuk menü + perde boyunca perde arkasında canlı oyun.

A: kurulum `_launch_game_via_wipe` ile perdenin tam kapandığı ana (callback)
ertelenir; state orada değişir → oyun tam görünür anda başlar. Tıklama
karesinde yalnız perde kapanmaya başlar (anında görsel geri bildirim).
C2: `update()` callback'ten SONRA açılış saatini taze damgalar — kurulum
süresi açılış fazını duvar-saatiyle yutamaz (pop-in yerine yumuşak açılış).
Demo perde ritmi v2'den farklıdır (toplam 350 ms, campaign 450 ms); helper
demo'nun doğal 350 ms varsayılanıyla başlatır. Coop bu dalgada bilinçli
olarak dokunulmaz (kendi açılış perdesini çizer; main.py:5364 yorumu);
state değiştirmeyen next-level akışları da perde oynamadığı için kapsam
dışındadır.
"""
from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pygame  # noqa: E402
import pytest  # noqa: E402

import background_effects as be  # noqa: E402

MAIN_SRC = (SRC_DIR / 'main.py').read_text(encoding='utf-8')

# Wipe perdesinin oynadığı tüm kurulum noktaları (menu 11, guide 2, extras 13,
# user_selection 1, campaign_select 1, coop_campaign_select 1 — coop ve
# state-değiştirmeyen next-level blokları hariç).
EXPECTED_LAUNCH_SITES = 29


@pytest.fixture(autouse=True)
def _gecisi_temizle():
    """Global geçiş instance'ını testler arası izole et."""
    be._screen_transition = None
    yield
    be._screen_transition = None


def _saat_kur(monkeypatch):
    """pygame.time.get_ticks'i kontrollü saate bağla (duvar-saati testi).

    Tam süitte purge denen testler pygame'i sys.modules'ten söküp yeniden
    ithal edebildiğinden background_effects'in kendi pygame referansı bu
    test modülünün pygame'inden farklı nesne olabilir — ikisini de yamala.
    """
    saat = {'t': 1000}

    def fake():
        return saat['t']

    monkeypatch.setattr(pygame.time, 'get_ticks', fake)
    be_pygame_time = getattr(getattr(be, 'pygame', None), 'time', None)
    if be_pygame_time is not None and be_pygame_time is not pygame.time:
        try:
            monkeypatch.setattr(be_pygame_time, 'get_ticks', fake)
        except Exception:
            pass
    return saat


# --- C2: callback sonrası açılış saati taze damgalanır ---------------------


def test_wipe_callback_sonrasi_acilis_saati_taze_damgalanir(monkeypatch):
    """C2: kurulum 933 ms sürse de açılış fazı 0'dan başlar.

    Eski davranışta saat flip ANINDA damgalanıyordu; kurulum süresi açılış
    fazını yutuyor, perde tek karede yutuluyordu (pop-in).
    """
    pygame.init()
    saat = _saat_kur(monkeypatch)
    screen = pygame.Surface((160, 120))

    calisti = []

    def yavas_kurulum():
        calisti.append(saat['t'])
        saat['t'] += 933  # ölçülen kurulum karesi (933.4 ms)

    be.start_screen_transition(screen, yavas_kurulum, duration_ms=1000, transition_type='wipe')

    saat['t'] += 510  # kapanış (out) fazı tamamlandı
    assert be.update_screen_transition() is True
    assert calisti == [1510]  # tam kapanış anında, perde kapalıyken

    tr = be._screen_transition
    assert tr.phase == 'in'
    # C2: saat kurulumdan SONRA damgalanmalı (eski: min(1, 943/500) = 1.0).
    assert tr.progress == 0.0


def test_wipe_callback_sonrasi_acilis_yumusak_ilerler(monkeypatch):
    """C2: kurulum sonrası açılış tüm in-fazı boyunca yumuşak ilerler."""
    pygame.init()
    saat = _saat_kur(monkeypatch)
    screen = pygame.Surface((160, 120))

    def yavas_kurulum():
        saat['t'] += 933

    be.start_screen_transition(screen, yavas_kurulum, duration_ms=1000, transition_type='wipe')
    saat['t'] += 510
    be.update_screen_transition()  # flip + kurulum

    tr = be._screen_transition
    saat['t'] += 100
    be.update_screen_transition()
    assert abs(tr.progress - 0.2) < 1e-9  # 100/500 — yumuşak açılış

    saat['t'] += 400
    assert be.update_screen_transition() is False  # 500 ms dolunca biter
    assert tr.progress == 1.0


def test_wipe_callback_yok_tek_fazli_yasam_dongusu(monkeypatch):
    """Callback'siz wipe demo'da tek fazlıdır (perde anında kapalı başlar,
    yalnız açılır); 1000 ms'de tamamlanır, capture hiç alınmaz."""
    pygame.init()
    saat = _saat_kur(monkeypatch)
    screen = pygame.Surface((160, 120))

    be.start_screen_transition(screen, None, duration_ms=1000, transition_type='wipe')
    assert be.is_screen_transition_active()

    saat['t'] += 520
    assert be.update_screen_transition() is True
    assert be._screen_transition.phase == 'in'
    assert not be._screen_transition._two_phase_transition

    saat['t'] += 500
    assert be.update_screen_transition() is False
    assert not be.is_screen_transition_active()
    assert be._screen_transition._old_screen_capture is None  # capture yok


# --- İptal yolu: kurulum hatasında perde açık kalmasın ---------------------


def test_cancel_screen_transition_aktif_gecisi_derhal_keser(monkeypatch):
    """Kurulum hatası yolu: aktif perde derhal kesilir, capture serbest kalır."""
    pygame.init()
    _saat_kur(monkeypatch)
    screen = pygame.Surface((160, 120))

    be.start_screen_transition(screen, None, duration_ms=1000, transition_type='wipe')
    assert be.is_screen_transition_active()

    be.cancel_screen_transition()

    assert not be.is_screen_transition_active()
    assert be.update_screen_transition() is False
    assert be._screen_transition._old_screen_capture is None


def test_cancel_bekleyen_callbacki_dusurur(monkeypatch):
    """İptal sonrası bekleyen kurulum callback'i bir daha tetiklenmez."""
    pygame.init()
    saat = _saat_kur(monkeypatch)
    screen = pygame.Surface((160, 120))

    calisti = []
    be.start_screen_transition(screen, lambda: calisti.append(1), duration_ms=1000, transition_type='wipe')

    be.cancel_screen_transition()
    saat['t'] += 2000  # out fazı çoktan geçecek kadar ilerlet
    be.update_screen_transition()
    be.update_screen_transition()

    assert calisti == []


# --- A: kaynak sözleşmeleri (main.py) ---------------------------------------


def test_launch_helper_tanimli_ve_guvenli():
    """`_launch_game_via_wipe`: çift-launch koruması + hata yolu + wipe."""
    assert 'def _launch_game_via_wipe(' in MAIN_SRC
    # Çift-launch koruması (perde sürerken ikinci launch yutulur).
    assert 'if is_screen_transition_active():' in MAIN_SRC
    # Hata yolu: kurulum patlarsa perde iptal edilir, state değişmez.
    assert MAIN_SRC.count('cancel_screen_transition') >= 3  # 2 import bloğu + çağrı
    # Yardımcı daima iki fazlı wipe başlatır (demo ritmi: 175+175 ms).
    assert "transition_type='wipe'" in MAIN_SRC


def test_launch_siteleri_helper_ile_ertelenmis():
    """Wipe oynayan 29 kurulum noktası helper callback'ine taşınmış."""
    adet = MAIN_SRC.count('_launch_game_via_wipe(_launch')
    assert adet == EXPECTED_LAUNCH_SITES, (
        f'ertelemeli launch sayısı {adet} != beklenen {EXPECTED_LAUNCH_SITES} '
        '(yeni mod eklendiyse sayıyı ve bu testi birlikte güncelle)'
    )


def test_campaign_select_launch_kisa_sure_korunur():
    """Campaign select geçişi 450 ms kısa perde ritmini korur."""
    assert MAIN_SRC.count('_launch_game_via_wipe(_launch, duration_ms=450)') == 1


def test_algilama_bloku_perde_sirasinda_kitabi_gunceller():
    """Çift-geçiş bug'ı kapanır: perde sürerken state değişse bile kitap
    güncellenir; perde bitince İKİNCİ perde oynatılmaz."""
    assert 'state != _previous_state and not transition_active' not in MAIN_SRC
    assert 'if state != _previous_state:' in MAIN_SRC


def test_launch_telemetri_damgalari_callback_ici_kalir():
    """PERF-01 launch damgaları korunur (atıf: ÇAĞRI-ANDAKİ state)."""
    for faz in ('launch_game_ms', 'launch_pvp_ms', 'launch_online_pvp_ms', 'launch_online_coop_ms'):
        assert f'record_slow_phase(state, \'{faz}\'' in MAIN_SRC, faz


def test_coop_kendi_perdesinde_dokunulmaz_kalir():
    """Coop kendi açılış perdesini çizer; launch helper'a taşınmaz."""
    idx = MAIN_SRC.find('coop_game = CoopGame(')
    assert idx != -1
    pencere = MAIN_SRC[idx:idx + 700]
    assert "_launch_game_via_wipe" not in pencere
    assert "state = 'coop'" in pencere
