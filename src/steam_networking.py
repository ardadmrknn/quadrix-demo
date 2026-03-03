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
from typing import Any, Callable

# ---------- C++ Bridge import ----------

_bridge = None
_bridge_available = False

def _try_import_bridge():
    """C++ köprü modülünü yükle."""
    global _bridge, _bridge_available
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # steam_api64.dll / libsteam_api.dylib arama yoluna DLL dizinlerini ekle
    # (bridge modülü link-time'da bu DLL'e bağımlı)
    _dll_dirs_added: list[Any] = []
    if sys.platform == 'win32':
        dll_search_dirs = []
        # PyInstaller bundle
        if getattr(sys, '_MEIPASS', None):
            dll_search_dirs.append(sys._MEIPASS)
        # Proje kökü
        dll_search_dirs.append(project_root)
        # dll/win64 alt dizini
        dll_search_dirs.append(os.path.join(project_root, 'dll', 'win64'))
        for d in dll_search_dirs:
            if os.path.isdir(d):
                try:
                    _dll_dirs_added.append(os.add_dll_directory(d))
                except OSError:
                    pass
    elif sys.platform == 'darwin':
        for sub in ('dll/osx', '.'):
            d = os.path.join(project_root, sub)
            if os.path.isdir(d) and d not in os.environ.get('DYLD_LIBRARY_PATH', ''):
                os.environ['DYLD_LIBRARY_PATH'] = d + ':' + os.environ.get('DYLD_LIBRARY_PATH', '')

    try:
        import steam_net_bridge as snb
        _bridge = snb
        _bridge_available = True
        return True
    except ImportError:
        # Proje kökünden de dene (build sonrası .pyd burada olabilir)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        try:
            import steam_net_bridge as snb
            _bridge = snb
            _bridge_available = True
            return True
        except ImportError:
            print("[SteamNet] steam_net_bridge.pyd bulunamadi. Derleme gerekli.")
            print("           steamworks/steam_net_bridge/build.bat calistirin.")
            _bridge_available = False
            return False

_try_import_bridge()


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
# NOT: C++ bridge şu an yalnızca kanal 0'ı polluyor (_poll_incoming_messages).
# Tüm mesajlar CHANNEL_GAME (0) üzerinden gönderilmelidir.
# C++ tarafı düzeltildiğinde kanal ayrımı tekrar devreye alınabilir.

CHANNEL_GAME = 0       # Tüm mesajlar — C++ bridge tek kanal polluyor
CHANNEL_STATE = 0      # (Geçici: 0 — C++ çoklu kanal desteği eklenince 1 yapılacak)
CHANNEL_CONTROL = 0    # (Geçici: 0 — C++ çoklu kanal desteği eklenince 2 yapılacak)


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

    @property
    def available(self) -> bool:
        """C++ bridge mevcut mu?"""
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
        return self._bridge_instance is not None and self._bridge_instance.is_in_lobby()

    # ============ Lifecycle ============

    def init(self) -> bool:
        """Steam networking başlat. SteamAPI_Init() zaten çağrılmış olmalı."""
        if not _bridge_available:
            print("[SteamNet] C++ bridge mevcut değil.")
            return False

        try:
            self._bridge_instance = _bridge.SteamNetBridge()
            ok = self._bridge_instance.init()
            if ok:
                self._initialized = True
                self._my_steam_id = self._bridge_instance.get_my_steam_id()
                print(f"[SteamNet] Başlatıldı. Steam ID: {self._my_steam_id}")
            return ok
        except Exception as e:
            print(f"[SteamNet] init hatası: {e}")
            return False

    def shutdown(self):
        """Temizle."""
        if self._bridge_instance:
            self._bridge_instance.leave_lobby()
            self._bridge_instance = None
        self._initialized = False
        self._state = 'idle'

    # ============ Lobi İşlemleri ============

    def create_lobby(self, max_members: int = 2, public: bool = False):
        """Yeni lobi oluştur. Sonuç poll_events() ile gelir."""
        if not self._bridge_instance:
            return
        self._state = 'lobby'
        self._is_host = True
        if public:
            self._bridge_instance.create_public_lobby(max_members)
        else:
            self._bridge_instance.create_lobby(max_members)
        print(f"[SteamNet] Lobi oluşturuluyor... (public={public})")

    def join_lobby(self, lobby_id: int):
        """Mevcut lobiye katıl."""
        if not self._bridge_instance:
            return
        self._state = 'lobby'
        self._is_host = False
        self._bridge_instance.join_lobby(lobby_id)
        print(f"[SteamNet] Lobiye katılınıyor: {lobby_id}")

    def leave_lobby(self):
        """Lobiden ayrıl."""
        if self._bridge_instance:
            self._bridge_instance.leave_lobby()
        self._state = 'idle'
        self._opponent_steam_id = 0
        self._opponent_name = ''
        self._lobby_id = 0
        print("[SteamNet] Lobiden ayrıldı.")

    def invite_friend(self):
        """Steam overlay arkadaş davet penceresi aç."""
        if self._bridge_instance:
            self._bridge_instance.invite_friend()

    def set_lobby_data(self, key: str, value: str):
        """Lobi metadata'sı ayarla."""
        if self._bridge_instance:
            self._bridge_instance.set_lobby_data(key, value)

    def get_lobby_data(self, key: str) -> str:
        """Lobi metadata'sı oku."""
        if self._bridge_instance:
            return self._bridge_instance.get_lobby_data(key)
        return ''

    def get_lobby_members(self) -> list[int]:
        """Lobideki üyelerin Steam ID listesi."""
        if self._bridge_instance:
            return self._bridge_instance.get_lobby_members()
        return []

    def request_lobby_list(self):
        """Public lobi listesini iste. Sonuç poll_events() ile gelir."""
        if self._bridge_instance:
            self._bridge_instance.request_lobby_list()

    # ============ Mesajlaşma ============

    def send(self, data: dict, reliable: bool = True, channel: int = CHANNEL_GAME):
        """Rakibe JSON mesaj gönder."""
        if not self._bridge_instance:
            return False
        payload = json.dumps(data, separators=(',', ':'))
        if self._opponent_steam_id:
            return self._bridge_instance.send_message(
                self._opponent_steam_id, payload, reliable, channel)
        else:
            return self._bridge_instance.send_message_to_lobby(
                payload, reliable, channel)

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
        self.send(board_data, reliable=False, channel=CHANNEL_STATE)

    def send_score_update(self, score: int, lines: int, level: int):
        """Skor güncellemesi gönder."""
        self.send({
            'type': MsgType.SCORE_UPDATE,
            'score': score,
            'lines': lines,
            'level': level,
        }, reliable=False, channel=CHANNEL_STATE)

    def send_game_start(self, seed: int, piece_sequence: list[int] | None = None):
        """Oyun başlat sinyali gönder (host gönderir)."""
        msg = {
            'type': MsgType.GAME_START,
            'seed': seed,
            'timestamp': time.time(),
        }
        if piece_sequence:
            msg['pieces'] = piece_sequence[:200]  # İlk 200 parça
        self.send(msg, reliable=True, channel=CHANNEL_CONTROL)

    def send_ready(self):
        """Hazır sinyali gönder."""
        self.send({'type': MsgType.READY}, reliable=True, channel=CHANNEL_CONTROL)

    def send_game_over(self, score: int = 0, lines: int = 0):
        """Oyun bitti sinyali gönder."""
        self.send({
            'type': MsgType.GAME_OVER,
            'score': score,
            'lines': lines,
        }, reliable=True, channel=CHANNEL_CONTROL)

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
            return self._bridge_instance.get_friend_persona_name(steam_id)
        return str(steam_id)
