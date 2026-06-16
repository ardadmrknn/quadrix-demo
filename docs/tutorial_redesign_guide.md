# Quadrix Demo - Eğitim Modu ve Ana Menü Yeniden Tasarım Kılavuzu

Bu kılavuz, Quadrix Demo sürümünde yeni oyuncu akışını (FTUE) iyileştirmek, oyunu hızlı terk etme (churn) oranını düşürmek ve ana odak noktası olan "Card Mastery" (Kart Ustalığı) modunu öne çıkarmak amacıyla yapılacak kod düzenlemelerini içermektedir. Bu doküman, başka bir yapay zeka kodlama modelinin doğrudan uygulayabileceği adım adım talimatlar ve kod referansları ile hazırlanmıştır.

---

## Hedefler

1.  **Hızlı Başlangıç (Quick Start) Süresini Kısaltmak:** Ayrı ayrı yüklenen 5 ders yerine temel hareketleri tek bir ders altında birleştirmek.
2.  **Kart Mekaniğini İlk Dakikada Tanıtmak:** Hızlı başlangıcın sonuna oyuncunun kart gücünü deneyimleyeceği kısa bir kriz ve kart seçim senaryosu eklemek.
3.  **Görsel Hiyerarşiyi Güçlendirmek:** Ana menüdeki karmaşıklığı azaltmak için "Card Mastery" moduna "ÖNERİLEN / RECOMMENDED" rozeti eklemek ve diğer panelleri hafifçe karartmak.
4.  **Eğitim Sonu Yönlendirmesini (CTA) Optimize Etmek:** Eğitim bittiğinde oyuncuyu ana menüde kaybolmaya bırakmak yerine doğrudan ilk Card Mastery run'ına yönlendirmek.

---

## İlgili Dosyalar ve Kod Referansları

*   [src/tutorial_lessons.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/tutorial_lessons.py) - Bölüm ve ders tanımlamaları.
*   [src/tutorial.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/tutorial.py) - Eğitim modu çalışma zamanı (runtime) mantığı ve arayüzü.
*   [src/menu.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/menu.py) - Ana menü panellerinin ve görsel kartların çizildiği dosya.
*   [src/main.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/main.py) - Hızlı başlangıç ve tam eğitim modlarının başlatılma mantığı.
*   [src/localization.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/localization.py) - Metinlerin çevirileri.

---

## Adım Adım Uygulama Talimatları

### Adım 1: Temel Kontrollerin Tek Derste Birleştirilmesi

`quick_start` bölümündeki ders sayısını ve yükleme ekranlarını azaltmak için ilk 4 ders tek bir akışta birleştirilecektir.

1.  **[tutorial_lessons.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/tutorial_lessons.py) Güncellemesi:**
    *   `LESSONS` listesindeki `qs_move_lane`, `qs_rotate_fit`, `qs_soft_drop_control`, `qs_safe_hard_drop` derslerini kaldırın veya devre dışı bırakın.
    *   Bu derslerin yerine tek bir `qs_basic_controls` dersi tanımlayın:
        ```python
        {
            "id": "qs_basic_controls",
            "chapter": "quick_start",
            "kind": "legacy_step",
            "legacy_step": 1,
            "lesson_type": "drill",
            "title_key": "tutorial_lesson_basics_title",
            "title_fallback": "Temel Kontroller",
            "description_key": "tutorial_lesson_basics_desc",
            "description_fallback": "Hareket et, döndür ve parçayı sert düşürmeyle yerleştir.",
            "why_it_matters": "Oyunu kontrol etmek ve yerleşim yapmak her şeyin temelidir.",
            "difficulty": 1,
            "duration_seconds": 30,
            "skill_tags": ["movement", "rotation", "hard_drop"],
            "allowed_actions": ["move_left", "move_right", "rotate", "hard_drop"],
            "success_condition": "basics_combined_success",
        }
        ```

2.  **[tutorial.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/tutorial.py) Güncellemesi:**
    *   `TutorialMode` sınıfı içerisindeki `_setup_step` veya adım kontrol mekanizmasında tek tek adım geçişleri yerine, oyuncunun ekranda beliren yönlendirmeleri sırayla yapmasını sağlayın:
        *   Adım 1a: Oyuncu sola veya sağa hareket eder (Hareket tamamlandı kontrolü).
        *   Adım 1b: Hareket tamamlanınca ekrandaki yazı "Şimdi Döndür" olarak güncellenir (Döndürme tamamlandı kontrolü).
        *   Adım 1c: Döndürme tamamlanınca "Sert Düşürerek Kilitle" yazar ve oyuncu parçayı sert düşürdüğünde ders başarıyla biter.
    *   `success_condition` olarak `basics_combined_success` mantıksal kontrolünü ekleyin.

---

### Adım 2: Hızlı Başlangıca Kart Tanıtım Dersi Eklenmesi

Oyuncunun Quadrix'in asıl mekaniğini anlaması için hızlı başlangıcın sonuna kart seçimi adımı eklenmelidir.

1.  **[tutorial_lessons.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/tutorial_lessons.py) Güncellemesi:**
    *   `quick_start` chapter'ına yeni bir ders ekleyin:
        ```python
        {
            "id": "qs_card_introduction",
            "chapter": "quick_start",
            "kind": "card_choice",
            "scenario_id": "intro_rescue_pick",
            "lesson_type": "card_lab",
            "title_key": "tutorial_lesson_card_intro_title",
            "title_fallback": "İlk Kartın",
            "description_key": "tutorial_lesson_card_intro_desc",
            "description_fallback": "Sıkışan tahtayı temizlemek için doğru kartı seç ve kullan.",
            "why_it_matters": "Kartlar Quadrix'te hayatta kalmanın ve ustalaşmanın anahtarıdır.",
            "difficulty": 1,
            "duration_seconds": 30,
            "skill_tags": ["cards"],
            "allowed_actions": ["move_left", "move_right", "confirm"],
        }
        ```

2.  **[tutorial.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/tutorial.py) Runtime Senaryosu:**
    *   `_start_lesson` veya kart dersi başlangıcında, oyuncunun tahtasını (board) yapay olarak doldurarak bir kriz durumu yaratın (Örn: Board yüksekliğini 12 birime çıkarıp deliklerle doldurun).
    *   Oyuncuya iki kart seçeneği sunun:
        1.  *Satır Temizleyici (Row Clear):* En alttaki 3 satırı temizler.
        2.  *Rastgele Blok Yerleştirici:* Yararsız bir kart.
    *   Oyuncu doğru kartı seçtiğinde kartın çalışmasını sağlayın ve animasyon eşliğinde alt satırların yok olduğunu göstererek dersi başarıyla tamamlatın.

---

### Adım 3: Eğitim Sonu Yönlendirmesinin (CTA) Güçlendirilmesi

Oyuncu hızlı başlangıcı bitirdiğinde ana menüye yönlendirilmek yerine doğrudan oyuna sokulmalı veya çok net yönlendirilmelidir.

1.  **[tutorial.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/tutorial.py) `_progression_panel_play` Metodu Güncellemesi:**
    *   `_progression_panel_play` fonksiyonu normalde ana menüye (`'menu'`) döner. Bunu, doğrudan "Card Mastery" modunu başlatacak şekilde değiştirin:
        ```python
        def _progression_panel_play(self):
            self.progress_panel_active = False
            self.progress_panel_data = None
            return 'start_card_mastery' # Ana döngüye özel bir sinyal gönderin
        ```
2.  **[src/main.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/main.py) Oyun Döngüsü Entegrasyonu:**
    *   `main` oyun döngüsünde `TutorialMode`dan dönen sinyal `start_card_mastery` ise, ana menüyü göstermeden doğrudan `Card Mastery` oyun modunu (`game_mode='classic'` veya ilgili ana mod) başlatın.

---

### Adım 4: Ana Menü Kart Ustalığı Rozeti ve Diğer Panellerin Karartılması

Ana menüdeki bilişsel yükü azaltmak için görsel hiyerarşi kurun.

1.  **[src/menu.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/menu.py) Panellerin Karartılması (Dimming):**
    *   `_render_main_dashboard_tile` fonksiyonunda panel alpha değerini hesaplarken, yeni kullanıcı veya varsayılan durumlar için `new_gen_tetris` (Card Mastery) haricindeki panellerin alpha değerini düşürün:
        ```python
        # Orijinal alpha hesabı:
        # alpha = 230 if is_highlighted else 180
        
        # Yeni akış:
        is_card_mastery = (panel_key == 'new_gen_tetris')
        if not is_card_mastery and not is_highlighted:
            alpha = 90  # %50 oranında karartma uygulanır
        else:
            alpha = 230 if is_highlighted else 180
        ```
    *   Aynı karartma mantığını panel içeriklerinin çizildiği `_draw_dashboard_tile_flavor` ve metinlerin çizildiği kısımlarda da uygulayın. Oyuncu panelin üzerine mouse ile geldiğinde (hover) veya klavye/gamepad ile seçtiğinde panel normal parlaklığına dönmelidir.

2.  **[src/menu.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/menu.py) Önerilen Badgesi Ekleme:**
    *   `_render_main_dashboard_tile` fonksiyonunun sonuna, `panel_key == 'new_gen_tetris'` ise sol veya sağ üst köşeye şık bir "ÖNERİLEN / RECOMMENDED" badgesi çizecek kod ekleyin:
        ```python
        if panel_key == 'new_gen_tetris':
            # Rozet kutusu boyutları
            badge_w = sp(110)
            badge_h = sp(22)
            badge_rect = pygame.Rect(
                rect.x + sp(10),
                rect.y + sp(10),
                badge_w,
                badge_h
            )
            # Kırmızı/turuncu neon arka plan
            pygame.draw.rect(target_surface, (230, 50, 50), badge_rect, border_radius=sp(6))
            # Metin çizimi (Lokalize edilmiş)
            badge_text = t('menu_recommended_badge', default='RECOMMENDED')
            badge_font = retro_style.get_font(sp(11), bold=True)
            text_surf = badge_font.render(badge_text, True, (255, 255, 255))
            text_rect = text_surf.get_rect(center=badge_rect.center)
            target_surface.blit(text_surf, text_rect.topleft)
        ```

3.  **[src/localization.py](file:///c:/Users/arda%20demirkan/Desktop/v2_23022026/quadrix-demo/src/localization.py) Dil Eşleştirmesi:**
    *   Lokalizasyon dosyalarına veya json overrides dosyasına `menu_recommended_badge` key'ini ekleyin:
        ```json
        "menu_recommended_badge": {
            "tr": "ÖNERİLEN",
            "en": "RECOMMENDED"
        }
        ```

---

## Doğrulama ve Test Adımları

Değişiklikler yapıldıktan sonra yapay zekanın şu kontrolleri yapması istenir:
1.  Oyunu sıfır bir kullanıcı profiliyle başlatın.
2.  İlk açılıştaki pop-up ekranından "Hızlı Başlangıç" seçildiğinde 90 saniye altındaki yeni birleşik akışın hatasız çalıştığını test edin.
3.  Eğitim sonunda kart seçimi ekranının doğru şekilde kriz çözdüğünü doğrulayın.
4.  Eğitim bittiğinde "Çıkıp Oyna" seçeneğinin doğrudan Card Mastery run'ını başlattığından emin olun.
5.  Ana menüyü açarak Card Mastery dışındaki panellerin karartıldığını ve Card Mastery üzerinde kırmızı renkli "ÖNERİLEN" rozetinin düzgün şekilde hizalandığını gözle kontrol edin.
