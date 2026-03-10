"""Tutorial kart dersi verisi ve saf helper'lar.

Bu modul, kart akademisi icin kontrollu kart secim senaryolari sunar.
Gercek kart kimlikleri korunur; UI'da gosterilen baslik ve aciklamalar
localization anahtarlarindan cozulur.
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
        "title": "Alt Supur",
        "description": "En alttaki {value} satiri temizler. Bloklar asagi oturur.",
        "value": 2,
        "rarity": "uncommon",
        "tag": "Uncommon",
        "single_use": True,
    },
    "peak_sculpt": {
        "id": "peak_sculpt",
        "localization_id": "peak_sculpt",
        "title": "Tepe Kesici",
        "description": "En yuksek {value} blogu keser, tahtayi duzlestirir.",
        "value": 3,
        "rarity": "uncommon",
        "tag": "Uncommon",
        "single_use": True,
    },
    "speed_burst_legendary": {
        "id": "speed_burst_legendary",
        "localization_id": "speed_burst",
        "title": "Hiz Patlamasi",
        "description": "{value} saniye boyunca %60 hizli dusus + temizlenen her satir icin 1.75x puan!",
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
        "description": "PERK: V tusuyla ikinci bir parca saklayabilirsin.",
        "value": 1,
        "rarity": "legendary",
        "tag": "Legendary",
        "persistent": True,
    },
    "row_shuffle": {
        "id": "row_shuffle",
        "localization_id": "row_shuffle",
        "title": "Blok Karistirici",
        "description": "Alt {value} satirdaki bloklari karistirir, sansini dene!",
        "value": 3,
        "rarity": "common",
        "tag": "Common",
        "single_use": True,
    },
    "perk_synergy": {
        "id": "perk_synergy",
        "localization_id": "perk_synergy",
        "title": "Sinerji Bonus",
        "description": "PERK: Her aktif kart icin +%10 skor bonusu.",
        "value": 1,
        "rarity": "rare",
        "tag": "Rare",
        "persistent": True,
    },
    "line_bonus": {
        "id": "line_bonus",
        "localization_id": "line_bonus",
        "title": "Puan Carpani",
        "description": "Sonraki {value} satir temizlemede 2x puan.",
        "value": 4,
        "rarity": "rare",
        "tag": "Rare",
        "single_use": True,
        "payload": {"multiplier": 2.0},
    },
}


CARD_CHOICE_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "rescue_pick": {
        "goal_key": "tutorial_card_rescue_goal",
        "tip_key": "tutorial_card_rescue_tip",
        "goal_text": "Hedef: Tehlikeli tahtada en dogru kurtarma kartini sec.",
        "tip_text": "Parlak kart her zaman dogru kart degildir. Once tahtanin ihtiyacini oku.",
        "context_keys": [
            "tutorial_card_rescue_context_1",
            "tutorial_card_rescue_context_2",
        ],
        "context_lines": [
            "Durum: Delikli ve yuksek bir tahta.",
            "Oncelik: Nefes aldiran hamle secmek.",
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
            "clear_rows": "Dogru secim. Alt Supur tahtaya hemen alan acar ve baskiyi dusurur.",
            "peak_sculpt": "Kabul edilebilir secim. Tepeyi kesmek baskiyi azaltir ama alt taraftaki karmasayi tam cozmez.",
            "speed_burst_legendary": "Zayif secim. Hiz karti bu tahtada hatayi buyutur; once hayatta kalman gerekir.",
        },
    },
    "long_term_pick": {
        "goal_key": "tutorial_card_long_term_goal",
        "tip_key": "tutorial_card_long_term_tip",
        "goal_text": "Hedef: Guvenli oyunda en iyi uzun vadeli yatirimi sec.",
        "tip_text": "Tahta sakinse anlik kart yerine run boyunca deger ureten perk daha guclu olabilir.",
        "context_keys": [
            "tutorial_card_long_term_context_1",
            "tutorial_card_long_term_context_2",
        ],
        "context_lines": [
            "Durum: Duzenli ve alçak bir tahta.",
            "Oncelik: Uzun vadeli deger kazanmak.",
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
            "perk_second_pocket": "Dogru secim. Guvenli tahtada Ekstra Cep gibi kalici bir perk tum run boyunca deger uretir.",
            "clear_rows": "Zayif secim. Tahta zaten rahat; anlik temizlik burada gereksiz deger kaybi.",
            "row_shuffle": "Zayif secim. Sans karti sakin bir tahtayi sebepsiz yere bozabilir.",
        },
    },
    "synergy_pick": {
        "goal_key": "tutorial_card_synergy_goal",
        "tip_key": "tutorial_card_synergy_tip",
        "goal_text": "Hedef: Mevcut build ile en iyi sinerji kartini sec.",
        "tip_text": "Kart secimi tek kart gucu degil, mevcut build ile nasil calistigi uzerinden okunur.",
        "context_keys": [
            "tutorial_card_synergy_context_1",
            "tutorial_card_synergy_context_2",
        ],
        "context_lines": [
            "Aktif perkler: Ekstra Cep, Esnek Sinir.",
            "Oncelik: Build'i buyuten secimi bulmak.",
        ],
        "board_rows": [
            ".....X....",
            "....XXX...",
            "...XXXXX..",
            "..XXXXXX..",
        ],
        "current_piece": {"name": "J", "x": 3, "y": 0, "rotation": 0},
        "next_queue": ["T", "I", "S"],
        "card_choices": ["perk_synergy", "line_bonus", "row_shuffle"],
        "recommended_card_id": "perk_synergy",
        "acceptable_card_ids": [],
        "feedback_keys_by_card": {
            "perk_synergy": "tutorial_card_synergy_feedback_perk_synergy",
            "line_bonus": "tutorial_card_synergy_feedback_line_bonus",
            "row_shuffle": "tutorial_card_synergy_feedback_row_shuffle",
        },
        "feedback_by_card": {
            "perk_synergy": "Dogru secim. Halihazirda aktif perklerin oldugu icin Sinerji Bonus hemen buyuyen bir carpana donusur.",
            "line_bonus": "Zayif secim. Puan Carpani faydali olsa da bu dersin odagi mevcut perk zincirini buyutmek; tek basina build sinerjisi kurmaz.",
            "row_shuffle": "Zayif secim. Rastgelelik eklemek yerine aktif perklerden daha fazla deger cikarmalisin.",
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

    card = real_card
    card.update(tutorial_card)
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
    feedback_by_card = scenario_data.get("feedback_by_card", {}) if isinstance(scenario_data.get("feedback_by_card"), dict) else {}
    feedback_keys_by_card = scenario_data.get("feedback_keys_by_card", {}) if isinstance(scenario_data.get("feedback_keys_by_card"), dict) else {}

    if selected_id == recommended_id:
        success = True
        stars = 3
        title = t("tutorial_card_choice_title_correct", default="Dogru Secim")
    elif selected_id in acceptable_ids:
        success = True
        stars = 2
        title = t("tutorial_card_choice_title_acceptable", default="Kabul Edilebilir")
    else:
        success = False
        stars = 0
        title = t("tutorial_result_retry_title", default="Tekrar Dene")

    feedback_key = feedback_keys_by_card.get(selected_id)
    fallback_feedback = str(feedback_by_card.get(selected_id) or t("tutorial_card_choice_feedback_generic", default="Secimin bu tahta ihtiyacina iyi uymuyor."))
    feedback = t(str(feedback_key), default=fallback_feedback) if feedback_key else fallback_feedback
    chosen_card = get_card_preview(selected_id) or {"id": selected_id, "title": selected_id}

    return {
        "success": success,
        "stars": stars,
        "title": title,
        "feedback": feedback,
        "selected_card_id": selected_id,
        "selected_card_title": get_tutorial_card_title(chosen_card),
        "recommended_card_id": recommended_id,
        "recommended_card_title": get_tutorial_card_title(get_card_preview(recommended_id) or {"id": recommended_id, "title": recommended_id}),
    }