"""DE'de eksik olan ve TR'ye düşen 355 anahtarın detayı"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from localization import TRANSLATIONS, set_language, t

# Kategorilere ayır
set_language('de')

ui_critical = []   # Menü, buton, başlık gibi kullanıcı-görünür
gameplay = []      # Oyun içi mesajlar
guide_docs = []    # Rehber/doküman
misc = []          # Diğer

for key in sorted(TRANSLATIONS.keys()):
    if 'de' in TRANSLATIONS[key]:
        continue
    tr_val = TRANSLATIONS[key].get('tr', key)
    en_val = TRANSLATIONS[key].get('en', key)
    
    # Kategorize et
    if any(p in key for p in ['menu', 'btn', 'button', 'tab_', 'settings_', 'title', 'label', 'option']):
        ui_critical.append((key, tr_val, en_val))
    elif any(p in key for p in ['mode_', 'game_', 'hud_', 'score', 'level', 'combo', 'tetris']):
        gameplay.append((key, tr_val, en_val))
    elif any(p in key for p in ['guide_', 'tutorial_', 'help_', 'tip_']):
        guide_docs.append((key, tr_val, en_val))
    else:
        misc.append((key, tr_val, en_val))

print(f"=== DE'de Eksik Anahtar Dağılımı (toplam 355) ===")
print(f"  UI/Menü (kritik): {len(ui_critical)}")
print(f"  Oyun içi: {len(gameplay)}")
print(f"  Rehber/Doküman: {len(guide_docs)}")
print(f"  Diğer: {len(misc)}")

print(f"\n--- UI/Menü Kritik ({len(ui_critical)}) ---")
for key, tr, en in ui_critical[:30]:
    print(f"  {key}")
    print(f"    TR: {tr[:60]}")
    print(f"    EN: {en[:60]}")

if len(ui_critical) > 30:
    print(f"  ... ve {len(ui_critical) - 30} tane daha")

print(f"\n--- Oyun İçi ({len(gameplay)}) ---")
for key, tr, en in gameplay[:15]:
    print(f"  {key}")
    print(f"    TR: {tr[:60]}")
    print(f"    EN: {en[:60]}")

if len(gameplay) > 15:
    print(f"  ... ve {len(gameplay) - 15} tane daha")

# get_text fallback zinciri kodu
print(f"\n=== get_text() fallback zinciri analizi ===")
print("Kod: TRANSLATIONS[key].get(_current_language, .get('tr', .get('en', ...)))")
print("Sonuç: Eğer aktif dilde yoksa -> TR'ye düşüyor -> EN'ye düşüyor")
print()
print("Sorun: DE/FR/ES/IT/PT kullanıcıları eksik anahtarlarda")
print("       Türkçe metin görüyor (İngilizce değil)")
print()

# Bunun gerçek etkisi
print("=== Gerçek Etki Örnekleri ===")
examples = [
    'single_player',
    'mode_classic',
    'mode_sprint',
    'pause_title',
    'game_over_title',
]
for key in examples:
    if key in TRANSLATIONS and 'de' not in TRANSLATIONS[key]:
        print(f"  '{key}':")
        print(f"    Alman kullanıcı görüyor: '{TRANSLATIONS[key].get('tr', '?')}'")
        print(f"    Görmesi gereken: '{TRANSLATIONS[key].get('en', '?')}'")
