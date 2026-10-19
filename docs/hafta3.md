# Üçüncü hafta — Dijkstra ve yol maliyeti

İkinci haftanın veri modeli üzerine başlangıç ve hedef arasında en düşük maliyetli rota hesabı eklendi. Bu haftanın kapsamı Dijkstra, hasar maliyeti, doğruluk testleri ve statik rota gösterimidir. Önceki çalışma [ikinci hafta notunda](hafta2.md) korunur.

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
py -3.11 -m ayros data/hafta3_ornek.json --start S --target T --svg docs/hafta3_rota.svg
py -3.11 -m ayros data/hafta3_ornek.json --start S --target T --damage-factor 1
py -3.11 -m ayros --start H0 --target A1
py -3.11 -m unittest discover -s tests -v
```

1. İlk komutun 5 dakikalık rotasını gösterin; `docs/hafta3_rota.svg` dosyasını tarayıcıda açın. Mavi çerçeve seçilen rotayı gösterir, yolun iç rengi durumunu korur.
2. Üst rotanın hasar nedeniyle 6 dakika olduğunu elle anlatın. Kırmızı S–T yolunun kapalı olduğunu gösterin.
3. İkinci komutta katsayı 1 olduğunda rotanın 4 dakikalık üst yola geçtiğini gösterin. Bu, farklı parametreyle yeni bir aramadır; hareket sırasında otomatik yeniden planlama henüz yoktur.
4. Önceki haftanın daha büyük ağı üzerinde de çalıştığını üçüncü komutla gösterin.
5. Test sonucunu gösterin; A* karşılaştırmasının sonraki hafta yapılacağını söyleyin.

Hedefe ulaşılamazsa program “Rota bulunamadı” der; maliyet sıfır olarak sunulmaz. Başlangıç ve hedef aynıysa tek düğümlü, sıfır maliyetli geçerli sonuç döner. Geçersiz düğüm kimliği ve hasar katsayısı açıklayıcı hata üretir. Çıkış kodları: başarı 0, veri/dosya hatası 1, komut kullanımı hatası 2, ulaşılamayan hedef 3.

## Doğrulama sonucu

19 Ekim 2026'da Python 3.11 ile **38 test metodu geçti**: ikinci haftadan 19, bu haftadan 19. Parametreli alt kontroller ayrı test olarak sayılmaz. Rota testleri elle hesaplanan sonuç, hasar etkisi, kapalı kısayol, erken durma, eski kuyruk kayıtları, erişilemeyen hedef, aynı başlangıç/hedef, hatalı girişler, sayısal taşma, eşit maliyet, veri değişmezliği, ters yön, önceki senaryo, SVG ve CLI davranışlarını kapsar.

Ek olarak bir test içinde, sabit tohumla üretilmiş 12 küçük ağın her birinde 4 hedef kontrol edilir. Dijkstra maliyeti, bütün tekrarsız yolların ayrı bir yöntemle sıralanmasıyla bulunan en düşük maliyetle karşılaştırılır: **48 bağımsız rota karşılaştırması**. Bu kontrol yalnızca küçük test ağları içindir; üretim algoritması değildir.

## Kaptanın kısa anlatımı

“Hocam, geçen hafta afet bölgesini düğüm ve yollardan oluşan bir çizgeye dönüştürmüştük. Bu hafta bu yapıya Dijkstra algoritmasını ekledik. Artık seçtiğimiz başlangıç ve hedef arasında, yol koşullarını dikkate alan bir rota bulabiliyoruz.

Maliyeti dakika üzerinden tanımladık. Açık yolda temel süreyi, hasarlı yolda varsayılan olarak sürenin iki katını kullanıyoruz. Kapalı yolları aramaya almıyoruz. İki katsayısı değiştirebildiğimiz bir simülasyon varsayımı.

Bu küçük örnekte üst yol hasarla birlikte 6 dakika, alt yol 5 dakika sürüyor. Program 5 dakikalık alt yolu seçiyor. Hasar etkisini kaldırınca 4 dakikalık üst yolu seçmesi de maliyetin sonucu değiştirdiğini gösteriyor.

Önceki testleri koruyup rota testleri ekledik; toplam 38 test geçti. Sonraki hafta aynı model üzerinde A* geliştirerek sonuç maliyetlerini ve arama ölçümlerini karşılaştırmayı planlıyoruz.”

## Ekip içi çalışma paylaşımı

Mevcut rol dağılımına göre sunum ve kod inceleme odağı: Muhammet Altınoluk Dijkstra ve maliyet modeli; Mert Aydın küçük/büyük senaryo ve elle hesap; Yusuf Öksüz rota görseli, testler ve ölçümlerin açıklaması. Bu liste bireysel commit sahipliği iddiası değildir; her üye sunacağı kısmı çalıştırıp açıklayabilmelidir.

## Gelebilecek kısa sorular

- **Neden Dijkstra?** Pozitif süre maliyetleriyle en düşük maliyetli rota için temel çözümümüz; A* karşılaştırmasına referans olacak.
- **En kısa mesafeyi mi buluyor?** Bu modelde en düşük tahmini süreyi buluyor; kilometre ayrı bir çıktı.
- **Neden hasar katsayısı 2?** İlk örneği anlaşılır tutmak için seçilmiş, değiştirilebilir bir varsayım. Gerçek veriyle kalibre edilmedi.
- **38 test her şeyin tamamlandığını mı gösterir?** Mevcut veri ve rota işlevlerinin kontrolleri geçiyor. A*, öncelik ve araç hareketi henüz yok.
- **Araç hareket ederken yol kapanırsa?** Otomatik yeniden planlama sonraki aşamada. Şu anda her komut tek bir sabit senaryoyu çözüyor.
- **A* daha hızlı olacak mı?** Henüz ölçmedik. Aynı maliyet modeli, uygun sezgisel ve tekrarlı deneylerle değerlendireceğiz.

## Dördüncü haftaya geçiş

A* aynı `CostModel` ve `RouteResult` yapısını kullanacak. Sezgisel dakika cinsinden ve kalan gerçek maliyeti aşmayacak biçimde tasarlanmalı; kilometre doğrudan dakika maliyetine eklenmemeli. Aynı senaryolarda en düşük maliyetlerin eşitliği test edilecek. Hasar katsayısı, başlangıç/hedef, incelenen düğüm tanımı ve zaman ölçüm sınırları iki algoritmada ortak tutulacak. Öncelik puanı, araç atama ve hareket sonraki haftalarda ele alınacak.
