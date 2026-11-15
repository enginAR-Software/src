# FieldShift: İklim Değişikliğinde Buğdayın Göç Bölgesi ve Parsel Bazında Ekonomik Ekim Rotasyonu

**Proje kayıt tarihi:** 15 Kasım 2026  
**Çalışan gerçek veri yazılımı:** FieldShift Data 0.9.0  
**Geliştirme ortamı:** Python; hedef kullanım ortamı Linux Mint üzerinde yerel bilgisayar

## Proje amacı

Projemizin amacı, Kuzey Amerika kıtasında yetiştirilen buğdayın iklim
değişikliğine bağlı olarak ve çeşitli verilere bakılarak göç edeceği en uygun
bölgeyi kestirmektir. Buğdayın izlediği yol boyunca bölgeler parsellere
ayrılır. Her parsel için ekonomik anlamda en verimli ekim rotasyonunu
hesaplayan bir matematiksel model eğitilir. Böylece çiftçiye her yıl ne zaman
ve hangi ürünü ekeceği söylenerek işi kolaylaştırılır.

Bu amaç yazılımda beş bileşene ayrılmıştır. Her sürümün durumu bu beş
bileşene göre raporlanır (`python3 -m fieldshift_data goal`):

| Bileşen | Amaçtaki karşılığı | Yazılımdaki modül | Ürettiği çıktı |
|---|---|---|---|
| A | Buğdayın iklim değişikliğiyle göç edeceği en uygun bölge | `suitability.py`, `corridor` komutu | Hücre bazında bugünkü ve gelecekteki buğday uygunluğu, uygun bölgenin kayma mesafesi ve yönü |
| B | İzlediği yol boyunca bölgeleri parsellere ayırmak | `goal.py` | Gerçek ürün geçmişi olan parseller ve harita dosyası |
| C | Parsel başına ekonomik anlamda en verimli ekim rotasyonu | `economics.py` | Mevcut, en kârlı ve buğday ağırlıklı üç strateji; yıllık kâr ve P kaldırması |
| D | Eğitilmiş matematiksel model | `suitability.py` | Gerçek veriyle eğitilen ve mekânsal blok doğrulamasıyla sınanan uygunluk modeli |
| E | Çiftçiye her yıl ne zaman ve hangi ürünü ekeceğini söylemek | `planting.py`, `goal --date` | Parsel × yıl için ürün ve ekim tarih aralığı |

“Göç” buğdayın fiziksel olarak taşınması değildir. İklim değiştikçe buğday
yetiştirmeye uygun bölgenin yer değiştirmesidir ve haritada uygunluk
katmanı olarak gösterilir.

## Ekonomik verim ve toprak

Amaç fonksiyonu ekonomik verimdir: plan yılları boyunca parsel başına toplam
beklenen kâr. Toprak besin dengesi bu hesabın içinde yer alır, çünkü hasatla
topraktan çıkan fosfor yerine konmadıkça sonraki yılların verimi ve kârı
düşer. Bu nedenle her yılın kârından, o ürünün kaldırdığı P'nin gübreyle
yerine konma maliyeti düşülür. Ürünün P kaldırması P-FLUX ölçümlerinden
alınır. Rotasyonun verime etkisi de kaynak gösterilerek modele girilebilir;
örneğin nadasın su biriktirmesi veya baklagilin bıraktığı azot.

Bu yaklaşım NASA Space Apps “Field Shift” challenge'ının toprak sağlığı
beklentisini de karşılar. Toprak sağlığı ayrı bir amaç olarak değil,
ekonomik verimin uzun vadede sürmesinin koşulu olarak modele girer.

## Araştırma sorusu

**İklim değişikliği altında buğday yetiştirmeye uygun bölge nereye kayar ve bu
yol üzerindeki her parsel için, gerçek ürün geçmişi, NASA iklim verisi ve
ekonomik girdiler kullanılarak, her yıl ne zaman ve hangi ürünün ekileceğini
söyleyen en kârlı rotasyon nasıl hesaplanır?**

Gözlenen ilişki ile nedensel etki ve geleceğe yönelik tahmin birbirine
karıştırılmaz. Her çıktı hangi ölçüm ve varsayımlardan üretildiğini taşır.
Eksik veri tahminle doldurulmaz; boş bırakılır ve nedeni yazılır.

## Sistemin yapısı

| Bölüm | Görevi |
|---|---|
| Veri | Kaynak dosyalarını edinmek; sürüm, birim, yöntem, kimlik ve eksikleri denetlemek |
| Hesaplama ve model | Besin muhasebesi, gözlem karşılaştırmaları ve ileride rotasyon senaryolarını hesaplamak |
| Arayüz | Harita, tarih/ay seçimi ve girdi–çıktı ekranları; 0.7.0'da harita için GeoJSON çıktıları hazırdır |

Hesaplamalar arayüzden bağımsız Python modülleriyle yürütülür. Böylece web
arayüzü geliştirilmeden önce veri ve hesaplama bölümleri yerel bilgisayarda
test edilebilir. İlk gerçek veri yazılımı Python standart kütüphanesini
kullanır; üçüncü taraf paket kurulumu gerektirmez.

## Kullanılan gerçek veriler

**P-FLUX / LTAR Phosphorus Budget Summary:** ABD ve Kanada'daki üretim
sistemlerinin fosfor girişlerini, hasatla çıkışlarını ve kayıtlı hidrolojik
kayıplarını içerir. Çalışan veri hattında 61 sistemin 224 kaydı işlenmektedir.
Rotasyon konumları ile sistem özetleri ayrı tutulur. Buğdayla ilişkili metin
bulunan 23 aday sistem, seçim kanıtıyla birlikte ayrıca kaydedilir; bu adaylık
tek başına bütün kayıtların buğday tarlasına ait olduğunu göstermez.

**NAPESHM:** ABD ve Meksika'daki uzun süreli araştırma alanlarının toprak
ölçümlerini ve yönetim bilgilerini içerir. Kaynakta 94 alan, 508 uygulama ve
1.453 toprak gözlemi vardır. Toprak tablosunda 93 alanın gözlemi bulunmaktadır.
Buğday bulunan 40 aday alanın 39'unda bu tablo üzerinden toprak verisi
eşlenebilmiştir; USWA03 için veri yokluğu açıkça işaretlenmiştir.

Veri setleri farklı araştırmaları temsil eder. Aynı alan ve dönem oldukları
doğrulanmadan tek bir deneyin parçaları gibi birleştirilmez. Mevcut araştırma
alanları Kuzey Amerika'nın tamamını temsil eden bir tarla envanteri değildir.

## Veri işleme ve kayıt düzeni

Ham dosyalar değiştirilmeden korunur. Dosya boyutu, kaynakta bildirilen MD5
ve yerel SHA-256 özetleri kaydedilir. Temizleme sırasında kimlikler, ölçüm
yöntemleri ve birimler korunur; eksikler sıfıra çevrilmez. Toprak gözlemleri
uygulama ve alan bilgilerine bağlanır; yönetim olayları gözlem sayısını
yapay biçimde artırmaması için ayrı tutulur.

Mehlich-3 ve Olsen fosforu ayrı göstergelerdir. Toplam azot, mineral azot
sayılmaz. mg/kg ve yüzde değerleri, gerekli derinlik ve süreç bilgisi olmadan
kg/ha stoklarına çevrilmez. İşlenmiş tablolar CSV, çalışma kayıtları JSON ve
SQLite, açıklamalar Markdown biçiminde saklanır. Her çalıştırma ayrı kimlikle
kayıt altına alınır.

## Mevcut hesaplamalar ve pilotlar

Çalışan fosfor hesabı şu muhasebeyi yeniden üretir:

**Agronomik P bütçesi = Uygulama + Atmosferik çökelme + Sulama − Hasatla çıkış**

Kayıtlı hidrolojik P çıkışı da mevcutsa genel tarla bütçesi hesaplanır.
Yayımlanmış 61 sistem özetinin 59'unda agronomik bütçe belirlenen yuvarlama
toleransıyla yeniden üretilebilmiştir; iki sistemde gerekli bilgi eksiktir.
Bu kontrol hesaplamanın kaynakla tutarlılığını gösterir; geleceği öngören
bir modelin doğruluk ölçüsü değildir.

Yeni pilot analiz bölümü iki alana odaklanır:

- **Oregon / USOR03:** Kışlık buğday–bezelye sıralamasındaki üç toprak işleme
  uygulaması, toplam 12 tekil deney birimi üzerinden karşılaştırılır.
- **Kansas / USKS01:** Nadas, ikinci ürün soya ve örtü bitkisi seçeneklerinin
  iki azot düzeyi etiketiyle oluşturduğu altı uygulama, toplam 24 deney birimi
  üzerinden incelenir. Buradaki ölçüm fazı sorgumdur.

Dokuz toprak göstergesi için sayı, eksiklik, ortalama, medyan, aralık ve örnek
standart sapması hesaplanır. Yapılandırılmış uygulama çiftleri için B−A
ortalama farkları verilir. Bu farklar betimseldir; zaman içindeki değişim,
istatistiksel anlamlılık veya nedensel etki olarak sunulmaz.

## Tamamlanan ve planlanan bölümler

0.3.0 sürümünde gözlenen ürün döngülerinden çok yıllı referans plan hesaplayan
bir bölüm eklenmiştir. Kullanıcı; kaynak grubunu, başlangıç yılını, sezon
sayısını, izin verilen ürünleri, buğday sezonu sayısını ve P muhasebesi
sınırlarını tanımlar. Motor, kaynak döngülerinin başlangıç fazlarını karşılaştırır
ve uygun senaryoyu seçer. Varsayılan altı sezonluk örnek, buğday–kanola–soya
döngüsünü iki kez kullanır. Kaynak akılarının değişmeden tekrarlanması bir
senaryo varsayımıdır; yeni alandaki verim veya mineral stoku tahmini değildir.

NASA POWER geçmiş hava verisi ve NEX-GDDP-CMIP6 tabanlı gelecek iklim
projeksiyonu da ayrı türlerde indirilmektedir. SSP senaryosu, model, birim,
UTC standardı, dönem ve eksiklikler kayıt altındadır. Gelecek senaryoları henüz
rotasyonların verim ve besin tepkisine bağlanmamıştır. 2027 için canlı
projeksiyon sorgusunda eksik günler görülmüş; yıllık yağış toplamı bu nedenle
tamamlanmış sonuç gibi verilmemiştir.

İndirme ve kullanım için boş geçici dizinde yapılan canlı kontrol; üç kaynak
dosyasını yeniden edinmiş, veri hattını ve planlamayı çalıştırmış, geçmiş ve
gelecek NASA servislerini ayrı ayrı sorgulamıştır. Güncel sürümde sekiz canlı kontrol ve
72 birim/entegrasyon testi başarılıdır. Yazılım doğrulaması, saha için
agronomik geçerliliğin doğrulanması olarak sunulmaz.

0.4.0 sürümünde kaynak yönetim kayıtlarından gerçek sezon takvimleri
çıkarılmıştır. İki pilotta uygulama bazında 26 sezon bulunmuş; Oregon'daki
12 toprak gözlemi örnekleme tarihine göre aynı alanın geçmiş havasına ve
yönetim kayıtlarına bağlanmıştır. Kansas'taki 24 gözlem için örnekleme tarihi
bulunmadığından tarihler uydurulmadan ayrı tutulmuştur.

Oregon buğdayı 15 Ekim 2018'de ekilmiş, 15 Nisan 2019'da örneklenmiş ve
15 Temmuz 2019'da hasat edilmiştir. Örnekleme saatinin bilinmemesi nedeniyle
model girdisi adayı hava ve yönetim kayıtları 14 Nisan'da kesilir. Tam sezon
özeti ayrı saklanır. Böylece hedef ölçümden sonraki hava bilgisi geçmişte
biliniyormuş gibi eğitim girdilerine alınmaz.

Bu eşleştirme, 12 bağımsız iklim deneyi oluşturmaz; gözlemler tek ortak hava
dönemini paylaşmaktadır. Toprak hedefleri tek kampanyaya aittir. Dinamik
model eğitimi için aynı parselde tekrarlı ölçümler ve hasat besin çıkışları
gerekir. Birleşik tablo ve model hazırlığı kaydı bu sınırları açıkça belirtir.

| Bölüm | 0.7.0 durum kaydı |
|---|---|
| Gerçek veri indirme ve bütünlük kontrolü | Çalışıyor |
| Eksik, yöntem ve birim incelemesi | Çalışıyor |
| Mevcut fosfor bütçesini yeniden hesaplama | Çalışıyor |
| Tekil gözlemlerden pilot karşılaştırması | Çalışıyor |
| Boş önbellekte gerçek indirme ve kullanım testi | Çalışıyor |
| Gözlenen döngülerden P-kısıtlı çok yıllı referans plan | Çalışıyor |
| NASA geçmiş veri ve gelecek senaryosu edinimi | Çalışıyor |
| Aynı model/senaryoyla iki dönemin alan bazlı iklim farkı | Çalışıyor |
| USDA yıllık ürün sınıfları ve gözlenen ürün dizileri | Çalışıyor |
| Ürün noktalarının alan düzeyinde iklim/toprak bağlamıyla eşlenmesi | Çalışıyor |
| Gerçek sezon–yönetim–örnekleme–geçmiş hava bağlantısı | Çalışıyor |
| Gelecek bilgisinin hedef öncesi girdilere karışmasını önleyen kesim | Çalışıyor |
| Yerel CSV/JSON/SQLite çıktıları | Çalışıyor |
| A. Buğday uygunluk modeli ve göç koridoru | Kod ve testler hazır; eğitim için `corridor --online` ile koridor ızgarası indirilmeli |
| B. Parsellere ayırma | Çalışıyor (30 pilot parsel) |
| C. Parsel başına en kârlı rotasyon ve üç strateji | Çalışıyor: resmî kaynaklı girdilerle (KFMA, NASS, OSU, USDA AMS) |
| D. Eğitilmiş model ve mekânsal doğrulama | Kod ve testler hazır; iki pilot alan eğitim için yetersiz, koridor verisi bekleniyor |
| E. Yıllık ürün ve ekim tarih aralığı | Çalışıyor (NASA projeksiyonundan, kaynaklı eşiklerle) |
| Gelecekteki N/P/K süreçlerinin saha kalibrasyonu | Sonraki aşama |
| Harita ve web arayüzü | Çalışıyor: `app` komutuyla yerel, internetsiz etkileşimli arayüz |

Önceden hazırlanan sentetik FieldShift Soil demosu matematiksel muhasebe
ve plan arama yaklaşımını göstermektedir. Mevcut gerçek veri yazılımı ile
bu demo henüz saha için doğrulanmış tek bir tahmin modeli hâline getirilmemiştir.

## Geliştirme yönü ve beklenen çıktı

Bir sonraki aşamada pilotların deney düzeni, tekil ölçümleri, yönetim olayları
ve zaman kapsamı ayrıntılı değerlendirilecektir. Uygun veriler sağlandığında
besin süreçleri kalibre edilecek, mevcut rotasyonlarla alternatifler aynı
başlangıç koşullarında karşılaştırılacak ve belirsizlik senaryoları incelenecektir.
Uzun dönem yetişme uygunluğu için edinilen iklim senaryoları ürün modellerine
bağlanacak; ekim haritaları ve gerekli mekânsal bilgiler ayrıca eklenecektir.

Nihai hedef; kullanıcının seçtiği alan ve tarihe göre uygulanabilir ürün
sıralamalarını, ekim aralıklarını, beklenen besin dengelerini, gerekçeleri ve
veri eksiklerini anlaşılır biçimde gösteren yerel bir web uygulamasıdır.
Öneriler, hangi ölçüm ve varsayımlardan üretildiği izlenebilen hesaplara dayanacaktır.

## Kaynaklar

1. Williams ve diğerleri (2021). LTAR Phosphorus Budget Summary. Ag Data Commons. https://doi.org/10.15482/USDA.ADC/1523365
2. Soil Health Institute (2024). North American Project to Evaluate Soil Health Measurements Dataset. Ag Data Commons. https://doi.org/10.15482/USDA.ADC/25632270
3. NASA POWER günlük API: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
4. NASA POWER Projection API: https://power.larc.nasa.gov/docs/services/api/projection/
5. FieldShift Data 0.7.0 kaynak kodu, kaynak dosyaları, yapılandırmalar ve doğrulama testleri. Bu açıklamadaki mevcut durum, bu sürümün çalıştırılmış sonuçlarına dayanır.
6. USDA NASS Quick Stats API: https://quickstats.nass.usda.gov/api
7. Ekim eşiklerinin kaynakları (SDSU, OSU, NDSU, Virginia Tech, Top Crop Manager): `config/crop_calendar.json` ve `docs/GOAL.md`.

## 0.5.0 gelişmesi: bölgesel değişimin iklim hesabı

`regional` komutu Oregon ve Kansas noktalarında 2015–2024 ile 2040–2049
dönemlerini aynı NASA NEX-GDDP ensemble modeli ve SSP2-4.5 senaryosuyla
karşılaştırır. Sıcaklık farkı, aylık/yıllık yağış farkı ve veri kapsamı
CSV, JSON ve GeoJSON çıktılarıyla kaydedilir. Referans dönem model
çıktısıdır; gözlem değildir. Eksik gün/yıl içeren ilgili özetler ve farklar
boş bırakılır.

Bu gelişme ürünlerin gelecekte yetişeceği alanları henüz doğrulamaz;
bölgesel değişim için gerekli sayısal iklim girdisini oluşturur. Bağımsız
ürün dağılımı verisiyle mekânsal doğrulama ve rotasyonların dinamik toprak
tepkisi sonraki aşamalardır. Ayrıntı: `docs/REGIONAL_CHANGE.md`.

## 0.6.0 gelişmesi: gerçek ürün dağılımı ve geçmiş diziler

USDA NASS Cropland Data Layer, CroplandCROS üzerinden edinilir. Oregon ve
Kansas merkezleri çevresindeki toplam 50 sabit nokta 2018–2023 boyunca
izlenmiştir. 300 nokta/yıl sınıflandırması, 64 buğday içeren kayıt ve
250 ardışık yıl ürün geçişi çıkarılmıştır. Uydu sınıflandırması, çiftçi
beyanı veya saha doğrusu sayılmaz; nokta oranları hektara çevrilmez.

Ürün kayıtları iklim ve toprak tablolarına context_id ile bağlanır.
36 toprak gözleminin 324 gösterge satırı ayrı tutulur; ölçümler çevredeki
her noktaya aitmiş gibi çoğaltılmaz. Yeni dosyalar CSV/JSON/GeoJSON'dur.
Bölgesel GeoJSON artık 12 aylık farkları da içerir.

Bu gelişme gözlenmiş rotasyon adayları için veri sağlar. Ürün dizisinin
tekrar eden bir döngü olduğu, en iyi toprak sonucunu verdiği veya buğdayın
yetişemeyeceği yerleri gösterdiği iddia edilmez. İki alanla coğrafi model
doğrulanmış sayılmaz. Dinamik toprak süreçleri ve iklimle birleşik optimum
rotasyon henüz kalibre edilmemiştir. Ayrıntı: `docs/CROPLAND.md`.

Kaynak: https://www.nass.usda.gov/Research_and_Science/Cropland/sarsfaqs2.php

## 0.7.0 gelişmesi: yazılımın proje amacına bağlanması

Bu sürümde projenin amacı (Preparation.md) beş bileşene ayrıldı ve tek bir
`goal` komutu her bileşenin durumunu, ürettiğini ve tamamlanması için ne
gerektiğini raporlar. Önceki sürümlerdeki “öncelik ekonomik kâr değil”
ifadesi amaçla çeliştiği için kaldırıldı. Toprak besin dengesi artık kâr
hesabının içinde, P yerine koyma maliyeti olarak yer alır.

**E: ekim zamanı.** NASA NEX-GDDP günlük projeksiyonundan her bölge, ürün ve
yıl için ekim tarih aralığı hesaplanır. Eşiklerin her biri kaynaklıdır:
mısır 10°C, soya 12,8°C, sorgum 15,6°C ve bezelye 4,4°C. Kışlık buğdayda 31
Aralık'a kadar 389 °C·gün birikmesi aranır. Kansas için kışlık buğday
penceresi 2027 hasadı için 11–25 Ekim 2026; 2040'larda yaklaşık dört gün
geç kayar. Oregon'da kaynak kaydındaki gerçek ekim tarihi (15 Ekim 2018),
hesaplanan pencerenin (6–20 Ekim 2018) içindedir.

**C: ekonomik rotasyon.** Plan yılları boyunca bütün geçerli ürün dizileri
sayılır ve toplam kâra göre sıralanır. Ardışık aynı ürün sınırı, en az buğday
sezonu ve ekim takvimi uyumu dikkate alınır; uyum kuralına göre önceki
ürünün hasadı, kışlık buğdayın en geç ekim tarihinden sonraya kalamaz. Her
parsel için mevcut, en kârlı ve buğday ağırlıklı olmak üzere üç strateji
verilir. Verim ve fiyat NASS Quick Stats'tan (ücretsiz API anahtarıyla)
veya kaynak gösterilerek elle girilir. Üretim maliyeti elle girilir;
önerilen kaynak USDA ERS Commodity Costs and Returns'tür. Pakette hiçbir
ekonomik değer uydurulmamıştır; girdiler boş gelir.

**A + D: göç modeli.** Izgara hücrelerinde USDA CDL buğday varlığı ile aynı
NASA projeksiyonunun 2015–2024 iklimi arasındaki ilişki lojistik regresyonla
öğrenilir. Model mekânsal blok çapraz doğrulamayla sınanır (AUC, Brier) ve
2040–2049 iklimine uygulanır. Sonuç, uygun bölgenin merkezinin kaç km ve
hangi yönde kaydığı ile kazanılan ve kaybedilen hücrelerdir. Varsayılan
koridor Kansas–Nebraska–Dakotalar hattıdır (91 hücre). Paketteki iki pilot
alan eğitime yetmez; yazılım bunu açıkça raporlar ve modeli eğitmez.

**B: parseller.** Pilotlarda 2018–2023 boyunca her yılı tarım sınıfı olan
30 CDL noktası parsel kabul edilir. Orman, su ve yerleşim gibi 20 nokta
dışarıda kalır.

Yazılım doğrulaması 96 birim ve entegrasyon testini kapsar. Ekonomik ve
uygunluk testlerinde kullanılan sayılar yalnız test içindir ve sentetik
olarak işaretlidir. Ayrıntı: `docs/GOAL.md`.

## 0.7.1 gelişmesi: ekonomik sonuç ve görsel pano

Ekonomik girdiler resmî kaynaklarla dolduruldu: Kansas için K-State KFMA
çiftlik kayıtları (2020–2024), Oregon için USDA NASS eyalet bülteni ve
Oregon State University işletme bütçeleri, fosfor gübresi için USDA AMS
fiyatları. Oregon'da USDA ARS Pendleton çalışmasının yağış kuşağı
sınıflamasına dayanan "en fazla iki yıl nadassız" kuralı eklendi.

Bu girdilerle en kârlı rotasyon, mevcut rotasyona göre 6 yılda acre başına
Kansas'ta yaklaşık 338 $, Oregon'da yaklaşık 115 $ daha fazla ekonomik kâr
bırakıyor. Kansas'ta sonuç ağırlıkla sorgum ve kışlık buğdaydır; Oregon'da
buğday–buğday–nadas düzenidir. Oregon sonucu, buğdaydan sonra buğdayın verim
düşüşü modelde olmadığı için iyimserdir.

`goal` komutu artık `DASHBOARD.html` amaç panosunu da üretir. Panoda beş
bileşenin durumu, ekim takviminin iklimle kayması, stratejilerin kâr
karşılaştırması ve parsel başına yıllık ürün ile ekim tarihi gösterilir.

## 0.8.0 gelişmesi: etkileşimli arayüz

`app` komutu tarayıcıda açılan, internet gerektirmeyen tek dosyalık bir
arayüz üretir. Arayüzde şunlar var:

- ABD haritası, pilot alanlar ve koridor indirildiğinde buğday uygunluğunun
  2015–2024'ten 2040–2049'a kayması;
- parsel haritası (seçilen yılda önerilen ürünün rengiyle);
- parsel başına 6 yıllık plan: ne ekileceği, ne zaman ekileceği, kâr ve
  fosfor kaldırması, "neden bu plan" açıklaması ve riskler;
- seçilen tarihte hangi parselde ekim zamanı olduğunu gösteren sorgu;
- çiftçi öncelikleri formu: ürün seçimi, buğday yılı, ardışık ürün sınırı,
  fiyat senaryosu ve nadas kuralı. Her değişiklikte planlar tarayıcıda
  yeniden hesaplanır.

Tarayıcıdaki hesap ile Python hesabının 90 parsel-stratejide aynı sonucu
verdiği testle doğrulanmıştır. Örneğin fiyatlar %20 düşük alındığında
Kansas'ta önerilen plan değişmez; bu, önerinin fiyat değişimine karşı
sağlam olduğunu gösterir.


## 0.9.0 gelişmesi: koridor parselleri, iklimden verim, uydu

- **B:** 2040–2049 uygun bölgesindeki koridor hücrelerinden CDL parselleri üretilir (eyalet bazında ekonomi, hücre bazında ekim takvimi).
- **C/D:** NASS ilçe verimleri ile hücre iklimi arasında ridge regresyon kurulur, mekânsal blok doğrulamayla sınanır. 2040'ların verim çarpanları hesaplanır ve koridor parselleri için `most_profitable_2040` planı çıkarılır.
- **C:** Oregon'da buğday sonrası buğday verim cezası (Maaz ve diğ. 2017) eklendi; fiyat ±%20 senaryoları hesaplanır.
- **Uydu:** MODIS MOD13Q1 NDVI eğrisinden tepe zamanı, çıplak toprak süresi ve CDL etiketiyle fenoloji uyumu çıkarılır.
- Ayrıntı ve çalıştırma sırası: `docs/GENISLETMELER_0_9.md`.
