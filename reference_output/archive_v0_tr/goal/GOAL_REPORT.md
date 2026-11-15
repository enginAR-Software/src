# FieldShift amaç raporu

**Proje amacı (Preparation.md):** Kuzey Amerika'da yetiştirilen buğdayın iklim değişikliğine bağlı olarak ve çeşitli verilere bakılarak göç edeceği en uygun bölgeyi kestirmek; izlediği yol boyunca parsellere ayrılan bölgeler için ekonomik anlamda en verimli ekim rotasyonunu hesaplayan matematiksel bir model eğitmek; çiftçiye her yıl ne zaman ve hangi ürünü ekeceğini söyleyerek işini kolaylaştırmak.

## Amaç bileşenlerinin durumu

| Bileşen | Durum | Üretilen | Tamamlamak için |
|---|---|---|---|
| A. Buğdayın iklim değişikliğiyle kayacağı en uygun bölge | Veri bekleniyor | Hücre bazında referans → gelecek iklim farkı hesaplandı; kayma vektörü için eğitilmiş model gerekli | `python3 -m fieldshift_data corridor --online (koridor ızgarasını NASA ve USDA'dan indirir)` |
| B. Yol boyunca parsellere ayırma | Çalışıyor | 30 parsel (tüm yılları tarım sınıfı olan CDL noktaları); 20 nokta tarım dışı | `Koridor indirildiğinde parseller koridor hücrelerinden de üretilebilir` |
| C. Parsel başına ekonomik açıdan en verimli rotasyon | Çalışıyor | Kâr optimizasyonu ve 3 strateji hesaplandı | `config/economics_inputs.csv'yi kaynaklarıyla doldurun veya FIELDSHIFT_NASS_KEY ile economics --online çalıştırın` |
| D. Eğitilmiş matematiksel model | Eğitim verisi yetersiz | Farklı iklimli hücre sayısı 2 < 12; Buğday görülen hücre 2 < 3; Buğdaysız tarım hücresi 2 < 3 | `corridor --online ile en az 12 farklı iklimli hücre` |
| E. Her yıl ne ve ne zaman ekileceği | Çalışıyor | Ekim gereken 54 bölge-ürün-yılın 30 tanesinde tam pencere, 7 tanesinde yalnız başlangıç veya düşük güven; kuralı olmayan ürün: Dbl Crop WinWht/Soybeans, Triticale | `Kaynak eşikleri config/crop_calendar.json'da; yerel toprak sıcaklığıyla doğrulayın` |

## Ekim pencereleri (E)

Kışlık buğdayda plan yılı hasat yılıdır; ekim önceki sonbahardadır.

| Bölge | Yıl | Ürün | Başlangıç | Bitiş | Durum | Dayanak |
|---|---|---|---|---|---|---|
| USKS01 | 2027 | Alfalfa | — | — | ekim_yok |  |
| USKS01 | 2027 | Corn | 2027-03-23 | 2027-07-27 | ok | NASA projeksiyonu 2027 |
| USKS01 | 2027 | Dbl Crop WinWht/Soybeans | — | — | kural_yok |  |
| USKS01 | 2027 | Sorghum | 2027-04-14 | 2027-08-01 | ok | NASA projeksiyonu 2027 |
| USKS01 | 2027 | Soybeans | 2027-04-06 | 2027-07-17 | ok | NASA projeksiyonu 2027 |
| USKS01 | 2027 | Winter Wheat | 2026-10-11 | 2026-10-25 | ok | NASA projeksiyon normali 2015–2024; 24 gün (Aralık sonu) yılların %80'inden azından |
| USKS01 | 2028 | Alfalfa | — | — | ekim_yok |  |
| USKS01 | 2028 | Corn | 2028-03-24 | 2028-07-26 | ok | NASA projeksiyon normali 2015–2024 |
| USKS01 | 2028 | Dbl Crop WinWht/Soybeans | — | — | kural_yok |  |
| USKS01 | 2028 | Sorghum | 2028-04-22 | 2028-07-31 | ok | NASA projeksiyon normali 2015–2024 |
| USKS01 | 2028 | Soybeans | 2028-04-06 | 2028-07-16 | ok | NASA projeksiyon normali 2015–2024 |
| USKS01 | 2028 | Winter Wheat | 2027-10-11 | 2027-10-25 | ok | NASA projeksiyon normali 2015–2024; 24 gün (Aralık sonu) yılların %80'inden azından (gerçek yıl eksik: 2027 Ağustos–Aralık günleri eksik (5 gün)) |
| USOR03 | 2027 | Alfalfa | — | — | ekim_yok |  |
| USOR03 | 2027 | Fallow/Idle Cropland | — | — | ekim_yok |  |
| USOR03 | 2027 | Other Hay/Non Alfalfa | — | — | ekim_yok |  |
| USOR03 | 2027 | Peas | 2027-01-26 | — | dusuk_guven | NASA projeksiyonu 2027 |
| USOR03 | 2027 | Spring Wheat | 2027-01-21 | — | dusuk_guven | NASA projeksiyonu 2027 |
| USOR03 | 2027 | Triticale | — | — | kural_yok |  |
| USOR03 | 2027 | Winter Wheat | 2026-10-06 | 2026-10-20 | ok | NASA projeksiyon normali 2015–2024; 24 gün (Aralık sonu) yılların %80'inden azından |
| USOR03 | 2028 | Alfalfa | — | — | ekim_yok |  |
| USOR03 | 2028 | Fallow/Idle Cropland | — | — | ekim_yok |  |
| USOR03 | 2028 | Other Hay/Non Alfalfa | — | — | ekim_yok |  |
| USOR03 | 2028 | Peas | 2028-02-07 | — | dusuk_guven | NASA projeksiyon normali 2015–2024 |
| USOR03 | 2028 | Spring Wheat | — | — | pencere_yok | NASA projeksiyon normali 2015–2024 |
| USOR03 | 2028 | Triticale | — | — | kural_yok |  |
| USOR03 | 2028 | Winter Wheat | 2027-10-06 | 2027-10-20 | ok | NASA projeksiyon normali 2015–2024; 24 gün (Aralık sonu) yılların %80'inden azından (gerçek yıl eksik: 2027 Ağustos–Aralık günleri eksik (5 gün)) |

**Kaynak kaydıyla kontrol:** Oregon USOR03 kışlık buğdayı 15 Ekim 2018'de ekilmiş. Hesaplanan 2019 hasat yılı penceresi: 2018-10-06 – 2018-10-20 (NASA projeksiyon normali 2015–2024; 24 gün (Aralık sonu) yılların %80'inden azından (gerçek yıl eksik: 2018 Ağustos–Aralık günleri eksik (4 gün))).

## Parsel stratejileri (C)

30 parsel; 20 nokta tarım dışı olduğu için parsel sayılmadı.

| Bölge | Strateji | Örnek dizi | Toplam kâr (USD/acre) | Durum / eksik |
|---|---|---|---|---|
| USKS01 | bugday_agirlikli | Sorghum → Sorghum → Winter Wheat → Sorghum → Winter Wheat → Winter Wheat | -11 | ok:  |
| USKS01 | en_karli | Sorghum → Sorghum → Winter Wheat → Sorghum → Sorghum → Winter Wheat | 49 | ok:  |
| USKS01 | mevcut | Soybeans → Soybeans → Soybeans → Soybeans → Sorghum → Soybeans | -184 | ok:  |
| USOR03 | bugday_agirlikli | Winter Wheat → Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland → Winter Wheat → Winter Wheat | 186 | ok:  |
| USOR03 | en_karli | Fallow/Idle Cropland → Winter Wheat → Winter Wheat → Fallow/Idle Cropland → Winter Wheat → Winter Wheat | 186 | ok:  |
| USOR03 | mevcut | Winter Wheat → Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland | 71 | ok:  |

Bütün parseller ve yıllar: `parcel_plans.csv`, `parcel_strategies.csv`; harita için `parcels.geojson`.

## P kaldırması (toprak besin dengesi kısıtı)

| Ürün | kg P/ha/yıl (medyan) | Sistem | Aralık |
|---|---:|---:|---|
| Alfalfa | 27.0 | 6 | 10.7–37.2 |
| Barley | 26.5 | 4 | 25.7–31.2 |
| Canola | 3.1 | 2 | 2.7–3.5 |
| Corn | 31.5 | 27 | 8.7–70.8 |
| Sorghum | 17.0 | 1 | 17.0–17.0 |
| Soybeans | 18.8 | 22 | 3.1–27.0 |
| Spring Wheat | 30.5 | 3 | 13.0–30.7 |
| Winter Wheat | 12.0 | 16 | 1.0–38.1 |

## Yorum sınırları

- Mevcut rotasyon, 2018–2023 CDL dizisinin döngüsel devamı olarak varsayılır.
- Bölge içindeki parseller aynı ilçe verimi, fiyatı ve maliyetini paylaşır; parsel farkı yalnız geçmiş ürün sırasından gelir.
- Rotasyonun verime etkisi (ör. nadasın su biriktirmesi, baklagilin azot katkısı) yalnız kaynaklı rotation_effects satırlarıyla hesaba girer; varsayılan listede yoktur.
- Ekim pencereleri hava sıcaklığını toprak sıcaklığına vekil alır ve NEX-GDDP ensemble ortalamasına dayanır.
- Bu araç karar desteğidir; çiftçinin ve yerel uzmanın yargısının yerine geçmez.
