"""
Birim testleri: FocusThrottlePolicy ve düşük güç modu davranışları.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from platform_utils import FocusThrottlePolicy


class TestFocusThrottlePolicy(unittest.TestCase):
    """Odak kaybı throttle ve delta clamp testleri."""

    def setUp(self):
        self.policy = FocusThrottlePolicy(inactive_fps=15, debounce_ms=150, max_resume_delta_ms=50.0)

    def test_active_window_not_throttled(self):
        """Aktif pencerede throttle uygulanmamalı ve orijinal hedef FPS korunmalıdır."""
        self.policy.update_active_state(True, now_ms=1000)
        self.assertFalse(self.policy.is_throttled(state='game', now_ms=1050))
        self.assertEqual(self.policy.resolve_frame_cap(144, state='game', now_ms=1050), 144)

    def test_transient_inactive_debounced(self):
        """Kısa süreli (transient, <150ms) inaktiflik anında debounce nedeniyle throttle uygulanmamalıdır."""
        self.policy.update_active_state(False, now_ms=1000)
        # 80ms sonra kontrol: henüz 150ms dolmadı
        self.assertFalse(self.policy.is_throttled(state='game', now_ms=1080))
        self.assertEqual(self.policy.resolve_frame_cap(60, state='game', now_ms=1080), 60)

    def test_sustained_inactive_throttled_to_low_fps(self):
        """Debounce süresi (150ms) aşıldığında inaktif pencere düşük FPS tavanına düşürülmelidir."""
        self.policy.update_active_state(False, now_ms=1000)
        # 200ms sonra kontrol: debounce aşıldı
        self.assertTrue(self.policy.is_throttled(state='game', now_ms=1200))
        self.assertEqual(self.policy.resolve_frame_cap(144, state='game', now_ms=1200), 15)

    def test_resume_clamps_delta_ms(self):
        """Odak geri kazanıldığında ilk karedeki simülasyon sıçraması clamp edilmelidir."""
        # 1. Uzun süreli odak kaybı simüle et
        self.policy.update_active_state(False, now_ms=1000)
        self.assertEqual(self.policy.resolve_frame_cap(144, state='game', now_ms=1500), 15)

        # 2. Odak geri geldi (resume)
        self.policy.update_active_state(True, now_ms=3000)
        # Normal şartlarda 3000-1500 = 1500ms delta gelirdi; bu clamp edilmeli:
        first_delta = self.policy.filter_delta_ms(1500.0)
        self.assertEqual(first_delta, 50.0, "Resume sırasındaki ilk delta max_resume_delta_ms'e sınırlandırılmalı")

        # 3. İkinci karede normal akış devam etmeli:
        second_delta = self.policy.filter_delta_ms(16.6)
        self.assertEqual(second_delta, 16.6, "Sonraki karelerde delta clamp uygulanmamalı")


if __name__ == '__main__':
    unittest.main()
