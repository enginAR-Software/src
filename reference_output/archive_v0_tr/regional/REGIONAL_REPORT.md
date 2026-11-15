# FieldShift bölgesel iklim değişimi

Referans: [2015, 2024]; gelecek: [2040, 2049]; SSP: ssp245; model: ensemble.

İki dönem aynı projeksiyon kaynağıyla karşılaştırılır. Referans gözlem değildir. Ürün uygunluk puanı veya göç rotası hesaplanmaz.

Her yılın tam günlük ortalama sıcaklığı/toplam yağışı hesaplanır; yıllara eşit ağırlık verilir. Fark = gelecek − referans. Yüzde yağış farkı = 100 × fark / referans; sıfır referansta boş.

## USOR03

Yıllık farklar: {'temperature_delta_c': None, 'annual_precipitation_delta_mm': None, 'annual_precipitation_delta_percent': None}

Tam aylık sıcaklık karşılaştırması: 11/12; yağış: 11/12.

| Ay | Sıcaklık farkı (°C) | Aylık yağış farkı (mm) |
|---|---:|---:|
| 1 | 0.899 | 3.831 |
| 2 | 0.842 | 0.289 |
| 3 | 1.018 | 1.589 |
| 4 | 0.645 | 0.225 |
| 5 | 0.693 | 3.187 |
| 6 | 1.012 | 0.979 |
| 7 | 1.306 | -0.148 |
| 8 | 1.141 | 1.515 |
| 9 | 0.919 | 1.749 |
| 10 | 1.008 | 2.019 |
| 11 | 0.870 | 7.235 |
| 12 | eksik | eksik |

## USKS01

Yıllık farklar: {'temperature_delta_c': None, 'annual_precipitation_delta_mm': None, 'annual_precipitation_delta_percent': None}

Tam aylık sıcaklık karşılaştırması: 11/12; yağış: 11/12.

| Ay | Sıcaklık farkı (°C) | Aylık yağış farkı (mm) |
|---|---:|---:|
| 1 | 1.346 | -0.426 |
| 2 | 1.072 | 0.724 |
| 3 | 1.282 | -1.425 |
| 4 | 0.500 | 4.114 |
| 5 | 0.883 | -2.712 |
| 6 | 0.797 | 1.384 |
| 7 | 1.103 | 2.393 |
| 8 | 1.391 | -6.387 |
| 9 | 1.137 | -0.798 |
| 10 | 1.357 | -1.286 |
| 11 | 1.103 | 4.027 |
| 12 | eksik | eksik |

## Yorum sınırları

- Referans dönem de aynı SSP'nin model çıktısıdır; gözlem veya tarihsel normal değildir.
- 5–30 yıllık keşif karşılaştırması; kısa dönemlerde iç iklim değişkenliği önemlidir.
- Ensemble ortalama günlerinden sıcaklık eşiği aşım sayıları hesaplanmaz.
- Eksik gün varsa ilgili aylık/yıllık özet ve fark boş kalır; eksik yıl atılmaz.
- Nokta çıktıları çalışma alanlarının koordinatlarıdır; parsel veya tarım sınırı değildir.
- Ürün gözlemleriyle doğrulanmış coğrafi model ve dinamik toprak tepkisi henüz yok.

NASA kaynak ve yöntem: https://power.larc.nasa.gov/docs/services/api/projection/
https://power.larc.nasa.gov/docs/methodology/data/sources_future/
