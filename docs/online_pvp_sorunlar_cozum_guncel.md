# Son 5 Git Pull Ozeti

Bu not 2 Mayis 2026 tarihinde hazirlandi. Analiz, git reflog icindeki son 5 pull kaydi uzerinden yapildi ve yalnizca pull ile gelen commitleri kapsiyor. Pull sonrasinda bu makinede olusan lokal commitler bu ozetin disinda tutuldu.

## Inceleme Yontemi

- Reflog kayitlari icinden son 5 pull olayi cikarildi.
- Her pull icin baslangic ve bitis commit araligi belirlendi.
- Ilgili commit diffleri, dokunan dosyalar ve eklenen testler incelendi.

## 1. Pull

Tarih: 2 Mayis 2026 19:10
Aralik: 00962f9 -> b0fd2fb
Baslik: feat: Guncellenmis kopru dosyalari ve hata yonetimi icin yeni islevler eklendi

Ne degisti?

- PyInstaller spec tarafinda steam_net_bridge modulu ve pygame.cursors bagimliligi paketleme kapsamına daha acik sekilde alindi.
- Bridge artifact arama ve secme mantigi, mevcut Python surumune uyan ve daha yeni derlenmis binary dosyalarini onceleyecek sekilde sertlestirildi.
- Online PvP line sweep cizimi, hata durumunda oyunu dusurmek yerine state sifirlayip akisi devam ettirecek bir guvenlik katmani altina alindi.
- Bridge artifact tarama, packaging ve Online PvP guard davranisi icin test kapsamı genisletildi.
- Build ve bridge entegrasyon dokumanlari guncellendi.

Ne cozuldu?

- Paketli buildlerde steam_net_bridge dosyasinin eksik kalmasi nedeniyle Online PvP tarafinda import veya runtime acilis sorunlari yasanabiliyordu; bu risk azaltildi.
- Eski veya farkli Python ABI ile uretilmis bridge binary dosyasinin secilmesi sonucu yanlis artefact kullanilabiliyordu; secim kurali dogru binary lehine duzeltildi.
- Rainbow cat line sweep efekti cizilirken exception olusursa match akisi bozulabiliyor veya hata fatal hale gelebiliyordu; bu yol non-fatal hale getirildi.

Cozum nasil calisiyor?

- Spec dosyalari bridge binary yolunu dogrudan binaries listesine ekleyerek pyinstaller paketine kopru dosyasini tasiyor.
- Runtime ve packaging tarafindaki siralama fonksiyonlari once gecerli CPython etiketini, sonra en yeni dosya zaman damgasini tercih ediyor.
- Online PvP tarafinda sweep cizimi tek bir guvenli wrapper uzerinden yapiliyor; hata olursa line clear feedback state temizleniyor ve oturum kapanmadan devam ediyor.

Ana dosyalar

- packaging/specs/tetris_en.spec
- src/online_pvp_game.py
- src/steam_networking.py
- tools/bridge_artifacts.py
- tests/test_windows_cursor_and_online_pvp_guard.py

## 2. Pull

Tarih: 2 Mayis 2026 15:59
Aralik: e723028 -> ea8497a
Baslik: feat(cursor): Guncellenmis fare imleci yukleme testleri eklendi ve hata yonetimi iyilestirildi

Ne degisti?

- Windows platformunda custom PNG cursor kullanimini daha basit bir erken donusle tamamen kapatan kod kaldirildi.
- Cursor yuklenebiliyorsa PNG dosyasinin okunmasi, olceklenmesi ve pygame cursor nesnesine donusturulmesi saglandi.
- Cursor asset yuklenemezse sistem cursoruna geri donen fallback yolu korunup test edildi.

Ne cozuldu?

- Windows tarafinda custom cursor asset mevcut olsa bile her zaman sistem oku kullaniliyordu; ozellestirilmis imlec hic devreye giremiyordu.
- Hata durumlarinda davranisin ne olacagi belirsizdi; basarili yukleme ve fallback senaryolari testle netlesti.

Cozum nasil calisiyor?

- setup_custom_cursor artik Windows icin ozel bir erken cikis yapmiyor; normal cursor yukleme akisina giriyor.
- Yukleme basarisiz olursa exception yakalaniyor ve kontrollu sekilde sistem cursoruna dusuluyor.
- Testler hem basarili custom cursor olusumunu hem de asset yoklugunda fallback davranisini dogruluyor.

Ana dosyalar

- src/main.py
- tests/test_windows_cursor_and_online_pvp_guard.py

## 3. Pull

Tarih: 27 Nisan 2026 17:31
Aralik: e8af8f6 -> 8aef9aa
Baslik: feat(mystery_mode): Implement ghost echo card mechanics and related tests

Ne degisti?

- Ghost Echo ikinci sans davranisi tek noktada toplanarak ayri bir tuketme mekanigine tasindi.
- Sadece yeni parca dogarken degil, parca lock olduktan sonra olusan lock-out durumda da kartin oyunu kurtarabilmesi saglandi.
- Kart tuketilince ust satirlari temizleme, lock-out flaglerini kapatma, aktif efekt gorselini kaldirma ve oyuncuya mesaj gosterme ayni akis icinde toplandi.
- Yeni regresyon testleri eklendi.

Ne cozuldu?

- Ghost Echo aktif olsa bile top-out parca kilitleme senaryosunda run yine de game over ile bitebiliyordu.
- Revive mantigi iki farkli noktaya dagildigi icin bakimi zordu ve bazi game over yollarini kaciriyordu.

Cozum nasil calisiyor?

- MysteryMode icindeki _consume_ghost_echo_revive yardimcisi, karti bulup harciyor, gerekli ust satirlari temizliyor ve board lock-out durumunu sifirliyor.
- Game.lock_and_new_piece akisina _try_prevent_game_over_after_lock hatti eklenerek board game over dediginde modun bir kurtarma sansi kullanmasi saglaniyor.
- Yeni parca spawn edildiginde gecersiz pozisyon olusursa ayni revive mantigi yine kullaniliyor; boylece hem spawn hem lock sonrasi yol ayni kurala baglaniyor.

Ana dosyalar

- src/game.py
- src/game_modes_extra.py
- tests/test_mystery_second_chance.py

## 4. Pull

Tarih: 26 Nisan 2026 10:03
Aralik: 47775ce -> 1c7995b
Baslik: codex denemesi

Not: Commit mesaji aciklayici degil; ozet asagidaki diff icerigine gore cikarildi.

Ne degisti?

- Mystery kart aciklama metinleri icin dil profiline uygun font ureten yardimci fonksiyon eklendi.
- Uzun kelimeleri parcalayabilen ve metni uc nokta ile kesmeden saran yeni wrap mantigi yazildi.
- Kart aciklamasi kutuya sigmiyorsa font boyutunu asamali kuculten bir fit algoritmasi eklendi.
- Overlay snapshot verisine aciklama satirlari ve kullanilan font yuksekligi kaydedildi; bu da testlenebilirlik sagladi.
- Uzun aciklama metinlerinin kisaltilmak yerine tam gosterildigini dogrulayan yeni UI testi eklendi.

Ne cozuldu?

- Mystery kart aciklamalari uzun oldugunda uc nokta ile kesiliyor ve anlam kaybi olusuyordu.
- Bazi aciklamalar kart kutusuna tasma riski tasiyordu.
- Farkli dil profillerinde ayni font varsayimi yapildigi icin yerellesmis metinlerin yerlestirilmesi kirilgan kalabiliyordu.

Cozum nasil calisiyor?

- Aciklama metni once genislik bazli satirlara bolunuyor; gerekirse tek bir uzun kelime de satirlara parcali sekilde dagitiliyor.
- Metin kutuya sigmazsa algoritma font yuksekligini kontrollu bicimde dusurup yeniden wrap yapiyor.
- Hedef, metni uc noktaya dusurmeden kart icinde tutmak; test de tam olarak bunu kontrol ediyor.

Ana dosyalar

- src/game_modes_extra.py
- tests/test_phase8_overlay_ui_scaling.py

## 5. Pull

Tarih: 23 Nisan 2026 23:59
Aralik: 42935dd -> e324d11
Baslik: feat(ui): Kart UI icin odak navigasyonu ve etkilesim islevselligi eklendi

Ne degisti?

- Mystery kart secim overlay icin ortak bir focus modeli eklendi; odak artik kartlar ve alt aksiyon dugmeleri arasinda tasinabiliyor.
- SKIP ve REROLL dugmeleri mevcut glass stilini koruyarak odak ve hover halkasi aldi.
- Klavye ile sol, sag, yukari, asagi gezintisi ve Enter veya Space ile aktif odagi tetikleme destegi eklendi.
- Mouse hareket ettiginde keyboard-only hover durumu kapatilip focus hedefi imlece gore tekrar senkronize ediliyor.
- Kart secimi, skip, reroll, peek ve random secim yolları tek bir handler katmanina toplandi.
- Ayrica main tarafinda mute kapatildiginda menu muziginin gercekten tekrar caldiginin garanti edilmesi icin ek koruma eklendi.
- Bu akislar icin yeni regresyon testleri yazildi.

Ne cozuldu?

- Kart secim overlay tam olarak klavye veya gamepad benzeri tus akislariyla kullanilamiyordu; odak sadece mouse merkezliydi.
- Reroll devre disiyken focus davranisi belirsizdi.
- Rotate aksiyonu Space tusuna rebound edilse bile Space ile aktif odagi secme ihtiyaci korunmaliydi; yeni kod bunu koruyor.
- Mute kapatilinca menu muzigi bazen geri donmeyebiliyordu; bu da menuye sessiz donus hissi olusturuyordu.

Cozum nasil calisiyor?

- MysteryCardUI icinde focus_target_kind, focus_card_index, focus_action ve keyboard_nav_active alanlari ile kalici odak modeli tutuluyor.
- move_focus, activate_focused ve _target_at_pos yardimcilari ayni overlay icinde kartlar ve aksiyon satiri arasinda gecisi yonetiyor.
- MysteryMode tarafindaki _handle_card_selection_keydown ve _handle_card_selection_choice fonksiyonlari klavye ve mouse secim yollarini ortak bir karar katmaninda birlestiriyor.
- Menu tarafinda _ensure_menu_music_playing, unmute sonrasi music channel ve mixer durumunu kontrol edip gerekirse playlist veya menu track baslatiyor.

Ana dosyalar

- src/game_modes_extra.py
- src/main.py
- tests/test_mystery_reroll_limit.py

## Genel Sonuc

Son 5 pull uc ana hatta yogunlasiyor:

- Packaging ve runtime dayanikliligi artirildi. Ozellikle bridge artifact secimi, PyInstaller kapsami ve non-fatal hata davranislari daha guvenli hale getirildi.
- Mystery mode oyun akisi daha tutarli hale getirildi. Ghost Echo artik kritik game over yolunu dogru sekilde kesebiliyor.
- Mystery kart overlay deneyimi belirgin sekilde iyilestirildi. Uzun metinler daha okunur, klavye navigasyonu daha belirgin ve aksiyon dugmeleri daha kontrollu hale geldi.

Bu 5 pull ortak olarak iki seyi guclendiriyor: oyun akisinda sessiz ama kritik hata toleransi ve UI tarafinda kullanilabilirlik ile regresyon guvencesi.