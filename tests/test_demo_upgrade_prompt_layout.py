from __future__ import annotations

import pytest

from demo_upgrade_prompt import (
    DemoUpgradePrompt,
    show_demo_full_lock_prompt,
    show_demo_partial_lock_prompt,
    show_demo_score_cap_prompt,
    show_demo_transition_lock_prompt,
)


class _FakeScreen:
    def __init__(self, width: int, height: int):
        self._size = (width, height)

    def get_size(self) -> tuple[int, int]:
        return self._size


class _MetricFont:
    def __init__(self, char_width: int, height: int):
        self._char_width = int(char_width)
        self._height = int(height)

    def size(self, text: str) -> tuple[int, int]:
        return max(1, len(str(text or '')) * self._char_width), self._height

    def get_height(self) -> int:
        return self._height


def test_demo_prompt_layout_expands_for_taller_body_fonts() -> None:
    message = (
        'Demo bu bölümün yalnızca ilk aşamalarını içerir. Devamını tam sürümde oyna. '
        'Demo bu bölümün yalnızca ilk aşamalarını içerir. Devamını tam sürümde oyna. '
        'Demo bu bölümün yalnızca ilk aşamalarını içerir. Devamını tam sürümde oyna.'
    )
    prompt = DemoUpgradePrompt(_FakeScreen(1366, 768))
    prompt.show(
        title='Demo Sınırı',
        message=message,
        confirm_label="Steam'de Aç",
        cancel_label='Kapat',
    )

    title_font = _MetricFont(char_width=14, height=30)
    compact_body_font = _MetricFont(char_width=8, height=18)
    tall_body_font = _MetricFont(char_width=8, height=34)

    compact_layout = prompt._build_layout((1366, 768), 1.0, title_font, compact_body_font)
    tall_layout = prompt._build_layout((1366, 768), 1.0, title_font, tall_body_font)

    assert tall_layout.panel_rect.height > compact_layout.panel_rect.height
    assert tall_layout.confirm_rect.y > compact_layout.confirm_rect.y
    assert tall_layout.body_rect.bottom < tall_layout.confirm_rect.top
    assert tall_layout.confirm_rect.bottom <= tall_layout.panel_rect.bottom
    assert tall_layout.cancel_rect.bottom <= tall_layout.panel_rect.bottom


def test_demo_prompt_wrap_text_preserves_manual_line_breaks() -> None:
    font = _MetricFont(char_width=9, height=20)
    lines = DemoUpgradePrompt._wrap_text(font, 'Ilk satir\nIkinci satir burada', 120)

    assert lines[0] == 'Ilk satir'
    assert lines[1].startswith('Ikinci satir')


@pytest.mark.parametrize(
    'show_prompt',
    [
        show_demo_full_lock_prompt,
        show_demo_partial_lock_prompt,
        show_demo_transition_lock_prompt,
        show_demo_score_cap_prompt,
    ],
)
@pytest.mark.parametrize('screen_size, scale', [((1366, 768), 1.0), ((2560, 1600), 1.18)])
def test_all_demo_prompt_variants_keep_layout_separated(show_prompt, screen_size, scale: float) -> None:
    prompt = DemoUpgradePrompt(_FakeScreen(*screen_size))
    show_prompt(prompt)

    title_font = _MetricFont(char_width=14, height=30)
    tall_body_font = _MetricFont(char_width=8, height=34)
    layout = prompt._build_layout(screen_size, scale, title_font, tall_body_font)

    assert layout.title_rect.top >= layout.panel_rect.top
    assert layout.body_rect.top >= layout.title_rect.bottom
    assert layout.body_rect.bottom < layout.confirm_rect.top
    assert layout.confirm_rect.bottom <= layout.panel_rect.bottom
    assert layout.cancel_rect.bottom <= layout.panel_rect.bottom
    assert layout.confirm_rect.left >= layout.panel_rect.left
    assert layout.cancel_rect.right <= layout.panel_rect.right


def test_demo_prompt_layout_keeps_scale_growth() -> None:
    prompt = DemoUpgradePrompt(_FakeScreen(1366, 768))
    show_demo_partial_lock_prompt(prompt)

    title_font = _MetricFont(char_width=14, height=30)
    body_font = _MetricFont(char_width=8, height=22)

    base_layout = prompt._build_layout((1366, 768), 1.0, title_font, body_font)
    large_layout = prompt._build_layout((2560, 1600), 1.18, title_font, body_font)

    assert large_layout.panel_rect.width > base_layout.panel_rect.width
    assert large_layout.panel_rect.height > base_layout.panel_rect.height
    assert large_layout.confirm_rect.width > base_layout.confirm_rect.width