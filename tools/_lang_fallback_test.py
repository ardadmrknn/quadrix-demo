"""DE dili fallback derinlik testi"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from localization import TRANSLATIONS, SUPPORTED_LANGUAGES, set_language, t

# ---- DE dilinde fallback sonrası durum ----
set_language('de')
missing_in_dict = 0
returns_key_as_value = []

for key in TRANSLATIONS:
    if 'de' not in TRANSLATIONS[key]:
        missing_in_dict += 1
    val = t(key)
    if val == key and len(key) > 5:
        returns_key_as_value.append(key)

print(f"DE: TRANSLATIONS dict'te eksik: {missing_in_dict}/{len(TRANSLATIONS)}")
print(f"DE: Runtime'da key=value dönen (çevrilmemiş gibi): {len(returns_key_as_value)}")
if returns_key_as_value:
    for k in returns_key_as_value[:10]:
        val_tr = TRANSLATIONS[k].get('tr', '?')
        val_en = TRANSLATIONS[k].get('en', '?')
        val_de = TRANSLATIONS[k].get('de', '?')
        print(f"  {k}: de='{val_de}' tr='{val_tr}' en='{val_en}'")

# ---- Fallback beklenen davranış ----
print()
print("=== Fallback beklenen davranış ===")
# _ensure_language_fallback DE için çağrılmıyor! Sadece ja/zh/ko için çağrılıyor.
# DE/FR/ES/IT/PT bunun dışında — get_text fallback zinciri ile çalışıyor.
# get_text: TRANSLATIONS[key].get(_current_language, .get('tr', .get('en', ...)))
# Yani DE'de yoksa -> TR'ye düşüyor (EN değil!)

# Bu gerçekten böyle mi test edelim:
test_key = None
for key in TRANSLATIONS:
    if 'de' not in TRANSLATIONS[key] and 'tr' in TRANSLATIONS[key] and 'en' in TRANSLATIONS[key]:
        tr_val = TRANSLATIONS[key]['tr']
        en_val = TRANSLATIONS[key]['en']
        if tr_val != en_val and len(tr_val) > 5:
            test_key = key
            break

if test_key:
    set_language('de')
    result = t(test_key)
    tr_val = TRANSLATIONS[test_key]['tr']
    en_val = TRANSLATIONS[test_key]['en']
    print(f"Test anahtar: {test_key}")
    print(f"  TR: '{tr_val}'")
    print(f"  EN: '{en_val}'")
    print(f"  DE (t() sonucu): '{result}'")
    if result == tr_val:
        print("  --> Fallback: TR'ye düşüyor")
    elif result == en_val:
        print("  --> Fallback: EN'ye düşüyor")
    else:
        print(f"  --> Fallback: bilinmeyen değer!")

# ---- DE için _ensure_language_fallback çağrılsa ne olur? ----
print()
print("=== DE/FR/ES/IT/PT için _ensure_language_fallback kontrolü ===")
for lang in ['de', 'fr', 'es', 'it', 'pt']:
    not_in_dict = sum(1 for k in TRANSLATIONS if lang not in TRANSLATIONS[k])
    # get_text fallback ile ne dönüyor?
    set_language(lang)
    falls_to_tr = 0
    falls_to_en = 0
    has_own = 0
    for key in TRANSLATIONS:
        if lang not in TRANSLATIONS[key]:
            # get_text: .get(lang) -> None -> .get('tr') -> TR değeri
            val = t(key)
            tr_val = TRANSLATIONS[key].get('tr', '')
            en_val = TRANSLATIONS[key].get('en', '')
            if val == tr_val:
                falls_to_tr += 1
            elif val == en_val:
                falls_to_en += 1
        else:
            has_own += 1
    print(f"  [{lang}] dict'te eksik: {not_in_dict} -> TR'ye düşen: {falls_to_tr}, EN'ye düşen: {falls_to_en}, kendi: {has_own}")
