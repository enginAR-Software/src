# Ekonomi girdileri: iki yol

Paketle iki hazır girdi dosyası gelir. İkisinde de maliyetler aynıdır; fark,
verim ve fiyatın nereden geldiğidir.

| Dosya | Verim ve fiyat | Maliyet | İnternet |
|---|---|---|---|
| `config/economics_inputs.csv` (varsayılan) | Elle girilmiş resmî değerler: Kansas K-State KFMA 2020–2024, Oregon USDA NASS eyalet bülteni 2019–2023 | KFMA; OSU AEB 0064 | Gerekmez |
| `config/economics_inputs_nass.csv` | USDA NASS Quick Stats API: ilçe verimi (yoksa eyalet), eyalet fiyatı, 2014–2023 ortalaması | KFMA; OSU AEB 0064 | İlk koşuda gerekir |

Fosfor gübresi fiyatı, nadas maliyeti ve Oregon nadas kuralı
`config/economics.json` içindedir; her birinin kaynağı dosyada yazılıdır.

## Yol 1: Elle girilmiş resmî değerler

```bash
python3 -m fieldshift_data goal --offline
```

## Yol 2: NASS API

1. https://quickstats.nass.usda.gov/api adresine gidin ve "Request API Key"
   bağlantısıyla e-posta adresinizi girin. Anahtar e-postayla gelir ve
   ücretsizdir.
2. Terminalde anahtarı tanımlayın:

   ```bash
   export FIELDSHIFT_NASS_KEY=ANAHTARINIZ
   ```

   Kalıcı olması için aynı satırı `~/.bashrc` dosyasının sonuna ekleyin.
3. NASS verisini indirip kontrol edin:

   ```bash
   python3 -m fieldshift_data economics --online --inputs config/economics_inputs_nass.csv
   ```

   Her bölge ve ürün için `verim=..., fiyat=...` satırları görünmelidir.
4. Planı NASS değerleriyle hesaplayın:

   ```bash
   python3 -m fieldshift_data goal --offline --inputs config/economics_inputs_nass.csv
   ```

Bir değer iki kaynakta da varsa elle girilen değer NASS'ın önüne geçer.
API anahtarı önbelleğe ve kayıtlara yazılmaz.

Oregon için güncel NASS bezelye ve yazlık buğday verisi bulunamadı. Bu
ürünleri içeren planlar, kaynaklı değer girilene kadar hesaplanmaz.

## Hangisi daha doğru?

İki yol farklı soruları yanıtlar:

- **Yol 1 (KFMA):** Kansas'ta kayıt tutan gerçek çiftliklerin verim, fiyat
  ve giderleri. Hepsi aynı çiftliklerden geldiği için birbiriyle tutarlıdır.
- **Yol 2 (NASS):** Riley ve Umatilla ilçelerinin resmî verimleri. Yere daha
  özgüdür, ama giderleri başka bir kaynaktan gelir.

İkisini karşılaştırmak, sonucun girdilere ne kadar duyarlı olduğunu gösterir.
Jüriye bu karşılaştırmayı göstermek güçlü bir kanıttır.
