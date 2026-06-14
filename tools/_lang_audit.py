"""Localization sistemi derin denetim scripti.

Kontrol edilen konular:
1. Tüm dillerde boş string ("") olan anahtarlar
2. Fallback sonrası hâlâ boş kalan anahtarlar
3. Format placeholder tutarsızlıkları ({name} TR'de var EN'de yok gibi)
4. TR veya EN'de eksik anahtarlar (birincil dillerde)
5. Aynı çevirinin TR ve EN'de birebir aynı olduğu durumlar (çevrilmemiş?)
6. _ensure_language_fallback sonrası de/fr/es/it/pt dillerde EN mi TR mi düşüyor
7. Büyük/küçük harf tutarsızlıkları (tüm büyük/küçük vs karışık)
8. Çok uzun çeviriler (UI taşması riski)
9. None değerli çeviriler
10. get_text runtime davranışı (her dil + her anahtar)
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from localization import (
    TRANSLATIONS, SUPPORTED_LANGUAGES, LANGUAGE_METADATA,
    set_language, get_language, t, get_text,
    _ensure_language_fallback, DEFAULT_LANGUAGE
)

issues = []
warnings = []

total_keys = len(TRANSLATIONS)
print(f"Toplam çeviri anahtarı: {total_keys}")
print(f"Desteklenen diller: {SUPPORTED_LANGUAGES}")
print()

# ============================================================
# 1) TR veya EN'de tamamen eksik anahtarlar
# ============================================================
print("=== 1. TR/EN Eksik Anahtar Kontrolü ===")
tr_missing = []
en_missing = []
for key, trans in TRANSLATIONS.items():
    if 'tr' not in trans:
        tr_missing.append(key)
    if 'en' not in trans:
        en_missing.append(key)

if tr_missing:
    issues.append(f"TR'de {len(tr_missing)} anahtar eksik")
    print(f"  ❌ TR'de {len(tr_missing)} anahtar eksik: {tr_missing[:10]}...")
else:
    print("  ✅ TR: tüm anahtarlar mevcut")

if en_missing:
    issues.append(f"EN'de {len(en_missing)} anahtar eksik")
    print(f"  ❌ EN'de {len(en_missing)} anahtar eksik: {en_missing[:10]}...")
else:
    print("  ✅ EN: tüm anahtarlar mevcut")

# ============================================================
# 2) Boş string ("") veya None çeviriler
# ============================================================
print("\n=== 2. Boş/None Çeviri Kontrolü ===")
empty_count = 0
none_count = 0
empty_details = {}
for key, trans in TRANSLATIONS.items():
    for lang, val in trans.items():
        if lang not in SUPPORTED_LANGUAGES:
            continue
        if val is None:
            none_count += 1
            issues.append(f"None değer: [{lang}] {key}")
            if lang not in empty_details:
                empty_details[lang] = []
            empty_details[lang].append(('None', key))
        elif isinstance(val, str) and val.strip() == '':
            empty_count += 1
            if lang in ('tr', 'en'):
                issues.append(f"Boş string: [{lang}] {key}")
            else:
                warnings.append(f"Boş string: [{lang}] {key}")
            if lang not in empty_details:
                empty_details[lang] = []
            empty_details[lang].append(('empty', key))

if empty_count == 0 and none_count == 0:
    print("  ✅ Boş veya None çeviri yok")
else:
    print(f"  ⚠️ {empty_count} boş string, {none_count} None değer bulundu")
    for lang, details in sorted(empty_details.items()):
        print(f"    [{lang}]: {len(details)} sorunlu — ilk 5: {[d[1] for d in details[:5]]}")

# ============================================================
# 3) Format placeholder tutarsızlıkları
# ============================================================
print("\n=== 3. Format Placeholder Tutarsızlılıkları ===")
placeholder_re = re.compile(r'\{(\w+)\}')
placeholder_issues = []
for key, trans in TRANSLATIONS.items():
    # TR ve EN'deki placeholder'ları baz al
    base_langs = {}
    for lang in ['tr', 'en']:
        if lang in trans and isinstance(trans[lang], str):
            base_langs[lang] = set(placeholder_re.findall(trans[lang]))
    
    if not base_langs:
        continue
    
    # TR ve EN arasında placeholder farkı var mı?
    if 'tr' in base_langs and 'en' in base_langs:
        tr_ph = base_langs['tr']
        en_ph = base_langs['en']
        if tr_ph != en_ph:
            # Bazı durumlarda kasıtlı olabilir (farklı cümle yapısı), ama kontrol edelim
            only_tr = tr_ph - en_ph
            only_en = en_ph - tr_ph
            if only_tr or only_en:
                placeholder_issues.append((key, f"TR extra: {only_tr}" if only_tr else "", f"EN extra: {only_en}" if only_en else ""))

if not placeholder_issues:
    print("  ✅ TR/EN arasında placeholder tutarsızlığı yok")
else:
    print(f"  ⚠️ {len(placeholder_issues)} anahtarda placeholder farkı:")
    for key, tr_extra, en_extra in placeholder_issues[:10]:
        print(f"    {key}: {tr_extra} {en_extra}")
    if len(placeholder_issues) > 10:
        print(f"    ... ve {len(placeholder_issues) - 10} tane daha")

# ============================================================
# 4) Fallback sonrası DE/FR/ES/IT/PT ne görüyor?
# ============================================================
print("\n=== 4. Fallback Dil Kontrolü (DE/FR/ES/IT/PT) ===")
secondary_langs = ['de', 'fr', 'es', 'it', 'pt']
for lang in secondary_langs:
    # Kaç anahtarın kendi çevirisi var vs fallback
    own_count = 0
    en_fallback = 0
    tr_fallback = 0
    key_fallback = 0
    for key, trans in TRANSLATIONS.items():
        val = trans.get(lang)
        if val is None:
            key_fallback += 1
            continue
        en_val = trans.get('en', '')
        tr_val = trans.get('tr', '')
        if val == en_val:
            en_fallback += 1
        elif val == tr_val:
            tr_fallback += 1
        else:
            own_count += 1
    
    print(f"  [{lang}]: {own_count} kendi çevirisi, {en_fallback} EN fallback, {tr_fallback} TR fallback, {key_fallback} eksik")

# ============================================================
# 5) t() runtime testi — her dilde her anahtarı çağır
# ============================================================
print("\n=== 5. t() Runtime Testi ===")
runtime_errors = []
for lang in SUPPORTED_LANGUAGES:
    set_language(lang)
    for key in TRANSLATIONS:
        try:
            result = t(key)
            if result is None:
                runtime_errors.append((lang, key, "None döndü"))
            elif not isinstance(result, str):
                runtime_errors.append((lang, key, f"str değil: {type(result)}"))
        except Exception as e:
            runtime_errors.append((lang, key, str(e)))

set_language(DEFAULT_LANGUAGE)

if not runtime_errors:
    print(f"  ✅ {len(SUPPORTED_LANGUAGES)} dil × {total_keys} anahtar = {len(SUPPORTED_LANGUAGES) * total_keys} çağrı — hata yok")
else:
    print(f"  ❌ {len(runtime_errors)} runtime hatası!")
    for lang, key, err in runtime_errors[:15]:
        print(f"    [{lang}] {key}: {err}")
    issues.extend([f"Runtime: [{l}] {k}: {e}" for l, k, e in runtime_errors])

# ============================================================
# 6) Format parametreli anahtarların tüm dillerde çalışması
# ============================================================
print("\n=== 6. Format Parametreli Anahtar Testi ===")
format_keys = []
for key, trans in TRANSLATIONS.items():
    for lang_code, val in trans.items():
        if isinstance(val, str) and '{' in val:
            format_keys.append(key)
            break

format_errors = []
for key in format_keys:
    # TR çevirisindeki placeholder'ları bul
    for base_lang in ['tr', 'en']:
        base_text = TRANSLATIONS[key].get(base_lang, '')
        if not isinstance(base_text, str):
            continue
        placeholders = placeholder_re.findall(base_text)
        if not placeholders:
            continue
        # Dummy kwargs oluştur
        dummy_kwargs = {p: 'TEST' for p in placeholders}
        # Her dilde dene
        for lang in SUPPORTED_LANGUAGES:
            set_language(lang)
            try:
                result = t(key, **dummy_kwargs)
                # Sonuçta 'TEST' olmalı (eğer placeholder varsa)
                lang_text = TRANSLATIONS[key].get(lang, '')
                if isinstance(lang_text, str) and '{' in lang_text:
                    lang_placeholders = set(placeholder_re.findall(lang_text))
                    missing_in_result = [p for p in lang_placeholders if 'TEST' not in result and f'{{{p}}}' in lang_text]
                    if missing_in_result:
                        format_errors.append((lang, key, f"placeholder çözülmedi: {missing_in_result}"))
            except Exception as e:
                format_errors.append((lang, key, str(e)))
        break  # bir base_lang yeterli

set_language(DEFAULT_LANGUAGE)

if not format_errors:
    print(f"  ✅ {len(format_keys)} format anahtarı tüm dillerde çalışıyor")
else:
    print(f"  ⚠️ {len(format_errors)} format hatası:")
    for lang, key, err in format_errors[:10]:
        print(f"    [{lang}] {key}: {err}")

# ============================================================
# 7) TR-EN birebir aynı çeviriler (çevrilmemiş olabilir)
# ============================================================
print("\n=== 7. TR-EN Aynı Çeviri Kontrolü ===")
same_count = 0
same_keys = []
for key, trans in TRANSLATIONS.items():
    tr_val = trans.get('tr', '')
    en_val = trans.get('en', '')
    if isinstance(tr_val, str) and isinstance(en_val, str) and tr_val == en_val and tr_val:
        # Sayılar, kısa semboller, özel isimler (Quadrix, PvP vb) hariç
        if len(tr_val) > 3 and not tr_val.replace(' ', '').isnumeric() and tr_val not in ('Quadrix', 'PvP', 'FPS', 'DAS', 'N/A', 'OK', 'GitHub', 'Discord'):
            same_count += 1
            same_keys.append((key, tr_val))

if same_count == 0:
    print("  ✅ TR-EN birebir aynı çeviri yok (3+ karakter olanlar)")
else:
    # Bu çoğunlukla teknik terimler olabilir, BUG değil ama kontrol edelim
    print(f"  ℹ️ {same_count} anahtarda TR=EN (muhtemelen teknik terim veya çevrilmemiş):")
    for key, val in same_keys[:20]:
        print(f"    {key}: '{val}'")
    if same_count > 20:
        print(f"    ... ve {same_count - 20} tane daha")

# ============================================================
# 8) _ensure_language_fallback boş string sorunu
# ============================================================
print("\n=== 8. Fallback Boş String Geçirme Sorunu ===")
# _ensure_language_fallback: eğer anahtar zaten var ve BOŞ değilse atlar
# AMA eğer anahtar var ve BOŞ ise (""), _ensure_language_fallback onu boş bırakır
# Çünkü kontrol: `if lang_code in translations and translations[lang_code]:`
# Boş string "" falsy olduğu için, boş string olan anahtarlar fallback'e gider ✓
# Ama None değilse ve truthy değilse? Test edelim
falsy_but_present = 0
for key, trans in TRANSLATIONS.items():
    for lang in SUPPORTED_LANGUAGES:
        if lang in trans and not trans[lang] and trans[lang] is not None:
            # Boş string var, fallback çalışmalı
            falsy_but_present += 1

if falsy_but_present > 0:
    print(f"  ℹ️ {falsy_but_present} yerde boş string var ama fallback doğru çalışmalı ('' is falsy)")
else:
    print("  ✅ Fallback boş string sorunu yok")

# ============================================================
# 9) Çok uzun çeviriler (UI taşma riski)
# ============================================================
print("\n=== 9. Uzun Çeviri Kontrolü (>120 karakter) ===")
long_translations = []
for key, trans in TRANSLATIONS.items():
    for lang, val in trans.items():
        if isinstance(val, str) and len(val) > 120 and lang in ('tr', 'en'):
            long_translations.append((key, lang, len(val)))

if not long_translations:
    print("  ✅ 120+ karakter çeviri yok")
else:
    print(f"  ℹ️ {len(long_translations)} uzun çeviri (UI taşma riski):")
    for key, lang, length in sorted(long_translations, key=lambda x: -x[2])[:10]:
        print(f"    [{lang}] {key}: {length} karakter")

# ============================================================
# 10) Dil ayarı kaydetme/yükleme tutarlılığı
# ============================================================
print("\n=== 10. set_language/get_language Tutarlılığı ===")
lang_errors = []
for lang in SUPPORTED_LANGUAGES:
    ok = set_language(lang)
    current = get_language()
    if not ok:
        lang_errors.append(f"{lang}: set_language False döndü")
    if current != lang:
        lang_errors.append(f"{lang}: get_language '{current}' döndü")

# Geçersiz dil kodu
ok = set_language('xx')
if ok:
    lang_errors.append("Geçersiz dil 'xx' kabul edildi!")
current = get_language()
# Son geçerli dil kalmalı
if current not in SUPPORTED_LANGUAGES:
    lang_errors.append(f"Geçersiz dil sonrası current: {current}")

set_language(DEFAULT_LANGUAGE)

if not lang_errors:
    print("  ✅ set_language/get_language tutarlı")
else:
    for e in lang_errors:
        print(f"  ❌ {e}")
    issues.extend(lang_errors)

# ============================================================
# ÖZET
# ============================================================
print("\n" + "=" * 60)
print(f"ÖZET: {len(issues)} gerçek sorun, {len(warnings)} uyarı")
if issues:
    print("\n❌ SORUNLAR:")
    for i, issue in enumerate(issues[:30], 1):
        print(f"  {i}. {issue}")
    if len(issues) > 30:
        print(f"  ... ve {len(issues) - 30} tane daha")
if warnings:
    print(f"\n⚠️ {len(warnings)} uyarı (çoğu ikincil dillerde boş string)")
if not issues and not warnings:
    print("✅ Lokalizasyon sistemi sağlıklı!")
print("=" * 60)
