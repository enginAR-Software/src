# FieldShift gerçek ürün dağılımı ve geçmiş ürün dizileri

Dönem: [2018, 2023]; alan: USOR03, USKS01; nokta: 50; nokta/yıl: 300.

Buğday içeren sınıflandırma: 64; ardışık yıl geçişi: 250.

| Alan | Yıl | Sınıflandırılan nokta | Buğday içeren nokta |
|---|---:|---:|---:|
| USOR03 | 2018 | 25 | 8 |
| USOR03 | 2019 | 25 | 12 |
| USOR03 | 2020 | 25 | 9 |
| USOR03 | 2021 | 25 | 12 |
| USOR03 | 2022 | 25 | 11 |
| USOR03 | 2023 | 25 | 10 |
| USKS01 | 2018 | 25 | 0 |
| USKS01 | 2019 | 25 | 0 |
| USKS01 | 2020 | 25 | 1 |
| USKS01 | 2021 | 25 | 0 |
| USKS01 | 2022 | 25 | 1 |
| USKS01 | 2023 | 25 | 0 |

## Merkez noktaların geçmişi

- USKS01: Soybeans → Sorghum → Winter Wheat → Corn → Dbl Crop WinWht/Soybeans → Corn
- USOR03: Peas → Winter Wheat → Spring Wheat → Winter Wheat → Fallow/Idle Cropland → Winter Wheat

## Birleştirme ve yorum

Toprak: 36 ayrı gözlem, 324 gösterge satırı. İklim: 24 alan/ay bağlamı.

Ürün noktaları context_id ile alan bağlamına başvurur; toprak ölçümleri nokta/yıl sayısı kadar çoğaltılmaz.

- CDL uydu sınıflandırmasıdır; nokta bazında çiftçi beyanı veya saha doğrusu değildir.
- Buğday bulunmaması yetişemeyeceğini göstermez; diğer ürün veya arazi kullanımı olabilir.
- Nokta örneklerinin oranı hektar veya bölgesel ekim alanı oranı değildir.
- Nokta dizisi gözlenen geçmiş ürün sınıflarıdır; döngünün tekrarlandığını veya en iyi olduğunu kanıtlamaz.
- Toprak ve iklim bağlamları merkez alan düzeyindedir; çevre noktalar için bağımsız ölçüm değildir.
- Toprak göstergeleri ayrı tutulur; çevre noktalarına ölçülmüş hedef olarak atanmaz.
- Çift ürün kodları aynı yıl içinde korunur; tek ürün veya iki yıl yapılmaz.
- Kışlık buğdayın CDL yılı hasat yılıdır; sonbahar ekim yılıyla karıştırılmaz.
- İki alanla mekânsal genelleme ve gelecek uygunluğu doğrulanmış sayılmaz; Kanada/Meksika kapsam dışıdır.

Kaynak: https://www.nass.usda.gov/Research_and_Science/Cropland/sarsfaqs2.php
Servis: https://pdi.scinet.usda.gov/image/rest/services/CDL_WM/ImageServer
