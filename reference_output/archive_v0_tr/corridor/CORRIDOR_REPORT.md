# FieldShift göç koridoru (bileşen A) ve uygunluk modeli (bileşen D)

Veri kaynağı: pilot_sites_offline. Koridor ızgarası önbellekte yok veya indirilemedi (Bu iklim isteği önbellekte yok. İlk indirme için --online kullanın.). Paketteki iki pilot alanla çalışıldı.

Hücre: 2; CDL noktası: 50; senaryo: ssp245; referans [2015, 2024] → gelecek [2040, 2049].

## Model hazırlığı

- Tarım arazisi bulunan hücre: 2 (farklı iklimli: 2)
- Buğday görülen hücre: 2; buğdaysız tarım hücresi: 2
- Eğitildi: hayır
- Neden: Farklı iklimli hücre sayısı 2 < 12
- Neden: Buğday görülen hücre 2 < 3
- Neden: Buğdaysız tarım hücresi 2 < 3

## Hücre iklimi: referans → gelecek

| Hücre | Ort. sıcaklık (°C) | GDD0 | Haz–Tem Tmax (°C) | Ekim–Haz yağış (mm) |
|---|---|---|---|---|
| USOR03 | 12.9 → 13.8 | 4703 → 5049 | 29.7 → 30.8 | 353 → 377 |
| USKS01 | 15.2 → 16.3 | 5573 → 5958 | 33.2 → 34.2 | 615 → 622 |

## Yorum sınırları

- Etiket CDL uydu sınıflandırmasıdır; buğday olmayan tarım noktası 'yetişemez' anlamına gelmez, ekonomik tercih olabilir.
- Model iklim dışı etkenleri (toprak, sulama, piyasa) içermez; uygunluk iklimsel benzerliktir.
- Referans ve gelecek aynı NEX-GDDP ensemble kaynağındandır; ensemble ortalaması uç olayları yumuşatır.
- Kayma vektörü uygunluk ağırlıklı ağırlık merkezinin yer değiştirmesidir; buğdayın fiziksel taşınması değildir.
- Kutunun dışına kayış ölçülemez; koridor kutu sınırına dayanıyorsa kutu genişletilmelidir.
