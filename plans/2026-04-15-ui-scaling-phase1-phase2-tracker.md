# UI Scaling Phase 1-2 Tracker

Created: 2026-04-15
Status: Phase 1-2 applied, targeted validation complete

## Scope

Bu dosya, Retina ve buyuk ekran olcekleme calismasinin Phase 1 ve Phase 2 uygulama durumunu takip eder.

Bu turda hedeflenen alanlar:

- gameplay occupancy politikasini merkezilesirmek
- base single-player board ve HUD geometri tavanlarini yumusak sekilde buyutmek
- coop layout icin ayni buyume politikasini uygulamak
- mevcut akislarda sert kirik olusup olusmadigini test etmek

Bu turda bilincli olarak kapsam disi birakilan alanlar:

- raw popup ailesinin effective-size migration'i
- menu modal/content migration'i
- overlay/pause/game-over popup rect zincirinin tam yeniden tasarimi

## Implemented

### 1. Shared gameplay layout policy eklendi

Dosya:

- [src/gameplay_layout.py](src/gameplay_layout.py)

Eklenenler:

- `get_display_pixel_ratio(...)`
- `compute_single_player_layout(...)`
- `compute_coop_layout(...)`
- `SinglePlayerLayoutMetrics`
- `CoopLayoutMetrics`

Temel karar:

- layout karari logical/effective size uzerinden veriliyor
- final draw geometriği active/raw surface pikseline projekte ediliyor
- bu sayede Retina backing surface board'u kuculten yanlis cap etkisi azaltildi

### 2. Base Game Phase 1-2 entegrasyonu yapildi

Ana degisiklikler:

- [src/game.py](src/game.py#L268) `_display_pixel_ratio()`
- [src/game.py](src/game.py#L271) `_get_gameplay_layout_metrics()`
- [src/game.py](src/game.py#L313) `_get_right_hud_panel_metrics(...)`
- [src/game.py](src/game.py#L1722) `update_fonts()`
- [src/game.py](src/game.py#L1732) `get_cell_size()`
- [src/game.py](src/game.py#L1736) `get_board_offset()`
- [src/game.py](src/game.py#L4424) `_draw_right_hud_panel(...)`

Etkisi:

- classic single-player icin `40 px` hucre tavani buyuk ekranlarda kontrollu sekilde acildi
- sag HUD paneli `220 px` ust sinirina takilmadan buyuyebiliyor
- board geometri ve HUD panel karari ayni merkezi helper'dan geliyor
- public call surface korunuyor: `get_cell_size()` ve `get_board_offset()` hala ayni isimlerle kullaniliyor

### 3. CoopGame Phase 1-2 entegrasyonu yapildi

Ana degisiklikler:

- [src/coop_game.py](src/coop_game.py#L134) `_active_ui_size()`
- [src/coop_game.py](src/coop_game.py#L147) `_effective_ui_size()`
- [src/coop_game.py](src/coop_game.py#L170) `_display_pixel_ratio()`
- [src/coop_game.py](src/coop_game.py#L173) `_ui_scale()`
- [src/coop_game.py](src/coop_game.py#L2662) `_calculate_layout()`
- [src/coop_game.py](src/coop_game.py#L2902) `_draw_side_panels(...)`

Etkisi:

- coop board `40 px` tavani buyuk ekranlarda kontrollu sekilde asabiliyor
- side panel `120 px` baseline'i buyuk ekranlarda buyuyebiliyor
- card preview ve hold panelleri yeni panel genisligini gercekten kullanmaya basladi

## Validation

### Gecen hedefli regresyonlar

Calistirildi ve gecti:

- `tests/test_phase8_overlay_ui_scaling.py`
- `tests/test_coop.py`
- `tests/test_platform_effective_ui_size.py`
- `tests/test_phase3_ui_scaling.py`
- `tests/test_phase7_campaign_hud_ui_scaling.py`
- `tests/test_phase8_main_popup_ui_scaling.py`

Toplam gecerli toplu kosu:

- `113 passed`

Ek dolayli akıs kontrolleri:

- `tests/test_phase8_tutorial_ui_scaling.py` -> gecti
- `tests/test_coop_campaign.py` -> gecti
- `tests/test_phase7_campaign_hud_ui_scaling.py` tek basina -> gecti

### Bu turda eklenen regression coverage

Base game tarafinda:

- [tests/test_phase8_overlay_ui_scaling.py](tests/test_phase8_overlay_ui_scaling.py#L698) buyuk ekranda `40 px` legacy cap asiliyor mu
- [tests/test_phase8_overlay_ui_scaling.py](tests/test_phase8_overlay_ui_scaling.py#L711) Retina effective->raw projeksiyonu dogru mu
- [tests/test_phase8_overlay_ui_scaling.py](tests/test_phase8_overlay_ui_scaling.py#L529) sag HUD paneli buyuyebiliyor mu

Coop tarafinda:

- [tests/test_coop.py](tests/test_coop.py#L632) buyuk ekranda cell ve side panel buyuyor mu
- [tests/test_coop.py](tests/test_coop.py#L646) Retina effective->raw projeksiyonu coop'ta da dogru mu

## Review Findings

### Confirmed product breakage

Bu inceleme turunda Phase 1-2 degisikliklerinden dogrudan kaynaklanan teyitli bir runtime kirigi bulunmadi.

Base game, coop, tutorial, coop campaign ve campaign HUD icin hedefli regresyonlar temiz gecti.

### Residual risks

1. [src/game.py](src/game.py#L4424) disindaki ozel HUD override yollari tam olarak ayni merkezi policy'ye tasinmis degil.
   Ornekler: `HardcoreMode`, `CampaignMode`, `MysteryMode`.
   Mevcut testler gecti, ama bunlar sonraki fazlarda tekrar audit edilmeli.

2. [src/gameplay_layout.py](src/gameplay_layout.py#L92) tek oyunculu minimum hucre boyutunu `14` altina dusurmuyor.
   Mevcut minimum pencere boyutu ve ana modlar icin sorun gorunmedi; yine de sira disi uzun board konfigleri varsa izlenmeli.

3. Phase 3 henuz uygulanmadi.
   Popup, overlay ve menu content tarafinda raw helper zinciri devam ediyor.

## Unrelated test/repo issues discovered during review

Bu iki konu Phase 1-2 implementasyonundan bagimsiz gorunuyor, ama takipte tutulmali:

1. Tam pytest gorevi hala [tests/test_main_persist_active_game_run.py](tests/test_main_persist_active_game_run.py#L11) toplama asamasinda durabiliyor.
   Zincir: [src/main.py](src/main.py#L193) icindeki `from campaign import CampaignMode, CampaignLevelSelect` fallback import yolu.

2. [tests/test_coop_campaign.py](tests/test_coop_campaign.py#L127) icindeki `UIColors` stub'i eksik alanlar tanimliyor.
   Bu dosya ile [tests/test_phase7_campaign_hud_ui_scaling.py](tests/test_phase7_campaign_hud_ui_scaling.py) ayni pytest process'inde belirli sirayla kosunca order-dependent import hatasi olusabiliyor.
   Tek basina kosuldugunda campaign HUD testi geciyor.

## Follow-up checklist

- [x] Shared gameplay occupancy helper eklendi
- [x] Base Game board/HUD layout bu helper'a baglandi
- [x] Coop layout bu helper'a baglandi
- [x] Buyuk ekran regression testleri eklendi
- [x] Retina effective->raw projection regression testleri eklendi
- [ ] Popup/overlay/menu migration Phase 3 baslatilacak
- [ ] Campaign ve hardcore gibi ozel HUD override yollari ortak policy ile daha siki hizalanacak
- [ ] Tam pytest kosusunu bloklayan bagimsiz import/test-order sorunlari ayiklanacak

## Quick status

Phase 1-2 sonucunda oyun alani buyuk ekranlarda gercekten daha fazla alan kullaniyor ve Retina/backing surface farki gameplay geometriyi daha az bozuyor.

Bu turdaki degisiklikler kontrollu ve test destekli ilerledi. Kalan ana is Phase 3: popup, overlay ve menu zincirini ayni mantikla temizlemek.