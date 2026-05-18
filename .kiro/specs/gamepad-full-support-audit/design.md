# Gamepad Full-Support Audit — Technical Design

## 1. Yönetici Özeti

Quadrix'in tüm ekranları gamepad_manager.py üzerinden sentetik KEYDOWN/KEYUP event'leri alıyor. Bu sayede çoğu ekran "çalışıyor" görünüyor; ancak gerçek bir focus/navigation modeli olmadan, sağ stick mouse emülasyonuna veya raw MOUSEBUTTONDOWN'a bağımlı yüzeyler var. Bu doküman her ekranı dört sınıftan birine koyuyor, kök nedenleri belirliyor ve aşamalı modernizasyon planı sunuyor.

**Kritik bulgular:**
- Sniper overlay: mouse zorunlu (gamepad cursor yok).
- Future changer piece selection: mouse zorunlu (keyboard/gamepad seçim yok).
- Co-op campaign level select: mouse zorunlu (keyboard nav yok).
- Card workshop: sentetik klavye ile tam çalışıyor (cursor + space + enter).
- Kart seçim overlay: sentetik klavye ile çalışıyor (focus + enter + 1/2/3).
- Ana menü, settings, gameplay: sentetik klavye ile tam çalışıyor.
- Splash: tam gamepad (was_action_just_pressed polling).

---

## 2. Ekran Bazlı Audit Matrisi

| # | Ekran | Giriş Noktası | Dosya:Satır / Sembol | Input Modeli | Gamepad-Only? | Fallback | Risk | Gerekçe |
|---|-------|---------------|---------------------|--------------|---------------|----------|------|---------|
| 1 | Splash | main.py → SplashScreen.run() | splash_screen.py:295 `was_action_just_pressed('menu_confirm')` | **Tam gamepad** | ✅ Evet | — | Düşük | Kendi loop'unda gamepad pump + polling yapıyor. A=confirm. |
| 2 | Ana Menü (dashboard) | main.py → Menu | menu.py:780 `_get_nav_keys()` | Sentetik klavye | ✅ Evet | — | Düşük | D-pad→K_UP/DOWN, A→K_RETURN, B→K_ESCAPE. 2D panel grid nav var. |
| 3 | Extras (mod seçim) | menu.py → ExtrasMenu | extras_menu.py | Sentetik klavye | ✅ Evet | — | Düşük | Aynı sentetik pipeline. |
| 4 | Settings (sekmeli) | main.py → TabbedSettingsScreen | settings_screen_tabbed.py:454 | Sentetik klavye | ✅ Evet | — | Düşük | Tab: LB/RB→bracket. Satır: D-pad→arrows. Slot: L/R. Capture: buton. |
| 5 | Guide | guide_screen.py | guide_screen.py | Sentetik klavye | ✅ Evet | — | Düşük | Scroll: D-pad. Back: B→ESC. |
| 6 | Profile / User Select | user_selection_screen.py | user_selection_screen.py | Sentetik klavye | ✅ Evet | — | Düşük | Arrow nav + Enter. |
| 7 | Campaign Level Select | campaign_mode.py → LevelSelect | level_select.py:311 `handle_input` | Sentetik klavye | ✅ Evet | — | Düşük | Arrow nav (±1, ±5), Enter=play, ESC=back. Mouse da çalışır. |
| 8 | **Co-op Campaign Level Select** | coop_campaign_mode.py → CoopLevelSelect | coop_level_select.py:94 `handle_input` | **Sadece mouse** | ❌ Hayır | Mouse zorunlu | **Yüksek** | Keyboard nav yok; sadece MOUSEBUTTONDOWN + collidepoint. D-pad/Enter işlenmez. |
| 9 | Gameplay (tek oyunculu) | Game.handle_input | game.py:1873 | Sentetik klavye + polling | ✅ Evet | — | Düşük | D-pad→move, A→hard_drop, butonlar→hold/pause. is_direction_held polling. |
| 10 | Gameplay (Mystery/Card) | MysteryMode.handle_input | game_modes_extra.py:7350 | Sentetik klavye + polling | ✅ Evet | — | Düşük | Kart ability'leri is_action_pressed ile polling. |
| 11 | Pause overlay | Game.handle_input (show_exit_prompt) | game.py:1893 | Sentetik klavye + mouse fallback | ⚠️ Kısmen | Mouse fallback (buton tıklama) | Orta | ESC/Enter/Y/N klavye çalışır. Gamepad: B=kapat, A=onayla (normalize_gamepad_event_button). Mouse rect tıklama da var. |
| 12 | Game Over overlay | Game.handle_input | game.py:1940 | Mouse fallback gerekli | ⚠️ Kısmen | Mouse fallback | Orta | Peek butonu sadece MOUSEBUTTONDOWN. Restart/menu butonları mouse rect. Gamepad A→mouse click (pointer mode) ile çalışıyor ama native değil. |
| 13 | **Kart Seçim Overlay** | MysteryMode.handle_input | game_modes_extra.py:8564 `_handle_card_selection_keydown` | Sentetik klavye | ✅ Evet | — | Düşük | Focus nav: L/R/U/D→move_focus. Enter/Space→activate_focused. 1/2/3 direkt seçim. ESC=skip. Mouse click de çalışır. |
| 14 | **Sniper Overlay** | MysteryMode.handle_input | game_modes_extra.py:7410 | **Sadece mouse** | ❌ Hayır | Mouse zorunlu | **Yüksek** | Sadece MOUSEBUTTONDOWN + `_sniper_screen_to_cell(pos)`. Gamepad cursor/grid targeting yok. ESC=kapat tek gamepad yolu. |
| 15 | **Future Changer Piece Selection** | MysteryMode.handle_input | game_modes_extra.py:7340, 12052 `_handle_piece_selection_click` | **Sadece mouse** | ❌ Hayır | Mouse zorunlu | **Yüksek** | Sadece MOUSEBUTTONDOWN + rect collidepoint. Keyboard/gamepad seçim yok (ESC=iptal tek yol). |
| 16 | Card Workshop Popup | MysteryMode.handle_input | game_modes_extra.py:11380 `_handle_card_workshop_input` | Sentetik klavye | ✅ Evet | — | Düşük | Cursor: arrows. Place/remove: Space. Finish: Enter. ESC=kapat. Mouse grid click de var. |
| 17 | Legacy Gamepad Tab (menu.py) | Menu._is_gamepad_tab | menu.py:5831 | Legacy / stale | N/A | — | Düşük | Artık settings_screen_tabbed.py aktif. Bu kod ölü ama silinmemiş. Çakışma yok (farklı ekran). |
| 18 | Online PvP Lobby | online_pvp_game.py | online_pvp_game.py | Sentetik klavye | ✅ Evet | — | Düşük | Clipboard/code input klavye tabanlı. |
| 19 | Local PvP | pvp_game.py | pvp_game.py | Sentetik klavye | ✅ Evet | — | Düşük | İki klavye seti. Gamepad P1 gibi davranır. |
| 20 | Co-op Gameplay | coop_game.py | coop_game.py | Sentetik klavye | ✅ Evet | — | Düşük | Tek gamepad P1 kontrol eder. |

---

## 3. Bulgular (Önem Sırasıyla)

### 3.1 Akışı Kilitleyen (Gamepad-Only İmkansız)

**B1: Sniper Overlay — Mouse Zorunlu**
- Dosya: `game_modes_extra.py:7410-7440`
- Kök neden: `_sniper_screen_to_cell(pos)` mouse pixel koordinatı alıyor. Gamepad cursor state machine yok. Sağ stick mouse emülasyonu "çalışıyor" ama hassas değil (board hücreleri küçük).
- Etki: Keskin Nişancı kartı gamepad-only oyuncular için kullanılamaz.

**B2: Future Changer Piece Selection — Mouse Zorunlu**
- Dosya: `game_modes_extra.py:7340, 12052`
- Kök neden: `_handle_piece_selection_click(pos)` sadece MOUSEBUTTONDOWN + rect collidepoint. Keyboard/gamepad seçim mekanizması yok.
- Etki: Geleceği Değiştiren kartı gamepad-only oyuncular için kullanılamaz (ESC ile iptal tek yol).

**B3: Co-op Campaign Level Select — Mouse Zorunlu**
- Dosya: `coop_level_select.py:94-130`
- Kök neden: `handle_input` sadece MOUSEBUTTONDOWN + MOUSEMOTION işliyor. KEYDOWN dalında yalnızca ESC=back var. Arrow nav, Enter=play yok.
- Etki: Co-op kampanya gamepad-only başlatılamaz.

### 3.2 Mouse Fallback Zorunluluğu

**B4: Game Over Overlay — Butonlar Mouse Rect**
- Dosya: `game.py:1940+`
- Kök neden: Restart/menu butonları MOUSEBUTTONDOWN + collidepoint. Gamepad A→mouse click (pointer mode) ile çalışıyor ama native focus/confirm yok.
- Etki: Çalışıyor ama borçlu. Sağ stick pointer mode UX'i kötü.

### 3.3 UX Tutarsızlığı / Bakım Borcu

**B5: Pointer Mode A=Click Davranışı**
- Dosya: `gamepad_manager.py:1516-1600`
- Kök neden: `_menu_pointer_active` True iken A butonu K_RETURN yerine MOUSEBUTTONDOWN üretiyor. Bu, overlay'lerde (game over, pause) gerekli ama ana menüde gereksiz (zaten K_RETURN çalışıyor).
- Etki: Kullanıcı sağ stick'e dokunursa pointer mode aktifleşiyor; sonra A butonu beklenmedik şekilde "tıklama" yapıyor.

**B6: Legacy Gamepad Tab (menu.py:5831)**
- Dosya: `menu.py:5831-5920`
- Kök neden: Eski gamepad rebind UI hâlâ menu.py içinde yaşıyor. Aktif settings ekranı settings_screen_tabbed.py. İkisi arasında çakışma yok (farklı ekranlar) ama bakım borcu.
- Etki: Düşük. Ölü kod.

**B7: Prompt Glyph Tutarsızlığı**
- Dosya: `promptfont_support.py`, `gamepad_manager.py:get_button_label`
- Kök neden: Prompt glyph'leri ekran bazında farklı yollarla çözülüyor. Bazı ekranlar `get_action_prompt_display` kullanıyor, bazıları hardcoded "N tuşuna bas" yazıyor.
- Etki: Gamepad bağlıyken "N tuşuna bas" yerine "Y butonuna bas" gösterilmeli.

---

## 4. Açık Sorular / Belirsiz Alanlar

1. **Avatar editor** ve **piece workshop** (customize sekmesi) ekranları submenu olarak işaretli; gerçek input handler'ları bu audit'te doğrulanmadı. Muhtemelen mouse-heavy.
2. **Highscore screen** ve **leaderboard trailer** ekranları audit dışı bırakıldı (gameplay-critical değil).
3. **Tutorial runtime** (`tutorial_runtime.py`) gamepad desteği doğrulanmadı; muhtemelen sentetik klavye ile çalışıyor.
4. **Online PvP lobby code input** clipboard paste gerektiriyor; gamepad-only akış belirsiz.

---

## 5. Modernizasyon Yol Haritası (HLD)

### 5.1 Global Focus/Navigation Abstraction

**Mevcut:** Her ekran kendi `selected` index'i + `option_rects` listesi tutuyor. Ortak bir soyutlama yok.

**Hedef:** `FocusManager` sınıfı — her ekran `register_targets(rects)` ile navigasyon matrisini bildirsin. D-pad/stick input'ları otomatik olarak focus'u kaydırsın. Confirm/back action'ları merkezi olarak işlensin.

### 5.2 Selectable Target Registry

**Mevcut:** `option_rects` + `_selectable_indices` + `_keybind_slot_rects` gibi paralel listeler.

**Hedef:** Her target bir `FocusTarget(rect, action_on_confirm, section_id)` objesi olsun. Grid/list layout otomatik hesaplansın.

### 5.3 Confirm/Back/Tab Action Contract

**Mevcut:** `ACTION_TO_KEY` mapping + her ekranın kendi K_RETURN/K_ESCAPE handling'i.

**Hedef:** Ortak `GamepadAction` enum: `CONFIRM, BACK, TAB_NEXT, TAB_PREV, NAVIGATE_UP/DOWN/LEFT/RIGHT`. Her ekran bu action'ları handle etsin; mapping gamepad_manager'da kalsın.

### 5.4 Gamepad Prompt Glyph Standardizasyonu

**Mevcut:** `promptfont_support.py` + `get_action_prompt_display` + `render_action_prompt_surface`. Bazı ekranlar kullanıyor, bazıları hardcoded.

**Hedef:** Tüm "tuşa bas" mesajları `get_action_prompt_display(action, keyboard_fallback)` üzerinden geçsin. Gamepad bağlıyken otomatik olarak buton glyph'i gösterilsin.

### 5.5 Sağ Stick Mouse Emülasyonu Fallback Politikası

**Mevcut:** Her zaman aktif; pointer mode D-pad kullanılınca deaktif oluyor.

**Hedef:** Sağ stick emülasyonu "fallback" olarak korunsun ama ana UX olmasın. Native focus/navigation olan ekranlarda pointer mode otomatik deaktif olsun. Sadece mouse-zorunlu overlay'lerde (sniper, future changer — modernize edilene kadar) aktif kalsın.

### 5.6 Sniper Gamepad Cursor Tasarımı

**Mevcut:** Yok. Mouse zorunlu.

**Hedef:** `_sniper_cursor_x/y` (board hücre koordinatları). D-pad→hücre adımı. A→ateş. B→iptal. Cursor görsel: parlak border + crosshair. Mevcut mouse path bozulmaz (paralel input).

### 5.7 Settings/Keybind Capture Gamepad-Only Rebind

**Mevcut:** Zaten çalışıyor. `_apply_captured_gamepad_button` + `normalize_gamepad_event_button`. Hold-to-clear da eklendi.

**Hedef:** Mevcut yapı yeterli. Sadece prompt glyph'leri capture sırasında gösterilmeli ("LB'ye basın" vs "Butona basın").

### 5.8 Popup/Overlay Focus-First Navigation

**Mevcut:** Card selection overlay focus nav var. Sniper/future changer yok. Workshop var.

**Hedef:** Tüm popup'lar `FocusableOverlay` base class'ından türesin. Ortak: focus ring, confirm/back, directional nav.

---

## 6. Low-Level Design

### 6.1 FocusManager API (Pseudocode)

```python
class FocusTarget:
    rect: pygame.Rect
    id: str
    on_confirm: Callable | None
    on_back: Callable | None
    group: str  # "main", "tabs", "slots"

class FocusManager:
    targets: list[FocusTarget]
    focused_index: int
    
    def register(self, targets: list[FocusTarget]) -> None: ...
    def move(self, direction: str) -> None:  # 'up','down','left','right'
        # Nearest-neighbor in direction from current rect
        ...
    def confirm(self) -> Any:
        return self.targets[self.focused_index].on_confirm()
    def back(self) -> Any:
        return self.targets[self.focused_index].on_back()
    def get_focused_rect(self) -> pygame.Rect: ...
    def draw_focus_ring(self, screen: pygame.Surface) -> None: ...
```

### 6.2 Sniper Cursor State Machine

```
States: IDLE → ACTIVE → FIRING → IDLE
Transitions:
  IDLE + N_pressed (charges > 0) → ACTIVE
  ACTIVE + D-pad → move cursor (clamp to board)
  ACTIVE + A_pressed → if cell occupied: FIRING else: deny sound
  ACTIVE + B_pressed → IDLE (cancel)
  ACTIVE + ESC → IDLE (cancel)
  FIRING → execute_sniper_shot(cx, cy) → if charges > 0: ACTIVE else: IDLE

State variables:
  _sniper_cursor_x: int  # board column
  _sniper_cursor_y: int  # board row
  _sniper_cursor_active: bool
```

### 6.3 Future Changer Keyboard/Gamepad Nav

```python
# _piece_selection_active durumunda:
# Mevcut: sadece mouse click
# Eklenmesi gereken:
#   - _piece_selection_index: int (focused piece)
#   - LEFT/RIGHT: index ±1 (wrap)
#   - ENTER/SPACE/A: select focused piece
#   - ESC/B: cancel
```

### 6.4 Co-op Level Select Keyboard Nav

```python
# coop_level_select.py handle_input'a eklenmesi gereken:
# KEYDOWN:
#   K_LEFT: selected_level -= 1
#   K_RIGHT: selected_level += 1
#   K_UP: selected_level -= columns_per_row
#   K_DOWN: selected_level += columns_per_row
#   K_RETURN: if unlocked → play
#   K_1..K_5: world switch (campaign level_select ile aynı)
```

### 6.5 Prompt Glyph Resolver

```python
def resolve_prompt(action: str, keyboard_label: str) -> str:
    """Gamepad bağlıysa buton glyph'i, değilse klavye label'ı döndür."""
    gpm = get_gamepad_manager()
    if gpm.is_connected():
        return gpm.get_button_label(action)
    return keyboard_label
```

---

## 7. Aşamalı Uygulama Planı

### Faz 1 — Kritik Kırıklar (1-2 gün)

| Görev | Dosya | Açıklama |
|-------|-------|----------|
| F1.1 Sniper gamepad cursor | game_modes_extra.py | `_sniper_cursor_x/y` + D-pad nav + A=fire + B=cancel. Mevcut mouse path korunur. |
| F1.2 Future changer keyboard nav | game_modes_extra.py | `_piece_selection_index` + L/R + Enter/A. |
| F1.3 Co-op level select keyboard nav | coop_level_select.py | Arrow nav + Enter + world keys (campaign ile aynı pattern). |
| F1.4 Game over overlay keyboard confirm | game.py | Restart: R key. Menu: Enter/M. Gamepad: A=restart, B=menu (veya tersi). |

### Faz 2 — Shared Abstraction (3-5 gün)

| Görev | Dosya | Açıklama |
|-------|-------|----------|
| F2.1 FocusManager sınıfı | src/focus_manager.py (yeni) | Ortak focus/nav/confirm/back. |
| F2.2 Prompt glyph standardizasyonu | Tüm "tuşa bas" mesajları | `resolve_prompt()` helper. Lokalizasyon key'leri güncelle. |
| F2.3 Pointer mode politikası | gamepad_manager.py | Focus-nav olan ekranlarda pointer mode otomatik deaktif. |
| F2.4 GamepadAction enum | gamepad_manager.py | CONFIRM/BACK/TAB_NEXT/TAB_PREV/NAV_* standart action seti. |

### Faz 3 — Uzun Kuyruk Cleanup (ongoing)

| Görev | Dosya | Açıklama |
|-------|-------|----------|
| F3.1 Legacy gamepad tab temizliği | menu.py:5831+ | Ölü kodu sil veya deprecation notu ekle. |
| F3.2 Avatar/piece workshop audit | İlgili ekranlar | Focus nav ekle. |
| F3.3 Tutorial runtime gamepad | tutorial_runtime.py | Doğrula ve gerekirse nav ekle. |
| F3.4 Online PvP lobby gamepad | online_pvp_game.py | Code input alternatifi (gamepad keyboard?). |

---

## 8. Doğrulama Planı (Manuel Smoke Checklist)

Her faz sonunda aşağıdaki akış gamepad-only (klavye/mouse kullanmadan) tamamlanabilmeli:

### Faz 1 Sonrası:
- [ ] Splash → A ile geç
- [ ] Ana menü → D-pad ile Kart Ustalığı seç → A ile başlat
- [ ] Gameplay → parça düşür → kart seçim overlay açılsın
- [ ] Kart seçim → D-pad ile kart seç → A ile onayla
- [ ] Sniper kartı al → N (veya gamepad binding) → D-pad ile hücre seç → A ile ateş
- [ ] Future changer kartı al → popup açılsın → D-pad ile parça seç → A ile onayla
- [ ] ESC/B → pause → B ile devam
- [ ] Game over → A ile restart VEYA B ile menü
- [ ] Ana menü → Co-op Campaign → D-pad ile level seç → A ile başlat

### Faz 2 Sonrası:
- [ ] Tüm Faz 1 + prompt glyph'leri gamepad bağlıyken doğru gösteriyor
- [ ] Settings → Kontroller → gamepad rebind → buton bas → glyph güncellendi
- [ ] Pointer mode sadece mouse-zorunlu overlay'lerde aktif

### Faz 3 Sonrası:
- [ ] Avatar editor gamepad-only
- [ ] Piece workshop gamepad-only
- [ ] Tutorial gamepad-only

---

## 9. Korunan Invariantlar (AGENTS.md)

- `board.level ≠ card_level` — bu özellik kart XP akışına dokunmaz.
- Generated markdown elle düzenlenmez.
- UIFonts tek font kaynağı kalır.
- Online PvP bridge pump thread'e dokunulmaz.
- Gamepad modernizasyonu mevcut sentetik klavye pipeline'ını BOZMAZ; üstüne native yollar ekler.
