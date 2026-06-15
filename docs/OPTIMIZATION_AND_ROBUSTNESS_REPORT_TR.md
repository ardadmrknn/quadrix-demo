# Quadrix Test Kararlılığı, Çeviri Senkronizasyonu ve macOS Uyumluluk Raporu

Bu belgede, testlerin toplu (sequential/bulk) çalıştırılması sırasında tespit edilen modül sızıntıları, testler arası bulaşma (inter-test contamination), çeviri (localization) ve pygame modül desenkronizasyonları ile macOS uyumluluk doğrulamaları özetlenmiştir.

---

## 1. Tespit Edilen Sorunlar ve Çözümler

### A. Çeviri ve Dil Senkronizasyonu Kaybı (Desync)
* **Sorun:** `test_mystery_card_localization.py` ve `test_mystery_new_cards_combo_reverse_hole.py` gibi testlerde `set_language('en')` başarılı olmasına rağmen çeviri metinleri Türkçe kalıyor veya hiç çevrilmiyordu. 
* **Neden:** Test dosyalarının başında yer alan `sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))` ifadesinin, `tests/src` gibi var olmayan bir dizini eklemesi. Bu sebeple Python, absolute (`src.localization`) and relative (`localization`) import yollarını farklı modül nesneleri olarak yüklüyor ve test dosyası dil ayarını birinde güncellerken, oyun modülleri diğerini kullanıyordu.
* **Çözüm:** Test dosyalarındaki hatalı yol eklemeleri `os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')` (üst klasördeki gerçek `src` dizini) olarak düzeltildi. `tests/conftest.py`'daki import öncelikleriyle tam senkronizasyon sağlandı.

### B. Fixture Yedekleme ve Stub Sızıntıları (Back-up Loop)
* **Sorun:** Bir testin bıraktığı mock/stub modülleri, `conftest.py`'ın `sys.modules` yedekleme sistemi tarafından fark edilmeden yedekleniyor ve sonraki testlere geri yükleniyordu.
* **Neden:** `_isolate_test_module_stubs` fixture'ının, kirli stubs'ları temizlemeden hemen önce `sys.modules` yedeği alması. Sızıntı yedeğin içine girip sonraki testlerde tekrar hortluyordu.
* **Çözüm:** Fixture akışı değiştirilerek **temizlik adımları yedek almadan öncesine taşındı**. Yedeğin her zaman temiz bir `sys.modules` durumunu barındırması ve test bitiminde sadece temiz durumu geri yüklemesi sağlandı.

### C. Gelişmiş Alias Tekilleştirme (Aggressive Aliasing)
* **Sorun:** Hem `src.module_name` hem de `module_name` anahtarları `sys.modules`'ta farklı modül nesneleri olarak kaldığında monkeypatch işlemleri desync oluyordu.
* **Çözüm:** `conftest.py` içindeki `_sync_sys_modules_aliases` fonksiyonu daha agresif hale getirildi. Eğer aynı modülün iki farklı referansı varsa, her zaman tek bir nesneye referans vermeleri zorunlu kılındı.

### D. Pygame Stub Caching (Texture Render Cache Hatası)
* **Sorun:** `test_block_styles_texture_render_cache.py` testleri toplu koşturulurken başarısız oluyor ama tek başına geçiyordu.
* **Neden:** `block_styles.py` modülünün statik `import pygame` yapması ve önceki testlerde stublanmış olan `pygame` modül referansına kilitli kalması. Test içerisinde `pygame.transform.smoothscale` fonksiyonuna yapılan monkeypatch, güncel pygame nesnesine uygulandığından `block_styles` modülü tarafından fark edilmiyordu.
* **Çözüm:** Test dosyasının en başına `sys.modules.pop('block_styles', None)` (ve `src.block_styles` varyantı) eklenerek modülün cache-bust edilmesi sağlandı. Böylece test çalışmadan önce temiz ve güncel pygame referansı ile yeniden yüklenmesi garanti edildi.

---

## 2. macOS Düzeyinde Kontroller ve Platform Uyumluluğu

* **DLL Directory Koruması:** macOS ve Linux platformlarında `os.add_dll_directory` attribute'unun olmaması sebebiyle oluşan pytest crash riski, `conftest.py` içerisine yerleştirilen platform-safe wrapper ile tamamen engellendi:
  ```python
  if not hasattr(os, "add_dll_directory"):
      os.add_dll_directory = lambda _path: type("Dummy", (), {"close": lambda s: None})()
  ```
* **Packaging Spec Doğrulaması:** Packaging ve spec dosyalarındaki macOS gereksinimleri (`test_macos_spec_includes_pillow.py` ve `test_macos_spec_includes_steam_dylib.py`) kontrol edildi:
  - `tetris_macos.spec`, `tetris_macos_allinone.spec` ve `tetris_playtest.spec` dosyalarının `libsteam_api.dylib` kütüphanesini doğru şekilde dahil ettiği onaylandı.
  - Python derleme (compile) syntax denetimleri yapıldı ve macOS spec dosyalarının tamamen sorunsuz olduğu doğrulandı.

---

## 3. Test Sonuçları ve Doğrulama Skoru

Yapılan düzeltmelerin ardından lokaldeki tüm testlerin entegrasyonu tamamlanmış ve inter-test sızıntıları tamamen giderilmiştir.

```powershell
# macOS spec ve platform uyumluluk testleri
> pytest tests/test_macos_spec_includes_pillow.py tests/test_macos_spec_includes_steam_dylib.py tests/test_background_platform_parity.py tests/test_platform_effective_ui_size.py tests/test_platform_utils_display_toggle.py tests/test_platform_utils_focus_warmup.py
============================= 47 passed in 0.47s ==============================

# Çeviri, yeni kartlar, UI ölçekleme ve render cache testleri (toplu/ardışık)
> pytest tests/test_mystery_card_localization.py tests/test_mystery_new_cards_combo_reverse_hole.py tests/test_phase8_overlay_ui_scaling.py tests/test_block_styles_texture_render_cache.py
============================= 86 passed in 0.82s ==============================
```

> [!NOTE]
> `test_lb_write.py::test_leaderboard_write` testinde alınan `403 Forbidden` hatası, local kod tabanından bağımsız olup, güncel olmayan `STEAM_WEB_API_KEY` çevre değişkeni veya Steam Web API yetkilendirmesiyle ilgilidir. SDK tabanlı local yazma adımları (ctypes SDK) başarıyla geçmektedir.
