# Quadrix — Görev & İyileştirme Listesi
> Oluşturulma: 27 Şubat 2026  
> Durum: Planlanıyor

---

## 🔄 Çalışma Döngüsü (Her Görev İçin)

1. **Sorunu anla** → İlgili dosyaları/fonksiyonları araştır, tam olarak ne olduğunu kavra
2. **En iyi çözümü düşün** → Alternatifler varsa tartış, en temiz yaklaşımı seç
3. **Kodu yaz** → Implementasyonu uygula
4. **Kodu incele** → Yazdığım kodu gözden geçir, hata/mantık sorunu var mı kontrol et, varsa düzelt
5. **Manuel test** → `python3 main.py` çalıştır, değişikliği gözle doğrula
6. **Sorun varsa geri dön 3'e** → Çözülene kadar döngü devam eder

> Anlamadığım bir şey olursa kullanıcıya sorarım, geri kalanını kendim hallederim.

---

## Öncelik Seviyeleri
- 🔴 **Önemli** — Öncelikli ele alınacak
- 🟡 **Normal** — Sırası gelince yapılacak
- ⚪ **Düşük** — Önemli değil, zaman bulununca

---

## 1. Ayarlar

| # | Başlık | Açıklama | Öncelik | Durum |
|---|--------|----------|---------|-------|
| 1.1 | Müzik Shuffle Butonu | Birden fazla müziği olan modlar ve kampanya bölümleri için ayarlar ekranındaki müzik seçim kısmına shuffle (karıştır) butonu eklenmesi. Böylece arka planda sürekli aynı müzik çalmaz. | 🟡 Normal | ✅ Tamamlandı ⚠️ test bekleniyor |

---

## 2. Kullanıcı Yönetimi & Profil

| # | Başlık | Açıklama | Öncelik | Durum |
|---|--------|----------|---------|-------|
| 2.1 | Yeni Kullanıcı Oluşturma — Ölçekleme | Yeni kullanıcı oluşturma ekranında ölçekleme problemi var; yazılar iç içe giriyor. | 🔴 Önemli | ✅ Tamamlandı |
| 2.2 | Profil Fotoğrafı Ortalama | Bazı profil fotoğrafları yuvarlak çerçeve içinde ortalanmamış, hafif sağa-sola kaymış veya çerçeve dışına taşıyor. | ⚪ Düşük | ✅ Tamamlandı ⚠️ test bekleniyor |
| 2.3 | Profil Fotoğrafı Arka Plan Rengi | Yuvarlak profil çerçevesinin arka plan rengi şu an yalnızca mavi. Farklı renklerle özelleştirilebilir hale getirilebilir. | 🟡 Normal | ✅ Tamamlandı ⚠️ test bekleniyor |

---

## 3. Ana Menü & UI

| # | Başlık | Açıklama | Öncelik | Durum |
|---|--------|----------|---------|-------|
| 3.1 | Küçük Yazı Ölçekleri | Bazı yazılar neredeyse okunamayacak kadar küçük. Örn: ana menüdeki blok görünümleri panelinin altındaki yazı. | 🔴 Önemli | ✅ Tamamlandı |
| 3.2 | Önemli Yazılar için Panel Kutucukları | Ana menü ve diğer ekranlardaki önemli/göze çarpan yazıların her biri için ayrı panel kutucuğu eklenmesi. Örn: görev modundaki "hızlı devam kutucuğu" referans alınabilir. | 🟡 Normal | ✅ Tamamlandı ⚠️ test bekleniyor |
| 3.3 | Panel Şeffaflık Bloğu Taşması | Ana menüdeki bazı panellerin arka planını hafif transparan yapan bloğun, panelin tamamını kaplamamaması sorunu. Örn: co-op panelinin ortasında transparan blok görünür hale geliyor. | ⚪ Düşük | ✅ Tamamlandı |
| 3.4 | Görev Çubuğu Simgesi & İsim | Oyun açıkken işletim sistemi görev çubuğundaki simge farklı görünüyor ve isimde "python" geçiyor. Doğru ikon ve uygulama adı atanıldı. | 🟡 Normal | ✅ Tamamlandı |

---

## 4. Kılavuz

| # | Başlık | Açıklama | Öncelik | Durum |
|---|--------|----------|---------|-------|
| 4.1 | Sayfa Geçiş Takılması | Kılavuz sol panelindeki 4 sayfa arasında geçiş yaparken ufak bir takılma var. Özellikle "2. Oyun Modları" sayfasına geçişte daha belirgin. Kök sebep araştırılacak. | 🟡 Normal | ✅ Tamamlandı ⚠️ test bekleniyor |

---

## 5. Eğitim

| # | Başlık | Açıklama | Öncelik | Durum |
|---|--------|----------|---------|-------|
| 6.1 | Yeni Hesap Eğitim Pop-up | Yeni hesap oluşturulduğunda "Eğitim ister misiniz?" tarzı bir pop-up çıkmıyor. Ana menüde eğitim zaten erişilebilir olsa da yeni hesaplar için bu pop-up'ın eklenmesi kullanıcı deneyimini iyileştirir. | 🔴 Önemli | ✅ Tamamlandı |
| 5.2 | Eğitim Aşamaları | Mevcut eğitim tek bir sekans içeriyor. Skill çeşitliliği göz önüne alınarak "Temel", "Orta", "İleri Seviye" gibi kademeli eğitim aşamaları tasarlanabilir. Her aşama belirli skill gruplarını öğretir. | 🟡 Normal | ⬜ Bekliyor |

---

## 6. Görev Modu

| # | Başlık | Açıklama | Öncelik | Durum |
|---|--------|----------|---------|-------|
| 6.1 | Hover Tooltip Takılması | Bölüm seçme ekranında fare boşa baksa bile en son hover yapılan bölümün koşulları bazen ekranda kalmaya devam ediyor. Örn: geçilmemiş bir bölüm seçilmeden koşulları görünüyor. | 🟡 Normal | ✅ Tamamlandı |
| 6.2 | Act içi Seviye Numaralandırma | Act içindeki seviyeler global numara alıyor. Örn: "Vadi" bir act olmasına rağmen "Vadi 1", "Vadi 2" şeklinde ilerliyor. Act-yerel numaralandırma uygulanmalı veya act adı tekrarlanmamalı. | 🟡 Normal | ✅ Tamamlandı |
| 6.3 | Bölüm Öncesi Koşul Anlatımı | Görev modu bölümlerinde istenebilecek koşulların (2'li satır yap, zincir, combo vb.) bölüm başlamadan önce kısa bir eğitim veya görsel ile anlatılması. | 🟡 Normal | ⬜ Bekliyor |
| 6.4 | Tamamlanma Oranı Yüzdesi | Görev modu ekranının üstündeki ilerleme barına yüzdelik değer eklenmesi. | ⚪ Düşük | ✅ Tamamlandı |
| 6.5 | Act Geçiş Siyah Efekti | Act değiştirme sırasında gelen siyah efektin yoğunluğu biraz azaltılabilir. Aynı efekt uygun diğer geçişlerde de kullanılabilir. | 🟡 Normal | ✅ Tamamlandı |
| 6.6 | Boss Bölüm Görsel Ayrımı | Boss bölümleri (örn: 10. bölüm) bölüm seçme ekranında diğerlerinden görsel olarak ayrışmalı. Örn: kırmızı renkli buton veya özel ikon. | 🟡 Normal | ✅ Tamamlandı |
| 6.7 | Bölüm Hover Yazı Rengi | Bir bölümün üstüne gelindiğinde çıkan görseldeki bölüm sayısı siyah renkte, arka planla karışıyor. Yazı rengi veya arka plan kontrası iyileştirilmeli. | ⚪ Düşük | ✅ Tamamlandı |

---

## 7. Başarımlar

| # | Başlık | Açıklama | Öncelik | Durum |
|---|--------|----------|---------|-------|
| 7.1 | Yıldız Sayısı Başarımları | Görev modundan kazanılan toplam yıldız sayısıyla ilgili başarımlar eklenmesi. Örn: "30 yıldız kazan", "50 yıldız kazan", "50. bölümü 3 yıldızla bitir". | 🟡 Normal | ✅ Tamamlandı ⚠️ test bekleniyor |

---

## Özet Sayım

| Öncelik | Adet |
|---------|------|
| 🔴 Önemli | 4 |
| 🟡 Normal | 12 |
| ⚪ Düşük | 4 |
| **Toplam** | **20** |

---

## ❌ Dokunulmayacak Maddeler — Luna Görselleri

> Kapsam dışı bırakıldı; şimdilik elle alınmıyor.

| # | Başlık | Açıklama | Öncelik |
|---|--------|----------|---------|
| L1 | Luna Fotoğrafı Kesim Sorunu | Kılavuz, ana menü vb. yerlerdeki luna fotoğraflarının kesildiği kısımlar panele tam oturmuyor. Çözüm seçenekleri: (a) fotoğrafı uzatıp panelin altına bitişik yapma, (b) mevcut haliyle altına çizgi çekme — "sos" kısmındaki görsel referans alınabilir. | 🔴 Önemli |
| L2 | Panel Üzerinde "Oyna" Butonu Bölgesi | Bir oyun modu paneline tıklayınca direkt oyunun başlaması beklenmedik. Panelin tıklanabilir bölgesine; görev modundaki "hızlı devam kutucuğu" gibi ayrı bir "Oyna" butonu/bölgesi eklenmeli. | 🟡 Normal |
| L3 | Luna Konuşma Balonları | Kılavuz sekmesi ve uygun diğer yerlerde "sos" kısmındaki gibi yerinde konuşma balonları eklenmesi. | ⚪ Düşük |
| L4 | Dil Seçeneğini Taşı | Ayarlar → "Diğer" sekmesindeki dil seçeneğini oradan kaldırıp "Oyun" sekmesinin başına taşımak. Geliştirici kodu kullanılmadığında "Diğer" sekmesi boş görünüyor. | ⚪ Düşük |
| L5 | Skill Tuş Atama Sistemi — Yuva Yapısı | Şu an her skill için ayrı tuş ataması var. Skill sayısı arttıkça ayarlar kısmı yönetilemez hale gelecek. Çözüm: belirli sayıda "skill yuvası" tanımlanır, her yuvaya tuş atanır. İleride mağaza sistemiyle ek yuva satın alınabilir hale gelebilir. | 🟡 Normal |
| L6 | Kartlar Sayfası — Enderlik Bilgisi | "3. Kartlar" sayfasındaki kart açıklamalarına enderlik bazında detay eklenmesi. Her enderlik seviyesinde o kartın kaç defa kullanılabileceğini gösteren bilgi penceresi/yazısı. Örn: Keskin Nişancı skilli için "Destansı: 5 kullanım, Efsanevi: 6 kullanım". | 🟡 Normal |
