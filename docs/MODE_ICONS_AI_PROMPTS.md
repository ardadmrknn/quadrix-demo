# 🎨 OYUN MODU SİMGELERİ - AI PROMPT REHBERİ

Bu dosya, Quadrix oyununun mod seçim ekranında kullanılacak simgelerin Nano Banana Pro veya benzeri AI görsel üretim araçlarıyla oluşturulması için hazırlanmış prompt şablonlarını içerir.

---

## 📋 GENEL BİLGİLER

- **Boyut**: 256x256 piksel (önerilen)
- **Format**: PNG (şeffaf arka plan)
- **Stil**: Neon cyberpunk, parlak renkler, modern minimalist
- **Kayıt Konumu**: `assets/ui/mode_icons/`

---

## 🧩 ANA UI TEMASI İLE BAĞLAM (ÖNEMLİ)

Bu oyunun UI teması “koyu lacivert arka plan + neon vurgu + cam (glassmorphism)” hissi üstüne kurulu. Simgeleri üretirken bu tutarlılığı korumak için aşağıdaki paleti ve kısıtları prompt’larda özellikle vurguluyoruz.

**UIColors referansı (oyun içi sabitler):**
- Arka plan hissi: `BG_DARK` (10, 10, 26) / `BG_MEDIUM` (18, 18, 40)
- Vurgu renkleri: `NEON_CYAN` (0, 240, 255), `NEON_MAGENTA` (255, 0, 200), `NEON_GREEN` (0, 255, 150), `NEON_ORANGE` (255, 150, 0), `NEON_RED` (255, 50, 80), `NEON_GOLD` (255, 215, 0)

---

## 🧱 TEK PROMPT ŞABLONU (KOPYALA / DOLDUR)

Bu şablon “mod adıyla bağ kurma”yı sağlar ama **görselin içine yazı basılmasını engellemek** için açıkça “no text” kısıtları içerir.

**Şablon (EN — ikon üretiminde daha stabil):**
```
Icon for the Quadrix game mode "{MODE_NAME}". Concept: {MODE_CONCEPT_SHORT}. Primary symbol: {PRIMARY_SYMBOL}. Secondary motif: {SECONDARY_MOTIF}.
Style: modern neon + glassmorphism UI, cyber-clean, simple readable silhouette, soft bloom glow, crisp edges, minimal detail, centered.
Palette: dark navy feel (RGB 10,10,26 / 18,18,40) with neon accent {ACCENT_RGB_1} and optional secondary {ACCENT_RGB_2}.
Output: 256x256 PNG, transparent background, no text, no letters, no numbers, no watermark, no border/frame, no background shapes.
```

**Negatif kısıtlar (isteğe bağlı ek satır):**
```
Avoid: photorealism, complex scene, character faces, detailed background, UI mockups, gradients that reduce readability.
```

---

## 🧠 MODLARIN TEMEL ÖZELLİKLERİ (FİKİR KAYNAĞI) + SİMGE YÖNLENDİRMESİ

Bu bölüm, **ekstra oyun modlarının ana/temel özelliklerini** tanımlar. Amaç: bu özellikleri “fikir” olarak kullanıp, her mod için **tek bakışta anlaşılır** bir ikon üretmek.

### Ortak Uyum Kuralları (Ana UI Teması + Quadrix)

Her mod simgesi şu uyum kriterlerini karşılamalı:
- **Tema uyumu**: Koyu lacivert UI hissi (BG_DARK/BG_MEDIUM) + 1-2 neon vurgu (UIColors) + yumuşak glow/bloom.
- **Quadrix uyumu**: Geometrik, blok hissi veren formlar; temiz silüet; “oyun içi ikon” gibi okunaklı.
- **Kompozisyon**: Ortalanmış tek ana sembol + (isteğe bağlı) ikincil motif; küçük ölçekte (64x64) bile anlaşılır.
- **Teknik**: 256x256 PNG, şeffaf arka plan; **yazı/harf/sayı yok**; watermark yok; çerçeve yok; arka plan sahnesi yok.

### 1) Sprint Mode — “40 satır yarışı / hız”
**Temel özellikler**
- Hedef odaklı: Amaç **40 satırı** en hızlı sürede temizlemek
- Tempo: Hız, refleks, ritim
- Ölçüm: Süre (time-trial hissi)

**Simge fikri (özellikten türetilen)**
- Ana sembol: **Şimşek** veya “hız oku” (speed chevron)
- İkincil motif: İnce hız çizgileri + küçük enerji parçacıkları

**UI/Quadrix uyumu notu**
- Vurgu: NEON_GOLD + beyaz highlight; keskin, blok benzeri açıları koru

### 2) Ultra Mode — “2 dakika skor baskısı”
**Temel özellikler**
- Süre kısıtlı: **2 dakika** içinde maksimum skor
- Baskı: Kısa sürede yoğun karar
- Odak: Skor/puan odaklı performans

**Simge fikri**
- Ana sembol: **Kronometre / timer gövdesi**
- İkincil motif: Dairesel hareket yayı + tik işaretleri (ama **sayı yok**)

**UI/Quadrix uyumu notu**
- Vurgu: NEON_RED + NEON_ORANGE; dramatik ama sade silüet

### 3) Zen Mode — “sınırsız, sakin, stressiz”
**Temel özellikler**
- Süresiz oynanış; rahat tempo
- Daha az baskı, daha fazla akış
- “Odaklan ve rahatla” hissi

**Simge fikri**
- Ana sembol: **Soyut zen/denge glifi** (insan figürü kullanmadan)
- İkincil motif: Hafif aura halkası + yumuşak partiküller

**UI/Quadrix uyumu notu**
- Vurgu: NEON_GREEN + NEON_CYAN; yumuşak glow, minimum detay

### 4) Quadrix 2 — “ekstra parçalar / gelişmiş şekiller”
**Temel özellikler**
- Klasik setin ötesinde **ekstra parçalar**
- Daha fazla çeşitlilik ve kombinasyon
- Sürpriz/yaratıcılık hissi

**Simge fikri**
- Ana sembol: **Blok kümesi** (klasik + bir “ekstra parça” ipucu: plus/domino silüeti)
- İkincil motif: Neon grid pırıltıları

**UI/Quadrix uyumu notu**
- Vurgu: NEON_MAGENTA + NEON_CYAN; bloklar net, kenarlar keskin

### 5) Wide Mode — “geniş tahta / yatay alan”
**Temel özellikler**
- Geniş oyun alanı (15x20)
- Yatay yerleşim ve alan yönetimi
- Daha fazla “yanlara yayılma” hissi

**Simge fikri**
- Ana sembol: **Çift yönlü yatay ok**
- İkincil motif: Genişleme parantezleri veya gerilmiş grid çizgileri

**UI/Quadrix uyumu notu**
- Vurgu: NEON_CYAN; geometrik, teknik görünüm

### 6) Survival Mode — “hayatta kal / baskı ve tehlike”
**Temel özellikler**
- Zorluk/tehdit hissi; ayakta kalma
- Hata payı düşük, gerilim yüksek
- “Can/yaşam” çağrışımı

**Simge fikri**
- Ana sembol: **Kalp çekirdeği**
- İkincil motif: EKG nabız çizgisi + küçük uyarı kıvılcımları

**UI/Quadrix uyumu notu**
- Vurgu: NEON_RED + NEON_ORANGE; güçlü kontrast ama tek ikon silüeti

### 7) Cascade Mode — “yerçekimi / kademeli düşüş, akış”
**Temel özellikler**
- Yerçekimi/cascade hissi
- Blokların akış gibi aşağı kademeli kayması
- Dinamik, akışkan tempo

**Simge fikri**
- Ana sembol: **Şelale/akış silüeti**
- İkincil motif: Aşağı çözülen küçük blok parçacıkları

**UI/Quadrix uyumu notu**
- Vurgu: NEON_CYAN + soğuk mavi highlight; akışkan ama okunaklı

---

## 🎮 MOD SİMGELERİ PROMPTLARI

### 1. ⚡ Sprint Mode
**Dosya Adı**: `sprint_mode_icon.png`

**AI Prompt**:
```
Icon for the Quadrix game mode "Sprint Mode". Concept: race to clear 40 lines fast. Primary symbol: sharp lightning bolt. Secondary motif: speed lines + tiny energy particles.
Style: modern neon + glassmorphism UI, cyber-clean, simple readable silhouette, soft bloom glow, crisp edges, minimal detail, centered.
Palette: dark navy feel (RGB 10,10,26 / 18,18,40) with neon gold accent (RGB 255,215,0) and subtle white highlights.
Output: 256x256 PNG, transparent background, no text, no letters, no numbers, no watermark, no border/frame, no background shapes.
```

**Açıklama**: Hızlı tempolu 40 satır yarışı modunu temsil eden elektrik çarpması simgesi. Enerji ve hız hissi vermeli.

**Renk Paleti**: Sarı-Altın (#FFD700), Beyaz (#FFFFFF), Turuncu vurgular

---

### 2. ⏱️ Ultra Mode
**Dosya Adı**: `ultra_mode_icon.png`

**AI Prompt**:
```
Icon for the Quadrix game mode "Ultra Mode". Concept: score as much as possible in 2 minutes. Primary symbol: stopwatch/timer body. Secondary motif: circular motion arc + subtle tick marks (no numbers).
Style: modern neon + glassmorphism UI, cyber-clean, simple readable silhouette, soft bloom glow, crisp edges, minimal detail, centered.
Palette: dark navy feel (RGB 10,10,26 / 18,18,40) with neon red accent (RGB 255,50,80) and neon orange accent (RGB 255,150,0).
Output: 256x256 PNG, transparent background, no text, no letters, no numbers, no watermark, no border/frame, no background shapes.
```

**Açıklama**: 2 dakikalık yoğun skor modunu temsil eden zamanlayıcı simgesi. Aciliyet ve yoğunluk hissi vermeli.

**Renk Paleti**: Kırmızı (#FF3250), Turuncu (#FF9600), Gradient geçişler

---

### 3. 🧘 Zen Mode
**Dosya Adı**: `zen_mode_icon.png`

**AI Prompt**:
```
Icon for the Quadrix game mode "Zen Mode". Concept: endless calm play, low stress. Primary symbol: minimalist zen/meditation glyph (abstract, not a person). Secondary motif: soft floating particles + gentle aura ring.
Style: modern neon + glassmorphism UI, cyber-clean, simple readable silhouette, soft bloom glow, crisp edges, minimal detail, centered.
Palette: dark navy feel (RGB 10,10,26 / 18,18,40) with neon green accent (RGB 0,255,150) and neon cyan accent (RGB 0,240,255).
Output: 256x256 PNG, transparent background, no text, no letters, no numbers, no watermark, no border/frame, no background shapes.
```

**Açıklama**: Süresiz, rahatlatıcı oyun modunu temsil eden meditasyon simgesi. Huzur ve sakinlik hissi vermeli.

**Renk Paleti**: Yumuşak Cyan (#00FF96), Mor (#A020F0), Pastel tonlar

---

### 4. 🧩 Quadrix 2
**Dosya Adı**: `tetris2_mode_icon.png`

**AI Prompt**:
```
Icon for the Quadrix game mode "Quadrix 2". Concept: extra pieces / advanced shapes. Primary symbol: compact cluster of tetris-like blocks (include one non-classic hint like a plus or domino shape silhouette). Secondary motif: subtle neon grid sparkles.
Style: modern neon + glassmorphism UI, cyber-clean, simple readable silhouette, soft bloom glow, crisp edges, minimal detail, centered.
Palette: dark navy feel (RGB 10,10,26 / 18,18,40) with neon magenta accent (RGB 255,0,200) and neon cyan accent (RGB 0,240,255).
Output: 256x256 PNG, transparent background, no text, no letters, no numbers, no watermark, no border/frame, no background shapes.
```

**Açıklama**: Ekstra parçalar içeren gelişmiş modun simgesi. Yaratıcılık ve çeşitlilik hissi vermeli.

**Renk Paleti**: Magenta (#FF00C8), Cyan (#00F0FF), Gökkuşağı tonları

---

### 5. ↔️ Wide Mode
**Dosya Adı**: `wide_mode_icon.png`

**AI Prompt**:
```
Icon for the Quadrix game mode "Wide Mode". Concept: wider board (15x20) and horizontal space. Primary symbol: bold left-right double arrow. Secondary motif: subtle expansion brackets or stretched grid lines.
Style: modern neon + glassmorphism UI, cyber-clean, simple readable silhouette, soft bloom glow, crisp edges, minimal detail, centered.
Palette: dark navy feel (RGB 10,10,26 / 18,18,40) with neon cyan accent (RGB 0,240,255) and a small cool-blue highlight.
Output: 256x256 PNG, transparent background, no text, no letters, no numbers, no watermark, no border/frame, no background shapes.
```

**Açıklama**: Geniş 15x20 oyun alanını temsil eden genişleme simgesi. Genişlik ve alan hissi vermeli.

**Renk Paleti**: Parlak Cyan (#00F0FF), Mavi (#3264FF), Geometrik çizgiler

---

### 6. ❤️ Survival Mode
**Dosya Adı**: `survival_mode_icon.png`

**AI Prompt**:
```
Icon for the Quadrix game mode "Survival Mode". Concept: stay alive under pressure. Primary symbol: heart core. Secondary motif: pulse line (EKG style) + subtle warning sparks.
Style: modern neon + glassmorphism UI, cyber-clean, simple readable silhouette, soft bloom glow, crisp edges, minimal detail, centered.
Palette: dark navy feel (RGB 10,10,26 / 18,18,40) with neon red accent (RGB 255,50,80) and neon orange accent (RGB 255,150,0).
Output: 256x256 PNG, transparent background, no text, no letters, no numbers, no watermark, no border/frame, no background shapes.
```

**Açıklama**: Hayatta kalma modunun zorluğunu temsil eden kalp simgesi. Yoğunluk ve gerilim hissi vermeli.

**Renk Paleti**: Kırmızı (#FF3250), Turuncu (#FF9600), Nabız efektleri

---

### 7. 🌊 Cascade Mode
**Dosya Adı**: `cascade_mode_icon.png`

**AI Prompt**:
```
Icon for the Quadrix game mode "Cascade Mode". Concept: gravity/cascade effect, falling flow. Primary symbol: cascading stream / waterfall silhouette. Secondary motif: stacked falling particles (like blocks dissolving downward).
Style: modern neon + glassmorphism UI, cyber-clean, simple readable silhouette, soft bloom glow, crisp edges, minimal detail, centered.
Palette: dark navy feel (RGB 10,10,26 / 18,18,40) with neon cyan accent (RGB 0,240,255) and a deeper cool-blue highlight.
Output: 256x256 PNG, transparent background, no text, no letters, no numbers, no watermark, no border/frame, no background shapes.
```

**Açıklama**: Yerçekimi efektli kademeli düşüş modunu temsil eden şelale simgesi. Akışkanlık ve hareket hissi vermeli.

**Renk Paleti**: Parlak Mavi (#3264FF), Cyan (#00F0FF), Akışkan dalga efektleri

---

## 🛠️ KULLANIM ADIMLARI

### Adım 1: AI Aracını Açın
- Nano Banana Pro, DALL-E, Midjourney, Stable Diffusion gibi araçlardan birini kullanın

### Adım 2: Prompt'u Kopyalayın
- Yukarıdaki ilgili mod için hazırlanmış prompt'u kopyalayın
- Gerekirse boyut ve stil parametrelerini ekleyin

### Adım 3: Görseli Oluşturun
- AI aracına prompt'u yapıştırın ve görseli oluşturun
- Gerekirse birkaç varyasyon deneyin

### Adım 4: İndirin ve Kaydedin
- Oluşturulan görseli PNG formatında indirin
- Belirtilen dosya adıyla kaydedin

### Adım 5: Klasöre Yerleştirin
```
tetris_macos/assets/ui/mode_icons/
```
Konumuna tüm simgeleri yerleştirin.

---

## 🎨 TASARIM PRENSİPLERİ

### ✅ Yapılması Gerekenler:
- Şeffaf arka plan kullanın (PNG alpha channel)
- Neon parlak renkler tercih edin
- Cyberpunk/modern aesthetic'i koruyun
- Merkezde net bir simge olsun
- Glow/parıltı efektleri ekleyin

### ❌ Yapılmaması Gerekenler:
- Arka plan rengi koymayın
- Çok karmaşık detaylardan kaçının
- Soluk veya mat renkler kullanmayın
- Simgeyi köşelere sıkıştırmayın
- Metin eklemeyin (isimler zaten kart üzerinde görünecek)

---

## 📊 RENK PALETİ REFERANSI

Oyunun ana UI teması ile uyumlu renkler:

| Renk İsmi | HEX Kod | RGB | Kullanım |
|-----------|---------|-----|----------|
| Neon Cyan | #00F0FF | (0, 240, 255) | Ana vurgu |
| Neon Magenta | #FF00C8 | (255, 0, 200) | İkincil vurgu |
| Neon Green | #00FF96 | (0, 255, 150) | Başarı/onay |
| Neon Orange | #FF9600 | (255, 150, 0) | Uyarı |
| Neon Red | #FF3250 | (255, 50, 80) | Hata/tehlike |
| Neon Gold | #FFD700 | (255, 215, 0) | Özel/premium |

---

## 🔍 ÖNIZLEME

Simgeler oyun içinde şu şekilde görünecek:

```
┌────────────────────────────┐
│                            │
│         [SIMGE]            │  ← 64x64 boyutunda
│                            │
│      Sprint Mode           │  ← Mod adı
│     40 satır yarışı        │  ← Açıklama
│                            │
└────────────────────────────┘
```

Her kart:
- 280x220 piksel boyutunda glassmorphism kart
- Hover efekti ile parıltı
- Seçildiğinde neon kenar ışığı
- Mod rengine göre accent color

---

## 📝 NOTLAR

1. **Opsiyonel**: Simgeler yoksa emoji fallback kullanılır (⚡, ⏱️, 🧘, vb.)
2. **Performans**: PNG dosyaları optimize edilmiş olmalı (tercihen 50KB altında)
3. **Tutarlılık**: Tüm simgeler benzer stil ve kalitede olmalı
4. **Test**: Her simgeyi hem açık hem koyu arka planda test edin

---

## 🚀 HIZLI BAŞLANGIÇ

Tüm simgeleri tek seferde oluşturmak için:

1. Nano Banana Pro'yu açın
2. Yukarıdaki 7 prompt'u sırayla kullanın
3. Her birini belirtilen dosya adıyla kaydedin
4. Tümünü `assets/ui/mode_icons/` klasörüne atın
5. Oyunu başlatın ve yeni simgelerin yüklendiğini görün!

---

**Hazırlayan**: GitHub Copilot  
**Tarih**: 20 Aralık 2025  
**Versiyon**: 1.0
