# Steam Leaderboard Web API — Kritik Parametre Notları

> Son güncelleme: 24 Şubat 2026  
> AppID: 4428040 (Playtest)

---

## Sorun: `result:8` (k_EResultInvalidParam)

`SetLeaderboardScore` çağrısında `result:8` dönmesinin **en sık nedeni** parametre tipi yanlışlığıdır.

---

## Parametre Tipleri (Karıştırma → result:8)

| Endpoint | Parametre | Doğru Tip | Yanlış Tip |
|---|---|---|---|
| `SetLeaderboardScore` | `scoremethod` | **string** (`"KeepBest"`, `"ForceUpdate"`) | integer (`1`, `2`) |
| `GetLeaderboardEntries` | `datarequest` | **integer** (`0`, `1`, `2`) | string (`"RequestGlobal"`) |
| `GetLeaderboardEntries` | `rangestart` | **1** (1-tabanlı) | 0 (0-tabanlı değil) |
| `GetLeaderboardEntries` | `rangeend` | **N** (örn: `5`) | `N-1` |

### datarequest integer değerleri
```
0 = RequestGlobal
1 = RequestGlobalAroundUser / RequestAroundUser
2 = RequestFriends
```

### scoremethod string değerleri
```
"KeepBest"    → oyuncunun en iyi skoru sakla
"ForceUpdate" → her zaman üzerine yaz
```

---

## Steamworks Leaderboard Konfigürasyonu

Steam API response'unda dönen alan adları (`GetLeaderboardsForGame/v2/`):

```json
{
  "id": 19198572,
  "name": "quadrix_mystery",
  "entries": 0,
  "sortmethod": "Descending",
  "displaytype": "Numeric",
  "onlytrustedwrites": true,
  "onlyfriendsreads": false,
  "onlyusersinsameparty": false,
  "limitrangearounduser": 0,
  "limitglobaltopentries": 0
}
```

### Gerekli ayarlar
| Alan | Gereken Değer | Açıklama |
|---|---|---|
| `sortmethod` | `"Descending"` | Yüksek skor iyi |
| `displaytype` | `"Numeric"` | Sayısal gösterim |
| `onlytrustedwrites` | `true` | Publisher Web API yazabilsin |
| `onlyfriendsreads` | `false` | Herkes okuyabilsin (Global) |

> ⚠️ `onlyfriendsreads: true` → `GetLeaderboardEntries` entries boş döner, hata vermez!

---

## result:8 için Kontrol Listesi

1. **`scoremethod` string mi?** → `"KeepBest"` veya `"ForceUpdate"` (integer değil)
2. **`datarequest` integer mi?** → `0` (string `"RequestGlobal"` değil)
3. **`rangestart` 1'den mi başlıyor?** → Steam 1-tabanlı (0 değil)
4. **`onlytrustedwrites: true` mu?** → Steamworks'te ayarlanmış olmalı
5. **SteamID geçerli mi?** → Playteste kayıtlı bir hesap olmalı

---

## Örnek Çalışan Çağrılar

### Skor yazma (Python requests)
```python
requests.post(
    "https://partner.steam-api.com/ISteamLeaderboards/SetLeaderboardScore/v1/",
    data={
        "key": PUBLISHER_KEY,
        "appid": 4428040,
        "leaderboardid": 19198572,
        "steamid": "76561199XXXXXXXXX",
        "score": 99999,
        "scoremethod": "KeepBest",   # ← STRING
    }
)
# Başarılı cevap: {"result": {"result": 1, "score_changed": true, ...}}
```

### Skor okuma (Python requests)
```python
requests.get(
    "https://partner.steam-api.com/ISteamLeaderboards/GetLeaderboardEntries/v1/",
    params={
        "key": PUBLISHER_KEY,
        "appid": 4428040,
        "leaderboardid": 19198572,
        "datarequest": 0,    # ← INTEGER (0=Global)
        "rangestart": 1,     # ← 1-tabanlı
        "rangeend": 5,
    }
)
```

---

## Tanı Scripti

```
py .\tools\steam_diag_leaderboard.py
```

Tüm leaderboard'ların `Writes`/`Reads` durumunu, ham alan adlarını ve test yazma/okuma sonuçlarını gösterir.
