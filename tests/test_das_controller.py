"""DasController (paylaşılan DAS çekirdeği) birim testleri.

Bu testler tek oyunculu, PvP ve co-op modlarının artık ortak kullandığı
``src/das_controller.py`` davranışını doğrular. Özellikle ``game.py``'nin olgun
algoritmasından gelen üç kritik garantiyi korur:

A) Şarj frame'inde delta_time çift sayılmamalı (erken tekrar olmamalı).
B) İlk otomatik tekrar tam repeat aralığı sonra düşmeli.
C) Aynı anda her iki tuş: biri bırakılınca karşı yöne geçiş.
"""
import pathlib
import sys

ROOT_DIR = pathlib.Path(__file__).parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from das_controller import DasController  # noqa: E402


def _mover(moves):
    return lambda direction: (moves.append(direction) or True)


def test_charge_frame_does_not_trigger_premature_repeat():
    das = DasController()
    moves = []
    das.start(1)
    # 200ms gecikme + 10ms overshoot -> tek frame'de şarj.
    das.update(210.0, _mover(moves), delay_ms=200, repeat_ms=200)
    assert moves == [1]
    assert abs(das.repeat_timer - 10.0) < 1e-6


def test_first_repeat_lands_after_full_repeat_interval():
    das = DasController()
    moves = []
    das.start(1)
    das.update(210.0, _mover(moves), delay_ms=200, repeat_ms=200)  # şarj
    assert moves == [1]
    das.update(190.0, _mover(moves), delay_ms=200, repeat_ms=200)  # 10+190=200
    assert moves == [1, 1]


def test_no_move_before_delay():
    das = DasController()
    moves = []
    das.start(-1)
    das.update(150.0, _mover(moves), delay_ms=200, repeat_ms=200)
    assert moves == []
    assert not das.charged


def test_arr_zero_teleports_to_wall_after_charge():
    das = DasController()
    moves = []
    das.start(1)
    # repeat=0: şarj olunca duvara kadar (perform_move False dönene dek) git.
    # Burada 3 hareketten sonra dur.
    calls = {'n': 0}

    def mover(direction):
        calls['n'] += 1
        return calls['n'] <= 3

    das.update(200.0, mover, delay_ms=200, repeat_ms=0)
    # 3 başarılı + 1 başarısız (durduran) = 4 çağrı
    assert calls['n'] == 4


def test_arr_zero_has_safety_bound_for_broken_success_callback():
    das = DasController()
    calls = {'n': 0}

    def always_success(direction):
        calls['n'] += 1
        return True

    das.start(1)
    das.update(200.0, always_success, delay_ms=200, repeat_ms=0)
    assert calls['n'] == 256


def test_catch_up_on_frame_drop():
    das = DasController()
    moves = []
    das.start(1)
    das.update(200.0, _mover(moves), delay_ms=200, repeat_ms=50)  # şarj, overshoot 0
    assert moves == [1]
    # 170ms'lik büyük bir frame: 170/50 = 3 tam tekrar yakalanmalı.
    das.update(170.0, _mover(moves), delay_ms=200, repeat_ms=50)
    assert moves == [1, 1, 1, 1]


def test_repeat_stops_at_wall():
    das = DasController()
    das.start(1)
    das.update(200.0, lambda d: True, delay_ms=200, repeat_ms=50)  # şarj
    # Duvara takıl: ilk tekrar False -> repeat_timer sıfırlanır.
    calls = {'n': 0}
    das.update(200.0, lambda d: (calls.__setitem__('n', calls['n'] + 1), False)[1],
               delay_ms=200, repeat_ms=50)
    assert calls['n'] == 1
    assert das.repeat_timer == 0.0


def test_release_switches_to_other_direction_when_held():
    das = DasController()
    das.start(1)  # sağa
    new_dir = das.release(1, other_still_held=True)
    assert new_dir == -1
    assert das.direction == -1


def test_release_stops_when_other_not_held():
    das = DasController()
    das.start(-1)
    new_dir = das.release(-1, other_still_held=False)
    assert new_dir == 0
    assert das.direction == 0
    assert not das.charged


def test_release_ignores_stale_opposite_keyup():
    # Aktif yön sağ iken, sol tuşun (zaten aktif olmayan) KEYUP'ı yön bozmamalı.
    das = DasController()
    das.start(1)
    new_dir = das.release(-1, other_still_held=False)
    assert new_dir == 0
    assert das.direction == 1  # sağ korunur


def test_start_preserves_charge_when_not_cancelling():
    das = DasController()
    das.start(1)
    das.update(250.0, lambda d: True, delay_ms=200, repeat_ms=200)
    assert das.charged
    # Yön değişiminde cancel kapalı -> şarj korunur (anında hızlı DAS).
    das.start(-1, cancel_das=False)
    assert das.charged
    assert das.direction == -1


def test_start_resets_charge_when_cancelling():
    das = DasController()
    das.start(1)
    das.update(250.0, lambda d: True, delay_ms=200, repeat_ms=200)
    assert das.charged
    das.start(-1, cancel_das=True)
    assert not das.charged
    assert das.timer == 0.0


def test_reset_clears_all_state():
    das = DasController()
    das.start(1)
    das.update(250.0, lambda d: True, delay_ms=200, repeat_ms=200)
    das.reset()
    assert das.direction == 0
    assert das.timer == 0.0
    assert das.repeat_timer == 0.0
    assert not das.charged


def test_two_controllers_are_independent():
    """Co-op/PvP'de P1 ve P2 ayrı kontrolör kullanır. Birinde yapılan release,
    diğerinin state'ini bozmamalı (eski elle-kopya kodda P2 release'i yanlışlıkla
    P1 sayaçlarını sıfırlayan bir kopya-yapıştır bug'ı vardı)."""
    p1 = DasController()
    p2 = DasController()

    # Her iki oyuncu da şarj olmuş durumda sağa gidiyor.
    p1.start(1)
    p2.start(1)
    p1.update(250.0, lambda d: True, delay_ms=200, repeat_ms=200)
    p2.update(250.0, lambda d: True, delay_ms=200, repeat_ms=200)
    assert p1.charged and p2.charged

    # P2 yön değiştiriyor (cancel açık): yalnızca P2 sıfırlanmalı.
    p2.release(1, other_still_held=True, cancel_das=True)
    assert p2.direction == -1
    assert not p2.charged
    assert p2.timer == 0.0
    # P1 hiç etkilenmemeli.
    assert p1.direction == 1
    assert p1.charged

