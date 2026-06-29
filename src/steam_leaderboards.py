"""Steam leaderboard istemci katmanı (güvenli proxy modeli).

Bu modül varsayılan olarak Steam Web API'ye doğrudan gitmez.
İstemci sadece kendi backend'ine istek atar; Steam publisher key sadece backend'de tutulur.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from leaderboard_rank_utils import rerank_entries_for_local_subset

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
        self.app_id = self._normalize_app_id(self._resolve_app_id(app_id))
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
        return base

    @staticmethod
    def _normalize_app_id(raw_app_id: Any) -> int:
        try:
            app_id = int(raw_app_id or 0)
        except Exception:
            return 0
        return app_id if app_id > 0 else 0

    def _get_direct_app_id(self) -> int:
        app_id = self._normalize_app_id(self.app_id)
        self.app_id = app_id
        return app_id

    def _get_direct_publisher_key(self) -> str:
        publisher_key = str(self.publisher_key or "").strip()
        self.publisher_key = publisher_key
        return publisher_key

    @staticmethod
    def _read_app_id_from_file() -> int:
        try:
            root = Path(__file__).resolve().parents[1]
            candidates = [
                root / "config" / "runtime" / "steam_appid.txt",
                root / "steam_appid.txt",
            ]
            for appid_path in candidates:
                if not appid_path.exists():
                    continue
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

        leaderboard_app_id = os.getenv("LEADERBOARD_APP_ID", "").strip()
        if leaderboard_app_id:
            try:
                return int(leaderboard_app_id)
            except Exception:
                return 0

        env_app_id = os.getenv("STEAM_APP_ID", "").strip()
        if env_app_id:
            try:
                return int(env_app_id)
            except Exception:
                return 0

        steam_app_id = os.getenv("SteamAppId", "").strip()
        if steam_app_id:
            try:
                return int(steam_app_id)
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
        return self._get_direct_app_id() > 0 and bool(self._get_direct_publisher_key())

    def set_session_token(self, token: str | None):
        self.session_token = (token or "").strip()

    def _build_headers(self, needs_auth: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "QuadrixClient/1.0",
        }
        app_id = self._get_direct_app_id()
        if app_id > 0:
            headers["X-Quadrix-App-Id"] = str(app_id)
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

    def submit_score(
        self,
        mode: str,
        score: int,
        ticket: str | None = None,
        scoremethod: str = "KeepBest",
    ) -> bool:
        """Submit score to leaderboard via backend proxy.

        Requires backend to be configured (LEADERBOARD_BACKEND_URL env var).
        Returns True on success.
        """
        if not self._is_backend_mode():
            return False
        if ticket is None:
            return False
        try:
            result = self._post_json(
                f"/api/v1/leaderboards/{mode}/submit",
                {"ticket": ticket, "score": int(score), "scoremethod": scoremethod},
            )
            return bool(result.get("ok"))
        except Exception as exc:
            print(f"[SteamLeaderboardService] submit_score error: {exc}")
            return False

    def _direct_get(self, endpoint: str, **params: Any) -> dict[str, Any]:
        if not self._is_direct_mode():
            self.last_error = "Direct Steam modu için STEAM_APP_ID ve STEAM_WEB_API_KEY gerekli."
            return {}

        url = f"{STEAM_WEB_API_BASE}/{endpoint}"
        merged = {
            "key": self._get_direct_publisher_key(),
            "appid": self._get_direct_app_id(),
            **params,
        }
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
        range_start = 1
        range_end = safe_limit
        if data_request_str == "RequestFriends":
            # Steam Web API GetLeaderboardEntries arkadaş filtresini DESTEKLEMIYOR —
            # datarequest=2 gönderilse bile global sonuçlar döner. Bunun yerine
            # Steam SDK (DownloadLeaderboardEntries + k_ELeaderboardDataRequestFriends)
            # kullanılmalıdır. SDK available ise oradan çek; yoksa boş dön.
            try:
                import steam_integration as _si  # type: ignore[import]
                if _si.is_available():
                    sdk_entries = _si.fetch_friend_scores(mode, limit=safe_limit)
                    if sdk_entries is not None:
                        return sdk_entries
            except Exception:
                pass
            self.last_error = "friends_sdk_required"
            return []
        elif data_request_str in ("RequestAroundUser", "RequestGlobalAroundUser"):
            half = max(1, safe_limit // 2)
            range_start = -half
            range_end = half
        params: dict[str, Any] = {
            "leaderboardid": leaderboard_id,
            "datarequest": data_request_int,
            "rangestart": range_start,
            "rangeend": range_end,
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
            # Proxy boş/hatalı döndüyse → direct Steam Web API fallback
            if self._is_direct_mode():
                direct_entries = self._fetch_direct_entries(mode, data_request="RequestGlobal", limit=safe_limit)
                if direct_entries:
                    return direct_entries
            return entries
        if self._is_direct_mode():
            return self._fetch_direct_entries(mode, data_request="RequestGlobal", limit=safe_limit)
        return []

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
                    return rerank_entries_for_local_subset(entries)

            # Proxy auth başarısız veya boş döndü — direct Steam Web API'ye geç
            if self._is_direct_mode():
                return rerank_entries_for_local_subset(self._fetch_direct_entries(
                    mode,
                    data_request="RequestFriends",
                    limit=safe_limit,
                    steam_id=sid,
                ))

            self.last_error = "friends_auth_required"
            return []

        return rerank_entries_for_local_subset(self._fetch_direct_entries(
            mode,
            data_request="RequestFriends",
            limit=safe_limit,
            steam_id=sid,
        ))

    def fetch_all_mode_highscores(self, modes: list[str], limit: int = 3) -> dict[str, list[dict[str, Any]]]:
        mode_scores: dict[str, list[dict[str, Any]]] = {}
        for mode in modes:
            mode_scores[mode] = self.fetch_mode_highscores(mode, limit=limit)
        return mode_scores

    def fetch_player_summaries(self, steam_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Verilen Steam ID'leri için oyuncu adı ve avatar URL döndür.

        Birincil kaynak: proxy backend veya direct Steam Web API (avatar URL'leri burada gelir).
        Yedek isim kaynağı: yerel Steam SDK (GetFriendPersonaName).
        Returns: steam_id -> {personaname, avatar, avatarmedium, avatarfull, profileurl}
        Boş veya kısmi dict döner.
        """
        clean_ids = [str(sid).strip() for sid in (steam_ids or []) if str(sid or "").strip()]
        if not clean_ids:
            return {}

        api_results: dict[str, dict[str, Any]] = {}
        if self._is_backend_mode():
            raw = self._get_json(
                "/api/v1/players/summaries",
                params={"steamids": ",".join(clean_ids[:100])},
            )
            players = raw.get("players")
            if isinstance(players, dict) and players:
                api_results = players
            # Backend boş döndüyse ve direct de yapılandırıldıysa direct'e düş
            if not api_results and self._is_direct_mode():
                api_results = self._fetch_player_summaries_direct(clean_ids)
        elif self._is_direct_mode():
            api_results = self._fetch_player_summaries_direct(clean_ids)

        sdk_names: dict[str, str] = {}
        ids_needing_sdk = [sid for sid in clean_ids if not api_results.get(sid, {}).get("personaname")]
        if ids_needing_sdk:
            try:
                import steam_integration as si
                if si.is_available():
                    for sid in ids_needing_sdk:
                        name = si.get_friend_persona_name(sid)
                        if name:
                            sdk_names[sid] = name
                        else:
                            si.request_user_information(sid, require_name_only=False)
            except Exception as exc:
                print(f"[SteamLeaderboardService] SDK oyuncu bilgisi alma hatası: {exc}")

        final_results: dict[str, dict[str, Any]] = {}
        for sid in clean_ids:
            final_info: dict[str, Any] = {}
            if sid in api_results:
                final_info.update(api_results[sid])
            if not final_info.get("personaname") and sid in sdk_names:
                final_info["personaname"] = sdk_names[sid]
            if final_info:
                final_results[sid] = final_info

        return final_results
    def _fetch_player_summaries_direct(self, clean_ids: list[str]) -> dict[str, dict[str, Any]]:
        """ISteamUser/GetPlayerSummaries/v2/ endpoint'ine direkt GET atar.

        appid gönderilmez; sadece publisher key ve steamids kullanılır.
        Sonuçlar: steam_id -> {personaname, avatar, avatarmedium, avatarfull, profileurl}
        """
        results: dict[str, dict[str, Any]] = {}
        chunk_size = 100
        for i in range(0, len(clean_ids), chunk_size):
            chunk = clean_ids[i : i + chunk_size]
            url = f"{STEAM_WEB_API_BASE}/ISteamUser/GetPlayerSummaries/v2/"
            params: dict[str, Any] = {
                "key": self._get_direct_publisher_key(),
                "steamids": ",".join(chunk),
            }
            try:
                response = requests.get(url, params=params, timeout=self.timeout_seconds)
                response.raise_for_status()
                payload = response.json() if response.content else {}
            except Exception as exc:
                self.last_error = self._humanize_network_error(exc)
                return results  # Kısmi sonuçlarla dön; yıkıcı olmayan hata

            response_obj = payload.get("response", {}) if isinstance(payload, dict) else {}
            players = response_obj.get("players", []) if isinstance(response_obj, dict) else []
            for player in players:
                if not isinstance(player, dict):
                    continue
                sid = str(player.get("steamid", "")).strip()
                if not sid:
                    continue
                results[sid] = {
                    "personaname": str(player.get("personaname", "") or ""),
                    "avatar": str(player.get("avatar", "") or ""),
                    "avatarmedium": str(player.get("avatarmedium", "") or ""),
                    "avatarfull": str(player.get("avatarfull", "") or ""),
                    "profileurl": str(player.get("profileurl", "") or ""),
                }

        if results:
            self.last_error = ""
        return results
