# Demo Sürümü: Dinamik Varsayılan Ülke İzi Sistemi Entegrasyon Kılavuzu

Bu kılavuz, ana oyunda mağazada satılan ülke bayrağı temalı satır temizleme izlerini (line-sweep traces), demo sürümünde oyuncunun oyunu hangi ülkeden/dilden başlatmışsa o satır temizleme izini varsayılan (default) yapacak sistemin mimari kurgusunu, performans optimizasyonlarını, macOS uyumluluğunu ve entegrasyon adımlarını içerir.

> [!IMPORTANT]
> **Demo Sürümü Sınırlandırmaları:**
> 1. Demo sürümünde mağaza (Store) ekranı açılmayacak ve oyuncular manuel kozmetik değiştiremeyecektir. Bu nedenle bu sistemin tek amacı, oyun içindeki varsayılan satır temizleme izini otomatik ve statik olarak kullanıcının diline/ülkesine göre ayarlamaktır. Mağaza arayüzünde (`store_screen.py`) herhangi bir değişiklik yapılmasına gerek yoktur.
> 2. Satır temizleme izinin ucundaki refakatçi hayvan seçimi (pet companion) demo sürümünde özelleştirilemez. Bu nedenle refakatçi hayvan **her zaman varsayılan olarak `luna_cat`** olacaktır.

---

## 1. Sistemin Mantıksal ve Stratejik Değerlendirmesi

Önerilen sistemin demo sürümüne entegrasyonu son derece mantıklıdır:

*   **Premium İlk İzlenim (FTUE):** Oyuncuların oyunu ilk açtıklarında kendi ülkelerine ait bir görsel öğeyle (satır temizleme efekti) karşılaşmaları, oyuna karşı bir aidiyet ve premium hissiyat oluşturur.
*   **Boyut Maliyeti Yok:** Tüm ülke bayrağı varlıkları (assets) toplamda sadece **~155 KB** boyutundadır. Demo sürümünün paket boyutunu (build size) neredeyse hiç etkilemez.
*   **Güvenli Fallback Yapısı:** Steamworks API'sine erişilemediği veya kullanıcının ülkesine ait bir bayrak bulunamadığı durumlarda sistem sessizce varsayılan Gökkuşağı (`rainbow`) izine döner.

---

## 2. Karar Mekanizması Kontrol Sırası (Fallback Mantığı)

Oyun başlatıldığında izlenecek hiyerarşi şu şekildedir:

```mermaid
graph TD
    Start[Oyun Başlatıldı] --> CheckSteam{Steam Bağlantısı Aktif mi?}
    
    CheckSteam -- Evet --> CheckLang{GetCurrentGameLanguage dili sözlükte var mı?}
    CheckSteam -- Hayır --> FallbackLang{Oyun ayarlarındaki dil sözlükte var mı?}
    
    CheckLang -- Evet (Örn: german) --> UseLangFlag[O Dile Ait Bayrağı Seç (germany)]
    CheckLang -- Hayır/English --> CheckIP{GetIPCountry ülke kodu sözlükte var mı?}
    
    FallbackLang -- Evet (tr) --> UseLangFlag
    FallbackLang -- Hayır (en) --> RainbowFallback[Gökkuşağı İzi (rainbow)]
    
    CheckIP -- Evet (Örn: CA) --> UseIPFlag[O Ülkeye Ait Bayrağı Seç (canada)]
    CheckIP -- Hayır/Bulunamadı --> RainbowFallback
```

---

## 3. macOS Uyumluluk Analizi (Compatibility Review)

Tasarımın macOS işletim sisteminde ve PyInstaller ile paketlenmiş `.app` paketlerinde sorunsuz çalışması için şu noktalar incelenmiştir:

*   **Kütüphane Yükleme (ctypes):** macOS üzerinde Steamworks API'si `libsteam_api.dylib` dosyası üzerinden yüklenir. [steam_integration.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/steam_integration.py) modülü halihazırda `sys.platform == 'darwin'` koşuluna sahip olup, `.app` bundle içerisindeki `Contents/MacOS` veya `Frameworks` konumlarını doğru şekilde taramaktadır. ctypes fonksiyon imzaları Windows ile %100 uyumludur.
*   **Varlık Erişim Yolu (Asset Paths):** macOS uygulamasında dosya yolları dinamik olarak değişir. Modüldeki `_resource_path()` fonksiyonu, PyInstaller'ın `sys._MEIPASS` geçici klasörünü macOS bundle standartlarına uygun olarak çözümler.
*   **Numpy / Surfarray Bağımsızlığı:** macOS paket boyutunu küçük tutmak için macOS dağıtımlarında `numpy` ve `pygame.surfarray` kütüphaneleri dışarıda bırakılmıştır. Bu durum, bayrak görsellerinde şeffaflık (alpha) katmanı kullanıldığında macOS üzerinde bayrakların tamamen görünmez olmasına (alpha=0 olarak işlenmesine) yol açıyordu. Bu sorunu çözmek için taşınan `country_sweep_assets.py` modülündeki şu kurallar korunmuştur:
    1.  Bayraklar diskte düz RGB (SRCALPHA içermeyen) 24-bit biçiminde tutulur.
    2.  Ölçeklendirme sonrası `scaled.convert(24)` ve `set_alpha(None)` uygulanarak SDL blitter'ın piksel bazlı şeffaflık kontrolü bypass edilir.
    3.  Böylece macOS üzerinde numpy bağımlılığı olmadan %100 kararlı ve görünür bayrak çizimi sağlanır.

---

## 4. Entegrasyon Adımları ve Performans Optimizasyonları

### Adım 1: Varlıkların ve Tescil Modülünün Demo Sürümüne Taşınması

1.  **Varlıkların Kopyalanması:**
    *   Ana oyundaki `v2/assets/ui/line_sweep_countries/` klasörünün tamamını, demo sürümündeki `quadrix-demo/assets/ui/line_sweep_countries/` konumuna kopyalayın.
2.  **Tescil Modülünün Kopyalanması:**
    *   Ana oyundaki `v2/src/country_sweep_assets.py` dosyasını demo sürümündeki `quadrix-demo/src/country_sweep_assets.py` konumuna kopyalayın. Bu modül ülke-bayrak eşlemelerini, alias'ları ve dosya yükleme mantığını barındırır.

### Adım 2: Steamworks API Genişletmesi (`steam_integration.py`)

Steamworks flat C API'sinden `GetIPCountry` fonksiyonunu ctypes üzerinden çekmek için `steam_integration.py` dosyasına eklemeler yapılmalıdır.

#### 1. DLL/Dylib Fonksiyon Tanımlaması (`_setup_dll_functions` içerisine):
DLL/Dylib sürüm uyuşmazlığı riskini engellemek için `try-except` kontrolü uygulanır.
```python
# ISteamUtils_GetIPCountry — Oyuncunun IP adresine göre ülke kodunu döndürür
try:
    dll.SteamAPI_ISteamUtils_GetIPCountry.restype = ctypes.c_char_p
    dll.SteamAPI_ISteamUtils_GetIPCountry.argtypes = [ctypes.c_void_p]
except AttributeError:
    pass
```

#### 2. Python Wrapper Fonksiyonu:
Fonksiyon çağrısının güvenliğini artırmak için DLL/Dylib bünyesinde `SteamAPI_ISteamUtils_GetIPCountry` bulunup bulunmadığı `hasattr` ile denetlenir.
```python
def get_ip_country() -> str | None:
    """Steam client'ın IP adresine göre ülke kodunu döndürür (örneğin 'US', 'TR', 'DE')."""
    if not is_available() or not _isteam_utils or not _dll:
        return None
    if not hasattr(_dll, 'SteamAPI_ISteamUtils_GetIPCountry'):
        return None
    try:
        raw = _dll.SteamAPI_ISteamUtils_GetIPCountry(_isteam_utils)
        if raw:
            return raw.decode('utf-8', errors='replace').upper()
    except Exception as e:
        print(f"[Steam] GetIPCountry hatası: {e}")
    return None
```

### Adım 3: Animasyon Çizim Mantığı ve Çözümleme Güncellemesi (`sweep_effects.py`)

> [!TIP]
> **Performans Uyarısı ve Optimizasyon:**
> Dil ve IP tespiti işlemleri ctypes üzerinden harici dylib çağrıları yaptığı ve string çözümleme (decode) gerektirdiği için her karede (frame) tekrar çalıştırılması mikro stotter (anlık takılma) riskine yol açabilir. Oyuncunun dili veya IP adresi oturum boyunca **asla değişmeyeceği için** çözümlenen ülke izi ilk çağrıda **modül seviyesinde önbelleğe alınmalıdır (Caching)**.

#### 1. Sabit Sözlüklerin, Alias ve Önbellek Değişkeninin Tanımlanması:
```python
# Dil adına göre doğrudan eşleşen tekil bayraklar (İngilizce hariç)
LANGUAGE_TO_FLAG = {
    'turkish': 'turkiye',
    'german': 'germany',
    'french': 'france',
    'spanish': 'spain',
    'italian': 'italy',
    'brazilian': 'brazil',
    'portuguese': 'brazil',
    'russian': 'russia',
    'japanese': 'japan',
    'korean': 'south_korea',
    'schinese': 'china',
}

# 2 haneli ISO Ülke koduna göre bayrak eşleşmeleri (İngilizce diller için kurtarıcı)
COUNTRY_TO_FLAG = {
    'TR': 'turkiye',
    'US': 'usa',
    'GB': 'united_kingdom',
    'UK': 'united_kingdom',
    'CA': 'canada',
    'JP': 'japan',
    'RU': 'russia',
    'CN': 'china',
    'DE': 'germany',
    'FR': 'france',
    'ES': 'spain',
    'IT': 'italy',
    'BR': 'brazil',
    'KR': 'south_korea',
    'SG': 'singapore',
    'HK': 'hong_kong',
    'VN': 'vietnam',
}

# Modül import zamanında alias listesini genişletmek için:
_LINE_SWEEP_THEME_ALIASES.update(_country_theme_aliases())

# Performans için oturum boyu geçerli olan önbellek değişkeni
_cached_default_theme: str | None = None
```

#### 2. Önbellek Destekli Varsayılan İz Bulma Fonksiyonu (`get_default_line_sweep_theme`):
Dil tespiti için karmaşık JSON dosyaları okumak yerine, oyunun o anki aktif çeviri dilini tutan `localization.get_language()` fonksiyonunu doğrudan çağırarak $O(1)$ performansla karara varırız.
```python
def get_default_line_sweep_theme() -> str:
    """Steam dili ve IP konumunu kontrol ederek varsayılan izi çözer.

    İlk çağrıdan sonra sonucu önbellekten dönerek performans kaybını önler.
    """
    global _cached_default_theme
    if _cached_default_theme is not None:
        return _cached_default_theme

    resolved_theme = 'rainbow'
    import steam_integration
    
    # 1. Aşama: Steam Dil Kontrolü
    if steam_integration.is_available():
        steam_lang = steam_integration.get_current_game_language()
        if steam_lang:
            steam_lang = steam_lang.strip().lower()
            if steam_lang in LANGUAGE_TO_FLAG:
                resolved_theme = LANGUAGE_TO_FLAG[steam_lang]
                _cached_default_theme = resolved_theme
                return resolved_theme
                
    # 2. Aşama: Steam IP Ülkesi Kontrolü (Özellikle English kullananlar için)
    if steam_integration.is_available():
        country_code = steam_integration.get_ip_country()
        if country_code and country_code in COUNTRY_TO_FLAG:
            resolved_theme = COUNTRY_TO_FLAG[country_code]
            _cached_default_theme = resolved_theme
            return resolved_theme
            
    # 3. Aşama: Offline / Steam Dışı Fallback (Oyunun kendi dil ayarı)
    try:
        import localization
        game_lang = localization.get_language()
        if game_lang == 'tr':
            resolved_theme = 'turkiye'
    except Exception:
        pass

    _cached_default_theme = resolved_theme
    return resolved_theme
```

#### 3. Kuşanılmış İzi ve Hayvan Refakatçisini Çözme Fonksiyonlarının Güncellenmesi:
```python
def get_equipped_line_sweep_theme(user_manager=None, profile: dict | None = None) -> str:
    return get_default_line_sweep_theme()

def get_equipped_pet(user_manager=None, profile: dict | None = None) -> str:
    """Evcil hayvanı çözer. Demo sürümünde kozmetik pet takma kapalı olduğundan
    her zaman varsayılan olarak 'luna_cat' döndürür.
    """
    return 'luna_cat'
```

#### 4. Ana Oyundaki Kayar Bayrak Animasyonunun Çizilmesi (`draw_rainbow_cat_sweep`):
```python
def draw_rainbow_cat_sweep(
    screen: pygame.Surface,
    state: SweepCatState,
    board_rect: pygame.Rect,
    sweep_x: int,
    sweep_width: int,
    phase: int,
    board_width_cells: int,
    theme: str | None = None,
    stripe_highlight_enabled: bool = True,
    pet: str | None = None,
) -> None:
    """Rainbow + opsiyonel kedi/evcil hayvan sprite sweep efektini çiz."""
    sweep_height = max(1, int(board_rect.height))
    sweep_y = board_rect.y

    custom_target_w = max(sweep_width, int(sweep_height * 1.65))
    custom_cat = state.get_companion_surface(custom_target_w, sweep_height, phase, pet)
    one_col_w = max(1, int(round(board_rect.width / float(max(1, board_width_cells)))))

    if custom_cat is not None:
        cat_w = custom_cat.get_width()
        trail_x = sweep_x
        trail_width = sweep_width
    else:
        trail_x = sweep_x
        trail_width = sweep_width

    # Eğer theme None gelmişse (demo varsayılanı), aktif temayı dinamik olarak belirle
    if theme is None:
        theme = get_equipped_line_sweep_theme()

    # Eski 6 satırlı hardcoded gökkuşağı çizimi yerine, ana oyundaki gibi
    # dinamik bayrak şeritlerini kaydıran draw_line_sweep_band fonksiyonunu çağırıyoruz:
    band_rect = pygame.Rect(trail_x, sweep_y, trail_width, sweep_height)
    clip = band_rect.clip(board_rect)
    if clip.width > 0 and clip.height > 0:
        band_surface = pygame.Surface((band_rect.width, band_rect.height), pygame.SRCALPHA)
        draw_line_sweep_band(
            band_surface,
            band_surface.get_rect(),
            theme=theme,
            stripe_highlight_enabled=stripe_highlight_enabled,
            phase=phase,
        )
        src = pygame.Rect(clip.x - band_rect.x, clip.y - band_rect.y, clip.width, clip.height)
        screen.blit(band_surface, clip.topleft, src)

    if custom_cat is not None:
        custom_rect = custom_cat.get_rect()
        # ... (Kedi sprite blit mantığı aynen korunur) ...
```

---

## 5. Test ve Doğrulama Senaryoları

Sistemin kararlılığını doğrulamak için aşağıdaki test senaryoları uygulanmalıdır:

1.  **Senaryo A (Almanca Steam):**
    *   Steam dili `German` olarak ayarlanır. Oyun açılır. Satır temizlendiğinde doğrudan Almanya bayrağının gelmesi ve ucunda `luna_cat` sprite'ının yürümesi beklenir.
2.  **Senaryo B (İngilizce Dil, ABD IP'si):**
    *   Steam dili `English` ayarlanır. IP konumu `US` döner. ABD bayrağının gelmesi ve ucunda `luna_cat` sprite'ının yürümesi beklenir.
3.  **Senaryo C (Offline / Fallback):**
    *   Steam kapalı başlatılır. Fallback olarak Gökkuşağı (`rainbow`) izinin seçilmesi ve ucunda `luna_cat` sprite'ının yürümesi beklenir.
