# 0.4.0 — aynı alan, sezon ve örnekleme tarihini birleştirme

## Çalıştırma

Yeni dağıtımın dosya ve klasör adı `FieldShiftData_0_4_0` içerir. Yeni klasörde:

```bash
python3 -m fieldshift_data --version
python3 -m fieldshift_data seasons --offline
python3 -m fieldshift_data self-test --online
```

Sürüm **0.4.0** olmalıdır. Pakette iki gerçek sezon hava sorgusu ve kaynak
kayıtları bulunur. Yeni bir tarih isteği veya eksik önbellek için:

```bash
python3 -m fieldshift_data seasons --online
python3 -m fieldshift_data seasons --pilot oregon --offline
python3 -m fieldshift_data seasons --pilot kansas --offline
```

`--online` ve `--offline` birlikte verilmez. İnternet izni verilmediyse yeni
bir hava isteği kendiliğinden yapılmaz. Üçüncü taraf kütüphane kurulumu gerekmez.

## Gerçek kaynak takvimi

NAPESHM yönetim dosyası; ekim, hasat, gübreleme, toprak işleme ve bazı alanlarda
toprak örnekleme olaylarını içerir. Önceki sürümlerde ayrı tutulan bu kayıtlar,
bu sürümde kaynak açıklamalarıyla incelenip eşleştirilmiştir.

Oregon USOR03:

- Bezelye: 25 Mart 2018 ekim, 25 Haziran 2018 hasat.
- Kışlık buğday: 15 Ekim 2018 ekim, 15 Temmuz 2019 hasat.
- Toprak örnekleme olayı: 15 Nisan 2019, üç uygulamanın her biri için kayıtlı.
- Toprak gözlemleri: her uygulamada dört, toplam 12 deney birimi.

Takvim yılı aşan kışlık ürün tek sezon olarak tutulur. Tam buğday sezonu 274
takvim günüdür. Hava verileri aynı alan koordinatlarında ve gerçek 2018–2019
döneminde NASA POWER geçmiş servisi üzerinden alınır; 2024 veya 2027 verisi
bu tarihlerin yerine kullanılmaz.

Kansas USKS01'de 2016–2018 ekim ve hasat olayları vardır; seçilen kayıtlarda
2019 toprak örnekleme tarihi bulunmaz. 24 toprak gözlemi bu nedenle tarihi
uydurulmadan `unlinked_soil.csv` dosyasına ayrılır. Tarihli ürün sezonlarının
hava özetleri yine hesaplanır.

## Eşleştirme kuralları

1. Alan ve uygulama kimlikleri kaynak ilişkileriyle doğrulanır.
2. `reserved index row` işaretleri tarla işlemi sayılmaz; kayıt kapsamını açıklayabilir.
3. Ekim satırındaki STIR makine kaydı gerçek ürün satırından ayrılır.
4. Ürün açıklaması, `config/season_alignment.json` içindeki incelenmiş takma adlarla eşlenir.
5. Aynı ürüne ait sonraki hasat olayı bulunur. Eksik veya çakışan dönemler sorun olarak kaydedilir.
6. Toprak ölçümünün kampanya yılı, kaynak açıklamasına göre 2019'dur. Tek ve uygun bir örnekleme olayı yoksa tarih atanmaz.
7. Örnekleme olayı uygulama düzeyindedir; tekil parsel saati gibi sunulmaz.

## Gelecek bilgisinin sızmasını önleme

15 Nisan 2019'da ölçülen toprağı açıklayacak tabloya, temmuz hasadına kadar
olan hava verisi eklenmez. Örnekleme saati bilinmediği için 15 Nisan gününün
havası ve yönetim olayları da özelliklere alınmaz; kesim **14 Nisan 2019**'dur.

Buğday ekiminden bu kesime kadar 182 tam gün vardır. Özellik tablosundaki
yağış, sıcaklık ve çevresel indeksler bu aralıkla hesaplanır. Tam sezon
özetleri ayrı dosyada tutulur; eğitim girdileriyle karıştırılmaz.

Toprak analizleri `target_` önekiyle hedef sütunlarıdır. Başlangıç toprak
durumuymuş gibi girdi yapılmaz. `training_contract.json` aday girdi, hedef,
kimlik ve ortak hava grubu sütunlarını ayırır. Dosya birleştirilmiş tabloyu
belgeler; dinamik model eğitimine otomatik izin vermez.

## Birim ve miktar denetimi

Elementel N olduğu açık birimler tanınır. `lbs acre-1 N` için dönüşüm:

```text
kg N/ha = lb N/acre × 0.45359237 × 10000 / 4046.8564224
```

Oregon'un buğday öncesi 80 lb N/acre kaydı yaklaşık 89,668 kg N/ha olarak
kaydedilir. Bu miktar bir öneri veya toprakta kalan azot değildir; kaynakta
belgelenmiş dış girdidir. Gübre ürün kütlesi, tohum miktarı ve STIR bu miktara
eklenmez. Belirsiz gübre birimleri ayrı sayılır. P/K miktarları bu sürümde
etiket yüzdelerinden türetilmez; bilinmiyorsa boş bırakılır.

Hasattaki `0 % residual removed`, 0 kg ürün verimi anlamına gelmez. Hasat
verimi bu satırlardan çıkarılmaz. Aynı gün hasat ve yeni ekim varsa o sınırdaki
gübre olayları zaman belirsizliğiyle ayrılır; iki sezonda birden sayılmaz.

## Hava özellikleri

- Ortalama sıcaklık ve yağış toplamı.
- 0 °C üzerindeki günlük ortalama sıcaklıkların toplamı.
- Minimum sıcaklığı 0 °C'nin altında olan gün sayısı.
- Maksimum sıcaklığı 35 °C'nin üzerinde olan gün sayısı.

Bunlar tanımlı çevresel indekslerdir; belirli bir çeşidin gelişme veya hasar
modeli değildir. Gerekli gün/parametre eksikse ilgili toplam boş bırakılır.
Yöntem, sıcaklık ortalamasıyla hesaplanan kapaksız bir indekstir; başka GDD
yöntemleriyle aynı değer olacağı varsayılmaz.

## Çıktılar

| Dosya | İçerik |
|---|---|
| SEASON_REPORT.md | Takvim, ölçüm bağlantısı ve sınırlamalar |
| observed_seasons.csv | Tam sezonlar, hava ve yönetim özetleri |
| management_events.csv | Kaynak olayları ve izlenebilir olay kimlikleri |
| amendment_audit.csv | Açık N miktarları ve çözülemeyen birimler |
| sampling_links.csv | Uygulama düzeyinde örnekleme/sezon bağlantısı |
| features_at_sampling.csv | Örneklemeden önceki girdiler ve ayrı hedef sütunları |
| unlinked_soil.csv | Tarihi/bağlantısı eksik toprak gözlemleri |
| target_dictionary.csv | Analiz yöntemi ve birim sözlüğü |
| readiness.json | Model hazırlığı ve eksik koşullar |
| training_contract.json | Aday girdi/hedef ayrımı ve gruplama sözleşmesi |
| aligned_data.sqlite3 | Aynı tabloların SQLite kaydı |
| manifest.json | Sürüm, konfigürasyon ve hava kaynağı özetleri |

## Doğrulanmış kapsam ve model sınırı

İki pilotta uygulama bazında **26 sezon** çıkarıldı. 36 toprak gözleminin
12'si tarihle bağlandı; 24'ü açık nedenle ayrı tutuldu. Bağlanan 12 gözlem,
**tek bir ortak hava dönemini** paylaşır. Bu, 12 bağımsız iklim deneyi değildir.

Bu tabloda aynı parselin önce/sonra ölçümü, hasat verimi ve N/P/K çıkışları
bulunmadığından dinamik toprak modeli henüz eğitilmez. Deney blokları ve
ölçümlerin bağımsızlığı da doğrulanmalıdır. Üretim amaçlı model kalibrasyonu
için tarihli, tekrarlı saha verisi gerekir. Bu aşama, o kalibrasyon için
gerekli zaman bakımından doğru tabloyu ve açık eksiklik kaydını kurar.

Kaynaklar:

- Soil Health Institute (2024), NAPESHM v1: https://doi.org/10.15482/USDA.ADC/25632270
- NASA POWER geçmiş API: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
- Isıl indeks bağlamı: https://power.larc.nasa.gov/docs/methodology/data/derived/met-derived-parameters/
