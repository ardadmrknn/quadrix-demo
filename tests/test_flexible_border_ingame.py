"""Manuel oyun içi doğrulama adımları (pytest için skip)."""

import pytest


@pytest.mark.skip(reason="Manuel oyun içi doğrulama; otomatik pytest kapsamında çalıştırılmaz.")
def test_flexible_border_manual_ingame_checklist():
	pass
