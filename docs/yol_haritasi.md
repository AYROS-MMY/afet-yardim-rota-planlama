# 9. hafta finaline kadar geliştirme planı

Bu plan, 6. hafta sonunda çalışan çizge, Dijkstra/A*, ihtiyaç puanı ve üç hizmet türünde bağımsız görevlere tek turluk araç atamasının üzerine kuruludur. Bölge ihtiyaç paneli ve araç seçilebilir HTML görünümü hesaplanmış başlangıç planını gösterir. 7. haftada hareket, yol olayları ve teslimat takibi ayrı bir hesap motorunda tamamlandı; mevcut HTML ekranı başlangıç planını göstermeye devam eder.

## 7. hafta — Tamamlanan durum takibi ve yeniden planlama

Araç konumu ve görev durumu zaman içinde izlenir. Her adım sıradaki düğüme varışa ilerler; aynı anda varan araçlar kimlik sırasıyla işlenir. Kontrol noktalarında yol değişimi uygulanır. Üzerinde araç olan yol değiştirilemez; ilerideki rotası etkilenen araç mevcut yolunu tamamlayıp ulaştığı düğümden aynı hedefe yeniden rota hesaplar. Alternatif yoksa bekler. Başlangıç ataması korunur; araç merkeze geri taşınmaz. Teslimat yalnız hedefe varıldığında bir kez sayılır. Sağlık/kurtarmada ekip varışı kaydedilir.

Doğrulandı: küçük ağda normal 4 dakika, alternatif rota 8 dakika; iki çıkış kapalıyken 0 teslim ve araçta 100 koli. Bölgesel örnekte 11 araç varışı, 455 koli teslimi, 4 ekip varışı ve 475 koli açık ihtiyaç. Bölgesel ağda R178 köprüsü kapanınca yalnız S02 yeniden rota bulur (53,575 → 67,79 dk); üç köprü kapanınca S02 ve V04 bekler, teslim 405 koliye iner. 25 yeni testle tüm proje 150 teste ulaştı; testler GitHub Actions ile her gönderimde çalışır. Olay günlüğü ve SVG karşılaştırması üretilebilir. Ayrıntılar: [Simülasyon kılavuzu](simulasyon.md).

Kabul koşulları karşılandı: mevcut konumdan yeniden rota, kapalı yola girmeme, etkilenmeyen görevin korunması, alternatif yokken açık bekleme durumu ve çift sayılmayan teslimat. Simülasyon komut satırında çalışır; canlı harita bağlantısı 8. haftadır. Başlangıçta atanmayan görevler otomatik yeniden atanmaz. Bütün araçlar durduğunda zaman ilerlemez; bekleyen araca yol açılması aynı kontrol noktasında API üzerinden uygulanabilir. Süreye bağlı olay kuyruğu bu aşamanın kapsamına alınmadı.

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

7. haftanın durum ve olay motoru tamamlandı. Kalan başlıca takvim riski 8. haftadaki kısmi teslimat ile harita bağlantısının birlikte geliştirilmesidir. Sıkışma halinde animasyon ve görsel efektler azaltılacak; doğrulanmış adımlı simülasyon ve yeniden planlama korunacak. 9. haftaya temel algoritma geliştirmesi bırakılmayacak. Hoca ayrıca zorunlu özellik belirtirse bu kapsam yeniden değerlendirilmeli.
