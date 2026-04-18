# Plan: Ayarlar > Mod Muzikleri Detayli Uygulama Plani

**Created:** 2026-04-18
**Status:** In Progress (Adim 5 tamamlandi)

## 1) Hedef

Bu planin amaci, Ayarlar > Mod Muzikleri ekranini su ozelliklerle guclendirmektir:

- Mod bazli playlist yonetimini daha anlasilir hale getirmek
- Varsayilan (inherit) ve ozel liste ayrimini acik gostermek
- Modlara gore hizli toplu islemler eklemek
- Muzik playback tarafinda geriye donuk uyumlulugu bozmamak

## 2) Kod Tabaninda Dogrulanan Mevcut Durum

### 2.1 Ayar Veri Katmani

- `settings_manager.py` zaten playlist temelli yapiya sahip:
  - `mode_music_playlists`
  - `get_mode_music_playlist(mode_key)`
  - `get_music_playlist_for_mode(mode_key)` fallback akisi
- Playlist bos ise varsayilan fallback devreye giriyor.

### 2.2 UI Katmani

- `settings_screen_tabbed.py` icinde `music_selector` satirlari var.
- Mod playlist editoru aciliyor:
  - `open_mode_playlist_editor(mode_key)`
  - `edit_mode_playlist:<mode_key>` action akisi
- Kampanya icin world/faz secici overlay mevcut.

### 2.3 Main Loop Integrasyonu

- `main.py` ayarlar ekranindan gelen action'lari isliyor.
- `mode_playlist_changed` action'i tanimli (sessiz gecis).

### 2.4 Ses Motoru

- `sound.py` playlist ve shuffle destekli:
  - `set_music_playlist(..., shuffle=False)`
  - `update_music_playlist()`
- Oyun ici mode playlist secimi `settings_manager` fallback zinciri ile calisiyor.

## 3) Mimari Kararlar (Netlestirildi)

1. Mevcut `mode_music_playlists` yapisi korunacak.
2. "Varsayilan" durumu explicit yeni bir key ile degil, mevcut davranisla temsil edilecek:

- mode key icin playlist yoksa -> varsayilan
- playlist varsa -> ozel

3. Ilk fazda agirlikli shuffle eklenmeyecek (risk azaltma).
4. UI degisiklikleri `settings_screen_tabbed.py` icinde yapilacak; `menu.py` tarafinda sadece gerekirse ortak helper genisletilecek.

## 4) Fazlar ve Adimlar

## Faz A - UX Iskeleti ve Durum Rozetleri

**Dosyalar:**

- `src/settings_screen_tabbed.py`
- (gerekirse) `src/localization.py`

**Yapilacaklar:**

1. Mod satirlarinda durum metnini standartlastir:

- `Varsayilan` (playlist yok)
- `<N> parca` (playlist var)

2. Kampanya satirinda mevcut `configured/5 faz` bilgisini koru, gorunurlugu artir.
3. Secili satir vurgusunu biraz guclendir (border/alpha), okunurlugu arttir.

**Cikis Kriteri:**

- Tum mod satirlari tutarli bir durum formatiyla gorunur.
- Kampanya satiri digerlerinden ayri ama ayni dilde bilgi verir.

**Dogrulama:**

- Oyun ici manuel kontrol: Ayarlar > Mod Muzikleri

---

## Faz B - Toplu Islem Butonlari (MVP)

**Dosyalar:**

- `src/settings_screen_tabbed.py`
- `src/settings_manager.py`
- (gerekirse) `src/localization.py`

**Yapilacaklar:**

1. Playlist editor overlay icine 3 hizli aksiyon ekle:

- Tumunu sec (track picker tarafinda)
- Temizle (playlist'i bosalt -> varsayilan)
- Varsayilana don (Temizle ile ayni semantic)

2. Kampanya faz editorunde secili faz playlisti icin ayni aksiyonlari destekle.
3. Geriye donuk uyumluluk: eski settings dosyalarinda hicbir migration gerektirmesin.

**Cikis Kriteri:**

- Oyuncu 2-3 tus ile playlist olusturup sifirlayabilir.
- Bos playlist her yerde varsayilan fallback'e duser.

**Dogrulama:**

- Manuel: mod sec, playlist ekle/sil, oyuna gir ve muzik davranisini gozle.

---

## Faz C - Onizleme ve Guvenli Uygulama

**Dosyalar:**

- `src/settings_screen_tabbed.py`
- `src/main.py` (gerekiyorsa sadece action tetigi)
- `src/sound.py` (gerekiyorsa mini helper)

**Yapilacaklar:**

1. Playlist editorunde "Onizleme" aksiyonu ekle:

- Secili parcayi kisa oynat (aynı track yeniden secilirse restart etme)

2. Onizleme sadece ayarlar ekranindayken aktif olsun.
3. Overlay kapanisinda menu playlist akisinin bozulmamasi garanti edilsin.

**Cikis Kriteri:**

- Kullanici secmeden once parcayi duyabilir.
- Menu muzigi/oyun muzigi gecislerinde stale state olmaz.

**Dogrulama:**

- Ayarlar ekraninda 5-10 kez hizli ac-kapa + onizleme testi.

---

## Faz D - Test Paketi

**Dosyalar:**

- `tests/test_mode_music_settings.py` (yeni)
- `tests/test_settings_manager_mode_playlist_fallback.py` (yeni veya mevcuta ek)

**Yapilacaklar:**

1. `SettingsManager` fallback testleri:

- playlist yok -> default playlist
- playlist var -> o playlist

2. playlist normalize testleri:

- bos/invalid item temizligi

3. campaign world fallback testleri:

- world playlist yoksa campaign playlist'e dusus

**Cikis Kriteri:**

- Kritik fallback davranislari testle korunur.

**Dogrulama:**

- VS Code task: `pytest (py3.12)`

---

## Faz E - Polish ve Lokalizasyon Tamamlama

**Dosyalar:**

- `src/localization.py`
- `src/settings_screen_tabbed.py`

**Yapilacaklar:**

1. Yeni UI metinlerini tum destekli dillere en az fallback ile ekle.
2. Rozet/etiket metinlerini kisalt (dar ekran okunurlugu).
3. Scrollbar ve hitbox metriklerini mevcut responsive helper ile ayni kaynaktan uret.

**Cikis Kriteri:**

- 1366x768 ve 1920x1080'de tasma olmadan okunur UI.

**Dogrulama:**

- Manuel cozumunurluk testi + temel navigation testi.

## 5) Riskler ve Koruma Stratejisi

1. Risk: UI scaling bozulmasi

- Koruma: mevcut responsive metrik helper disina cikmamak

2. Risk: playlist degisikliginden sonra yanlis muzik devam etmesi

- Koruma: action handlingi yalin tut, sadece gerekli yerde force refresh

3. Risk: kampanya world fallback regressioni

- Koruma: SettingsManager unit testleri

## 6) Adim Adim Ilerleme Kaydi

- [x] Adim 1: Mevcut kod akisinin audit'i tamamlandi.
- [x] Adim 2: Detayli faz plani yazildi.
- [x] Adim 3: Faz A / Part 1 tamamlandi (music_selector durum metinleri standartlastirildi).
- [x] Adim 4: Faz A / Part 2 tamamlandi (secili satir vurgusu guclendirildi).
- [x] Adim 5: Faz B / Part 1 tamamlandi (Tumunu Sec + Temizle + Varsayilana Don eklendi).
- [ ] Adim 6: Faz C implementasyonu (onizleme).
- [ ] Adim 7: Faz D testleri.
- [ ] Adim 8: Faz E polish ve lokalizasyon.

## 7) Sonraki Somut Adim

Sonraki kod degisikligi Faz C olacak:

- `settings_screen_tabbed.py` icinde secili parcayi onizleme aksiyonu eklenecek.
- Overlay kapanisinda menu muzik akisi bozulmadan kaldigi dogrulanacak.
