# Plan: Online PvP Private Lobby Cross-Platform Recovery

Created: 2026-04-09
Status: Investigation-backed, ready for implementation

## Scope

Bu plan iki guncel semptomu ayni kok neden ailesi icinde ele alir:

- macOS'ta ozel lobi olusturulamiyor.
- Windows'ta olusturulan ozel lobi macOS "Mac Bul" ekraninda gorunmuyor.

Bu belge yalnizca semptom listesi degildir. Mevcut kaynak, onceki planlar, rebuild belgeleri ve test davranislari uzerinden dogrulanan durumlari toplar; varyasyonlari ayirir; her varyasyon icin uygulanabilir cozum yolunu siralar.

## Verified Current State

Asagidaki noktalar kaynak ve belge okumalariyla dogrulandi:

1. Private lobby'nin tasarlanan Steam tipi `Invisible`.
   - `src/steam_networking.py` private create akisinda `create_lobby_with_type(LobbyType.INVISIBLE)` kullaniyor.
   - `steamworks/steam_net_bridge/steam_net_bridge.cpp` private create fallback'inde de `k_ELobbyTypeInvisible` kullaniyor.

2. Lobby browser tasarimi private lobby'leri de gostermeyi hedefliyor.
   - `src/online_pvp_game.py` icinde `_lobby_list_filter == 'all'` ise ek bir `visibility=public` filtresi uygulanmiyor.
   - UI altyazisi da bunu acikca soyluyor: `lobby_list_subtitle_all = Ozel ve acik lobiler`.
   - Bu nedenle `Mac Bul` ekraninda private lobby gorunmesi mevcut urun niyetinin parcasidir; yalnizca code-only akis beklenmiyor.

3. Bridge su an private lobby metadata'sini create callback'i icinde atomik yayinliyor.
   - `visibility`
   - `requires_code`
   - `lobby_code`
   - `lobby_code_full`
   - `metadata_ready = 1`
   - `SetLobbyJoinable(true)`

4. `RequestLobbyList()` tarafinda hedeflenen davranis Public + Invisible lobby'leri almaktir.
   - Bu kabul hem `steam_net_bridge.cpp` yorumlari hem de onceki dokumanlarla tutarlidir.
   - `FriendsOnly` shipping fallback'i uygun degildir; arama disina cikabildigi icin browse akisini tasarim geregi kirar.

5. macOS build helper stale bridge'i otomatik rebuild edebiliyor, Windows helper ise ayni guvenceyi vermiyor.
   - `scripts/build/build_macos_app.sh`: kaynak artefact'ten yeniyse rebuild zorluyor.
   - `scripts/build/build_windows_exe.ps1`: bridge yoksa veya `-RebuildBridge` gecilmisse rebuild ediyor; kaynak daha yeni olsa bile mevcut artefact varsa otomatik rebuild etmiyor.
   - Bu asimetri capraz platform binary skew riskini acik bir sekilde artiriyor.

6. Browse UI icinde `unknown/syncing` lobby cizim yolu var, ama bu yol tam kullanilmiyor.
   - `src/online_pvp_game.py` cizim kodu `visibility == 'unknown'` kartlarini cizebiliyor.
   - Buna ragmen `_on_lobby_found()` unknown lobby'leri `_pending_lobby_list` yerine sadece `_deferred_lobby_entries` icine koyuyor.
   - Eger `lobby_data_updated` hic gelmezse bu lobby browse UI'da tamamen gorunmez kalir.

7. Onceki testler private code join akisini browse gorunurlugunden ayri sertlestiriyor.
   - Deferred lobby girdileri code search sirasinda tekrar canli okunabiliyor.
   - Bu nedenle "Kod ile katilabiliyor ama listede gorunmuyor" ayrik bir failure mode olarak zaten mantiksal olarak mumkun.

## Problem Variations

Bu iki kullanici semptomu tek bir bug gibi gorunse de en az bes farkli varyasyon vardir. Bunlari ayirmadan duzeltme yapmak risklidir.

### V1. macOS Private Create Hard Failure

Belirti:

- macOS kullanicisi `Ozel Lobi Olustur` dediginde lobby create basarisiz oluyor veya WAITING state'e hic gecmiyor.

En olasi nedenler:

- `CreateLobby(k_ELobbyTypeInvisible)` macOS runtime'inda hata kodu donduruyor.
- macOS build'i guncel Python kaynagini kullansa da stale bridge artifact ile calisiyor.
- Bridge yukleniyor ama Steam init / overlay / API state create aninda saglikli degil.

Ayirici test:

- Ayni macOS build ile public create calisiyor mu?
- `lobby_create_failed` event'inin gercek result code'u nedir?
- Runtime'da yuklenen bridge binary'si hangi build/signature?

### V2. Browse-Only Invisibility

Belirti:

- Windows private lobby aslinda var.
- Code ile veya invite ile join mumkun olabilir.
- Ancak macOS `Mac Bul` listesinde lobby hic gorunmez.

En olasi nedenler:

- `RequestLobbyList` snapshot'i metadata'siz geliyor.
- `lobby_data_updated` callback'i hic gelmiyor veya gec geliyor.
- Unknown lobby browse listesine alinmadigi icin kullaniciya hic gosterilmiyor.

Bu varyasyon su anda en guclu adaylardan biridir, cunku mevcut kaynak unknown lobby kartini cizebildigi halde listeye sokmuyor.

### V3. Cross-Platform Binary Skew

Belirti:

- Ayni kaynak commit'indeymis gibi gorunen iki build farkli davranis gosteriyor.
- Bir platformda duzeltilmis davranis digerinde yok.

En olasi nedenler:

- Windows bridge artefact'i kaynak degisince otomatik stale sayilmiyor.
- Bir platform temiz rebuild, digeri incremental build ile alinmis.
- Paket icindeki bridge binary ile repo kaynagi fiilen farkli.

Bu varyasyon onceki channel/message problemlerinde zaten goruldugu icin teorik degil, gecmis ariza ailesinin devamidir.

### V4. Filter or UX Expectation Mismatch

Belirti:

- Kullanici private lobby'nin browse ekraninda olmasini bekliyor.
- Sistem gercekte `Public Lobbies` filtresinde veya stale UI state ile browse ediyor.

Not:

- Mevcut urun kopyasi `Butun Lobiler` altinda private + public bekledigini soyledigi icin bu tek basina yeterli aciklama degildir.
- Yine de tanilama sirasinda aktif filter state mutlaka loglanmali.

### V5. Steam Invisible Semantics Drift

Belirti:

- Kod mantigi dogru gozukur.
- Temiz rebuild yapilir.
- Yine de bir platform `Invisible` lobby'leri listede dondurmez veya create davranisi farkli olur.

Bu daha dusuk olasilikli ama pahali varyasyondur. Ancak V1-V4 elendikten sonra hedefli deney gerekir.

## Main Hypothesis Ranking

1. Browse tarafinda unknown lobby'lerin hidden kalmasi.
2. Windows/macOS bridge binary skew.
3. macOS private create path'inde runtime-level `Invisible` create failure.
4. Filter state veya urun beklentisi karisikligi.
5. Steam client / SDK seviyesinde `Invisible` davranis drift'i.

## Recommended Plan

## Phase 1: Reproduce and Classify Before Changing Semantics

Amac: `create failure` ile `browse invisibility` sorunlarini kesin olarak ayirmak.

Yapilacaklar:

1. `lobby_create_failed` durumunda result code ve requested lobby type Python log'una acik sekilde yazdir.
2. `Mac Bul` akisinda su alanlari tek satir log ile yazdir:
   - aktif filter (`all` veya `public`)
   - gorunen lobby sayisi
   - deferred lobby sayisi
   - unknown lobby sayisi
3. Runtime bridge capability/build signature bilgisini init sirasinda logla.
4. Manuel tanilama matrisi calistir:
   - macOS private create
   - macOS public create
   - Windows private create
   - Windows public create
   - private browse on `all`
   - private browse on `public`
   - code join
   - invite join

Beklenen ciktisi:

- Semptomun V1 mi, V2 mi, yoksa V3 ile karisik mi oldugu aciklasir.

## Phase 2: Fix Browse Pipeline So Unknown Lobbies Are Visible as Syncing Cards

Amac: Metadata yarisi veya eksik callback, lobby'yi tamamen gorunmez yapmasin.

Onerilen degisiklik:

1. `_on_lobby_found()` unknown entry'leri sadece `_deferred_lobby_entries` icine atmak yerine browse listesine de eklesin.
2. Bu kartlar mevcut draw yolundaki `visibility == 'unknown'` sunumunu kullansin.
3. Join aksiyonu metadata hazir olana kadar disable kalsin.
4. `lobby_data_updated` gelirse ayni kart private/public olarak upgrade edilsin.
5. `lobby_data_updated` hic gelmezse bile kullanici "senkronize ediliyor" kartini gorebilsin; "hic yok" algisi son bulsun.

Neden bu faz once gelmeli:

- Kullaniciya gorunurluk kazandirir.
- Kod/invite ile calisan ama browse'da kaybolan private lobby semptomunu dogrudan kapatir.
- Mevcut cizim kodu zaten buna hazir; eksik halka listeleme tarafidir.

Test ihtiyaci:

- Unknown lobby browse listesinde yer aliyor mu?
- Metadata geldikten sonra ayni entry promote oluyor mu?
- Unknown kart join edilemiyor mu?

## Phase 3: Eliminate Binary Skew at Build Time

Amac: Koddaki dogru davranisin stale bridge nedeniyle platformlardan birinde kaybolmasini engellemek.

Yapilacaklar:

1. `scripts/build/build_windows_exe.ps1` icine macOS helper'daki gibi stale bridge detection ekle.
2. Bridge source artefact'ten yeniyse Windows build de rebuild zorlasin.
3. Runtime'a bir bridge build signature veya capability string ekle.
4. Paket build log'unda kullanilan bridge binary path'i ve timestamp'i zorunlu olarak yazilsin.

Neden kritik:

- Bu repo daha once tam ayni ailede binary/source skew yasadi.
- Sadece belge ile "iki tarafi da rebuild edin" demek yeterli degil; helper script enforcement gerekli.

## Phase 4: Harden macOS Private Create Path

Bu faz Phase 1 loglari sonrasinda uygulanmali.

Yapilacaklar:

1. `create_private` ile `create_public` sonucunu ayni log formatinda karsilastir.
2. `Invisible` create yalnizca macOS'ta fail ediyorsa, once diagnostic branch ac:
   - `FriendsOnly` sadece tanilama icin denensin.
   - Bu shipping fix olmasin; browse davranisini by-design kirar.
3. Eğer sorun `Invisible` tipi degilse bridge load / Steam init / stale binary yoluna geri don.
4. Son care olarak urun semantigi yeniden degerlendir:
   - `Public + requires_code gate` modeli,
   - veya `Invisible + visible unknown card + strict access gate` modeli.

Oneri:

- Shipping icin ilk tercih `Invisible` semantigini korumaktir.
- `FriendsOnly` kalici fallback olmamali.
- `Public + strict gate` yalnizca Steam tarafli `Invisible` davranisinin platformlar arasi guvenilmez oldugu kanitlanirsa degerlendirilmeli.

## Phase 5: Clarify Product Rules in UI and Docs

Amac: Bug ile beklenti karisikligini kalici olarak azaltmak.

Yapilacaklar:

1. `Mac Bul` ekraninda aktif filter daha belirgin gosterilsin.
2. `Butun Lobiler` durumunda private + public listelendigi net kalsin.
3. `Public Lobbies` durumunda private lobby'lerin bilerek gizlendigi net kalsin.
4. Rebuild belgeleri tek bir canonical akisa baglansin:
   - Windows clean + rebuild bridge
   - macOS clean + rebuild bridge
   - ayni commit dogrulamasi

## Implementation Order

Onerilen uygulama sirasi:

1. Phase 1 logging and classification
2. Phase 2 browse visibility fix
3. Phase 3 Windows stale bridge enforcement
4. Phase 4 macOS private create hardening
5. Phase 5 UI/document cleanup

Bu siralama bilincli secildi. Ilk iki faz, semptomu kullanici gozunde hizla netlestirir ve browse kaybolma problemini buyuk olasilikla kapatir. Ucuncu faz kalici platform uyumlulugu icin gereklidir. Dorduncu faz ise gercekten create path fail ediyorsa hedefli olarak girilmelidir.

## Manual QA Matrix

Asagidaki matrix kapanmadan issue kapatilmis sayilmamali:

1. Windows private create -> macOS `all` filter browse
2. Windows private create -> macOS `public` filter browse
3. macOS private create -> Windows `all` filter browse
4. macOS private create -> Windows `public` filter browse
5. Windows public create -> macOS browse
6. macOS public create -> Windows browse
7. Windows private create -> macOS code join
8. macOS private create -> Windows code join
9. Windows private create -> macOS invite join
10. macOS private create -> Windows invite join
11. Browse listesinde unknown/syncing card gorunurlugu
12. Stale bridge source degisikligi sonrasi build helper enforcement

Beklenen urun kurali:

- `all` filter: private + public lobbies
- `public` filter: sadece public lobbies
- private join: code veya invite gerekli
- private lobby browse card'i metadata gecikse bile tamamen kaybolmamali

## Definition of Done

Bu issue ailesi ancak su kosullarda kapanmis sayilmali:

1. macOS private create fail etmiyor veya fail ediyorsa nedeni log ile acik, tekrarlanabilir ve giderilmis.
2. Windows private lobby macOS browse ekraninda `all` filter altinda gorunuyor.
3. Unknown metadata state'i browse UI'da gorunmez kayip degil, acik bir syncing state uretiyor.
4. Windows build helper stale bridge'i otomatik tespit ediyor.
5. Iki platform ayni bridge capability/build signature ile test edilebiliyor.

## Notes

- Bu plan private lobby icin `FriendsOnly`'a acele gecilmemesini ozellikle onerir. Bu, browse sorununu cozer gibi gorunup aslinda private lobby discoverability'yi by-design yok eder.
- Mevcut en somut kod kokusu browse pipeline'indadir: unknown lobby icin cizim yolu var, ama listeleme yolu eksik oldugu icin private lobby metadata callback'i kacarsa kullaniciya hic birsey gostermiyoruz.
- Mevcut en somut release kokusu build pipeline'indadir: macOS stale bridge guard var, Windows tarafinda ayni guard yok.
