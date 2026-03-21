# Stale-Check Checklist (Kod ↔ Doküman Tutarlılığı)

> Not: Bu dosya opsiyonel bir yardımcı kontroldür; zorunlu release/checkpoint prosedürü değildir.

Bu kontrol listesi, kod güncellendiğinde markdown dosyalarının eski kalmasını önlemek için kullanılır.

## 1) Sürüm ve Lisans
- [ ] `pyproject.toml` içindeki `requires-python` değeri (`>=3.12`) README/guides ile aynı mı?
- [ ] `pyproject.toml` lisansı (`Proprietary`) README/guides ile çelişiyor mu?

## 2) Çalıştırma Komutları
- [ ] Ana komut güncel mi? (`py main.py` / `python3 main.py`)
- [ ] Eski komut (`python src/main.py`) aktif dokümanlarda kalmış mı?
- [ ] Platform bazlı komutlar (Windows/macOS/Linux) doğru ayrılmış mı?

## 3) Test Komutları
- [ ] Birincil test akışı güncel mi? (`./scripts/test/run_tests.sh -q`)
- [ ] Alternatif `pytest` komutu gerekiyorsa doğru ve tutarlı mı?

## 4) Build / Packaging
- [ ] Spec yolu doğru mu? (`packaging/specs/*.spec`)
- [ ] Build dokümanlarında makineye özel path var mı? (`C:\Users\...` gibi)
- [ ] Runtime config pathleri güncel mi? (`config/runtime/...`)

## 5) Lokalizasyon
- [ ] Desteklenen diller listesi kodla aynı mı?
- [ ] RU (Rusça) dahil 11 dil dokümanlarda görünüyor mu?
- [ ] Dil adları (TR/EN/DE/FR/ES/IT/PT/RU/JA/ZH/KO) tutarlı mı?

## 6) Steam / Online PvP Dokümanları
- [ ] Bridge derleme notları runtime gereksinimiyle karışmıyor mu?
- [ ] Runtime Python beklentisi açık mı? (proje seviyesi `>=3.12`)
- [ ] `steam_appid` gibi kritik dosya yolları güncel mi?

## 7) Arşiv Ayrımı
- [ ] `docs/archive/` altı dosyalar aktif rehberlerden ayrı değerlendirildi mi?
- [ ] Arşivdeki eski içerikler aktif dokümanlara taşınmamış mı?

## 8) Hızlı Tarama Komutları
```bash
grep -RInE "Python 3\.8|python src/main\.py|tetris-game/|MIT License" README.md docs/
grep -RInE "C:\\Users\\|kök dizinde zaten mevcut" docs/
grep -RInE "Desteklenen diller|TR, EN, DE, FR, ES, IT, PT, RU, JA, ZH, KO" README.md docs/ AGENTS.md
```

## 9) Bitiş Kriteri
- [ ] Aktif dokümanlarda kritik stale bulgu yok
- [ ] Yapılan düzeltmeler kısa raporla kaydedildi
- [ ] Arşiv dosyaları bilinçli olarak hariç tutuldu
