# Kart Ustaligi Modu: Sinirli Hak Kartlarinin Stacklenmesi ve Havuz Kontrolu Analizi

Bu dokuman, Kart Ustaligi modunda yer alan sinirli kullanim hakki sunan kartlarin (Keskin Nisanci, Cekic, Bomba Ustasi, Son Dusus vb.) tekrar secilmesi durumunda uygulanan hak yenileme mantiginin degistirilerek birikimli (stack) hale getirilmesi ve belirlenen yedek sinirina ulasildiginda ilgili kartin secim ekranindan gecici olarak elenmesi tasarisi uzerine yapilan teknik ve oyun tasarimi analizini icermektedir.

---

## 1. Mevcut Sistemin Analizi ve Kod Tabanindaki Durum

Quadrix kod tabanindaki [game_modes_extra.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py) dosyasinda yapilan incelemeler sonucunda, sinirli kullanima sahip (limited) kartlarin secim ve etki uygulama surecleri asagidaki sekildedir:

### A. Kart Secim Havuzu Kontrolu (MysteryCardManager.select_card)
*   [game_modes_extra.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/v2/src/game_modes_extra.py#L1383-L1403) icerisinde tek kullanimlik (`single_use: True`) veya kalici (`persistent: True`) kartlar secildiginde `used_card_ids` setine eklenerek havuzdan kalici olarak cikarilir.
*   Ancak limited (`limited: True`) kartlar, `is_one_time = bool(card.get('persistent')) or (bool(card.get('single_use')) and not bool(card.get('limited')))` kontrolu sayesinde `used_card_ids` setine eklenmezler. Bu sayede bu kartlar haklari bitse de bitmese de tekrar secim havuzuna girebilir ve secim ekraninda karsimiza cikabilirler.

### B. Hak Atamalari ve Esitsizlikler (_apply_card_effect)
Mevcut kod tabaninda, limited kartlar tekrar secildiginde haklarin nasil degistigi konusunda bir tutarsizlik bulunmaktadir:

1.  **Maksimum Degere Tamamlama (Overwrite/Cap):**
    *   `bomb_master` (Bomba Ustasi), `rewind_power` (Geri Sarma), `perk_phase` (Sekil Degistirici), `quantum_tunneling` (Hayalet Parca), `hammer` (Cekic), `freeze_drop` (Son Dusus) ve `hole_hunter` (Delik Avcisi) kartlari tekrar secildiginde, eger oyuncunun elindeki mevcut hak kartin sagladigi temel hak degerinden kucukse, hak sayisi bu temel degere tamamlanir. Mevcut hak temel degerden buyuk veya esitse hicbir etki olusturmaz.
    *   Ornek (`bomb_master` icin):
        ```python
        cur = int(getattr(self, 'bomb_master_charges', 0) or 0)
        target_charges = self._card_int_value(card, 3)
        if cur < target_charges:
            self.bomb_master_charges = target_charges
        ```

2.  **Dogrudan Sifirlayarak Atama (Direct Reset):**
    *   `sniper_shot` (Keskin Nisanci) karti tekrar secildiginde, oyuncunun elindeki hak kontrol edilmeksizin dogrudan kartin temel degeri atanir. Oyuncunun elinde 2 hak varken tekrar secilirse hak sayisi 3'e tamamlanir, ancak elinde 4 hak olsaydi da deger 3'e dusurulurdu.
    *   Ornek (`sniper_shot` icin):
        ```python
        charges = int(card.get('value', 3))
        self._sniper_charges = charges
        ```

3.  **Birikimli Ekleme (Stacking):**
    *   `hold_destroyer` (Tuttugunu Koparan), `mirror_hold` (Ayna Cep) ve `echo_drop` (Yanki Dususu) kartlari ise zaten birikimli calismaktadir. Tekrar secildiklerinde hak sayisi dogrudan mevcut hakka eklenir.
    *   Ornek (`hold_destroyer` icin):
        ```python
        charges = int(card.get('value', 1))
        existing = int(getattr(self, '_hold_destroyer_charges', 0) or 0)
        self._hold_destroyer_charges = existing + charges
        ```

---

## 2. Onerilen Stackleme ve Havuz Seyreltme Sisteminin Detaylari

Onerilen sistemde:
1.  **Sinirli Hak Kartlarinin Stacklenmesi:** Bir sinirli hak karti elde varken tekrar secilirse, yeni haklar mevcut haklarin uzerine eklenir (orn. elde 2 Keskin Nisanci hakki varken 3 hak veren yeni bir Keskin Nisanci secilirse toplam hak 5 olur).
2.  **Yedek (Stack) Siniri:** Kartlarin sonsuza kadar birikmesini onlemek adina 1 stacklik yedek siniri (yani `temel_hak * 2` veya `temel_hak + yedek_hak`) belirlenir.
3.  **Dinamik Havuz Kontrolu:** Bir kartin haklari yedek sinirina ulastiginda, bu kart gecici olarak secim havuzundan cikarilir. Oyuncu haklarini harcayip yedek sinirinin altina dustugunde, kart secim ekraninda tekrar cikabilir hale gelir.

---

## 3. Oynanis Tasarimi Acisindan Yorumlar: Avantajlar ve Dezavantajlar

Onerilen sistemin oyuna eklenmesi durumunda olusabilecek avantajlar ve dezavantajlar asagida oyun tasarimi perspektifinden incelenmistir:

### Avantajlar

*   **Secimlerin Bosa Gitmesini Engelleme (UX ve Tatmin Hissi):** Mevcut sistemde oyuncunun elinde 2 hak varken ayni karti tekrar secmesi durumunda hakkin sadece 3'e tamamlanmasi veya elinde 3 hak varken secmesinin hicbir etki yaratmamasi oyuncuda hayal kirikligi yaratmaktadir. Stackleme sistemi, oyuncunun yaptigi secimin tam olarak karsiligini almasini saglayarak odullendirme hissini guclendirir.
*   **Stratejik Derinlik ve Kaynak Yonetimi:** Oyuncular zorlu seviyelere hazirlanmak amaciyla erken asamada Keskin Nisanci veya Cekic gibi guclu aktif yetenekleri biriktirip kritik anlarda ust uste kullanma stratejisi gelistirebilirler. Bu da oyunun taktiksel derinligini artirir.
*   **Dinamik Havuz Seyreltme (Deck Thinning):** Bir kart yedek sinirina ulastiginda havuzdan elenecegi icin oyuncunun karsisina cikma ihtimali olan diger kartlarin olasiligi artar. Bu durum oyuncunun daha dengeli ve cesitli bir deste olusturmasina yardimci olur.
*   **Tutarlilik:** Projedeki limited kartlarin bir kisminin stacklenmesi (Hold Destroyer gibi), bir kisminin ise overwrite edilmesi (Sniper gibi) tasarimsal bir tutarsizliktir. Tum sinirli kartlarin tek bir kurala baglanmasi sistem anlasilirligini kolaylastirir.

### Dezavantajlar ve Riskler

*   **Denge Bozulmasi (Overpowered Builds):** 5 adet Keskin Nisanci atisi veya 5-6 adet Cekic hakki biriktiren bir oyuncu, tahtada olusabilecek zor durumlarin tamamini hic risk almadan sadece bu haklari kullanarak cozebilir. Bu durum oyunun zorluk egrisini ve roguelite dinamiklerini zedeleyebilir.
*   **UI ve Geri Bildirim Zorlugu:** Oyuncunun hangi kartin stack sinirina ulastigini ve neden artik secim ekraninda cikmadigini anlamasi guc olabilir. Eger UI uzerinde maksimum stack siniri ve mevcut stack durumu net bir sekilde gorsellestirilmezse, oyuncular bunu bir hata olarak algilayabilir.
*   **Oyun Temposunun Yavaslamasi:** Aktif yeteneklerin cok fazla birikmesi, oyuncunun surekli oyunu durdurarak oyunun akisini bolmesine ve tempo kaybina neden olabilir.

---

## 4. Teknik Uygulama Yol Haritasi

Kod tabaninda somut bir degisiklik yapilmaksizin, bu sistemin en temiz ve performansli sekilde nasil kodlanabilecegi planlanmistir:

### A. Kart Katalog Metadatasinin Genisletilmesi
Katalogdaki her limited karta `base_charges` ve `max_stacks` alanlari tanimlanmalidir.
```python
# Örnek kart tanımı (game_modes_extra.py)
{
    "id": "sniper_shot",
    "title": "Keskin Nisanci",
    "base": 3,
    "value_range": (3, 3),
    "limited": True,
    "single_use": True,
    "base_charges": 3,  # Temel hak sayısı
    "max_stacks": 1,     # Maksimum yedek stack sayısı (1 stack yedek = 3 yedek hak)
    # ... diğer alanlar ...
}
```

### B. Dinamik Secim Havuzu Filtreleme (MysteryCardManager.prepare_selection)
`prepare_selection` fonksiyonunda, oyuncunun elindeki mevcut haklar ile kartin yedek kapasitesi karsilastirilmalidir:
```python
def _is_fully_stacked(c):
    if not c.get("limited"):
        return False
    
    cid = c.get("id", "")
    group = c.get("_group_id", cid)
    base_charges = c.get("base_charges", c.get("base", 3))
    max_stacks = c.get("max_stacks", 1)
    max_allowed = base_charges * (1 + max_stacks)
    
    # Her limited kartın değişkenine göre eldeki hakkı kontrol et
    current_charges = 0
    if group == "sniper_shot":
        current_charges = getattr(self.mode, "_sniper_charges", 0)
    elif group == "hammer":
        current_charges = getattr(self.mode, "hammer_charges_remaining", 0)
    elif group == "bomb_master":
        current_charges = getattr(self.mode, "bomb_master_charges", 0)
    elif group == "rewind_power":
        current_charges = getattr(self.mode.perk_manager, "rewind_uses", 0)
    elif group == "freeze_drop":
        current_charges = getattr(self.mode, "_freeze_drop_charges", 0)
    elif group == "hold_destroyer":
        current_charges = getattr(self.mode, "_hold_destroyer_charges", 0)
    elif group == "quantum_tunneling":
        current_charges = getattr(self.mode, "tunnel_charges_remaining", 0)
    elif group == "hole_hunter":
        current_charges = getattr(self.mode, "_hole_hunter_charges", 0)
    elif group == "mirror_hold":
        current_charges = getattr(self.mode, "_mirror_hold_charges", 0)
    elif group == "echo_drop":
        current_charges = getattr(self.mode, "_echo_drop_charges", 0)
    elif group == "perk_phase":
        current_charges = getattr(self.mode, "phase_shift_uses_remaining", 0)
        
    return current_charges >= max_allowed
```
Bu kontrol mantigi `prepare_selection` icindeki list filtration asamasina dahil edilerek tam stacklenmis kartlarin havuzdan elenmesi saglanir:
```python
filtered_available = [
    c for c in self.catalog
    if not (c.get("persistent") and any(ac.get("id") == c.get("id") for ac in self.active_cards))
    and not _is_used(c)
    and not _is_locked(c)
    and not _is_fully_stacked(c)  # Yeni kontrol filtresi
]
```

### C. Haklarin Toplanmasi ve Sinirlandirilmasi (MysteryMode._apply_card_effect)
Kart secildiginde hak atamalari birikimli hale getirilmeli ve yedek sinirini asmayacak sekilde sinirlandirilmalidir:
```python
elif effect_id == "sniper_shot":
    charges = int(card.get('value', 3))
    existing = int(getattr(self, '_sniper_charges', 0) or 0)
    base_charges = int(card.get('base_charges', 3))
    max_stacks = int(card.get('max_stacks', 1))
    max_allowed = base_charges * (1 + max_stacks)
    
    self._sniper_charges = min(max_allowed, existing + charges)
    # ... diger visual ve sync kodları ...
```

---

## 5. Sonuc ve Tavsiye

Onerilen biriktirme ve havuz kontrol mekanizmasi, **oyuncu memnuniyeti (UX) ve oyun tutarliligi acisindan cok buyuk bir avantaj saglamaktadir.** Mevcut sistemdeki "bosa giden secimler" hissini ortadan kaldirmak oyun deneyimini daha kaliteli hale getirecektir.

**Tavsiye:**
Bu sistemin oyuna eklenmesi **kesinlikle tavsiye edilmektedir.** Ancak oyun dengesinin korunabilmesi icin su noktalara dikkat edilmelidir:
1.  **Yedek Limitlerinin Siki Tutulmasi:** `max_stacks` degeri varsayilan olarak 1 (en fazla 2 temel kullanim hakki birikecek sekilde) olarak tutulmalidir. Sniper icin toplam hak hicbir zaman 6'yi asmamalidir.
2.  **UI Geri Bildirimi:** Aktif kart HUD gostergesinde, hak sayisi maksimuma ulastiginda sayi rengi altin rengine donmeli veya yanina kucuk bir MAX metni yerlestirilmelidir. Boylece oyuncu kartin artik secim ekraninda cikmayacagini sezgisel olarak anlayabilir.
