# AYROS MMY Gereksinim Analizi

## Amaç ve kapsam

Simüle edilmiş afet bölgesinde yardım araçlarının yol koşulları ve afet öncelikleri dikkate alınarak yönlendirilmesi hedeflenmektedir. Kullanıcı, senaryoyu hazırlayan ve sonuçları inceleyen proje kullanıcısıdır. İlk sürüm yerel bilgisayarda sentetik verilerle çalışacaktır. Bu belge tamamlanmış özellikleri değil, projenin hedef gereksinimlerini tanımlar.

## İşlevsel gereksinimler

| Kod | Gereksinim |
| --- | --- |
| G1 | Sistem düğüm, yol, yardım merkezi ve afet noktası verilerini yüklemeli; kimlikleri ve sayısal alanları doğrulamalıdır. |
| G2 | Yollar açık, hasarlı veya kapalı olarak temsil edilmeli; kapalı yollar rota aramasına alınmamalı, hasarlı yolların maliyeti artırılmalıdır. |
| G3 | Kullanıcının seçtiği başlangıç ve hedef için ekip tarafından geliştirilen Dijkstra veya A* ile rota ve toplam maliyet hesaplanmalıdır. |
| G4 | Afet noktaları yaralı sayısı, afetzede sayısı ve aciliyet verileriyle önceliklendirilmelidir. Katsayılar ve formül tasarım aşamasında belirlenecektir. |
| G5 | Uygun ve boş araçlar, afet önceliği ve ulaşım maliyeti değerlendirilerek temel bir yöntemle görevlere atanmalıdır. |
| G6 | Yol kapandığında veya maliyeti değiştiğinde etkilenen rota yeniden hesaplanmalı; alternatif yoksa kullanıcı bilgilendirilmelidir. |
| G7 | Yol durumları ve rotalar görselleştirilmeli; rota maliyeti, tahmini seyahat süresi, hesaplama süresi ve incelenen düğüm sayısı gösterilmelidir. |

## Kalite gereksinimleri ve kabul ölçütleri

- **K1 — Geçerli veri:** Negatif mesafe, kimlik tekrarı ve olmayan düğüme bağlanan yol açıklayıcı hata ile reddedilmelidir. Geçerli örnek senaryo aynı verilerle tekrar yüklenebilmelidir.
- **K2 — Rota doğruluğu:** Kapalı yol sonuç rotasında bulunmamalıdır. Aynı maliyet modelinde, uygun A* sezgiseliyle iki algoritmanın en düşük rota maliyeti eşit olmalıdır; yol dizileri farklı olabilir.
- **K3 — Hata yönetimi:** Ulaşılamayan hedef ve uygun araç bulunamaması kontrollü sonuç üretmelidir. Arayüzde işlem bekleme durumu başarıda ve hatada sonlanmalıdır.
- **K4 — Test edilebilirlik:** Algoritmalar arayüzden bağımsız olmalı; aynı senaryo ve koşullarda yapılan deneyler kaydedilebilmelidir. Performans eşiği deneylerden sonra belirlenecektir.

## Kısıtlar ve üçüncü hafta durumu

Ana dil Python'dur. İlk çizge çift yönlü yollar ve yerel düzlem koordinatları kullanır. Gerçek zamanlı saha verisi, canlı trafik, gerçek araç takibi ve kapsamlı VRP çözümü ilk sürüm kapsamı dışındadır.

19 Ekim 2026 itibarıyla G1 veri yükleme/doğrulama ve G2 açık/hasarlı/kapalı yol maliyeti uygulanmıştır. G3 kapsamında Dijkstra çalışmaktadır; A* sonraki haftaya planlanmıştır. Ana senaryo 40 düğüm, 65 yol, 2 yardım merkezi ve 6 afet noktası içerir. Düzensiz yerleşim, iki köprü ve çıkmaz sokaklar modellenmiştir; yol mesafeleri çizilen geometriden hesaplanır. Seçilen merkezden tüm afet noktaları bağımsız sorgulanabilir; bu işlem otomatik araç ataması değildir. G7 için statik SVG üzerinde rota, yol sınıfları ve maliyetler; terminalde tüm rota ölçümleri gösterilmektedir. K2'nin kapalı yol ve Dijkstra doğruluk kontrolleri, K3'ün ulaşılamayan hedef kontrolü ve K4'ün arayüzden bağımsız test yapısı mevcuttur. Köprü kapanma denemeleri sabit senaryoların testidir; G6'nın otomatik yeniden planlama işlevi henüz uygulanmamıştır. G4–G5, A* karşılaştırması ve araç/arayüz hata durumları da sonraki aşamalardır. Güncel doğrulama: 47 başarılı test metodu; ayrıntılar [üçüncü hafta notunda](hafta3.md).
