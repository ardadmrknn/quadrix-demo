# macOS local version bootstrap notu

Bu dosya, src/version_local_macos.py dosyasinin repoya bir kez gonderilmesi icin olusturuldu.

Amac:
- macOS cihaz repo'yu pull ettiginde version_local_macos.py ilk kez gelsin
- bundan sonraki macOS build artislari tekrar repoya gitmesin

macOS cihazdaki agent ne yapmali:

1. Repo'yu pull et.
2. src/version_local_macos.py dosyasinin geldigini dogrula.
3. Bu dosyayi bundan sonra yerel tutmak icin su komutu calistir:

   git update-index --skip-worktree src/version_local_macos.py

4. Bundan sonra macOS build'leri bu dosyayi lokal olarak artirabilir; git status icinde gorunmemelidir.

Gerekirse skip-worktree kaldirma:

   git update-index --no-skip-worktree src/version_local_macos.py

Ne zaman kaldirilmali:
- repo tarafindan bilerek yeni bir bootstrap macOS surum dosyasi gonderilecekse
- veya dosyayi yeniden senkronize etmek gerekiyorsa

Notlar:
- src/version_local_windows.py hala gitignore altindadir; Windows local kalmaya devam eder.
- src/version_local_macos.py bu asamada bilerek track ediliyor.
- macOS cihaz bu dosyayi aldiktan sonra normal gelistirme akisinda commit edilmemelidir.