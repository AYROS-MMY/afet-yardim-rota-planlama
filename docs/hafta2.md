# İkinci hafta çalışma notu

Bu hafta amaç, afet bölgesini Python nesnelerine dönüştürmek ve verinin doğruluğunu sınamaktır. Dijkstra, A*, öncelik puanı, araç atama ve hareket simülasyonu henüz yoktur.

## Model kararları

- Çizge yönsüzdür: her yol iki yönde geçişi temsil eder. Paralel yol ve kendi üzerine dönen yol desteklenmez.
- Komşuluk listesi her düğümün bağlı olduğu düğüm ve yol çiftlerini tutar.
- Kapalı yollar veri kaybını önlemek için silinmez. `neighbors()` varsayılan olarak bunları filtreler; `traversable_only=False` bütün bağlantıları getirir.
- Hasarlı yol geçilebilirdir. Hasar maliyetinin uygulanması sonraki haftanın işidir.
- Boş düğüm listesi reddedilir. Yolu olmayan veya birbirine erişemeyen düğümler geçerlidir; rota bulunamaması sonraki algoritma aşamasında ele alınacaktır.
- Koordinatlar sentetik bir yerel düzlemde kilometredir. Yol uzunluğu ile tahmini süre farklı alanlardır; bu sürümde hesaplama için birleştirilmez.
- Nesneler yüklendikten sonra düğüm/yol alanları değiştirilmez. Dinamik güncelleme arayüzü sonraki aşamada eklenecektir; `graph.nodes` ve `graph.roads` sözlükleri uygulama dışında değiştirilmemelidir.

## Veri sözlüğü

| Kayıt | Alan | Anlam ve kural |
| --- | --- | --- |
| Senaryo | `schema_version` | Bu sürüm için `1` |
| Senaryo | `name`, `description` | Boş olmayan ad ve açıklama |
| Senaryo | `directed` | Bu sürümde `false` |
| Senaryo | `coordinate_system` | `cartesian_km` |
| Düğüm | `id`, `name` | Benzersiz kimlik ve okunabilir ad |
| Düğüm | `node_type` | `intersection`, `aid_center`, `disaster_area` |
| Düğüm | `x_km`, `y_km` | Sonlu sayısal konum; negatif koordinat mümkündür |
| Afet düğümü | `affected_count` | Negatif olmayan tam sayı; yaralıları da içeren afetzede sayısı |
| Afet düğümü | `injured_count` | Afetzede sayısını aşmayan yaralı sayısı |
| Afet düğümü | `urgency_level` | 1–5 arasında aciliyet; 5 en yüksek. Öncelik puanı değildir |
| Diğer düğüm | İhtiyaç alanları | Verilmez veya sıfır olur |
| Yol | `id` | Benzersiz yol kimliği |
| Yol | `source`, `target` | Var olan iki farklı düğüm |
| Yol | `distance_km` | Pozitif, sonlu yol uzunluğu |
| Yol | `travel_time_min` | Pozitif, sonlu temel süre tahmini |
| Yol | `status` | `open`, `damaged`, `closed` |

## Örnek senaryo

`H0` yardım merkezi, `K1`–`K6` kavşak, `A1`–`A3` afet noktasıdır. 14 yolun 9'u açık, 3'ü hasarlı, 2'si kapalıdır. `R03` ve `R09` kapalı; `R07`, `R10` ve `R13` hasarlıdır.

Mesafeler örnek veri üretiminde düzlem uzaklığının yaklaşık 1,1 katı, temel süreler ise kilometre başına 2 dakika olarak seçilmiştir. Bunlar ölçülmüş saha verileri değildir. Hasarlı yol sürelerine henüz ceza eklenmez. Dosyadaki değerler senaryonun girdileridir; uygulama bunları otomatik yeniden hesaplamaz.

## Çalıştırma ve doğrulama

```bash
python -m ayros --svg docs/hafta2_senaryo.svg
python -m unittest discover -s tests -v
```

10 Ekim 2026 doğrulamasında **19 test metodu başarılıdır**. Parametreli alt kontroller bu sayıya ayrıca eklenmemiştir. Testler kayıt sayıları, çift yönlü bağlantı, kapalı/hasarlı yol davranışı, kimlik tekrarları, eksik düğüm, sayısal alanlar, afet verileri, bozuk JSON, bağlantısız ağ, SVG ve CLI çıkış kodlarını kapsar. Henüz rota doğruluğu veya algoritma performansı ölçülmemiştir.

## Kısa sunum akışı

1. JSON'da bir düğüm ve bir yol kaydını gösterin. Alanların birimlerini açıklayın.
2. `python -m ayros` komutunu çalıştırın; 10 düğüm, 14 yol ve durum sayılarını gösterin.
3. `K1` ile `K2` arasında `R03` veride bulunduğu halde geçilebilir komşularda görünmediğini açıklayın.
4. SVG'yi tarayıcıda açın. Çizginin rengi ve deseniyle yol durumunu gösterin.
5. Testleri çalıştırın. “Sonraki hafta bu model üzerinde Dijkstra ile rota hesaplayacağız” diyerek tamamlayın.

Deneme değişikliklerini asıl senaryoyu bozmadan bir kopyada yapın. Örneğin `R03` durumunu `open` yapınca iki düğüm birbirinin geçilebilir komşusu olur. Bu bir rota hesabı değil, komşuluk değişimidir.

## Sonraki hafta

Dijkstra uygulaması, açık ve hasarlı yol için açıkça tanımlanmış maliyet modeli, elle doğrulanmış kısa rota örneği ve ulaşılamayan hedef testi planlanmaktadır. A* ve araç atama daha sonraki aşamalardır.
