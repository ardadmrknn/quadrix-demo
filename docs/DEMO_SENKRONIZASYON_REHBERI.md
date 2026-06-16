# Quadrix Demo Senkronizasyon ve Geçiş Rehberi

Bu kılavuz, `v2` (ana/full oyun) ile `quadrix-demo` (demo sürümü) arasındaki git geçmişini, yapılan değişiklikleri ve ana oyundan demo sürümüne aktarılacak özelliklerin entegrasyon adımlarını ve kısıtlarını ayrıntılı şekilde tanımlar.

---

## 1. Git Geçmişi ve Son Değişiklikler Analizi

### A. v2 (Ana Oyun) Son 3 Günde Yapılan Değişiklikler (14 - 16 Haziran 2026)
1. **Lock Delay ve SRS+ 180 Kicks Refaktörü (`f21ca5e`, `50fb89d`):**
   * **Merkezileştirilmiş Lock Delay:** Lock delay sıfırlama (stalling) mantığı `_update_grounded_after_action` adında yeni bir instance metoduna taşınarak sadeleştirildi.
   * **Tetr.io Standartlarında Lock Delay Sıfırlaması:** Yatay hareketlerde ve döndürmelerde parça tabana temas ediyorsa (grounded) lock timer sıfırlanır. Maksimum 15 reset veya tabanda geçen toplam 3000ms süresi aşıldığında parça kilitlenir.
   * **Step Reset & Düşüş Sıfırlaması:** Parça yer çekimiyle daha aşağı seviyeye indiğinde (y düzeyi arttığında) limit sayaçları sıfırlanır.
   * **SRS+ 180 Kicks Güncellemesi:** Normal parçalar ve I parçası için SRS+ 180 derece döndürme kick veri tabloları Tetr.io standartlarına göre güncellendi (`pieces.py`).
   * **Görsel Kilit Gecikmesi (Glow) Efekti:** Yere inmiş parçalara kilitlenme süresine bağlı olarak beyaz parıltı (`alpha = ratio * 150`) eklendi (`game.py`).
   * **Test Entegrasyonu:** `tests/test_lock_delay_stalling_tetrio.py` adında 126 satırlık Tetr.io lock delay test paketi eklendi.

2. **Kart Ustalığı (Mystery Mode) 3x2 Grid Slot Sistemi (`cb9b765`, `8069b64`):**
   * **6'lı Slot Yapısı:** Sınırlı perk kartları artık alt listeden kaldırılıp 3x2 grid slot sistemine yerleştirildi. (`hold_destroyer` hariç tutuldu, hold_destroyer dikey listede listelenmeye devam ediyor).
   * **Dinamik Slota Özel Tuş Atamaları:** Karta özel tuş atamaları (`N`, `H`, `M`, `U`, `LSHIFT`, `J`) tamamen kaldırıldı. Kontroller sol paneldeki yuvaya (slota) bağlandı. Klavye için `1-6` tuşları ve Gamepad için bumper/trigger'lar (L1, R1, L2, RT vb.) varsayılan olarak tanımlandı.
   * **Seçim Overlay ve Duraklatma (Pause) Akışı:** Kart seçim ekranında kart seçildikten sonra "Hangi Slota Yerleştirmek İstiyorsunuz?" overlay'i (`draw_slot_allocation_panel`) açılır. Bu süreçte oyun tamamen duraklatılmış (`paused`) kalır. Oyuncu slot seçtiğinde iki overlay aynı anda kapatılır.
   * **Ayarlar Ekranı Revizyonu:** `settings_screen_tabbed.py` kontrol ekranında "Kart Yuvaları 1-6" (Slot 1-6 Keybindings) klavye ve gamepad satırları eklendi. Karta özel tuş ayarları temizlendi.
   * **Lokalizasyon Desteği:** Slot yerleşimi ile ilgili yeni çeviri anahtarları (`slot_allocation_title`, `slot_allocation_hint`, `slot_locked`, `slot_empty`) eklendi.

3. **Başarımlar ve Ödül Sistemi Güncellemesi (`cb9b765`, `50fb89d`):**
   * **Ödül Metni:** Ödül metni sadece kilitli (açılmamış) başarımlarda statik "+N Lunar" olarak gösterilir, açılmış başarımlarda gizlenir.

---

### B. quadrix-demo (Demo Sürümü) Son 2 Günde Yapılan Değişiklikler (15 - 16 Haziran 2026)
1. **T-spin ve B2B Geliştirmesi (`18e4603`):**
   * T-spin tespiti, 180 derece dönüş desteği ve güncellenmiş T-spin ve B2B puanlama mekanikleri demo sürümüne entegre edildi.
2. **Demo Uyumluluk Düzeltmeleri (`46f6a5e`):**
   * `pvp_game` ve `store_screen` gibi dosyalara demo uyumluluğu için dependency fallback tanımları eklendi.
3. **Lokalizasyon ve Test Setup Refaktörleri (`1210b41`).**

---

### C. Ana Oyunda Yapılan ve Demoya İşlenmeyen Kod Düzenlemeleri
1. `src/game.py`'de `_update_grounded_after_action` lock delay mantığı ve grounded parıltı (glow) efekti.
2. `src/pieces.py`'de güncellenmiş SRS+ 180 kicks tanımları.
3. `src/game_modes_extra.py`'de Kart Ustalığı sol panel 3x2 grid slot sistemi, slota özel yetenek tetiklemeleri ve duraklatma (pause) akışı.
4. `src/settings_screen_tabbed.py` ve `src/settings_manager.py`'de "Kart Yuvaları 1-6" (Slot 1-6 Keybindings) entegrasyonu ve varsayılan kontroller.
5. `src/menu.py`'de başarımlar ekranı ödül gösterim metni mantığı.
6. `src/localization.py`'de yeni eklenen slot lokalizasyon anahtarları.
7. `tests/test_lock_delay_stalling_tetrio.py` test dosyası.

---

## 2. Entegrasyon Kısıtları ve Farklılıklar (Demo-Özel Kurallar)

Ana oyundan demo sürümüne aktarım yapılırken aşağıdaki kısıtlar **kesinlikle korunacaktır**:

1. **Online Modlar ve Mağaza Gating:**
   * Online PvP, Online Coop ve Mağaza (Store) sistemleri demo sürümünde kilitlidir (`demo_config.py` kuralları uyarınca). Bu gating mekanizmaları aynen korunacak, ana oyundaki mağaza veya online kodları demo sürümüne taşınmayacaktır. `store_screen.py` için demo fallback uyumluluğu sürdürülecektir.
2. **150k Skor Sınırı (Score Cap):**
   * Demo sürümünde `MysteryMode` oyunlarında uygulanan 150k skor sınırı mekanizması (`_demo_score_cap_value`, `_should_trigger_demo_score_cap()`, `DemoUpgradePrompt` vb.) `game_modes_extra.py` içerisinde özenle korunacak ve v2'deki `game_modes_extra.py` dosyası doğrudan üzerine yazılmak yerine bu kısımlar korunarak entegre edilecektir.
3. **Kart Satın Alma ve Kart Havuzu Mantığı:**
   * Ana oyunda mağazadan kart satın alındıkça havuza eklenirken, demo sürümünde mağaza kapalı olduğu için mağazadan kart satın alma zorunluluğu kaldırılmalıdır.
   * `MysteryCardManager.prepare_selection` metodu içerisinde yer alan `_is_locked` filtrelemesinde `IS_DEMO` kontrolü eklenerek, demo modunda tüm kartlar doğrudan havuzda olmaya devam edecek, kilitli sayılmayacaktır.
4. **Satır Temizleme Animasyonu Satın Alma:**
   * Mağaza sistemi demo'da kilitli olduğundan, satır temizleme animasyonlarının Lunar karşılığında satın alınması ve değiştirilmesi özelliği demo sürümüne **dahil edilmeyecektir**. Demo'nun varsayılan satır temizleme animasyonu yapısı korunacaktır.

---

## 3. Adım Adım Entegrasyon Planı

### Adım 1: `src/localization.py` Entegrasyonu
* `TRANSLATIONS` sözlüğü içerisine aşağıdaki 4 yeni lokalizasyon anahtarı (hem Türkçe hem İngilizce ve diğer dillerde) eklenmelidir:
  * `slot_allocation_title`
  * `slot_allocation_hint`
  * `slot_locked`
  * `slot_empty`

### Adım 2: `src/pieces.py` Entegrasyonu
* Normal ve I parçaları için Tetr.io SRS+ 180 kicks matrisleri (`SRS_KICKS_180_NORMAL` ve `SRS_KICKS_180_I`) `v2` dosyasından `quadrix-demo` dosyasına birebir kopyalanmalıdır.

### Adım 3: `src/settings_manager.py` Entegrasyonu
* `DEFAULT_CONTROLS` içine `card_slots` ve `gamepad` içerisine `slot_1` - `slot_6` varsayılan klavye ve gamepad atamaları kopyalanmalıdır.
* Kart yuvaları atama kontrolü ve merging yardımcı mantıkları (`_ensure_card_inventory` vb. uyarlamaları) taşınmalıdır.

### Adım 4: `src/settings_screen_tabbed.py` Entegrasyonu
* "Kart Yuvaları 1-6" tuş atama ayarlarının yapılabilmesi için dual-slot keybinding metodolojisindeki değişiklikler (`_is_dual_slot_section`, `_get_dual_binding_slots` vb.) demo'ya taşınmalı, tabbed ayar satırları güncellenmelidir.

### Adım 5: `src/menu.py` Entegrasyonu
* Başarımlar ekranındaki `AchievementScreen` ödül metni çizim mantığı `if reward_amt > 0 and not unlocked:` koşuluna güncellenmelidir.

### Adım 6: `src/game.py` Entegrasyonu
* Lock delay sıfırlama refaktörü (`_update_grounded_after_action` metodu, hareket ve döndürme fonksiyonlarındaki lock delay çağrıları) demo'ya aktarılmalıdır.
* Grounded parçalar için görsel beyaz parıltı (glow) efekti `draw_textured_block` metodu içine entegre edilmelidir.

### Adım 7: `src/game_modes_extra.py` Entegrasyonu (En Kritik Adım)
* `MysteryCardManager` ve `MysteryMode` sınıfları entegre edilmelidir.
* **150k Skor Sınırı Korunması:** Demo'daki `_should_trigger_demo_score_cap` ve `DemoUpgradePrompt` entegrasyonu yeni kod tabanında korunmalıdır.
* **Slot Entegrasyonu:** 3x2 grid çizim ve slot atama mantığı getirilirken, demo sürümünde kilitli kartların (`_is_locked` filtresi) bypass edilmesi sağlanmalıdır.
* Karta özel atanmış eski sabit tuşların temizlendiğinden ve slota özel tuş kontrollerinin sağlandığından emin olunmalıdır.

### Adım 8: Testler ve Doğrulama
* `tests/test_lock_delay_stalling_tetrio.py` test dosyası demo sürümüne eklenmelidir.
* Demo testleri (`pytest tests/test_demo_*.py`) ve genel test suite çalıştırılarak doğrulanmalıdır.
