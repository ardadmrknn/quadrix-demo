# macOS local version notu

src/version_local_macos.py artik repoda tutulmaz.

Guncel akis:
- Dosya macOS build sirasinda lokal olarak uretilir.
- Dosya .gitignore altindadir ve repoya commit edilmez.
- Dosya silinirse bir sonraki macOS build tekrar olusturur.

macOS cihazdaki beklenti:

1. Repo'yu pull et.
2. Gerekliyse macOS build al.
3. Build sonrasi src/version_local_macos.py dosyasinin lokal olustugunu dogrula.

Notlar:
- src/version_local_windows.py da gitignore altindadir.
- Runtime tarafinda dosya yoksa surum bilgisi version_base.py uzerinden fallback ile calisir.
