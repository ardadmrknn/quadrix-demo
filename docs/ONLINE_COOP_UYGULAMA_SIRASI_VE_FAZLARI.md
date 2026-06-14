# Online Co-op Uygulama Sırası ve Faz Planı

> Tarih: 13 Nisan 2026  
> Amaç: Online co-op işini hangi sırayla, hangi dosyalara dokunarak, hangi faz kapılarıyla ilerletmemiz gerektiğini operasyonel seviyede tanımlamak  
> Dayanak belge: [ONLINE_COOP_ANALIZ_VE_MIMARI.md](ONLINE_COOP_ANALIZ_VE_MIMARI.md)

---

## Bu Belge Ne İçin Var?

İlk belge olan [ONLINE_COOP_ANALIZ_VE_MIMARI.md](ONLINE_COOP_ANALIZ_VE_MIMARI.md) mimari yönü, teknik kararları, reuse alanlarını ve riskleri tanımlar.

Bu ikinci belge ise şu sorunun cevabıdır:

"Tamam, ne yapacağımızı biliyoruz; peki bunu hangi sırayla, hangi parçaları önce bitirerek, hangi dosyalara dokunarak ve hangi kapılardan geçerek geliştireceğiz?"

Bu nedenle bu doküman:
- günlük geliştirme sırasını,
- faz bazlı teslimleri,
- hangi faz bitmeden hangisine geçilmemesi gerektiğini,
- dosya bazlı iş dağılımını,
- her fazın çıkış kriterlerini,
- teknik borç ve risk yönetimini
tanımlar.

---

## Okuma Sırası

Bu belge tek başına okunmak için değil, ilk belgeyle birlikte kullanılmak için yazıldı.

Önerilen okuma sırası:

1. [ONLINE_COOP_ANALIZ_VE_MIMARI.md](ONLINE_COOP_ANALIZ_VE_MIMARI.md)
   Amaç: Ne yapılacağını, hangi mimarinin seçildiğini, hangi reuse kararlarının alındığını anlamak.

2. [ONLINE_COOP_UYGULAMA_SIRASI_VE_FAZLARI.md](ONLINE_COOP_UYGULAMA_SIRASI_VE_FAZLARI.md)
   Amaç: Bu işi gerçek geliştirme sırasında hangi sırayla uygulayacağımızı görmek.

---

## Temel Yürütme İlkeleri

Bu işe başlarken aşağıdaki ilkeler sabit kabul edilir:

1. V1 önceliği iki oyunculu online co-op endless akışıdır.
2. Campaign desteği, endless akışı stabil olmadan başlatılmaz.
3. Online shell ekranları Online PvP'den reuse edilir.
4. Maç içi görünüm yerel `CoopGame` zincirinden gelir.
5. Simülasyon modeli authoritative host olarak kalır.
6. C++ bridge'e ancak gerçekten zorunluysa dokunulur; başlangıçta dokunulmaz.
7. V1'de hız için tek dosyalı `online_coop_game.py` yaklaşımı tercih edilir.
8. Kod tekrarının azaltılması V2 konusu olabilir; V1'de çalışan akış önceliklidir.

---

## Faz Haritası

| Faz | Başlık | Çıktı | Bloklayıcı mı? |
|-----|--------|-------|----------------|
| 0 | Scope Kilidi ve Teknik Sözleşmeler | Kararların sabitlenmesi | Evet |
| 1 | Giriş Noktaları ve Boş Shell | Menüden moda girilebilmesi | Evet |
| 2 | Networking Sözleşmesi ve Lobi Metadata | Lobi oluştur/katıl altyapısı | Evet |
| 3 | Online Shell UI | Giriş, bekleme, ready-check, countdown ekranları | Evet |
| 4 | Host Otoriteli Gameplay Köprüsü | Host tarafında gerçek co-op simülasyonu | Evet |
| 5 | Guest Render ve Match State Akışı | Guest tarafında maçın görülebilmesi | Evet |
| 6 | Prediction ve Input Düzeltme | Oynanabilir guest hissi | Public release için evet |
| 7 | Pause, Disconnect, Game Over Hardening | Stabil V1 akışı | Evet |
| 8 | Görsel Parite ve UX Parlatma | Yerel co-op ile aynı his | Evet |
| 9 | Campaign Online Entegrasyonu | V2 kampanya desteği | V1 için hayır |
| 10 | QA, Soak, Release Kapanışı | Yayına hazır build | Evet |

---

## Faz 0 — Scope Kilidi ve Teknik Sözleşmeler

### Amaç

Takımın geliştirme sırasında sürekli karar değiştirmesini engellemek. Bu fazda kod değil karar sabitlenir.

### Bu Fazda Sabitlenecek Kararlar

1. V1 kapsamı:
   - 2 oyunculu online co-op
   - endless destekli
   - lobby / join code / public list destekli
   - countdown, pause, disconnect, game over destekli

2. V1 dışı bırakılacaklar:
   - campaign online
   - reconnect-after-process-restart
   - spectator
   - 3+ oyuncu
   - sesli iletişim / chat sistemi

3. Teknik kararlar:
   - authoritative host
   - tek kanal (`CHANNEL_GAME = 0`)
   - online shell reuse = `OnlinePvPGame`
   - in-match render reuse = `CoopGame`
   - ilk iterasyonda `online_coop_game.py` içinde tek dosya yaklaşımı

4. İsim sözlüğü:
   - `mode = coop`
   - V1'de `sub_mode = endless` sabittir; `campaign` dalı Faz 9'da açılır
   - `campaign_level = int` yalnızca Faz 9 sonrası aktif kullanılır
   - `role = host | guest`

### Dokunulacak Dosyalar

- Kod dosyası yok
- Gerekirse yalnızca dokümantasyon

### Çıkış Kriterleri

- Takım V1 kapsamı üzerinde anlaşmış olmalı.
- İlk belgedeki mimari kararlarla çelişen açık madde kalmamalı.
- Faz 1 öncesinde “campaign de aynı anda girelim mi?” tarzı açık kapılar kapatılmış olmalı.

### Bu Faz Bitmeden Yapılmaması Gerekenler

- `online_coop_game.py` üretmek
- `steam_networking.py` içine yeni mesajlar eklemek
- menüye buton koymak

---

## Faz 1 — Giriş Noktaları ve Boş Shell

### Amaç

Oyuncunun ana menüden online co-op moduna güvenli biçimde girebilmesini sağlamak. Bu fazın sonunda lobby çalışmak zorunda değildir; ama mod açılmalı, kapanmalı ve çökmemelidir.

### Hedef Çıktı

- Ana menüde `Online Co-op` seçeneği görünür.
- Mod açılınca boş ama çalışan bir `OnlineCoopGame` instance oluşur.
- `handle_input()`, `update()`, `draw()`, `_cleanup()` yaşam döngüsü çalışır.
- ESC ile güvenli çıkış yapılır.

### Dokunulacak Dosyalar

- `src/menu.py`
- `src/main.py`
- `src/localization.py`
- `src/online_coop_game.py` yeni dosya

### Uygulama Adımları

1. `src/online_coop_game.py` oluştur.
   İçerik:
   - `OnlineCoopState` veya `OnlineState` benzeri state sabitleri
   - `__init__`
   - `handle_input`
   - `update`
   - `draw`
   - `_cleanup`

2. `src/main.py` içine import ekle.

3. `src/main.py` içinde `online_pvp` akışına paralel `online_coop` state yönetimi ekle.

4. `src/menu.py` içine yeni dashboard tile veya menü aksiyonu ekle.

5. `src/localization.py` içine minimum metinler ekle:
   - `mode_online_coop`
   - `mode_intro_online_coop_desc`
   - `online_coop_title`
   - `online_coop_placeholder`

### Tasarım Kuralı

Bu fazda gerçek Steam networking entegre edilmez. Ama state makinesi ve yaşam döngüsü iskeleti kurulur.

### Çıkış Kriterleri

- Menüden online co-op açılır.
- Boş ekran veya placeholder shell çizilir.
- Çıkışta cleanup çağrılır.
- Tam ekran geçişi / pencere resize akışı bozulmaz.

### Test Listesi

- Menüden moda gir
- ESC ile çık
- tekrar gir
- fullscreen aç/kapa
- farklı çözünürlükte aç
- crash olmuyor mu kontrol et

### Faz 1 Bitmeden Faz 2’ye Geçilmemesi Gereken Neden

Eğer yaşam döngüsü oturmadan networking entegre edilirse, hata ayıklarken sorunun UI state’ten mi yoksa Steam tarafından mı geldiği anlaşılmaz.

---

## Faz 2 — Networking Sözleşmesi ve Lobi Metadata

### Amaç

Online co-op için kullanılacak mesaj isimlerini, lobby metadata alanlarını ve Steam event bağlarını kurmak.

### Hedef Çıktı

- `SteamNetworking` üzerinden co-op lobisi oluşturulabilir.
- `mode=coop` metadata’sı set edilir.
- join code, lobby list, public/private filtreleri co-op için çalışır.
- `OnlineCoopGame` gerekli event’leri dinler.

### Dokunulacak Dosyalar

- `src/steam_networking.py`
- `src/online_coop_game.py`

### Uygulama Adımları

1. `src/steam_networking.py` içine yeni `MsgType` sabitlerini ekle:
   - `guest_input`
   - `piece_state`
   - `lock_event`
   - `game_event`
   
   Not: `objective_state` V1'e dahil değildir; campaign ile birlikte Faz 9'da eklenir.

2. `OnlineCoopGame.__init__` içinde şu alanları tanımla:
   - `_lobby_list`
   - `_lobby_list_filter`
   - `_lobby_list_fetching`
   - `_pending_lobby_list`
   - `_status_msg`
   - `_lobby_code`
   - `_join_code_active`
   - `_join_code_input`
   - `_join_code_error`
   - `my_ready`
   - `opponent_ready`
   - `selected_submode` (V1'de sabit `endless`)

3. `_init_networking()` benzeri akışı `OnlinePvPGame`’den uyarlayarak yaz.
   İçerik:
   - `pause_pump()`
   - `net.init()`
   - event registration
   - başarısızlık halinde `_status_msg`

4. Lobi metadata sözleşmesini uygula:
   - `game = quadrix`
   - `mode = coop`
   - `sub_mode = endless`
   - `host_name = ...`
   - `visibility = public | private`
   - `lobby_code = 6 digit`
   - `metadata_ready = true`

   V1 istemcisi `sub_mode != endless` gelen lobileri liste dışı bırakmalı veya join-disabled göstermelidir.

5. Şu handler’ları ekle:
   - `_on_lobby_created`
   - `_on_lobby_joined`
   - `_on_member_joined`
   - `_on_member_left`
   - `_on_lobby_list_complete`
   - `_on_lobby_list_error`

6. Co-op için şu aksiyon fonksiyonlarını yaz:
   - `_create_private_endless_lobby`
   - `_create_public_endless_lobby`
   - `_request_coop_lobby_list`
   - `_join_lobby_by_code`

   Campaign lobi oluşturma akışları Faz 9'da eklenir.

### Çıkış Kriterleri

- İki makinede co-op lobi oluşturma mümkün.
- Lobi listesinde `mode=coop` filtrelenebiliyor.
- Kod ile katıl akışı çalışıyor.
- Waiting state’e kadar gidilebiliyor.

### Test Listesi

- private endless lobby oluştur
- public endless lobby oluştur
- kod ile katıl
- listeden katıl
- yanlış kod gir ve hata mesajını gör
- metadata eksik lobi geldiğinde sistem çökmesin
- `sub_mode != endless` lobi V1 istemcisinde joinable görünmesin

### Faz 2 Bitmeden Faz 3’e Geçilmemesi Gereken Neden

Shell UI’ı gerçek event akışına bağlamadan önce data kontratı sabitlenmezse, daha sonra tüm buton-action wiring yeniden yapılır.

---

## Faz 3 — Online Shell UI

### Amaç

Online co-op için giriş, bekleme, ready-check, countdown ve disconnected ekranlarının gerçek görsel shell’ini kurmak.

### Hedef Çıktı

- Online PvP’den reuse edilen ama co-op semantiğine çevrilmiş tüm online-shell ekranları çalışır.
- Butonlar gerçek aksiyonlara bağlıdır.
- Waiting ve ready-check akışı oynanabilir eşleşmeye kadar gelir.

### Dokunulacak Dosyalar

- `src/online_coop_game.py`
- gerekirse `src/localization.py`

### Uygulama Adımları

1. `OnlinePvPGame` kaynaklı şu ekran bloklarını adapte et:
   - `_draw_lobby_menu`
   - `_draw_join_code_input`
   - `_draw_waiting_screen`
   - `_draw_ready_check`
   - `_draw_countdown`
   - `_draw_disconnected`

2. Tüm ekranlarda ortak helper kullan:
   - `draw_glass_panel`
   - `draw_uniform_button`
   - `get_font`
   - `get_fitting_font`

3. V1 için co-op özel metinler ve rozetler ekle:
   - `Endless`
   - `Takım Arkadaşı Bekleniyor`
   - `Co-op Lobi Alanına Dön`
   - `Hazır`
   - `Hazır Değil`

   `Campaign` ve `Level X` etiketleri Faz 9'da eklenir.

4. Lobby menu’de action rail ve right-side lobby list panelini ayrı mantık blokları olarak tut.

5. Ready-check ekranında `VS` kararını sabitle:
   - V1 önerisi: `CO-OP`
   - alternatif ikon çözümü V2’ye bırakılabilir

6. Countdown state geçişlerini gerçek ready akışıyla bağla.

### Çıkış Kriterleri

- Host create → waiting
- guest join → ready-check
- iki taraf ready → countdown
- countdown sonrası gameplay bootstrap noktasına geçiş

### Test Listesi

- join code panel aç/kapat
- public/private filtre değiştir
- waiting ekranında copy code butonu
- invite friend butonu
- ready-check avatar yerleşimi
- countdown state geçişi

### Faz 3 Bitmeden Faz 4’e Geçilmemesi Gereken Neden

Oyuncular eşleşmeye güvenli giremeden gameplay fazına geçmek, debug sırasında sorunları gereksiz yere networking/gameplay karıştırır.

---

## Faz 4 — Host Otoriteli Gameplay Köprüsü

### Amaç

Host tarafında gerçek `CoopGame` simülasyonunu çalıştırmak ve guest input’larını bu simülasyona enjekte edebilmek.

### Hedef Çıktı

- Host gerçek `CoopGame` instance’ı açar.
- Guest input mesajları host’a gelir.
- Host bu input’ları `CoopGame` içine uygular.
- Oyun authoritative host olarak akar.

### Dokunulacak Dosyalar

- `src/coop_game.py`
- `src/online_coop_game.py`

### Uygulama Adımları

1. `coop_game.py` içine `inject_remote_input(player, input_event)` ekle.

2. `guest_input` payload'ını aksiyon çağrısı olarak değil, normalize input olayı olarak tanımla:
   - `seq`
   - `phase = key_down | key_up`
   - `control = left | right | rotate | soft_drop | hard_drop | hold`
   - `sent_at`

3. `inject_remote_input()` host tarafında yerel `handle_input()` ile aynı state alanlarını sürmeli:
   - left/right key_down ve key_up = DAS state başlatma / bırakma
   - soft_drop key_down ve key_up = hold state açma / kapama
   - rotate / hard_drop / hold = edge-trigger input

4. `CoopGame`’in mevcut event sistemi kullanılacaksa, `_event_listeners` üstünden network hook bağla.

5. `OnlineCoopGame` içinde host rolü için şu alanları oluştur:
   - `self.coop_game`
   - `self.role = 'host'`
   - guest input queue
   - host snapshot timers
   - message seq sayaçları

6. `game_start` aşamasında host şu işi yapsın:
   - `CoopGame(...)` instance oluştur
   - V1 için endless initial setup yap
   - Faz 9'da level config branch'ini ekle
   - countdown bitince `PLAYING` state’e geç

7. Host tarafında her frame şu akış çalışsın:
   - network tick
   - guest input dequeue
   - `inject_remote_input('P2', ...)`
   - lokal P1 input uygula
   - `coop_game.update(delta_ms)`
   - event’leri topla

8. Host message handler’ında `guest_input` işle.

### Çıkış Kriterleri

- Host tarafında gerçek `CoopGame` çalışıyor olmalı.
- Guest input host’a ulaşıp simülasyonu etkiliyor olmalı.
- Gameplay authoritative olarak host üzerinde ilerlemeli.

### Test Listesi

- guest left key_down gönder → host’ta P2 DAS başlatır
- guest left key_up gönder → host’ta P2 DAS durdurur
- guest rotate gönder → host’ta P2 döner
- guest soft_drop key_down / key_up → host’ta basılı tutma doğru çalışır
- guest hold gönder → host’ta hold çalışır
- guest input spam’inde crash olmamalı

### Bu Fazda Bilerek Eksik Bırakılabilecekler

- guest tarafında final görsel parite
- prediction
- reconnect

---

## Faz 5 — Guest Match State ve Render Akışı

### Amaç

Guest tarafında host’un authoritative state’ini görmek ve maçı gerçek zamanlı izlemek/oynamak.

### Hedef Çıktı

- Guest host’tan gelen board/piece state ile maçı görür.
- Guest yalnızca shell değil, gerçek maç ekranına geçer.
- Oyun baştan sona iki uçta görünür biçimde akar.

### Dokunulacak Dosyalar

- `src/online_coop_game.py`
- gerekirse `src/coop_game.py` render reuse için

### Uygulama Adımları

1. Host → guest mesajlarını aktif et:
   - `board_state`
   - `piece_state`
   - `lock_event`
   - `game_event`

2. Guest tarafında şu state bloklarını oluştur:
   - `remote_grid`
   - `remote_owners`
   - `remote_score`
   - `remote_level`
   - `remote_contribution`
   - `remote_piece_state`
   - `remote_hold_next_state`

3. Render stratejisini seç:
   - tercih edilen: `CoopGame` çizim helper’larını reuse etmek
   - alternatif: `OnlineCoopGame` içinde guest render için minimal uyarlama katmanı

4. Guest `PLAYING` state’te shell ekranı değil, co-op maç ekranı çizmeye başlasın.

5. `lock_event` geldiğinde guest tarafında:
   - skor güncelle
   - line clear feedback güncelle
   - frozen/pending_unfreeze alanlarını güncelle

### Çıkış Kriterleri

- Guest maç ekranını görebiliyor olmalı.
- Host ve guest aynı anda maçın mantıklı bir temsilini görüyor olmalı.
- Match başlatılabiliyor ve bitirilebiliyor olmalı.

### Test Listesi

- host line clear yapınca guest’te görünmesi
- P1/P2 active piece state senkronu
- hold/next panel güncellemesi
- freeze overlay görünümü
- game over ekranına geçiş

### Faz 5 Sonunda Beklenen Seviye

Bu noktada oyun teknik olarak oynanabilir olabilir; ama guest input hissi henüz yeterince iyi olmayabilir.

---

## Faz 6 — Prediction ve Input Düzeltme

### Amaç

Guest tarafında input gecikmesini daha az hissedilir hale getirmek.

### Hedef Çıktı

- Guest left/right ve soft_drop basma-bırakma akışlarında anında görsel tepki alır.
- Host ACK geldiğinde guest state’i doğrulanır.
- Gerekirse correction/snap yapılır.

### Dokunulacak Dosyalar

- `src/online_coop_game.py`

### Uygulama Adımları

1. Guest tarafında local predicted piece state ve pressed input state tut.

2. `guest_input.seq` sistemi oturt.

3. Host `piece_state` içine `input_ack` eklesin.

4. Guest tarafında şu kuralları uygula:
   - left/right key_down-key_up: prediction açık
   - rotate: prediction açık
   - soft_drop key_down-key_up: prediction açık
   - hard_drop: prediction kapalı
   - hold: prediction kapalı veya çok kontrollü

5. Prediction katmanı yerel `handle_input()` ile aynı pressed-state modelinden yürümeli; sentetik `move_left` spam'i üretmemeli.

6. Correction mekanizması:
   - fark küçükse yumuşak düzeltme
   - fark büyükse anlık snap

### Çıkış Kriterleri

- Guest hissi yerel olmayan ama rahatsız edici olmayan seviyeye gelir.
- Duvar çarpışmalarında correction mantıklı davranır.
- Prediction desync yaratmaz.

### Test Listesi

- hızlı sol/sağ spam
- rotate spam
- soft drop tutma
- duvara yaslanıp rotate etme
- lock sınırında correction

---

## Faz 7 — Pause, Disconnect, Game Over Hardening

### Amaç

V1’in kararlı sayılması için gereken oyun dışı ama kritik akışları tamamlamak.

### Hedef Çıktı

- ortak pause çalışır
- disconnect grace period çalışır
- disconnected ekranı doğru açılır
- game over / sonuç ekranı iki tarafta doğru akar

### Dokunulacak Dosyalar

- `src/online_coop_game.py`
- gerekirse `src/steam_networking.py`

### Uygulama Adımları

1. Pause sözleşmesini tamamla:
   - pause request
   - resume
   - hangi tarafın resume yetkili olduğu

2. Disconnect grace süresi uygula:
   - kısa kesinti = bekle
   - uzun kesinti = disconnected ekranı

3. Game over nedenlerini tek yerde topla:
   - double freeze
   - manual exit
   - disconnect
   - host abort

4. Sonuç ekranında host-authoritative final data kullan.

5. `_cleanup()` akışını güvenli hale getir:
   - networking shutdown
   - lobby leave
   - pump resume
   - dangling state reset

### Çıkış Kriterleri

- ESC ile ortak pause çalışır.
- Kablo çekme / process kill senaryolarında uygulama çökmez.
- Ana menüye temiz dönülür.

### Test Listesi

- host pause
- guest pause
- host disconnect
- guest disconnect
- countdown sırasında çıkış
- game over sonrası menüye dönüş

---

## Faz 8 — Yerel Parite ve UX Parlatma

### Amaç

Teknik olarak çalışan sistemi yerel co-op ile aynı hisse getirmek.

### Hedef Çıktı

- Görsel parite checklist’i sağlanır.
- Ses/ayar davranışı yerel ile aynı olur.
- Shell ve in-match görünüm tek stil ailesi gibi davranır.

### Dokunulacak Dosyalar

- `src/online_coop_game.py`
- gerekirse `src/coop_game.py`
- `src/localization.py`

### Uygulama Adımları

1. `CoopGame` render parity checklist’i tek tek doğrula.

2. Waiting / ready / disconnected ekranlarında accent renkleri co-op paletine çek.

3. HUD’ta network-only bilgileri eklerken local görünümü bozma.

4. Pause içi settings davranışını yerel akışla hizala.

5. Parçacık, trail, shake yoğunluklarını local ile birebir test et.

### Çıkış Kriterleri

- Görsel fark “başka mod gibi” hissettirmeyecek kadar az olmalı.
- Oyuncu “bu local co-op’un online hali” diyebilmeli.

### Test Listesi

- local ve online’ı aynı çözünürlükte yan yana karşılaştır
- screenshot bazlı hizalama kontrolü
- volume slider davranışı
- theme / block style değişiminde görünüm bozuluyor mu kontrol et

---

## Faz 9 — Campaign Online Entegrasyonu

### Amaç

Endless stabil olduktan sonra campaign katmanını online co-op’a taşımak.

### Hedef Çıktı

- host lobby oluştururken level seçebilir
- guest level bilgisini görür
- objective ve star akışı host-authoritative çalışır

### Dokunulacak Dosyalar

- `src/online_coop_game.py`
- `src/campaign/coop_campaign_mode.py`
- `src/campaign/coop_level_select.py`
- `src/localization.py`

### Uygulama Adımları

1. Lobi shell’e sub_mode seçimi ekle.

2. Campaign ise host level picker akışını aç.

3. `game_start` payload’una level config ve objective state ekle.

4. Objective progress’i host’tan guest’e taşı:
   - `game_event`
   - veya ayrı `objective_state`

5. Level complete / fail / stars / save write kararını host-authoritative yap.

### Çıkış Kriterleri

- online campaign level açılabiliyor
- hedefler görünüyor
- yıldızlar doğru hesaplanıyor
- iki taraf da ilerleme kazanıyor

### Test Listesi

- level seçimi
- time limit objective
- balanced contribution objective
- freeze recovery objective
- level complete
- level failed

---

## Faz 10 — QA, Soak ve Release Kapanışı

### Amaç

Sistemi feature-complete olmaktan release-candidate seviyesine taşımak.

### Hedef Çıktı

- crash-free temel akış
- bilinen kritik bug kalmaması
- smoke test listesi tamamlanmış olması

### Dokunulacak Dosyalar

- Hata bulunan her ilgili dosya
- gerekiyorsa test ve dokümanlar

### Zorunlu QA Başlıkları

1. Soak test:
   - 20+ tam maç
   - art arda lobby create/join/leave

2. Ağ koşulları:
   - orta latency
   - kısa disconnect
   - packet loss benzeri davranış

3. UX:
   - yanlış kod girişleri
   - dolu lobiye katılma
   - host oyun kapatınca guest davranışı

4. Görsel:
   - farklı çözünürlükler
   - fullscreen/windowed
   - farklı dil setleri

5. Ayarlar:
   - music off/on
   - sfx off/on
   - volume slider
   - theme / block style farkları

### Release Kapı Kriterleri

- En az 2 makinede full flow çalışmalı.
- V1 kapsamı dışında kalan feature’lar release blocker olmamalı.
- Bilinen crash bug kalmamalı.
- Disconnect sonrası bozuk state ile menüye dönüş olmamalı.

---

## Fazlar Arası Geçiş Kuralları

1. Faz 1 bitmeden Faz 2’ye geçme.
2. Faz 3 bitmeden gameplay koduna tam dalma.
3. Faz 4 ve 5 tamamlanmadan campaign başlatma.
4. Faz 6 internal prototip için atlanabilir; public shipping için atlanmaz.
5. Faz 8 yapılmadan “local ile aynı his” iddiasında bulunma.
6. Faz 10 tamamlanmadan release etiketi vurma.

---

## Önerilen PR / Commit Dilimi

En pratik teslim modeli:

### V1 PR Seti

1. PR-1: Menü + main + boş `online_coop_game.py`
2. PR-2: Steam metadata + endless co-op lobby contract
3. PR-3: Lobi / waiting / ready / countdown shell UI
4. PR-4: `inject_remote_input()` + host authoritative bootstrap
5. PR-5: board_state / piece_state / guest render
6. PR-6: prediction + ack
7. PR-7: pause + disconnect + game over hardening
8. PR-8: local parity polish
9. PR-9: QA fixes ve release cleanup

### V2 PR Seti

10. PR-10: campaign online

Bu dilimleme review ve rollback açısından güvenlidir.

---

## Hangi Sırayı Kesinlikle Tersine Çevirmemeliyiz?

Şunlar kötü sıra örnekleridir:

### Kötü Sıra 1

Önce campaign online yapmak, sonra endless’i toparlamak.

Neden kötü:
- objective sync,
- level metadata,
- save write,
- victory/fail ekranları
erken karmaşıklık yaratır.

### Kötü Sıra 2

Önce prediction yazmak, sonra authoritative host kurmak.

Neden kötü:
- ACK yoksa prediction sağlam temele oturmaz.

### Kötü Sıra 3

Önce yeni co-op UI tasarlamak, sonra PvP shell reuse etmeyi düşünmek.

Neden kötü:
- gereksiz UI üretimi olur,
- bakım maliyeti artar,
- stil parçalanır.

---

## Nihai Yol Haritası Özeti

### V1 Shipping Slice

- Faz 0
- Faz 1
- Faz 2
- Faz 3
- Faz 4
- Faz 5
- Faz 6
- Faz 7
- Faz 8
- Faz 10

### V2 / Genişleme Slice

- Faz 9

Yani gerçekçi sırayla:

1. moda gir
2. lobi oluştur / katıl
3. bekleme / ready / countdown akışını oturt
4. host authoritative maçı ayağa kaldır
5. guest tarafında maçı göster
6. prediction ile hissi düzelt
7. pause / disconnect / game over’u sağlamlaştır
8. local parity polish yap
9. sonra campaign’i taşı

Bu sıra korunursa iş yönetilebilir kalır. Bu sıra bozulursa online co-op işi aynı anda hem networking, hem UI, hem render, hem campaign, hem UX problemi haline gelir.