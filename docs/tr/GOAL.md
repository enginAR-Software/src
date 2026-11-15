# Proje amacı ve yazılım bileşenleri (0.7.1)

## Amaç (Preparation.md)

Kuzey Amerika'da yetiştirilen buğdayın iklim değişikliğine bağlı olarak ve
çeşitli verilere bakılarak göç edeceği en uygun bölgeyi kestirmek. İzlediği
yol boyunca parsellere ayrılan bölgeler için ekonomik anlamda en verimli
ekim rotasyonunu hesaplayan matematiksel bir model eğitmek. Çiftçiye her yıl
ne zaman ve hangi ürünü ekeceğini söyleyerek işini kolaylaştırmak.

## Tek komut

```bash
python3 -m fieldshift_data goal --offline
python3 -m fieldshift_data goal --offline --date 2027-10-15
python3 -m fieldshift_data goal-view outputs/goal_KIMLIK --date 2027-10-15 --parcel USOR03:r2:c2
```

`goal`, `outputs/goal_<kimlik>/` klasöründe şu dosyaları üretir:

| Dosya | İçerik |
|---|---|
| `GOAL_REPORT.md` | A–E bileşenlerinin durumu, ekim pencereleri, stratejiler, P kaldırması, sınırlar |
| `parcel_plans.csv` | Parsel × strateji × yıl: ürün, ekim başlangıç/bitiş, beklenen kâr, P kaldırması, eksik girdiler |
| `parcel_strategies.csv` | Parsel × strateji: ürün dizisi, toplam kâr, birikimli P kaldırması, durum |
| `planting_windows.csv` | Bölge × ürün × yıl ekim pencereleri ve dayanakları |
| `parcels.geojson` | Harita için parseller: mevcut ve en kârlı rotasyon, ilk yılın ürünü ve ekim aralığı |
| `parcels_excluded.csv` | Tarım dışı olduğu için parsel sayılmayan noktalar |
| `goal.json` | Bütün sonuçlar, kaynak özetleri ve sınırlar |

`--date` seçeneği her parsel için o tarihin yılındaki ürünü ve tarihin ekim
penceresine göre durumunu verir: “ekim penceresinde”, “pencereden önce” veya
“pencere geçti”. Kışlık buğdayda plan yılı hasat yılıdır; 15 Ekim 2027
sorgusu 2028 hasatlı buğdayın ekimini gösterir.

## A + D: göç bölgesi ve eğitilmiş model

```bash
python3 -m fieldshift_data corridor --online      # ilk indirme (uzun sürer)
python3 -m fieldshift_data corridor --offline     # sonraki koşular
```

1. `config/corridor.json` içindeki kutu 1° hücrelere bölünür (varsayılan
   Kansas–Nebraska–Dakotalar hattı: 91 hücre).
2. **Etiket:** her hücrede 3×3 nokta için USDA CDL 2019–2023 sınıfları.
   Tarım arazisi olan nokta, bu yıllardan birinde buğday görülürse 1,
   görülmezse 0 alır.
3. **Özellik:** hücre merkezinde NASA NEX-GDDP ensemble (SSP2-4.5)
   2015–2024 verisinden yıllık ortalama sıcaklık, GDD (taban 0°C),
   Haziran–Temmuz ortalama en yüksek sıcaklık, yıllık yağış ve Ekim–Haziran
   yağışı. Ensemble ortalaması uç değerleri yumuşattığı için eşik aşım
   sayıları kullanılmaz.
4. **Model:** standartlaştırılmış özelliklerle L2 düzenlileştirmeli lojistik
   regresyon (yalnız Python standart kütüphanesi).
5. **Doğrulama:** 2×2 hücrelik bloklar sırayla test kümesine ayrılır.
   AUC ve Brier skoru, yalnız yaygınlığa dayanan Brier skoruyla birlikte
   raporlanır.
6. **Gelecek:** aynı model 2040–2049 iklimine uygulanır. Uygunluğu ≥ 0,5
   olan hücrelerin merkezi bugün ve gelecekte hesaplanır. Kayma mesafesi
   (km), yönü (°), kazanılan ve kaybedilen hücreler raporlanır. Uygun bölge
   kutunun kenarına dayanıyorsa uyarı verilir.

Eğitim koşulları: en az 12 farklı iklimli hücre, buğday görülen en az 3
hücre ve buğdaysız tarım arazisi olan en az 3 hücre. Paketteki iki pilot
alan bu koşulları sağlamaz. Yazılım bunu raporlar ve modeli eğitmez.

## B: parseller

Pilot sürümde 2018–2023 boyunca her yılı tarım sınıfı (ürün, nadas, yem
bitkisi) olan CDL noktaları parsel kabul edilir. Mevcut rotasyon, gözlenen
6 yıllık dizinin plan yıllarına döngüsel devamı olarak varsayılır.

## C: ekonomik açıdan en verimli rotasyon

Her yılın kârı (USD/acre) şöyle hesaplanır:

> kâr = verim × rotasyon çarpanı × fiyat − üretim maliyeti − P kaldırması (kg/ha ÷ 2,471) × P gübresi fiyatı

- **Arama:** 2–8 yıllık planlarda bütün ürün dizileri sayılır; yaklaşık bir
  çözüm değil, kesin en iyi plan bulunur.
- **Kısıtlar:**
  - ardışık aynı ürün sınırı;
  - en az buğday sezonu;
  - bölgede izin verilen ürünler;
  - ekim takvimi uyumu: önceki yaz ürününün en erken hasadı kışlık buğdayın
    en geç ekim tarihinden sonraya kalırsa dizi elenir.
- **Stratejiler:** `mevcut` (CDL devamı), `most_profitable` ve `wheat_focused`
  (yılların en az yarısında buğday olan en kârlı farklı plan).
- **P kaldırması:** P-FLUX rotasyon yılı ölçümlerinden; önce her sistem
  içinde ortalama, sonra sistemler arası medyan alınır.

### 0.7.1: girdiler resmî kaynaklarla dolu

Hazır gelen değerler ve kaynakları:

| Girdi | Değer | Kaynak |
|---|---|---|
| Kansas mısır | 101,09 bu; 4,93 $/bu; 521,48 $/acre | K-State KFMA, sulanmayan, tüm çiftlikler, 2020–2024 |
| Kansas soya | 34,85 bu; 11,64 $/bu; 418,29 $/acre | KFMA |
| Kansas dane sorgum | 77,70 bu; 5,06 $/bu; 338,14 $/acre | KFMA |
| Kansas buğday | 50,97 bu; 6,15 $/bu; 326,37 $/acre | KFMA |
| Oregon kışlık buğday | 60,2 bu; 7,046 $/bu | USDA NASS Oregon bülteni, eyalet 2019–2023 |
| Oregon kışlık buğday maliyeti | 336 $/acre | OSU AEB 0064 (2020) |
| Oregon nadas maliyeti | 45,50 $/acre | OSU AEB 0045, nadas işlemleri |
| P gübresi | 3,91 $/kg P | USDA AMS: DAP 912,22 $/ton ve amonyak 915,50 $/ton (Ağustos 2026); DAP'ın azot değeri düşülür |
| Oregon nadas kuralı | En fazla 2 yıl nadassız | USDA ARS Pendleton: 13–18 inçte buğday–yazlık tahıl–nadas; Pendleton yaklaşık 406 mm |

Bu değerlerin sınırları:

- **Bölgesel ölçek:** KFMA Kansas geneli çiftlik kaydıdır, Riley ilçesine
  özgü değildir.
- **Ekonomik kâr:** KFMA ve OSU giderleri fırsat maliyetini de içerir. Sonuç
  ekonomik kârdır (yönetime net getiri), nakit kâr değildir.
- **Fosfor çift sayılabilir:** Giderler çiftliğin satın aldığı gübreyi zaten
  içerir; P yerine koyma maliyeti bunun üstüne eklenir. Bu nedenle kâr
  ihtiyatlıdır.
- **Oregon'da üst üste buğday:** Buğdaydan sonra buğdayın verim düşüşü
  modelde yoktur; yalnız nadas sıklığı kısıtı vardır. Sürekli buğdayın daha
  düşük verdiği bilinir (Machado ve diğ. 2007, CBARC). Aynı denemede
  karşılaştırmalı bir oran bulunduğunda `rotation_effects` satırı
  eklenmelidir.
- **Kışlık buğdaydan önceki hasat:** Yaz ürününün hasadı, en erken ekim
  tarihi ile sezon süresinden tahmin edilir. Bu iyimser bir tahmindir.

NASS yolu için `docs/NASS_ANAHTARI.md` dosyasına bakın.

### Girdiler: hiçbiri uydurulmaz

1. **Verim ve fiyat, NASS'tan:** https://quickstats.nass.usda.gov/api
   adresinden ücretsiz anahtar alın. Ardından:

   ```bash
   export FIELDSHIFT_NASS_KEY=ANAHTARINIZ
   python3 -m fieldshift_data economics --online
   ```

   Verim önce ilçe, yoksa eyalet düzeyinde 2014–2023 ortalamasıdır. Fiyat
   eyalet pazarlama yılı ortalamasıdır. Sorgum fiyatı $/CWT olarak
   yayımlanır ve $/bu'ya çevrilir. API anahtarı önbelleğe ve kayıtlara
   yazılmaz.
2. **Elle giriş:** `config/economics_inputs.csv`. Değer girilen her alanın
   kaynak sütunu zorunludur. Elle girilen değer NASS değerinin önüne geçer.
3. **Maliyet:** NASS'ta yoktur. Önerilen kaynak USDA ERS Commodity Costs
   and Returns (bölgesel, $/acre).
4. **Genel parametreler:** `config/economics.json` içinde P gübresi fiyatı
   ($/kg P) ve nadas maliyeti, her biri kaynağıyla birlikte girilir.
5. **Rotasyon etkileri:** `rotation_effects` listesine kaynaklı verim
   çarpanları girilebilir; örneğin nadastan sonra buğday. Oregon'da nadasın
   su biriktirme faydası bu satır olmadan modele girmez. Bu durumda
   optimizasyon nadası yalnız maliyet olarak görür.

İlçe atamaları (USKS01 → Riley, KS; USOR03 → Umatilla, OR) koordinatlardan
elle yapılmıştır; kullanmadan önce doğrulayın.

## E: her yıl ne zaman ekilir

`config/crop_calendar.json` içindeki her eşiğin kaynağı dosyada yazılıdır.

| Ürün | Kural | Kaynak |
|---|---|---|
| Mısır | 3 günlük ort. ≥ 10°C, 7 gün kalıcı; bitiş = sonbahar kesimi − 110 gün | SDSU Extension; 110 gün **varsayım** |
| Soya | ≥ 12,8°C; bitiş = kesim − 120 gün | SDSU Extension; 120 gün **varsayım** |
| Sorgum | ≥ 15,6°C; bitiş = kesim − 105 gün | Oregon State EM 8794 (60–65°F, 98–105 gün) |
| Bezelye | ≥ 4,4°C (yalnız başlangıç) | NDSU A1166; University of Idaho |
| Yazlık buğday | ≥ 1,7°C (yalnız başlangıç) | SDSU Extension |
| Kışlık buğday | En geç ekim = 31 Aralık'a kadar ≥ 389 °C·gün kalan son gün; pencere 14 gün | Virginia Tech SPES-730 (700 °F·gün); Top Crop Manager |

Kurallar şöyle uygulanır:

- **Sonbahar kesimi:** 7 günlük ortalama sıcaklığın 10°C altına indiği ilk
  sonbahar günü.
- **Toprak sıcaklığı vekili:** hava sıcaklığı (T2M) toprak sıcaklığı yerine
  kullanılır. Ensemble ortalaması soğuk dalgaları yumuşattığı için ilkbahar
  başlangıçları erken çıkabilir.
- **Kış ortası eşikleri:** 1 Mart'tan önce geçilen eşikler `low_confidence`
  olarak işaretlenir. Bu bölgelerde ekim zamanını toprak işlenebilirliği ve
  don riski belirler.
- **Kullanılan iklim:** o yılın gerçek günlük projeksiyonu varsa o
  kullanılır. Yoksa veya eksikse en yakın 10 yıllık model normali (2015–2024
  ya da 2040–2049) kullanılır ve dayanak sütununa yazılır.
- **Aralık sonu boşlukları:** NEX-GDDP yanıtlarında Aralık sonu günleri
  sistematik olarak eksik. Kışlık buğdayda 20–31 Aralık arasındaki en fazla
  3 eksik gün GDD'ye katılmaz ve bu durum sonuçta yazılır.

**Kaynak kaydıyla kontrol:** NAPESHM'e göre Oregon USOR03'te kışlık buğday
15 Ekim 2018'de ekilmiştir. Hesaplanan pencere 6–20 Ekim 2018'dir.

## Pano

`goal` komutu sonunda `DASHBOARD.html` dosyasını üretir. Dosya tek
parçadır, internet istemez ve tarayıcıda açılır. Panoda şunlar yer alır:

- beş bileşenin durumu;
- 2016–2024 ile 2041–2049 arasında ekim takviminin kayması;
- üç stratejinin kâr karşılaştırması;
- parsel başına yıllık ürün ve ekim tarihi;
- göç bölgesi. Koridor verisi indirildiyse uygunluk haritası gösterilir,
  indirilmediyse pilot alanlardaki iklim kayması.

Panoyu yeniden üretmek için:

```bash
python3 -m fieldshift_data dashboard
```

Pano verileri `dashboard_data/` klasöründe CSV olarak durur.

## Challenge (Details.md) karşılığı

| Challenge beklentisi | Karşılığı |
|---|---|
| NASA yer gözlemi | NASA POWER / NEX-GDDP günlük iklim: E ve A |
| Yerel toprak bilgisi | NAPESHM ve P-FLUX: P kaldırması kâr hesabında |
| Çiftçi öncelikleri | İzinli ürünler, en az buğday sezonu, ardışık ürün sınırı, girdiler |
| Mevcut rotasyon dahil en az 3 strateji | `mevcut`, `most_profitable`, `wheat_focused` |
| Gerekçe, kanıt, eksik, risk | Her satırda dayanak, kaynak ve eksik girdi sütunları; rapor sınırları |
| Harita | `parcels.geojson`, `corridor.geojson` |
| Uzman yargısının yerine geçmez | Raporların “Yorum sınırları” bölümleri |

## Sınırlar

- CDL uydu sınıflandırmasıdır; çiftçi beyanı değildir.
- Bölge içindeki parseller aynı ilçe verimini, fiyatını ve maliyetini
  paylaşır.
- Ekim pencereleri yerel toprak sıcaklığıyla doğrulanmalıdır.
- Uygunluk modeli iklimsel benzerliktir; toprak, sulama ve piyasa modelin
  dışındadır.
- Bu araç karar desteğidir; çiftçinin ve yerel uzmanın yargısının yerine
  geçmez.
