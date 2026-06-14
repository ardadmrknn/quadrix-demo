# High-Density Ekranlarda Kucuk Gorunme Sorunu - Arastirma ve Cozum Plani

## 1. Problem Ozeti

Kullanici raporu su paterni gosteriyor:

- 16 inc 2560x1660 ekranlarda oyun hala kucuk gorunuyor.
- 16.1 inc 1920x1080 ekranlarda oyun tum ekrana daha dogal oturuyor.
- MacBook Air M2 tarafinda dahili 13.6 inc ekran kabul edilebilir gorunurken, 2560x1660 sinifi ekranlar gibi davranan senaryolarda oyun kucuk kaliyor.

Bu tablo, yalnizca tek bir ekrandaki stale rect/font hatasina degil, cozumunurluk bazli UI olcekleme politikasinin yuksek piksel yogunluklu ekranlarda fiziksel boyutu koruyamamasina isaret ediyor.

## 2. Arastirma Sonucu

### 2.1 Windows tarafindaki temel neden

`src/platform_utils.py` icinde Windows acilis akisi su sekilde:

- `_init_windows_dpi_awareness()` ile process `SetProcessDpiAwareness(2)` seviyesine cekiliyor.
- Borderless fullscreen yaratilirken `create_display(...)` icinde `_get_windows_physical_resolution()` cagriliyor.
- Bu yardimci `GetSystemMetrics(0/1)` ile fiziksel piksel cozunurlugunu donuyor.

Sonuc:

- Isletim sistemi 125% / 150% / 175% display scaling kullansa bile oyun UI olcegini efektif desktop boyutuna gore degil, ham fiziksel piksele gore hesapliyor.
- 2560x1660 gibi panellerde UI 1920x1080 referansina gore biraz buyuyor ama fiziksel boyutu koruyacak kadar buyumuyor.
- 16 inc 2560x1660 panel ile 16.1 inc 1920x1080 panel arasindaki asil fark PPI/yogunluk farki oldugu icin, sadece fiziksel pikseli referans alan mevcut formuller kullaniciya kucuk gorunuyor.

### 2.2 macOS tarafindaki temel neden

`src/platform_utils.py:get_native_resolution()` macOS'ta logical point boyutunu donmeye calisiyor. Bu dahili Retina ekranda yardimci oluyor.

Ancak UI tarafinda cogu ekran hala su yoldan olcek aliyor:

- `screen.get_size()`
- `pygame.display.Info().current_w/current_h`
- sabit `1366x768` veya `1920x1080` referanslari

Bu yaklasim iki nedenle yetersiz:

1. Harici yuksek cozumunurluklu ama logical olarak da buyuk ekranlarda UI yine ham buyukluk uzerinden hesap yapiliyor.
2. Fiziksel boyutu koruyan bir `effective desktop size` kavrami yok; sadece mevcut ekran boyutu var.

Ek not:

- Daha onceki `plans/pygame_ce_migration_research.md` arastirmasi, pygame software renderer tarafinda HiDPI'nin SDL/renderer katmaninda dogrudan cozulmedigini zaten not ediyor.
- Yani bu sorun tek basina `SDL_VIDEO_HIGHDPI_DISABLED` veya `ALLOW_HIGHDPI` ile kapanacak bir sorun sinifi degil.

### 2.3 Son faz duzenlemeleri bu sorunu neden kapatmadi

Yakindaki Faz 3-8 UI scaling duzenlemeleri su problemi cozmeye odaklandi:

- stale `window_width/window_height`
- yanlis surface'e bagli popup/layout
- ekran rebind eksikleri
- overlay/HUD/popup tutarsizligi

Bu degisiklikler buyuk oranda `active canvas` ya da `screen.get_size()` otoritesine gecirdi.

Bu dogru bir tutarlilik duzeltmesiydi, ama su problemi cozmuyor:

- `active canvas` halen yuksek yogunluklu ekranda kullanici algisina gore fazla buyuk bir boyut olabilir.
- Formuller fiziksel boyut / effective desktop / OS scaling bilgisini kullanmadigi icin, tutarli ama yine de kucuk gorunen bir UI uretebilir.

Ozet:

- Son duzenlemeler stale-size buglarini cozddu.
- Ama kullanicinin rapor ettigi "16 inc 2560x1660 ekranda hala kucuk" problemi buyuk ihtimalle hala acik.
- Yani son dalga bu sorunun kok nedenini kapatmadi.

## 3. Kod Tabaninda Etkilenen Katmanlar

Sorun tek bir dosyada degil, uc katmanda dagiliyor.

### Katman A - Display olusturma ve monitor boyutu secimi

- `src/platform_utils.py`
  - `_init_windows_dpi_awareness()`
  - `_get_windows_physical_resolution()`
  - `get_native_resolution()`
  - `create_display()`

### Katman B - Genel UI scale helper'lari

- `src/ui_scaling.py`
- `src/main.py:_fullscreen_popup_scale()`

### Katman C - Ekranlarin yerel `_ui_scale()` / `_active_ui_size()` wrapper'lari

Onemli ornekler:

- `src/menu.py`
- `src/game.py`
- `src/tutorial.py`
- `src/guide_screen.py`
- `src/graphics_menu.py`
- `src/settings_screen_tabbed.py`
- `src/user_screens.py`
- `src/extras_menu.py`
- `src/campaign/level_select.py`
- `src/pvp_game.py`
- `src/online_pvp_game.py`

Ozellikle `menu.py` ve `game.py` kritik, cunku kullanicinin ilk algisi burada olusuyor.

## 4. Kisa Teknik Teshis

Sorunun kok modeli su:

1. Uygulama borderless/fullscreen yuzeyi aciyor.
2. UI olcekleri cogunlukla `screen.get_size()` veya benzeri cozumunurluk verisinden turetiliyor.
3. Bu veri, kullanicinin algiladigi fiziksel boyutu veya isletim sisteminin effective UI scaling'ini temsil etmiyor.
4. Max clamp degerleri (`1.12`, `1.16`, `1.18`, `1.20`) 1080p uzeri panellerde fiziksel farki telafi etmeye yetmiyor.
5. Sonuc: layout dogru olabilir ama fiziksel olarak kucuk gorunur.

## 5. Cozum Stratejisi

Ana ilke:

- Cizim yuzeyi ve mouse/particle geometri hesaplari icin fiziksel surface boyutu korunacak.
- Font, panel, padding ve genel UI okunabilirlik olcegi icin `effective UI size` kullanilacak.

Yani tek bir "screen size" kavrami yerine iki kavram olacak:

1. `render surface size`
2. `effective ui size`

## 6. Onerilen Uygulama Plani

### Faz 1 - Platform katmanina effective UI size yardimcisi ekle

Hedef:

- Tum ekranlarin kullanabilecegi tek bir `effective UI size` kaynagi tanimlamak.

Onerilen eklemeler:

- `src/platform_utils.py`
  - yeni yardimci: `get_effective_ui_size(screen=None)`
  - yeni yardimci: `get_window_logical_size(screen=None)` veya esdeger ad
  - Windows icin gerekirse `GetDpiForSystem` veya `GetScaleFactorForMonitor` tabanli effective desktop hesabi

Beklenen davranis:

- Windows 2560x1660 + %150 scaling gibi durumda effective UI size, fiziksel 2560x1660 yerine yaklasik logical/effective desktop boyutuna yakin donmeli.
- macOS dahili Retina ekranda logical point boyutu korunmali.
- macOS harici yuksek cozumunurluklu ekranlarda da UI scale fiziksel pikselle dogrudan sisirilmemeli.

Not:

- Bu helper render surface boyutunun yerine gecmeyecek.
- Sadece UI scale hesaplarinin girdisi olacak.

Uygulama notu (2026-04-07 / Faz 1 baslangici):

- `src/platform_utils.py` icine `get_window_logical_size(screen=None)` ve `get_effective_ui_size(screen=None)` eklendi.
- Capraz-faz uyumluluk auditinde Windows yolunda sistem DPI yerine pencereye bagli DPI kullanimi gerektigi goruldu; helper `GetDpiForWindow` / monitor fallback zinciriyle guncellendi.
- Ayni auditte `get_window_size()` zaten logical boyut donduren build'lerde ikinci kez DPI bolmesi yapilmamasi gerektigi goruldu; effective helper sadece window size ile surface size ayniysa ek normalizasyon yapiyor.
- Gelecek fazlarda stale display referansi riskini azaltmak icin helper'lara acik `display_surface=` niyeti eklendi; offscreen surface'ler normalize yoluna sokulmuyor.
- `tests/test_platform_effective_ui_size.py` eklendi; logical-window, Windows DPI ve offscreen-surface korunumu senaryolari kilitlendi.
- Hedef platform katmani regresyonu olarak `tests/test_platform_effective_ui_size.py` + `tests/test_platform_utils_display_toggle.py` birlikte `26 passed` gecti.
- Faz 3-8 UI scaling regresyon paketi (`tests/test_ui_scaling.py` + phase3-8 dosyalari) `90 passed` ile helper degisikliginin mevcut migration dalgalarini bozmadigini dogruladi.
- Tam pytest kosusunda bu fazdan bagimsiz gorunen `tests/test_steam_net_bridge_private_metadata_source.py` beklentisi nedeniyle `1 failed, 583 passed, 6 skipped` sonucu alindi.

### Faz 2 - Ortak scale helper'larini effective size ile uyumlu hale getir

Hedef:

- `src/ui_scaling.py` ve merkezi wrapper'larin effective UI size ile kullanilabilir hale gelmesi.

Onerilen yaklasim:

- `ui_scaling.py` icindeki mevcut API'leri geriye donuk bozmadan koru.
- Yeni bir opt-in yardimci ekle:
  - `get_effective_scale(...)`
  - veya `resolve_ui_scale_size(...)`
- `_fullscreen_popup_scale()` gibi merkezi wrapper'lar bu yeni katmani kullansin.

Neden dogrudan `get_scale()` degistirilmemeli:

- Projede display surface disinda gecici/offscreen surface'lerde de size tabanli hesaplar var.
- Global davranisi tek hamlede degistirmek yan etki riskini yukseltiyor.

Uygulama notu (2026-04-07 / Faz 2):

- `src/ui_scaling.py` icine opt-in `resolve_ui_scale_size(...)`, `get_effective_scale(...)`, `get_effective_content_scale(...)` ve `get_effective_modal_scale(...)` eklendi; mevcut `get_scale(...)`, `get_content_scale(...)` ve `get_modal_scale(...)` semantigi korunarak geriye donuk uyumluluk bozulmadi.
- Capraz-faz auditinde `src/main.py::_fullscreen_popup_scale(...)` wrapper'inin Faz 3 oncesi tek basina effective-size yoluna alinmasinin popup ile cevre UI arasinda boyut ayrismasi urettigi goruldu; bu nedenle wrapper yeniden ham surface olcegine cekildi ve effective helper benimsenmesi Faz 3 ana-omurga migration'ina ertelendi.
- `tests/test_ui_scaling.py` icinde opt-in effective-size davranişi ve profile clamp uyumu testlerle kilitlendi.
- `tests/test_ui_scaling.py` icinde effective helper'in tuple/Rect benzeri non-surface girdilerde sessiz fallback yapmamasini saglayan guard testi eklendi.
- `tests/test_phase8_main_popup_ui_scaling.py` icinde popup wrapper'in Faz 3'e kadar ham surface olceginde kaldigini kilitleyen regression testi eklendi.
- Faz 2 uyumluluk revizyonu sonrasinda dar helper/popup/platform paketi (`tests/test_ui_scaling.py` + `tests/test_phase8_main_popup_ui_scaling.py` + `tests/test_platform_effective_ui_size.py`) `35 passed` gecti.
- Faz 1 + Faz 3-8 capraz UI scaling regresyon paketi (`tests/test_platform_effective_ui_size.py` + `tests/test_ui_scaling.py` + `tests/test_phase3_ui_scaling.py` + `tests/test_phase4_ui_scaling.py` + `tests/test_phase5_settings_ui_scaling.py` + `tests/test_phase6_campaign_modal_ui_scaling.py` + `tests/test_phase7_campaign_hud_ui_scaling.py` + `tests/test_phase8_main_popup_ui_scaling.py` + `tests/test_phase8_overlay_ui_scaling.py` + `tests/test_phase8_tutorial_ui_scaling.py`) `106 passed` ile temiz gecti.
- Faz 2 helper paketi (`tests/test_ui_scaling.py` + `tests/test_phase8_main_popup_ui_scaling.py` + Faz 1 platform testleri) `50 passed` gecti.
- Capraz Faz 1 + Faz 3-8 UI scaling regresyon paketi `121 passed` ile ortak helper degisikliginin onceki migration dalgalarini bozmadigini dogruladi.

### Faz 3 - En kritik ekranlari effective UI size'a tası

Ilk dalga:

- `src/menu.py`
- `src/game.py`
- `src/main.py`

Bu dalgada:

- ana menu `_ui_scale()`
- ana menu `_fullscreen_panel_scale()`
- gameplay `Game._ui_scale()`
- render geometriğini korumak icin `Game._active_ui_size()` ham active canvas otoritesinde kalir
- `main._fullscreen_popup_scale()` ve menu `_menu_panel_content_scale()` zinciri fiziksel surface container'lariyla birlikte tasinmadigi icin ham surface'te tutulur

effective UI size kullanacak sekilde, ancak fiziksel geometriyle dogrudan bagli zincirleri bozmadan guncellenecek.

Beklenen etki:

- Kullanici ilk anda gordugu ana menu ve oyun ici genel UI okumasi HiDPI display surface'te daha tutarli olcek kaynagindan beslenecek; popup ve dashboard mikro-icerik zinciri ise fiziksel kuculme regressyonu olusturmamak icin gecici olarak ham surface'te kalacak.

Uygulama notu (2026-04-07 / Faz 3):

- `src/menu.py` icinde `_effective_ui_size()` helper'i eklendi; helper yalnizca `self.screen` canli display surface ile ayniysa effective-size yoluna giriyor, aksi halde ham screen size'a donuyor.
- `src/menu.py::_ui_scale()` ve `src/menu.py::_fullscreen_panel_scale()` ortak `get_scale(...)` matematigini koruyarak yeni helper'a baglandi.
- Capraz auditte `src/menu.py::_menu_panel_content_scale()` wrapper'inin ham panel rect zinciri uzerinde effective-size ile fiziksel piksel olarak kuculme urettigi goruldu; bu nedenle dashboard icerik olcegi Faz 3'te ham surface bazinda tutuldu.
- `src/game.py` icinde render geometriği icin `_active_ui_size()` korunurken, yalniz UI scale icin ayri `_effective_ui_size()` helper'i eklendi ve `Game._ui_scale()` bu helper'a baglandi.
- `src/main.py::_fullscreen_popup_scale()` Faz 3 denemesinde effective-size ile popup panelini fiziksel olarak kuculttugu icin yeniden ham surface olceginde birakildi; popup geometri zinciri birlikte tasinmadan effective rollout acilmiyor.
- Faz 3 uyumluluk auditinin ikinci turunda `src/menu.py::_fullscreen_panel_scale()` ve `src/game.py` icindeki pause / quit / game-over overlay zincirlerinin de raw panel geometrisi kullandigi goruldu; bu nedenle menu fullscreen panelleri ham surface olcegine geri alindi ve oyun ici overlay/popup zinciri icin ayri `_overlay_ui_scale()` helper'i eklendi.
- `tests/test_phase3_ui_scaling.py` icine ana menu effective-size gating testleri eklendi.
- `tests/test_phase8_overlay_ui_scaling.py` icine `Game._ui_scale()` effective-size gating regression testi eklendi.
- `tests/test_phase8_overlay_ui_scaling.py` icine gameplay overlay/popup zincirinin ham surface scale'de kaldigini kilitleyen regression testi eklendi.
- `tests/test_phase8_main_popup_ui_scaling.py` icinde popup wrapper'in ham surface'te kaldigini kilitleyen Faz 3 regression testi guncellendi.
- Revize Faz 3 dar paketi (`tests/test_ui_scaling.py` + `tests/test_platform_effective_ui_size.py` + `tests/test_phase3_ui_scaling.py` + `tests/test_phase8_overlay_ui_scaling.py` + `tests/test_phase8_main_popup_ui_scaling.py`) `72 passed` ile gecti.
- Faz 3 uyumluluk duzeltmeleri sonrasinda dar paket `73 passed` ile tekrar gecti.
- Faz 3 uyumluluk duzeltmeleri sonrasinda capraz regresyon + pause smoke paketi (`tests/test_platform_effective_ui_size.py` + `tests/test_ui_scaling.py` + `tests/test_phase3_ui_scaling.py` + `tests/test_phase4_ui_scaling.py` + `tests/test_phase5_settings_ui_scaling.py` + `tests/test_phase6_campaign_modal_ui_scaling.py` + `tests/test_phase7_campaign_hud_ui_scaling.py` + `tests/test_phase8_main_popup_ui_scaling.py` + `tests/test_phase8_overlay_ui_scaling.py` + `tests/test_phase8_tutorial_ui_scaling.py` + `tests/test_menu_dashboard_tile_cache.py` + `tests/test_ingame_esc_opens_pause_menu.py`) `127 passed` ile temiz gecti.
- Kisa runtime smoke icin `main.py` baslatildi; Python traceback gorulmedi. Tek runtime uyari Steam istemcisi kapali oldugu icin `SteamAPI_InitFlat` IPC hatasiydi; menu muzik/arka plan/logo yukleme zinciri calisti.

### Faz 4 - Faz 3-8 migration ekranlarini yeni olcege uyarla

Ikinci dalga:

- `src/guide_screen.py`
- `src/graphics_menu.py`
- `src/settings_screen_tabbed.py`
- `src/user_screens.py`
- `src/extras_menu.py`
- `src/campaign/level_select.py`
- `src/tutorial.py`
- gerekirse `src/pvp_game.py` ve `src/online_pvp_game.py`

Bu ekranlarda yerel `_ui_scale()` wrapper'lari yeni effective size yardimcisina baglanacak.

Uygulama notu (2026-04-07 / Faz 4):

- Dusuk riskli safe-wave olarak `src/guide_screen.py`, `src/graphics_menu.py`, `src/settings_screen_tabbed.py` ve `src/extras_menu.py` icindeki yerel `_ui_scale()` wrapper'lari `get_effective_scale(...)` yoluna tasindi; mevcut ekran bazli referans boyutlari korunarak 1366x768 baseline sapmasi acilmadi.
- `src/user_screens.py` icindeki ortak `_get_user_screen_scale(...)` helper'i screen-benzeri girdilerde effective helper, tuple benzeri girdilerde raw helper kullanacak sekilde ayrildi; `UserSelectionScreen` ve `UserManagementScreen` ayni 1600x900 + readable floor ailesinde kaldi.
- Faz 4 uyumluluk auditinde `UserSelectionScreen` gecis animasyonunun `self.screen` degerini gecici offscreen surface ile degistirdigi ve effective-scale yolunu animation frame'lerinde raw scale'a dusurebildigi goruldu; bu nedenle gecis draw yolunda orijinal display surface `_ui_scale_surface` ile pinlendi.
- Ayni auditte `src/campaign/level_select.py` icindeki erken effective-size migration'inin `src/campaign/campaign_ui.py` modal olcegi ve `src/campaign/campaign_mode.py` HUD/content scale yolu hala raw iken akislar arasi boyut sicrama riski olusturdugu goruldu; bu nedenle `CampaignLevelSelect._get_ui_scale()` Faz 4 sonunda bilincli olarak tekrar ham `get_scale(...)` yoluna cekildi.
- Faz 4 kapanisinda screen-rebind davranisini daha gorunur ve testlenebilir hale getirmek icin `src/main.py` icine `_apply_screen_to_targets(...)` yardimcisi cikarildi; display recreate/recover sonrasinda settings/extras/guide/user screens gibi uzun omurlu ekran sahipleri ile user screens icindeki nested `avatar_editor.screen` referanslarinin yeni screen'i korudugu regression testi ile kilitlendi.
- `src/tutorial.py`, `src/pvp_game.py` ve `src/online_pvp_game.py` bu dalgada bilerek ertelendi; overlay/popup/gameplay zincirleri Faz 3 ve Faz 8 dersleri nedeniyle toplu geometri audit'i olmadan parcali effective rollout'a alinmiyor.
- Faz 4 hedefli regresyon paketi (`tests/test_phase3_ui_scaling.py` + `tests/test_phase4_ui_scaling.py` + `tests/test_phase5_settings_ui_scaling.py` + `tests/test_extras_includes_classic.py` + `tests/test_campaign_debug_unlock_all.py` + `tests/test_campaign_level_panel_keyboard.py` + `tests/test_ui_scaling.py` + `tests/test_platform_effective_ui_size.py` + `tests/test_phase8_main_popup_ui_scaling.py`) `92 passed` ile temiz gecti.
- Faz 1-8 capraz UI scaling regresyon paketi (`tests/test_platform_effective_ui_size.py` + `tests/test_ui_scaling.py` + `tests/test_phase3_ui_scaling.py` + `tests/test_phase4_ui_scaling.py` + `tests/test_phase5_settings_ui_scaling.py` + `tests/test_phase6_campaign_modal_ui_scaling.py` + `tests/test_phase7_campaign_hud_ui_scaling.py` + `tests/test_phase8_main_popup_ui_scaling.py` + `tests/test_phase8_overlay_ui_scaling.py` + `tests/test_phase8_tutorial_ui_scaling.py` + `tests/test_menu_dashboard_tile_cache.py` + `tests/test_ingame_esc_opens_pause_menu.py` + `tests/test_extras_includes_classic.py` + `tests/test_campaign_level_panel_keyboard.py` + `tests/test_campaign_debug_unlock_all.py`) `159 passed` ile temiz gecti.
- Kisa runtime smoke icin `main.py` tekrar baslatildi; Python traceback gorulmedi. Steam istemcisi kapali oldugu icin `SteamAPI_InitFlat` IPC uyarisi devam etti, fakat menu muzik/arka plan/logo init zinciri ve kapanis akisi normal calisti.
- Son closure review'unde bloklayici bulgu kalmadi; Faz 4 safe-wave onaylandi.

### Faz 5 - Clamp degerlerini yeniden kalibre et

Kok neden yalniz yanlis size secimi degil; bazi max clamp degerleri de yuksek yogunlukte fazla tutucu.

Bu yuzden Faz 1-4 sonrasi su alanlar tekrar kalibre edilmeli:

- `max_scale=1.12`
- `max_scale=1.16`
- `max_scale=1.18`
- `max_scale=1.20`

Kurallar:

- Once effective size duzeltmesi yapilacak.
- Hala kucuk kalan alan varsa clamp ayari ekran bazli revize edilecek.
- Tek hamlede tum projede ust limit buyutulmeyecek.

Uygulama notu (2026-04-07 / Faz 5):

- Faz 5 toplu/global clamp artisi olarak degil, effective-size yoluna gecmis ve hedef cihaz sinifinda gercekten cap'e carpan ekranlar icin dar bir kalibrasyon dalgasi olarak uygulandi.
- `src/menu.py` ve `src/game.py` icindeki genel effective UI wrapper'lari 1366x768 referansi korunarak `max_scale=1.24` seviyesine gevsetildi; ham overlay/popup helper'lari bilincli olarak dokunulmadan birakildi.
- `src/settings_screen_tabbed.py` icindeki tabbed settings ekrani yogun icerik ve kaydirma/input geometriği nedeniyle daha konservatif tutuldu; default effective clamp `1.16 -> 1.22` olarak guncellendi.
- `src/guide_screen.py`, `src/graphics_menu.py` ve `src/extras_menu.py` icindeki full-screen effective UI wrapper'lari `1.18 -> 1.24` seviyesine cekildi; mevcut 1366x768 referans ailesi korunarak daha buyuk logical/effective ekranlarda gereksiz erken tavanlama azaltildi.
- `src/user_screens.py` Faz 5 clamp dalgasinda bilincli olarak degistirilmedi; 1600x900 referans ailesi nedeniyle hedef high-density senaryoda zaten sert bir ust limite carpmiyordu.
- `src/campaign/level_select.py`, oyun ici raw overlay/popup zincirleri, tutorial ve PvP aileleri bu fazda bilincli olarak disarida tutuldu; bunlar ya raw geometri zincirine bagli ya da ayri faz boundary riski tasiyor.
- Faz 5 dogrudan regression testleri ile yeni cap degerleri kilitlendi: main menu/game genel UI icin `1.24`, settings icin `1.22`, guide/graphics/extras icin `1.24`.
- Dar Faz 5 yuzeyi (`tests/test_phase3_ui_scaling.py` + `tests/test_phase5_settings_ui_scaling.py` + `tests/test_extras_includes_classic.py` + `tests/test_phase8_overlay_ui_scaling.py`) `58 passed` ile gecti.
- Odakli UI scaling paketi (`tests/test_phase3_ui_scaling.py` + `tests/test_phase4_ui_scaling.py` + `tests/test_phase5_settings_ui_scaling.py` + `tests/test_extras_includes_classic.py` + `tests/test_campaign_debug_unlock_all.py` + `tests/test_campaign_level_panel_keyboard.py` + `tests/test_ui_scaling.py` + `tests/test_platform_effective_ui_size.py` + `tests/test_phase8_main_popup_ui_scaling.py` + `tests/test_phase8_overlay_ui_scaling.py`) `126 passed` ile temiz gecti.
- Faz 1-8 capraz UI scaling regresyon paketi `164 passed` ile temiz gecti.
- Kisa runtime smoke icin `main.py` baslatildi; Python traceback gorulmedi. Steam istemcisi kapali oldugu icin `SteamAPI_InitFlat` IPC uyarisi devam etti.
- Faz 5 final review'unde bloklayici bulgu cikmadi; raw overlay/popup ve campaign-level zincirlerinde goreli boyut farki artik sadece bilinen faz-siniri residual risk olarak kaydedildi.

### Faz 6 - Son mile fallback: manuel UI scale override

Eger bazi cihazlar hala kullanici beklentisinden kucuk buyuk kalirsa, son katman olarak ayara bagli bir UI override dusunulebilir:

- `ui_scale_override`
- `ui_scale_preset = compact / normal / large`

Bu, kok cozumu yerine gecmemeli; sadece cihazlar arasi ince ayar icin olmalı.

## 7. Test ve Dogrulama Plani

### Otomatik testler

Yeni testler:

- `tests/test_platform_effective_ui_size.py`
- `tests/test_ui_scaling_effective_size.py`

Kilitlemek gereken senaryolar:

1. Windows 1920x1080, scale 100%
   - effective size = 1920x1080
   - mevcut gorunus bozulmuyor

2. Windows 2560x1660, scale 150%
   - effective size fiziksel 2560x1660 olarak alinmiyor
   - UI scale 1920x1080 vakasina gore makul buyuyor

3. macOS built-in Retina
   - effective size logical points ile uyumlu kaliyor

4. macOS harici 2560x1660 sinifi ekran
   - UI scale ham fiziksel piksele karsi fazla kucuk kalmiyor

5. Offscreen surface kullanan helper yollar
   - yeni effective-size mantigi yanlislikla kart surface'i / gradient cache / popup snapshot gibi gecici surface'leri bozmayacak

### Manuel test matrisi

Zorunlu cihaz/senaryo listesi:

1. 16.1 inc 1920x1080 Windows laptop
2. 16 inc 2560x1660 Windows laptop
3. MacBook Air 13.6 dahili ekran
4. Mac tarafinda 2560x1660 davranisi veren ekran/senaryo

Her cihazda kontrol edilecek alanlar:

- ana menu
- extras
- settings
- guide
- campaign select
- oyun ici HUD
- pause / game-over popup
- tutorial prompt

## 8. Kabul Kriterleri

Bu is kapanmis sayilabilmesi icin:

- 2560x1660 sinifi ekranlarda oyun artik 1920x1080 laptopa gore belirgin bicimde kucuk hissettirmemeli.
- 1920x1080 iyi senaryosu bozulmamali.
- macOS dahili Retina gorunusu bozulmamali.
- Faz 3-8 UI scaling regression testleri yesil kalmali.

## 9. Sonuc

Mevcut bulguya gore problem hala acik.

Son Faz 3-8 duzenlemeleri:

- stale size
- yanlis surface
- popup rebind
- overlay/hud tutarsizligi

sinifindaki hatalari cozddu.

Ama kullanicinin tarif ettigi yuksek yogunluklu ekranda kucuk gorunme sorunu, `effective UI size` katmani eklenmeden kapanmayacak.

Dogru siralama su olmali:

1. platform katmaninda effective UI size yardimcisi
2. merkezi wrapper'lar
3. menu + game + popup ana omurgasi
4. kalan ekranlar
5. clamp kalibrasyonu
6. gerekirse manuel override
