# Tutorial Smoke Checklist

## Kapsam

Bu checklist, tutorial yeniden yapılanmasının tamamını smoke seviyesinde doğrulamak için hazırlanmıştır.
Kapsanan alanlar:

- İlk kullanıcı tutorial prompt akışı
- Tutorial hub ve chapter/lesson seçimi
- Basics lesson zinciri
- Board basics scenario lesson'ları
- Card academy seçim lesson'ları
- Lesson result panel, retry/next/hub dönüş akışları
- Progress, yıldız ve chapter unlock kalıcılığı
- Guide ekranından tutorial açma entegrasyonu

## Test Ortamı

- Platform: macOS
- Dil: önce Türkçe, ardından kısa bir İngilizce turu
- Giriş: klavye + fare
- Profil: biri yeni kullanıcı, biri eski ilerlemeli kullanıcı

## Ön Hazırlık

1. Oyunu temiz şekilde başlat.
Beklenen sonuç: ana menü sorunsuz açılır.

2. Kullanılacak iki profil hazırla.
Beklenen sonuç: bir yeni profil ve bir mevcut profil ile giriş yapılabilir.

3. Mümkünse test boyunca ses ve efektler açık olsun.
Beklenen sonuç: tutorial geçişlerinde sesli geri bildirimler duyulur, kritik yerde sessiz çökme yaşanmaz.

## A. İlk Kullanıcı Prompt Akışı

1. Yeni kullanıcı oluştur.
Beklenen sonuç: tutorial öneri/prompt akışı görünür.

2. Prompt üzerinde tutorial kabul et.
Beklenen sonuç: doğrudan basics ilk dersi olan hareket dersi açılır.

3. Oyundan çıkmadan tutorial içi birkaç adım ilerle.
Beklenen sonuç: lesson akışı çalışır, soft lock veya boş ekran oluşmaz.

4. Uygulamayı yeniden başlat ve aynı kullanıcıyla geri gir.
Beklenen sonuç: tutorial ilerlemesi korunur, yeni kullanıcı prompt'u tekrar zorla açılmaz.

5. Ayrı bir yeni kullanıcı oluştur ve bu kez tutorial prompt'unu reddet.
Beklenen sonuç: oyun normal menüye döner, kullanıcı tutorial tamamlandı/atlandı durumuyla sonsuz prompt döngüsüne girmez.

6. Reddetme sonrası menüden tutorial modunu manuel aç.
Beklenen sonuç: tutorial hub açılır ve basics chapter erişilebilir durumda olur.

## B. Tutorial Hub

1. Ana menüden tutorial modunu aç.
Beklenen sonuç: doğrudan hub ekranı açılır.

2. Hub'da chapter listesi ile lesson listesi aynı anda görünür mü kontrol et.
Beklenen sonuç: chapter paneli ve seçili chapter'ın lesson paneli düzgün yerleşir, metinler taşmaz.

3. Klavye ile chapter ve lesson seçimini değiştir.
Beklenen sonuç: odak kararlı şekilde değişir, kilitli chapter'lar yanlışlıkla başlatılamaz.

4. Fare ile chapter ve lesson seçimini değiştir.
Beklenen sonuç: hover ve tıklama davranışı düzgün çalışır.

5. Hub'da yıldız ve tamamlanma bilgilerini kontrol et.
Beklenen sonuç: tamamlanan lesson'lar ve chapter ilerlemesi doğru görünür.

6. Dar pencere ve standart pencere boyutunda hub'ı kontrol et.
Beklenen sonuç: kart yüksekliği, satır aralıkları ve başlıklar üst üste binmez.

## C. Basics Chapter

1. move_intro dersini başlat.
Beklenen sonuç: legacy tutorial davranışı korunur ve hareket hedefi anlaşılır şekilde gösterilir.

2. rotate_intro dersini tamamla.
Beklenen sonuç: dönüş girdileri algılanır ve lesson sonucu görünür.

3. soft_drop_intro dersini tamamla.
Beklenen sonuç: soft drop metriği doğru hesaplanır; reset/retry sonrası önceki deneme verisi taşınmaz.

4. hard_drop_intro dersini tamamla.
Beklenen sonuç: hard drop ile lesson başarıya ulaşır.

5. line_clear_intro dersini tamamla.
Beklenen sonuç: satır temizleme hedefi doğru algılanır.

6. hold_intro dersini tamamla.
Beklenen sonuç: hold mekaniği doğru çalışır ve lesson başarıyla kapanır.

7. tutorial_complete dersine kadar basics zincirini bitir.
Beklenen sonuç: basics chapter tamamlanır, yıldızlar kaydedilir ve board basics chapter unlock olur.

## D. Board Basics Chapter

1. board_gap_fill dersini başlat.
Beklenen sonuç: hazırlı tahta senaryosu doğru yüklenir.

2. Hedefe uygun oynayıp dersi bitir.
Beklenen sonuç: başarı ekranında scenario odaklı metrikler görünür.

3. Aynı derste başarısız olacak şekilde oyna.
Beklenen sonuç: fail sonucu, neden bilgisi ve retry akışı çalışır.

4. Retry seçeneğini kullan.
Beklenen sonuç: aynı senaryo temiz başlangıç durumuna döner.

5. board_keep_low dersini tamamla.
Beklenen sonuç: stack yüksekliği metriği doğru değerlendirilir.

6. board_vertical_well dersini tamamla.
Beklenen sonuç: well koruma ve quadrix odaklı hedef mantığı doğru değerlendirilir.

7. Chapter tamamlanınca hub'a dön.
Beklenen sonuç: card academy unlock olur.

## E. Card Academy Chapter

1. card_rescue_pick dersini aç.
Beklenen sonuç: kart seçim overlay'i kontrollü senaryo ile açılır.

2. Doğru kartı seç.
Beklenen sonuç: başarı ekranında seçilen ve önerilen kart adları düzgün sarılır, taşma olmaz.

3. Aynı dersi tekrar açıp yanlış kartı seç.
Beklenen sonuç: başarısız geri bildirim ilgili scenario açıklamasıyla görünür.

4. card_long_term_pick dersini tamamla.
Beklenen sonuç: kısa vadeli güçlü kart yerine uzun vadeli doğru seçim mantığı doğrulanır.

5. card_synergy_pick dersini tamamla.
Beklenen sonuç: sinerji odaklı öneri mantığı doğru çalışır.

6. Card academy chapter tamamlanınca hub'a dön.
Beklenen sonuç: yıldız ve completion bilgisi kaydedilmiş olur.

## F. Result Panel ve Akış Kontrolleri

1. Başarılı bir lesson sonrası result panelini incele.
Beklenen sonuç: başlık, yıldız ve aksiyon metinleri lokalized görünür.

2. Retry aksiyonunu kullan.
Beklenen sonuç: aynı lesson tekrar başlar.

3. Next aksiyonunu kullan.
Beklenen sonuç: sıradaki lesson otomatik açılır.

4. Hub'a dönüş aksiyonunu kullan.
Beklenen sonuç: tutorial hub doğru chapter/lesson durumuyla açılır.

5. Card lesson ve scenario lesson sonuç panellerini ayrı ayrı kontrol et.
Beklenen sonuç: kart derslerinde kart odaklı bilgi, scenario derslerinde board odaklı metrik gösterilir.

## G. Kalıcılık ve Profil Geçişleri

1. Bir kullanıcıyla birkaç lesson tamamla ve oyunu kapat.
Beklenen sonuç: yeniden girişte progress ve yıldızlar korunur.

2. Başka kullanıcıya geç.
Beklenen sonuç: tutorial progress kullanıcı bazlı ayrışır.

3. Eski bir profilde tutorial_completed benzeri legacy durum varsa profili yükle.
Beklenen sonuç: basics chapter tamamlanmış görünür ve sonraki chapter unlock durumu tutarlı olur.

4. Tutorial tamamlandıktan sonra menüden yeniden tutorial moduna gir.
Beklenen sonuç: hub açılır, ilerleme kaybolmaz.

## H. Guide Entegrasyonu

1. Ana menüden guide ekranını aç.
Beklenen sonuç: guide normal şekilde açılır.

2. Nasıl Oynanır tabında alt butondan ilgili eğitimi aç.
Beklenen sonuç: move_intro dersi açılır.

3. Oyun Modları tabında ilgili eğitimi aç.
Beklenen sonuç: board_gap_fill dersi açılır.

4. Kartlar tabında ilgili eğitimi aç.
Beklenen sonuç: card_rescue_pick dersi açılır.

5. İpuçları ve SSS tabında ilgili eğitimi aç.
Beklenen sonuç: doğrudan tutorial hub açılır.

6. Guide ekranında T kısayolunu dene.
Beklenen sonuç: seçili taba göre doğru tutorial aksiyonu çalışır.

7. Guide ekranında yeni butonun dar pencere boyutlarında yerleşimini kontrol et.
Beklenen sonuç: tutorial butonu ve geri butonu üst üste binmez.

## I. Kısa Lokalizasyon Turu

1. Dili İngilizceye al ve hub ekranını aç.
Beklenen sonuç: yeni hub/result/guide tutorial metinleri İngilizce görünür.

2. Guide ekranındaki yeni tutorial butonunu ve hint satırını kontrol et.
Beklenen sonuç: metinler kırpılmadan görünür.

3. Bir card lesson result ekranını İngilizcede kontrol et.
Beklenen sonuç: selected/recommended metinleri düzgün görünür.

## J. Regresyon Notları

1. Tutorial dışı ana menü akışlarını kısaca kontrol et.
Beklenen sonuç: guide, menu ve normal oyun başlatma akışları tutorial entegrasyonu nedeniyle bozulmaz.

2. Fullscreen toggle'ı guide ekranında dene.
Beklenen sonuç: mevcut toggle davranışı korunur.

3. Tutorial'dan çıkış sonrası menü müzik akışını kontrol et.
Beklenen sonuç: müzik yönetimi önceki davranışla uyumlu kalır.

## Smoke Exit Kriteri

Smoke turu başarılı sayılır if:

- Tutorial basics, board basics ve card academy manuel olarak başlatılabiliyor
- Chapter unlock zinciri doğru ilerliyor
- Progress ve yıldızlar kullanıcı bazında kalıcı
- Guide ekranından tutorial açma akışı çalışıyor
- Sonuç panellerinde yanlış metrik veya taşan metin görünmüyor
- Kritik akışlarda crash, soft lock veya boş ekran oluşmuyor