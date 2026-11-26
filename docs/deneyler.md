# Tekrarlanabilir senaryolar ve deneyler

İki veri kümesi aynı JSON şemasını ve rota API'sini kullanır. `hafta3_genis_ag.json` önceki 40 düğümlü referanstır; `bolgesel_ag.json` daha büyük görev dağıtımı ve yol değişikliği deneyleri için hazırlanmıştır. Gerçek şehir, trafik veya afet verisi kullanılmaz.

## Bölgesel ağın yapısı

- 180 düğüm: H0–H2 merkezleri, A01–A12 afet noktaları, 165 kavşak.
- 348 yol: 287 açık, 47 hasarlı, 14 kapalı. Yollar çift yönlüdür.
- Üç köprü: K001–K002, K003–K004, K005–K006. Dereyi geçen başka bağlantı yoktur.
- A12'nin iki girişi kapalıdır. Diğer 11 afet noktasına bütün merkezlerden ulaşılabilir.
- Afetzede, yaralı ve aciliyet alanları mevcut şemayla doldurulur. Bu alanlar henüz rota seçimini etkilemez.

Üretici sabit `20261026` tohumu kullanır. Noktalar iki yakaya düzensiz yerleştirilir; en az 0,7 km aralık bırakılır. Her yakada önce bağlı bir yol omurgası, sonra kısa yerel bağlantılar kurulur. Ortak kavşak dışındaki yol kesişimleri engellenir. Kapalı yan yollar omurgayı koparmaz; A12 kontrollü erişilemez örnektir. Koordinatlar km, yol maliyetleri dakikadır. Hız varsayımları ana/ikincil/yerel/köprü için 40/30/20/25 km/saattir. Bu sentetik üretim yöntemi gerçek şehirlerin dağılımını temsil etme iddiası taşımaz.

```powershell
py -3.11 scripts/generate_regional_scenario.py
```

Sabit tohum ve değişmeyen üretici aynı JSON'u verir. Gelecekte değişiklik denemeleri için dosyanın bir kopyasını kullanın; referans senaryoyu değiştirmeyin. Yeni bir sürüm gerekiyorsa ayrı adla saklayın. Deney dosyası SHA-256 özetiyle kullanılan veriyi tanımlar.

## Deney protokolü

40 düğümlü ağ: 2 merkez × 6 hedef × 2 hasar katsayısı = 24 sorgu. Bölgesel ağ: 3 merkez × 12 hedef × 2 katsayı = 72 sorgu. Yalnızca olumlu örnekleri seçmek yerine tüm merkez/hedef çiftleri ölçülür. Her algoritma 2 ısınma ve 50 ölçümle, dönüşümlü sırayla çalıştırılır.

```powershell
py -3.11 scripts/compare_algorithms.py --scenario data/hafta3_genis_ag.json --scenario data/bolgesel_ag.json --repeats 50 --output output/ag_karsilastirma.json
```

Her sorgunun medyanı ayrı hesaplanır. Ağ özeti bu medyanların aritmetik ortalamasıdır; birleşik medyan veya güven aralığı değildir. Maliyet hazırlama, A* tahmini, arama ve rota kurma süreye dahildir. JSON okuma, çıktı, arama kayıtları ve SVG çizimi hariçtir. Aynı maliyetli farklı düğüm dizileri geçerlidir. İki ağın topolojileri farklı olduğundan sonuçlar yalnızca düğüm sayısının etkisi olarak yorumlanamaz.

Yerel 50 tekrarlı deneyde 96 sorgunun tamamında erişim ve optimum maliyet sonuçları uyuşmuştur. 86 sorgu erişilebilir, 10 sorgu erişilemezdir. A* erişilebilir sorgularda daha az düğüm incelemiştir; hazırlık dahil süreler iki ağda da Dijkstra'dan uzundur. Performans eşiği veya her ağda hız üstünlüğü iddiası yoktur. Ham örnekler `output/` içinde tutulur, depoya eklenmez.

## Arama kayıtlarını okuma

```powershell
py -3.11 -m ayros data/bolgesel_ag.json --start H0 --target A11 --compare --repeats 50 --search-svg output/arama.svg
```

Sarı halkalar kuyruktan alınıp maliyeti kesinleştirilen benzersiz düğümlerdir. Kuyruğa eklenen her düğüm sarı olmak zorunda değildir. Başlangıç ve erişilen hedef sayıya dahildir. Düğümün üzerine gelince sıra numarası okunur. Mavi çizgi nihai rotadır. İki panel aynı ağ ve ölçeği kullanır. Görsel animasyon değildir. API'de `record_search=True` ile `settled_order` alınabilir; varsayılan boş kayıttır. Karşılaştırma komutu görsel kayıtlarını zamanlanan deneylerden sonra ayrı aramalarla üretir.

## Sonraki geliştirmelerde kullanım

1. **Önceliklendirme:** A01–A12 ihtiyaç alanlarından gerekçeli puan üretin. A12'nin yüksek ihtiyacı olabileceği ile erişilemez olması ayrı bilgiler olarak gösterilmeli. Kabul ölçütü: eşit girdide aynı puan ve açık bir eşitlik bozma kuralı.
2. **Araç atama:** Araç kayıtlarını merkez kimlikleriyle ilişkilendiren ayrı bir model ekleyin. Yol modeline araç durumunu gömmeyin. Boş araç, kapasite ve ulaşılamayan hedef davranışını sınayın; birden çok hedef sorgulamak araç ataması sayılmaz.
3. **Yeniden planlama:** Senaryo kopyasında bir köprüyü kapatıp kalan iki köprü üzerinden alternatif rotayı deneyin. Üçü kapandığında karşı yakaya erişim kesilir. Şimdiki kapanma testleri sabit durumları sınar; olay işleme ve otomatik rota yenileme henüz yoktur.
4. **Arayüz:** Aynı rota sonuçlarını ve arama kayıtlarını tüketin. Hesaplama ve çizimi ayrı tutun. Güncel durum, kullanıcı kontrolü ve hareket gösterimi ayrı geliştirme adımlarıdır.

Bu sıralama mevcut senaryo ve algoritmaları tekrar kullanır; sonraki özelliklerin bugünden tamamlandığı anlamına gelmez.
