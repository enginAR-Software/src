# FieldShift aynı alan ve sezon eşleştirmesi

Kaynak sezon sayısı: 26. Toprak gözlemi: 36; tarihle bağlanan: 12; bağlanamayan: 24.

## Kaynaktan çıkarılan takvim

Aşağıdaki satırlar aynı alan/ürün/takvimdeki uygulamaları tek kez gösterir; ayrıntı CSV'de uygulama bazındadır.

| Alan | Ürün | Ekim | Hasat | Gün |
|---|---|---|---|---:|
| USKS01 | sorghum | 2016-05-12 | 2016-10-21 | 163 |
| USKS01 | soybean | 2017-05-16 | 2017-10-12 | 150 |
| USKS01 | winter_wheat | 2017-10-12 | 2018-06-18 | 250 |
| USKS01 | soybean | 2018-06-27 | 2018-10-31 | 127 |
| USOR03 | pea | 2018-03-25 | 2018-06-25 | 93 |
| USOR03 | winter_wheat | 2018-10-15 | 2019-07-15 | 274 |

## Toprak ölçümü ile zaman ilişkisi

Örnekleme tarihi, kaynak yönetim tablosundaki uygulama düzeyindeki soil sampling olayından gelir. Tekil parsel saat damgası değildir. Örnekleme gününün saati bilinmediği için hava ve yönetim özellikleri bir önceki günün sonunda kesilir.

| Alan | Örnekleme | Özelliklerin son günü | Ekimden itibaren gün | Belgelenmiş N (kg N/ha) |
|---|---|---|---:|---:|
| USOR03 / 440 | 2019-04-15 | 2019-04-14 | 182 | 89.668 |
| USOR03 / 438 | 2019-04-15 | 2019-04-14 | 182 | 89.668 |
| USOR03 / 439 | 2019-04-15 | 2019-04-14 | 182 | 89.668 |

Bağlanamayan kayıt nedenleri: {'sampling_date_missing': 24}

Bağlanan gözlemlerde bağımsız kabul edilemeyecek ortak hava grubu sayısı: 1.

## Yorumlama

Tam sezon hava özeti observed_seasons.csv içindedir. Örnekleme sonrasındaki günler features_at_sampling.csv'ye alınmaz. Hasattaki % residual removed miktarı ürün verimi sayılmaz; STIR makine/bozulma göstergesi tohum veya gübre miktarı sayılmaz.

N dönüşümü yalnız birimi açıkça elementel N olan kayıtlara uygulanır. Ürün kütlesi, tohum veya gübre etiket yüzdeleri otomatik N/P/K miktarına çevrilmez. P/K bilinmiyorsa boş kalır. Aynı gün hasat ve ekim sınırındaki gübre olayları belirsiz olarak ayrılır.

0 °C üzeri termal toplam, 0 °C altı minimum sıcaklık günleri ve 35 °C üzeri maksimum sıcaklık günleri çevresel indekslerdir. Buğdayın gelişme modeli veya zarar tahmini değildir.

## Model hazırlığı

Dinamik toprak modeli eğitimi: **hazır değil**. Aynı parselde önce/sonra toprak ölçümleri, ürün verimi ve hasat besin çıkışları eksiktir. Tekrarlı aynı alan havası, çok sayıda bağımsız iklim örneği sayılmaz.

Bu sürüm, gerçek ekim/hasat/örnekleme takvimini doğru geçmiş hava verisine bağlar. Bir sonraki süreç kalibrasyonu için gereken birleşik tabloyu ve eksiklerin kaydını üretir.

Kaynaklar: https://doi.org/10.15482/USDA.ADC/25632270 ve https://power.larc.nasa.gov/docs/services/api/temporal/daily/
