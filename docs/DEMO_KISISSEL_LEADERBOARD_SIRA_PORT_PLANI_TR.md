# Demo skor paneline kişisel sıralama satırı port planı

## Sonuç

Ana oyunda, global ilk 10 listesine girmeyen aktif oyuncunun gerçek Steam sırasını ve skorunu panelin altında gösteren özellik şu committe eklendi:

- **Commit:** `af139a4633f1b6d81fda16dce5ac61aeefeed9c7`
- **Tarih:** 24 Temmuz 2026 15:24 (+03:00)
- **Başlık:** `feat: implement store feedback popup and add personal rank display to mystery leaderboards`
- **İlgili kapsam:** `src/menu.py`, `src/steam_leaderboards.py`, `src/steam_integration.py`, `backend/steam_leaderboard_proxy.py`, `src/localization.py` ve leaderboard testleri.

Commit toplam 9 dosyada 918 satır değiştiriyor; mağaza geri bildirim popup'ı ve `KeepBest` zorlaması kişisel sıra satırından bağımsızdır. Demo'ya bütün commit'i cherry-pick etmek yerine aşağıdaki kişisel sıra hunisi seçici olarak port edilmelidir.

## Davranış sözleşmesi

1. Global panelin ilk 10 satırı aynı kalır; oyuncu ilk 10'da ise mevcut satır mavi vurguyla gösterilir.
2. Oyuncu ilk 10 dışında ise liste yeniden sıralanmaz ve araya eklenmez. Alt bölümde yalnızca aktif oyuncunun gerçek global `rank` ve `score` değeri gösterilir.
3. Alt satır yalnızca global sekmede ve geçerli bir `steam_id` ile `rank > 0` olduğunda görünür. Arkadaş sekmesi ve trailer debug verisi bu satırı kullanmaz.
4. Rank verisi bulunamazsa skor panelinin mevcut global/arkadaş davranışı değişmez; boş veya hata durumunda footer çizilmez.
5. Tüm istekler mevcut backend/client-token/app-ID doğrulama zincirinden geçer. Demo AppID'si **4635310** olarak kalır; ana oyunun **4414520** veya playtest kimlikleri kopyalanmaz.

## Platform uyumluluğu

Planın veri akışı ve backend endpoint'i Windows, macOS ve Linux için aynıdır. Native Steam kütüphanesi mevcut platform loader'ı üzerinden seçilir; port sırasında platforma özel yeni bir DLL/SO/DYLIB yolu yazılmamalıdır.

| Platform | Steam runtime dosyası | Dikkat edilmesi gerekenler |
| --- | --- | --- |
| Windows | `steam_api64.dll` | Steam açık olmalı; demo AppID'si `4635310` ile başlatılmalı. |
| macOS | `libsteam_api.dylib` | Uygulama kapanışında worker iptali ve `should_cancel_background_work()` akışı korunmalı. |
| Linux / Steam Deck | `libsteam_api.so` | ELF/64-bit runtime ve doğru Steam AppID'si doğrulanmalı; dosya yolları `pathlib`/`os.path` ile kurulmalı. |

Kod portunda şu platform bağımsızlık kuralları korunur:

- `datarequest` ve JSON endpoint sözleşmesi işletim sisteminden bağımsızdır.
- Steam SDK çağrıları mevcut `_start_tracked_worker()`, callback bekleme ve `should_cancel_background_work()` akışıyla çalıştırılır; UI thread'inde bloklayıcı yeni çağrı eklenmez.
- Windows ters eğik çizgisi, `/usr/lib` veya macOS bundle yolu doğrudan koda gömülmez. Native dosya çözümlemesi mevcut `steam_integration.py` loader'ına bırakılır.
- Backend proxy Flask/urllib katmanında çalışır; Steam publisher key yalnız backend ortamında tutulur.
- Headless CI/QA için SDL değişkenleri yalnız test komutunun ortamında ayarlanır; oyun çalışma ayarlarına yazılmaz.

## Demo'daki mevcut eksikler

Demo dalında (`release/demo`) global ve arkadaş listesi vardır, ancak kişisel sıra hunisi yoktur:

- `src/menu.py:585` civarında `_mystery_lb_self_entry` state'i yoktur.
- `src/menu.py:4340-4528` civarındaki refresh worker yalnızca global ve arkadaş sonuçlarını çeker.
- `src/menu.py:4727-4905` civarındaki renderer yalnızca liste satırlarını çizer; footer alanı ayırmaz ve ana oyundaki `_mystery_lb_surface_cache` state/cache alanı demo init'inde bulunmaz.
- `src/steam_leaderboards.py:481-499` global fetch içerir, `fetch_mode_user_score()` yoktur.
- `src/steam_integration.py:2837-2844` global/arkadaş wrapper'larına sahiptir; `fetch_user_score()` yoktur. Buna rağmen alt seviye AroundUser desteği `fetch_leaderboard_entries()` içinde zaten `request_type=1` ve `range_start/range_end=(-half, half)` ile mevcuttur (`:2747-2750`).
- `backend/steam_leaderboard_proxy.py:684-704` global endpoint'ten sonra doğrudan arkadaş endpoint'ine geçer; `/api/v1/leaderboards/<mode>/user` route'u yoktur.
- Demo `src/localization.py:21963-22015` içinde `menu_lb_you` anahtarı yoktur. Ana oyundaki karşılığı `src/localization.py:26845` civarındadır.
- Demo backend'i hâlâ `RequestGlobal/AroundUser/Friends` değerlerini sayısal enum'a çevirir (`backend/steam_leaderboard_proxy.py:268-283`). Ana oyundaki commit, Steam Web API isteğinde metin değerini (`RequestAroundUser`) ve AroundUser aralığını (`-half..half`) kullanacak şekilde bu yolu düzeltmiştir. Bu hunk, endpoint ile birlikte port edilmelidir; SDK tarafındaki sayısal enum sabitleri değiştirilmemelidir.

## Uygulama sırası

### 1. SDK kişisel kayıt wrapper'ı

`src/steam_integration.py` içine `fetch_user_score(mode)` eklenir:

- `get_steam_id_str()` ile aktif Steam ID alınır; boşsa `None` döner.
- `fetch_leaderboard_entries(mode, request_type=_LB_REQUEST_AROUND_USER, limit=3)` çağrılır.
- Dönen küçük çevrede Steam ID eşleşen kayıt bulunur ve tek kayıt döndürülür.
- Mevcut callback, worker izleme ve `should_cancel_background_work()` akışı korunur.

Bu, demo'da zaten çalışan `_LB_REQUEST_AROUND_USER = 1` altyapısını yeniden kullanır; yeni bir DLL API'si uydurulmaz.

### 2. Client service yolu

`src/steam_leaderboards.py` içine `fetch_mode_user_score(mode, steam_id=None)` eklenir:

- Steam ID parametresi veya `current_steam_id` normalize edilir; yoksa `last_error` yazılıp `None` döner.
- Backend modunda `GET /api/v1/leaderboards/{mode}/user?steam_id={sid}` çağrılır.
- Backend boş döner ve direct mod yapılandırılmışsa `RequestAroundUser`, `limit=3`, `steam_id=sid` ile direct Web API fallback'i denenir.
- Sonuçlar içinde Steam ID'si tam eşleşen tek kayıt döndürülür.
- `fetch_mode_highscores()` ve arkadaş akışının mevcut hata/fallback sözleşmesi bozulmaz.

Direct Web API helper'ında `RequestGlobalAroundUser` değeri `RequestAroundUser` olarak normalize edilmeli; yalnızca Web API'ye gönderilen `datarequest` metin olmalıdır. SDK `request_type` değerleri sayısal kalır.

### 3. Backend endpoint ve gateway

`backend/steam_leaderboard_proxy.py` içinde:

1. `SteamDirectGateway.fetch_entries()` için `RequestAroundUser` yolu eklenir. `safe_limit=3` için `half=max(1, safe_limit//2)` ve aralık `(-half, half)` kullanılır.
2. Web API parametresinde `datarequest` metin (`RequestAroundUser`) olarak gönderilir; bilinmeyen değerler `RequestGlobal`'a normalize edilir.
3. Global route'un hemen sonrasına `GET /api/v1/leaderboards/<mode>/user` eklenir.
4. Mode doğrulanır, `steam_id` zorunlu tutulur, gateway AroundUser çağrılır ve dönen çevreden yalnızca istenen Steam ID'ye ait kayıt `entries[:1]` olarak döndürülür.
5. Mevcut `_gateway_for_request()` akışı korunarak client-token ve AppID kontrolü atlanmaz.

`KeepBest` zorlaması aynı committe bulunduğu için port sırasında görülebilir; bu özellik için zorunlu olmayan yazma davranışı değişikliğini ayrı bir karar/commit olarak ele almak daha güvenlidir.

### 4. Menü fetch worker'ı

`src/menu.py` içinde:

- `__init__` state'ine `self._mystery_lb_self_entry: dict | None = None` eklenir.
- Yapılandırma yoksa bu state `None` yapılır.
- Global SDK/backend birleştirmesinden sonra `current_sid` alınır.
- Önce SDK: `_si.fetch_user_score('mystery')`.
- SDK kayıt vermezse backend/direct service: `service.fetch_mode_user_score('mystery', steam_id=current_sid)`.
- Shutdown/cancel kontrolleri her iki çağrıdan sonra korunur.
- Bulunan kişisel kayıt, oyuncu summary/avatar cache'ine dahil edilir; böylece footer etiketi mevcut persona cache yolunu kullanır.
- Sonuç worker tamamlanırken `self._mystery_lb_self_entry = dict(self_entry) if self_entry else None` atanır.

Kişisel kayıt global listeye eklenmez; aksi halde ilk 10 listesi yanlış biçimde yeniden sıralanır.

### 5. Menü footer'ı

`_draw_mystery_leaderboard_panel()` içinde mevcut `list_rect` iki bölüme ayrılır:

- `visible_entries = active_entries[:max_rows]` ve mevcut satırlar `rows_rect` içinde çizilir.
- Aktif Steam ID ilk 10'da değilse ve kişisel kayıt geçerliyse `footer_h`/`footer_gap` ayrılır.
- Footer `#rank`, kişi adı veya `t('menu_lb_you')`, ve skor değerini gösterir.
- Demo init'ine leaderboard yüzey cache'i eklenir (ana oyundaki `_mystery_lb_surface_cache` ve kapasite sınırı veya repo standardındaki eşdeğer `SurfaceLRUCache`). Satır ve footer yüzeyleri bu cache desenine uygun cache'lenir; ana game-loop içinde sürekli yeni `Surface` veya font render tahsisi yapılmaz.
- Etiket çok uzunsa mevcut multilingual ölçüm ve üç nokta kırpma yaklaşımı kullanılır.
- `pygame.Rect` koordinatları mevcut `s()` ölçek fonksiyonundan geçer; sabit ekran pikseli eklenmez.

### 6. Lokalizasyon

Demo `src/localization.py` içine `menu_lb_you` anahtarı, desteklenen 11 dilin tamamıyla eklenir. En azından Türkçe `Sen` ve İngilizce `You` eş zamanlı bulunmalıdır; eksik diller fallback'e bırakılmaz.

## Test portu ve yeni regresyonlar

Ana oyundaki `tests/test_leaderboard_app_id_routing.py` içindeki şu senaryolar demo'ya uyarlanmalıdır:

- backend client kişisel rank/score kaydını doğru endpoint'ten alıyor;
- direct client `datarequest=RequestAroundUser`, `rangestart=-1`, `rangeend=1` gönderiyor;
- gateway gerçek global rank'i normalize ediyor;
- backend üç AroundUser kaydından yalnız istenen Steam ID'yi döndürüyor;
- mevcut AppID yönlendirmesi demo `4635310` için çalışıyor.

`tests/test_p1_screen_containment.py` içindeki leaderboard fixture'ı `self_entry` kabul edecek şekilde genişletilmeli ve şu UI testleri eklenmelidir:

- oyuncu ilk 10 dışında: footer görünür, rank/score çizilir ve panel sınırları içinde kalır;
- oyuncu ilk 10 içinde: footer görünmez, mevcut satır vurgusu korunur;
- footer persona adı uzun olduğunda üç noktayla kırpılır;
- dar/geniş sanal tuvalde satır yüksekliği ve footer çakışmaz;
- cache anahtarları rank/score/ölçü değişiminde doğru yüzey üretir.

Doğrulama komutları:

Windows PowerShell:

```powershell
py -3.12 -m compileall -q src tests
py -3.12 -m pytest -q tests/test_leaderboard_app_id_routing.py tests/test_lb_write_proxy.py tests/test_p1_screen_containment.py tests/test_leaderboard_friend_ranks.py
```

macOS / Linux / Steam Deck shell:

```bash
python3.12 -m compileall -q src tests
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1 \
python3.12 -m pytest -q tests/test_leaderboard_app_id_routing.py \
  tests/test_lb_write_proxy.py tests/test_p1_screen_containment.py \
  tests/test_leaderboard_friend_ranks.py
```

Repository test wrapper (macOS/Linux/Steam Deck):

```bash
./scripts/test/run_tests.sh -q tests/test_leaderboard_app_id_routing.py \
  tests/test_lb_write_proxy.py tests/test_p1_screen_containment.py \
  tests/test_leaderboard_friend_ranks.py
```

Windows'ta Bash/WSL kullanılmıyorsa wrapper yerine PowerShell komutları çalıştırılır. Her üç platformda Python **3.12** ve pygame-ce bağımlılığı kullanılmalıdır.

Steam açık olmayan ortamda SDK/gerçek backend smoke testi yapılamaz; bu durumda mock testleri kanıt olarak raporlanmalı, Steam entegrasyonu doğrulanmış gibi yazılmamalıdır. Steam smoke sırasında hem ilk 10'da hem de ilk 10 dışında kayıtlı bir demo hesabı, Steam kapalı durum ve backend boş/hata durumu ayrı ayrı denenmelidir.

Native smoke matrisi:

- Windows: `steam_api64.dll` yüklenmesi, demo AppID `4635310`, ilk 10 dışı kullanıcı ve Steam kapalı fallback.
- macOS: `libsteam_api.dylib` yüklenmesi, normal kapanış ve kapanış sırasında bekleyen leaderboard worker'ının iptal edilmesi.
- Linux/Steam Deck: `libsteam_api.so` yüklenmesi, 64-bit Steam runtime, AppID doğrulaması ve aynı AroundUser rank cevabı.
- Backend üç platformda ortak çalıştırılabilir; publisher key, client token ve `LEADERBOARD_ALLOWED_APP_IDS=4635310` ortam değişkenleri platformun secret/env mekanizmasıyla sağlanmalıdır.

## Commit önerisi

Port tamamlandığında değişiklikleri dar etki alanıyla ayır:

1. `feat(leaderboard): demo kişisel sıra veri akışını ekle`
2. `feat(leaderboard): demo skor paneline kişisel sıra footer'ı ekle`
3. `test(leaderboard): demo AroundUser ve footer regresyonlarını ekle`
4. Bu kılavuz için ayrı `docs(leaderboard): demo kişisel sıra port planını ekle`

Ana oyundaki `af139a4` referans olarak kalmalı; demo'ya bütün commit'i doğrudan taşımak yerine bu dört yüzeyin seçici portu uygulanmalıdır.
