# FieldShift arayüzü (0.9.0)

```bash
python3 -m fieldshift_data app          # en son goal çıktısından; yoksa önce goal çalıştırır
python3 -m fieldshift_data app --open   # oluşturup varsayılan tarayıcıda açar
```

Çıktı `outputs/app_<kimlik>/FieldShift_App.html` dosyasıdır. Tek dosyadır,
internet gerektirmez ve sunucu istemez. Dosyayı çift tıklayarak açabilir, USB
bellekle taşıyabilir ya da sunumda kullanabilirsiniz.

## Ekranlar

| Bölüm | Ne yapar | Amaçtaki karşılığı |
|---|---|---|
| Üstteki A–E çipleri | Bileşen durumları; üzerine gelince ayrıntı | Bütün amaç |
| Harita: ABD / Göç koridoru | Pilot alanlar. Koridor indirildiyse buğday uygunluğu (2015–2024 ↔ 2040–2049) ve kayma oku | A, D |
| Harita: Kansas / Oregon parselleri | Her kare bir parsel; renk, seçilen yılda önerilen ürün | B |
| Parsel planı | Uydu geçmişi; önerilen, buğday ağırlıklı ve mevcut planlar; yıl yıl ürün, ekim tarihi, kâr ve P; "Neden bu plan?"; iklimle takvim kayması; riskler | C, E |
| Bu tarihte ne ekilir? | Seçilen günde hangi parselde ekim zamanı olduğu | E |
| Çiftçi öncelikleri | Ürün seçimi, en az buğday yılı, ardışık ürün sınırı, ±%20 fiyat senaryosu, Oregon nadas kuralı; bütün planlar anında yeniden hesaplanır | C, challenge'daki "çiftçi öncelikleri" |
| Göç | Kayma mesafesi ve yönü, uygun hücre sayısı, model doğruluğu (AUC); pilot alanlarda iklim kayması | A, D |
| Kaynaklar | Her verim, fiyat ve maliyetin kaynağı ve notlar | Kanıt ve şeffaflık |

## Doğruluk

Tarayıcıdaki rotasyon hesabı (`fieldshift_data/app_optimizer.js`),
`economics.py` ile aynı kuralları uygular. `tests/test_app.py` testi, 30
parselin 3 stratejisinde (90 sonuç) iki hesabın aynı diziyi ve aynı kârı
bulduğunu Node.js ile doğrular.

±%20 fiyat senaryosu bir duyarlılık varsayımıdır, tahmin değildir.

## Göç haritası

Koridor verisi yokken harita yalnız pilot alanları gösterir. Göç haritasını
doldurmak için şu üç komutu sırayla çalıştırın:

```bash
python3 -m fieldshift_data corridor --online
python3 -m fieldshift_data goal --offline
python3 -m fieldshift_data app
```

## Gömülü bileşenler

`fieldshift_data/assets/` içindekilerin lisansları `LICENSES.txt`
dosyasındadır:

- **d3 v7:** ISC lisansı.
- **ABD eyalet sınırları:** US Census Bureau 2017 sınır dosyalarından
  türetilmiş us-atlas verisi; kamu malı, ISC lisansı.

## 0.9.0 eklemeleri
- Parsel kartında **İklim değişince verim**: koridor hücresinin 2040'lar verim çarpanları ve o verimlerle en kârlı plan. Bunun için `yield-model` çalışmış olmalı.
- Parsel kartında **Uydudan bitki gelişimi**: MODIS NDVI eğrisi, tepe zamanı, çıplak toprak süresi ve CDL etiket denetimi. Bunun için `satellite` çalışmış olmalı.
- "Koridor parselleri" görünümü: göç koridorundaki parseller 5. yakınlaştırma düzeyinden itibaren çizilir.
