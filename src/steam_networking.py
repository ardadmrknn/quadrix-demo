"""Quadrix Steam Networking — Python Wrapper

C++ Pybind11 köprü modülü (steam_net_bridge) üzerinden Steam Lobi ve
P2P mesajlaşma işlemlerini yöneten yüksek seviye Python arayüzü.

Kullanım (oyun döngüsünde):
    net = SteamNetworking()
    net.init()
    net.create_lobby()

    while running:
        net.tick()                       # Her frame çağır
        for ev in net.get_events():      # Olayları oku
            ...
        for msg in net.get_messages():   # Gelen mesajları oku
            ...
        net.send(target_id, payload)     # Mesaj gönder
"""
from __future__ import annotations

import json
import time
import sys
import os
from pathlib import Path
from typing import Any, Callable

# ---------- C++ Bridge import ----------

_bridge = None
_bridge_available = False
_bridge_import_attempted = False

# Windows: os.add_dll_directory() dönüş değerleri (context/handle objeleri) burada
# saklanır. Fonksiyon-local bir listede olsalardı GC tarafından geri alınabilirler;
# module-global tutarak DLL arama yolunun canlı kalması garanti edilir.
_dll_dirs: list[Any] = []


def _dedupe_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for path in paths:
        normalized = os.path.normpath(str(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _get_bridge_search_roots() -> list[str]:
    roots: list[str] = []

    meipass = getattr(sys, '_MEIPASS', None)
    if isinstance(meipass, str) and meipass:
        roots.append(meipass)

    exe_path = getattr(sys, 'executable', '')
    if exe_path:
        try:
            roots.append(str(Path(exe_path).resolve().parent))
        except Exception:
            pass

    try:
        roots.append(str(Path.cwd()))
    except Exception:
        pass

    try:
        roots.append(str(Path(__file__).resolve().parent.parent))
    except Exception:
        pass

    return _dedupe_paths(roots)


def _get_bridge_candidate_dirs() -> list[str]:
    candidates: list[str] = []
    for root_str in _get_bridge_search_roots():
        root = Path(root_str)
        candidates.extend([
            str(root / 'local_artifacts' / 'bridge'),
            str(root),
            str(root / 'dist'),
        ])

        bridge_build_root = root / 'steamworks' / 'steam_net_bridge'
        try:
            candidates.extend(
                str(path)
                for path in sorted(bridge_build_root.glob('build*/Release'))
            )
        except Exception:
            pass

    return _dedupe_paths(candidates)


def _get_bridge_dll_search_dirs() -> list[str]:
    candidates: list[str] = []

    meipass = getattr(sys, '_MEIPASS', None)
    if isinstance(meipass, str) and meipass and sys.platform == 'darwin':
        meipass_path = Path(meipass)
        candidates.extend([
            str(meipass_path.parent / 'Frameworks'),
            str(meipass_path.parent / 'MacOS'),
            str(meipass_path),
        ])

    for root_str in _get_bridge_search_roots():
        root = Path(root_str)
        candidates.append(str(root))
        if sys.platform == 'darwin':
            candidates.append(str(root / 'dll' / 'osx'))
        elif sys.platform.startswith('linux'):
            candidates.append(str(root / 'dll' / 'linux64'))
        else:
            candidates.append(str(root / 'dll' / 'win64'))

    candidates.extend(_get_bridge_candidate_dirs())
    return _dedupe_paths(candidates)


def _try_import_bridge():
    """C++ köprü modülünü yükle (lazy — yalnızca SteamNetworking.init() içinden çağrılır)."""
    global _bridge, _bridge_available, _bridge_import_attempted
    _bridge_import_attempted = True

    search_roots = _get_bridge_search_roots()
    bridge_candidate_dirs = _get_bridge_candidate_dirs()
    tried_paths: list[str] = []

    # steam_api64.dll / libsteam_api.dylib arama yoluna DLL dizinlerini ekle
    # (bridge modülü link-time'da bu DLL'e bağımlı)
    if sys.platform == 'win32':
        for d in _get_bridge_dll_search_dirs():
            tried_paths.append(d)
            if os.path.isdir(d):
                try:
                    # handle module-global listede saklanır — GC'den korunur
                    if hasattr(os, 'add_dll_directory'):
                        _dll_dirs.append(os.add_dll_directory(d))
                except OSError:
                    pass
    elif sys.platform == 'darwin':
        for d in _get_bridge_dll_search_dirs():
            tried_paths.append(d)
            if os.path.isdir(d):
                if d not in sys.path:
                    sys.path.insert(0, d)
                dyld = os.environ.get('DYLD_LIBRARY_PATH', '')
                if d not in dyld:
                    os.environ['DYLD_LIBRARY_PATH'] = d + ':' + dyld

    for root in search_roots:
        if os.path.isdir(root) and root not in sys.path:
            sys.path.insert(0, root)

    for bridge_dir in bridge_candidate_dirs:
        tried_paths.append(bridge_dir)
        if os.path.isdir(bridge_dir) and bridge_dir not in sys.path:
            sys.path.insert(0, bridge_dir)

    try:
        import steam_net_bridge as snb
        _bridge = snb
        _bridge_available = True
        return True
    except Exception as exc:
        print(f"[SteamNet] steam_net_bridge yuklenemedi: {exc}")
        print(f"           Denenen yollar: {_dedupe_paths(tried_paths)}")
        print("           build.bat ile derleyin veya artifacti local_artifacts/bridge altina koyun.")
        _bridge_available = False
        return False

# NOT: _try_import_bridge() artık import zamanında OTOMATİK çağrılmıyor.
# Bridge yüklemesi YALNIZCA SteamNetworking.init() içinde (lazy) gerçekleşir.


# ---------- Event ve Message tipleri ----------

class NetEvent:
    """Ağ olayı (lobi oluşturuldu, oyuncu katıldı vb.)"""
    __slots__ = ('type', 'steam_id', 'data', 'timestamp')

    def __init__(self, type: str, steam_id: int = 0, data: str = ''):
        self.type = type
        self.steam_id = steam_id
        self.data = data
        self.timestamp = time.monotonic()

    def __repr__(self):
        return f"<NetEvent {self.type} sid={self.steam_id} data='{self.data}'>"


class NetMessage:
    """Ağ mesajı (JSON payload)."""
    __slots__ = ('sender', 'payload', 'channel', 'timestamp')

    def __init__(self, sender: int, payload: str, channel: int = 0):
        self.sender = sender
        self.payload = payload
        self.channel = channel
        self.timestamp = time.monotonic()

    @property
    def data(self) -> dict:
        """Payload'ı JSON dict olarak döndür."""
        try:
            return json.loads(self.payload)
        except (json.JSONDecodeError, TypeError):
            return {'raw': self.payload}

    def __repr__(self):
        return f"<NetMessage from={self.sender} size={len(self.payload)}>"


# ---------- Kanal sabitleri ----------
# ÖNEMLİ: Platformlar arası uyumluluk için TÜM mesajlar CHANNEL_GAME (0)
# üzerinden gönderilir. C++ bridge üç kanalı da pollar ancak macOS (.so)
# ve Windows (.pyd) derlemeleri senkronizasyon dışında kalabilir; eski ikili
# dosyalar yalnızca kanal 0 yoklar. Bu yüzden kanal sabitleri tanımlıdır
# ama gönderimde hep CHANNEL_GAME kullanılır.

CHANNEL_GAME = 0       # TÜM mesajlar bu kanal üzerinden gönderilir
CHANNEL_STATE = 0      # (eski: 1) — artık CHANNEL_GAME ile aynı
CHANNEL_CONTROL = 0    # (eski: 2) — artık CHANNEL_GAME ile aynı


# ---------- Lobi tipleri (Steam ELobbyType) ----------

class LobbyType:
    PRIVATE = 0       # Sadece davet ile katılım
    FRIENDS_ONLY = 1  # Arkadaşlar görür, lobby ID ile katılım mümkün
    PUBLIC = 2        # Herkes görür ve katılabilir
    INVISIBLE = 3     # Arama sonuçlarında görünür ama arkadaş listesinde görünmez


# ---------- Lobi kodu yardımcıları ----------

def generate_lobby_code(lobby_id: int) -> str:
    """Steam lobby ID'sinden 6 haneli, insan-dostu lobi kodu üret.

    Kod, lobby_id'nin stabil bir hash'inden (hashlib) türetilir.
    Python hash() her process'te farklı seed kullandığı için
    hashlib.md5 tercih edilir — her iki tarafta aynı kodu üretir.
    """
    if not lobby_id:
        return '000000'
    import hashlib
    digest = hashlib.md5(str(lobby_id).encode('utf-8')).hexdigest()
    code = int(digest[:8], 16) % 1_000_000
    return f'{code:06d}'


# ---------- Mesaj tipleri ----------

class MsgType:
    """Standart mesaj tipleri."""
    # Kontrol
    READY           = 'ready'
    GAME_START      = 'game_start'
    GAME_OVER       = 'game_over'
    PAUSE_REQUEST   = 'pause_request'
    RESUME          = 'resume'
    REMATCH         = 'rematch'

    # Oyun
    GARBAGE_ATTACK  = 'garbage'
    PIECE_LOCKED    = 'piece_locked'
    BOARD_STATE     = 'board_state'
    SCORE_UPDATE    = 'score_update'
    ELIMINATED      = 'eliminated'
    PIECE_POSITION  = 'piece_pos'    # Aktif parça pozisyonu (gerçek zamanlı)


# ---------- Aktif instance takibi (shutdown sırasında temizlik için) ----------

_active_instances: list['SteamNetworking'] = []


def shutdown_all_instances():
    """Tüm aktif SteamNetworking instance'larını kapat.

    steam_integration.shutdown() ÖNCESİNDE çağrılmalı.
    Aksi halde C++ bridge destructor'ı, SteamAPI_Shutdown() sonrası
    geçersiz interface'lere erişmeye çalışır ve macOS'ta donma oluşur.
    """
    for inst in list(_active_instances):
        try:
            inst.shutdown()
        except Exception:
            pass
    _active_instances.clear()


# ---------- Ana Sınıf ----------

class SteamNetworking:
    """Yüksek seviye Steam Networking yöneticisi.

    Oyun döngüsüne entegre edilir:
        net = SteamNetworking()
        net.init()
        ...
        # Her frame:
        net.tick()
        events = net.get_events()
        messages = net.get_messages()
    """

    # Arka arkaya bu kadar exception olursa networking devre dışı bırakılır
    _TICK_ERROR_THRESHOLD: int = 5

    def __init__(self):
        self._bridge_instance = None
        self._initialized = False
        self._events: list[NetEvent] = []
        self._messages: list[NetMessage] = []
        self._event_handlers: dict[str, list[Callable]] = {}
        self._my_steam_id: int = 0
        self._opponent_steam_id: int = 0
        self._is_host: bool = False
        self._lobby_id: int = 0
        self._opponent_name: str = ''
        self._state: str = 'idle'  # idle, lobby, waiting, playing
        self._tick_consecutive_errors: int = 0  # Ardışık tick() hata sayacı

    @property
    def available(self) -> bool:
        """C++ bridge mevcut mu? Henüz denenmemişse lazy import tetikler."""
        if not _bridge_import_attempted:
            _try_import_bridge()
        return _bridge_available

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def my_steam_id(self) -> int:
        return self._my_steam_id

    @property
    def opponent_steam_id(self) -> int:
        return self._opponent_steam_id

    @property
    def opponent_name(self) -> str:
        return self._opponent_name

    @property
    def is_host(self) -> bool:
        return self._is_host

    @property
    def lobby_id(self) -> int:
        return self._lobby_id

    @property
    def state(self) -> str:
        return self._state

    @property
    def in_lobby(self) -> bool:
        if self._bridge_instance is not None:
            try:
                return self._bridge_instance.is_in_lobby()
            except Exception:
                pass
        return False

    # ============ Lifecycle ============

    def init(self) -> bool:
        """Steam networking başlat. SteamAPI_Init() zaten çağrılmış olmalı."""
        global _bridge_available, _bridge_import_attempted
        # Lazy import: bridge yalnızca ilk init() çağrısında yüklenir
        if not _bridge_import_attempted:
            _try_import_bridge()
        if not _bridge_available:
            print("[SteamNet] C++ bridge mevcut değil.")
            return False

        try:
            self._bridge_instance = _bridge.SteamNetBridge()
            ok = self._bridge_instance.init()
            if ok:
                self._initialized = True
                self._my_steam_id = self._bridge_instance.get_my_steam_id()
                _active_instances.append(self)
                print(f"[SteamNet] Başlatıldı. Steam ID: {self._my_steam_id}")
            else:
                print("[SteamNet] init() False döndürdü — bridge instance sıfırlanıyor")
                self._bridge_instance = None
            return ok
        except Exception as e:
            print(f"[SteamNet] init hatası: {e}")
            import traceback; traceback.print_exc()
            self._bridge_instance = None
            return False

    def shutdown(self):
        """Temizle. SteamAPI_Shutdown() öncesinde çağrılmalı."""
        if self._bridge_instance:
            try:
                # Önce C++ shutdown() dene (lobi çıkışı + pointer temizliği)
                self._bridge_instance.shutdown()
            except (AttributeError, TypeError):
                # Eski bridge sürümü — fallback
                try:
                    self._bridge_instance.leave_lobby()
                except Exception:
                    pass
            except Exception as e:
                print(f"[SteamNet] shutdown hatası: {e}")
            self._bridge_instance = None
        self._initialized = False
        self._state = 'idle'
        # Instance takibinden çıkar
        try:
            _active_instances.remove(self)
        except ValueError:
            pass

    # ============ Lobi İşlemleri ============

    def create_lobby(self, max_members: int = 2, public: bool = False):
        """Yeni lobi oluştur. Sonuç poll_events() ile gelir."""
        if not self._bridge_instance:
            return
        try:
            self._state = 'lobby'
            self._is_host = True
            if public:
                self._bridge_instance.create_public_lobby(max_members)
            else:
                # Özel lobi: Invisible (arama sonuçlarında filtre ile bulunabilir,
                # ancak arkadaş listesinde görünmez). Bu sayede hem Steam davet
                # hem de lobi kodu ile katılım çalışır.
                try:
                    self._bridge_instance.create_lobby_with_type(
                        LobbyType.INVISIBLE, max_members)
                except (AttributeError, TypeError):
                    # C++ bridge eski sürüm — fallback: FriendsOnly
                    try:
                        self._bridge_instance.create_lobby_with_type(
                            LobbyType.FRIENDS_ONLY, max_members)
                    except (AttributeError, TypeError):
                        self._bridge_instance.create_lobby(max_members)
            print(f"[SteamNet] Lobi oluşturuluyor... (public={public})")
        except Exception as e:
            print(f"[SteamNet] create_lobby hatası: {e}")
            import traceback; traceback.print_exc()

    def join_lobby(self, lobby_id: int):
        """Mevcut lobiye katıl."""
        if not self._bridge_instance:
            return
        try:
            self._state = 'lobby'
            self._is_host = False
            self._bridge_instance.join_lobby(lobby_id)
            print(f"[SteamNet] Lobiye katılınıyor: {lobby_id}")
        except Exception as e:
            print(f"[SteamNet] join_lobby hatası: {e}")

    def leave_lobby(self):
        """Lobiden ayrıl."""
        if self._bridge_instance:
            try:
                self._bridge_instance.leave_lobby()
            except Exception as e:
                print(f"[SteamNet] leave_lobby hatası: {e}")
        self._state = 'idle'
        self._opponent_steam_id = 0
        self._opponent_name = ''
        self._lobby_id = 0
        print("[SteamNet] Lobiden ayrıldı.")

    def invite_friend(self):
        """Steam overlay arkadaş davet penceresi aç."""
        if self._bridge_instance:
            try:
                self._bridge_instance.invite_friend()
            except Exception as e:
                print(f"[SteamNet] invite_friend hatası: {e}")

    def set_lobby_type(self, lobby_type: int):
        """Lobi tipini değiştir (LobbyType sabitleri kullanın)."""
        if self._bridge_instance:
            try:
                return self._bridge_instance.set_lobby_type(lobby_type)
            except (AttributeError, TypeError):
                pass
        return False

    def set_lobby_joinable(self, joinable: bool):
        """Lobinin katılıma açık olup olmadığını ayarla."""
        if self._bridge_instance:
            try:
                return self._bridge_instance.set_lobby_joinable(joinable)
            except (AttributeError, TypeError):
                pass
        return False

    def add_lobby_search_filter(self, key: str, value: str):
        """Sonraki request_lobby_list() çağrısına string filtre ekle."""
        if self._bridge_instance:
            try:
                self._bridge_instance.add_request_lobby_list_string_filter(key, value)
            except (AttributeError, TypeError):
                pass

    def set_lobby_data(self, key: str, value: str):
        """Lobi metadata'sı ayarla."""
        if self._bridge_instance:
            try:
                self._bridge_instance.set_lobby_data(key, value)
            except Exception as e:
                print(f"[SteamNet] set_lobby_data hatası: {e}")

    def get_lobby_data(self, key: str) -> str:
        """Lobi metadata'sı oku."""
        if self._bridge_instance:
            try:
                return self._bridge_instance.get_lobby_data(key)
            except Exception as e:
                print(f"[SteamNet] get_lobby_data hatası: {e}")
        return ''

    def get_lobby_data_for(self, lobby_id: int, key: str) -> str:
        """Belirli bir lobi için metadata oku."""
        if self._bridge_instance:
            try:
                return self._bridge_instance.get_lobby_data_for(lobby_id, key)
            except (AttributeError, TypeError):
                pass
            except Exception as e:
                print(f"[SteamNet] get_lobby_data_for hatası: {e}")
        return ''

    def get_lobby_members(self) -> list[int]:
        """Lobideki üyelerin Steam ID listesi."""
        if self._bridge_instance:
            try:
                return self._bridge_instance.get_lobby_members()
            except Exception as e:
                print(f"[SteamNet] get_lobby_members hatası: {e}")
        return []

    def request_lobby_list(self):
        """Lobi listesini iste. Sonuç poll_events() ile gelir."""
        if self._bridge_instance:
            try:
                self._bridge_instance.request_lobby_list()
            except Exception as e:
                print(f"[SteamNet] request_lobby_list hatası: {e}")

    def search_lobby_by_code(self, code: str):
        """Lobi koduna göre arama başlat.

        Önce lobby_code filtresi ekler, sonra request_lobby_list() çağırır.
        Sonuç poll_events() ile lobby_found / lobby_list_complete olarak gelir.
        """
        if self._bridge_instance:
            try:
                self._bridge_instance.add_request_lobby_list_string_filter(
                    'lobby_code', code.strip())
            except (AttributeError, TypeError):
                pass
            try:
                self._bridge_instance.request_lobby_list()
            except Exception as e:
                print(f"[SteamNet] search_lobby_by_code hatası: {e}")

    # ============ Mesajlaşma ============

    def send(self, data: dict, reliable: bool = True, channel: int = CHANNEL_GAME):
        """Rakibe JSON mesaj gönder."""
        if not self._bridge_instance:
            return False
        try:
            payload = json.dumps(data, separators=(',', ':'))
            if self._opponent_steam_id:
                return self._bridge_instance.send_message(
                    self._opponent_steam_id, payload, reliable, channel)
            else:
                return self._bridge_instance.send_message_to_lobby(
                    payload, reliable, channel)
        except Exception as e:
            print(f"[SteamNet] send hatası: {e}")
            return False

    def send_garbage(self, lines: int, gap_col: int = -1):
        """Rakibe çöp satır saldırısı gönder."""
        self.send({
            'type': MsgType.GARBAGE_ATTACK,
            'lines': lines,
            'gap': gap_col,
        }, reliable=True, channel=CHANNEL_GAME)

    def send_board_state(self, board_data: dict):
        """Tahta durumunu gönder (unreliable — kayıp packet önemsiz)."""
        board_data['type'] = MsgType.BOARD_STATE
        self.send(board_data, reliable=False, channel=CHANNEL_GAME)

    def send_piece_position(self, shape_index: int, x: int, y: int,
                            rotation: int, seq: int):
        """Aktif parça pozisyonunu gönder (unreliable, düşük gecikme)."""
        self.send({
            'type': MsgType.PIECE_POSITION,
            'si': shape_index,
            'x': x,
            'y': y,
            'r': rotation,
            'seq': seq,
        }, reliable=False, channel=CHANNEL_GAME)

    def send_score_update(self, score: int, lines: int, level: int):
        """Skor güncellemesi gönder."""
        self.send({
            'type': MsgType.SCORE_UPDATE,
            'score': score,
            'lines': lines,
            'level': level,
        }, reliable=False, channel=CHANNEL_GAME)

    def send_game_start(self, seed: int, piece_sequence: list[int] | None = None):
        """Oyun başlat sinyali gönder (host gönderir)."""
        msg = {
            'type': MsgType.GAME_START,
            'seed': seed,
            'timestamp': time.time(),
        }
        if piece_sequence:
            msg['pieces'] = piece_sequence[:200]  # İlk 200 parça
        return self.send(msg, reliable=True, channel=CHANNEL_GAME)

    def send_ready(self):
        """Hazır sinyali gönder."""
        return self.send({'type': MsgType.READY}, reliable=True, channel=CHANNEL_GAME)

    def send_game_over(self, score: int = 0, lines: int = 0):
        """Oyun bitti sinyali gönder."""
        self.send({
            'type': MsgType.GAME_OVER,
            'score': score,
            'lines': lines,
        }, reliable=True, channel=CHANNEL_GAME)

    # ============ Event Handler ============

    def on(self, event_type: str, handler: Callable):
        """Olay dinleyicisi ekle."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def _dispatch_event(self, event: NetEvent):
        """Olayı handler'lara dağıt."""
        handlers = self._event_handlers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"[SteamNet] Event handler hatası ({event.type}): {e}")

    # ============ Tick (Her frame) ============

    def tick(self):
        """Her frame çağrılmalı. Steam callback'leri işler, kuyruğu doldurur."""
        if not self._bridge_instance or not self._initialized:
            return

        try:
            # Steam callback'leri işle + gelen mesajları kuyrukla
            self._bridge_instance.run_callbacks()

            # C++ event'lerini Python'a aktar
            for ev in self._bridge_instance.poll_events():
                net_event = NetEvent(ev.type, ev.steam_id, ev.data)
                self._events.append(net_event)
                self._handle_internal_event(net_event)
                self._dispatch_event(net_event)

            # C++ mesajlarını Python'a aktar
            for msg in self._bridge_instance.poll_messages():
                self._messages.append(NetMessage(msg.sender, msg.payload, msg.channel))

            # Başarılı tick — ardışık hata sayacını sıfırla
            self._tick_consecutive_errors = 0

        except Exception as e:
            print(f"[SteamNet] tick hatası: {e}")
            self._tick_consecutive_errors += 1
            if self._tick_consecutive_errors >= self._TICK_ERROR_THRESHOLD:
                print(
                    f"[SteamNet] {self._tick_consecutive_errors} ardışık tick hatası — "
                    "networking devre dışı bırakılıyor."
                )
                self._initialized = False
                self._tick_consecutive_errors = 0
                self._events.append(
                    NetEvent('error', 0, 'networking_disabled')
                )

    def get_events(self) -> list[NetEvent]:
        """Birikmiş olayları döndür ve kuyruğu temizle."""
        events = self._events[:]
        self._events.clear()
        return events

    def get_messages(self) -> list[NetMessage]:
        """Birikmiş mesajları döndür ve kuyruğu temizle."""
        messages = self._messages[:]
        self._messages.clear()
        return messages

    # ============ İç Olay İşleme ============

    def _handle_internal_event(self, event: NetEvent):
        """Otomatik lobi durumu yönetimi."""
        if event.type == 'lobby_created':
            self._lobby_id = event.steam_id
            self._state = 'waiting'
            print(f"[SteamNet] Lobi oluşturuldu: {self._lobby_id}")

        elif event.type == 'lobby_joined':
            self._lobby_id = event.steam_id
            self._state = 'waiting'
            print(f"[SteamNet] Lobiye katılındı: {self._lobby_id}")
            # Rakibi bul
            self._find_opponent()

        elif event.type == 'lobby_member_joined':
            # Yeni üye katıldı — rakip olarak kaydet
            if event.steam_id != self._my_steam_id:
                self._opponent_steam_id = event.steam_id
                self._opponent_name = event.data or self._get_name(event.steam_id)
                print(f"[SteamNet] Rakip katıldı: {self._opponent_name} ({event.steam_id})")

        elif event.type == 'lobby_member_left' or event.type == 'lobby_member_disconnected':
            if event.steam_id == self._opponent_steam_id:
                try:
                    members = set(self.get_lobby_members() or [])
                except Exception:
                    members = set()
                if members and event.steam_id in members:
                    print(
                        f"[SteamNet] Gecici {event.type} ignore edildi: "
                        f"{event.steam_id} hala lobide gorunuyor"
                    )
                    return
                print(f"[SteamNet] Rakip ayrıldı: {self._opponent_name}")
                self._opponent_steam_id = 0
                self._opponent_name = ''
                self._state = 'waiting'

        elif event.type == 'join_requested':
            # Kullanıcı Steam overlay'den birinin oyununa katılmak istedi
            lobby_id = event.steam_id
            print(f"[SteamNet] Katılım isteği: lobi {lobby_id}")
            self.join_lobby(lobby_id)

        elif event.type == 'lobby_create_failed' or event.type == 'lobby_join_failed':
            print(f"[SteamNet] HATA: {event.type} — {event.data}")
            self._state = 'idle'

    def _find_opponent(self):
        """Lobideki rakibi bul."""
        members = self.get_lobby_members()
        for mid in members:
            if mid != self._my_steam_id:
                self._opponent_steam_id = mid
                self._opponent_name = self._get_name(mid)
                print(f"[SteamNet] Rakip bulundu: {self._opponent_name}")
                break

    def _get_name(self, steam_id: int) -> str:
        """Steam ID'den persona ismini al."""
        if self._bridge_instance:
            try:
                return self._bridge_instance.get_friend_persona_name(steam_id)
            except Exception as e:
                print(f"[SteamNet] get_friend_persona_name hatası: {e}")
        return str(steam_id)
