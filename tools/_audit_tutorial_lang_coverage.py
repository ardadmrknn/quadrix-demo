"""Tutorial sisteminin referans verdigi TUM anahtarlari (onek fark etmeksizin)
final runtime TRANSLATIONS tablosunda her dil icin denetler.

Bir dil degeri:
  - hic yoksa            -> MISSING
  - 'en' ile birebir ayni-> EQUALS_EN (olasi cevrilmemis)
olarak raporlanir. Marka/loanword icin ALLOWED_EQUAL listesi haric tutulur.
"""
import os
import sys
import importlib.util
from collections import Counter

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
SRC = os.path.join(ROOT, 'src')
sys.path.insert(0, SRC)
sys.path.insert(0, TOOLS)

# referans anahtar toplayicilarini yeniden kullan
import _audit_tutorial_loc_keys as auditor  # noqa: E402
from localization import TRANSLATIONS, SUPPORTED_LANGUAGES  # noqa: E402

CHECK_LANGS = [l for l in SUPPORTED_LANGUAGES if l not in ('tr', 'en')]

# Mesru olarak ingilizce ile ayni kalabilecek marka adlari / uluslararasi terimler
ALLOWED_EQUAL = {
    'Quadrix', 'Quadrix!', 'Hold', 'Combo', 'Tempo', 'Tutorial', 'Ideal',
    'Rotation', 'Surface', 'Timing', 'Bravo!', 'Hard Drop', 'Soft Drop',
    'Perk', 'Balance', 'ESC', 'OK', 'I', 'T', 'L', 'J', 'S', 'Z', 'O',
}


def referenced_keys():
    keys = {}
    for fn, fn_collector in (
        ('tutorial.py', auditor.collect_t_call_keys),
        ('tutorial_lessons.py', auditor.collect_data_pairs),
        ('tutorial_scenarios.py', auditor.collect_data_pairs),
        ('tutorial_cards.py', auditor.collect_data_pairs),
    ):
        try:
            for k in fn_collector(fn):
                keys[k] = True
        except Exception as e:
            print('WARN', fn, e)
    return set(keys)


def main():
    refs = referenced_keys()
    counter = Counter()
    problems = {}
    for key in sorted(refs):
        entry = TRANSLATIONS.get(key)
        if not isinstance(entry, dict):
            continue
        en = entry.get('en')
        if not en:
            continue
        en_norm = en.strip()
        if en_norm in ALLOWED_EQUAL:
            continue
        for lang in CHECK_LANGS:
            v = entry.get(lang)
            if v is None:
                counter[lang] += 1
                problems.setdefault(key, []).append(f'{lang}:MISSING')
            elif v.strip() == en_norm and en_norm:
                counter[lang] += 1
                problems.setdefault(key, []).append(f'{lang}:EQUALS_EN')

    print(f'referenced_keys {len(refs)}')
    print(f'problem_keys {len(problems)}')
    print('per_lang:', {l: counter.get(l, 0) for l in CHECK_LANGS})
    for k in sorted(problems):
        print(' ', k, problems[k])


if __name__ == '__main__':
    main()
