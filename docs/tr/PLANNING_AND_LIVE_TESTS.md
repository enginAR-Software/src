# 0.3.0 — gerçek veri testleri ve ilk planlama

## Komutlar

```bash
python3 -m fieldshift_data --version
python3 -m unittest discover -s tests -v
python3 -m fieldshift_data self-test --online
python3 -m fieldshift_data plan --date 2028-05-15
python3 -m fieldshift_data climate --site USOR03 --kind projection --start 2027-01-01 --end 2027-12-31 --scenario ssp245 --online
```

Sürüm **FieldShiftData 0.3.0** olmalıdır. Yeni ZIP'i önceki klasörün üstüne
açmak yerine boş bir klasöre çıkarın. Python standart kütüphanesi yeterlidir.

## Canlı testin kapsamı

`self-test --online`, her koşuda boş geçici klasör açar; hazır ham dosyaları
buraya kopyalamaz. Altı kontrol çalışır:

1. P-FLUX'un iki dosyasını indirme ve sürüm/boyut/MD5/SHA-256 doğrulaması.
2. NAPESHM arşivini indirme ve aynı bütünlük kontrolleri.
3. Yeni indirilen dosyalardan veri hattı ve 36 gözlemlik pilot analizi.
4. Gerçek kayıtlardan altı sezonluk referans planın hesaplanması.
5. NASA POWER geçmiş servisi: Oregon, 1–7 Ocak 2024.
6. NASA POWER projeksiyon servisi: Oregon, SSP2-4.5/ensemble, 1–7 Ocak 2027.

Her kontrol ve kanıtı `outputs/selftest_<kimlik>/SELF_TEST.json` içinde
saklanır. `SELF_TEST.md` kısa rapordur. Bir kontrol başarısız veya atlanmışsa
genel sonuç başarısızdır ve çıkış kodu 1 olur. Testin geçici verileri kaldırılır;
kaynak DOI, sürüm, SHA-256 ve API başlıkları raporda kalır.

`self-test` komutunun internetsiz biçimi yerel doğrulamadır; indirme kanıtı
değildir. Birim testleri ağ sınırında zaman aşımı, kesilmiş indirme, 404,
bozuk özet, aşırı boyut, önbellek tekrar kullanımı ve bozuk dosyanın korunmasını
kontrollü yanıtlarla sınar. Bu kontrollü yanıtlar gerçek gözlem yerine kullanılmaz.

`fetch`, geçerli mevcut dosyaları tekrar indirmez. `acquisition.json` kaydında
indirilen ve önbellekten kullanılan dosyalar ayrılır. Bozuk mevcut dosyanın
üzerine yazılmaz. Başarısız `.part` dosyaları temizlenir; metadata tüm kaynak
dosyaları doğrulandıktan sonra tamamlanır. Metadata ve kayıt yazımları atomiktir.

## Planlama sözleşmesi

`plan`, kaynaktaki tam ürün döngülerini korur ve başlangıç fazlarını değerlendirir.
Kaynakta gözlenmeyen bir sıranın etki katsayılarını tahmin etmez. `Location`
etiketi yalnız kaynak grubudur; aynı tarla veya iklim anlamına gelmez.

`config/planning.json` şu seçimleri içerir: kaynak grubu; başlangıç yılı ve
sezon sayısı; izin verilen açık ürün adları; minimum buğday sezonu ve ürün
etiketi çeşitliliği; kaynak ortalama P uygulaması sınırı; birikimli P değişimi
sınırı; bütçe türü; tam döngü şartı ve biliniyorsa önceki ürün.

`field_tp` bütçesi, eksiksiz bütçenin yanında toplam P (TP) kaybı ölçümünü de
gerektirir. Yalnız çözünmüş P (DRP) bulunan sistemler TP bütçesi sayılmaz.
`agronomic` seçeneği kayıtlı uygulama, atmosferik çökelme, sulama ve hasat
çıkışını kullanır. Eksik bileşenler sıfır kabul edilmez.

Hedef, sezon sonlarındaki **birikimli net P değişiminin sıfırdan mutlak
sapmalarının toplamını azaltmak**tır. Eşitlikte kaynak ortalama P girdisi daha
düşük olan seçilir. Sıfır başlangıcı bir muhasebe referansıdır; toprağın P
stoğu değildir. Sınırlar kullanıcı senaryosu olup agronomik yeterlilik veya
gübre dozu önerisi değildir. Toprak sağlığının tümü bu hedefle temsil edilmez.

Varsayılan 2027–2032 senaryosunda beş geçerli başlangıç fazı vardır. Sonuç:
buğday → kanola → soya → buğday → kanola → soya. Kaynak akıları değişmeden
tekrarlandığında net değişim +19 kg P/ha'dır; gelecekteki toprak konsantrasyonu
veya hasat verimi değildir. `recommendation_readiness=reference_only` kalır.

Çıktılar: `PLAN_REPORT.md`, `plan.json`, `schedule.csv`, `candidates.csv` ve
`excluded.csv`. Eleme nedenleri saklanır. Çözüm yoksa `no_feasible_plan` olur.

```bash
python3 -m fieldshift_data plan-view outputs/plan_KIMLIK/plan.json --date 2029-05-15
```

Tarih filtresi yalnız plan yılına uygulanır. Ay/gün ekim takvimi ve kışlık
ürünün iki takvim yılına yayılan sezonu henüz çözülmez. Ürün etiketlerinin
çeşitliliği botanik aile sayısı olarak yorumlanmaz.

## İklim verisi

NAPESHM alan koordinatları kullanılır. Farklı P-FLUX alanları bu noktaların
aynısı kabul edilmez. İstekler iki ayrı servise gider:

- `historical`: NASA POWER günlük geçmiş hava/yeniden analiz verisi.
- `projection`: NEX-GDDP-CMIP6 tabanlı gelecek iklim senaryosu.

Projeksiyonda `ssp126`, `ssp245`, `ssp370` seçilebilir; bu sürüm ensemble
modelini kullanır. Tür, senaryo, model, UTC standardı, birimler ve dönem
denetlenir. Ortalama/minimum/maksimum sıcaklık ve günlük yağış istenir.
Sorgu aralığı yaklaşık beş yılla sınırlıdır. Ham yanıt, API başlığı ve SHA-256
birlikte saklanır. Yeni sorgu için `--online` gerekir; mevcut istek önbellekten
doğrulanarak okunabilir.

```bash
python3 -m fieldshift_data climate --site USOR03 --kind historical --start 2024-01-01 --end 2024-12-31 --online
python3 -m fieldshift_data climate --site USKS01 --kind projection --start 2027-01-01 --end 2027-12-31 --scenario ssp245 --online
```

Çıktılar: `daily.csv`, `monthly.csv`, `climate.json`, `site_climate.geojson`
ve `CLIMATE_REPORT.md`. GeoJSON nokta katmanıdır; tarla sınırı veya buğday
uygunluk haritası değildir. Projeksiyon, gerçekleşecek hava tahmini değildir.

Canlı denemede iki pilotun 2027 SSP2-4.5/ensemble yanıtında 365 günün 360'ı
vardı. Eksikler sıfır yapılmadı ve dönem yağış toplamı boş bırakıldı. Sıcaklık
ortalaması yalnız mevcut günlere aittir; eksiklik bayrağıyla verilir. Oregon
2024 geçmiş sorgusunda 366 gün tamdı. Kısmi ay/yıl sorguları tam dönem gibi
yorumlanmaz. Eksik günler ve parametre sayıları JSON'da kaydedilir.

## Asıl hedefe geçiş

Planlama ve iklim verisi edinimi çalışıyor; iklim tepkisi henüz P bütçesine
bağlanmadı. Aynı parselde tarihli gübre/hasat ve verim kayıtları, tekrarlı
toprak ölçümleri, N/K akıları, çeşit ve sezon takvimi gereklidir. Bu verilerle
süreç kalibrasyonu ve bağımsız yıl doğrulaması yapılmadan genel toprak verimi,
geri kazanılan mineral miktarı veya iklim nedeniyle üretim alanı kayması
hesaplandığı iddia edilmez. Bir sonraki hedef bu kalibrasyon ve bağlantıdır.

Kaynak belgeler:

- https://docs.figshare.com/v2/
- https://power.larc.nasa.gov/docs/services/api/temporal/daily/
- https://power.larc.nasa.gov/docs/services/api/projection/
- https://www.nrcs.usda.gov/getting-assistance/other-topics/nutrient-management
