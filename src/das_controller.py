"""Paylaşılan DAS (Delayed Auto Shift) çekirdeği.

Bu modül tek oyunculu (``game.py``), yerel PvP (``pvp_game.py``) ve yerel
co-op (``coop_game.py``) modlarının ortak yatay-hareket tekrar mantığını tek
bir yerde toplar. Daha önce bu mantık her dosyada elle kopyalanmış ve zamanla
ayrışmıştı; ``game.py``'ye giren düzeltmeler (ARR=0 anında ışınlanma, frame
düşüşü telafisi/catch-up, şarj frame'inde delta_time çift sayımı koruması)
PvP/co-op kopyalarına yansımıyordu.

Tasarım:
- Her oyuncu (tek oyunculu modda tek örnek; PvP/co-op'ta P1 ve P2 için ayrı)
  bir :class:`DasController` örneğine sahiptir.
- Kontrolör yalnızca DAS zamanlama durumunu (yön, sayaçlar, şarj) tutar.
- Hareketin gerçekten yapılabilmesi çağırana aittir: ``update`` bir
  ``perform_move(direction) -> bool`` callback'i çağırır. Callback başarılıysa
  ``True`` döndürmeli (engele takıldıysa ``False``).
- Soft-drop / DCD gibi "yanal hareketi askıya al" kararları çağırana aittir;
  askıya alınmışsa çağıran ``update`` çağırmaz (game.py'nin erken-return
  davranışıyla birebir uyumlu).
"""

from __future__ import annotations

from typing import Callable

from constants import DAS_DELAY, DAS_REPEAT


class DasController:
    """Tek bir hareket ekseni (bir oyuncu) için DAS zamanlama durumu.

    Attributes:
        direction: -1 sol, 0 yok, 1 sağ.
        timer: İlk gecikme sayacı (ms).
        repeat_timer: Şarj sonrası tekrar sayacı (ms).
        charged: İlk gecikme tamamlandı mı?
    """

    __slots__ = ("direction", "timer", "repeat_timer", "charged")

    def __init__(self) -> None:
        self.direction: int = 0
        self.timer: float = 0.0
        self.repeat_timer: float = 0.0
        self.charged: bool = False

    # -- Durum yönetimi --------------------------------------------------

    def reset(self) -> None:
        """Tüm DAS durumunu sıfırla (yeni parça, oyun sonu, restart vb.)."""
        self.direction = 0
        self.timer = 0.0
        self.repeat_timer = 0.0
        self.charged = False

    def start(self, direction: int, *, cancel_das: bool = False) -> None:
        """Bir yön tuşuna basıldığında DAS'ı başlat.

        İlk (anında) hareketin kendisi çağıran tarafından yapılır; burada
        yalnızca tekrar sistemi için zamanlama durumu kurulur.

        Args:
            direction: -1 (sol) veya 1 (sağ).
            cancel_das: ``cancel_das_on_direction_change`` ayarı. True ise veya
                henüz şarj olmadıysa sayaçlar baştan başlatılır. Şarjlıyken ve
                ayar kapalıyken şarj korunur (yön değişiminde anında DAS).
        """
        self.direction = direction
        if cancel_das or not self.charged:
            self.timer = 0.0
            self.repeat_timer = 0.0
            self.charged = False

    def release(
        self,
        released_direction: int,
        *,
        other_still_held: bool,
        cancel_das: bool = False,
    ) -> int:
        """Bir yön tuşu bırakıldığında çağrılır.

        Args:
            released_direction: Bırakılan tuşun yönü (-1 veya 1).
            other_still_held: Karşı yön tuşu hâlâ basılı mı? (Aynı anda her iki
                tuşa basma davranışı: biri bırakılınca diğerine geç.)
            cancel_das: Yön değişiminde sayaçları sıfırla.

        Returns:
            Karşı yöne geçildiyse o yön (-1/1), yoksa 0. Çağıran bu değere göre
            anında bir hareket tetikleyebilir.
        """
        # Sadece aktif yön bırakıldıysa tepki ver (eski/yankı KEYUP'ları yoksay).
        if self.direction != released_direction:
            return 0

        if other_still_held:
            new_dir = -released_direction
            self.direction = new_dir
            if cancel_das:
                self.timer = 0.0
                self.repeat_timer = 0.0
                self.charged = False
            return new_dir

        self.direction = 0
        self.charged = False
        return 0

    # -- Güncelleme ------------------------------------------------------

    def update(
        self,
        delta_time: float,
        perform_move: Callable[[int], bool],
        *,
        delay_ms: float | None = None,
        repeat_ms: float | None = None,
    ) -> None:
        """DAS tekrar sistemini ilerlet.

        ``game.py``'nin olgun algoritmasıyla birebir aynıdır:
        - ARR (repeat) 0 ise şarj sonrası anında duvara kadar ışınlanır.
        - Şarjın tamamlandığı frame'de delta_time çift sayılmaz.
        - Frame düşüşlerinde kaçan tekrarlar catch-up ile telafi edilir.

        Args:
            delta_time: Geçen süre (ms).
            perform_move: ``perform_move(direction) -> bool``. Hareket
                başarılıysa True döndürmeli. Ses/lock-reset gibi yan etkiler
                callback'in sorumluluğundadır.
            delay_ms / repeat_ms: Ayarlardan okunan DAS değerleri. None ise
                varsayılan sabitler kullanılır.
        """
        if self.direction == 0:
            return

        delay = float(DAS_DELAY if delay_ms is None else delay_ms)
        repeat = float(DAS_REPEAT if repeat_ms is None else repeat_ms)
        delay = max(0.0, delay)
        repeat = max(0.0, repeat)

        self.timer += delta_time

        # ARR (repeat) 0 -> anında ışınlanma
        if repeat == 0:
            if not self.charged:
                if self.timer >= delay:
                    self.charged = True
                    # A valid board callback returns False at the wall. Keep a
                    # hard guard as a last-resort protection against a broken
                    # callback reporting success forever.
                    for _ in range(256):
                        if not perform_move(self.direction):
                            break
            else:
                for _ in range(256):
                    if not perform_move(self.direction):
                        break
            return

        # İlk gecikme dolduğu frame'de tek bir şarj hareketi yap.
        charged_this_frame = False
        if not self.charged:
            if self.timer >= delay:
                overshoot = max(0.0, self.timer - delay)
                self.charged = True
                # Gecikme aşımını repeat timer'a aktar (frame bağımsız akıcılık).
                self.repeat_timer = overshoot
                perform_move(self.direction)
                charged_this_frame = True

        if self.charged:
            # Şarjın yeni tamamlandığı frame'de delta_time'ı tekrar ekleme:
            # overshoot zaten bu frame'in süresini temsil ediyor.
            if not charged_this_frame:
                self.repeat_timer += delta_time
            # Frame düşüşlerinde kaçan tekrarları telafi et (catch-up).
            while self.repeat_timer >= repeat:
                self.repeat_timer -= repeat
                if not perform_move(self.direction):
                    self.repeat_timer = 0.0
                    break
