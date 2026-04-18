# Plan: Yerel PvP ve Yerel Co-op Icin Cift Gamepad Destegi

**Created:** 2026-04-18
**Status:** Draft - Ready for Review

## Ozet

Bu planin amaci, yerel PvP ve yerel Co-op (endless + coop_campaign akisina etkileri dahil) icin ayni anda 2 gamepad ile stabil oynanisi saglamaktir.

Mevcut sistemde gamepad girisi global bir katmanda toplanip sentetik klavye eventlerine cevriliyor. Ancak bu eventler tek bir aktif gamepad semantigi ile uretildigi ve oyuncu kimligi tasimadigi icin PvP/Co-op tarafinda P1/P2 ayrimi guvenli yapilamiyor.

Planin ana stratejisi:

- Mevcut sentetik event mimarisini komple degistirmeden genisletmek.
- Her gamepad icin oyuncu slotu (P1/P2) kavrami eklemek.
- Oyun ici action eventlerini oyuncu slotuna gore dogru player key mapping ile uretmek.
- PvP/Co-op tarafinda gamepad kaynakli eventleri oyuncu kapsamina gore ele almak.
- Ayarlar ekraninda oyuncu-slot atama UX'i eklemek (fazli rollout).

## Mevcut Durum Analizi

### Dogrulanmis teknik kisitlar

1. `GamepadManager` action query metodlari tek aktif kontrolcu semantigine dayaniyor:
   - `get_active_gamepad()` ilk aktif cihazi donduruyor.
   - `is_action_pressed()` ve `was_action_just_pressed()` bu tek cihaza bakiyor.
2. Sentetik KEY event uretiminde kaynak cihaz/oyuncu metadata'si yok:
   - `_make_key_event()` su anda sadece `from_gamepad=True` tasiyor.
   - Eventte `gamepad_player` benzeri alan yok.
3. Gamepad -> key map global ve oyuncudan bagimsiz:
   - `ACTION_TO_KEY` tek bir map.
   - Oyun ici action'lar cihazdan bagimsiz ayni key'lere cevriliyor.
4. PvP/Co-op input cozumu keyboard key tabanli ve oyuncu ayirimi key map ile yapiliyor:
   - P1/P2 key setleri `pvp_controls` icinden okunuyor.
   - Event kaynak gamepad olsa da oynanis tarafinda oyuncu-kaynagi ayristirilmiyor.
5. Main loop gamepad update sonucunu global event kuy ruguna basiyor:
   - `gamepad_mgr.update(delta_ms)` sonucu tum state'lerde `pygame.event.post(...)` ile yayinlaniyor.

### Ilgili dosyalar

- `src/gamepad_manager.py`
- `src/main.py`
- `src/pvp_game.py`
- `src/coop_game.py`
- `src/campaign/coop_campaign_mode.py`
- `src/settings_manager.py`
- `src/settings_screen_tabbed.py`
- `tests/test_coop.py`
- `tests/test_ingame_esc_opens_pause_menu.py`
- `tests/test_gamepad_mouse_emulation.py`

## Hedefler

1. Iki gamepad bagli iken:
   - Gamepad-A sadece P1'i,
   - Gamepad-B sadece P2'yi kontrol etsin.
2. PvP ve yerel Co-op oyun akislari icinde P1/P2 input karismasi olmasin.
3. Pause/menu gibi ortak aksiyonlar deterministic calissin.
4. Cihaz tak-cikar durumunda slot atamasi guvenli fallback versin.
5. Tek gamepad, klavye ve mevcut single-player/game/menu davranislari bozulmasin.

## Non-Goals

1. Online PvP / Online Co-op input mimarisini bu fazda degistirmek.
2. 3+ gamepad ile cok oyunculu destek.
3. Tum oyun ici ekranlarda yeni UI redesign.
4. Gamepad action modelini tamamen custom event bus'a tasimak.

## Onerilen Mimari

### 1) Oyuncu-slot atama katmani

`GamepadManager` icine yerel coklu oyun oturumu icin assignment katmani eklenir:

- `local_mode`: `none | pvp | coop`
- `player_slots`: `{1: instance_id|None, 2: instance_id|None}`
- `auto_assign`: ilk iki aktif gamepad'i P1/P2'ye ata
- `lock_assignment`: oyun basladiktan sonra hot-plug davranisini kontrollu yonet

Atama anahtari olarak cihazin `instance_id` degeri kullanilir. Bu, Windows tarafindaki raw joystick index degiskenligine daha dayaniklidir.

### 2) Oyun ici action routing

Mevcut global action->key cevirimi korunur ancak local multiplayer modunda oyuncu-slot bazli ceviri eklenir:

- P1 icin action key hedefi: runtime `pvp_controls['player1'][action]`
- P2 icin action key hedefi: runtime `pvp_controls['player2'][action]`

Not:

- Co-op zaten `pvp` tabanli oyuncu kontrol kaynaklarini kullandigi icin ayni mekanizma hem PvP hem Co-op icin ortak kullanilabilir.

### 3) Event metadata genisletmesi

`_make_key_event()` ve mouse click eventleri opsiyonel metadata alacak sekilde genisletilir:

- `from_gamepad=True`
- `gamepad_context`
- `gamepad_instance_id`
- `gamepad_player` (1 veya 2)

Bu metadata, collision durumlarinda PvP/Co-op tarafinda hangi oyuncu blogunun calisacagini netlestirmek icin kullanilir.

### 4) Main state entegrasyonu

Main loop gamepad context ayari yerel coklu modlari acik tanimlar:

- `pvp` state: `local_mode='pvp'`, context `game/menu`
- `coop` state: `local_mode='coop'`, context `game/menu`
- `coop_campaign` state: coop ile ayni input politikasina alinmali
- Diger state'lerde `local_mode='none'`

## Fazli Uygulama Plani

### Faz 0 - Scope Kilidi ve API Taslagi

**Hedef:** Implementation oncesi net sozlesme

**Dosyalar:**

- `plans/2026-04-18-yerel-pvp-coop-cift-gamepad-destegi-plan.md` (bu dokuman)

**Isler:**

1. Local dual-gamepad davranis sozlesmesini sabitle.
2. Slot assignment fallback kurallarini netlestir.
3. Keyboard + gamepad karma modunda oncelik kurallarini belirle.

**Kabul Kriterleri:**

- [ ] P1/P2 ownership kurallari yazili ve net.
- [ ] Cihaz unplug/replug durumunda beklenen davranis tanimli.

---

### Faz 1 - GamepadManager Coklu Cihaz Temeli

**Hedef:** Cihazi oyuncuya baglayan cekirdek altyapi

**Dosyalar:**

- `src/gamepad_manager.py`

**Isler:**

1. Player slot assignment state ve helper API'leri ekle:
   - `set_local_mode(...)`
   - `auto_assign_players(...)`
   - `set_player_device(...)`
   - `get_player_device_map(...)`
2. Device list/identity helperlari ekle (UI'da listelenecek kadar).
3. Assignment invalidation ve hot-plug recovery akisini ekle.

**Kabul Kriterleri:**

- [ ] Iki gamepad bagli iken stabil P1/P2 assignment olusur.
- [ ] Bir gamepad cikarsa slot deterministic fallback alir.

---

### Faz 2 - Oyun Ici Action Routing ve Event Metadata

**Hedef:** Her gamepadin dogru oyuncu aksiyonunu tetiklemesi

**Dosyalar:**

- `src/gamepad_manager.py`

**Isler:**

1. `update()` pipeline'inda game event uretimini player-slot aware hale getir.
2. `ACTION_TO_KEY` kullanimini local mode'da player-specific key target ile override et.
3. `_make_key_event()` metadata genisletmesini yap.
4. D-pad/stick repeat eventlerinde de player-slot route uygulansin.
5. Trigger ve button eventlerinde secondary binding davranisi korunur.

**Kabul Kriterleri:**

- [ ] P1 gamepad hareketleri P2 boarduna etki etmez.
- [ ] P2 gamepad hareketleri P1 boarduna etki etmez.
- [ ] Menu context davranisi bozulmaz.

---

### Faz 3 - PvP Input Entegrasyonu

**Hedef:** PvP handle_input akisini player metadata ile guvenli hale getirmek

**Dosyalar:**

- `src/pvp_game.py`

**Isler:**

1. KEYDOWN/KEYUP handlingde gamepad kaynakli eventler icin oyuncu kapsami helper'i ekle.
2. Event `gamepad_player=1` ise sadece P1 blogu; `2` ise sadece P2 blogu calissin.
3. Metadata olmayan eventlerde mevcut legacy davranis korunsun.
4. Pause/game_over click guardlarinin mevcut `from_gamepad` davranisi korunur.

**Kabul Kriterleri:**

- [ ] Ayni key collision olsa bile oyuncu kapsami bozulmaz.
- [ ] PvP pause/menu/game_over akislari regress etmez.

---

### Faz 4 - Co-op ve Co-op Campaign Entegrasyonu

**Hedef:** Co-op tarafinda da ayni oyuncu-route garantisi

**Dosyalar:**

- `src/coop_game.py`
- `src/campaign/coop_campaign_mode.py`
- `src/main.py`

**Isler:**

1. `CoopGame.handle_input()` icinde PvP ile ayni oyuncu-kapsam filtresi.
2. `coop_campaign` state icin gamepad context/local_mode dogru set edilir.
3. Co-op campaign super handle_input zincirinde yeni metadata yolunun calistigi dogrulanir.

**Kabul Kriterleri:**

- [ ] Endless co-opta iki gamepad ayri oyunculari kontrol eder.
- [ ] Coop campaignde input context dogru (menu degil game) calisir.

---

### Faz 5 - Ayarlar ve UX

**Hedef:** Oyuncularin slot atamasini gorup degistirebilmesi

**Dosyalar:**

- `src/settings_manager.py`
- `src/settings_screen_tabbed.py`
- gerekirse `src/localization.py`

**Isler:**

1. Persist edilen local dual-gamepad assignment ayar alanlari ekle.
2. Controls tabina assignment selector satirlari ekle:
   - `P1 Controller`
   - `P2 Controller`
   - `Auto Assign` toggle
3. Cihaz bagli degilse okunur fallback label goster.
4. reload path'te `reload_gamepad_settings()` ve assignment senkronu yap.

**Kabul Kriterleri:**

- [ ] Atamalar kaydedilir ve restart sonrasi geri gelir.
- [ ] Bagli cihaz degisince UI tutarli fallback verir.

---

### Faz 6 - Test Sertlestirme ve Rollout

**Hedef:** Regressionsiz yayin

**Dosyalar (yeni testler):**

- `tests/test_local_dual_gamepad_assignment.py`
- `tests/test_pvp_dual_gamepad_player_routing.py`
- `tests/test_coop_dual_gamepad_player_routing.py`
- `tests/test_coop_campaign_dual_gamepad_context.py`
- `tests/test_gamepad_unplug_reassign_fallback.py`
- `tests/test_settings_dual_gamepad_assignment_persist.py`

**Ek test etkisi:**

- `tests/test_coop.py`
- `tests/test_ingame_esc_opens_pause_menu.py`
- `tests/test_gamepad_mouse_emulation.py`

**Kabul Kriterleri:**

- [ ] Tanimli testler yesil.
- [ ] Manuel smoke matrix (Xbox+Xbox, Xbox+PS, tek gamepad+keyboard) geciyor.

## Riskler ve Azaltim

1. Windows raw/canonical mapping sapmasi:
   - Azaltim: capture ve event normalize helperlarini kullanmaya devam et.
2. Event collision ve cift tetikleme:
   - Azaltim: `gamepad_player` metadata + oyuncu kapsami filtresi.
3. Legacy davranis bozulmasi:
   - Azaltim: metadata olmayan eventlerde fallback legacy path.
4. Coop campaign context uyumsuzlugu:
   - Azaltim: main state context tablosunda explicit `coop_campaign` destegi.

## Rollout Stratejisi

1. Internal branchte Faz 1-2 ile headless test + local smoke.
2. Faz 3-4 sonrasi PvP/Co-op canli oynanis dogrulamasi.
3. Faz 5 UI eklemesi ile user-facing beta.
4. Faz 6 test kilidi ve release.

## Acik Sorular

1. V1'de per-player gamepad action binding gerekli mi, yoksa global gamepad binding + player route yeterli mi?
2. P1/P2 ayni fiziksel key'e map edilirse (custom keybind collision) oyunu strict metadata ile mi yoksa mevcut key semantigiyle mi calistiralim?
3. Auto-assign kuralinda son aktif gamepad mi, baglanma sirasi mi oncelikli olsun?

## Onerilen V1 Karari

- V1 icin: global gamepad binding + player-slot routing + assignment UI.
- Per-player gamepad binding (ayri profile) V1.1'e birakilsin.

Bu karar, blast radius'i dusurur ve mevcut pvp/co-op keyboard tabanli input mimarisini en az degisiklikle cift gamepad'e genisletir.
