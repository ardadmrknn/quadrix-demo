# Quadrix Mod İkonları

Bu klasör, mod seçim ekranı (`src/extras_menu.py`) ve rehber ekranında (`src/guide_screen.py`) kullanılan PNG ikonlarını barındırır. Dosya adları kod tarafından sabit olarak beklendiği için isimler birebir korunmalıdır.

> **Bu klasör nedir?** Mod kartlarında gösterilen PNG ikonların kanonik konumu.
> **Beklenen sayı:** 14 ikon (her bir mod için bir tane). Eksik ikonlar için fallback metin/emoji çizilir; oyun çökmez.

## Beklenen Dosyalar

| Dosya adı | Kullanım |
| --- | --- |
| `campaign_mode_icon.png` | Campaign |
| `classic_mode_icon.png` | Classic |
| `sprint_mode_icon.png` | Sprint |
| `ultra_mode_icon.png` | Ultra |
| `zen_mode_icon.png` | Zen |
| `tetris2_mode_icon.png` | Quadrix 2 |
| `mystery_mode_icon.png` | Mystery |
| `wide_mode_icon.png` | Wide |
| `survival_mode_icon.png` | Survival |
| `cascade_mode_icon.png` | Cascade |
| `hardcore_mode_icon.png` | Hardcore |
| `daily_mode_icon.png` | Daily |
| `pvp_mode_icon.png` | Local PvP |
| `online_pvp_mode_icon.png` | Online PvP |

## Teknik Kurallar

- Format: şeffaf arka planlı PNG
- Önerilen boyut: 256x256 veya 512x512
- Kare oran kullanın
- Önemli görsel öğeleri merkeze yakın tutun
- Kart içinde rahat görünmesi için kenarlarda güvenli boşluk bırakın

## Stil Önerileri

- Her ikon tek bakışta mod fikrini anlatmalı
- Aynı aileden gelen ikonlarda ortak bir ışık, gölge ve çerçeve dili kullanın
- Aşırı detaylı veya küçük yazılı ikonlar menü ölçeklerinde kaybolur
- Koyu arka planlar üzerinde test ederek kontrastı doğrulayın

## Fallback Davranışı

- Bir dosya eksikse oyun çökmez
- İlgili ekranda emoji veya yazı tabanlı fallback kullanılabilir
- Yine de tutarlı bir görünüm için tüm dosyaların mevcut olması önerilir

## Prompt ve Tasarım Kaynağı

Mod temalarına göre hazırlanmış görsel prompt notları için şu belgeyi kullanın:

- [../../../docs/MODE_ICONS_AI_PROMPTS.md](../../../docs/MODE_ICONS_AI_PROMPTS.md)

## Güncelleme Notu

İkon dosyalarını değiştirdikten sonra en güvenli yol oyunu yeniden başlatmaktır. Menü veya rehber ekranı tekrar açıldığında yeni görseller yüklenir.

## İlgili Dokümanlar

- Genel proje rehberi: [../../../README.md](../../../README.md)
- Mod ikonu prompt rehberi (üretim notları, tarihsel): [../../../docs/MODE_ICONS_AI_PROMPTS.md](../../../docs/MODE_ICONS_AI_PROMPTS.md)
- Geniş mod listesi ve sistem haritası: [../../../docs/guides/README_FULL.md](../../../docs/guides/README_FULL.md)
