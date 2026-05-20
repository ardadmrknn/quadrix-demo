# Demo Popup Gloss Removal Port Guide

Bu not, quadrix-demo icinde popup panellerin ustunde gorunen parlama/yansima overlay'ini kaldirmak icin yapilan degisiklikleri listeler. Amac, ayni degisikliklerin daha sonra v2 tarafina kontrollu sekilde uygulanmasini kolaylastirmaktir.

## Hedef

Kaldirilan efekt su desenlere karsilik geliyor:

- Panelin ust ucunda acik renkli yari saydam bant
- Popup icindeki kutucuk veya butonun ust kismina cizilen beyaz parlama cizgileri
- Header bandi icine eklenen ekstra ust highlight katmani

## Demo'da Degisen Dosyalar

### 1. Ortak glass panel helper'lari

#### src/retro_style.py

Degisiklik:

- `retro_style.draw_glass_panel()` icindeki ust kenar highlight cizimi kaldirildi.
- `top_highlight` parametresi API uyumlulugu icin korundu, ama demo tarafinda ust parlama artik cizilmiyor.

Port onceligi:

- v2 tarafinda once bu helper'i bulun.
- V2'de popup panellerin buyuk kismi bu helper'i kullaniyorsa, tek basina bu degisiklik popup yansimalarinin buyuk bolumunu temizler.

#### src/ui_components.py

Degisiklik:

- `draw_glass_panel()` icindeki ust highlight rect/gradient katmani kaldirildi.

Port onceligi:

- Online/PvP/Co-op popup veya lobby panelleri bu helper'i kullaniyorsa v2'de ayni noktayi guncelleyin.

### 2. Demo popup ozel override'lari

#### src/demo_upgrade_prompt.py

Degisiklik:

- `_draw_panel_overlays()` icindeki ust `header_tint` dikdortgeni kaldirildi.
- `_draw_button()` icindeki ust beyaz parlama cizgileri kaldirildi.

V2 port notu:

- V2'de demo prompt'un birebir karsiligi olmayabilir.
- Ancak benzer store upsell / locked mode / upgrade prompt varsa ayni overlay mantigini arayin.

#### src/game.py

Degisiklik:

- `_draw_exit_prompt_overlay()` icindeki hover ust parlama cizgisi kaldirildi.
- `_draw_game_over_overlay()` icinde:
  - alt theme panel tint'ine eklenen ust highlight kaldirildi
  - game over butonlarindaki ust highlight cizgileri kaldirildi

V2 port notu:

- V2'de normal gameplay game over ve exit confirm popup'lari icin ilk bakilacak yer burasi.
- Eger game over kodu farkli siniflara bolunmusse ayni highlight desenini arayin.

#### src/campaign/campaign_ui.py

Degisiklik:

- Level complete overlay fallback panel highlight'i kaldirildi.
- Level complete header bandinin ust highlight'i kaldirildi.
- Section panel fallback cizimindeki ust highlight kaldirildi.
- Level failed overlay fallback panel highlight'i kaldirildi.

V2 port notu:

- V2 campaign popup'lari demo ile genelde en yakin eslesmeye sahip kisimdir.
- Ozellikle level complete / level failed / reward summary panellerini bu dosyada arayin.

#### src/campaign/coop_campaign_mode.py

Degisiklik:

- Co-op campaign level complete popup'inin baslik bandina cizilen ust beyaz highlight kaldirildi.

V2 port notu:

- Co-op campaign veya benzer ikinci campaign popup'lari ayri sinifta tutuluyorsa ayni header bandi mantigini burada da temizleyin.

#### src/tutorial.py

Degisiklik:

- Tutorial overlay icindeki ok butonlarinin ust highlight'i kaldirildi.
- Chapter kartlari `top_highlight=False` ile cizilecek sekilde guncellendi.
- Lesson paneli `top_highlight=False` ile cizilecek sekilde guncellendi.
- Lesson row kartlarinin ust highlight cizgileri kaldirildi.

V2 port notu:

- V2 tutorial veya lesson hub popup'larinda benzer kart yapisi varsa ayni noktalar tasinmali.

#### src/menu.py

Degisiklik:

- Popup tarzi hover butonlarinda kullanilan ust parlama cizgileri kaldirildi.
- Kontrol ayarlari ve muzik/track secici gibi tam ekran modal panellerde panel ust bandi ve secili satir highlight katmani kaldirildi.
- Demo'da dogrudan gorulen en yakin ornekler SOS/geri don/exit turu modal aksiyon butonlari.

V2 port notu:

- V2 ana menu icindeki modal popup'larda hover durumunda ustte cizilen 1 piksellik parlama cizgileri varsa ayni sekilde temizleyin.

## V2 Icin Onerilen Port Sirasi

1. `v2/src/retro_style.py` icinde `draw_glass_panel()` helper'ini guncelleyin.
2. `v2/src/ui_components.py` icinde glass panel helper varsa ayni degisikligi uygulayin.
3. Sonra popup ozel dosyalari su sirayla kontrol edin:
   - `v2/src/game.py`
   - `v2/src/campaign/campaign_ui.py`
   - `v2/src/campaign/coop_campaign_mode.py`
   - `v2/src/tutorial.py`
   - `v2/src/menu.py`
   - varsa upgrade/store/locked-mode popup dosyalari
4. Hover butonlarinda su deseni arayin ve kaldirin:
   - `highlight_rect = pygame.Rect(4, 2, ... )`
   - `pygame.draw.rect(..., (*color, 60), highlight_rect)`
   - `for y in range(hl_h): pygame.draw.line(... white alpha ...)`
5. Header bandi icin su deseni arayin ve kaldirin:
   - `header_tint = pygame.Surface(..., pygame.SRCALPHA)`
   - `header_highlight_h = ...`
   - `for i in range(header_highlight_h):`

## V2'de Aranacak Desenler

Asagidaki desenler ust parlama efektinin tipik izleridir:

```text
highlight_rect = pygame.Rect(4, 2, ...)
header_tint = pygame.Surface(..., pygame.SRCALPHA)
for y in range(highlight_height):
    pygame.draw.line(..., (255, 255, 255, alpha), ...)
top_highlight=True
```

## Demo Tarafinda Etkilenen Popup Siniflari

Bu degisikliklerden sonra demo tarafinda su popup aileleri parlama overlay'inden temizlenmis olur:

- Demo limit / upgrade prompt
- Exit confirm popup
- Game over popup ve alt butonlari
- Campaign level complete / failed popup'lari
- Tutorial overlay kartlari ve lesson paneli
- Menu icindeki ilgili modal aksiyon butonlari
- `retro_style` ve `ui_components` uzerinden cizilen diger popup paneller

## Onerilen V2 Dogrulama

Port sonrasi su popup'lari elle kontrol edin:

- Game Over
- Exit Confirm
- Demo/Store/Locked Mode prompt benzeri paneller
- Campaign level complete
- Campaign level failed
- Tutorial veya lesson popup'lari
- Online pause / lobby / game over panelleri

Beklenen sonuc:

- Panelin ust bolumunde yari saydam acik renkli bant gorunmemeli
- Hover butonlarin ust kenarinda tek cizgilik parlama gorunmemeli
- Header bandi varsa yalnizca koyu zemin ve normal accent cizgisi kalmali
