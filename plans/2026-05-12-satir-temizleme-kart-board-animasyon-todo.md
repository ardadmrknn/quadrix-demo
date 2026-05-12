# 2026-05-12 Satır Temizleme ve Kart Board Animasyon Todo

Bu dosya kod değişikliğinden önce yapılan araştırma notlarını ve uygulanacak işi toplar.

## Araştırılan ana yüzeyler

- `src/board.py`
  - `lock_piece()`
  - `clear_lines()`
  - `apply_gravity()`
- `src/game.py`
  - `lock_and_new_piece()`
  - `_queue_line_clear_effects()`
  - `_start_block_fall_animation()`
  - `_get_block_fall_offset()`
  - `update()` içindeki `line_clear_sweep_active` ve `falling_block_animations` akışı
  - `draw()` içindeki `line_clear_pending_rows`, `line_clear_pending_colors`, `line_clear_sweep_rows` çizimi
- `src/game_modes_extra.py`
  - `MysteryMode.lock_and_new_piece()`
  - `MysteryMode._apply_card_effect()`
  - `MysteryMode._post_external_line_clear()`
  - `MysteryMode._clear_rows()`
  - `MysteryMode._clear_columns()`
  - `MysteryMode._apply_block_magnet()`
  - `MysteryMode._shuffle_bottom_rows()`
  - `MysteryMode._clear_drill_cells()`
  - `MysteryMode._level_peaks()`
  - `MysteryMode._apply_color_cleanse()`
  - `MysteryMode._execute_sniper_shot()`
  - `MysteryMode._restore_time_capsule()` / `_restore_time_capsule_state()`
  - `MysteryMode.draw_mode_overlay()`
  - `MysteryMode._spawn_sniper_explosion()` / `_draw_sniper_explosion_effects()`
- `src/game_modes_advanced.py`
  - `CascadeMode.lock_and_new_piece()`
- Testler
  - `tests/test_mystery_card_effect_behavior.py`
  - `tests/test_coop.py`

## Görev 1: Satır temizleme animasyonundan sonra blokların aşağı düşmesi

### Mevcut davranış özeti

- Temel kök neden: `src/board.py` içindeki `clear_lines()` satırları anında siliyor ve board state'i anında yeni haline geçiriyor.
- `src/game.py` bunu görsel olarak telafi etmeye çalışıyor:
  - silinen satırların eski görünümü `line_clear_pending_rows` ve `line_clear_pending_colors` ile tutuluyor,
  - yeni yerlerine geçmiş bloklar `falling_block_animations` ile yukarıdan düşüyormuş gibi çiziliyor,
  - yani oyun mantığında düşüş çoktan olmuş oluyor, oyuncu sadece bunun overlay halini görüyor.
- Bu yüzden satır temizleme efekti ile blok düşüşü gerçek anlamda iki ayrı faz değil; mantıkta tek adım, ekranda sahte ayrıştırma var.
- `MysteryMode.lock_and_new_piece()` temel lock akışını `super().lock_and_new_piece()` üzerinden kullandığı için bu davranış Card Mastery moduna da aynen taşınıyor.
- `CascadeMode.lock_and_new_piece()` ayrı bir akış kuruyor ve satır temizleme + gravity zincirini bilinçli olarak kendi içinde yönetiyor. Bu mod, ana davranış değişirse ayrıca korunmalı.

### Falsifiable local hypothesis

- Kullanıcının istediği davranışın önündeki ana engel, `Board.clear_lines()` ve devamındaki gravity sonucunun animasyon bitmeden board'a uygulanması.
- Eğer satır temizleme sonucunu geciktirilmiş bir "pending resolve" aşamasına taşırsak, bloklar gerçekten sweep/clear animasyonundan sonra düşmeye başlayabilir.

### Uygulama yönü

- [ ] Satır temizleme için mantık ve görsel çözümü iki faza ayır.
- [ ] `Game.lock_and_new_piece()` içinde satır temizleme tespit edildiğinde şu üç şeyi ayrı tut:
  - temizlenecek satır snapshot'ı,
  - temizleme sonrası hedef board state,
  - animasyon bitene kadar kullanılacak geçici render state.
- [ ] Board mutasyonunun ne zaman uygulanacağına karar ver:
  - seçenek A: `clear_lines()` çağrısını animasyon bitimine ertele,
  - seçenek B: board'u hemen çöz ama çizimde yeni yerlerine geçen blokları animasyon bitene kadar gizle ve düşüşü gerçekten animasyon sonunda başlat.
- [ ] En küçük ve güvenli çözüm seçilirken `MysteryMode`, `PvP`, `Coop`, `Online PvP` kodlarının da aynı line-clear altyapısını kullandığı unutulmasın.
- [ ] `CascadeMode` bu değişiklikten yanlış etkilenmesin.
  - Bu modun tasarımı zincir gravity olduğu için normal modla aynı akışa zorlanmamalı.
- [ ] `line_clear_pending_rows`, `line_clear_pending_colors`, `line_clear_sweep_rows`, `falling_block_animations` durumlarının yaşam döngüsünü yeniden düzenle.
- [ ] Sweep bitiş anı ile block-fall başlangıç anı arasındaki geçiş tek bir kontrol noktasına taşınsın.
- [ ] Çizim tarafında eski satır snapshot'ı ile yeni blokların aynı anda çakışıp çakışmadığı tekrar gözden geçirilsin.

### Riskler

- `board.last_cleared_lines` ve `board.last_cleared_colors` çok yerde kullanılıyor; erken temizlenirse efektler kaybolabilir, geç temizlenirse yanlış flash kalabilir.
- Satır temizleme sonrası skor, combo, seviye ve achievement akışı görsel gecikmeden bağımsız çalışıyor; animasyon gecikmesi bunları bozmamalı.
- Co-op / PvP tarafında da benzer pending-line çizimi var; temel davranış değişirse oralar da hizalanmalı.

### Test todo

- [ ] Temel Game akışı için dar kapsamlı test ekle: satır dolduğunda board resolve ile fall animasyon başlangıcı aynı frame'de olmamalı.
- [ ] Sweep bittikten sonra düşüş animasyonu başladığını doğrulayan test ekle.
- [ ] `CascadeMode` için regresyon testi ekle ya da mevcut davranışın korunduğunu doğrula.
- [ ] Mevcut co-op/pvp pending-row testleri yeniden geçirilip gerekiyorsa güncellensin.

## Görev 2: Kart ustalığında board'u değiştiren kartlar için anlaşılır animasyon

### Mevcut davranış özeti

- Şu anda kartların büyük kısmı board'u doğrudan mutate ediyor ve oyuncuya çoğunlukla sadece üstte kısa bir text toast (`card_message`) gösteriliyor.
- Ortak görsel state yok; kartın neyi sildiği, neleri kaydırdığı veya nerede yeni düzen oluştuğu çoğu zaman board üzerinde işaretlenmiyor.
- İstisnalar:
  - `sniper_shot`: hedefleme overlay'i ve hücre üstü GIF patlaması var.
  - `clear_rows`: bazı durumlarda `falling_block_animations` dolduruyor.
  - `mini_bomb` / `nova_burst`: merkezde power particle üretiyor ama tüm etkilenen hücreleri açıkça göstermiyor.
  - `laser_drill`: parçayı kırmızıya boyuyor ama temizlenen hücreler için ayrı bir board animasyonu yok.

### Board'u doğrudan etkileyen kartlar / akışlar

- `clear_rows` / Alt Süpür
  - alttan satır siler, sonra gravity uygular, sonra oluşan tam satırları temizleyebilir.
- `column_cleanse`
  - rastgele sütun(lar)ı tamamen siler.
- `gravity_well`
  - gravity uygular, yeni dolan satırlar oluşursa temizler.
- `peak_sculpt`
  - en yüksek kolonların tepesinden blok koparır.
- `block_magnet`
  - her satırdaki blokları sola yaslar.
- `row_shuffle`
  - alt bölgedeki dolu/boş hücreleri karıştırır.
- `laser_drill`
  - düşen parça ilerledikçe çarptığı blokları siler.
- `sniper_shot`
  - tek hücre siler.
- `mini_bomb`
  - lock sonrası komşu hücreleri siler.
- `nova_burst`
  - lock sonrası 3x3 alanı temizler.
- `gambler_dice`
  - ya tüm board'u temizler ya da board'un yarısını doldurur.
- `color_cleanse`
  - rastgele bir rengi topluca temizler, sonra gravity ve ek line clear tetikleyebilir.
- `time_capsule`
  - kaydedilmiş eski board durumunu aniden geri yükler.

### Falsifiable local hypothesis

- Board'a etkisi olan kartların anlaşılmamasının ana nedeni, kart helper'larının before/after farkını hiçbir ortak state'e kaydetmeden board'u anında değiştirmesi.
- Eğer ortak bir board-delta efekt katmanı eklenirse, her kart için tek tek özel animasyon yazmadan oyuncuya "ne silindi / ne taşındı / ne eklendi" açıkça gösterilebilir.

### Uygulama yönü

- [ ] `MysteryMode` içinde ortak bir board-delta görsel sistemi tanımla.
  - giriş: effect id, before snapshot, after snapshot
  - çıktı: silinen hücreler, taşınan hücreler, yeni dolan hücreler, belki etki merkezi
- [ ] Snapshot formatı `grid`, `occupancy`, `texture_grid`, `gold`, `owners` ile uyumlu olsun.
- [ ] Ortak render katmanı için minimum efekt tiplerini belirle:
  - remove: kısa flash + fade + particle
  - move: eski hücreden yeni hücreye kısa slide/fall
  - add: pulse / glow / spawn pop
- [ ] `draw_mode_overlay()` veya Game draw zincirine kart-board-efekt renderer'ı ekle.
- [ ] `sniper_shot` mevcut patlama efektini yeni ortak sistemle çakışmayacak şekilde entegre et.
- [ ] `clear_rows` mevcut `falling_block_animations` davranışını yeni sistemle çifte efekt üretmeyecek şekilde hizala.
- [ ] `gambler_dice` için iki farklı preset tanımla:
  - jackpot: tüm board wipe
  - bad roll: yeni blokların board'a dolma/pulse animasyonu
- [ ] `time_capsule` restore için anlık state sıçraması yerine kısa rewind/ghost overlay düşün.
- [ ] `laser_drill`, `mini_bomb`, `nova_burst` gibi lock sonrası hücre silen etkilerde etkilenen hücre koordinatları zaten elde ediliyor; bunlar doğrudan görsel katmana beslensin.
- [ ] `block_magnet` ve `row_shuffle` için sadece particle yetmez; hücrelerin eski ve yeni konumu gösterilmeli.
- [ ] `column_cleanse`, `peak_sculpt`, `color_cleanse` için hangi hücrelerin silindiği board üstünde açıkça parlamalı.

### Önerilen ilk faz kapsamı

- [ ] Faz 1: board delta altyapısı
- [ ] Faz 1: `clear_rows`, `block_magnet`, `row_shuffle`, `color_cleanse`, `column_cleanse`
- [ ] Faz 1: `gambler_dice` iki sonucu
- [ ] Faz 2: `laser_drill`, `mini_bomb`, `nova_burst`, `time_capsule`
- [ ] Faz 2: görsel preset iyileştirmeleri ve balans

### Test todo

- [ ] `tests/test_mystery_card_effect_behavior.py` içinde her ana kart helper'ı için sadece board state değil, görsel state de assert edilsin.
- [ ] `clear_rows` için mevcut fall animation testleri yeni sistemle uyumlu hale getirilsin.
- [ ] `block_magnet`, `row_shuffle`, `color_cleanse`, `gambler_dice` için board-delta queue üretildiğini doğrulayan testler eklensin.
- [ ] `sniper_shot` mevcut overlay/patlama davranışı ile yeni board-delta efektinin birlikte çalıştığı doğrulansın.

## Tasarım notları

- Mümkün olduğunca mevcut altyapı yeniden kullanılmalı:
  - `create_line_clear_particles()`
  - `create_power_particles()`
  - `falling_block_animations`
  - sniper explosion çizimi
- Kart başına bağımsız, dağınık efekt state'i yerine tek bir ortak queue daha sürdürülebilir olur.
- Sweep-only veya card-source satır temizlemeleri oyuncu-line statistiklerini şişirmemeli; bu repoda bu konuda zaten hassasiyet var.

## Uygulama sırası

- [ ] Önce Görev 1 için satır temizleme resolve sırasını netleştir.
- [ ] Sonra Görev 2 için ortak board-delta effect altyapısını ekle.
- [ ] Ardından kart helper'larını tek tek bu altyapıya bağla.
- [ ] Son olarak testleri ve gerekiyorsa co-op/pvp uyumunu güncelle.

## Not

- Bu dosya araştırma sonucu oluşturuldu. Henüz oyun davranışını değiştiren kod edit'i yapılmadı.