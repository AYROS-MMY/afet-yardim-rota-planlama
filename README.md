<h1 align="center">AYROS MMY</h1>
<p align="center">Afet Yardım Rota Optimizasyon Sistemi</p>

AYROS MMY, Fırat Üniversitesi Bilgisayar Mühendisliği Tasarım Dersi kapsamında geliştirilen bir afet lojistiği simülasyonudur. Uygulama, yardım merkezlerinden afet noktalarına yol koşullarını dikkate alan rotalar hesaplar ve ihtiyaç noktalarını öncelik puanına göre sıralar.

**Güncel geliştirme: 5. hafta.** Çalıştırılabilir kod, kullanım örnekleri ve teknik görseller [5. hafta geliştirme dalında](https://github.com/AYROS-MMY/afet-yardim-rota-planlama/tree/hafta-5-onceliklendirme) yer alır. Bu haftanın değişiklikleri [taslak PR #6](https://github.com/AYROS-MMY/afet-yardim-rota-planlama/pull/6) üzerinden incelenebilir.

## Tamamlanan çalışmalar

- Açık, hasarlı ve kapalı yolları içeren çizge modeli.
- Tahmini geçiş sürelerine göre Dijkstra ve A* ile rota hesabı.
- Aciliyet, yaralı ve afetzede sayısından hesaplanan açıklanabilir ihtiyaç puanı.
- İhtiyaç sırasından ayrı gösterilen rota süresi ve erişim durumu.
- SVG görselleri, JSON çıktıları ve 90 başarılı otomatik test.

Sıradaki geliştirme, araç kapasitesi ve müsaitliğini dikkate alan görev atamasıdır. Yol durumuna göre otomatik yeniden planlama sonraki aşamada ele alınacaktır.

## Hızlı başlangıç

Python 3.11 veya üzeri gerekir. Ek Python paketi kurulumu gerekmez.

```powershell
git clone --branch hafta-5-onceliklendirme https://github.com/AYROS-MMY/afet-yardim-rota-planlama.git
cd afet-yardim-rota-planlama
py -3.11 -m ayros data/bolgesel_ag.json --start H0 --prioritize
```

## Ekip

Muhammet Altınoluk · Mert Aydın · Yusuf Öksüz
