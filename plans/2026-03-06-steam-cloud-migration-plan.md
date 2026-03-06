# Steam Cloud Gecis Plani

## Hedef

Steam ile acilan oyunda profil/veri kayitlarini tek makinede lokal tutmak yerine ayni Steam hesabi altinda cihazlar arasi tasinabilir hale getirmek.

Bu planin ana hedefi su iki noktayi ayni anda cozmektir:

1. Steam kullanicisinin profili ve ona bagli ilerleme verileri Steam Cloud ile tasinsin.
2. Mevcut lokal mimaride cihaz-ozel ayarlar ile hesap/progres verileri birbirine karismasin.

Onemli sinir: Steam Cloud uygulama dosyalarini Steam hesabina bagli olarak senkronize eder. Bu yuzden "diger hesaplar" da senkronize olabilir, ama bu sadece ayni Steam hesabinin Cloud alanindaki lokal oyun profilleri icin gecerli olur. Farkli Steam hesaplari birbirinin Cloud verisini goremez.

## Mevcut Durum

Su an kalici veri buyuk oranda ortak uygulama veri klasorune yaziliyor:

- `users.json`
- `settings.json`
- `achievements_<username>.json`
- `highscores_<username>.json`

Bu dosyalarin yolu `src/data_paths.py` uzerinden cozuluyor.

Ancak iki kritik sorun var:

1. Avatar PNG dosyalari halen dogrudan `avatars/` klasorune yaziliyor.
2. `settings.json` icinde hem Cloud'a alinmasi gereken ilerleme verileri hem de makineye ozel grafik ayarlari bir arada duruyor.

Bu haliyle tum `settings.json` dosyasini Cloud'a almak yanlis olur; cozunurluk, fullscreen, vsync gibi ayarlar baska cihazlarda istenmeyen davranis uretir.

## Onerilen Mimari

Ilk fazda `Steam Auto-Cloud` kullanilmasi en dogru secim.

Gerekce:

- Projede kalici verinin cogu zaten disk tabanli.
- Steam Cloud icin mevcut oyun akislarini bastan yazmak gerekmiyor.
- Steam istemcisi oyun acilmadan once indirme, oyun kapandiktan sonra yukleme isini otomatik yapiyor.
- Bu repo icinde henuz `ISteamRemoteStorage` kullanimi yok; ilk adimda bunu eklemek gereksiz karmasa olur.

Ikinci faz olarak, yalnizca ihtiyac dogarsa `src/steam_integration.py` icine `ISteamRemoteStorage` ctypes sarmali eklenmeli.

Bu ikinci faz ancak su ihtiyaclardan biri varsa gerekli:

- oyun ici Cloud ac/kapat secenegi
- kota/alan bilgisini UI'da gostermek
- dosya bazli daha ince kontrol
- dinamik sync callback'lerini aktif kullanmak
- senkron degisikliklerini oyun oturumu sirasinda karsilamak

## Dosya Siniflandirma

### Cloud'a alinacak veri

- profil listesi ve profil baglantilari
- kullaniciya bagli achievement verileri
- kullaniciya bagli highscores ve istatistikler
- campaign progress
- bio, avatar secimi, favoriteler, tutorial tamamlanma durumu gibi profile ait alanlar
- ozel avatar PNG dosyalari
- istege bagli olarak dil ve oynanis tercihleri

### Lokal kalacak veri

- fullscreen
- borderless fullscreen
- resolution
- vsync
- fps limit
- cihaz/performance odakli grafik tercihleri
- ileride cikabilecek makineye ozel cache dosyalari

### Ayrik karar gerektiren veri

- ses seviyesi
- kontrol atamalari
- gamepad deadzone ve rumble
- menu/transparency gibi tercihsel UI ayarlari

Bu grup icin onerim su: klavye ve genel kullanici tercihleri Cloud'a alinabilir, ama gamepad ve donanim bagimli alt ayarlar lokal tutulmali.

## Uygulama Fazlari

## Faz 1: Kayit yolunu normalize et

Amac: tum senkronize edilecek veriler tek bir Cloud alt agacinda toplansin.

Kod degisiklikleri:

- `src/data_paths.py`
  - `get_user_data_dir()` korunacak.
  - yeni yardimcilar eklenecek:
    - `get_cloud_data_dir()`
    - `get_local_data_dir()`
    - `resolve_cloud_path()`
    - `resolve_local_path()`
    - gerekirse `resolve_cloud_asset_path()`
- Yeni hedef dizin yapisi:
  - `.../quadrix_full/cloud/`
  - `.../quadrix_full/local/`

Onerilen klasor yapisi:

```text
quadrix_full/
  cloud/
    users.json
    profiles/
      <profile_id>/
        achievements.json
        highscores.json
        avatar.png
    campaign_progress.json
    settings_cloud.json
  local/
    settings_local.json
```

Not: `profile_id` icin yalnizca username kullanmak yerine stabil bir kimlik eklenmesi daha dogru olur. Mevcut sistem username'e dayali dosya isimleri kullandigi icin, uzun vadeli cozum profil bazli benzersiz ID'dir.

## Faz 2: Avatar kaydini ortak veri agacina tasi

Amac: avatarlarin calisma dizinine bagli olmasini bitirmek.

Kod degisiklikleri:

- `src/avatar_editor.py`
  - `self.avatars_dir = 'avatars'` mantigi kaldirilacak.
  - avatar kaydi `resolve_cloud_path()` ile cozulmus profile klasorune yapilacak.
- `src/user_screens.py`
  - custom avatar path saklama/yukleme mantigi yeni profile klasor yapisina gore guncellenecek.
- avatar load eden yardimci yerler
  - mutlak/goreli/legacy path uyumlulugu korunacak.

Migrasyon:

- Eski `avatars/<username>_avatar.png` varsa yeni profile klasorune bir kez tasinacak.
- Profilde tutulan avatar referansi yeni yola yazilacak.

## Faz 3: Settings'i Cloud ve lokal diye ayir

Amac: cihaz-ozel ayarlar ile kullanici/progres ayarlarini ayri dosyalarda tutmak.

Kod degisiklikleri:

- `src/settings_manager.py`
  - tek dosya yerine iki katmanli yukleme modeli gelecek:
    - `settings_local.json`
    - `settings_cloud.json`
  - okuma sirasinda birlestirilecek
  - kayit sirasinda anahtar bazli dogru hedefe yazilacak
- `campaign_progress` yeni ayri Cloud dosyasina alinacak ya da `settings_cloud.json` icinde tutulacak.

Onerilen anahtar ayrimi:

- Lokal:
  - `fullscreen`
  - `borderless_fullscreen`
  - `resolution`
  - `vsync`
  - `fps_limit`
- Cloud:
  - `language`
  - `theme`
  - `music_enabled`
  - `sound_enabled`
  - `music_volume`
  - `menu_music_volume`
  - `sfx_volume`
  - `das_delay`
  - `das_repeat`
  - `soft_drop_speed`
  - `campaign_progress`

Eger ayri bir `campaign_progress.json` dosyasi acilirsa conflict analizi daha kolay olur.

## Faz 4: Profil metadatasini Cloud merkezli hale getir

Amac: kullanici kayitlarini ve profile bagli dosya referanslarini yeni yapiya tasimak.

Kod degisiklikleri:

- `src/user_manager.py`
  - `users.json` Cloud tarafina tasinacak.
  - yeni schema eklenecek:
    - `schema_version`
    - `profile_id`
    - `last_modified_utc`
  - `current_user` degeri tercihen lokal tutulacak; profil listesi ise Cloud'da kalacak.
  - `achievements_file` ve `highscores_file` alanlari yeni klasor yapisina guncellenecek.

Gerekce:

- Profil listesi cihazlar arasi ortak olmali.
- Ama aktif secili kullanici cihaz bazli farkli olabilir.

## Faz 5: Achievements ve highscores path migrasyonu

Kod degisiklikleri:

- `src/achievements.py`
- `src/score_manager.py`

Bu iki modulde ana is, yeni Cloud path'lerini kullanmak ve ilk acilista eski dosyalari yeni profile dizinine tasimak.

Migrasyon sirasinda:

- `achievements_<username>.json` -> `profiles/<profile_id>/achievements.json`
- `highscores_<username>.json` -> `profiles/<profile_id>/highscores.json`

## Faz 6: Baslangic migrasyon akisini ekle

Amac: eski kurulumlardan gelen veriyi veri kaybi olmadan yeni duzene almak.

Kod degisiklikleri:

- oyunun acilisinda, Steam init sonrasinda ama profil secimi netlesmeden once tek seferlik migrasyon calisacak
- uygun baglama noktasi `src/main.py` icindeki Steam profil secim blogunun oncesi veya hemen sonrasi

Migrasyon adimlari:

1. `cloud/` ve `local/` klasorlerini olustur.
2. Eski `users.json` dosyasini `cloud/users.json` altina tasi.
3. Eski `settings.json` dosyasini ayrisarak `settings_local.json` ve `settings_cloud.json` olarak yaz.
4. Profil bazli achievement/highscore dosyalarini yeni profile klasorlerine tasi.
5. Eski avatarlari yeni profile klasorune tasi.
6. `schema_version` ve `migration_completed_at` yaz.

Bu migrasyon idempotent olmali; ayni sistem ikinci kez acildiginda tekrar veri bozmamali.

## Faz 7: Test matrisi

Gerekli testler:

1. Eski save'li kullanicida ilk acilista tum veriler yeni duzene geciyor mu?
2. Steam Cloud kapaliysa oyun fallback olarak sadece lokal diski kullanmaya devam ediyor mu?
3. Ayni Steam hesabi ile ikinci cihazda profil/achievement/highscore/campaign/avatar geliyor mu?
4. Grafik ayarlari baska cihazda tasinmadigi icin cihaz-uyumsuzluk cikmiyor mu?
5. Ayni kullanici iki cihazda farkli ilerleme kaydederse Steam conflict davranisi kabul edilebilir mi?
6. Steam disinda baslatilan build'lerde veri klasoru mantigi bozuluyor mu?

## Opsiyonel Faz 8: Explicit Remote Storage

Auto-Cloud canliya alindiktan sonra ihtiyac varsa uygulanacak.

Kod degisiklikleri:

- `src/steam_integration.py`
  - `ISteamRemoteStorage` accessor ve function imzalari eklenecek
  - olasi ilk fonksiyonlar:
    - `is_cloud_enabled_for_account()`
    - `is_cloud_enabled_for_app()`
    - `get_cloud_quota()`
    - `begin_file_write_batch()`
    - `end_file_write_batch()`
- gerekirse dinamik sync callback handling eklenecek

Bu faz ilk yayinda zorunlu degil.

## Steamworks Panelinde Yapilacaklar

## 1. Steam Cloud'u etkinlestir

Steamworks uygulama yonetim panelinde Steam Cloud ayarlarina gir.

Ayarlanacak temel alanlar:

- `User Byte Quota`
- `User File Count`

Bu proje icin ilk guvenli onerim:

- kota: `32 MB`
- dosya sayisi: `256`

Sebep:

- JSON save dosyalari cok kucuk
- avatar PNG'ler de 128x128 oldugu surece dusuk boyutlu kalir
- gereksiz devasa kota tanimlamaya gerek yok

Eger ileride daha buyuk kullanici uretilmis veri eklenecekse bu deger yukseltilir.

Yayinlanmis oyunda once test etmek icin:

- `Enable cloud support for developers only` secenegini ac

Eger playtest/demo ile ayni save alanini paylasmak istiyorsan:

- `Shared cloud APP ID` alanini buna gore doldur

## 2. Auto-Cloud root tanimi yap

Onerilen strateji: sadece `cloud/` alt agacini senkronize et.

Boylece `local/` altindaki makineye ozel ayarlar Steam tarafina hic cikmaz.

Ilk root tanimi:

- Root: `WinAppDataRoaming`
- Subdirectory: `quadrix_full/cloud`
- Pattern: `*`
- OS: `All OSes`
- Recursive: `Yes`

Ardindan root override ekle:

- Original Root: yukaridaki root
- OS: `macOS`
- New Root: `MacAppSupport`
- Path Add/Replace: `quadrix_full/cloud`
- Replace Path: `Yes`

Bir override daha ekle:

- Original Root: yukaridaki root
- OS: `Linux`
- New Root: `LinuxXdgDataHome`
- Path Add/Replace: `quadrix_full/cloud`
- Replace Path: `Yes`

Bu, `src/data_paths.py` icindeki platforma ozel kalici veri mantigiyla uyumlu olur.

## 3. Degisiklikleri kaydet ve publish et

Panelde sadece kaydetmek yetmez.

Gerekli adim:

- ayarlari `Save` et
- Steamworks degisikliklerini `Publish` et
- gerekiyorsa 10 dakika bekle veya Steam istemcisini yeniden baslat

## 4. Auto-Cloud testi yap

Steam istemcisinde su konsol akisini kullan:

1. `steam://open/console`
2. `testappcloudpaths <AppID>`
3. `set_spew_level 4 4`
4. oyunu Steam uzerinden baslat
5. bir save degisikligi yap
6. oyundan cik
7. log ve console ciktisini kontrol et

Bitince temizle:

1. `testappcloudpaths 0`
2. `set_spew_level 0 0`

Log inceleme noktasi:

- Steam istemci loglari icindeki `cloud_log.txt`

## 5. Dinamik sync'i ilk yayinda zorunlu tutma

Steam Deck / suspend-resume senaryolari icin dinamik sync desteklenebilir.
Ama mevcut kod tabaninda dosya degisiklik callback'lerini ele alan akıs yok.

Bu nedenle ilk canli surum icin onerim:

- once klasik Auto-Cloud migrasyonunu bitir
- sonra dinamik sync'i ayrica test edip ac

## Uygulama Sirasi Onerisi

1. `data_paths.py` icine cloud/local ayrimini ekle
2. avatar kaydini yeni path yapisina tasi
3. `settings_manager.py` dosyasini cloud/local olarak ayir
4. `user_manager.py` schema migrasyonunu yap
5. achievements/highscores dosyalarini yeni profile dizinine tasi
6. ilk acilis migrasyonunu ekle
7. Steamworks Auto-Cloud ayarlarini ac
8. iki cihaz testi yap
9. gerekirse ikinci fazda explicit Remote Storage ekle

## Karar Ozeti

Bu repo icin dogru ilk adim `Steam Auto-Cloud + veri yapisini yeniden ayirma` yaklasimidir.

Dogrudan `ISteamRemoteStorage` ile baslamak teknik olarak mumkun olsa da mevcut mimaride asil sorun Steam API eksikligi degil, Cloud'a alinacak veri ile lokal kalacak verinin birbirine karismis olmasidir.

Once bu ayrim yapilmali. Sonra Steamworks tarafinda yalnizca `cloud/` klasoru Auto-Cloud ile eslestirilmelidir.