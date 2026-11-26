# 9. hafta finaline kadar geliştirme planı

Bu plan, 6. hafta sonunda çalışan çizge, Dijkstra/A*, ihtiyaç puanı ve üç hizmet türünde bağımsız görevlere tek turluk araç atamasının üzerine kuruludur. Bölge ihtiyaç paneli ve araç seçilebilir HTML görünümü hesaplanmış başlangıç planını gösterir. Hareket, olay işleme ve teslimat takibi henüz uygulanmadı.

## 7. hafta — Durum takibi ve yeniden planlama

Araç için planlandı, yolda, teslim edildi ve yol bulunamadı durumları tanımlanacak. Simülasyon düğümler arasında adım adım ilerleyecek. İlk sürümde yol olayı araç bir düğümdeyken uygulanacak; yol ortasında konum ve dönüş kuralı eklenmeyecek. Yol kapanınca yalnızca etkilenen görevin kalan rotası mevcut düğümden aynı hedefe yeniden hesaplanacak. Alternatif yoksa araç bekleyecek; olay ve gerekçe kaydedilecek. Hedefe varış tek sefer sayılacak.

Kabul koşulları: araç merkezine geri ışınlanmaz; kapanan yol yeni rotaya alınmaz; etkilenmeyen görev değişmez; alternatif bulunamadığında açık bekleme durumu vardır; tekrar ilerletmede teslimat iki kez sayılmaz. Önce komut satırı ve testlerle doğrulanacak.

## 8. hafta — Kısmi teslimat, karar karşılaştırması ve arayüz

7. haftanın durumu mevcut haritaya bağlanacak. Başlat, adım ilerlet ve sıfırla kontrolleri; yol kapatma seçimi; mevcut araç konumu; eski/yeni rota ve olay kaydı gösterilecek. Yeni bir teknoloji yığınına geçilmeyecek. Hesap motoru Python'da kalacak; arayüz hesapları tekrar uygulamayacak. İnce bir yerel arayüz bağlantısı kurulacak.

Kabul koşulları: normal teslimat, köprü kapanmasıyla alternatif rota, tüm girişleri kapanan hedef ve müsait olmayan araç senaryoları ekrandan açıklanabilmeli. Ekran ile hesap motorunun araç ve görev durumları eşleşmeli. Bu hafta sonunda özellik kapsamı dondurulacak.

Lojistikte kontrollü kısmi teslimat eklenecek. Ana ihtiyaç kaydı korunacak; teslim edilmiş, araca ayrılmış ve henüz atanmamış miktarlar ayrı izlenecek. Kapasite ile planlanan yük ayrılacak. Yakın küçük ve uzak büyük araç birlikte değerlendirilecek; büyük araçları koruma kuralı karşı örneklerle sınanacak. İlk sürüm araç başına tek sefer olacak; boş araç afet noktasında kendiliğinden yeniden yüklenmeyecek.

Deneyler: 100 koli ihtiyaca yakın 80/uzak 120 kapasite; iki bölgenin aynı büyük aracı istemesi; kısmi teslimattan sonra kapanan yol. İlk yardım ve tam karşılama zamanı, kalan ihtiyaç ve toplam yolculuk ayrı raporlanacak. Eski/yeni algoritmalar aynı kurallarla; kısmi teslimat açık/kapalı koşulları ayrı deneylerde karşılaştırılacak. Üstünlük varsayılmayacak.

İkinci eşleştirme algoritması ve basit ekipman uygunluğu yalnız temel simülasyon güvenilir biçimde tamamlanırsa eklenecek. Optimum iddiası ancak açıkça tanımlanan model ve doğrulanan küçük örneklerle sınırlı olacak. Sabit teslimat eşikleri deney parametresidir, saha standardı değildir.

## 9. hafta — Doğrulama ve final teslimi

Uçtan uca senaryolar, bütün testler, temiz klasörden kurulum/çalıştırma, veri dosyaları ve çıktı bağlantıları kontrol edilecek. Final raporu, kısa demo akışı ve ekip sunumu tamamlanacak. GitHub yayını kullanıcı onayıyla yapılacak. Canlı demo için aynı senaryonun sabit çıktıları da hazırlanacak.

Kabul koşulları: tek belgelenmiş başlangıç akışı; tekrarlanabilir senaryo; hata halinde anlaşılır mesaj; raporla uygulamanın aynı sayıları göstermesi; bütün ekip üyelerinin kendi modülünü ve temel sınırlamaları anlatabilmesi.

## Kapsam sınırı ve riskler

Global filo optimumu, gerçek şehir/OSM verisi, canlı saha entegrasyonu, stok, çok duraklı tur final kapsamı dışında kalacak. Mevcut açgözlü yöntemin büyük aracı erken tüketebilmesi testli bir sınırlamadır. Bazı görevlere ilk turda atama yapılamaması veri/kaynak kısıtlarının sonucudur; başarılı teslimat oranı veya gerçek afet performansı değildir.

En büyük takvim riski 7. haftadaki durum ve olay mantığıdır. Sıkışma halinde animasyon ve görsel efektler azaltılacak; doğrulanmış adımlı simülasyon ve yeniden planlama korunacak. 9. haftaya temel algoritma geliştirmesi bırakılmayacak. Hoca ayrıca zorunlu özellik belirtirse bu kapsam yeniden değerlendirilmeli.
