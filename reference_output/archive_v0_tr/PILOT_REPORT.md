# FieldShift pilot analiz raporu

Tekil deney birimlerinden hesaplanan betimsel istatistikler. Kaynak: NAPESHM, sürüm 1.

Ortalama farkı B − A yönündedir. % birimindeki farklar yüzde puandır; bağıl yüzde değişim değildir. pH farkı pH birimindedir.

Örnek standart sapması n−1 paydasıyla hesaplanır. Tek veya sıfır ölçümde standart sapma boş bırakılır. Eksikler sıfır sayılmaz.

## Oregon: kışlık buğday–bezelye, toprak işleme karşılaştırması

12 deney birimi, 3 uygulama. Ölçüm fazı: winter wheat.

| Uygulama | Kaynaktaki açıklama |
|---|---|
| 438 | winter-wheat_pea;chisel |
| 439 | winter-wheat_pea;no-till |
| 440 | winter-wheat_pea;plow |

Organik karbon özeti (kaynak birimi: %):

| Uygulama | n | Ortalama | Medyan | Örnek SS | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| 438 | 4 | 1.5872 | 1.5678 | 0.0741 | 1.5231 | 1.6900 |
| 439 | 4 | 1.7256 | 1.7264 | 0.1036 | 1.6214 | 1.8282 |
| 440 | 4 | 1.4736 | 1.4802 | 0.1836 | 1.2459 | 1.6882 |

Organik karbon ortalama farkları (yüzde puan, B − A):

| Karşılaştırma | A | B | Fark |
|---|---|---|---:|
| Çizel → no-till | 438 | 439 | 0.1384 |
| Çizel → pulluk | 438 | 440 | -0.1135 |
| Pulluk → no-till | 440 | 439 | 0.2520 |

## Kansas: azot düzeyi, nadas, ikinci ürün ve örtü bitkisi

24 deney birimi, 6 uygulama. Ölçüm fazı: Sorghum.

| Uygulama | Kaynaktaki açıklama |
|---|---|
| 259 | chemical fallow; 0 nitrogen |
| 260 | chemical fallow; 120 lbs of n/acre |
| 261 | double crop-soy; 0 nitrogen |
| 262 | double crop-soy; 120 lbs of n/acre |
| 263 | summer covercrop before sorghum; 0 nitrogen |
| 264 | summer covercrop before sorghum; 120 lbs of n/acre |

Organik karbon özeti (kaynak birimi: %):

| Uygulama | n | Ortalama | Medyan | Örnek SS | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| 259 | 4 | 1.4939 | 1.5004 | 0.0782 | 1.4044 | 1.5703 |
| 260 | 4 | 1.4153 | 1.3705 | 0.1089 | 1.3440 | 1.5762 |
| 261 | 4 | 1.5643 | 1.5870 | 0.0908 | 1.4378 | 1.6456 |
| 262 | 4 | 1.6039 | 1.6203 | 0.1336 | 1.4365 | 1.7385 |
| 263 | 4 | 1.6197 | 1.6382 | 0.1211 | 1.4554 | 1.7467 |
| 264 | 4 | 1.6598 | 1.6076 | 0.1372 | 1.5616 | 1.8625 |

Organik karbon ortalama farkları (yüzde puan, B − A):

| Karşılaştırma | A | B | Fark |
|---|---|---|---:|
| Nadas: 0 → 120 lb N/acre etiketli uygulama | 259 | 260 | -0.0786 |
| İkinci ürün soya: 0 → 120 lb N/acre etiketli uygulama | 261 | 262 | 0.0395 |
| Örtü bitkisi: 0 → 120 lb N/acre etiketli uygulama | 263 | 264 | 0.0402 |
| 0 N: nadas → ikinci ürün soya | 259 | 261 | 0.0705 |
| 0 N: nadas → örtü bitkisi | 259 | 263 | 0.1258 |
| 0 N: ikinci ürün soya → örtü bitkisi | 261 | 263 | 0.0553 |
| 120 lb N/acre etiketi: nadas → ikinci ürün soya | 260 | 262 | 0.1886 |
| 120 lb N/acre etiketi: nadas → örtü bitkisi | 260 | 264 | 0.2446 |
| 120 lb N/acre etiketi: ikinci ürün soya → örtü bitkisi | 262 | 264 | 0.0560 |

## Yorumlama sınırı

Oregon'da ürün sırası aynı, toprak işleme farklıdır. Kansas'ta ölçüm fazı sorgumdur; buğday fazı ölçümü gibi yorumlanmaz. Azot düzeyleri uygulama açıklamasındaki etiketlerdir; her yıl gerçekleşen gübre uygulama takvimi bu etiketten türetilmez.

Deney blokları ve istatistiksel bağımsızlık doğrulanmadan gözlemler eşleştirilmedi; p değeri veya anlamlılık testi üretilmedi. Ortalama farkı gelecekteki değişim hızı veya nedensel etki değildir. En iyi rotasyon sıralaması yapılmadı.

Tüm 9 göstergenin sayıları ve dağılımları `processed/analysis/pilot_summary.csv`, tekil değerleri `pilot_plots.csv`, karşılaştırmaları `pilot_contrasts.csv` içindedir.

Soil Health Institute (2024). https://doi.org/10.15482/USDA.ADC/25632270 — CC BY 4.0. Ham dosyalar korunur; gösterilen istatistikler türetilmiştir.
