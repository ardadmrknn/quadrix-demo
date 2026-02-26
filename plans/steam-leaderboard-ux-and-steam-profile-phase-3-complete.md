## Phase 3 Complete: Liderlik Tablosu Top 10 Gösterimi Eklendi

Liderlik tablosu paneli artık 5 yerine 10 giriş gösteriyor; panel yüksekliği büyütüldü, satır yüksekliği dinamik olarak hesaplanıyor, aktif kullanıcının satırı mavi renk tonu ile vurgulanıyor.

**Files created/changed:**
- `src/menu.py`

**Functions created/changed:**
- `Menu._refresh_mystery_leaderboard_cache()` — limit=5 → limit=10 (global ve friends için)
- `Menu._draw_mystery_leaderboard_panel()` — aşağıdaki değişiklikler:
  - `panel_h = max(360, int(500 * scale))` (önceki sabit `min(300, ...)` yerine)
  - `max_rows = min(10, len(active_entries))` (önceki 5 yerine)
  - `row_h = max(s(26), (list_rect.height - s(10)) // max(1, max_rows))` — dinamik satır yüksekliği
  - Aktif kullanıcı `is_self` tespiti: steam_id mevcut oturumdakiyle karşılaştırılır
  - `is_self=True` satırları mavi tonlu arka plan ve daha parlak border ile çizilir

**Tests created/changed:**
- Mevcut liderlik tablosu testleri geçmeye devam ediyor (render logic unit test yok, görsel değişiklik)

**Review Status:** APPROVED

**Git Commit Message:**
```
feat: increase leaderboard panel to top 10 with active user highlight

- Fetch limit changed from 5 to 10 for both global and friends tabs
- Panel height enlarged, row count raised to max 10
- Dynamic row_h computed from available list height to prevent overflow
- Active user row highlighted with blue tint when steam_id matches current session
```
