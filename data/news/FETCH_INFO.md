# GDELT events pull

- pulled at: 2026-10-10 20:57:51 UTC
- range: 2026-01-01 to 2026-09-08 (exclusive), 15-minute export files from https://data.gdeltproject.org/gdeltv2/<slot>.export.CSV.zip
- files expected: 24000, found: 23999, missing (404): 1
- rows whose DATEADDED differs from their file's slot: 0
- filter: ActionGeo_CountryCode == UP; conflict = CAMEO root 18/19/20; aerial = CAMEO 195x
- timestamp: DATEADDED (when the record entered GDELT), floored to the hour, UTC

Missing files per day (days with any):

- 2026-05-09: 1
