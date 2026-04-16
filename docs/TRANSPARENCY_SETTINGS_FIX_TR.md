# Transparanlık & Menü Şeffaflığı Ayarları — Düzeltme Raporu

**Tarih:** 16 Nisan 2026

---

## Tespit Edilen Sorunlar

### 1. `bg_transparency` Varsayılan Değer Tutarsızlığı

Farklı dosyalarda farklı default değerler kullanılıyordu:

| Dosya / Konum | Eski Default |
|---|---|
| `game.py` → `__init__` | `0.9` |
| `coop_game.py` → `__init__` (board_background) | `1.0` |
| `coop_game.py` → `__init__` (outer_background) | `1.0` |
| `coop_game.py` → `_sync_runtime_settings_from_manager` | `1.0` |
| `game.py` → `_sync_runtime_settings_from_manager` | `0.3` ✅ |
| `graphics_menu.py` | `0.3` ✅ |
| `main.py` (başlangıç) | `0.3` ✅ |
| `retro_style.py` (init) | `0.3` ✅ |

**Sorun:** Coop modunda default `1.0` (tamamen opak) kullanıldığı için, kullanıcı settings'e hiç dokunmadıysa arka plan tam opak görünüyordu — diğer modlarla tutarsız.

### 2. `main.py` Action Handler — Coop Desteği Eksik

`change_bg_transparency` action'ı tetiklendiğinde yalnızca `game` ve `pvp_game` nesneleri güncelleniyordu. **`coop_game` hiç güncellenmiyordu.** Bu, grafik menüsünden yapılan transparanlık değişikliğinin aktif bir coop oturumuna yansımamasına neden oluyordu.

### 3. Falling Blocks (Arka Plan Blok Akışı) Şeffaflıktan Bağımsız

`FallingBlocksLayer` sınıfı sabit alpha değerleri (50–110) kullanıyordu. Ne `bg_transparency` ne de `menu_transparency` bu katmanı etkiliyordu. Kullanıcı transparanlığı değiştirdiğinde düşen bloklar aynı parlaklıkta kalmaya devam ediyordu.

---

## Yapılan Düzeltmeler

### Düzeltme 1: Default Değerler Tutarlı Hale Getirildi

Tüm `bg_transparency` default değerleri **`0.3`** olarak birleştirildi.

**Değişen dosyalar:**
- `src/game.py` — `__init__` default: `0.9` → `0.3`
- `src/coop_game.py` — `__init__` board_background default: `1.0` → `0.3`
- `src/coop_game.py` — `__init__` background default: `1.0` → `0.3`
- `src/coop_game.py` — `__init__` outer_background default: `1.0` → `0.3`
- `src/coop_game.py` — `_sync_runtime_settings_from_manager` default: `1.0` → `0.3`

### Düzeltme 2: Coop Game Anlık Transparanlık Güncellemesi

`main.py`'deki `change_bg_transparency` action handler'ına `coop_game` desteği eklendi:
- `coop_game.background`, `coop_game.board_background`, `coop_game.outer_background` nesnelerinin `set_transparency()` metodu çağrılıyor.
- Composite cache (`_outer_bg_composite_cache`) invalidate ediliyor → değişiklik anında yansıyor.

**Değişen dosya:** `src/main.py`

### Düzeltme 3: Falling Blocks — `bg_transparency` ile Orantılı Alfa

`FallingBlocksLayer` sınıfına `set_opacity_multiplier(value)` metodu eklendi. Bu metot 0.0–1.0 arası bir çarpan kabul eder ve her bloğun alfa değeri draw sırasında bu çarpanla orantılı olarak uygulanır.

Entegrasyon noktaları:
- **Başlangıç:** `main.py` uygulama başlatılırken `bg_transparency` değeri falling blocks'a aktarılıyor.
- **Anlık değişiklik:** `main.py` → `change_bg_transparency` handler'ında shared falling blocks layer güncelleniyor.
- **Oyun içi sync:** `game.py` ve `coop_game.py` → `_sync_runtime_settings_from_manager` fonksiyonlarında falling blocks opacity'si `bg_transparency` ile senkronize ediliyor.

**Değişen dosyalar:**
- `src/background_effects.py` — `set_opacity_multiplier()` metodu, `draw()` içinde çarpan uygulaması (hem jelly hem fallback renderer)
- `src/game.py` — `_sync_runtime_settings_from_manager` sonunda falling blocks sync
- `src/coop_game.py` — `_sync_runtime_settings_from_manager` sonunda falling blocks sync
- `src/main.py` — başlangıç sync + action handler sync

---

## Etkilenen Dosyalar Özeti

| Dosya | Değişiklik |
|---|---|
| `src/game.py` | Default fix + falling blocks sync |
| `src/coop_game.py` | Default fix + coop transparency propagation + falling blocks sync |
| `src/main.py` | Coop handler + falling blocks handler + başlangıç sync |
| `src/background_effects.py` | `set_opacity_multiplier()` + draw'da alfa çarpanı |

## Platform Notu

Windows ve macOS arasında transparanlık mekanizmasında platform-spesifik fark yoktur. Her iki platformda da aynı `set_alpha()` ve `_scale_menu_alpha()` mantığı çalışmaktadır. Bu düzeltmeler her iki platformu da eşit şekilde etkiler.
