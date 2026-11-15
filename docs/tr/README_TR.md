# FieldShift Data

**Sürüm 0.9.0.** Göç koridorundaki parseller plana girdi; iklimden verim modeli, Oregon buğday-sonrası-buğday etkisi,
fiyat senaryoları ve MODIS NDVI uydu göstergesi eklendi. Çalıştırma sırası ve ayrıntı: `docs/GENISLETMELER_0_9.md`.

```bash
python3 -m fieldshift_data corridor --offline                 # koridor nokta dizilerini yeniden üret (indirme yok)
export FIELDSHIFT_NASS_KEY=anahtariniz                          # ücretsiz: https://quickstats.nass.usda.gov/api
python3 -m fieldshift_data economics --online                 # eyalet verim/fiyatları
python3 -m fieldshift_data yield-model --online               # ilçe verimi ~ iklim modeli, 2040'lar çarpanları
python3 -m fieldshift_data goal --offline
python3 -m fieldshift_data satellite --online                 # MODIS NDVI (anahtar gerekmez)
python3 -m fieldshift_data app --open
```

**Önceki: 0.8.0.** Etkileşimli arayüz eklendi: harita, parsel planı, tarih sorgusu ve çiftçi öncelikleri.

## Arayüz

```bash
python3 -m fieldshift_data app --open
```

Tek dosyalık, internetsiz bir sayfa açılır (`outputs/app_*/FieldShift_App.html`). Ayrıntı: `docs/ARAYUZ.md`.

**Önceki: 0.7.1.** Ekonomi girdileri resmî kaynaklarla dolu; `DASHBOARD.html` amaç panosu eklendi. Önceki: **0.7.0.** Yazılım proje amacına (Preparation.md) bağlandı: buğdayın iklim değişikliğiyle
göç edeceği bölge, parseller, parsel başına ekonomik açıdan en verimli rotasyon, eğitilmiş model
ve çiftçiye her yıl ne zaman, hangi ürünü ekeceği.
Projenin genel açıklaması ve mevcut durum kaydı: `FieldShift_Proje_Aciklamasi.md`. Yöntem: `docs/GOAL.md`.

## Proje amacı tek komutta

```bash
python3 -m fieldshift_data --version
python3 -m fieldshift_data goal --offline
python3 -m fieldshift_data goal --offline --date 2027-10-15
```

Komutun sonunda gösterilen `DASHBOARD.html` dosyasını tarayıcıda açın.
`GOAL_REPORT.md` amacın beş bileşeninin durumunu verir:

| Bileşen | Komut | Paketle çevrimdışı durum |
|---|---|---|
| A. Buğdayın göç edeceği en uygun bölge | `corridor` | Koridor ızgarası `corridor --online` ile indirilince hesaplanır |
| B. Parsellere ayırma | `goal` | 30 pilot parsel |
| C. Parsel başına en kârlı rotasyon | `goal`, `economics` | Çalışıyor: KFMA, NASS, OSU ve USDA AMS kaynaklı girdilerle (bkz. docs/NASS_ANAHTARI.md) |
| D. Eğitilmiş model | `corridor` | Mekânsal blok doğrulamalı lojistik model; iki pilot alan eğitime yetmez |
| E. Her yıl ne zaman ve ne ekilir | `goal --date` | Çalışıyor: NASA projeksiyonundan, kaynaklı eşiklerle |

Eksik kısımları tamamlamak için:

```bash
python3 -m fieldshift_data corridor --online            # A + D: NASA ve USDA koridor verisi
export FIELDSHIFT_NASS_KEY=ANAHTARINIZ                   # ücretsiz: https://quickstats.nass.usda.gov/api
python3 -m fieldshift_data economics --online           # C: NASS verim ve fiyatları
# maliyetleri kaynağıyla config/economics_inputs.csv dosyasına yazın
python3 -m fieldshift_data goal --offline
```

NASS dışındaki bütün kaynaklar API anahtarı istemez. Ayrıntı: `docs/GOAL.md`.

## Gerçek ürün dağılımı ve ürün dizileri

```bash
python3 -m fieldshift_data --version
python3 -m fieldshift_data cropland --offline
```

USDA CDL kaynağından 2018–2023 boyunca 50 sabit noktanın 300 yıllık
ürün sınıfını işler; gözlenen dizileri ve ardışık yıl geçişlerini çıkarır.
Veriler pakettedir. Yeni sorgu için `--online`, sıfırdan gerçek indirme
kontrolü için `self-test --online` kullanın. Yönerge: `docs/CROPLAND.md`.
Sonuç `CROPLAND_REPORT.md`, `crop_samples.geojson`, ürün dizileri ve ayrı
iklim/toprak bağlam tablolarını içerir. Gözlenen dizi, en iyi rotasyon değildir.

## Bölgesel değişimi hesaplama

```bash
python3 -m fieldshift_data regional --offline
```

2015–2024 ile 2040–2049 dönemlerini SSP2-4.5 altında aynı modelle
karşılaştırır. Gerçek NASA yanıtları pakettedir. Yeni sorgular için
`--online` kullanın. Sonuç: `REGIONAL_REPORT.md`, `monthly_changes.csv`,
`annual.csv`, `regional.json` ve `regional_change.geojson`.
Ayrıntılı yöntem, eksik veri kuralları ve Linux Mint komutları:
`docs/REGIONAL_CHANGE.md`. Bu çıktı ürün uygunluk puanı değildir.

## Aynı alan ve sezonu birleştirme

Yeni `FieldShiftData_0_8_0` klasöründe:

```bash
python3 -m fieldshift_data --version
python3 -m fieldshift_data seasons --offline
```

Sürüm 0.9.1 olmalı. Kaynak sezonlarına ait gerçek hava dosyaları pakettedir;
bu denemede yeniden indirme gerekmez. Yeni veri gerekiyorsa `--online`
kullanın. `SEASON_REPORT.md`, `features_at_sampling.csv` ve `readiness.json`
oluşur. 26 sezonun 12 toprak gözlemiyle tarihli bağlantısı kurulur; tarihi
eksik 24 gözlem ayrı tutulur. Ayrıntı: `docs/SEASON_ALIGNMENT.md`.

## Planlama ve canlı veri testi

Yeni ZIP'i boş bir klasöre açıp proje klasöründe:

```bash
python3 -m fieldshift_data --version
python3 -m fieldshift_data self-test --online
python3 -m fieldshift_data plan --date 2028-05-15
python3 -m fieldshift_data climate --site USOR03 --kind projection --start 2027-01-01 --end 2027-12-31 --scenario ssp245 --online
```

`self-test --online` dosyaları boş geçici dizine gerçekten indirir. `plan`,
kaynakta gözlenmiş döngülerden kullanıcı sınırlarına uygun çok yıllı referans
senaryosu seçer. `climate`, geçmiş veri veya gelecek projeksiyonu getirir.
Planlayıcının P hedefi bütün toprak sağlığını veya verimi tahmin etmez; iklim
tepkisi bütçeye henüz bağlanmadı. Ayrıntılar: `docs/PLANNING_AND_LIVE_TESTS.md`.

Gerçek tarım ve toprak verilerini kendi bilgisayarınızda indirmeniz, incelemeniz,
ön işlemeniz ve kayıtlı fosfor bütçelerini yeniden hesaplamanız için Python araçları.

**Python 3.10+ yeterlidir. Üçüncü taraf kütüphane, pip veya web sunucusu gerekmez.
API anahtarı yalnız isteğe bağlı NASS ekonomik verisi için gerekir.** Hazır pakette doğrulanmış gerçek kaynak dosyaları vardır;
ilk veri analizi ve planlama denemesini internet olmadan yapabilirsiniz.

## Linux Mint'te hızlı başlangıç

ZIP'in bulunduğu klasörde terminal açın. Python veya unzip yoksa bir kez:

```bash
sudo apt update
sudo apt install python3 unzip
```

Ardından:

```bash
unzip FieldShiftData_0_8_0.zip
cd FieldShiftData_0_8_0
python3 --version
python3 -m fieldshift_data verify
python3 -m fieldshift_data run --offline
```

Oregon ve Kansas pilotlarını karşılaştırmak için aynı klasörde:

```bash
python3 -m fieldshift_data analyze --offline
```

Bu komut veri hattını da çalıştırır; ayrıca `PILOT_REPORT.md` ve tekil gözlem,
dağılım özeti ve uygulama farkı tabloları üretir. Ayrıntı: `docs/PILOT_ANALYSIS.md`.

Kısa yol: `bash run_data.sh`. Her koşu yeni bir çıktı klasörü oluşturur;
önceki sonuçların üzerine yazmaz. İşlemler proje klasöründeki verilere uygulanır.
Komutlarda `CALISTIRMA_KIMLIGI` gibi yer tutucuların yerine terminalde gösterilen
gerçek klasör adını kullanın.

## Neler üretir?

| Dosya / klasör | İçerik |
|---|---|
| `outputs/<kimlik>/REPORT.md` | Türkçe sonuç ve yorumlama raporu |
| `profiles.csv`, `profiles.json` | Her kaynak sütununun eksik oranı, farklı değerleri ve sayısal özeti |
| `metrics.json` | Alan, gözlem, sistem ve bütçe kontrol sayıları |
| `manifest.json` | Veri sürümü, DOI, lisans, dosya özeti ve işlem durumu |
| `processed/pflux/` | Kaynak tabloları, ayrılmış bütçeler ve yayımlanmış sonuçla karşılaştırma |
| `processed/napeshm/` | Kaynak tabloları, bağlam eklenmiş toprak gözlemleri ve gösterge özetleri |
| `fieldshift_data.sqlite3` | Aynı tabloların yerel SQLite veritabanı |
| `PILOT_REPORT.md` | `analyze` komutuyla Oregon/Kansas pilot karşılaştırması |
| `processed/analysis/` | `analyze` komutunun tekil gözlemleri, özetleri ve farkları |

`REPORT.md` dosyasını Linux Mint'in metin düzenleyicisiyle; CSV dosyalarını
LibreOffice Calc ile açabilirsiniz. Sayısal CSV çıktılarında ondalık ayırıcı nokta,
sütun ayırıcı virgüldür. CSV içe aktarımında UTF-8 ve virgül seçin. Kimlik
sütunları metin olarak alınmalı; baştaki sıfırlar korunmalıdır.

## Komutlar

```bash
# Kaynaklar, dosya kimlikleri ve sabitlenmiş sürümler:
python3 -m fieldshift_data catalog

# Yerel ham dosyaların MD5 ve boyut kontrolü:
python3 -m fieldshift_data verify

# Yalnız fosfor veri seti:
python3 -m fieldshift_data run --dataset pflux --offline

# Yalnız toprak veri seti:
python3 -m fieldshift_data run --dataset napeshm --offline

# İnternetten sabitlenmiş sürümün eksik dosyalarını indir / mevcutları doğrula:
python3 -m fieldshift_data fetch --dataset all

# Hesaplanmış bir sistemin veritabanı sorgusu:
python3 -m fieldshift_data query outputs/CALISTIRMA_KIMLIGI/fieldshift_data.sqlite3 --system AAFC-Sys1

# Testler:
python3 -m unittest discover -s tests -v
```

Verileri başka bir klasörde tutmak için `--workspace` komuttan önce yazılır:

```bash
python3 -m fieldshift_data --workspace /home/KULLANICI/FieldShiftVeri fetch
python3 -m fieldshift_data --workspace /home/KULLANICI/FieldShiftVeri run --offline
```

`fetch` yeni yayımlanmış sürüme kendiliğinden geçmez. İki veri kaynağında da
sürüm 1 sabitlenmiştir. Geçerli mevcut dosyaları yeniden indirmez. Beklenmeyen
dosya değişikliğinde çalışmayı durdurur; eski dosyayı sessizce değiştirmez.

## Gerçek veriyle beklenen sonuçlar

| Ölçüt | Beklenen |
|---|---:|
| P-FLUX üretim sistemi | 61 |
| P-FLUX toplam veri kaydı | 224 |
| Rotasyon konumu kaydı | 163 |
| Sistem özeti | 61 |
| Buğday sözcüğü geçen P-FLUX sistemi | 23 |
| Yeniden hesaplanan agronomik bütçe | 59 uyumlu, 2 eksik |
| Yeniden hesaplanan genel tarla bütçesi | 45 uyumlu, 16 eksik |
| NAPESHM araştırma alanı | 94 |
| NAPESHM uygulaması | 508 |
| Toprak gözlemi / deney birimi | 1.453 |
| Buğday bulunan alan bayrağı | 40 alan |

"Uyumlu", yayımlanmış sistem bütçesine göre ±0,03 kg P/ha/yıl karşılaştırma
toleransı içindedir. Bu bir toprak modeli doğruluk puanı değildir.

P-FLUX'ta `LMRB-Sys2` sisteminin sulama P girdisi `Not measured` olarak
belirtilmiştir. Sayı uydurulmaz; ilgili bütçe eksik kalır. Kaynak dipnotları
ve yönetim tablosundaki `reserved index row` kayıtları korunur ve raporlanır.

## Sonuçların kapsamı

Bu araç mevcut gerçek gözlemleri işler ve kayıtlı fosfor giriş-çıkışlarını
hesaplar. Yeni bir rotasyonun gelecekteki toprak verimini veya azot stokunu
tahmin etmez. Önceki FieldShift Soil sentetik demosuna gerçek stokları otomatik
aktarmaz. Gerçek N/P/K süreç modeline geçmeden önce ölçüm yöntemleri ve
kalibrasyon ayrıca değerlendirilmelidir.

Toplam N ile mineral N; Mehlich-3 P ile Olsen P ayrı tutulur. mg/kg ve yüzde
değerleri kg/ha stoklarına dönüştürülmez. Bir alanda buğday bulunması, o alandaki
bütün gözlemlerin buğday yetiştirilen parsellerden geldiğini göstermez.

## Proje düzeni

```text
FieldShiftData/
├── README.md
├── requirements.txt
├── run_data.sh
├── FieldShift_Proje_Aciklamasi.md
├── config/pilots.json    # Pilotlar ve A/B karşılaştırmaları
├── config/planning.json  # Çok yıllı referans planlama sınırları
├── config/season_alignment.json # Tarih, ürün ve çevresel indeks sözleşmesi
├── config/crop_calendar.json # E: kaynaklı ekim eşikleri
├── config/economics.json # C: kâr hesabı ve kısıtlar
├── config/economics_inputs.csv # C: kaynaklı verim/fiyat/maliyet (boş gelir)
├── config/corridor.json # A+D: göç koridoru ızgarası
├── fieldshift_data/
│   ├── catalog.py        # Sabit kaynaklar ve sürümler
│   ├── download.py       # İndirme ve bütünlük doğrulama
│   ├── tables.py         # CSV/ZIP okuma ve sütun profilleri
│   ├── pflux.py          # Fosfor hesabı ve kaynak eşleme
│   ├── napeshm.py        # Toprak tablolarını ilişkilendirme
│   ├── analysis.py       # Tekil gözlemlerden pilot istatistikleri
│   ├── planning.py       # Gerçek döngülerden çok yıllı senaryo
│   ├── climate.py        # NASA geçmiş ve gelecek iklim verisi
│   ├── diagnostics.py    # Boş önbellekte canlı uçtan uca test
│   ├── seasons.py        # Kaynak sezonu, birim ve kesim tarihi kuralları
│   ├── goal.py           # Amaç bileşenleri A–E ve parsel × yıl çıktısı
│   ├── app.py, app_template.html, app_optimizer.js  # Etkileşimli arayüz
│   ├── dashboard.py      # Rapor panosu
│   ├── assets/           # d3 ve ABD eyalet sınırları (lisanslar içeride)
│   ├── planting.py       # E: ekim penceresi
│   ├── economics.py      # C: kâr, NASS, P kaldırması, rotasyon araması
│   ├── suitability.py    # A+D: uygunluk modeli ve göç koridoru
│   ├── alignment.py      # Yönetim–hava–toprak bağlantısı
│   ├── pipeline.py       # İş akışı ve rapor
│   ├── storage.py        # SQLite
│   └── __main__.py       # Terminal komutları
├── data/raw/             # Doğrulanmış gerçek kaynak dosyaları
├── docs/                 # Yöntem, kaynaklar ve test bilgileri
├── reference_output/     # Örnek rapor ve beklenen sayılar
└── tests/                # Birim ve gerçek veri entegrasyon testleri
```

## Test sonucunu paylaşma

Çalıştırdıktan sonra `REPORT.md`, `metrics.json` ve `manifest.json` dosyalarını
paylaşmanız incelemeye başlamak için yeterlidir. Hata olursa çalıştırdığınız
komutla birlikte terminaldeki `Hata:` satırını paylaşın. Büyük veritabanını
ilk aşamada göndermeniz gerekmez.

Kurulum ayrıntıları: `docs/LINUX_MINT.md`. İşleme yöntemleri:
`docs/DATA_METHOD.md`. Kaynak atıfları: `docs/SOURCES.md`.

## AI use / Yapay zekâ kullanımı

This software, its documentation and its charts were developed with the help of Claude (Anthropic), an AI assistant, and reviewed and run by the FieldShift team. All input values come from the cited public datasets (see `docs/` and `config/`); no data values were generated by AI.

Bu yazılım, belgeleri ve grafikleri Claude (Anthropic) yapay zekâ asistanının yardımıyla geliştirildi; FieldShift ekibi tarafından çalıştırıldı ve gözden geçirildi. Bütün girdi değerleri belirtilen kamuya açık veri setlerinden gelir; hiçbir veri değeri yapay zekâ tarafından üretilmemiştir.
