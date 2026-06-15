# Başarım Ödül Ekonomisi ve Kart Geliştirme Kilitleme Sistemi Entegrasyonu

Bu belge, Quadrix oyununa kazandırılan başarımlardan Lunar (Nöral Parça) kazanılması, geriye dönük ödül talepleri ve Mystery modundaki efsanevi (Legendary) kart geliştirmeleri için başarım kilit gereksinimlerinin entegrasyonunu ve bu sistemler üzerine uygulanan performans optimizasyonlarını açıklamaktadır.

---

## 1. Uygulama Detayları ve Mimari Yapı

Entegrasyon, oyunun mevcut ekonomi, başarım ve mağaza katmanlarına dokunarak şu modüller üzerinde gerçekleştirilmiştir:

*   **`src/achievements.py` (Ödül Havuzu ve Hak Talebi):**
    *   `ACHIEVEMENT_REWARDS` sözlüğü eklenerek tüm başarımlar zorluk ve nadirliklerine göre kategorilendirildi (Starter: 100 Lunar, Common: 150 Lunar, Rare: 300 Lunar, Epic: 500 Lunar, Legendary: 1000 Lunar).
    *   Kazanılan ödülleri benzersiz olarak takip etmek için `claimed_rewards` listesi eklendi.
    *   `grant_unclaimed_rewards()` metodu ile geriye dönük (eski sürümden gelen) açılmış başarımların Lunar ödüllerinin topluca profile yazılması sağlandı.
    *   `unlock()` metodu oyun içi anlık başarım kazanımlarında Lunar ödülünü cüzdana ekleyecek şekilde güncellendi.
*   **`src/game_modes_extra.py` (Kilit Kataloğu):**
    *   `CARD_LEGENDARY_REQUIREMENTS` tanımlanarak 16 geliştirilebilir kart ailesinin en üst seviyesi (Legendary) belirli oyun içi başarımların açılmış olmasına bağlandı.
*   **`src/user_manager.py` (Kilit Kontrolü):**
    *   `is_achievement_unlocked()` metodu eklenerek oyuncu başarımları üzerinden kilit kontrolü sağlandı.
    *   `upgrade_card()` metodu, bir sonraki seviye efsanevi ise ve başarım kilidi açılmamışsa geliştirmeyi reddedecek şekilde güncellendi.
*   **`src/store_screen.py` (Mağaza Görsel ve İnteraktif Kilit):**
    *   Efsanevi kart yükseltmesi kilitliyse sahiplik durumu `achievement_locked` olarak çözülür.
    *   Mağaza CTA butonu gri renkle `"Kilitli (Rozet)"` olarak çizilir ve altında kilit açıcı başarımın yerelleştirilmiş adı (`get_achievement_name`) gösterilir.
    *   Tıklama durumunda oyuncuya açıklayıcı statü mesajı verilir ve işlem engellenir.
*   **`src/localization.py` (Çeviriler):**
    *   Gerekli mağaza kilit etiketleri ve uyarı mesajları TR/EN dillerinde `TRANSLATIONS` sözlüğüne eklendi.

---

## 2. Araştırılan ve Uygulanan Performans Optimizasyonları

Oyunun Pygame tabanlı render döngüsünde (30 veya 60 FPS) çalışması nedeniyle, disk erişimi ve veri işleme süreçlerinde mikro takılmaları (micro-stutters) engellemek amacıyla şu optimizasyonlar uygulanmıştır:

### A. Mtime-Tabanlı Lazy Caching (Disk Girdi-Çıktı Optimizasyonu)
*   **Problem:** Mağaza ekranında kartların sahiplik durumunu çözmek için `is_achievement_unlocked()` fonksiyonu çağrılır. Mağaza ekranı saniyede 30-60 kez çizildiğinden, her karede diskteki `achievements_[user].json` dosyasını açıp okumak ve JSON verisini parse etmek ciddi bir CPU/Disk darboğazına ve oyunda donmalara yol açabilirdi.
*   **Çözüm:** `UserManager` içerisine `_ach_cache` hafıza önbelleği entegre edildi. Fonksiyon çağrıldığında ilk olarak diskteki dosyanın son değiştirilme zamanı (`os.path.getmtime(ach_file)`) okunur. Bu değer sistem düzeyinde son derece hızlı ve hafiftir.
*   **Çalışma Mantığı:** Eğer dosyanın değiştirilme zamanı önbellekteki zamanla aynıysa, doğrudan bellekteki $O(1)$ küme (Set) aranarak sonuç döndürülür. Sadece dosya değiştiğinde (yeni bir başarım açıldığında) dosya diskten yeniden okunarak önbellek güncellenir.

### B. Toplu Disk Yazma (I/O Write-Amplification Engelleme)
*   **Problem:** Oyuncu oyunu ilk başlattığında veya profil değiştirdiğinde geriye dönük hak talebi tetiklenir (`grant_unclaimed_rewards()`). Eğer oyuncu geçmişte 15 başarım kazanmışsa, her başarım için diske ayrı ayrı yazma (I/O write) işlemi yapmak disk ömrünü kısaltır ve CPU'yu meşgul ederdi.
*   **Çözüm:** Hak talebi döngüsü boyunca kazanılan ödüller hafızada biriktirilir. Tüm eski başarımlar tarandıktan sonra, eğer en az bir değişiklik yapılmışsa disk yazma işlemi (`self.save()`) **tek bir kez** tetiklenir. Bu sayede write-amplification riski sıfırlanmıştır.

### C. Küme (Set) Arama Karmaşıklığı ($O(1)$ Complexity)
*   `claimed_rewards` listesi veri tabanından liste olarak yüklense de, arama işlemlerinin (membership testing) hızlı yapılabilmesi için bellekte bir `set` (küme) nesnesine dönüştürülür. Bu sayede `ach_id not in claimed_rewards` aramaları $O(N)$ yerine $O(1)$ zaman karmaşıklığı ile tamamlanır.

### D. Atomik JSON Yazma Entegrasyonu (Veri Güvenliği)
*   Lunar ödülleri güncellenirken veya başarım kayıtları diske yazılırken oyunun aniden kapatılması durumunda veri kaybını (corruption) önlemek için projenin atomik dosya yazma altyapısı (`atomic_write_json`) kullanılmıştır. Bu altyapı veriyi önce geçici bir dosyaya yazar, yazım başarılı olunca asıl dosyanın üzerine yazar (renaming).

---

## 3. Doğrulama ve Testler

Geliştirilen önbellek ve başarım kilit mekanizmaları `tests/test_achievement_rewards.py` altındaki testlerle doğrulanmıştır:
*   `test_achievement_rewards_granting` (Anlık ödül kazanımı ve claimed listesi yazımı)
*   `test_retroactive_achievement_claims` (Geriye dönük toplu Lunar aktarımı ve mtime-cache tetiklemesi)
*   `test_legendary_card_upgrade_locked_state` (Efsanevi kart kilidinin başarım durumuna göre anlık kilitlenmesi ve açılması)

**Test Başarı Durumu:**
*   Yazılan yeni testler ve mevcut tüm mağaza/başarım testleri (`test_store_card_products.py` ve `test_steam_achievements_sync.py`) sıfır hata ile tamamlanmıştır.
