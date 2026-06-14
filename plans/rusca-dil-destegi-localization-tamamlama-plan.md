# Plan: Rusça Dil Desteği + localization.py Eksik Anahtarları Tamamlama

**Created:** 2026-02-28
**Status:** Ready for Atlas Execution

## Summary

Bu çalışma oyuna Rusça (ru) dil desteği ekler ve `src/localization.py` içindeki çeviri tablosunda bazı anahtarların yalnızca birkaç dilde bulunması sorununu giderir. Amaç: (1) Rusça’nın menü/ayar ekranlarından seçilebilir olması, (2) dil dropdown’unda “Русский” etiketinin her platformda doğru fontla render edilmesi, (3) `TRANSLATIONS` sözlüğünde **her anahtarın** desteklenen **tüm dillerde** karşılığının bulunması (en azından fallback metinle), (4) placeholder (`{name}`) formatlarının tüm dillerde bozulmaması.

## Context & Analysis

**Relevant Files:**
- src/localization.py: `SUPPORTED_LANGUAGES`, `LANGUAGE_METADATA`, devasa `TRANSLATIONS` dict’i, `t()/get_text()` fallback zinciri, runtime `_ensure_language_fallback`.
- src/ui_language_profile.py: Dil panelinde dil adlarını doğru fontla çizmek için `get_font_for_language()`, ayrıca dil değişince `apply_language_ui_profile()`.
- src/menu.py: Dil dropdown paneli çizimi `get_font_for_language(code, size)` kullanıyor; yeni dil burada otomatik listeleniyor.
- src/settings_screen_tabbed.py: Ayarlar ekranında `language` selector’ı `SUPPORTED_LANGUAGES` sırasını döngüler.
- src/settings_manager.py: `TETRIS_DEFAULT_LANGUAGE` env override şu an sadece `tr/en` kabul ediyor.
- tetris.spec, tetris_en.spec, tetris_macos.spec: `font/` klasörü zaten paket datas içine ekleniyor; RU için eklenecek yeni font otomatik paketlenir.
- tools/_lang_audit.py: placeholder, boş string, TR/EN eksik vb. denetimler için hazır script.

**Key Findings:**
- Çeviriler harici dosyada değil, tek dosya `src/localization.py` içinde dict literal olarak tutuluyor.
- `get_text()` fallback zinciri: aktif dil → `en` → `tr` → `default` → `key`.
- Font profili override şu an yalnızca CJK (`ja/zh/ko`) için var. Rusça etiketleri dropdown’da çizilirken sistem fontu Kiril desteklemeyebilir; bu yüzden “sağlam” RU entegrasyonu için bundled Cyrillic font + UI profil eklenmeli.
- `font/` klasöründe CJK fontları var; Kiril (Cyrillic) kapsayan bir font yok.

## Implementation Phases

### Phase 1: RU Dilinin Sisteme Eklenmesi (Liste + Metadata)

**Objective:** Rusça (ru) kodu oyunun dil listesine girsin ve UI’da doğru isim/bayrakla görünsün.

**Files to Modify/Create:**
- src/localization.py

**Steps (TDD):**
1. Yeni test yaz: `test_localization_ru_registered.py`
   - `from localization import SUPPORTED_LANGUAGES, LANGUAGE_METADATA`
   - `'ru' in SUPPORTED_LANGUAGES` ve metadata’da `native_name == 'Русский'` gibi kontroller.
2. Testi çalıştır (fail beklenir).
3. src/localization.py:
   - `SUPPORTED_LANGUAGES` listesine `'ru'` ekle (öneri: `... 'pt', 'ru', 'ja', ...` gibi Latin alfabe dillerinin hemen sonuna).
   - `LANGUAGE_METADATA['ru']` ekle:
     - `name`: `Russian`
     - `native_name`: `Русский`
     - `flag_emoji`: `🇷🇺`
     - `rtl`: `False`
     - `complete`: başlangıçta `False` (Phase 4’te tüm RU çevirileri tamamlanınca `True` yapılacak)
4. Testi çalıştır (pass).

**Acceptance Criteria:**
- [ ] Rusça dil seçici listelerinde görünür.
- [ ] `LANGUAGE_METADATA` ru için doğru değerler içerir.

---

### Phase 2: Rusça İçin Font Profili (Kiril Güvencesi)

**Objective:** Dil dropdown’unda “Русский” (ve RU seçilince tüm UI) her platformda bozuk karakter kutuları olmadan render edilsin.

**Files to Modify/Create:**
- src/ui_language_profile.py
- (Yeni asset) font/<ru-font-folder>/<ru-font-file>.ttf (örn: `font/dejavu/DejaVuSans.ttf` veya `font/noto_sans/NotoSans-Regular.ttf`)
- (Opsiyonel) src/ui_theme.py veya src/retro_style.py (gerekirse font fallback sırası)

**Implementation Notes (Önerilen yaklaşım):**
- “Sağlam” entegrasyon için sistem fontuna güvenmek yerine Cyrillic kapsayan bir `.ttf`’yi repo’ya ekleyin.
- PyInstaller spec’ler `font/` klasörünü datas’a zaten eklediği için ek font otomatik paketlenir.

**Steps (TDD):**
1. Yeni test yaz: `test_ui_language_profile_ru_font_path.py`
   - `pygame` import’u test ortamında sorun çıkarabileceği için, mevcut testlerdeki gibi `sys.modules['pygame']` stub’la.
   - `ui_language_profile` import edildikten sonra `_PROFILE_BY_LANG` içinde `ru` var mı kontrol et.
   - `ru` için `font_path`’ın `font/` altında olduğunu ve dosyanın repo’da mevcut olduğunu `os.path.exists()` ile doğrula.
2. Testi çalıştır (fail beklenir).
3. Font asset ekle (örn. DejaVu Sans veya Noto Sans Regular). (Lisans dosyası gerekiyorsa font klasörüne ekleyin.)
4. src/ui_language_profile.py:
   - `_PROFILE_BY_LANG['ru'] = {'font_path': ..., 'size_scale': 1.0, 'force_no_bold': True}` ekle.
   - `get_font_for_language()`:
     - Sadece `_CJK_LANGS` kontrolüne bağlı kalmayın. En düşük-riskli değişiklik: `profile = _PROFILE_BY_LANG.get(lang_code)` varsa font yüklemeyi dene.
     - CJK dilleri için mevcut `HybridFont(latin_font, cjk_font)` davranışı korunsun.
     - RU için: `pygame.font.Font(font_path, size)` döndürmek yeterli (HybridFont gerekmiyor).
   - `apply_language_ui_profile()`:
     - En düşük-riskli yol: `profile = _PROFILE_BY_LANG.get(lang_code)` varsa uygula; yoksa resetle.
     - Böylece RU da otomatik “özel font” kullanır.
5. Testi çalıştır (pass).

**Acceptance Criteria:**
- [ ] Menü dil panelinde RU etiketi doğru render olur.
- [ ] RU seçilince UI font profili Cyrillic destekli fontu kullanır.

---

### Phase 3: Ayarlarda Env Varsayılan Dilinin Genişletilmesi (Sağlamlık)

**Objective:** `TETRIS_DEFAULT_LANGUAGE=ru` gibi değerlerle oyunun başlangıç dili ru yapılabilsin (en azından ru; tercihen tüm SUPPORTED_LANGUAGES).

**Files to Modify/Create:**
- src/settings_manager.py
- (Yeni) test_settings_env_default_language_ru.py

**Steps (TDD):**
1. Test yaz:
   - `os.environ['TETRIS_DEFAULT_LANGUAGE']='ru'` set et.
   - `SettingsManager()` oluşturup `default_settings['language']=='ru'` bekle.
   - Test izolasyonu için env değişkenini temizle.
2. Testi çalıştır (fail beklenir).
3. src/settings_manager.py `_apply_env_default_language()`:
   - Şu an `{'tr','en'}` whitelist’i var.
   - Bunu `from localization import SUPPORTED_LANGUAGES` ile (döngüsel import riskine dikkat ederek) veya lokal bir sabit listeyle genişlet:
     - En güvenlisi: burada küçük bir whitelist ekle: `{'tr','en','de','fr','es','it','pt','ru','ja','zh','ko'}`.
     - Alternatif: `SUPPORTED_LANGUAGES`’ı import et, ama settings_manager init sırasını kontrol et.
4. Testi çalıştır (pass).

**Acceptance Criteria:**
- [ ] Env ile RU varsayılan dil seçilebiliyor.

---

### Phase 4: localization.py İçinde Eksik Dil Anahtarlarını Tamamlama

**Objective:** `src/localization.py` içindeki `TRANSLATIONS` tablosunda her anahtarın tüm dillerde (tr/en/de/fr/es/it/pt/ru/ja/zh/ko) bir değeri olsun.

**Files to Modify/Create:**
- src/localization.py
- (Yeni) test_localization_no_missing_keys_any_language.py

**Yaklaşım:**
- Bu fazın amacı “missing key” problemini bitirmek. Tam çeviri kalitesi hedefi RU için Phase 5’te, diğer diller için ise minimumda EN fallback metniyle “tamamlama” yapılabilir.
- Kurallar:
  - TR ve EN her anahtarda zaten olmalı; eksikse test fail.
  - Diğer dillerde eksikse: en azından `en` değerini kopyalayın (yoksa `tr`). Böylece UI’da dil karışıklığı ve denetimlerde eksik görünümü ortadan kalkar.
  - `{placeholder}` içeren metinlerde placeholder isimleri korunmalı.

**Steps (TDD):**
1. Test yaz: `test_localization_no_missing_keys_any_language.py`
   - `from localization import TRANSLATIONS, SUPPORTED_LANGUAGES`
   - `SUPPORTED_LANGUAGES` içinde her dil için, her `TRANSLATIONS[key]` dict’inde ilgili dil anahtarı var mı assert et.
   - Ayrıca `TRANSLATIONS[key]['tr']` ve `['en']` var mı assert et (birincil diller).
2. Testi çalıştır (fail beklenir; özellikle de/fr/es/it/pt ve bazı anahtarlar).
3. src/localization.py:
   - Eksik dilleri tek tek tamamla.
   - “Sadece 4 dil var” olan anahtarlar için de/fr/es/it/pt/ru ekle.
   - `playlist_add` gibi yalnızca tr/en olanları da tüm dillere tamamla.
4. Testi çalıştır (pass).

**Acceptance Criteria:**
- [ ] Tüm `SUPPORTED_LANGUAGES` için tüm anahtarlar dict’te mevcut.
- [ ] `pytest` altında localization completeness testi geçer.

---

### Phase 5: Rusça Çevirileri Tamamlama (Kalite + Placeholder Güvenliği)

**Objective:** RU dili gerçek Rusça metinlerle kullanılabilir olsun; fallback’e yaslanmasın.

**Files to Modify/Create:**
- src/localization.py
- (Yeni) test_localization_ru_placeholders_match_en.py

**Steps (TDD):**
1. Placeholder testi yaz:
   - Regex ile EN metindeki `{...}` placeholder set’ini çıkar.
   - RU metindeki placeholder set’i ile eşleştiğini doğrula (eşit olmalı).
   - Bazı anahtarlar kasıtlı farklıysa, çok küçük bir allowlist ile istisna yönetilebilir (tercihen 0 istisna).
2. Testi çalıştır (fail beklenir; RU metinler yeni eklendikçe yakalar).
3. src/localization.py:
   - Her anahtar için `'ru': '...'` metnini **Rusça** olarak ekle.
   - Format placeholder’ları birebir aynı isimlerle koru (örn. `{minutes}`, `{level}` vb.).
   - UI taşmasını azaltmak için çok uzun cümleleri mümkün olduğunca kısa tut (özellikle buton/etiketlerde).
4. RU tamamlandıktan sonra `LANGUAGE_METADATA['ru']['complete'] = True` yap.
5. `tools/_lang_audit.py`’yi manuel doğrulama için çalıştır (placeholder, boş string, runtime hatası vb.).

**Acceptance Criteria:**
- [ ] RU’da görünen tüm kritik UI metinleri Rusça.
- [ ] Placeholder uyumsuzluğu yok.
- [ ] `complete=True` yalnızca RU gerçekten tamamsa.

---

### Phase 6: Regresyon ve Manuel Smoke Test

**Objective:** Rusça entegrasyonunun menü, ayarlar ve oyun içi ekranlarda sorunsuz çalıştığını doğrula.

**Steps:**
1. Oyunu aç → menüden dil panelini aç → “Русский” satırı düzgün görünüyor mu?
2. RU seç → ana menü, ayarlar, pause ekranı, kılavuz, kampanya ekranlarında bozuk karakter var mı?
3. Windows + macOS paket build (varsa) içinde RU fontu yükleniyor mu? (Kutu karakter olmamalı.)
4. `pytest` çalıştır.

**Acceptance Criteria:**
- [ ] Menü dil dropdown’u RU etiketini doğru fontla render eder.
- [ ] RU seçiliyken UI’da kare/kutu karakter yok.
- [ ] Tüm testler geçer.

## Open Questions

1. RU font seçimi (asset) hangisi olmalı?
   - **Option A:** DejaVu Sans (genelde küçük boyut, Kiril + Latin kapsar)
   - **Option B:** Noto Sans (çok geniş Unicode kapsamı, dosya daha büyük olabilir)
   - **Recommendation:** DejaVu Sans ile başla; boyut/kapsam dengesi iyi.

2. DE/FR/ES/IT/PT için “tamamlama” seviyesi?
   - **Option A:** Sadece eksikleri EN kopyasıyla doldur (minimum, hızlı)
   - **Option B:** Bu dilleri de gerçek çeviriyle tamamla (çok büyük kapsam)
   - **Recommendation:** Kullanıcı isteği “eksik anahtarları tamamla” olduğu için A yeterli; gerçek çeviri için ayrı görev aç.

## Risks & Mitigation

- **Risk:** `src/localization.py` çok büyük; yanlış merge/format hatası yapma riski.
  - **Mitigation:** Değişiklikleri küçük commit parçalarına böl; önce Phase 1-3, sonra Phase 4-5.
- **Risk:** Placeholder hatası runtime’da sessizce yutuluyor (`format` exception’ı catch ediliyor) → bug gizlenir.
  - **Mitigation:** Placeholder eşleme testi ekle (Phase 5).
- **Risk:** RU font asset’i eklenmezse bazı platformlarda kare karakterler görünür.
  - **Mitigation:** Phase 2’de bundled font + test.

## Success Criteria

- [ ] `SUPPORTED_LANGUAGES` içinde `'ru'` var ve UI’dan seçilebiliyor.
- [ ] Dil dropdown’unda “Русский” doğru görüntüleniyor.
- [ ] `TRANSLATIONS` tablosunda tüm anahtarlar tüm dillerde mevcut.
- [ ] RU çevirileri gerçek Rusça ve placeholder’lar tutarlı.
- [ ] `pytest` ve manuel smoke testler geçiyor.

## Notes for Atlas

- `menu.py` dil paneli label çiziminde `get_font_for_language(code, 18)` kullanıyor; RU için burada font döndürmek kritik.
- `ui_language_profile.py`’de en düşük-riskli refactor: `_CJK_LANGS` kontrolü yerine “profil var mı?” kontrolüne geçmek; CJK hybrid davranışı korunmalı.
- `tetris.spec` / `tetris_macos.spec` zaten `font/` klasörünü datas’a ekliyor; yeni RU font dosyası otomatik paketlenecek.

##önemli
-Let Sisyphus do all the coding.