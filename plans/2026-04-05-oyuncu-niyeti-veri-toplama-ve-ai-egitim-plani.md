# Oyuncu Niyeti Veri Toplama ve AI Egitim Plani

## Istedigin Seyin Dogru Yorumu

Bu istek, sadece replay veya tus logu toplama istegi degil.

Asil hedef su:

1. Oyuncunun her aktif parcada ne yaptigini kaydetmek.
2. Bu hareketlerin yapildigi baglami da saklamak.
3. Sonradan bir AI modelinin "oyuncu bu hamleyi hangi amacla yapti?" sorusunu cevaplayabilecegi bir egitim dataseti olusturmak.
4. Nihai asamada modelin, oyuncu o anda hareket ederken veya parca kilitlenmeden hemen once niyet tahmini yapabilmesini saglamak.

Bu yuzden kaydedilecek sey sadece su degil:

- sol
- sag
- rotate
- hold
- hard drop

Kaydedilmesi gereken asıl bilgi su uc katmandir:

1. Ham hareket dizisi
2. Karar anindaki board ve oyun baglami
3. O hamlenin muhtemel amaci icin etiket veya zayif etiket

Kritik nokta: "amac" dogrudan oyunun icinde gorulen bir veri degil. Latent bir degisken. Bu yuzden veri toplama sistemi ham log + baglam + sonradan uretilen etiket mantigiyla kurulmak zorunda.

## Kod Tabaninda Buldugum Omurga

Su anda bu sistemin omurgasi icin en uygun yerlestirme noktasi ana single-player akisi:

- `src/game.py`
  - `handle_input()` oyuncu input'unun ana dispatch noktasi
  - `_update_das()` basili yatay hareket tekrarini yonetiyor
  - `update()` gravity, grounded state ve auto-lock akisina karar veriyor
  - `lock_and_new_piece()` aktif parcayi finalize edip sonucu uretiyor
  - `spawn_new_piece()` yeni parcayi uretiyor ve queue mantigi burada oturuyor
- `src/board.py`
  - `lock_piece()` grid'e gercek yazimi yapiyor
  - `clear_lines()` satir temizligi, combo, level ve skor tarafini sonuclandiriyor
- `src/campaign/campaign_mode.py`
  - `lock_and_new_piece()` override ettigi icin campaign ileride adapter ile baglanabilir
  - `_emit_event('piece_placed', ...)` ek telemetry firsati sagliyor
- `src/pvp_game.py`
  - `lock_and_new_piece(player)` cift oyunculu varyant; ilk faza dahil edilmemeli ama genisleme noktasi hazir
- `src/ghost_bug_tracer.py` ve `src/game_modes_extra.py`
  - projede zaten event bazli debug tracer paterni var
- `src/data_paths.py`, `src/storage_layout.py`, `src/atomic_io.py`
  - kalici veri yolu ve local/cloud ayrimi zaten yerlesik

Analiz sonucu: bu sistemin ilk fazi icin dogru merkez `src/game.py` olmalidir. `src/board.py` minimal tutulmali; recorder mantigi board'a degil gameplay akisina asilmalidir.

## Neden Hamle Logu Tek Basina Yetmez

Modelin "bu hareket neden yapildi" demesi icin yalnizca input gecmisi yeterli olmaz.

Asagidaki baglamlar da lazim:

- parcadan onceki board geometri durumu
- aktif parcanin tipi, rotasyonu ve pozisyonu
- hold ve next queue durumu
- skor, seviye, combo, yukseklik baskisi, top-out riski
- mod baglami
- varsa ozel yetenek veya parca modifier'lari

Ek olarak, egitim icin hedef etiket gereklidir. O etiketler de ya:

- kurallarla zayif sekilde uretilecek
- ya da insan tarafindan duzeltilecek

Bu nedenle sistemin cekirdegi su olmali:

observation -> action trace -> outcome -> weak label / reviewed label

## Ilk Faz Icin Kapsam Karari

Ilk fazi dar tutmak gerekir. Aksi halde mod varyasyonlari sistemi bulaniklastirir.

Onerilen Faz 1 kapsami:

- classic
- sprint
- ultra
- zen

Faz 1 disinda birakilmasi gerekenler:

- pvp
- campaign
- tutorial
- mystery ve agir perk varyasyonlari
- workshop parcalarinin ayri egitim kolu

Sebep:

- tek oyunculu `Game` omurgasi daha stabil
- niyet cikarsama icin once temiz bir veri dagilimi gerekir
- PvP ve campaign niyet uzayi farkli hedefler getirir

## Onerilen Veri Birimi: Piece Episode

Temel kayit birimi frame degil, `piece episode` olmalidir.

Bir episode su penceredir:

`piece_spawned -> action sequence -> lock -> outcome`

Her episode icin su alanlar tutulmali:

### 1. Session meta

- `session_id`
- `run_id`
- `started_at_utc`
- `game_mode`
- `difficulty`
- `app_version`
- `profile_id_hash`
- `piece_rng_seed`
- `control_profile_summary`

### 2. Piece identity

- `piece_id`
- `piece_name`
- `shape_index`
- `spawn_rotation`
- `spawn_x`
- `spawn_y`
- `piece_flags`
  - `tunnel`
  - `drill`
  - `is_bomb`
  - `is_gold`
  - `flexible_border`
  - `is_workshop_piece`

### 3. Pre-piece context

- `board_before_raw`
- `board_before_features`
- `hold_before`
- `queue_before`
- `score_before`
- `level_before`
- `combo_before`
- `lines_before`
- `fall_speed_before`
- `topout_risk_before`

### 4. Action trace

Her anlamli degisim icin event:

- `move_left`
- `move_right`
- `move_left_das`
- `move_right_das`
- `rotate`
- `rotate_wallkick`
- `soft_drop_start`
- `soft_drop_stop`
- `soft_drop_step`
- `hard_drop`
- `hold`
- `grounded_enter`
- `lock`

Her action icin minimum alanlar:

- `t_ms_from_piece_spawn`
- `action_type`
- `x`
- `y`
- `rotation_state`
- `cells`
- `success`
- `source`
  - `manual`
  - `das`
  - `auto`

### 5. Outcome

- `board_after_raw`
- `board_after_features`
- `locked_cells`
- `lines_cleared`
- `cleared_rows`
- `score_delta`
- `combo_after`
- `level_after`
- `topout_after`
- `hold_after`
- `queue_after`

### 6. Label alanlari

- `intent_primary`
- `intent_secondary_tags`
- `intent_confidence`
- `intent_source`
  - `heuristic`
  - `reviewed`
  - `model_bootstrap`
- `label_version`

## Board Temsili Nasil Olmali

Tam gorsel frame saklamak ilk faz icin gereksiz ve pahali.

Onerilen temsil iki katmanli olmalidir:

### Ham temsil

- 20 satirlik occupancy mask
- her satir icin 10-bit ya da kisa string temsil
- opsiyonel cell tag map

### Turetilmis feature temsil

- `column_heights`
- `hole_count`
- `covered_holes`
- `bumpiness`
- `well_depths`
- `max_height`
- `surface_profile`
- `line_clear_potential`
- `danger_score`

Bu ayrim onemli cunku:

- ham temsil daha sonra farkli modeller icin saklanir
- feature temsil ilk heuristic ve baseline model icin hiz kazandirir

## Niyet Etiket Taksonomisi

Etiket uzayi basta kucuk tutulmali. Ilk versiyon icin onerim:

- `survive_reduce_height`
- `clean_holes_or_garbage`
- `preserve_tetris_well`
- `build_tetris_well`
- `burn_for_safety`
- `combo_continue`
- `score_maximize`
- `hold_for_future_value`
- `recover_misdrop`
- `objective_or_mode_specific`
- `unknown`

Bu etiketler multi-label olabilir ama ilk model icin bir `primary` ve sifira ya da daha fazla `secondary tag` daha saglikli olur.

Ornek secondary tag'ler:

- `fill_hole`
- `flatten_surface`
- `open_well`
- `keep_i_piece`
- `avoid_topout`
- `burn_single`
- `burn_double`
- `late_rotate_fix`
- `wall_kick_escape`

## Canli AI Yorumu Icin Veri Perspektifi

Bu noktada kritik tasarim karari su:

Canli model, gelecegi gormemeli.

Yani egitim satiri olusturulurken model girdisi sadece o ana kadar bilinen veriden gelmeli. Ama etiket, parca sonuclandiktan sonra hesaplanabilir.

Bu nedenle dataset iki gorunume sahip olmali:

1. `observation_snapshot`
2. `final_episode_label`

Onerilen snapshot anlari:

- parca spawn aninda
- basarili move/rotate/hold sonrasinda
- grounded ilk kez oldugunda
- hard drop oncesinde
- lock oncesindeki son state

Boylece ileride iki ayri model secenegi acik kalir:

- sadece `pre-lock` tahmin modeli
- tum `action trace` kullanan sira modeli

## Onerilen Runtime Mimari

### Yeni modul: `src/player_intent_recorder.py`

Ana sorumluluklar:

- recorder ac/kapa
- session lifecycle
- aktif piece episode acma/kapama
- action event toplama
- snapshot alma
- rolling JSONL yazma

Onerilen siniflar:

- `PlayerIntentRecorder`
- `PieceEpisodeBuilder`
- `RollingJsonlWriter`

### Yeni modul: `src/player_intent_features.py`

Ana sorumluluklar:

- board encode etme
- feature turetme
- board before/after diff cikarma
- tehlike ve yukseklik metri gi uretme

### Yeni modul: `src/player_intent_labels.py`

Ana sorumluluklar:

- weak label heuristics
- confidence hesaplama
- label versioning

### Yeni script: `scripts/analytics/build_player_intent_dataset.py`

Ana sorumluluklar:

- local JSONL session dosyalarini oku
- export dataset uret
- anonymize et
- train/val/test split cikar

## Kayit Yeri ve Dosya Duzeni

Bu veri Cloud'a gitmemeli.

Sebep:

- buyuk dosya uretir
- mahremdir
- runtime icin zorunlu degildir
- model egitimi icin daha cok lokal veya ayri export akisi gerekir

Onerilen yol:

`get_local_data_dir()` altinda yeni bir klasor.

Onerilen agac:

```text
local/
  player_intent/
    manifests/
      session_<id>.json
    sessions/
      date=2026-04-05/
        part_0001.jsonl
        part_0002.jsonl
    exports/
      dataset_v1.jsonl
```

Not:

- `atomic_write_json` manifest ve metadata icin uygun
- yüksek frekansli event append icin rolling JSONL daha dogru
- part dosyalari boyut sinirina gore rollover yapmali

## Mevcut Koda Tam Nereye Hook Atmali

### 1. `Game.__init__`

Burada:

- telemetry setting okunur
- recorder olusturulur
- session meta baslatilir
- ilk queue/current piece snapshot'i baslatilir

### 2. `Game.handle_input()`

Burada action-level kayit yapilir.

Kayitlanmasi gerekenler:

- move left/right success veya fail
- rotate success ve wall-kick kullanimi
- hold kullanimi
- hard drop mesafesi
- soft drop baslama ve bitis

Kural:

- sadece anlamli state degisimi varsa event yaz
- key repeat spam'i degil, state change log'u tutulmali

### 3. `Game._update_das()`

Burada manual yatay hareket ile DAS kaynakli hareket ayrilabilir.

Bu veri niyet analizi icin degerli cunku:

- oyuncu duzeltme mi yapiyor
- hizli kaydirma mi yapiyor
- well'e hizli gomuyor mu

### 4. `Game.update()`

Burada su anlar yakalanmali:

- grounded'a ilk giris
- soft drop step
- auto-lock oncesi son snapshot

Ama burada her frame log alinmamali.

### 5. `Game.lock_and_new_piece()`

Bu sistemin altin noktasi burasi.

Burada su yapilmali:

- `board_before` snapshot al
- `piece_before_lock` snapshot al
- `board.lock_piece()` sonucu al
- `board_after` ve line-clear sonucunu kaydet
- episode'u finalize et
- sonraki piece icin yeni episode baslat

Bu metod ana single-player omurganin en dogru finalizasyon noktasi.

### 6. `Board.lock_piece()`

Ilk fazda recorder mantigi buraya tasinmamali.

Board saf oyun kurali katmani olarak kalmali. Gerekirse daha sonra `LockResult` gibi zengin bir sonuc objesi dondurmesi dusunulebilir, ama ilk fazda buna ihtiyac yok.

## Mevcut Mod Kopyalari ve Riskler

`lock_and_new_piece()` mantigi birden fazla dosyada dagilmis durumda:

- `src/game.py`
- `src/game_modes.py`
- `src/game_modes_advanced.py`
- `src/game_modes_extra.py`
- `src/campaign/campaign_mode.py`
- `src/tutorial.py`
- `src/pvp_game.py`

Bu nedenle recorder entegrasyonu tek hamlede tum modlara yayilmamali.

Dogru strateji:

1. Once `Game` tabanli single-player omurgayi dogrula
2. Sonra child class farklarini adapter ile ele al
3. PvP ve campaign icin ayri `context adapter` katmani ekle

## Weak Label Uretim Stratejisi

Ham kayitlari egitim etiketine cevirmek icin ikinci bir katman lazim.

### Heuristic label engine ilkeleri

Asagidaki kurallar ilk versiyon icin yeterli olur:

- `max_height` belirgin dustuyse: `survive_reduce_height`
- `hole_count` dustuyse: `clean_holes_or_garbage`
- well korunup line alinmadiysa: `preserve_tetris_well`
- iyi bir well acildiysa: `build_tetris_well`
- kritik yukseklikte 1-2 satir alindiysa: `burn_for_safety`
- combo artip board acik kaldiysa: `combo_continue`
- hold ile yuksek degerli parca saklandiysa: `hold_for_future_value`
- kotu board ustunde duzeltici placement varsa: `recover_misdrop`

### Confidence mantigi

- tek kuvvetli kural: orta guven
- birden fazla bagimsiz kural ayni niyeti destekliyorsa: yuksek guven
- catisan kural varsa: `unknown` veya dusuk guven

### Human review akisi

Ikıncı dalgada su lazim olacak:

- belirsiz episode'leri ayikla
- kucuk bir review araci ile insan duzeltsin
- `reviewed` label set olussun

Bu katman olmadan model, sadece heuristic'i ezberleme riski tasir.

## Performans ve Runtime Butcesi

Bu sistem gameplay hissini bozmamali.

Butce hedefleri:

- input event basina minimal ek maliyet
- frame basina sifira yakin maliyet
- tam board serilestirmesi sadece spawn/snapshot/lock anlarinda
- disk yazimi buffered ve part file tabanli
- buyuk boyutlu export runtime'da degil, offline script ile

Onerilen pratikler:

- occupancy encode kucuk tutulmali
- sadece state degisince event yazilmali
- `fsync` her eventte degil, parca veya batch bazli yapilmali
- runtime'da ML inference henüz yokken recorder tamamen pasif olabilmeli

## Ayar ve Guvenlik Kararlari

Onerilen yeni ayarlar:

- `collect_player_intent_telemetry`
- `player_intent_sampling_rate`
- `player_intent_capture_raw_board`
- `player_intent_max_local_storage_mb`

Env override ornekleri:

- `QUADRIX_INTENT_TRACE=1`
- `QUADRIX_INTENT_TRACE_DIR=...`

Mahremiyet karari:

- export dataset'te acik username veya Steam ID tutulmamali
- `profile_id` hash'lenmeli veya anonimlestirilmeli
- ekran goruntusu ilk fazda toplanmamali

## Fazlandirilmis Uygulama Plani

## Faz 0: Taksonomi ve Schema Freeze

Hedef:

- `intent_primary` listesi sabitlensin
- episode schema v1 tanimlansin
- snapshot anlari karara baglansin

Teslimatlar:

- schema dokumani
- label taxonomy v1
- data retention karari

## Faz 1: Recorder Omurgasi

Hedef:

- single-player `Game` akisina recorder eklemek

Kod alanlari:

- yeni `src/player_intent_recorder.py`
- yeni `src/player_intent_features.py`
- `src/game.py` hook'lari
- gerekiyorsa `src/data_paths.py` yardimcisi kullanimi

Beklenen sonuc:

- classic/sprint/ultra/zen icin local JSONL session dosyalari olusur
- her piece episode spawn->lock arasi kaydolur

## Faz 2: Weak Label Engine

Hedef:

- ham episode'lardan zayif niyet etiketi uretmek

Kod alanlari:

- yeni `src/player_intent_labels.py`
- offline export script

Beklenen sonuc:

- heuristically labeled dataset v1

## Faz 3: Dataset Export ve QA

Hedef:

- egitime uygun temiz dataset uretmek

Icerik:

- anonymization
- dedupe
- train/val/test split
- label distribution raporu
- uncertain sample raporu

## Faz 4: Human Review Loop

Hedef:

- dusuk guvenli kayitlarin insan tarafindan duzeltilmesi

Beklenen sonuc:

- gold subset
- heuristic bias azaltma

## Faz 5: Shadow Inference

Hedef:

- modeli oyunda sadece izleme modunda denemek

Yapilacaklar:

- live observation snapshot ver
- modelin top-k intent tahminini logla
- oyuncuya UI'da gosterme, sadece dogrulama icin sakla

## Faz 6: Mod Genisletme

Sira:

1. campaign
2. mystery/perk varyasyonlari
3. pvp

Sebep:

- bu modlar farkli niyet uzayina sahip
- ayni model yerine adapter ya da ayri label space gerekebilir

## Test Plani

Yeni test paketi en az su kapsami icermeli:

- recorder disabled iken hic dosya yazilmaz
- move/rotate/hold/hard_drop event'leri dogru kaydolur
- `lock_and_new_piece()` episode'u finalize eder
- queue ve hold once/sonra state'i tutarlidir
- local path disinda yere yazilmaz
- rollover dosyalari bozulmaz
- weak label heuristics deterministic calisir

Onerilen test dosyalari:

- `tests/test_player_intent_recorder.py`
- `tests/test_player_intent_game_hooks.py`
- `tests/test_player_intent_storage_rotation.py`
- `tests/test_player_intent_labels.py`

## Ilk Uygulanacak Minimum Paket

Eger bu plani koda cevirmeye hemen baslanacaksa en dogru ilk paket su olur:

1. `src/player_intent_recorder.py` iskeletini ekle
2. `src/game.py` icine sadece single-player hook'lari koy
3. `get_local_data_dir()` altina local session yazimi bagla
4. `piece episode` JSONL v1 formatini sabitle
5. 3-4 tane temel test ekle

Bu ilk paket su soruya cevap vermeli:

"Oyuncunun bir parcayi spawn'dan lock'a kadar hangi baglamda nasil oynadigini kayipsiz ve dusuk maliyetle toplayabiliyor muyuz?"

Bu cevap evet olunca ancak sonraki adim olan intent labeling ve model egitimi anlamli olur.

## Son Karar

Bu sistemin temeli, oyuna AI modeli yapistirmak degil; once oyunun karar anlarini egitim verisine cevirecek saglam bir telemetry omurgasi kurmaktir.

Dogru sira su olmalidir:

1. observation toplama
2. piece episode finalization
3. weak label uretimi
4. review loop
5. model egitimi
6. shadow inference
7. canli yorumlama

Bu sirayi bozup ham tus logundan dogrudan niyet modeli egitmeye calismak, dusuk kaliteli ve yanlis ogrenen bir sistem uretir.
