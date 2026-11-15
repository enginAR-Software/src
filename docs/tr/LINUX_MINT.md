# Linux Mint kurulumu ve kullanım

## Gereksinimler

- Python 3.10 veya üzeri.
- ZIP'i açmak için dosya yöneticisi veya `unzip`.
- Paket içindeki gerçek kaynak dosyalarıyla çalışırken internet gerekmez.
- `fetch` komutunda HTTPS internet bağlantısı gerekir.
- İlk sürümde harita, QGIS veya Python paket kurulumu gerekmez.

Başlangıç paketi yaklaşık 6 MB ham veri içerir. Çıktılar gözlem ve kaynak
tablolarını da içerdiği için daha büyüktür. Her koşu ayrı saklanır; denemeler
çoğaldıkça eski çıktı klasörlerini ihtiyacınıza göre arşivleyebilirsiniz.

```bash
sudo apt update
sudo apt install python3 unzip
unzip FieldShiftData_0_8_0.zip
cd FieldShiftData_0_8_0
python3 -m fieldshift_data verify
bash run_data.sh
```

Pilot karşılaştırmaları için:

```bash
python3 -m fieldshift_data analyze --offline
```

Yeni ZIP'i önceki proje klasörünün üstüne açmak yerine yeni bir klasöre
çıkarın. Önceki `outputs` klasörünüzü koruyun; eski koşular yeni sürümdeki
rapor alanlarını otomatik kazanmaz. Güncel analizi yeni sürümle yeniden çalıştırın.

Komutları ZIP dosyasının olduğu dizinde başlatın. `unzip` yerine dosya
yöneticisinde "Buraya çıkart" kullanılabilir; sonra `FieldShiftData` klasöründe
terminal açın. Mevcut aynı adlı proje klasörü varsa önce ZIP'i ayrı bir
klasöre açın; kendi değişikliklerinizin üzerine yazmayın.

## İsteğe bağlı sanal ortam

Üçüncü taraf bağımlılık olmadığı için zorunlu değildir. Kullanmak isterseniz:

```bash
sudo apt install python3-venv
python3 -m venv .venv
source .venv/bin/activate
python -m unittest discover -s tests -v
python -m fieldshift_data run --offline
```

Sanal ortamdan çıkış `deactivate`. `run_data.sh`, `.venv/bin/python` varsa onu
kullanır. `sudo pip`, sistem Python'unu değiştirme veya ek paket indirme gerekmez.

## Sorun giderme

| Durum | Kontrol |
|---|---|
| `No module named fieldshift_data` | `FieldShiftData` proje klasöründe terminal açın |
| Dosya eksik / metadata eksik | Tam ZIP'i açın veya `python3 -m fieldshift_data fetch` çalıştırın |
| Dosya bütünlüğü uyuşmuyor | İlgili dosyayı düzenlemeyin; farklı bir yere ayırıp fetch ile yeniden indirin |
| HTTP/bağlantı hatası | `run --offline` için hazır dosyaları kullanın; fetch için ağ bağlantısını kontrol edin |
| SSL sertifika hatası | Sistem tarihi ve sertifika paketlerini kontrol edin; TLS doğrulamasını kapatmayın |
| CSV sayıları metin görünüyor | Calc içe aktarımında UTF-8, virgül ve noktalı ondalığa uygun dil seçin |
| Çıktı klasöründe `status: failed` | Bu koşuyu tamamlanmış sonuç saymayın; manifestteki hata açıklamasını inceleyin |

## Taşıma

Projeyi başka bilgisayara taşırken kaynak kodu ve `data/raw` klasörünü birlikte
taşıyın. `.venv` varsa kopyalamak yerine yeni bilgisayarda oluşturun. Geçmiş
hesaplamalar için `outputs` klasörünü ayrıca taşıyın. Çalışma devam ederken
SQLite dosyasını taşımayın.

Linux/Python 3.12 üzerinde, temiz kopya ve yeni sanal ortamda doğrulandı.
Linux Mint masaüstü üzerinde doğrudan çalıştırma ayrıca doğrulanmadı.

## Gerçek ürün sınıflandırması

```bash
python3 -m fieldshift_data cropland --offline
```

Varsayılan USDA ve NASA yanıtları pakettedir. Farklı yıl/alan için
`--online` kullanın. Ayrıntı: `docs/CROPLAND.md`.
