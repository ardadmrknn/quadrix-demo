# ESNEK SINIR ÖZELLİĞİ TEST TALİMATLARI

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

5. **Parçayı sola/sağa hareket ettirin:**
   - Parçayı board'un sol kenarına götürün
   - Sol ok tuşuna basın
   - **BAŞARILI:** Parça 1 blok dışarı çıkıyor ve konsolda "✓ Sol hareket başarılı" görünüyor
   - **BAŞARISIZ:** Parça sınırda kalıyor ve konsolda "⚠️ SOL HAREKET ENGELLENDİ" görünüyor

6. **Konsol çıktısını kontrol edin:**
   - Eğer "perk_active=True" ama "piece_flag=False" görüyorsanız → Flag ekleme sorunu
   - Eğer "perk_active=False" görüyorsanız → Perk aktivasyon sorunu
   - Eğer her ikisi de True ama hareket engelleniyorsa → board.is_valid_position sorunu

## Beklenen Sonuç:

✅ Parçalar board'un kenarlarından 1 blok dışarı çıkabilmeli
✅ Board'un arka planı ve grid çizgileri genişlemeli
✅ Sınır dışındaki bloklar görünmeli

## Sorun Giderme:

Eğer hala çalışmıyorsa, konsol çıktısını buraya yapıştırın.
