# Plan: PromptFont Gamepad Glyph Entegrasyonu

**Created:** 2026-04-18
**Status:** Draft — Ready for Review
**Scope:** Phase 1 yalnizca Ayarlar > Kontroller > Gamepad ekranı

## Ozet

Amaç: gamepad button label metinlerini uygun yerlerde PromptFont glyph ile göstermek.

Ilk rollout tum oyuna degil. Sadece `Ayarlar > Kontroller` ekranindaki gamepad keybind slot'lari hedeflenecek.

Sebep:

- blast radius kucuk
- draw akisi izole
- fallback kontrolu kolay
- PromptFont pygame uyumu once tek ekranda dogrulanir

Mevcut arastirma sonucu:

- PromptFont var: `assets/gamepad_icon/promptfont/promptfont.ttf`
- Lisans uygun: SIL OFL 1.1
- `pygame.font.Font` ile yuklenip glyph render ediyor
- Gamepad settings row'lari zaten `src/settings_screen_tabbed.py` icinde ayri branch ile ciziliyor

## Hedef Davranis

Gamepad keybind slot'larinda:

- `A / B / X / Y` gibi duz metin yerine uygun PromptFont glyph'i gorunsun
- `LB / RB / LT / RT / L1 / R1 / L2 / R2 / D-pad / Start / Back` icin uygun glyph gorunsun
- aktif controller tipi biliniyorsa family-specific glyph kullanilsin
- aktif controller yoksa generic glyph kullanilsin
- glyph bulunamazsa bugun kullandigimiz metin fallback devam etsin

Ilk phase disi:

- splash screen
- guide/card text icindeki `{button}` placeholder'lari
- oyun ici popup/hint/metinler
- inline mixed text layout

## Ilgili Dosyalar

| Dosya | Rol |
| --- | --- |
| `assets/gamepad_icon/promptfont/promptfont.ttf` | PromptFont font dosyasi |
| `assets/gamepad_icon/promptfont/promptfont.py` | Python constant map |
| `assets/gamepad_icon/promptfont/README.md` | kullanim + attribution + format notlari |
| `assets/gamepad_icon/promptfont/LICENSE.txt` | SIL OFL 1.1 |
| `src/settings_screen_tabbed.py` | phase1 draw/integration noktasi |
| `src/gamepad_manager.py` | binding index + controller family bilgisi |
| `src/retro_style.py` | mevcut font/render stack |

## Mevcut Kod Durumu

Gamepad keybind row'lari su yolda ciziliyor:

- `_build_tab_items()` gamepad item listesi kuruyor
- `_draw_selector_value()` icinde `section == 'gamepad'` branch'i iki slot ciziyor
- `_format_gamepad_button_label()` ham button index'i duz string label'a ceviriyor

Bu iyi. Cunku phase1 tek dosyada izole degisiklik ile bitebilir.

## Ana Tasarim Kararlari

### 1. Global font degistirme yok

`retro_style.get_font()` veya ana UI font stack degismeyecek.

Sebep:

- CJK/latin hibrit yapi var
- tum UI'yi etkiler
- regression riski gereksiz buyur

Phase1 icin PromptFont ayri yardimci font olarak yuklenecek.

### 2. Ligature / wide alternate / backfill yok

PromptFont README ligature, zero-width-space, backfill, wide alternate anlatiyor. Bunlar phase1'de kullanilmayacak.

Sebep:

- `pygame.font` ligature davranisi guvenli varsayilamaz
- iki slotluk basit badge UI icin gerek yok
- once tek glyph + basit tint yeter

### 3. Metin icine inline gömme yok

Phase1 yalnız slot icindeki buton label gorunumu icin.

Sebep:

- mevcut `font.render(text)` akisi inline image/glyph run istemiyor
- mixed text layout daha sonra ayrica ele alinmali

### 4. Fallback zorunlu

Her glyph resolve yolu sonunda text fallback olacak.

Ornek:

- glyph bulundu -> PromptFont glyph ciz
- glyph yok -> `LB`, `A`, `Start`, `D-Pad Up` gibi mevcut text label ciz

## Onerilen Dosya Degisiklikleri

### A. Yeni Yardimci Modül

Yeni dosya:

- `src/promptfont_support.py`

Rol:

- PromptFont dosyasini cache'li yuklemek
- gamepad action/button index + controller family -> glyph constant map kurmak
- render yardimci surface dondurmek
- text fallback vermek

Onerilen API:

```python
def get_promptfont(size: int) -> pygame.font.Font | None
def get_gamepad_glyph_for_button_index(btn_index: int, gp_type: str | None) -> str | None
def get_gamepad_glyph_or_label(btn_index: int, gp_type: str | None) -> tuple[str | None, str]
def render_gamepad_glyph(text_or_glyph: str, size: int, color: tuple[int, int, int]) -> pygame.Surface
```

Not:

- `promptfont.py` icindeki constant'lar import edilir
- mapping helper sadece bu modülde tutulur
- `settings_screen_tabbed.py` PromptFont constant adlarini bilmez

### B. Settings Screen Entegrasyonu

Ana hedef dosya:

- `src/settings_screen_tabbed.py`

Degisim noktasi:

1. `_format_gamepad_button_label()`
   - duz string donmek yerine text fallback kaynagi olarak korunur
   - istenirse adi `_format_gamepad_button_text_label()` olarak ayrilabilir

2. `_draw_selector_value()` gamepad branch
   - bugun `primary_text` / `secondary_text` aliyor
   - phase1 sonra slot basina `display spec` alacak:
     - `kind = glyph | text | waiting | unbound`
     - `glyph_char`
     - `fallback_label`

3. slot cizici ayristir
   - lokal nested `_draw_slot(...)` yerine ayri helper daha temiz:

```python
def _draw_gamepad_slot(self, slot_rect, display_spec, active):
    ...
```

4. waiting/unbound text korunur
   - `Butona basin`
   - `Atanmamis`

### C. Packaging / Credits Kontrolu

Phase1 kod degisimi ekran odakli olsa da su kontrol gerekir:

- PromptFont asset build'e giriyor mu?
- credits / third-party notes icine attribution eklenmeli mi?

Minimum:

- `PromptFont by Yukari "Shinmera" Hafner, available at https://shinmera.com/promptfont`

## Mapping Stratejisi

### Controller family secimi

Kaynak:

- `get_gamepad_manager().get_active_gamepad()`
- `gp.gamepad_type`

Kurallar:

1. aktif controller varsa:
   - Xbox -> Xbox glyph
   - PlayStation -> Sony glyph
   - Nintendo -> Nintendo glyph

2. aktif controller yoksa:
   - face button icin generic glyph tercih
   - trigger/shoulder/dpad/start icin generic varsa generic
   - yoksa mevcut text fallback

### Minimum phase1 coverage

Bu aksiyonlar ilk phase'te kapsanacak:

| Aksiyon | Mevcut binding | Hedef glyph |
| --- | --- | --- |
| `hard_drop` | button 0 | Xbox A / Sony Cross / Nintendo B / generic A |
| `hold` | button 9 | Xbox LB / Sony L1 / Nintendo L / generic shoulder |
| `hold2` | button 2 | Xbox X / Sony Square / Nintendo Y / generic X |
| `pause` | button 6 | Start / Options / Plus |
| `discard_held` | button 3 | Xbox Y / Sony Triangle / Nintendo X / generic Y |
| `menu_confirm` | button 0 | family-specific confirm glyph |
| `menu_back` | button 1 | family-specific back glyph |
| `menu_tab_next` | button 10 | Xbox RB / Sony R1 / Nintendo R |
| `menu_tab_prev` | button 9 | Xbox LB / Sony L1 / Nintendo L |
| trigger bindings | pseudo 100/101 | LT/RT, L2/R2, ZL/ZR |

### Mapping disinda kalabilecekler

Phase1 icin sorun degil:

- share / guide / touchpad gibi exotic button'lar
- combo / double-glyph / backfill varyantlari
- mouse emulation icon'lari

## Faz Plani

### Faz 1 — Settings ekranina izole PromptFont altyapisi

**Hedef:** gamepad keybind slot'larinda glyph goster.

**Adimlar:**

1. `src/promptfont_support.py` ekle
   - PromptFont font cache
   - controller-family aware glyph map
   - text fallback helper

2. `src/settings_screen_tabbed.py` import ekle
   - yalniz gamepad slot draw branch kullanir

3. gamepad value pipeline ayir
   - text label helper korunur
   - yeni display-spec helper gelir

4. gamepad slot draw helper ekle
   - glyph varsa PromptFont ile ciz
   - yoksa mevcut metin ciz
   - selected/unselected renkleri korunur

5. width-fit davranisi ayarla
   - glyph font size slot yuksekligine gore belirlenir
   - `Atanmamis` / `Butona basin` gibi text halleri eski fit mantigi ile kalir

6. no-controller fallback uygula
   - aktif gamepad yoksa generic glyph veya text fallback

7. attribution notu ekle
   - uygun credits / third-party doc noktasina

**Bitis Kriteri:**

- ayarlar ekraninda gamepad keybind slot'lari glyph gosterir
- keyboard/PvP/single-player keybind UI etkilenmez
- PromptFont load fail olursa ekran text mode ile calisir

### Faz 2 — Shared helper sertlestirme

**Hedef:** phase1 kodunu tekrar kullanilabilir hale getir.

**Adimlar:**

1. settings ekranindaki gecici local helper'lar temizlenir
2. promptfont support API stabilize edilir
3. ui-scale / slot-fit edge case'leri toparlanir

### Faz 3 — Sonraki rollout adaylari

Bu faz phase1 disi. Sadece sonraki hedef listesi:

1. splash screen continue prompt
2. `guide_screen` card/perk placeholder text
3. `game_modes_extra` `{button}` aciklamalari
4. pause / modal / overlay button hint'leri

## Teknik Riskler

### Risk 1 — Pygame glyph metrics farki

PromptFont glyph boyu normal harflerden buyuk olabilir.

Onlem:

- phase1 sadece slot icinde kullan
- text line baseline ile ugrasmak yok
- slot icinde dikey ortala

### Risk 2 — Controller family yokken yanlis ikon

Aktif gamepad bagli degilse stored binding family'si bilinmez.

Onlem:

- generic glyph once
- yoksa text fallback

### Risk 3 — PyInstaller asset eksigi

Font dosyasi paketlenmezse runtime fail olur.

Onlem:

- build spec veya mevcut asset kopyalama zinciri kontrol edilir
- fail halinde helper `None` doner, text fallback calisir

### Risk 4 — Ligature/backfill beklentisi

PromptFont README ileri ozellik anlatiyor. `pygame.font` ile ayni davranis garanti degil.

Onlem:

- phase1 tek glyph only
- ligature/backfill/wide variant yok

## Test Plani

### Smoke

1. `pygame.font.Font` PromptFont TTF yukleyebiliyor mu?
2. Xbox A, generic A, Sony X, D-pad, Start render oluyor mu?

Bu smoke zaten arastirmada basarili goruldu.

### UI Doğrulama

1. Settings > Controls > Gamepad sekmesi ac
2. bagli Xbox ile glyph'leri kontrol et
3. bagli PlayStation ile glyph'leri kontrol et
4. bagli Nintendo ile glyph'leri kontrol et
5. gamepad bagli degilken fallback davranisini kontrol et
6. capture mode'da `Butona basin` text kalmali
7. `Atanmamis` text kalmali

### Regresyon

1. keyboard keybind satirlari bozulmadi
2. PvP keybind satirlari bozulmadi
3. settings row layout tasmadi
4. tab navigation ve bind capture akisi bozulmadi

## Acceptance Criteria

Phase1 tamam sayilir, eger:

- PromptFont yalniz settings gamepad slot'larinda kullaniliyorsa
- family-specific veya generic glyph secimi calisiyorsa
- fallback text her failure yolunda calisiyorsa
- UI slot layout bozulmuyorsa
- build/package yolunda font asset erisilebilir ise

## Onerilen Uygulama Sirasi

1. `promptfont_support.py` helper ekle
2. settings ekraninda gamepad slot draw branch'e entegre et
3. no-font / no-controller fallback'i kapat
4. local smoke + settings ekran manuel check
5. attribution ve packaging notunu ekle

## Not

Bu plan bilerek tum oyuna rollout acmiyor.

Ilk kazanim: tek ekranda dusuk-risk dogrulama.

Phase1 temiz gecerse, ayni helper ile diger `{button}` placeholder ekranlarina yaymak kolaylasir.