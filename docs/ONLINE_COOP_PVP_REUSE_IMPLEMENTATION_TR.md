# Online Co-op: Online PvP Uzerinden Tasima ve Uygulama Rehberi

> Tarih: 3 Mayis 2026
> Amac: Mevcut online PvP altyapisini yeniden kullanarak online co-op'u en kisa yoldan, en az riskle ve mevcut kod tabanina en uyumlu sekilde hayata gecirmek.
> Kapsam: Bu belge V1 endless online co-op icindir. Online co-op campaign bu belgenin disindadir.

---

## 1. Tek Cumlelik Karar

Online co-op, sifirdan yeni bir online sistem olarak degil, `OnlinePvPGame` kabugunun lobi, invite, join-by-code, private/public metadata, Steam bridge, session bootstrap ve disconnect hardening parcalarinin alinip `CoopGame` etrafina host-otoriteli bir mac katmani olarak sarilmasi ile yapilmali.

Kisa form:

```text
Online Co-op = Online PvP shell + SteamNetworking + authoritative host CoopGame + guest render cache
```

Bu repo icin dogru rota budur.

---

## 2. Neden Dogru Rota Bu?

Online PvP tarafinda zaten cozulmus olan problemler tekrar cozulmemeli:

- Steam bridge yukleme ve pump thread cakismasi
- private/public lobby metadata akisi
- join by code
- Steam invite / overlay entegrasyonu
- session bootstrap ve ready akisi
- disconnect grace period
- sender validation ve lobby-member fallback
- main loop entegrasyonu

Online co-op tarafinin gercek yeni problemi bunlar degil. Gercek yeni problem su:

- iki oyuncu ayni anda ayni ortak board mantigina nasil baglanacak?
- host ve guest hangi state'i otorite kabul edecek?
- freeze, unfreeze, line clear, team score, shared board owner bilgisi nasil tasinacak?

Bu nedenle en mantikli ayirim su:

- transport ve lobby problemleri = PvP'den tasinacak
- ortak gameplay state problemi = Co-op'a ozel yeni katman olacak

---

## 3. Mevcut Kodun Bugunku Durumu

### 3.1 Bugun Hazir Olan Cekirdekler

Bu dosyalar online co-op icin guclu bir temel veriyor:

| Dosya | Durum | Not |
|---|---|---|
| `src/online_pvp_game.py` | Cok olgun | Lobby UI, code join, metadata hardening, ready, session ping, disconnect grace, pause, rematch |
| `src/steam_networking.py` | Genel altyapi hazir | Lobby ve P2P transport katmani moddan bagimsiz |
| `src/coop_game.py` | Cok guclu | Shared 20x20 board, iki oyuncu state'i, freeze/unfreeze, event sistemi, `inject_remote_input()` |
| `src/coop_board.py` | Hazir | Midline, owner tracking, contribution mantigi |
| `src/online_coop_game.py` | Kismen var | Shell, state machine, host snapshot gonderimi ve guest render taslagi mevcut |
| `src/main.py` | State handler var | `online_coop` handler yazilmis ama menu baglantisi bilerek kapali |

### 3.2 Bugun Online Co-op'ta Zaten Yazilmis Olanlar

`src/online_coop_game.py` bos bir placeholder degil. Simdiden su parcalar var:

- `OnlineCoopState` state machine'i
- `_init_networking()`
- lobi menusu / waiting / ready-check / countdown / game over / disconnected ekranlari
- host tarafinda `CoopGame` olusturma
- host tarafinda board ve piece snapshot gonderme
- guest tarafinda snapshot cache ile cizim
- guest input'u `guest_input` mesaji olarak host'a gonderme
- rematch kabugu
- host tarafinda `CoopGame.inject_remote_input('P2', action)` kullanimi

Yani dogru yon secilmis durumda.

### 3.3 Ama Bugun Hala Kirik veya Yetersiz Olanlar

Online co-op dosyasi bugun release'e yakin degil. Temel sebepler:

1. `src/online_coop_game.py` mesajlari `self.net.poll_message()` ile cekiyor.
   `src/steam_networking.py` tarafinda boyle bir public API yok. Mevcut API `get_messages()`.

2. Co-op dosyasi `MsgType.GAME_START` ve `send_game_start()` kullaniyor.
   Oysa `steam_networking.py` icinde co-op icin ayrica `COOP_GAME_START` tanimlanmis. Protokol net degil.

3. Co-op dosyasinda PvP'deki sender validation yok.
   Bilinmeyen gonderici, stale opponent id veya lobby-member fallback mantigi tasinmamis.

4. Co-op dosyasinda PvP'deki private lobby metadata normalization ve deferred metadata akisi yok.
   Su anki co-op lobi listesi cok daha basit.

5. `main.py` tarafinda menu aksiyonu hala bilerek coming-soon toast gosteriyor.
   `tests/test_online_coop_menu_coming_soon.py` da bunu dogruluyor.

6. Co-op dosyasinda `session_accepted` ve `session_rejected` handler'lari bos.
   Halbuki Steam oturum bootstrap davranisi PvP'de kritik sekilde harden edilmis durumda.

7. `_on_lobby_joined()` su an dogrudan `READY_CHECK`'e geciyor.
   PvP'deki WAITING -> presence sync -> READY_CHECK zinciri daha dayanikli.

8. Freeze icin event var ama unfreeze icin acik bir event yok.
   Host snapshot'lar bunu tasiyabilir ama bilincli olarak ele alinmasi gerekiyor.

9. Guest state cache guncellemeleri icin sequence ve out-of-order korumasi zayif.
   PvP'deki `seq` mantigi kadar sert degil.

10. Co-op shell, PvP'nin yillar icinde kazandigi test korumalarini henuz miras almamis.

Kisacasi: yon dogru, ama kabuk yeterince sertlestirilmemis.

---

## 4. Eski Belgeler ile Bugunku Kod Arasindaki Durum

Repoda zaten iki onemli belge var:

- `docs/ONLINE_COOP_ANALIZ_VE_MIMARI.md`
- `docs/ONLINE_COOP_UYGULAMA_SIRASI_VE_FAZLARI.md`

Bu belgeler dogru yonde, fakat bugunku kod gercekligi ile beraber okunmali.

Bu yeni belgenin farki su:

- soyut teori degil
- bugunku dosyalarin gercek durumuna gore yazildi
- online PvP'de artik hangi parcalar olgun, hangileri co-op'a aynen tasinmali onu acikca ayiriyor
- mevcut `online_coop_game.py` icindeki drift ve kirik noktalarini isim vererek yaziyor

Bu belge, mevcut co-op docs'un yerine degil, onlari guncel koda baglayan uygulama notu olarak dusunulmeli.

---

## 5. Onerilen Mimari

### 5.1 V1 Mimarisi

V1 endless online co-op icin onerilen model:

```text
Host:
  tam CoopGame simule eder
  P1 local input alir
  P2 guest input'unu agdan alir
  tek dogru board state host'tadir
  periyodik snapshot gonderir

Guest:
  local tam simule etmez
  input yollar
  host'tan gelen board/piece/event snapshot'larini render eder
  otorite host'tadir
```

Bu, authoritative host modelidir.

### 5.2 Bu Repo Icin Neden Lockstep Degil?

Tam lockstep veya iki tarafli tam deterministik shared simulation bu repo icin V1'de yanlis secim olur.

Nedenleri:

- shared 20x20 board var, iki oyuncu ayni board'a etkide bulunuyor
- freeze ve unfreeze kararlari board uygunluguna bagli
- satir temizligi owner tracking ile birlikte yurutuluyor
- contribution yuzdeleri ve team score ayni olaydan turetiliyor
- hidden spawn ve pending unfreeze mantigi var
- `CoopGame` bugun zaten host-side injection'a uygun ama iki tarafli tam replay / reconciliation icin tasarlanmamis

PvP'deki gibi iki tarafin bagimsiz simulasyonu burada dogal degil. PvP'de iki board ayriydi. Burada board ortak.

### 5.3 Bu Repo Icin Neden Authoritative Host Dogru?

Su sebeplerle:

- `CoopGame` zaten tam local truth'u tasiyor
- `inject_remote_input()` zaten var
- `CoopBoard` zaten owner tracking yapiyor
- guest tarafina sadece render cache yaptirmak daha basit
- transport tarafi zaten PvP'de hazir
- V1 endless en hizli bu yolla cikar

Net karar:

- V1: full host authority
- V1.1: gerekirse hafif guest prediction
- V2: campaign ve daha zengin sync iyilestirmeleri

---

## 6. Hangi Parcalar PvP'den Ayni Sekilde Tasinmali?

### 6.1 Neredeyse Birebir Tasinacaklar

`src/online_pvp_game.py` icinden su kisimlar co-op'a buyuk oranda aynen tasinmali veya ortaklastirilmali:

1. `_init_networking()` kalibi
2. `_send_session_ping()`
3. `_send_ready_signal()`
4. `_on_session_accepted()`
5. `_on_session_rejected()`
6. `_sync_lobby_presence_from_members()`
7. private/public lobby metadata normalization yardimcilari:
   - `_parse_lobby_bool`
   - `_normalize_lobby_visibility`
   - `_resolve_private_lobby_code`
   - gerekirse `_resolve_lobby_display_state`
8. `_on_lobby_found()` icindeki deferred metadata mantigi
9. `_on_lobby_data_updated()` icindeki cache refresh ve pending code join tamamlama mantigi
10. `_on_lobby_list_complete()` icindeki lobby merge ve flicker onleme mantigi
11. private join authorization ve joined-lobby access validation mantigi
12. disconnect grace mantigi
13. pause sirasinda aktif input'u temizleme mantigi
14. rematch reset mantigi
15. cleanup ve Steam pump resume kalibi

### 6.2 Mantik Ayni, Icerik Farkli Olacaklar

Bunlar PvP'den yapisal olarak alinmali ama payload ve gameplay anlami co-op'a gore degismeli:

1. `_process_messages()`
2. `_check_both_ready()`
3. `_start_countdown()`
4. `_start_game()`
5. `update()` icindeki state-machine akisi
6. `draw()` icindeki PLAYING branch'i
7. game over ve disconnected ekranlari

### 6.3 Tasinmamasi Gerekenler

Bunlari oldugu gibi co-op'a kopyalamamak lazim:

- PvP'nin kendi `Board()` ve tek oyuncu parca mantigi
- garbage attack mantigi
- majority winner mantigi
- opponent board display-only 10x20 modelinin aynisi
- PvP skor semantigi

Co-op'ta ana truth `CoopGame` olmali, PvP'deki local tetris loop degil.

---

## 7. Hangi Parcalar Yerel Co-op'tan Korunmali?

`src/coop_game.py` ve `src/coop_board.py` icinden su seyler korunmali ve yeni online mantigin merkezi olmali:

1. `CoopBoard`
   - 20x20 ortak grid
   - owner tracking
   - midline kurali
   - clear katkisi

2. `CoopGame`
   - iki oyunculu aktif piece state'i
   - freeze / pending unfreeze / spawn kurallari
   - team score / total lines / level
   - line clear ve game over mantigi
   - event emitter (`_event_listeners`)
   - `inject_remote_input(player, action)`

3. `CoopGame` icindeki mevcut eventler
   - `lines_cleared`
   - `score_update`
   - `player_frozen`
   - `time_update`

4. `CoopGame._render_game()`
   - host tarafinda mevcut local render pipeline'i korumak icin

Kritik ilke:

Online co-op'ta `CoopGame.handle_input()` ana kontrol merkezi olmamali.

Onun yerine:

- host local P1 input'unu kendi mapping'i ile `inject_remote_input('P1', action)` uzerinden gecirmeli
- guest input da hostta `inject_remote_input('P2', action)` ile uygulanmali

Boylece online modda tek bir input yuzeyi olur.

---

## 8. En Dogru Uygulama Modeli: PvP Shell + Host Otoriteli Match Core

### 8.1 State Makinesi

PvP ile ayni state zinciri korunmali:

```text
LOBBY_MENU
  -> WAITING
  -> READY_CHECK
  -> COUNTDOWN
  -> PLAYING
  -> GAME_OVER / DISCONNECTED
```

Bu zincir degistirilmemeli.

### 8.2 Lobby Akisi

PvP ile ayni ana davranis korunmali:

1. create private
2. create public
3. invite friend
4. join by code
5. browse public lobby list

Ancak metadata anahtarlari co-op icin farkli olmali:

- `game = quadrix`
- `mode = coop`
- `sub_mode = endless`
- `visibility = public | private`
- `requires_code = 1 | 0`
- `lobby_code = 6 haneli kod`
- `host_name = ...`
- `metadata_ready = 0 -> 1`

### 8.3 Ready ve Session Bootstrap

PvP'deki transport davranisi aynen lazim. Cunku bu gameplay degil, Steam transport problemi.

Bu nedenle co-op tarafinda da sunlar olmali:

- `session_ping`
- `_session_established`
- `_ready_send_pending`
- ready resend timer
- game-start retry timer

Ready akisi su sekilde olmali:

1. iki oyuncu lobide bulusun
2. WAITING durumunda member listeden presence sync yap
3. READY_CHECK'e gec
4. her taraf ready mesaji gondersin
5. host reliable `COOP_GAME_START` gondersin
6. gonderim basarisizsa retry etsin
7. countdown baslasin

Bugun `online_coop_game.py` icindeki `_start_countdown()` hem countdown baslatip hem game_start gonderiyor. Bu, PvP'deki kadar guvenli degil.

Dogru model:

- `_check_both_ready()` host tarafinda start paketini yollar
- `_start_countdown()` sadece countdown state'ini acar

---

## 9. Onerilen Mesaj Protokolu

### 9.1 Kanal Kurali

Tum mesajlar `CHANNEL_GAME` uzerinden gitmeli.

Bu PvP'de zaten zorunlu hale getirilmis durumda. Co-op tarafi da farkli kanal denememeli.

### 9.2 V1 Icin Zorunlu Mesajlar

| Mesaj | Yon | Reliable | Icerik | Not |
|---|---|---|---|---|
| `ready` veya co-op esleniği | iki yonlu | evet | hazir durumu | transport acisindan PvP ile ayni davranis |
| `coop_start` | host -> guest | evet | seed, sub_mode, opsiyonel config | `COOP_GAME_START` kullanilmali |
| `guest_input` | guest -> host | evet | action, seq, timestamp | host P2 input olarak uygular |
| `coop_board` | host -> guest | hayir | grid, owners, score, lines, level, frozen flags, seq | periyodik tam board snapshot |
| `coop_piece` | host -> guest | hayir | p1/p2 current, next, hold, ghost, input_ack, seq | daha sik guncellenir |
| `coop_event` | host -> guest | evet | pause, resume, game_over, disconnect-warning vb. | olay tabanli state degisiklikleri |
| `rematch` | iki yonlu | evet | basit rematch istegi | PvP ile benzer |

### 9.3 V1.1 Icin Tavsiye Edilen Mesajlar

Bunlar V1'de de faydali olabilir ama zorunlu ilk adim degil:

| Mesaj | Yon | Reliable | Amac |
|---|---|---|---|
| `coop_full_state` | host -> guest | evet | reconnect veya zorunlu resync |
| `coop_resync_request` | guest -> host | evet | seq kopuklugu veya cache corruption durumunda |

### 9.4 Payload Tasarimi

`coop_board` icin onerilen alanlar:

```json
{
  "type": "coop_board",
  "seq": 17,
  "grid": [[0, [255,0,0], 0, ...], ...],
  "owners": [["", "P1", "", ...], ...],
  "team_score": 4200,
  "total_lines": 11,
  "level": 3,
  "fall_speed": 780.0,
  "p1_frozen": false,
  "p2_frozen": true
}
```

`coop_piece` icin onerilen alanlar:

```json
{
  "type": "coop_piece",
  "seq": 44,
  "input_ack": 103,
  "p1_current": {"si": 2, "x": 3, "y": 5, "r": 1},
  "p2_current": {"si": 6, "x": 13, "y": 1, "r": 0},
  "p1_next_si": 0,
  "p2_next_si": 4,
  "p1_hold_si": -1,
  "p2_hold_si": 3,
  "p1_ghost_y": 15,
  "p2_ghost_y": 18
}
```

`guest_input` icin onerilen alanlar:

```json
{
  "type": "guest_input",
  "seq": 103,
  "action": "move_left",
  "ts": 1777795.23
}
```

### 9.5 Kritik Kural

Co-op start mesaji ile PvP start mesaji ayni isimde tutulmamali.

Bugun kodda `COOP_GAME_START` tanimli ama kullanilmiyor. Bu drift kapatilacak.

En temiz yol:

- `steam_networking.py` icinde `send_coop_start(...)` yardimcisi ekle
- `online_coop_game.py` sadece `COOP_GAME_START` islesin

Alternatif olarak tek ortak `GAME_START` kullanilabilir, ama o zaman `COOP_GAME_START` sabiti silinmeli. Ikisini birden birakmak yanlis.

---

## 10. Host Tarafinin Frame Akisi Nasil Olmali?

Host tarafi `PLAYING` state'inde asagidaki mantikla calismali:

```text
1. net.tick()
2. gelen mesajlari isle
   - guest_input
   - pause / rematch / session event
3. guest_input geldiyse CoopGame'e P2 olarak inject et
4. local host input geldiyse CoopGame'e P1 olarak inject et
5. coop_game.update(dt)
6. kritik degisim varsa hemen snapshot gonder
7. periyodik board snapshot gonder
8. daha sik piece snapshot gonder
9. game_over olduysa reliable game_over olayi gonder
10. draw host-side local CoopGame render
```

### 10.1 Kritik Degisim Oldugunda Hemen Snapshot Gonder

Yalnizca timer bazli gonderim yeterli degil. Asagidaki olaylardan sonra host hemen state gondermeli:

- line clear
- freeze
- unfreeze
- game over
- pause / resume
- rematch reset
- reconnect sonrasi ilk frame

Neden?

Shared board oldugu icin guest ekrani 100ms bile stale kalinca co-op hissi bozulur. Ozellikle freeze ve unfreeze durumlari kritik.

### 10.2 Unfreeze Boslugu

Bugun `CoopGame` icinde `player_frozen` eventi var, ama `player_unfrozen` yok.

Bu iki yolla cozulebilir:

1. En hizli yol:
   host her frame `p1_frozen/p2_frozen` onceki deger ile simdiki degeri kiyaslar, degisti ise `coop_event` gonderir.

2. Daha temiz yol:
   `CoopGame._do_unfreeze()` icine `player_unfrozen` eventi eklenir.

V1 icin 1. yol daha hizli, V1.1 icin 2. yol daha temizdir.

---

## 11. Guest Tarafinin Frame Akisi Nasil Olmali?

Guest tarafi V1'de tam simulasyon yapmamalidir.

Akis:

```text
1. net.tick()
2. host'tan gelen mesajlari isle
3. board cache guncelle
4. piece cache guncelle
5. event cache guncelle
6. draw_guest_view() ile render et
```

### 11.1 V1 Icin Guest Prediction Zorunlu mu?

Hayir.

V1'i cikarabilmek icin prediction zorunlu degil.

Dogru sira:

1. once host authority ve dogru state
2. sonra latency hissi gerekirse prediction

Prediction'ı erkenden eklemek, daha co-op akisi stabil degilken hata ayiklamayi zorlastirir.

### 11.2 Guest'te Prediction Ne Zaman Eklenmeli?

Asagidaki kosullar saglandiysa:

- lobby akisi stabil
- start/restart stabil
- board desync yok
- disconnect ve pause stabil
- host snapshot'lari dogru

Ondan sonra su hafif prediction eklenebilir:

- guest local input'u anlik gecici gosterir
- host `input_ack` ile en son islenen input'u bildirir
- ack disi kalan prediction kuyrugu replay edilir

Ama bu V1 icin sart degil.

---

## 12. Co-op Lobby Sistemini PvP'den Nasil Tasimak Lazim?

### 12.1 Buyuk Hata: Basit Lobi Listesi Yazmak

Co-op icin sifirdan daha basit bir lobi tarayici yazmak yanlis olur.

Sebep:

- PvP tarafinda metadata propagasyon yarislari zaten goruldu
- private lobby'ler metadata gec gelirken unknown gorunebiliyor
- `get_lobby_data()` ile `get_lobby_data_for(lobby_id, key)` farki kritik
- authorization, deferred entries ve stale unknown temizligi coktan cozuldu

Bu nedenle co-op browse ekraninda PvP'nin olgunlasmis metadata akisi kullanilmali.

### 12.2 Mutlaka Tasinacak Lobby Hardening Davranislari

Su davranislar co-op'ta da olmali:

1. lobi metadata'si unknown ise hemen private/public karari verme
2. unknown lobi kartini bir sure gorunur tut
3. `get_lobby_data_for(lobby_id, key)` kullan
4. join sonrasi access validation yap
5. authorized private join state tut
6. pending code join ve pending browser join akisini ayir
7. partial propagation durumunda yanlis public karari verme
8. stale validated id'yi lobby degisince sifirla
9. invite-authorized lobi id mantigini koru
10. worldwide scan fallback mantigini koru

PvP testlerinde bunlarin cogu zaten dogrulaniyor. Co-op tarafina da ayni test ailesi tasinmali.

---

## 13. Disconnect ve Pause Davranisi Co-op'ta Nasil Olmali?

### 13.1 Disconnect Grace

PvP'deki disconnect grace mantigi co-op'a aynen lazim.

Akis:

1. `lobby_member_left` veya `lobby_member_disconnected`
2. host/guest hemen maci bitirmesin
3. `pending_disconnect_steam_id` set et
4. grace timer baslat
5. gelen ilk gecerli mesaj grace'i temizlesin
6. timer dolarsa `DISCONNECTED`

Co-op'ta fark su:

- PvP'deki gibi kazanan ilan etmek yerine mac bozuldu state'i daha dogru olabilir
- V1 endless icin oyunu durdurup menuye dondurmek yeterli

### 13.2 Pause

Pause'ta su kural korunmali:

- pause transport-level olarak ortak state'tir
- active movement state sifirlanir
- DAS / soft drop temizlenir

Co-op'ta host authority oldugu icin en temiz model:

- guest `pause_request` gonderir
- host pause kararini verir
- host reliable `coop_event: pause/resume` gonderir

Host disindaki hic kimse local authoritative pause karari vermemeli.

### 13.3 Focus Loss

PvP'de focus loss pause davranisi test ile korunuyor.

Online co-op'ta da aynisi eklenmeli:

- focus kaybi host tarafinda pause tetiklemeli
- host peer'e pause event gondermeli
- aktif input state sifirlanmali

---

## 14. Mevcut `online_coop_game.py` Icin Dogrudan Teknik Duzeltme Listesi

Bu kisim en pratik kisım. Kod yazmaya baslayinca ilk yapilacaklar bunlar.

### 14.1 Ilk Duzeltmeler

1. `poll_message()` kullanimini kaldir.
   `for msg in self.net.get_messages():` modeline gec.

2. sender validation'i PvP'den kopyala.
   - opponent id bilinmiyorsa lobby member icinden bind et
   - bilinmeyen sender'i ignore et
   - disconnect pending sender'dan gelen ilk mesaji grace temizligi icin kullan

3. `GAME_START` vs `COOP_GAME_START` drift'ini kapat.

4. `_on_session_accepted()` ve `_on_session_rejected()` doldur.

5. `_on_lobby_joined()` akisini PvP ile hizala.
   Dogrudan READY_CHECK yerine:
   - WAITING
   - metadata refresh
   - access validation
   - presence sync

6. private/public metadata helper'larini PvP'den tası.

7. `_request_lobby_list()` icine PvP benzeri filtre ve fallback mantigi ekle.

8. `_check_both_ready()` icine game-start retry mantigi ekle.

9. `_start_countdown()` sadece countdown acsin.

10. board ve piece state cache icin seq takibi ekle.

### 14.2 Orta Seviye Duzeltmeler

11. `coop_event` akisini standartlastir.

12. `player_frozen` ve unfreeze degisimlerini host tarafinda diff ile yayinla.

13. reconnect veya kritik fark durumunda reliable tam snapshot gonder.

14. host tarafinda immediate board push noktalarini arttir.

15. guest render yolunu mevcut custom draw ile baslat, sonra istersen `CoopGame` ortak render helper'larina yaklastir.

### 14.3 Yapilmamasi Gereken Kisa Yol

Sadece `steam_networking.py` icine `poll_message()` ekleyip bugunku co-op dosyasini calistirmaya calismak dogru degil.

Bu semptomu kapatir, ama asil drift'i kapatmaz.

Dogru olan:

- co-op dosyasini PvP ile ayni queue modeline cekmek

---

## 15. `steam_networking.py` Icin Onerilen Degisiklikler

Bu dosya buyuk mimari degisim istemiyor. Ama kucuk ve temiz eklemeler faydali olur.

### 15.1 Tavsiye Edilen Yardimci Metotlar

V1 icin faydali yardimcilar:

- `send_coop_start(seed, config=None)`
- `send_coop_board_state(data)`
- `send_coop_piece_state(data)`
- `send_coop_event(event_name, data=None)`

Neden?

- yanlis `type` yazma riskini azaltir
- `online_coop_game.py` icindeki raw string daginikligini toplar
- test yazmayi kolaylastirir

### 15.2 Yapilmamasi Gerekenler

- co-op icin ayrica farkli networking wrapper yazma
- farkli kanal sistemi kurma
- bridge'e erken asamada dokunma

Bridge degisimi ancak su durumda gundeme gelmeli:

- mevcut event payload'i gerekli metadata'yi vermiyorsa
- mevcut `request_lobby_data` ve `get_lobby_data_for` ile gereken bilgi alinmiyorsa

Bugunku kod durumuna gore V1 icin buna gerek yok.

---

## 16. `main.py` ve Menu Baglantisi Nasil Acilmali?

Bugun `menu.py` online_coop action'u uretiyor, ama `main.py` bu action'da bilerek coming-soon toast gosteriyor.

Bu zincir su sekilde acilmali:

1. `src/main.py` icinde `action == 'online_coop'` branch'i gerçek state gecisine cevrilecek.
2. `OnlineCoopGame(...)` instantiate edilecek.
3. `state = 'online_coop'` yapilacak.
4. `tests/test_online_coop_menu_coming_soon.py` ya guncellenecek ya da yerine yeni test yazilacak.

Yeni beklenen davranis testi:

- `online_coop` action'u `OnlineCoopGame` olusturuyor mu?
- `state` degisiyor mu?
- handler `_handle_online_coop` instance'i yasatabiliyor mu?

Menu tarafinda buyuk bir UI degisimi gerekmiyor. Aksiyon zaten hazir.

---

## 17. Kod Tekrarini Azaltmak Icin Simdi Ne Yapilmamali?

Bu asamada en tehlikeli hata su olur:

- PvP ve co-op'taki ortak kisimlari hemen buyuk bir base class'a cekmek

Bu fikir teorik olarak guzel gorunur ama pratikte su riskleri tasir:

- ayni anda cok fazla hareketli parca degisir
- bug kaynagini bulmak zorlasir
- online co-op daha calismadan buyuk refactor acilir

Dogru sira:

1. once online co-op'u calistir
2. sonra ortak kod alanlarini gor
3. sonra ufak helper extraction yap

Yani:

- once kopyala ve uyarla
- sonra sadeleştir

V1 icin bu daha dogru.

---

## 18. Faz Faz Uygulama Sirasi

### Faz 1: Online Co-op'u Gercekten Ac

Hedef:

- menu action'u gercek state'e gecsin
- `OnlineCoopGame` instantiate edilsin
- crash etmeden shell acilsin

Dokunulacak yerler:

- `src/main.py`
- `tests/test_online_coop_menu_coming_soon.py`

### Faz 2: Mevcut Co-op Shell'i PvP Seviyesinde Sertlestir

Hedef:

- message queue API drift kapansin
- sender validation gelsin
- session accepted/rejected dolsun
- ready retry ve session ping gelsin

Dokunulacak yerler:

- `src/online_coop_game.py`
- gerekirse `src/steam_networking.py`

### Faz 3: Lobby Metadata ve Join-by-Code Hardening

Hedef:

- PvP'deki private/public metadata sistemi co-op'a gelsin
- browse list unknown metadata ve deferred entry mantigi gelsin
- access validation gelsin

Dokunulacak yerler:

- `src/online_coop_game.py`
- test dosyalari

### Faz 4: Match Core'u Dogrula

Hedef:

- host `CoopGame` tam oynatsin
- guest input hostta P2 olarak uygulansin
- board ve piece snapshot'lari duzgun aksin

Dokunulacak yerler:

- `src/online_coop_game.py`
- opsiyonel kucuk yardimcilar icin `src/coop_game.py`

### Faz 5: Freeze, Unfreeze, Pause, Disconnect Hardening

Hedef:

- freeze state kaybi olmasin
- unfreeze state stale kalmasin
- reconnect grace calissin
- pause ortak state olarak tutarli olsun

### Faz 6: Visual Parity ve UX

Hedef:

- guest board gostergesi daha guzel hale gelsin
- host ve guest ekranlari yerel coop'a daha cok benzesin
- durum mesajlari ve reconnect bilgi metinleri netlessin

### Faz 7: Prediction Gerekiyorsa Sonradan

Hedef:

- sadece gercekten input latency sorunu varsa hafif prediction eklemek

---

## 19. Test Stratejisi

Online co-op icin sifirdan test kulturü kurma. PvP testlerini klonlayip co-op'a uyarlamak daha dogru.

### 19.1 Tasinacak Test Aileleri

PvP'den co-op'a uyarlanacak ana test aileleri:

1. lobby visibility metadata
2. ready sender rebind
3. disconnect grace
4. game_start retry
5. pause freezes input
6. lobby presence fallback
7. code search validation
8. message validation

### 19.2 Co-op'a Ozel Yeni Testler

Ek olarak bunlar yazilmali:

1. guest input hostta `inject_remote_input('P2', action)` cagiriyor mu?
2. host `CoopGame` game over oldugunda guest `GAME_OVER` goruyor mu?
3. `coop_board` snapshot guest cache'i duzgun guncelliyor mu?
4. stale `coop_piece` seq ignore ediliyor mu?
5. freeze ve unfreeze state degisimi guest'e tasiniyor mu?
6. rematch state her iki tarafta sifirlaniyor mu?
7. menu branch instantiate yapiyor mu?
8. `poll_message` gibi olmayan API'lere bagimlilik kaldi mi?

### 19.3 Minimum Kabul Test Paketi

Asgari olarak bunlar gecmeden online co-op acilmamali:

- private lobby join by code
- public browse list
- ready -> countdown -> playing
- guest input -> host P2 hareketi
- line clear -> guest score update
- freeze -> game over
- disconnect grace
- rematch

---

## 20. En Buyuk Riskler

### Risk 1: Lobby Tarafini Basitlestirip PvP Hardening'i Kaybetmek

Bu en buyuk hata olur.

Co-op da ayni Steam ortaminda calisacak. PvP'deki cross-platform metadata ve join sorunlari co-op'ta da ayni sekilde geri gelir.

### Risk 2: Guest'te Tam Simulasyon Yapmaya Calismak

Bu V1'i yavaslatir ve desync riskini buyutur.

### Risk 3: Protokol Sabitlerini Temizlemeden Yola Cikmak

`GAME_START` ile `COOP_GAME_START` gibi cift isimler ileride karmaşa yaratir.

### Risk 4: `online_coop_game.py`'i sadece semptom duzeltmeleriyle ayakta tutmaya calismak

Ornek:

- sirf `poll_message()` icin yeni API eklemek
- sender validation yazmamak
- metadata validation tasimamak

Bu yol, bug'lari sadece gizler.

### Risk 5: Ilk gunden campaign'i dahil etmeye calismak

Endless V1 stabil olmadan campaign online acilmamali.

---

## 21. Acik Tasarim Tercihleri

Bu noktalarda net tercih oneriyorum:

### 21.1 `COOP_GAME_START` Kullan

Karar:

- co-op kendi start mesajina sahip olsun

### 21.2 `poll_message` Ekleme, `get_messages` Kullan

Karar:

- co-op dosyasi PvP ile ayni queue modeline gelsin

### 21.3 Prediction Sonraya Kalsin

Karar:

- once correctness, sonra responsiveness

### 21.4 Lobby Browse Mantigi PvP'den Tasinsin

Karar:

- basit yeni browse list yazilmasin

### 21.5 Buyuk Refactor Sonraya Kalsin

Karar:

- once calisan co-op
- sonra ortak base/helper dusun

---

## 22. Ilk Kodlama Sprint'i Icin Net Gorev Listesi

Eger bu isi yarin kodlamaya baslayacaksan, ilk sprint gorevleri su olmali:

1. `main.py` icinde online_coop branch'ini gercek state'e bagla.
2. coming-soon testini kaldir veya yeni davranisa gore guncelle.
3. `online_coop_game.py` icindeki `poll_message()` kullanimini `get_messages()` ile degistir.
4. sender validation ve pending disconnect temizligini PvP'den tası.
5. `GAME_START` / `COOP_GAME_START` kararini ver ve tek protokole in.
6. session accepted/rejected ve ready resend akisini PvP'den tası.
7. `_on_lobby_joined()` ve lobby metadata akisini PvP ile hizala.
8. private/public browse ve code join akisini PvP seviyesine cek.
9. host tarafinda kritik olaylardan sonra immediate snapshot gonder.
10. freeze/unfreeze state degisimi icin net bir host diff mekanizmasi ekle.
11. PvP test ailelerinden en kritiklerini co-op icin klonla.

Bu sprint sonunda hedef su olmali:

- iki makina ayni private lobby'de bulusabiliyor
- ready-check calisiyor
- host baslatinca iki tarafta da countdown aciliyor
- guest input hostta P2 olarak oynuyor
- host state'i guest'te izlenebiliyor

Bu nokta geldikten sonra gorsel kalite ve prediction konusuna gecilir.

---

## 23. Definition of Done

Online co-op'u gercekten acmak icin asagidaki kosullar saglanmali:

1. menu'den moda girilebilmeli
2. private lobby create / join by code calismali
3. public lobby browse calismali
4. invite flow calismali
5. ready-check ve countdown tutarli calismali
6. host tarafinda tam `CoopGame` simule edilmeli
7. guest input hostta P2 olarak uygulanmali
8. guest ekraninda ortak board dogru gorunmeli
9. line clear / score / freeze / unfreeze state'i tasinmali
10. pause ve disconnect akisi bozulmamali
11. rematch calismali
12. bilinmeyen sender mesajlari ignore edilmeli
13. private lobby yetkisiz giris kabul etmemeli
14. cross-platform metadata gecikmelerinde browse list yalanci karar vermemeli

Bu maddeler saglanmadan online co-op'u acmak erken olur.

---

## 24. Son Karar

Bu projede online co-op'u yapmanin en dogru yolu su:

- online PvP'yi yeniden yazmak degil
- online co-op'u sifirdan yeni bir sistem kurmak degil
- online PvP shell'ini alip `CoopGame` etrafinda host-otoriteli bir mac katmanina donusturmek

En kritik teknik tavsiye:

`src/online_coop_game.py` dosyasini bugunku yarim haliyle “tamamlanacak bir taslak” olarak gormelisin, ama lobby/network hardening tarafinda kesinlikle `src/online_pvp_game.py`'nin olgun akisini referans alip birebir tasimalisin.

Co-op'un zor kismi Steam degil.

Co-op'un zor kismi, shared board state'in tek dogru otoritesini kurmak.

Bu repo icin o otorite hostta calisan `CoopGame` olmalidir.