# Faz 6 — Local PvP ağırlıklı sonuç modeli

## Ölçüm kapsamı

Kılavuzdaki S-10 kararı gereği mevcut ağırlıklar korunarak 0–2 örneği yeniden
çalıştırıldı. `src/pvp_game.py` içindeki sabitler şu şekilde kaldı:

- Skor karşılaştırması: 1 puan
- Satır karşılaştırması: 1 puan
- Açık tahta karşılaştırması: 2 puan
- Kazanma eşiği: 3 puan

Örnek: P1 skor ve satır karşılaştırmasını kazanıyor (1+1=2); P1 elendiği için
P2 açık tahta puanını alıyor (2). Sonuç `2-2`, kazanan `draw`.

## Uygunluk sonucu

Sonuç, ağırlıklı modelle tutarlı bir berabere kararıdır. Görünen açıklama
metni `2-2` puanını, berabere sonucunu ve “skor/satır 1, alan 2 puan” kuralını
belirtiyor. Kazananı seçen ağırlıklara dokunulmadı; bu örnek için ayrı bir
round skoru uygulanmadı. Kabul testi: `test_phase6_pvp_draw_rule.py`.

