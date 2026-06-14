from __future__ import annotations

from localization import get_text


def test_demo_prompt_localization_keys_exist_in_turkish() -> None:
    assert get_text('demo_prompt_title') == 'Demo Sınırı'
    assert get_text('demo_open_steam') == "Steam'de Aç"
    assert get_text('demo_back_to_menu') == 'Menüye Dön'
    assert get_text('locked_badge') == 'Kilitli'
    assert get_text('demo_score_cap_title') == 'Demo Tamamlandı'
    assert get_text('demo_score_cap_message') == 'Oynadığınız için teşekkürler, daha fazlası için tam sürümü bekleyin.'
    assert get_text('demo_full_lock_message') == 'Bu mod tam sürümde mevcut.'
    assert get_text('demo_partial_lock_message') == 'Demo bu bölümün yalnızca ilk aşamalarını içerir. Devamını tam sürümde oyna.'
    assert get_text('demo_transition_lock_message') == 'Çevrimiçi modlar tam sürümde mevcut.'
    assert get_text('demo_store_lock_message') == 'Mağaza vitrini ve satın alma akışı tam sürümde açılır.'
    assert get_text('demo_close') == 'Kapat'