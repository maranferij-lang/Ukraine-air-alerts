# Oblast boundaries for the forecast map

`ukraine_oblasts.geojson` (about 59 KB, 27 units: our 24 plus Luhansk, Crimea and Sevastopol) is what `scripts/forecast_map.py` draws. It is derived, by `scripts/build_geo.py`, from
**Natural Earth, "Admin 1 - States, Provinces", 1:10m** (`ne_10m_admin_1_states_provinces.geojson`).

- **Source:** https://github.com/nvkelso/natural-earth-vector, file `geojson/ne_10m_admin_1_states_provinces.geojson`, at commit `ca96624a56bd078437bca8184e78163e5039ad19`
  (`https://raw.githubusercontent.com/nvkelso/natural-earth-vector/ca96624a56bd078437bca8184e78163e5039ad19/geojson/ne_10m_admin_1_states_provinces.geojson`; 40,726,851 bytes, not committed).
  SHA-256 of that file: `22d0e3ad85eb3e27f17cabf8ba2d50e554fbc27a87796ff891d958185da62fb5`; `build_geo.py` refuses any other file.
- **Licence: public domain.** Natural Earth's terms (https://www.naturalearthdata.com/about/terms-of-use/, and `LICENSE.md` in the repository above): "All versions of Natural Earth raster +
  vector map data found on this website are in the public domain. You may use the maps in any manner, including modifying the content and design, electronic dissemination, and
  offset printing." No permission or credit is needed; if you cite it: "Made with Natural Earth."
- **What was changed:** only the 27 Ukrainian units were kept, picked by ISO 3166-2 code (UA-05 ... UA-77); coordinates were simplified (Douglas-Peucker, 0.012 degrees, about 1.3 km; shared
  borders are simplified once so neighbours keep the same line) and rounded to 3 decimals (20,117 vertices became 3,270); a label point was added to each unit; the attributes were cut down to the
  ISO code, the file's three name fields and our unit name.
- **Crimea and Sevastopol:** Natural Earth's default file files them under Russia (its de facto view) while giving them Ukraine's ISO codes UA-43 and UA-40. They are taken here by that code, i.e.
  as units of Ukraine within its internationally recognised borders, and drawn grey and hatched with the words "no data" (the alert data do not cover them; Luhansk is the permanent-alert
  oblast the model leaves out). Nothing else about the file's borders was altered; they are generalised, not survey lines.
- **Matching to our 24 units** (`OURS` in `scripts/forecast_map.py`) is by ISO code and is checked by `python scripts/check_forecast_map.py`: each code against the feature's own name fields,
  completeness, no duplicates, and that our 24 are the 24 units in the alert data.

To rebuild: download the file above, then `python scripts/build_geo.py PATH_TO_THE_FILE`.
