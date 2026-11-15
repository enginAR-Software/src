# Pilot analizi — 0.2.0

```bash
python3 -m fieldshift_data analyze --offline
```

Komut normal veri hattını çalıştırır ve aynı sonuç klasörüne `PILOT_REPORT.md`
ile `processed/analysis/` dosyalarını ekler. Önceden `run` çalıştırmak gerekmez.

Yalnız bir pilot için:

```bash
python3 -m fieldshift_data analyze --pilot oregon --offline
python3 -m fieldshift_data analyze --pilot kansas --offline
```

`config/pilots.json`, alanları, uygulama kimliklerini, beklenen ürün fazını
ve A/B karşılaştırmalarını tanımlar. Dosyanın SHA-256 değeri çalışma kaydına
eklenir. Denemek için kopyasını düzenleyip `--config config/deneme.json`
kullanabilirsiniz. Yeni kaynak veya alan eklerken uygulama açıklamalarını
kontrol edin; karşılaştırma etiketleri bu yapılandırmadan gelir.

## Dosyalar

| Dosya | İçerik |
|---|---|
| pilot_sites.csv | İki alanın kaynak bilgileri |
| pilot_treatments.csv | Seçilmiş dokuz uygulamanın kaynak açıklamaları |
| pilot_plots.csv | Tekil gözlem × gösterge; ham değer, sayısal değer, birim ve yöntem |
| pilot_summary.csv | Uygulama × gösterge; sayı, ortalama, medyan, min/max, örnek standart sapması |
| pilot_contrasts.csv | Aynı alanda ve aynı yöntemde B−A ortalama farkları |

Bu dosyalar SQLite içinde `analysis_` önekiyle de bulunur.

## Sabitlenmiş veride beklenen sayılar

- Oregon: 3 uygulama, 12 deney birimi, 3 karşılaştırma çifti.
- Kansas: 6 uygulama, 24 deney birimi, 9 karşılaştırma çifti.
- İki pilot: 324 gösterge kaydı, 81 özet ve 108 karşılaştırma satırı.
- 84 karşılaştırmada iki ortalama da var; 24 karşılaştırma ölçüm eksikliğiyle boş.

Eksik göstergelerin satırları korunur. Standart sapma için en az iki sayısal
gözlem gerekir. Farklar aynı alan, gösterge, birim ve yöntem içinde hesaplanır.
`%` biriminde fark **yüzde puan**, pH'da fark pH birimidir. Göreli yüzde artış
veya p değeri hesaplanmaz.

Kansas'taki 120 lb N/acre ifadesi kaynak uygulama etiketidir; gerçekleşmiş
yıllık uygulama takvimine çevrilmez. Aynı zamanda ölçüm fazı sorgumdur.
Oregon karşılaştırması aynı ürün sırasındaki toprak işlemeyi inceler; farklı
rotasyonların etkisini tek başına göstermez.

## Veri kapsamı iyileştirmeleri

Normal `run` komutuna da şu çıktılar eklendi:

- `processed/napeshm/wheat_site_coverage.csv`: 40 aday alanın 39'unda toprak
  kaydı olduğunu, USWA03'te bulunmadığını gösterir.
- `processed/pflux/wheat_system_comparison.csv`: alt ürün kayıtları dahil
  tanımlanan 23 sistemin tamamının özetini verir.
- `system_contains_wheat_text` ve `wheat_evidence`: üyeliği ve seçim nedenini
  açıklar. Önceki `contains_wheat_text` satır düzeyinde aynen korunur.
- `wheat_budgets.csv`: seçilen 23 sistemin tüm konum ve özet kayıtlarını kapsar.
  Buğday dışındaki rotasyon ürünleri de görünür; doğrudan buğday satırları
  gerektiğinde `crop` alanından ayrıca seçilmelidir.

Bu filtreler metin temellidir. Özellikle geniş ve karma sistem adlarında
ürün/alan kapsamı ayrıca incelenmeden bilimsel sınıflandırma sayılmamalıdır.

## Bilimsel sınır

Bağımsızlık, blok yapısı, örnekleme derinliği ve ölçüm zamanı doğrulanmadan
eşleştirilmiş test veya nedensel etki hesabı üretilmez. Bu sürümün sonucu
betimsel karşılaştırmadır; gelecekteki toprak verimi veya mineral stok tahmini değildir.
