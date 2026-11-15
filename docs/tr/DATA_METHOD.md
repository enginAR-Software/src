# Veri ön işleme ve hesaplama yöntemi

## Kapsam ve kaynakların ayrılması

İki bağımsız veri kaynağı işlenir. P-FLUX'taki bir sistem NAPESHM'deki bir
deney alanıyla kendiliğinden eşleştirilmez. Bu sürümde mekânsal raster,
SSURGO/CDL veya iklim verisi indirilmez. Amaç, ilk gerçek veri hattını denetlenebilir
kılmak ve mevcut fosfor hesabını yeniden üretmektir.

Sürüm 1 dosyaları katalogda dosya kimliği, boyutu ve kaynağın computed_md5
değeriyle sabitlenmiştir. Her koşuda yerel dosya boyutu ve MD5 kontrol edilir,
ayrıca SHA-256 rapora yazılır. API metadata kimliği/sürümü de denetlenir.
MD5 burada kaynakta bildirilen dosyayla eşitlik kontrolüdür; tek başına bir
kimlik doğrulama mekanizması olarak sunulmaz. İndirmede HTTPS kullanılır.

## Ortak işlemler

1. CSV önce UTF-8/BOM, gerekirse Windows-1252 olarak okunur; seçilen kodlama kaydedilir.
2. Başlıkların benzersizliği ve satır genişliği kontrol edilir.
3. Hücrelerin baş/son boşlukları temizlenir; ham dosya değiştirilmez.
4. Boş, NA, N/A, NaN ve NULL değerleri temiz çıktıda null/boş olarak tutulur.
5. Sıfır gerçek bir sayıdır; eksikle karıştırılmaz. Diğer metinler korunur.
6. Kaynak kimlikleri metin kalır; baştaki sıfırlar kaybolmaz.
7. Her sütunun eksik, farklı ve sayıya çevrilebilir değer sayısı hesaplanır.
8. CSV'ler UTF-8, virgül ayırıcı ve noktalı ondalıkla yazılır.

Profilde bir sütunun sayıya çevrilebilmesi, o sütunun ölçüm olduğu anlamına
gelmez. Kimliklerdeki ortalama/min/max anlamlı agronomik göstergeler değildir.
Kaynak sözlüğü ve sütunun görevi ayrıca değerlendirilmelidir. Sayısal olmayan
ölçüm metinleri yerine otomatik sayı veya ortalama konmaz.

NAPESHM arşivindeki CSV'ler bellekte okunur; keyfi dosya yolları diske açılmaz.
Güvensiz yollar, sembolik bağlantılar ve 128 MiB'den büyük açılmış arşivler
reddedilir. Arşivdeki orijinal XLSX sözlüğü, DOCX açıklaması ve SQLite dosyası
ham ZIP içinde korunur; bu sürüm CSV sözlüklerini kullanır.

## P-FLUX

### Kayıt düzeyi

`PBudgetData.csv` 224 kayıt içerir:

- 163 satır: rotasyon içindeki ürün konumu (`1`, `2`, `1 (no rotation)` vb.).
- 61 satır: bütün üretim sisteminin ortalaması (`System 1-3` vb.).

Bunlar ayrı `record_type` etiketleriyle saklanır. `Rotation year` takvim yılı
olarak yorumlanmaz. Sistem ortalamaları yıllık satırlarla toplanıp çift sayılmaz.
`contains_wheat_text`, adlarda wheat sözcüğünü arayan açıklanabilir metin filtresidir.

### Kaynak eşleme

Kaynak tablosunun anahtarı `Location + Cropping system ID + Rotation year`dır.
163 rotasyon konumu doğrudan kaynak satırıyla eşleşir. 61 sistem özeti için
ilgili sistemin konum bazlı kaynakları bağlam olarak saklanır; doğrudan eşleşme
olarak işaretlenmez. Anahtarsız 11 dipnot veri satırı sayılmaz, temiz kaynak
tablosunda korunur. Kısmen eksik veya tekrar eden gerçek anahtarda işlem durur.

`provenance_match`: `exact`, `system_context` veya `missing`.
`provenance_json` ölçümün Measured, Literature veya Estimated olarak kayıtlı
olmasını ve orijinal referanslarını taşır. Bütün bileşenlerin doğrudan ölçüm
olduğu varsayılmaz.

### Bütçe hesabı

```text
Agronomik P bütçesi = P uygulaması + atmosferik P + sulama P − hasat P
Genel tarla P bütçesi = agronomik bütçe − hidrolojik P çıkışı
```

Rotasyon konumunda hidrolojik çıkış yüzey + yüzey altı bileşenlerinin toplamıdır.
Sistem özetinde kaynağın system average hydrologic P loads alanı kullanılır.
Gerekli herhangi bir bileşen yoksa ilgili hesap null kalır. Hidrolojik ölçümün
P formu aynen taşınır; farklı formlar aynı toplam P ölçümü gibi karşılaştırılmaz.

Sistem özetleri kaynakta yayımlanan bütçelerle karşılaştırılır. ±0,03 kg P/ha/yıl
eşiği, yuvarlatılmış kaynak değerleriyle yeniden hesaplama için seçilmiştir.
Bu, tarımsal modelin hata payı veya güven aralığı değildir. Standart sapmalar
kaynak tablosunda korunur; kovaryans bilgisi olmadan bütçe belirsizliğine
otomatik dönüştürülmez.

Bir örnek (`AAFC-Sys1`): 6,17 + 0,55 + 0 − 3,33 = 3,39 kg P/ha/yıl.
Yayımlanan değer 3,38'dir; fark 0,01'dir ve belirlenen tolerans içindedir.

Kaynakta `LMRB-Sys2` sulama girdisi `Not measured`dır. Bu değer bir sayı gibi
okunmaz; `nonnumeric_flux_columns` içinde gösterilir ve gereken bütçe boş kalır.

Pozitif bütçe birikim, negatif bütçe net çıkış yönünü gösterir. Tek başına
"en verimli toprak" veya "en iyi rotasyon" sonucunu vermez. Bitkiye yarayışlı
P ve başlangıç stoku bilinmeden kaç yıl yeterli kalacağı hesaplanmaz.

## NAPESHM

### Tablolar ve ilişkiler

- `sites`: 94 araştırma alanı.
- `treatments`: 508 yönetim uygulaması.
- `soildata`: 1.453 deney biriminin toprak gözlemleri.
- `mgmtdata`: 12.643 olay/index kaydı, ayrı tutulur.
- `dbcolumns`, `dbtables`: veri sözlükleri.
- `rr_lookup`: kaynakta tanımlı karşılaştırma çiftleri, korunur.
- `plfa_ng`, `plfa_nm`: biyolojik ölçüm tabloları, korunur/profillenir.

Toprak tablosuna `siteid` ve `treatmentid` üzerinden tekil bağlam eklenir.
Alan/uygulama kimlikleri ve sitecode tutarlılığı kontrol edilir. Yönetim olayları
toprak satırlarına doğrudan bağlanmaz; aksi halde tek gözlem çok kez sayılabilir.
İlk kaynakta 986 `reserved index row` vardır; bunlar gerçek tarla işlemi
gibi sayılmadan ayrıca raporlanır.

### Seçilen göstergeler

| Kaynak sütunu | Ölçüm | Kaynaktaki birim |
|---|---|---|
| b_soc | Organik karbon | % |
| b_total_n | Toplam azot, kuru yakma | % |
| b_ph | 1:2 su pH'ı | unitless |
| b_p_m3 | Mehlich-3 fosfor | mg/kg |
| b_p_olsen | Olsen fosfor | mg/kg |
| b_k_m3 | Mehlich-3 potasyum | mg/kg |
| b_k_amac | Amonyum asetat potasyum | mg/kg |
| b_pmn_am_mgkg | Potansiyel mineralize N, inkübasyon | mg/kg |
| d_h3a_no3 | H3A nitrat-N | mg N/kg |

Ad, birim ve yöntem kaynak CSV sözlüğünden alınır. Özellikle Olsen ve
Mehlich-3 sonuçları aynı sütunda birleştirilmez. Potansiyel mineralize N,
gerçek tarlanın bir sezonda serbest bırakacağı N miktarı sayılmaz.

`soil_indicators.csv` uzun biçimde 1.453 × 9 = 13.077 kayıt üretir; eksik
göstergeler de `value_status` ile görünür kalır. `treatment_summary.csv`, aynı
alan/uygulama/gösterge içindeki mevcut değerlerin sayısını, ortalamasını ve
aralığını verir. Bu istatistikler zaman eğilimi, nedensel etki veya gelecekteki
stok tahmini değildir. PLFA tabloları ve karşılaştırma çiftleri sonraki analiz
için korunur; bu sürümde otomatik etki hesabına alınmaz.

`site_wheat` bayrağı 40 alan için 1'dir. Bu alanlarda toplam 753 toprak gözlemi
vardır; bunların hepsine buğday parseli denmez. `crop_phase` metninde wheat
geçen 277 gözlem ayrıca işaretlenir; faz açıklaması önceki/sonraki üründen
bahsedebileceği için bu da kesin ürün sınıfı değildir.

## Depolama ve başarısız koşular

Her koşu benzersiz bir `outputs/<kimlik>` klasörü açar. Tamamlanmış sonuçta
`manifest.json` içindeki `status` değeri `completed` olur. İşlem ortasında hata
olursa klasör teşhis için bırakılır ve durum `failed` olarak kaydedilir.
Ham dosya kontrolü başarısızsa sonuç klasörü açılmaz.

SQLite kaynak sütunlarını TEXT olarak saklar; türetilmiş sayısal göstergeler
ve bütçeler REAL, bayraklar INTEGER olur. Her koşu ayrı veritabanı üretir.
Bu sürümde eşzamanlı aynı klasöre fetch çalıştırılmamalıdır.
