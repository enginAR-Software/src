# FieldShift gerçek veri raporu

Veri kaynakları: P-FLUX ve/veya NAPESHM, sabitlenmiş sürüm 1.

Bu rapor gerçek kaynak tablolarını inceler ve mevcut fosfor bütçelerini yeniden hesaplar. Yeni rotasyon önerisi veya gelecekteki toprak stoku tahmini üretmez.

## Dosyalar

- `profiles.csv` / `profiles.json`: sütunlar, eksikler ve sayısal özetler.
- `processed/`: temizlenmiş ve türetilmiş CSV tabloları.
- `fieldshift_data.sqlite3`: aynı tabloların yerel veritabanı.
- `manifest.json`: kaynak, sürüm, dosya bütünlüğü ve işlem kaydı.

## Tablolar

| Kaynak | Tablo | Satır | Sütun |
|---|---|---:|---:|
| pflux | DataSourcesAndReferences | 174 | 16 |
| pflux | PBudgetData | 224 | 44 |
| napeshm | dbcolumns | 464 | 7 |
| napeshm | dbtables | 9 | 2 |
| napeshm | mgmtdata | 12643 | 8 |
| napeshm | plfa_ng | 1403 | 131 |
| napeshm | plfa_nm | 1403 | 114 |
| napeshm | rr_lookup | 932 | 5 |
| napeshm | sites | 94 | 50 |
| napeshm | soildata | 1453 | 126 |
| napeshm | treatments | 508 | 21 |

## Fosfor hesabı

Agronomik bütçe = uygulama + atmosferik çökelme + sulama − hasatla uzaklaşma.

Genel tarla bütçesi = agronomik bütçe − kaydedilmiş hidrolojik P çıkışı.

Birim: kg P/ha/yıl. Hidrolojik ölçümün P formu korunur; farklı formlar eşdeğer toplam P kaybı sayılmaz.

224 kayıt, 61 sistem; 163 rotasyon konumu ve 61 sistem özeti.

Buğday sözcüğü içeren 23 sistem var; bu metin filtresi ürün ontolojisi değildir.

Bunların 21 tanesi özet adında, 2 tanesi yalnız alt ürün kayıtlarında belirlenmiştir. `wheat_system_comparison.csv` tüm aday sistemleri içerir.

Yayımlanmış sistem bütçesine göre kontrol (±0.03 kg P/ha/yıl yuvarlama toleransı):

- Agronomik: {'within_rounding': 59, 'missing': 2}
- Genel: {'within_rounding': 45, 'missing': 16}

`difference` satırları otomatik düzeltilmedi; `system_comparison.csv` dosyasında farklarıyla korunur. Eksik bileşenler sıfır sayılmaz.

İlk beş sistem özeti:

| Sistem | Rotasyon | Hesaplanan agronomik | Yayımlanan | Kontrol |
|---|---|---:|---:|---|
| AAFC-Sys1 | Canola-Soybean-Wheat | 3.39 | 3.38 | within_rounding |
| AAFC-Sys2 | Wheat-Canola | 4.38 | 4.38 | within_rounding |
| AAFC-Sys3 | Wheat-Hemp (oilseed) | 2.76 | 2.76 | within_rounding |
| AAFC-Sys4 | Organic small grains mixed farm with flexible rotation | 12.76 | 12.76 | within_rounding |
| ABS-Sys1 | Rangeland_subtropical (pastures/grazinglands) | 0.53 | 0.53 | within_rounding |

## Toprak gözlemleri

94 alan, 508 uygulama, 1453 deney birimi.

Buğday bulunan alan bayrağı: 40 alan. Ürün fazında wheat geçen gözlem: 277.

Gerçek toprak gözlemi bulunan aday alan sayısı: 39. Toprak tablosunda bulunmayan adaylar: ['USWA03']. Ayrıntı: `wheat_site_coverage.csv`.

`site_wheat_flag` bir alanın herhangi bir deney biriminde buğday bulunmasını belirtir; bütün gözlemlerin buğday olduğu anlamına gelmez.

Toplam azot (%), H3A nitratı ve potansiyel mineralize azot ayrı göstergelerdir. Olsen ve Mehlich-3 fosforu birleştirilmedi. ppm/mg kg değerleri kg/ha stoklarına dönüştürülmedi.

`treatment_summary.csv` aynı alan/uygulama/gösterge içindeki deney birimlerini özetler. Zaman içindeki değişim veya uygulamanın nedensel etkisi olarak yorumlanmaz.

Yönetim tablosunda 986 reserved index row ve 0 eşleşmeyen bağlantı var. Yönetim olayları ayrı tutuldu; toprak satırları olay sayısı kadar çoğaltılmadı.

## Sonraki değerlendirme

Önce eksik oranlarını, bütçe farklarını ve ölçüm yöntemlerini inceleyin. Sonra aynı deney alanındaki karşılaştırılabilir uygulamaları seçin. Farklı kaynakların alanları ortak deney gibi birleştirilmedi.

## Kaynak atıfları

Williams ve diğerleri (2021). LTAR Phosphorus Budget Summary. https://doi.org/10.15482/USDA.ADC/1523365

Soil Health Institute (2024). North American Project to Evaluate Soil Health Measurements. https://doi.org/10.15482/USDA.ADC/25632270
