# -*- coding: utf-8 -*-
"""text_cache'in kalıtılamaz (stub) pygame.font.Font'a dayanıklılığı.

Kök neden (2026-10-09, VDS): text_cache modül seviyesinde
``class PatchedFont(pygame.font.Font)`` türetir; guard yalnız Font'un
VARLIĞINI (hasattr) denetliyordu. ``Font=lambda *a, **kw: ...`` kalıbıyla
pygame stub'layan test dosyalarında (test_extras_*) lambda tabanını
kalıtmak ``TypeError: function() argument 'code' must be code, not
str`` üretir; hata modül importunda — pytest KOLEKSİYON aşamasında —
fırlar ve koşumun tamamını keser ("Interrupted: 1 error during
collection" — test_extras_back_button / test_extras_includes_classic).

Sözleşme: Font mevcut ama sınıf değilse PatchedFont sade fallback
sınıfına düşmeli; modül importu asla TypeError ile düşmemeli. Üretimde
gerçek pygame.font.Font bir sınıftır — fallback yolu asla çalışmaz.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types


ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'


def _exec_text_cache_with_stub_pygame(monkeypatch):
    stub_pygame = types.ModuleType('pygame')
    stub_pygame.font = types.SimpleNamespace(Font=lambda *a, **kw: None)

    class _StubSurface:
        def __init__(self, *args, **kwargs):
            pass

    stub_pygame.Surface = _StubSurface

    monkeypatch.setitem(sys.modules, 'pygame', stub_pygame)
    monkeypatch.setitem(sys.modules, 'pygame.font', stub_pygame.font)

    spec = importlib.util.spec_from_file_location(
        'text_cache_stub_font_probe', SRC / 'text_cache.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # koleksiyon eşdeğeri: burada patlamamalı
    return mod


def test_text_cache_import_tolerates_nonclass_font(monkeypatch):
    mod = _exec_text_cache_with_stub_pygame(monkeypatch)
    assert isinstance(mod.PatchedFont, type), (
        'PatchedFont sınıf olarak tanımlı kalmalı (fallback yolu); '
        'kalıtılamaz Font importu TypeError ile düşürmemeli'
    )


def test_text_cache_fallback_does_not_claim_stub_font(monkeypatch):
    """Fallback yolunda stub'un Font'u ezilmemeli:PatchedFont ataması
    yalnız gerçek subclass türetildiğinde yapılır."""
    mod = _exec_text_cache_with_stub_pygame(monkeypatch)
    stub_font = sys.modules['pygame'].font.Font
    assert stub_font is not mod.PatchedFont, (
        'kalıtılamaz Font ortamında pygame.font.Font referansı '
        'fallback sınıfıyla ezilmemeli'
    )
