# Faz 3 — Oyun akışı doğrulama kaydı

Tarih: 2026-11-05

- Faz 3 odak kapısı: `10 passed`
- Faz 0/1/2 kümülatif kapı: `43 passed` (marker seçimi)
- Derleme: `py -3.12 -m compileall -q src tests` başarılı.

Uygulanan sözleşmeler:

- 20 görünür + 2 gizli satır tamponu fiziksel olarak Board üzerinde tutuluyor.
- Kısmi gizli kilit oyun bitirmiyor; tamamen gizli veya tampon dışı kilit lock-out oluyor.
- Sweep progress süresi çözünürlükten bağımsız 180 ms sözleşmesine bağlandı.
- Sprint/40L clear/fall sırasında otomatik gravity bekletilmiyor.
- ARE pending-spawn ve rotate/hold/drop tampon alanları tanımlandı.
- Inf-SDF mevcut anlık düşüş yolu korunup kabul testiyle ölçüldü.
