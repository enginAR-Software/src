# Doğrulama kaydı

## Sürüm 0.4.0 — kaynak tarihleriyle sezon eşleştirmesi

15 Kasım 2026, Linux/Python 3.12.14: **55 test başarılı**. Boş geçici dizindeki
canlı test, önceki altı kontrolün yanında gerçek sezon–örnekleme eşleştirmesini
de çalıştırdı; **yedi kontrol geçti**. İki yeni geçmiş hava sorgusu gerçek
tarih aralıklarıyla indirildi: Kansas 2016-05-12–2018-10-31, Oregon
2018-03-25–2019-07-15.

Kaynak takviminden 26 uygulama-sezonu bulundu. 36 toprak gözleminin 12'si
tarihle bağlandı, 24'ü örnekleme tarihi eksikliğiyle ayrı tutuldu. Oregon
buğday sezonu 274 gündür; 15 Nisan 2019 örneklemesi için özellik penceresi
14 Nisan'da biter ve 182 gündür. Bu aralıktaki 12 gözlemde hava verisi tamdır.

Yeni kontroller; kışlık ürünün yıl aşması, STIR/ürün ayrımı, artık yüzdesinin
verim sayılmaması, açık N birimi dönüşümü, eksik gün, gelecekteki gübre/hava
verisinin özelliklere alınmaması, belirsiz örnekleme tarihi, aynı gün hasat/ekim
sınırında N'nin çift sayılmaması, hedef/girdi ayrımı ve Kansas'ta sıfır bağlı
gözlem olduğunda bile çıktı sözleşmesinin korunmasını kapsar.

Ortak hava grubu sayısı 1'dir; 12 bağımsız iklim örneği sayılmamıştır. Dinamik
model hazır bayrağı false kalır. Bu bir test başarısızlığı değildir; tek
kampanyalı veriyle dinamik toprak eğitimi yapılmasını önleyen kapsam kaydıdır.

Örnekler: `reference_output/seasons/` ve `reference_output/live_test_v040/`.

## Sürüm 0.3.0 — gerçek ağ testi ve planlama

15 Kasım 2026, Linux/Python 3.12.14: **43 test başarılı**. Ayrıca boş geçici
klasörde `self-test --online` çalıştırıldı; altı canlı kontrol geçti:

1. P-FLUX iki dosyanın gerçekten indirilmesi ve bütünlüğü.
2. NAPESHM arşivinin gerçekten indirilmesi ve bütünlüğü.
3. Yeni indirilen kaynaklardan veri hattı ve pilot analizinin çalışması.
4. Altı sezonluk referans planın gerçek kaynaklardan hesaplanması.
5. NASA POWER geçmiş servisi, Oregon 1–7 Ocak 2024.
6. NASA POWER projeksiyon servisi, Oregon SSP2-4.5/ensemble 1–7 Ocak 2027.

Canlı ağ testi mevcut paket önbelleğini kullanmadı. Ham indirme kanıtları,
özet değerleri ve API başlıkları `reference_output/live_test/SELF_TEST.json`
içindedir. Geçmiş ve projeksiyon kaynakları ayrı denetlendi.

Tam dönem ek sorgular: Oregon 2024'te 366/366 gün; Oregon ve Kansas 2027
projeksiyonlarında 360/365 gün. Eksik günler sıfır kabul edilmedi; yağış toplamı
boş bırakıldı. Dönem sıcaklık ortalaması yalnız mevcut günlere aittir.

Ek birim testleri metadata zaman aşımı, kesilmiş akış, HTTP 404, bozuk özet,
aşırı boyut, önbelleğin kullanılması, bozuk dosyanın korunması, iklim tür/model/
senaryo/birim ayrımı, eksik ve sıfır yağış, önbellek SHA-256 kontrolü, bağımsız
planlama optimumu, P muhasebesi, TP/DRP ayrımı, tam döngü ve tarih filtresini kapsar.

Varsayılan plan: beş geçerli seçenek, AAFC-Sys1 döngüsü, 2027–2032 için
buğday–kanola–soya iki tekrar; kaynak P akılarından birikimli +19 kg P/ha.
Bu değer toprak konsantrasyonu, ürün verimi veya saha gübre tavsiyesi değildir.

Linux Mint masaüstü doğrudan mevcut değil; standart Linux/Python terminal
akışı doğrulanmıştır. Tam N/P/K süreç modeli ve iklim-ürün tepkisi kalibrasyonu
bu sürümde doğrulanmış özellikler değildir.

## Sürüm 0.2.0 — pilot analizi

15 Kasım 2026, Linux/Python 3.12.14: 23 test başarılı. Önceki veri hattına
ek olarak şu kontroller çalıştırıldı:

- Üç sayılık bağımsız örnekte medyan ve n−1 örnek standart sapması.
- Eksik ve tek gözlemde boş istatistikler; eksiklerin sıfır sayılmaması.
- B−A yönü ve yüzde puan birimi.
- Farklı alan, yöntem veya birimin karşılaştırılmasının reddedilmesi.
- Oregon ve Kansas'ta toplam 36 tekil deney biriminin korunması.
- Dokuz göstergede 81 özet ve 108 karşılaştırma satırı.
- Kansas ölçüm fazının sorgum olarak korunması.
- Oregon CLI analizinde kaynak ortalaması ve bağımsız beklenen fark.
- Pilot yapılandırma özetinin çalışma kaydına eklenmesi.
- 23 buğday aday sisteminin tamamının özet çıktısına alınması.
- USWA03 alanındaki toprak veri yokluğunun açıkça raporlanması.

`run`, `verify`, `query` ve `fetch` komutlarının sözleşmeleri korunur.
Yeni `analyze` komutu veri hattını çalıştırıp pilot çıktıları ekler.
Gözlemlerden yeni bir nedensel etki veya gelecek tahmini türetilmez.

## Önceki sürüm 0.1.0 — veri hattı

Tarih: 15 Kasım 2026 (Türkiye). Ortam: Linux / Python 3.12.14.

| Kontrol | Kanıt | Sonuç |
|---|---|---|
| Resmî veri erişimi | Figshare API'den iki veri setinin sürüm 1 metadata ve 3 dosyası | Başarılı |
| Tam indirme akışı | Boş çalışma dizininde `fetch --dataset all` | Başarılı; 3 dosya boyutu/MD5 doğrulandı |
| İndirilen verinin işlenmesi | Aynı yeni çalışma dizininde `run --offline` | Başarılı |
| Paket içindeki kaynakların kontrolü | `verify` | Başarılı |
| Birim ve entegrasyon testleri | `python3 -m unittest discover -s tests -v` | 15 test başarılı |
| Sözdizimi | `python3 -m compileall -q fieldshift_data tests` ve `bash -n run_data.sh` | Başarılı |
| Temiz yerel ortam | Yeni kopya + `python3 -m venv .venv` + `verify` + `bash run_data.sh` | Başarılı; pip/harici paket gerekmedi |
| Linux Mint masaüstü | Doğrudan Mint makinesi kullanılmadı | Doğrulanmadı; standart Linux/Python akışı doğrulandı |

## Davranış kontrolleri

- Eksik değerlerin sıfıra dönüştürülmemesi.
- Tekrarlı CSV başlığı ve hatalı satır genişliğinin reddedilmesi.
- ZIP yol aşımının reddedilmesi ve dosyaların keyfi yollara çıkarılmaması.
- Fosfor hesabının bağımsız aritmetik kontrolü.
- Kaynak dipnotlarının veri anahtarı olarak kullanılmaması.
- Bozuk mevcut ham dosyanın üzerine yazılmaması.
- Eksik veride kendiliğinden ağa bağlanılmaması.
- NAPESHM toprak satırlarının yönetim olaylarıyla çoğalmaması.
- Rotasyon konumları ile sistem ortalamalarının ayrılması.
- Gerçek `AAFC-Sys1` bütçesinin kaynak bileşenlerinden yeniden hesaplanması.
- Eksik bütçelerin ve sayısal olmayan `Not measured` girdisinin görünür tutulması.
- Olsen/Mehlich-3 ve toplam N yöntem/birimlerinin korunması.
- Çıktı kaynağı, bütünlük özetleri ve tamamlanma durumunun saklanması.
- Terminal sorgusu ve eksik kaynakta açıklayıcı hata çıkışı.

## Gerçek veri kontrol sayıları

P-FLUX: 61 sistem, 224 kayıt; 163 rotasyon konumu + 61 sistem özeti.
Kaynak eşlemesinde 163 konumun tamamı eşleşti; 11 dipnot ayrı tutuldu.
Agronomik karşılaştırma: 59 yuvarlama toleransı içinde, 2 eksik.
Genel tarla karşılaştırması: 45 yuvarlama toleransı içinde, 16 eksik.
Eksikler tamamlanmış hesap gibi gösterilmedi.

NAPESHM: 94 alan, 508 uygulama, 1.453 toprak gözlemi.
Toprak → alan/uygulama bağlamı 1.453 satır kaldı.
Seçilmiş 9 gösterge uzun biçimde 13.077 kayıt oluşturdu.
Yönetim bağlantılarında eşleşmeyen kayıt yoktu.

`reference_output/` temiz ortam koşusunun örnek çıktılarını içerir. Yeni bir
koşuda kimlik ve UTC zamanı değişir; aynı kaynaklarla sayısal sonuçlar aynı kalır.

Bu kontroller veri hattı ve kayıtlı fosfor muhasebesini doğrular. Saha için
gelecek rotasyon tahmini, model eğitimi ve web arayüzü henüz tamamlanmamıştır.
İklim projeksiyonları edinilir ve 0.5.0 ile iki dönem arasında karşılaştırılır;
bunlar agronomik geçerlilik kanıtı değildir.

## 0.5.0 bölgesel karşılaştırma doğrulaması

`python3 -m unittest discover -s tests -v`: 62 test başarılı.
Yeni yedi test; bağımsız sabit seri aritmetiğini, eksik gün/eksik yıl
kurallarını, tekrar/eksik tarih reddini, sıfır referansta yüzde hesabını ve
yapılandırma sınırlarını ve gerçek önbellekle CLI/GeoJSON çıktısını denetler. Gerçek varsayılan karşılaştırmanın
ham yanıtları ve örnek çıktısı paketle birlikte saklanır.

Canlı `regional --online` koşusunda 8/8 istek gerçekten indirildi;
`regional --offline` ile aynı karşılaştırma yeniden üretildi. Her iki
alanda sıcaklık ve yağış için 11/12 ay karşılaştırıldı. Temmuz sıcaklık
farkları Oregon +1,306193548 °C, Kansas +1,103387097 °C. Aralık eksikleri
nedeniyle yıllık farklar boş kaldı. Bu sonuçlar agronomik doğrulama değildir.

## 0.6.0 — gerçek USDA ürün sınıflandırması

15 Kasım 2026, Python 3.12.14/Linux: `python3 -m unittest discover -s tests`
72 test ile başarılıdır. Yeni testler yıl/raster kilidini, yanıt sırası yerine
konum eşlemesini, eksik/background kodlarını, çift ürün sözlüğünü, karabuğdayın
ayrılmasını, eksik yıldan geçiş üretilmemesini, cache bütünlüğünü ve
gerçek önbellekten public CLI/GeoJSON/bağlam sayılarını denetler.

Canlı `cropland --online`: 20 yeni HTTPS yanıtı (1 servis, 1 sınıf sözlüğü,
6 katalog, 12 çoklu nokta sorgusu). 50 noktada 300 nokta/yıl sınıfı, 64 buğday
içeren sınıf, 250 geçiş. Çevrimdışı tekrar aynı sonuçları verir.

Güncellenmiş `self-test --online`: boş geçici önbellekte 8/8 canlı kontrol
başarılı; yeni USDA kontrolü 2019 Oregon merkezinde kışlık buğday kodunu ve
25 nokta sorgusunu doğrular. Rapor `reference_output/live_test_v060/` içinde.
Bu testler uydu sınıflandırmasının saha doğruluğunu, geleceğin ürün
uygunluğunu veya optimum rotasyonu doğrulamaz.

Bölgesel GeoJSON artık aylık farkları içerir; gerçek önbellekle CLI testinde
12 ay ve Oregon temmuz farkı ayrıca denetlenir.

## 0.7.0 — amaç bileşenleri

`tests/test_goal_components.py` 24 test ekler; toplam 96 test başarılıdır.
Ekim penceresinde eşik geçişi, eksik gün, kışlık buğdayın hasat yılı
kuralı ve GDD toplamı sınanır. Paketteki NASA verisiyle Oregon penceresi,
kaynaktaki 15 Ekim 2018 ekim tarihine 21 günden yakın olmalıdır. Ekonomi
tarafında kâr formülü, eksik girdinin doldurulmaması, tam sayım optimumu,
rotasyon etkisi, ekim takvimi uyumu, NASS ayrıştırma ve API anahtarının
kayda yazılmaması sınanır. Uygunluk tarafında sentetik ızgarada eğitim, AUC
ve ısınmada kuzeye kayma sınanır; iki alanla eğitimin reddedilmesi de test
edilir. Sentetik sayılar yalnız testlerde kullanılır. Canlı NASS ve koridor
indirmesi bu paketi hazırlayan ortamda ağ kısıtı nedeniyle çalıştırılamadı;
ilk `--online` koşusunda sonuç kontrol edilmelidir.
