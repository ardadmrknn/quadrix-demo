"""Tutorial kart dersi verisi ve saf yardımcılar.

Bu modül, kart akademisi için kontrollü kart seçim senaryoları sunar.
Gerçek kart kimlikleri korunur; UI'da gösterilen başlık ve açıklamalar
localization anahtarlarından çözülür.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

try:
    from .localization import t  # type: ignore
except Exception:
    from localization import t


_REAL_CARD_LIBRARY: Dict[str, Dict[str, Any]] | None = None
_REAL_GET_CARD_TITLE = None
_REAL_GET_CARD_DESCRIPTION = None
_REAL_CARD_TYPE_LABEL_KEY = None


def _ensure_real_card_helpers() -> None:
    global _REAL_CARD_LIBRARY, _REAL_GET_CARD_TITLE, _REAL_GET_CARD_DESCRIPTION, _REAL_CARD_TYPE_LABEL_KEY
    if _REAL_CARD_LIBRARY is not None:
        return

    _REAL_CARD_LIBRARY = {}
    try:
        try:
            from .game_modes_extra import (  # type: ignore
                MysteryCardManager,
                _card_type_label_key,
                get_card_description,
                get_card_title,
            )
        except Exception:
            from game_modes_extra import (  # type: ignore
                MysteryCardManager,
                _card_type_label_key,
                get_card_description,
                get_card_title,
            )

        class _DummySettingsManager:
            def get(self, _key: str, default=None):
                return default

        class _DummyMode:
            settings_manager = _DummySettingsManager()

        manager = MysteryCardManager(_DummyMode())
        _REAL_CARD_LIBRARY = {
            str(card.get("id") or ""): deepcopy(card)
            for card in getattr(manager, "catalog", []) or []
            if card.get("id")
        }
        _REAL_GET_CARD_TITLE = get_card_title
        _REAL_GET_CARD_DESCRIPTION = get_card_description
        _REAL_CARD_TYPE_LABEL_KEY = _card_type_label_key
    except Exception:
        _REAL_CARD_LIBRARY = {}
        _REAL_GET_CARD_TITLE = None
        _REAL_GET_CARD_DESCRIPTION = None
        _REAL_CARD_TYPE_LABEL_KEY = None


CARD_LIBRARY: Dict[str, Dict[str, Any]] = {
    "clear_rows": {
        "id": "clear_rows",
        "localization_id": "clear_rows",
        "title": "Alt Süpür",
        "description": "En alttaki {value} satırı temizler. Bloklar aşağı oturur.",
        "value": 2,
        "rarity": "uncommon",
        "tag": "Uncommon",
        "single_use": True,
    },
    "peak_sculpt": {
        "id": "peak_sculpt",
        "localization_id": "peak_sculpt",
        "title": "Tepe Kesici",
        "description": "En yüksek {value} bloğu keser, tahtayı düzleştirir.",
        "value": 3,
        "rarity": "uncommon",
        "tag": "Uncommon",
        "single_use": True,
    },
    "speed_burst_legendary": {
        "id": "speed_burst_legendary",
        "localization_id": "speed_burst",
        "title": "Hız Patlaması",
        "description": "{value} saniye boyunca %60 hızlı düşüş + temizlenen her satır için 1.75x puan!",
        "value": 40,
        "rarity": "legendary",
        "tag": "Legendary",
        "timed_buff": True,
        "payload": {"speed_multiplier": 1.6, "line_multiplier": 1.75},
    },
    "perk_second_pocket": {
        "id": "perk_second_pocket",
        "localization_id": "perk_second_pocket",
        "title": "Ekstra Cep",
        "description": "PERK: V tuşuyla ikinci bir parça saklayabilirsin.",
        "value": 1,
        "rarity": "legendary",
        "tag": "Legendary",
        "persistent": True,
    },
    "row_shuffle": {
        "id": "row_shuffle",
        "localization_id": "row_shuffle",
        "title": "Blok Karıştırıcı",
        "description": "Alt {value} satırdaki blokları karıştırır, şansını dene!",
        "value": 3,
        "rarity": "common",
        "tag": "Common",
        "single_use": True,
    },
    "perk_synergy": {
        "id": "perk_synergy",
        "localization_id": "perk_synergy",
        "title": "Sinerji Bonusu",
        "description": "PERK: Her aktif kart için +%10 skor bonusu.",
        "value": 1,
        "rarity": "rare",
        "tag": "Rare",
        "persistent": True,
    },
    "speed_burst_rare": {
        "id": "speed_burst_rare",
        "localization_id": "speed_burst",
        "title": "Hız Patlaması",
        "description": "{value} saniye boyunca %25 hızlı düşüş + temizlenen her satır için 1.3x puan!",
        "value": 20,
        "rarity": "rare",
        "tag": "Rare",
        "timed_buff": True,
        "payload": {"speed_multiplier": 1.25, "line_multiplier": 1.3},
    },
    "freeze_drop_rare": {
        "id": "freeze_drop_rare",
        "localization_id": "freeze_drop",
        "title": "Son Düşüş",
        "description": "Parça kilitlenmeden önce {value} sn düşünme süresi — 3 hak.",
        "value": 6,
        "rarity": "rare",
        "tag": "Rare",
        "single_use": False,
    },
    "perk_flexible_border": {
        "id": "perk_flexible_border",
        "localization_id": "perk_flexible_border",
        "title": "Esnek Sınır",
        "description": "PERK: Parçalar duvardan geçebilir (wrap-around).",
        "value": 1,
        "rarity": "legendary",
        "tag": "Legendary",
        "persistent": True,
    },
    "nova_burst": {
        "id": "nova_burst",
        "localization_id": "nova_burst",
        "title": "Nova Patlaması",
        "description": "Tüm bloklardan 3x3 patlama! En yoğun bölgeyi temizler.",
        "value": 1,
        "rarity": "epic",
        "tag": "Epic",
        "single_use": True,
    },
    "ghost_echo": {
        "id": "ghost_echo",
        "localization_id": "ghost_echo",
        "title": "İkinci Şans",
        "description": "PERK: Game over'da bir kez canlanırsın — tahtanın üst yarısı temizlenir.",
        "value": 1,
        "rarity": "legendary",
        "tag": "Legendary",
        "persistent": True,
    },
    "gravity_well": {
        "id": "gravity_well",
        "localization_id": "gravity_well",
        "title": "Yerçekimi Dalgası",
        "description": "Tüm bloklar aşağı çöker, boşluklar kapanır.",
        "value": 1,
        "rarity": "epic",
        "tag": "Epic",
        "single_use": True,
    },
    "mini_bomb": {
        "id": "mini_bomb",
        "localization_id": "mini_bomb",
        "title": "Mini Bomba",
        "description": "Küçük bir alanı temizler.",
        "value": 1,
        "rarity": "common",
        "tag": "Common",
        "single_use": True,
    },
}


CARD_CHOICE_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "rescue_pick": {
        "goal_key": "tutorial_card_rescue_goal",
        "tip_key": "tutorial_card_rescue_tip",
        "goal_text": "Tahta tehlikede — seni yaşatacak kartı bul.",
        "tip_text": "Parlak olan değil, şu an tahtanı kurtaracak kartı seç.",
        "context_keys": [
            "tutorial_card_rescue_context_1",
            "tutorial_card_rescue_context_2",
        ],
        "context_lines": [
            "Durum: Delikli ve yüksek bir tahta.",
            "Öncelik: Nefes aldıran hamleyi seçmek.",
        ],
        "board_rows": [
            "XXXXXX.XXX",
            "XXXXX..XXX",
            "XXXX.XXXXX",
            "XXX..XXXXX",
            "XXXX.XXXXX",
            "XX..XXXXXX",
        ],
        "current_piece": {"name": "S", "x": 3, "y": 0, "rotation": 0},
        "next_queue": ["Z", "L", "I"],
        "card_choices": ["clear_rows", "peak_sculpt", "speed_burst_legendary"],
        "recommended_card_id": "clear_rows",
        "acceptable_card_ids": ["peak_sculpt"],
        "feedback_keys_by_card": {
            "clear_rows": "tutorial_card_rescue_feedback_clear_rows",
            "peak_sculpt": "tutorial_card_rescue_feedback_peak_sculpt",
            "speed_burst_legendary": "tutorial_card_rescue_feedback_speed_burst",
        },
        "feedback_by_card": {
            "clear_rows": "Doğru seçim. Alt Süpür tahtada hemen alan açar ve baskıyı düşürür.",
            "peak_sculpt": "Kabul edilebilir seçim. Tepeyi kesmek baskıyı azaltır ama alt taraftaki karmaşayı tam çözmez.",
            "speed_burst_legendary": "Zayıf seçim. Hız kartı bu tahtada hatayı büyütür; önce hayatta kalman gerekir.",
        },
    },
    "long_term_pick": {
        "goal_key": "tutorial_card_long_term_goal",
        "tip_key": "tutorial_card_long_term_tip",
        "goal_text": "Tahta sakin — uzun vadede en çok işe yarayacak kartı seç.",
        "tip_text": "Acil sorun yoksa run boyunca değer üretecek kartı düşün.",
        "context_keys": [
            "tutorial_card_long_term_context_1",
            "tutorial_card_long_term_context_2",
        ],
        "context_lines": [
            "Durum: Düzenli ve alçak bir tahta.",
            "Öncelik: Uzun vadeli değer kazanmak.",
        ],
        "board_rows": [
            "....XX....",
            "...XXXX...",
            "..XXXXXX..",
        ],
        "current_piece": {"name": "T", "x": 3, "y": 0, "rotation": 0},
        "next_queue": ["I", "O", "L"],
        "card_choices": ["perk_second_pocket", "clear_rows", "row_shuffle"],
        "recommended_card_id": "perk_second_pocket",
        "acceptable_card_ids": [],
        "feedback_keys_by_card": {
            "perk_second_pocket": "tutorial_card_long_term_feedback_second_pocket",
            "clear_rows": "tutorial_card_long_term_feedback_clear_rows",
            "row_shuffle": "tutorial_card_long_term_feedback_row_shuffle",
        },
        "feedback_by_card": {
            "perk_second_pocket": "Doğru seçim. Güvenli tahtada Ekstra Cep gibi kalıcı bir perk tüm run boyunca değer üretir.",
            "clear_rows": "Zayıf seçim. Tahta zaten rahat; anlık temizlik burada gereksiz değer kaybı.",
            "row_shuffle": "Zayıf seçim. Şans kartı sakin bir tahtayı sebepsiz yere bozabilir.",
        },
    },
    "synergy_pick": {
        "goal_key": "tutorial_card_synergy_goal",
        "tip_key": "tutorial_card_synergy_tip",
        "goal_text": "Aktif perklerin var — bunları güçlendirecek kartı bul.",
        "tip_text": "Kartı tek başına değil, mevcut build'inle birlikte değerlendir.",
        "context_keys": [
            "tutorial_card_synergy_context_1",
            "tutorial_card_synergy_context_2",
        ],
        "context_lines": [
            "Aktif perkler: Ekstra Cep, Esnek Sınır.",
            "Öncelik: Build'i büyüten seçimi bulmak.",
        ],
        "board_rows": [
            ".....X....",
            "....XXX...",
            "...XXXXX..",
            "..XXXXXX..",
        ],
        "current_piece": {"name": "J", "x": 3, "y": 0, "rotation": 0},
        "next_queue": ["T", "I", "S"],
        "card_choices": ["perk_synergy", "speed_burst_rare", "row_shuffle"],
        "recommended_card_id": "perk_synergy",
        "acceptable_card_ids": [],
        "feedback_keys_by_card": {
            "perk_synergy": "tutorial_card_synergy_feedback_perk_synergy",
            "speed_burst_rare": "tutorial_card_synergy_feedback_speed_burst",
            "row_shuffle": "tutorial_card_synergy_feedback_row_shuffle",
        },
        "feedback_by_card": {
            "perk_synergy": "Doğru seçim. Zaten aktif perklerin olduğu için Sinerji Bonusu hemen büyüyen bir çarpana dönüşür.",
            "speed_burst_rare": "Zayıf seçim. Hız Patlaması faydalı olsa da bu dersin odağı mevcut perk zincirini büyütmek; tek başına build sinerjisi kurmaz.",
            "row_shuffle": "Zayıf seçim. Rastgelelik eklemek yerine aktif perklerden daha fazla değer çıkarmalısın.",
        },
    },

    # ── Yeni kart senaryoları ──────────────────────────────────

    "tempo_trap": {
        "goal_key": "tutorial_cards_tempo_trap_goal",
        "tip_key": "tutorial_cards_tempo_trap_tip",
        "goal_text": "Hız tuzağını gör — dağınık tahtada doğru araç hangisi?",
        "tip_text": "Hızlı oynamak çözüm değil — tahtayı düzeltecek kartı bul.",
        "context_keys": [
            "tutorial_cards_tempo_trap_context_1",
            "tutorial_cards_tempo_trap_context_2",
        ],
        "context_lines": [
            "Durum: Orta yükseklikte dağınık tahta.",
            "Öncelik: Tahtayı düzeltmek, skor değil.",
        ],
        "board_rows": [
            "XXX..XXXXX",
            "XXXX.XXXXX",
            "XX.XXXXXXX",
            "XXXXX.XXXX",
            "XXXXXXX.XX",
        ],
        "current_piece": {"name": "T", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["I", "L", "O"],
        "card_choices": ["speed_burst_rare", "peak_sculpt", "gravity_well"],
        "recommended_card_id": "gravity_well",
        "acceptable_card_ids": [],
        "card_star_overrides": {"peak_sculpt": 1},
        "feedback_keys_by_card": {
            "speed_burst_rare": "tutorial_cards_tempo_trap_feedback_speed",
            "peak_sculpt": "tutorial_cards_tempo_trap_feedback_sculpt",
            "gravity_well": "tutorial_cards_tempo_trap_feedback_gravity",
        },
        "feedback_by_card": {
            "speed_burst_rare": "Yanlış seçim. Dağınık tahtada hız artışı hataları büyütür. Önce tahtayı düzelt.",
            "peak_sculpt": "Kısmen işe yarar ama yetersiz. Sadece üstü keser; alttaki boşlukları ve kırık yüzeyi çözmez.",
            "gravity_well": "Doğru seçim. Yerçekimi Dalgası tüm blokları aşağı oturtup dağınık yüzeyi toparlar.",
        },
    },

    "perk_vs_instant": {
        "goal_key": "tutorial_cards_perk_vs_instant_goal",
        "tip_key": "tutorial_cards_perk_vs_instant_tip",
        "goal_text": "Kalıcı perk mi, anlık etki mi? Tahtana göre karar ver.",
        "tip_text": "Tahta temizken kalıcı güç uzun vadede daha çok işe yarar.",
        "context_keys": [
            "tutorial_cards_perk_vs_instant_context_1",
            "tutorial_cards_perk_vs_instant_context_2",
        ],
        "context_lines": [
            "Durum: Orta yükseklikte, temiz tahta.",
            "Öncelik: Run boyunca en çok değer üreten kartı seç.",
        ],
        "board_rows": [
            "...XXX....",
            "..XXXXX...",
            ".XXXXXXX..",
        ],
        "current_piece": {"name": "O", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["T", "I", "L"],
        "card_choices": ["perk_flexible_border", "clear_rows", "nova_burst"],
        "recommended_card_id": "perk_flexible_border",
        "acceptable_card_ids": [],
        "feedback_keys_by_card": {
            "perk_flexible_border": "tutorial_cards_perk_vs_instant_feedback_border",
            "clear_rows": "tutorial_cards_perk_vs_instant_feedback_clear",
            "nova_burst": "tutorial_cards_perk_vs_instant_feedback_nova",
        },
        "feedback_by_card": {
            "perk_flexible_border": "Doğru seçim. Esnek Sınır tüm run boyunca daha esnek yerleştirme sağlar.",
            "clear_rows": "Zayıf seçim. Tahta zaten temiz — anlık temizlik gereksiz.",
            "nova_burst": "Zayıf seçim. Nova patlaması anlık çözüm sunar ama tahta buna ihtiyaç duymuyor.",
        },
    },

    "rare_not_auto": {
        "goal_key": "tutorial_cards_rare_not_auto_goal",
        "tip_key": "tutorial_cards_rare_not_auto_tip",
        "goal_text": "Efsanevi kart her zaman doğru değil. Tahtanın gerçek ihtiyacını oku.",
        "tip_text": "Tahtanın acili ne? Parlak etikete değil, gerçek soruna bak.",
        "context_keys": [
            "tutorial_cards_rare_not_auto_context_1",
            "tutorial_cards_rare_not_auto_context_2",
        ],
        "context_lines": [
            "Durum: Orta yükseklikte, pürüzlü ama kurtarılabilir tahta.",
            "Öncelik: Sonraki birkaç hamleyi güvene almak.",
        ],
        "board_rows": [
            "...XX.....",
            "..XXXX....",
            ".XXXXXX...",
            "XXX..XXXXX",
            "XXXX..XXXX",
            "XXXXX.XXXX",
        ],
        "current_piece": {"name": "L", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["L", "I", "S"],
        "card_choices": ["speed_burst_legendary", "freeze_drop_rare", "clear_rows"],
        "recommended_card_id": "freeze_drop_rare",
        "acceptable_card_ids": ["clear_rows"],
        "feedback_keys_by_card": {
            "speed_burst_legendary": "tutorial_cards_rare_not_auto_feedback_speed",
            "freeze_drop_rare": "tutorial_cards_rare_not_auto_feedback_freeze",
            "clear_rows": "tutorial_cards_rare_not_auto_feedback_clear",
        },
        "feedback_by_card": {
            "speed_burst_legendary": "Zayıf seçim. Bu tahta hız değil hassasiyet istiyor; hızlanmak delik riskini artırır.",
            "freeze_drop_rare": "Doğru seçim. Son Düşüş önündeki kritik yerleşimlerde düşünme süresi vererek gerçek problemi çözer.",
            "clear_rows": "Kabul edilebilir. Alan açar ama sorunun özü hassas yerleşimler; ek düşünme süresi daha fazla değer üretir.",
        },
    },

    "build_direction": {
        "goal_key": "tutorial_cards_build_direction_goal",
        "tip_key": "tutorial_cards_build_direction_tip",
        "goal_text": "Sadece bir sorun var — onu çözen, fazlasını yapmayan kartı seç.",
        "tip_text": "Büyük silah her zaman en iyi cevap değil. Soruna göre ölç.",
        "context_keys": [
            "tutorial_cards_build_direction_context_1",
            "tutorial_cards_build_direction_context_2",
        ],
        "context_lines": [
            "Durum: Tahta genel olarak güvenli ama sağ tarafta tek bir sivri kule var.",
            "Öncelik: Sadece o problemi temizleyip yüzeyi yeniden sakinleştirmek.",
        ],
        "board_rows": [
            ".......X..",
            "......XX..",
            "....XXXX..",
            "..XXXXXXX.",
            ".XXXXXXXX.",
        ],
        "current_piece": {"name": "I", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["T", "O", "L"],
        "card_choices": ["peak_sculpt", "nova_burst", "row_shuffle"],
        "recommended_card_id": "peak_sculpt",
        "acceptable_card_ids": [],
        "feedback_keys_by_card": {
            "peak_sculpt": "tutorial_cards_build_direction_feedback_sculpt",
            "nova_burst": "tutorial_cards_build_direction_feedback_nova",
            "row_shuffle": "tutorial_cards_build_direction_feedback_shuffle",
        },
        "feedback_by_card": {
            "peak_sculpt": "Doğru seçim. Sorun tek bir sivri kuleyse Tepe Kesici tam hedefe vurur ve güçlü kartları boşa harcamaz.",
            "nova_burst": "Zayıf seçim. Nova Patlaması bu kadar lokal bir problem için fazla büyük; gereksiz değer yakarsın.",
            "row_shuffle": "Zayıf seçim. Stabil tahtada rastgelelik eklemek çözmek yerine yeni sorun üretebilir.",
        },
    },

    "risk_reward_timing": {
        "goal_key": "tutorial_cards_risk_reward_goal",
        "tip_key": "tutorial_cards_risk_reward_tip",
        "goal_text": "Tahta güvende — risk alıp puan kazanma zamanı mı?",
        "tip_text": "Güvenli tahtada cesur kart seni büyütür, tehlikeli tahtada öldürür.",
        "context_keys": [
            "tutorial_cards_risk_reward_context_1",
            "tutorial_cards_risk_reward_context_2",
        ],
        "context_lines": [
            "Durum: Alçak, temiz ve güvenli tahta.",
            "Öncelik: Büyüme fırsatını değerlendir.",
        ],
        "board_rows": [
            "..........",
            "....XX....",
            "...XXXX...",
        ],
        "current_piece": {"name": "T", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["I", "L", "O"],
        "card_choices": ["speed_burst_legendary", "freeze_drop_rare", "gravity_well"],
        "recommended_card_id": "speed_burst_legendary",
        "acceptable_card_ids": [],
        "feedback_keys_by_card": {
            "speed_burst_legendary": "tutorial_cards_risk_reward_feedback_speed",
            "freeze_drop_rare": "tutorial_cards_risk_reward_feedback_freeze",
            "gravity_well": "tutorial_cards_risk_reward_feedback_gravity",
        },
        "feedback_by_card": {
            "speed_burst_legendary": "Doğru seçim. Güvenli board'da Hız Patlaması riski büyüme fırsatına çevirir.",
            "freeze_drop_rare": "Zayıf seçim. Güvenli board'da yavaşlamak gereksiz — büyüme zamanı.",
            "gravity_well": "Zayıf seçim. Tahta zaten temiz — yerçekimi dalgası işe yaramaz.",
        },
    },
}


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _resolve_localization_id(card: Dict[str, Any]) -> str:
    return str(card.get("localization_id") or card.get("id") or "")


def _build_format_context(card: Dict[str, Any]) -> Dict[str, Any]:
    context: Dict[str, Any] = {}
    for key, raw_value in card.items():
        if isinstance(raw_value, (str, int, float)):
            context[key] = raw_value
    payload = card.get("payload")
    if isinstance(payload, dict):
        for key, raw_value in payload.items():
            if isinstance(raw_value, (str, int, float)):
                context[key] = raw_value
    speed_multiplier = context.get("speed_multiplier")
    if isinstance(speed_multiplier, (int, float)) and "speed_percent" not in context:
        context["speed_percent"] = int(round((float(speed_multiplier) - 1.0) * 100))
    return context


def _format_text(text: str, card: Dict[str, Any]) -> str:
    if not text or "{" not in text:
        return text
    try:
        return text.format_map(_SafeFormatDict(_build_format_context(card)))
    except Exception:
        return text


def get_card_preview(card_id: str) -> Dict[str, Any] | None:
    _ensure_real_card_helpers()
    card_key = str(card_id)
    real_card = deepcopy((_REAL_CARD_LIBRARY or {}).get(card_key, {}))
    tutorial_card = deepcopy(CARD_LIBRARY.get(card_key, {}))
    if not real_card and not tutorial_card:
        return None

    card = deepcopy(real_card) if real_card else tutorial_card
    if tutorial_card.get("localization_id"):
        card["localization_id"] = tutorial_card["localization_id"]
    if real_card:
        if real_card.get("value") is not None:
            card["value"] = real_card.get("value")
        elif real_card.get("base") is not None:
            card["value"] = real_card.get("base")
    card.setdefault("id", card_key)
    if "value" not in card and "base" in card:
        card["value"] = card.get("base")
    if card.get("description"):
        card["description"] = _format_text(str(card.get("description") or ""), card)
    return card


def get_tutorial_card_title(card: Dict[str, Any]) -> str:
    _ensure_real_card_helpers()
    localization_id = _resolve_localization_id(card)
    fallback = str(card.get("title") or localization_id)
    if callable(_REAL_GET_CARD_TITLE):
        try:
            return str(_REAL_GET_CARD_TITLE(card, fallback=fallback))
        except Exception:
            pass
    return _format_text(t(f"card_{localization_id}_title", default=fallback), card)


def get_tutorial_card_description(card: Dict[str, Any]) -> str:
    _ensure_real_card_helpers()
    localization_id = _resolve_localization_id(card)
    fallback = str(card.get("description") or "")
    if callable(_REAL_GET_CARD_DESCRIPTION):
        try:
            return str(_REAL_GET_CARD_DESCRIPTION(card, card.get("value"), fallback=fallback))
        except Exception:
            pass
    return _format_text(t(f"card_{localization_id}_desc", default=fallback), card)


def get_tutorial_card_type_label(card: Dict[str, Any]) -> str:
    _ensure_real_card_helpers()
    if callable(_REAL_CARD_TYPE_LABEL_KEY):
        try:
            return t(_REAL_CARD_TYPE_LABEL_KEY(card), default="Sinirli Kullanim")
        except Exception:
            pass
    if bool(card.get("persistent", False)):
        return t("card_type_persistent", default="Kalici Perk")
    if bool(card.get("limited", False)) or bool(card.get("timed_buff", False)) or bool(card.get("charges", False)):
        return t("card_type_limited", default="Sinirli Kullanim")
    if bool(card.get("single_use", False)):
        return t("card_type_single_use", default="Tek Kullanim")
    return t("card_type_limited", default="Sinirli Kullanim")


def get_tutorial_card_rarity_label(card: Dict[str, Any]) -> str:
    rarity = str(card.get("rarity") or "common")
    fallback = str(card.get("tag") or rarity.title())
    return t(f"card_rarity_{rarity}", default=fallback)


def get_card_choice_scenario(scenario_id: str | None) -> Dict[str, Any] | None:
    if not scenario_id:
        return None
    scenario = CARD_CHOICE_SCENARIOS.get(str(scenario_id))
    if not scenario:
        return None
    hydrated = deepcopy(scenario)
    hydrated["scenario_id"] = str(scenario_id)
    hydrated["choices"] = []
    for card_id in hydrated.get("card_choices", []):
        preview = get_card_preview(card_id)
        if preview is not None:
            hydrated["choices"].append(preview)

    context_keys = list(hydrated.get("context_keys", []) or [])
    context_fallbacks = list(hydrated.get("context_lines", []) or [])
    if context_keys:
        hydrated["context_lines"] = [
            t(key, default=context_fallbacks[index] if index < len(context_fallbacks) else "")
            for index, key in enumerate(context_keys)
        ]
    goal_key = hydrated.get("goal_key")
    if goal_key:
        hydrated["goal_text"] = t(str(goal_key), default=str(hydrated.get("goal_text") or ""))
    tip_key = hydrated.get("tip_key")
    if tip_key:
        hydrated["tip_text"] = t(str(tip_key), default=str(hydrated.get("tip_text") or ""))
    return hydrated


def evaluate_card_choice(scenario: Dict[str, Any] | None, selected_card_id: str | None) -> Dict[str, Any]:
    scenario_data = deepcopy(scenario) if isinstance(scenario, dict) else {}
    selected_id = str(selected_card_id or "")
    recommended_id = str(scenario_data.get("recommended_card_id") or "")
    acceptable_ids = {str(card_id) for card_id in scenario_data.get("acceptable_card_ids", [])}
    card_star_overrides = {
        str(card_id): max(0, min(3, int(stars or 0)))
        for card_id, stars in (scenario_data.get("card_star_overrides", {}) or {}).items()
    }
    feedback_by_card = scenario_data.get("feedback_by_card", {}) if isinstance(scenario_data.get("feedback_by_card"), dict) else {}
    feedback_keys_by_card = scenario_data.get("feedback_keys_by_card", {}) if isinstance(scenario_data.get("feedback_keys_by_card"), dict) else {}

    if selected_id == recommended_id:
        success = True
        stars = card_star_overrides.get(selected_id, 3)
        title = t("tutorial_card_choice_title_correct", default="Dogru Secim")
    elif selected_id in acceptable_ids:
        stars = card_star_overrides.get(selected_id, 2)
        success = stars > 0
        title = t("tutorial_card_choice_title_acceptable", default="Kabul Edilebilir")
    elif selected_id in card_star_overrides and card_star_overrides[selected_id] > 0:
        success = True
        stars = card_star_overrides[selected_id]
        title = t("tutorial_card_choice_title_acceptable", default="Kabul Edilebilir")
    else:
        success = False
        stars = 0
        title = t("tutorial_result_retry_title", default="Tekrar Dene")

    feedback_key = feedback_keys_by_card.get(selected_id)
    fallback_feedback = str(feedback_by_card.get(selected_id) or t("tutorial_card_choice_feedback_generic", default="Secimin bu tahta ihtiyacina iyi uymuyor."))
    feedback = t(str(feedback_key), default=fallback_feedback) if feedback_key else fallback_feedback
    chosen_card = get_card_preview(selected_id) or {"id": selected_id, "title": selected_id}

    # FAZ 5 — Yanlış/kabul edilebilir seçimde önerilen kartın NEDEN doğru olduğunu da
    # göster: "senin seçimin" ile "ideal seçim" arasındaki kontrastı öğret.
    recommended_reason = ""
    if recommended_id and selected_id != recommended_id:
        rec_key = feedback_keys_by_card.get(recommended_id)
        rec_fallback = str(feedback_by_card.get(recommended_id) or "")
        if rec_key:
            recommended_reason = t(str(rec_key), default=rec_fallback)
        else:
            recommended_reason = rec_fallback

    return {
        "success": success,
        "stars": stars,
        "title": title,
        "feedback": feedback,
        "selected_card_id": selected_id,
        "selected_card_title": get_tutorial_card_title(chosen_card),
        "recommended_card_id": recommended_id,
        "recommended_card_title": get_tutorial_card_title(get_card_preview(recommended_id) or {"id": recommended_id, "title": recommended_id}),
        "recommended_reason": recommended_reason,
    }
