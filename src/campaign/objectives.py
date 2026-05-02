"""Campaign Görev (Objective) Sınıfları

Her level için farklı görev türleri tanımlar.
Tüm görevler Objective base class'ından türer.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Any, Optional, List

if TYPE_CHECKING:
    from .campaign_mode import CampaignMode


class Objective(ABC):
    """Temel Görev Sınıfı (Abstract)"""
    
    def __init__(
        self,
        target: int,
        description_tr: str,
        description_en: str,
        description_key: str | None = None,
        description_params: Dict[str, Any] | None = None,
    ):
        self.target = target
        self.progress = 0
        self.description = {"tr": description_tr, "en": description_en}
        self.description_key = description_key
        self.description_params = description_params or {}
        self.completed = False
    
    @abstractmethod
    def update(self, game: 'CampaignMode', event_type: str, event_data: Dict[str, Any]) -> None:
        """Oyun olaylarına göre ilerlemeyi güncelle"""
        pass
    
    def check_completion(self) -> bool:
        """Görev tamamlandı mı kontrol et"""
        if self.progress >= self.target:
            self.completed = True
        return self.completed
    
    def get_progress_ratio(self) -> float:
        """İlerleme oranını döndür (0.0 - 1.0)"""
        if self.target <= 0:
            return 1.0
        return min(1.0, self.progress / self.target)
    
    def get_progress_text(self) -> str:
        """İlerleme metnini döndür"""
        return f"{self.progress}/{self.target}"
    
    def reset(self) -> None:
        """Görevi sıfırla"""
        self.progress = 0
        self.completed = False

    @staticmethod
    def _format_number(value: int, lang: str) -> str:
        formatted = f"{value:,}"
        if lang == 'tr':
            formatted = formatted.replace(',', '.')
        return formatted

    def _resolve_description_params(self, lang: str) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}
        for key, value in self.description_params.items():
            if callable(value):
                resolved[key] = value(lang)
            else:
                resolved[key] = value
        return resolved

    def get_description(self, lang: str | None = None) -> str:
        """Lokalize görev açıklamasını döndür"""
        from localization import t, get_language

        lang = lang or get_language()
        if self.description_key:
            params = self._resolve_description_params(lang)
            return t(self.description_key, **params)
        return self.description.get(lang, self.description.get('en', ''))


class ClearLinesObjective(Objective):
    """X Satır Temizle Görevi"""
    
    def __init__(self, target: int = 10, line_type: Optional[str] = None):
        """
        Args:
            target: Hedef satır sayısı
            line_type: None=herhangi, 'single'=1'li, 'double'=2'li, 
                      'triple'=3'lü, 'tetris'=4'lü
        """
        self.line_type = line_type
        
        if line_type == 'single':
            desc_tr = f"{target} Tekli Temizle"
            desc_en = f"Clear {target} Singles"
            desc_key = 'campaign_obj_clear_singles'
        elif line_type == 'double':
            desc_tr = f"{target} İkili Temizle"
            desc_en = f"Clear {target} Doubles"
            desc_key = 'campaign_obj_clear_doubles'
        elif line_type == 'triple':
            desc_tr = f"{target} Üçlü Temizle"
            desc_en = f"Clear {target} Triples"
            desc_key = 'campaign_obj_clear_triples'
        elif line_type == 'tetris':
            desc_tr = f"{target} Quadrix Yap"
            desc_en = f"Make {target} Quadrix"
            desc_key = 'campaign_obj_tetris'
        else:
            desc_tr = f"{target} Satır Temizle"
            desc_en = f"Clear {target} Lines"
            desc_key = 'campaign_obj_clear_lines'

        super().__init__(
            target,
            desc_tr,
            desc_en,
            description_key=desc_key,
            description_params={
                'target': lambda lang, v=target: Objective._format_number(v, lang)
            },
        )
    
    def update(self, game: 'CampaignMode', event_type: str, event_data: Dict[str, Any]) -> None:
        if event_type != 'lines_cleared':
            return
        
        lines = event_data.get('lines', 0)
        
        if self.line_type is None:
            # Herhangi bir temizleme sayılır
            self.progress += lines
        elif self.line_type == 'single' and lines == 1:
            self.progress += 1
        elif self.line_type == 'double' and lines == 2:
            self.progress += 1
        elif self.line_type == 'triple' and lines == 3:
            self.progress += 1
        elif self.line_type == 'tetris' and lines >= 4:
            self.progress += 1
        
        self.check_completion()


class ScoreObjective(Objective):
    """X Puana Ulaş Görevi"""
    
    def __init__(self, target: int = 1000):
        super().__init__(
            target,
            f"{target:,} Puana Ulaş".replace(',', '.'),
            f"Reach {target:,} Score",
            description_key='campaign_obj_score',
            description_params={
                'target': lambda lang, v=target: Objective._format_number(v, lang)
            },
        )
    
    def update(self, game: 'CampaignMode', event_type: str, event_data: Dict[str, Any]) -> None:
        if event_type == 'score_update':
            self.progress = event_data.get('score', 0)
            self.check_completion()


class TetrisObjective(Objective):
    """X Quadrix Yap Görevi"""
    
    def __init__(self, target: int = 1):
        super().__init__(
            target,
            f"{target} Quadrix Yap",
            f"Make {target} Quadrix",
            description_key='campaign_obj_tetris',
            description_params={
                'target': lambda lang, v=target: Objective._format_number(v, lang)
            },
        )
    
    def update(self, game: 'CampaignMode', event_type: str, event_data: Dict[str, Any]) -> None:
        if event_type == 'lines_cleared':
            lines = event_data.get('lines', 0)
            if lines >= 4:
                self.progress += 1
                self.check_completion()


class MultiClearObjective(Objective):
    """Tek hamlede hedef sayida satir temizleme gorevi."""

    def __init__(self, target: int = 2):
        self.lines_required = max(2, int(target))

        if self.lines_required == 2:
            desc_tr = "2'li satır temizle"
            desc_en = 'Get a Double'
            desc_key = 'campaign_obj_clear_doubles'
            desc_params = {}
        elif self.lines_required == 3:
            desc_tr = "3'lü satır temizle"
            desc_en = 'Get a Triple'
            desc_key = 'campaign_obj_clear_triples'
            desc_params = {}
        elif self.lines_required >= 4:
            desc_tr = 'Quadrix Yap'
            desc_en = 'Make a Quadrix'
            desc_key = 'campaign_obj_tetris'
            desc_params = {
                'target': lambda lang, v=1: Objective._format_number(v, lang)
            }
        else:
            desc_tr = f"{self.lines_required}'li satır temizle"
            desc_en = f'Get a {self.lines_required}-clear'
            desc_key = None
            desc_params = {}

        super().__init__(
            1,
            desc_tr,
            desc_en,
            description_key=desc_key,
            description_params=desc_params,
        )

    def update(self, game: 'CampaignMode', event_type: str, event_data: Dict[str, Any]) -> None:
        if event_type != 'lines_cleared':
            return

        if int(event_data.get('lines', 0) or 0) >= self.lines_required:
            self.progress = self.target
            self.check_completion()


class ComboObjective(Objective):
    """X Combo Zinciri Yap Görevi"""
    
    def __init__(self, target: int = 3):
        super().__init__(
            target,
            f"{target} adım zincir yap",
            f"Build a {target}-step chain",
            description_key='campaign_obj_combo',
            description_params={
                'target': lambda lang, v=target: Objective._format_number(v, lang)
            },
        )
        self.current_combo = 0
        self.max_combo = 0
    
    def update(self, game: 'CampaignMode', event_type: str, event_data: Dict[str, Any]) -> None:
        if event_type == 'combo_update':
            self.current_combo = event_data.get('combo', 0)
            if self.current_combo > self.max_combo:
                self.max_combo = self.current_combo
            if self.max_combo >= self.target:
                self.progress = self.target
                self.check_completion()
        elif event_type == 'combo_break':
            self.current_combo = 0


class TimeObjective(Objective):
    """Süre Hedefli Görev"""
    
    def __init__(self, target_seconds: int = 60, objective_type: str = 'survive'):
        """
        Args:
            target_seconds: Hedef süre (saniye)
            objective_type: 'survive' = X saniye hayatta kal, 
                           'complete' = X saniyede bitir
        """
        self.objective_type = objective_type
        self.elapsed_time = 0.0
        
        if objective_type == 'survive':
            desc_tr = f"{target_seconds} Saniye Hayatta Kal"
            desc_en = f"Survive {target_seconds} Seconds"
            desc_key = 'campaign_obj_survival'
        else:
            desc_tr = f"{target_seconds} Saniyede Bitir"
            desc_en = f"Complete in {target_seconds} Seconds"
            desc_key = 'campaign_obj_time'

        super().__init__(
            target_seconds,
            desc_tr,
            desc_en,
            description_key=desc_key,
            description_params={
                'target': lambda lang, v=target_seconds: Objective._format_number(v, lang)
            },
        )
    
    def update(self, game: 'CampaignMode', event_type: str, event_data: Dict[str, Any]) -> None:
        if event_type == 'time_update':
            self.elapsed_time = event_data.get('elapsed', 0.0)
            
            if self.objective_type == 'survive':
                self.progress = int(self.elapsed_time)
                self.check_completion()
                return

            try:
                other_objectives_done = all(
                    obj.completed for obj in getattr(game, 'objectives', []) if obj is not self
                )
            except Exception:
                other_objectives_done = False

            if other_objectives_done and float(self.elapsed_time) <= float(self.target):
                self.progress = self.target
                self.check_completion()


class SpecialBlockObjective(Objective):
    """Özel Blok Temizleme Görevi"""
    
    def __init__(self, target: int = 5, block_type: str = 'ice'):
        """
        Args:
            target: Temizlenecek özel blok sayısı
            block_type: 'ice', 'locked', 'bomb', 'star', 'timer'
        """
        self.block_type = block_type
        
        block_names = {
            'ice': {'tr': 'Buz', 'en': 'Ice', 'key': 'campaign_special_block_ice'},
            'locked': {'tr': 'Kilitli', 'en': 'Locked', 'key': 'campaign_special_block_locked'},
            'bomb': {'tr': 'Bomba', 'en': 'Bomb', 'key': 'campaign_special_block_bomb'},
            'star': {'tr': 'Yıldız', 'en': 'Star', 'key': 'campaign_special_block_star'},
            'timer': {'tr': 'Zamanlı', 'en': 'Timer', 'key': 'campaign_special_block_timer'},
        }

        name = block_names.get(block_type, {'tr': 'Özel', 'en': 'Special', 'key': 'campaign_special_block_special'})
        desc_tr = f"{target} {name['tr']} Blok Temizle"
        desc_en = f"Clear {target} {name['en']} Blocks"

        super().__init__(
            target,
            desc_tr,
            desc_en,
            description_key='campaign_obj_special_block_typed',
            description_params={
                'target': lambda lang, v=target: Objective._format_number(v, lang),
                'block': lambda lang, k=name['key']: __import__('localization').t(k)
            },
        )
    
    def update(self, game: 'CampaignMode', event_type: str, event_data: Dict[str, Any]) -> None:
        if event_type == 'special_block_cleared':
            cleared_type = event_data.get('block_type', '')
            if cleared_type == self.block_type:
                self.progress += event_data.get('count', 1)
                self.check_completion()


class ClearGarbageObjective(Objective):
    """Çöp Bloklarını Temizleme Görevi
    
    Başlangıçta yerleştirilen TÜM gri çöp bloklarını temizleyerek tamamlanır.
    Hedef, başlangıçtaki çöp hücresi sayısıdır.
    """
    
    # Gri çöp blok rengi (günlük görevdeki gibi)
    GARBAGE_COLOR = (70, 70, 100)
    
    def __init__(self, target: int = 0):
        """
        Args:
            target: Başlangıçta 0, sonra set_initial_garbage ile ayarlanır
        """
        self.garbage_cells_cleared = 0
        self.initial_garbage_count = 0  # Başlangıçtaki çöp hücre sayısı
        self._garbage_initialized = False
        
        # Başlangıçta genel metin, sonra güncellenir
        super().__init__(
            target if target > 0 else 1,  # Geçici hedef
            "Tüm Çöp Bloklarını Temizle",
            "Clear All Garbage Blocks",
            description_key='campaign_obj_clear_garbage'
        )
    
    def set_initial_garbage(self, count: int) -> None:
        """Başlangıçtaki çöp hücre sayısını ayarla ve hedefi güncelle"""
        self.initial_garbage_count = count
        self.target = count
        self._garbage_initialized = True
        # Açıklamayı güncelle
        self.description = {
            "tr": f"Tüm Çöp Bloklarını Temizle ({count} hücre)",
            "en": f"Clear All Garbage Blocks ({count} cells)"
        }
        self.description_key = 'campaign_obj_clear_garbage_count'
        self.description_params = {
            'count': lambda lang, v=count: Objective._format_number(v, lang)
        }
    
    def update(self, game: 'CampaignMode', event_type: str, event_data: Dict[str, Any]) -> None:
        # İlk çağrıda çöp bloklarını say
        if not self._garbage_initialized and hasattr(game, 'board') and game.board:
            self._count_garbage_cells(game)
        
        if event_type == 'lines_cleared':
            # Temizlenen satırların içindeki çöp hücrelerini say
            # Şimdilik her temizlenen satırda ortalama yarısı çöp kabul edelim
            # Veya daha doğrusu: kalan çöp hücrelerini say
            self._update_garbage_progress(game)
    
    def _count_garbage_cells(self, game: 'CampaignMode') -> None:
        """Board'daki gri çöp hücrelerini say"""
        if not hasattr(game, 'board') or not game.board:
            return
        
        count = 0
        for row in game.board.grid:
            for cell in row:
                if cell == self.GARBAGE_COLOR:
                    count += 1
        
        if count > 0:
            self.set_initial_garbage(count)
    
    def _update_garbage_progress(self, game: 'CampaignMode') -> None:
        """Kalan çöp hücrelerini sayarak ilerlemeyi güncelle"""
        if not hasattr(game, 'board') or not game.board:
            return
        
        remaining = 0
        for row in game.board.grid:
            for cell in row:
                if cell == self.GARBAGE_COLOR:
                    remaining += 1
        
        # Temizlenen = Başlangıç - Kalan
        self.garbage_cells_cleared = self.initial_garbage_count - remaining
        self.progress = self.garbage_cells_cleared
        self.check_completion()
    
    def get_progress_text(self) -> str:
        """İlerleme metnini döndür"""
        return f"{self.progress}/{self.target}"


class MoveEfficiencyObjective(Objective):
    """Hareket Verimliliği Görevi - Sınırlı hamle ile tamamla"""
    
    def __init__(self, max_moves: int = 50, lines_to_clear: int = 20):
        self.max_moves = max_moves
        self.lines_to_clear = lines_to_clear
        self.moves_used = 0
        self.lines_done = 0
        
        super().__init__(
            lines_to_clear,
            f"{max_moves} Hamlede {lines_to_clear} Satır",
            f"{lines_to_clear} Lines in {max_moves} Moves",
            description_key='campaign_obj_move_efficiency_detail',
            description_params={
                'moves': lambda lang, v=max_moves: Objective._format_number(v, lang),
                'lines': lambda lang, v=lines_to_clear: Objective._format_number(v, lang)
            },
        )
    
    def update(self, game: 'CampaignMode', event_type: str, event_data: Dict[str, Any]) -> None:
        if event_type == 'piece_placed':
            self.moves_used += 1
        elif event_type == 'lines_cleared':
            self.lines_done += event_data.get('lines', 0)
            self.progress = self.lines_done
            
            if self.lines_done >= self.lines_to_clear:
                self.completed = True
    
    def is_failed(self) -> bool:
        """Hamle hakkı bitti mi ve görev tamamlanmadı mı?"""
        return self.moves_used >= self.max_moves and not self.completed
    
    def get_remaining_moves(self) -> int:
        """Kalan hamle sayısı"""
        return max(0, self.max_moves - self.moves_used)


# Görev factory fonksiyonu
def create_objective(obj_type: str, **kwargs) -> Objective:
    """Görev tipine göre Objective instance'ı oluştur"""
    factories = {
        'clear_lines': lambda: ClearLinesObjective(
            target=kwargs.get('target', 10),
            line_type=kwargs.get('line_type')
        ),
        'score': lambda: ScoreObjective(target=kwargs.get('target', 1000)),
        'tetris': lambda: TetrisObjective(target=kwargs.get('target', 1)),
        'combo': lambda: ComboObjective(target=kwargs.get('target', 3)),
        'multi_clear': lambda: MultiClearObjective(target=kwargs.get('target', 2)),
        'time': lambda: TimeObjective(
            target_seconds=kwargs.get('target', 60),
            objective_type=kwargs.get('time_type', 'survive')
        ),
        'time_challenge': lambda: TimeObjective(
            target_seconds=kwargs.get('target', 60),
            objective_type='complete'
        ),
        'special_block': lambda: SpecialBlockObjective(
            target=kwargs.get('target', 5),
            block_type=kwargs.get('block_type', 'ice')
        ),
        'clear_garbage': lambda: ClearGarbageObjective(
            target=kwargs.get('target', 3)
        ),
        'survival': lambda: TimeObjective(
            target_seconds=kwargs.get('target', 60),
            objective_type='survive'
        ),
        'move_efficiency': lambda: MoveEfficiencyObjective(
            max_moves=kwargs.get('max_moves', 50),
            lines_to_clear=kwargs.get('target', 20)
        ),
    }
    
    factory = factories.get(obj_type)
    if factory:
        return factory()
    
    # Varsayılan: satır temizleme
    return ClearLinesObjective(target=kwargs.get('target', 10))
