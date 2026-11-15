# Gerçek ürün dağılımı ve gözlenen ürün dizileri — 0.6.0

## Linux Mint üzerinde çalıştırma

```bash
unzip FieldShiftData_0_8_0.zip
cd FieldShiftData_0_8_0
python3 -m fieldshift_data --version
python3 -m fieldshift_data cropland --offline
```

Python 3.10+ yeterlidir; yeni kütüphane veya API anahtarı gerekmez. Pakette
varsayılan USDA ve NASA sorgularının gerçek ham yanıtları bulunur. Her koşu
ayrı çıktı klasörü oluşturur. İlk kez farklı veri indirmek için:

```bash
python3 -m fieldshift_data cropland --online
python3 -m fieldshift_data self-test --online
```

`--online` yalnız eksik sorguları indirir. `self-test --online` ise boş
geçici önbellekte gerçekten yeniden indirir; artık sekiz canlı kontrol içerir.
CDL kontrolü; servis, sınıf sözlüğü, 2019 raster kataloğu ve Oregon çevresinde
25 noktanın sınıflandırmasını yeni indirir. Bu test tüm yıllar/bölgeler için
doğruluk değerlendirmesi değildir.

## Kaynak ve coğrafya

USDA NASS Cropland Data Layer (CDL), uydu ve referans verileriyle üretilmiş
yıllık ürün/arazi örtüsü sınıflandırmasıdır. Bu sürüm, resmî CroplandCROS
ImageServer servisinin `query`, `rasterAttributeTable` ve `getSamples`
işlemlerini kullanır. Çiftçi beyanı veya tekil tarla yer gerçeği olarak sunulmaz.

Varsayılan iki alan NAPESHM içindeki USOR03 ve USKS01'dir. Her merkezin
çevresinde 5 × 5 sabit nokta, enlem/boylamda 0,01 derece aralıklarla seçilir.
50 nokta 2018–2023 boyunca izlenir: toplam 300 nokta/yıl kaydı. Bu derece
ızgarası eşit alanlı değildir; boylam adımının gerçek uzaklığı enleme bağlıdır.
Noktalar parsel veya alan sınırı değildir. Örneklerin oranı hektara veya
bölgesel ekim payına çevrilmez. Kanada ve Meksika bu CDL pilotuna dahil değildir.

`config/cropland.json` ayarları:

```json
{
  "sites": ["USOR03", "USKS01"],
  "years": [2018, 2023],
  "grid_side": 5,
  "step_degrees": 0.01
}
```

Bu sürüm 2008–2023 içindeki aynı 30 m CDL serisini destekler. 2024 ile
ürün çözünürlüğü/yöntemi değiştiği için farklı seriler sessizce birleştirilmez.
1–5 alan, 1/3/5 kenarlı ızgara ve en fazla 16 yıl kabul edilir. Alternatif:

```bash
python3 -m fieldshift_data cropland --config config/cropland.json --regional-config config/regional.json --online
```

Alan kodları `config/regional.json` içinde de bulunmalıdır. İklim hesabı aynı
model/senaryoyla yapılır; ürün noktalarına ayrı birer hava gözlemi atanmamıştır.

## Edinme ve ön işleme

1. Servisin tek bantlı tematik CDL şeması kontrol edilir; sınıf sözlüğü indirilir.
2. Her yıl için tek bir birincil raster kaydı seçilir. Raster kimlikleri yıllar
   arasında tahmin edilmez. API örneklemesi o raster kimliğine kilitlenir.
3. Noktalar EPSG:4326 (boylam, enlem) ile gönderilir; en yakın komşu kullanılır.
   Yanıtın yılı, raster kimliği, koordinatı ve çözünürlük bilgisi denetlenir.
4. Yanıt sırasına güvenilmez; noktalar koordinatlarıyla eşlenir. Eksik,
   tekrarlı veya yabancı konumlar ayrı değerlendirilir; tekrarlı/yabancı reddedilir.
5. Sıfır/background, NoData ve dönmeyen noktalar bilinmeyen olarak korunur;
   buğday yok anlamına çevrilmez. Tanımı olmayan sınıf kodları reddedilir.
6. Buğday kodları 22, 23, 24 ve buğday içeren çift ürün kodları 26, 225,
   230, 234, 236, 238'dir. Buckwheat (39, karabuğday) buğday sayılmaz.
7. Çift ürün sınıfı tek yılın bileşik sınıfı olarak korunur. Eksik yılın
   üzerinden atlayarak ardışık ürün geçişi oluşturulmaz.

CDL kışlık buğday yılı hasat yılıdır; önceki sonbaharın ekim yılı değildir.
Buğday olmayan sınıf, buğdayın yetişemeyeceğinin kanıtı değildir; başka bir
ürün ekilmiş veya farklı arazi kullanımı seçilmiş olabilir.

Ham yanıtlar `data/raw/cropland_cros/` altında özgün baytlarıyla saklanır.
Yanında URL, indirme zamanı, boyut ve SHA-256 içeren kayıt bulunur. İnternet
yanıtındaki servis hataları veri olarak kabul edilmez. Bozuk önbellek otomatik
ezilmez. USDA tarafından verilen değişmez sürüm numarası yoktur; bu nedenle
indirilen anın içerik özetleriyle tekrar üretilebilirlik sağlanır.

## Çıktıların anlamı

| Dosya | İçerik |
|---|---|
| CROPLAND_REPORT.md | Türkçe sonuç, merkez ürün dizileri ve sınırlar |
| crop_observations.csv | 300 nokta/yıl; konum, sınıf, buğday ve eksiklik bilgisi |
| observed_sequences.csv | 50 noktanın 6 yıllık sınıf dizisi |
| observed_transitions.csv | 250 ardışık yıl geçişi |
| sample_coverage.csv | Alan/yıl başına örnek ve buğday sayısı |
| class_dictionary.csv | Kaynak sınıf kodları; buğday kapsamı |
| crop_samples.geojson | Sınıf ve yıl içeren 300 nokta özelliği |
| climate_context.csv | 2 merkez × 12 ay: mevcut iklim dönem karşılaştırması |
| regional_context.json | Aynı koşunun tam iklim hesabı ve kökenleri |
| soil_context.csv | 36 toprak gözlemi × 9 gösterge; yöntem, birim ve uygulama kimliği |
| cropland.json | Kapsam, yapılandırma özeti, indirme kayıtları ve hazırlık durumu |

Ürün kayıtları `context_id` ile alan düzeyindeki iklim/toprak bağlamına
başvurur. Toprak değerleri 300 ürün kaydına bağımsız ölçümlermiş gibi
eklenmez. Kaynakta tekil parsel koordinatları/sınırları olmadığı için merkez
CDL pikselinin tüm deney parsellerini temsil ettiği varsayılmaz. CSV/JSON
çıktıları bu aşamada yerel veri alışverişi içindir; önceki veri hattının SQLite
çıktıları ayrıca çalışmaya devam eder.

## Gerçek koşunun sonucu

300/300 nokta/yıl sınıflandırılmış; 64'ü buğday içeren sınıftadır. Eksik
olmadığı için 50 × 5 = 250 komşu yıl geçişi çıkarılmıştır. Merkez örnekleri:

- Oregon: Peas → Winter Wheat → Spring Wheat → Winter Wheat → Fallow/Idle Cropland → Winter Wheat.
- Kansas: Soybeans → Sorghum → Winter Wheat → Corn → Dbl Crop WinWht/Soybeans → Corn.

Bunlar gözlenen sınıf geçmişleridir. Aynı döngünün tekrarlandığı, toprağa en
iyi geldiği veya sonraki yıl ekilmesi gerektiği sonucu çıkarılmaz. 300 satır
iki iklim bağlamını paylaşır; rastgele satır ayırarak eğitim/test yapılması
mekânsal bağımsızlık sağlamaz. Bu sürüm model eğitmez ve en iyi rotasyonu
hesapladığını iddia etmez. Mevcut P-FLUX referans planlayıcısı ayrı çalışır.

Sonraki aşamada daha çok bağımsız coğrafi blok ve yıl, plot/piksel konum
doğrulaması ve aynı parselde zamanla değişen toprak/hasat kayıtları gerekir.
Yeni ürün dizileri alternatif rotasyon adayları için veri sağlar; besin
tepkisi ve verim karşılaştırması ayrı kalibre edilmelidir.

## Kaynaklar

- USDA veri kapsamı ve tanımlar: https://www.nass.usda.gov/Research_and_Science/Cropland/sarsfaqs2.php
- USDA 2019 Oregon metaverisi: https://www.nass.usda.gov/Research_and_Science/Cropland/metadata/metadata_or19.htm
- Gerçek servis: https://pdi.scinet.usda.gov/image/rest/services/CDL_WM/ImageServer
- Örnekleme sözleşmesi: https://developers.arcgis.com/rest/services-reference/enterprise/get-samples/
- NAPESHM: https://doi.org/10.15482/USDA.ADC/25632270
