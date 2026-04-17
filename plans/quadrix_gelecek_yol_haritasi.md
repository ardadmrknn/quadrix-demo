# Quadrix — Gelecek Yol Haritası & İyileştirme Planı

> **Tarih:** 28 Şubat 2026  
> **Mevcut Sürüm:** v1.0.21 (Build 22)  
> **Motor:** pygame-ce 2.5.7 + SDL 2.32.10  
> **Diller:** 11 (TR, EN, DE, FR, ES, IT, PT, RU, JA, ZH, KO)  
> **Mod Sayısı:** 11+ (Classic, Sprint, Ultra, Zen, Hardcore, Survival, Cascade, Daily, Tetris2, Mystery, Wide, PvP, Campaign, Tutorial)

---

## 🔴 Kritik Öncelik

### 1. Online Multiplayer & Co-op
Menüde "Online & Co-op coming soon" metni gösteriliyor ama ortada hiç ağ kodu yok.

**Yapılacaklar:**
- WebSocket veya UDP tabanlı ağ katmanı seçimi ve implementasyonu
- Matchmaking sistemi (lobby, eşleştirme, bekleme odası)
- Lag compensation / input prediction (netcode)
- Turnuva / ranked modu altyapısı
- Oyuncu bağlantı kopması yönetimi (reconnect, timeout)
- Anti-cheat mekanizması (seed doğrulama, input replay)
- Steam Networking (Steamworks ISteamNetworking veya GameNetworkingSockets) entegrasyonu
- Co-op modu tasarımı (ortak board? Garbage paylaşımı? daha sonra detaylandırılabilir)

**Teknik notlar:**
- Mevcut `PvPGame` lokal split-screen mantığını ağ üzerinden soyutlamak mümkün
- Steam relay server'ları kullanılabilir (NAT traversal gerektirmez)
- Deterministik simülasyon (aynı seed + aynı input = aynı sonuç) ile bant genişliği minimumda tutulabilir

---

### 2. HiDPI / Retina Desteği (SDL3 Bekleniyor)
Software renderer ile Retina ekranlar 1x çözünürlükte render ediliyor. Kod altyapısı hazır (`get_display_scale_factor()`, `normalize_mouse_pos()`) ama çalışmıyor.

**Seçenekler:**
- **Kısa vade:** pygame-ce `Renderer` + `Texture` API'ye geçiş (GPU hızlandırmalı) — büyük refactor
- **Orta vade:** pygame-ce 3.0 + SDL3 çıkışını bekle — native HiDPI gelecek
- **Geçici çözüm:** Yüksek çözünürlüklü asset'ler + yazılım ölçekleme (2x render → downsample)

**Beklenen zaman:** pygame-ce 3.0 (SDL3 port) — 2026 sonu / 2027 başı tahmini

---

### 3. Localization Dosyası Refactoru
`localization.py` **18.467 satır** — tek dosyada 11 dil. Bakımı, merge conflict'leri ve yükleme süresi sorunlu.

**Yapılacaklar:**
- Her dili ayrı JSON/YAML dosyasına taşı (`lang/tr.json`, `lang/en.json`...)
- `t()` fonksiyonunu dosya tabanlı lazy loading yapacak şekilde güncelle
- Çeviri anahtarı eksik tespiti için CI tool'u yaz
- Crowdin / Weblate gibi çeviri platformu entegrasyonu

---

### 4. 9 Dil Çeviri Tamamlama
Yalnızca TR ve EN tam. Kalan 9 dil `complete: False` işaretli.

| Dil | Durum | Not |
|-----|-------|-----|
| DE (Almanca) | ❌ Eksik | |
| FR (Fransızca) | ❌ Eksik | |
| ES (İspanyolca) | ❌ Eksik | |
| IT (İtalyanca) | ❌ Eksik | |
| PT (Portekizce) | ❌ Eksik | |
| RU (Rusça) | 🔶 Kısmen | Plan mevcut (plans/ altında) |
| JA (Japonca) | ❌ Eksik | CJK font desteği mevcut |
| ZH (Çince) | ❌ Eksik | CJK font desteği mevcut |
| KO (Korece) | ❌ Eksik | CJK font desteği mevcut |

**Öneri:** Profesyonel çeviri servisi veya topluluk çevirisi (Crowdin)

---

## 🟡 Orta Öncelik

### 5. Kod Refactoru — Büyük Dosyaların Bölünmesi

| Dosya | Satır | Sorun |
|-------|-------|-------|
| `localization.py` | 18.467 | Dil verisini ayrı dosyalara taşı |
| `game_modes_extra.py` | 9.353 | Tetris2, Mystery, Wide → ayrı dosyalar |
| `game.py` | 5.168 | Rendering mantığını game_renderer.py'ye çıkar |
| `pvp_game.py` | 3.608 | Ağ katmanı eklendiğinde yeniden yapılanacak |
| `settings_screen_tabbed.py` | 2.662 | Her sekmeyi ayrı modüle çıkmak mümkün |

**Hedef:** Hiçbir kaynak dosya 2.000 satırı geçmesin

---

### 6. ~~CI/CD Pipeline~~ ✅ TAMAMLANDI (1 Mart 2026)
Şu an otomatik test veya build pipeline'ı yok.

**Yapılanlar:**
- ~~GitHub Actions ile otomatik `pytest` çalıştırma (push/PR tetikli)~~ → `.github/workflows/ci.yml` oluşturuldu
- ~~macOS / Windows / Linux matris build~~ → ubuntu-latest, macos-latest, windows-latest matris
- PyInstaller ile otomatik .app / .exe derleme — henüz eklenmedi (release otomasyonuyla yapılacak)
- Test coverage raporlama — henüz eklenmedi
- ~~Linting (flake8 / ruff)~~ → ruff lint job eklendi
- Release otomasyonu (tag → build → upload) — henüz eklenmedi

---

### 7. Kademeli Eğitim Sistemi
Mevcut tutorial tek bir temel akış. GOREV_LISTESI.md'de planlanmış ama bekliyor.

**Yapılacaklar:**
- **Temel:** Taşı, döndür, yerleştir, satır sil (mevcut)
- **Orta:** T-spin, wall kick, combo zinciri, hold stratejisi
- **İleri:** Downstack, opener kalıpları (TKI, DT Cannon), garbage yönetimi
- Interaktif görev bazlı eğitim (belirli durumu çöz)
- Video/animasyon destekli açıklamalar

---

### 8. Bölüm Öncesi Koşul Anlatımı (Kampanya)
GOREV_LISTESI.md'de bekleyen madde. Boss/mini-boss seviyeler öncesi oyuncuya koşullar görsel olarak açıklanmıyor.

**Yapılacaklar:**
- Combo, zincir, T-spin gibi mekaniklerin kısa animasyonlu açıklaması
- Bölüm giriş ekranında hedef/kısıtlama özeti
- İpucu sistemi (ilk 2-3 denemede otomatik ipucu)

---

### 9. ~~Mod Bazlı Başarımlar~~ ✅ TAMAMLANDI (1 Mart 2026)
Mevcut ~28 başarımın çoğu genel. Modlara özel başarımlar eksik.

**Eklenen başarımlar (11 yeni):**
- ~~**Survival:** 5 dk hayatta kal~~ → `survival_5min` eklendi
- ~~**Cascade:** 10x+ zincir combo~~ → `cascade_chain_10` eklendi
- ~~**Sprint:** 40 satır < 60 sn, < 45 sn~~ → `sprint_sub60`, `sprint_sub45` eklendi
- ~~**Ultra:** 50K+, 100K+ skor~~ → `ultra_50k`, `ultra_100k` eklendi
- ~~**Hardcore:** 10 level~~ → `hardcore_lvl10` eklendi
- ~~**Wide:** 200 satır tek oyunda~~ → `wide_200_lines` eklendi
- **Mystery:** Tüm kartları topla, nadir kart aç — henüz eklenmedi (Mystery kartları runtime verisi gerektirir)
- **Daily Challenge:** 7 gün üst üste oyna, 30 gün streak — henüz eklenmedi (streak takibi gerekli)

**Teknik:** `update_stats()` fonksiyonuna `game_mode` parametresi eklendi; mod-spesifik istatistikler (sprint_best_time, ultra_max_score vb.) otomatik takip ediliyor.

---

### 10. ~~Steam Achievements Senkronizasyonu~~ ✅ TAMAMLANDI (1 Mart 2026)
Oyun içi `achievements.py` ile Steam Achievement API'nin senkronizasyonu net değil.

**Yapılanlar:**
- ~~Her oyun içi başarım → Steam Achievement ID eşlemesi~~ → `STEAM_ACHIEVEMENT_MAP` dict'i eklendi
- ~~Unlock anında `ISteamUserStats::SetAchievement()` + `StoreStats()` çağrısı~~ → `unlock()` içinde otomatik çağrı
- Steam overlay'de başarım popup'ı (Steam SDK native olarak hallediyor, ek kod gerekmez)
- ~~Mevcut başarımların geriye dönük senkronizasyonu~~ → `sync_to_steam()` + `sync_all_achievements()` fonksiyonları eklendi
- `steam_integration.py`'ye `SetAchievement`, `GetAchievement`, `StoreStats` ctypes binding'leri eklendi
- 10 test yazıldı (`test_steam_achievements_sync.py`), hepsi geçiyor

---

### 11. Performans Optimizasyonları

**Yapılacaklar:**
- **Dirty rect rendering:** Sadece değişen board bölgelerini yeniden çiz
- **`Surface.fblits()`:** pygame-ce'de toplu blit (tek çağrıda birden fazla surface)
- **FPS profiler:** Oyun içi FPS/frame time overlay (debug modu)
- **Board render cache:** Statik blokları bir surface'e cache'le, sadece hareket eden parçayı üstten çiz
- **Sprite group optimizasyonu:** Arka plan efektleri için `pygame.sprite.LayeredDirty`
- **Memory profiling:** Büyük cache'lerin (text 512, UI 128, jelly cell) boyut izleme

---

### 12. Accessibility (Erişilebilirlik)
Hiçbir erişilebilirlik özelliği mevcut değil.

**Yapılacaklar:**
- Yüksek kontrast modu (renk körü dostu palet)
- Blok şekillerine desen/sembol ekleme (renk + şekil ile ayırt etme)
- Ekran okuyucu (screen reader) desteği — en azından menülerde
- Özelleştirilebilir font boyutu
- Tek elle oynanabilir kontrol şeması
- Ses ile görsel ipucu eşleme (sağır oyuncular için titreşim/flash)
- Oyun hızı ayarı (yavaşlatma seçeneği)

---

## ⚪ Düşük Öncelik / Gelecek Vizyonu

### 13. Mobil Platform Desteği (iOS / Android)
Şu an sadece desktop (Windows, macOS, Linux). Mobil sürüm yok.

**Seçenekler:**
- **pygame-ce + Briefcase/BeeWare** — Python mobil paketleme (deneysel)
- **Kivy / KivyMD** — Alternatif Python mobil framework (tam yeniden yazım)
- **Flutter / Unity** — Performans için native rewrite
- **Web sürümü (Pygbag / Emscripten)** — Tarayıcıda çalışan pygame (sınırlı)

**Gerçekçi değerlendirme:** pygame tabanlı mobil port zor. En olası yol web sürümü (Pygbag) veya ayrı bir mobil proje.

---

### 14. Web Sürümü
Pygbag ile pygame oyunlarını WebAssembly'ye derlemek mümkün.

**Avantajlar:**
- İndirme gerektirmez
- Bağlantı paylaşarak hemen oyna
- Steam Deck tarayıcısında çalışabilir

**Yapılacaklar:**
- Pygbag uyumluluğu testi
- Async game loop adaptasyonu (`asyncio.sleep()`)
- Dosya I/O → IndexedDB adaptasyonu (kayıt/yükleme)
- Ses: Web Audio API uyumluluğu
- Steam entegrasyonu web'de çalışmaz — ayrı skor sistemi gerekir

---

### 15. Replay / Tekrar İzleme Sistemi
Oyun tekrarı kaydet ve izle özelliği.

**Yapılacaklar:**
- Input recording (her frame'deki tuş girişleri + timing)
- Deterministik replay (aynı seed + aynı input = aynı oyun)
- Replay dosyası formatı (.qrp)
- Replay paylaşımı (dosya veya link)
- Replay üzerinde ileri/geri sarma
- "Highlight" anlarını otomatik tespit (Tetris, T-spin, büyük combo)

---

### 16. Oyun İçi İstatistik Paneli
Detaylı oyuncu istatistikleri.

**Yapılacaklar:**
- Toplam oynama süresi
- Mod bazlı detaylı istatistikler (en iyi skor, ortalama, oynama sayısı)
- Parça kullanım dağılımı (en çok hangi tetromino düşürüldü)
- Satır temizleme dağılımı (single/double/triple/tetris yüzdeleri)
- APM (Actions Per Minute) / PPD (Pieces Per Second) metrikleri
- Zaman bazlı grafik (son 7 gün, 30 gün trend)
- Kişisel rekor geçmişi

---

### 17. Tema Mağazası / Özelleştirme Genişletme
Mevcut tema sistemi var ama sınırlı.

**Yapılacaklar:**
- Kullanıcı yapımı tema desteği (JSON tabanlı tema dosyası)
- Blok skin editörü (Piece Workshop genişletme)
- Board arka plan görseli seçimi
- Parçacık efekti seçenekleri (satır silme animasyonu)
- Ses paketi değiştirme (farklı efekt setleri)
- Tema paylaşımı (Steam Workshop entegrasyonu?)

---

### 18. Günlük Görevler / Battle Pass Sistemi
Oyuncuyu düzenli oynamaya teşvik eden sistemler.

**Yapılacaklar:**
- Günlük 3 görev (örn: "Sprint modunda 40 satır bitir", "5 Tetris yap")
- Haftalık zorluk görevleri
- XP / seviye sistemi (oyuncu profili)
- Sezon bazlı ödüller (tema, avatar, başlık)
- Streak bonus (üst üste gün oynama ödülü)

---

### 19. Puzzle / Challenge Modu
Önceden hazırlanmış board durumlarından çözüm bul.

**Yapılacaklar:**
- Editör: Board durumu + hedef belirle
- 100+ önceden hazırlanmış puzzle
- Zorluk seviyeleri (kolay → imkansız)
- Topluluk puzzle paylaşımı
- Speedrun: en hızlı çözme süresi

---

### 20. Yapay Zeka (AI) Rakibi
PvP modunda bilgisayar rakibi.

**Yapılacaklar:**
- Temel AI: Basit scoring heuristic (yükseklik, boşluk, tamamlanan satır)
- Orta AI: El Tetris / Pierre Dellacherie algoritması
- İleri AI: MCTS (Monte Carlo Tree Search) veya minimax
- Zorluk ayarı (input gecikmesi, karar kalitesi)
- Farklı "kişilikler" (agresif, defansif, hızlı, stratejik)

---

### 21. Workshop / Mod Desteği
Kullanıcıların kendi modlarını oluşturması.

**Yapılacaklar:**
- Lua veya Python script tabanlı mod API
- Özel blok şekilleri tanımlama (mevcut Piece Workshop genişletme)
- Özel oyun kuralları (gravity, scoring, board boyutu)
- Steam Workshop entegrasyonu (mod yükleme / paylaşma)
- Mod sandbox (güvenlik: dosya sistemi erişim kısıtlaması)

---

### 22. Linux Paketleme
macOS ve Windows için build script'leri var, Linux için yok.

**Yapılacaklar:**
- AppImage build script'i
- Flatpak manifest dosyası
- Snap paketi
- .deb / .rpm paketleme
- Steam Linux depot hazırlığı

---

### 23. Ses Sistemi İyileştirmeleri
**Yapılacaklar:**
- Önceden kaydedilmiş SFX dosyaları (prosedürel yerine profesyonel)
- Ses efekti katmanlama (aynı anda birden fazla efekt)
- Adaptive müzik (oyun hızına göre tempo değişimi)
- Müzik: BPM senkronizasyonu (blok düşüşünü ritme eşle)
- 3D spatial audio (PvP modunda sol/sağ oyuncu sesleri)

---

### 24. RTL (Sağdan Sola) Dil Desteği
Metadata'da `rtl: False` alanı var ama hiç RTL dil tanımlı değil.

**Yapılacaklar:**
- Arapça (AR), İbranice (HE) dil desteği
- UI layout mirror (menüler, panel düzeni sağdan sola)
- Metin yönü: RTL text rendering
- Sayılar: Arapça rakamlar opsiyonel

---

### 25. Güvenlik & Anti-Cheat
**Yapılacaklar:**
- Skor doğrulama (client-side skor manipülasyonunu engelle)
- Input hash / game state checksum
- Steam leaderboard'a gönderilen skorlarda replay data ekleme
- Replay doğrulaması (sunucu tarafında)

---

## 🔧 Teknik Borç & Bakım

### 26. Test Coverage Artırma — 🔶 KISMEN TAMAMLANDI (1 Mart 2026)
- Mevcut: ~135 test geçiyor (önceki: ~121), birçoğu mock tabanlı
- ~~Test ordering sorunları var (izole geçen testler toplu çalışınca başarısız)~~ → 14 test düzeltildi (pygame stub kirlenmesi, constants stub, _PARTNER_API_KEY eksikliği)
- Kalan 5 başarısız test: derin cross-module pygame state kirlenmesi (pytest-forked veya subprocess izolasyonu gerekli)
- Integration test eksik (gerçek pygame init ile)
- Campaign modu testleri sınırlı
- PvP modu testleri yok

### 27. Type Hints & Dokümantasyon
- Kod büyük oranda type hint'siz
- Docstring'ler Türkçe (uluslararası katkı zorlaşır)
- API dokümantasyonu yok
- Modül bağımlılık diyagramı yok

### 28. ~~Bağımlılık Yönetimi~~ ✅ TAMAMLANDI (1 Mart 2026)
- ~~`requirements.txt` 186 satır — birçoğu geliştirme bağımlılığı~~ → `pyproject.toml` oluşturuldu
- ~~Runtime vs dev dependency ayrımı yok~~ → `[project.dependencies]` (runtime: pygame-ce, numpy, Pillow) + `[project.optional-dependencies]` dev/build/macos ayrımı yapıldı
- ~~`pyproject.toml` veya `setup.cfg` kullanımına geçiş düşünülebilir~~ → `pyproject.toml` ile modern Python packaging
- pytest ve ruff konfigürasyonu da `pyproject.toml`'a taşındı (`[tool.pytest.ini_options]`, `[tool.ruff]`)

---

## 📅 Önerilen Uygulama Sırası

### Faz 1 — Stabilizasyon (1-2 hafta)
1. ~~pygame-ce geçişi~~ ✅ TAMAMLANDI
2. Bekleyen 2 görev (kademeli eğitim + bölüm koşul anlatımı)
3. ~~Test ordering sorunlarını düzelt~~ ✅ KISMEN TAMAMLANDI (14 test düzeltildi)
4. ~~CI/CD pipeline kur~~ ✅ TAMAMLANDI

### Faz 2 — İçerik & Kalite (2-4 hafta)
5. 9 dil çevirilerini tamamla
6. localization.py'yi dosya bazlı sisteme refactor et
7. ~~Mod bazlı başarımlar ekle~~ ✅ TAMAMLANDI
8. ~~Steam Achievements senkronizasyonu~~ ✅ TAMAMLANDI
9. Performans optimizasyonları (dirty rect, fblits)

### Faz 3 — Büyük Özellikler (1-3 ay)
10. Online Multiplayer altyapısı
11. Replay sistemi
12. AI rakibi
13. Puzzle modu
14. İstatistik paneli

### Faz 4 — Platform Genişleme (3-6 ay)
15. Web sürümü (Pygbag)
16. Linux paketleme
17. Erişilebilirlik
18. RTL dili desteği

### Faz 5 — Ekosistem (6+ ay)
19. Tema mağazası & Workshop
20. Günlük görevler / Battle Pass
21. Mobil port araştırma
22. HiDPI (pygame-ce 3.0 + SDL3 geldiğinde)

---

> **Not:** Bu belge yaşayan bir döküman olarak güncellenmelidir. Her tamamlanan madde üzerini çizilerek işaretlenebilir.
