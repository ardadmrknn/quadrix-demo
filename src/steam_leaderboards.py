"""Steam leaderboard istemci katmanı (güvenli proxy modeli).

Bu modül varsayılan olarak Steam Web API'ye doğrudan gitmez.
İstemci sadece kendi backend'ine istek atar; Steam publisher key sadece backend'de tutulur.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

STEAM_WEB_API_BASE = "https://partner.steam-api.com"
DEFAULT_LOCAL_BACKEND_URL = "http://127.0.0.1:8787"


DEFAULT_MODE_TO_LEADERBOARD = {
    "classic": "quadrix_classic",
    "sprint": "quadrix_sprint",
    "ultra": "quadrix_ultra",
    "zen": "quadrix_zen",
    "mystery": "quadrix_mystery",
    "survival": "quadrix_survival",
    "cascade": "quadrix_cascade",
    "wide": "quadrix_wide",
    "hardcore": "quadrix_hardcore",
    "daily": "quadrix_daily",
    "tetris2": "quadrix_tetris2",
}


class SteamLeaderboardService:
    """Oyun istemcisinin backend leaderboard proxy istemcisi.

    Ortam değişkenleri:
    - LEADERBOARD_BACKEND_URL (zorunlu)
    - LEADERBOARD_CLIENT_TOKEN (opsiyonel)
    - LEADERBOARD_SESSION_TOKEN (friends endpoint için opsiyonel)
    """

    def __init__(
        self,
        backend_base_url: str | None = None,
        client_token: str | None = None,
        session_token: str | None = None,
        steam_ticket: str | None = None,
        app_id: int | None = None,
        publisher_key: str | None = None,
        current_steam_id: str | int | None = None,
        timeout_seconds: float = 5.0,
    ):
        raw_base = backend_base_url or os.getenv("LEADERBOARD_BACKEND_URL", "")
        self.backend_base_url = self._resolve_backend_base_url(raw_base)
        self.client_token = (client_token or os.getenv("LEADERBOARD_CLIENT_TOKEN", "")).strip()
        self.session_token = (session_token or os.getenv("LEADERBOARD_SESSION_TOKEN", "")).strip()
        self.steam_ticket = (steam_ticket or os.getenv("LEADERBOARD_STEAM_TICKET", "")).strip()
        self.app_id = self._resolve_app_id(app_id)
        self.publisher_key = (publisher_key or os.getenv("STEAM_WEB_API_KEY", "")).strip()
        self.current_steam_id = str(
            current_steam_id
            or os.getenv("STEAM_CURRENT_USER_ID", "")
            or os.getenv("STEAM_USER_ID", "")
            or ""
        ).strip()
        self.timeout_seconds = float(timeout_seconds)

        self._leaderboard_id_cache: dict[str, int] = {}
        self.last_error = ""

    @staticmethod
    def _resolve_backend_base_url(raw_base: str | None) -> str:
        base = str(raw_base or "").strip().rstrip("/")
        if base:
            return base
        return DEFAULT_LOCAL_BACKEND_URL

    @staticmethod
    def _read_app_id_from_file() -> int:
        try:
            root = Path(__file__).resolve().parents[1]
            appid_path = root / "steam_appid.txt"
            if not appid_path.exists():
                return 0
            raw = appid_path.read_text(encoding="utf-8").strip()
            return int(raw or 0)
        except Exception:
            return 0

    def _resolve_app_id(self, explicit_app_id: int | None) -> int:
        if explicit_app_id:
            try:
                return int(explicit_app_id)
            except Exception:
                return 0

        env_app_id = os.getenv("STEAM_APP_ID", "").strip()
        if env_app_id:
            try:
                return int(env_app_id)
            except Exception:
                return 0

        return self._read_app_id_from_file()

    def _humanize_network_error(self, exc: Exception) -> str:
        raw = str(exc)
        lowered = raw.lower()

        if "127.0.0.1" in lowered or "localhost" in lowered:
            return "Leaderboard servisine bağlanılamadı (127.0.0.1:8787). Proxy kapalı olabilir. `py backend/steam_leaderboard_proxy.py` ile başlatın."
        if "max retries exceeded" in lowered or "newconnectionerror" in lowered or "failed to establish a new connection" in lowered:
            return "Leaderboard servisine bağlantı kurulamadı. Ağ bağlantısını ve backend adresini kontrol edin."
        if "timed out" in lowered:
            return "Leaderboard isteği zaman aşımına uğradı. Sunucu yavaş veya erişilemiyor olabilir."
        if "name or service not known" in lowered or "nameresolutionerror" in lowered:
            return "Leaderboard sunucu adresi çözümlenemedi (DNS). URL'yi kontrol edin."
        if "ssl" in lowered or "certificate" in lowered:
            return "SSL/TLS doğrulama hatası. Sunucu sertifikasını ve saat ayarını kontrol edin."

        return raw

    def is_configured(self) -> bool:
        return self._is_backend_mode() or self._is_direct_mode()

    def _is_backend_mode(self) -> bool:
        return bool(self.backend_base_url)

    def _is_direct_mode(self) -> bool:
        return self.app_id > 0 and bool(self.publisher_key)

    def set_session_token(self, token: str | None):
        self.session_token = (token or "").strip()

    def _build_headers(self, needs_auth: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "QuadrixClient/1.0",
        }
        if self.client_token:
            headers["X-Client-Token"] = self.client_token
        if needs_auth and self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"
        return headers

    def _get_json(self, path: str, *, needs_auth: bool = False, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._is_backend_mode():
            self.last_error = "LEADERBOARD_BACKEND_URL tanımlı değil."
            return {}

        try:
            response = requests.get(
                f"{self.backend_base_url}{path}",
                headers=self._build_headers(needs_auth=needs_auth),
                params=params or {},
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            self.last_error = self._humanize_network_error(exc)
            return {}

        if response.status_code >= 400:
            try:
                payload = response.json()
            except Exception:
                payload = {}
            self.last_error = str(payload.get("error") or f"HTTP {response.status_code}")
            return {}

        try:
            payload = response.json()
            self.last_error = ""
            return payload if isinstance(payload, dict) else {}
        except Exception as exc:
            self.last_error = str(exc)
            return {}

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._is_backend_mode():
            self.last_error = "LEADERBOARD_BACKEND_URL tanımlı değil."
            return {}

        try:
            response = requests.post(
                f"{self.backend_base_url}{path}",
                headers={
                    **self._build_headers(needs_auth=False),
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            self.last_error = self._humanize_network_error(exc)
            return {}

        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = {}
            self.last_error = str(body.get("error") or f"HTTP {response.status_code}")
            return {}

        try:
            body = response.json()
            self.last_error = ""
            return body if isinstance(body, dict) else {}
        except Exception as exc:
            self.last_error = str(exc)
            return {}

    def authenticate_with_steam_ticket(self, ticket: str | None = None) -> bool:
        """Steam ticket ile backend session token alır.

        Başarılı olursa `self.session_token` set edilir.
        """
        raw_ticket = (ticket or self.steam_ticket or "").strip()
        if not raw_ticket:
            self.last_error = "Steam ticket gerekli"
            return False

        payload = self._post_json("/api/v1/auth/steam-ticket", {"ticket": raw_ticket})
        token = str(payload.get("session_token", "") or "").strip()
        if not token:
            if not self.last_error:
                self.last_error = "Session token alınamadı"
            return False

        self.session_token = token
        return True

    def _direct_get(self, endpoint: str, **params: Any) -> dict[str, Any]:
        if not self._is_direct_mode():
            self.last_error = "Direct Steam modu için STEAM_APP_ID ve STEAM_WEB_API_KEY gerekli."
            return {}

        url = f"{STEAM_WEB_API_BASE}/{endpoint}"
        merged = {"key": self.publisher_key, "appid": self.app_id, **params}
        try:
            response = requests.get(url, params=merged, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json() if response.content else {}
            self.last_error = ""
            return payload if isinstance(payload, dict) else {}
        except Exception as exc:
            self.last_error = self._humanize_network_error(exc)
            return {}

    @staticmethod
    def _extract_leaderboard_id(raw: Any) -> int | None:
        candidates: list[Any] = []
        if isinstance(raw, dict):
            candidates.extend(
                [
                    raw.get("leaderboardid"),
                    raw.get("leaderboard_id"),
                    raw.get("id"),
                ]
            )
        else:
            candidates.append(raw)

        for value in candidates:
            try:
                if value is None:
                    continue
                return int(value)
            except Exception:
                continue
        return None

    def _find_direct_leaderboard_id(self, leaderboard_name: str) -> int | None:
        payload = self._direct_get(
            "ISteamLeaderboards/FindLeaderboard/v1/",
            name=leaderboard_name,
        )
        response = payload.get("response", {}) if isinstance(payload, dict) else {}
        if not isinstance(response, dict):
            return None

        direct_id = self._extract_leaderboard_id(response)
        if direct_id is not None:
            return direct_id
        nested = response.get("leaderboard")
        return self._extract_leaderboard_id(nested)

    def _load_direct_leaderboard_ids(self) -> dict[str, int]:
        if self._leaderboard_id_cache:
            return self._leaderboard_id_cache

        payload = self._direct_get("ISteamLeaderboards/GetLeaderboardsForGame/v2/")
        response = payload.get("response", {}) if isinstance(payload, dict) else {}
        raw_boards = response.get("leaderboards", []) if isinstance(response, dict) else []

        cache: dict[str, int] = {}
        for board in raw_boards:
            if not isinstance(board, dict):
                continue
            name = str(board.get("name", "")).strip()
            board_id = self._extract_leaderboard_id(board)
            if not name:
                continue
            if board_id is None:
                continue
            cache[name] = board_id

        self._leaderboard_id_cache = cache
        return cache

    def _fetch_direct_entries(self, mode: str, *, data_request: str, limit: int, steam_id: str | None = None) -> list[dict[str, Any]]:
        lb_name = DEFAULT_MODE_TO_LEADERBOARD.get(str(mode or "").strip().lower())
        if not lb_name:
            self.last_error = f"Desteklenmeyen mod: {mode}"
            return []

        leaderboard_map = self._load_direct_leaderboard_ids()
        leaderboard_id = leaderboard_map.get(lb_name)
        if leaderboard_id is None:
            leaderboard_id = self._find_direct_leaderboard_id(lb_name)
            if leaderboard_id is None:
                self.last_error = f"Steam leaderboard bulunamadı: {lb_name}"
                return []
            leaderboard_map[lb_name] = leaderboard_id

        safe_limit = max(1, min(int(limit or 3), 100))
        # Steam API datarequest integer enum: 0=Global, 1=AroundUser, 2=Friends
        _DATA_REQUEST_MAP = {
            "RequestGlobal": 0,
            "RequestAroundUser": 1,
            "RequestGlobalAroundUser": 1,
            "RequestFriends": 2,
        }
        data_request_str = str(data_request or "RequestGlobal")
        data_request_int = _DATA_REQUEST_MAP.get(data_request_str, 0)
        params: dict[str, Any] = {
            "leaderboardid": leaderboard_id,
            "datarequest": data_request_int,
            "rangestart": 1,
            "rangeend": safe_limit,
        }
        if data_request_str in ("RequestFriends", "RequestAroundUser", "RequestGlobalAroundUser"):
            sid = str(steam_id or self.current_steam_id or "").strip()
            if not sid:
                self.last_error = f"{data_request_str} için steam_id gerekli"
                return []
            params["steamid"] = sid

        payload = self._direct_get("ISteamLeaderboards/GetLeaderboardEntries/v1/", **params)
        # GetLeaderboardEntries/v1/ root key'i "leaderboardEntryInformation"'dır, "response" değil
        lb_info = payload.get("leaderboardEntryInformation", {}) if isinstance(payload, dict) else {}
        return self._normalize_entries(lb_info.get("leaderboardEntries") or lb_info.get("entries"))[:safe_limit]

    @staticmethod
    def _normalize_entries(raw_entries: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_entries, list):
            return []

        results: list[dict[str, Any]] = []
        for idx, raw in enumerate(raw_entries):
            if not isinstance(raw, dict):
                continue
            # Steam Web API: "globalrank" / "steamid" — proxy backend: "rank" / "steam_id"
            rank = raw.get("rank") or raw.get("globalrank") or idx + 1
            score = raw.get("score", 0)
            steam_id = raw.get("steam_id") or raw.get("steamid") or ""
            details = raw.get("details", [])

            try:
                rank = int(rank)
            except Exception:
                rank = idx + 1
            try:
                score = int(score)
            except Exception:
                score = 0
            if not isinstance(details, list):
                details = []

            results.append(
                {
                    "rank": rank,
                    "score": score,
                    "steam_id": str(steam_id),
                    "details": details,
                }
            )
        return results

    def fetch_mode_highscores(self, mode: str, limit: int = 3) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit or 3), 100))
        if self._is_backend_mode():
            payload = self._get_json(
                f"/api/v1/leaderboards/{mode}/global",
                params={"limit": safe_limit},
            )
            entries = self._normalize_entries(payload.get("entries"))
            if entries:
                return entries
            if (not payload) and self.last_error and self._is_direct_mode():
                return self._fetch_direct_entries(mode, data_request="RequestGlobal", limit=safe_limit)
            return entries
        return self._fetch_direct_entries(mode, data_request="RequestGlobal", limit=safe_limit)

    def fetch_mode_friend_highscores(self, mode: str, steam_id: str | int | None = None, limit: int = 3) -> list[dict[str, Any]]:
        """Friends skorlarını döndürür.

        Sıra: proxy backend (session_token ile) → direct Steam Web API (publisher_key ile).
        Buradaki steam_id parametresi geriye dönük uyumluluk için korunmuştur.
        """
        safe_limit = max(1, min(int(limit or 3), 100))
        sid = str(steam_id or self.current_steam_id or "").strip() or None

        if self._is_backend_mode():
            # Önce proxy üzerinden token almayı dene
            if not self.session_token and self.steam_ticket:
                self.authenticate_with_steam_ticket(self.steam_ticket)

            if self.session_token:
                # Proxy üzerinden arkadaş listesini çek
                payload = self._get_json(
                    f"/api/v1/leaderboards/{mode}/friends",
                    needs_auth=True,
                    params={"limit": safe_limit},
                )
                entries = self._normalize_entries(payload.get("entries"))
                if entries:
                    return entries

            # Proxy auth başarısız veya boş döndü — direct Steam Web API'ye geç
            if self._is_direct_mode():
                return self._fetch_direct_entries(
                    mode,
                    data_request="RequestFriends",
                    limit=safe_limit,
                    steam_id=sid,
                )

            self.last_error = "friends_auth_required"
            return []

        return self._fetch_direct_entries(
            mode,
            data_request="RequestFriends",
            limit=safe_limit,
            steam_id=sid,
        )

    def fetch_all_mode_highscores(self, modes: list[str], limit: int = 3) -> dict[str, list[dict[str, Any]]]:
        mode_scores: dict[str, list[dict[str, Any]]] = {}
        for mode in modes:
            mode_scores[mode] = self.fetch_mode_highscores(mode, limit=limit)
        return mode_scores

    def fetch_player_summaries(self, steam_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Verilen Steam ID'leri için oyuncu adı ve avatar URL döndür.

        Returns: steam_id -> {personaname, avatar, avatarmedium, avatarfull}
        Boş dict döner: servis yapılandırılmamış, ID listesi boşsa veya hata oluşursa.
        """
        clean_ids = [str(sid).strip() for sid in (steam_ids or []) if str(sid or "").strip()]
        if not clean_ids:
            return {}

        if self._is_backend_mode():
            raw = self._get_json(
                "/api/v1/players/summaries",
                params={"steamids": ",".join(clean_ids[:100])},
            )
            players = raw.get("players")
            if isinstance(players, dict):
                return players
            return {}

        # Direkt mod (şu an sadece backend destekli - future proof)
        return {}
