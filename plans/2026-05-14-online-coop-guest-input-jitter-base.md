# Online Co-op Guest Input Lag/Jitter — Düzeltme Notları ve Mimari Baz

**Tarih:** 2026-05-14
**Kapsam:** `src/online_coop_game.py`, `src/coop_game.py` (kontrol), `src/steam_networking.py` (kontrol), `steamworks/steam_net_bridge/steam_net_bridge.cpp` (kontrol)
**İlgili testler:** `tests/test_online_coop_network_flow.py`, `tests/test_online_pvp_piece_sync.py`, `tests/test_steam_net_bridge_private_metadata_source.py`
**Türkçe işaret:** Aşağıdaki tüm açıklamalar gelecekteki bakım için referans alınmak üzere yazılmıştır. Bu dosya tek başına Online Co-op senkronizasyon mimarisini ve neyin neden yapıldığını anlamaya yetecek seviyededir.

---

## 1. Problem Tanımı

Online Co-op'ta guest oyuncu iki ayrı semptom yaşıyordu:
- **Görsel jitter:** P2 parçası yana/aşağıya hareket ederken titreyip "geri-ileri" sıçrıyordu.
- **Algılanan input gecikmesi:** Tuşa basıldıktan sonra parça oynar gibi görünüp ~140ms sonra geri atlamak. Kullanıcı "tuş gecikmesi" olarak yorumluyordu, fakat asıl sorun reconciliation'dı.

Online PvP'de bu sorunlar yoktu çünkü PvP "her oyuncu kendi parçasını sahipleniyor" modeline kuruluydu.

---

## 2. Mevcut Mimari (Düzeltme Öncesi)

### 2.1. Roller

| Rol | Sorumluluk |
|---|---|
| **Host** | `CoopGame` simülasyonunu çalıştırır. Lock, line clear, freeze, score, level, game over otoriter. P1 inputlarını lokal olarak işler, P2 için guest'ten input/state alır. |
| **Guest** | Kendi tarafında lokal `CoopGame` instance'ı tutar (yalnız render + P2 prediction için). Gerçek otoriter durum host'tan gelir. |

### 2.2. Mesaj akışı

```
Guest                         Host
=====                         ====
                                
keydown(K_LEFT)                
  ├─► _predict_guest_input    
  │     inject_remote_input('P2','move_left')   # lokal P2 anında oynar
  │                                              
  ├─► _send_guest_input ───────► GUEST_INPUT(seq, action)        [reliable, CONTROL]
  │                                  └─► _last_guest_input_seq = seq
  │                                       inject_remote_input('P2', action)
  │                                       _last_input_ack_seq = seq
  │                                                    
  └─► _send_guest_piece_state ─► GUEST_PIECE_STATE(seq, p2_curr) [unreliable, STATE]
                                       └─► _apply_guest_authoritative_piece_state
                                            board.is_valid_position_for_player → reject?
                                            _last_guest_piece_state_seq = seq

her frame:                      her frame:
                                _send_board_state(unreliable, STATE)  # 200ms heartbeat
                                _send_piece_state(unreliable, STATE)  # 50ms heartbeat
                                _send_lock_event(reliable, CONTROL)   # event-driven
                                _send_game_event(reliable, CONTROL)   # pause/freeze
```

### 2.3. Channel haritası

```
CHANNEL_GAME    = 0   (legacy/genel)
CHANNEL_STATE   = 1   (unreliable: COOP_BOARD_STATE, COOP_PIECE_STATE,
                       GUEST_PIECE_STATE, BOARD_STATE, PIECE_POSITION)
CHANNEL_CONTROL = 2   (reliable: GUEST_INPUT, COOP_GAME_START,
                       COOP_GAME_CONFIG, COOP_LOCK_EVENT,
                       COOP_GAME_EVENT, READY, GAME_OVER, REMATCH)
```

C++ bridge her tick'te üç kanalı **ayrı ayrı** poll eder (`_poll_incoming_messages(0/1/2)` — `steam_net_bridge.cpp:542-544`). Bu sayede reliable kontrol mesajları unreliable state akışını **bloklamaz** (head-of-line blocking yok).

### 2.4. Reliability mapping

C++ bridge:

```cpp
int flags = reliable
    ? k_nSteamNetworkingSend_ReliableNoNagle
    : k_nSteamNetworkingSend_UnreliableNoDelay;
```

`ReliableNoNagle` = TCP-benzeri sıralı/garantili teslim, ama Nagle algoritması olmadan (tek byte mesajları bile hemen gönder).
`UnreliableNoDelay` = UDP-benzeri en hızlı yol, sıralama yok, kayıp tolere edilir.

### 2.5. Identity ve sahiplik

`CoopGame` instance'ı `remote_authority_players: set[str]` tutar. `'P2' in remote_authority_players` ise:
- `_player_uses_remote_active_authority('P2')` → True
- Host CoopGame `update()` içinde **P2 için**: gravity skip, DAS skip, soft-drop skip
- P2 active piece tamamen guest'in `GUEST_PIECE_STATE` mirror'ı tarafından sürülür

Guest authoritative piece sync default açık (`_guest_authoritative_piece_sync_enabled = True`); host `_start_game` içinde `'P2'`yi `remote_authority_players`'a ekler (`online_coop_game.py:3741-3744`).

---

## 3. Kök Sebep Analizi

### 3.1. Jitter (görsel titreme)

Eski `_should_keep_locally_simulated_p2` aşağıdaki gibiydi:

```python
if prediction_ms >= prediction_cap and (dx > 0 or dy > 0):
    return False  # snap-back
if last_authoritative_ms > 0.0
   and host_elapsed_ms - last_authoritative_ms >= prediction_cap
   and (dx > 0 or dy > 0):
    return False  # snap-back
return dx <= 3 and dy <= 6
```

`_GUEST_LOCAL_PREDICTION_MAX_MS = 140ms`, host piece heartbeat 50ms.

Akıcı oyunda:
1. Guest P2'yi 140ms tahmin eder → cap dolar.
2. Sonraki host heartbeat'i (eski snapshot ile) gelir → `False` döner → P2 host'un eski pozisyonuna **geri çekilir**.
3. Bir sonraki frame guest tekrar tahmin yapar → ileri sıçrar.
4. Tekrar heartbeat → tekrar geri çekilir.

**Görsel sonuç:** Sürekli ileri-geri zıplayan parça.

### 3.2. Algılanan input gecikmesi

- `_predict_guest_input` zaten anında lokal mutasyon yapıyor → input prediction sağlıklı.
- "Lag" hissi aslında jitter'ın yan etkisi: parça oynayıp geri sıçrayınca kullanıcı "tuşa bastım, sonra geri atıldı" diye algılıyor.

### 3.3. Lock noktasında küçük takılma

Guest hard_drop yapıp `_guest_pending_inputs` listesine ekledi → `pending_board_mutation = True` → `_apply_guest_render_cache` board snapshot'ı atlıyor. Host kilidi gerçekleştirip `COOP_LOCK_EVENT` gönderse bile, `input_ack` işleyene kadar pending listede `hard_drop` duruyor → bir sonraki snapshot da bloke kalıyor.

### 3.4. SDR yüksek RTT'de unacked grace yetersiz

`_GUEST_PIECE_ACK_GRACE_S = 0.75s`. SDR relay 200-400ms RTT verince mirror ack bu süreyi aşabiliyor → `_should_keep_unacked_guest_p2` False dönüyor → identity-based koruma yoksa snap-back tetiklenebiliyordu.

---

## 4. Düzeltme — Mimari Karar ve Uygulama

### 4.1. Mimari karar: PvP-style local active-piece ownership

**Kural:** Guest authoritative piece sync açıkken (`_guest_authoritative_piece_sync_enabled = True`) ve P2 piece **identity** (active `si` + next `si` + hold `si`) host snapshot'ıyla aynıyken, **pozisyon farkı veya cap ne olursa olsun** host snapshot uygulanmaz. Identity değişimi (lock/spawn/hold-swap) early-return yapıp host'a re-sync sağlar.

Bu kural Online PvP'nin "kendi `my_piece`'in lokal sahipliği" örüntüsünün co-op P2'ye uyarlanmış halidir. PvP'de board paylaşılmadığı için bu otomatik olarak çalışır; co-op'ta board paylaşıldığı için sadece **active piece** üzerinde uygulanır, board ve lock olayları hâlâ host-otoriter.

### 4.2. `src/online_coop_game.py::_should_keep_locally_simulated_p2`

```python
# Yeni davranış (özet):
if int(incoming.si) != int(local.si): return False        # identity değişti → host kazansın
if local.next_si != incoming.next_si: return False
if local.hold_si != incoming.hold_si: return False

if self._guest_authoritative_piece_sync_enabled:
    return True  # PvP-style ownership: lokal P2 korunur

# Authority kapalı (legacy fallback) — eski cap'li davranış burada kalır.
if prediction_ms >= prediction_cap and (dx>0 or dy>0): return False
if host_elapsed_gap >= prediction_cap and (dx>0 or dy>0): return False
return dx <= 3 and dy <= 6
```

**Neden burası kritik:** `_apply_guest_render_cache` host piece snapshot'ı uygulamadan önce sırayla şu kontrolleri yapar:
1. `pending_guest_inputs` varsa → P2'ye dokunma.
2. `_should_keep_unacked_guest_p2` → ack-bazlı koruma.
3. `_should_keep_locally_simulated_p2` → identity-bazlı koruma.

Üçü de False dönerse host snapshot uygulanır. Yeni davranışla 3. katman authority açıkken her zaman True döner; jitter penceresi tamamen kapanır.

### 4.3. COOP_PIECE_STATE replay protection

```python
# Önce: if seq < self._guest_piece_seq: continue
# Sonra: if seq <= self._guest_piece_seq: continue
```

Aynı seq'in tekrar uygulanmasını engeller. PvP'de eşit seq kabul edilir çünkü BOARD_STATE içine gömülü piece field'ı PIECE_POSITION ile çakışabiliyor. Co-op'ta board ve piece **ayrı** seq dizilerinde olduğu için eşit seq sadece gerçek replay anlamına gelir; drop güvenli.

### 4.4. Lock event'te pending P2 board-mutating input temizliği (Risk 1)

```python
def _apply_guest_lock_event(self, data: dict):
    if str(data.get('player', '')) == 'P2':
        pending = getattr(self, '_guest_pending_inputs', None)
        if isinstance(pending, list) and pending:
            self._guest_pending_inputs = [
                (seq, action) for seq, action in pending
                if str(action or '') not in ('hard_drop', 'hold')
            ]
    ...
```

**Etki:** Lock event reliable+CONTROL olduğu için host'un guest'in hard_drop'unu zaten uyguladığını biliyoruz. Pending listede tutmak `pending_board_mutation` üzerinden bir sonraki board snapshot'ı bloke ediyordu. Lock onayı geldiğinde proaktif temizlik yaparak re-sync gecikmesini sıfırladık.

### 4.5. SDR-friendly ack grace (Risk 2)

```python
self._GUEST_PIECE_ACK_GRACE_S = 2.5  # önce 0.75
```

Identity-based koruma zaten yedek olarak çalışıyor; ack-bazlı yolu yüksek RTT için açık tutmak iki katmanlı savunma sağlıyor. Worst-case'de identity match yolu hâlâ geçersiz state'i bloke ediyor → ack gecikmesi tehlikeli değil.

### 4.6. `from __future__ import annotations` (Risk 3 — test izolasyonu)

`src/game.py`'ye eklendi. PEP 604 union (`X | None`) kullanan 30+ annotation runtime'da artık string olarak değerlendiriliyor; pygame test mock'larının import sırasında tetiklediği `unsupported operand type(s) for |: 'function' and 'NoneType'` hatasını tamamen ortadan kaldırıyor. `game.py`'de runtime annotation evaluation (`get_type_hints`, dataclass, vb.) yok, güvenli.

### 4.7. Test mock'una eksik UI sabitleri

`tests/test_coop_campaign.py::_UIColors` mock'una `NEON_MAGENTA`, `NEON_ORANGE`, `NEON_GREEN`, `TEXT_*`, `GLASS_*`, `BUTTON_*`, `SLIDER_BG` eklendi. `campaign_ui.py` import edildiğinde gerekli sabitler hazır.

---

## 5. Online PvP ile Mimari Karşılaştırma

| Boyut | Online PvP | Online Co-op (final) |
|---|---|---|
| Active piece sahipliği | `my_piece` her zaman lokal (kendi tahtanda yaşar) | P2: guest authoritative; host CoopGame `remote_authority_players={'P2'}` ile P2 gravity/DAS uygulamaz |
| Board sahipliği | Kendi board'un lokal otoriter | Paylaşılan board host-otoriter |
| Pozisyon yayını | `PIECE_POSITION` 33ms coalescing, seq guard, unreliable+STATE | `GUEST_PIECE_STATE` 20ms heartbeat + event flush; `COOP_PIECE_STATE` 50ms heartbeat |
| Stale paket reddi | `seq >= _opponent_piece_seq` (BOARD_STATE içine gömülü piece çakışmasını önler) | `seq <= _guest_piece_seq` ⇒ drop |
| Snapshot çakışması | Board snapshot içinde piece var; lokal piece asla overwrite edilmez | Board ve piece ayrı snapshot; identity match'te P2 lokal kalır |
| Lock zamanı | Lokal lock + reliable lock event | Host otoriter lock + reliable `COOP_LOCK_EVENT` |
| Garbage hattı | Reliable garbage attack | (yok — co-op'ta yardımlaşma var, çöp yok) |

**Tasarım sebebi:** Co-op paylaşılan board nedeniyle host-otoriter olmak zorunda; ama active piece sahipliğini guest'e bırakmak hem hissiyatı PvP seviyesine getirir hem de lock validation'ı host'ta tutarak desync'i imkansızlaştırır.

---

## 6. Sequence/Ack Akış Diyagramı

```
Guest tarafında üç ayrı sayaç ailesi:

(A) Input akışı (Guest → Host):
    _guest_input_seq          : guest'in son ürettiği input numarası
    _guest_pending_inputs[]   : henüz host tarafından ack'lenmemiş inputlar (last 64)
    _last_input_ack_seq       : host'un onayladığı en yüksek seq
                                (host: gelen GUEST_INPUT(seq) için clamp/max,
                                 guest: COOP_PIECE_STATE/COOP_BOARD_STATE'in
                                 'input_ack' field'ından okunur)

(B) Piece mirror akışı (Guest → Host):
    _guest_piece_state_out_seq      : guest'in son gönderdiği mirror seq
    _last_host_guest_piece_ack_seq  : host'un onayladığı mirror seq
                                      (host snapshot'larındaki 'guest_piece_ack')
    _guest_piece_unacked_since      : ack beklenen mirror'un timestamp'i

(C) Host snapshot akışı (Host → Guest):
    _board_state_seq          (host)
    _piece_state_seq          (host)
    _guest_board_seq          (guest tarafında: kabul edilen son board seq)
    _guest_piece_seq          (guest tarafında: kabul edilen son piece seq)
    _last_guest_piece_state_seq (host tarafında: kabul edilen son guest mirror seq)

Pending input ack flow:
  guest sends: GUEST_INPUT(seq=N, action="move_left")
              _guest_pending_inputs.append((N, "move_left"))
  host applies, _last_input_ack_seq = max(prev, N)
  host sends: COOP_PIECE_STATE(seq=M, input_ack=N)
  guest receives: _consume_guest_input_ack(N) → siler tüm pending(seq <= N)

Replay protection:
  host: GUEST_PIECE_STATE(seq <= _last_guest_piece_state_seq) → reject + resend host truth
  guest: COOP_PIECE_STATE(seq <= _guest_piece_seq) → drop
  guest: COOP_BOARD_STATE(seq < _guest_board_seq) → drop
```

---

## 7. Heartbeat ve Send Frekansları

| İsim | Yön | Periyot | Reliability | Açıklama |
|---|---|---|---|---|
| `_BOARD_STATE_INTERVAL` | Host→Guest | 200ms | unreliable | Force-full snapshot heartbeat. Asıl board değişimi event-driven (`_send_board_state` lock/freeze sonrası). |
| `_PIECE_STATE_INTERVAL` | Host→Guest | 50ms | unreliable | Piece signature değişmediyse atlanır (`_push_piece_state_if_changed`). |
| `_GUEST_PIECE_STATE_INTERVAL` | Guest→Host | 20ms | unreliable | Guest mirror heartbeat; signature değişmediyse send atlanır. |
| `_PIECE_POSITION_INTERVAL_MS` (PvP) | Both | 33ms | unreliable | Karşılaştırma referansı. |
| `STATE_SNAPSHOT_INTERVAL` (PvP) | Both | 100ms | unreliable | Karşılaştırma referansı. |
| `_GUEST_LOCAL_PREDICTION_MAX_MS` | Guest internal | 140ms | n/a | Sadece authority kapalı yolda etkili. Authority açıkken bilgi olarak güncellenir, kullanılmaz. |
| `_GUEST_PIECE_ACK_GRACE_S` | Guest internal | 2.5s | n/a | SDR-friendly grace. Bu sürede ack gelmezse `_should_keep_unacked_guest_p2` False döner ama identity check hâlâ True dönebilir. |

---

## 8. Reconciliation Karar Ağacı (Guest tarafında host piece snapshot geldiğinde)

```
Host snapshot geldi (COOP_PIECE_STATE)
│
├─ seq <= _guest_piece_seq?
│     YES → drop (replay protection)
│     NO  → cache'le, _guest_piece_seq güncelle
│
└─ Bir sonraki frame _apply_guest_render_cache:
   │
   ├─ pending_guest_inputs varsa (input_ack < son seq)?
   │     YES → P2'ye DOKUNMA
   │     NO  → devam
   │
   ├─ _should_keep_unacked_guest_p2?  (mirror henüz host tarafından ack'lenmedi
   │                                   ve grace içindeyiz ve identity match)
   │     YES → P2'ye DOKUNMA
   │     NO  → devam
   │
   └─ _should_keep_locally_simulated_p2?
         │
         ├─ identity (si + next + hold) farklı?
         │     YES → P2'YE HOST SNAPSHOT'INI UYGULA (re-sync)
         │     NO  → devam
         │
         ├─ authority açık?
         │     YES → P2'ye DOKUNMA (PvP-style ownership)
         │     NO  → legacy cap kontrolü
         │           (cap aşıldıysa snap-back, değilse dx<=3/dy<=6 toleransı)
         │
         └─ host snapshot uygulandığında: prediction_ms = 0,
                                          last_authoritative_elapsed_ms = host_elapsed_ms
```

---

## 9. Test Kapsamı

`tests/test_online_coop_network_flow.py` güncel kapsam (toplam 72 test):

**Input responsiveness:**
- `test_online_coop_filters_held_key_repeat_before_relaying_guest_movement`
- `test_online_coop_guest_predicts_before_first_host_snapshot`
- `test_online_coop_guest_held_key_repeat_sends_exactly_one_input`
- `test_online_coop_directional_das_stop_preserves_opposite_direction`

**Authority açık → identity-based koruma:**
- `test_online_coop_guest_authority_holds_p2_across_prediction_cap_with_identity_match`
- `test_online_coop_guest_authority_holds_p2_across_host_elapsed_cap_with_identity_match`
- `test_online_coop_guest_authority_resyncs_when_host_signals_new_piece_identity`
- `test_online_coop_guest_authority_keeps_p2_against_repeated_heartbeats_no_jitter`
- `test_online_coop_guest_keeps_local_p2_across_matching_host_heartbeat`
- `test_online_coop_guest_keeps_locally_simulated_p2_across_matching_host_heartbeat`

**Authority kapalı → legacy cap fallback:**
- `test_online_coop_guest_accepts_small_host_correction_after_prediction_cap`
- `test_online_coop_guest_accepts_small_host_correction_after_host_elapsed_cap`
- `test_online_coop_guest_accepts_large_host_p2_correction`
- `test_online_coop_guest_authority_disabled_falls_back_to_legacy_tolerance`

**Sequence/ack/replay:**
- `test_online_coop_guest_drops_stale_coop_piece_state_with_equal_seq`
- `test_online_coop_guest_input_ack_only_removes_acknowledged_pending_inputs`
- `test_online_coop_guest_input_ack_ignores_decreasing_ack_seq`
- `test_online_coop_guest_ignores_out_of_order_board_snapshots`

**Lock event ve pending temizlik:**
- `test_online_coop_lock_event_clears_pending_p2_board_mutating_inputs`
- `test_online_coop_lock_event_for_p1_does_not_clear_p2_pending`

**Board snapshot guard'ları:**
- `test_online_coop_guest_board_snapshot_does_not_wipe_p2_with_pending_inputs`
- `test_online_coop_guest_keeps_predicted_p2_piece_after_input_ack`

**SDR ayarları:**
- `test_online_coop_default_guest_piece_ack_grace_supports_high_rtt`

**Pause/güvenlik:**
- `test_online_coop_pause_blocks_host_gameplay_input`
- `test_online_coop_pause_blocks_guest_gameplay_input`
- `test_online_coop_host_acks_but_ignores_guest_input_while_paused`

---

## 10. Manuel İki İstemcili Steam Smoke Test Listesi

Otomatik suite SDR/relay üzerindeki gerçek davranışı kapsayamadığı için aşağıdaki manuel akış release öncesi yapılmalıdır.

- [ ] Host: Online Co-op lobi oluştur, davet linkini paylaş.
- [ ] Guest: code/Steam invite ile katıl, ready basın → countdown başladığını doğrula.
- [ ] Guest hızlıca art arda left/right/rotate basıp bıraksın → her tuşta P2 anında, jitter olmadan oynamalı.
- [ ] Guest soft drop (S/Down) tutsun → P2 pürüzsüz aşağı kaymalı, geri sıçrama yok.
- [ ] Guest sol/sağ tuşunu DAS tetikleyene kadar tutsun → DAS başlangıcı ve repeat akışı pürüzsüz olmalı.
- [ ] Guest hard drop spamı (Space) → her bastığında piece yere düşmeli, host'tan reliable lock event ve yeni parça gelmeli, "phantom geri sıçrama" olmamalı.
- [ ] Guest hold (E/RShift) → swap anında olmalı, host'un onayladığı yeni shape görünmeli.
- [ ] Host kendi P1'iyle oynarken guest'in P2 hareketini izle → host görünümünde de jitter olmamalı.
- [ ] Line clear sırasında ekran sallantı/parçacık efektleri her iki tarafta tetiklenmeli.
- [ ] Pause/resume (ESC) host tarafında toggle, guest tarafından `pause_request` → her iki tarafta UI senkron donmalı/açılmalı.
- [ ] Game over / freeze geçişi → her iki tarafta görsel ve skor senkron olmalı.
- [ ] Steam relay/SDR (mümkünse iki farklı şehirde) ile yüksek RTT senaryosunda tekrarla → yüksek latency'de bile guest input akıcı kalmalı, lock noktasında en fazla küçük tek-frame düzeltme görünmeli.
- [ ] Network spike senaryosu (host tarafında geçici bant darlığı): guest aynı pozisyona yapışır gibi görünebilir; host akışı düzeldiğinde lock event gelirse re-sync düzgün gelmeli.

---

## 11. Gelecek İçin Yol Haritası ve Bakım Notları

### 11.1. Gelecek mühendis için kritik invariantlar

Aşağıdakiler **kırılırsa** jitter/snap-back geri gelir:

1. `_guest_authoritative_piece_sync_enabled` default `True` kalmalı.
2. `_start_game` host tarafında `'P2'`yi `coop_game.remote_authority_players`'a eklemeli.
3. `_should_keep_locally_simulated_p2` identity match durumunda authority açıkken `True` dönmeli.
4. `_apply_guest_authoritative_piece_state` host tarafında `board.is_valid_position_for_player` validation'ını yapmalı (geçersiz state'i `_reject_guest_authoritative_piece_state` ile geri reddetmeli).
5. `COOP_LOCK_EVENT` reliable kalmalı (CHANNEL_CONTROL).
6. `_apply_guest_lock_event` P2 lock'ta pending hard_drop/hold'u temizlemeye devam etmeli.
7. Bridge `OnSessionRequest` callback'i `AcceptSessionWithUser` çağırmaya devam etmeli.

### 11.2. Eklenmesi düşünülebilecek geliştirmeler

| Öneri | Not |
|---|---|
| **Server reconciliation overlay** (geliştirici tooling): Authority açıkken her host snapshot için `dx`/`dy` değerini debug HUD'da gösteren toggle. SDR testlerinde drift'i ölçmek için. | Sadece `--dev` flag'i ardında olsun. |
| **Adaptive guest piece interval**: Network kalitesine göre `_GUEST_PIECE_STATE_INTERVAL`'i 20ms ↔ 33ms arası dinamik. | RTT/loss telemetrisi gerekir; şu an gerekli değil. |
| **Mirror coalescing**: PvP'nin `_pending_piece_position_dirty` örüntüsü co-op guest mirror'a port edilebilir. Şu an signature equality early-return zaten benzer iş yapıyor; ekstra `_pending_dirty` flag'i son frame'de kaybolan değişimleri yakalar. | Düşük öncelik. |
| **Lock validation logging**: `_reject_guest_authoritative_piece_state` ne sıklıkta tetikleniyor? Eğer >1Hz ise ya validation çok agresif ya da guest tahmininde bug var. | `--diag` modunda counter eklensin. |
| **Co-op campaign'a aynı pattern'i uygulamak**: Şu an `coop_campaign_mode.py` lokal, ama online co-op campaign eklenirse bu doküman temel referans. | Roadmap. |

### 11.3. Tehlike bölgeleri (regresyon riski yüksek)

- `_handle_gameplay_keydown` / `_handle_gameplay_keyup` sıralaması: Önce held-key check, sonra `_predict_guest_input`, sonra `_send_guest_input`, sonra `_flush_guest_piece_mirror_for_action`. Bu sıra bozulursa duplicate input veya kaybolan mirror olur.
- `_send_guest_piece_state` içindeki `_guest_control_sync_pending` kontrolü: hard_drop/hold pending iken mirror göndermek host'ta validation fail tetikleyebilir → reject loop. Bu kontrol kaldırılmamalı.
- `_apply_guest_render_cache` içindeki üç katmanlı koruma sırası (pending → unacked → identity) **bu sırada** kalmalı. Sıra değişirse jitter geri gelebilir.
- `_guest_pending_inputs` her erişimde `[-64:]` ile cap'lenmeli (memory + ack mantığı).
- Pause/disconnect noktalarında `_held_gameplay_keys.clear()` ve DAS state reset (`_freeze_active_gameplay_input`) çağrılmalı; aksi halde resume sonrası phantom DAS kalır.

### 11.4. Performans notları

- `_send_guest_piece_state` **signature equality** (önceki vs şimdiki) check yapıyor; aynı state ardışık send'lerde paket gönderilmez. Bu sayede 20ms heartbeat tetiklendiğinde bile gerçek değişim yoksa trafik üretmiyor.
- `_send_board_state` `_capture_semantic_board_cells` ile delta hesaplıyor; tüm board grid yerine sadece değişen hücreler gönderiliyor. 200ms heartbeat'te `force_full=True` ile periyodik full snapshot atılarak kalıcı desync engelleniyor.
- `_push_piece_state_if_changed` host signature değişmediyse send atlamasıyla `_PIECE_STATE_INTERVAL=50ms` tavanını aşmaz.

### 11.5. Test izolasyonu için bilgi

`src/game.py`'de `from __future__ import annotations` eklendi. Bu **bütün dosyadaki annotation'ları string olarak değerlendiriyor**. Eğer ileride `game.py`'de runtime annotation evaluation yapan kod (örn. `dataclass`, `pydantic`, `get_type_hints` ile çağrılan fonksiyon) eklenirse:
- Ya `from __future__ import annotations`'ı kaldır ve PEP 604 union'ları `Optional[T]` ile değiştir,
- Ya da o spesifik annotation'ları `Annotated[T, ...]` veya runtime-string olarak ele al.

`tests/test_coop_campaign.py::_UIColors` mock'u eksik attribute eklenince geçti. Eğer ileride `campaign_ui.py` yeni `UIColors.X` referansı eklerse, bu mock güncellenmeli — yoksa yine sıralama bağımlı failure olur.

---

## 12. Hızlı Referans

### Test komutları

```bash
# Hedeflenen suite
python -m pytest tests/test_online_coop_network_flow.py -q

# Geniş regresyon
python -m pytest tests/test_online_coop_network_flow.py \
                 tests/test_online_pvp_piece_sync.py \
                 tests/test_online_pvp_message_validation.py \
                 tests/test_steam_net_bridge_private_metadata_source.py \
                 tests/test_coop.py \
                 tests/test_coop_campaign.py -q
```

### Değişen dosyalar (bu PR)

| Dosya | Değişiklik özü |
|---|---|
| `src/online_coop_game.py` | Identity-based P2 ownership, COOP_PIECE_STATE replay, lock event pending temizliği, ack grace 2.5s |
| `src/game.py` | `from __future__ import annotations` |
| `tests/test_online_coop_network_flow.py` | +12 yeni test |
| `tests/test_coop_campaign.py` | `_UIColors` mock genişletildi |

### Ana referans noktaları (kod)

| Sembol | Konum |
|---|---|
| `_should_keep_locally_simulated_p2` | `src/online_coop_game.py:3015` |
| `_should_keep_unacked_guest_p2` | `src/online_coop_game.py:3076` |
| `_apply_guest_authoritative_piece_state` | `src/online_coop_game.py:2944` |
| `_apply_guest_render_cache` | `src/online_coop_game.py:3170` |
| `_apply_guest_lock_event` | `src/online_coop_game.py:3316` |
| `_predict_guest_input` | `src/online_coop_game.py:4352` |
| `_send_guest_input` | `src/online_coop_game.py:4395` |
| `_send_guest_piece_state` | `src/online_coop_game.py:2914` |
| `_handle_gameplay_keydown` | `src/online_coop_game.py:1980` |
| `inject_remote_input` | `src/coop_game.py:2498` |
| `_player_uses_remote_active_authority` | `src/coop_game.py:1953` |
| Bridge send flag mapping | `steamworks/steam_net_bridge/steam_net_bridge.cpp:497-498` |
| Channel polling | `steamworks/steam_net_bridge/steam_net_bridge.cpp:542-544` |
| Session accept | `steamworks/steam_net_bridge/steam_net_bridge.cpp:1113` |

---

**Son söz:** Co-op senkronizasyonu üç katmanlı bir savunma hattı kuruyor (pending → unacked → identity). Bu üç katmanın hangi koşulda hangisinin lokal P2'yi koruduğunu bilmek, gelecekte regresyonu hem teşhis hem de önleme kolaylığı sağlar. PvP'den farklı olarak co-op'ta board paylaşıldığı için **active piece sahipliği** ile **board otoritesi** ayrı tutulmalı; bu doküman bu ayrımın neden ve nasıl yapıldığının kayıtlı temelidir.
