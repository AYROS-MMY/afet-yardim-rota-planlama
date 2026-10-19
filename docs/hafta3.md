# Üçüncü hafta — Dijkstra ve yol maliyeti

İkinci haftanın veri modeli üzerine başlangıç ve hedef arasında en düşük maliyetli rota hesabı eklendi. Ana senaryo 30 düğüm ve 55 yola genişletildi. Bu haftanın kapsamı Dijkstra, hasar maliyeti, toplu hedef sorguları, doğruluk testleri ve statik rota gösterimidir. **Bu haftanın takım kaptanı Yusuf Öksüz'dür.** Önceki çalışma [ikinci hafta notunda](hafta2.md) korunur.

## Ana senaryo ve doğrulanmış sonuçlar

`data/hafta3_genis_ag.json` varsayılan senaryodur. 6×5 yerleşimde **2 yardım merkezi (H0/H1), 6 afet noktası (A1–A6), 22 kavşak** vardır. 49 yatay/dikey yola 6 çapraz bağlantı eklenmiştir. **55 yolun 39'u açık, 10'u hasarlı, 6'sı kapalıdır.** A6'nın üç girişi kapalıdır; diğer 29 düğüm geçilebilir ağ üzerinden birbirine bağlıdır.

Veriler sentetiktir. Izgarada komşu düğümler arası düzlem uzaklığı 2 km'dir; yol mesafesi bunun yaklaşık 1,1 katıdır. Temel süreler 24, 30 veya 36 km/saat varsayımlarıyla hesaplanıp iki ondalığa yuvarlanmıştır. Aynı veri `py -3.11 scripts/generate_week3_scenario.py` ile yeniden üretilebilir.

Varsayılan hasar katsayısı 2 ile bağımsız sorgu sonuçları:

- **H0 merkezi:** A1 30,49 dk; A2 25,72 dk; A3 38,14 dk; A4 21,64 dk; A5 32,64 dk; A6 erişilemez.
- **H1 merkezi:** A1 29,76 dk; A2 24,99 dk; A3 39,29 dk; A4 27,88 dk; A5 38,88 dk; A6 erişilemez.

Ana demo rotası **H0 → K05 → K06 → K07 → K08 → A4 → K09 → A3**: hasar dahil **38,14 dakika**, temel **32,64 dakika**, mesafe **15,40 km**, incelenen düğüm **29**. Hasar katsayısı 1 seçilince **H0 → K10 → K11 → K17 → A2 → K18 → A3**, **31,24 dakika** bulunur. Bunlar aynı sabit ağın farklı maliyet varsayımlarıyla çözülmesidir.

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
py -3.11 -m ayros --start H0 --target A3 --svg docs/hafta3_genis_rota.svg
py -3.11 -m ayros --start H0 --all-targets
py -3.11 -m ayros --start H1 --all-targets
py -3.11 -m ayros --start H0 --target A3 --damage-factor 1 --svg docs/hafta3_hasar_1.svg
py -3.11 -m ayros --start H0 --target A6
py -3.11 -m unittest discover -s tests -v
```

1. İlk komutun 38,14 dakikalık rotasını gösterin; `docs/hafta3_genis_rota.svg` dosyasını tarayıcıda açın. Mavi çerçeve rotayı, iç renk yol durumunu gösterir. Yol etiketlerinde kimlik ve hasar dahil dakika bulunur. Düğüm/yol üzerine gelince açıklama görünür.
2. H0 ve H1 için toplu sorguları çalıştırın. İki merkezden de 5/6 afet noktasına erişildiğini gösterin; hedeflerin ayrı hesaplandığını açıklayın.
3. Katsayıyı 1 yaparak rotanın ve maliyetin değiştiğini gösterin. Bu yeni bir aramadır; hareket sırasında otomatik yeniden planlama henüz yoktur.
4. A6 sorgusunu çalıştırın. Üç girişin de kapalı olması nedeniyle “Rota bulunamadı” sonucunu gösterin. Bu komutun çıkış kodu 3 olması beklenen davranıştır.
5. Test sonucunu gösterin; A* karşılaştırmasının sonraki hafta yapılacağını söyleyin. Elle ispat istenirse dört düğümlü örneği açın: `py -3.11 -m ayros data/hafta3_ornek.json --start S --target T`.

Hedefe ulaşılamazsa program “Rota bulunamadı” der; maliyet sıfır olarak sunulmaz. Başlangıç ve hedef aynıysa tek düğümlü, sıfır maliyetli geçerli sonuç döner. Geçersiz düğüm kimliği ve hasar katsayısı açıklayıcı hata üretir. Çıkış kodları: başarı 0, veri/dosya hatası 1, komut kullanımı hatası 2, tek hedefte ulaşılamama 3. Toplu özet tamamlanınca erişilemeyen hedefler olsa da 0 döner. SVG için tek hedef seçilmelidir; `--all-targets` ile birlikte kullanılamaz.

## Doğrulama sonucu

19 Ekim 2026'da Python 3.11 ile **44 test metodu geçti**: ikinci haftadan 19, temel rota için 19, geniş ağ ve toplu sorgular için 6. Parametreli alt kontroller ayrı test olarak sayılmaz. Rota testleri elle hesaplanan sonuç, hasar etkisi, kapalı kısayol, erken durma, eski kuyruk kayıtları, erişilemeyen hedef, aynı başlangıç/hedef, hatalı girişler, sayısal taşma, eşit maliyet, veri değişmezliği, ters yön, önceki senaryo, SVG ve CLI davranışlarını kapsar.

Ek olarak bir test içinde, sabit tohumla üretilmiş 12 küçük ağın her birinde 4 hedef kontrol edilir. Dijkstra maliyeti, bütün tekrarsız yolların ayrı bir yöntemle sıralanmasıyla bulunan en düşük maliyetle karşılaştırılır: **48 bağımsız rota karşılaştırması**. Bu kontrol yalnızca küçük test ağları içindir; üretim algoritması değildir.

Geniş ağda ayrıca iki merkez × altı hedef × iki hasar katsayısı = **24 sorgu**, test içinde bağımsız Bellman-Ford hesabıyla karşılaştırılmıştır. Bu referans hesap yalnızca test kodundadır; kullanıcıya sunulan rota algoritması Dijkstra'dır. Senaryonun yeniden üretilebilirliği, fiziksel mesafe tutarlılığı, A6'nın kapalı bağlantıları, maliyet etiketleri ve toplu CLI seçenekleri de doğrulanmıştır.

## Kaptanın kısa anlatımı — Yusuf Öksüz

“Hocam, ben Yusuf Öksüz, bu haftanın takım kaptanıyım. Geçen hafta veri modelini oluşturmuştuk. Bu hafta Dijkstra algoritmasını ekledik ve ana senaryoyu 30 düğüm, 55 yola çıkardık. Ağda iki yardım merkezi ve altı afet noktası var.

Maliyeti dakika üzerinden tanımladık. Açık yolda temel süreyi, hasarlı yolda varsayılan olarak sürenin iki katını kullanıyoruz. Kapalı yolları aramaya almıyoruz. İki katsayısı değiştirebildiğimiz bir simülasyon varsayımı.

Ekrandaki H0-A3 rotası 38,14 dakika. Hasar etkisini kaldırınca program farklı bir yol seçerek 31,24 dakika buluyor. Böylece yol koşullarının rota seçimini etkilediğini görebiliyoruz. Her iki merkez için tüm afet noktalarını da sorgulayabiliyoruz. A6'nın bütün girişleri kapalı olduğu için oraya rota bulunamıyor.

Ben görselleştirme, testler ve haftalık raporun sunumunu anlatacağım. Muhammet algoritmayı ve maliyet hesabını, Mert senaryoyu ve verilerin nasıl oluşturulduğunu açıklayacak. Toplam 44 test geçti. Sonraki hafta aynı model üzerinde A* geliştirip sonuç maliyetlerini ve arama ölçümlerini karşılaştırmayı planlıyoruz.”

## Ekip içi çalışma paylaşımı

**Bu hafta kaptan Yusuf Öksüz'dür:** açılış, ekip geçişleri, görselleştirme, testler ve raporun anlatımı. Muhammet Altınoluk Dijkstra ve maliyet modeli; Mert Aydın geniş senaryo, veri üretimi ve elle kontrol örneği üzerinde çalışır. Teknik görev alanları korunur. Bu liste bireysel commit sahipliği iddiası değildir; her üye sunacağı kısmı çalıştırıp açıklayabilmelidir.

## Gelebilecek kısa sorular

- **Neden Dijkstra?** Pozitif süre maliyetleriyle en düşük maliyetli rota için temel çözümümüz; A* karşılaştırmasına referans olacak.
- **En kısa mesafeyi mi buluyor?** Bu modelde en düşük tahmini süreyi buluyor; kilometre ayrı bir çıktı.
- **Neden hasar katsayısı 2?** İlk örneği anlaşılır tutmak için seçilmiş, değiştirilebilir bir varsayım. Gerçek veriyle kalibre edilmedi.
- **44 test her şeyin tamamlandığını mı gösterir?** Mevcut veri ve rota işlevlerinin kontrolleri geçiyor. A*, öncelik ve araç hareketi henüz yok.
- **Neden 30 düğüm, 55 yol?** Farklı alternatifleri, iki merkezi, hasar etkisini ve erişilemeyen bölgeyi birlikte gösterirken sunumda izlenebilir kalması için.
- **İki merkezden hangisini sistem seçiyor?** Şu an kullanıcı seçiyor; toplu sorgu her merkez için bağımsız sonuç veriyor. Otomatik atama henüz yok.
- **A4 üzerinden geçerken yardım bırakılıyor mu?** Hayır. Düğümlerden geçiş modelleniyor; durma, hizmet süresi ve yardım dağıtımı henüz yok.
- **Araç hareket ederken yol kapanırsa?** Otomatik yeniden planlama sonraki aşamada. Şu anda her komut tek bir sabit senaryoyu çözüyor.
- **A* daha hızlı olacak mı?** Henüz ölçmedik. Aynı maliyet modeli, uygun sezgisel ve tekrarlı deneylerle değerlendireceğiz.

## Dördüncü haftaya geçiş

A* aynı `CostModel` ve `RouteResult` yapısını kullanacak. Sezgisel dakika cinsinden ve kalan gerçek maliyeti aşmayacak biçimde tasarlanmalı; kilometre doğrudan dakika maliyetine eklenmemeli. Aynı senaryolarda en düşük maliyetlerin eşitliği test edilecek. Hasar katsayısı, başlangıç/hedef, incelenen düğüm tanımı ve zaman ölçüm sınırları iki algoritmada ortak tutulacak. Öncelik puanı, araç atama ve hareket sonraki haftalarda ele alınacak.
