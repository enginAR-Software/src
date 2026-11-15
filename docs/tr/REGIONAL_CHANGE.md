# Bölgesel iklim değişimi — 0.5.0

Bu sürüm, iki gerçek çalışma alanında aynı model ve SSP senaryosunun iki
dönemini karşılaştırır. Varsayılan alanlar NAPESHM içindeki USOR03 (Oregon)
ve USKS01 (Kansas); referans dönem 2015–2024, gelecek dönem 2040–2049,
senaryo SSP2-4.5, model NASA POWER NEX-GDDP `ensemble` değeridir.

## Çalıştırma

Yeni paketi ayrı bir klasöre açın:

```bash
unzip FieldShiftData_0_5_0.zip
cd FieldShiftData_0_5_0
python3 -m fieldshift_data --version
python3 -m fieldshift_data regional --offline
```

Varsayılan sorguların ham yanıtları paketle gelir. Yeni dönem veya senaryo
için `config/regional.json` dosyasını değiştirip:

```bash
python3 -m fieldshift_data regional --online
```

`--online` yalnız eksik istekleri indirir; mevcut doğrulanmış yanıtı kullanır.
İki seçenek aynı anda kullanılamaz. Alternatif yapılandırma:

```bash
python3 -m fieldshift_data regional --config config/regional.json --offline
```

5–30 yıl uzunluğunda, eşit uzunlukta ve çakışmayan dönemler desteklenir.
API sorguları en fazla beş yıllık parçalara ayrılır. Her isteğin tam URL'si,
tarihleri, koordinat kaynağı, yanıt başlığı ve SHA-256 değeri korunur.
Varsayılan hesap sekiz yeni günlük veri isteğinden oluşur.

## Hesap

Önce her yıl için tüm günlerin sıcaklık ortalaması ve yağış toplamı alınır.
Sonra yıllara eşit ağırlık verilerek dönem özeti hesaplanır. Aylık karşılaştırma
için her yılın aynı ayı özetlenir ve yıllar üzerinden ortalama alınır.

- Sıcaklık farkı: gelecek dönem ortalaması − referans dönem ortalaması, °C.
- Yağış farkı: gelecek ortalama yıllık/aylık toplam − referans toplam, mm.
- Yıllık yağış yüzdesi: 100 × fark / referans; sıfır referansta tanımsızdır.

Her değişkenin eksikliği ayrı denetlenir. İlgili değişkende tek gün eksikse
o yıl/ay özeti boş kalır; gerekli yıllardan biri boşsa dönem özeti ve farkı
da boş kalır. Eksik yıl ortalamadan çıkarılmaz. Verisi tam diğer aylar
hesaplanabilir. Eksik gün sıfır kabul edilmez veya 365 güne ölçeklenmez.
Artık günler Gregorian takvimine göre korunur.

## Çıktılar

Her koşuda yeni `outputs/regional_<kimlik>/` klasörü açılır:

| Dosya | İçerik |
|---|---|
| REGIONAL_REPORT.md | Türkçe yöntem, farklar ve yorum sınırları |
| regional.json | Dönem, kapsam, yıllık/aylık özetler ve ham yanıt kökenleri |
| annual.csv | Her alan/dönem/yıl için kapsam ve tam veri özetleri |
| monthly_changes.csv | Her alan için 12 ayın karşılaştırması |
| regional_change.geojson | Haritada kullanılabilecek gerçek çalışma alanı noktaları |

GeoJSON çalışma alanlarını nokta olarak gösterir; alan sınırı veya parsel
üretmez. Eksik farklar JSON/GeoJSON'da `null`, CSV'de boş hücredir.

## Bu hesap neyi gösterir?

Bu adım, bölgesel değişimin iklim girdisini sayısallaştırır. Referans dönemi
de aynı SSP'nin model çıktısıdır; gerçek hava gözlemi veya resmi iklim normali
olarak adlandırılmaz. Kısa dönemlerin doğal değişkenliği önemlidir. Ensemble
ortalamasından model üyelerinin belirsizlik aralığı çıkarılamaz; günlük ensemble
ortalamasının eşik aşımı gerçek aşırı sıcak gün sayısı sayılmaz.

Buğday yetiştirme kayıtları/bağımsız uygunluk katmanı ve mekânsal doğrulama
henüz bu hesaba bağlanmamıştır. Bu nedenle uygunluk puanı, göç yönü veya
rotasyon değiştirme kararı üretilmez. Rotasyon planlayıcı aynı gözlenen
P-FLUX döngüleriyle çalışmaya devam eder; iklim farkları fosfor bütçesine
nedensel tepki katsayısı gibi uygulanmaz.

Sonraki geliştirme: bağımsız coğrafi ürün verisini edinmek, aynı ızgarada
iklim/toprakla eşlemek, mekânsal olarak ayrılmış doğrulama alanlarında
yetiştirilme tahminini sınamak ve ardından alternatif ürün döngülerini
aynı toprak başlangıç koşullarında değerlendirmek.

## Kaynaklar

- NASA servis kapsamı: https://power.larc.nasa.gov/docs/services/api/projection/
- Model ve yorumlama yöntemi: https://power.larc.nasa.gov/docs/methodology/data/sources_future/
- NAPESHM alan koordinatları: https://doi.org/10.15482/USDA.ADC/25632270

## Paketle gelen gerçek koşu

Sekiz isteğin tamamı yeni indirildi; çevrimdışı tekrar başarılıdır. Her iki
alanda 11 ay tam karşılaştırılabilir. Temmuz sıcaklık farkı Oregon'da
+1,306 °C, Kansas'ta +1,103 °C; temmuz yağış farkı sırasıyla −0,148 ve
+2,393 mm'dir. Aralık eksik olduğundan yıllık farklar boş kalır. Ayrıntılı
çıktı: `reference_output/regional/REGIONAL_REPORT.md`.

0.6.0 notu: `regional_change.geojson` özelliklerine 12 aylık
`monthly_change` listesi eklendi. Yıllık farklar eksik olsa da tam aylar
harita tüketicisi tarafından kullanılabilir.
