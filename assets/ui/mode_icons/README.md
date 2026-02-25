# Mod Simgeleri Klasörü

Bu klasör, oyun modu seçim ekranında görüntülenecek PNG simgeleri içindir.

## Beklenen Dosyalar:

1. `sprint_mode_icon.png` - Sprint Mode simgesi
2. `ultra_mode_icon.png` - Ultra Mode simgesi
3. `zen_mode_icon.png` - Zen Mode simgesi
4. `tetris2_mode_icon.png` - Quadrix 2 simgesi
5. `wide_mode_icon.png` - Wide Mode simgesi
6. `survival_mode_icon.png` - Survival Mode simgesi
7. `cascade_mode_icon.png` - Cascade Mode simgesi

## Dosya ↔ Mod Bağlamı (hızlı kontrol)

| Dosya | Mod | Mod fikri | Önerilen neon vurgu |
|------|-----|----------|----------------------|
| `sprint_mode_icon.png` | Sprint Mode | 40 satır yarışı / hız | NEON_GOLD (255, 215, 0) |
| `ultra_mode_icon.png` | Ultra Mode | 2 dk skor baskısı | NEON_RED (255, 50, 80) + NEON_ORANGE (255, 150, 0) |
| `zen_mode_icon.png` | Zen Mode | Süresiz sakin oyun | NEON_GREEN (0, 255, 150) + NEON_CYAN (0, 240, 255) |
| `tetris2_mode_icon.png` | Quadrix 2 | Ekstra parçalar | NEON_MAGENTA (255, 0, 200) + NEON_CYAN (0, 240, 255) |
| `wide_mode_icon.png` | Wide Mode | 15x20 geniş alan | NEON_CYAN (0, 240, 255) |
| `survival_mode_icon.png` | Survival Mode | Hayatta kal / baskı | NEON_RED (255, 50, 80) + NEON_ORANGE (255, 150, 0) |
| `cascade_mode_icon.png` | Cascade Mode | Kademeli düşüş / akış | NEON_CYAN (0, 240, 255) |

## Özellikler:

- **Format**: PNG (şeffaf arka plan)
- **Boyut**: 256x256 piksel (önerilen)
- **Stil**: Neon cyberpunk, parlak renkler
- **Optimizasyon**: 50KB altında olması önerilir

## AI Prompt Rehberi:

Detaylı, “mod adıyla bağ kuran” prompt şablonları için ana dizindeki `MODE_ICONS_AI_PROMPTS.md` dosyasına bakın.

## Not:

Eğer bir simge dosyası yoksa, oyun otomatik olarak emoji fallback kullanacaktır (⚡, ⏱️, 🧘, vb.)
