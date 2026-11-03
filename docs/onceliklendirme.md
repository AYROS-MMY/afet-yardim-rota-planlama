# İhtiyaç önceliklendirme

## Amaç ve kapsam

Rota algoritması seçilmiş bir hedefe nasıl gidileceğini hesaplar. İhtiyaç modeli hangi noktaların daha yüksek ihtiyaç gösterdiğini sıralar. İki sonuç birlikte sunulur; ihtiyaç puanı yol maliyetine bölünmez ve ulaşım zorlaştığında azaltılmaz. Liste araçların görev dağılımı veya tek aracın ziyaret sırası değildir.

`priority.py` hesaplamayı, `priority_output.py` JSON ve SVG üretimini yapar. Mevcut `Node`, `Graph`, Dijkstra ve A* API'leri kullanılır. Veri kümeleri ve yol maliyeti modeli değişmez. Dış Python paketi gerekmez.

## Formül ve varsayımlar

`P = 100 × [wU × (U/5) + wY × min(Y/RY, 1) + wA × min(A/RA, 1)]`

- U: senaryoda verilen 1–5 aciliyet seviyesi. Sistem bu seviyeyi kendisi tahmin etmez.
- Y: yaralı sayısı; A: toplam etkilenen kişi sayısı. Y, A'nın alt kümesidir.
- RY ve RA: katkının doyduğu sabit referans sayıları; varsayılan 100 ve 500.
- wU, wY, wA: varsayılan 0,50 / 0,30 / 0,20. Her biri 0–1 aralığında ve toplam 1.

Aciliyete en büyük başlangıç ağırlığı verilmiştir; yaralı sayısının ayrı katkısı bu alt kümeye ek ağırlık tanır. Bunlar karşılaştırılabilir bir başlangıç modeli kurmak için seçilmiş deneysel değerlerdir. Tıbbi triyaj, kurum standardı veya doğrulanmış saha karar modeli değildir. Paydaş görüşmeleri henüz yapılmamıştır; ağırlıklar bu görüşmeler ve senaryo deneyleriyle gözden geçirilmelidir.

Sabit referanslar kullanılır: yeni bir hedef eklemek başka hedeflerin puanlarını değiştirmez. Senaryonun en büyük sayısına bölme yapılmaz. Referans üstünde katkı sabit kalır; ham sayılar ve referansın aşılıp aşılmadığı JSON'da korunur. Bu doygunluk, büyük sayıların diğer ölçütleri tamamen bastırmasını önler; çok yüksek ihtiyaçlar arasındaki puan farkını azaltması modelin sınırlamasıdır. U=1 ve sayılar sıfırken varsayılan puan 10'dur; en düşük aciliyet sıfır ihtiyaç anlamına gelmez.

Puan artan bir ihtiyaca karşı azalmaz; bazı ağırlıklar sıfırsa veya referans aşılmışsa aynı kalabilir. Bütün ölçütler maksimum katkıyı verdiğinde puan 100 olur. Rota süresi, merkez seçimi ve hasar katsayısı puanın girdisi değildir.

## Eşitlik ve erişim

Sıralama yuvarlanmamış puanla azalandır. Eşitlikte sırasıyla aciliyet, ham yaralı sayısı, ham afetzede sayısı azalan; bunlar da eşitse düğüm kimliği artan kullanılır. Sıra numarası bu kararlı listedeki konumdur. Gösterimde iki ondalık kullanıldığından aynı görünen puanlar daha fazla basamakta farklı olabilir.

Her nokta için seçilen yardım merkezinden bağımsız rota hesaplanır. Ulaşılamayan noktalar aynı ihtiyaç sırasında kalır. JSON'da `reachable: false`, `cost_min: null` ve boş yol bulunur; sahte sıfır dakika yazılmaz. Hiçbir noktaya erişilemese de liste tamamlanır. Komutun sıfır çıkış kodu değerlendirme üretildiğini belirtir, bütün hedeflere ulaşılabildiğini belirtmez.

## Örnek ve duyarlılık deneyi

Bölgesel ağda A08: U=5, Y=20, A=181. Katkılar 50 + 6 + 7,24 = **63,24**. Sonraki noktalar A03 **61,94** ve A11 **61,58**. H0'dan hasar katsayısı 2 ile süreler sırasıyla 59,74 / 36,40 / 53,575 dakikadır. A12 **31,76** puanla sekizinci sırada kalır ve erişilemezdir.

Üç profil denenir: başlangıç (0,50/0,30/0,20), aciliyet ağırlıklı (0,70/0,20/0,10) ve afetzede sayısı ağırlıklı (0,30/0,20/0,50). 100/500 referansları aynı kalır. Bölgesel ağda ilk iki profil A08'i, üçüncü profil A11'i öne çıkarır. Bu, bir profilin daha doğru olduğunu kanıtlamaz; tercihlerin sonucu değiştirebildiğini gösterir. Ağırlıklar değiştirilirken yol ağı ve hedeflerin rota süreleri sabit kalır.

```powershell
py -3.11 scripts/analyze_priorities.py --output output/oncelik_deneyi.json
```

40 düğümlü ağda 2 merkez × 2 hasar katsayısı × 3 profil × 2 algoritma = 24 değerlendirme; 6 hedefle 144 kayıt. 180 düğümlü ağda 3 × 2 × 3 × 2 = 36 değerlendirme; 12 hedefle 432 kayıt. Toplam **60 değerlendirme ve 576 hedef kaydıdır**. Bunlar 576 bağımsız ihtiyaç senaryosu değildir; aynı girdiler farklı koşullarda değerlendirilir. Dosyada veri SHA-256 özetleri, politikalar, ham ihtiyaçlar, katkılar ve rotalar bulunur.

## Doğrulama

23 yeni testle toplam 90 test geçer. Yeni testler bilinen elle hesabı, 300 sabit tohumlu örneği bağımsız rasyonel hesapla, puanın sınırlarını ve monotonluğunu, eşitlik sırasını, referans doygunluğunu, geçersiz politikaları, tüm yolların kapanmasını, en yüksek ihtiyaçlı hedefin erişilemez olmasını ve girdilerin değişmezliğini sınar. Merkez/katsayı/algoritma bağımsızlığı, JSON'un yeniden üretilebilirliği ve SVG satırlarının hesap sonucuyla eşleşmesi de denetlenir. Bu yazılım doğruluğudur; modelin saha ihtiyaçlarını doğru ağırlıklandırdığına ilişkin kanıt değildir.

## Sonraki aşamaya aktarım

Araç atama modülü `PriorityAssessment.entries` içindeki ihtiyaç ve rota sonuçlarını tüketebilir. Araç konumu, kapasitesi ve müsaitliği ayrı modelde tutulmalıdır. Erişilemeyen yüksek ihtiyaçlar raporda kalmalı; atama yapılmama nedeni ayrıca belirtilmelidir. Araç modeli, otomatik atama, olaylarla rota yenileme ve etkileşimli arayüz henüz uygulanmamıştır.
