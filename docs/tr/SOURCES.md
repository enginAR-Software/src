# Veri kaynakları ve atıf

Kaynak API ve dosyalar 15 Kasım 2026'da kontrol edildi. Orijinal sayısal dosyalar
pakette değiştirilmeden korunur. Türetilmiş tablolar ve özetler FieldShift Data
tarafından üretilir; veri sağlayıcılarının onayını ifade etmez.

## P-FLUX

Williams, Mark R.; Welikhe, Pauline; Bos, Janae H.; King, Kevin W. ve diğerleri
(2021). **LTAR Phosphorus Budget Summary.** Ag Data Commons.

- DOI: https://doi.org/10.15482/USDA.ADC/1523365
- Veri sayfası: https://agdatacommons.nal.usda.gov/articles/dataset/LTAR_Phosphorus_Budget_Summary/24855381
- Sabitlenmiş API: https://api.figshare.com/v2/articles/24855381/versions/1
- Kaynak metadata lisansı: U.S. Public Domain.
- Veri sayfasının kullanım açıklaması LTAR Data Sharing Principles and Guidelines'a da atıf yapar: https://ltar.ars.usda.gov/wp-content/uploads/2020/05/LTAR_DataSharing_PrincGuide_v1_0.pdf
- Sayısal dosya: `PBudgetData.csv`.
- Referans dosyası: `DataSourcesAndReferences.csv`.

İlgili çalışma: Williams ve diğerleri (2022). P-FLUX: A phosphorus budget
dataset spanning diverse agricultural production systems in the United States
and Canada. https://doi.org/10.1002/jeq2.20351

## NAPESHM

Soil Health Institute (2024). **North American Project to Evaluate Soil Health
Measurements Dataset.** Ag Data Commons.

- DOI: https://doi.org/10.15482/USDA.ADC/25632270
- Veri sayfası: https://agdatacommons.nal.usda.gov/articles/dataset/North_American_Project_to_Evaluate_Soil_Health_Measurements_Dataset/25632270
- Sabitlenmiş API: https://api.figshare.com/v2/articles/25632270/versions/1
- Lisans: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/
- Kaynak: Soil Health Institute tarafından derlenen kamuya açık sürüm.
- Özgün arşiv: `NAPESHM_public_dataset_06032024.zip`.

CC BY atfı için veri setinin adı, Soil Health Institute, DOI, lisans ve yapılan
dönüşümler birlikte korunmuştur. Ham dosyalar değiştirilmedi; temiz CSV'ler,
ilişkili tablolar ve istatistikler türetilmiştir. Dönüşümler DATA_METHOD.md ve
her koşunun manifest.json dosyasında açıklanır. Veri setinin fon sağlayıcıları
ve tam metadata bilgisi `data/raw/napeshm/v1/metadata.json` içinde korunur.

## Yazılım/API belgeleri

0.3.0 sürümünde NASA POWER geçmiş ve projeksiyon yanıtları da ham dosyalarıyla
kaydedilir. Geçmiş serviste MERRA-2 tabanlı değişkenler; projeksiyonda kaynak
başlığında NEXGDDP olarak belirtilen iklim senaryoları kullanılır. API sürümü,
model, SSP, tarih aralığı, istek koordinatı ve yanıt özeti her sorguda saklanır.
Bu bilgiler, Ag Data Commons veri setlerinin sürüm sabitlemesinden ayrıdır.

- Geçmiş: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
- Projeksiyon: https://power.larc.nasa.gov/docs/services/api/projection/

NASA verileri için kaynak atfı ve kullanım bilgisi: https://power.larc.nasa.gov/
Projeksiyon senaryoları gerçekleşmiş ölçümler gibi yeniden etiketlenmez.

- Figshare API: https://docs.figshare.com/v2/
- Python CSV: https://docs.python.org/3/library/csv.html
- Python SQLite: https://docs.python.org/3/library/sqlite3.html

Veri dosyaları kendi yukarıdaki lisanslarına tabidir. Paket içindeki kaynak
kod için MIT lisansı `LICENSE` dosyasındadır.
