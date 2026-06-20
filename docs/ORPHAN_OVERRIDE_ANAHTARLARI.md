# Orphan Override Anahtarları — Override JSON'da Kalan Girişler (YZ Referans Dokümanı)

Tarih: 20 Haziran 2026
Kapsam: `src/localization_auto_overrides.json` içinde **bilerek bırakılan** anahtar
İlgili dosyalar: `src/localization.py`, `src/localization_auto_overrides.json`

> Bu doküman, `TUTORIAL_EKSIK_LOCALIZATION_ANAHTARLARI.md` ile **karıştırılmamalıdır**.
> O doküman tutorial sisteminde TRANSLATIONS'a hiç eklenmemiş anahtarları anlatır.
> Bu doküman ise override JSON konsolidasyonundan **sonra** geriye kalan "yetim"
> (orphan) anahtarları anlatır.

---

## 0. Bağlam — Override JSON Neden Vardı, Neden Boşaltıldı

Çeviri sistemi eskiden iki katmanlı çalışıyordu:

1. `src/localization.py` içindeki satır-içi `TRANSLATIONS` sözlüğü — birçok anahtarın
   `de/fr/es/it/pt/ru/ja/zh/ko` değeri İngilizce **placeholder** (yani `en` ile aynı) idi.
2. `src/localization_auto_overrides.json` — gerçek çevirileri içeriyordu. Modül yüklenirken
   `_merge_translation_overrides(TRANSLATIONS)` (≈ `localization.py:31028`) ve hot-reload
   yolunda (≈ `localization.py:31135`) bu JSON `entry.update(lang_map)` ile
   placeholder'ların üzerine biniyordu.

**Konsolidasyon (20 Haziran 2026):** JSON'daki tüm gerçek çeviriler satır-içi
`TRANSLATIONS` sözlüğüne kalıcı olarak **bake edildi** (4661 dil değeri). Artık
`localization.py` tek başına kendi kendine yeterli kaynaktır; override JSON'a çalışma
zamanında ihtiyaç yoktur. Bake işlemi `tools/_bake_overrides.py` ile yapıldı.

Bake işleminden **önce ve sonra** runtime çeviri tablosu (`TRANSLATIONS`) birebir aynı
kalmıştır (`tools/_dump_runtime_translations.py` ile doğrulandı; before == after).

---

## 1. Yetim (Orphan) Anahtar Nedir

Override JSON'daki bazı anahtarların `tr`/`en` taban değeri `TRANSLATIONS`'da **yoktu**.
`_merge_translation_overrides` yalnızca `TRANSLATIONS`'da zaten **var olan** anahtarları
günceller (`localization.py:31021-31025`):

```python
for key, lang_map in overrides.items():
    entry = table.get(key)
    if not isinstance(entry, dict):
        continue          # anahtar yoksa atla
    entry.update(lang_map)
```

**Sonuç:** Bu yetim anahtarlar runtime'da **hiçbir zaman uygulanmadı** — yani çalışma
zamanı davranışı açısından etkisizdiler. Bake sırasında bunlar `TRANSLATIONS`'a
**eklenmedi** (kırmızı çizgi: `tr`/`en` tabanı tahmin edilmez). Bunun yerine override
JSON'da **olduğu gibi bırakıldılar**, böylece çevirileri kaybolmaz ve runtime davranışı
birebir korunur. Override mekanizması (`_load_translation_overrides`,
`_merge_translation_overrides`, hot-reload) **silinmedi**; küçük/yetim JSON ile merge
zararsız bir no-op olur ve gelecekte yeniden kullanılabilir.

> Not: Bu repoda (demo) yalnızca **1** yetim anahtar vardır. Tam sürümde (v2) bu sayı
> 11'dir; ikiz projeler bağımsız olarak ölçülür.

---

## 2. Bırakılan Yetim Anahtar

`src/localization_auto_overrides.json` artık yalnızca aşağıdaki anahtarı içerir.
Override'da bulunan dil değerleri listelenmiştir (`tr`/`en` tabanı yoktur, bu yüzden
runtime'da merge tarafından görmezden gelinir):

| Anahtar | Override'daki diller |
|---|---|
| `bg_show` | de, es, fr, it, ja, ko, pt, ru, zh |

---

## 3. Bu Anahtarla Ne Yapılmalı (Gelecekteki İş)

Bu anahtarı **etkin** kılmak isteyen bir geliştirici/YZ modeli:

1. Önce anahtarın `tr` ve `en` taban metnini belirlemeli (kod/veri içinde nasıl
   kullanıldığına bakarak — **tahmin etmeden**, gerçek kullanımdan).
2. Anahtarı 11 dilli olarak `localization.py:TRANSLATIONS`'a eklemeli (override'daki
   mevcut dil değerleri olduğu gibi kullanılabilir, eksik diller çevrilir).
3. Anahtar `TRANSLATIONS`'a girdikten sonra override JSON'daki karşılığı silinebilir.

**Kırmızı çizgi:** Bu anahtarın `tr`/`en` tabanını uydurma. Override'daki mevcut
çevirileri silme veya değiştirme. Runtime davranışını (merge no-op olması) değiştirme.

---

## 4. Doğrulama

```
# Runtime tablosu bake öncesi/sonrası birebir aynı olmalı (boş diff)
python tools/_dump_runtime_translations.py snapshot.json

# Tutorial audit'leri yeşil
python tools/_audit_tutorial_loc_keys.py        # missing_total 0
python tools/_audit_tutorial_lang_coverage.py   # problem_keys 0

# Localization testleri yeşil
python -m pytest tests/ -k "localiz or translation" -q
```
