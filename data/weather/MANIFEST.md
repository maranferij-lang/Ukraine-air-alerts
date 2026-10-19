# Manifest: hourly weather per unit centre

Produced by `scripts/fetch_weather.py` from the Open-Meteo Historical Weather API (archive-api.open-meteo.com, ERA5-based; free non-commercial endpoint). The CSVs are git-ignored; re-download them with the script and compare the SHA-256 prefixes below (the API may revise recent hours).

- range requested: 2022-03-15 to 2026-10-17, UTC; variables requested: wind_speed_10m, cloud_cover, precipitation, visibility
- **visibility: the API accepts the variable but returns null for every hour (the 'missing values' column is exactly that column), so it is not used**; features use wind, cloud cover and precipitation
- precipitation is the sum of the hour that ends at the stamp; wind in m/s; cloud cover in %

| unit | hours | missing values | SHA-256 of the file (prefix) |
|---|---|---|---|
| Cherkaska oblast | 40272 | 40272 | cfa97f98bd5d6d60 |
| Chernihivska oblast | 40272 | 40272 | 0390b42678272711 |
| Chernivetska oblast | 40272 | 40272 | 4ab85b4451303fde |
| Dnipropetrovska oblast | 40272 | 40272 | aa0e1afaebc7027e |
| Donetska oblast | 40272 | 40272 | f8103e9e9e7b1e70 |
| Ivano-Frankivska oblast | 40272 | 40272 | 284d4b09f817b931 |
| Kharkivska oblast | 40272 | 40272 | 0a27dd818ee425e5 |
| Khersonska oblast | 40272 | 40272 | bf14ac0815559c48 |
| Khmelnytska oblast | 40272 | 40272 | 8ce9f4031e837a1c |
| Kirovohradska oblast | 40272 | 40272 | 4039e735cb1a3727 |
| Kyiv City | 40272 | 40272 | e0b82de06d56371f |
| Kyivska oblast | 40272 | 40272 | e0b82de06d56371f |
| Lvivska oblast | 40272 | 40272 | a90ff3422259bed6 |
| Mykolaivska oblast | 40272 | 40272 | de270b9651a6f3b1 |
| Odeska oblast | 40272 | 40272 | 426cfebca5c57ee2 |
| Poltavska oblast | 40272 | 40272 | 0fbdb77db15daf11 |
| Rivnenska oblast | 40272 | 40272 | 4d964d95384d8935 |
| Sumska oblast | 40272 | 40272 | 83b6ba835213ef64 |
| Ternopilska oblast | 40272 | 40272 | fc645dae8db561a1 |
| Vinnytska oblast | 40272 | 40272 | cba65d1ad848d044 |
| Volynska oblast | 40272 | 40272 | 2d66a4dc55c257a7 |
| Zakarpatska oblast | 40272 | 40272 | 97ee25b41456b889 |
| Zaporizka oblast | 40272 | 40272 | c50bcd5beea08fe2 |
| Zhytomyrska oblast | 40272 | 40272 | 992a26941e2c4ff6 |
