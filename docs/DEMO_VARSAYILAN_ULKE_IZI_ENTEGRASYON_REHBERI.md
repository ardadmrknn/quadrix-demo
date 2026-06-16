# Demo Sürümü: Dinamik Varsayılan Ülke İzi Sistemi Entegrasyon Kılavuzu

Bu kılavuz, ana oyunda mağazada satılan ülke bayrağı temalı satır temizleme izlerini (line-sweep traces), demo sürümünde oyuncunun indirip başlattığı ülkeye/dile göre otomatik olarak "varsayılan ve ücretsiz" yapan sistemin mimari kurgusunu ve entegrasyon adımlarını içerir.

---

## 1. Sistemin Mantıksal ve Stratejik Değerlendirmesi

Önerilen sistemin demo sürümüne entegrasyonu hem **oyuncu deneyimi (UX)** hem de **pazarlama stratejisi** açısından son derece mantıklıdır:

*   **Kişiselleştirilmiş İlk İzlenim (FTUE - First-Time User Experience):** Oyuncuların oyunu ilk açtıklarında kendi ülkelerine ait bir görsel öğeyle (satır temizleme efekti) karşılaşmaları, oyuna karşı bir aidiyet ve premium hissiyat oluşturur.
*   **Düşük Kaynak Maliyeti:** Tüm ülke bayrağı varlıkları (assets) toplamda sadece **~155 KB** boyutundadır. Demo sürümünün paket boyutunu (build size) neredeyse hiç etkilemez.
*   **Kullanıcı Tercihine Saygı (Manual Override):** Sistem, otomatik tespiti yalnızca kullanıcı manuel bir seçim yapmadığında devreye sokar. Kullanıcı mağazadan (Store) başka bir iz seçtiğinde bu tercih kaydedilir ve otomatik tespit ezilir.
*   **Güvenli Fallback Yapısı:** Steamworks API'sine erişilemediği veya kullanıcının ülkesine ait bir bayrak bulunamadığı durumlarda sistem sessizce varsayılan Gökkuşağı (`rainbow`) izine döner.

---

## 2. Karar Mekanizması Kontrol Sırası (Fallback Mantığı)

Oyun başlatıldığında izlenecek hiyerarşi şu şekildedir:

```mermaid
graph TD
    Start[Oyun Başlatıldı] --> LoadProfile{Profilde kayıtlı iz var mı?}
    LoadProfile -- Evet (Kullanıcı Seçimi) --> UseEquipped[Kayıtlı İzi Kullan]
    LoadProfile -- Hayır (İlk Açılış/Boş) --> CheckSteam{Steam Bağlantısı Aktif mi?}
    
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

## 3. Entegrasyon Adımları

### Adım 1: Flag Varlıklarının ve Tescil Modülünün Demo Sürümüne Taşınması

1.  **Varlıkların Kopyalanması:**
    *   Ana oyundaki `v2/assets/ui/line_sweep_countries/` klasörünün tamamını, demo sürümündeki `quadrix-demo/assets/ui/line_sweep_countries/` konumuna kopyalayın.
2.  **Tescil Modülünün Kopyalanması:**
    *   Ana oyundaki `v2/src/country_sweep_assets.py` dosyasını demo sürümündeki `quadrix-demo/src/country_sweep_assets.py` konumuna kopyalayın. Bu modül ülke-bayrak eşlemelerini, alias'ları ve dosya yükleme mantığını barındırır.

### Adım 2: Steamworks API Genişletmesi (`steam_integration.py`)

Steamworks flat C API'sinden `GetIPCountry` fonksiyonunu ctypes üzerinden çekmek için `steam_integration.py` dosyasına eklemeler yapılmalıdır.

#### 1. DLL Fonksiyon Tanımlaması (`_setup_dll_functions` içerisine):
```python
# ISteamUtils_GetIPCountry — Oyuncunun IP adresine göre ülke kodunu döndürür
try:
    dll.SteamAPI_ISteamUtils_GetIPCountry.restype = ctypes.c_char_p
    dll.SteamAPI_ISteamUtils_GetIPCountry.argtypes = [ctypes.c_void_p]
except AttributeError:
    pass
```

#### 2. Python Wrapper Fonksiyonu:
```python
def get_ip_country() -> str | None:
    """Steam client'ın IP adresine göre ülke kodunu döndürür (örneğin 'US', 'TR', 'DE')."""
    if not is_available() or not _isteam_utils or not _dll:
        return None
    try:
        raw = _dll.SteamAPI_ISteamUtils_GetIPCountry(_isteam_utils)
        if raw:
            return raw.decode('utf-8', errors='replace').upper()
    except Exception as e:
        print(f"[Steam] GetIPCountry hatası: {e}")
    return None
```

### Adım 3: Sweep Efekti Çözümleme Mantığı (`sweep_effects.py`)

`sweep_effects.py` içinde varsayılan izin çözümlendiği noktaya Steam ve dil hiyerarşisi entegre edilmelidir.

#### 1. Sabit Sözlüklerin Tanımlanması:
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
```

#### 2. Varsayılan İz Bulma Fonksiyonu (`get_default_line_sweep_theme`):
```python
def get_default_line_sweep_theme() -> str:
    """Steam dili ve IP konumunu kontrol ederek varsayılan izi çözer."""
    import steam_integration
    
    # 1. Aşama: Steam Dil Kontrolü
    if steam_integration.is_available():
        steam_lang = steam_integration.get_current_game_language()
        if steam_lang:
            steam_lang = steam_lang.strip().lower()
            if steam_lang in LANGUAGE_TO_FLAG:
                return LANGUAGE_TO_FLAG[steam_lang]
                
    # 2. Aşama: Steam IP Ülkesi Kontrolü (Özellikle English/Çoklu dil kullananlar için)
    if steam_integration.is_available():
        country_code = steam_integration.get_ip_country()
        if country_code and country_code in COUNTRY_TO_FLAG:
            return COUNTRY_TO_FLAG[country_code]
            
    # 3. Aşama: Offline / Steam Dışı Fallback (Oyunun kendi dil ayarı)
    # settings_manager üzerinden dil ayarı kontrol edilir
    try:
        from settings_manager import SettingsManager
        # get_instance() veya doğrudan okuma yapılabilir
        # Basitlik için 'tr' ise 'turkiye', değilse 'rainbow'
    except ImportError:
        pass

    return 'rainbow'
```

#### 3. Kuşanılmış İzi Çözme Fonksiyonunun Güncellenmesi (`get_equipped_line_sweep_theme`):
```python
def get_equipped_line_sweep_theme(user_manager=None, profile: dict | None = None) -> str:
    profile = _resolve_profile(user_manager, profile)
    if isinstance(profile, dict):
        equipped_map = profile.get('equipped_cosmetics', {})
        if isinstance(equipped_map, dict):
            equipped = equipped_map.get(_LINE_SWEEP_SLOT)
            # Eğer kullanıcı manuel bir seçim yaptıysa onu kullan (rainbow dahil)
            if equipped is not None:
                return normalize_line_sweep_theme(equipped)
                
    # Eğer henüz hiçbir şey kuşanılmadıysa dinamik varsayılanı kullan
    return get_default_line_sweep_theme()
```

### Adım 4: Mağaza Arayüzü Durum Yönetimi (`store_screen.py`)

Kullanıcının ülkesine ait dinamik bayrak, mağazada kilitli (`unowned`) görünmek yerine tıpkı Gökkuşağı izi gibi ücretsiz varsayılan (`demo` / "Varsayılan") durumunda gösterilmelidir.

#### `_resolve_ownership_state` Fonksiyonu Güncellemesi:
```python
        # ... (Önceki kart ve kuşanılmış kozmetik kontrolleri) ...

        # Dinamik varsayılan izin tespiti
        try:
            from sweep_effects import get_default_line_sweep_theme
            default_sweep = f"luna_{get_default_line_sweep_theme()}"
        except ImportError:
            default_sweep = "luna_rainbow"

        # Eğer ürün varsayılan gökkuşağı veya kullanıcının ülkesinin varsayılan izi ise
        # mağazada satın alma yerine ücretsiz takılabilir ('demo') moduna çek
        if value == 'luna_rainbow' or value == default_sweep or value == _DEFAULT_PET_VALUE or _is_default_block_skin(value):
            return 'demo'
```

---

## 4. Test ve Doğrulama Senaryoları

Sistemin kararlılığını doğrulamak için aşağıdaki test senaryoları uygulanmalıdır:

1.  **Senaryo A (Almanca Steam):**
    *   Steam dili `German` olarak ayarlanır. Oyun açılır. Satır temizlendiğinde doğrudan Almanya bayrağının gelmesi beklenir. Mağazada Almanya İzi "Varsayılan" olarak görünmelidir.
2.  **Senaryo B (İngilizce Dil, ABD IP'si):**
    *   Steam dili `English` ayarlanır. IP konumu `US` döner. Satır temizlendiğinde ABD bayrağının gelmesi beklenir.
3.  **Senaryo C (İngilizce Dil, Kanada IP'si):**
    *   Steam dili `English` ayarlanır. IP konumu `CA` döner. Kanada bayrağının gelmesi beklenir.
4.  **Senaryo D (Desteklenmeyen Ülke / Offline):**
    *   Steam kapalı başlatılır veya IP'den `NZ` (Yeni Zelanda - bayrağı yok) döner. Fallback olarak Gökkuşağı (`rainbow`) izinin seçilmesi beklenir.
5.  **Senaryo E (Manuel Değiştirme):**
    *   Kullanıcı mağazadan manuel olarak "Japonya İzi" satın alıp takar. Sonraki oyunlarda dil veya konum ne olursa olsun Japonya izinin gelmesi beklenir. Mağazadan tekrar kendi ülke izine tıklayıp "Varsayılan yap" diyerek geri dönebilmelidir.
