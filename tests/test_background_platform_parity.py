from __future__ import annotations

import background as background_module


class _FakeImage:
    def __init__(self, *, alpha_value=None):
        self._alpha_value = alpha_value
        self.convert_calls = 0
        self.convert_alpha_calls = 0

    def get_alpha(self):
        return self._alpha_value

    def convert(self):
        self.convert_calls += 1
        return self

    def convert_alpha(self):
        self.convert_alpha_calls += 1
        return self


def test_cached_background_image_tries_display_conversion_on_macos(monkeypatch):
    image = _FakeImage(alpha_value=None)

    background_module._BACKGROUND_IMAGE_CACHE.clear()
    monkeypatch.setattr(background_module, 'load_image', lambda *_args, **_kwargs: image)
    monkeypatch.setattr(background_module.pygame.display, 'get_surface', lambda: object())

    result = background_module._get_cached_background_image('/tmp/fake-bg.png')

    assert result is image
    assert image.convert_calls == 1
    assert image.convert_alpha_calls == 0
