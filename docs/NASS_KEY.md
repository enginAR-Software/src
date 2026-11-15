# Getting a USDA NASS Quick Stats key

A key is needed only for state yields and prices outside Kansas (`economics --online`) and for the climate-to-yield model (`yield-model --online`). The demo and the pilot results do not need one.

1. Request a free key at https://quickstats.nass.usda.gov/api (name and e-mail; the key arrives by e-mail).
2. Set it for the current terminal session:
   ```bash
   export FIELDSHIFT_NASS_KEY=your_key          # Linux / macOS
   set FIELDSHIFT_NASS_KEY=your_key             # Windows cmd
   ```
3. Run:
   ```bash
   python3 -m fieldshift_data economics --online
   python3 -m fieldshift_data yield-model --online
   python3 -m fieldshift_data goal --offline
   ```

The key is added only to the request URL. It is never written to the cache, the receipts or the reports. Responses are cached under `data/raw/nass/` with SHA-256 receipts, so later runs work with `--offline`.
