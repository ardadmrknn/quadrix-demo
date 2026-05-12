# Demo Implementation Log - 2026-05-11

## Branch ve Konum

- Branch: feature/steam-demo-4635310
- Worktree: C:\Users\arda demirkan\Desktop\v2_23022026\v2-demo
- Kaynak plan: plans/2026-04-17-demo-surumu-uretim-plani.md

## Uygulanan Kapsam

### 1. Demo config ve runtime ayrimi

- src/demo_config.py eklendi.
- scripts/build/write_demo_config.py eklendi.
- config/runtime/steam_appid_demo.txt eklendi.
- Demo/full mod gecisi icin deterministik config writer kuruldu.
- Runtime save/app ayrimi icin QUADRIX_APP_NAME = quadrix_demo akisi eklendi.
- PyInstaller runtime hook, demo_config uzerinden demo app adini okuyacak sekilde guncellendi.

### 2. Demo prompt katmani

- src/demo_upgrade_prompt.py eklendi.
- Full lock, partial lock ve transition lock promptlari tek helper uzerinden toplandi.
- Prompt store acma davranisi DEMO_STEAM_STORE_URL uzerinden webbrowser.open ile calisiyor.

### 3. Build ve paketleme altyapisi

- packaging/specs/tetris_demo.spec eklendi.
- packaging/specs/tetris_demo_macos_allinone.spec eklendi.
- scripts/build/build_windows_demo.ps1 eklendi.
- scripts/build/build_macos_demo_app.sh eklendi.
- scripts/build/build_macos_app.sh --spec ve --app-name parametrelerini kabul edecek sekilde guncellendi.
- Windows demo artifact hedefi QuadrixDemo.exe olarak ayrildi.
- macOS demo artifact hedefi Quadrix Demo.app olarak ayrildi.
- Demo build icin steam_appid_demo.txt kaynagi paket icinde steam_appid.txt hedefiyle uretiliyor.

### 4. UI ve erisim kilitleri

- src/extras_menu.py demo lock promptlari ve kart overlay badge ile guncellendi.
- src/menu.py online_pvp ve online_coop gecislerini demo promptu ile bloke edecek sekilde guncellendi.
- src/campaign/level_select.py solo kampanya dunya ve level limitlerini demo config uzerinden uygular hale getirildi.
- src/campaign/coop_level_select.py co-op kampanya dunya ve level limitlerini demo config uzerinden uygular hale getirildi.

### 5. Kart modu interval degisikligi

- src/game_modes_extra.py icinde MysteryCardManager ve MysteryMode kart secim tetigi seviye-bucket mantigina alindi.
- Full build: her 5 seviyede bir kart secimi.
- Demo build: her 10 seviyede bir kart secimi.
- Runtime queue mantigi pending_level_ups yerine card interval bucket uzerinden kontrol edilir hale getirildi.

### 6. Mystery demo hotfix

- Kullanici geri bildirimi sonrasi demo kart seciminin fiilen calismadigi tekrar incelendi.
- Kök neden: src/board.py level artisini hala her 5 satirda yapiyordu, buna karsin demo kart secimi board.level bucket'larina bakiyordu.
- Sonuc: demo buildde ilk kart secimi 10 satirda degil, cok daha gec bir noktada tetikleniyordu.
- Cozum: src/board.py icinde satir-basina level esigi configurabl hale getirildi.
- MysteryMode baslangic ve restart akisinda board.level_lines_per_level degeri kart modu intervali ile ayni esige senkronlandi.
- src/game_modes_extra.py icinde kart secim mantigi ana projedeki gibi tekrar seviye-delta ve line-progress akisina alindi; bucket tabanli demo farki kaldirildi.
- Demo Mystery/Card mode icin beklenen davranis: her 10 temizlenen satirda 1 level ve ayni ritimde 1 kart secimi.

### 7. Gorsel varsayilanlar ve demo veri ayrimi tamamlama

- Kullanici geri bildirimi uzerine display varsayilanlari referans ekran goruntusundeki degerlere sabitlendi.
- Varsayilan arka plan transparanligi 0.7 (%70) yapildi.
- Efekt seffafligi 1.0 (%100), menu seffafligi 1.0 (%100) ve parcacik efektleri medium (Orta) olarak korundu.
- Bu varsayilanlar settings_manager ile birlikte explicit bg_transparency fallback kullanan runtime yuzeylerine de tasindi.
- Demo/full user-data ayrimi sadece demo moduna degil, her iki moda da explicit app name set edecek sekilde sertlestirildi.
- apply_runtime_environment artik full buildde de QUADRIX_APP_NAME = quadrix_full degerini set ediyor; demo buildde quadrix_demo olarak kaliyor.
- PyInstaller runtime hook full/demo app name secimini demo_config.get_runtime_app_name uzerinden cozer hale getirildi.
- Sonuc: demo ve tam surum profil/ayar/kayitlari ayri user-data koklerinde tutuluyor.

### 8. Demo prompt lokalizasyonu ve store link guncellemesi

- Demo prompt paneli, extras kilit badge'leri ve campaign kilit etiketleri localization anahtarlarina baglandi.
- Demo prompt fallback metinlerindeki Turkce karakterler duzeltildi.
- Steam'de Ac butonunun actigi link https://store.steampowered.com/app/4414520/Quadrix/ olarak guncellendi.
- Co-op campaign tarafindaki LOCK ve BOSS sabit etiketleri localization uzerinden cizilir hale getirildi.

## Degisen Dosyalar

### Yeni dosyalar

- src/demo_config.py
- src/demo_upgrade_prompt.py
- scripts/build/write_demo_config.py
- scripts/build/build_windows_demo.ps1
- scripts/build/build_macos_demo_app.sh
- packaging/specs/tetris_demo.spec
- packaging/specs/tetris_demo_macos_allinone.spec
- config/runtime/steam_appid_demo.txt
- tests/test_demo_config.py
- tests/test_demo_build_specs.py
- tests/test_demo_menu_locks.py
- tests/test_demo_campaign_limits.py
- tests/test_demo_card_mode_interval.py
- tests/test_display_defaults.py
- tests/test_demo_localization.py

### Guncellenen dosyalar

- main.py
- src/main.py
- packaging/pyinstaller/hooks/pyi_rth_quadrix_data.py
- scripts/build/build_macos_app.sh
- src/settings_manager.py
- src/retro_style.py
- src/menu.py
- src/extras_menu.py
- src/campaign/level_select.py
- src/campaign/coop_level_select.py
- src/board.py
- src/game_modes_extra.py
- src/graphics_menu.py
- src/settings_screen_tabbed.py
- src/game.py
- src/coop_game.py
- src/pvp_game.py
- src/localization.py

## Calistirilan Dogrulamalar

### Dar syntax/compile dogrulamalari

- py -3.12 -m py_compile src/demo_config.py src/demo_upgrade_prompt.py src/extras_menu.py src/menu.py src/campaign/level_select.py src/campaign/coop_level_select.py src/game_modes_extra.py scripts/build/write_demo_config.py
- Sonuc: gecti

### Demo odakli testler

- pytest tests/test_demo_config.py -q
- Sonuc: 3 passed

- pytest tests/test_demo_build_specs.py -q
- Sonuc: 5 passed

- pytest tests/test_demo_config.py tests/test_demo_build_specs.py tests/test_demo_menu_locks.py tests/test_demo_campaign_limits.py tests/test_demo_card_mode_interval.py -q
- Sonuc: 14 passed

### Hedeflenmis regresyon paketi

- pytest tests/test_demo_config.py tests/test_demo_build_specs.py tests/test_demo_menu_locks.py tests/test_demo_campaign_limits.py tests/test_demo_card_mode_interval.py tests/test_extras_includes_classic.py tests/test_campaign_level_panel_keyboard.py tests/test_mystery_external_line_clear_reward.py tests/test_save_layout_migration.py -q
- Sonuc: 40 passed

### Mystery hotfix dogrulamalari

- pytest tests/test_demo_card_mode_interval.py tests/test_mystery_external_line_clear_reward.py -q
- Sonuc: 4 passed

- pytest tests/test_demo_card_mode_interval.py tests/test_demo_config.py tests/test_game_modes_extra_helpers.py tests/test_mystery_external_line_clear_reward.py -q
- Sonuc: 70 passed

### Varsayilanlar ve lokalizasyon dogrulamalari

- pytest tests/test_demo_config.py tests/test_display_defaults.py -q
- Sonuc: 6 passed

- pytest tests/test_demo_localization.py tests/test_demo_config.py tests/test_display_defaults.py -q
- Sonuc: 7 passed

### Gercek build dogrulamalari

- powershell -ExecutionPolicy Bypass -File scripts/build/build_windows_demo.ps1
- Sonuc: gecti
- Artifact: dist/QuadrixDemo.exe uretildi
- Ek dogrulama: src/demo_config.py build sonunda full moda geri dondu (IS_DEMO = False)

- bash -n scripts/build/build_macos_app.sh
- bash -n scripts/build/build_macos_demo_app.sh
- Sonuc: iki script de syntax olarak gecti

## Karsilasilan Sorunlar ve Cozumler

### 1. Worktree workspace disinda oldugu icin arama toollari sinirliydi

- Sorun: VS Code workspace sadece ana repo kokunu gordugu icin v2-demo uzerinde file_search/grep_search yuzeyi kisitli kaldi.
- Cozum: v2-demo altinda dogrudan dosya okuma ve komut-tabanli arama kullanildi.

### 2. Windows demo spec ilk denemede PyInstaller version hatasi verdi

- Sorun: tetris_demo.spec icinde EXE(..., version=APP_VERSION) kullanimi, PyInstaller tarafinda version resource dosyasi bekledigi icin FileNotFoundError uretti.
- Cozum: version parametresi kaldirildi. Sonraki gercek build gecti ve QuadrixDemo.exe uretildi.

### 3. Plan dokumanindaki extras mod adlari ile runtime id'ler bire bir uyusmuyordu

- Sorun: Daily Challenge runtime id'si Daily Challenge degil, daily_challenge idi. Online PvP de extras tarafinda Online PvP id'si ile geciyordu.
- Cozum: demo_config icinde kilit listeleri runtime id'lere gore guncellendi ve transition lock ayrimi eklendi.

### 4. Kart modu mevcut threshold yorumu seviye bazli degildi

- Sorun: MysteryCardManager.threshold mevcut haliyle dogrudan seviye intervalini degil, tetik senkronunu yonetiyordu; dogrudan carpma yaklasimi birden fazla prompt queue uretebilirdi.
- Cozum: interval mantigi seviye bucket modeline tasindi. Boylece full buildde 5, demo buildde 10 seviyede bir tek secim queue olusuyor.

### 5. Bucket tabanli demo kart secimi gercek oyun akisiyla uyusmadi

- Sorun: Demo tarafinda kart secimi board.level bucket'ina alinmisti, ancak board level-up esigi hala 5 satirdi.
- Etki: Demo kart secimi pratikte 10 satirda degil, cok daha gec tetikleniyordu ve kullanici tarafinda bozuk gorunuyordu.
- Cozum: Board level-up esigi kart modu icin configurabl yapildi ve MysteryMode tarafi line-progress + level-delta modeline geri cekildi.

### 6. Demo/full veri ayrimi sadece demo modunda explicit set ediliyordu

- Sorun: Demo app name env tarafinda explicit set ediliyordu, full build ise varsayilan davranisa dusuyordu.
- Risk: Farkli bootstrap veya paketleme yollarinda demo/full veri koklerinin sessizce ayni yerlere baglanma ihtimali kalirdi.
- Cozum: demo_config.apply_runtime_environment ve runtime hook full/demo iki modu da explicit app name ile normalize eder hale getirildi.

## Mevcut Limitasyonlar

- macOS gercek .app build'i bu Windows host uzerinde calistirilmadi.
- macOS tarafinda syntax ve spec/wrapper dogrulamasi yapildi, fakat dist/Quadrix Demo.app artifact'i burada uretilmedi.
- Steam store linki DEMO_STEAM_STORE_URL sabitine baglandi; repo ici taraf bu URL ile hazir.

## Durum Ozeti

- Demo config altyapisi hazir.
- Demo save/app identity ayrimi hazir.
- Windows demo build hatti gercekten calisti ve QuadrixDemo.exe uretildi.
- macOS demo build hatti script/spec seviyesinde hazirlandi ve syntax dogrulamasi gecti.
- Extras, menu, solo campaign, co-op campaign demo limitleri uygulandi.
- Kart modu demo hotfix'i ile her 10 satirda 1 level ve 1 kart secimi davranisi geri kazanildi.
- Display varsayilanlari referans gorsele gore 70 / 100 / 100 / Orta degerlerine getirildi.
- Demo prompt/panel lokalizasyonu eklendi ve Steam store linki guncellendi.

## 2026-05-11 Ek Faz - Ana menu kilit gorunumu ve 75K demo bitis akisi

### 9. Ana menu online panelleri gri kilit gorunumu

- src/menu.py icinde pvp_2_players ve coop_mode split panellerinin online yarilari demo lock state'ine gore ayrica gorsellestirildi.
- online_pvp ve online_coop taraflari artik yariya ozel gri overlay, diyagonal tarama ve Kilitli badge'i ile ciziliyor.
- Bu degisiklik input kilidini tasiyan mevcut \_maybe_handle_demo_main_action akisiyla ayni runtime lock kaynagini kullanir.

### 10. Kart Ustaligi demo 75K skor siniri

- src/game_modes_extra.py icinde demo-only 75.000 skor siniri eklendi.
- Esik asildiginda MysteryMode standart game_over overlay'ine dusmek yerine ozel bir demo completion prompt state'ine geciyor.
- Bu sayede Game.draw icindeki varsayilan game-over overlay ile mod overlay'lerinin cakismasi engellendi.
- Prompt acildiginda aktif kart secimi, sniper/piece/workshop overlay'leri ve bekleyen kart secim kuyruğu temizleniyor; oyun update akisi donduruluyor.
- Prompt uzerinden Steam'de Ac secilirse store linki aciliyor; her iki buton da oyunu menuye donduruyor.

### 11. Demo prompt katmani genisletmesi

- src/demo_upgrade_prompt.py icinde prompt son aksiyonu consume_last_action() ile okunabilir hale getirildi.
- Mystery demo score cap icin show_demo_score_cap_prompt helper'i eklendi.
- src/localization.py icine demo_score_cap_title ve demo_score_cap_message anahtarlari eklendi.

## Bu fazda guncellenen dosyalar

- src/menu.py
- src/game_modes_extra.py
- src/demo_upgrade_prompt.py
- src/localization.py
- tests/test_demo_menu_locks.py
- tests/test_demo_localization.py
- tests/test_demo_mystery_score_cap.py

## Bu fazin dogrulamalari

- py -3.12 -m py_compile src/menu.py
- Sonuc: gecti

- pytest tests/test_demo_menu_locks.py -q
- Sonuc: 3 passed

- py -3.12 -m py_compile src/demo_upgrade_prompt.py src/game_modes_extra.py src/localization.py
- Sonuc: gecti

- pytest tests/test_demo_mystery_score_cap.py tests/test_demo_localization.py -q
- Sonuc: 4 passed

- py -3.12 -m py_compile src/menu.py src/demo_upgrade_prompt.py src/game_modes_extra.py src/localization.py
- Sonuc: gecti

- pytest tests/test_demo_menu_locks.py tests/test_demo_localization.py tests/test_demo_mystery_score_cap.py -q
- Sonuc: 7 passed

- bash -n scripts/build/build_macos_app.sh
- bash -n scripts/build/build_macos_demo_app.sh
- Sonuc: iki script de syntax olarak gecti

## Bu fazda karsilasilan teknik risk ve cozum

- Risk: Game.draw icinde self.game_over oldugunda mod overlay'leri bastirilir ve varsayilan game-over paneli ustte cizilir.
- Etki: 75K demo bitis paneli klasik game-over yolu ile yapilsaydi MysteryMode ozel prompt'u cizemezdi ya da iki overlay cakisirdi.
- Cozum: game_over yerine MysteryMode'a ozel demo completion state eklendi; draw_mode_overlay uzerinden prompt cizildi ve update/input oradan bloke edildi.

## Guncel durum

- Ana menude demo kilitli online PvP ve online Co-op yarilari artik gri ve kilitli gorunuyor.
- Kart Ustaligi demo modunda 75.000 skorda mac otomatik duruyor ve tesekkur/promo paneli aciliyor.
- Yeni kod yollarinda Windows-only bir bagimlilik eklenmedi; macOS build script syntax dogrulamasi da gecti.
