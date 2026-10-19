# Üçüncü hafta — Dijkstra ve yol maliyeti

İkinci haftanın veri modeli üzerine başlangıç ve hedef arasında en düşük maliyetli rota hesabı eklendi. Ana senaryo 40 düğüm ve 65 yollu düzensiz yerleşim ağıdır. Bu haftanın kapsamı Dijkstra, hasar maliyeti, toplu hedef sorguları, doğruluk testleri ve statik rota gösterimidir. **Bu haftanın takım kaptanı Yusuf Öksüz'dür.** Önceki çalışma [ikinci hafta notunda](hafta2.md) korunur.

## Ana senaryo ve doğrulanmış sonuçlar

`data/hafta3_genis_ag.json` varsayılan senaryodur. **2 yardım merkezi (H0/H1), 6 afet noktası (A1–A6), 32 kavşak** vardır. **65 yolun 51'i açık, 9'u hasarlı, 5'i kapalıdır.** A6'nın iki girişi kapalıdır; diğer 39 düğüm geçilebilir ağ üzerinden birbirine bağlıdır.

Yerleşimde farklı açılarla birleşen yollar, düzensiz mahalle halkaları ve K16/K32 çıkmazları bulunur. Dere iki yakayı ayırır; geçiş yalnızca R16 ve R17 köprülerinden mümkündür. Kuzeydeki R16 hasarlı, güneydeki R17 açıktır. Ana yollar, ikincil yollar ve dar sokaklar çizgi kalınlığıyla ayrılır. Bu düzen gerçek bir şehirden alınmamış, öğrenci projesi için tasarlanmış sentetik bir senaryodur.

Mesafe, yolun başlangıç noktası, ara geometri noktaları ve bitişi arasındaki parça uzunluklarının toplamıdır; 0,01 km hassasiyetle yukarı yuvarlanır. Temel süreler ana yolda 40, ikincil yolda 30, sokakta 20, köprüde 25 km/saat varsayımıyla hesaplanıp iki ondalığa yuvarlanır. Hızlar saha ölçümü değildir. Aynı veri `py -3.11 scripts/generate_week3_scenario.py` ile yeniden üretilebilir.

JSON modelinde isteğe bağlı üç alan kullanılır:

- Yolun `road_type` alanı `main`, `secondary`, `local` veya `bridge` olur; yoksa `secondary` kabul edilir.
- Yolun `via` alanı yerel kilometre koordinatlarıyla ara noktaları tutar. Bunlar yolun şeklini belirler; kavşak veya yeni bağlantı oluşturmaz. Geometri varsa mesafenin bu uzunluktan kısa olmaması doğrulanır (0,011 km yuvarlama toleransı).
- Senaryonun `river` alanı görsel dere eksenidir; çizgeye düğüm eklemez. Yaka bağlantısını köprü kenarları belirler.

Bu alanları içermeyen önceki senaryolar çalışmaya devam eder.

Varsayılan hasar katsayısı 2 ile bağımsız sorgu sonuçları:

- **H0 merkezi:** A1 10,75 dk; A2 15,50 dk; A3 32,54 dk; A4 28,41 dk; A5 38,08 dk; A6 erişilemez.
- **H1 merkezi:** A1 29,75 dk; A2 19,65 dk; A3 13,75 dk; A4 21,44 dk; A5 17,74 dk; A6 erişilemez.

Ana demo rotası **H0 → K09 → K10 → K11 → K25 → K26 → K30 → K31 → K28 → A5**: hasar dahil **38,08 dakika**, temel **34,84 dakika**, mesafe **17,60 km**, incelenen düğüm **39**. Hasar katsayısı 1 seçilince **H0 → K09 → K10 → K11 → K25 → K26 → K27 → K31 → A5**, **28,90 dakika** ve **15,18 km** bulunur. Bunlar aynı sabit ağın farklı maliyet varsayımlarıyla çözülmesidir.

İki merkezden sorgu yapmak otomatik araç/merkez ataması değildir; kullanıcı başlangıcı seçer. Afet noktaları üzerinden geçişe izin verilir; bu noktalarda durma, hizmet süresi veya yardım bırakma modellenmez. `--all-targets` hedefleri kimliğe göre listeler; liste bir öncelik veya ziyaret sırası değildir.

## Maliyet kararı

Maliyet birimi dakikadır. Açık yolda JSON'daki temel süre, hasarlı yolda temel sürenin hasar katsayısıyla çarpımı kullanılır. Kapalı yol kullanılmaz. Varsayılan katsayı 2'dir; en az 1 olan sonlu bir sayı seçilebilir. Katsayı 1 hasarın ek süre etkisini kaldırır, kapalı yolları açmaz. Bu bir simülasyon varsayımıdır, saha ölçümü değildir.

Mesafe ve süre toplanmaz. Rota en kısa kilometreye göre değil, en düşük süre maliyetine göre seçilir. Mesafe ayrıca gösterilir. **Maliyet ile hasar dahil tahmini süre bu modelde aynı ölçüttür.** Temel süre hasar etkisi hariç toplamdır. Afet aciliyeti henüz hedef seçimine veya yol maliyetine katılmaz.

## Dijkstra nasıl çalışıyor?

Başlangıcın maliyeti sıfır yapılır. Öncelik kuyruğundan birikmiş maliyeti en düşük düğüm alınır; komşularına daha ucuz bir geçiş bulunursa maliyet ve önceki düğüm bilgisi güncellenir. Hedef kuyruktan alınıp kesinleştirildiğinde arama biter. Hedef ilk görüldüğünde durmak yanlış sonuç verebileceğinden ayrıca test edilmiştir. Rota, hedeften başlangıca önceki düğümler izlenerek oluşturulur.

`heapq` hazır bir rota algoritması değildir; yalnızca öncelik kuyruğunu sağlar. Yol maliyetleri pozitiftir. Aynı maliyetli seçeneklerde farklı rotalar mümkün olsa da en düşük maliyet değişmez. Çizge verisi arama sırasında değiştirilmez.

**İncelenen düğüm**, kuyruktan alınarak maliyeti kesinleştirilen benzersiz düğümdür. Başlangıç ve erişilirse hedef de sayılır; eski kuyruk kayıtları ikinci kez sayılmaz. **Hesaplama süresi**, maliyetlerin hazırlanması, arama ve rotanın geri kurulmasını kapsar; JSON okuma, terminal yazdırma ve SVG üretimini kapsamaz. Tek çalıştırmanın süresi karşılaştırmalı performans sonucu değildir.

## Elle doğrulanan örnek

`data/hafta3_ornek.json` içinde S yardım merkezi, B/C kavşak, T afet noktasıdır.

- S–B: açık, 2 dakika; B–T: hasarlı, temel 2 dakika.
- S–C: açık, 3 dakika; C–T: açık, 2 dakika.
- S–T: temel 1 dakika, **kapalı**; hiçbir rotada kullanılamaz.
- Katsayı 2 iken üst rota 2 + 2×2 = **6 dakika**, alt rota 3 + 2 = **5 dakika**: sonuç **S → C → T**, 3,2 km.
- Katsayı 1 iken üst rota 2 + 2 = **4 dakika**: sonuç **S → B → T**, 3 km.

Önceki 10 düğümlü senaryoda varsayılan katsayıyla H0 → K1 → K3 → K5 → A2 → A1 rotası bulunur: maliyet **27,44 dakika**, temel süre **23,04 dakika**, mesafe **11,52 km**.

## Çalıştırma ve sunum sırası

Komutları depo klasöründeki terminalde çalıştırın. Python 3.11+ yeterlidir; ek paket kurulmaz. Windows dışındaki sistemlerde `py -3.11` yerine uygun Python komutunu kullanın.

```powershell
py -3.11 -m ayros --start H0 --target A5 --svg docs/hafta3_genis_rota.svg
py -3.11 -m ayros --start H0 --all-targets
py -3.11 -m ayros --start H1 --all-targets
py -3.11 -m ayros --start H0 --target A5 --damage-factor 1 --svg docs/hafta3_hasar_1.svg
py -3.11 -m ayros --start H0 --target A6
py -3.11 -m unittest discover -s tests -v
```

1. İlk komutun 38,08 dakikalık rotasını gösterin; `docs/hafta3_genis_rota.svg` dosyasını tarayıcıda açın. İki yakayı, köprüleri ve çıkmazları işaret edin. Mavi çerçeve rotayı, iç renk yol durumunu gösterir. Bütün yolların kimliği, rota üzerindeki yolların hasar dahil süreleri görünür; her yolun ayrıntıları üzerine gelince açılır.
2. H0 ve H1 için toplu sorguları çalıştırın. İki merkezden de 5/6 afet noktasına erişildiğini gösterin; hedeflerin ayrı hesaplandığını açıklayın.
3. Katsayıyı 1 yaparak rotanın ve maliyetin değiştiğini gösterin. Bu yeni bir aramadır; hareket sırasında otomatik yeniden planlama henüz yoktur.
4. A6 sorgusunu çalıştırın. İki girişin de kapalı olması nedeniyle “Rota bulunamadı” sonucunu gösterin. Bu komutun çıkış kodu 3 olması beklenen davranıştır.
5. Test sonucunu gösterin; A* karşılaştırmasının sonraki hafta yapılacağını söyleyin. Elle ispat istenirse dört düğümlü örneği açın: `py -3.11 -m ayros data/hafta3_ornek.json --start S --target T`.

Hedefe ulaşılamazsa program “Rota bulunamadı” der; maliyet sıfır olarak sunulmaz. Başlangıç ve hedef aynıysa tek düğümlü, sıfır maliyetli geçerli sonuç döner. Geçersiz düğüm kimliği ve hasar katsayısı açıklayıcı hata üretir. Çıkış kodları: başarı 0, veri/dosya hatası 1, komut kullanımı hatası 2, tek hedefte ulaşılamama 3. Toplu özet tamamlanınca erişilemeyen hedefler olsa da 0 döner. SVG için tek hedef seçilmelidir; `--all-targets` ile birlikte kullanılamaz.

## Doğrulama sonucu

19 Ekim 2026'da Python 3.11 ile **47 test metodu geçti**: ikinci haftadan 19, temel rota için 19, geniş ağ ve toplu sorgular için 9. Parametreli alt kontroller ayrı test olarak sayılmaz. Rota testleri elle hesaplanan sonuç, hasar etkisi, kapalı kısayol, erken durma, eski kuyruk kayıtları, erişilemeyen hedef, aynı başlangıç/hedef, hatalı girişler, sayısal taşma, eşit maliyet, veri değişmezliği, ters yön, önceki senaryo, SVG ve CLI davranışlarını kapsar.

Ek olarak bir test içinde, sabit tohumla üretilmiş 12 küçük ağın her birinde 4 hedef kontrol edilir. Dijkstra maliyeti, bütün tekrarsız yolların ayrı bir yöntemle sıralanmasıyla bulunan en düşük maliyetle karşılaştırılır: **48 bağımsız rota karşılaştırması**. Bu kontrol yalnızca küçük test ağları içindir; üretim algoritması değildir.

Geniş ağda ayrıca iki merkez × altı hedef × iki hasar katsayısı = **24 sorgu**, test içinde bağımsız Bellman-Ford hesabıyla karşılaştırılmıştır. Bu referans hesap yalnızca test kodundadır; kullanıcıya sunulan rota algoritması Dijkstra'dır. Senaryonun yeniden üretilebilirliği, yol geometrisi/mesafe tutarlılığı, A6'nın kapalı bağlantıları, maliyet açıklamaları ve toplu CLI seçenekleri doğrulanmıştır. Yol parçalarının kavşaksız çapraz kesişmemesi ve geçersiz geometrinin reddedilmesi de kontrol edilir. Ayrı test senaryolarında tek köprü kapatıldığında diğer geçişin kullanılabildiği, iki köprü kapatıldığında yakalar arası erişimin kesildiği doğrulanır; bu test otomatik yeniden planlama özelliği değildir.

## Kaptanın kısa anlatımı — Yusuf Öksüz

“Hocam, ben Yusuf Öksüz, bu haftanın takım kaptanıyım. Geçen hafta veri modelini oluşturmuştuk. Bu hafta Dijkstra algoritmasını ekledik ve 40 düğüm, 65 yollu bir senaryo hazırladık. Ağda iki yardım merkezi ve altı afet noktası var. Mahalleleri düzensiz yerleştirdik; ana yollar, ara sokaklar, çıkmazlar ve iki köprü ekledik. Mesafeleri çizdiğimiz yolun uzunluğundan hesaplıyoruz. Bu, gerçek şehir verisi değil, bizim oluşturduğumuz bir simülasyon.

Maliyeti dakika üzerinden tanımladık. Açık yolda temel süreyi, hasarlı yolda varsayılan olarak sürenin iki katını kullanıyoruz. Kapalı yolları aramaya almıyoruz. İki katsayısı değiştirebildiğimiz bir simülasyon varsayımı.

Ekrandaki H0-A5 rotası 38,08 dakika. Hasarın ek süre etkisini kaldırınca program farklı bir yol seçerek 28,90 dakika buluyor. Böylece yol koşullarının rota seçimini etkilediğini görebiliyoruz. Her iki merkez için tüm afet noktalarını da sorgulayabiliyoruz. A6'nın iki girişi kapalı olduğu için oraya rota bulunamıyor.

Ben görselleştirme, testler ve haftalık raporun sunumunu anlatacağım. Muhammet algoritmayı ve maliyet hesabını, Mert senaryoyu ve verilerin nasıl oluşturulduğunu açıklayacak. Toplam 47 test geçti. Sonraki hafta aynı model üzerinde A* geliştirip sonuç maliyetlerini ve arama ölçümlerini karşılaştırmayı planlıyoruz.”

## Ekip içi çalışma paylaşımı

**Bu hafta kaptan Yusuf Öksüz'dür:** açılış, ekip geçişleri, görselleştirme, testler ve raporun anlatımı. Muhammet Altınoluk Dijkstra ve maliyet modeli; Mert Aydın geniş senaryo, veri üretimi ve elle kontrol örneği üzerinde çalışır. Teknik görev alanları korunur. Bu liste bireysel commit sahipliği iddiası değildir; her üye sunacağı kısmı çalıştırıp açıklayabilmelidir.

## Gelebilecek kısa sorular

- **Neden Dijkstra?** Pozitif süre maliyetleriyle en düşük maliyetli rota için temel çözümümüz; A* karşılaştırmasına referans olacak.
- **En kısa mesafeyi mi buluyor?** Bu modelde en düşük tahmini süreyi buluyor; kilometre ayrı bir çıktı.
- **Neden hasar katsayısı 2?** İlk örneği anlaşılır tutmak için seçilmiş, değiştirilebilir bir varsayım. Gerçek veriyle kalibre edilmedi.
- **47 test her şeyin tamamlandığını mı gösterir?** Mevcut veri ve rota işlevlerinin kontrolleri geçiyor. A*, öncelik ve araç hareketi henüz yok.
- **Neden 40 düğüm, 65 yol?** Farklı mahalleleri, alternatif yolları, köprü darboğazlarını ve erişilemeyen bölgeyi sunumda takip edilebilir büyüklükte göstermek için.
- **Bu gerçek bir şehrin haritası mı?** Hayır; düzensiz yerleşim ve yol sınıfları içeren sentetik bir ağ. Hızlar ve hasar katsayısı da varsayım.
- **Kıvrımlar yeni kavşak mı?** Hayır; aynı yolun ara geometri noktaları. Bağlantılar yalnızca kimliği olan düğümlerde oluşuyor.
- **Köprüler kapanırsa?** Testte bir köprü kapanınca diğerinden geçiliyor; ikisi kapanınca karşı yakaya rota bulunamıyor. Hareket sırasında otomatik yeniden planlama henüz yok.
- **İki merkezden hangisini sistem seçiyor?** Şu an kullanıcı seçiyor; toplu sorgu her merkez için bağımsız sonuç veriyor. Otomatik atama henüz yok.
- **Bir afet noktasından geçerken yardım bırakılıyor mu?** Hayır. Düğümlerden geçiş modelleniyor; durma, hizmet süresi ve yardım dağıtımı henüz yok.
- **Araç hareket ederken yol kapanırsa?** Otomatik yeniden planlama sonraki aşamada. Şu anda her komut tek bir sabit senaryoyu çözüyor.
- **A* daha hızlı olacak mı?** Henüz ölçmedik. Aynı maliyet modeli, uygun sezgisel ve tekrarlı deneylerle değerlendireceğiz.

## Dördüncü haftaya geçiş

A* aynı `CostModel` ve `RouteResult` yapısını kullanacak. Sezgisel dakika cinsinden ve kalan gerçek maliyeti aşmayacak biçimde tasarlanmalı; kilometre doğrudan dakika maliyetine eklenmemeli. Aynı senaryolarda en düşük maliyetlerin eşitliği test edilecek. Hasar katsayısı, başlangıç/hedef, incelenen düğüm tanımı ve zaman ölçüm sınırları iki algoritmada ortak tutulacak. Öncelik puanı, araç atama ve hareket sonraki haftalarda ele alınacak.
