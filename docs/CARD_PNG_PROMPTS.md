# 🃏 Kart PNG Arka Plan Promptları — Nano Banana Pro

## Genel Bilgiler

| Özellik | Değer |
|---|---|
| **Kart Boyutu** | 300 × 380 px (normal mod) |
| **Format** | PNG, şeffaf arka plan (alpha channel) |
| **UI Teması** | Koyu lacivert uzay/cyberpunk, neon vurgular, glassmorphism |
| **Toplam Gerekli Görsel** | 10 adet (5 enderlik × 2 yüz) |

### Renk Paleti Referansı (UI ile Uyumlu)
- **Ana Arka Plan:** `#0A0A1A` (koyu lacivert gece)
- **Panel:** `#12122B` (koyu mor-mavi)
- **Cam Efekti:** Yarı saydam, `rgba(20, 20, 45, 0.7)` tarzı
- **Ana Neon Vurgu:** `#00F0FF` (cyan)
- **İkincil Vurgu:** `#FF00C8` (magenta)

### Enderlik Renk Kodları
| Enderlik | Renk | Hex |
|---|---|---|
| Common (Yaygın) | Gümüş-Gri | `#B4B4B4` |
| Uncommon (Sıradışı) | Zümrüt Yeşili | `#64DC8C` |
| Rare (Nadir) | Buz Mavisi | `#50B4FF` |
| Epic (Epik) | Ametist Moru | `#B450FF` |
| Legendary (Efsanevi) | Altın-Turuncu | `#FFB400` |

---

## 📋 Ortak Prompt Kuralları

Her prompt için şu sabitler geçerlidir — aşağıdaki promptlarda tekrar edilmez:

> **Ortak suffix (her prompta eklenecek):**
> `game UI card template, 300x380 pixels, portrait orientation, PNG with transparent background, clean edges, no text, no characters, flat vector-meets-painterly style, dark cosmic space theme, designed for a cyberpunk Quadrix game UI, 4K render quality`

---

## 🂠 ARKA YÜZ PROMPTLARI (Card Back)

Arka yüz kartı döndürülmeden önceki "gizemli" taraftır. Ortasında soru işareti veya gizemli sembol bulunacak alan bırakılmalı (kod ile eklenecek). Desen, enderliğe göre değişir.

---

### 1. 🔘 Common — Arka Yüz
**Dosya adı:** `card_back_common.png`

```
A minimalist dark card back template for a game UI. Deep charcoal-gray base (#1A1A2E) with a subtle repeating grid pattern made of thin silver-gray (#B4B4B4) lines at 15% opacity. The grid lines form a clean geometric lattice across the entire surface. Edges have a thin 1px silver border with very slight rounded corners. The center area is slightly lighter to hint at a hidden symbol underneath. Overall feel: industrial, simple, no-frills. Muted tones, no glow effects, no sparkles. The card should look like a standard playing card back — reliable but unremarkable.
```

---

### 2. 🟢 Uncommon — Arka Yüz
**Dosya adı:** `card_back_uncommon.png`

```
A nature-infused dark card back template for a game UI. Deep navy-black base (#0F1525) with an elegant pattern of softly glowing emerald-green (#64DC8C) botanical vines and small leaves, drawn in a minimalist geometric style, wrapping symmetrically from all four corners toward the center. The vines have a subtle 20% opacity glow. A thin emerald-green border (1.5px) with rounded corners frames the card. The center has a slightly brighter circular area suggesting hidden energy beneath. Three small concentric rings of faint green light sit at the very center. Feel: organic growth meeting dark technology, fresh and promising but not overpowering.
```

---

### 3. 🔵 Rare — Arka Yüz
**Dosya adı:** `card_back_rare.png`

```
A crystalline dark card back template for a game UI. Deep midnight-blue base (#0C1428) with an intricate pattern of ice-blue (#50B4FF) crystal shards and geometric diamond shapes, arranged in a symmetric mandala formation radiating from the center. The crystals have subtle internal light refraction effects with soft blue glow at 30% opacity. A 2px ice-blue glowing border with rounded corners frames the card, with tiny crystal fragments scattered along the edges. The center features a larger diamond shape formed by four overlapping crystal facets, creating a focal point. Small frozen particles float near the border areas. Feel: precious and mysterious, like looking into a frozen ancient artifact.
```

---

### 4. 🟣 Epic — Arka Yüz
**Dosya adı:** `card_back_epic.png`

```
A mystical dark card back template for a game UI. Deep void-purple base (#0D0820) with a mesmerizing swirling vortex pattern made of amethyst-purple (#B450FF) energy spirals emanating from the center. The spiral arms are made of many small luminous dots decreasing in opacity as they reach outward, creating a galaxy-like formation. Arcane geometric rune-like symbols (abstract, not real runes) float at the four cardinal points with a faint purple glow. A 2px amethyst border pulses with inner light, rounded corners. The center has a bright violet nebula-like concentration of energy with subtle magenta (#FF00C8) highlights. Tiny orbiting energy particles trace elliptical paths around the center. Feel: arcane, powerful, otherworldly — like a portal to another dimension is barely contained within the card.
```

---

### 5. 🟡 Legendary — Arka Yüz
**Dosya adı:** `card_back_legendary.png`

```
A majestic legendary dark card back template for a game UI. Ultra-deep black-purple base (#08061A) with an elaborate golden (#FFB400) mandala pattern at the center — six symmetrical ornate arms extending outward with intricate filigree details, each arm ending in a small starburst. The mandala lines have a warm golden glow with subtle fire-like ember particles drifting upward from the pattern. An outer ring of golden light encircles the mandala. The border is a 3px ornate golden frame with decorative corner flourishes, slightly beveled for a premium feel. Subtle warm orange-to-gold gradient highlights trace the edges. Behind the mandala, very faint concentric golden circles ripple outward like gravitational waves. Tiny golden star-shaped sparkles are scattered across the surface at low opacity. Feel: divine, awe-inspiring, ultimate rarity — this card radiates importance and prestige. The holder knows they have something truly extraordinary.
```

---

## 🂡 ÖN YÜZ PROMPTLARI (Card Front)

Ön yüz kartı döndürüldükten sonra içeriğin göründüğü taraftır. Kart üzerinde şu alanlar kod ile eklenecek:
- **Üst bölge:** İkon alanı (~80×80 px, merkezde)
- **Orta bölge:** Başlık + Etiket (tag badge)
- **Alt bölge:** Açıklama metni

Bu nedenle ön yüz PNG'si bir **çerçeve/şablon** olmalı — içerik alanları boş/şeffaf bırakılmalı, sadece kenarlık, arka plan gradientı ve dekoratif detaylar bulunmalı.

---

### 6. 🔘 Common — Ön Yüz
**Dosya adı:** `card_front_common.png`

```
A clean minimalist card front frame template for a game UI. Dark slate-gray base (#1C1C32) with a smooth vertical gradient going slightly lighter toward the center. A thin 1px silver-gray (#B4B4B4) border with 12px rounded corners frames the entire card. The upper third has a subtle circular indentation area (darker, ~80px diameter) where an icon will be placed — just a soft shadow ring, no actual icon. The middle area is mostly clear with a very faint horizontal divider line at 10% opacity. The lower third has a slightly darker recessed area for text. No decorations, no patterns, no glow — just clean, functional, modern UI card design. Minimal corner bevels add slight depth. Feel: standard issue, utilitarian, a reliable basic card.
```

---

### 7. 🟢 Uncommon — Ön Yüz
**Dosya adı:** `card_front_uncommon.png`

```
An elegant nature-themed card front frame template for a game UI. Deep teal-black base (#141E28) with a subtle vertical gradient: slightly lighter emerald-tinted center fading to dark edges. A 1.5px emerald-green (#64DC8C) glowing border with 14px rounded corners. Small decorative leaf-like flourishes at the top-left and bottom-right corners, drawn in thin green lines at 30% opacity. The upper area has a soft circular glow zone (~80px) in muted green for the icon placement — just a gentle green ambient ring. A thin horizontal emerald line divides the upper icon area from the content below at 15% opacity. The lower content area has a very subtle organic pattern overlay (faint veins/leaves) at 5% opacity. Feel: a step above common — there's a quiet elegance here, nature-powered and promising.
```

---

### 8. 🔵 Rare — Ön Yüz
**Dosya adı:** `card_front_rare.png`

```
A prestigious crystal-themed card front frame template for a game UI. Deep ocean-blue base (#101830) with a rich vertical gradient from slightly brighter blue at the top to deep navy at the bottom. A 2px ice-blue (#50B4FF) glowing border with subtle outer glow (3px soft bloom) and 16px rounded corners. Decorative crystal shard elements at all four corners — small angular ice fragments catching light at 25% opacity. The upper area features a hexagonal icon frame zone (~85px) with crystalline edges glowing faintly blue. A thin horizontal band of crystal-pattern divides the top area from the content zone, with small refraction sparkles along it. The content area background has a very subtle diamond-lattice pattern at 8% opacity. The overall card has a faint inner shadow creating depth. Feel: rare and valuable — like a card forged from arctic crystal, cold but beautiful.
```

---

### 9. 🟣 Epic — Ön Yüz
**Dosya adı:** `card_front_epic.png`

```
A powerful arcane-themed card front frame template for a game UI. Deep void-purple base (#120C28) with a dramatic gradient: dark purple edges fading to a slightly lighter mystical center. A 2px amethyst-purple (#B450FF) neon-glowing border with a visible 5px outer glow bloom and 18px rounded corners. Small arcane energy wisps curl inward from the top corners. The upper icon area features an octagonal frame (~90px) with rotating energy ring effect drawn in purple and hints of magenta (#FF00C8), giving a dual-color mystical feel. A horizontal energy wave band separates the icon area from the lower content zone — this band has small orbiting particle dots along it. The lower content area has a very faint swirling nebula overlay at 6% opacity. Two small decorative orbs of purple light float near the bottom corners. The inner edge of the border has subtle inner glow. Feel: epic and intimidating — this card pulses with contained magical power.
```

---

### 10. 🟡 Legendary — Ön Yüz
**Dosya adı:** `card_front_legendary.png`

```
An awe-inspiring legendary card front frame template for a game UI. Ultra-deep black-midnight base (#0A0818) with a dramatic golden-lit gradient: warm golden (#FFB400) light emanates subtly from the center, fading into deep darkness at the edges, like a treasure glowing in a dark vault. A 3px ornate golden border with intricate corner decorations — each corner has a small starburst filigree design with fine golden lines. The border has a warm 6px outer glow bloom in gold-orange. The upper icon area features an elaborate circular mandala-frame (~95px) with golden filigree petals and a subtle inner golden glow ring — this is where the icon sits. Golden ember particles drift upward from this frame. A luxurious horizontal golden ornamental divider with a small diamond centerpiece separates the icon from the content zone. The lower content area has an extremely faint golden damask pattern at 4% opacity. The entire card surface has barely visible golden dust particles floating. Bottom edge has subtle upward-flowing warm light wisps. Feel: the pinnacle of rarity — this card is a legendary artifact, radiating prestige, power, and unmistakable importance. Anyone who sees this card knows it's something truly special.
```

---

## 📁 Dosya Yapısı

Üretilen PNG dosyaları şu konuma yerleştirilmeli:

```
assets/ui/cards/
├── card_back_common.png
├── card_back_uncommon.png
├── card_back_rare.png
├── card_back_epic.png
├── card_back_legendary.png
├── card_front_common.png
├── card_front_uncommon.png
├── card_front_rare.png
├── card_front_epic.png
└── card_front_legendary.png
```

## 🎨 Üretim Sonrası Kontrol Listesi

- [ ] Tüm görseller 300×380 px boyutunda mı?
- [ ] Şeffaf arka plan (alpha channel) var mı?
- [ ] Ön yüzlerde içerik alanları (ikon, başlık, açıklama) boş bırakılmış mı?
- [ ] Enderlik renkleri doğru HEX kodlarına uyuyor mu?
- [ ] Arka yüzlerde merkez alanı soru işareti için uygun mu?
- [ ] Kenarlık köşe yuvarlaklıkları görsel olarak tutarlı mı?
- [ ] Her enderlik seviyesi görsel olarak ayırt edilebilir mi? (Common → Legendary artan ihtişam)
- [ ] Koyu tema uyumlu mu? (Açık renk arka plan YOK)
- [ ] PNG dosya boyutu makul mü? (< 500 KB her biri)

## 💡 Ek Notlar

1. **Ön yüz PNG'leri şablondur** — metin, ikon, etiket (tag badge) gibi tüm içerikler **kod ile** render edilir. PNG sadece arka plan çerçevesidir.

2. **Arka yüz PNG'leri tam desendir** — ortadaki "?" soru işareti hâlâ **kod ile** eklenecektir ama desen tamamen PNG'den gelecektir.

3. **Kart boyutu dinamik olabilir** — debug modunda 220×300'e küçülür. PNG'lerin `pygame.transform.smoothscale` ile ölçekleneceğini göz önünde bulundurun, bu yüzden çok ince (1px) detaylardan kaçınmak en iyisidir.

4. **Parçacık efektleri kodda kalacak** — kart etrafındaki parçacıklar, glow animasyonları ve pulse efektleri zaten kodda var. PNG sadece statik arka planı sağlar.

5. **Glassmorphism uyumu** — Kart arkasında oyun tahtası hafifçe görünür (UI glassmorphism efekti). PNG'lerin %85-95 opaklıkta olması, alttaki cam efektinin hissedilmesini sağlar.
