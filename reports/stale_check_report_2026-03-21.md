# Stale-Check Raporu — 2026-03-21

> Not: Bu rapor opsiyonel bir doküman hijyeni çıktısıdır; zorunlu release/checkpoint artefaktı değildir.

## Kapsam
- README ve aktif `docs/` içerikleri
- `pyproject.toml` ile sürüm/lisans karşılaştırması
- Lokalizasyon dil listesi doğrulaması

## Doğrulanan Gerçekler
- Python runtime gereksinimi: `>=3.12` (`pyproject.toml`)
- Lisans: `Proprietary` (`pyproject.toml`)
- Desteklenen diller: `TR, EN, DE, FR, ES, IT, PT, RU, JA, ZH, KO` (`src/localization.py`, `AGENTS.md`)

## Sonuçlar
- Aktif dokümanlarda kritik stale bulgu tespit edilmedi.
- README/guides tarafında dil listeleri RU dahil güncel.
- Çalıştırma komutları güncel akışla uyumlu (`py main.py`, `python3 main.py`).
- Build dokümanlarında runtime config pathleri `config/runtime/...` ile uyumlu.

## Bilinçli Hariç Tutulanlar
- `docs/archive/` altındaki eski içerikler (arşiv olduğu için stale kabul edilmedi).

## Not
- Gelecek güncellemelerde aynı prosedür için: `docs/STALE_CHECKLIST_TR.md`

## Yeniden Doğrulama (Aynı Gün)
- Checklist adımları manuel olarak tekrar çalıştırıldı.
- Aktif dokümanlarda kritik stale desenine rastlanmadı.
- Eşleşen bazı sonuçlar sadece `docs/STALE_CHECKLIST_TR.md` içindeki örnek komut/metin satırlarından geldi (beklenen durum).
