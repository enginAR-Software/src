# 0.9.0 genişletmeleri

Hepsi Preparation.md amacına bağlıdır; hiçbir verim, fiyat veya NDVI değeri uydurulmaz. Önbellek yoksa ilgili parça
"veri bekleniyor" olarak raporlanır ve nasıl tamamlanacağı yazılır.

## 1. Koridor parselleri (bileşen B)
`goal`, 2040–2049'da uygun (`suitable_future = 1`) olan koridor hücrelerindeki CDL noktalarını parsel yapar.
Koşul: 2019–2023'ün her yılı tarım ürünü sınıfı olmalı. Bölge = noktanın eyaleti (US Census sınırları);
ekim takvimi o hücrenin NASA iklimiyle hesaplanır. Ekonomi eyalet girdileriyle çalışır.
Kansas girdileri kaynaklı olarak pakette; diğer eyaletler için verim ve fiyat NASS anahtarıyla gelir.

0.8.0 ile indirilmiş koridor verisi nokta dizilerini saklamıyordu: bir kez `corridor --offline` çalıştırın.
Bu komut önbellekten okur, indirme yapmaz.

## 2. İklimden verim modeli (bileşenler C ve D): `yield-model --online`
- Veri: USDA NASS Quick Stats ilçe verimleri, 2014–2023, en az 3 yıl. "998" birleşik ilçe satırı ile gizli (D) değerler atlanır.
- İlçe merkezleri: `assets/county_centroids.csv` (US Census sınırlarından). Her ilçe 1°'lik koridor hücresine düşer; hücre verimi, içindeki ilçelerin ortalamasıdır.
- Model: ridge regresyon. Özellikler beş iklim özelliği ile ortalama sıcaklığın ve Haziran–Temmuz maksimum sıcaklığının kareleridir.
- Doğrulama: mekânsal blok çapraz doğrulama (R², RMSE, yalnız-ortalama RMSE).
- Çarpan = tahmin(2040–2049) / tahmin(2015–2024), [0,5; 1,5] aralığına kırpılır.
- `goal` yalnız CV R² ≥ 0,2 olan ürünlerin çarpanlarını kullanır. Gelecek iklimi eğitim aralığı dışında kalan hücreler de dışarıda tutulur.
- Çıktı: koridor parselleri için `most_profitable_2040` stratejisi, yani 2040'ların verimiyle en kârlı plan. Rapor ve arayüz bugünkü planla farkını gösterir.

## 3. Rotasyon etkisi ve fiyat senaryoları (bileşen C)
- Oregon USOR03: buğdaydan sonra kışlık buğday verimi ×0,618 (Maaz ve diğ. 2017, Tablo 4; hesap `config/economics.json` içinde).
- Fiyat senaryoları: kaynak fiyatların ×0,8 / ×1,0 / ×1,2 hali. Sonuç `price_sensitivity.csv` dosyasında; arayüzde "Çiftçi öncelikleri" sekmesinde.

## 4. Uydu göstergesi: `satellite --online`
- Kaynak: ORNL DAAC MODIS Web Service, MOD13Q1 v061, 250 m, 16 günlük NDVI. Anahtar gerekmez; istek başına en fazla 10 tarih alınır.
- Her parsel için bir yıllık eğri çıkarılır (varsayılan 2023). Hesaplananlar: tepe NDVI ve tarihi, yeşil dönem, çıplak toprak günleri (NDVI < 0,25).
- Fenoloji denetimi: tepe ayı, CDL'nin o yıl verdiği ürünün tipik tepe aylarıyla karşılaştırılır (`config/phenology.json`, kaynaklı). Böylece uydu, CDL etiketini bağımsız olarak doğrular.
- Deneme için: `satellite --online --only pilot` (30 parsel, yaklaşık 90 istek). Tüm parseller birkaç dakika sürer.

## Sınırlar
- 250 m MODIS pikseli küçük tarlalarda komşu alanı da görür.
- Verim modeli hücre (≈ 1°) ölçeğindedir; parsel içi toprak farkını görmez.
- İlçe verimleri teknoloji eğilimi içerir; model iklim dışı farkları da iklime yükleyebilir.
