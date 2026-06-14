# Stale-Check Kontrol Listesi (Kod ↔ Doküman Tutarlılığı)

Bu belge, kod güncellendiğinde markdown dokümanlarının eski kalıp kalmadığını hızlıca tarayan bir **operasyonel kontrol listesi**dir. Düzenli release veya büyük refactor sonrası 5-10 dakika içinde tekrar geçilebilir.

> **Bu dosya nedir?** Yaygın stale örüntüleri için kontrol listesi + hızlı tarama komutları.
> **Bu dosya ne değil?** Gerekli release prosedürü; kullanım opsiyoneldir.

## Doküman Hiyerarşisi (Hızlı Yönlendirme)

| Soru | Bak |
| --- | --- |
| "Ana giriş noktası nedir?" | [../README.md](../README.md) |
| "macOS'ta nasıl çalıştırırım?" | [guides/README_MACOS.md](guides/README_MACOS.md) |
| "Repo yapısı nedir?" | [PROJECT_STRUCTURE_TR.md](PROJECT_STRUCTURE_TR.md) |
| "Mystery kart sistemi nasıl çalışır?" | [CARD_PERK_INVENTORY_TR.md](CARD_PERK_INVENTORY_TR.md) |
| "Online PvP nasıl davranır?" | [ONLINE_PVP_FLOW_TR.md](ONLINE_PVP_FLOW_TR.md) |
| "Online PvP kod katmanları nedir?" | [ONLINE_PVP_ARCHITECTURE.md](ONLINE_PVP_ARCHITECTURE.md) |
| "Build ve Steam upload nasıl?" | [BUILD_AND_UPLOAD.md](BUILD_AND_UPLOAD.md) (generated) |
| "Steam playtest yayını nasıl?" | [STEAM_PLAYTEST_YAYIN_REHBERI_TR.md](STEAM_PLAYTEST_YAYIN_REHBERI_TR.md) (generated) |
| "Leaderboard kurulum / mod ↔ Steam adı?" | [STEAMWORKS_LEADERBOARD_SETUP_TR.md](STEAMWORKS_LEADERBOARD_SETUP_TR.md) |
| "Leaderboard operasyon / incident?" | [STEAM_LEADERBOARD_OPERATIONS_TR.md](STEAM_LEADERBOARD_OPERATIONS_TR.md) |

Eğer bir doküman bunlardan birinin yerini almaya çalışıyorsa: yanlış konumda. Stale işaretle.

## 1) Sürüm ve Lisans

- [ ] `pyproject.toml` içindeki `requires-python` değeri (`>=3.12`) README/guides ile aynı mı?
- [ ] `pyproject.toml` lisansı (`Proprietary`) README/guides ile çelişiyor mu?

## 2) Çalıştırma Komutları

- [ ] Ana komut güncel mi? (`py main.py` / `python3 main.py`)
- [ ] Eski komut (`python src/main.py`) aktif dokümanlarda kalmış mı? (Yalnızca arşivde olmalı.)
- [ ] Platform bazlı komutlar (Windows/macOS/Linux) doğru ayrılmış mı?

## 3) Test Komutları

- [ ] Birincil test akışı güncel mi? (`./scripts/test/run_tests.sh -q`)
- [ ] Pytest komutu Python 3.12 hedefli mi? (`python3.12 -m pytest -q`)
- [ ] Hedefli test örnekleri (`-k mystery`, `tests/test_markdown_doc_sync.py` vb.) gerçekten çalışıyor mu?

## 4) Build / Packaging

- [ ] Spec yolu doğru mu? (`packaging/specs/*.spec`)
- [ ] Build dokümanlarında makineye özel path var mı? (`C:\Users\...` gibi — tutulmamalı)
- [ ] Runtime config pathleri güncel mi? (`config/runtime/...`)
- [ ] Generated build/upload dokümanları (`docs/BUILD_AND_UPLOAD.md`, `docs/STEAM_PLAYTEST_YAYIN_REHBERI_TR.md`, `docs/EXE_APP_BRIDGE_ENTEGRASYON_ZORUNLULUKLARI_TR.md`) **elle düzenlenmemiş** mi? Düzenleme her zaman `tools/sync_markdown_docs.py` üzerinden olmalı.
- [ ] `python3 tools/sync_markdown_docs.py` "No Markdown doc changes needed" döndürüyor mu?

## 5) Lokalizasyon

- [ ] Desteklenen diller listesi kodla aynı mı?
- [ ] 11 dil dokümanlarda görünüyor mu? (TR/EN/DE/FR/ES/IT/PT/RU/JA/ZH/KO)

## 6) Steam / Online PvP Dokümanları

- [ ] Bridge derleme notları runtime gereksinimiyle karışmıyor mu?
- [ ] Runtime Python beklentisi açık mı? (proje seviyesi `>=3.12`)
- [ ] Bridge `.pyd` adlandırması güncel mi? (cp312 birincil hedef)
- [ ] `config/runtime/steam_appid.txt` referansları doğru mu?
- [ ] Online PvP **mimari** ve **akış** dokümanları rollerini birbirine karıştırmıyor mu?

## 7) Mystery Kart Sistemi

- [ ] `CARD_PERK_INVENTORY_TR.md` katalog sayısı `MysteryCardManager._build_catalog()` ile aynı mı?
- [ ] `card_xp` / `card_level` sistemi aktif olarak belgelenmiş mi?
- [ ] Anti-farm kuralı (`source='player'` dışındaki clear'lar XP üretmez) yazılı mı?
- [ ] Time capsule restore'un `pending_level_ups` ve `pending_choices` koruduğu belirtilmiş mi?

## 8) Leaderboard / Achievements

- [ ] Mod ↔ Steam adı eşleşmesi setup belgesi ile kod arasında tutarlı mı?
- [ ] Operations belgesindeki incident playbook'u güncel mi?
- [ ] Achievement listesinde 40 başarım, 17 stat sayısı korunuyor mu?
- [ ] `tests/test_lb_write.py` referansları **`tests/`** prefiksi ile mi?

## 9) Arşiv Ayrımı

- [ ] `docs/archive/` ve `plans/` / `reports/` / `todo/` altı dosyalar aktif rehberlere yanlış referans vermiyor mu?
- [ ] Arşivdeki eski içerikler aktif dokümanlara taşınmamış mı?
- [ ] Tarihsel kök neden analizleri ürün rehberi gibi konumlandırılmamış mı?

## 10) Kırık Link Taraması

```bash
# Repo kökünde tüm aktif markdown dosyalarındaki relative linkleri tara:
python3 - <<'PY'
import os, re, sys
ROOT = '.'
SKIP = ('.git/', 'node_modules/', 'dist/', '__pycache__/', '.pytest_cache/',
        'plans/', 'reports/', 'docs/archive/', 'todo/', 'diary/',
        'docs/steam_icin/', 'steamworks/sdk/', 'assets/gamepad_icon/promptfont/')
md = []
for root, _, files in os.walk(ROOT):
    if any(s in root for s in SKIP):
        continue
    for f in files:
        if f.endswith('.md'):
            md.append(os.path.join(root, f))
broken = []
for path in md:
    text = open(path, encoding='utf-8', errors='replace').read()
    for m in re.finditer(r'\]\(([^)]+)\)', text):
        target = m.group(1).split(' ')[0]
        if target.startswith(('http', '#', 'mailto:')):
            continue
        full = os.path.normpath(os.path.join(os.path.dirname(path), target.split('#', 1)[0]))
        if not os.path.exists(full):
            broken.append((path, target))
for b in broken:
    print(b)
sys.exit(1 if broken else 0)
PY
```

## 11) Hızlı Tarama Komutları

```bash
grep -RInE "Python 3\.8|python src/main\.py|tetris-game/|MIT License" README.md docs/
grep -RInE 'C:\\Users\\|kök dizinde zaten mevcut' docs/
grep -RInE "Desteklenen diller|TR, EN, DE, FR, ES, IT, PT, RU, JA, ZH, KO" README.md docs/ AGENTS.md
```

## 12) Bitiş Kriteri

- [ ] Aktif dokümanlarda kritik stale bulgu yok
- [ ] `python3 tools/sync_markdown_docs.py` temiz çıktı veriyor
- [ ] `pytest tests/test_markdown_doc_sync.py` geçiyor
- [ ] Yapılan düzeltmeler kısa raporla kaydedildi
- [ ] Arşiv dosyaları bilinçli olarak hariç tutuldu
