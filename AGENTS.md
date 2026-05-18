# AGENTS — Operasyonel Rehber

Bu dosya bu repoda çalışan AI ajanları için **karar rehberidir**. Repo haritası, klasör dökümü ve mod listesi için [docs/PROJECT_STRUCTURE_TR.md](docs/PROJECT_STRUCTURE_TR.md) ve [docs/guides/README_FULL.md](docs/guides/README_FULL.md) kullanılır. Burada amaç: bir ajan ne yaparken nereden başlamalı, neyi elle patchlememeli, ne test etmeli, hangi yüzey kırılgan.

> **Plan dizini:** `plans/` (tarihsel; aktif plan klasörü değil).
> **Aktif plan akışı tutmak için yeni klasör açma**. Tarihsel plan/rapor referansını kanıt olarak kullanma.

---

## 1. Project Snapshot

| Alan | Değer |
| --- | --- |
| Tip | Pygame tabanlı çok modlu Tetris türevi (Quadrix) + Steam entegrasyonu |
| Dil / Framework | Python 3.12 (zorunlu) + Pygame 2.x |
| Web frontend | **Yok.** Tüm UI Pygame tabanlıdır. |
| Source dizini | `src/` |
| Ana giriş | `main.py` (TR), `src/main_en.py` (EN fallback) |
| Test komutu | `./scripts/test/run_tests.sh -q` |
| Üst düzey alt sistemler | Tek oyunculu modlar, Mystery (Kart Ustalığı), Campaign + Co-op Campaign, Local PvP/Co-op, Online PvP (Steam P2P), Steam leaderboard + backend proxy, başarımlar, lokalizasyon (11 dil), avatar/profil, Workshop/Atölye |

---

## 2. Canonical Entry Points

| İş alanı | Önce buraya bak |
| --- | --- |
| Tek oyunculu gameplay | `src/game.py`, `src/board.py`, `src/pieces.py` |
| Mystery / Kart Ustalığı / kart ekonomisi | `src/game_modes_extra.py` (`MysteryMode`, `MysteryCardManager`) |
| Diğer mod aileleri | `src/game_modes.py`, `src/game_modes_advanced.py` |
| Campaign | `src/campaign/campaign_mode.py` (+ `level_data.py`, `objectives.py`) |
| Co-op (yerel) | `src/coop_game.py`, `src/coop_board.py` |
| Co-op Campaign | `src/campaign/coop_campaign_mode.py` (+ `coop_level_select.py`, `coop_level_data.py`) |
| Local PvP | `src/pvp_game.py` |
| Online PvP | `src/online_pvp_game.py`, `src/steam_networking.py`, `steamworks/steam_net_bridge/` |
| Ana menü ve dashboard | `src/menu.py` |
| Mod kart ekranı / extras | `src/extras_menu.py` |
| Mod rehber ekranı | `src/guide_screen.py` |
| Ayarlar | `src/settings_screen_tabbed.py`, `src/settings_manager.py` |
| UI tema, font, glass panel | `src/ui_theme.py` (`UIFonts`/`UIColors`), `src/retro_style.py` |
| Başarımlar | `src/achievements.py`, `src/steam_integration.py` |
| Steam leaderboard istemci | `src/steam_leaderboards.py` |
| Steam backend proxy | `backend/steam_leaderboard_proxy.py` |
| Lokalizasyon | `src/localization.py` (`t()`), `src/ui_language_profile.py` |
| Build | `scripts/build/build_macos_app.sh`, `scripts/build/build_windows_exe.ps1` |
| Steam upload | `scripts/build/steam_upload_macos.sh`, `tools/steam_upload_playtest.ps1` |
| Generated markdown üretici | `tools/sync_markdown_docs.py` |
| Generated markdown test | `tests/test_markdown_doc_sync.py` |

---

## 3. Task Routing

Görev tipine göre ilk hareket. **Geniş repo turu yapma; aşağıdaki yüzeyden başla.**

### 3.1 Gameplay bug (lock, hareket, çizim, kombo, satır temizleme)
- **Başla:** `src/game.py` (`lock_and_new_piece`, `update`), `src/board.py` (`clear_lines`, `apply_gravity`)
- **Yanlış başlangıç:** `menu.py`, `extras_menu.py` (UI değil, oyun mantığı)
- **Doğrulama:** `./scripts/test/run_tests.sh -q -k <ilgili>` (örn. `-k tetris`, `-k board`)

### 3.2 Mystery / kart ekonomisi / reward queue
- **Başla:** `src/game_modes_extra.py` (`MysteryCardManager`, `MysteryMode`, `_post_external_line_clear`, `lock_and_new_piece`)
- **Anahtar invariant:** `card_xp` / `card_level` `board.level`'den **ayrıdır**. Detay: [docs/CARD_PERK_INVENTORY_TR.md](docs/CARD_PERK_INVENTORY_TR.md).
- **Yanlış başlangıç:** `board.py` `level_lines_cleared` mantığını dokunma (oyun temposu için kalır).
- **Doğrulama:**
  ```
  ./scripts/test/run_tests.sh -q tests/test_mystery_card_xp_progression.py \
                                 tests/test_mystery_card_quality_gaps.py \
                                 tests/test_mystery_external_line_clear_reward.py \
                                 tests/test_mystery_card_effect_behavior.py
  ```

### 3.3 Campaign / başarım bug
- **Başla:** `src/campaign/campaign_mode.py` (`_save_progress`), `src/achievements.py`, `src/steam_integration.py`
- **Anahtar invariant:** Başarım tetiklemesi `_save_progress()` sonunda yapılır. Save akışını bozarsan başarım pop'ları kaçar.
- **Yanlış başlangıç:** `menu.py` veya `extras_menu.py`
- **Doğrulama:** `-k campaign` ve `-k achievement` test filtreleri.

### 3.4 UI scaling / font / panel boyutu
- **Başla:** İlgili ekranın kendi scale fonksiyonu.
  - Ana menü: `src/menu.py` `_menu_panel_content_scale()` (1920×1080 ref).
  - Level select: `src/campaign/level_select.py` `max(0.72, min(1.0, w/1400, h/900))`.
  - Extras: `src/extras_menu.py` `_extras_ui_scale()` (`base_window_size` ref).
  - Mystery in-game HUD: `src/game_modes_extra.py` `_card_ui_scale()`, `_build_left_panel_font_pack()`.
- **Anahtar invariant:** `UIFonts` (`src/ui_theme.py`) tüm in-game UI fontlarının tek kaynağıdır. Yeni bir font factory yaratma; `UIFonts` üzerinden geç.
- **Yanlış başlangıç:** Genel "global font scale" değişkeni eklemek. Her ekranın kendi scale fonksiyonu vardır.
- **Doğrulama:** İlgili `tests/test_phase*_ui_scaling.py` veya etkilenen ekrana özel test.

### 3.5 Lokalizasyon işi
- **Başla:** `src/localization.py` (`t()` ve çeviri tabloları)
- **CJK / dil profili:** `src/ui_language_profile.py`
- **Anahtar invariant:** Desteklenen 11 dil: TR, EN, DE, FR, ES, IT, PT, RU, JA, ZH, KO. Bir key eklerken hepsini doldur (eksik dil İngilizce'ye fallback'lenir ama bu intent değildir).
- **Doğrulama:** `-k localization` veya ilgili lokalizasyon audit dosyası.

### 3.6 Steam leaderboard / upload / başarım
- **Başla:** Sorun client'ta mı backend'de mi?
  - Client/SDK: `src/steam_leaderboards.py`, `src/steam_integration.py`
  - Backend: `backend/steam_leaderboard_proxy.py`
- **Operasyon:** [docs/STEAM_LEADERBOARD_OPERATIONS_TR.md](docs/STEAM_LEADERBOARD_OPERATIONS_TR.md)
- **Kurulum / mod adı eşleşmesi:** [docs/STEAMWORKS_LEADERBOARD_SETUP_TR.md](docs/STEAMWORKS_LEADERBOARD_SETUP_TR.md)
- **Anahtar kural:** Build/upload **gerçeği** markdown'dan değil, helper scriptlerden okunur (bkz. §4).
- **Doğrulama:** `tests/test_lb_write.py` (yalnızca Windows + Steam açık), `tools/steam_leaderboard_smoke_test.py`.

### 3.7 Build / packaging
- **Başla:**
  - macOS: `scripts/build/build_macos_app.sh` + `packaging/specs/<*macos*>.spec`
  - Windows: `scripts/build/build_windows_exe.ps1` + `packaging/specs/<*windows*>.spec`
- **Köprü:** `local_artifacts/bridge/` altında doğru `.pyd` / `.so` var mı?
- **Doğrulama:** PyInstaller log'unda `steam_net_bridge eklendi` satırı; sonra paket build ile Online PvP smoke.

### 3.8 Markdown / doküman güncellemesi
- **Önce kategori belirle (bkz. §5).** Generated mı, kanonik mi, tarihsel mi, vendor mı?
- **Generated ise:** Source'u (helper script veya VDF) düzelt → `python3 tools/sync_markdown_docs.py` → `pytest tests/test_markdown_doc_sync.py`. **Generated dosyaya doğrudan dokunma.**
- **Kanonik ise:** Doğrudan düzenle, sonra ilgili relative linkleri doğrula.
- **Tarihsel ise:** Genelde dokunma; kullanıcıyı yanıltıyorsa minimal not ekle.
- **Doğrulama:** `./scripts/test/run_tests.sh -q tests/test_markdown_doc_sync.py` + manuel link tarama (bkz. §6).

### 3.9 Online PvP / native bridge
- **Başla:** `src/online_pvp_game.py` (akış), `src/steam_networking.py` (Python wrapper), `steamworks/steam_net_bridge/steam_net_bridge.cpp` (C++).
- **Mimari:** [docs/ONLINE_PVP_ARCHITECTURE.md](docs/ONLINE_PVP_ARCHITECTURE.md). Davranış/akış: [docs/ONLINE_PVP_FLOW_TR.md](docs/ONLINE_PVP_FLOW_TR.md).
- **Köprü derleme:** [steamworks/steam_net_bridge/README_BUILD.md](steamworks/steam_net_bridge/README_BUILD.md).
- **Anahtar invariant:** Köprü aktifken `steam_integration.py` pump thread **duraklatılmış** olmalı (`pause_pump`/`resume_pump`). Aksi halde segfault.

---

## 4. Generated Markdown Policy

**Sert kural.** Aşağıdaki üç dosya `tools/sync_markdown_docs.py` tarafından üretilir ve **doğrudan elle patchlenmez**:

- `docs/BUILD_AND_UPLOAD.md`
- `docs/STEAM_PLAYTEST_YAYIN_REHBERI_TR.md`
- `docs/EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md`

İçerik yanlış görünüyorsa akış:

1. Sync script'in okuduğu kaynak yüzeylerden **hangisi yanlış** belirle:
   - `scripts/build/build_windows_exe.ps1`
   - `tools/steam_upload_playtest.ps1`
   - `scripts/build/build_macos_app.sh`
   - `scripts/build/steam_upload_macos.sh`
   - `steamworks/scripts/app_build_*.vdf`
2. Source yüzeyini düzelt (veya gerekiyorsa `tools/sync_markdown_docs.py` içindeki extraction/render mantığını).
3. `python3 tools/sync_markdown_docs.py`
4. `python3 -m pytest tests/test_markdown_doc_sync.py -q`

**Source-of-Truth Kuralı:** Generated markdown helper script gerçekleriyle çelişiyorsa **helper script doğru kabul edilir**. Markdown sahte kanıt değildir.

**Geçmişteki gerçek bug örneği:** `tools/steam_upload_playtest.ps1` PS1 default'u `AppBuildScript = ""` olunca, sync script bu boş değeri canonical "varsayılan dosya yolu" sandı ve generated docs'a `Windows helper varsayilan olarak `` dosyasini kullanir.` ile `+run_app_build ".\" +quit` üretti. Çözüm: source-level düzeltme `sync_markdown_docs.py` içine `windows_app_build_script_default_is_synthesized` flag'i eklemek; markdown'u elle yamamak değildi.

---

## 5. Documentation Categories

| Kategori | Davranış |
| --- | --- |
| **Kanonik ürün/geliştirici dokümanı** — `README.md`, `docs/guides/*`, `docs/PROJECT_STRUCTURE_TR.md`, `docs/CARD_PERK_INVENTORY_TR.md`, `docs/STEAM_LEADERBOARD_*`, `docs/ONLINE_PVP_*`, `docs/STEAM_ACHIEVEMENTS_SETUP.md`, `docs/STALE_CHECKLIST_TR.md`, küçük asset README'leri (`assets/ui/mode_icons/`, `backgrounds/`), `steamworks/steam_net_bridge/README_BUILD.md` | Aktif rehber. Doğrudan düzenle; sonra link doğrulaması yap. |
| **Generated** — bkz. §4 listesi | **Doğrudan dokunma.** Source yüzeyini düzelt → `python3 tools/sync_markdown_docs.py` → `pytest tests/test_markdown_doc_sync.py -q`. (Detay: §4) |
| **Tarihsel plan/rapor/arşiv** — `plans/`, `reports/`, `todo/`, `docs/archive/`, tarihli `docs/MACOS_*KOK_NEDENI_TR.md` ve benzeri kök neden analizleri, `docs/macos_borderless_fullscreen.md`, `docs/online_pvp_sorunlar_cozum_guncel.md`, `docs/CAMPAIGN_LEVEL_SYSTEM_ROADMAP.md`, `docs/SECURITY_REVIEW_*`, `docs/TRANSPARENCY_SETTINGS_FIX_TR.md`, vb. | Tarihsel kayıttır. **Rewrite etme.** Yalnızca kullanıcıyı yanıltan kanonik başlık veya bariz kırık link varsa minimal düzeltme; gerekiyorsa "tarihsel kayıt, güncel rehber X'tir" notu ekle. |
| **Vendor / upstream** — `assets/gamepad_icon/promptfont/README.md`, `steamworks/sdk/**/README.md`, `.pytest_cache/README.md`, `dist/Quadrix*/**/README.md` | **Varsayılan: dokunma.** Upstream içerik veya build artifact. Yalnızca repo gerçeğiyle aktif çelişen ve gerçekten kaçınılmaz bir durumda, dar ve savunulabilir bir düzeltme yapılabilir; rewrite asla. |
| **Agent / config** — `AGENTS.md` (bu dosya), `.github/prompts/*.agent.md` | Ürün dokümanı muamelesi yapma. Yalnızca repo gerçeğiyle aktif çelişiyorsa dokun. |
| **Mağaza / pazarlama** — `docs/steam_icin/*` | Audit et ama pazarlama dilini geliştirici rehberi gibi yeniden yazma. Yalnızca teknik yanlışları düzelt. |

---

## 6. Validation Matrix

**İlke:** Önce dar doğrulama, sonra geniş doğrulama. Asla "tüm test suite'i koştu" cümlesini geniş test koşmadan yazma.

| Dokunduğun alan | İlk koşulacak |
| --- | --- |
| Genel / dar | `./scripts/test/run_tests.sh -q` (filtre kullanarak) |
| Markdown / generated docs | `python3 tools/sync_markdown_docs.py` + `pytest tests/test_markdown_doc_sync.py -q` + canonical link tarama (bkz. aşağıda) |
| Mystery / kart ekonomisi / restore | `pytest tests/test_mystery_card_xp_progression.py tests/test_mystery_card_quality_gaps.py tests/test_mystery_external_line_clear_reward.py tests/test_mystery_card_effect_behavior.py tests/test_mystery_time_capsule_score_restore.py -q` |
| Campaign / achievement / save | `pytest -q -k "campaign or achievement"` |
| Steam leaderboard / backend | `pytest -q -k "steam or leaderboard or partner_fallback"`. SDK testleri (`tests/test_lb_write.py`) yalnızca Windows + Steam açıkken anlamlıdır. |
| UI scaling / font / panel | `pytest -q -k "ui_scaling or scaling or phase"` |
| Lokalizasyon | `pytest -q -k "localization"` |
| Build / packaging | Source spot-check: spec dosyaları, build helper'ları. Mümkünse `pyinstaller --noconfirm` smoke. |
| Online PvP / bridge | Bridge derleme + `pytest -q -k "online_pvp or steam_networking"`. SDK gerektiren testler ortam bağımlıdır. |

**Geniş regresyon (sonra):** `./scripts/test/run_tests.sh -q -k mystery` veya tam suite (yalnızca dar doğrulama bittikten sonra).

**Kanonik markdown link doğrulama (kısa script):**

```bash
python3 - <<'PY'
import os, re
canonical = ['README.md','docs/guides/README_TR.md','docs/guides/README_FULL.md',
             'docs/guides/README_MACOS.md','docs/PROJECT_STRUCTURE_TR.md',
             'docs/CARD_PERK_INVENTORY_TR.md','docs/STEAM_LEADERBOARD_OPERATIONS_TR.md',
             'docs/STEAMWORKS_LEADERBOARD_SETUP_TR.md','docs/STEAM_ACHIEVEMENTS_SETUP.md',
             'docs/ONLINE_PVP_FLOW_TR.md','docs/ONLINE_PVP_ARCHITECTURE.md',
             'docs/STALE_CHECKLIST_TR.md','docs/BUILD_AND_UPLOAD.md',
             'docs/STEAM_PLAYTEST_YAYIN_REHBERI_TR.md',
             'docs/EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md',
             'assets/ui/mode_icons/README.md','backgrounds/README.md',
             'steamworks/steam_net_bridge/README_BUILD.md']
broken=[]
for p in canonical:
    text=open(p,encoding='utf-8',errors='replace').read()
    for m in re.finditer(r'\]\(([^)]+)\)', text):
        url=m.group(1).split(' ')[0]
        if url.startswith(('http','#','mailto:')): continue
        full=os.path.normpath(os.path.join(os.path.dirname(p), url.split('#',1)[0]))
        if not os.path.exists(full): broken.append((p,url))
print(f'broken={len(broken)}')
for b in broken: print(' ',b)
PY
```

---

## 7. High-Risk Invariants

Aşağıdaki kuralları **kırma**. Hata yapmadan önce iki kez kontrol et.

1. **Board level ≠ Card level.** Mystery modunda iki ayrı progression hattı vardır. `board.level` (`board.py` `level_lines_cleared`) düşüş hızını yönetir. `MysteryCardManager.card_xp` / `card_level` kart ödül ekranını yönetir. Birini diğerine bağlama.
2. **External clear → no card XP.** `_post_external_line_clear` ve `MysteryCardManager.notify_lines_cleared(..., source='card'|'ability'|...)` çağrıları `pending_level_ups` üretmez ve `card_xp` artırmaz. `card_mode_debug` kısayolu da bu kurala uyar.
3. **Restore queue korunur.** Time capsule capture/restore akışı `pending_level_ups`, `pending_choices`, `card_xp`, `card_level`, `card_xp_to_next` alanlarını taşır. Yeni state alanı eklerken capture/restore listelerini güncelle.
4. **Tek reward → tek prepare_selection.** `notify_lines_cleared` level-up tetiklediğinde bir kez `prepare_selection` çağırır; `MysteryMode.update()` `pending_choices` doluysa tekrar çağırmaz. Bu kuralı bozma — RNG ikinci kez tüketilir.
5. **Campaign save tetikler achievement.** `src/campaign/campaign_mode.py` `_save_progress()` sonunda başarım tetikleme yapılır. Save akışını early-return ile bozma.
6. **UI font tek kaynaktan akar.** `UIFonts` (`src/ui_theme.py`) in-game UI fontlarının tek kaynağıdır. Yeni paralel font factory yaratma. Scale fonksiyonları **ekran bazlıdır** (menu, level_select, extras, mystery HUD); global tek bir scale yoktur.
7. **Steam upload kanıtı helper'dadır.** Build/upload markdown'ı yanıltabilir; gerçek `scripts/build/*.{sh,ps1}`, `tools/steam_upload_playtest.ps1` ve `steamworks/scripts/app_build_*.vdf` içindedir.
8. **Generated test geçmesi semantik doğruluk değildir.** `pytest tests/test_markdown_doc_sync.py` yalnızca generated içerik beklenen formatla eşleşiyor mu der. İçerik **anlamlı doğru** mı kontrolü için source spot-check yapılır.
9. **Online PvP bridge + pump thread çakışmaz.** Bridge `RunCallbacks()` çağırırken Steam pump thread duraklatılmış olmalı. `pause_pump()` / `resume_pump()` ref-count'lu.
10. **Vendor ve tarihsel dokümanlar kanonik gibi ele alınmaz.** `plans/`, `reports/`, `docs/archive/`, `assets/gamepad_icon/promptfont/`, `steamworks/sdk/` rewrite edilmez.
11. **Audio shuffle:** `settings_manager` `music_shuffle` key + `sound.set_music_playlist(shuffle=...)`. Playlist davranışını değiştirirken bu iki yüzeyi birlikte düşün.
12. **Co-op shared board:** 20×20, MIDLINE=10. P1 sütunlar 0-9, P2 sütunlar 10-19. Hareket alanları izole; havada parça çarpışması yoktur. Online co-op için `docs/ONLINE_COOP_*` analiz dosyaları tarihsel kayıttır; ürün dokümanı değildir.

---

## 8. Out-of-Scope Defaults

- **Web frontend yok.** Tüm UI Pygame'dir. **Frontend-Engineer-subagent KULLANILMAZ.**
- Vendor README'ler düzenlenmez (PromptFont, Steamworks SDK, pytest cache, dist mirror).
- Tarihsel plan/rapor/arşiv ürün rehberi gibi rewrite edilmez.
- Geniş repo turu yerine **en yakın kontrol yüzeyi** tercih edilir; §3'teki routing tablosu birinci başvurudur.
- Dirty worktree varsa ilgisiz dosyalara dokunulmaz.
- Generated markdown elle yamanmaz; source'a gidilir.
- **`Frontend-Engineer-subagent` çağrılmaz.** Onun yerine repo gerçeklerine uygun, o anki ortamda gerçekten mevcut olan bir subagent/agent seç; varsayım yapma.

---

## 9. Useful Commands

```bash
# Çalıştırma (macOS/Linux)
./scripts/run/start_game.sh
python3 main.py

# Çalıştırma (Windows)
py main.py

# Geliştirme kurulumu (Python 3.12 zorunlu)
python3.12 -m pip install --user -e ".[dev,build]"

# Test (önerilen)
./scripts/test/run_tests.sh -q
./scripts/test/run_tests.sh -q -k mystery
./scripts/test/run_tests.sh -q tests/test_markdown_doc_sync.py

# Pytest doğrudan
python3.12 -m pytest -q

# Generated markdown senkronu
python3 tools/sync_markdown_docs.py

# macOS build + Steam upload
./scripts/build/build_macos_app.sh --clean
./scripts/build/steam_upload_macos.sh --build-first --desc "macOS build YYYY-MM-DD"

# Windows build + Steam upload (kanonik komutlar; detay: docs/BUILD_AND_UPLOAD.md)
pwsh -File .\scripts\build\build_windows_exe.ps1 -Clean
pwsh -File .\tools\steam_upload_playtest.ps1 -SteamCmdPath ... -SteamUser ...
```

---

## 10. Pre-Submit Checklist (Kısa)

- [ ] Görev tipi §3 routing'e göre doğru yüzeyden başlandı.
- [ ] §7 invariantları kırılmadı (özellikle Mystery `card_xp` ↔ `board.level` ayrımı).
- [ ] Generated docs elle düzenlenmedi (§4).
- [ ] Dar doğrulama yapıldı (§6); gerekirse geniş regresyon koşuldu.
- [ ] Kanonik markdown linkleri broken değil.
- [ ] Tarihsel/vendor dosyalar dokunulmadı.
- [ ] Dirty worktree'deki ilgisiz değişiklikler bizim PR'a sızmadı.
