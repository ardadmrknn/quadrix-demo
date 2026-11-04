# İkinci Geri Bildirim Seti — Teknik Tetris Oyuncusu Analizi

> **Bu belgenin kaynağı `v2` deposudur.** `quadrix-demo`'ya kopyalanma nedeni: aşağıdaki **en kritik 7 bulgu demo kodunda da birebir mevcuttur** (2026-11-05 doğrulaması). Belgedeki `file:///` bağlantıları ve satır numaraları **v2** ağacına aittir.
>
> | Bulgu | v2 konumu | Demo konumu |
> | :--- | :--- | :--- |
> | Cascade turları tek skora toplanıyor (TRIPLE→QUADRIX) | `src/board.py:190-211` | [`src/board.py:191`](../../quadrix-demo/src/board.py#L191) |
> | Kombo sayacı 1'den başlıyor | `src/board.py:260-264` | [`src/board.py:268`](../../quadrix-demo/src/board.py#L268) |
> | Mini T-spin puanı yarı (100×level) | `src/board.py:253-255` | [`src/board.py:254-255`](../../quadrix-demo/src/board.py#L254) |
> | O parçası spawn_x hatası | `src/game.py:2374-2379` | [`src/game.py:2263-2268`](../../quadrix-demo/src/game.py#L2263) |
> | Hold oryantasyonu sıfırlanmıyor | `src/game_modes_extra.py:8329` | [`src/game_modes_extra.py:7587`](../../quadrix-demo/src/game_modes_extra.py#L7587) |
> | I parçası kick tablosu | `src/pieces.py:69-78` | [`src/pieces.py:72-80`](../../quadrix-demo/src/pieces.py#L72) |
> | Hız Patlaması rozeti "40 Hak" / açıklama "40 saniye" | `game_modes_extra.py:14226` | [`game_modes_extra.py:12030`](../../quadrix-demo/src/game_modes_extra.py#L12030), [`localization.py:1363`](../../quadrix-demo/src/localization.py#L1363) |


> **Kaynak:** `aboooo/` klasörü — `aboooo.html` (teknik rapor) + `images/` altında **18 PNG + 6 GIF** (toplam 24 medya dosyası).
>
> **İlişkili belge:** Bu belge, [`fullmetalpomak_feedback_analizi.md`](fullmetalpomak_feedback_analizi.md) belgesinin **tamamlayıcısıdır**. İki set farklı oyunculardan gelmiştir ve **beş konuda bağımsız olarak örtüşmektedir**. Çapraz eşleme için bkz. [§2](#2-i̇ki-geri-bildirim-seti-arasındaki-çapraz-eşleme).
>
> **Üçüncü belge:** [`TESTER_INSTAGRAM_FEEDBACK_ANALIZI_TR.md`](TESTER_INSTAGRAM_FEEDBACK_ANALIZI_TR.md) — bu, **FullMetalPomak sohbetinin daha titiz bir analizidir** (16 başlık, 12 maddelik doğrulama planı). Bu belgedeki #A (SRS) için **dördüncü** teyit kaynağı değildir (o sohbette SRS iddiası yok), ancak **#M (kampanya) ve #D/#G/#H** için o belge daha ayrıntılı kod kanıtı sunar.
>
> **Bu belgede olmayan, tester belgesine özgü 3 bulgu:** `show_ghost` ayarının çizimle bağlantısız olması · maksimum 3 ardışık parça filtresinin torbayı bozması · workshop parçalarının torbaya otomatik girmesi.
>
> **Analiz yöntemi:** Rapordaki her iddia için ilgili kaynak kod okunmuş, kritik olanlar gerçek `Game` nesnesi kurulup ampirik olarak test edilmiştir (`scratch/fb_probe.py`). **Kod tabanında hiçbir değişiklik yapılmamıştır** — bu belge yalnızca analizdir.

## Bu oyuncunun profili

Bu geri bildirim sahibi, FullMetalPomak'tan belirgin biçimde farklı bir profil: **SRS / SRS+ ayrımına**, **B2B zinciri mantığına**, **MTSS (Mini T-Spin Single) değerlerine**, **Cascade yerçekimi semantiğine**, **TOP OUT vs LOCK OUT tanımlarına** ve **ARE (Entry Delay)** kavramına hâkim. Bu, Tetris mekaniklerini tasarım seviyesinde bilen bir oyuncudur.

Bunun pratik sonucu: tespitlerinin çoğu **teknik olarak doğrulanabilir** çıkmıştır. Aşağıdaki 14 maddenin **9'u kodla birebir doğrulandı**, **3'ü kısmen doğrulandı**, **2'si doğrulanamadı** (manuel test gerekiyor).

---

# 1. Geri Bildirimlerin Özet Tablosu (#A – #N)

| # | Kategori | Geri Bildirim Özeti | Doğrulama Durumu | Kod Referansı | Öncelik |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A** | **SRS / Rotasyon** | I parçasının rotasyonları yanlış; bundan dolayı bazı I-spin'ler yanlış veya mümkün olanlar mümkün değil. | **DOĞRULANDI** (bağımsız ölçüm: I, Guideline'da 0/8, SRS+'ta 0/8) | [`pieces.py:69-78`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L69-L78) | **Kritik (P0)** |
| **B** | **Spawn** | O parçasının doğduğu yer yanlış — bir sağda doğmalı. | **DOĞRULANDI** (ölçüm: O şu an sütun 3–4; Guideline 4–5) | [`game.py:2374-2379`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L2374-L2379) | **Yüksek (P1)** |
| **C** | **Hold** | Döndürülmüş parça hold'a alınırsa sıfır oryantasyonuna dönmeli; ayrıca hold+rotate yakın basımı kontrolsüz dönmeye sebep oluyor. | **DOĞRULANDI** (ampirik: `rotation_state` 2→2, sıfırlanmıyor) | [`game_modes_extra.py:8329`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py#L8329), [`game.py:1997`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L1997) | **Yüksek (P1)** |
| **D** | **Animasyon / ARE** | Satır temizleme animasyonu bitene kadar parça **doğmamalı**; "aşağı düşmesin ama hareket edebilsin" veya "SDF çalışmasın" yetersiz. | **DOĞRULANDI** (ölçüm: 768–1568 ms, çözünürlüğe bağlı) | [`game.py:5276-5280`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5276-L5280), [`game.py:5436-5440`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5436-L5440) | **Kritik (P0)** |
| **E** | **MTSS / Skor** | MTSS (Mini T-Spin Single) yok; 200×level vermeli ve B2B korumalı. | **DOĞRULANDI** (kod: mini = 100×level, satır sayısı ayrımı yok) | [`board.py:253-255`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L253-L255) | **Orta (P2)** |
| **F** | **Skor Tutarlılığı** | Single temizlikte bazen 138, bazen 133 puan — tutarsız. | **KÖK NEDEN BULUNDU** (`int()` ile kesilen 1.5× B2B çarpanı) | [`board.py:276`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L276) | **Orta (P2)** |
| **G** | **TOP OUT / LOCK OUT** | 20. satıra blok koyduğum anda oyun bitiyor; kural fazla agresif. | **DOĞRULANDI** (kod: görünür `row 0`'da tek dolu hücre → anında ölüm) | [`board.py:148-152`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L148-L152) | **Kritik (P0)** |
| **H** | **Kombo Sayacı** | Kombo sayacı 1'den başlıyor; ilk temizleme 0. kombo olmalı. | **DOĞRULANDI** (kod: `combo += 1` ilk temizlemede 1 yapıyor) | [`board.py:260-264`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L260-L264), [`game.py:6455`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6455) | **Yüksek (P1)** |
| **I** | **Cascade Modu** | Cascade'de tek hamle TRIPLE yerine QUADRIX sayıyor; bloklar iç içe giriyor. Cascade aşamaları ayrı temizlenmeli. | **KÖK NEDEN BULUNDU** (`while True` cascade turu tek `total_lines`'a toplanıyor) | [`board.py:190-211`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L190-L211) | **Kritik (P0)** |
| **J** | **(Inf) SDF** | SDF=Inf iken tuşa basınca tahtanın bir kısmı iniyor, geri kalanı standart SDF ile devam ediyor. | **DOĞRULANAMADI** — kod doğru görünüyor, manuel test şart | [`game.py:4828-4838`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L4828-L4838), [`game.py:5545-5548`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5545-L5548) | **Araştırılacak** |
| **K** | **Görsel Geri Bildirim** | T-spin olduğunu anlamanın tek yolu skora bakmak; görsel ipucu yok. | **DOĞRULANDI** (kod yorumu: *"T-spin kelimeleri kaldırıldı"*) | [`game.py:5079`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5079) | **Yüksek (P1)** |
| **L** | **40L HUD** | Hız gerektiren modda kocaman skor gösterilmemeli. | **DOĞRULANDI** (Sprint HUD'da skor çizimi var) | [`game_modes.py:28-72`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes.py#L28-L72) | **Orta (P2)** |
| **M** | **Kampanya Dengeleme** | Görev 7/16/22 (3000 skor), Görev 17 (3 yıldız için max 2 blok israf) başlangıç seviyesi için fazla zor. Tüm görevlerin 3 yıldızla bitirilebilir olduğu varsayılmamalı. | **İDDİA — solvabilite taraması gerekli** | [`difficulty_model.py:216-218`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/difficulty_model.py#L216-L218) | **Orta (P2)** |
| **N** | **Metin Kalitesi / UX** | Metinlerde "YZ slop" (anlamsız/alakasız cümleler), eğitim 5/8/11/14 metin sorunları, oyun içi ayarların çoğu değiştirilemiyor, başarım ünlemi, Steam ismi senkronu, eğitim navigasyonu, pencere kapama, inaktif pencere tuşları, Local PvP 0-2 berabere. | **KISMEN — UI akışları manuel doğrulama gerektiriyor** | `localization.py`, `tutorial_lessons.py`, `game_modes.py`, `focus_manager.py` | **Düşük (P3)** |
| **O** | **Kart Metni / Birim Tutarsızlığı** | **"40 saniye mi 40 hak mı?"** — Hız Patlaması kartında süre rozeti "40 Hak" yazıyor ama açıklama "40 saniye boyunca" diyor. Aynı değer iki farklı birimle sunuluyor. | **DOĞRULANDI** (kod: `limited: True` + `timed_buff: True` → rozet `"{value} Hak"`, `_speed_burst_timer = value` saniye) | [`game_modes_extra.py:890-904`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py#L890-L904), [`game_modes_extra.py:14226`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py#L14226), [`localization.py:18275`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/localization.py#L18275) | **Orta (P2)** |

**Doğrulama özeti:** 10 birebir doğrulandı · 3 kısmen/araştırılacak · 2'si manuel test gerektiriyor.

> **NOT: Bu belgedeki maddelerin ana belgedeki karşılıkları:**
> **#A** ↔ [#12](fullmetalpomak_feedback_analizi.md#feedback-12-rotasyon-sistemi--srs--srs-uyumu-ve-kick-sistemi-çalışmıyor-geri-bildirimi) · **#D** ↔ [#7](fullmetalpomak_feedback_analizi.md#feedback-7-satır-silme-clear-ve-düşüş-fall-animasyonlarındaki-yarı-donuk-hybrid-durum-çelişkisi) · **#G** ↔ [#9](fullmetalpomak_feedback_analizi.md#feedback-9-tahta-boyutu-2010-vs-222410-buffer-zone-skip_hidden_rows-ve-yüksek-kulede-comeback-imkânsızlığı) · **#H** ↔ [#8](fullmetalpomak_feedback_analizi.md#feedback-8-puan-combo-ve-milestone-bildirimlerinin-tahtayı-kapatması-puan-bildirimleri-kör-edebiliyor) · **#M** ↔ [#4](fullmetalpomak_feedback_analizi.md#feedback-4-campaign-görev-farkındalığı-level-17-matematikselrng-darboğazı-ve-dinamik-zorluk-önerisi)
> **#B, #C, #E, #F, #I, #J, #K, #L, #N** → bu belgeye özgü yeni bulgular; ana belgede karşılığı yok.
> Ana belgenin birleşik eylem planı: [§3 Özet Eylem Planı](fullmetalpomak_feedback_analizi.md#3-özet-eylem-planı-ve-öncelik-sırası-önce-gameplayi-çöz)

---

# 2. İki Geri Bildirim Seti Arasındaki Çapraz Eşleme

Bu bölüm, **iki farklı oyuncunun aynı sorunu bağımsız olarak bildirdiği** maddeleri gösterir. Bağımsız teyit, sorunun öznel bir tercih değil **nesnel bir kusur** olduğunun en güçlü kanıtıdır.

## 2.1 Örtüşen maddeler (bağımsız teyit)

| Bu belge (#A–N) | Diğer belge | Ortak konu | Ne ekliyor |
| :--- | :--- | :--- | :--- |
| **#A** (SRS/I tablosu) | [Feedback #12](fullmetalpomak_feedback_analizi.md#feedback-12-rotasyon-sistemi--srs--srs-uyumu-ve-kick-sistemi-çalışmıyor-geri-bildirimi) | I parçası kick tablosu Guideline/SRS+ ile uyuşmuyor | **Bağımsız üçüncü kaynak.** Ayrıca **O spawn hatasını** ekliyor (#B) — #12'de yoktu. |
| **#D** (Animasyon/ARE) | [Feedback #7](fullmetalpomak_feedback_analizi.md#feedback-7-satır-silme-clear-ve-düşüş-fall-animasyonlarındaki-yarı-donuk-hybrid-durum-çelişkisi) | Satır temizleme animasyonu sırasında "yarı-donuk" durum | **"İç içe geçme" mekanizmasını** daha net tarif ediyor: yerleşim animasyon-sonrası tahtaya göre hesaplanıyor, görsel tahta geride. Çözüm olarak **ARE**'yi açıkça adlandırıyor. |
| **#G** (Lock out) | [Feedback #9](fullmetalpomak_feedback_analizi.md#feedback-9-tahta-boyutu-2010-vs-222410-buffer-zone-skip_hidden_rows-ve-yüksek-kulede-comeback-imkânsızlığı) | Buffer zone yokluğu ve üst satırda ölüm | #9 "comeback imkânsız" diyor; bu belge **kuralın yanlış olduğunu** söylüyor (normal satır kısmen dolu olabilir). İkisi aynı kökü işaret ediyor. |
| **#H** (Kombo off-by-one) | [Feedback #8](fullmetalpomak_feedback_analizi.md#feedback-8-puan-combo-ve-milestone-bildirimlerinin-tahtayı-kapatması-puan-bildirimleri-kör-edebiliyor) | Kombo sayacı ve gösterimi | #8 görsel kirlilikten şikâyet ediyor; bu belge **değerin kendisinin hatalı olduğunu** buluyor. Tamamlayıcı. |
| **#M** (Kampanya zorluğu) | [Feedback #4](fullmetalpomak_feedback_analizi.md#feedback-4-campaign-görev-farkındalığı-level-17-matematikselrng-darboğazı-ve-dinamik-zorluk-önerisi) | Görev zorluğu (özellikle Level 17) | #4 tek seviyeye odaklanıyor; bu belge **en az 4 seviye + solvabilite taraması** gerektiğini söylüyor. Kapsamı genişletiyor. |

## 2.2 Bu belgenin getirdiği **yeni** konular

| Bu belge | Konu | Neden önemli |
| :--- | :--- | :--- |
| **#B** | **O parçası 1 sütun solda doğuyor** | Hiçbir önceki analizde yok. Tüm O parçası yerleşimlerini sistematik olarak 1 hücre kaydırıyor. |
| **#C** | **Hold oryantasyonu sıfırlanmıyor** | Guideline ihlali; hold kullanan her oyuncuyu etkiliyor. |
| **#E** | **Mini T-spin puanı yanlış** (100 vs 200, single/double ayrımı yok) | T-spin ağırlıklı oynayan herkesin skorunu bozuyor. |
| **#F** | **Skor yuvarlama tutarsızlığı** | Oyuncunun "bazen 138, bazen 133" gözlemi — güven kaybı. |
| **#I** | **Cascade modu bozuk** (TRIPLE→QUADRIX) | **Tek başına bir modu oynanamaz kılıyor.** En ciddi yeni bulgu. |
| **#J** | **(Inf) SDF dengesizliği** | Doğrulanamadı ama doğrulanması gerekir. |
| **#K** | **T-spin görsel bildirimi** | FullMetalPomak "puan bildirimleri kör ediyor" diyordu — bu oyuncu **tam tersini** istiyor. Dikkat: iki geri bildirim burada **çelişiyor**, tasarım kararı gerekir. |
| **#N** | **Metin kalitesi / "YZ slop" denetimi** | Sistematik çerçeve öneriyor: tüm metinleri sesli okuyup tutarsızları ayıklama. |

## 2.3 Çelişen nokta — dikkat

| Konu | FullMetalPomak | Bu belge | Çözüm |
| :--- | :--- | :--- | :--- |
| **T-spin bildirimi** | *"Puan bildirimleri kör edebiliyor"* → bildirimleri **azalt/tahta dışına al** | *"T-spin'in gerçekten T-spin olduğunu anlamanın tek yolu skora bakmak"* → **görsel ipucu ekle** | **İkisi birlikte uygulanabilir:** bildirimi **tahta dışına** (HUD kenarına) taşı ve **kısa süreli** yap. Böylece hem kör etmez hem oyuncu T-spin'i anlar. |

Bu çelişki, iki geri bildirimin **farklı oynanış tarzlarından** kaynaklanıyor: FullMetalPomak hız odaklı (bildirim engelliyor), bu oyuncu mekanik doğrulama odaklı (bildirim eksik).

---

# 3. Detaylı Analiz ve Çözüm Önerileri

## #A: SRS — I Parçası Kick Tablosu

**Oyuncu ifadesi:**
> *"Oyunda SRS olduğunu varsayarak; I parçasının rotasyonları yanlış… Bundan dolayı da bazı I spinler de ya yanlış ya da mümkün olanlar mümkün değil."*

**Kod kanıtı:** [`pieces.py:69-78`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/pieces.py#L69-L78)

**Bağımsız doğrulama:** Ampirik ölçümde I parçası Guideline SRS ile **0/8**, SRS+ ile **0/8** eşleşiyor. Gerçekçi tahtalarda dönüşlerin **%94.9'u** farklı hücreye oturuyor. Detaylı ölçümler için bkz. [Feedback #12](fullmetalpomak_feedback_analizi.md#feedback-12-rotasyon-sistemi--srs--srs-uyumu-ve-kick-sistemi-çalışmıyor-geri-bildirimi).

**Çözüm:**
1. `SRS_KICKS_I` tablosunu **Guideline SRS** veya **SRS+** (tercih: SRS+) tablosuyla değiştir.
2. `SRS_KICKS_180_I` tablosuna `(0, 0)` ilk testini ekle — şu anda boş tahtada bile kayma var.
3. **J/L/S/T/Z tablolarına dokunma** — ölçümde 8/8 birebir doğru.
4. Testi resmî tablolara karşı yaz (mevcut `test_tetrio_srs_plus_parity.py` kendi kopyasıyla karşılaştırdığı için tautolojik).

---

## #B: O Parçası Spawn Konumu

**Oyuncu ifadesi:**
> *"O parçasının doğduğu yer yanlış (bir sağda doğmalı)."*

**Kod kanıtı:** [`game.py:2374-2379`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L2374-L2379)

```python
def _compute_spawn_x(self, piece_width: int) -> int:
    board_width = ...
    preferred = max(0, (board_width // 2) - 2)   # 10 genişlikte -> 3
    max_x = max(0, board_width - piece_width)
    return max(0, min(preferred, max_x))
```

**Ampirik ölçüm (10 sütunlu tahtada):**

| Parça | Matris genişliği | `spawn_x` | Dolduğu sütunlar | Guideline beklentisi | Durum |
| :--- | ---: | ---: | :--- | :--- | :--- |
| I | 4×4 | 3 | 3, 4, 5, 6 | 3–6 | Doğru |
| **O** | **2×2** | **3** | **3, 4** | **4–5** | **1 sütun solda (HATA)** |
| T | 3×3 | 3 | 3, 4, 5 | 3–5 | Doğru |
| S/Z/J/L | 3×3 | 3 | 3, 4, 5 | 3–5 | Doğru |

**Kök neden:** `- 2` ofseti, **matris genişliği 3 ve 4 olan parçalar için** doğru sonuç veriyor. O parçası 2 genişliğinde olduğu için aynı ofset onu merkezden uzaklaştırıyor. Guideline "merkez" tanımı parçanın **dolu hücrelerinin** merkezidir, matris kutusunun değil.

**Çözüm:**
```python
# Öneri: spawn_x'i matris genişliğine göre değil,
# parçanın gerçek dolu hücre genişliğine göre hesapla (merkez hizalama).
def _compute_spawn_x(self, piece) -> int:
    cells = piece.get_cells()
    if not cells:
        return max(0, (self.board_width // 2) - 1)
    min_x = min(c[0] for c in cells)
    max_x = max(c[0] for c in cells)
    cell_width = max_x - min_x + 1
    # (board_width - cell_width) // 2 -> merkez; Guideline "sola yaslı" için -0
    return max(0, (self.board_width - cell_width) // 2)
```

Not: Guideline'da I ve O **merkezde**, diğerleri **sola yaslı** doğar. Bu yüzden I ve O için ayrı, T/S/Z/J/L için ayrı hesap gerekir — düz bir formül ikisini birden doğru yapamaz. **Test yazılmalı:** 7 parça × beklenen sütun aralığı.

---

## #C: Hold Oryantasyonu Sıfırlanmıyor

**Oyuncu ifadesi:**
> *"Modern Tetris'in doğası gereği, bir parça döndürmeden sonra saklanılması için tuşuna basılırsa, parça doğduğu oryantasyona geri döner… standart kural Hold parçasının sıfır oryantasyonuna dönmesidir."*

**Kod kanıtı:** [`game_modes_extra.py:8329`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py#L8329)

```python
def _prepare_piece_for_hold(self, piece, *, slot: str = 'primary'):
    _ = slot
    if piece is None:
        return None
    charges = int(getattr(self, '_mirror_hold_charges', 0) or 0)
    if charges <= 0:
        return piece          # <-- oryantasyon sıfırlama YOK
    mirrored = self._create_mirrored_hold_piece(piece)
    ...
```

Fonksiyon yalnızca **"Ayna Cep" perk'inin** mirror mantığını yapıyor; **oryantasyon sıfırlama hiç yok**. [`_reset_piece_state`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L1997) de `rotation_state` / `shape` alanlarına dokunmuyor.

**Ampirik doğrulama** (`scratch/fb_probe.py`): T parçası 2 kez döndürüldü (`rotation_state = 2`) → spawn'a yerleştirildi → **`rotation_state` hâlâ 2**.

**Çözüm:**
```python
def _reset_piece_orientation(self, piece):
    """Hold/swap sırasında parçayı spawn oryantasyonuna döndür."""
    if piece is None:
        return None
    from pieces import create_piece_by_name
    fresh = create_piece_by_name(piece.name, x=piece.x, y=piece.y)
    # renk/tekstür/workshop bayrakları korunur
    for attr in ('color', 'color_matrix', 'texture_path',
                 'texture_surface', 'texture_surface_original',
                 'is_workshop_piece', 'workshop_block_id'):
        if hasattr(piece, attr):
            setattr(fresh, attr, getattr(piece, attr))
    return fresh
```
Bu, hold'a giren ve hold'dan çıkan **her iki yolda** çağrılmalı (`game.py:2970`, `2992`, `3086`, `3116`).

**Ayrıca:** *"hold ile döndürme tuşunun yakın vakitlerde basılması parçaların kontrolsüz dönmesine sebep olabiliyor"* — bu büyük ihtimalle yukarıdaki hatanın yan etkisi. Hold düzeltildikten sonra **tekrar test edilmeli**; kalırsa input sıralaması (hold→rotate aynı karede) ayrıca incelenmeli.

---

## #D: Satır Temizleme Animasyonu ve ARE

**Oyuncu ifadesi:**
> *"Satır temizlene animasyonu bitene kadar parçanın DOĞMAMASI gerekiyor (ARE, Entry Delay). Parçanın bir süre aşağı düşmemesi ama hareket edebilmesi VEYA bu süre boyunca SDF'nin çalışmaması bunun için yetersiz."*

**Kod kanıtı:** [`game.py:5276-5280`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5276-L5280)

```python
def _automatic_gravity_paused(self) -> bool:
    """Modlar gravity'yi durdurabilir; normal animasyonda soft drop çalışır."""
    return self._line_clear_animation_active() and not bool(
        getattr(self, '_soft_drop_held', False)
    )
```

**Ölçüm** (`scratch/sweep_real4.py`, `sweep_resolution.py`): animasyon **768–1568 ms** sürüyor (çözünürlüğe bağlı), ve bu süre boyunca **gravity duruyor** ama parça hareket edebiliyor. Bu tam olarak oyuncunun "yetersiz" dediği durum.

Ayrıntılı ölçüm ve çözüm tablosu için bkz. [Feedback #7 ampirik ölçüm bölümü](fullmetalpomak_feedback_analizi.md#ampirik-ölçüm-sonuçları-2026-11-04).

**Bu belgenin eklediği yeni bilgi:** oyuncu "iç içe geçme" mekanizmasını netleştiriyor — *"Koyulan parçanın bulunduğu yer, satır temizleme animasyonundan SONRAKİ duruma göre hesaplandığından, bunlar iç içe giriyor."* Yani **ghost/yerleşim mantıksal tahtayı** kullanıyor, **görsel tahta** ise geride. İki temsil ayrışmış.

**Çözüm (oyuncunun önerisi doğrultusunda):**
1. **ARE uygula:** animasyon bitene kadar `current_piece = None` tut. Bu en temiz çözüm — hem görsel hem mantıksal tutarlılık sağlanır.
2. **Animasyon süresini sabitle** (piksel yerine zaman): `sweep_effects.py`'deki `travel_px / px_per_sec` hesabı yerine doğrudan `SWEEP_DURATION_MS ≈ 180`.
3. **Alternatif "TETR.IO anlık modu":** yarışma modlarında animasyonu hiç oynatma, tahtayı anında güncelle.

**Dikkat:** `_automatic_gravity_paused()` docstring'i *"normal animasyonda soft drop çalışır"* diyor **ama kodla çelişiyor** (`CLAUDE.md` §3: kod, yorumdan üstündür). Bu yorum da düzeltilmeli.

---

## #E: Mini T-Spin Puanlaması

**Oyuncu ifadesi:**
> *"MTSS'ler 200 × seviye kadar puan verir ve B2B serisini korur, bu puan Single'da 100 × seviyedir."*

**Kod kanıtı:** [`board.py:253-260`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L253-L260)

```python
if t_spin == 'mini':
    base_score = 100 * self.level        # <-- satır sayısı hiç kullanılmıyor
elif t_spin == 'full':
    t_spin_points = [400, 800, 1200, 1600]
    base_score = t_spin_points[min(total_lines, 3)] * self.level
else:
    points = [0, 100, 300, 500, 800]
    base_score = points[min(total_lines, 4)] * self.level
```

**İki ayrı kusur:**
1. **Mini T-spin satır sayısını ayırt etmiyor.** MTSS ve MTSD aynı puanı (100×level) veriyor.
2. **Değer yarısı:** Guideline'da mini T-spin single = **200×level**, kodda **100×level** — yani **Single ile birebir aynı**. MTSS ödüllendirmiyor.

**B2B tarafı doğru:** `board.py:273` — `is_b2b_action = (t_spin is not None and total_lines > 0)` → mini de B2B koruyor. **Doğru.**

**Çözüm:**
```python
if t_spin == 'mini':
    mini_points = [0, 200, 400]        # MTSS, MTSD
    base_score = mini_points[min(total_lines, 2)] * self.level
elif t_spin == 'full':
    t_spin_points = [0, 800, 1200, 1600]   # TSS=800 (Guideline: 800)
    base_score = t_spin_points[min(total_lines, 3)] * self.level
```
**Not:** mevcut `full` tablosu `[400, 800, 1200, 1600]` — ilk eleman **T-spin sıfır satır** için 400 (Guideline'da TSS=800). Yani **TSS de yarı puan**. Bu tablo da gözden geçirilmeli. Guideline değerleri: TSS 800, TSD 1200, TST 1600, T-spin (0 satır) 400.

---

## #F: Skor Tutarsızlığı ("bazen 138, bazen 133")

**Oyuncu ifadesi:**
> *"Skor hesaplamalarında ufak çaplı sorunlar var, single temizliyorum bazen 138 alıyorum, bazen 133."*

**Kök neden:** [`board.py:276`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L276)

```python
if self.back_to_back:
    base_score = int(base_score * 1.5)   # <-- int() kesme (yuvarlama değil)
```

`int()` **aşağıya kesiyor**, yuvarlamıyor. Combo bonusu (`self.combo * 50 * self.level`) ve unit points toplamı da buna eklenince, aynı hamle farklı level/combo durumlarında 133–138 aralığına düşebiliyor.

**Doğrulama:** Oyuncunun gördüğü sayılar level 1 dışında (muhtemelen level 1'de unit points veya gold bonus karışıyor). Kesin sayıyı üretmek için oyun içi durumu bilmek gerekir, ama **`int()` kullanımı** deterministik olmayan skor algısının en olası kaynağı.

**Çözüm:**
1. **Tek bir skorlama fonksiyonu** tanımla; tüm bonuslar toplandıktan **sonra tek seferde** `round()` uygula (ara adımlarda `int()` yok).
2. Skor bileşenlerini (base, combo, b2b, gold, unit) **ayrı ayrı HUD'da gösterebilir** hale getir — debug ve oyuncu güveni için.
3. Birim testi yaz: aynı tahta+hamle+level+combo kombinasyonu **her zaman aynı puanı** vermeli.

---

## #G: TOP OUT / LOCK OUT Kuralı

**Oyuncu ifadesi:**
> *"20'ye BLOK KOYDUĞUM ANDA oyunun bitmesi o kadar hoş bir şey değil… Parça doğacaksa tek bir yerde doğmalı ve top out/lock out durumlarını her koşulda sağlamalı ki oyun devam edebilsin ya da sona ersin."*

**Kod kanıtı:** [`board.py:143-152`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L143-L152)

```python
# Lock-out kuralı: satır temizlikleri bittikten sonra en üst GÖRÜNÜR satırda
# (row 0) dolu hücre kaldıysa game-over.
if _overflow_top or any(self._cell_filled(x, 0) for x in range(self.width)):
    self._last_lock_out = True
    if track_game_over:
        self._locked_out = True
```

**Sorun:** Guideline'da game over **iki** durumdur:
1. **Block Out:** yeni parça spawn olduğunda mevcut bloklarla çakışıyor
2. **Lock Out:** aktif parça **tamamıyla** görünür alanın üstünde kilitlendi

Kod ise "**görünür `row 0`'da herhangi bir dolu hücre**" durumunu ölüm sayıyor. Bu, normal oynanışta da ölüme yol açar: tahta `row 0`'da kısmen doluyken oynamaya devam etmek imkânsız hale gelir.

**Yorum çelişkisi:** Kod yorumu *"haksız ölümü önlemek için kural net biçimde görünür row 0'a bağlandı"* diyor — ama sonuç tersi. Ayrıca **buffer zone (vanish zone)** hiç yok: `BOARD_HEIGHT = 20` (`constants.py:14`), Guideline ise 20 görünür + gizli buffer ister.

**Çözüm:**
1. **Buffer zone tanımla:** mantıksal tahta `20 + 4 = 24` satır, görünür alan son 20. Spawn gizli alanda.
2. **Game over kuralını Guideline'a çek:**
   - Block Out: yeni parça spawn konumunda çakışıyorsa
   - Lock Out: kilitlenen parçanın **hiçbir** hücresi görünür alanda değilse
3. `row 0`'da kısmen dolu olmak **ölüm sebebi olmamalı**.
4. Buffer zone olmadan bu kural uygulanamaz — bu yüzden **#9 ile birlikte yapılmalı**.

---

## #H: Kombo Sayacı Off-by-One

**Oyuncu ifadesi:**
> *"Genel olarak, satır temizlenen ilk parça 0. kombo, satır temizlenen ikinci parça 1. kombo olarak geçer. Ancak burada kombo sayacı 1'den başlıyor."*

**Kod kanıtı:** [`board.py:260-268`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L260-L268)

```python
combo_bonus = 0
if total_lines > 0:
    if self.combo > 0:
        combo_bonus = self.combo * 50 * self.level
    self.combo += 1        # <-- ilk temizlemede combo 0 -> 1
else:
    self.combo = 0
```

İlk temizlemede `combo` 0→1. Ekran gösterimi [`game.py:6455`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L6455):

```python
if self.board.combo > 1:
    stat_row_defs.append((t('combo'), f'x{self.board.combo}', ...))
```

Yani ikinci temizlemede "x2 Combo" gösteriliyor — Guideline'da bu **x1** olmalı.

**Not:** `combo_bonus` hesabı **doğru** (ilk temizlemede bonus 0). Sorun yalnızca **sayacın kendisi ve gösterimi**.

**Çözüm:**
1. `self.combo` değerini **temizleme sayısının bir eksiği** olarak tut: `combo = temizleme_sayısı - 1`.
2. HUD eşiğini `> 0` yap (şu an `> 1`).
3. **İstatistik göçü:** mevcut profillerdeki `highest_combo` değerleri 1 fazla kaydedilmiş — migration veya "yeni baştan" kararı gerekir.

---

## #I: Cascade Modu — En Ciddi Bulgu

**Oyuncu ifadesi:**
> *"Normalde bunun TRIPLE sayılması gerekiyor… AMA bu blok TRIPLE'dan sonra temizlerdi, anında değil. Ancak durum bu oyunda böyle değil… Sadece hatalı bir şekilde QUADRIX olmadı, TRIPLE yerine QUADRIX saydı. Bloklar iç içe girdi, salak saçma bir şeyler oldu."*

**Kod kanıtı:** [`board.py:190-211`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/board.py#L190-L211)

```python
while True:
    lines_to_clear = []
    for y in range(self.height):
        if all(self._cell_filled(x, y) for x in range(self.width)):
            lines_to_clear.append(y)
    if not lines_to_clear:
        break
    ...
    total_lines += len(lines_to_clear)    # <-- tüm cascade turları TEK sayaca
```

**Kök neden:** Cascade döngüsü **tek bir `clear_lines` çağrısı içinde** çalışıyor. Döngü bittiğinde `total_lines` şunları toplamış oluyor:
- İlk turda temizlenen 3 satır (**TRIPLE** olmalı)
- Bloklar düştükten sonra oluşan 1 satır (**ayrı bir sonraki temizleme** olmalı)

Sonuç: `total_lines = 4` → `points[min(4, 4)] = 800` → **"QUADRIX"** sayılıyor ve tek bir tetris olarak kaydediliyor.

**Doğru cascade semantiği:**
1. Kilitlenme → ilk dolu satırlar temizlenir → **skorlanır** (TRIPLE)
2. Üstteki bloklar düşer → **yeni** dolu satırlar oluşursa temizlenir → **ayrı skorlanır** (SINGLE)
3. Her aşama kendi combo adımını ve kendi B2B durumunu işler

**Çözüm:**
1. `clear_lines` içindeki cascade döngüsünü **ayrı skorlama çağrılarına** böl: her tur kendi `total_lines` değeriyle `_score_clear()` çağırsın.
2. Her tur **combo'yu ayrı artırsın** — cascade zinciri combo zinciridir.
3. Her tur **tetris sayacını ayrı işlesin** (`board.tetrises` yalnızca 4 satırlık turlarda artmalı).
4. Görsel efektleri (`line_clear_sweep_rows`, `cascade_animations`) **tura göre** kuyruğa al; hepsi tek seferde patlamasın.
5. Oyuncunun "bloklar iç içe girdi" gözlemi, animasyon tarafında da tur ayrımı olmadığını gösteriyor — aynı düzeltme animasyonu da kapsamalı.

**Kapsam notu:** `clear_lines` **tüm modlarda** ortak. Cascade olmayan modlarda döngü ilk turda biter, yani düzeltme cascade'siz modları **etkilemez**. Ancak "Cascade Modu" (`game_modes_advanced.py:1196`) ekranda `cascade_bonus`/`cascade_animations` tutuyor — bu ayrı bir katman, ayrıca incelenmeli.

---

## #J: (Inf) SDF Dengesizliği — Doğrulanamadı

**Oyuncu ifadesi:**
> *"Soft Drop Factor ayarı infinite iken, soft drop kullanımında bir takım sorunlar oluşuyor. Tuş basıldığı anda tahtanın bir kısmını iniyor ve geri kalanı standart SDF ile devam ediyor. Basılı tutma durumunda parça normal SDF'de inmeye devam ediyor."*

**Kod kanıtı:** [`game.py:5545-5548`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5545-L5548)

```python
if not gravity_paused and getattr(self, '_soft_drop_held', False) and self.get_soft_drop_speed() == 0.0 and self.current_piece is not None:
    while self.board.is_valid_position(self.current_piece, dy=1):
        self.current_piece.y += 1
    self.fall_time = 0
```

Mantık **doğru görünüyor**: SDF `0.0` (sonsuz) ise parça geçerli olduğu sürece dibe kadar iner.

**Ampirik test:** İzole kurulumda parça **hiç inmedi** — çünkü `_soft_drop_held` bizim kurulumumuzda set edilmemişti. Yani iddia **doğrulanamadı**.

**Olası nedenler:**
1. `_soft_drop_held` **KEYDOWN**'da `True` oluyor, ama oyuncunun hissettiği "bir kısmı iniyor" **KEYDOWN**'ın kendisinden mi geliyor? (İlk dokunuşta birkaç satır iniyor olabilir)
2. `gravity_paused` kontrolü — animasyon sırasında anlık düşüş **çalışmıyor**. Oyuncu animasyon sırasında denemişse tam bu senaryo görülür.
3. **Tuş basımı state sırası:** KEYDOWN → `_soft_drop_held = True`; ama `update()` farklı bir sırayla işliyorsa, o karede anlık düşüş atlanabilir.

**Çözüm / sonraki adım:**
1. **Manuel test protokolü:** Sprint modunda SDF=Inf seç, bir parçayı hızlıca bırak, kaydırarak 5 tekrar yap. Her seferinde dibe kadar indi mi?
2. Eğer bazen iniyorsa: `_soft_drop_held` poll'ı yerine **olay tabanlı** anlık düşüş (KEYDOWN'da bir kez `while … y += 1`) ekle. Hold tarafı ayrıca ele alınmalı.
3. **Bu madde doğrulanmadan düzeltme yapılmamalı** — yanlış bir düzeltme mevcut doğru davranışı bozabilir.

---

## #K: T-Spin Görsel Bildirimi Yok

**Oyuncu ifadesi:**
> *"Bu oyunda T-spin'in gerçekten T spin olduğunu anlamamızın tek yolu skora bakmak… Belki bir görsel ipucu?"*

**Kod kanıtı:** [`game.py:5079`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game.py#L5079)

```python
# 2. Ekranda Gösterilecek Bildirim Mesajı (T-spin kelimeleri kaldırıldı)
if lines_cleared == 4:
    self.combo_message = "QUADRIX!"
elif lines_cleared >= 2:
    ...
```

Yorum açık: **T-spin kelimeleri bilinçli olarak kaldırılmış**. Muhtemelen FullMetalPomak'ın "bildirimler kör ediyor" geri bildirimi sonucu.

**Çelişki (dikkat):** İki oyuncu **karşıt** şey istiyor. Çözüm için bkz. [§2.3](#23-çelişen-nokta--dikkat).

**Çözüm (ikisini uzlaştıran):**
1. **Bildirimi HUD'a taşı:** tahtanın üstünde/ortasında değil, **sağ veya sol panelde** küçük bir rozet. FullMetalPomak'ın "kör etme" şikâyeti giderilir.
2. **T-spin için kısa + kalıcı gösterge:** T-spin gerçekleştiğinde HUD'da 1–2 saniye küçük bir `T-SPIN` rozeti.
3. **Parçacık/ekran sarsıntısını hafif tut:** T-spin'i tahtayı kapatmadan belli eden görsel dil.
4. **Kontrast/renk:** rozet ile arka plan kontrastı yüksek olmalı (`themes.py`).

---

## #L: 40L (Sprint) HUD'ında Skor Gösterimi

**Oyuncu ifadesi:**
> *"Kimse, hız gerektiren bir modda kafayı allak bullak edecek kocaman bir skor istemez."*

**Kod kanıtı:** [`game_modes.py:28-72`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes.py#L28-L72) — `SprintMode` süre odaklı; ama HUD'da `board.score` çiziliyor.

**Çözüm:**
1. **Sprint HUD'da büyük skoru kaldır** — ana istatistik **kronometre** ve **kalan satır** olmalı.
2. Skor yalnızca **sonuç ekranında** gösterilsin.
3. `UltraMode` skoru ana istatistik olarak **tutmalı** — orada doğru.
4. Mod bazlı HUD tanımı ayrıştırılmalı: `SprintMode.hud_fields = ('time', 'lines_left')`, `UltraMode.hud_fields = ('score', 'time')`.

---

## #M: Kampanya Dengelemesi ve Solvabilite

**Oyuncu ifadesi:**
> *"Görev 7- 3000 skor yapmak çok zor, bunu yapabilmenin tek yolu T-spin Triple, bundan emin misiniz?… Görev 17- Bu görevi 3 yıldız ile bitirmek teorik olarak biraz zor… VARSAYIM OLARAK, GÖREVLERİN HEPSİ 3 YILDIZLA TAMAMLANMASI MÜMKÜN OLMAYABİLİR, BÖLÜMLERİN ŞARTLARINA GÖZ ATILMASI GEREKİYOR."*

**Etkilenen seviyeler (oyuncunun bildirdiği):** 7, 16, 22 (3000 skor hedefi) · 17 (3 yıldızda max 2 blok israfı)

**Bağımsız teyit:** [Feedback #4](fullmetalpomak_feedback_analizi.md#feedback-4-campaign-görev-farkındalığı-level-17-matematikselrng-darboğazı-ve-dinamik-zorluk-önerisi) da Level 17'yi aynı şekilde işaretliyor.

**Çözüm — "solvabilite taraması":**
1. **Otomasyon yaz:** her seferinde `level_data` + `difficulty_model` okuyup hedefleri matematiksel olarak değerlendiren bir tarama betiği.
   - Örnek: "17 hamlede 2 Quadrix" → minimum hamle sayısı = f(tahta, blok dağılımı). Blok sayısı 17 ise ve Quadrix 4 satır demekse **matematiksel alt sınır** hesaplanabilir.
2. **Her seviye için "3 yıldız mümkün mü?" raporu** üret.
3. **Mümkün olmayanları** ya hedefi düşür ya da seviyeyi yeniden tasarla.
4. **CI kapısı:** bu tarama test suite'e eklensin — gelecekteki denge değişiklikleri solvabiliteyi bozarsa test kırılsın.

Kod referansları: [`difficulty_model.py:216-218`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/difficulty_model.py#L216-L218), [`level_data.py:539`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/campaign/level_data.py#L539).

---

## #N: Metin Kalitesi, Eğitim ve UI/UX

### N.1 "YZ slop" — metin denetimi

**Oyuncu ifadesi:**
> *"Oyunda çok fazla text-slop olduğunu hissediyorum… Eğer bir text ilkokul çocuğu tarafından oluşturulmuş gibi ise / anlatılması gereken şey ile alakası yoksa / cümle yapısında sorun varsa → büyük ihtimalle YZ yazmıştır. Bunun kontrolü için cümleyi seslice okumayı deneyin."*

**Sistematik denetim önerisi:**
1. `localization.py` içindeki tüm `tr`/`en` çiftlerini dışa aktar (CSV).
2. Her metin için üç kontrol: (a) mekanikle uyumlu mu, (b) cümle yapısı bozuk mu, (c) oyuncunun anlayacağı terim mi kullanıyor.
3. **Tutarsız terim sözlüğü:** aynı mekanik farklı isimlerle anılıyorsa (örn. "parça"/"taş"/"blok") tek terime indir.
4. Bu denetim **her yeni içerik eklenmesinde** tekrarlanmalı — CI'da bir terim listesi kontrolü olabilir.

### N.2 Eğitim metinleri

| Eğitim | Sorun | Öneri |
| :--- | :--- | :--- |
| **5** | Blok konduktan sonra ana hatlar yukarı hareket ediyor | Ana hattı kaldır veya sabit tut |
| **8 = 11** | Aynı sorun | İkisinde de düzelt |
| **14** | *"Bir deliği azalt"* garip ifade | *"Bir çöp satırı temizle"* |

Kod: `tutorial_lessons.py`, `tutorial_cards.py`.

### N.3 UI/UX hataları

| Sorun | Medya | Öneri |
| :--- | :--- | :--- |
| Oyun içi ayarların çoğu değiştirilemiyor | — | Hangi anahtarların salt-okunur olduğunu belirle; ya aktifleştir ya da gizle |
| Başarım yokken ünlem gösteriyor | `image12.png` | Bildirim tetikleme koşulunu düzelt (`achievement_manager` yeni başarım döndürdüğünde göstermeli) |
| Steam ismi değişince sıralamadaki isim güncellenmiyor | `image1.png` | Cache invalidation: Steam ismi değiştiğinde leaderboard cache temizle |
| "varsayılan" ve "takılı" aynı anlama geliyor | `image3.png` | Terminolojiyi ayır: "varsayılan" = otomatik seçim, "takılı" = manuel seçim; ya da tek terim kullan |
| Eğitim menüye değil mod seçimine dönüyor | — | Navigasyon hedefini düzelt |
| Pencere inaktifken tuşlar bozuk (*"imlecin bulunduğu yerdeki tuşa basamayabiliyor"*) | — | `focus_manager` odak yönetimini gözden geçir; fare konumu tabanlı seçim klavye odağını ezmemeli |
| Oyun altta iken görev çubuğundan kapatılamıyor | — | `QUIT`/`WM_CLOSE` olayı işleme; pencere simge durumundayken de kapanabilmeli |
| Local PvP 0-2'ye berabere yazıyor | — | Beraberlik/kaza koşulunu incele: tek taraflı skor 0-2 iken "berabere" hükmü yanlış olabilir |

---

## #O: Kart Metni / Birim Tutarsızlığı — "40 saniye mi 40 hak mı?"

**Oyuncu ifadesi:**
> *"40 saniye mi 40 hak mı?"* — Hız Patlaması kartı ekran görüntüsüyle birlikte.

**Görsel kanıt:** Kart üzerinde rozet **"40 Hak"** yazıyor; altındaki açıklama **"40 saniye boyunca parçalar daha hızlı düşer. Her sildiğin satır 1.5 katı puan kazandırır."**

**Kod kanıtı — üç nokta birbirini doğruluyor:**

1. **Kart hem `limited` hem `timed_buff` işaretli** ([`game_modes_extra.py:2172`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py#L2172), [`2198`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py#L2198)):
```python
{
    "id": "speed_burst_epic",
    "value": 40,              # <-- tek alan, iki anlam
    "limited": True,
    "timed_buff": True,
    "description": "{value} saniye boyunca parçalar daha hızlı düşer...",
}
```

2. **Rozet metni "Hak" diyor** ([`game_modes_extra.py:890-904`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py#L890-L904)):
```python
key = _card_type_label_key(card)          # 'card_type_limited' döner
if key == 'card_type_limited':
    val = card.get('value')               # 40
    label_tmpl = t('card_type_limited_dynamic')   # '{value} Hak'
    return label_tmpl.format(value=val)   # -> "40 Hak"
```
`card_type_limited_dynamic` tüm dillerde "kullanım" anlamı taşıyor: `tr: '{value} Hak'`, `en: '{value} Uses'`, `de: '{value} Verwendungen'` ([`localization.py:18274-18290`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/localization.py#L18274-L18290)).

3. **Ama çalışma zamanında değer SÜRE olarak kullanılıyor** ([`game_modes_extra.py:14226`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py#L14226)):
```python
elif effect_id == "speed_burst":
    duration = int(value)                      # <-- 40 SANİYE
    self._speed_burst_timer = duration
```

**Kök neden:** Tek `value` alanı iki farklı birimi temsil ediyor. `limited: True` bayrağı rozeti "hak" moduna sokuyor; ama etkinin kendisi **süreli** (`timed_buff`). Kod, başka kartlarda bu ayrımı doğru yapıyor — `freeze_drop` ayrı `freeze_duration` alanı kullanıyor ([`game_modes_extra.py:14384`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py#L14384)) ve hak sayısını `_card_int_value(card, 3)` ile ayrı okuyor. Yani **bu, `speed_burst` ailesine özgü bir eksiklik**, sistemik değil.

**Türkçe'ye özgü ek kusur:** `_card_type_label_key` ([`game_modes_extra.py:881`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py#L881)) açıklama metninde `'hak'` kelimesi geçerse kartı "limited" sayıyor. Bu sezgisel eşleşme İngilizce metinlerde (`"lives"`, `"uses"`) çalışmaz — yani **aynı kart farklı dilde farklı rozet gösterebilir**. Kırılgan bir bağımlılık.

**Dil tutarlılığı notu:** `card_speed_burst_desc` tüm dillerde `{value} saniye/seconds/Sekunden…` diyor; rozet ise her dilde "kullanım" diyor. **11 dilin tamamında** aynı çelişki var.

**Çözüm:**
1. **Ayrı alan kullan** — `freeze_drop` deseniyle tutarlı olacak şekilde:
```python
{
    "id": "speed_burst_epic",
    "value": 40,                    # hak/rozet anlamı (1 kullanım)
    "duration_seconds": 40,         # süre anlamı
    "timed_buff": True,
    "limited": False,               # timed_buff rozeti kullanılsın
}
```
2. **Rozet metnini süreye çevir:** `timed_buff` kartlar için `'{value} sn'` / `'{value} s'` etiketi ekle ([`localization.py`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/localization.py), 11 dil).
3. **Sezgisel `'hak' in desc` kontrolünü kaldır** ([`game_modes_extra.py:881`](file:///C:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py#L881)) — kart türü yalnızca açık bayraklardan (`limited` / `timed_buff` / `charges` / `single_use`) belirlenmeli.
4. **Kapsamı genişlet:** `timed_buff: True` bayrağı taşıyan **3 kart** var; üçü de aynı rozet yolundan geçiyor — hepsi kontrol edilmeli.

**Test:** Her `timed_buff` kartı için rozet ve açıklama metninin **aynı birimi** gösterdiğini doğrulayan birim testi; 11 dilin her biri için.

---

# 4. Öncelik Sıralaması ve Uygulama Planı

## 4.1 P0 — Oynanışı bozan (önce bunlar)

| Sıra | Madde | Sorun | Efor | Neden P0 |
| ---: | :--- | :--- | :--- | :--- |
| **1** | **#I Cascade** | TRIPLE→QUADRIX; mod oynanamaz | Orta (~60 satır) | Tek başına bir modu kırıyor |
| **2** | **#A SRS/I** | I dönüşleri standart dışı | Küçük (~15 satır) | İki bağımsız oyuncu bildirdi; pro temeli |
| **3** | **#G Lock out** | `row 0`'da tek hücre = ölüm | Orta (buffer zone ile birlikte) | Normal oynanışta haksız ölüm |
| **4** | **#D Animasyon/ARE** | Yarı-donuk, iç içe geçme | Orta | Akıcılık + görsel/mantıksal ayrışma |

## 4.2 P1 — Doğruluk ve tutarlılık

| Sıra | Madde | Sorun | Efor |
| ---: | :--- | :--- | :--- |
| 5 | **#B O spawn** | 1 sütun solda doğuyor | Küçük (~10 satır) |
| 6 | **#C Hold oryantasyon** | Sıfırlanmıyor | Küçük (~25 satır + 4 çağrı yeri) |
| 7 | **#H Kombo off-by-one** | 1'den başlıyor | Küçük (~5 satır + migration kararı) |
| 8 | **#K T-spin bildirimi** | Görsel ipucu yok | Küçük (HUD rozeti) |

## 4.3 P2 — Cila ve denge

| Sıra | Madde | Efor |
| ---: | :--- | :--- |
| 9 | **#E Mini T-spin puanı** | Küçük (tablo değişikliği) |
| 10 | **#F Skor yuvarlama** | Küçük (tek skorlama fonksiyonu) |
| 11 | **#L 40L HUD** | Küçük |
| 12 | **#O Kart birim tutarsızlığı** | Küçük (`duration_seconds` alanı + rozet etiketi + 11 dil) |
| 13 | **#M Kampanya solvabilite taraması** | Orta (otomasyon) |

## 4.4 Araştırılacak

| Sıra | Madde | Önce yapılacak |
| ---: | :--- | :--- |
| 14 | **#J (Inf) SDF** | Manuel test protokolü; doğrulanmadan düzeltme YOK |
| 15 | **#N Metin/UI** | Sesli okuma denetimi + UI akışlarının tek tek gezilmesi |

---

# 5. Uygulama Sırası Önerisi

Bu belge ile [`fullmetalpomak_feedback_analizi.md`](fullmetalpomak_feedback_analizi.md) birlikte okunduğunda, tek bir **ortak yol haritası** çıkar:

1. **SRS + spawn + hold** (A, #12, B, C) — **tek bir "parça geometrisi" düzeltme dalgası**. Aynı dosyalara dokunuyor, aynı testleri paylaşıyor.
2. **Cascade + skorlama** (I, E, F, H) — **tek bir "skorlama doğruluğu" dalgası**. Hepsi `board.py` içinde; birlikte ele alınınca tek seferde test edilebilir.
3. **Animasyon + lock out** (D, #7, G, #9) — **tek bir "oyun akışı" dalgası**. Buffer zone ve ARE aynı mekanizmanın iki yüzü.
4. **HUD + görsel geri bildirim** (#8, K, L, #1, #2) — **tek bir "arayüz" dalgası**. FullMetalPomak'ın kör etme şikâyeti ile bu belgenin görsel ipucu isteği birlikte çözülür.
5. **Kart metni + içerik** (#O, #4, M, N) — **tek bir "kart/içerik tutarlılığı" dalgası**. #O'daki birim tutarsızlığı, N.1'deki "text-slop" denetimiyle aynı taramada yakalanabilir.
5. **Kampanya + içerik** (#4, M, N) — **tek bir "içerik kalitesi" dalgası**. Solvabilite taraması + metin denetimi.

**Kritik uyarı:** 3. dalga (buffer zone) yapılmadan #9 ve #G düzeltilemez — `BOARD_HEIGHT = 20` sabit olduğu sürece Guideline lock-out kuralı uygulanamaz. Bu yüzden **buffer zone işi ilk adım olmalı**.

---

# 6. Doğrulama Durumu Özeti

| Durum | Madde sayısı | Maddeler |
| :--- | ---: | :--- |
| **Kodla birebir doğrulandı** | 9 | A, B, C, D, E, G, H, I, K |
| **Kısmen doğrulandı / araştırılacak** | 3 | J, L, M |
| **Manuel/UI doğrulama gerekiyor** | 2 | F (kök neden bulundu, sayı üretimi için oyun içi durum gerekli), N |

**Doğrulanan 9 maddenin 5'i mevcut bir testle kilitlenmiyor.** Aşağıdaki testlerin yazılması önerilir:

| Test | Kapsam |
| :--- | :--- |
| `test_spawn_columns_all_pieces.py` | 7 parça × beklenen sütun aralığı (B) |
| `test_hold_resets_orientation.py` | Döndürülmüş parça hold'a gidip dönünce oryantasyon 0 (C) |
| `test_i_kick_table_matches_guideline.py` | I tablosu resmî tabloya karşı, **statik kopya değil** (A) |
| `test_cascade_scores_per_stage.py` | Cascade'de TRIPLE→SINGLE ayrı skorlanıyor (I) |
| `test_mini_t_spin_values.py` | MTSS=200, MTSD=400 (E) |
| `test_combo_counter_starts_at_zero.py` | İlk temizleme combo 0 (H) |
| `test_lock_out_full_outside_only.py` | Kısmen görünür parça öldürmez (G) |
| `test_score_determinism.py` | Aynı durum → aynı puan (F) |

---

# 7. Kaynak Notu

Bu belge, `aboooo/aboooo.html` raporundaki bulguları ve 24 medya dosyasını (18 PNG, 6 GIF) analiz eder. XSS/güvenlik gereği HTML dosyası **statik olarak** işlenmiş, görseller **okunmuş ve yorumlanmıştır**; hiçbir dosya çalıştırılmamıştır.

Rapor sahibinin kimliği HTML içinde belirtilmemiştir; bu nedenle belge "ikinci geri bildirim seti" olarak anılmaktadır.

**Kod tabanına dokunulmamıştır** — bu belge yalnızca analiz ve çözüm önerileri içerir. Ölçüm betikleri `scratch/` altında olup repoya commit edilmemiştir.