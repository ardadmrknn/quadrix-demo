
# Online Co-op: Guest Ýçin "Yerel Simülasyon (Local Sim)" Yaklaþýmý Fizibilite Raporu

Kullanýcýnýn ilettiði tespit tamamen doðrudur: Quadrix Co-op modunda (özellikle `src/coop_board.py` incelendiðinde), oyun 20x20'lik tek bir tahta kullansa da aslýnda oyuncularýn hareket alanlarý P1 (0-9 sütunlar) ve P2 (10-19 sütunlar) olarak kesin sýnýrlarla (MIDLINE=10) birbirinden izole edilmiþtir. Parçalar havada düþerken ASLA havada çarpýþmazlar.

Bu mimari avantaj, Guest'in "Sadece tuþ gönderip Host'tan tahtayý bekleme" (aðrýlý input lag) modelinden çýkarýlýp; týpký Online PvP modundaki gibi **her bilgisayarýn kendi oynadýðý alanýn fizik simülasyonunu %100 yerel, 0ms lag ile yönetebilmesi** anlamýna gelir.

## 1. Neden Bu Öneri Mükemmel Uyuyor?
*   **Ýzolasyon:** P1'in düþürdüðü aktif parça sadece 0-9 sütunlarýný ilgilendirir. P2'nin parçasýna sürtünmez.
*   **0 ms Input Lag:** Guest, kendi parçasýný (örneðin sað yarým tahtada) kendi makinesinde tamamen anlýk (gerçek zamanlý) kontrol eder. 
*   **PvP Adaptasyonu:** PvP'deki gibi, Host ve Guest sadece "Benim düþen parçam þu X,Y kordinatýnda" paketi (görsellik için) ve parça yere sabitlendiðinde "Benim 10x20 alanýmýn son blok doluluk durumu budur" paketini birbirine yollar.

## 2. Kilit Sorun (Edge Case): Satýr Temizleme (Line Clear) Senkronizasyonu
Herkesin kendi bilgisayarýnda kendi alanýnda oyun oynamasý mükemmeldir ancak iþ **satýr silmeye (Line Clear)** geldiðinde çakýþmalar doðar.

Oyunda bir satýrýn temizlenmesi için BÜTÜN 20 hücrenin (P1'in 10 hücresi + P2'nin 10 hücresi) dolmasý gerekir. 
*   **Senaryo:** P1 (Host) bir blok koyarak row 19'un solunu tamamlar. P2 (Guest) de bir blok koyarak row 19'un saðýný tamamlar.
*   **Problem:** Að gecikmesinden dolayý (ör. 50ms), P1 kendi bloðunu oturtur oturtmaz "P2 çoktan bloðu koymuþtu satýr tam dolu" diyerek satýrý kendi ekranýnda silecektir ve üstteki bloklar aþaðý kayacaktýr. Ancak P2'nin bilgisayarýna henüz P1'in son hamlesi ulaþmamýþsa, P2'nin ekranýndaki bloklar henüz aþaðý kaymayacaktýr (Desync - Çarpýk senkronizasyon).

## 3. Mimari Çözüm Uygulamasý

Bu sorunu kökünden çözüp, tamamen akýcý ve Guest'i lagsýz oynatacak hibrit mimari þu adýmlarla kurgulanýr:

**Adým 1: Düþen Parçalarda (Active Pieces) %100 Yerel Otorite (0ms Lag)**
- Host, P1_Piece hareketlerini sadece kendi hesaplar ve Guest'e "P1 parçasý Þuradadýr" mesajý atar. Guest bu paketi sadece Host'un hayalet parçasýný ekranda çizmek (Render) için kullanýr. Güvenilir ve çok hýzlýdýr.
- Guest, P2_Piece hareketlerini sadece KENDÝ yerelinde hesaplar ve Host'a yollar. Böylece Guest kendi girdiði girdiyi anýnda kendi tahtasýnda görür. Oyun kaymak gibi akar.

**Adým 2: Yere Sabitleme (Lock) Anýnda Veri Transferi**
- Guest kendi parçasýný yere koyduðunda, sað yarýdaki 10 kolonluk dizinin son halini Host'a bir að paketi (`MsgType.COOP_GUEST_LOCK_STATE`) olarak gönderir.
- Host kendi parçasýný yere koyduðunda, sol yarýdaki að paketini Guest'e (`MsgType.COOP_HOST_LOCK_STATE`) gönderir.

**Adým 3: Satýr Temizleme Otoritesi SADECE Host'tadýr**
- Ýki oyuncu da parçalarýný kendi ekranýnda kilitleyebilir, ancak ekraný aþaðý kaydýrma (Line Clear Sweep) iþlemini KENDÝ BAÞLARINA YAPAMAZLAR.
- **Kritik kural:** Guest parçasýný yere koyduðunda yeni parça çýkarýp oynamaya devam eder, ancak kendi ekranýndaki doluluklarý P1 ile eþleþtirip silmeye YETKÝSÝ YOKTUR.
- Host her milisaniye 20 kolonun doluluðunu (Kendi 10'u ve Guest'ten en son gelen 10'u) kontrol eder. 
- Eðer 20 kolonluk tam bir satýr oluþtuysa, Host bir `MsgType.COOP_LINE_CLEAR` (Örn: Hangi satýrlarýn silindiði, satýr numaralarý: [18, 19]) mesajýný network'e fýrlatýr.
- Mesaj P2'ye ulaþtýðý "an", iki bilgisayarda KESÝN OLARAK ortak ve eþ zamanlý bir sweep/clear animasyonu tetiklenir ve bloklar aþaðýya inmiþ olur. Kilit/Senkron kopmasý yaþanmaz.

## Sonuç
Kullanýcýnýn bahsettiði "*Online PvP mantýðýyla iki tarafa da local simülasyon uygulansýn*" fikri hem mantýklý hem de mevcut modun mimarisini çok daha üst seviyeye çýkaracak bir çözümdür. Bu deðiþimi koda iþlemek teknik olarak fizibildir ancak **otorite dengesini ve line-clear gecikmesini iyi ele almak kaydýyla**, Guest'teki can sýkýcý gecikme problemini kesin olarak çözecektir.
