# ESNEK SINIR ÖZELLİĞİ TEST TALİMATLARI (YENİ)

## Yapılan Değişiklikler:

1. **Tüm manuel flag ekleme kodları silindi**
   - spawn_new_piece içindeki flag ekleme kodları kaldırıldı
   - hold/swap işlemlerindeki flag ekleme kodları kaldırıldı
   - Kart aktivasyonundaki manuel flag ekleme kodları kaldırıldı

2. **PerkManager üzerinden otomatik flag ekleme**
   - `PerkManager.on_piece_spawn()` metodu her yeni parçaya otomatik flag ekliyor
   - Perk aktif olduğu sürece tüm yeni parçalar flag alıyor

3. **Debug çıktıları eklendi**
   - Kart seçildiğinde detaylı konsol çıktısı
   - Her yeni parçaya flag eklendiğinde bildirim
   - Hareket sırasında esnek sınır kontrolü bildirimi

## Test Adımları:

1. **Oyunu başlatın:**
   ```
   python main.py
   ```

2. **Kart Ustalığı modunu seçin:**
   - Ana menüden "Ekstralar" > "Kart Ustalığı"

3. **Oyunu başlatın ve 5 satır temizleyin**
   - Level 1 tamamlanınca kart seçimi gelecek

4. **"Esnek Sınır" kartını seçin**
   - Konsolda şu mesajları göreceksiniz:
   ```
   ============================================================
   🔷 ESNEK SINIR KARTI SEÇİLDİ!
   ============================================================
   ✓ perk_manager.activate('perk_flexible_border') çağrıldı
   ✓ perk_manager.is_active('perk_flexible_border') = True
   ✓ current_piece.flexible_border = True
   ✓ next_piece_queue'daki 3 parçaya flexible_border eklendi
   ============================================================
   ```

5. **Yeni parça geldiğinde konsolu kontrol edin:**
   - Her yeni parça için şu mesajı göreceksiniz:
   ```
   ✓ Esnek Sınır: Yeni parçaya flag eklendi (piece=I)
   ```

6. **Parçayı sola/sağa hareket ettirin:**
   - Parçayı board'un sol kenarına götürün
   - Sol ok tuşuna basın
   - Konsolda şu mesajları göreceksiniz:
   ```
   🔷 Esnek Sınır: is_valid_position çağrıldı (dx=-1, dy=0, border_extend=1)
   ```

## Beklenen Sonuç:

✅ Parçalar board'un kenarlarından 1 blok dışarı çıkabilmeli
✅ Her yeni parça otomatik olarak flag almalı
✅ Konsol çıktıları düzgün görünmeli

## Sorun Giderme:

Eğer hala çalışmıyorsa:
1. Konsol çıktısını kontrol edin
2. "✓ Esnek Sınır: Yeni parçaya flag eklendi" mesajını görüyor musunuz?
3. Hareket sırasında "🔷 Esnek Sınır: is_valid_position çağrıldı" mesajını görüyor musunuz?
4. Eğer bu mesajları görmüyorsanız, PerkManager.on_piece_spawn çağrılmıyor demektir
