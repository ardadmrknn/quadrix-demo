# Faz 6 — Survival antivirüs eşiği ölçümü

## Ölçülen davranış

`SurvivalMode.update()` içinde antivirüs kontrolü, mevcut skorun son tetik
puanına `ANTIVIRUS_SCORE` eklenmesini geçtiğinde çalışıyor. Sabit değer
`ANTIVIRUS_SCORE = 5000` olarak kaldı ve tetiklenen değer tam 5000'in katına
yuvarlanarak `last_antivirus_score` alanına yazılıyor.

| Skor | Tetik | Son `last_antivirus_score` |
|---:|:---:|---:|
| 4.999 | Hayır | 0 |
| 5.000 | Evet | 5.000 |
| 10.000 | Evet | 10.000 |

Bu ölçüm, eşiğin her 5000 puanda bir yenileme yaptığını gösterir. Antivirüs
tetiklenince `consumed_count` sıfırlanır, enfeksiyonlar temizlenir ve mevcut
efekt korunur.

## Ertelenen karar

S-11 gereği eşik katsayısı değiştirilmedi. I-35 sarsıntı düzenlemesi de
ertelendi; kaynak değerleri zafer için `25 / 60` saniye, virüs game-over için
`30 / 60` saniye ve antivirüs için `15 / 60` saniye olarak doğrulandı. Yeni
eşik veya sarsıntı şiddeti ancak ayrı kullanıcı kararıyla ele alınabilir.

Kabul testi: `test_phase6_survival_shake_threshold.py`.

