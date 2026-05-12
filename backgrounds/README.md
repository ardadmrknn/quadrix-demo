# Quadrix Arka Plan Dosyaları

Bu klasör, oyunda kullanılan görsel arka planların varsayılan konumudur. Ayarlar menüsünden seçilen özel dosyalar varsa onlar öncelikli kullanılır; bu klasördeki isimler ise otomatik fallback akışını belirler.

## Desteklenen Arka Plan Yüzeyleri

### 1. Dış / tam ekran arka plan

Menüler, bazı UI panelleri, PvP dış yüzeyi ve genel tam ekran arka plan için önerilen adlar:

- `outer_background.png`
- `outer_background.jpg`
- `background.png`
- `background.jpg`

Eski uyumluluk için bazı yerlerde şu adlar da fallback olarak okunabilir:

- `outer_backgrounds.png`
- `anime_bg.png`
- `waifu.png`

Yeni içerik eklerken önerilen isim `outer_background.png` dosyasıdır.

### 2. Tek oyunculu oyun alanı

Tek oyunculu, Sprint, Ultra, Zen ve benzeri tek board odaklı modlarda oyun alanı içi arka plan için desteklenen sıralama:

- `game_background.png`
- `game_background.jpg`
- `single_background.png`
- `single_background.jpg`
- `single_bg.png`
- `game_area_bg.png`
- `board_background.png`

Önerilen isim `game_background.png` veya `single_background.png` dosyasıdır.

### 3. PvP ve co-op oyun alanı

PvP ve co-op board içi arka plan için desteklenen adlar:

- `game_background.png`
- `game_background.jpg`
- `board_background.png`
- `board_background.jpg`
- `board_bg.png`
- `tetris_bg.png`
- `game_bg.jpg`

Önerilen isim `board_background.png` dosyasıdır.

### 4. Co-op ana arka plan

Co-op akışında tam ekran ana arka plan için önce şu adlar aranır:

- `main_background.png`
- `main_background.jpg`
- ardından `game_background.png`
- ardından `game_background.jpg`

## Format ve Hazırlık Önerileri

- Format: PNG veya JPG
- Ana tam ekran yüzeyler için 16:9 oranlı görseller tercih edin
- Board içi arka planlarda orta alanı fazla kalabalıklaştırmayan görseller seçin
- Çok parlak veya yazı dolu görseller UI okunabilirliğini düşürür
- Oyun görüntüyü otomatik ölçekler; yine de yüksek çözünürlüklü kaynak daha iyi sonuç verir

## Transparanlık ve Ayarlar

- Board arka planları yarı saydam olarak çizilebilir
- Varsayılan transparanlık genellikle `0.3` civarındadır
- Ayarlar menüsünden arka plan görünürlüğü ve özel dosya seçimi yapılabilir

## Önemli Notlar

- Ayarlar menüsünden seçilmiş özel yol varsa, bu klasördeki sabit isimlerin önüne geçer
- Tek oyunculu, PvP ve co-op yüzeyleri birbirinden bağımsız fallback listeleri kullanır
- Bu klasör önerilen ana konumdur; bazı eski akışlarda `assets/backgrounds` için geriye dönük destek de bulunur

## Hızlı Deneme

1. Bu klasöre `outer_background.png` ekleyin
2. İsterseniz ayrıca `game_background.png` ve `board_background.png` ekleyin
3. Oyunu yeniden başlatın
4. Ayarlar menüsünden arka plan seçeneklerini kontrol edin
