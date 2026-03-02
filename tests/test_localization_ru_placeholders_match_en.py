"""localization.py — RU çevirilerindeki placeholder'lar EN ile eşleşmeli."""
import os, sys, re

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Önceki test tarafından stub olarak yerleştirilen localization'ı temizle
if 'localization' in sys.modules and not hasattr(sys.modules['localization'], 'TRANSLATIONS'):
    del sys.modules['localization']

from localization import TRANSLATIONS, SUPPORTED_LANGUAGES

PH_RE = re.compile(r'\{(\w+)\}')

# Kasıtlı farklı olabilecek anahtarlar (allowlist - tercihen boş)
PLACEHOLDER_ALLOWLIST = set()


def test_ru_placeholders_match_en():
    errors = []
    for key, trans in TRANSLATIONS.items():
        if key in PLACEHOLDER_ALLOWLIST:
            continue
        en_val = trans.get('en', '')
        ru_val = trans.get('ru', '')
        if not en_val or not ru_val:
            continue
        en_ph = set(PH_RE.findall(en_val))
        ru_ph = set(PH_RE.findall(ru_val))
        if en_ph != ru_ph:
            errors.append(f"  [{key}] EN={en_ph} vs RU={ru_ph}")
    assert not errors, "Placeholder uyumsuzluğu:\n" + "\n".join(errors)
