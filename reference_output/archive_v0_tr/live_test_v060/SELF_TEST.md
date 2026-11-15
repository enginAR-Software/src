# FieldShift indirme ve veri kullanımı testi

Mod: live_network_empty_cache; sonuç: passed.

Canlı mod, mevcut ham dosyaları kullanmadan boş geçici dizinde indirir. Geçici veri test sonunda kaldırılır; DOI, sürüm, SHA-256 ve API bilgileri JSON kaydında kalır.

| Kontrol | Sonuç |
|---|---|
| pflux: gerçek indirme | passed |
| napeshm: gerçek indirme | passed |
| gerçek dosyadan ön işleme ve pilot analizi | passed |
| gerçek rotasyondan altı sezonluk plan | passed |
| NASA POWER historical: gerçek HTTPS indirme | passed |
| NASA POWER projection: gerçek HTTPS indirme | passed |
| aynı alan/sezon/örnekleme tarihi eşleştirmesi | passed |
| USDA CDL: ürün sınıflandırması ve kaynak yılı | passed |
