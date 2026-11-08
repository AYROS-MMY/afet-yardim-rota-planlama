# İhtiyaç türüne göre görev atama

Varsayılan senaryo `data/gorev_senaryosu_12_arac.json` sürüm 2'dir: `schema_version`, `vehicles`, `tasks`. Araç alanları `id`, `center`, `capacity`, `available`, `service`; görev alanları `id`, `target`, `service`, `quantity`, `urgency`.

Hizmet türleri `logistics`, `medical`, `rescue`. Lojistik kapasite ve miktar pozitif tam sayı standart kolidir. Sağlık/kurtarma kapasitesi ve görev miktarı 1 ekip olarak sınırlandırılır. Görev aciliyeti 1–5 tam sayıdır. Her hedef/tür çifti için bir görev vardır. Görevi olmayan bölgeye otomatik ihtiyaç üretilmez. Boş görev listesi geçerlidir. Yinelenen JSON alanları, görev/araç kimlikleri, yanlış türler, alanlar ve hedefler reddedilir.

Sürüm 1 `data/arac_senaryosu.json` eski koli davranışını korur: bütün afet noktaları için talep gerekir; sıralama önceki bölge puanıdır. Sürüm 2'de görev aciliyeti azalan, bölge puanı azalan, hedef kimliği ve görev kimliği artan sıralanır. Bölge puanının kendi eşitlik kuralları eski modda korunur.

## Atama

Her görev için uygun hizmet türündeki müsait ve boş araçlar bulunur. Tam miktarı taşıyabilen ve hedefe erişebilen adaylardan en düşük rota süreli olan seçilir; eşit sürede araç kimliği kullanılır. Araç bu turda başka görev almaz. Aynı bölgenin farklı ihtiyaçlarına farklı araçlar atanabilir. Bölge bütün olarak tamamlandı işaretlenmez. Girdi dosyaları ve filo durumu hesaplama sırasında değiştirilmez.

Aday yoksa gerekçe önceliği: hiçbir merkezden rota yok (`unreachable`); uygun hizmet türü yok (`no_matching_vehicle`); türü uygun müsait/boş araç yok (`no_available_vehicle`); bu araçların kapasitesi yetersiz (`insufficient_capacity`); kapasitesi yeterli araçların merkezlerinden rota yok (`no_reachable_vehicle`). Bu, seçim anındaki birincil gerekçedir; bütün engellerin listesi değildir.

## 9 araçlı karşılaştırma örneği ve birimler

9 araç, 16 görev; 8 atama. Lojistik toplam 340 koli, sağlık 2 ekip, kurtarma 1 ekip görevi. Koli ile ekip miktarları tek bir toplamda toplanmaz. A08-L V03'e, A08-S S01'e atanır; A08-K bekler. K01 daha acil A03-K görevindedir. A11-L kapasite nedeniyle bekler ama A11-S S02'ye atanır. A12 erişilemez. Bunlar planlanan görevlerdir, gerçekleşmiş teslimatlar değildir.

Görev aciliyeti ve miktarı sentetik girdidir; insan sayısından otomatik sağlık/kurtarma ihtiyacı çıkarılmaz. Sağlık aracı sağlık ekibini, kurtarma aracı kurtarma ekibini bölgeye ulaştırmayı temsil eder. Operasyon sonucu, tahliye, hastane ve saha başarısı modellenmez.

## Görünüm ve çıktı

`py -3.11 -m ayros.dispatch --html output/hafta6_araclar.html --svg output/hafta6_atama.svg --json output/hafta6_atama.json`

Bölge paneli ayrı ihtiyaçları ve nedenleri gösterir. Bölge/araç seçimi yalnızca rotaları filtreler; alttaki tablo bütün planı gösterir. Tüm görevler seçimi rotaları geri getirir. Araçlar başlangıç merkezlerindedir; hareket yoktur. Ortak yollarda renkler örtüşebileceğinden tek araç seçimi kullanılabilir. Mobilde harita yatay kaydırılır.

JSON çıktı sürümü 2; görev bilgisi, birim, hizmet türü, araç, rota, politika ve kaynak dosyaların SHA-256 özetlerini içerir. Eski şema kullanıldığında `task` boş olur; hizmet lojistik ve birim koli olarak kaydedilir. Süre ölçümleri çalıştırmalar arasında değişebilir.

## Sınırlar

Açgözlü seçim global optimum değildir; büyük araç küçük talepte erken kullanılabilir. Her araç/görev tek eşleşme alır; bölünmüş talep, stok ve tekrar sefer yoktur. Durum takibi ve yol olayı sonraki haftanın işidir. 125 test; eski rota/öncelik davranışını, görev türlerini, aciliyet sırasını, bağımsız ihtiyaçları, hatalı girdileri ve çıktı eşleşmesini kapsar.

## 12 araçlı destek filosu denemesi

Aynı 16 görev ve yol ağı korunarak `data/gorev_senaryosu_12_arac.json` hazırlandı. Ek araçlar: H2'de bir kurtarma aracı K02; H1'de 100 koli kapasiteli V07; H0'da 100 koli kapasiteli V08. V05 yine müsait değil. İlk turda 11 görev atanır: 7 lojistik görevde 455 koli, 2 sağlık ve 2 kurtarma görevi. A08'in üç görevine V03, S01 ve K02 atanır. A11-L kapasite, A12-L kapalı yollar, A02-L/A10-L/A05-L boş araç yokluğu nedeniyle bekler. 9 araçlı senaryo karşılaştırma için korunmuştur; varsayılan ve güncel rapor 12 araçlı sürümdür.

```powershell
py -3.11 -m ayros.dispatch --fleet data/gorev_senaryosu_12_arac.json --html output/hafta6_12_arac.html --svg output/hafta6_12_arac.svg --json output/hafta6_12_arac.json
```

A*/Dijkstra atamaları karşılaştırıldı; araç türü, kapasite ve tek görev koşulları doğrulandı. Tarayıcıda A08'in üç rotası ve tüm görevler görünümündeki 11 rota kontrol edildi. Bu sonuçlar planlanan görevlerdir, gerçekleşmiş teslimatlar değildir.

## 6. hafta karşılaştırma kaydı

`deneyler/hafta6_baslangic.json` mevcut 12 araçlı başlangıç planını, girdi dosyalarının SHA-256 özetlerini ve hesap parametrelerini saklar. Sonraki yöntemler aynı girdiler ve kurallarla karşılaştırılmalıdır. Bu kayıt 16 görev, 11 atama ve 455 koli planlanan yük içerir; teslimat kanıtı değildir. HTML özet kartları toplam lojistik ihtiyacı, araçlara planlanan ve henüz araç atanmayan miktarı ayrı gösterir. Araç kartları başlangıç, hedef, planlanan yük/kapasite ve tahmini ulaşım süresini içerir.
