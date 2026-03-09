"""Secure Steam leaderboard proxy (server-side).

Amaç:
- Steam publisher key'i istemciye vermeden leaderboard verisi sağlamak
- Friends endpoint'i için kısa ömürlü imzalı session token kullanmak
- Basit rate-limit ve güvenlik başlıkları uygulamak
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException


STEAM_WEB_API_BASE = "https://partner.steam-api.com"

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


def _resolve_app_id() -> int:
    raw = (os.getenv("STEAM_APP_ID", "") or "").strip()
    if raw:
        try:
            return int(raw)
        except Exception:
            return 0
    return _read_app_id_from_file()


def _normalize_env_secret(value: str | None) -> str:
    raw = str(value or "").strip()
    raw = raw.strip('"').strip("'")
    return raw.rstrip(",;").strip()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))


def _mask_ip(ip: str) -> str:
    ip = str(ip or "")
    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:3]) + ":*"
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3]) + ".*"
    return "unknown"


class InMemoryRateLimiter:
    def __init__(self, rate_per_sec: float = 0.8, burst: float = 15.0):
        self.rate = float(rate_per_sec)
        self.burst = float(burst)
        self._lock = threading.Lock()
        self._state: dict[str, tuple[float, float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._state.get(key, (self.burst, now))
            elapsed = max(0.0, now - last)
            tokens = min(self.burst, tokens + elapsed * self.rate)
            if tokens < 1.0:
                self._state[key] = (tokens, now)
                return False
            tokens -= 1.0
            self._state[key] = (tokens, now)
            return True


class SteamDirectGateway:
    """Steam Web API ile server-side konuşan gateway."""

    def __init__(self, app_id: int, publisher_key: str, timeout_seconds: float = 5.0):
        self.app_id = int(app_id)
        self.publisher_key = str(publisher_key or "").strip()
        self.timeout_seconds = float(timeout_seconds)
        self.last_error = ""
        self._leaderboard_id_cache: dict[str, int] = {}

    def is_ready(self) -> bool:
        return self.app_id > 0 and bool(self.publisher_key)

    def _get(self, endpoint: str, **params: Any) -> dict[str, Any]:
        url = f"{STEAM_WEB_API_BASE}/{endpoint}"
        response = requests.get(url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json() if response.content else {}

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

    def _find_leaderboard_id(self, leaderboard_name: str) -> int | None:
        try:
            payload = self._get(
                "ISteamLeaderboards/FindLeaderboard/v1/",
                key=self.publisher_key,
                appid=self.app_id,
                name=leaderboard_name,
            )
        except Exception:
            return None

        response = payload.get("response", {}) if isinstance(payload, dict) else {}
        if not isinstance(response, dict):
            return None

        direct_id = self._extract_leaderboard_id(response)
        if direct_id is not None:
            return direct_id
        nested = response.get("leaderboard")
        return self._extract_leaderboard_id(nested)

    def _load_leaderboard_ids(self) -> dict[str, int]:
        if self._leaderboard_id_cache:
            return self._leaderboard_id_cache

        payload = self._get(
            "ISteamLeaderboards/GetLeaderboardsForGame/v2/",
            key=self.publisher_key,
            appid=self.app_id,
        )
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

    def _resolve_mode_leaderboard_id(self, mode: str) -> int | None:
        lb_name = DEFAULT_MODE_TO_LEADERBOARD.get(mode)
        if not lb_name:
            self.last_error = f"Desteklenmeyen mod: {mode}"
            return None

        board_map = self._load_leaderboard_ids()
        board_id = board_map.get(lb_name)
        if board_id is None:
            board_id = self._find_leaderboard_id(lb_name)
            if board_id is None:
                self.last_error = f"Leaderboard bulunamadı: {lb_name}"
                return None
            board_map[lb_name] = board_id
        return board_id

    def fetch_entries(
        self,
        mode: str,
        *,
        data_request: str = "RequestGlobal",
        limit: int = 5,
        steam_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.is_ready():
            self.last_error = "Steam gateway hazır değil"
            return []

        safe_limit = max(1, min(int(limit or 5), 100))
        mode_key = str(mode or "").strip().lower()
        board_id = self._resolve_mode_leaderboard_id(mode_key)
        if board_id is None:
            return []

        # Steam API datarequest integer enum: 0=Global, 1=AroundUser, 2=Friends
        _DATA_REQUEST_MAP = {
            "RequestGlobal": 0,
            "RequestAroundUser": 1,
            "RequestGlobalAroundUser": 1,
            "RequestFriends": 2,
        }
        request_type_str = str(data_request or "RequestGlobal")
        request_type_int = _DATA_REQUEST_MAP.get(request_type_str, 0)
        is_global_request = request_type_int == 0
        base_params: dict[str, Any] = {
            "key": self.publisher_key,
            "appid": self.app_id,
            "leaderboardid": board_id,
            "datarequest": request_type_int,
        }
        if request_type_str in ("RequestFriends", "RequestAroundUser", "RequestGlobalAroundUser"):
            if not steam_id:
                self.last_error = f"{request_type_str} için steamid gerekli"
                return []
            base_params["steamid"] = str(steam_id)

        def _request_entries(req_params: dict[str, Any]) -> tuple[list[Any], str]:
            try:
                payload = self._get("ISteamLeaderboards/GetLeaderboardEntries/v1/", **req_params)
            except Exception as exc:
                return [], str(exc)

            if not isinstance(payload, dict):
                return [], ""

            # Steam bu endpoint'te "response" yerine "leaderboardEntryInformation" döndürüyor
            # Her iki yapıyı da dene
            response = (
                payload.get("leaderboardEntryInformation")
                or payload.get("response")
                or payload
            )
            if not isinstance(response, dict):
                return [], ""
            raw = (
                response.get("leaderboardEntries")
                or response.get("entries")
                or response.get("leaderboardentries")
                or []
            )
            return (raw if isinstance(raw, list) else []), ""

        raw_entries: list[Any] = []
        last_req_error = ""
        candidate_ranges: list[tuple[int, int]]
        if is_global_request:
            candidate_ranges = [
                (1, safe_limit),
                (0, max(0, safe_limit - 1)),
                (1, max(1, safe_limit - 1)),
                (0, safe_limit),
            ]
        else:
            candidate_ranges = [(0, max(0, safe_limit - 1))]

        for range_start, range_end in candidate_ranges:
            req_params = dict(base_params)
            req_params["rangestart"] = range_start
            req_params["rangeend"] = range_end

            entries_candidate, req_error = _request_entries(req_params)
            if req_error:
                last_req_error = req_error
                continue

            if entries_candidate:
                raw_entries = entries_candidate
                break

            if not raw_entries:
                raw_entries = entries_candidate

        if last_req_error and not raw_entries:
            self.last_error = last_req_error
            return []

        results: list[dict[str, Any]] = []
        for idx, raw in enumerate(raw_entries):
            if not isinstance(raw, dict):
                continue
            rank = raw.get("globalrank", raw.get("rank", idx + 1))
            score = raw.get("score", 0)
            sid = raw.get("steamid") or raw.get("steam_id") or raw.get("steamID") or ""
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
            results.append({"rank": rank, "score": score, "steam_id": str(sid), "details": details})

        self.last_error = ""
        return results[:safe_limit]

    def verify_steam_ticket(self, ticket_hex: str) -> tuple[bool, str, str]:
        """Steam ticket doğrula. Returns: (ok, steam_id, error)."""
        ticket = str(ticket_hex or "").strip()
        if not ticket:
            return False, "", "ticket boş"

        try:
            payload = self._get(
                "ISteamUserAuth/AuthenticateUserTicket/v1/",
                key=self.publisher_key,
                appid=self.app_id,
                ticket=ticket,
            )
        except Exception as exc:
            return False, "", str(exc)

        response = payload.get("response", {}) if isinstance(payload, dict) else {}
        params = response.get("params", {}) if isinstance(response, dict) else {}
        result = str(params.get("result", "")).upper()
        steam_id = str(params.get("steamid", "")).strip()

        if result == "OK" and steam_id:
            return True, steam_id, ""
        return False, "", f"ticket doğrulanamadı: {result or 'UNKNOWN'}"

    def fetch_player_summaries(self, steam_ids: list[str]) -> dict[str, dict[str, Any]]:
        """ISteamUser/GetPlayerSummaries/v2/ ile oyuncu bilgilerini getir.

        Returns: steam_id -> {personaname, avatar, avatarmedium, avatarfull, profileurl}
        """
        if not self.is_ready():
            self.last_error = "Steam gateway hazır değil"
            return {}

        clean_ids = [str(sid).strip() for sid in (steam_ids or []) if str(sid or "").strip()]
        if not clean_ids:
            return {}

        # Steam maksimum 100 ID alır; büyük listeleri parçalara böl
        results: dict[str, dict[str, Any]] = {}
        chunk_size = 100
        for i in range(0, len(clean_ids), chunk_size):
            chunk = clean_ids[i : i + chunk_size]
            try:
                payload = self._get(
                    "ISteamUser/GetPlayerSummaries/v2/",
                    key=self.publisher_key,
                    steamids=",".join(chunk),
                )
            except Exception as exc:
                self.last_error = str(exc)
                continue

            response = payload.get("response", {}) if isinstance(payload, dict) else {}
            players = response.get("players", []) if isinstance(response, dict) else []
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

    def _post_web(self, endpoint: str, **params: Any) -> dict[str, Any]:
        """POST to Steam partner API (form-encoded)."""
        import urllib.parse as _urlparse
        import urllib.request as _urlrequest
        import json as _json
        merged = {"key": self.publisher_key, "appid": self.app_id, **params}
        data = _urlparse.urlencode(merged).encode("ascii")
        url = f"{STEAM_WEB_API_BASE}/{endpoint}"
        req = _urlrequest.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with _urlrequest.urlopen(req, timeout=self.timeout_seconds) as resp:
            return _json.loads(resp.read().decode("utf-8", errors="replace"))

    def set_score(
        self,
        mode: str,
        steam_id: str,
        score: int,
        scoremethod: str = "KeepBest",
    ) -> bool:
        """Write score to Steam leaderboard via SetLeaderboardScore/v1/.

        scoremethod must be 'KeepBest' or 'ForceUpdate' (string — NOT int).
        Returns True if result==1.
        """
        lb_id = self._resolve_mode_leaderboard_id(mode)
        if not lb_id:
            return False
        try:
            body = self._post_web(
                "ISteamLeaderboards/SetLeaderboardScore/v1/",
                leaderboardid=lb_id,
                steamid=steam_id,
                score=int(score),
                scoremethod=scoremethod,
            )
            result_code = body.get("result", {}).get("result", -1)
            if result_code == 1:
                rank = body.get("result", {}).get("global_rank_new", 0)
                print(f"[Proxy] set_score OK: {mode} → {score} rank={rank}")
                return True
            hint = ""
            if result_code == 8:
                hint = " (InvalidParam: check scoremethod string, leaderboardid, appid)"
            print(f"[Proxy] set_score FAIL: {mode} result={result_code}{hint}")
            return False
        except Exception as exc:
            print(f"[Proxy] set_score error ({mode}): {exc}")
            return False


class SessionTokenManager:
    def __init__(self, secret: str, ttl_seconds: int = 900):
        self.secret = str(secret or "").encode("utf-8")
        self.ttl_seconds = int(ttl_seconds)

    def is_ready(self) -> bool:
        return bool(self.secret)

    def issue(self, steam_id: str) -> str:
        now = int(time.time())
        payload = {
            "steam_id": str(steam_id),
            "iat": now,
            "exp": now + self.ttl_seconds,
        }
        body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        sig = hmac.new(self.secret, body.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{body}.{sig}"

    def verify(self, token: str) -> tuple[bool, dict[str, Any], str]:
        if not self.is_ready():
            return False, {}, "token manager hazır değil"

        raw = str(token or "").strip()
        if not raw or "." not in raw:
            return False, {}, "token formatı geçersiz"

        body, sig = raw.rsplit(".", 1)
        expected = hmac.new(self.secret, body.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False, {}, "token imzası geçersiz"

        try:
            payload = json.loads(_b64url_decode(body).decode("utf-8"))
        except Exception:
            return False, {}, "token payload geçersiz"

        exp = int(payload.get("exp", 0) or 0)
        if int(time.time()) >= exp:
            return False, {}, "token süresi doldu"

        steam_id = str(payload.get("steam_id", "")).strip()
        if not steam_id:
            return False, {}, "token steam_id içermiyor"

        return True, payload, ""


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024

    app_id = _resolve_app_id()
    publisher_key = _normalize_env_secret(os.getenv("STEAM_WEB_API_KEY", ""))
    client_token = _normalize_env_secret(os.getenv("LEADERBOARD_CLIENT_TOKEN", ""))
    token_secret = _normalize_env_secret(os.getenv("LEADERBOARD_TOKEN_SECRET", ""))

    allowed_origins_raw = (os.getenv("LEADERBOARD_ALLOWED_ORIGINS", "") or "").strip()
    allowed_origins = {x.strip() for x in allowed_origins_raw.split(",") if x.strip()}

    gateway = SteamDirectGateway(app_id=app_id, publisher_key=publisher_key)
    token_manager = SessionTokenManager(secret=token_secret, ttl_seconds=900)
    limiter = InMemoryRateLimiter(rate_per_sec=0.8, burst=20)

    def json_error(message: str, status: int = 400):
        return jsonify({"ok": False, "error": message}), status

    def _client_ip() -> str:
        forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        return forwarded or (request.remote_addr or "unknown")

    def _check_client_token() -> tuple[bool, Any]:
        if not client_token:
            return True, None
        incoming = (request.headers.get("X-Client-Token", "") or "").strip()
        if not incoming or not hmac.compare_digest(incoming, client_token):
            return False, json_error("yetkisiz istemci", 401)
        return True, None

    def _extract_bearer_token() -> str:
        raw = (request.headers.get("Authorization", "") or "").strip()
        if raw.lower().startswith("bearer "):
            return raw[7:].strip()
        return ""

    @app.before_request
    def _security_gate():
        if request.method not in ("GET", "POST", "OPTIONS"):
            return json_error("method not allowed", 405)

        if request.method == "OPTIONS":
            return None

        ip = _client_ip()
        limit_key = f"{ip}:{request.path}"
        if not limiter.allow(limit_key):
            return json_error("çok fazla istek", 429)

        if request.path.startswith("/api/"):
            ok, failure = _check_client_token()
            if not ok:
                return failure
        return None

    @app.after_request
    def _set_security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Pragma"] = "no-cache"

        origin = (request.headers.get("Origin", "") or "").strip()
        if origin and origin in allowed_origins:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Client-Token"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    @app.get("/health")
    def health():
        return jsonify(
            {
                "ok": True,
                "steam_ready": gateway.is_ready(),
                "token_ready": token_manager.is_ready(),
            }
        )

    @app.post("/api/v1/auth/steam-ticket")
    def auth_steam_ticket():
        if not gateway.is_ready():
            return json_error("steam gateway hazır değil", 503)
        if not token_manager.is_ready():
            return json_error("token manager hazır değil", 503)

        if not request.is_json:
            return json_error("json body gerekli", 415)

        payload = request.get_json(silent=True) or {}
        ticket = str(payload.get("ticket", "") or "").strip()
        if not ticket:
            return json_error("ticket gerekli", 400)

        ok, steam_id, err = gateway.verify_steam_ticket(ticket)
        if not ok:
            return json_error(err or "ticket doğrulanamadı", 401)

        token = token_manager.issue(steam_id)
        return jsonify(
            {
                "ok": True,
                "session_token": token,
                "expires_in": token_manager.ttl_seconds,
                "steam_id": steam_id,
            }
        )

    @app.get("/api/v1/leaderboards/<mode>/global")
    def leaderboard_global(mode: str):
        if not gateway.is_ready():
            return json_error("steam gateway hazır değil", 503)

        try:
            limit = int(request.args.get("limit", "5") or 5)
        except Exception:
            limit = 5

        mode_key = str(mode or "").strip().lower()
        if mode_key not in DEFAULT_MODE_TO_LEADERBOARD:
            return json_error("desteklenmeyen mod", 400)

        entries = gateway.fetch_entries(mode_key, data_request="RequestGlobal", limit=limit)
        if not entries and gateway.last_error:
            return json_error(gateway.last_error, 502)

        return jsonify({"ok": True, "mode": mode_key, "scope": "global", "entries": entries})

    @app.get("/api/v1/leaderboards/<mode>/friends")
    def leaderboard_friends(mode: str):
        if not gateway.is_ready():
            return json_error("steam gateway hazır değil", 503)
        if not token_manager.is_ready():
            return json_error("token manager hazır değil", 503)

        try:
            limit = int(request.args.get("limit", "5") or 5)
        except Exception:
            limit = 5

        mode_key = str(mode or "").strip().lower()
        if mode_key not in DEFAULT_MODE_TO_LEADERBOARD:
            return json_error("desteklenmeyen mod", 400)

        bearer = _extract_bearer_token()
        ok, payload, err = token_manager.verify(bearer)
        if not ok:
            return json_error(err or "oturum doğrulanamadı", 401)

        steam_id = str(payload.get("steam_id", "")).strip()
        entries = gateway.fetch_entries(
            mode_key,
            data_request="RequestFriends",
            limit=limit,
            steam_id=steam_id,
        )
        if not entries and gateway.last_error:
            return json_error(gateway.last_error, 502)

        return jsonify({"ok": True, "mode": mode_key, "scope": "friends", "entries": entries})

    @app.get("/api/v1/players/summaries")
    def players_summaries():
        """Verilen Steam ID listesi için oyuncu adı ve avatar URL döndür."""
        if not gateway.is_ready():
            return json_error("steam gateway hazır değil", 503)

        raw_ids = (request.args.get("steamids", "") or "").strip()
        if not raw_ids:
            return json_error("steamids parametresi gerekli", 400)

        steam_ids = [sid.strip() for sid in raw_ids.split(",") if sid.strip()]
        if not steam_ids:
            return json_error("geçerli steamid bulunamadı", 400)

        if len(steam_ids) > 100:
            return json_error("maksimum 100 steamid", 400)

        summaries = gateway.fetch_player_summaries(steam_ids)
        return jsonify({"ok": True, "players": summaries})

    @app.post("/api/v1/leaderboards/<mode>/submit")
    def submit_score(mode: str):
        if not gateway.is_ready():
            return json_error("steam gateway hazır değil", 503)

        body = request.get_json(silent=True) or {}
        ticket = str(body.get("ticket", "")).strip()
        score = body.get("score")
        scoremethod = str(body.get("scoremethod", "KeepBest")).strip()

        if not ticket or score is None:
            return json_error("ticket and score required", 400)

        try:
            score = int(score)
        except (TypeError, ValueError):
            return json_error("score must be integer", 400)

        if scoremethod not in ("KeepBest", "ForceUpdate"):
            scoremethod = "KeepBest"

        ok, steam_id, err = gateway.verify_steam_ticket(ticket)
        if not ok:
            return json_error(f"ticket validation failed: {err}", 403)

        success = gateway.set_score(mode, steam_id, score, scoremethod=scoremethod)
        if success:
            return jsonify({"ok": True, "steam_id": steam_id, "score": score})
        return json_error("score write failed", 502)

    @app.errorhandler(Exception)
    def unhandled_error(exc):
        if isinstance(exc, HTTPException):
            return json_error(str(exc.description or exc.name), exc.code or 500)
        ip_masked = _mask_ip(_client_ip())
        print(f"[proxy-error] ip={ip_masked} path={request.path} err={exc}")
        return json_error("sunucu hatası", 500)

    return app


if __name__ == "__main__":
    web_app = create_app()
    host = os.getenv("LEADERBOARD_BIND_HOST", "127.0.0.1")
    port = int(os.getenv("LEADERBOARD_BIND_PORT", "8787") or 8787)
    web_app.run(host=host, port=port, debug=False)
